"""Saisonwertung, Auf- und Abstieg (GDD 13).

Punkte je Rennwochenende:

* Rennen, Plaetze 1 bis 20: 40-35-30-25-20-18-16-14-12-11-10-9-8-7-6-5-4-3-2-1
* Schnellste Rennrunde: 3 Punkte, auch ohne Zielankunft
* Qualifying, Plaetze 1 bis 3: 5-3-1

Bei Gleichstand in der Saisonwertung liegt vorn, wer mehr Siege hat, dann
mehr zweite Plaetze und so weiter.

Am Saisonende steigen die Top 3 einer Liga auf und die letzten 3 ab; Liga 1
kennt keinen Aufstieg, Liga 20 keinen Abstieg. Auf- und Abstieg gelten fuer
einzelne Fahrer, nicht fuer Teams.
"""

from __future__ import annotations

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


def rennpunkte(konfiguration: Konfiguration, platz: int) -> int:
    """Punkte fuer eine Rennplatzierung (GDD 13)."""
    tabelle = konfiguration.wert("wertung", "punkte_rennen")
    return int(tabelle[platz - 1]) if 1 <= platz <= len(tabelle) else 0


def qualifyingpunkte(konfiguration: Konfiguration, platz: int) -> int:
    """Punkte fuer einen Qualifying-Platz (GDD 13)."""
    tabelle = konfiguration.wert("wertung", "punkte_qualifying")
    return int(tabelle[platz - 1]) if 1 <= platz <= len(tabelle) else 0


def punkte_fuer(konfiguration: Konfiguration, ergebnis: Rennergebnis) -> int:
    """Alle Punkte eines Fahrers an einem Rennwochenende."""
    punkte = rennpunkte(konfiguration, ergebnis.rennplatz)
    punkte += qualifyingpunkte(konfiguration, ergebnis.qualifyingplatz)
    if ergebnis.schnellste_runde:
        # GDD 13: auch ohne Zielankunft.
        punkte += konfiguration.wert("wertung", "punkte_schnellste_runde")
    return punkte


@dataclass
class Tabelle:
    """Die Saisonwertung einer Liga."""

    liga: int
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
        raise WertungsFehler(f"Fahrer {fahrer} steht nicht in der Tabelle der Liga {self.liga}")


# ---------------------------------------------------------------------------
# Auf- und Abstieg
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Wechsel:
    """Ein Fahrer wechselt die Liga (GDD 13)."""

    fahrer: int
    von_liga: int
    nach_liga: int

    @property
    def ist_aufstieg(self) -> bool:
        return self.nach_liga < self.von_liga


def auf_und_abstieg(
    konfiguration: Konfiguration, tabellen: dict[int, Tabelle]
) -> tuple[Wechsel, ...]:
    """Bestimmt alle Ligawechsel nach einer Saison (GDD 13).

    Die Top 3 steigen auf, die letzten 3 ab. Liga 1 kennt keinen Aufstieg,
    Liga 20 keinen Abstieg.
    """
    aufsteiger = konfiguration.wert("auf_abstieg", "aufsteiger")
    absteiger = konfiguration.wert("auf_abstieg", "absteiger")
    hoechste = 1
    niedrigste = konfiguration.wert("ligen", "anzahl")

    wechsel: list[Wechsel] = []
    for liga in sorted(tabellen):
        stand = tabellen[liga].stand()
        if liga > hoechste:
            for eintrag in stand[:aufsteiger]:
                wechsel.append(Wechsel(eintrag.fahrer, liga, liga - 1))
        if liga < niedrigste:
            for eintrag in stand[-absteiger:]:
                wechsel.append(Wechsel(eintrag.fahrer, liga, liga + 1))
    return tuple(wechsel)


def pruefe_ligastaerken(konfiguration: Konfiguration, tabellen: dict[int, Tabelle]) -> None:
    """Prueft, dass jede Liga voll besetzt ist - sonst geht der Wechsel schief."""
    erwartet = konfiguration.wert("ligen", "autos_je_liga")
    for liga, tabelle in tabellen.items():
        if len(tabelle.eintraege) != erwartet:
            raise WertungsFehler(
                f"Liga {liga} hat {len(tabelle.eintraege)} Fahrer, erwartet {erwartet}"
            )
