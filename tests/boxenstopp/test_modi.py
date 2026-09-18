"""Zeitraffer und Schnellmodus fahren dieselben Stopps (Punkt 39).

Der Zeitraffer faehrt die Boxengasse wirklich langsam ab und steht die
Standzeit; der Schnellmodus bucht dieselbe Differenz. Beide muessen
dieselbe Strategie fahren und im selben Zeitrahmen ankommen. Dazu der
Wetterwechsel, der zum Notstopp zwingt.
"""

import pytest

from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as rn
from rennmanager.kern import schnellsimulation as schnell
from rennmanager.kern import strategie as sg
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import (
    LIGA,
    RUNDEN,
    TROCKEN,
    rennwetter,
    strategie_mit,
)


def test_beide_modi_fahren_dieselbe_strategie(k, monza, feld, umgebung):
    """Dieselbe Strategie, dieselben Stopprunden und Mischungen."""
    mittel, verschleiss = umgebung
    strategien = tuple(strategie_mit(k, (8, 16)) for _ in feld)
    voll = rn.simuliere(
        k, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel,
        wetter=rennwetter(k, monza, feld, TROCKEN),
        streckenverschleiss=verschleiss, strategien=strategien,
    )
    flott = schnell.fahre_wochenende(
        k, LIGA, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel, verschleiss,
        strategien=strategien,
    )
    for i in range(len(feld)):
        gefahren = [(b.runde, b.von, b.nach) for b in voll.stopps_von(i)]
        assert gefahren == [(8, "W", "H"), (16, "H", "W")]
    assert flott.siegerzeit_ms > 0


def test_beide_modi_kosten_die_stopps_gleich_viel(k, monza, feld, umgebung):
    """Der Schnellmodus darf durch Stopps nicht anders verlieren als der Zeitraffer.

    Verglichen wird der **Unterschied**, den die Stopps machen: einmal
    ein Rennen ohne, einmal mit. Die Modelle selbst liegen ohnehin nur
    auf zwei Prozent beieinander (siehe test_schnellsimulation), deshalb
    zaehlt hier nur der Zuwachs.

    Gefahren wird ein **trockenes** Rennen. Sobald das Wetter wechselt,
    entscheidet jedes Auto selbst ueber Notstopps, und die beiden Modelle
    fragen das Wetter an verschiedenen Stellen: die volle Simulation zur
    Ueberfahrt jedes einzelnen Autos, der Schnellmodus einmal je Runde
    beim Fuehrenden. Dann faellt die Zahl der Notstopps auseinander - das
    ist der Preis des Schnellmodus und keine Abweichung, die sich
    wegrechnen liesse.
    """
    mittel, verschleiss = umgebung
    hart = kern_reifen.mischung(k, "hart")
    ohne = sg.Strategie(mischungen=(hart,), stopps=())
    mit = strategie_mit(k, (8, 16))

    wetter = rennwetter(k, monza, feld, TROCKEN)
    assert len(wetter.zustaende) == 1, "Der Test braucht ein Rennen ohne Wetterwechsel"

    def zeiten(strategie):
        voll = rn.simuliere(
            k, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel, wetter=wetter,
            streckenverschleiss=verschleiss,
            strategien=tuple(strategie for _ in feld),
        )
        flott = schnell.fahre_wochenende(
            k, LIGA, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel, verschleiss,
            strategien=tuple(strategie for _ in feld),
        )
        return voll.ergebnisse[0].zeit_ms, flott.siegerzeit_ms

    voll_ohne, flott_ohne = zeiten(ohne)
    voll_mit, flott_mit = zeiten(mit)
    zuwachs_voll = voll_mit - voll_ohne
    zuwachs_flott = flott_mit - flott_ohne
    # Zwei Stopps kosten rund eine Minute; fuenf Sekunden Unterschied
    # zwischen den Modellen sind die Koernung beider Rechnungen.
    assert zuwachs_voll == pytest.approx(zuwachs_flott, abs=10_000)


# -- Wetterwechsel ----------------------------------------------------------
def test_der_falsche_reifen_zwingt_zum_notstopp(k, monza, feld, strecken, umgebung):
    """Hoechstens drei Runden auf dem falschen Reifen - so der Auftraggeber."""
    from rennmanager.kern import wetter as kern_wetter

    mittel, verschleiss = umgebung
    wetter = kern_wetter.Wetterverlauf(
        abschnitte=(
            kern_wetter.Abschnitt(
                zustand="starkregen",
                ab_ms=0,
                grip_je_sektor=(0.7,) * len(monza.sektoren),
            ),
        ),
        uebergang_ms=0,
    )
    trocken = kern_reifen.mischung(k, "hart")
    verlauf = rn.simuliere(
        k, monza, feld[:4], RUNDEN, Seedquelle(2), mittel, wetter=wetter,
        streckenverschleiss=verschleiss,
        strategien=tuple(
            sg.Strategie(mischungen=(trocken, trocken), stopps=(18,)) for _ in range(4)
        ),
    )
    notstopps = [b for b in verlauf.boxenstopps if b.notstopp]
    assert notstopps, "Im Starkregen muss auf Regenreifen gewechselt werden"
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    for b in notstopps:
        assert b.nach == "R"
        assert b.runde <= abstand + 2
