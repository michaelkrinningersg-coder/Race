"""Saisonlauf: 20 Rennwochenenden, Wertung, Auf- und Abstieg (GDD 13).

Ein Saisonlauf haelt die Tabellen aller 20 Ligen und faehrt Wochenende
fuer Wochenende. Die Liga des Spielers laeuft dabei ausfuehrlich ueber
``rennmanager.kern.rennen`` - mit Qualifying, sichtbarem Rennverlauf und
Zeitraffer -, die uebrigen 19 im Schnellmodus aus
``rennmanager.kern.schnellsimulation``.

Nach dem zwanzigsten Rennen steigen in jeder Liga die besten drei auf und
die letzten drei ab (GDD 13). Der Wechsel gilt fuer einzelne Fahrer; die
Teams bleiben bestehen und haben danach ihre vier Autos gegebenenfalls in
anderen Ligen als zuvor.

Alle Wuerfe haengen am Hauptseed: Der Zweig eines Rennens heisst
``saison/<jahr>/rennen/<nummer>/liga/<liga>``. Dieselbe Saison mit
demselben Seed laeuft deshalb genau gleich ab, gleich ob die Liga des
Spielers ausfuehrlich oder schnell gefahren wird - die uebrigen 19 Ligen
bleiben davon unberuehrt (GDD 15).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from rennmanager.kern import qualifying as kern_qualifying
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import welt as kern_welt
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.qualifying import Qualifying
from rennmanager.kern.rennen import Rennverlauf
from rennmanager.kern.schnellsimulation import fahre_wochenende as fahre_schnell
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.welt import Fahrer, Welt
from rennmanager.kern.wertung import Rennergebnis, Tabelle, Wechsel
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class SaisonFehler(Exception):
    """Der Saisonlauf laesst sich so nicht fortsetzen."""


@dataclass(frozen=True)
class Ligawochenende:
    """Was eine Liga an einem Rennwochenende gefahren ist.

    ``ergebnisse`` nennt Fahrer mit ihrer weltweiten Nummer, nicht mit dem
    Platz im Starterfeld - nur so passen die Zeilen zur Tabelle.
    """

    liga: int
    ergebnisse: tuple[Rennergebnis, ...]
    wetter: tuple[str, ...]
    siegerzeit_ms: int
    schnellste_runde_ms: int
    ueberholmanoever: int
    ausfaelle: int
    ausfuehrlich: bool = False

    @property
    def sieger(self) -> int:
        return self.ergebnisse[0].fahrer

    def ergebnis_von(self, fahrer: int) -> Rennergebnis | None:
        return next((e for e in self.ergebnisse if e.fahrer == fahrer), None)


@dataclass(frozen=True)
class Wochenende:
    """Ein komplettes Rennwochenende ueber alle 20 Ligen (GDD 13)."""

    nummer: int
    strecke: str
    ligen: dict[int, Ligawochenende]
    # Nur fuer die ausfuehrlich gefahrene Liga gefuellt; die Oberflaeche
    # spielt daraus den Rennverlauf ab (GDD 15).
    verlauf: Rennverlauf | None = None
    qualifying: Qualifying | None = None
    ausfuehrliche_liga: int | None = None

    def liga(self, nummer: int) -> Ligawochenende:
        return self.ligen[nummer]


# ---------------------------------------------------------------------------
# Ein Rennwochenende einer Liga
# ---------------------------------------------------------------------------
def _ausfuehrlich(
    konfiguration: Konfiguration,
    welt: Welt,
    liga: int,
    fahrer: tuple[Fahrer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float,
    meisterschaft: tuple[int, ...] | None,
) -> tuple[Ligawochenende, Rennverlauf, Qualifying]:
    """Qualifying und Rennen einer Liga in voller Aufloesung (GDD 4)."""
    feld = kern_welt.starterfeld(welt, liga)
    quali = kern_qualifying.fahre(
        konfiguration, strecke, feld, seedquelle.zweig("qualifying"), meisterschaft
    )
    # Die Startaufstellung kommt aus dem Qualifying; Platz 1 ist die Pole.
    gestartet = tuple(
        kern_rennen.Teilnehmer(
            auto=feld[i].auto,
            startplatz=platz,
            farbe=feld[i].farbe,
            ist_spieler=feld[i].ist_spieler,
        )
        for platz, i in enumerate(quali.aufstellung, start=1)
    )

    # Das Rennwetter wird getrennt vom Qualifying gewuerfelt (GDD 7).
    rundendauer = quali.pole.zeit_ms
    wetter = kern_wetter.wuerfle(
        konfiguration,
        strecke.name,
        rundendauer * runden,
        rundendauer,
        seedquelle.zweig("rennwetter"),
    )
    verlauf = kern_rennen.simuliere(
        konfiguration,
        strecke,
        gestartet,
        runden,
        seedquelle.zweig("rennen"),
        streckenmittel,
        wetter=wetter,
        streckenverschleiss=streckenverschleiss,
    )

    # ``Ergebnis.teilnehmer`` zaehlt in der Startaufstellung, also ist der
    # Index zugleich der Qualifying-Platz minus eins. Ueber
    # ``quali.aufstellung`` geht es zurueck aufs Feld und von dort auf die
    # weltweite Fahrernummer.
    beste = [p.beste_runde_ms for p in verlauf.protokolle]
    gefahren = [ms for ms in beste if ms is not None]
    schnellste_ms = min(gefahren) if gefahren else 0
    schnellster = beste.index(schnellste_ms) if gefahren else None

    ergebnisse = tuple(
        Rennergebnis(
            fahrer=fahrer[quali.aufstellung[e.teilnehmer]].nummer,
            rennplatz=e.platz,
            qualifyingplatz=e.teilnehmer + 1,
            schnellste_runde=(e.teilnehmer == schnellster),
            ausgefallen=e.zeit_ms is None,
        )
        for e in verlauf.ergebnisse
    )
    wochenende = Ligawochenende(
        liga=liga,
        ergebnisse=ergebnisse,
        wetter=wetter.zustaende,
        siegerzeit_ms=verlauf.ergebnisse[0].zeit_ms or 0,
        schnellste_runde_ms=schnellste_ms,
        ueberholmanoever=len(verlauf.manoever),
        ausfaelle=sum(1 for e in verlauf.ergebnisse if e.zeit_ms is None),
        ausfuehrlich=True,
    )
    return wochenende, verlauf, quali


def _schnell(
    konfiguration: Konfiguration,
    welt: Welt,
    liga: int,
    fahrer: tuple[Fahrer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float,
) -> Ligawochenende:
    """Ein Rennwochenende auf Rundenebene (GDD 13).

    Anders als die ausfuehrliche Liga bekommt der Schnellmodus keinen
    Meisterschaftsstand: Dort faehrt jedes Auto seine gezeitete Runde in
    der Lage zu Sessionbeginn, die Reihenfolge der Starts aendert am
    Ergebnis also nichts.
    """
    feld = kern_welt.starterfeld(welt, liga)
    ergebnis = fahre_schnell(
        konfiguration,
        liga,
        strecke,
        feld,
        runden,
        seedquelle,
        streckenmittel,
        streckenverschleiss,
    )
    return Ligawochenende(
        liga=liga,
        ergebnisse=tuple(
            replace(e, fahrer=fahrer[e.fahrer].nummer) for e in ergebnis.ergebnisse
        ),
        wetter=ergebnis.wetter,
        siegerzeit_ms=ergebnis.siegerzeit_ms,
        schnellste_runde_ms=ergebnis.schnellste_runde_ms,
        ueberholmanoever=ergebnis.ueberholmanoever,
        ausfaelle=ergebnis.ausfaelle,
    )


# ---------------------------------------------------------------------------
# Der Saisonlauf
# ---------------------------------------------------------------------------
class Saisonlauf:
    """Faehrt eine ganze Saison und fuehrt die Tabellen aller Ligen."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        seedquelle: Seedquelle,
        jahr: int = 2026,
        strecken: tuple[Strecke, ...] | None = None,
    ) -> None:
        self.konfiguration = konfiguration
        self.welt = welt
        self.jahr = jahr
        self.seedquelle = seedquelle
        self.strecken = strecken or kern_strecke.lade_alle(konfiguration)

        anzahl = konfiguration.wert("kalender", "rennen_je_saison")
        if len(self.strecken) < anzahl:
            raise SaisonFehler(
                f"Eine Saison hat {anzahl} Rennen, geladen sind {len(self.strecken)} Strecken"
            )

        # Bezugsgroessen fuer Ueberholen und Reifenverschleiss; sie gelten
        # ueber alle Strecken und werden deshalb einmal gebildet.
        self.streckenmittel = kern_rennen.mittlerer_ueberholzonenanteil(
            konfiguration, self.strecken
        )
        self._querbeschleunigung = kern_reifen.mittlere_querbeschleunigung(self.strecken)

        self.tabellen: dict[int, Tabelle] = {
            liga: Tabelle(liga) for liga in range(1, konfiguration.wert("ligen", "anzahl") + 1)
        }
        self.wochenenden: list[Wochenende] = []

    # -- Stand -------------------------------------------------------------
    @property
    def rennen_je_saison(self) -> int:
        return self.konfiguration.wert("kalender", "rennen_je_saison")

    @property
    def gefahren(self) -> int:
        """Zahl der bereits gefahrenen Rennwochenenden."""
        return len(self.wochenenden)

    @property
    def naechstes_rennen(self) -> int | None:
        """Nummer des naechsten Rennens, 1-basiert; ``None`` am Saisonende."""
        return self.gefahren + 1 if self.gefahren < self.rennen_je_saison else None

    @property
    def ist_fertig(self) -> bool:
        return self.naechstes_rennen is None

    def strecke_zu(self, rennen: int) -> Strecke:
        if not 1 <= rennen <= self.rennen_je_saison:
            raise SaisonFehler(f"Rennen {rennen} gibt es in dieser Saison nicht")
        return self.strecken[rennen - 1]

    def tabelle(self, liga: int) -> Tabelle:
        try:
            return self.tabellen[liga]
        except KeyError:
            raise SaisonFehler(f"Liga {liga} gibt es nicht") from None

    def meisterschaft(self, liga: int, feld: tuple[Fahrer, ...]) -> tuple[int, ...] | None:
        """Meisterschaftsstand als Feldindizes, Erster zuerst (GDD 4).

        Das Qualifying braucht ihn fuer die Startreihenfolge. Vor dem
        ersten Rennen gibt es ihn nicht; dann faehrt das Feld aufsteigend
        nach Qualifying-Faehigkeit.
        """
        tabelle = self.tabelle(liga)
        if not tabelle.eintraege:
            return None
        stelle = {f.nummer: i for i, f in enumerate(feld)}
        geordnet = [stelle[e.fahrer] for e in tabelle.stand() if e.fahrer in stelle]
        if len(geordnet) != len(feld):
            # Nach einem Auf- oder Abstieg passt der Vorjahresstand nicht
            # mehr zum Feld; dann gilt wieder die Regel des ersten Rennens.
            return None
        return tuple(geordnet)

    # -- Fahren ------------------------------------------------------------
    def fahre_rennen(self, ausfuehrliche_liga: int | None = None) -> Wochenende:
        """Faehrt das naechste Rennwochenende in allen 20 Ligen (GDD 13).

        :param ausfuehrliche_liga: Liga, die voll simuliert wird - ueblich
            die des Spielers. Ohne Angabe laufen alle Ligen im
            Schnellmodus.
        """
        nummer = self.naechstes_rennen
        if nummer is None:
            raise SaisonFehler(f"Die Saison {self.jahr} ist zu Ende")
        if ausfuehrliche_liga is not None and ausfuehrliche_liga not in self.tabellen:
            raise SaisonFehler(f"Liga {ausfuehrliche_liga} gibt es nicht")

        strecke = self.strecke_zu(nummer)
        verschleiss = kern_reifen.streckenfaktor(
            self.konfiguration, strecke, self._querbeschleunigung
        )
        wochenende = self.seedquelle.zweig("saison", self.jahr).zweig("rennen", nummer)

        ligen: dict[int, Ligawochenende] = {}
        verlauf: Rennverlauf | None = None
        quali: Qualifying | None = None

        for liga in sorted(self.tabellen):
            fahrer = self.welt.liga(liga)
            runden = kern_rennen.rundenzahl(self.konfiguration, strecke, liga)
            seed = wochenende.zweig("liga", liga)
            if liga == ausfuehrliche_liga:
                ligen[liga], verlauf, quali = _ausfuehrlich(
                    self.konfiguration,
                    self.welt,
                    liga,
                    fahrer,
                    strecke,
                    runden,
                    seed,
                    self.streckenmittel,
                    verschleiss,
                    self.meisterschaft(liga, fahrer),
                )
            else:
                ligen[liga] = _schnell(
                    self.konfiguration,
                    self.welt,
                    liga,
                    fahrer,
                    strecke,
                    runden,
                    seed,
                    self.streckenmittel,
                    verschleiss,
                )
            self.tabellen[liga].verbuche(self.konfiguration, ligen[liga].ergebnisse)

        ergebnis = Wochenende(
            nummer=nummer,
            strecke=strecke.name,
            ligen=ligen,
            verlauf=verlauf,
            qualifying=quali,
            ausfuehrliche_liga=ausfuehrliche_liga,
        )
        self.wochenenden.append(ergebnis)
        return ergebnis

    def fahre_saison(self, ausfuehrliche_liga: int | None = None) -> tuple[Wochenende, ...]:
        """Faehrt alle noch offenen Rennwochenenden der Saison."""
        while not self.ist_fertig:
            self.fahre_rennen(ausfuehrliche_liga)
        return tuple(self.wochenenden)

    # -- Saisonende --------------------------------------------------------
    def auf_und_abstieg(self) -> tuple[Wechsel, ...]:
        """Die Ligawechsel nach dem letzten Rennen (GDD 13)."""
        if not self.ist_fertig:
            raise SaisonFehler(
                f"Erst nach Rennen {self.rennen_je_saison} steht der Auf- und Abstieg fest; "
                f"gefahren sind {self.gefahren}"
            )
        kern_wertung.pruefe_ligastaerken(self.konfiguration, self.tabellen)
        return kern_wertung.auf_und_abstieg(self.konfiguration, self.tabellen)

    def naechste_welt(self) -> Welt:
        """Die Welt der Folgesaison, mit vollzogenen Ligawechseln (GDD 13)."""
        return wende_wechsel_an(self.welt, self.auf_und_abstieg())


# ---------------------------------------------------------------------------
# Ligawechsel in die Welt uebernehmen
# ---------------------------------------------------------------------------
def wende_wechsel_an(welt: Welt, wechsel: tuple[Wechsel, ...]) -> Welt:
    """Setzt Auf- und Abstiege in eine neue Welt um (GDD 13).

    Die Teams bleiben unveraendert - ein Team kann danach Autos in anderen
    Ligen haben als zuvor. Die Zahl der Fahrer je Liga bleibt gleich, weil
    jeder Aufsteiger einen Absteiger der Liga darueber ersetzt.
    """
    ziel = {w.fahrer: w.nach_liga for w in wechsel}
    if len(ziel) != len(wechsel):
        raise SaisonFehler("Ein Fahrer kann nicht zugleich auf- und absteigen")

    fahrer = tuple(
        replace(f, liga=ziel[f.nummer]) if f.nummer in ziel else f for f in welt.fahrer
    )
    neu = Welt(teams=welt.teams, fahrer=fahrer, seed=welt.seed)

    vorher: dict[int, int] = {}
    for f in welt.fahrer:
        vorher[f.liga] = vorher.get(f.liga, 0) + 1
    nachher: dict[int, int] = {}
    for f in neu.fahrer:
        nachher[f.liga] = nachher.get(f.liga, 0) + 1
    for liga in sorted(set(vorher) | set(nachher)):
        if nachher.get(liga, 0) != vorher.get(liga, 0):
            raise SaisonFehler(
                f"Liga {liga} haette nach dem Wechsel {nachher.get(liga, 0)} Fahrer "
                f"statt {vorher.get(liga, 0)}"
            )
    return neu
