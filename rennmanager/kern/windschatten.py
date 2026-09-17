"""Windschatten: der Sog hinter einem anderen Auto (Punkt 7).

Die Simulation kannte ihn bisher gar nicht - GDD 4 nennt Folgen und
Ueberholen, aber keinen Sog. Er ist mit dem Auftraggeber abgestimmt
(OFFENE_PUNKTE.md, Punkt 48) und in drei Regeln gefasst:

* Er wirkt **nur auf Geraden**. In Kurven bringt er nichts.
* Er wirkt **nur im Fenster von 30 m bis auf gleiche Hoehe**, dicht
  dahinter am staerksten und bei 30 m gar nicht mehr.
* Er wirkt **einmal je Gerade**. Wer einmal auf gleicher Hoehe war, ist
  aus dem Sog heraus und bekommt ihn auf dieser Geraden nicht wieder.

Wie stark er ausfaellt, haengt an der Eigenschaft ``windschatten``. Sie
steht neben der Wirkungsmatrix aus GDD 8, damit Gesamtwert, Bereichswerte
und die Kalibriertabelle aus GDD 9 unberuehrt bleiben.

Der Sog hebt das moegliche Tempo des Verfolgers. Ob er damit vorbeikommt,
entscheidet danach ``rennmanager.kern.rennen.erfolgschance`` wie bisher:
Ein groesserer Tempovorteil heisst eine bessere Chance. Genau das ist der
Zweck - ohne Sog entstand ein Ueberholmanoever nur aus dem Unterschied der
freien Profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto
from rennmanager.kern.tempo import leistungsanteil

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Eigenschaft neben der Wirkungsmatrix; fehlt sie, gilt 0 (GDD 1).
WINDSCHATTEN = "windschatten"


def gewinn(konfiguration: Konfiguration, auto: Auto) -> float:
    """Tempogewinn dicht hinter einem anderen Auto, 0 bis 1."""
    einstellung = konfiguration.wert("windschatten")
    anteil = min(
        leistungsanteil(auto.wetterwert(WINDSCHATTEN), konfiguration.wert("skala", "referenz")),
        1.0,
    )
    bei_null = einstellung["gewinn_bei_null"]
    return bei_null + (einstellung["gewinn_bei_maximum"] - bei_null) * anteil


def fenster_m(konfiguration: Konfiguration) -> float:
    """Ab welchem Abstand es keinen Sog mehr gibt."""
    return float(konfiguration.wert("windschatten", "fenster_m"))


def faktor(konfiguration: Konfiguration, auto: Auto, abstand_m: float) -> float:
    """Faktor aufs Tempo bei diesem Abstand zum Vordermann.

    Voll dicht dahinter, linear auf 1,0 bei ``fenster_m``. Ausserhalb des
    Fensters und auf gleicher Hoehe oder davor gibt es keinen Sog.
    """
    grenze = fenster_m(konfiguration)
    if grenze <= 0.0 or abstand_m <= 0.0 or abstand_m >= grenze:
        return 1.0
    return 1.0 + gewinn(konfiguration, auto) * (1.0 - abstand_m / grenze)
