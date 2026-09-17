"""Kalender und Zeitmodell (GDD 2).

Eine Saison laeuft vom 1. Januar bis zum 31. Dezember. Das erste Rennen
ist der erste Sonntag ab dem 1. Maerz, danach folgt alle 14 Tage eines;
das zwanzigste liegt 266 Tage nach dem ersten, also Ende November.

Ein 14-Tage-Zyklus hat 10 nutzbare Tage. Die uebrigen vier sind zwei
Reisetage, der Qualifying-Samstag und der Renn-Sonntag. Vor- und
Nachsaison sind voll nutzbar.

Zeit ist dabei eine Kapazitaet: Jeder nutzbare Tag hat zwei Plaetze, einen
fuer den Fahrer (Training) und einen fuer die Werkstatt (Entwicklung).
Ohne dieses Modell waere Zeit bei hohen Werten nicht bezahlbar - bis
98.000 waeren rund 9.800 Einzelschritte noetig.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class KalenderFehler(Exception):
    """Der Kalender laesst sich mit dieser Konfiguration nicht bilden."""


class Tagesart(Enum):
    """Wofuer ein Tag im Kalender steht (GDD 2)."""

    NUTZBAR = "nutzbar"
    REISE = "reise"
    QUALIFYING = "qualifying"
    RENNEN = "rennen"

    @property
    def bezeichnung(self) -> str:
        return {
            Tagesart.NUTZBAR: "Nutzbar",
            Tagesart.REISE: "Reise",
            Tagesart.QUALIFYING: "Qualifying",
            Tagesart.RENNEN: "Rennen",
        }[self]


@dataclass(frozen=True)
class Kalendertag:
    """Ein Tag der Saison."""

    datum: dt.date
    art: Tagesart
    # Nummer des Rennwochenendes, zu dem der Tag gehoert (1 bis 20);
    # in der Vor- und Nachsaison None.
    rennen: int | None

    @property
    def ist_nutzbar(self) -> bool:
        return self.art is Tagesart.NUTZBAR


@dataclass(frozen=True)
class Saison:
    """Der Kalender eines Jahres."""

    jahr: int
    tage: tuple[Kalendertag, ...]
    renntage: tuple[dt.date, ...]

    def tag(self, datum: dt.date) -> Kalendertag:
        stelle = (datum - self.tage[0].datum).days
        if not 0 <= stelle < len(self.tage):
            raise KalenderFehler(f"{datum} liegt nicht in der Saison {self.jahr}")
        return self.tage[stelle]

    @property
    def erstes_rennen(self) -> dt.date:
        return self.renntage[0]

    @property
    def letztes_rennen(self) -> dt.date:
        return self.renntage[-1]

    def rennnummer_nach(self, datum: dt.date) -> int | None:
        """Nummer des naechsten Rennens ab diesem Tag, 1-basiert."""
        for nummer, renntag in enumerate(self.renntage, start=1):
            if renntag >= datum:
                return nummer
        return None

    def naechster_renntag(self, datum: dt.date) -> dt.date | None:
        nummer = self.rennnummer_nach(datum)
        return self.renntage[nummer - 1] if nummer else None

    def nutzbare_tage(self, von: dt.date, bis: dt.date) -> tuple[Kalendertag, ...]:
        """Alle nutzbaren Tage in einem Zeitraum, Grenzen eingeschlossen."""
        return tuple(
            tag for tag in self.tage if von <= tag.datum <= bis and tag.ist_nutzbar
        )

    def zyklus_vor(self, rennen: int) -> tuple[Kalendertag, ...]:
        """Die Tage, die zu einem Rennwochenende gehoeren (GDD 2)."""
        return tuple(tag for tag in self.tage if tag.rennen == rennen)

    @property
    def vorsaison(self) -> tuple[Kalendertag, ...]:
        """1. Januar bis zum ersten Rennwochenende, voll nutzbar."""
        return tuple(tag for tag in self.tage if tag.rennen == 1 and tag.ist_nutzbar)

    @property
    def nachsaison(self) -> tuple[Kalendertag, ...]:
        """Nach dem letzten Rennen bis zum 31. Dezember, voll nutzbar."""
        return tuple(
            tag for tag in self.tage if tag.datum > self.letztes_rennen and tag.ist_nutzbar
        )


def erstes_rennen(konfiguration: Konfiguration, jahr: int) -> dt.date:
    """Der erste Sonntag ab dem im Kalender genannten Stichtag (GDD 2)."""
    stichtag = dt.date(
        jahr,
        konfiguration.wert("kalender", "saisonstart_monat"),
        konfiguration.wert("kalender", "saisonstart_tag"),
    )
    wochentag = konfiguration.wert("kalender", "rennen_wochentag")
    return stichtag + dt.timedelta(days=(wochentag - stichtag.weekday()) % 7)


def erzeuge(konfiguration: Konfiguration, jahr: int) -> Saison:
    """Baut den Kalender eines Jahres (GDD 2)."""
    anzahl = konfiguration.wert("kalender", "rennen_je_saison")
    abstand = konfiguration.wert("kalender", "abstand_tage")
    nutzbar_je_zyklus = konfiguration.wert("kalender", "nutzbare_tage_je_zyklus")

    erster = erstes_rennen(konfiguration, jahr)
    renntage = tuple(erster + dt.timedelta(days=abstand * n) for n in range(anzahl))
    if renntage[-1].year != jahr:
        raise KalenderFehler(
            f"Das letzte Rennen faellt auf {renntage[-1]} und damit aus dem Jahr {jahr}"
        )

    # Vier Tage je Rennwochenende sind nicht nutzbar: zwei Reisetage, der
    # Qualifying-Samstag und der Renn-Sonntag. Die Zahl folgt aus dem
    # Zyklus, damit Konfiguration und Kalender nicht auseinanderlaufen.
    unnutzbar = abstand - nutzbar_je_zyklus
    if unnutzbar < 2:
        raise KalenderFehler(
            f"{abstand} Tage je Zyklus lassen nach {nutzbar_je_zyklus} nutzbaren "
            "keinen Platz fuer Reise, Qualifying und Rennen"
        )
    reisetage = unnutzbar - 2

    besonders: dict[dt.date, Tagesart] = {}
    fuer_rennen: dict[dt.date, int] = {}
    for nummer, renntag in enumerate(renntage, start=1):
        besonders[renntag] = Tagesart.RENNEN
        besonders[renntag - dt.timedelta(days=1)] = Tagesart.QUALIFYING
        for versatz in range(2, 2 + reisetage):
            besonders[renntag - dt.timedelta(days=versatz)] = Tagesart.REISE
        # Alles seit dem vorigen Rennen gehoert zu diesem Rennwochenende.
        beginn = renntage[nummer - 2] + dt.timedelta(days=1) if nummer > 1 else dt.date(jahr, 1, 1)
        tag = beginn
        while tag <= renntag:
            fuer_rennen[tag] = nummer
            tag += dt.timedelta(days=1)

    anfang = dt.date(jahr, 1, 1)
    ende = dt.date(
        jahr,
        konfiguration.wert("kalender", "nachsaison_ende_monat"),
        konfiguration.wert("kalender", "nachsaison_ende_tag"),
    )
    tage = []
    tag = anfang
    while tag <= ende:
        tage.append(
            Kalendertag(
                datum=tag,
                art=besonders.get(tag, Tagesart.NUTZBAR),
                rennen=fuer_rennen.get(tag),
            )
        )
        tag += dt.timedelta(days=1)

    return Saison(jahr=jahr, tage=tuple(tage), renntage=renntage)
