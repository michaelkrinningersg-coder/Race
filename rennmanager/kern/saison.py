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

``naechste_saison()`` macht daraus den Saisonwechsel: Statistik,
Streckenkenntnis und die Karriere des Spielers wandern mit, Tabellen und
Kalender beginnen neu. Die Karriere ist damit endlos.

Alle Wuerfe haengen am Hauptseed: Der Zweig eines Rennens heisst
``saison/<jahr>/rennen/<nummer>/liga/<liga>``. Dieselbe Saison mit
demselben Seed laeuft deshalb genau gleich ab, gleich ob die Liga des
Spielers ausfuehrlich oder schnell gefahren wird - die uebrigen 19 Ligen
bleiben davon unberuehrt (GDD 15).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import generationen as kern_generationen
from rennmanager.kern import heimstrecke as kern_heimstrecke
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern import popularitaet as kern_popularitaet
from rennmanager.kern import qualifying as kern_qualifying
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import rhythmus as kern_rhythmus
from rennmanager.kern import statistik as kern_statistik
from rennmanager.kern import strategie as kern_strategie
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import transfer as kern_transfer
from rennmanager.kern import welt as kern_welt
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.generationen import Winterbericht
from rennmanager.kern.qualifying import Qualifying
from rennmanager.kern.rennen import Rennverlauf
from rennmanager.kern.schnellsimulation import fahre_wochenende as fahre_schnell
from rennmanager.kern.statistik import Statistik
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.streckenkenntnis import Streckenkenntnis
from rennmanager.kern.welt import Fahrer, Welt
from rennmanager.kern.wertung import Rennergebnis, Tabelle, Wechsel
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class SaisonFehler(Exception):
    """Der Saisonlauf laesst sich so nicht fortsetzen."""


@dataclass(frozen=True)
class Wochenendrahmen:
    """Was an einem Rennwochenende fuer alle 20 Ligen gleich ist."""

    nummer: int
    strecke: Strecke
    verschleiss: float
    seedquelle: Seedquelle


@dataclass(frozen=True)
class Ligadaten:
    """Was eine Liga an einem Rennwochenende mitbringt.

    Einmal gezogen, von Qualifying und Rennen gemeinsam benutzt: Der
    Heimbonus aus Punkt 2 wird je Wochenende **einmal** gewuerfelt, und
    die Streckenkenntnis gilt fuer beide Sessions (GDD 6).
    """

    liga: int
    fahrer: tuple[Fahrer, ...]
    runden: int
    seedquelle: Seedquelle
    kenntnis: tuple[float, ...]
    tagesform: tuple[float, ...]
    autos: dict[str, dict[int, object]]
    rhythmus: tuple[float, ...]
    meisterschaft: tuple[int, ...] | None

    @property
    def nummern(self) -> tuple[int, ...]:
        return tuple(f.nummer for f in self.fahrer)


@dataclass(frozen=True)
class Ligawochenende:
    """Was eine Liga an einem Rennwochenende gefahren ist.

    ``ergebnisse`` nennt Fahrer mit ihrer weltweiten Nummer, nicht mit dem
    Platz im Starterfeld - nur so passen die Zeilen zur Tabelle.

    ``ueberholmanoever`` zaehlt Positionsgewinne je Runde, in beiden
    Rennmodellen gleich. Die volle Simulation kennt daneben jeden einzelnen
    Vorbeigang; der steht in ``Rennverlauf.manoever`` und ist fuer die
    Anzeige des Rennens da, nicht fuer die Wertung.
    """

    liga: int
    ergebnisse: tuple[Rennergebnis, ...]
    wetter: tuple[str, ...]
    siegerzeit_ms: int
    schnellste_runde_ms: int
    ueberholmanoever: int
    ausfaelle: int
    # Punkt 93 (A17): Die schnellste Qualirunde des Wochenendes und wer
    # sie fuhr, mit weltweiter Nummer. Daraus wird die Streckenbestmarke,
    # die im Qualifying der naechsten Saison oben steht.
    polezeit_ms: int = 0
    polefahrer: int = 0
    # Punkt 23: die Lage, unter der am meisten gefahren wurde. Die
    # Wetterbilanz braucht eine Lage je Rennen, nicht den ganzen Verlauf.
    vorherrschendes_wetter: str = ""
    ausfuehrlich: bool = False
    # Je Fahrer, mit weltweiter Nummer: gelungene Ueberholmanoever, die im
    # Rennen aufgetretenen Defekte und die gefahrenen Kilometer je
    # Wetterlage. Die Karriere braucht das fuer Erfahrung, Reparaturen und
    # die Wetter-Erfahrung (GDD 10 und 14).
    manoever_je_fahrer: dict[int, int] = field(default_factory=dict)
    defekte_je_fahrer: dict[int, tuple[str, ...]] = field(default_factory=dict)
    kilometer_je_fahrer: dict[int, dict[str, float]] = field(default_factory=dict)

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
def _kilometer_je_wetter(verlauf: Rennverlauf) -> tuple[dict[str, float], ...]:
    """Gefahrene Kilometer je Auto und Wetterlage (GDD 10).

    Der Rennverlauf haelt die zurueckgelegte Strecke in festen Abstaenden
    fest; das Wetter wechselt zu bekannten Zeitpunkten. Gezaehlt wird
    deshalb abschnittweise: Was ein Auto zwischen zwei Wetterwechseln
    zurueckgelegt hat, faellt der Lage dieses Abschnitts zu. Das ist
    dieselbe Zuordnung wie im Schnellmodus, wo jede Runde zu der Lage
    zaehlt, die zu ihrem Beginn galt.
    """
    if verlauf.wetter is None:
        # Kommt aus dem Saisonlauf nicht vor - dort bekommt jedes Rennen
        # sein Wetter. Ohne Wetterverlauf gibt es keine Lage, der die
        # Kilometer zufallen koennten.
        return tuple({} for _ in range(verlauf.anzahl))

    zeiten = np.asarray(verlauf.zeitpunkte_ms, dtype=float)
    distanz = np.asarray(verlauf.distanz_m, dtype=float)
    abschnitte = verlauf.wetter.abschnitte

    ergebnis: list[dict[str, float]] = [{} for _ in range(verlauf.anzahl)]
    for stelle, abschnitt in enumerate(abschnitte):
        von = int(np.searchsorted(zeiten, float(abschnitt.ab_ms), side="left"))
        bis = (
            int(np.searchsorted(zeiten, float(abschnitte[stelle + 1].ab_ms), side="left"))
            if stelle + 1 < len(abschnitte)
            else len(zeiten) - 1
        )
        if bis <= von:
            continue
        gefahren = (distanz[bis] - distanz[von]) / 1000.0
        for i, kilometer in enumerate(gefahren):
            if kilometer > 0.0:
                ergebnis[i][abschnitt.zustand] = (
                    ergebnis[i].get(abschnitt.zustand, 0.0) + float(kilometer)
                )
    return tuple(ergebnis)


def _fahre_qualifying(
    konfiguration: Konfiguration,
    welt: Welt,
    liga: int,
    strecke: Strecke,
    seedquelle: Seedquelle,
    meisterschaft: tuple[int, ...] | None,
    kenntnisfaktor: tuple[float, ...],
    spielerautos: dict[str, dict[int, object]],
    tagesformbonus: tuple[float, ...],
    rhythmusfaktor: tuple[float, ...],
) -> Qualifying:
    """Das Qualifying einer Liga (GDD 4).

    Eigene Funktion, weil das gefuehrte Rennwochenende dazwischen anhaelt
    (Punkt 12): Der Spieler sieht erst sein Qualifying, dann sein Rennen.
    Der Seedzweig heisst ``qualifying`` und haengt nicht an der
    Aufrufreihenfolge - derselbe Seed ergibt dasselbe Qualifying, ob am
    Stueck gefahren oder in zwei Etappen.
    """
    feld = kern_welt.starterfeld(
        welt, liga, autos=spielerautos.get(kern_ereignis.QUALIFYING)
    )
    return kern_qualifying.fahre(
        konfiguration,
        strecke,
        feld,
        seedquelle.zweig("qualifying"),
        meisterschaft,
        kenntnisfaktor=kenntnisfaktor,
        tagesformbonus=tagesformbonus,
        rhythmusfaktor=rhythmusfaktor,
    )


@dataclass(frozen=True)
class Rennvorbereitung:
    """Was vor dem Start feststeht: Wetter und zulaessige Strategien.

    Punkt 39: Der Spieler soll die Reifen seiner vier Fahrer selbst
    waehlen duerfen. Dafuer muss er sehen koennen, was ueberhaupt zur
    Wahl steht - und das steht vor dem Rennen fest, nicht erst danach.
    """

    wetter: kern_wetter.Wetterverlauf
    strategien: kern_strategie.Rennstrategien
    teilnehmer: tuple[kern_rennen.Teilnehmer, ...]


def startfeld(
    konfiguration: Konfiguration,
    welt: Welt,
    liga: int,
    spielerautos: dict[str, dict[int, object]],
    quali: Qualifying,
) -> tuple[kern_rennen.Teilnehmer, ...]:
    """Das Feld in der Startaufstellung des Qualifyings; Platz 1 ist die Pole."""
    rennfeld = kern_welt.starterfeld(
        welt, liga, autos=spielerautos.get(kern_ereignis.RENNEN)
    )
    return tuple(
        kern_rennen.Teilnehmer(
            auto=rennfeld[i].auto,
            startplatz=platz,
            farbe=rennfeld[i].farbe,
            ist_spieler=rennfeld[i].ist_spieler,
            nummer=rennfeld[i].nummer,
        )
        for platz, i in enumerate(quali.aufstellung, start=1)
    )


def vor_dem_rennen(
    konfiguration: Konfiguration,
    gestartet: tuple[kern_rennen.Teilnehmer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenverschleiss: float,
    quali: Qualifying,
    liga: int | None = None,
) -> Rennvorbereitung:
    """Wetter und Strategien, bevor ein Meter gefahren ist.

    Zweimal aufgerufen ergibt zweimal dasselbe: Beides haengt allein am
    Seed (GDD 15). Die Oberflaeche darf das also vorziehen, um dem
    Spieler die Wahl zu zeigen, ohne das Rennen zu veraendern.
    """
    # Das Rennwetter wird getrennt vom Qualifying gewuerfelt (GDD 7).
    rundendauer = quali.pole.zeit_ms
    wetter = kern_wetter.wuerfle(
        konfiguration,
        strecke.name,
        rundendauer * runden,
        rundendauer,
        seedquelle.zweig("rennwetter"),
    )
    # Punkt 39: Eine Vorausberechnung entscheidet, welche Mischungsfolgen
    # zulaessig sind; unter ihnen waehlt jedes Auto. Das Wetter geht als
    # ganze Vorhersage ein - es steht ja schon fest.
    strategien = kern_strategie.feldstrategien(
        konfiguration,
        [t.auto for t in gestartet],
        strecke,
        runden,
        streckenverschleiss,
        wetter,
        seedquelle.zweig("strategie"),
        liga,
    )
    return Rennvorbereitung(
        wetter=wetter, strategien=strategien, teilnehmer=gestartet
    )


def _strategieblaetter(
    strategien: kern_strategie.Rennstrategien,
    je_auto: list[kern_strategie.Strategie],
    kennungen: list,
) -> tuple[kern_rennen.Strategieblatt, ...]:
    """Fasst das Feld zu Strategien zusammen - ohne zu verraten, wer welche faehrt.

    Eine Zeile je vertretener Variante, geordnet nach der Rennzeit, die
    der Planer **ohne Verkehr** fuer sie gerechnet hat. Die Autonummern
    stehen darin, damit die Anzeige den Rueckstand der Gruppe mitteln
    kann; angezeigt werden sie nicht (Entscheidung des Auftraggebers).

    Die Stopprunden kommen aus der **Variante**, nicht aus dem gefahrenen
    Plan: Das Boxenstoppfenster zieht zwei Autos derselben Strategie um
    bis zu drei Runden auseinander, und das sind trotzdem nicht zwei
    Strategien.
    """
    gruppen: dict[object, list[int]] = {}
    for stelle, kennung in enumerate(kennungen):
        gruppen.setdefault(kennung, []).append(stelle)

    blaetter: list[kern_rennen.Strategieblatt] = []
    for kennung, autos in gruppen.items():
        if isinstance(kennung, int) and 0 <= kennung < len(strategien.varianten):
            variante = strategien.varianten[kennung]
            folge, stopps, zeit = variante.folge, variante.stopps, variante.zeit_ms
        else:
            # Der Notfallplan oder eine vom Spieler selbst gebaute Folge:
            # Fuer sie hat der Planer keine Zeit gerechnet.
            eigen = je_auto[autos[0]]
            folge = "-".join(m.kuerzel for m in eigen.mischungen)
            stopps, zeit = eigen.stopps, None
        blaetter.append(
            kern_rennen.Strategieblatt(
                folge=folge, stopps=tuple(stopps), autos=tuple(autos), zeit_ms=zeit
            )
        )
    blaetter.sort(key=lambda b: (b.zeit_ms is None, b.zeit_ms or 0.0, b.folge))
    return tuple(blaetter)


def _fahre_rennen(
    konfiguration: Konfiguration,
    welt: Welt,
    liga: int,
    fahrer: tuple[Fahrer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float,
    kenntnisfaktor: tuple[float, ...],
    spielerautos: dict[str, dict[int, object]],
    tagesformbonus: tuple[float, ...],
    rhythmusfaktor: tuple[float, ...],
    quali: Qualifying,
    wahl: dict[int, kern_strategie.Strategie] | None = None,
    fortschritt=None,
) -> tuple[Ligawochenende, Rennverlauf]:
    """Das Rennen einer Liga auf ein gefahrenes Qualifying (GDD 4).

    Rennen und Qualifying bekommen ein eigenes Feld: Die entwickelten
    Werte des Spielers koennen sich zwischen beiden unterscheiden, weil
    E12 aus GDD 14 nur im Qualifying wirkt. Die *Reihenfolge* des Feldes
    richtet sich in beiden Faellen nach der Welt, sonst passten die
    Indizes aus dem Qualifying nicht mehr aufs Rennen.

    :param wahl: je Fahrernummer eine vom Spieler gewaehlte Strategie
        (Punkt 39). Wer nicht darin steht, faehrt, was die
        Vorausberechnung ihm zuteilt.
    :param fortschritt: wird je gefahrener Runde des Fuehrenden gerufen
        (E10), damit die Oberflaeche waehrend der Rechnung etwas zeigen
        kann.
    """
    gestartet = startfeld(konfiguration, welt, liga, spielerautos, quali)
    vorbereitung = vor_dem_rennen(
        konfiguration, gestartet, strecke, runden, seedquelle,
        streckenverschleiss, quali, liga,
    )
    strategien = vorbereitung.strategien
    wetter = vorbereitung.wetter
    je_auto = list(strategien.je_auto)
    # Punkt 91: Womit das Feld unterwegs ist - die gezogene Variante je
    # Auto. Wer vom Spieler eine eigene Strategie bekommen hat, zaehlt
    # mit seiner Wahl; sonst kaeme die Zahl oben im Rennen zu klein
    # heraus, wenn der Spieler etwas faehrt, was sonst niemand faehrt.
    kennungen: list[object] = list(
        strategien.gewaehlt or range(len(strategien.je_auto))
    )
    for stelle, teilnehmer in enumerate(gestartet):
        gewaehlt = (wahl or {}).get(teilnehmer.nummer)
        if gewaehlt is not None:
            je_auto[stelle] = gewaehlt
            kennungen[stelle] = (
                tuple(m.schluessel for m in gewaehlt.mischungen),
                tuple(gewaehlt.stopps),
            )
    blaetter = _strategieblaetter(strategien, je_auto, kennungen)
    verlauf = kern_rennen.simuliere(
        konfiguration,
        strecke,
        gestartet,
        runden,
        seedquelle.zweig("rennen"),
        streckenmittel,
        wetter=wetter,
        streckenverschleiss=streckenverschleiss,
        strategien=tuple(je_auto),
        strategieblaetter=blaetter,
        mischungspflicht=strategien.pflicht_zwei,
        liga=liga,
        # Die Startaufstellung ordnet das Feld um; Kenntnisfaktor und
        # Tagesformbonus muessen mitwandern, sonst faehrt jeder mit den
        # Werten eines anderen.
        kenntnisfaktor=tuple(kenntnisfaktor[i] for i in quali.aufstellung),
        tagesformbonus=tuple(tagesformbonus[i] for i in quali.aufstellung),
        rhythmusfaktor=tuple(rhythmusfaktor[i] for i in quali.aufstellung),
        fortschritt=fortschritt,
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
    # Was je Fahrer anfaellt (GDD 10 und 14). Die Indizes zaehlen in der
    # Startaufstellung, deshalb geht es ueber ``quali.aufstellung`` zurueck
    # auf die weltweite Fahrernummer.
    def nummer_von(stelle: int) -> int:
        return fahrer[quali.aufstellung[stelle]].nummer

    # Gezaehlt werden die Positionsgewinne je Runde, nicht die rohen
    # Vorbeigaenge: Ein Duell, das innerhalb einer Runde hin und her geht,
    # ist kein Dutzend Ueberholmanoever. Nur so ist die Erfahrung aus
    # GDD 10 mit der des Schnellmodus vergleichbar - gemessen lagen die
    # rohen Vorbeigaenge um den Faktor 3,2 darueber.
    manoever_je_fahrer = {
        nummer_von(stelle): anzahl
        for stelle, anzahl in enumerate(verlauf.positionsgewinne)
        if anzahl
    }

    defekte_je_fahrer: dict[int, tuple[str, ...]] = {}
    for zwischenfall in verlauf.zwischenfaelle:
        if zwischenfall.art != kern_zwischenfall.Art.DEFEKT:
            continue
        schluessel = nummer_von(zwischenfall.teilnehmer)
        defekte_je_fahrer[schluessel] = defekte_je_fahrer.get(schluessel, ()) + (
            zwischenfall.defekt,
        )

    kilometer = _kilometer_je_wetter(verlauf)
    kilometer_je_fahrer = {
        nummer_von(stelle): eintrag
        for stelle, eintrag in enumerate(kilometer)
        if eintrag
    }

    wochenende = Ligawochenende(
        liga=liga,
        ergebnisse=ergebnisse,
        wetter=wetter.zustaende,
        vorherrschendes_wetter=wetter.vorherrschend(verlauf.dauer_ms),
        siegerzeit_ms=verlauf.ergebnisse[0].zeit_ms or 0,
        schnellste_runde_ms=schnellste_ms,
        polezeit_ms=quali.pole.zeit_ms if quali is not None else 0,
        polefahrer=(
            nummer_von(quali.aufstellung[0]) if quali is not None else 0
        ),
        ueberholmanoever=sum(verlauf.positionsgewinne),
        ausfaelle=sum(1 for e in verlauf.ergebnisse if e.zeit_ms is None),
        ausfuehrlich=True,
        manoever_je_fahrer=manoever_je_fahrer,
        defekte_je_fahrer=defekte_je_fahrer,
        kilometer_je_fahrer=kilometer_je_fahrer,
    )
    return wochenende, verlauf


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
    kenntnisfaktor: tuple[float, ...],
    spielerautos: dict[str, dict[int, object]],
    tagesformbonus: tuple[float, ...],
    rhythmusfaktor: tuple[float, ...],
) -> tuple[Ligawochenende, Rennverlauf, Qualifying]:
    """Qualifying und Rennen einer Liga am Stueck (GDD 4).

    Der Weg fuer die Saison, die 20 Ligen hintereinander faehrt. Das
    gefuehrte Rennwochenende ruft stattdessen die beiden Etappen einzeln
    auf und haelt dazwischen an (Punkt 12) - herauskommen muss dasselbe.
    """
    quali = _fahre_qualifying(
        konfiguration,
        welt,
        liga,
        strecke,
        seedquelle,
        meisterschaft,
        kenntnisfaktor,
        spielerautos,
        tagesformbonus,
        rhythmusfaktor,
    )
    wochenende, verlauf = _fahre_rennen(
        konfiguration,
        welt,
        liga,
        fahrer,
        strecke,
        runden,
        seedquelle,
        streckenmittel,
        streckenverschleiss,
        kenntnisfaktor,
        spielerautos,
        tagesformbonus,
        rhythmusfaktor,
        quali,
    )
    return wochenende, verlauf, quali


def _schnellstrategien(
    konfiguration: Konfiguration,
    feld,
    strecke: Strecke,
    runden: int,
    streckenverschleiss: float,
    seedquelle: Seedquelle,
    liga: int,
):
    """Die Strategien einer Liga im Schnellmodus (Punkt 39).

    Das Rennwetter wird hier vorweggenommen: Der Schnellmodus wuerfelt es
    selbst aus ``zweig("rennwetter")``, und dieselbe Rechnung hier ergibt
    denselben Verlauf. Nur so plant die Strategie gegen das Wetter, das
    im Rennen wirklich kommt.
    """
    autos = [t.auto for t in feld]
    grundrunde = sum(
        kern_tempo.fahre_runde(konfiguration, strecke, auto).zeit_ms for auto in autos
    ) / max(len(autos), 1)
    wetter = kern_wetter.wuerfle(
        konfiguration,
        strecke.name,
        int(grundrunde * runden),
        int(grundrunde),
        seedquelle.zweig("rennwetter"),
    )
    return kern_strategie.feldstrategien(
        konfiguration, autos, strecke, runden, streckenverschleiss, wetter,
        seedquelle.zweig("strategie"), liga,
    ).je_auto


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
    kenntnisfaktor: tuple[float, ...],
    spielerautos: dict[str, dict[int, object]],
    tagesformbonus: tuple[float, ...],
    rhythmusfaktor: tuple[float, ...],
) -> Ligawochenende:
    """Ein Rennwochenende auf Rundenebene (GDD 13).

    Anders als die ausfuehrliche Liga bekommt der Schnellmodus keinen
    Meisterschaftsstand: Dort faehrt jedes Auto seine gezeitete Runde in
    der Lage zu Sessionbeginn, die Reihenfolge der Starts aendert am
    Ergebnis also nichts.
    """
    feld = kern_welt.starterfeld(
        welt, liga, autos=spielerautos.get(kern_ereignis.RENNEN)
    )
    # Punkt 39: Der Schnellmodus faehrt dieselben Strategien wie die volle
    # Simulation - nur das Wetter kennt er erst dort. Deshalb wird es hier
    # aus demselben Zweig gewuerfelt wie drinnen.
    ergebnis = fahre_schnell(
        konfiguration,
        liga,
        strecke,
        feld,
        runden,
        seedquelle,
        streckenmittel,
        streckenverschleiss,
        kenntnisfaktor=kenntnisfaktor,
        tagesformbonus=tagesformbonus,
        rhythmusfaktor=rhythmusfaktor,
        strategien=_schnellstrategien(
            konfiguration, feld, strecke, runden, streckenverschleiss, seedquelle, liga
        ),
    )
    return Ligawochenende(
        liga=liga,
        ergebnisse=tuple(
            replace(e, fahrer=fahrer[e.fahrer].nummer) for e in ergebnis.ergebnisse
        ),
        wetter=ergebnis.wetter,
        vorherrschendes_wetter=ergebnis.vorherrschendes_wetter,
        siegerzeit_ms=ergebnis.siegerzeit_ms,
        schnellste_runde_ms=ergebnis.schnellste_runde_ms,
        polezeit_ms=ergebnis.polezeit_ms,
        polefahrer=(
            fahrer[ergebnis.polefahrer].nummer
            if ergebnis.polefahrer < len(fahrer)
            else 0
        ),
        ueberholmanoever=ergebnis.ueberholmanoever,
        ausfaelle=ergebnis.ausfaelle,
        # Der Schnellmodus zaehlt je Feldplatz; hier wird daraus die
        # weltweite Fahrernummer (GDD 10 und 14).
        manoever_je_fahrer={
            fahrer[i].nummer: anzahl
            for i, anzahl in enumerate(ergebnis.manoever_je_auto)
            if anzahl
        },
        defekte_je_fahrer={
            fahrer[i].nummer: defekte
            for i, defekte in enumerate(ergebnis.defekte_je_auto)
            if defekte
        },
        kilometer_je_fahrer={
            fahrer[i].nummer: eintrag
            for i, eintrag in enumerate(ergebnis.kilometer_je_wetter)
            if eintrag
        },
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
        jahr: int | None = None,
        strecken: tuple[Strecke, ...] | None = None,
        statistik: Statistik | None = None,
        kenntnis: Streckenkenntnis | None = None,
        tabellen: dict[int, Tabelle] | None = None,
        vorgefahren: int = 0,
        karriere=None,
        popularitaet: kern_popularitaet.Popularitaet | None = None,
    ) -> None:
        self.konfiguration = konfiguration
        self.welt = welt
        self.jahr = jahr if jahr is not None else kern_karriere.startjahr(konfiguration)
        self.seedquelle = seedquelle
        self.strecken = strecken or kern_strecke.lade_alle(konfiguration)
        # Statistik und Streckenkenntnis ueberdauern die Saison (GDD 6 und
        # 13); ein Saisonlauf fuehrt sie nur fort.
        self.statistik = statistik or kern_statistik.Statistik(konfiguration)
        self.kenntnis = kenntnis or kern_streckenkenntnis.Streckenkenntnis(
            konfiguration, seedquelle=seedquelle.zweig("lerntempo")
        )
        # Die Popularitaet ueberdauert die Saison wie die Streckenkenntnis
        # (Punkt 5).
        self.popularitaet = popularitaet or kern_popularitaet.Popularitaet(konfiguration)

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
        # Bezugsgroesse des Rhythmus aus Punkt 15: der Kurvenfolgenanteil
        # gegen den Schnitt aller 20 Strecken.
        self._kurvenmittel = kern_rhythmus.mittlerer_kurvenfolgenanteil(self.strecken)

        self.tabellen: dict[int, Tabelle] = tabellen or {
            liga: Tabelle(liga) for liga in range(1, konfiguration.wert("ligen", "anzahl") + 1)
        }
        self.wochenenden: list[Wochenende] = []
        # Punkt 35: Was der letzte Generationswechsel bewegt hat.
        self.letzter_winter: Winterbericht | None = None
        # Rennen, die vor dem Laden eines Spielstands schon gefahren waren
        # (GDD 15). Ihre Wochenenden liegen nicht mehr vor, ihre Punkte
        # stehen aber in den Tabellen.
        self.vorgefahren = vorgefahren
        # Die Karriere haelt die entwickelten Werte des Spielers samt
        # Ereignissen und Defekten (GDD 1 und 14). Ohne sie faehrt der
        # Spieler mit den Werten, die die Welt ihm gegeben hat - bei einem
        # neuen Spielstand also dauerhaft mit Nullen.
        self.karriere = karriere
        self._teile_kenntnis()

    # -- Stand -------------------------------------------------------------
    @property
    def rennen_je_saison(self) -> int:
        return self.konfiguration.wert("kalender", "rennen_je_saison")

    @property
    def gefahren(self) -> int:
        """Zahl der bereits gefahrenen Rennwochenenden."""
        return self.vorgefahren + len(self.wochenenden)

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

    def spielerautos(self, liga: int) -> dict[str, dict[int, object]]:
        """Das Auto des Spielers je Session, wenn er in dieser Liga faehrt.

        Je Session ein eigenes, weil E12 aus GDD 14 nur im Qualifying
        wirkt.
        """
        if self.karriere is None:
            return {}
        # Alle eigenen Fahrer dieser Liga, nicht nur einer: Seit der
        # Spieler Teamchef ist, koennen mehrere seiner vier im selben
        # Rennen stehen - und jedes Auto ist einzeln entwickelt.
        eigene = [
            f.nummer
            for f in self.welt.fahrer
            if f.ist_spieler and f.liga == liga and f.nummer in self.karriere.autos
        ]
        if not eigene:
            return {}
        return {
            sitzung: {
                nummer: self.karriere.rennauto_von(
                    nummer, self.welt.fahrer[nummer].auto, sitzung
                )
                for nummer in eigene
            }
            for sitzung in (kern_ereignis.QUALIFYING, kern_ereignis.RENNEN)
        }

    def tagesformbonus(self, liga: int, feld: tuple[Fahrer, ...]) -> tuple[float, ...]:
        """Zuschlag auf den Tagesform-Mittelwert je Feldplatz (GDD 14).

        Nur E3 Motivationsschub hebt ihn, und nur beim Spieler: Die KI hat
        keine Ereignisse (GDD 12).
        """
        ohne = (0.0,) * len(feld)
        if self.karriere is None:
            return ohne
        bonus = self.karriere.tagesformbonus()
        if not bonus:
            return ohne
        # E3 gilt dem Team, also allen eigenen Fahrern dieser Liga.
        eigene = {
            f.nummer for f in self.welt.fahrer if f.ist_spieler and f.liga == liga
        }
        if not eigene:
            return ohne
        return tuple(bonus if f.nummer in eigene else 0.0 for f in feld)

    def rhythmusfaktoren(
        self, strecke: Strecke, feld: tuple[Fahrer, ...], autos: dict[int, object]
    ) -> tuple[float, ...]:
        """Faktor auf die Querbeschleunigung je Feldplatz (Punkt 15).

        Gerechnet wird mit dem Auto, das wirklich faehrt - beim Spieler
        also mit dem entwickelten aus der Karriere.
        """
        return tuple(
            kern_rhythmus.faktor(
                self.konfiguration,
                autos.get(f.nummer, f.auto),
                strecke,
                self._kurvenmittel,
            )
            for f in feld
        )

    def sessionautos(
        self,
        liga: int,
        strecke: Strecke,
        fahrer: tuple[Fahrer, ...],
        seedquelle: Seedquelle,
    ) -> dict[str, dict[int, object]]:
        """Die Autos, mit denen dieses Feld faehrt, je Session.

        Zwei Dinge treten an die Stelle des Autos aus der Welt: die
        entwickelten Werte des Spielers (GDD 1 und 14) und der Heimbonus
        aus Punkt 2. Beide zusammen - wer im eigenen Land faehrt und der
        Spieler ist, bekommt beides.

        Die fuenf Eigenschaften des Heimbonus werden je Rennwochenende
        einmal gezogen und gelten fuer Qualifying und Rennen.
        """
        autos = self.spielerautos(liga)
        daheim = kern_heimstrecke.heimfahrer(fahrer, strecke)
        if not daheim:
            return autos

        heimseed = seedquelle.zweig("heimstrecke")
        for sitzung in (kern_ereignis.QUALIFYING, kern_ereignis.RENNEN):
            je_sitzung = dict(autos.get(sitzung, {}))
            for f in daheim:
                basis = je_sitzung.get(f.nummer, f.auto)
                je_sitzung[f.nummer] = kern_heimstrecke.mit_bonus(
                    self.konfiguration, basis, heimseed.zweig("fahrer", f.nummer)
                )
            autos[sitzung] = je_sitzung
        return autos

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
    def beginne_wochenende(self, nummer: int | None = None) -> Wochenendrahmen:
        """Ruestet das naechste Rennwochenende zu und startet den Renntag.

        Strecke, Reifenverschleiss und der Seedzweig gelten fuer alle 20
        Ligen; sie einmal zu bilden ist die halbe Arbeit. Der Kalender der
        Karriere wird dabei auf den Renntag vorgeschaltet (GDD 2) - vor dem
        Rennen, damit die Ereignisse dieser Tage noch auf es wirken.

        **Das bewegt die Karriere.** Wer nur wissen will, was als Naechstes
        ansteht, nimmt ``strecke_zu`` und ``renntag``; das gefuehrte
        Wochenende ruft diese Methode erst, wenn wirklich gefahren wird.
        """
        if nummer is None:
            nummer = self.naechstes_rennen
        if nummer is None:
            raise SaisonFehler(f"Die Saison {self.jahr} ist zu Ende")
        # Eine Karriere kann auch nach dem Aufbau gesetzt worden sein.
        self._teile_kenntnis()
        self._stelle_auf_renntag(nummer)
        strecke = self.strecke_zu(nummer)
        return Wochenendrahmen(
            nummer=nummer,
            strecke=strecke,
            verschleiss=kern_reifen.streckenfaktor(
                self.konfiguration, strecke, self._querbeschleunigung
            ),
            seedquelle=self.seedquelle.zweig("saison", self.jahr).zweig(
                "rennen", nummer
            ),
        )

    def ligadaten(self, rahmen: Wochenendrahmen, liga: int) -> Ligadaten:
        """Alles, was eine Liga an diesem Wochenende mitbringt.

        Qualifying und Rennen brauchen dasselbe; das gefuehrte Wochenende
        haelt dazwischen an (Punkt 12) und darf es nicht zweimal ziehen -
        der Heimbonus etwa wird je Wochenende **einmal** gewuerfelt.
        """
        fahrer = self.welt.liga(liga)
        seed = rahmen.seedquelle.zweig("liga", liga)
        autos = self.sessionautos(liga, rahmen.strecke, fahrer, seed)
        return Ligadaten(
            liga=liga,
            fahrer=fahrer,
            runden=kern_rennen.rundenzahl(self.konfiguration, rahmen.strecke, liga),
            seedquelle=seed,
            kenntnis=self.kenntnis.tempofaktoren(
                tuple(f.nummer for f in fahrer), rahmen.strecke.name
            ),
            tagesform=self.tagesformbonus(liga, fahrer),
            autos=autos,
            rhythmus=self.rhythmusfaktoren(
                rahmen.strecke, fahrer, autos.get(kern_ereignis.RENNEN, {})
            ),
            meisterschaft=self.meisterschaft(liga, fahrer),
        )

    def _fahre_liga(
        self, rahmen: Wochenendrahmen, daten: Ligadaten, ausfuehrlich: bool
    ) -> tuple[Ligawochenende, Rennverlauf | None, Qualifying | None]:
        """Eine Liga an diesem Wochenende, voll oder im Schnellmodus."""
        if ausfuehrlich:
            wochenende, verlauf, quali = _ausfuehrlich(
                self.konfiguration,
                self.welt,
                daten.liga,
                daten.fahrer,
                rahmen.strecke,
                daten.runden,
                daten.seedquelle,
                self.streckenmittel,
                rahmen.verschleiss,
                daten.meisterschaft,
                daten.kenntnis,
                daten.autos,
                daten.tagesform,
                daten.rhythmus,
            )
            return wochenende, verlauf, quali
        return (
            _schnell(
                self.konfiguration,
                self.welt,
                daten.liga,
                daten.fahrer,
                rahmen.strecke,
                daten.runden,
                daten.seedquelle,
                self.streckenmittel,
                rahmen.verschleiss,
                daten.kenntnis,
                daten.autos,
                daten.tagesform,
                daten.rhythmus,
            ),
            None,
            None,
        )

    def verbuche_liga(
        self, rahmen: Wochenendrahmen, daten: Ligadaten, ergebnis: Ligawochenende
    ) -> None:
        """Traegt ein gefahrenes Ligawochenende ueberall ein.

        Tabelle, Popularitaet, Statistik, Streckenkenntnis und - nur in der
        Liga des Spielers - die Karriere. Jede Liga bucht fuer sich, mit
        eigenem Seedzweig: Die Reihenfolge, in der die 20 Ligen gebucht
        werden, aendert am Ergebnis nichts. Nur deshalb darf das gefuehrte
        Wochenende (Punkt 12) mit der Liga des Spielers anfangen.
        """
        liga = daten.liga
        self.tabellen[liga].verbuche(self.konfiguration, ergebnis.ergebnisse)
        # Siege, Podien und Poles machen bekannt (Punkt 5).
        self.popularitaet.verbuche_wochenende(ergebnis.ergebnisse)
        self.statistik.verbuche_wochenende(
            saison=self.jahr,
            rennen=rahmen.nummer,
            liga=liga,
            strecke=rahmen.strecke.name,
            ergebnisse=ergebnis.ergebnisse,
            schnellste_runde_ms=ergebnis.schnellste_runde_ms,
            wetter=ergebnis.vorherrschendes_wetter,
            quali_ms=ergebnis.polezeit_ms,
            quali_fahrer=ergebnis.polefahrer or None,
        )
        # Qualifying und Rennen zaehlen beide fuer die Kenntnis (GDD 6).
        quali_runden = self.konfiguration.wert(
            "qualifying", "aufwaermrunden"
        ) + self.konfiguration.wert("qualifying", "gezeitete_runden")
        gefahrene = daten.runden + quali_runden
        kenntnisseed = daten.seedquelle.zweig("kenntnis")
        eigene = self._spielernummern(liga)
        # Die eigenen Fahrer buchen ueber die Karriere, weil E10 Testfahrt
        # geglueckt ihren Zuwachs hebt (GDD 14). Ihr Seedzweig ist
        # derselbe wie im Feld, damit derselbe Seed dieselbe Saison
        # ergibt (GDD 15).
        self.kenntnis.verbuche_feld(
            tuple(n for n in daten.nummern if n not in eigene),
            rahmen.strecke.name,
            gefahrene,
            kenntnisseed,
        )
        for stelle, spieler in enumerate(eigene):
            self.karriere.verbuche_runden(
                rahmen.strecke.name,
                gefahrene,
                kenntnisseed.zweig("fahrer", spieler),
                fahrer=spieler,
            )
            # Sponsorenvertraege und Ereignisse zaehlen je Rennen, nicht
            # je Fahrer - deshalb nur beim ersten eigenen Auto.
            self._verbuche_karriere(ergebnis, spieler, zaehlt=stelle == 0)

    def schliesse_wochenende_ab(self, ergebnis: Wochenende) -> Wochenende:
        """Haengt das gefahrene Wochenende an und beendet den Renntag."""
        self.wochenenden.append(ergebnis)
        # Der Renntag ist vorbei; der naechste Tag gehoert schon wieder
        # der Planung (GDD 2).
        self._schliesse_renntag_ab()
        return ergebnis

    def fahre_rennen(self, ausfuehrliche_liga: int | None = None) -> Wochenende:
        """Faehrt das naechste Rennwochenende in allen 20 Ligen (GDD 13).

        :param ausfuehrliche_liga: Liga, die voll simuliert wird - ueblich
            die des Spielers. Ohne Angabe laufen alle Ligen im
            Schnellmodus.
        """
        if ausfuehrliche_liga is not None and ausfuehrliche_liga not in self.tabellen:
            raise SaisonFehler(f"Liga {ausfuehrliche_liga} gibt es nicht")

        rahmen = self.beginne_wochenende()
        ligen: dict[int, Ligawochenende] = {}
        verlauf: Rennverlauf | None = None
        quali: Qualifying | None = None

        for liga in sorted(self.tabellen):
            daten = self.ligadaten(rahmen, liga)
            ligen[liga], gefahren, gequalt = self._fahre_liga(
                rahmen, daten, liga == ausfuehrliche_liga
            )
            if liga == ausfuehrliche_liga:
                verlauf, quali = gefahren, gequalt
            self.verbuche_liga(rahmen, daten, ligen[liga])

        return self.schliesse_wochenende_ab(
            Wochenende(
                nummer=rahmen.nummer,
                strecke=rahmen.strecke.name,
                ligen=ligen,
                verlauf=verlauf,
                qualifying=quali,
                ausfuehrliche_liga=ausfuehrliche_liga,
            )
        )

    # -- Kalender (GDD 2) --------------------------------------------------
    def renntag(self, nummer: int) -> dt.date | None:
        """Das Datum, an dem dieses Rennen stattfindet.

        Der Kalender haengt an der Karriere; ohne sie hat der Saisonlauf
        keine Daten, nur Rennnummern.
        """
        if self.karriere is None:
            return None
        renntage = self.karriere.saison.renntage
        return renntage[nummer - 1] if 1 <= nummer <= len(renntage) else None

    @property
    def offene_tage_vor_dem_rennen(self) -> int:
        """Nutzbare Tage, die bis zum naechsten Renntag noch frei sind.

        Die Oberflaeche warnt damit vor Tagen, die ungenutzt verfallen
        wuerden (GDD 2: "Ein Tag, der vorbei ist, ohne belegt zu sein, ist
        verloren").
        """
        if self.karriere is None or self.naechstes_rennen is None:
            return 0
        return self.karriere.offene_tage

    def _stelle_auf_renntag(self, nummer: int) -> int:
        """Schaltet den Kalender der Karriere bis zum Renntag (GDD 2).

        Nur vorwaerts: Ein geladener Spielstand kann schon weiter sein,
        dann bleibt der Kalender, wie er ist.

        :return: Zahl der uebersprungenen Tage
        """
        ziel = self.renntag(nummer)
        if ziel is None:
            return 0
        uebersprungen = 0
        while self.karriere.heute < ziel:
            self.karriere.tag_weiter()
            uebersprungen += 1
        return uebersprungen

    def _schliesse_renntag_ab(self) -> None:
        """Schaltet einen Tag ueber den Renntag hinaus (GDD 2).

        Sonst stuende der Kalender weiter auf dem Renntag und das naechste
        Rennwochenende faende am selben Tag statt.
        """
        if self.karriere is None:
            return
        if self.karriere.heute < self.karriere.saison.tage[-1].datum:
            self.karriere.tag_weiter()

    def _teile_kenntnis(self) -> None:
        """Karriere und Welt teilen sich eine Streckenkenntnis (GDD 6).

        Es gibt nur *eine* im Spiel - sie haelt alle 600 Fahrer. Die
        Karriere schreibt die Runden des Spielers hinein, das Rennen liest
        die Tempofaktoren daraus; zwei getrennte Staende kaemen nie
        zusammen. Der Spielstand verbindet beide beim Laden auf dieselbe
        Weise (GDD 15).
        """
        if self.karriere is not None and self.karriere.kenntnis is not self.kenntnis:
            self.karriere.kenntnis = self.kenntnis

    def _spielernummern(self, liga: int) -> tuple[int, ...]:
        """Die eigenen Fahrer, die in dieser Liga starten.

        Seit der Spieler Teamchef ist, koennen mehrere seiner vier im
        selben Rennen stehen - und jeder verdient fuer sich.
        """
        if self.karriere is None:
            return ()
        return tuple(
            f.nummer
            for f in self.welt.fahrer
            if f.ist_spieler and f.liga == liga and f.nummer in self.karriere.autos
        )

    def _verbuche_karriere(
        self, wochenende: Ligawochenende, spieler: int, zaehlt: bool = True
    ) -> None:
        """Schreibt einem eigenen Fahrer gut, was sein Wochenende brachte.

        GDD 10: Preisgeld, Startgeld, Sponsorenauszahlung und Erfahrung -
        Letztere auch aus den Ueberholmanoevern und den Kilometern je
        Wetterlage. GDD 14: Defekte aus dem Rennen bleiben offen, bis der
        Spieler sie bezahlt.

        Die Streckenkenntnis ist vorher gebucht: ``verbuche_rennen``
        zaehlt die Ereignisse ein Rennwochenende weiter, danach ist E10
        abgelaufen.
        """
        ergebnis = wochenende.ergebnis_von(spieler)
        if ergebnis is None:  # pragma: no cover - das Feld enthaelt den Spieler
            return
        self.karriere.uebernimm_defekte(wochenende.defekte_je_fahrer.get(spieler, ()))
        self.karriere.verbuche_rennen(
            platz=ergebnis.rennplatz,
            ueberholmanoever=wochenende.manoever_je_fahrer.get(spieler, 0),
            kilometer_je_wetter=wochenende.kilometer_je_fahrer.get(spieler),
            fahrer=spieler,
            liga=wochenende.liga,
            zaehle_rennwochenende=zaehlt,
        )

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

    def schliesse_ab(self) -> tuple[Wechsel, ...]:
        """Schreibt die Saison in die Historie und liefert die Wechsel (GDD 13)."""
        wechsel = self.auf_und_abstieg()
        if not any(a.saison == self.jahr for a in self.statistik.historie):
            self.statistik.schliesse_saison(self.jahr, self.tabellen)
        return wechsel

    def naechste_welt(self) -> Welt:
        """Die Welt der Folgesaison, mit vollzogenen Ligawechseln (GDD 13)."""
        return wende_wechsel_an(self.welt, self.schliesse_ab())

    def platzierungen(self) -> dict[int, int]:
        """Je Fahrer sein Platz in der abgelaufenen Saison (Punkt 35).

        Danach richtet sich, wer nachrueckt, wenn ein Platz frei wird: Wer
        seine Liga gewonnen hat, geht zuerst. Das koppelt den Aufstieg an
        die Ergebnisse und nicht an die blossen Werte.
        """
        return {
            eintrag.fahrer: platz
            for tabelle in self.tabellen.values()
            for platz, eintrag in enumerate(tabelle.stand(), start=1)
        }

    def generationswechsel(self, welt: Welt, jahr: int) -> Winterbericht:
        """Ruecktritte, Newgens und die Alterung der KI (Punkt 35).

        Laeuft **nach** dem Auf- und Abstieg: Der regelt, wer sich
        sportlich hoch- oder runtergefahren hat; hier geht es um die
        Plaetze, die niemand mehr besetzt.

        Ein Newgen erbt die Nummer des Zurueckgetretenen - die Welt haelt
        genau 600 Fahrer. Was an dieser Nummer hing, wird deshalb
        vergessen: Karrierezahlen, Bilanzen, Streckenkenntnis und
        Popularitaet. Die Historie bleibt; sie gehoert der Saison, nicht
        dem Nachfolger.
        """
        neue, bericht = kern_generationen.naechste_generation(
            self.konfiguration,
            welt,
            jahr,
            self.seedquelle,
            platzierungen=self.platzierungen(),
        )
        for nummer in bericht.newgens:
            self.statistik.vergiss_fahrer(nummer)
            self.kenntnis.vergiss_fahrer(nummer)
            self.popularitaet.vergiss_fahrer(nummer)
        if self.karriere is not None:
            self._uebergib_eigene_autos(neue, bericht)
        self._neue_welt = neue
        return bericht

    def _uebergib_eigene_autos(self, neue: Welt, bericht) -> None:
        """Ein eigener Fahrer hoert auf - sein Auto geht mit ihm.

        Der Auftraggeber hat entschieden: Jedes Auto gehoert seinem
        Fahrer, und ein neuer bringt ein **leeres, nicht upgegradetes**
        Auto mit. Wer in den eigenen Reihen aufhoert, nimmt also alles
        mit, was der Chef in sein Auto gesteckt hat.

        Die Fahrernummer bleibt dieselbe - der Newgen erbt sie -, das
        Auto dahinter nicht.
        """
        gegangen = set(bericht.zurueckgetreten)
        eigene_neue = {
            f.nummer for f in neue.fahrer if f.ist_spieler and f.nummer in bericht.newgens
        }
        for nummer in sorted(gegangen & set(self.karriere.autos)):
            nachfolger = nummer if nummer in eigene_neue else None
            self.karriere.fahrer_geht(nummer, nachfolger)
        # Ein Fahrer, der ueber einen Wechsel neu ins Team kam, bekommt
        # ebenfalls sein leeres Auto.
        for fahrer in neue.fahrer:
            if fahrer.ist_spieler and fahrer.nummer not in self.karriere.autos:
                self.karriere.autos[fahrer.nummer] = kern_karriere.leere_werte(
                    self.konfiguration
                )

    def transfermarkt(self) -> tuple[int, ...]:
        """Wer im kommenden Winter zu haben ist (Punkt 7).

        Frei sind alle, deren Vertrag mit dieser Saison auslaeuft; wer
        noch laeuft, kostet eine Abloese. Die Newgens des Jahrgangs kommen
        dazu, sobald der Generationswechsel vollzogen ist - vorher gibt es
        sie noch nicht.
        """
        return kern_transfer.verfuegbare(
            self.konfiguration,
            self.welt,
            self.jahr + 1,
            self.seedquelle,
            newgens=self.letzter_winter.newgens if self.letzter_winter else (),
        )

    def naechste_saison(self) -> Saisonlauf:
        """Der Saisonlauf des Folgejahres (GDD 13).

        Schliesst die laufende Saison ab, vollzieht Auf- und Abstieg und
        traegt die Karriere ins neue Jahr. Was die Saison ueberdauert,
        wandert unveraendert mit:

        * **Statistik** - Rundenrekorde, Karrierezahlen und die
          vollstaendige Historie aller bisherigen Saisons,
        * **Streckenkenntnis** aller 600 Fahrer (GDD 6),
        * die **Popularitaet** aller 600 Fahrer (Punkt 5),
        * aus der Karriere Konto, Werte, Sponsorenvertraege, offene
          Defekte und laufende Ereignisse (GDD 10 und 14).

        Neu sind Tabellen, Kalender und Ereignisplan. Es bleiben 600
        Fahrer, aber nicht dieselben: Wer ueber seinem Ruecktrittsalter
        ist, hoert auf, und ebenso viele Newgens steigen unten ein
        (Punkt 35). Was dabei geschah, steht in ``letzter_winter`` des
        **zurueckgegebenen** Laufs: Der Winter gehoert der Saison, die er
        eroeffnet, nicht der, die er beendet.
        """
        welt = self.naechste_welt()
        jahr = self.jahr + 1
        # Punkt 35: Erst danach treten die Alten ab und die Newgens ein.
        winter = self.generationswechsel(welt, jahr)
        welt = self._neue_welt
        if self.karriere is not None:
            # Die Liga des Fahrers, an dem die Karriere haengt - nicht die
            # des ersten Spielerfahrers. Seit dem Teamchef hat der Spieler
            # vier, und sie koennen in verschiedenen Ligen stehen.
            eigener = next(
                (f for f in welt.fahrer if f.nummer == self.karriere.fahrernummer),
                None,
            )
            self.karriere.naechste_saison(
                jahr,
                eigener.liga if eigener is not None else self.karriere.liga,
                self.seedquelle.zweig("karriere", jahr),
            )
        if self.karriere is not None:
            # Punkt 7: Die Jahresgehaelter laufen aus dem Konto, einmal je
            # Saisonwechsel. Ausgelaufene Vertraege verschwinden dabei.
            self.karriere.zahle_gehaelter()
        folge = Saisonlauf(
            self.konfiguration,
            welt,
            self.seedquelle,
            jahr,
            strecken=self.strecken,
            statistik=self.statistik,
            kenntnis=self.kenntnis,
            karriere=self.karriere,
            popularitaet=self.popularitaet,
        )
        folge.letzter_winter = winter
        return folge


# ---------------------------------------------------------------------------
# Das gefuehrte Rennwochenende (Punkt 12)
# ---------------------------------------------------------------------------
class WochenendFehler(SaisonFehler):
    """Die Etappen des Rennwochenendes sind in falscher Reihenfolge."""


class Wochenendlauf:
    """Ein Rennwochenende in Etappen, fuer die Oberflaeche (Punkt 12).

    ``Saisonlauf.fahre_rennen`` faehrt alle 20 Ligen am Stueck. Der
    Spieler soll sein Wochenende dagegen Schritt fuer Schritt erleben:
    erst das Qualifying, dann - auf dessen Aufstellung - das Rennen, und
    erst danach laufen die 19 anderen Ligen im Schnellmodus durch.

    Gefahren wird **dasselbe**: Die Seedzweige heissen nach ihrer Sache,
    nicht nach der Reihenfolge, und jede Liga bucht fuer sich. Ein Test
    haelt fest, dass gefuehrt und am Stueck bei gleichem Seed Zeichen fuer
    Zeichen dasselbe herauskommt.

    Zwischen Qualifying und Rennen haelt der Lauf an. Dort sitzt die
    Reifenwahl aus Punkt 39: ``strategiewahl`` zeigt, was zur Wahl steht,
    ``waehle_reifen`` legt sie fest. Beides geht nur **vor** dem Start -
    der Rennverlauf wird in einem Stueck gerechnet und danach nur noch
    abgespielt.
    """

    def __init__(self, lauf: Saisonlauf, liga: int) -> None:
        if liga not in lauf.tabellen:
            raise SaisonFehler(f"Liga {liga} gibt es nicht")
        nummer = lauf.naechstes_rennen
        if nummer is None:
            raise SaisonFehler(f"Die Saison {lauf.jahr} ist zu Ende")
        self.lauf = lauf
        self.liga = liga
        # Der Aufbau ist eine **Vorschau** und bewegt nichts: Strecke,
        # Rundenzahl und Renntag stehen fest, ohne dass der Kalender
        # vorschaltet oder ein Wuerfel faellt. Erst ``fahre_qualifying``
        # beginnt das Wochenende wirklich - sonst kostete schon das
        # Aufschlagen des Reiters die nutzbaren Tage bis zum Rennen
        # (GDD 2).
        self.nummer = nummer
        self.strecke = lauf.strecke_zu(nummer)
        self.runden = kern_rennen.rundenzahl(
            lauf.konfiguration, self.strecke, liga
        )
        self.rahmen: Wochenendrahmen | None = None
        self.daten: Ligadaten | None = None
        self.qualifying: Qualifying | None = None
        self.verlauf: Rennverlauf | None = None
        # Punkt 39: Was der Spieler fuer seine Fahrer gewaehlt hat, je
        # Fahrernummer. Wer nicht darin steht, faehrt, was die
        # Vorausberechnung ihm zuteilt.
        self.reifenwahl: dict[int, kern_strategie.Strategie] = {}
        self._vorbereitung: Rennvorbereitung | None = None
        self.wochenende: Wochenende | None = None

    # -- Was vor dem Fahren schon feststeht ---------------------------------

    @property
    def renntag(self) -> dt.date | None:
        return self.lauf.renntag(self.nummer)

    @property
    def ist_gefahren(self) -> bool:
        return self.wochenende is not None

    # -- Die Etappen --------------------------------------------------------
    def fahre_qualifying(self) -> Qualifying:
        """Erste Etappe: das Qualifying der Liga des Spielers (GDD 4).

        Hier beginnt das Wochenende: Der Kalender schaltet auf den Renntag
        vor (GDD 2), und die Werte des Feldes werden gezogen.
        """
        if self.qualifying is not None:
            return self.qualifying
        self.rahmen = self.lauf.beginne_wochenende(self.nummer)
        self.daten = self.lauf.ligadaten(self.rahmen, self.liga)
        self.qualifying = _fahre_qualifying(
            self.lauf.konfiguration,
            self.lauf.welt,
            self.liga,
            self.rahmen.strecke,
            self.daten.seedquelle,
            self.daten.meisterschaft,
            self.daten.kenntnis,
            self.daten.autos,
            self.daten.tagesform,
            self.daten.rhythmus,
        )
        return self.qualifying

    def strategiewahl(self) -> Rennvorbereitung:
        """Was vor dem Rennen zur Wahl steht (Punkt 39).

        Rechnet Wetter und Varianten vor, ohne das Rennen zu fahren.
        Beides haengt allein am Seed, also aendert der Blick darauf
        nichts am Ergebnis.
        """
        if self.qualifying is None:
            raise WochenendFehler(
                "Das Qualifying muss vor der Reifenwahl gefahren werden"
            )
        if self._vorbereitung is None:
            self._vorbereitung = vor_dem_rennen(
                self.lauf.konfiguration,
                startfeld(
                    self.lauf.konfiguration,
                    self.lauf.welt,
                    self.liga,
                    self.daten.autos,
                    self.qualifying,
                ),
                self.rahmen.strecke,
                self.daten.runden,
                self.daten.seedquelle,
                self.rahmen.verschleiss,
                self.qualifying,
                self.liga,
            )
        return self._vorbereitung

    def waehle_reifen(
        self, fahrernummer: int, strategie: kern_strategie.Strategie | None
    ) -> None:
        """Legt die Strategie eines eigenen Fahrers fest - oder gibt sie frei.

        ``None`` heisst: Das Team entscheidet, also die
        Vorausberechnung. Nach dem Start geht nichts mehr; der
        Rennverlauf wird in einem Stueck gerechnet und danach nur noch
        abgespielt.
        """
        if self.verlauf is not None:
            raise WochenendFehler(
                "Das Rennen laeuft schon - die Reifen stehen fest"
            )
        if strategie is None:
            self.reifenwahl.pop(fahrernummer, None)
            return
        kern_strategie.pruefe(
            self.lauf.konfiguration,
            strategie,
            self.daten.runden,
            nass=not self.strategiewahl().strategien.pflicht_zwei,
        )
        self.reifenwahl[fahrernummer] = strategie

    def fahre_rennen(self, fortschritt=None) -> Rennverlauf:
        """Zweite Etappe: das Rennen auf die gefahrene Aufstellung.

        Gebucht wird hier noch nichts - erst ``schliesse_ab`` traegt ein,
        damit ein abgebrochenes Wochenende die Saison nicht halb bewegt.

        :param fortschritt: wird je gefahrener Runde des Fuehrenden mit
            ``(Runde, Runden)`` gerufen (E10). Die Oberflaeche rechnet
            damit im Hintergrund und zeigt, wie weit sie ist.
        """
        if self.qualifying is None:
            raise WochenendFehler(
                "Das Qualifying muss vor dem Rennen gefahren werden (GDD 4)"
            )
        if self.verlauf is not None:
            return self.verlauf
        self._eigenes, self.verlauf = _fahre_rennen(
            self.lauf.konfiguration,
            self.lauf.welt,
            self.liga,
            self.daten.fahrer,
            self.rahmen.strecke,
            self.daten.runden,
            self.daten.seedquelle,
            self.lauf.streckenmittel,
            self.rahmen.verschleiss,
            self.daten.kenntnis,
            self.daten.autos,
            self.daten.tagesform,
            self.daten.rhythmus,
            self.qualifying,
            wahl=dict(self.reifenwahl),
            fortschritt=fortschritt,
        )
        return self.verlauf

    def schliesse_ab(self) -> Wochenende:
        """Dritte Etappe: die 19 anderen Ligen, dann alles verbuchen.

        Die Liga des Spielers wird zuerst gebucht, die uebrigen danach in
        aufsteigender Reihenfolge. Das darf sie, weil jede Liga ihren
        eigenen Seedzweig hat und fuer sich bucht.
        """
        if self.verlauf is None:
            raise WochenendFehler("Das Rennen muss vor dem Abschluss gefahren werden")
        if self.wochenende is not None:
            return self.wochenende

        ligen: dict[int, Ligawochenende] = {self.liga: self._eigenes}
        self.lauf.verbuche_liga(self.rahmen, self.daten, self._eigenes)
        for liga in sorted(self.lauf.tabellen):
            if liga == self.liga:
                continue
            daten = self.lauf.ligadaten(self.rahmen, liga)
            ligen[liga], _, _ = self.lauf._fahre_liga(self.rahmen, daten, False)
            self.lauf.verbuche_liga(self.rahmen, daten, ligen[liga])

        self.wochenende = self.lauf.schliesse_wochenende_ab(
            Wochenende(
                nummer=self.rahmen.nummer,
                strecke=self.rahmen.strecke.name,
                ligen={liga: ligen[liga] for liga in sorted(ligen)},
                verlauf=self.verlauf,
                qualifying=self.qualifying,
                ausfuehrliche_liga=self.liga,
            )
        )
        return self.wochenende


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
