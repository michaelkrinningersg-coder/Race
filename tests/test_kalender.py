"""Tests fuer Kalender und Zeitmodell (GDD 2)."""

from __future__ import annotations

import datetime as dt
from collections import Counter

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import kalender as kl
from rennmanager.kern.kalender import Tagesart


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def saison(k) -> kl.Saison:
    return kl.erzeuge(k, 2026)


def test_erstes_rennen_ist_der_erste_sonntag_ab_dem_stichtag(k) -> None:
    """GDD 2: Erstes Rennen am ersten Sonntag ab 01.03."""
    for jahr in range(2026, 2041):
        erstes = kl.erstes_rennen(k, jahr)
        assert erstes.weekday() == k.wert("kalender", "rennen_wochentag")
        stichtag = dt.date(jahr, 3, 1)
        assert stichtag <= erstes < stichtag + dt.timedelta(days=7)


def test_zwanzig_rennen_alle_vierzehn_tage(saison, k) -> None:
    """GDD 2: 20 Rennen alle 14 Tage, das letzte 266 Tage nach dem ersten."""
    assert len(saison.renntage) == k.wert("kalender", "rennen_je_saison")
    abstaende = {
        (danach - davor).days
        for davor, danach in zip(saison.renntage, saison.renntage[1:], strict=False)
    }
    assert abstaende == {k.wert("kalender", "abstand_tage")}
    assert (saison.letztes_rennen - saison.erstes_rennen).days == 266


def test_letztes_rennen_liegt_ende_november(k) -> None:
    for jahr in range(2026, 2041):
        letztes = kl.erzeuge(k, jahr).letztes_rennen
        assert letztes.month == 11
        assert letztes.day >= 22


def test_zehn_nutzbare_tage_je_zyklus(saison, k) -> None:
    """GDD 2: Pro 14-Tage-Zyklus 10 nutzbare Tage."""
    erwartet = k.wert("kalender", "nutzbare_tage_je_zyklus")
    for rennen in range(2, len(saison.renntage) + 1):
        nutzbar = [tag for tag in saison.zyklus_vor(rennen) if tag.ist_nutzbar]
        assert len(nutzbar) == erwartet, f"Rennen {rennen}"


def test_rennwochenende_hat_reise_quali_und_rennen(saison) -> None:
    for renntag in saison.renntage:
        assert saison.tag(renntag).art is Tagesart.RENNEN
        assert saison.tag(renntag - dt.timedelta(days=1)).art is Tagesart.QUALIFYING
        assert saison.tag(renntag - dt.timedelta(days=2)).art is Tagesart.REISE
        assert saison.tag(renntag - dt.timedelta(days=3)).art is Tagesart.REISE


def test_qualifying_ist_samstag_und_rennen_sonntag(saison, k) -> None:
    """GDD 2: Qualifying Samstag, Rennen Sonntag."""
    for renntag in saison.renntage:
        assert renntag.weekday() == k.wert("kalender", "rennen_wochentag")
        quali = renntag - dt.timedelta(days=1)
        assert quali.weekday() == k.wert("kalender", "qualifying_wochentag")


def test_saison_geht_ueber_das_ganze_jahr(saison) -> None:
    assert saison.tage[0].datum == dt.date(2026, 1, 1)
    assert saison.tage[-1].datum == dt.date(2026, 12, 31)
    assert len(saison.tage) == 365


def test_vorsaison_und_nachsaison_sind_lang_genug(k) -> None:
    """GDD 2 nennt "rund 59-65" Tage Vorsaison und "rund 33-39" Nachsaison.

    Die tatsaechliche Spanne ist 58 bis 66 beziehungsweise 33 bis 40: Der
    Wochentag des 1. Maerz verschiebt das erste Rennen um bis zu sechs
    Tage, und in einem Schaltjahr kommt einer dazu. Das GDD sagt "rund",
    die Abweichung von einem Tag an beiden Enden ist also gedeckt.
    """
    for jahr in range(2026, 2051):
        saison = kl.erzeuge(k, jahr)
        vorsaison = (saison.erstes_rennen - dt.date(jahr, 1, 1)).days
        nachsaison = (dt.date(jahr, 12, 31) - saison.letztes_rennen).days
        assert 58 <= vorsaison <= 66, f"{jahr}: {vorsaison}"
        assert 33 <= nachsaison <= 40, f"{jahr}: {nachsaison}"
        # Vor- und Nachsaison ergeben zusammen immer dasselbe Jahr.
        assert vorsaison + nachsaison + 266 == (365 + (jahr % 4 == 0)) - 1


def test_vorsaison_ist_voll_nutzbar(saison) -> None:
    """Bis auf das erste Rennwochenende selbst."""
    vor = [tag for tag in saison.tage if tag.datum < saison.erstes_rennen]
    unnutzbar = [tag for tag in vor if not tag.ist_nutzbar]
    # Nur die drei Tage des ersten Rennwochenendes vor dem Renntag.
    assert len(unnutzbar) == 3


def test_nachsaison_ist_voll_nutzbar(saison) -> None:
    nach = [tag for tag in saison.tage if tag.datum > saison.letztes_rennen]
    assert all(tag.ist_nutzbar for tag in nach)
    assert len(saison.nachsaison) == len(nach)


def test_jeder_tag_gehoert_hoechstens_zu_einem_rennen(saison) -> None:
    gezaehlt = Counter(tag.rennen for tag in saison.tage if tag.rennen)
    assert sorted(gezaehlt) == list(range(1, len(saison.renntage) + 1))


def test_naechster_renntag(saison) -> None:
    assert saison.naechster_renntag(dt.date(2026, 1, 1)) == saison.erstes_rennen
    assert saison.rennnummer_nach(dt.date(2026, 1, 1)) == 1
    assert saison.naechster_renntag(saison.erstes_rennen) == saison.erstes_rennen
    nach_dem_letzten = saison.letztes_rennen + dt.timedelta(days=1)
    assert saison.naechster_renntag(nach_dem_letzten) is None


def test_tag_ausserhalb_der_saison_meldet_fehler(saison) -> None:
    with pytest.raises(kl.KalenderFehler, match="nicht in der Saison"):
        saison.tag(dt.date(2025, 12, 31))
