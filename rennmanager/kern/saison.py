"""Saisonlauf: 20 Rennwochenenden und die Meisterschaft (GDD 13, Punkt 101).

Ein Saisonlauf haelt die Tabelle des Feldes und faehrt Wochenende fuer
Wochenende. Ueblich laeuft ein Rennen ausfuehrlich ueber
``rennmanager.kern.rennen`` - mit Qualifying, sichtbarem Rennverlauf und
Zeitraffer -; wer es ueberspringen will, laesst es im Schnellmodus aus
``rennmanager.kern.schnellsimulation`` durchlaufen.

``naechste_saison()`` macht daraus den Saisonwechsel: Statistik,
Streckenkenntnis und der Kalender des Spielers wandern mit, Tabelle und
Kalender beginnen neu. Die Karriere ist damit endlos - und weil seit
Punkt 101 niemand mehr altert, sich entwickelt oder das Team wechselt,
faehrt jede Saison dasselbe Feld.

Alle Wuerfe haengen am Hauptseed: Der Zweig eines Rennens heisst
``saison/<jahr>/rennen/<nummer>``. Dieselbe Saison mit demselben Seed
laeuft deshalb genau gleich ab, gleich ob ausfuehrlich oder schnell
gefahren wird (GDD 15).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

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
from rennmanager.kern import welt as kern_welt
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.qualifying import Qualifying
from rennmanager.kern.rennen import Rennverlauf
from rennmanager.kern.schnellsimulation import fahre_wochenende as fahre_schnell
from rennmanager.kern.statistik import Statistik
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.streckenkenntnis import Streckenkenntnis
from rennmanager.kern.welt import Fahrer, Welt
from rennmanager.kern.wertung import Rennergebnis, Tabelle
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class SaisonFehler(Exception):
    """Der Saisonlauf laesst sich so nicht fortsetzen."""


@dataclass(frozen=True)
class Wochenendrahmen:
    """Was an einem Rennwochenende unabhaengig vom Feld feststeht."""

    nummer: int
    strecke: Strecke
    verschleiss: float
    seedquelle: Seedquelle


@dataclass(frozen=True)
class Felddaten:
    """Was das Feld an einem Rennwochenende mitbringt.

    Einmal gezogen, von Qualifying und Rennen gemeinsam benutzt: Der
    Heimbonus aus Punkt 2 wird je Wochenende **einmal** gewuerfelt, und
    die Streckenkenntnis gilt fuer beide Sessions (GDD 6).
    """

    fahrer: tuple[Fahrer, ...]
    runden: int
    seedquelle: Seedquelle
    kenntnis: tuple[float, ...]
    autos: dict[int, object]
    rhythmus: tuple[float, ...]
    meisterschaft: tuple[int, ...] | None

    @property
    def nummern(self) -> tuple[int, ...]:
        return tuple(f.nummer for f in self.fahrer)


@dataclass(frozen=True)
class Wochenende:
    """Ein komplettes Rennwochenende (GDD 13).

    ``ergebnisse`` nennt Fahrer mit ihrer weltweiten Nummer, nicht mit dem
    Platz im Starterfeld - nur so passen die Zeilen zur Tabelle.

    ``ueberholmanoever`` zaehlt Positionsgewinne je Runde, in beiden
    Rennmodellen gleich. Die volle Simulation kennt daneben jeden
    einzelnen Vorbeigang; der steht in ``Rennverlauf.manoever`` und ist
    fuer die Anzeige des Rennens da, nicht fuer die Wertung.
    """

    nummer: int
    strecke: str
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
    # Nur beim ausfuehrlich gefahrenen Rennen gefuellt; die Oberflaeche
    # spielt daraus den Rennverlauf ab (GDD 15).
    verlauf: Rennverlauf | None = None
    qualifying: Qualifying | None = None
    # Je Fahrer, mit weltweiter Nummer: gelungene Ueberholmanoever und die
    # im Rennen aufgetretenen Defekte.
    manoever_je_fahrer: dict[int, int] = field(default_factory=dict)
    defekte_je_fahrer: dict[int, tuple[str, ...]] = field(default_factory=dict)

    @property
    def sieger(self) -> int:
        return self.ergebnisse[0].fahrer

    def ergebnis_von(self, fahrer: int) -> Rennergebnis | None:
        return next((e for e in self.ergebnisse if e.fahrer == fahrer), None)


# ---------------------------------------------------------------------------
# Ein Rennwochenende
# ---------------------------------------------------------------------------
def _fahre_qualifying(
    konfiguration: Konfiguration,
    welt: Welt,
    strecke: Strecke,
    seedquelle: Seedquelle,
    meisterschaft: tuple[int, ...] | None,
    kenntnisfaktor: tuple[float, ...],
    autos: dict[int, object],
    rhythmusfaktor: tuple[float, ...],
) -> Qualifying:
    """Das Qualifying (GDD 4).

    Eigene Funktion, weil das gefuehrte Rennwochenende dazwischen anhaelt
    (Punkt 12): Der Spieler sieht erst sein Qualifying, dann sein Rennen.
    Der Seedzweig heisst ``qualifying`` und haengt nicht an der
    Aufrufreihenfolge - derselbe Seed ergibt dasselbe Qualifying, ob am
    Stueck gefahren oder in zwei Etappen.
    """
    feld = kern_welt.starterfeld(welt, autos=autos)
    return kern_qualifying.fahre(
        konfiguration,
        strecke,
        feld,
        seedquelle.zweig("qualifying"),
        meisterschaft,
        kenntnisfaktor=kenntnisfaktor,
        rhythmusfaktor=rhythmusfaktor,
    )


@dataclass(frozen=True)
class Rennvorbereitung:
    """Was vor dem Start feststeht: Wetter und zulaessige Strategien.

    Punkt 39: Der Spieler soll die Reifen seiner Fahrer selbst
    waehlen duerfen. Dafuer muss er sehen koennen, was ueberhaupt zur
    Wahl steht - und das steht vor dem Rennen fest, nicht erst danach.
    """

    wetter: kern_wetter.Wetterverlauf
    strategien: kern_strategie.Rennstrategien
    teilnehmer: tuple[kern_rennen.Teilnehmer, ...]


def startfeld(
    konfiguration: Konfiguration,
    welt: Welt,
    autos: dict[int, object],
    quali: Qualifying,
) -> tuple[kern_rennen.Teilnehmer, ...]:
    """Das Feld in der Startaufstellung des Qualifyings; Platz 1 ist die Pole."""
    del konfiguration  # die Aufstellung steht fest, sie braucht keinen Wert
    rennfeld = kern_welt.starterfeld(welt, autos=autos)
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
    nummer: int,
    fahrer: tuple[Fahrer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float,
    kenntnisfaktor: tuple[float, ...],
    autos: dict[int, object],
    rhythmusfaktor: tuple[float, ...],
    quali: Qualifying,
    wahl: dict[int, kern_strategie.Strategie] | None = None,
    fortschritt=None,
) -> tuple[Wochenende, Rennverlauf]:
    """Das Rennen auf ein gefahrenes Qualifying (GDD 4).

    Die *Reihenfolge* des Feldes richtet sich nach der Welt, sonst
    passten die Indizes aus dem Qualifying nicht mehr aufs Rennen.

    :param wahl: je Fahrernummer eine vom Spieler gewaehlte Strategie
        (Punkt 39). Wer nicht darin steht, faehrt, was die
        Vorausberechnung ihm zuteilt.
    :param fortschritt: wird je gefahrener Runde des Fuehrenden gerufen
        (E10), damit die Oberflaeche waehrend der Rechnung etwas zeigen
        kann.
    """
    gestartet = startfeld(konfiguration, welt, autos, quali)
    vorbereitung = vor_dem_rennen(
        konfiguration, gestartet, strecke, runden, seedquelle,
        streckenverschleiss, quali,
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
        # Die Startaufstellung ordnet das Feld um; Kenntnisfaktor und
        # Rhythmus muessen mitwandern, sonst faehrt jeder mit den Werten
        # eines anderen.
        kenntnisfaktor=tuple(kenntnisfaktor[i] for i in quali.aufstellung),
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
    # Was je Fahrer anfaellt (GDD 14). Die Indizes zaehlen in der
    # Startaufstellung, deshalb geht es ueber ``quali.aufstellung`` zurueck
    # auf die weltweite Fahrernummer.
    def nummer_von(stelle: int) -> int:
        return fahrer[quali.aufstellung[stelle]].nummer

    # Gezaehlt werden die Positionsgewinne je Runde, nicht die rohen
    # Vorbeigaenge: Ein Duell, das innerhalb einer Runde hin und her geht,
    # ist kein Dutzend Ueberholmanoever. Nur so ist die Erfahrung aus
    # GDD 10 mit der des Schnellmodus vergleichbar - gemessen lagen die
    # rohen Vorbeigaenge um den Faktor 3,2 darueber; die Zahl steht in
    # der Statistik.
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

    wochenende = Wochenende(
        nummer=nummer,
        strecke=strecke.name,
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
        verlauf=verlauf,
        qualifying=quali,
        manoever_je_fahrer=manoever_je_fahrer,
        defekte_je_fahrer=defekte_je_fahrer,
    )
    return wochenende, verlauf


def _ausfuehrlich(
    konfiguration: Konfiguration,
    welt: Welt,
    nummer: int,
    fahrer: tuple[Fahrer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float,
    meisterschaft: tuple[int, ...] | None,
    kenntnisfaktor: tuple[float, ...],
    autos: dict[int, object],
    rhythmusfaktor: tuple[float, ...],
) -> tuple[Wochenende, Rennverlauf, Qualifying]:
    """Qualifying und Rennen am Stueck (GDD 4).

    Der Weg fuer die Saison, die ein Wochenende in einem Zug faehrt. Das
    gefuehrte Rennwochenende ruft stattdessen die beiden Etappen einzeln
    auf und haelt dazwischen an (Punkt 12) - herauskommen muss dasselbe.
    """
    quali = _fahre_qualifying(
        konfiguration,
        welt,
        strecke,
        seedquelle,
        meisterschaft,
        kenntnisfaktor,
        autos,
        rhythmusfaktor,
    )
    wochenende, verlauf = _fahre_rennen(
        konfiguration,
        welt,
        nummer,
        fahrer,
        strecke,
        runden,
        seedquelle,
        streckenmittel,
        streckenverschleiss,
        kenntnisfaktor,
        autos,
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
):
    """Die Strategien des Feldes im Schnellmodus (Punkt 39).

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
        seedquelle.zweig("strategie"),
    ).je_auto


def _schnell(
    konfiguration: Konfiguration,
    welt: Welt,
    nummer: int,
    fahrer: tuple[Fahrer, ...],
    strecke: Strecke,
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float,
    kenntnisfaktor: tuple[float, ...],
    autos: dict[int, object],
    rhythmusfaktor: tuple[float, ...],
) -> Wochenende:
    """Ein Rennwochenende auf Rundenebene (GDD 13).

    Anders als die volle Simulation bekommt der Schnellmodus keinen
    Meisterschaftsstand: Dort faehrt jedes Auto seine gezeitete Runde in
    der Lage zu Sessionbeginn, die Reihenfolge der Starts aendert am
    Ergebnis also nichts.
    """
    feld = kern_welt.starterfeld(welt, autos=autos)
    # Punkt 39: Der Schnellmodus faehrt dieselben Strategien wie die volle
    # Simulation - nur das Wetter kennt er erst dort. Deshalb wird es hier
    # aus demselben Zweig gewuerfelt wie drinnen.
    ergebnis = fahre_schnell(
        konfiguration,
        strecke,
        feld,
        runden,
        seedquelle,
        streckenmittel,
        streckenverschleiss,
        kenntnisfaktor=kenntnisfaktor,
        rhythmusfaktor=rhythmusfaktor,
        strategien=_schnellstrategien(
            konfiguration, feld, strecke, runden, streckenverschleiss, seedquelle
        ),
    )
    return Wochenende(
        nummer=nummer,
        strecke=strecke.name,
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
        # weltweite Fahrernummer (GDD 14).
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
    )


# ---------------------------------------------------------------------------
# Der Saisonlauf
# ---------------------------------------------------------------------------
class Saisonlauf:
    """Faehrt eine ganze Saison und fuehrt die Tabelle des Feldes."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        seedquelle: Seedquelle,
        jahr: int | None = None,
        strecken: tuple[Strecke, ...] | None = None,
        statistik: Statistik | None = None,
        kenntnis: Streckenkenntnis | None = None,
        tabelle: Tabelle | None = None,
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
        self.kenntnis = kenntnis or kern_streckenkenntnis.Streckenkenntnis(konfiguration)
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

        self.tabelle = tabelle if tabelle is not None else Tabelle()
        self.wochenenden: list[Wochenende] = []
        # Rennen, die vor dem Laden eines Spielstands schon gefahren waren
        # (GDD 15). Ihre Wochenenden liegen nicht mehr vor, ihre Punkte
        # stehen aber in der Tabelle.
        self.vorgefahren = vorgefahren
        # Die Karriere haelt den Kalender des Spielers (GDD 2) und die
        # Streckenkenntnis. Ohne sie laeuft die Saison ohne Datumsangaben.
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

    def rhythmusfaktoren(
        self, strecke: Strecke, feld: tuple[Fahrer, ...], autos: dict[int, object]
    ) -> tuple[float, ...]:
        """Faktor auf die Querbeschleunigung je Feldplatz (Punkt 15).

        Gerechnet wird mit dem Auto, das wirklich faehrt - mit Heimbonus
        also mit dem aufgewerteten.
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
        strecke: Strecke,
        fahrer: tuple[Fahrer, ...],
        seedquelle: Seedquelle,
    ) -> dict[int, object]:
        """Die Autos, mit denen dieses Feld faehrt.

        Eines tritt an die Stelle des Autos aus der Welt: der Heimbonus
        aus Punkt 2. Seine fuenf Eigenschaften werden je Rennwochenende
        einmal gezogen und gelten fuer Qualifying und Rennen.
        """
        daheim = kern_heimstrecke.heimfahrer(fahrer, strecke)
        if not daheim:
            return {}
        heimseed = seedquelle.zweig("heimstrecke")
        return {
            f.nummer: kern_heimstrecke.mit_bonus(
                self.konfiguration, f.auto, heimseed.zweig("fahrer", f.nummer)
            )
            for f in daheim
        }

    def meisterschaft(self, feld: tuple[Fahrer, ...]) -> tuple[int, ...] | None:
        """Meisterschaftsstand als Feldindizes, Erster zuerst (GDD 4).

        Das Qualifying braucht ihn fuer die Startreihenfolge. Vor dem
        ersten Rennen gibt es ihn nicht; dann faehrt das Feld aufsteigend
        nach Qualifying-Faehigkeit.
        """
        if not self.tabelle.eintraege:
            return None
        stelle = {f.nummer: i for i, f in enumerate(feld)}
        geordnet = [stelle[e.fahrer] for e in self.tabelle.stand() if e.fahrer in stelle]
        if len(geordnet) != len(feld):  # pragma: no cover - das Feld ist fest
            return None
        return tuple(geordnet)

    # -- Fahren ------------------------------------------------------------
    def beginne_wochenende(self, nummer: int | None = None) -> Wochenendrahmen:
        """Ruestet das naechste Rennwochenende zu und startet den Renntag.

        Der Kalender der Karriere wird dabei auf den Renntag vorgeschaltet
        (GDD 2).

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

    def felddaten(self, rahmen: Wochenendrahmen) -> Felddaten:
        """Alles, was das Feld an diesem Wochenende mitbringt.

        Qualifying und Rennen brauchen dasselbe; das gefuehrte Wochenende
        haelt dazwischen an (Punkt 12) und darf es nicht zweimal ziehen -
        der Heimbonus etwa wird je Wochenende **einmal** gewuerfelt.
        """
        fahrer = self.welt.feld
        seed = rahmen.seedquelle.zweig("feld")
        autos = self.sessionautos(rahmen.strecke, fahrer, seed)
        return Felddaten(
            fahrer=fahrer,
            runden=kern_rennen.rundenzahl(self.konfiguration, rahmen.strecke),
            seedquelle=seed,
            kenntnis=self.kenntnis.tempofaktoren(
                tuple(f.nummer for f in fahrer), rahmen.strecke.name
            ),
            autos=autos,
            rhythmus=self.rhythmusfaktoren(rahmen.strecke, fahrer, autos),
            meisterschaft=self.meisterschaft(fahrer),
        )

    def _fahre_feld(
        self, rahmen: Wochenendrahmen, daten: Felddaten, ausfuehrlich: bool
    ) -> Wochenende:
        """Das Wochenende, voll simuliert oder im Schnellmodus."""
        if ausfuehrlich:
            wochenende, _verlauf, _quali = _ausfuehrlich(
                self.konfiguration,
                self.welt,
                rahmen.nummer,
                daten.fahrer,
                rahmen.strecke,
                daten.runden,
                daten.seedquelle,
                self.streckenmittel,
                rahmen.verschleiss,
                daten.meisterschaft,
                daten.kenntnis,
                daten.autos,
                daten.rhythmus,
            )
            return wochenende
        return _schnell(
            self.konfiguration,
            self.welt,
            rahmen.nummer,
            daten.fahrer,
            rahmen.strecke,
            daten.runden,
            daten.seedquelle,
            self.streckenmittel,
            rahmen.verschleiss,
            daten.kenntnis,
            daten.autos,
            daten.rhythmus,
        )

    def verbuche(self, rahmen: Wochenendrahmen, ergebnis: Wochenende) -> None:
        """Traegt ein gefahrenes Wochenende in Tabelle und Statistik ein."""
        self.tabelle.verbuche(self.konfiguration, ergebnis.ergebnisse)
        # Siege, Podien und Poles machen bekannt (Punkt 5).
        self.popularitaet.verbuche_wochenende(ergebnis.ergebnisse)
        self.statistik.verbuche_wochenende(
            saison=self.jahr,
            rennen=rahmen.nummer,
            strecke=rahmen.strecke.name,
            ergebnisse=ergebnis.ergebnisse,
            schnellste_runde_ms=ergebnis.schnellste_runde_ms,
            wetter=ergebnis.vorherrschendes_wetter,
            quali_ms=ergebnis.polezeit_ms,
            quali_fahrer=ergebnis.polefahrer or None,
        )

    def schliesse_wochenende_ab(self, ergebnis: Wochenende) -> Wochenende:
        """Haengt das gefahrene Wochenende an und beendet den Renntag."""
        self.wochenenden.append(ergebnis)
        # Der Renntag ist vorbei; der naechste Tag gehoert schon wieder
        # dem Kalender (GDD 2).
        self._schliesse_renntag_ab()
        return ergebnis

    def fahre_rennen(self, ausfuehrlich: bool = False) -> Wochenende:
        """Faehrt das naechste Rennwochenende (GDD 13).

        :param ausfuehrlich: voll simulieren statt im Schnellmodus
        """
        rahmen = self.beginne_wochenende()
        daten = self.felddaten(rahmen)
        ergebnis = self._fahre_feld(rahmen, daten, ausfuehrlich)
        self.verbuche(rahmen, ergebnis)
        return self.schliesse_wochenende_ab(ergebnis)

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
        """Nutzbare Tage, die bis zum naechsten Renntag noch frei sind."""
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

        Es gibt nur *eine* im Spiel - sie haelt alle 50 Fahrer. Der
        Spielstand verbindet beide beim Laden auf dieselbe Weise (GDD 15).
        """
        if self.karriere is not None and self.karriere.kenntnis is not self.kenntnis:
            self.karriere.kenntnis = self.kenntnis

    def fahre_saison(self, ausfuehrlich: bool = False) -> tuple[Wochenende, ...]:
        """Faehrt alle noch offenen Rennwochenenden der Saison."""
        while not self.ist_fertig:
            self.fahre_rennen(ausfuehrlich)
        return tuple(self.wochenenden)

    # -- Saisonende --------------------------------------------------------
    def schliesse_ab(self) -> None:
        """Schreibt die Saison in die Historie (GDD 13)."""
        if not self.ist_fertig:
            raise SaisonFehler(
                f"Erst nach Rennen {self.rennen_je_saison} ist die Saison zu Ende; "
                f"gefahren sind {self.gefahren}"
            )
        if not any(a.saison == self.jahr for a in self.statistik.historie):
            self.statistik.schliesse_saison(self.jahr, self.tabelle)

    def naechste_saison(self) -> Saisonlauf:
        """Der Saisonlauf des Folgejahres (GDD 13).

        Was die Saison ueberdauert, wandert unveraendert mit:

        * **Statistik** - Rundenrekorde, Karrierezahlen und die
          vollstaendige Historie aller bisherigen Saisons,
        * **Streckenkenntnis** aller 50 Fahrer (GDD 6),
        * die **Popularitaet** aller 50 Fahrer (Punkt 5).

        Neu sind Tabelle und Kalender. Das Feld bleibt dasselbe: Seit
        Punkt 101 altert niemand, entwickelt sich niemand und wechselt
        niemand das Team.
        """
        self.schliesse_ab()
        jahr = self.jahr + 1
        if self.karriere is not None:
            self.karriere.naechste_saison(jahr)
        return Saisonlauf(
            self.konfiguration,
            self.welt,
            self.seedquelle,
            jahr,
            strecken=self.strecken,
            statistik=self.statistik,
            kenntnis=self.kenntnis,
            karriere=self.karriere,
            popularitaet=self.popularitaet,
        )


# ---------------------------------------------------------------------------
# Das gefuehrte Rennwochenende (Punkt 12)
# ---------------------------------------------------------------------------
class WochenendFehler(SaisonFehler):
    """Die Etappen des Rennwochenendes sind in falscher Reihenfolge."""


class Wochenendlauf:
    """Ein Rennwochenende in Etappen, fuer die Oberflaeche (Punkt 12).

    ``Saisonlauf.fahre_rennen`` faehrt das Wochenende am Stueck. Der
    Spieler soll es dagegen Schritt fuer Schritt erleben: erst das
    Qualifying, dann - auf dessen Aufstellung - das Rennen.

    Gefahren wird **dasselbe**: Die Seedzweige heissen nach ihrer Sache,
    nicht nach der Reihenfolge. Ein Test haelt fest, dass gefuehrt und am
    Stueck bei gleichem Seed Zeichen fuer Zeichen dasselbe herauskommt.

    Zwischen Qualifying und Rennen haelt der Lauf an. Dort sitzt die
    Reifenwahl aus Punkt 39: ``strategiewahl`` zeigt, was zur Wahl steht,
    ``waehle_reifen`` legt sie fest. Beides geht nur **vor** dem Start -
    der Rennverlauf wird in einem Stueck gerechnet und danach nur noch
    abgespielt.
    """

    def __init__(self, lauf: Saisonlauf) -> None:
        nummer = lauf.naechstes_rennen
        if nummer is None:
            raise SaisonFehler(f"Die Saison {lauf.jahr} ist zu Ende")
        self.lauf = lauf
        # Der Aufbau ist eine **Vorschau** und bewegt nichts: Strecke,
        # Rundenzahl und Renntag stehen fest, ohne dass der Kalender
        # vorschaltet oder ein Wuerfel faellt. Erst ``fahre_qualifying``
        # beginnt das Wochenende wirklich - sonst kostete schon das
        # Aufschlagen des Reiters die nutzbaren Tage bis zum Rennen
        # (GDD 2).
        self.nummer = nummer
        self.strecke = lauf.strecke_zu(nummer)
        self.runden = kern_rennen.rundenzahl(lauf.konfiguration, self.strecke)
        self.rahmen: Wochenendrahmen | None = None
        self.daten: Felddaten | None = None
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
    def welt(self) -> Welt:
        return self.lauf.welt

    @property
    def renntag(self) -> dt.date | None:
        return self.lauf.renntag(self.nummer)

    @property
    def ist_gefahren(self) -> bool:
        return self.wochenende is not None

    # -- Die Etappen --------------------------------------------------------
    def fahre_qualifying(self) -> Qualifying:
        """Erste Etappe: das Qualifying (GDD 4).

        Hier beginnt das Wochenende: Der Kalender schaltet auf den Renntag
        vor (GDD 2), und die Werte des Feldes werden gezogen.
        """
        if self.qualifying is not None:
            return self.qualifying
        self.rahmen = self.lauf.beginne_wochenende(self.nummer)
        self.daten = self.lauf.felddaten(self.rahmen)
        self.qualifying = _fahre_qualifying(
            self.lauf.konfiguration,
            self.lauf.welt,
            self.rahmen.strecke,
            self.daten.seedquelle,
            self.daten.meisterschaft,
            self.daten.kenntnis,
            self.daten.autos,
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
                    self.daten.autos,
                    self.qualifying,
                ),
                self.rahmen.strecke,
                self.daten.runden,
                self.daten.seedquelle,
                self.rahmen.verschleiss,
                self.qualifying,
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
        self._ergebnis, self.verlauf = _fahre_rennen(
            self.lauf.konfiguration,
            self.lauf.welt,
            self.rahmen.nummer,
            self.daten.fahrer,
            self.rahmen.strecke,
            self.daten.runden,
            self.daten.seedquelle,
            self.lauf.streckenmittel,
            self.rahmen.verschleiss,
            self.daten.kenntnis,
            self.daten.autos,
            self.daten.rhythmus,
            self.qualifying,
            wahl=dict(self.reifenwahl),
            fortschritt=fortschritt,
        )
        return self.verlauf

    def schliesse_ab(self) -> Wochenende:
        """Dritte Etappe: alles verbuchen."""
        if self.verlauf is None:
            raise WochenendFehler("Das Rennen muss vor dem Abschluss gefahren werden")
        if self.wochenende is not None:
            return self.wochenende
        self.lauf.verbuche(self.rahmen, self._ergebnis)
        self.wochenende = self.lauf.schliesse_wochenende_ab(self._ergebnis)
        return self.wochenende
