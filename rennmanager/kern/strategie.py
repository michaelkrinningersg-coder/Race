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
from typing import TYPE_CHECKING

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
) -> Strategie:
    """Die Strategie eines KI-Autos - jedes faehrt seine eigene.

    Der Auftraggeber hat es so festgelegt:

    * Die KI **erkennt die passende Mischung**, faehrt aber nicht alle
      dieselbe. Ohne Streuung kam gemessen das ganze Feld mit derselben
      Folge heraus, und die Boxengasse waere ein Stau statt einer
      Entscheidung.
    * Ob beim Stopp **erst der kurze und dann der lange Stint** kommt
      oder umgekehrt, ist Zufall. Im Trockenen ist die Reihenfolge der
      Mischungen frei.
    * Die **Stintlaenge folgt der Reifenwahl**: Wer auf Hart faehrt,
      bleibt laenger draussen als der auf Weich. Dazu ein zufaelliges
      Delta im Boxenstoppfenster.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    wuerfel = seedquelle.generator()

    passend = _nach_eignung(konfiguration, naesse)
    reichweiten = {
        m.schluessel: reichweite_runden(
            konfiguration, auto, m, rundenlaenge_m, streckenfaktor, wetterfaktor, naesse
        )
        for m in passend
    }
    # Nur Mischungen, die zur Lage passen. Im Trockenen sind das die drei
    # Trockenmischungen, im Starkregen nur der Regenreifen - eine
    # Mischung, die zu weit danebenliegt, faehrt niemand freiwillig.
    # Ohne diese Grenze kamen gemessen Folgen wie H-I-W-I im Trockenen
    # heraus, und ein Intermediate kostet dort 6 % Tempo.
    grenze = konfiguration.wert("boxenstopp", "strategie", "eignungsgrenze")
    brauchbar = [m for m in passend if abs(m.naesse - naesse) <= grenze] or passend[:1]

    folge = _waehle_folge(
        konfiguration, brauchbar, reichweiten, runden, wuerfel, pflicht_zwei
    )
    stopps = _setze_stopps(einstellung, folge, reichweiten, runden, wuerfel)
    return Strategie(mischungen=tuple(folge), stopps=tuple(stopps))


def _waehle_folge(
    konfiguration: Konfiguration,
    brauchbar: list[Mischung],
    reichweiten: dict[str, int],
    runden: int,
    wuerfel,
    pflicht_zwei: bool,
) -> list[Mischung]:
    """Wuerfelt eine Mischungsfolge, die das Rennen traegt.

    Gesucht ist eine Folge, deren Reichweiten zusammen ueber die
    Renndistanz reichen und die die Pflicht zu zwei Mischungen erfuellt.
    Unter den erlaubten wird gewuerfelt - deshalb faehrt nicht das ganze
    Feld dasselbe.
    """
    einstellung = konfiguration.wert("boxenstopp", "strategie")
    kleinste = einstellung["stopps_min"]
    groesste = einstellung["stopps_max"]

    moeglich: list[list[Mischung]] = []
    for stopps in range(kleinste, groesste + 1):
        for _ in range(40):
            folge = [
                brauchbar[int(wuerfel.integers(0, len(brauchbar)))]
                for _ in range(stopps + 1)
            ]
            if pflicht_zwei and len({m.schluessel for m in folge}) < 2:
                continue
            if sum(reichweiten[m.schluessel] for m in folge) >= runden:
                moeglich.append(folge)
                break
    if not moeglich:
        # Notfall: die haltbarste Mischung, so oft wie erlaubt.
        zaeh = min(brauchbar, key=lambda m: m.verschleiss)
        andere = max(brauchbar, key=lambda m: m.verschleiss)
        folge = [zaeh] * (groesste + 1)
        if pflicht_zwei and len(folge) > 1:
            folge[-1] = andere
        return folge

    gewaehlt = list(moeglich[int(wuerfel.integers(0, len(moeglich)))])
    # Die Reihenfolge ist frei: ob erst der kurze oder erst der lange
    # Stint kommt, entscheidet der Zufall.
    wuerfel.shuffle(gewaehlt)
    return gewaehlt


def _setze_stopps(
    einstellung: dict,
    folge: list[Mischung],
    reichweiten: dict[str, int],
    runden: int,
    wuerfel,
) -> list[int]:
    """Die Stopprunden - Stintlaenge aus der Reifenwahl plus Streuung."""
    sperre = einstellung["sperre_runden"]
    fenster = einstellung["ki_fenster_runden"]
    frueheste = sperre + 1
    spaeteste = runden - sperre

    # Die Stints verhalten sich wie die Reichweiten ihrer Mischungen.
    anteile = [max(reichweiten[m.schluessel], 1) for m in folge]
    summe = sum(anteile)

    gesetzt: list[int] = []
    gelaufen = 0.0
    for anteil in anteile[:-1]:
        gelaufen += runden * anteil / summe
        versatz = float(wuerfel.uniform(-fenster / 2.0, fenster / 2.0))
        runde = int(round(gelaufen + versatz))
        runde = max(frueheste, min(runde, spaeteste))
        while runde in gesetzt and runde < spaeteste:
            runde += 1
        while runde in gesetzt and runde > frueheste:
            runde -= 1
        gesetzt.append(runde)
    return sorted(gesetzt)


def _nach_eignung(konfiguration: Konfiguration, naesse: float) -> list[Mischung]:
    """Die Mischungen, die am besten zur Lage passen, zuerst.

    Bei gleicher Eignung gewinnt die haltbarere: Die KI faehrt lieber
    einen Stopp weniger als eine Zehntel je Runde schneller.
    """
    alle = list(kern_reifen.mischungen(konfiguration))
    return sorted(alle, key=lambda m: (abs(m.naesse - naesse), m.verschleiss))
