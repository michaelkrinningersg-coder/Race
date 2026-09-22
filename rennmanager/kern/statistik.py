"""Statistiken und Historie (GDD 13, Punkt 101).

"Rundenrekorde je Strecke in Tausendsteln. Karriere: Siege, Podien,
Pole-Positions, schnellste Runden, Gesamtpunkte je Saison. Historie aller
Saisons." Seit Punkt 101 gibt es eine Liga, also auch nur je einen
Rekord, eine Abschlusstabelle und einen Punktestand.

Die Statistik sammelt, was ein Rennwochenende hinterlaesst, und ueberdauert
die Saison - anders als ``rennmanager.kern.wertung.Tabelle``, die mit dem
Saisonende abgeschlossen ist. Vier Dinge werden gefuehrt:

* **Rundenrekorde** je Strecke, in ganzen Millisekunden (die Einheit des
  ganzen Projekts).
* **Karrierezahlen** je Fahrer: Rennen, Siege, Podien, Poles, schnellste
  Runden, Ausfaelle und Punkte.
* **Saisonverlauf**: die Punkte je Rennwochenende der *laufenden* Saison,
  damit sich zeichnen laesst, wer wann gefuehrt hat (Punkt 9).
* **Historie**: je Saison die vollstaendige Abschlusstabelle -
  Platz, Punkte, Siege, Podien, Poles, schnellste Runden, Ausfaelle und
  Rennen je Fahrer. Vollstaendig, weil die Tabelle der Saison beim
  Saisonwechsel geleert wird: Was dann nicht in der Historie steht, ist
  fort.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rennmanager.kern.wertung import Eintrag, Rennergebnis, Tabelle, punkte_fuer

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class StatistikFehler(Exception):
    """Der Statistik fehlt etwas, das sie braucht."""


@dataclass(frozen=True)
class Rekord:
    """Die schnellste je gefahrene Runde auf einer Strecke."""

    strecke: str
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
    # Punkt 102: Runden in Fuehrung, an der Start/Ziel-Linie gezaehlt.
    # Sie kommen nicht aus dem Rennergebnis, sondern aus dem Rennmodell -
    # deshalb werden sie getrennt gemeldet (``verbuche_fuehrungsrunden``).
    fuehrungsrunden: int = 0
    # Und die Runden, die er ueberhaupt gefahren ist. Ohne sie liesse
    # sich kein Anteil bilden: 30 Fuehrungsrunden sagen wenig, solange
    # nicht danebensteht, ob es 60 oder 600 Runden waren.
    gefahrene_runden: int = 0

    def verbuche(
        self, konfiguration: Konfiguration, ergebnis: Rennergebnis
    ) -> None:
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

    @property
    def fuehrungsanteil(self) -> float:
        """Anteil der gefahrenen Runden, die er vorn lag."""
        return (
            self.fuehrungsrunden / self.gefahrene_runden
            if self.gefahrene_runden
            else 0.0
        )


@dataclass
class Bilanz:
    """Was ein Fahrer irgendwo erreicht hat (Punkte 21 und 23).

    Dieselben Zahlen wie in ``Karrierezahlen``, aber je Strecke oder je
    Wetterlage. Gefuehrt wird die **Summe**, nicht die Liste der einzelnen
    Rennen: 50 Fahrer mal 20 Rennen mal beliebig vielen Saisons waere ein
    Spielstand, der endlos waechst. Als Summe bleiben es 1.000 Zeilen je
    Strecke und 250 je Wetterlage - gleich viele nach der ersten Saison
    wie nach der zwanzigsten.
    """

    rennen: int = 0
    siege: int = 0
    podien: int = 0
    poles: int = 0
    schnellste_runden: int = 0
    ausfaelle: int = 0
    punkte: int = 0
    # Das beste je erreichte Rennergebnis; 0 heisst "noch nie angekommen".
    bester_platz: int = 0
    # Vorschlag 16: dieselben zwei Zahlen wie in ``Karrierezahlen``, nur
    # hier je Strecke und je Lage. Sie kommen nicht aus dem Rennergebnis,
    # sondern ueber ``verbuche_fuehrungsrunden`` aus dem Rennmodell.
    fuehrungsrunden: int = 0
    gefahrene_runden: int = 0

    def verbuche(
        self, konfiguration: Konfiguration, ergebnis: Rennergebnis
    ) -> None:
        self.rennen += 1
        self.punkte += punkte_fuer(konfiguration, ergebnis)
        if ergebnis.ausgefallen:
            self.ausfaelle += 1
        else:
            if not self.bester_platz or ergebnis.rennplatz < self.bester_platz:
                self.bester_platz = ergebnis.rennplatz
        if ergebnis.rennplatz == 1:
            self.siege += 1
        if ergebnis.rennplatz <= 3:
            self.podien += 1
        if ergebnis.qualifyingplatz == 1:
            self.poles += 1
        if ergebnis.schnellste_runde:
            self.schnellste_runden += 1

    @property
    def siegquote(self) -> float:
        return self.siege / self.rennen if self.rennen else 0.0

    @property
    def podestquote(self) -> float:
        return self.podien / self.rennen if self.rennen else 0.0

    @property
    def fuehrungsanteil(self) -> float:
        """Anteil der hier gefahrenen Runden, die er vorn lag.

        Der Anteil und nicht die blosse Zahl macht die Strecken
        vergleichbar: Fuenf Runden in Fuehrung sind in Monaco wenig und
        in Spa viel, weil die Rennen verschieden lang sind.
        """
        return (
            self.fuehrungsrunden / self.gefahrene_runden
            if self.gefahrene_runden
            else 0.0
        )


@dataclass(frozen=True)
class Saisonzeile:
    """Eine Zeile der Abschlusstabelle, mit allen Zahlen des Fahrers.

    Die Tabelle einer Saison wird beim Wechsel geleert; was von ihr
    bleiben soll, steht hier. Deshalb traegt die Zeile dieselben Zahlen
    wie ``wertung.Eintrag`` - Punkte allein liessen sich spaeter nicht
    mehr nach Siegen oder Ausfaellen aufschluesseln.
    """

    fahrer: int
    platz: int
    punkte: int
    siege: int = 0
    podien: int = 0
    poles: int = 0
    schnellste_runden: int = 0
    ausfaelle: int = 0
    rennen: int = 0
    # Punkt 102: Runden in Fuehrung dieser Saison.
    fuehrungsrunden: int = 0


@dataclass(frozen=True)
class Saisonabschluss:
    """Der Endstand einer Saison (GDD 13: Historie)."""

    saison: int
    # Die Abschlusstabelle, Bester zuerst.
    zeilen: tuple[Saisonzeile, ...]

    @property
    def reihenfolge(self) -> tuple[int, ...]:
        """Fahrernummern in der Reihenfolge der Abschlusstabelle."""
        return tuple(z.fahrer for z in self.zeilen)

    @property
    def punkte(self) -> tuple[int, ...]:
        return tuple(z.punkte for z in self.zeilen)

    @property
    def meister(self) -> int:
        return self.zeilen[0].fahrer

    def zeile_von(self, fahrer: int) -> Saisonzeile | None:
        return next((z for z in self.zeilen if z.fahrer == fahrer), None)

    def platz_von(self, fahrer: int) -> int | None:
        zeile = self.zeile_von(fahrer)
        return zeile.platz if zeile else None


@dataclass
class Statistik:
    """Alles, was ueber die Saison hinaus aufgehoben wird (GDD 13)."""

    konfiguration: Konfiguration
    rekorde: dict[str, Rekord] = field(default_factory=dict)
    # Punkt 93 (A17): Dasselbe fuers Qualifying, getrennt gefuehrt. Eine
    # Qualirunde faehrt man auf leerer Strecke mit frischen Reifen, eine
    # Rennrunde mit Verkehr und abbauenden Reifen - in einem Topf fiele
    # der Rennrekord nie wieder.
    qualirekorde: dict[str, Rekord] = field(default_factory=dict)
    karriere: dict[int, Karrierezahlen] = field(default_factory=dict)
    historie: list[Saisonabschluss] = field(default_factory=list)
    # Punkte je (Saison, Fahrer).
    saisonpunkte: dict[tuple[int, int], int] = field(default_factory=dict)
    # Punkte je (Rennen, Fahrer) der *laufenden* Saison (Punkt 9). Nur
    # daraus laesst sich zeichnen, wer wann gefuehrt hat. Beim
    # Saisonwechsel wird die Sammlung geleert: Der Endstand steht dann in
    # der Historie, und 50 Fahrer mal 20 Rennen mal beliebig viele
    # Saisons waere ein Spielstand, der nur noch waechst.
    saisonverlauf: dict[tuple[int, int], int] = field(default_factory=dict)
    # Punkt 102: Runden in Fuehrung je (Saison, Fahrer). Die laufende
    # Saison braucht sie fuer ihre Abschlusstabelle; die Karrierezahlen
    # summieren daneben weiter.
    saisonfuehrung: dict[tuple[int, int], int] = field(default_factory=dict)
    # Punkt 21 und 23: Summen je (Fahrer, Strecke) und je (Fahrer,
    # Wetterlage). Siehe ``Bilanz``, warum Summen und keine Rennliste.
    streckenbilanz: dict[tuple[int, str], Bilanz] = field(default_factory=dict)
    wetterbilanz: dict[tuple[int, str], Bilanz] = field(default_factory=dict)

    # -- Rundenrekorde -----------------------------------------------------
    def rekord(self, strecke: str) -> Rekord | None:
        return self.rekorde.get(strecke)

    # -- Der Qualifyingrekord (Punkt 93, A17) ------------------------------
    def qualirekord(self, strecke: str) -> Rekord | None:
        """Die schnellste je gefahrene **Qualirunde** hier.

        Getrennt vom Rennrekord gefuehrt, und zwar mit Absicht: Eine
        Qualirunde wird auf leerer Strecke mit frischen Reifen gefahren,
        eine Rennrunde mit Sprit, Verkehr und abbauenden Reifen. Die
        beiden in einen Topf zu werfen hiesse, dass der Rennrekord nie
        wieder faellt.
        """
        return self.qualirekorde.get(strecke)

    def melde_qualirunde(
        self,
        strecke: str,
        zeit_ms: int,
        fahrer: int,
        saison: int,
        rennen: int,
    ) -> bool:
        """Traegt eine Qualifyingzeit ein, wenn sie ein Rekord ist.

        :return: ob der Rekord neu ist
        """
        if zeit_ms <= 0:
            return False
        bisher = self.qualirekorde.get(strecke)
        if bisher is not None and bisher.zeit_ms <= zeit_ms:
            return False
        self.qualirekorde[strecke] = Rekord(
            strecke=strecke,
            zeit_ms=zeit_ms,
            fahrer=fahrer,
            saison=saison,
            rennen=rennen,
        )
        return True

    def melde_runde(
        self,
        strecke: str,
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
        bisher = self.rekorde.get(strecke)
        if bisher is not None and bisher.zeit_ms <= zeit_ms:
            return False
        self.rekorde[strecke] = Rekord(
            strecke=strecke,
            zeit_ms=zeit_ms,
            fahrer=fahrer,
            saison=saison,
            rennen=rennen,
        )
        return True

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
        strecke: str,
        ergebnisse: tuple[Rennergebnis, ...],
        schnellste_runde_ms: int = 0,
        wetter: str = "",
        quali_ms: int = 0,
        quali_fahrer: int | None = None,
    ) -> bool:
        """Traegt ein Rennwochenende ein.

        :param wetter: die vorherrschende Lage des Rennens (Punkt 23).
            Ohne sie bleibt die Wetterbilanz unberuehrt - so bleiben alte
            Spielstaende lesbar, sie beginnen nur bei null.
        :param quali_ms: die Polezeit des Wochenendes (Punkt 93, A17).
            Ohne sie bleibt der Qualifyingrekord unberuehrt.
        :return: ob dabei ein **Renn**rundenrekord gefallen ist
        """
        for ergebnis in ergebnisse:
            self.zahlen(ergebnis.fahrer).verbuche(self.konfiguration, ergebnis)
            schluessel = (saison, ergebnis.fahrer)
            punkte = punkte_fuer(self.konfiguration, ergebnis)
            self.saisonpunkte[schluessel] = self.saisonpunkte.get(schluessel, 0) + punkte
            self.saisonverlauf[(rennen, ergebnis.fahrer)] = punkte
            self.strecke_von(ergebnis.fahrer, strecke).verbuche(
                self.konfiguration, ergebnis
            )
            if wetter:
                self.wetter_von(ergebnis.fahrer, wetter).verbuche(
                    self.konfiguration, ergebnis
                )

        # Punkt 93 (A17): Die Polezeit getrennt melden - sie steht im
        # Qualifying der naechsten Saison als Streckenbestmarke.
        if quali_ms > 0 and quali_fahrer is not None:
            self.melde_qualirunde(strecke, quali_ms, quali_fahrer, saison, rennen)

        schnellster = next((e.fahrer for e in ergebnisse if e.schnellste_runde), None)
        if schnellster is None or schnellste_runde_ms <= 0:
            return False
        return self.melde_runde(strecke, schnellste_runde_ms, schnellster, saison, rennen)

    def verbuche_fuehrungsrunden(
        self,
        saison: int,
        je_fahrer: dict[int, int],
        starter: Iterable[int],
        strecke: str = "",
        wetter: str = "",
    ) -> None:
        """Traegt die Runden in Fuehrung eines Rennens ein (Punkt 102).

        Getrennt von ``verbuche_wochenende``, weil sie nicht im
        Rennergebnis stehen: Wer eine Runde gefuehrt hat, weiss nur das
        Rennmodell, und beide Modelle melden es auf demselben Weg.

        Die **Renndistanz** steht dabei schon in den Zahlen selbst: Jede
        Runde hat genau einen Fuehrenden, also ist ihre Summe die
        Rundenzahl des Rennens.

        :param je_fahrer: Runden in Fuehrung; wer nie vorn lag, fehlt
        :param starter: alle gemeldeten Fahrer. Sie bekommen die Distanz
            als gefahrene Runden gutgeschrieben - auch der Letzte, sonst
            haette der Anteil keinen Nenner.
        :param strecke: Strecke des Rennens (Vorschlag 16). Ohne sie
            bleibt die Streckenbilanz unberuehrt - wie bei der
            Wetterlage in ``verbuche_wochenende``.
        :param wetter: vorherrschende Lage des Rennens (Vorschlag 16)
        """
        runden = sum(je_fahrer.values())
        if not runden:
            return
        for fahrer, anzahl in je_fahrer.items():
            self.zahlen(fahrer).fuehrungsrunden += anzahl
            schluessel = (saison, fahrer)
            self.saisonfuehrung[schluessel] = (
                self.saisonfuehrung.get(schluessel, 0) + anzahl
            )
            for bilanz in self._bilanzen_von(fahrer, strecke, wetter):
                bilanz.fuehrungsrunden += anzahl
        for fahrer in starter:
            self.zahlen(fahrer).gefahrene_runden += runden
            for bilanz in self._bilanzen_von(fahrer, strecke, wetter):
                bilanz.gefahrene_runden += runden

    def _bilanzen_von(
        self, fahrer: int, strecke: str, wetter: str
    ) -> list[Bilanz]:
        """Die Bilanzen, in die ein Rennen dieses Fahrers zaehlt.

        Aufgerufen wird das erst **nach** ``verbuche_wochenende``, das
        beide Bilanzen fuer jeden Starter ohnehin anlegt - hier entsteht
        also keine Zeile, die sonst leer bliebe.
        """
        gefunden: list[Bilanz] = []
        if strecke:
            gefunden.append(self.strecke_von(fahrer, strecke))
        if wetter:
            gefunden.append(self.wetter_von(fahrer, wetter))
        return gefunden

    # -- Bilanzen (Punkte 21 und 23) ---------------------------------------
    def strecke_von(self, fahrer: int, strecke: str) -> Bilanz:
        """Die Bilanz eines Fahrers auf einer Strecke."""
        return self.streckenbilanz.setdefault((fahrer, strecke), Bilanz())

    def wetter_von(self, fahrer: int, lage: str) -> Bilanz:
        """Die Bilanz eines Fahrers bei einer Wetterlage."""
        return self.wetterbilanz.setdefault((fahrer, lage), Bilanz())

    def strecken_von(self, fahrer: int) -> dict[str, Bilanz]:
        """Alle Streckenbilanzen eines Fahrers, Strecke zu Bilanz."""
        return {
            name: bilanz
            for (nummer, name), bilanz in self.streckenbilanz.items()
            if nummer == fahrer
        }

    def wetterlagen_von(self, fahrer: int) -> dict[str, Bilanz]:
        """Alle Wetterbilanzen eines Fahrers, Lage zu Bilanz."""
        return {
            lage: bilanz
            for (nummer, lage), bilanz in self.wetterbilanz.items()
            if nummer == fahrer
        }

    def bilanzen_auf(self, strecke: str) -> dict[int, Bilanz]:
        """Alle Fahrer, die auf dieser Strecke gefahren sind."""
        return {
            nummer: bilanz
            for (nummer, name), bilanz in self.streckenbilanz.items()
            if name == strecke
        }

    def bilanzen_bei(self, lage: str) -> dict[int, Bilanz]:
        """Alle Fahrer, die bei dieser Wetterlage gefahren sind."""
        return {
            nummer: bilanz
            for (nummer, name), bilanz in self.wetterbilanz.items()
            if name == lage
        }

    def schliesse_saison(self, saison: int, tabelle: Tabelle) -> None:
        """Schreibt den Endstand in die Historie (GDD 13).

        Vollstaendig, nicht nur Reihenfolge und Punkte: Nach dem
        Saisonwechsel ist die Tabelle leer, und was dann nicht in der
        Historie steht, ist fort.
        """
        # Der Verlauf gehoert zur abgelaufenen Saison; was bleiben soll,
        # steht jetzt in der Historie.
        self.saisonverlauf.clear()
        self.historie.append(
            Saisonabschluss(
                saison=saison,
                zeilen=tuple(
                    zeile_aus(
                        eintrag,
                        platz,
                        self.saisonfuehrung.get((saison, eintrag.fahrer), 0),
                    )
                    for platz, eintrag in enumerate(tabelle.stand(), start=1)
                ),
            )
        )

    # -- Historie ----------------------------------------------------------
    def abschluss(self, saison: int) -> Saisonabschluss | None:
        return next((a for a in self.historie if a.saison == saison), None)

    @property
    def saisons(self) -> tuple[int, ...]:
        return tuple(sorted({a.saison for a in self.historie}))

    def titel_von(self, fahrer: int) -> tuple[Saisonabschluss, ...]:
        """Alle Meisterschaften eines Fahrers."""
        return tuple(a for a in self.historie if a.meister == fahrer)

    def laufbahn(self, fahrer: int) -> tuple[tuple[int, int], ...]:
        """Je Saison der Platz des Fahrers, aeltestes zuerst."""
        bahn = []
        for a in self.historie:
            platz = a.platz_von(fahrer)
            if platz is not None:
                bahn.append((a.saison, platz))
        return tuple(sorted(bahn))

    def punkte_in(self, saison: int, fahrer: int) -> int:
        """Die Meisterschaftspunkte eines Fahrers in dieser Saison."""
        return self.saisonpunkte.get((saison, fahrer), 0)

    # -- Verlauf der laufenden Saison (Punkt 9) ----------------------------
    def gefahrene_rennen(self) -> tuple[int, ...]:
        """Die Rennnummern der laufenden Saison."""
        return tuple(sorted({rennen for (rennen, _) in self.saisonverlauf}))

    def punktestand(self, fahrer: int) -> tuple[int, ...]:
        """Der aufsummierte Punktestand eines Fahrers, Rennen fuer Rennen.

        Die Liste ist so lang wie die Zahl der gefahrenen Rennen; ein
        Fahrer ohne Punkte in einem Rennen behaelt seinen Stand.
        """
        stand = 0
        verlauf = []
        for rennen in self.gefahrene_rennen():
            stand += self.saisonverlauf.get((rennen, fahrer), 0)
            verlauf.append(stand)
        return tuple(verlauf)


def zeile_aus(eintrag: Eintrag, platz: int, fuehrungsrunden: int = 0) -> Saisonzeile:
    """Macht aus einer Saisonzeile der Tabelle eine Zeile der Historie."""
    return Saisonzeile(
        fahrer=eintrag.fahrer,
        platz=platz,
        punkte=eintrag.punkte,
        siege=eintrag.siege,
        podien=eintrag.podien,
        poles=eintrag.poles,
        schnellste_runden=eintrag.schnellste_runden,
        ausfaelle=eintrag.ausfaelle,
        rennen=eintrag.rennen,
        fuehrungsrunden=fuehrungsrunden,
    )


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
