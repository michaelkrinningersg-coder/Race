"""Statistiken und Historie (GDD 13).

"Rundenrekorde je Strecke und Liga in Tausendsteln. Karriere: Siege,
Podien, Pole-Positions, schnellste Runden, Gesamtpunkte je Liga und
Saison. Historie aller Saisons und Ligen."

Die Statistik sammelt, was ein Rennwochenende hinterlaesst, und ueberdauert
die Saison - anders als ``rennmanager.kern.wertung.Tabelle``, die mit dem
Saisonende abgeschlossen ist. Drei Dinge werden gefuehrt:

* **Rundenrekorde** je Paar aus Strecke und Liga, in ganzen Millisekunden
  (die Einheit des ganzen Projekts).
* **Karrierezahlen** je Fahrer: Rennen, Siege, Podien, Poles, schnellste
  Runden, Ausfaelle und Punkte.
* **Historie**: je Saison und Liga der Endstand, damit sich spaeter
  nachschlagen laesst, wer wann Meister war.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rennmanager.kern.wertung import Eintrag, Rennergebnis, Tabelle, punkte_fuer

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class StatistikFehler(Exception):
    """Der Statistik fehlt etwas, das sie braucht."""


@dataclass(frozen=True)
class Rekord:
    """Die schnellste je gefahrene Runde auf einer Strecke in einer Liga."""

    strecke: str
    liga: int
    zeit_ms: int
    fahrer: int
    saison: int
    rennen: int


@dataclass
class Karrierezahlen:
    """Was ein Fahrer ueber alle Saisons erreicht hat (GDD 13)."""

    fahrer: int
    rennen: int = 0
    siege: int = 0
    podien: int = 0
    poles: int = 0
    schnellste_runden: int = 0
    ausfaelle: int = 0
    punkte: int = 0

    def verbuche(self, konfiguration: Konfiguration, ergebnis: Rennergebnis) -> None:
        self.rennen += 1
        self.punkte += punkte_fuer(konfiguration, ergebnis)
        if ergebnis.rennplatz == 1:
            self.siege += 1
        if ergebnis.rennplatz <= 3:
            self.podien += 1
        if ergebnis.qualifyingplatz == 1:
            self.poles += 1
        if ergebnis.schnellste_runde:
            self.schnellste_runden += 1
        if ergebnis.ausgefallen:
            self.ausfaelle += 1

    @property
    def siegquote(self) -> float:
        return self.siege / self.rennen if self.rennen else 0.0


@dataclass(frozen=True)
class Saisonabschluss:
    """Der Endstand einer Liga in einer Saison (GDD 13: Historie)."""

    saison: int
    liga: int
    # Fahrernummern in der Reihenfolge der Abschlusstabelle.
    reihenfolge: tuple[int, ...]
    punkte: tuple[int, ...]

    @property
    def meister(self) -> int:
        return self.reihenfolge[0]

    def platz_von(self, fahrer: int) -> int | None:
        return self.reihenfolge.index(fahrer) + 1 if fahrer in self.reihenfolge else None


@dataclass
class Statistik:
    """Alles, was ueber die Saison hinaus aufgehoben wird (GDD 13)."""

    konfiguration: Konfiguration
    rekorde: dict[tuple[str, int], Rekord] = field(default_factory=dict)
    karriere: dict[int, Karrierezahlen] = field(default_factory=dict)
    historie: list[Saisonabschluss] = field(default_factory=list)
    # Punkte je (Saison, Liga, Fahrer) - GDD 13: "Gesamtpunkte je Liga und
    # Saison".
    saisonpunkte: dict[tuple[int, int, int], int] = field(default_factory=dict)

    # -- Rundenrekorde -----------------------------------------------------
    def rekord(self, strecke: str, liga: int) -> Rekord | None:
        return self.rekorde.get((strecke, liga))

    def melde_runde(
        self,
        strecke: str,
        liga: int,
        zeit_ms: int,
        fahrer: int,
        saison: int,
        rennen: int,
    ) -> bool:
        """Traegt eine Rundenzeit ein, wenn sie ein Rekord ist.

        :return: ob der Rekord neu ist
        """
        if zeit_ms <= 0:
            return False
        bisher = self.rekorde.get((strecke, liga))
        if bisher is not None and bisher.zeit_ms <= zeit_ms:
            return False
        self.rekorde[(strecke, liga)] = Rekord(
            strecke=strecke,
            liga=liga,
            zeit_ms=zeit_ms,
            fahrer=fahrer,
            saison=saison,
            rennen=rennen,
        )
        return True

    def rekorde_je_strecke(self, strecke: str) -> tuple[Rekord, ...]:
        """Alle Ligarekorde einer Strecke, schnellste Liga zuerst."""
        gefunden = [r for (name, _), r in self.rekorde.items() if name == strecke]
        return tuple(sorted(gefunden, key=lambda r: r.zeit_ms))

    # -- Karriere ----------------------------------------------------------
    def zahlen(self, fahrer: int) -> Karrierezahlen:
        return self.karriere.setdefault(fahrer, Karrierezahlen(fahrer))

    def bestenliste(self, merkmal: str = "siege", anzahl: int = 10):
        """Die besten Fahrer nach einem Merkmal (GDD 13).

        Bei Gleichstand im Merkmal entscheiden Punkte, dann Siege - sonst
        stuenden bei zwei Siegen die Fahrernummern durcheinander.
        """
        if not hasattr(Karrierezahlen(0), merkmal):
            raise StatistikFehler(f"Unbekanntes Merkmal: {merkmal}")
        geordnet = sorted(
            self.karriere.values(),
            key=lambda z: (-getattr(z, merkmal), -z.punkte, -z.siege, z.fahrer),
        )
        return tuple(geordnet[:anzahl])

    # -- Rennwochenende ----------------------------------------------------
    def verbuche_wochenende(
        self,
        saison: int,
        rennen: int,
        liga: int,
        strecke: str,
        ergebnisse: tuple[Rennergebnis, ...],
        schnellste_runde_ms: int = 0,
    ) -> bool:
        """Traegt ein Rennwochenende einer Liga ein.

        :return: ob dabei ein Rundenrekord gefallen ist
        """
        for ergebnis in ergebnisse:
            self.zahlen(ergebnis.fahrer).verbuche(self.konfiguration, ergebnis)
            schluessel = (saison, liga, ergebnis.fahrer)
            self.saisonpunkte[schluessel] = self.saisonpunkte.get(schluessel, 0) + punkte_fuer(
                self.konfiguration, ergebnis
            )

        schnellster = next((e.fahrer for e in ergebnisse if e.schnellste_runde), None)
        if schnellster is None or schnellste_runde_ms <= 0:
            return False
        return self.melde_runde(strecke, liga, schnellste_runde_ms, schnellster, saison, rennen)

    def schliesse_saison(self, saison: int, tabellen: dict[int, Tabelle]) -> None:
        """Schreibt den Endstand aller Ligen in die Historie (GDD 13)."""
        for liga in sorted(tabellen):
            stand = tabellen[liga].stand()
            self.historie.append(
                Saisonabschluss(
                    saison=saison,
                    liga=liga,
                    reihenfolge=tuple(e.fahrer for e in stand),
                    punkte=tuple(e.punkte for e in stand),
                )
            )

    # -- Historie ----------------------------------------------------------
    def abschluss(self, saison: int, liga: int) -> Saisonabschluss | None:
        return next(
            (a for a in self.historie if a.saison == saison and a.liga == liga), None
        )

    @property
    def saisons(self) -> tuple[int, ...]:
        return tuple(sorted({a.saison for a in self.historie}))

    def titel_von(self, fahrer: int) -> tuple[Saisonabschluss, ...]:
        """Alle Meisterschaften eines Fahrers."""
        return tuple(a for a in self.historie if a.meister == fahrer)

    def laufbahn(self, fahrer: int) -> tuple[tuple[int, int, int], ...]:
        """Je Saison Liga und Platz des Fahrers, aeltestes zuerst."""
        bahn = []
        for a in self.historie:
            platz = a.platz_von(fahrer)
            if platz is not None:
                bahn.append((a.saison, a.liga, platz))
        return tuple(sorted(bahn))

    def punkte_in(self, saison: int, liga: int, fahrer: int) -> int:
        return self.saisonpunkte.get((saison, liga, fahrer), 0)


def aus_tabelle(eintrag: Eintrag) -> Karrierezahlen:
    """Macht aus einer Saisonzeile eine Karrierezeile - fuer Vergleiche."""
    return Karrierezahlen(
        fahrer=eintrag.fahrer,
        rennen=eintrag.rennen,
        siege=eintrag.siege,
        podien=eintrag.podien,
        poles=eintrag.poles,
        schnellste_runden=eintrag.schnellste_runden,
        ausfaelle=eintrag.ausfaelle,
        punkte=eintrag.punkte,
    )
