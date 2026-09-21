"""Reifenstrategie: Mischungsfolge und Stoppfenster (Punkt 39).

Eine Strategie sagt zwei Dinge: **womit** gefahren wird und **wann**
gewechselt wird. Die Regeln kommen vom Auftraggeber:

* **Mindestens ein Stopp**, weil zwei verschiedene Mischungen Pflicht
  sind. Wer mit einem Satz durchkaeme, muss trotzdem einmal herein.
* **Hoechstens drei Stopps.**
* **Zwei verschiedene Mischungen** im Rennen. Weich-Weich-Hart ist
  erlaubt, Weich-Weich-Weich nicht.
* **Kein Stopp in den ersten und letzten drei Runden.**
* **Die Stintlaenge folgt der Mischung**: Wer weich faehrt, muss frueher
  herein.
* **Die KI streut** - sie stoppt in einem Fenster von sechs Runden, nicht
  auf den Punkt.

Die Pflicht zum Mischungswechsel gilt nur im Trockenen. Wer bei Regen
auf Regenreifen wechselt, hat sie ohnehin erfuellt; und ein Rennen, das
durchgehend unter Wasser steht, soll niemanden zwingen, einmal auf
Trockenreifen herauszufahren.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import boxenstopp as kern_boxenstopp
from rennmanager.kern import gummierung as kern_gummierung
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.auto import Auto, gesamtwert
from rennmanager.kern.reifen import Mischung
from rennmanager.kern.tempo import grenzen_aus
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class StrategieFehler(Exception):
    """Diese Reifenstrategie ist nach den Regeln nicht erlaubt."""


@dataclass(frozen=True)
class Strategie:
    """Mischungsfolge und geplante Stopprunden eines Autos.

    ``mischungen`` hat immer einen Eintrag mehr als ``stopps``: Man
    startet auf der ersten und wechselt bei jeder Stopprunde auf die
    naechste.
    """

    mischungen: tuple[Mischung, ...]
    stopps: tuple[int, ...]

    @property
    def anzahl_stopps(self) -> int:
        return len(self.stopps)

    def mischung_in(self, runde: int) -> Mischung:
        """Womit in dieser Runde gefahren wird, 1-basiert."""
        stelle = sum(1 for stopp in self.stopps if stopp < runde)
        return self.mischungen[min(stelle, len(self.mischungen) - 1)]


# ---------------------------------------------------------------------------
# Regeln
# ---------------------------------------------------------------------------
def pruefe(
    konfiguration: Konfiguration, strategie: Strategie, runden: int, nass: bool = False
) -> None:
    """Prueft eine Strategie gegen die Regeln; wirft sonst.

    :param nass: Bei nassem Rennen entfaellt die Pflicht zu zwei
        Mischungen - ein Wechsel auf Regenreifen erfuellt sie ohnehin,
        und ein Rennen unter Wasser soll niemanden auf Trockenreifen
        zwingen.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    anzahl = strategie.anzahl_stopps
    if len(strategie.mischungen) != anzahl + 1:
        raise StrategieFehler(
            f"{anzahl} Stopps brauchen {anzahl + 1} Mischungen, "
            f"angegeben sind {len(strategie.mischungen)}"
        )
    if anzahl < einstellung["stopps_min"]:
        raise StrategieFehler(
            f"Mindestens {einstellung['stopps_min']} Stopp, weil zwei "
            "verschiedene Mischungen Pflicht sind"
        )
    if anzahl > einstellung["stopps_max"]:
        raise StrategieFehler(
            f"Hoechstens {einstellung['stopps_max']} Stopps, angegeben sind {anzahl}"
        )
    if list(strategie.stopps) != sorted(set(strategie.stopps)):
        raise StrategieFehler("Die Stopprunden muessen aufsteigend und verschieden sein")

    sperre = einstellung["sperre_runden"]
    for stopp in strategie.stopps:
        if stopp <= sperre or stopp > runden - sperre:
            raise StrategieFehler(
                f"Runde {stopp}: In den ersten und letzten {sperre} Runden "
                "wird nicht gestoppt"
            )
    if not nass and len({m.schluessel for m in strategie.mischungen}) < 2:
        raise StrategieFehler(
            "Zwei verschiedene Mischungen sind Pflicht - "
            f"gefahren wird nur {strategie.mischungen[0].name}"
        )


def ist_erlaubt(
    konfiguration: Konfiguration, strategie: Strategie, runden: int, nass: bool = False
) -> bool:
    """Wie ``pruefe``, nur ohne Ausnahme - fuer die Oberflaeche."""
    try:
        pruefe(konfiguration, strategie, runden, nass)
    except StrategieFehler:
        return False
    return True


# ---------------------------------------------------------------------------
# Wie weit ein Satz traegt
# ---------------------------------------------------------------------------
def reichweite_runden(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    rundenlaenge_m: float,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
) -> int:
    """Wie viele Runden dieser Satz traegt, bevor er hin ist."""
    weite = kern_reifen.stintweite_m(
        konfiguration, auto, misch, streckenfaktor, wetterfaktor, naesse
    )
    return max(int(weite / max(rundenlaenge_m, 1.0)), 1)


def hoechststint_runden(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    rundenlaenge_m: float,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
) -> int:
    """Wie viele Runden ein Satz traegt, **ohne** unters Mindestprofil zu fallen.

    Das ist die Groesse, mit der geplant wird: ``reichweite_runden``
    faehrt den Satz bis auf null ab, hier bleibt der Rest uebrig, den der
    Auftraggeber verlangt hat. Die Vorausberechnung haelt sie ein - und
    seit Punkt 39 auch das Boxenstoppfenster, das sie vorher aushebeln
    konnte.
    """
    mindest = konfiguration.wert("boxenstopp", "strategie", "mindest_restprofil")
    abbau = (
        kern_reifen.verschleiss_je_meter(
            konfiguration, auto, misch, streckenfaktor, wetterfaktor, naesse
        )
        * rundenlaenge_m
    )
    if abbau <= 0.0:  # pragma: no cover - Notbremse
        return 1_000_000
    return max(int((1.0 - mindest) / abbau), 1)


def noetige_stopps(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    runden: int,
    rundenlaenge_m: float,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
) -> int:
    """Wie viele Stopps das Rennen mit dieser Mischung mindestens kostet.

    Mindestens einer, weil zwei Mischungen Pflicht sind.
    """
    reichweite = reichweite_runden(
        konfiguration, auto, misch, rundenlaenge_m, streckenfaktor, wetterfaktor, naesse
    )
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    aus_verschleiss = max(math.ceil(runden / reichweite) - 1, 0)
    return min(
        max(aus_verschleiss, einstellung["stopps_min"]), einstellung["stopps_max"]
    )


# ---------------------------------------------------------------------------
# Was eine Variante kostet
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Variante:
    """Eine Mischungsfolge mit ihrer besten Stoppverteilung."""

    mischungen: tuple[Mischung, ...]
    stopps: tuple[int, ...]
    # Geschaetzte Rennzeit in Millisekunden, Stopps eingerechnet.
    zeit_ms: float

    @property
    def anzahl_stopps(self) -> int:
        return len(self.stopps)

    @property
    def folge(self) -> str:
        return "-".join(m.kuerzel for m in self.mischungen)


def je_runde(wert, runden: int, ohne=0.0) -> np.ndarray:
    """Eine Groesse fuer jede Rennrunde als Feld.

    Eine einzelne Zahl gilt fuer das ganze Rennen; eine Folge wird auf die
    Rundenzahl gestreckt oder gekuerzt. So nimmt dieselbe Rechnung die
    Startlage *und* die ganze Vorhersage entgegen.
    """
    if np.isscalar(wert):
        return np.full(runden, float(wert))
    feld = np.asarray(wert, dtype=float)
    if len(feld) == runden:
        return feld
    if len(feld) == 0:  # pragma: no cover - Notbremse
        return np.full(runden, float(ohne))
    stellen = np.clip((np.arange(runden) * len(feld)) // runden, 0, len(feld) - 1)
    return feld[stellen]


def naesse_je_runde(naesse, runden: int) -> np.ndarray:
    """Die Naesse jeder Rennrunde - 0 trocken bis 1 unter Wasser."""
    return je_runde(naesse, runden, 0.0)


# Feinheit der Tempotabelle: Der Tempofaktor haengt allein am
# aufgelaufenen Verschleiss, also wird er einmal ueber die ganze Spanne
# gerechnet und danach nur noch nachgeschlagen.
TEMPOSTUFEN = 2000


@dataclass(frozen=True)
class Stinttabelle:
    """Zeit und Restprofil eines Stints, nach Startrunde und Laenge.

    Ist das Wetter ueber das ganze Rennen gleich, haengt beides nur an der
    Laenge - dann stehen hier eindimensionale Felder und ``konstant`` ist
    wahr. Wechselt das Wetter, kostet derselbe Stint an verschiedenen
    Stellen des Rennens verschieden viel, und die Felder sind
    zweidimensional: ``[Startrunde, Laenge]``.

    Der Unterschied ist nicht nur Buchhaltung: Solange die Tabelle
    konstant ist, ist die Reihenfolge der Stints fuer die Rennzeit egal,
    und aus einer Rechnung werden alle Reihenfolgen. Sobald sie es nicht
    mehr ist, muss jede Reihenfolge einzeln gerechnet werden.
    """

    zeiten: np.ndarray
    rest: np.ndarray
    konstant: bool

    def zeit(self, start, laenge):
        """Was ein Stint dieser Laenge ab dieser Startrunde kostet."""
        if not self.konstant:
            return self.zeiten[start, laenge]
        # Bei gleichbleibendem Wetter zaehlt nur die Laenge; die Form des
        # Ergebnisses richtet sich trotzdem nach ``start``, damit die
        # Rechnung in beiden Faellen dieselbe ist.
        return np.broadcast_to(self.zeiten[laenge], np.shape(start))

    def restprofil(self, start, laenge):
        """Was nach einem Stint dieser Laenge noch auf dem Reifen ist."""
        if not self.konstant:
            return self.rest[start, laenge]
        return np.broadcast_to(self.rest[laenge], np.shape(start))


def _tempotabelle(konfiguration: Konfiguration, auto: Auto) -> np.ndarray:
    """Tempofaktor je Verschleissstufe - einmal gerechnet, oft gebraucht."""
    return np.array(
        [
            kern_reifen.tempofaktor(konfiguration, auto, stufe / TEMPOSTUFEN)
            for stufe in range(TEMPOSTUFEN + 1)
        ]
    )


def _stinttabelle(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    runden: int,
    rundenzeit_ms: float,
    rundenlaenge_m: float,
    streckenfaktor: float,
    wetterfaktor: float,
    naesse,
    tempotabelle: np.ndarray | None = None,
    gummifaktor=1.0,
) -> Stinttabelle:
    """Zeit und Restprofil nach n Runden auf diesem Satz.

    Runde fuer Runde gerechnet, weil die Gripkurve ihr Optimum bei 80 %
    hat: Ein Stint ist am Anfang und am Ende langsamer als in der Mitte,
    und das laesst sich nicht mitteln.

    ``naesse`` darf eine Zahl sein - dann gilt sie fuer das ganze Rennen -
    oder die Naesse je Runde. Im zweiten Fall haengt alles auch an der
    Startrunde: Ein Satz Trockenreifen, der in Runde 1 aufgezogen wird,
    haelt laenger als derselbe Satz ab Runde 40, wenn es ab Runde 20
    regnet.

    ``gummifaktor`` ist dasselbe fuer die Strecke (Punkt 90): Sie frisst
    am Anfang mehr Reifen als am Ende. Der Auftraggeber hat entschieden,
    dass der Planer das kennt - den wachsenden **Grip** dagegen nicht.
    Ein Stint am Rennanfang ist damit kuerzer als derselbe Stint am
    Rennende, und die Reihenfolge der Mischungen ist keine freie Wahl
    mehr.
    """
    feld = naesse_je_runde(naesse, runden)
    # Was von aussen am Reifen zehrt: das Wetter (GDD 7) und die Strecke
    # selbst (Punkt 90). Beides haengt nur an der Runde, nicht an der
    # Mischung - deshalb ein Feld statt zweier.
    zehrfeld = je_runde(wetterfaktor, runden, 1.0) * je_runde(gummifaktor, runden, 1.0)
    if tempotabelle is None:
        tempotabelle = _tempotabelle(konfiguration, auto)
    verschleiss = np.array(
        [
            kern_reifen.verschleiss_je_meter(
                konfiguration, auto, misch, streckenfaktor, float(wf), float(n)
            )
            * rundenlaenge_m
            for wf, n in zip(zehrfeld, feld, strict=True)
        ]
    )
    mischfaktor = np.array(
        [kern_reifen.mischungsfaktor(konfiguration, misch, float(n)) for n in feld]
    )

    def zeile(ab: int) -> tuple[np.ndarray, np.ndarray]:
        """Zeit und Restprofil eines Stints, der in Runde ``ab + 1`` beginnt."""
        aufgelaufen = np.concatenate(([0.0], np.cumsum(verschleiss[ab:])))
        stufen = np.clip(
            (aufgelaufen[:-1] * TEMPOSTUFEN).astype(int), 0, TEMPOSTUFEN
        )
        dauer = rundenzeit_ms / np.maximum(
            mischfaktor[ab:] * tempotabelle[stufen], 1e-6
        )
        return np.concatenate(([0.0], np.cumsum(dauer))), np.clip(
            1.0 - aufgelaufen, 0.0, 1.0
        )

    konstant = bool(np.all(feld == feld[0]) and np.all(zehrfeld == zehrfeld[0]))
    if konstant:
        zeiten, rest = zeile(0)
        return Stinttabelle(zeiten=zeiten, rest=rest, konstant=True)

    zeiten = np.zeros((runden + 1, runden + 1))
    rest = np.ones((runden + 1, runden + 1))
    for ab in range(runden):
        z, r = zeile(ab)
        zeiten[ab, : len(z)] = z
        rest[ab, : len(r)] = r
        # Was ueber das Rennende hinausginge, wird nie abgefragt; damit es
        # nicht faelschlich als "geht noch" durchrutscht, steht dort 0.
        rest[ab, len(r) :] = 0.0
    return Stinttabelle(zeiten=zeiten, rest=rest, konstant=False)


def bewerte(
    konfiguration: Konfiguration,
    auto: Auto,
    folge: tuple[Mischung, ...],
    runden: int,
    rundenzeit_ms: float,
    rundenlaenge_m: float,
    stoppverlust_ms: float,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse=0.0,
    tabellen: dict[str, Stinttabelle] | None = None,
    gummifaktor=1.0,
) -> Variante | None:
    """Die beste Stoppverteilung fuer diese Mischungsfolge.

    Gesucht wird die Aufteilung der Runden auf die Stints, die die
    Rennzeit kleinstmoeglich macht - unter der Bedingung, dass **kein
    Stint unter das Mindestrestprofil faellt**, auch der letzte nicht.

    Gerechnet wird als Minimum-Plus-Faltung ueber die Stints: Fuer jede
    Runde steht, was die beste Aufteilung bis dahin gekostet hat. Das ist
    exakt, nicht geraten - und genau das meint "vorher berechnen, welche
    Reifenkombination die beste ist".

    :param tabellen: fertige Stinttabellen je Mischung. Ohne Angabe
        rechnet die Funktion sie selbst - fuer viele Folgen lohnt es,
        sie einmal vorab zu bauen, denn sie haengen nur an der Mischung.

    :return: ``None``, wenn die Folge das Rennen nicht traegt
    """
    mindest = konfiguration.wert("boxenstopp", "strategie", "mindest_restprofil")
    sperre = konfiguration.wert("boxenstopp", "strategie", "sperre_runden")
    abstand = konfiguration.wert("boxenstopp", "strategie", "abstand_min_runden")

    if tabellen is None:
        tabellen = {
            misch.schluessel: _stinttabelle(
                konfiguration, auto, misch, runden, rundenzeit_ms, rundenlaenge_m,
                streckenfaktor, wetterfaktor, naesse, gummifaktor=gummifaktor,
            )
            for misch in set(folge)
        }
    genommen = [tabellen[m.schluessel] for m in folge]

    # Die Regeln stecken **in** der Rechnung, nicht dahinter: Eine
    # Zwischenrunde muss ausserhalb der Sperrfristen liegen, und jeder
    # Stint muss den Mindestabstand zwischen zwei Stopps tragen. Wer
    # zuerst das freie Optimum sucht und es danach verwirft, verliert
    # brauchbare Varianten - gemessen fiel so 4x Hart in Monza heraus,
    # obwohl ein harter Satz dort 46 der 51 Runden traegt.
    unendlich = float("inf")
    erlaubt = np.zeros(runden + 1, dtype=bool)
    erlaubt[sperre + 1 : runden - sperre + 1] = True

    beste = np.full(runden + 1, unendlich)
    beste[0] = 0.0
    herkunft: list[np.ndarray] = []
    for stelle, tabelle in enumerate(genommen):
        letzter = stelle == len(folge) - 1
        naechste = np.full(runden + 1, unendlich)
        woher = np.zeros(runden + 1, dtype=int)
        aufschlag = 0.0 if letzter else stoppverlust_ms
        # Ein Stint zwischen zwei Stopps muss den Mindestabstand tragen.
        kuerzeste = 1 if (stelle == 0 or letzter) else abstand
        for laenge in range(kuerzeste, runden + 1):
            ziel = np.arange(laenge, runden + 1)
            if not letzter:
                ziel = ziel[erlaubt[ziel]]
            if not len(ziel):
                continue
            start = ziel - laenge
            # Kein Stint faellt unter das Mindestrestprofil. Bei
            # wechselndem Wetter haengt das an der Startrunde, deshalb
            # wird es hier je Ziel geprueft und nicht vorab je Mischung.
            haelt = tabelle.restprofil(start, laenge) >= mindest
            ziel, start = ziel[haelt], start[haelt]
            if not len(ziel):
                continue
            kandidat = beste[start] + tabelle.zeit(start, laenge) + aufschlag
            besser = kandidat < naechste[ziel]
            naechste[ziel[besser]] = kandidat[besser]
            woher[ziel[besser]] = laenge
        beste = naechste
        herkunft.append(woher)

    if not np.isfinite(beste[runden]):
        return None

    # Rueckwaerts auslesen, welche Stintlaengen die beste Zeit ergaben.
    laengen: list[int] = []
    stand = runden
    for woher in reversed(herkunft):
        laenge = int(woher[stand])
        laengen.append(laenge)
        stand -= laenge
    laengen.reverse()

    stopps: list[int] = []
    gelaufen = 0
    for laenge in laengen[:-1]:
        gelaufen += laenge
        stopps.append(gelaufen)
    return Variante(
        mischungen=tuple(folge), stopps=tuple(stopps), zeit_ms=float(beste[runden])
    )


def varianten(
    konfiguration: Konfiguration,
    auto: Auto,
    runden: int,
    rundenzeit_ms: float,
    rundenlaenge_m: float,
    stoppverlust_ms: float,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
    pflicht_zwei: bool = True,
    gummifaktor=1.0,
) -> list[Variante]:
    """Alle Mischungsfolgen, die nah genug an der besten liegen.

    Zuerst wird jede zulaessige Folge durchgerechnet, dann nach Rennzeit
    geordnet. Was mehr als die Schwelle hinter der besten liegt, faellt
    heraus - die Schwelle waechst mit der Renndistanz (30 s bei 100 km,
    60 s bei 300 km).

    Liegen die Varianten dicht beieinander, bleiben alle Stoppzahlen
    moeglich und das Feld faehrt verschiedene Strategien. Liegen sie weit
    auseinander, bleibt nur die beste - dann gibt es auf dieser Strecke
    eben nur einen Weg.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    feld = naesse_je_runde(naesse, runden)
    # Brauchbar ist, was zu **irgendeiner** Lage des Rennens passt: Wer
    # nur die Startlage fragt, plant ein trockenes Rennen und steht im
    # Regen auf Slicks. Die Reihenfolge richtet sich nach der Startlage,
    # damit dort weiter das Naheliegende oben steht.
    brauchbar: list[Mischung] = []
    for lage in [float(feld[0]), *sorted({float(n) for n in feld})]:
        for m in _nach_eignung(konfiguration, lage):
            if abs(m.naesse - lage) <= einstellung["eignungsgrenze"] and m not in brauchbar:
                brauchbar.append(m)
    if not brauchbar:
        brauchbar = _nach_eignung(konfiguration, float(feld[0]))[:1]
    # Entscheidung des Auftraggebers: Ab einem bestimmten Streckenfaktor
    # traegt die weichste Trockenmischung nicht mehr - dort bleiben nur
    # die haerteren. Die Regenreifen bleiben unberuehrt; die Regel zielt
    # auf den Verschleiss der Strecke, nicht auf die Lage.
    if streckenfaktor > einstellung["weich_hoechstens_streckenfaktor"]:
        ohne_weich = _ohne_weichste(konfiguration, brauchbar)
        if ohne_weich:
            brauchbar = ohne_weich

    # Die Stinttabellen haengen nur an der Mischung, nicht an der Folge -
    # einmal gebaut, gelten sie fuer alle. Ohne das rechnete jede der 117
    # Folgen ihre vier Tabellen neu, und ein Auto brauchte eine halbe
    # Sekunde statt weniger Millisekunden.
    tempotabelle = _tempotabelle(konfiguration, auto)
    tabellen = {
        misch.schluessel: _stinttabelle(
            konfiguration, auto, misch, runden, rundenzeit_ms, rundenlaenge_m,
            streckenfaktor, wetterfaktor, naesse, tempotabelle,
            gummifaktor=gummifaktor,
        )
        for misch in brauchbar
    }

    gefunden = _suche(
        konfiguration, auto, brauchbar, tabellen, runden, rundenzeit_ms,
        rundenlaenge_m, stoppverlust_ms, streckenfaktor, wetterfaktor, naesse,
        pflicht_zwei, einstellung["stopps_max"], gummifaktor,
    )
    if not gefunden:
        # Geht es mit drei Stopps nicht auf, darf ein vierter dazu. Das ist
        # dann das Maximum - so hat es der Auftraggeber festgelegt.
        gefunden = _suche(
            konfiguration, auto, brauchbar, tabellen, runden, rundenzeit_ms,
            rundenlaenge_m, stoppverlust_ms, streckenfaktor, wetterfaktor, naesse,
            pflicht_zwei, einstellung["stopps_max_notfall"], gummifaktor,
        )

    if not gefunden:
        return []

    gefunden.sort(key=lambda v: v.zeit_ms)
    distanz_km = runden * rundenlaenge_m / 1000.0
    schwelle = (
        einstellung["variantenschwelle_sockel_s"]
        + einstellung["variantenschwelle_je_100km_s"] * distanz_km / 100.0
    ) * 1000.0
    grenze = gefunden[0].zeit_ms + schwelle
    return [v for v in gefunden if v.zeit_ms <= grenze]


def _ohne_weichste(
    konfiguration: Konfiguration, mischungen: list[Mischung]
) -> list[Mischung]:
    """Dieselbe Liste ohne die weichste Trockenmischung.

    Gibt eine leere Liste zurueck, wenn danach nichts uebrig bleibt - der
    Aufrufer entscheidet dann, dass die Regel hier nicht greifen kann.
    """
    weichste = weichste_trockene(konfiguration)
    if weichste is None:
        return list(mischungen)
    return [m for m in mischungen if m.schluessel != weichste.schluessel]


def _suche(
    konfiguration: Konfiguration,
    auto: Auto,
    brauchbar: list[Mischung],
    tabellen: dict,
    runden: int,
    rundenzeit_ms: float,
    rundenlaenge_m: float,
    stoppverlust_ms: float,
    streckenfaktor: float,
    wetterfaktor: float,
    naesse: float,
    pflicht_zwei: bool,
    hoechstens: int,
    gummifaktor=1.0,
) -> list[Variante]:
    """Alle tragfaehigen Varianten bis zu dieser Stoppzahl."""
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    # Punkt 91: Jede Reihenfolge wird einzeln gerechnet. Frueher galt:
    # Ein Stint kostet, was er kostet, egal ob er der erste oder der
    # letzte ist - dann genuegte eine Rechnung je Zusammenstellung, und
    # die Reihenfolgen erbten sie. Seit die gruene Strecke am Anfang mehr
    # Reifen frisst als am Ende (Punkt 90), stimmt das nicht mehr: Ein
    # weicher Satz auf gruenem Asphalt ist etwas anderes als derselbe
    # Satz auf eingegummiertem. Die Reihenfolge ist damit keine freie
    # Wahl des Fahrers mehr, sondern Teil der Strategie - so hat es der
    # Auftraggeber festgelegt.
    gefunden: list[Variante] = []
    for stopps in range(einstellung["stopps_min"], hoechstens + 1):
        # Entscheidung des Auftraggebers: Wer so oft hereinkommen muss,
        # hat auf dem weichsten Gummi nichts verloren. Die Mischung faellt
        # fuer diese Stoppzahl weg, die niedrigeren behalten sie.
        erlaubt = brauchbar
        if stopps > einstellung["weich_hoechstens_stopps"]:
            erlaubt = _ohne_weichste(konfiguration, brauchbar) or brauchbar
        for satz in product(erlaubt, repeat=stopps + 1):
            if pflicht_zwei and len({m.schluessel for m in satz}) < 2:
                continue
            eine = bewerte(
                konfiguration, auto, satz, runden, rundenzeit_ms, rundenlaenge_m,
                stoppverlust_ms, streckenfaktor, wetterfaktor, naesse,
                tabellen=tabellen, gummifaktor=gummifaktor,
            )
            if eine is None:
                continue
            gefunden.append(eine)
    return gefunden


# ---------------------------------------------------------------------------
# Was die KI faehrt
# ---------------------------------------------------------------------------
def pflicht_zwei_mischungen(konfiguration: Konfiguration, wetter) -> bool:
    """Ob zwei verschiedene Mischungen Pflicht sind.

    Im Trockenen ja. Bei Regen, Starkregen oder wechselhaft nicht: Wer
    dort auf Intermediates oder Regenreifen wechselt, hat ohnehin
    gewechselt, und ein Rennen unter Wasser soll niemanden zwingen,
    einmal auf Trockenreifen herauszufahren.

    Das Wetter steht vor dem Rennen fest (GDD 7), also steht auch diese
    Regel vor dem Rennen fest - der Spieler weiss beim Planen, woran er
    ist.
    """
    ohne = set(konfiguration.wert("boxenstopp", "strategie", "ohne_pflicht_bei"))
    lagen = {wetter} if isinstance(wetter, str) else set(wetter)
    return not (lagen & ohne)


def ki_strategie(
    konfiguration: Konfiguration,
    auto: Auto,
    runden: int,
    rundenlaenge_m: float,
    seedquelle: Seedquelle,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
    pflicht_zwei: bool = True,
    rundenzeit_ms: float = 90_000.0,
    stoppverlust_ms: float = 25_000.0,
    auswahl: list[Variante] | None = None,
    gummifaktor=1.0,
) -> Strategie:
    """Die Strategie eines KI-Autos - siehe ``gewaehlte_strategie``."""
    return gewaehlte_strategie(
        konfiguration, auto, runden, rundenlaenge_m, seedquelle, streckenfaktor,
        wetterfaktor, naesse, pflicht_zwei, rundenzeit_ms, stoppverlust_ms,
        auswahl, gummifaktor,
    )[0]


def variantengewicht(konfiguration: Konfiguration, stopps: int) -> float:
    """Mit welchem Gewicht eine Variante mit so vielen Stopps gezogen wird.

    Naturgemaess gibt es mehr Varianten mit mehr Stopps: Bei drei
    Trockenmischungen hat eine Ein-Stopp-Folge 3^2 = 9 Reihenfolgen,
    eine Zwei-Stopp-Folge 27 und eine Drei-Stopp-Folge 81. Wer gleich
    verteilt zieht, laesst das Feld schon deshalb oefter dreimal
    stoppen - gemessen planten in Zandvoort 86 und am Nuerburgring 97
    Prozent der Autos drei Stopps, ohne dass das jemand entschieden
    haette. Die Gewichte gleichen das aus.
    """
    tabelle = konfiguration.wert("boxenstopp", "strategie", "variantengewicht")
    return float(tabelle.get(str(stopps), 1.0))


def _ziehe(konfiguration: Konfiguration, moeglich: list[Variante], wuerfel) -> int:
    """Zieht eine der zugelassenen Varianten, gewichtet nach Stoppzahl.

    Gezogen wird **nur** aus dem, was die Vorausberechnung zugelassen
    hat - das Gewicht aendert die Auswahl nicht, nur ihre Haeufigkeit.
    """
    gewichte = np.array(
        [variantengewicht(konfiguration, v.anzahl_stopps) for v in moeglich],
        dtype=float,
    )
    summe = gewichte.sum()
    if summe <= 0.0:  # pragma: no cover - Notbremse
        return int(wuerfel.integers(0, len(moeglich)))
    return int(wuerfel.choice(len(moeglich), p=gewichte / summe))


def gewaehlte_strategie(
    konfiguration: Konfiguration,
    auto: Auto,
    runden: int,
    rundenlaenge_m: float,
    seedquelle: Seedquelle,
    streckenfaktor: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
    pflicht_zwei: bool = True,
    rundenzeit_ms: float = 90_000.0,
    stoppverlust_ms: float = 25_000.0,
    auswahl: list[Variante] | None = None,
    gummifaktor=1.0,
) -> tuple[Strategie, int]:
    """Die Strategie eines KI-Autos und **welche** Variante es genommen hat.

    Die Nummer ist der Platz in ``auswahl``. Sie wird gebraucht, um
    abzuzaehlen, wie viele verschiedene Strategien im Feld unterwegs sind
    (Punkt 91); ohne sie liessen sich zwei Autos auf derselben Variante
    nicht mehr von zweien auf verschiedenen unterscheiden, sobald das
    Boxenstoppfenster die Stopprunden verschoben hat. ``-1`` steht fuer
    den Notfallplan, der gar nicht aus der Auswahl stammt.

    **Erst rechnen, dann wuerfeln.** Alle zulaessigen Mischungsfolgen
    werden durchgerechnet und nach Rennzeit geordnet; was zu weit hinter
    der besten liegt, faellt heraus. Unter den verbliebenen waehlt das
    Auto - deshalb faehrt nicht das ganze Feld dasselbe, und trotzdem
    faehrt niemand offensichtlichen Unsinn.

    **Danach** kommt das Boxenstoppfenster: ein zufaelliges Delta von
    +/- 5 % der Renndistanz, mindestens zwei Runden, solange der
    Mindestabstand zwischen zwei Stopps das hergibt.

    :param auswahl: fertig gerechnete Varianten. Ohne Angabe rechnet die
        Funktion sie selbst - das kostet Zeit und laesst sich fuer ein
        ganzes Feld einmal vorab erledigen.
    """
    wuerfel = seedquelle.generator()
    moeglich = (
        auswahl
        if auswahl is not None
        else varianten(
            konfiguration, auto, runden, rundenzeit_ms, rundenlaenge_m,
            stoppverlust_ms, streckenfaktor, wetterfaktor, naesse, pflicht_zwei,
        )
    )
    if not moeglich:
        # Notfall: kein Plan haelt das Mindestprofil. Dann wird so oft
        # gestoppt, wie erlaubt ist, und zwar auf der Mischung, die zur
        # Lage bei jedem Stopp passt - das ist das Beste, was ueberhaupt
        # noch geht. Frueher stand hier ein einziger Stopp zur Rennmitte;
        # in einem Regenrennen kam damit das ganze Feld auf null Profil
        # ins Ziel.
        einstellung = konfiguration.wert("boxenstopp", "strategie")
        anzahl = einstellung["stopps_max_notfall"]
        feld = naesse_je_runde(naesse, runden)
        sperre = einstellung["sperre_runden"]
        spanne = max(runden - 2 * sperre, 1)
        stopps = tuple(
            sperre + max(round(spanne * (n + 1) / (anzahl + 1)), n + 1)
            for n in range(anzahl)
        )
        folge = tuple(
            passende_mischung(konfiguration, float(feld[min(runde, runden - 1)]))
            for runde in (0, *stopps)
        )
        return Strategie(mischungen=folge, stopps=stopps), -1

    nummer = _ziehe(konfiguration, moeglich, wuerfel)
    gewaehlt = moeglich[nummer]
    # Punkt 91: **Kein Nachrechnen je Auto mehr.** Frueher rechnete jedes
    # Auto die Stopprunden seiner Folge noch einmal mit seinen eigenen
    # Werten - wer die Reifen schlechter schont, kam frueher herein. Der
    # Auftraggeber hat entschieden, dass die Strategie ohne dieses Delta
    # gerechnet wird: Der Plan gilt dem Medianfahrer des Feldes, und was
    # ein Auto davon abweicht, faengt im Rennen der Zwangsstopp bei 30
    # Prozent ab. So faehrt das Feld wirklich die zugelassenen
    # Strategien und nicht dreissig Abwandlungen davon.
    #
    # Das Fenster darf die Mindestprofil-Regel nicht aushebeln. Geprueft
    # wird gegen die nasseste Lage des Rennens und die gruenste Strecke -
    # beides zehrt am staerksten, also haelt die Grenze dann auch sonst.
    haerteste = float(naesse_je_runde(naesse, runden).max())
    zaehrendste = float(
        (je_runde(wetterfaktor, runden, 1.0) * je_runde(gummifaktor, runden, 1.0)).max()
    )
    hoechststints = tuple(
        hoechststint_runden(
            konfiguration, auto, misch, rundenlaenge_m,
            streckenfaktor, zaehrendste, haerteste,
        )
        for misch in gewaehlt.mischungen
    )
    return Strategie(
        mischungen=gewaehlt.mischungen,
        stopps=_mit_fenster(
            konfiguration, gewaehlt.stopps, runden, wuerfel, hoechststints
        ),
    ), nummer


def _mit_fenster(
    konfiguration: Konfiguration,
    stopps: tuple[int, ...],
    runden: int,
    wuerfel,
    hoechststints: tuple[int, ...] | None = None,
) -> tuple[int, ...]:
    """Legt das Zufallsfenster auf die berechneten Stopprunden.

    Das Fenster ist +/- 5 % der Renndistanz, aufgerundet, mindestens zwei
    Runden - aber nur, solange der Mindestabstand von drei Runden zwischen
    zwei Stopps gewahrt bleibt. Sonst kaeme ein Auto zweimal kurz
    hintereinander herein und verloere das Rennen in der Boxengasse.

    **Und nur, solange das Mindestrestprofil haelt.** Vorher hat das
    Fenster die 30-Prozent-Regel wieder ausgehebelt, die die
    Vorausberechnung eingehalten hatte: In Zandvoort kamen 23 von 30
    Autos darunter, eines mit 9 Prozent ins Ziel. ``hoechststints`` sagt
    je Stint, wie viele Runden sein Satz traegt; das Fenster darf einen
    Stopp nur so weit nach hinten schieben, wie der laufende Satz reicht,
    und nur so weit nach vorn, wie die uebrigen Saetze noch bis ins Ziel
    kommen.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    sperre = einstellung["sperre_runden"]
    abstand = einstellung["abstand_min_runden"]
    fenster = max(
        math.ceil(einstellung["fenster_anteil"] * runden),
        einstellung["fenster_min_runden"],
    )
    # Was die noch folgenden Saetze zusammen tragen.
    rest_reicht = [0] * (len(stopps) + 1)
    if hoechststints is not None:
        for stelle in range(len(stopps) - 1, -1, -1):
            rest_reicht[stelle] = rest_reicht[stelle + 1] + hoechststints[stelle + 1]

    verschoben: list[int] = []
    for stelle, runde in enumerate(stopps):
        versatz = int(round(float(wuerfel.uniform(-fenster, fenster))))
        neu = runde + versatz
        vorheriger = verschoben[-1] if verschoben else 0
        untere = sperre + 1
        if verschoben:
            untere = max(untere, vorheriger + abstand)
        obere = runden - sperre
        if stelle + 1 < len(stopps):
            # Fuer die noch folgenden Stopps muss Platz bleiben.
            obere = min(obere, runden - sperre - abstand * (len(stopps) - stelle - 1))
        if hoechststints is not None:
            # So weit traegt der Satz, auf dem das Auto gerade steht.
            obere = min(obere, vorheriger + hoechststints[stelle])
            # Und so frueh darf es nicht kommen, sonst reichen die
            # uebrigen Saetze nicht mehr bis ins Ziel.
            untere = max(untere, runden - rest_reicht[stelle])
        if untere > obere:
            # Der Plan ist gerechnet und haelt; im Zweifel bleibt er.
            verschoben.append(runde)
            continue
        verschoben.append(max(untere, min(neu, obere)))
    return tuple(verschoben)


# ---------------------------------------------------------------------------
# Wetterwechsel im Rennen
# ---------------------------------------------------------------------------
def notstopp(
    konfiguration: Konfiguration,
    gefahren: Mischung,
    naesse: float,
    seit_letztem_stopp: int,
    runden_auf_falschem_reifen: int = 0,
    geduld: int = 0,
) -> bool:
    """Ob ein Auto wegen des Wetters ausserplanmaessig hereinkommen muss.

    Drei Bedingungen. Der Reifen muss **falsch** sein - weiter von der
    Lage entfernt, als die Eignungsgrenze zulaesst, also genau die
    Mischungen, die die KI fuer diese Lage gar nicht erst gewaehlt haette.
    Das Auto muss seine **Geduld** aufgebraucht haben (Punkt 83): So
    viele Runden faehrt es auf dem falschen Reifen weiter, ausgewuerfelt
    von ``geduld_falscher_reifen``. Und zwischen zwei Stopps muessen
    **mindestens drei Runden** liegen - ohne das kaeme ein Auto bei einem
    schnellen Wechsel zweimal hintereinander herein und verloere das
    Rennen an der Boxengasse statt auf der Strecke.

    :param runden_auf_falschem_reifen: wie lange der Reifen schon nicht
        mehr zur Lage passt
    :param geduld: wie lange dieses Auto das aushaelt
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    if abs(gefahren.naesse - naesse) <= einstellung["eignungsgrenze"]:
        return False
    if runden_auf_falschem_reifen < geduld:
        return False
    return seit_letztem_stopp >= einstellung["abstand_min_runden"]


def geduld_falscher_reifen(konfiguration: Konfiguration, seedquelle: Seedquelle) -> int:
    """Wie viele Runden dieses Auto auf dem falschen Reifen bleibt.

    Ausgewuerfelt von null bis ``falscher_reifen_max_runden``
    (Entscheidung des Auftraggebers). Ohne den Wurf kam das ganze Feld in
    derselben Runde herein: Dreht das Wetter, werden alle Reifen des
    Feldes im selben Augenblick falsch, und jedes Auto nahm die
    fruehestmoegliche Runde. Gemessen damals in der untersten Liga auf
    Sakhir: 17 Autos in Runde 10, 12 in Runde 11.

    Je Auto **ein** Wurf je Rennen - wer zweimal auf den falschen Reifen
    geraet, bleibt beide Male gleich geduldig.
    """
    hoechstens = konfiguration.wert(
        "boxenstopp", "strategie", "falscher_reifen_max_runden"
    )
    return int(seedquelle.generator().integers(0, hoechstens + 1))


def weichste_trockene(konfiguration: Konfiguration) -> Mischung | None:
    """Die weichste Mischung, die fuer trockene Strecke gebaut ist.

    Nicht ueber den Schluessel gesucht, sondern ueber die Zahlen: unter
    allen Mischungen ohne Naesse die mit dem hoechsten Verschleiss. Kaeme
    eine vierte Trockenmischung dazu, stimmte das weiter.
    """
    trocken = [m for m in kern_reifen.mischungen(konfiguration) if m.naesse == 0.0]
    if not trocken:  # pragma: no cover - es gibt immer Trockenmischungen
        return None
    return max(trocken, key=lambda m: m.verschleiss)


def nicht_weicher_als(gewuenscht: Mischung, untergrenze: Mischung) -> Mischung:
    """Die haertere von beiden - die Regel nach einem Zwangsstopp (Punkt 78).

    Entscheidung des Auftraggebers: Wer sich einen Satz abgefahren hat,
    darf danach nicht wieder auf eine weichere Mischung zurueck. Weicher
    heisst hier: hoeherer Verschleiss.

    Verglichen wird nur **innerhalb** einer Naesseklasse. Ein Regenreifen
    ist nicht "haerter" als ein weicher Slick, er ist etwas anderes; bei
    Nasse entscheidet die Lage, nicht die Haerte.
    """
    if gewuenscht.naesse != untergrenze.naesse:
        return gewuenscht
    if gewuenscht.verschleiss <= untergrenze.verschleiss:
        return gewuenscht
    return untergrenze


def verschiebeschwelle(konfiguration: Konfiguration, *, nach_notstopp: bool) -> float:
    """Ab welchem Restprofil ein geplanter Stopp nicht mehr verschoben wird.

    Normalerweise ``planstopp_ab_restprofil``. Stand aber eben erst ein
    **Notstopp** an, gilt der tiefere Wert: Der Satz ist frisch, und ihn
    wenige Runden spaeter schon wieder abzugeben hiesse, zweimal fuer
    denselben Reifenwechsel zu zahlen (Entscheidung des Auftraggebers).
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    if nach_notstopp:
        return einstellung["planstopp_nach_notstopp_restprofil"]
    return einstellung["planstopp_ab_restprofil"]


def notstopp_verschleiss(
    konfiguration: Konfiguration, restprofil: float, seit_letztem_stopp: int
) -> bool:
    """Ob ein Auto wegen **abgefahrener Reifen** hereinkommen muss.

    Entscheidung des Auftraggebers, nachdem der Messlauf ueber fuenf
    Strecken zeigte, was sonst passiert: Ein Auto, dessen Satz lange vor
    der geplanten Stopprunde durch ist, erreicht diese Runde nie. Es
    schleicht auf blankem Gummi weiter - gemessen 16 km/h statt 150 - und
    beendet das Rennen ohne den vorgeschriebenen Mischungswechsel.

    Der Mindestabstand zwischen zwei Stopps gilt auch hier: Ein Auto mit
    sehr hohem Verschleiss soll nicht Runde um Runde hereinkommen.

    Wann **nicht** gestoppt wird - in den letzten Runden -, entscheidet
    der Aufrufer ueber dieselbe Sperre wie bei jedem anderen Stopp.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    if restprofil >= einstellung["notstopp_ab_restprofil"]:
        return False
    return seit_letztem_stopp >= einstellung["abstand_min_runden"]


def vorhersage(
    konfiguration: Konfiguration, wetter, runden: int, rundenzeit_ms: float
) -> tuple[float, ...]:
    """Die Naesse jeder Rennrunde aus dem Wetterverlauf.

    Das Wetter steht vor dem Rennen fest (GDD 7) - also kann die
    Strategie es kennen. Vorher wurde nur gegen die **Startlage** geplant;
    das kostete in einem nassen Zandvoort-Lauf allen 40 Autos das
    Mindestprofil, weil sie ein trockenes Rennen eingeplant hatten und in
    den Regen fuhren.

    Gefragt wird zur Mitte jeder Runde: Wer eine Runde zur Haelfte im
    Regen faehrt, faehrt sie nass.
    """
    if wetter is None:
        return (0.0,) * runden
    return tuple(
        kern_reifen.naesse_von(
            konfiguration, wetter.zustand_zu((n + 0.5) * rundenzeit_ms)
        )
        for n in range(runden)
    )


def verschleissvorhersage(
    konfiguration: Konfiguration, wetter, runden: int, rundenzeit_ms: float
) -> tuple[float, ...]:
    """Der Wetter-Verschleissfaktor jeder Rennrunde (GDD 7).

    Er gehoert zur Vorhersage wie die Naesse: Ein Regenrennen frisst die
    Reifen schneller, und wer das beim Planen nicht weiss, faehrt einen
    Plan, der auf dem Papier 30 Prozent Restprofil laesst und auf der
    Strecke bei null endet.
    """
    if wetter is None:
        return (1.0,) * runden
    return tuple(
        kern_wetter.verschleissfaktor(
            konfiguration, wetter.zustand_zu((n + 0.5) * rundenzeit_ms)
        )
        for n in range(runden)
    )


def gummivorhersage(
    konfiguration: Konfiguration,
    wetter,
    runden: int,
    rundenzeit_ms: float,
    autos: int = 1,
) -> tuple[float, ...]:
    """Der Verschleissfaktor der **Strecke** je Rennrunde (Punkt 90).

    Die gruene Strecke frisst Reifen, die eingegummierte schont sie. Der
    Stand zaehlt Auto-Runden, also steigt er mit der Feldgroesse: Ein
    Rennen mit vierzig Autos gummiert vierzigmal so schnell ein wie
    eine einsame Runde. Gefragt wird zur **Mitte** jeder Runde, wie bei
    der Naesse - das ist der beste einzelne Wert fuer eine Runde, in der
    der Stand ja weiter steigt.

    Der Auftraggeber hat entschieden, dass der Planer diesen Faktor
    kennt. Den wachsenden **Grip** kennt er nicht; der bleibt eine
    Ueberraschung der Strecke.
    """
    if wetter is None:
        return (1.0,) * runden
    stand = 0.0
    werte: list[float] = []
    for n in range(runden):
        lage = wetter.zustand_zu((n + 0.5) * rundenzeit_ms)
        schritt = kern_gummierung.stand_je_runde(konfiguration, autos, lage)
        werte.append(
            kern_gummierung.verschleissfaktor(
                konfiguration, max(0.0, stand + schritt / 2.0)
            )
        )
        stand = max(0.0, stand + schritt)
    return tuple(werte)


def lagen_im_rennen(konfiguration: Konfiguration, wetter, runden: int, rundenzeit_ms: float):
    """Welche Wetterlagen im Rennen ueberhaupt vorkommen.

    ``pflicht_zwei_mischungen`` braucht sie: Die Pflicht faellt, sobald
    das Rennen irgendwann nass wird - nicht erst, wenn es nass startet.
    """
    if wetter is None:
        return ("trocken",)
    gesehen: list[str] = []
    for n in range(runden):
        lage = wetter.zustand_zu((n + 0.5) * rundenzeit_ms)
        if lage not in gesehen:
            gesehen.append(lage)
    return tuple(gesehen)


def nach_notstopp(
    konfiguration: Konfiguration,
    strategie: Strategie,
    stelle: int,
    runde: int,
    runden: int,
) -> Strategie:
    """Schiebt den naechsten geplanten Stopp hinter einen Notstopp.

    Zwischen zwei Stopps liegen mindestens die Abstandsrunden. Passt der
    geplante Stopp danach nicht mehr ins Rennen, faellt er weg - das Auto
    hat ja eben frische Reifen bekommen.

    Beide Rennmodelle rufen dieselbe Funktion, damit Zeitraffer und
    Schnellmodus nach einem Wetterwechsel nicht auseinanderlaufen.
    """
    stopps = list(strategie.stopps)
    if stelle >= len(stopps):
        return strategie
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    frueheste = runde + einstellung["abstand_min_runden"]
    if stopps[stelle] >= frueheste:
        return strategie
    if frueheste > runden - einstellung["sperre_runden"]:
        return Strategie(
            mischungen=strategie.mischungen, stopps=tuple(stopps[:stelle])
        )
    stopps[stelle] = frueheste
    return Strategie(mischungen=strategie.mischungen, stopps=tuple(stopps))


def qualifyingmischung(konfiguration: Konfiguration, wetter) -> Mischung:
    """Womit im Qualifying gefahren wird (Punkt 39).

    Keine Wahl, sondern eine Regel des Auftraggebers: **Immer weich** -
    im Qualifying zaehlt eine einzige Runde, da nimmt jeder den
    schnellsten Satz. Nur wenn es nass ist, gilt etwas anderes:
    Intermediates bei wechselhaftem Wetter, Regenreifen bei Regen und
    Starkregen.

    Das Wetter des Qualifyings steht fest und ist hier nicht aenderbar;
    die Reifenwahl des Spielers gilt dem Rennen.
    """
    naesse = kern_reifen.naesse_von(konfiguration, wetter)
    if naesse <= 0.0:
        trocken = [m for m in kern_reifen.mischungen(konfiguration) if m.naesse == 0.0]
        return max(trocken, key=lambda m: m.tempo)
    return passende_mischung(konfiguration, naesse)


def passende_mischung(
    konfiguration: Konfiguration, naesse: float
) -> Mischung:
    """Die Mischung, die zu dieser Lage am besten passt.

    Bei gleicher Eignung die haltbarere: Wer gerade ausserplanmaessig
    hereinkommt, hat schon Zeit verloren und will nicht gleich wieder
    stoppen.
    """
    return _nach_eignung(konfiguration, naesse)[0]


def _nach_eignung(konfiguration: Konfiguration, naesse: float) -> list[Mischung]:
    """Die Mischungen, die am besten zur Lage passen, zuerst.

    Bei gleicher Eignung gewinnt die haltbarere: Die KI faehrt lieber
    einen Stopp weniger als eine Zehntel je Runde schneller.
    """
    alle = list(kern_reifen.mischungen(konfiguration))
    return sorted(alle, key=lambda m: (abs(m.naesse - naesse), m.verschleiss))


# ---------------------------------------------------------------------------
# Das ganze Feld vor dem Rennen
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Rennstrategien:
    """Was vor dem Rennen feststeht: zulaessige Varianten und die Wahl je Auto."""

    je_auto: tuple[Strategie, ...]
    varianten: tuple[Variante, ...]
    pflicht_zwei: bool
    rundenzeit_ms: float
    stoppverlust_ms: float
    lagen: tuple[str, ...]
    # Punkt 91: Je Auto der Platz der Variante, die es genommen hat -
    # ``-1`` fuer den Notfallplan. Daraus wird die Zahl oben im Rennen:
    # wie viele verschiedene Strategien ueberhaupt unterwegs sind.
    gewaehlt: tuple[int, ...] = ()

    @property
    def strategiezahl(self) -> int:
        """Wie viele verschiedene Varianten im Feld gefahren werden.

        Gezaehlt wird die **gewaehlte Variante**, nicht die gefahrene
        Stopprunde: Zwei Autos auf derselben Variante fahren dieselbe
        Strategie, auch wenn das Boxenstoppfenster ihre Stopps um eine
        Runde auseinanderzieht.
        """
        return len(set(self.gewaehlt))


def feldstrategien(
    konfiguration: Konfiguration,
    autos,
    strecke,
    runden: int,
    streckenfaktor: float,
    wetter,
    seedquelle: Seedquelle,
    liga: int | None = None,
) -> Rennstrategien:
    """Rechnet die Strategien eines ganzen Feldes vor dem Rennen.

    So hat es der Auftraggeber festgelegt: **Eine** Vorausberechnung
    entscheidet, welche Mischungsfolgen zulaessig sind; unter ihnen waehlt
    jedes Auto zufaellig.

    **Gerechnet wird mit dem Medianfahrer des Feldes** (Punkt 91), und
    zwar so, als waere das Auto allein auf der Strecke. Frueher setzte
    das staerkste Auto den Massstab und jedes Auto rechnete seine
    Stopprunden danach noch einmal mit den eigenen Werten nach. Das gab
    dreissig Abwandlungen statt einer Handvoll Strategien. Jetzt steht
    ein Satz zugelassener Varianten fest, die Autos ziehen daraus, und
    was ein einzelnes Auto vom Median abweicht, faengt im Rennen der
    Zwangsstopp ab.

    Das Wetter geht als **ganze Vorhersage** ein, nicht als Startlage. Es
    steht vor dem Rennen fest (GDD 7), also darf die Strategie es kennen.
    Dasselbe gilt fuer den Zustand der Strecke: Sie frisst am Anfang mehr
    Reifen als am Ende (Punkt 90), und der Planer weiss das.
    """
    if not autos:
        raise StrategieFehler("Ohne Autos gibt es keine Strategien")
    nach_wert = sorted(autos, key=lambda a: gesamtwert(konfiguration, a))
    referenz = nach_wert[len(nach_wert) // 2]
    grenzen = grenzen_aus(konfiguration, referenz)
    rundenzeit = float(
        kern_tempo.rundenzeit_ms(strecke, kern_tempo.geschwindigkeitsprofil(strecke, grenzen))
    )
    stoppverlust = float(
        kern_boxenstopp.durchfahrtsverlust_ms(
            konfiguration, strecke, grenzen, liga=liga
        )
        + kern_boxenstopp.haltverlust_ms(konfiguration, grenzen, liga)
        + kern_boxenstopp.mittlere_standzeit_ms(konfiguration)
    )
    naesse = vorhersage(konfiguration, wetter, runden, rundenzeit)
    wetterfaktor = verschleissvorhersage(konfiguration, wetter, runden, rundenzeit)
    gummifaktor = gummivorhersage(
        konfiguration, wetter, runden, rundenzeit, len(autos)
    )
    lagen = lagen_im_rennen(konfiguration, wetter, runden, rundenzeit)
    pflicht = pflicht_zwei_mischungen(konfiguration, lagen)

    moeglich = varianten(
        konfiguration, referenz, runden, rundenzeit, strecke.laenge_m, stoppverlust,
        streckenfaktor, wetterfaktor, naesse, pflicht, gummifaktor,
    )
    # Punkt 91: Jedes Auto bekommt den Plan des Medianfahrers - die
    # eigenen Werte gehen nicht mehr ein. Gewuerfelt wird nur noch,
    # **welche** der zugelassenen Varianten es faehrt und wohin das
    # Boxenstoppfenster ihre Stopprunden schiebt.
    gezogen = tuple(
        gewaehlte_strategie(
            konfiguration, referenz, runden, strecke.laenge_m,
            seedquelle.zweig("strategie", i),
            streckenfaktor, wetterfaktor, naesse, pflicht,
            rundenzeit, stoppverlust, moeglich, gummifaktor,
        )
        for i in range(len(autos))
    )
    return Rennstrategien(
        je_auto=tuple(s for s, _ in gezogen),
        varianten=tuple(moeglich),
        pflicht_zwei=pflicht,
        rundenzeit_ms=rundenzeit,
        stoppverlust_ms=stoppverlust,
        lagen=tuple(lagen),
        gewaehlt=tuple(n for _, n in gezogen),
    )
