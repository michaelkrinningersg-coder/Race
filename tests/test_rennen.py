"""Tests fuer die Rennsimulation (GDD 4).

Weil ein volles Rennen ueber 20 Ligen und 24 Runden laeuft, arbeiten die
meisten Tests mit wenigen Runden und kleinen Feldern. Die teuren Laeufe
stehen in Fixtures mit ``scope="module"``.
"""

from __future__ import annotations

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import tempo as tp
from rennmanager.kern.zufall import Seedquelle

LIGA = 20


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def mittel(k, strecken) -> float:
    return rn.mittlerer_ueberholzonenanteil(k, strecken)


@pytest.fixture(scope="module")
def zandvoort(strecken) -> st.Strecke:
    return next(s for s in strecken if s.name == "Zandvoort")


@pytest.fixture(scope="module")
def rennen(k, zandvoort, mittel) -> rn.Rennverlauf:
    """Kurzes Rennen mit regulaerer Aufstellung."""
    feld = rn.starterfeld(k, LIGA, spielerplatz=30)
    return rn.simuliere(k, zandvoort, feld, 3, Seedquelle(4711), mittel)


@pytest.fixture(scope="module")
def umgedreht(k, zandvoort, mittel) -> rn.Rennverlauf:
    """Staerkstes Auto startet hinten - erzwingt Ueberholmanoever."""
    feld = rn.starterfeld(k, LIGA, umgedreht=True)
    return rn.simuliere(k, zandvoort, feld, 3, Seedquelle(4711), mittel)


# -- Startaufstellung -------------------------------------------------------
def test_startaufstellung_haelt_fuenf_meter_abstand(k) -> None:
    """GDD 4: Platz 30 steht 145 m hinter Platz 1."""
    assert rn.startdistanz_m(k, 1) == 0.0
    assert rn.startdistanz_m(k, 2) == -5.0
    assert rn.startdistanz_m(k, 30) == -145.0


def test_reaktionszeit_liegt_im_vorgegebenen_band(k) -> None:
    """GDD 4: Reaktionszeit 0,100 bis 0,300 s."""
    schnellste = k.wert("start", "reaktionszeit_min_ms")
    langsamste = k.wert("start", "reaktionszeit_max_ms")
    for s in (0, 10_000, 50_000, 98_000, 100_000):
        zeit = rn.reaktionszeit_ms(k, ka.gleichverteilt(k, s))
        assert schnellste <= zeit <= langsamste


def test_bessere_reaktion_startet_frueher(k) -> None:
    schwach = rn.reaktionszeit_ms(k, ka.gleichverteilt(k, 0))
    stark = rn.reaktionszeit_ms(k, ka.gleichverteilt(k, 98_000))
    assert stark < schwach
    assert stark == k.wert("start", "reaktionszeit_min_ms")
    assert schwach == k.wert("start", "reaktionszeit_max_ms")


def test_autos_stehen_bis_zur_reaktionszeit(rennen, k) -> None:
    """Vor der Reaktionszeit bewegt sich nichts (GDD 4)."""
    am_anfang = rennen.distanzen_zu(0)
    # Die Startaufstellung: 5 m Abstand, Platz 1 auf der Linie.
    erwartet = [rn.startdistanz_m(k, t.startplatz) for t in rennen.teilnehmer]
    assert np.allclose(am_anfang, erwartet)

    # Die schnellste Reaktion betraegt 100 ms, nach 50 ms steht alles still.
    assert np.allclose(rennen.distanzen_zu(50), am_anfang)
    # Nach einer Sekunde hat sich jedes Auto bewegt.
    assert (rennen.distanzen_zu(1_000) > am_anfang).all()


def test_start_erfolgt_aus_dem_stand(rennen) -> None:
    """Kein Sprung auf Profiltempo: die Autos beschleunigen."""
    strecken_nach_2s = rennen.distanzen_zu(2_000) - rennen.distanzen_zu(0)
    strecken_nach_4s = rennen.distanzen_zu(4_000) - rennen.distanzen_zu(2_000)
    # In der zweiten Sekundenpaarung ist das Auto schneller als in der ersten.
    assert (strecken_nach_4s > strecken_nach_2s).all()


# -- Rundenzahl -------------------------------------------------------------
def test_rundenzahl_folgt_der_distanz(k, zandvoort) -> None:
    """GDD 4: Liga 20 = 100 km, je Liga +10 km, aufgerundet."""
    import math

    for liga, km in ((20, 100), (10, 200), (1, 290)):
        erwartet = math.ceil(km * 1000 / zandvoort.laenge_m)
        assert rn.rundenzahl(k, zandvoort, liga) == erwartet


def test_hoehere_liga_faehrt_weiter(k, zandvoort) -> None:
    assert rn.rundenzahl(k, zandvoort, 1) > rn.rundenzahl(k, zandvoort, 20)


# -- Verlauf ----------------------------------------------------------------
def test_alle_autos_kommen_ins_ziel(rennen) -> None:
    assert len(rennen.ergebnisse) == 30
    assert all(e.zeit_ms is not None for e in rennen.ergebnisse)


def test_platzierungen_sind_luckenlos(rennen) -> None:
    assert [e.platz for e in rennen.ergebnisse] == list(range(1, 31))
    assert len({e.teilnehmer for e in rennen.ergebnisse}) == 30


def test_sieger_faehrt_die_volle_distanz(rennen) -> None:
    assert rennen.ergebnisse[0].runden == rennen.runden


def test_rennende_bei_der_naechsten_zielueberfahrt(rennen) -> None:
    """GDD 4: Nach dem Sieger beendet jedes Auto bei seiner naechsten Ueberfahrt."""
    for ergebnis in rennen.ergebnisse:
        # Niemand faehrt mehr Runden als vorgesehen ...
        assert ergebnis.runden <= rennen.runden
        # ... und niemand hoert mehr als eine Runde frueher auf, solange er
        # nicht ueberrundet wurde.
        assert ergebnis.rundenrueckstand >= 0


def test_rueckstand_waechst_mit_dem_platz(rennen) -> None:
    rueckstaende = [
        e.rueckstand_ms for e in rennen.ergebnisse if e.rueckstand_ms is not None
    ]
    assert rueckstaende[0] == 0
    assert rueckstaende == sorted(rueckstaende)


def test_zeiten_sind_ganze_millisekunden(rennen) -> None:
    for ergebnis in rennen.ergebnisse:
        assert isinstance(ergebnis.zeit_ms, int)
    for protokoll in rennen.protokolle:
        assert all(isinstance(zeit, int) for zeit in protokoll.rundenzeiten_ms)


def test_jedes_auto_hat_rundenzeiten_und_sektoren(rennen, k) -> None:
    """GDD 4: Zeitenmonitor mit letzter Runde, bester Runde, 4 Sektorzeiten."""
    sektoren = k.wert("strecke", "sektoren")
    for i, protokoll in enumerate(rennen.protokolle):
        assert protokoll.rundenzeiten_ms, f"Auto {i} ohne Rundenzeit"
        assert protokoll.beste_runde_ms == min(protokoll.rundenzeiten_ms)
        assert protokoll.letzte_runde_ms == protokoll.rundenzeiten_ms[-1]
        for zeiten in protokoll.sektorzeiten_ms:
            assert len(zeiten) == sektoren


def test_sektorzeiten_ergeben_die_rundenzeit(rennen) -> None:
    for protokoll in rennen.protokolle:
        for runde, sektoren in zip(
            protokoll.rundenzeiten_ms, protokoll.sektorzeiten_ms, strict=True
        ):
            assert sum(sektoren) == pytest.approx(runde, abs=3)


def test_freie_fahrt_entspricht_der_einzelrunde(k, zandvoort, mittel) -> None:
    """Ein Auto allein muss im Rennen so schnell sein wie in der Einzelrunde.

    Das prueft, dass die Rennschleife dasselbe Modell benutzt wie
    rennmanager.kern.tempo und nicht heimlich langsamer oder schneller ist.
    """
    auto = ka.gleichverteilt(k, 8_400, "EIN")
    solo = tp.fahre_runde(k, zandvoort, auto)
    verlauf = rn.simuliere(
        k, zandvoort, (rn.Teilnehmer(auto=auto, startplatz=1, farbe="#fff"),),
        3, Seedquelle(1), mittel,
    )
    # Die erste Runde enthaelt den stehenden Start, ab der zweiten faehrt
    # das Auto fliegend.
    fliegend = verlauf.protokolle[0].rundenzeiten_ms[1]
    assert fliegend == pytest.approx(solo.zeit_ms, rel=0.001)


def test_erste_runde_ist_wegen_des_starts_langsamer(k, zandvoort, mittel) -> None:
    auto = ka.gleichverteilt(k, 8_400, "EIN")
    verlauf = rn.simuliere(
        k, zandvoort, (rn.Teilnehmer(auto=auto, startplatz=1, farbe="#fff"),),
        3, Seedquelle(1), mittel,
    )
    zeiten = verlauf.protokolle[0].rundenzeiten_ms
    assert zeiten[0] > zeiten[1]


# -- Ueberholen -------------------------------------------------------------
def test_ohne_tempovorteil_wird_nicht_ueberholt(k, zandvoort, mittel) -> None:
    """Gleich schnelle Autos duerfen die Reihenfolge nicht tauschen."""
    gleich = tuple(
        rn.Teilnehmer(auto=ka.gleichverteilt(k, 8_400, f"G{n:02d}"), startplatz=n, farbe="#fff")
        for n in range(1, 6)
    )
    verlauf = rn.simuliere(k, zandvoort, gleich, 2, Seedquelle(7), mittel)
    assert verlauf.manoever == ()


def test_umgedrehtes_feld_erzwingt_ueberholmanoever(umgedreht) -> None:
    assert len(umgedreht.manoever) > 0


def test_schnellstes_auto_arbeitet_sich_nach_vorn(umgedreht) -> None:
    """Von Platz 30 aus muss das staerkste Auto Plaetze gutmachen."""
    staerkstes = next(
        i for i, t in enumerate(umgedreht.teilnehmer) if t.auto.kuerzel == "A01"
    )
    ergebnis = next(e for e in umgedreht.ergebnisse if e.teilnehmer == staerkstes)
    assert umgedreht.teilnehmer[staerkstes].startplatz == 30
    assert ergebnis.platz < 30


def test_ueberholmanoever_sind_vollstaendig_beschrieben(umgedreht) -> None:
    for manoever in umgedreht.manoever:
        assert 0 <= manoever.angreifer < umgedreht.anzahl
        assert 0 <= manoever.verteidiger < umgedreht.anzahl
        assert manoever.angreifer != manoever.verteidiger
        assert manoever.zeit_ms >= 0
        assert 1 <= manoever.runde <= umgedreht.runden


def test_erfolgschance_bleibt_im_band(k) -> None:
    einstellung = k.wert("ueberholen", "erfolg")
    schwach = ka.gleichverteilt(k, 0)
    stark = ka.gleichverteilt(k, 100_000)
    for angreifer, verteidiger in ((schwach, stark), (stark, schwach), (schwach, schwach)):
        for vorteil in (2.0, 5.0, 50.0):
            chance = rn.erfolgschance(k, angreifer, verteidiger, vorteil, 1.0)
            assert einstellung["wahrscheinlichkeit_min"] <= chance
            assert chance <= einstellung["wahrscheinlichkeit_max"]


def test_besserer_angreifer_hat_mehr_chance(k) -> None:
    schwach = ka.gleichverteilt(k, 0)
    stark = ka.gleichverteilt(k, 100_000)
    assert rn.erfolgschance(k, stark, schwach, 5.0, 1.0) > rn.erfolgschance(
        k, schwach, stark, 5.0, 1.0
    )


def test_mehr_tempovorteil_hilft(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    assert rn.erfolgschance(k, auto, auto, 20.0, 1.0) > rn.erfolgschance(
        k, auto, auto, 2.0, 1.0
    )


def test_gleiche_werte_ergeben_faire_chance(k) -> None:
    """Beide Fahrer bei 0 - laut GDD 1 der Ausgangszustand - muss gehen."""
    null = ka.gleichverteilt(k, 0)
    chance = rn.erfolgschance(k, null, null, 2.0, 1.0)
    assert chance == pytest.approx(0.5, abs=0.01)


def test_streckenfaktor_folgt_dem_ueberholzonenanteil(k, strecken, mittel) -> None:
    monza = next(s for s in strecken if s.name == "Monza")
    budapest = next(s for s in strecken if s.name == "Budapest")
    assert rn.streckenfaktor(k, monza, mittel) > rn.streckenfaktor(k, budapest, mittel)


# -- Verlauf abspielen ------------------------------------------------------
def test_distanzen_werden_interpoliert(rennen) -> None:
    davor = rennen.distanzen_zu(10_000)
    dazwischen = rennen.distanzen_zu(10_100)
    danach = rennen.distanzen_zu(10_200)
    assert (dazwischen >= davor).all()
    assert (danach >= dazwischen).all()


def test_reihenfolge_stimmt_mit_der_distanz_ueberein(rennen) -> None:
    zeitpunkt = rennen.dauer_ms // 2
    reihenfolge = rennen.reihenfolge_zu(zeitpunkt)
    distanzen = rennen.distanzen_zu(zeitpunkt)
    assert len(reihenfolge) == 30
    assert [distanzen[i] for i in reihenfolge] == sorted(distanzen, reverse=True)


def test_distanz_waechst_monoton(rennen) -> None:
    zuwachs = np.diff(rennen.distanz_m, axis=0)
    assert (zuwachs >= -1e-6).all()


def test_abfrage_ausserhalb_des_verlaufs_ist_gueltig(rennen) -> None:
    assert rennen.distanzen_zu(-5_000).shape == (30,)
    assert rennen.distanzen_zu(rennen.dauer_ms * 2).shape == (30,)


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiches_rennen(k, zandvoort, mittel) -> None:
    feld = rn.starterfeld(k, LIGA, umgedreht=True)
    erste = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(123), mittel)
    zweite = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(123), mittel)
    assert np.array_equal(erste.distanz_m, zweite.distanz_m)
    assert erste.manoever == zweite.manoever
    assert erste.ergebnisse == zweite.ergebnisse


def test_anderer_seed_anderes_rennen(k, zandvoort, mittel) -> None:
    feld = rn.starterfeld(k, LIGA, umgedreht=True)
    erste = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(123), mittel)
    zweite = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(456), mittel)
    assert erste.manoever != zweite.manoever


# -- Startfeld --------------------------------------------------------------
def test_starterfeld_hat_dreissig_autos(k) -> None:
    feld = rn.starterfeld(k, LIGA)
    assert len(feld) == k.wert("rennen", "autos")
    assert sorted(t.startplatz for t in feld) == list(range(1, 31))


def test_starterfeld_spannt_die_liga_auf(k) -> None:
    """GDD 9: von Letztem bis Bestem der Liga."""
    zeile = next(z for z in k.wert("ligen", "kontrolle") if z["liga"] == LIGA)
    feld = rn.starterfeld(k, LIGA)
    werte = [t.auto.wert("F1") for t in feld]
    assert max(werte) == zeile["s_bester"]
    assert min(werte) == zeile["s_letzter"]


def test_starterfeld_kennzeichnet_den_spieler(k) -> None:
    feld = rn.starterfeld(k, LIGA, spielerplatz=7)
    spieler = [t for t in feld if t.ist_spieler]
    assert len(spieler) == 1
    assert spieler[0].startplatz == 7


def test_starterfeld_ohne_kontrollwert_meldet_fehler(k) -> None:
    with pytest.raises(ValueError, match="Kontrollwert"):
        rn.starterfeld(k, 17)


def test_simulation_ohne_teilnehmer_meldet_fehler(k, zandvoort, mittel) -> None:
    with pytest.raises(ValueError, match="Teilnehmer"):
        rn.simuliere(k, zandvoort, (), 3, Seedquelle(1), mittel)


def test_simulation_ohne_runden_meldet_fehler(k, zandvoort, mittel) -> None:
    with pytest.raises(ValueError, match="Runde"):
        rn.simuliere(k, zandvoort, rn.starterfeld(k, LIGA), 0, Seedquelle(1), mittel)
