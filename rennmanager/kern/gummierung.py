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


def _bezug(konfiguration: Konfiguration) -> float:
    """Der Verschleiss der Bezugsmischung - dort sind beide Faktoren 1,0."""
    kuerzel = konfiguration.wert("strecke", "gummierung", "bezugsmischung")
    for zeile in konfiguration.wert("reifen", "mischungen", "liste"):
        if zeile["kuerzel"] == kuerzel:
            return float(zeile["verschleiss"])
    raise KeyError(f"Bezugsmischung {kuerzel} steht nicht in [reifen.mischungen]")


def auftrag(konfiguration: Konfiguration, mischung) -> float:
    """Wie viel Gummi diese Mischung je Runde liegen laesst.

    **Linear** im Verschleiss: Gummi auf der Strecke *ist* abgefahrener
    Reifen. Was 1,44-mal so schnell abbaut, laesst 1,44-mal so viel
    liegen. Ohne Mischung gilt 1,0 - dann rechnet die Strecke so, als
    fuehre das ganze Feld die Bezugsmischung.
    """
    if mischung is None:
        return 1.0
    return float(mischung.verschleiss) / _bezug(konfiguration)


def ansprechen(konfiguration: Konfiguration, mischung) -> float:
    """Wie viel diese Mischung aus dem liegenden Gummi herausholt.

    **Gedaempft** gegenueber dem Auftrag: Dass sich ein weicher Reifen
    besser in den liegenden Gummi einarbeitet, ist der schwaechere
    Zusammenhang. Deshalb derselbe Quotient, aber mit einem Exponenten
    unter eins - eine Stellschraube statt fuenf erfundener Zahlen.
    """
    if mischung is None:
        return 1.0
    exponent = float(
        konfiguration.wert("strecke", "gummierung", "ansprechen_exponent")
    )
    return auftrag(konfiguration, mischung) ** exponent


def je_runde(konfiguration: Konfiguration, zustand: str) -> float:
    """Was eine gefahrene Auto-Runde bei dieser Lage am Stand aendert.

    Trocken und heiss bauen auf, Regen waescht ab, wechselhaft nur sehr
    wenig - so hat es der Auftraggeber festgelegt. Eine unbekannte Lage
    aendert nichts; das ist die vorsichtige Annahme.
    """
    beitraege = konfiguration.wert("strecke", "gummierung", "je_runde")
    return float(beitraege.get(zustand, 0.0))


def naechster_stand(
    konfiguration: Konfiguration,
    stand: float,
    zustand: str,
    runden: float = 1.0,
    mischung=None,
) -> float:
    """Der Stand nach ``runden`` gefahrenen Auto-Runden bei dieser Lage.

    Die Mischung wirkt **nur auf den Aufbau**. Abgewaschen wird vom
    Regen, nicht vom Reifen - ein Intermediate darf nicht staerker
    abwaschen als ein Regenreifen.
    """
    beitrag = je_runde(konfiguration, zustand)
    if beitrag > 0.0:
        beitrag *= auftrag(konfiguration, mischung)
    return max(0.0, stand + beitrag * runden)


def faktor(konfiguration: Konfiguration, stand: float, mischung=None) -> float:
    """Der Grip-Aufschlag zu diesem Stand, fuer diese Mischung.

    1,0 auf gruener Strecke, hoechstens ``1 + max_anteil * Ansprechen``.
    Ohne Mischung gilt die Bezugsmischung - das ist der Wert, den die
    Anzeige zeigt.
    """
    einstellung = konfiguration.wert("strecke", "gummierung")
    halbwert = float(einstellung["halbwert_runden"])
    if stand <= 0.0 or halbwert <= 0.0:
        return 1.0
    roh = float(einstellung["max_anteil"]) * (1.0 - math.exp(-stand / halbwert))
    return 1.0 + roh * ansprechen(konfiguration, mischung)


def anteil(konfiguration: Konfiguration, stand: float, mischung=None) -> float:
    """Derselbe Aufschlag als Anteil, fuer die Anzeige: 0,0136 statt 1,0136."""
    return faktor(konfiguration, stand, mischung) - 1.0
