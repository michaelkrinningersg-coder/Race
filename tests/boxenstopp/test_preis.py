"""Was ein Boxenstopp kostet (Punkt 39).

Durchfahrt, Halt und Standzeit - gemessen gegen dasselbe Rennen ohne
Stopp. Dazu die Regel, dass am Rennende keiner mehr gestoppt wird.
"""

import pytest

from rennmanager.kern import boxenstopp as bx
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as rn
from rennmanager.kern import strategie as sg
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import RUNDEN, strategie_mit


def test_ein_stopp_kostet_durchfahrt_halt_und_standzeit(
    ohne_verschiebung, monza, feld, umgebung
):
    """Der Preis eines Stopps muss der sein, den boxenstopp.py ausrechnet.

    Gemessen an einem Satz, der praktisch nicht abbaut - sonst
    ueberlagert der frische Reifen nach dem Stopp alles andere.

    Die Toleranz von zwei Sekunden ist die Koernung der Simulation: Sie
    rechnet in Schritten von 50 Millisekunden, beschleunigt aus der Box
    mit der eigenen Grenze statt mit der des Profils, und das Bremsen bis
    zum Stillstand wird als Standzeit gebucht, waehrend das Profil die
    Bremszone schon eingerechnet hat. Auf einen Stopp von rund vierzig
    Sekunden sind das vier Prozent.
    """
    from dataclasses import replace

    mittel, verschleiss = umgebung
    glatt = replace(kern_reifen.mischung(ohne_verschiebung, "hart"), verschleiss=1e-6)
    ohne = rn.simuliere(
        ohne_verschiebung, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(sg.Strategie(mischungen=(glatt,), stopps=()),),
    )
    mit = rn.simuliere(
        ohne_verschiebung, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(sg.Strategie(mischungen=(glatt, glatt), stopps=(12,)),),
    )
    grenzen = kern_tempo.grenzen_aus(ohne_verschiebung, feld[0].auto)
    erwartet = (
        bx.durchfahrtsverlust_ms(ohne_verschiebung, monza, grenzen)
        + bx.haltverlust_ms(ohne_verschiebung, grenzen)
        + mit.boxenstopps[0].standzeit_ms
    )
    gemessen = mit.ergebnisse[0].zeit_ms - ohne.ergebnisse[0].zeit_ms
    assert gemessen == pytest.approx(erwartet, abs=2_000)


def test_in_der_boxengasse_wird_langsam_gefahren(
    ohne_verschiebung, monza, feld, umgebung
):
    """Die Runde des Stopps ist laenger als die davor - auch ohne Standzeit."""
    from dataclasses import replace

    mittel, verschleiss = umgebung
    glatt = replace(kern_reifen.mischung(ohne_verschiebung, "hart"), verschleiss=1e-6)
    mit = rn.simuliere(
        ohne_verschiebung, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(sg.Strategie(mischungen=(glatt, glatt), stopps=(12,)),),
    )
    runden = mit.protokolle[0].rundenzeiten_ms
    # Runde 12 traegt die Einfahrt, Runde 13 Standzeit und Ausfahrt.
    assert runden[11] > runden[9]
    assert runden[12] > runden[9]
    assert runden[13] == pytest.approx(runden[9], rel=0.02)


def test_am_rennende_wird_nicht_mehr_gestoppt(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(strategie_mit(k, (RUNDEN - 1,)),),
    )
    for b in verlauf.boxenstopps:
        assert b.runde < RUNDEN
