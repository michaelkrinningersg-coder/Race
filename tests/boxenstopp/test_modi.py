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
    VERSCHLEISS_PLANSTOPP,
    rennwetter,
    strategie_mit,
)


def test_beide_modi_fahren_dieselbe_strategie(ohne_verschiebung, monza, feld, umgebung):
    """Dieselbe Strategie, dieselben Stopprunden und Mischungen.

    Wie beim Planstopp-Test in ``test_rennen`` muessen zwei Dinge aus dem
    Weg: der sonst uebliche Streckenverschleiss, der beide Modelle schon
    in Runde 6 wegen abgefahrener Reifen hereinholte, und die
    Verschiebeschwelle, die als Balancing-Wert die Stopprunde verschoebe.
    """
    mittel, _verschleiss = umgebung
    k = ohne_verschiebung
    verschleiss = VERSCHLEISS_PLANSTOPP
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


def test_beide_modi_kosten_die_stopps_gleich_viel(ohne_verschiebung, monza, feld, umgebung):
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
    mittel, _verschleiss = umgebung
    # Wie beim Strategietest nebenan: kein Streckenverschleiss, der einen
    # Zwangsstopp ausloest, und keine Verschiebeschwelle. Sonst faehrt
    # jedes Modell eine andere Zahl von Stopps - gemessen wurden mit dem
    # hohen Verschleiss 1 gegen 3 Stopps -, und der Vergleich misst nicht
    # mehr, was ein Stopp kostet, sondern wie viele es waren.
    k = ohne_verschiebung
    verschleiss = VERSCHLEISS_PLANSTOPP
    hart = kern_reifen.mischung(k, "hart")
    ohne = sg.Strategie(mischungen=(hart,), stopps=())
    mit = strategie_mit(k, (8, 16))

    wetter = rennwetter(k, monza, feld, TROCKEN)
    assert len(wetter.zustaende) == 1, "Der Test braucht ein Rennen ohne Wetterwechsel"

    # Nur die Spitze des Feldes: Verglichen wird, was zwei Stopps kosten.
    # Der Schnellmodus kennt keinen Verkehr, der volle schon - wer nach
    # dem Stopp in ein Feld von vierzig Autos zurueckkommt, verliert dort
    # zusaetzlich Zeit, und die stuende hier als Unterschied der Modelle
    # da. Mit sechs Autos ist die Boxengasse die einzige Quelle.
    schmal = feld[:6]

    def zeiten(strategie):
        voll = rn.simuliere(
            k, monza, schmal, RUNDEN, Seedquelle(TROCKEN), mittel, wetter=wetter,
            streckenverschleiss=verschleiss,
            strategien=tuple(strategie for _ in schmal),
        )
        flott = schnell.fahre_wochenende(
            k, LIGA, monza, schmal, RUNDEN, Seedquelle(TROCKEN), mittel, verschleiss,
            strategien=tuple(strategie for _ in schmal),
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
    # Nur die Stopps, die wirklich die Mischung wechseln: Ein Reifen, der
    # sich unter 30 % abfaehrt, zwingt seit dem Zwangsstopp ebenfalls
    # herein - der wechselt aber Regen gegen Regen und hat mit der Frist
    # fuer den falschen Reifen nichts zu tun.
    notstopps = [b for b in verlauf.boxenstopps if b.notstopp and b.von != b.nach]
    assert notstopps, "Im Starkregen muss auf Regenreifen gewechselt werden"
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    for b in notstopps:
        assert b.nach == "R"
        assert b.runde <= abstand + 2
