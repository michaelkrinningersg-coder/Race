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
from itertools import combinations_with_replacement, permutations
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern.auto import Auto
from rennmanager.kern.reifen import Mischung
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


def _stinttabelle(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    runden: int,
    rundenzeit_ms: float,
    rundenlaenge_m: float,
    streckenfaktor: float,
    wetterfaktor: float,
    naesse: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Zeit und Restprofil nach n Runden auf diesem Satz.

    Runde fuer Runde gerechnet, weil die Gripkurve ihr Optimum bei 80 %
    hat: Ein Stint ist am Anfang und am Ende langsamer als in der Mitte,
    und das laesst sich nicht mitteln.
    """
    je_runde = (
        kern_reifen.verschleiss_je_meter(
            konfiguration, auto, misch, streckenfaktor, wetterfaktor, naesse
        )
        * rundenlaenge_m
    )
    mischfaktor = kern_reifen.mischungsfaktor(konfiguration, misch, naesse)
    zeiten = np.zeros(runden + 1)
    rest = np.ones(runden + 1)
    verschleiss = 0.0
    for n in range(1, runden + 1):
        tempo = kern_reifen.tempofaktor(konfiguration, auto, verschleiss)
        zeiten[n] = zeiten[n - 1] + rundenzeit_ms / max(mischfaktor * tempo, 1e-6)
        verschleiss += je_runde
        rest[n] = kern_reifen.zustand(verschleiss)
    return zeiten, rest


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
    naesse: float = 0.0,
    tabellen: dict[str, tuple[np.ndarray, np.ndarray]] | None = None,
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
                streckenfaktor, wetterfaktor, naesse,
            )
            for misch in set(folge)
        }
    genommen = [tabellen[m.schluessel] for m in folge]
    # Wie lang ein Stint hoechstens sein darf, ohne unter das
    # Mindestrestprofil zu fallen.
    grenzen = [int(np.count_nonzero(rest >= mindest) - 1) for _, rest in genommen]
    if sum(grenzen) < runden:
        return None

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
    for stelle, ((zeiten, _rest), grenze) in enumerate(zip(genommen, grenzen, strict=True)):
        letzter = stelle == len(folge) - 1
        naechste = np.full(runden + 1, unendlich)
        woher = np.zeros(runden + 1, dtype=int)
        aufschlag = 0.0 if letzter else stoppverlust_ms
        # Ein Stint zwischen zwei Stopps muss den Mindestabstand tragen.
        kuerzeste = 1 if (stelle == 0 or letzter) else abstand
        for laenge in range(kuerzeste, grenze + 1):
            ziel = np.arange(laenge, runden + 1)
            if not letzter:
                ziel = ziel[erlaubt[ziel]]
                if not len(ziel):
                    continue
            kandidat = beste[ziel - laenge] + zeiten[laenge] + aufschlag
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


def _reihenfolgen(eine: Variante, runden: int) -> list[Variante]:
    """Alle Reihenfolgen einer Zusammenstellung, mit ihren Stopprunden.

    Im Trockenen ist die Reihenfolge frei - ob erst der kurze oder erst
    der lange Stint kommt, entscheidet der Fahrer. Die Rennzeit ist
    dieselbe, die Stopprunden sind es nicht: Wer den langen Stint
    vorzieht, stoppt spaeter.
    """
    laengen: list[int] = []
    vorher = 0
    for runde in eine.stopps:
        laengen.append(runde - vorher)
        vorher = runde
    laengen.append(runden - vorher)

    paare = list(zip(eine.mischungen, laengen, strict=True))
    gesehen: set[tuple[str, ...]] = set()
    ergebnis: list[Variante] = []
    for reihenfolge in permutations(range(len(paare))):
        mischungen = tuple(paare[i][0] for i in reihenfolge)
        schluessel = tuple(m.schluessel for m in mischungen)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        stopps: list[int] = []
        gelaufen = 0
        for i in reihenfolge[:-1]:
            gelaufen += paare[i][1]
            stopps.append(gelaufen)
        ergebnis.append(
            Variante(mischungen=mischungen, stopps=tuple(stopps), zeit_ms=eine.zeit_ms)
        )
    return ergebnis


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
    brauchbar = [
        m
        for m in _nach_eignung(konfiguration, naesse)
        if abs(m.naesse - naesse) <= einstellung["eignungsgrenze"]
    ] or _nach_eignung(konfiguration, naesse)[:1]

    # Die Stinttabellen haengen nur an der Mischung, nicht an der Folge -
    # einmal gebaut, gelten sie fuer alle. Ohne das rechnete jede der 117
    # Folgen ihre vier Tabellen neu, und ein Auto brauchte eine halbe
    # Sekunde statt weniger Millisekunden.
    tabellen = {
        misch.schluessel: _stinttabelle(
            konfiguration, auto, misch, runden, rundenzeit_ms, rundenlaenge_m,
            streckenfaktor, wetterfaktor, naesse,
        )
        for misch in brauchbar
    }

    # Die Rennzeit haengt nur davon ab, **welche** Reifen gefahren werden,
    # nicht in welcher Reihenfolge: Ein Stint kostet, was er kostet, egal
    # ob er der erste oder der letzte ist. Gerechnet wird deshalb einmal
    # je Zusammenstellung, und die Reihenfolgen erben das Ergebnis - aus
    # 117 Folgen werden 31 Rechnungen.
    gefunden = _suche(
        konfiguration, auto, brauchbar, tabellen, runden, rundenzeit_ms,
        rundenlaenge_m, stoppverlust_ms, streckenfaktor, wetterfaktor, naesse,
        pflicht_zwei, einstellung["stopps_max"],
    )
    if not gefunden:
        # Geht es mit drei Stopps nicht auf, darf ein vierter dazu. Das ist
        # dann das Maximum - so hat es der Auftraggeber festgelegt.
        gefunden = _suche(
            konfiguration, auto, brauchbar, tabellen, runden, rundenzeit_ms,
            rundenlaenge_m, stoppverlust_ms, streckenfaktor, wetterfaktor, naesse,
            pflicht_zwei, einstellung["stopps_max_notfall"],
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
) -> list[Variante]:
    """Alle tragfaehigen Varianten bis zu dieser Stoppzahl."""
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    gefunden: list[Variante] = []
    for stopps in range(einstellung["stopps_min"], hoechstens + 1):
        for satz in combinations_with_replacement(brauchbar, stopps + 1):
            if pflicht_zwei and len({m.schluessel for m in satz}) < 2:
                continue
            eine = bewerte(
                konfiguration, auto, satz, runden, rundenzeit_ms, rundenlaenge_m,
                stoppverlust_ms, streckenfaktor, wetterfaktor, naesse,
                tabellen=tabellen,
            )
            if eine is None:
                continue
            gefunden.extend(_reihenfolgen(eine, runden))
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
) -> Strategie:
    """Die Strategie eines KI-Autos.

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
        # Notfall: die haltbarste Mischung, so oft wie erlaubt.
        passend = _nach_eignung(konfiguration, naesse)
        zaeh = min(passend, key=lambda m: m.verschleiss)
        folge = [zaeh, max(passend, key=lambda m: m.verschleiss)]
        mitte = max(min(runden // 2, runden - 3), 4)
        return Strategie(mischungen=tuple(folge), stopps=(mitte,))

    gewaehlt = moeglich[int(wuerfel.integers(0, len(moeglich)))]
    return Strategie(
        mischungen=gewaehlt.mischungen,
        stopps=_mit_fenster(konfiguration, gewaehlt.stopps, runden, wuerfel),
    )


def _mit_fenster(
    konfiguration: Konfiguration, stopps: tuple[int, ...], runden: int, wuerfel
) -> tuple[int, ...]:
    """Legt das Zufallsfenster auf die berechneten Stopprunden.

    Das Fenster ist +/- 5 % der Renndistanz, aufgerundet, mindestens zwei
    Runden - aber nur, solange der Mindestabstand von drei Runden zwischen
    zwei Stopps gewahrt bleibt. Sonst kaeme ein Auto zweimal kurz
    hintereinander herein und verloere das Rennen in der Boxengasse.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    sperre = einstellung["sperre_runden"]
    abstand = einstellung["abstand_min_runden"]
    fenster = max(
        math.ceil(einstellung["fenster_anteil"] * runden),
        einstellung["fenster_min_runden"],
    )

    verschoben: list[int] = []
    for stelle, runde in enumerate(stopps):
        versatz = int(round(float(wuerfel.uniform(-fenster, fenster))))
        neu = runde + versatz
        untere = sperre + 1
        if verschoben:
            untere = max(untere, verschoben[-1] + abstand)
        obere = runden - sperre
        if stelle + 1 < len(stopps):
            # Fuer die noch folgenden Stopps muss Platz bleiben.
            obere = min(obere, runden - sperre - abstand * (len(stopps) - stelle - 1))
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
) -> bool:
    """Ob ein Auto wegen des Wetters ausserplanmaessig hereinkommen muss.

    Der Auftraggeber hat die Frist gesetzt: **hoechstens drei Runden auf
    dem falschen Reifen**, und **mindestens drei Runden zwischen zwei
    Stopps**. Ohne die zweite Bedingung kaeme ein Auto bei einem schnellen
    Wechsel zweimal hintereinander herein und verloere das Rennen an der
    Boxengasse statt auf der Strecke.

    Falsch ist ein Reifen, wenn er weiter von der Lage entfernt ist, als
    die Eignungsgrenze zulaesst - also genau die Mischungen, die die KI
    fuer diese Lage gar nicht erst gewaehlt haette.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    if abs(gefahren.naesse - naesse) <= einstellung["eignungsgrenze"]:
        return False
    return seit_letztem_stopp >= einstellung["abstand_min_runden"]


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
