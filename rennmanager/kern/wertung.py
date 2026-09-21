"""Meisterschaft (GDD 13, Punkt 101).

Es gibt ein Feld und eine Tabelle. Jeder Platz bringt Punkte aus einer
festen Tabelle, die der Auftraggeber vorgegeben hat:

    100, 90, 80, 76, 72, dann in Zweierschritten 70 bis 20 auf Platz 31,
    danach 19 bis 1 auf Platz 50.

Dazu kommen Zusatzpunkte als Anteil der Siegerpunkte, aufgerundet und
mindestens 1: die schnellste Rennrunde (auch ohne Zielankunft, GDD 13)
und die ersten drei des Qualifyings.

Jeder Platz bekommt Punkte, auch die Ausgefallenen - sie stehen nach
absolvierten Runden und Zeit hinter den Angekommenen (siehe
``rennen._ergebnisse``).

Bei Gleichstand entscheiden mehr Siege, dann mehr zweite Plaetze und so
weiter. Auf- und Abstieg gibt es seit Punkt 101 nicht mehr; mit den Ligen
ist auch die Punkteleiter ueber mehrere Ligen weggefallen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class WertungsFehler(Exception):
    """Eine Wertung passt nicht zur Konfiguration."""


@dataclass(frozen=True)
class Rennergebnis:
    """Was ein Fahrer an einem Rennwochenende erreicht hat."""

    fahrer: int
    rennplatz: int
    qualifyingplatz: int
    schnellste_runde: bool = False
    ausgefallen: bool = False


@dataclass
class Eintrag:
    """Eine Zeile der Saisontabelle."""

    fahrer: int
    punkte: int = 0
    # Wie oft der Fahrer auf jedem Platz stand, Index 0 = Sieg.
    platzierungen: list[int] = field(default_factory=list)
    siege: int = 0
    podien: int = 0
    poles: int = 0
    schnellste_runden: int = 0
    ausfaelle: int = 0
    rennen: int = 0

    def zaehle(self, platz: int, autos: int) -> None:
        if len(self.platzierungen) < autos:
            self.platzierungen.extend([0] * (autos - len(self.platzierungen)))
        self.platzierungen[platz - 1] += 1


def punktetabelle(konfiguration: Konfiguration) -> tuple[int, ...]:
    """Die Punkte je Platz, Platz 1 zuerst (Punkt 101)."""
    return tuple(int(wert) for wert in konfiguration.wert("wertung", "punkte_je_platz"))


def siegerpunkte(konfiguration: Konfiguration) -> int:
    """Was ein Sieg bringt - der Bezug aller Zusatzpunkte."""
    return punktetabelle(konfiguration)[0]


def rennpunkte(konfiguration: Konfiguration, platz: int) -> int:
    """Punkte fuer eine Rennplatzierung (GDD 13, Punkt 101).

    Jeder Platz des Feldes bekommt Punkte; ausserhalb gibt es keine.
    """
    tabelle = punktetabelle(konfiguration)
    if not 1 <= platz <= len(tabelle):
        return 0
    return tabelle[platz - 1]


def _anteilspunkte(konfiguration: Konfiguration, anteil: float) -> int:
    """Ein Anteil der Siegerpunkte, aufgerundet, mindestens 1."""
    return max(1, math.ceil(siegerpunkte(konfiguration) * anteil - 1e-9))


def qualifyingpunkte(konfiguration: Konfiguration, platz: int) -> int:
    """Punkte fuer einen Qualifying-Platz (GDD 13)."""
    anteile = konfiguration.wert("wertung", "anteil_qualifying")
    if not 1 <= platz <= len(anteile):
        return 0
    return _anteilspunkte(konfiguration, anteile[platz - 1])


def punkte_schnellste_runde(konfiguration: Konfiguration) -> int:
    """Punkte fuer die schnellste Rennrunde, auch ohne Zielankunft."""
    return _anteilspunkte(
        konfiguration, konfiguration.wert("wertung", "anteil_schnellste_runde")
    )


def punkte_fuer(konfiguration: Konfiguration, ergebnis: Rennergebnis) -> int:
    """Alle Punkte eines Fahrers an einem Rennwochenende."""
    punkte = rennpunkte(konfiguration, ergebnis.rennplatz)
    punkte += qualifyingpunkte(konfiguration, ergebnis.qualifyingplatz)
    if ergebnis.schnellste_runde:
        punkte += punkte_schnellste_runde(konfiguration)
    return punkte


@dataclass
class Tabelle:
    """Die Saisonwertung des Feldes."""

    eintraege: dict[int, Eintrag] = field(default_factory=dict)

    def verbuche(self, konfiguration: Konfiguration, ergebnisse: list[Rennergebnis]) -> None:
        """Traegt ein ganzes Rennwochenende ein."""
        autos = konfiguration.wert("rennen", "autos")
        for ergebnis in ergebnisse:
            eintrag = self.eintraege.setdefault(ergebnis.fahrer, Eintrag(ergebnis.fahrer))
            eintrag.punkte += punkte_fuer(konfiguration, ergebnis)
            eintrag.zaehle(ergebnis.rennplatz, autos)
            eintrag.rennen += 1
            if ergebnis.rennplatz == 1:
                eintrag.siege += 1
            if ergebnis.rennplatz <= 3:
                eintrag.podien += 1
            if ergebnis.qualifyingplatz == 1:
                eintrag.poles += 1
            if ergebnis.schnellste_runde:
                eintrag.schnellste_runden += 1
            if ergebnis.ausgefallen:
                eintrag.ausfaelle += 1

    def stand(self) -> list[Eintrag]:
        """Die Tabelle, bester zuerst (GDD 13).

        Bei Punktgleichheit entscheidet, wer mehr Siege hat, dann mehr
        zweite Plaetze und so weiter.
        """
        return sorted(
            self.eintraege.values(),
            key=lambda e: (-e.punkte, [-anzahl for anzahl in e.platzierungen], e.fahrer),
        )

    def platz_von(self, fahrer: int) -> int:
        for platz, eintrag in enumerate(self.stand(), start=1):
            if eintrag.fahrer == fahrer:
                return platz
        raise WertungsFehler(f"Fahrer {fahrer} steht nicht in der Tabelle")


# ---------------------------------------------------------------------------
# Live-Meisterschaftsstand (Punkt 73)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Livezeile:
    """Eine Zeile des Meisterschaftsstands waehrend eines Rennens.

    ``punkte`` ist der Stand **einschliesslich** der Punkte, die dieser
    Fahrer fuer seine derzeitige Position bekaeme; ``zuwachs`` sind genau
    diese Punkte. ``veraenderung`` sagt, wie viele Plaetze er in der
    Meisterschaft gewinnt oder verliert, wenn das Rennen so ausgeht -
    positiv heisst nach vorn.
    """

    fahrer: int
    platz: int
    punkte: int
    zuwachs: int
    platz_vorher: int
    punkte_vorher: int

    @property
    def veraenderung(self) -> int:
        return self.platz_vorher - self.platz


def livewertung(
    konfiguration: Konfiguration,
    tabelle: Tabelle,
    ergebnisse: list[Rennergebnis],
) -> list[Livezeile]:
    """Der Meisterschaftsstand, als waere das Rennen jetzt zu Ende.

    Rein rechnerisch und ohne Nebenwirkung: Die Tabelle bleibt, wie sie
    ist. Das Rennen laeuft ja noch - was hier steht, ist eine Vorschau auf
    den Stand, wenn es so ausginge. Erst am Rennende schreibt
    ``verbuche`` den Stand wirklich fort.

    Qualifyingpunkte und die schnellste Runde zaehlen mit, weil sie
    genauso in ``punkte_fuer`` stehen (GDD 13).

    :param tabelle: der Stand **vor** diesem Rennen
    :param ergebnisse: die derzeitige Lage im Rennen je Fahrer
    """
    vorher = {e.fahrer: platz for platz, e in enumerate(tabelle.stand(), start=1)}
    punkte_vorher = {f: e.punkte for f, e in tabelle.eintraege.items()}

    zuwachs = {e.fahrer: punkte_fuer(konfiguration, e) for e in ergebnisse}
    platzierungen = {e.fahrer: e.rennplatz for e in ergebnisse}
    beteiligt = set(punkte_vorher) | set(zuwachs)

    def schluessel(fahrer: int) -> tuple:
        # Wie ``stand``: Punkte zuerst; bei Gleichstand liegt vorn, wer im
        # laufenden Rennen weiter vorn ist - das ist die Zahl, die sich
        # gerade aendert.
        gesamt = punkte_vorher.get(fahrer, 0) + zuwachs.get(fahrer, 0)
        return (-gesamt, platzierungen.get(fahrer, 10**6), fahrer)

    return [
        Livezeile(
            fahrer=fahrer,
            platz=platz,
            punkte=punkte_vorher.get(fahrer, 0) + zuwachs.get(fahrer, 0),
            zuwachs=zuwachs.get(fahrer, 0),
            platz_vorher=vorher.get(fahrer, platz),
            punkte_vorher=punkte_vorher.get(fahrer, 0),
        )
        for platz, fahrer in enumerate(sorted(beteiligt, key=schluessel), start=1)
    ]


def pruefe_feldgroesse(konfiguration: Konfiguration, tabelle: Tabelle) -> None:
    """Prueft, dass die Tabelle das ganze Feld fuehrt."""
    erwartet = konfiguration.wert("rennen", "autos")
    if len(tabelle.eintraege) != erwartet:
        raise WertungsFehler(
            f"Die Tabelle fuehrt {len(tabelle.eintraege)} Fahrer, erwartet {erwartet}"
        )
