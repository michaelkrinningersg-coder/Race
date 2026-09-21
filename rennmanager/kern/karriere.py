"""Karrierestand: Kalender und Streckenkenntnis (GDD 2, Punkt 101).

Was der Spieler zwischen zwei Rennen tut, ist seit Punkt 101 genau eines:
Tage weiterschalten, bis das naechste Rennwochenende ansteht. Geld,
Erfahrung, Upgrades, Trainingsprogramme, Sponsoren, Vertraege und
Ereignisse sind weggefallen - es wird mit festen Fahrern und festen
Staerken gefahren.

Geblieben sind

* der **Kalender** aus GDD 2 mit seinen Renntagen und
* die **Streckenkenntnis** aus GDD 6, die je Fahrer und Strecke einmal
  bei der Welterzeugung gewuerfelt wird und dann feststeht.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern.kalender import Saison

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class KarriereFehler(Exception):
    """Die Aktion ist an diesem Tag nicht moeglich."""


@dataclass
class Karriere:
    """Der Stand einer Karriere - Kalender und Streckenkenntnis.

    :param fahrer: die Fahrernummern des Spielerteams. Seit Punkt 101
        sind es zwei, und sie wechseln nie.
    """

    konfiguration: Konfiguration
    saison: Saison
    heute: dt.date
    fahrer: tuple[int, ...] = ()
    kenntnis: kern_streckenkenntnis.Streckenkenntnis | None = None
    # Der Fahrer, den Anzeigen zeigen, wenn sie genau einen brauchen.
    fahrernummer: int = 0

    def __post_init__(self) -> None:
        if self.kenntnis is None:
            self.kenntnis = kern_streckenkenntnis.Streckenkenntnis(self.konfiguration)
        self.fahrer = tuple(sorted(self.fahrer))
        if self.fahrer and self.fahrernummer not in self.fahrer:
            self.fahrernummer = self.fahrer[0]

    def waehle_fahrer(self, nummer: int) -> None:
        """Stellt auf einen anderen eigenen Fahrer um."""
        if nummer not in self.fahrer:
            raise KarriereFehler(f"Fahrer {nummer} gehoert nicht zum Team")
        self.fahrernummer = nummer

    # -- Kalender ----------------------------------------------------------
    @property
    def tag(self) -> kern_kalender.Kalendertag:
        return self.saison.tag(self.heute)

    @property
    def naechstes_rennen(self) -> dt.date | None:
        return self.saison.naechster_renntag(self.heute)

    @property
    def tage_bis_zum_rennen(self) -> int | None:
        ziel = self.naechstes_rennen
        return (ziel - self.heute).days if ziel else None

    @property
    def offene_tage(self) -> int:
        """Nutzbare Tage bis zum naechsten Rennen, heute eingeschlossen."""
        ziel = self.naechstes_rennen
        if ziel is None:
            ziel = self.saison.tage[-1].datum
        return len(self.saison.nutzbare_tage(self.heute, ziel))

    def tag_weiter(self) -> kern_kalender.Kalendertag:
        """Schaltet einen Tag weiter (GDD 2)."""
        naechster = self.heute + dt.timedelta(days=1)
        if naechster > self.saison.tage[-1].datum:
            raise KarriereFehler("Die Saison ist zu Ende")
        self.heute = naechster
        return self.tag

    def bis_zum_rennen(self) -> int:
        """Schaltet bis zum naechsten Renntag vor und meldet die Tage."""
        ziel = self.naechstes_rennen
        if ziel is None:
            raise KarriereFehler("In dieser Saison steht kein Rennen mehr an")
        tage = 0
        while self.heute < ziel:
            self.tag_weiter()
            tage += 1
        return tage

    # -- Streckenkenntnis (GDD 6) ------------------------------------------
    def kenntnisfaktor(self, strecke: str) -> float:
        """Der Tempofaktor des gewaehlten Fahrers auf dieser Strecke."""
        return self.kenntnis.tempofaktor(self.fahrernummer, strecke)

    # -- Saisonwechsel -----------------------------------------------------
    def naechste_saison(self, jahr: int) -> None:
        """Setzt die Karriere auf den 1. Januar der naechsten Saison.

        Der Kalender wird neu gebaut, alles andere bleibt: Die Fahrer
        sind dieselben, ihre Staerken auch (Punkt 101).
        """
        self.saison = kern_kalender.erzeuge(self.konfiguration, jahr)
        self.heute = self.saison.tage[0].datum


def startjahr(konfiguration: Konfiguration) -> int:
    """Das Jahr, in dem eine neue Karriere beginnt (GDD 2)."""
    return int(konfiguration.wert("kalender", "startjahr"))


def beginne(
    konfiguration: Konfiguration,
    jahr: int | None = None,
    fahrer: tuple[int, ...] = (),
) -> Karriere:
    """Baut eine frische Karriere zum 1. Januar ihrer ersten Saison."""
    jahr = startjahr(konfiguration) if jahr is None else jahr
    saison = kern_kalender.erzeuge(konfiguration, jahr)
    return Karriere(
        konfiguration=konfiguration,
        saison=saison,
        heute=saison.tage[0].datum,
        fahrer=tuple(fahrer),
    )


def kopiere(karriere: Karriere) -> Karriere:
    """Eine eigenstaendige Kopie - fuer Vergleiche im Test.

    Die Streckenkenntnis wird mitgenommen, nicht geteilt: Sie ist zwar
    seit Punkt 101 fest, aber der Editor darf sie setzen.
    """
    alt = karriere.kenntnis
    kenntnis = kern_streckenkenntnis.Streckenkenntnis(
        karriere.konfiguration,
        runden=dict(alt.runden),
        seedquelle=alt.seedquelle,
        fest=set(alt.fest),
    )
    return Karriere(
        konfiguration=karriere.konfiguration,
        saison=karriere.saison,
        heute=karriere.heute,
        fahrer=karriere.fahrer,
        kenntnis=kenntnis,
        fahrernummer=karriere.fahrernummer,
    )
