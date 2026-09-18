"""Der Boxenstopp im Rennmodell (Punkt 39).

Ob ueberhaupt gestoppt wird, wann, und was der Stopp mit den Reifen
und der Mischung macht.
"""

import pytest

from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as rn
from rennmanager.kern import strategie as sg
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import RUNDEN, VERSCHLEISS_PLANSTOPP, strategie_mit


# -- Der Stopp im Rennen ----------------------------------------------------
def test_ohne_strategie_wird_nicht_gestoppt(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
    )
    assert verlauf.boxenstopps == ()


def test_der_geplante_stopp_wird_gefahren(k, monza, feld, umgebung):
    """Hier zaehlt der **Plan**, also der mildere Streckenverschleiss.

    Mit dem sonst ueblichen Faktor kaeme das Auto schon in Runde 6 wegen
    abgefahrener Reifen herein, und der geplante Stopp rutschte nach
    hinten - das prueft der Zwangsstopp-Test weiter unten.
    """
    mittel, _verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=VERSCHLEISS_PLANSTOPP,
        strategien=tuple(strategie_mit(k, (8, 16)) for _ in range(3)),
    )
    for i in range(3):
        stopps = verlauf.stopps_von(i)
        assert [b.runde for b in stopps] == [8, 16]
        assert [b.von for b in stopps] == ["W", "H"]
        assert [b.nach for b in stopps] == ["H", "W"]
        assert all(not b.notstopp for b in stopps)


@pytest.fixture(scope="module")
def einzelstopp(k, monza, feld, umgebung):
    """Ein Auto, ein geplanter Stopp in Runde 12 - einmal gefahren.

    Punkt 77: Reifen und Mischung wurden vorher in zwei getrennten
    Laeufen geprueft, die sich nur in der Mischungspflicht unterschieden.
    Die aendert am Fahren nichts, also genuegt ein Lauf fuer beides - das
    spart gemessen acht Sekunden.
    """
    mittel, verschleiss = umgebung
    return rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(strategie_mit(k, (12,)),),
        mischungspflicht=True,
    )


def test_der_stopp_setzt_die_reifen_zurueck(einzelstopp):
    stopp = einzelstopp.stopps_von(0)[0]
    davor = einzelstopp.reifen_zu(stopp.zeit_ms - 1_000)[0]
    danach = einzelstopp.reifen_zu(stopp.zeit_ms + 20_000)[0]
    assert davor < 1.0
    assert danach > davor


def test_die_mischung_steht_im_verlauf(einzelstopp):
    stopp = einzelstopp.stopps_von(0)[0]
    assert einzelstopp.mischung_zu(0)[0] == "W"
    assert einzelstopp.mischung_zu(stopp.zeit_ms + 20_000)[0] == "H"
    assert einzelstopp.gefahrene_mischungen(0, einzelstopp.dauer_ms) == ("W", "H")
    assert einzelstopp.mischungspflicht


# -- Zwangsstopp bei abgefahrenem Reifen ------------------------------------
def test_der_abgefahrene_reifen_zwingt_zum_stopp(k, monza, feld, umgebung):
    """Entscheidung des Auftraggebers: unter 30 % Restprofil herein.

    Vorher zwang nur das Wetter. Ein Auto, dessen Satz vor der geplanten
    Stopprunde durch war, schlich den Rest des Rennens auf blankem Gummi
    - gemessen ueber fuenf Strecken drei bis vier Autos je Rennen.
    """
    mittel, verschleiss = umgebung
    ohne_plan = sg.Strategie(mischungen=(kern_reifen.mischung(k, "weich"),), stopps=())
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(ohne_plan,),
    )
    stopps = verlauf.stopps_von(0)
    assert stopps, "Ein durchgefahrener Satz muss das Auto hereinzwingen"
    schwelle = k.wert("boxenstopp", "strategie", "notstopp_ab_restprofil")
    assert all(b.notstopp for b in stopps)
    assert stopps[0].restprofil < schwelle


def test_in_den_letzten_runden_wird_nicht_mehr_gestoppt(k, monza, feld, umgebung):
    """Dieselbe Sperre wie fuer jeden anderen Stopp: die letzten Runden."""
    mittel, verschleiss = umgebung
    ohne_plan = sg.Strategie(mischungen=(kern_reifen.mischung(k, "weich"),), stopps=())
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(ohne_plan,),
    )
    sperre = k.wert("boxenstopp", "strategie", "sperre_runden")
    assert all(b.runde <= RUNDEN - sperre for b in verlauf.boxenstopps)


def test_zwischen_zwei_zwangsstopps_liegt_der_mindestabstand(k, monza, feld, umgebung):
    """Sonst kaeme ein Auto mit sehr hohem Verschleiss Runde um Runde herein."""
    mittel, verschleiss = umgebung
    ohne_plan = sg.Strategie(mischungen=(kern_reifen.mischung(k, "weich"),), stopps=())
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(ohne_plan,),
    )
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    runden = [b.runde for b in verlauf.stopps_von(0)]
    assert all(b - a >= abstand for a, b in zip(runden, runden[1:], strict=False))
