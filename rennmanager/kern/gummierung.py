"""Die Strecke gummiert ein (Punkt 88).

Je mehr auf einer trockenen Strecke gefahren wird, desto mehr Gummi
liegt auf der Ideallinie und desto mehr Grip gibt sie her. Regen waescht
das wieder ab; sobald es trocknet, baut es sich von neuem auf.

**Eine einzige Zahl traegt das.** Der *Stand* zaehlt gefahrene
**Auto-Runden**: Jede Runde, die ein Auto auf dieser Strecke in dieser
Session dreht, aendert ihn um den Beitrag der gerade herrschenden Lage -
bei trocken und heiss nach oben, bei Regen nach unten, bei wechselhaft
fast gar nicht. Unter null faellt er nie.

Aus dem Stand wird der Grip-Aufschlag:

    faktor(n) = 1 + max_anteil * (1 - e^(-n / halbwert_runden))

Also viel am Anfang und immer weniger, je mehr schon liegt. Der Aufschlag
wirkt **nach** ``wetter.grip_fuer`` auf den wirksamen Grip. Davor waere
er falsch: Dort daempft die Wetterfaehigkeit die Abweichung von 1,0, und
ein Regenspezialist bekaeme vom Gummi weniger ab als ein anderer. Gummi
auf der Strecke ist aber keine Fahrkunst.

**Warum Auto-Runden und nicht Zeit.** Dreissig Autos gummieren schneller
ein als eines. Im Rennen geht es damit von selbst schneller als im
Qualifying, ohne dass irgendwo eine zweite Zahl noetig waere - und es
bleibt ueber den Seed reproduzierbar, weil kein Wurf mitspielt.

**Der Anker bleibt gruen.** Die Kalibrierung aus GDD 9 rechnet eine
einzelne Runde ohne Wetter und ohne Verkehr; dort ist der Stand null und
der Faktor genau 1,0. Zandvoort bei S=98.000 bleibt bei 180,00 km/h.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


def je_runde(konfiguration: Konfiguration, zustand: str) -> float:
    """Was eine gefahrene Auto-Runde bei dieser Lage am Stand aendert.

    Trocken und heiss bauen auf, Regen waescht ab, wechselhaft nur sehr
    wenig - so hat es der Auftraggeber festgelegt. Eine unbekannte Lage
    aendert nichts; das ist die vorsichtige Annahme.
    """
    beitraege = konfiguration.wert("strecke", "gummierung", "je_runde")
    return float(beitraege.get(zustand, 0.0))


def naechster_stand(
    konfiguration: Konfiguration, stand: float, zustand: str, runden: float = 1.0
) -> float:
    """Der Stand nach ``runden`` gefahrenen Auto-Runden bei dieser Lage."""
    return max(0.0, stand + je_runde(konfiguration, zustand) * runden)


def faktor(konfiguration: Konfiguration, stand: float) -> float:
    """Der Grip-Aufschlag zu diesem Stand: 1,0 bis 1 + ``max_anteil``."""
    einstellung = konfiguration.wert("strecke", "gummierung")
    halbwert = float(einstellung["halbwert_runden"])
    if stand <= 0.0 or halbwert <= 0.0:
        return 1.0
    return 1.0 + float(einstellung["max_anteil"]) * (1.0 - math.exp(-stand / halbwert))


def anteil(konfiguration: Konfiguration, stand: float) -> float:
    """Derselbe Aufschlag als Anteil, fuer die Anzeige: 0,0136 statt 1,0136."""
    return faktor(konfiguration, stand) - 1.0
