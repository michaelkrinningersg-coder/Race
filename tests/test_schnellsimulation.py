"""Tests fuer die Schnellsimulation der uebrigen Ligen (GDD 13).

Die Schnellsimulation ersetzt die volle Rennsimulation fuer die 9 Ligen,
in denen der Spieler nicht faehrt. Sie muss deshalb dasselbe liefern -
eine vollstaendige Wertung mit Qualifying, Wetter, Ausfaellen und
Ueberholmanoevern -, nur schneller und auf Rundenebene statt in
50-Millisekunden-Schritten.
"""

from __future__ import annotations

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import reifen as kr
from rennmanager.kern import rennen as rn
from rennmanager.kern import schnellsimulation as sn
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern import wetter as kwet
from rennmanager.kern import zwischenfall as zw
from rennmanager.kern.tempo import fahre_runde
from rennmanager.kern.zufall import Seedquelle
from tests.conftest import KLEINE_LIGEN

LIGA = KLEINE_LIGEN
RUNDEN = 6


@pytest.fixture(scope="module")
def k(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``.

    Drei Ligen zu je vier Autos statt zwanzig zu je dreissig. Geprueft
    wird, *ob* die Logik stimmt - dafuer genuegt das kleine Feld, und ein
    Rennwochenende kostet 1,5 statt 54 Sekunden.
    """
    return kleine_konfiguration


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def zandvoort(strecken) -> st.Strecke:
    return next(s for s in strecken if s.name == "Zandvoort")


@pytest.fixture(scope="module")
def welt(k) -> kw.Welt:
    return kw.erzeuge(k, Seedquelle(3).zweig("welt"), spielerliga=LIGA)


@pytest.fixture(scope="module")
def feld(welt):
    return kw.starterfeld(welt, LIGA)


@pytest.fixture(scope="module")
def umgebung(k, strecken, zandvoort) -> tuple[float, float]:
    """Bezugsgroessen fuer Ueberholen und Reifenverschleiss."""
    mittel = rn.mittlerer_ueberholzonenanteil(k, strecken)
    verschleiss = kr.streckenfaktor(k, zandvoort, kr.mittlere_querbeschleunigung(strecken))
    return mittel, verschleiss


def fahre(k, zandvoort, feld, umgebung, seed: int, runden: int = RUNDEN):
    mittel, verschleiss = umgebung
    return sn.fahre_wochenende(
        k, LIGA, zandvoort, feld, runden, Seedquelle(seed), mittel, verschleiss
    )


@pytest.fixture(scope="module")
def wochenende(k, zandvoort, feld, umgebung) -> sn.Schnellergebnis:
    return fahre(k, zandvoort, feld, umgebung, seed=1)


# --- Wertung --------------------------------------------------------------
def test_jedes_auto_wird_gewertet(wochenende, feld):
    assert len(wochenende.ergebnisse) == len(feld)
    assert [e.rennplatz for e in wochenende.ergebnisse] == list(range(1, len(feld) + 1))
    assert sorted(e.fahrer for e in wochenende.ergebnisse) == list(range(len(feld)))


def test_jeder_qualifyingplatz_wird_genau_einmal_vergeben(wochenende, feld):
    plaetze = sorted(e.qualifyingplatz for e in wochenende.ergebnisse)
    assert plaetze == list(range(1, len(feld) + 1))


def test_genau_ein_auto_faehrt_die_schnellste_runde(wochenende):
    assert sum(1 for e in wochenende.ergebnisse if e.schnellste_runde) == 1


def test_ausgefallene_autos_stehen_hinten(wochenende):
    plaetze = [e.rennplatz for e in wochenende.ergebnisse if e.ausgefallen]
    letzte = [e.rennplatz for e in wochenende.ergebnisse][-len(plaetze) :] if plaetze else []
    assert plaetze == letzte
    assert wochenende.ausfaelle == len(plaetze)


def test_siegerzeit_passt_zur_rundenzahl(wochenende, k, zandvoort, feld):
    """Die Siegerzeit muss zwischen Rundenzahl mal Bestzeit und dem
    Doppelten davon liegen - sonst stimmt die Zeitrechnung nicht."""
    untergrenze = wochenende.schnellste_runde_ms * RUNDEN
    assert untergrenze <= wochenende.siegerzeit_ms <= untergrenze * 2


def test_ausfaelle_bleiben_unter_der_grenze(k, zandvoort, feld, umgebung):
    """GDD 4 begrenzt die Ausfaelle je Rennen; das muss auch hier gelten."""
    obergrenze = max(
        zw.ausfallgrenze(k, Seedquelle(seed).zweig("hilfe").generator()) for seed in range(6)
    )
    for seed in range(6):
        assert fahre(k, zandvoort, feld, umgebung, seed).ausfaelle <= obergrenze


# --- Zufall ---------------------------------------------------------------
def test_gleicher_seed_gleiches_wochenende(k, zandvoort, feld, umgebung):
    erstes = fahre(k, zandvoort, feld, umgebung, seed=5)
    zweites = fahre(k, zandvoort, feld, umgebung, seed=5)
    assert erstes == zweites


def test_anderer_seed_anderes_wochenende(k, zandvoort, feld, umgebung):
    erstes = fahre(k, zandvoort, feld, umgebung, seed=5)
    zweites = fahre(k, zandvoort, feld, umgebung, seed=6)
    assert erstes.ergebnisse != zweites.ergebnisse


# --- Rennverlauf ----------------------------------------------------------
def test_es_wird_ueberholt(k, zandvoort, feld, umgebung):
    """Ohne Ueberholmanoever waere das Rennen nur eine Zeitaddition.

    Vier Autos ueber sechs Runden sind eine kleine Stichprobe: Dass in
    einem einzelnen Rennen niemand vorbeikommt, ist kein Fehler des
    Modells. Geprueft wird deshalb ueber acht Seeds, dass es regelmaessig
    passiert - in der Mehrheit der Rennen und insgesamt deutlich.
    """
    manoever = [fahre(k, zandvoort, feld, umgebung, seed).ueberholmanoever for seed in range(8)]
    assert sum(manoever) > 0
    assert sum(1 for anzahl in manoever if anzahl > 0) >= len(manoever) // 2


def test_das_wetter_wird_gewuerfelt(wochenende, k):
    zustaende = set(k.wert("wetter", "zustand"))
    assert wochenende.wetter
    assert set(wochenende.wetter) <= zustaende


def test_ohne_teilnehmer_gibt_es_kein_wochenende(k, zandvoort, umgebung):
    mittel, verschleiss = umgebung
    with pytest.raises(ValueError):
        sn.fahre_wochenende(k, LIGA, zandvoort, (), RUNDEN, Seedquelle(0), mittel, verschleiss)


def test_starke_autos_gewinnen_haeufiger(k, zandvoort, umgebung):
    """Ein Feld ist nur dann brauchbar, wenn Staerke sich auszahlt.

    **Das Feld wird dafuer eigens gebaut.** Vorher stand hier das Feld
    der kleinen Welt aus ``conftest`` - und dessen vier Autos haben alle
    den Gesamtwert null, sind also gleich stark. Der Test mass damit
    reinen Zufall: ueber 200 Seeds gewann die "vordere Haelfte" in genau
    50 Prozent der Rennen, und dass er ueber die Seeds 0 bis 7 durchging,
    war Glueck. Aufgefallen ist es, als ein Seed kippte.

    Jetzt steht ein Gefaelle im Feld, und zwei Rennlaengen werden
    gemessen: Ueber die Distanz muss sich Staerke durchsetzen.
    """
    mittel, verschleiss = umgebung
    werte = (98_000, 70_000, 30_000, 10_000)
    feld = tuple(
        rn.Teilnehmer(
            auto=ka.gleichverteilt(k, wert, kuerzel=f"S{i}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i, wert in enumerate(werte)
    )
    haelfte = len(feld) // 2
    versuche = 12
    vorne = sum(
        1
        for seed in range(versuche)
        if sn.fahre_wochenende(
            k, LIGA, zandvoort, feld, RUNDEN, Seedquelle(seed), mittel, verschleiss
        ).ergebnisse[0].fahrer
        < haelfte
    )
    assert vorne >= versuche - 1, f"Nur {vorne} von {versuche} Siegen fuer die Starken"


# --- Abgleich mit der vollen Simulation -----------------------------------
def test_schnellmodus_trifft_die_volle_simulation(k, zandvoort, feld, umgebung):
    """Der Schnellmodus darf nicht systematisch schneller oder langsamer sein.

    Sonst waeren Rundenrekorde und Siegerzeiten der Spielerliga - die
    ausfuehrlich faehrt - nicht mit denen der uebrigen 9 Ligen
    vergleichbar. Verglichen wird bei gleichem Wetter: Es kommt in beiden
    Modellen aus demselben Zweig der Seedquelle.
    """
    mittel, verschleiss = umgebung
    grund = np.array([fahre_runde(k, zandvoort, t.auto).zeit_ms for t in feld], dtype=float)

    schnell_zeiten, volle_zeiten = [], []
    for seed in range(3):
        schnell = fahre(k, zandvoort, feld, umgebung, seed)
        wetter = kwet.wuerfle(
            k,
            zandvoort.name,
            int(grund.mean() * RUNDEN),
            int(grund.mean()),
            Seedquelle(seed).zweig("rennwetter"),
        )
        # Gleicher Zweig, gleiches Wetter - sonst vergleicht der Test nur
        # zwei verschiedene Rennsonntage.
        assert schnell.wetter == wetter.zustaende
        voll = rn.simuliere(
            k,
            zandvoort,
            feld,
            RUNDEN,
            Seedquelle(seed),
            mittel,
            wetter=wetter,
            streckenverschleiss=verschleiss,
        )
        schnell_zeiten.append(schnell.siegerzeit_ms)
        volle_zeiten.append(voll.ergebnisse[0].zeit_ms)

    abweichung = sum(schnell_zeiten) / sum(volle_zeiten) - 1.0
    assert abs(abweichung) < 0.02, f"Siegerzeit weicht um {abweichung:+.2%} ab"
