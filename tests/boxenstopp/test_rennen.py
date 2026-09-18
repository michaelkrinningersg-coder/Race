"""Der Boxenstopp im Rennmodell (Punkt 39).

Ob ueberhaupt gestoppt wird, wann, und was der Stopp mit den Reifen
und der Mischung macht.
"""

import pytest

from rennmanager.kern import rennen as rn
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import RUNDEN, strategie_mit


# -- Der Stopp im Rennen ----------------------------------------------------
def test_ohne_strategie_wird_nicht_gestoppt(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
    )
    assert verlauf.boxenstopps == ()


def test_der_geplante_stopp_wird_gefahren(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
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
