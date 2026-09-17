"""Tests fuer das Qualifying (GDD 4)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import qualifying as ql
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern.zufall import Seedquelle

LIGA = 10


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecke(k) -> st.Strecke:
    return st.lade(k, "Catalunya")


@pytest.fixture(scope="module")
def feld(k) -> tuple[rn.Teilnehmer, ...]:
    return rn.starterfeld(k, LIGA)


@pytest.fixture(scope="module")
def session(k, strecke, feld) -> ql.Qualifying:
    return ql.fahre(k, strecke, feld, Seedquelle(4711))


# -- Ablauf -----------------------------------------------------------------
def test_jedes_auto_faehrt_genau_eine_gezeitete_runde(session, feld) -> None:
    assert len(session.fahrten) == len(feld)
    assert {f.teilnehmer for f in session.fahrten} == set(range(len(feld)))
    assert all(f.zeit_ms > 0 for f in session.fahrten)


def test_autos_fahren_nacheinander(session) -> None:
    """GDD 4: Jedes Auto faehrt allein."""
    for davor, danach in zip(session.fahrten, session.fahrten[1:], strict=False):
        assert davor.ziel_ms <= danach.beginn_ms


def test_aufwaermrunde_kostet_zeit(session, k) -> None:
    """Die ungezeitete Runde verbraucht Sessionzeit, wird aber nicht gewertet."""
    for fahrt in session.fahrten:
        # Zwischen Beginn und Zielankunft liegen Aufwaermrunde und gezeitete
        # Runde, also deutlich mehr als nur die gewertete Zeit.
        assert fahrt.ziel_ms - fahrt.beginn_ms > fahrt.zeit_ms


def test_sektorzeiten_ergeben_die_rundenzeit(session, k) -> None:
    sektoren = k.wert("strecke", "sektoren")
    for fahrt in session.fahrten:
        assert len(fahrt.sektoren_ms) == sektoren
        assert sum(fahrt.sektoren_ms) == pytest.approx(fahrt.zeit_ms, abs=5)


def test_zeiten_sind_ganze_millisekunden(session) -> None:
    for fahrt in session.fahrten:
        assert isinstance(fahrt.zeit_ms, int)
        assert all(isinstance(wert, int) for wert in fahrt.sektoren_ms)


# -- Startreihenfolge -------------------------------------------------------
def test_erstes_rennen_faehrt_nach_qualifyingstaerke(k, feld) -> None:
    """GDD 4: im ersten Rennen aufsteigend nach Qualifying-Faehigkeit."""
    reihenfolge = ql.startreihenfolge(k, feld)
    staerken = [ql.qualifyingstaerke(k, feld[i]) for i in reihenfolge]
    assert staerken == sorted(staerken)


def test_meisterschaftsfuehrender_faehrt_zuletzt(k, feld) -> None:
    """GDD 4: umgekehrter Meisterschaftsstand."""
    meisterschaft = tuple(range(len(feld)))
    reihenfolge = ql.startreihenfolge(k, feld, meisterschaft)
    assert reihenfolge[-1] == meisterschaft[0]
    assert reihenfolge[0] == meisterschaft[-1]


def test_unvollstaendige_meisterschaft_meldet_fehler(k, feld) -> None:
    with pytest.raises(ValueError, match="genau einmal"):
        ql.startreihenfolge(k, feld, (0, 1, 2))


# -- Aufstellung ------------------------------------------------------------
def test_aufstellung_folgt_den_zeiten(session) -> None:
    zeiten = [
        next(f for f in session.fahrten if f.teilnehmer == i).zeit_ms
        for i in session.aufstellung
    ]
    assert zeiten == sorted(zeiten)


def test_aufstellung_enthaelt_jedes_auto_einmal(session, feld) -> None:
    assert sorted(session.aufstellung) == list(range(len(feld)))
    assert session.startplatz(session.aufstellung[0]) == 1


def test_pole_ist_die_schnellste_runde(session) -> None:
    assert session.pole.zeit_ms == min(f.zeit_ms for f in session.fahrten)


# -- Live-Einsortierung -----------------------------------------------------
def test_zwischenstand_waechst_mit_den_fahrten(session) -> None:
    """GDD 4: Live-Einsortierung ins Ranking."""
    assert session.stand_nach(0) == ()
    assert len(session.stand_nach(1)) == 1
    assert len(session.stand_nach(10)) == 10
    assert len(session.stand_nach(len(session.fahrten))) == len(session.fahrten)


def test_zwischenstand_ist_nach_zeit_geordnet(session) -> None:
    stand = session.stand_nach(12)
    assert [f.zeit_ms for f in stand] == sorted(f.zeit_ms for f in stand)


def test_bestzeit_verbessert_sich_nur(session) -> None:
    """Die aktuelle Bestzeit kann nie schlechter werden."""
    bisher = None
    for anzahl in range(1, len(session.fahrten) + 1):
        beste = session.bestzeit_nach(anzahl)
        if bisher is not None:
            assert beste <= bisher
        bisher = beste
    assert session.bestzeit_nach(0) is None


# -- Wetter und Zufall ------------------------------------------------------
def test_session_hat_ein_wetter(session, k) -> None:
    assert session.wetter.startzustand in k.wert("wetter", "kette")
    assert all(f.zustand in k.wert("wetter", "kette") for f in session.fahrten)


def test_nasses_wetter_macht_langsamer(k, strecke, feld) -> None:
    """Der Grip-Faktor senkt das Tempo (GDD 7)."""
    trockene = []
    nasse = []
    for seed in range(40):
        session = ql.fahre(k, strecke, feld, Seedquelle(seed))
        ziel = trockene if session.pole.zustand in ("trocken", "heiss") else nasse
        ziel.append(session.pole.zeit_ms)
    assert trockene and nasse
    assert min(nasse) > min(trockene)


def test_tagesform_ist_je_auto_verschieden(session) -> None:
    formen = {round(f.tagesform, 9) for f in session.fahrten}
    assert len(formen) > 1


def test_qualifyingbonus_waechst_mit_dem_koennen(k, feld) -> None:
    """GDD 8: Die Q-Spalte ist ein zusaetzliches Gewicht fuer die Runde."""
    from rennmanager.kern import auto as ka

    schwach = ql.qualifyingbonus(k, ka.gleichverteilt(k, 0))
    stark = ql.qualifyingbonus(k, ka.gleichverteilt(k, 100_000))
    assert schwach == pytest.approx(0.0)
    assert stark == pytest.approx(k.wert("qualifying", "bonus", "max_anteil"), rel=0.02)


def test_gleicher_seed_gleiches_qualifying(k, strecke, feld) -> None:
    erste = ql.fahre(k, strecke, feld, Seedquelle(77))
    zweite = ql.fahre(k, strecke, feld, Seedquelle(77))
    assert erste.aufstellung == zweite.aufstellung
    assert erste.fahrten == zweite.fahrten


def test_anderer_seed_anderes_qualifying(k, strecke, feld) -> None:
    erste = ql.fahre(k, strecke, feld, Seedquelle(77))
    zweite = ql.fahre(k, strecke, feld, Seedquelle(78))
    assert erste.fahrten != zweite.fahrten


def test_ohne_teilnehmer_meldet_fehler(k, strecke) -> None:
    with pytest.raises(ValueError, match="Teilnehmer"):
        ql.fahre(k, strecke, (), Seedquelle(1))


def test_staerkere_autos_stehen_meist_vorn(k, strecke, feld) -> None:
    """Der Zufall darf die Rangfolge stoeren, aber nicht umkehren."""
    plaetze = []
    for seed in range(12):
        session = ql.fahre(k, strecke, feld, Seedquelle(seed))
        # Teilnehmer 0 ist das staerkste Auto des Feldes.
        plaetze.append(session.startplatz(0))
    assert sum(plaetze) / len(plaetze) < len(feld) / 3
