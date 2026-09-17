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

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import qualifying as kern_qualifying
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import statistik as kern_statistik
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import welt as kern_welt
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern import zwischenfall as kern_zwischenfall
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
) -> tuple[Ligawochenende, Rennverlauf, Qualifying]:
    """Qualifying und Rennen einer Liga in voller Aufloesung (GDD 4).

    Qualifying und Rennen bekommen ein eigenes Feld: Die entwickelten
    Werte des Spielers koennen sich zwischen beiden unterscheiden, weil
    E12 aus GDD 14 nur im Qualifying wirkt. Die *Reihenfolge* des Feldes
    richtet sich in beiden Faellen nach der Welt, sonst passten die
    Indizes aus dem Qualifying nicht mehr aufs Rennen.
    """
    feld = kern_welt.starterfeld(
        welt, liga, autos=spielerautos.get(kern_ereignis.QUALIFYING)
    )
    quali = kern_qualifying.fahre(
        konfiguration,
        strecke,
        feld,
        seedquelle.zweig("qualifying"),
        meisterschaft,
        kenntnisfaktor=kenntnisfaktor,
        tagesformbonus=tagesformbonus,
    )
    # Die Startaufstellung kommt aus dem Qualifying; Platz 1 ist die Pole.
    rennfeld = kern_welt.starterfeld(
        welt, liga, autos=spielerautos.get(kern_ereignis.RENNEN)
    )
    gestartet = tuple(
        kern_rennen.Teilnehmer(
            auto=rennfeld[i].auto,
            startplatz=platz,
            farbe=rennfeld[i].farbe,
            ist_spieler=rennfeld[i].ist_spieler,
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
        # Die Startaufstellung ordnet das Feld um; Kenntnisfaktor und
        # Tagesformbonus muessen mitwandern, sonst faehrt jeder mit den
        # Werten eines anderen.
        kenntnisfaktor=tuple(kenntnisfaktor[i] for i in quali.aufstellung),
        tagesformbonus=tuple(tagesformbonus[i] for i in quali.aufstellung),
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

    manoever_je_fahrer: dict[int, int] = {}
    for m in verlauf.manoever:
        schluessel = nummer_von(m.angreifer)
        manoever_je_fahrer[schluessel] = manoever_je_fahrer.get(schluessel, 0) + 1

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
        siegerzeit_ms=verlauf.ergebnisse[0].zeit_ms or 0,
        schnellste_runde_ms=schnellste_ms,
        ueberholmanoever=len(verlauf.manoever),
        ausfaelle=sum(1 for e in verlauf.ergebnisse if e.zeit_ms is None),
        ausfuehrlich=True,
        manoever_je_fahrer=manoever_je_fahrer,
        defekte_je_fahrer=defekte_je_fahrer,
        kilometer_je_fahrer=kilometer_je_fahrer,
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
    kenntnisfaktor: tuple[float, ...],
    spielerautos: dict[str, dict[int, object]],
    tagesformbonus: tuple[float, ...],
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
        jahr: int = 2026,
        strecken: tuple[Strecke, ...] | None = None,
        statistik: Statistik | None = None,
        kenntnis: Streckenkenntnis | None = None,
        tabellen: dict[int, Tabelle] | None = None,
        vorgefahren: int = 0,
        karriere=None,
    ) -> None:
        self.konfiguration = konfiguration
        self.welt = welt
        self.jahr = jahr
        self.seedquelle = seedquelle
        self.strecken = strecken or kern_strecke.lade_alle(konfiguration)
        # Statistik und Streckenkenntnis ueberdauern die Saison (GDD 6 und
        # 13); ein Saisonlauf fuehrt sie nur fort.
        self.statistik = statistik or kern_statistik.Statistik(konfiguration)
        self.kenntnis = kenntnis or kern_streckenkenntnis.Streckenkenntnis(
            konfiguration, seedquelle=seedquelle.zweig("lerntempo")
        )

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

        self.tabellen: dict[int, Tabelle] = tabellen or {
            liga: Tabelle(liga) for liga in range(1, konfiguration.wert("ligen", "anzahl") + 1)
        }
        self.wochenenden: list[Wochenende] = []
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
        if self.karriere is None or self.karriere.liga != liga:
            return {}
        nummer = self.karriere.fahrernummer
        vorlage = self.welt.fahrer[nummer].auto
        return {
            sitzung: {nummer: self.karriere.rennauto(vorlage, sitzung)}
            for sitzung in (kern_ereignis.QUALIFYING, kern_ereignis.RENNEN)
        }

    def tagesformbonus(self, liga: int, feld: tuple[Fahrer, ...]) -> tuple[float, ...]:
        """Zuschlag auf den Tagesform-Mittelwert je Feldplatz (GDD 14).

        Nur E3 Motivationsschub hebt ihn, und nur beim Spieler: Die KI hat
        keine Ereignisse (GDD 12).
        """
        ohne = (0.0,) * len(feld)
        if self.karriere is None or self.karriere.liga != liga:
            return ohne
        bonus = self.karriere.tagesformbonus()
        if not bonus:
            return ohne
        return tuple(
            bonus if f.nummer == self.karriere.fahrernummer else 0.0 for f in feld
        )

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

        # Eine Karriere kann auch nach dem Aufbau gesetzt worden sein.
        self._teile_kenntnis()
        # GDD 2: Das Rennen findet an seinem Renntag statt. Der Kalender
        # der Karriere wird deshalb bis dorthin vorgeschaltet - vor dem
        # Rennen, damit die Ereignisse dieser Tage noch auf es wirken.
        self._stelle_auf_renntag(nummer)
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
            nummern = tuple(f.nummer for f in fahrer)
            runden = kern_rennen.rundenzahl(self.konfiguration, strecke, liga)
            seed = wochenende.zweig("liga", liga)
            kenntnis = self.kenntnis.tempofaktoren(nummern, strecke.name)
            tagesform = self.tagesformbonus(liga, fahrer)
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
                    kenntnis,
                    self.spielerautos(liga),
                    tagesform,
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
                    kenntnis,
                    self.spielerautos(liga),
                    tagesform,
                )
            self.tabellen[liga].verbuche(self.konfiguration, ligen[liga].ergebnisse)
            self.statistik.verbuche_wochenende(
                saison=self.jahr,
                rennen=nummer,
                liga=liga,
                strecke=strecke.name,
                ergebnisse=ligen[liga].ergebnisse,
                schnellste_runde_ms=ligen[liga].schnellste_runde_ms,
            )
            # Qualifying und Rennen zaehlen beide fuer die Kenntnis (GDD 6).
            quali_runden = self.konfiguration.wert(
                "qualifying", "aufwaermrunden"
            ) + self.konfiguration.wert("qualifying", "gezeitete_runden")
            gefahrene = runden + quali_runden
            kenntnisseed = seed.zweig("kenntnis")
            spieler = self._spielernummer(liga)
            # Der Spieler bucht ueber die Karriere, weil E10 Testfahrt
            # geglueckt seinen Zuwachs hebt (GDD 14). Sein Seedzweig ist
            # derselbe wie im Feld, damit derselbe Seed dieselbe Saison
            # ergibt (GDD 15).
            self.kenntnis.verbuche_feld(
                tuple(n for n in nummern if n != spieler),
                strecke.name,
                gefahrene,
                kenntnisseed,
            )
            if spieler is not None:
                self.karriere.verbuche_runden(
                    strecke.name, gefahrene, kenntnisseed.zweig("fahrer", spieler)
                )
                self._verbuche_karriere(ligen[liga], spieler)

        ergebnis = Wochenende(
            nummer=nummer,
            strecke=strecke.name,
            ligen=ligen,
            verlauf=verlauf,
            qualifying=quali,
            ausfuehrliche_liga=ausfuehrliche_liga,
        )
        self.wochenenden.append(ergebnis)
        # Der Renntag ist vorbei; der naechste Tag gehoert schon wieder
        # der Planung (GDD 2).
        self._schliesse_renntag_ab()
        return ergebnis

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

    def _spielernummer(self, liga: int) -> int | None:
        """Die Fahrernummer des Spielers, wenn er in dieser Liga faehrt."""
        if self.karriere is None or self.karriere.liga != liga:
            return None
        return self.karriere.fahrernummer

    def _verbuche_karriere(self, wochenende: Ligawochenende, spieler: int) -> None:
        """Schreibt dem Spieler gut, was das Rennwochenende gebracht hat.

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
