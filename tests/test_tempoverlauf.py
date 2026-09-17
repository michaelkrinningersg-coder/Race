"""Tests fuer die Verlaeufe ueber die Renndistanz (Punkte 9, 11 und 20).

Ermuedung aus GDD 8 und die beiden neuen Eigenschaften Kaltreifen und
Bremskuehlung. Alle drei haengen an der gefahrenen Distanz und muessen im
zufallsfreien Modus wegfallen, sonst waere ein Auto im Rennen langsamer
als in der Einzelrunde, auf die GDD 9 kalibriert.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import rennen as kr
from rennmanager.kern import strecke as st
from rennmanager.kern import tempoverlauf as tv
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecke(k) -> st.Strecke:
    return st.lade(k, "Monza")


def mit_zusatz(k, schluessel: str, wert: int, grund: int = 50_000) -> ka.Auto:
    """Ein Auto, bei dem eine Eigenschaft neben der Matrix gesetzt ist."""
    auto = ka.gleichverteilt(k, grund)
    wetterwerte = dict(auto.wetterwerte)
    wetterwerte[schluessel] = wert
    return ka.Auto(auto.kuerzel, auto.name, auto.werte, wetterwerte)


# --- Ermuedung (GDD 8, Bereich er) ----------------------------------------
def test_die_ermuedung_wirkt_erst_in_der_zweiten_haelfte(k) -> None:
    auto = ka.gleichverteilt(k, 0)
    beginn = k.wert("ermuedung", "beginn_anteil_distanz")
    assert tv.ermuedungsfaktor(k, auto, 0.0) == 1.0
    assert tv.ermuedungsfaktor(k, auto, beginn) == 1.0
    assert tv.ermuedungsfaktor(k, auto, beginn + 0.01) < 1.0


def test_der_ermuedungsverlust_haelt_die_abgestimmten_grenzen(k) -> None:
    """Punkt 48: 2,0 % bei 0, 0,3 % bei vollem Wert."""
    einstellung = k.wert("ermuedung")
    schwach = tv.ermuedungsverlust(k, ka.gleichverteilt(k, 0))
    stark = tv.ermuedungsverlust(k, ka.gleichverteilt(k, k.wert("skala", "referenz")))
    assert schwach == pytest.approx(einstellung["tempoverlust_am_ende_bei_null"])
    assert stark == pytest.approx(einstellung["tempoverlust_am_ende_bei_maximum"])
    assert tv.ermuedungsfaktor(k, ka.gleichverteilt(k, 0), 1.0) == pytest.approx(
        1.0 - schwach
    )


def test_die_ermuedung_waechst_gleichmaessig_bis_ins_ziel(k) -> None:
    auto = ka.gleichverteilt(k, 0)
    beginn = k.wert("ermuedung", "beginn_anteil_distanz")
    mitte = beginn + (1.0 - beginn) / 2
    voll = 1.0 - tv.ermuedungsfaktor(k, auto, 1.0)
    assert 1.0 - tv.ermuedungsfaktor(k, auto, mitte) == pytest.approx(voll / 2)


# --- Kaltreifen (Punkt 48) ------------------------------------------------
def test_kalte_reifen_kosten_nur_die_erste_runde(k) -> None:
    auto = mit_zusatz(k, tv.KALTREIFEN, 0)
    laenge = 5_000.0
    runden = k.wert("kaltreifen", "aufwaermstrecke_runden")
    assert tv.kaltreifenfaktor(k, auto, 0.0, laenge) < 1.0
    assert tv.kaltreifenfaktor(k, auto, runden * laenge, laenge) == 1.0
    assert tv.kaltreifenfaktor(k, auto, 10 * laenge, laenge) == 1.0


def test_der_kaltreifenverlust_haelt_die_abgestimmten_grenzen(k) -> None:
    """Punkt 48: 3,0 % bei 0, 0,5 % bei vollem Wert."""
    einstellung = k.wert("kaltreifen")
    referenz = k.wert("skala", "referenz")
    assert tv.kaltreifenverlust(k, mit_zusatz(k, tv.KALTREIFEN, 0)) == pytest.approx(
        einstellung["tempoverlust_bei_null"]
    )
    assert tv.kaltreifenverlust(
        k, mit_zusatz(k, tv.KALTREIFEN, referenz)
    ) == pytest.approx(einstellung["tempoverlust_bei_maximum"])


def test_der_verlust_wird_gleichmaessig_abgebaut(k) -> None:
    auto = mit_zusatz(k, tv.KALTREIFEN, 0)
    laenge = 4_000.0
    voll = 1.0 - tv.kaltreifenfaktor(k, auto, 0.0, laenge)
    assert 1.0 - tv.kaltreifenfaktor(k, auto, laenge / 2, laenge) == pytest.approx(voll / 2)


# --- Bremskuehlung (Punkt 48) ---------------------------------------------
def test_die_bremse_laesst_ueber_die_distanz_nach(k) -> None:
    """Punkt 48: 4,0 % bei 0, 0,5 % bei vollem Wert."""
    einstellung = k.wert("bremskuehlung")
    referenz = k.wert("skala", "referenz")
    schwach = mit_zusatz(k, tv.BREMSKUEHLUNG, 0)
    stark = mit_zusatz(k, tv.BREMSKUEHLUNG, referenz)
    assert tv.bremsverlust(k, schwach) == pytest.approx(
        einstellung["verlust_am_ende_bei_null"]
    )
    assert tv.bremsverlust(k, stark) == pytest.approx(
        einstellung["verlust_am_ende_bei_maximum"]
    )
    assert tv.bremsgrenze_am_ende(k, schwach, 40.0) == pytest.approx(
        40.0 * (1.0 - einstellung["verlust_am_ende_bei_null"])
    )


def test_eine_fehlende_eigenschaft_gilt_als_null(k) -> None:
    """GDD 1 laesst den Spieler bei 0 anfangen - das ist der schlechteste Fall."""
    ohne = ka.Auto("X", "Ohne Zusatz", ka.gleichverteilt(k, 50_000).werte)
    assert tv.kaltreifenverlust(k, ohne) == tv.kaltreifenverlust(
        k, mit_zusatz(k, tv.KALTREIFEN, 0)
    )
    assert tv.bremsverlust(k, ohne) == tv.bremsverlust(k, mit_zusatz(k, tv.BREMSKUEHLUNG, 0))


# --- Im Rennen ------------------------------------------------------------
def feld(k, anzahl: int = 3, wert: int = 50_000) -> tuple[kr.Teilnehmer, ...]:
    return tuple(
        kr.Teilnehmer(
            auto=ka.gleichverteilt(k, wert, kuerzel=f"A{i:02d}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i in range(anzahl)
    )


def test_ohne_zufall_bleibt_alles_weg(k, strecke) -> None:
    """GDD 9 kalibriert die blanke Runde - ohne Ermuedung und kalte Reifen."""
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    verlauf = kr.simuliere(
        k, strecke, feld(k, 1), runden=6, seedquelle=Seedquelle(1),
        streckenmittel=mittel, ohne_zufall=True,
    )
    zeiten = verlauf.protokolle[0].rundenzeiten_ms
    # Die erste Runde traegt den stehenden Start aus GDD 4 und ist immer
    # langsamer; ab der zweiten muss jede Runde gleich sein.
    assert len(set(zeiten[1:])) == 1


def test_mit_zufall_wird_das_rennende_langsamer(k, strecke) -> None:
    """Ermuedung und nachlassende Bremsen kosten gegen Ende Zeit."""
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    verlauf = kr.simuliere(
        k, strecke, feld(k, 1), runden=8, seedquelle=Seedquelle(1),
        streckenmittel=mittel,
    )
    zeiten = verlauf.protokolle[0].rundenzeiten_ms
    # Die erste Runde traegt die kalten Reifen, die letzte die Ermuedung.
    assert zeiten[0] > zeiten[1]
    assert zeiten[-1] > zeiten[len(zeiten) // 2]
