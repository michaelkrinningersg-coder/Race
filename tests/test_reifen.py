"""Tests fuer den Reifenverschleiss (GDD 4)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import reifen as rf
from rennmanager.kern import strecke as st
from rennmanager.kern.auto import Auto

DISTANZ = 200_000.0


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


def mit(k, schluessel: str, wert: int, grund: int = 50_000) -> Auto:
    """Auto mit einem abweichenden Wert; Schluessel auch aus den Zusatzwerten."""
    werte = {f.schluessel: grund for f in k.faehigkeiten}
    zusatz = {rf.FLUESTERER: grund}
    if schluessel in werte:
        werte[schluessel] = wert
    else:
        zusatz[schluessel] = wert
    return Auto("TST", "Test", werte, zusatz)


# -- Zustand und Wirkung ----------------------------------------------------
def test_frische_reifen_kosten_nichts(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    assert rf.zustand(0.0) == 1.0
    assert rf.tempofaktor(k, auto, 0.0) == pytest.approx(1.0)
    assert rf.fehlerfaktor(k, auto, 0.0) == pytest.approx(1.0)


def test_abgefahrene_reifen_kosten_tempo(k) -> None:
    """GDD 4: Verschleiss senkt das Tempo und erhoeht die Fehlerquote."""
    auto = mit(k, rf.FLUESTERER, 0)
    einstellung = k.wert("reifen", "verschleiss")
    assert rf.tempofaktor(k, auto, 1.0) == pytest.approx(
        1.0 - einstellung["tempoverlust_voll"]
    )
    assert rf.fehlerfaktor(k, auto, 1.0) == pytest.approx(
        1.0 + einstellung["fehlerzuschlag_voll"]
    )


def test_wirkung_waechst_progressiv(k) -> None:
    """Entscheidung B: erst flach, letztes Drittel steil."""
    auto = mit(k, rf.FLUESTERER, 0)
    verlust = [1.0 - rf.tempofaktor(k, auto, anteil) for anteil in (0.25, 0.5, 0.75, 1.0)]
    # Die Zuwaechse werden von Stufe zu Stufe groesser.
    zuwaechse = [danach - davor for davor, danach in zip(verlust, verlust[1:], strict=False)]
    assert zuwaechse == sorted(zuwaechse)
    # Nach der Haelfte ist erst ein Viertel des Verlusts aufgelaufen.
    assert verlust[1] == pytest.approx(verlust[3] / 4, rel=0.01)


def test_zustand_bleibt_im_band(k) -> None:
    assert rf.zustand(-0.5) == 1.0
    assert rf.zustand(2.0) == 0.0


# -- Verschleissrate --------------------------------------------------------
def test_gute_reifenwerte_bauen_langsamer_ab(k) -> None:
    """Der Bereich ve traegt den Verschleiss - vor allem F10 und D14."""
    schwach = rf.verschleiss_je_meter(k, ka.gleichverteilt(k, 0), DISTANZ)
    stark = rf.verschleiss_je_meter(k, ka.gleichverteilt(k, 98_000), DISTANZ)
    assert stark < schwach


def test_verschleiss_trifft_die_vorgaben(k) -> None:
    einstellung = k.wert("reifen", "verschleiss")
    schwach = rf.verschleiss_je_meter(k, ka.gleichverteilt(k, 0), DISTANZ) * DISTANZ
    stark = (
        rf.verschleiss_je_meter(k, ka.gleichverteilt(k, k.wert("skala", "referenz")), DISTANZ)
        * DISTANZ
    )
    assert schwach == pytest.approx(einstellung["verschleiss_bei_null"], rel=0.01)
    assert stark == pytest.approx(einstellung["verschleiss_bei_referenz"], rel=0.01)


def test_schwache_reifen_sind_am_ende_hin(k) -> None:
    """Bei S = 0 sind die Reifen ueber die Distanz abgefahren."""
    auto = ka.gleichverteilt(k, 0)
    verschleiss = rf.verschleiss_je_meter(k, auto, DISTANZ) * DISTANZ
    assert rf.zustand(verschleiss) == 0.0


def test_lange_distanz_verteilt_den_verschleiss(k) -> None:
    """Die Rate ist auf die Renndistanz geeicht, nicht auf die Strecke."""
    auto = ka.gleichverteilt(k, 50_000)
    kurz = rf.verschleiss_je_meter(k, auto, 100_000.0) * 100_000.0
    lang = rf.verschleiss_je_meter(k, auto, 300_000.0) * 300_000.0
    assert kurz == pytest.approx(lang)


def test_wetter_und_strecke_skalieren_den_verschleiss(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    normal = rf.verschleiss_je_meter(k, auto, DISTANZ)
    hart = rf.verschleiss_je_meter(k, auto, DISTANZ, streckenfaktor_wert=1.3)
    heiss = rf.verschleiss_je_meter(k, auto, DISTANZ, wetterfaktor=1.4)
    assert hart == pytest.approx(normal * 1.3)
    assert heiss == pytest.approx(normal * 1.4)


# -- Reifenfluesterer -------------------------------------------------------
def test_fluesterer_senkt_die_wirkung_nicht_den_verschleiss(k) -> None:
    """Der Unterschied zu D14: D14 bremst den Abbau, der Fluesterer seine Folgen."""
    ohne = mit(k, rf.FLUESTERER, 0)
    mit_koennen = mit(k, rf.FLUESTERER, 100_000)

    # Gleicher Verschleiss ...
    assert rf.verschleiss_je_meter(k, ohne, DISTANZ) == pytest.approx(
        rf.verschleiss_je_meter(k, mit_koennen, DISTANZ)
    )
    # ... aber geringere Wirkung.
    assert rf.tempofaktor(k, mit_koennen, 1.0) > rf.tempofaktor(k, ohne, 1.0)
    assert rf.fehlerfaktor(k, mit_koennen, 1.0) < rf.fehlerfaktor(k, ohne, 1.0)


def test_fluesterer_daempft_hoechstens_wie_vorgegeben(k) -> None:
    max_daempfung = k.wert("reifen", "fluesterer", "max_daempfung")
    verlust_voll = k.wert("reifen", "verschleiss", "tempoverlust_voll")
    bester = mit(k, rf.FLUESTERER, 100_000)
    assert 1.0 - rf.tempofaktor(k, bester, 1.0) == pytest.approx(
        verlust_voll * (1.0 - max_daempfung), rel=0.02
    )


def test_d14_und_fluesterer_wirken_verschieden(k) -> None:
    """Beide helfen, aber an verschiedenen Stellen."""
    schoner = mit(k, "D14", 100_000)
    fluesterer = mit(k, rf.FLUESTERER, 100_000)

    # D14 senkt den Abbau ...
    assert rf.verschleiss_je_meter(k, schoner, DISTANZ) < rf.verschleiss_je_meter(
        k, fluesterer, DISTANZ
    )
    # ... der Fluesterer die Wirkung bei gleichem Abbau.
    assert rf.tempofaktor(k, fluesterer, 0.8) > rf.tempofaktor(k, schoner, 0.8)


# -- Streckenfaktor ---------------------------------------------------------
def test_streckenfaktor_trennt_enge_von_schnellen_kurven(k, strecken) -> None:
    """Entscheidung zu Punkt 10: Grundlage ist die Querbeschleunigung."""
    mittel = rf.mittlere_querbeschleunigung(strecken)
    faktor = {s.name: rf.streckenfaktor(k, s, mittel) for s in strecken}

    # Zandvoort ist eng, Monza schnell.
    assert faktor["Zandvoort"] > faktor["Monza"]
    # Suzuka hat viele, aber schnelle Kurven - deutlich unter Zandvoort.
    assert faktor["Suzuka"] < faktor["Zandvoort"]
    # Catalunya nennt GDD 3 ausdruecklich beim Reifenverschleiss.
    assert faktor["Catalunya"] > 1.0


def test_streckenfaktor_ist_auf_den_mittelwert_normiert(k, strecken) -> None:
    mittel = rf.mittlere_querbeschleunigung(strecken)
    faktoren = [rf.streckenfaktor(k, s, mittel) for s in strecken]
    assert sum(faktoren) / len(faktoren) == pytest.approx(1.0, abs=0.05)
