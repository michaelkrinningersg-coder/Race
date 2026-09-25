"""Tests fuer Spritverbrauch und Masse.

Drei Ebenen: die Physik der Grenzen, der Tank je Fahrer und das Rennen,
in dem beides zusammenkommt - in beiden Rennmodellen. Verglichen wird
fast immer gegen dieselbe Konfiguration **ohne** Verbrauch: Dann ist der
Sprit das Einzige, was sich zwischen zwei Laeufen unterscheidet.
"""

from __future__ import annotations

import copy
import dataclasses

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import rennen as rn
from rennmanager.kern import schnellsimulation as sm
from rennmanager.kern import sprit
from rennmanager.kern import strategie as sg
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern import wetter as kwet
from rennmanager.kern.auto import gesamtwert
from rennmanager.kern.tempo import (
    fahre_runde,
    geschwindigkeitsprofil,
    grenzen_aus,
    rundenzeit_ms,
)
from rennmanager.kern.zufall import Seedquelle

# So wenig Verschleiss, dass die Reifen nicht mitreden: Wer die Masse
# messen will, darf keinen Satz haben, der unterwegs abbaut.
KAUM_VERSCHLEISS = 1e-6


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def ohne_sprit(k) -> kf.Konfiguration:
    """Dieselbe Konfiguration, nur verbraucht niemand etwas."""
    roh = copy.deepcopy(k.roh)
    roh["sprit"]["verbrauch_kg_je_km"] = 0.0
    return dataclasses.replace(k, roh=roh)


@pytest.fixture(scope="module")
def strecke(k) -> st.Strecke:
    return st.lade(k, "Catalunya")


@pytest.fixture(scope="module")
def mittel(k) -> float:
    return rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))


def mit_materialgefuehl(k, wert: int, grund: int = 50_000) -> ka.Auto:
    """Ein Auto, bei dem nur das Materialgefuehl gesetzt ist."""
    auto = ka.gleichverteilt(k, grund)
    wetterwerte = dict(auto.wetterwerte)
    wetterwerte[sprit.MATERIALGEFUEHL] = wert
    return ka.Auto(auto.kuerzel, auto.name, auto.werte, wetterwerte)


def rundenzeit(k, strecke, grenzen) -> int:
    return rundenzeit_ms(strecke, geschwindigkeitsprofil(strecke, grenzen))


# --- Physik der Grenzen ----------------------------------------------------
def test_ohne_sprit_bleibt_das_leere_auto_unangetastet(k) -> None:
    """Das leere Auto ist der Bezug fuer Qualifying und GDD 9."""
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    assert sprit.grenzen_mit_sprit(k, grenzen, 0.0) is grenzen


def test_beschleunigen_traegt_die_masse_voll(k) -> None:
    """F = m * a: Die Kraft des Motors bleibt, die Masse waechst."""
    leer = k.wert("sprit", "masse_leer_kg")
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    voll = sprit.grenzen_mit_sprit(k, grenzen, 100.0)
    assert voll.laengs / grenzen.laengs == pytest.approx(leer / (leer + 100.0))


def test_bremsen_und_kurven_nur_ueber_den_abtrieb(k) -> None:
    """Der mechanische Grip waechst mit dem Gewicht mit, der Abtrieb nicht.

    Bremsen und Kurven verlieren deshalb weniger als das Beschleunigen,
    und enge Kurven - wo der Abtrieb klein ist - am wenigsten.
    """
    einstellung = k.wert("sprit")
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    voll = sprit.grenzen_mit_sprit(k, grenzen, 100.0)
    mu = einstellung["masse_leer_kg"] / (einstellung["masse_leer_kg"] + 100.0)
    alpha = einstellung["abtriebsanteil"]
    alpha_eng = einstellung["abtriebsanteil_enge_kurve"]

    assert voll.brems / grenzen.brems == pytest.approx(1 - alpha + alpha * mu)
    assert voll.quer / grenzen.quer == pytest.approx(1 - alpha + alpha * mu)
    assert voll.quer_eng / grenzen.quer_eng == pytest.approx(
        1 - alpha_eng + alpha_eng * mu
    )
    assert voll.laengs / grenzen.laengs < voll.brems / grenzen.brems
    assert voll.brems / grenzen.brems < voll.quer_eng / grenzen.quer_eng < 1.0


def test_die_hoechstgeschwindigkeit_bleibt(k) -> None:
    """Sie haengt an Leistung und Luftwiderstand, nicht an der Masse."""
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    assert sprit.grenzen_mit_sprit(k, grenzen, 100.0).hoechst == grenzen.hoechst


def test_ein_leichteres_auto_ist_schneller(k, strecke) -> None:
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    zeiten = [
        rundenzeit(k, strecke, sprit.grenzen_mit_sprit(k, grenzen, menge))
        for menge in (100.0, 75.0, 50.0, 25.0, 0.0)
    ]
    assert zeiten == sorted(zeiten, reverse=True)
    assert len(set(zeiten)) == len(zeiten)


def _langsamste_kurve(profil: np.ndarray) -> int:
    """Der Scheitel der langsamsten Kurve einer Runde."""
    return int(np.argmin(profil))


def test_ein_leichtes_auto_bremst_kuerzer(k) -> None:
    """Weniger Masse, mehr Verzoegerung - der Bremsweg ``v^2 / 2a`` wird kuerzer.

    Gemessen **aus demselben Tempo**. Die Bremszone im fertigen Profil
    taugt dafuer nicht: Das leichte Auto kommt auf der Geraden davor auf
    mehr Tempo und bremst daraus - gemessen in Catalunya zwei Punkte
    laenger, obwohl es aus gleichem Tempo frueher steht.
    """
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    schwer = sprit.grenzen_mit_sprit(k, grenzen, 100.0)
    von, auf = 80.0, 25.0

    def bremsweg(g) -> float:
        return (von * von - auf * auf) / (2.0 * g.brems)

    assert bremsweg(grenzen) < bremsweg(schwer)


def test_ein_leichtes_auto_faehrt_schneller_durch_die_kurve(k, strecke) -> None:
    """Gleiches Tempo, kleinere Fliehkraft ``m * v^2 / r`` - das Limit steigt."""
    grenzen = grenzen_aus(k, ka.gleichverteilt(k, 60_000))
    schwer = geschwindigkeitsprofil(strecke, sprit.grenzen_mit_sprit(k, grenzen, 100.0))
    leicht = geschwindigkeitsprofil(strecke, grenzen)
    scheitel = _langsamste_kurve(leicht)
    assert leicht[scheitel] > schwer[scheitel]


def test_voller_tank_kostet_rund_drei_sekunden(k) -> None:
    """Vorgabe des Auftraggebers: voller gegen leeren Tank rund 3 s je Runde.

    Gemessen am Medianfahrer der Welt ueber alle zwanzig Strecken. Je
    Strecke weicht das ab - eine lange Runde kostet mehr Sekunden als
    eine kurze, die Physik rechnet in Prozent. Deshalb gilt die Vorgabe
    fuer das Mittel, mit etwas Spiel (Entscheidung des Auftraggebers:
    geringe Abweichungen sind erlaubt).
    """
    welt = kw.erzeuge(k, Seedquelle(0).zweig("welt"))
    autos = sorted((f.auto for f in welt.fahrer), key=lambda a: gesamtwert(k, a))
    median = autos[len(autos) // 2]
    grenzen = grenzen_aus(k, median)
    unterschiede = []
    for strecke in st.lade_alle(k):
        distanz = rn.rundenzahl(k, strecke) * strecke.laenge_m
        tank = sprit.tank(k, median, distanz)
        voll = rundenzeit(k, strecke, sprit.grenzen_mit_sprit(k, grenzen, tank.start_kg))
        leer = rundenzeit(k, strecke, grenzen)
        unterschiede.append((voll - leer) / 1000.0)
    mittel = sum(unterschiede) / len(unterschiede)
    assert 2.7 <= mittel <= 3.3, f"voller Tank kostet im Mittel {mittel:.2f} s"
    assert min(unterschiede) > 0.0


# --- Der Tank ----------------------------------------------------------------
def test_das_materialgefuehl_senkt_den_verbrauch(k) -> None:
    """+5 % beim Wert 0, -5 % beim Hoechstwert (Entscheidung des Auftraggebers)."""
    faktoren = [
        sprit.verbrauchsfaktor(k, mit_materialgefuehl(k, wert))
        for wert in (0, 25_000, 50_000, 75_000, 100_000)
    ]
    assert faktoren[0] == pytest.approx(k.wert("sprit", "verbrauch_faktor_bei_null"))
    assert faktoren[-1] == pytest.approx(k.wert("sprit", "verbrauch_faktor_bei_maximum"))
    assert faktoren == sorted(faktoren, reverse=True)


def test_getankt_wird_die_distanz_plus_reserve(k) -> None:
    auto = mit_materialgefuehl(k, 50_000)
    distanz = 290_000.0
    tank = sprit.tank(k, auto, distanz)
    bedarf = sprit.verbrauch_kg_je_m(k, auto) * distanz
    reserve = k.wert("sprit", "reserve_anteil")
    assert tank.start_kg == pytest.approx(bedarf * (1.0 + reserve))
    assert float(tank.menge_kg(distanz)) == pytest.approx(bedarf * reserve)
    # Rund 100 kg ueber eine Renndistanz - so ist der Verbrauch gewaehlt.
    assert 90.0 < tank.start_kg < 110.0


def test_wer_sparsam_faehrt_ist_das_ganze_rennen_leichter(k) -> None:
    distanz = 290_000.0
    sparsam = sprit.tank(k, mit_materialgefuehl(k, 100_000), distanz)
    durstig = sprit.tank(k, mit_materialgefuehl(k, 0), distanz)
    for gefahren in np.linspace(0.0, distanz, 11):
        assert sparsam.menge_kg(gefahren) < durstig.menge_kg(gefahren)


def test_der_abrieb_verteilt_sich_nur_um(k) -> None:
    """Entscheidung des Auftraggebers: im Mittel des Rennens genau 1,0.

    Der schwere Start frisst mehr, das leichte Ende weniger - was ein
    Satz ueber das ganze Rennen hergibt, bleibt dasselbe.
    """
    distanz = 290_000.0
    tank = sprit.tank(k, mit_materialgefuehl(k, 50_000), distanz)
    stellen = np.linspace(0.0, distanz, 10_001)
    faktoren = sprit.abriebfaktor(k, tank, stellen, distanz)
    assert float(np.trapezoid(faktoren, stellen) / distanz) == pytest.approx(1.0)
    assert faktoren[0] > 1.0 > faktoren[-1]


def test_der_planer_bekommt_denselben_abrieb_je_runde(k) -> None:
    auto = mit_materialgefuehl(k, 50_000)
    je_runde = sprit.abrieb_je_runde(k, auto, 64, 4_657.0)
    assert len(je_runde) == 64
    assert sum(je_runde) / len(je_runde) == pytest.approx(1.0)
    assert list(je_runde) == sorted(je_runde, reverse=True)


# --- Im Rennen ---------------------------------------------------------------
def test_der_sprit_reicht_im_rennen_immer(k, strecke, mittel) -> None:
    """Getankt wird mit Reserve - leer faehrt niemand."""
    feld = rn.starterfeld(k)[:6]
    verlauf = rn.simuliere(k, strecke, feld, 5, Seedquelle(3), mittel)
    stand = verlauf.sprit_kg
    assert stand is not None
    assert (stand[-1] > 0.0).all()
    # Er nimmt nur ab - nachgetankt wird (noch) nicht.
    assert (np.diff(stand, axis=0) <= 1e-4).all()
    # Im Ziel ist rund die Reserve uebrig: Getankt war fuer genau diese
    # Distanz, und die hinteren Startplaetze fahren ein paar Meter mehr.
    # Wer ausfaellt, behaelt seinen Rest - gezaehlt wird, wer ankommt.
    reserve = k.wert("sprit", "reserve_anteil")
    angekommen = [e.teilnehmer for e in verlauf.ergebnisse if e.zeit_ms is not None]
    assert angekommen
    for i in angekommen:
        assert stand[-1][i] == pytest.approx(
            stand[0][i] * reserve / (1.0 + reserve), rel=0.25
        )


def test_ohne_zufall_faehrt_das_leere_auto(k, strecke, mittel) -> None:
    """GDD 9 kalibriert die blanke Runde - ohne Sprit, wie ohne Ermuedung."""
    verlauf = rn.simuliere(
        k, strecke, rn.starterfeld(k)[:1], 3, Seedquelle(3), mittel, ohne_zufall=True
    )
    assert verlauf.sprit_kg is None
    assert verlauf.sprit_zu(0) is None


def _allein(konfiguration, strecke, mittel, runden: int, wetter=None):
    """Ein Auto allein, ohne Verschleiss: Nur die Masse aendert sich."""
    return rn.simuliere(
        konfiguration, strecke, rn.starterfeld(konfiguration)[:1], runden,
        Seedquelle(7), mittel, wetter=wetter, streckenverschleiss=KAUM_VERSCHLEISS,
    )


def test_mit_vollem_tank_kommt_das_auto_langsamer_vom_fleck(k, strecke, mittel) -> None:
    """Aus dem Stand und hinter einem Langsameren zaehlt die Beschleunigung.

    Sie steckt nicht im Profil, sondern wird je Schritt nachgerechnet -
    also wird sie hier auch einzeln geprueft.
    """
    lauf = rn._Lauf(k, strecke, rn.starterfeld(k)[:2], 10, Seedquelle(1), mittel)
    leer = k.wert("sprit", "masse_leer_kg")
    laengs = lauf._tanke_ab()
    assert laengs == pytest.approx(lauf.laengs * leer / (leer + lauf.sprit_start))
    assert (laengs < lauf.laengs).all()


def test_im_rennen_verteilt_der_sprit_den_abrieb_nur_um(k, ohne_sprit, mittel) -> None:
    """Zur Halbzeit ist der Satz mit Sprit staerker abgefahren, im Ziel gleich.

    Gemessen an **derselben Stelle** der Strecke, nicht zur selben Zeit:
    Abrieb faellt je Meter, und das Auto mit Sprit ist langsamer.
    """
    monza = st.lade(k, "Monza")
    runden = 10

    def zustand(konfiguration):
        verlauf = rn.simuliere(
            konfiguration, monza, rn.starterfeld(konfiguration)[:1], runden,
            Seedquelle(7), mittel,
        )
        strecke = verlauf.distanz_m[:, 0]
        halbzeit = int(np.argmax(strecke >= runden * monza.laenge_m / 2.0))
        return float(verlauf.reifenzustand[halbzeit, 0]), float(verlauf.reifenzustand[-1, 0])

    mitte_mit, ziel_mit = zustand(k)
    mitte_ohne, ziel_ohne = zustand(ohne_sprit)
    assert mitte_mit < mitte_ohne
    assert abs(ziel_mit - ziel_ohne) < 0.25 * (mitte_ohne - mitte_mit)


def test_mit_sprit_ist_der_rennanfang_langsamer(k, ohne_sprit, strecke, mittel) -> None:
    """Der Tank macht die ersten Runden langsam, die letzten kaum noch.

    Verglichen wird Runde fuer Runde gegen dasselbe Rennen ohne
    Verbrauch - derselbe Seed, dieselbe Form, nur der Sprit fehlt.
    """
    runden = 12
    mit = np.array(_allein(k, strecke, mittel, runden).protokolle[0].rundenzeiten_ms)
    ohne = np.array(_allein(ohne_sprit, strecke, mittel, runden).protokolle[0].rundenzeiten_ms)
    unterschied = mit - ohne

    auto = rn.starterfeld(k)[0].auto
    tank = sprit.tank(k, auto, runden * strecke.laenge_m)
    grenzen = grenzen_aus(k, auto)
    voll = rundenzeit(k, strecke, sprit.grenzen_mit_sprit(k, grenzen, tank.start_kg))
    leer = rundenzeit(k, strecke, grenzen)
    # Runde 2 liegt bei 1,5 von 12 Runden: rund 7/8 des vollen Tanks.
    erwartet = (voll - leer) * (1.0 - 1.5 / runden)
    assert unterschied[1] == pytest.approx(erwartet, rel=0.25)
    assert unterschied[1] > unterschied[runden // 2] > unterschied[-1] >= 0
    assert unterschied[-1] < 0.15 * unterschied[1]


def test_beide_rennmodelle_rechnen_den_sprit_gleich(k, ohne_sprit, strecke, mittel) -> None:
    """Der Schnellmodus darf den Sprit nicht anders verbuchen als der Zeitraffer.

    Verglichen wird, was der Sprit **kostet** - dieselbe Rechnung mit und
    ohne Verbrauch - und das bei gleichem Wetter aus demselben Zweig.
    Gemessen lagen die Modelle 0,3 bis 2,6 Prozent auseinander; ohne
    Sprit liegen sie selbst schon um ein Prozent auseinander.
    """
    runden = 12
    feld = rn.starterfeld(k)[:1]
    grund = fahre_runde(k, strecke, feld[0].auto).zeit_ms
    wetter = kwet.wuerfle(
        k, strecke.name, grund * runden, grund, Seedquelle(7).zweig("rennwetter")
    )

    def kosten(konfiguration):
        voll = _allein(konfiguration, strecke, mittel, runden, wetter)
        flott = sm.fahre_wochenende(
            konfiguration, strecke, feld, runden, Seedquelle(7), mittel, KAUM_VERSCHLEISS
        )
        return voll.ergebnisse[0].zeit_ms, flott.siegerzeit_ms

    voll_mit, flott_mit = kosten(k)
    voll_ohne, flott_ohne = kosten(ohne_sprit)
    zuwachs_voll = voll_mit - voll_ohne
    zuwachs_flott = flott_mit - flott_ohne
    assert zuwachs_voll > 0
    assert zuwachs_flott == pytest.approx(zuwachs_voll, rel=0.05)


def test_der_planer_rechnet_den_schweren_ersten_stint_mit(k, ohne_sprit) -> None:
    """Mit vollem Tank frisst das Auto mehr Reifen - der erste Stopp rueckt vor.

    Verglichen werden dieselben Mischungsfolgen mit und ohne Sprit. **Im
    Mittel** rueckt der erste Stopp vor, und bei einem Stopp nie nach
    hinten. Bei drei Stints ist das kein Gesetz: Der Planer rechnet exakt
    und legt die Zwischenstopps mit um - gemessen hielt dort manche Folge
    ihren ersten Satz eine Runde laenger.
    """
    welt = kw.erzeuge(k, Seedquelle(0).zweig("welt"))
    autos = [f.auto for f in welt.fahrer]
    monza = st.lade(k, "Monza")
    runden = rn.rundenzahl(k, monza)

    def plaene(konfiguration):
        strategien = sg.feldstrategien(
            konfiguration, autos, monza, runden, 1.0, None, Seedquelle(1)
        )
        return {v.mischungen: v.stopps for v in strategien.varianten}

    mit, ohne = plaene(k), plaene(ohne_sprit)
    gemeinsam = [folge for folge in mit if folge in ohne and mit[folge]]
    assert gemeinsam, "keine gemeinsame Mischungsfolge"
    ein_stopp = [folge for folge in gemeinsam if len(mit[folge]) == 1]
    assert ein_stopp, "keine Ein-Stopp-Folge zum Vergleich"
    for folge in ein_stopp:
        assert mit[folge][0] <= ohne[folge][0], folge
    erste_mit = sum(mit[folge][0] for folge in gemeinsam) / len(gemeinsam)
    erste_ohne = sum(ohne[folge][0] for folge in gemeinsam) / len(gemeinsam)
    assert erste_mit < erste_ohne
