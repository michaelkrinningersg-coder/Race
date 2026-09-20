"""Tests fuer die Popularitaet (Punkt 5).

Sie bewegt die Sponsorenangebote aus GDD 10 und waechst aus Siegen,
Podien und Poles. Abgestimmt: gestreut, aber *nicht* nach Ligastaerke.
"""

from __future__ import annotations

import statistics

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import sponsoren as sp
from rennmanager.kern import welt as kw
from rennmanager.kern.popularitaet import Popularitaet
from rennmanager.kern.wertung import Rennergebnis
from rennmanager.kern.zufall import Seedquelle

SEED = 21


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def welt(k) -> kw.Welt:
    return kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=10)


@pytest.fixture(scope="module")
def gestreut(k, welt) -> Popularitaet:
    p = Popularitaet(k)
    p.anfang(tuple(f.nummer for f in welt.fahrer), Seedquelle(SEED))
    return p


def test_alle_fahrer_bekommen_einen_anfangswert(gestreut, welt) -> None:
    assert len(gestreut.werte) == len(welt.fahrer)
    assert all(wert > 0 for wert in gestreut.werte.values())


def test_die_popularitaet_haengt_nicht_an_der_ligastaerke(gestreut, welt, k) -> None:
    """Abgestimmt: Bekanntheit ist nicht dasselbe wie Schnelligkeit."""
    oben = [gestreut.stand(f.nummer) for f in welt.fahrer if f.liga == 1]
    unten = [gestreut.stand(f.nummer) for f in welt.fahrer if f.liga == 10]
    # Dieselbe Verteilung - die Mittelwerte duerfen sich kaum unterscheiden.
    assert statistics.mean(oben) == pytest.approx(statistics.mean(unten), rel=0.20)


def test_die_streuung_ist_breit(gestreut, k) -> None:
    werte = list(gestreut.werte.values())
    mittel = k.wert("popularitaet", "mittelwert")
    breite = k.wert("popularitaet", "anfang_streuung")
    assert min(werte) < mittel * (1.0 - breite * 0.9)
    assert max(werte) > mittel * (1.0 + breite * 0.9)


def test_der_gleiche_seed_ergibt_dieselbe_verteilung(k, welt) -> None:
    nummern = tuple(f.nummer for f in welt.fahrer)
    erste, zweite = Popularitaet(k), Popularitaet(k)
    erste.anfang(nummern, Seedquelle(SEED))
    zweite.anfang(nummern, Seedquelle(SEED))
    assert erste.werte == zweite.werte


# --- Wachstum -------------------------------------------------------------
def test_sieg_podium_und_pole_zaehlen_nebeneinander(k) -> None:
    einstellung = k.wert("popularitaet")
    p = Popularitaet(k)
    assert p.zuwachs(Rennergebnis(0, 1, 1)) == (
        einstellung["je_sieg"] + einstellung["je_podium"] + einstellung["je_pole"]
    )
    assert p.zuwachs(Rennergebnis(0, 3, 9)) == einstellung["je_podium"]
    assert p.zuwachs(Rennergebnis(0, 9, 1)) == einstellung["je_pole"]
    assert p.zuwachs(Rennergebnis(0, 12, 12)) == 0


def test_ein_wochenende_schreibt_dem_ganzen_feld_gut(k) -> None:
    p = Popularitaet(k)
    p.setze(0, 10_000)
    p.setze(1, 10_000)
    p.verbuche_wochenende([Rennergebnis(0, 1, 1), Rennergebnis(1, 20, 20)])
    assert p.stand(0) > 10_000
    assert p.stand(1) == 10_000


def test_die_popularitaet_bleibt_auf_der_skala(k) -> None:
    p = Popularitaet(k)
    groesster = k.wert("skala", "maximum")
    p.setze(0, groesster)
    for _ in range(50):
        p.verbuche_wochenende([Rennergebnis(0, 1, 1)])
    assert p.stand(0) == groesster


# --- Wirkung auf die Sponsoren (GDD 10) -----------------------------------
def test_der_mittelwert_laesst_die_betraege_wie_gdd_10_sie_nennt(k) -> None:
    p = Popularitaet(k)
    p.setze(0, k.wert("popularitaet", "mittelwert"))
    assert p.faktor(0) == pytest.approx(1.0)


def test_bekannt_bringt_mehr_unbekannt_weniger(k) -> None:
    """Abgestimmt: bis zu 25 Prozent in beide Richtungen."""
    max_anteil = k.wert("popularitaet", "max_anteil_sponsor")
    mittel = k.wert("popularitaet", "mittelwert")
    p = Popularitaet(k)
    p.setze(0, 0)
    p.setze(1, 2 * mittel)
    assert p.faktor(0) == pytest.approx(1.0 - max_anteil)
    assert p.faktor(1) == pytest.approx(1.0 + max_anteil)
    # Weiter hoch geht es nicht.
    p.setze(2, k.wert("skala", "maximum"))
    assert p.faktor(2) == pytest.approx(1.0 + max_anteil)


def test_die_angebote_folgen_der_popularitaet(k) -> None:
    mittel = sp.wuerfle_angebote(k, 10, 1, Seedquelle(1), 1.0)
    bekannt = sp.wuerfle_angebote(k, 10, 1, Seedquelle(1), 1.25)
    unbekannt = sp.wuerfle_angebote(k, 10, 1, Seedquelle(1), 0.75)
    for platz, angebote in mittel.items():
        for stelle, angebot in enumerate(angebote):
            assert bekannt[platz][stelle].grundbetrag > angebot.grundbetrag
            assert unbekannt[platz][stelle].grundbetrag < angebot.grundbetrag
            # Die Praemien haengen am Grundbetrag und wandern mit.
            assert bekannt[platz][stelle].praemie_sieg > angebot.praemie_sieg
