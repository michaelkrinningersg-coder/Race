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
* **Saisonverlauf**: die Punkte je Rennwochenende der *laufenden* Saison,
  damit sich zeichnen laesst, wer wann gefuehrt hat (Punkt 9).
* **Historie**: je Saison und Liga die vollstaendige Abschlusstabelle -
  Platz, Punkte, Siege, Podien, Poles, schnellste Runden, Ausfaelle und
  Rennen je Fahrer. Vollstaendig, weil die Tabelle der Saison beim
  Saisonwechsel geleert wird: Was dann nicht in der Historie steht, ist
  fort.
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

    def verbuche(
        self, konfiguration: Konfiguration, ergebnis: Rennergebnis, liga: int
    ) -> None:
        self.rennen += 1
        self.punkte += punkte_fuer(konfiguration, liga, ergebnis)
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


@dataclass
class Bilanz:
    """Was ein Fahrer irgendwo erreicht hat (Punkte 21 und 23).

    Dieselben Zahlen wie in ``Karrierezahlen``, aber je Strecke oder je
    Wetterlage. Gefuehrt wird die **Summe**, nicht die Liste der einzelnen
    Rennen: 400 Fahrer mal 20 Rennen mal beliebig vielen Saisons waere ein
    Spielstand, der endlos waechst. Als Summe bleiben es 12.000 Zeilen je
    Strecke und 3.000 je Wetterlage - gleich viele nach der ersten Saison
    wie nach der zwanzigsten.

    ``beste_liga`` ist die staerkste Liga (also die kleinste Nummer), in
    der hier ein Podium gelang. Zehn Siege in Liga 10 und einer in Liga 3
    stehen sonst gleichwertig nebeneinander. 0 heisst: noch kein Podium.
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
    beste_liga: int = 0

    def verbuche(
        self, konfiguration: Konfiguration, ergebnis: Rennergebnis, liga: int
    ) -> None:
        self.rennen += 1
        self.punkte += punkte_fuer(konfiguration, liga, ergebnis)
        if ergebnis.ausgefallen:
            self.ausfaelle += 1
        else:
            if not self.bester_platz or ergebnis.rennplatz < self.bester_platz:
                self.bester_platz = ergebnis.rennplatz
        if ergebnis.rennplatz == 1:
            self.siege += 1
        if ergebnis.rennplatz <= 3:
            self.podien += 1
            if not self.beste_liga or liga < self.beste_liga:
                self.beste_liga = liga
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


@dataclass(frozen=True)
class Saisonabschluss:
    """Der Endstand einer Liga in einer Saison (GDD 13: Historie)."""

    saison: int
    liga: int
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
    rekorde: dict[tuple[str, int], Rekord] = field(default_factory=dict)
    # Punkt 93 (A17): Dasselbe fuers Qualifying, getrennt gefuehrt. Eine
    # Qualirunde faehrt man auf leerer Strecke mit frischen Reifen, eine
    # Rennrunde mit Verkehr und abbauenden Reifen - in einem Topf fiele
    # der Rennrekord nie wieder.
    qualirekorde: dict[tuple[str, int], Rekord] = field(default_factory=dict)
    karriere: dict[int, Karrierezahlen] = field(default_factory=dict)
    historie: list[Saisonabschluss] = field(default_factory=list)
    # Punkte je (Saison, Fahrer). Punkt 95: Die Meisterschaft laeuft ueber
    # alle Ligen, und ein Fahrer wechselt sie mitten in der Saison - seine
    # Punkte je Liga zu fuehren hiesse, seinen Stand auf zwei Schluessel zu
    # verteilen. Welche Liga er gefahren hat, steht in der Historie.
    saisonpunkte: dict[tuple[int, int], int] = field(default_factory=dict)
    # Punkte je (Rennen, Fahrer) der *laufenden* Saison (Punkt 9). Nur
    # daraus laesst sich zeichnen, wer wann gefuehrt hat. Beim
    # Saisonwechsel wird die Sammlung geleert: Der Endstand steht dann in
    # der Historie, und 400 Fahrer mal 20 Rennen mal beliebig viele
    # Saisons waere ein Spielstand, der nur noch waechst.
    saisonverlauf: dict[tuple[int, int], int] = field(default_factory=dict)
    # Punkt 21 und 23: Summen je (Fahrer, Strecke) und je (Fahrer,
    # Wetterlage). Siehe ``Bilanz``, warum Summen und keine Rennliste.
    streckenbilanz: dict[tuple[int, str], Bilanz] = field(default_factory=dict)
    wetterbilanz: dict[tuple[int, str], Bilanz] = field(default_factory=dict)

    # -- Rundenrekorde -----------------------------------------------------
    def rekord(self, strecke: str, liga: int) -> Rekord | None:
        return self.rekorde.get((strecke, liga))

    # -- Der Qualifyingrekord (Punkt 93, A17) ------------------------------
    def qualirekord(self, strecke: str, liga: int) -> Rekord | None:
        """Die schnellste je gefahrene **Qualirunde** hier.

        Getrennt vom Rennrekord gefuehrt, und zwar mit Absicht: Eine
        Qualirunde wird auf leerer Strecke mit frischen Reifen gefahren,
        eine Rennrunde mit Sprit, Verkehr und abbauenden Reifen. Die
        beiden in einen Topf zu werfen hiesse, dass der Rennrekord nie
        wieder faellt.
        """
        return self.qualirekorde.get((strecke, liga))

    def melde_qualirunde(
        self,
        strecke: str,
        liga: int,
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
        bisher = self.qualirekorde.get((strecke, liga))
        if bisher is not None and bisher.zeit_ms <= zeit_ms:
            return False
        self.qualirekorde[(strecke, liga)] = Rekord(
            strecke=strecke,
            liga=liga,
            zeit_ms=zeit_ms,
            fahrer=fahrer,
            saison=saison,
            rennen=rennen,
        )
        return True

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
        wetter: str = "",
        quali_ms: int = 0,
        quali_fahrer: int | None = None,
    ) -> bool:
        """Traegt ein Rennwochenende einer Liga ein.

        :param wetter: die vorherrschende Lage des Rennens (Punkt 23).
            Ohne sie bleibt die Wetterbilanz unberuehrt - so bleiben alte
            Spielstaende lesbar, sie beginnen nur bei null.
        :param quali_ms: die Polezeit des Wochenendes (Punkt 93, A17).
            Ohne sie bleibt der Qualifyingrekord unberuehrt.
        :return: ob dabei ein **Renn**rundenrekord gefallen ist
        """
        for ergebnis in ergebnisse:
            self.zahlen(ergebnis.fahrer).verbuche(self.konfiguration, ergebnis, liga)
            schluessel = (saison, ergebnis.fahrer)
            punkte = punkte_fuer(self.konfiguration, liga, ergebnis)
            self.saisonpunkte[schluessel] = self.saisonpunkte.get(schluessel, 0) + punkte
            self.saisonverlauf[(rennen, ergebnis.fahrer)] = punkte
            self.strecke_von(ergebnis.fahrer, strecke).verbuche(
                self.konfiguration, ergebnis, liga
            )
            if wetter:
                self.wetter_von(ergebnis.fahrer, wetter).verbuche(
                    self.konfiguration, ergebnis, liga
                )

        # Punkt 93 (A17): Die Polezeit getrennt melden - sie steht im
        # Qualifying der naechsten Saison als Streckenbestmarke.
        if quali_ms > 0 and quali_fahrer is not None:
            self.melde_qualirunde(strecke, liga, quali_ms, quali_fahrer, saison, rennen)

        schnellster = next((e.fahrer for e in ergebnisse if e.schnellste_runde), None)
        if schnellster is None or schnellste_runde_ms <= 0:
            return False
        return self.melde_runde(strecke, liga, schnellste_runde_ms, schnellster, saison, rennen)

    # -- Bilanzen (Punkte 21 und 23) ---------------------------------------
    def strecke_von(self, fahrer: int, strecke: str) -> Bilanz:
        """Die Bilanz eines Fahrers auf einer Strecke, ueber alle Ligen."""
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

    def schliesse_saison(self, saison: int, tabellen: dict[int, Tabelle]) -> None:
        """Schreibt den Endstand aller Ligen in die Historie (GDD 13).

        Vollstaendig, nicht nur Reihenfolge und Punkte: Nach dem
        Saisonwechsel sind die Tabellen leer, und was dann nicht in der
        Historie steht, ist fort.
        """
        # Der Verlauf gehoert zur abgelaufenen Saison; was bleiben soll,
        # steht jetzt in der Historie.
        self.saisonverlauf.clear()
        for liga in sorted(tabellen):
            stand = tabellen[liga].stand()
            self.historie.append(
                Saisonabschluss(
                    saison=saison,
                    liga=liga,
                    zeilen=tuple(
                        zeile_aus(eintrag, platz)
                        for platz, eintrag in enumerate(stand, start=1)
                    ),
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

    def vergiss_fahrer(self, nummer: int) -> None:
        """Loescht, was an einer Fahrernummer haengt (Punkt 35).

        Ein Newgen erbt die Nummer des Zurueckgetretenen - die Welt haelt
        genau 400 Fahrer, und an 53 Stellen ist die Nummer zugleich der
        Platz in der Liste. Ohne dieses Vergessen begaenne er seine
        Laufbahn mit dessen Siegen, Punkten und Bilanzen.

        Die **Historie** bleibt: Sie ist das Protokoll dessen, was wirklich
        passiert ist, und gehoert nicht dem Nachfolger, sondern der Saison.
        """
        self.karriere.pop(nummer, None)
        for sammlung in (self.saisonpunkte, self.saisonverlauf):
            for schluessel in [s for s in sammlung if s[-1] == nummer]:
                del sammlung[schluessel]
        for bilanz in (self.streckenbilanz, self.wetterbilanz):
            for schluessel in [s for s in bilanz if s[0] == nummer]:
                del bilanz[schluessel]

    def karriere_in_liga(self, liga: int) -> dict[int, Karrierezahlen]:
        """Die Karrierezahlen, aber nur aus einer Liga (Punkt 25).

        ``Karrierezahlen`` wissen nicht, in welcher Liga ein Sieg fiel -
        sie zaehlen alles zusammen. Wer wissen will, wer **in Liga 14** am
        meisten gewonnen hat, braucht die Historie: Sie fuehrt je Saison
        und Liga eine vollstaendige Abschlusstabelle.

        Der Preis: Nur **abgeschlossene** Saisons zaehlen. Die laufende
        steht noch in den Tabellen, nicht in der Historie.
        """
        summen: dict[int, Karrierezahlen] = {}
        for abschluss in self.historie:
            if abschluss.liga != liga:
                continue
            for zeile in abschluss.zeilen:
                zahlen = summen.setdefault(
                    zeile.fahrer, Karrierezahlen(fahrer=zeile.fahrer)
                )
                zahlen.rennen += zeile.rennen
                zahlen.siege += zeile.siege
                zahlen.podien += zeile.podien
                zahlen.poles += zeile.poles
                zahlen.schnellste_runden += zeile.schnellste_runden
                zahlen.ausfaelle += zeile.ausfaelle
                zahlen.punkte += zeile.punkte
        return summen

    def punkte_in(self, saison: int, fahrer: int) -> int:
        """Die Meisterschaftspunkte eines Fahrers in dieser Saison."""
        return self.saisonpunkte.get((saison, fahrer), 0)

    # -- Verlauf der laufenden Saison (Punkt 9) ----------------------------
    def gefahrene_rennen(self) -> tuple[int, ...]:
        """Die Rennnummern der laufenden Saison.

        Alle Ligen fahren dieselben Rennen; seit Punkt 95 waere eine
        Frage je Liga auch irrefuehrend, weil Fahrer die Liga mitten in
        der Saison wechseln.
        """
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


def zeile_aus(eintrag: Eintrag, platz: int) -> Saisonzeile:
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
