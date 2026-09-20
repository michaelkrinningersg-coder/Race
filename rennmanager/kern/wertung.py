"""Meisterschaft, Auf- und Abstieg (GDD 13, Punkt 95).

Die Meisterschaft laeuft ueber **alle** Ligen. Jeder Platz jeder Liga hat
seine eigene Punktzahl auf einer durchgehenden Leiter:

    punkte(liga, platz) = sieger_liga1 - (liga - 1) * versatz - abstand(platz)

``abstand`` faellt innerhalb einer Liga: zehn Punkte vom Ersten zum
Zweiten, sechs vom Zweiten zum Dritten, danach drei je Platz. Der
``versatz`` ist der Abstand bis zum Ankerplatz - der Sieger einer Liga
bekommt genau so viel wie dieser Platz der Liga darueber. Dadurch
ueberlappen die Ligen: Mit den Werten aus der Konfiguration liegen zwoelf
Fahrer jeder Liga im Punktebereich der Liga ueber ihnen.

Dazu kommen Zusatzpunkte als Anteil der Siegerpunkte **derselben** Liga,
aufgerundet und mindestens 1: die schnellste Rennrunde (auch ohne
Zielankunft, GDD 13) und die ersten drei des Qualifyings.

Jeder der 40 Plaetze bekommt Punkte, auch die Ausgefallenen - sie stehen
nach absolvierten Runden und Zeit hinter den Angekommenen (siehe
``rennen._ergebnisse``).

Bei Gleichstand liegt vorn, wer in der hoeheren Liga faehrt; danach
entscheiden mehr Siege, mehr zweite Plaetze und so weiter.

Auf- und Abstieg laufen nicht erst am Saisonende, sondern alle fuenf
Rennen: Die besten drei einer Liga steigen auf, die letzten drei ab,
entschieden nach der Gesamttabelle seit Saisonbeginn. Liga 1 kennt keinen
Aufstieg, die unterste keinen Abstieg. Der Wechsel gilt fuer einzelne
Fahrer, nicht fuer Teams; die gesammelten Punkte wandern mit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class WertungsFehler(Exception):
    """Eine Wertung passt nicht zur Konfiguration."""


@dataclass(frozen=True)
class Rennergebnis:
    """Was ein Fahrer an einem Rennwochenende erreicht hat."""

    fahrer: int
    rennplatz: int
    qualifyingplatz: int
    schnellste_runde: bool = False
    ausgefallen: bool = False


@dataclass
class Eintrag:
    """Eine Zeile der Saisontabelle."""

    fahrer: int
    punkte: int = 0
    # Wie oft der Fahrer auf jedem Platz stand, Index 0 = Sieg.
    platzierungen: list[int] = field(default_factory=list)
    siege: int = 0
    podien: int = 0
    poles: int = 0
    schnellste_runden: int = 0
    ausfaelle: int = 0
    rennen: int = 0

    def zaehle(self, platz: int, autos: int) -> None:
        if len(self.platzierungen) < autos:
            self.platzierungen.extend([0] * (autos - len(self.platzierungen)))
        self.platzierungen[platz - 1] += 1


def abstand(konfiguration: Konfiguration, platz: int) -> int:
    """Wie viele Punkte dieser Platz hinter dem Sieger seiner Liga liegt."""
    if platz <= 1:
        return 0
    erster_zweiter = konfiguration.wert("wertung", "abstand_erster_zweiter")
    if platz == 2:
        return int(erster_zweiter)
    zweiter_dritter = konfiguration.wert("wertung", "abstand_zweiter_dritter")
    schritt = konfiguration.wert("wertung", "schritt")
    return int(erster_zweiter + zweiter_dritter + schritt * (platz - 3))


def versatz(konfiguration: Konfiguration) -> int:
    """Der Punktabstand von einer Liga zur naechsten.

    Er ist keine eigene Zahl, sondern der Abstand bis zum Ankerplatz: Der
    Sieger einer Liga bekommt so viel wie dieser Platz der Liga darueber.
    """
    return abstand(konfiguration, konfiguration.wert("wertung", "ankerplatz"))


def siegerpunkte(konfiguration: Konfiguration, liga: int) -> int:
    """Was ein Sieg in dieser Liga bringt - der Bezug aller Zusatzpunkte."""
    return int(
        konfiguration.wert("wertung", "sieger_liga1") - (liga - 1) * versatz(konfiguration)
    )


def rennpunkte(konfiguration: Konfiguration, liga: int, platz: int) -> int:
    """Punkte fuer eine Rennplatzierung in dieser Liga (GDD 13, Punkt 95).

    Jeder der Plaetze bekommt Punkte; ausserhalb des Feldes gibt es keine.
    """
    if not 1 <= platz <= konfiguration.wert("rennen", "autos"):
        return 0
    return siegerpunkte(konfiguration, liga) - abstand(konfiguration, platz)


def _anteilspunkte(konfiguration: Konfiguration, liga: int, anteil: float) -> int:
    """Ein Anteil der Siegerpunkte, aufgerundet, mindestens 1 (Punkt 95)."""
    return max(1, math.ceil(siegerpunkte(konfiguration, liga) * anteil - 1e-9))


def qualifyingpunkte(konfiguration: Konfiguration, liga: int, platz: int) -> int:
    """Punkte fuer einen Qualifying-Platz (GDD 13, Punkt 95)."""
    anteile = konfiguration.wert("wertung", "anteil_qualifying")
    if not 1 <= platz <= len(anteile):
        return 0
    return _anteilspunkte(konfiguration, liga, anteile[platz - 1])


def punkte_schnellste_runde(konfiguration: Konfiguration, liga: int) -> int:
    """Punkte fuer die schnellste Rennrunde, auch ohne Zielankunft."""
    return _anteilspunkte(
        konfiguration, liga, konfiguration.wert("wertung", "anteil_schnellste_runde")
    )


def punkte_fuer(konfiguration: Konfiguration, liga: int, ergebnis: Rennergebnis) -> int:
    """Alle Punkte eines Fahrers an einem Rennwochenende dieser Liga."""
    punkte = rennpunkte(konfiguration, liga, ergebnis.rennplatz)
    punkte += qualifyingpunkte(konfiguration, liga, ergebnis.qualifyingplatz)
    if ergebnis.schnellste_runde:
        punkte += punkte_schnellste_runde(konfiguration, liga)
    return punkte


@dataclass
class Tabelle:
    """Die Saisonwertung einer Liga."""

    liga: int
    eintraege: dict[int, Eintrag] = field(default_factory=dict)

    def verbuche(self, konfiguration: Konfiguration, ergebnisse: list[Rennergebnis]) -> None:
        """Traegt ein ganzes Rennwochenende ein.

        Gewertet wird mit den Punkten **dieser** Liga; ein Fahrer, der
        spaeter auf- oder absteigt, nimmt sie mit (siehe ``vollziehe``).
        """
        autos = konfiguration.wert("rennen", "autos")
        for ergebnis in ergebnisse:
            eintrag = self.eintraege.setdefault(ergebnis.fahrer, Eintrag(ergebnis.fahrer))
            eintrag.punkte += punkte_fuer(konfiguration, self.liga, ergebnis)
            eintrag.zaehle(ergebnis.rennplatz, autos)
            eintrag.rennen += 1
            if ergebnis.rennplatz == 1:
                eintrag.siege += 1
            if ergebnis.rennplatz <= 3:
                eintrag.podien += 1
            if ergebnis.qualifyingplatz == 1:
                eintrag.poles += 1
            if ergebnis.schnellste_runde:
                eintrag.schnellste_runden += 1
            if ergebnis.ausgefallen:
                eintrag.ausfaelle += 1

    def stand(self) -> list[Eintrag]:
        """Die Tabelle, bester zuerst (GDD 13).

        Bei Punktgleichheit entscheidet, wer mehr Siege hat, dann mehr
        zweite Plaetze und so weiter.
        """
        return sorted(
            self.eintraege.values(),
            key=lambda e: (-e.punkte, [-anzahl for anzahl in e.platzierungen], e.fahrer),
        )

    def platz_von(self, fahrer: int) -> int:
        for platz, eintrag in enumerate(self.stand(), start=1):
            if eintrag.fahrer == fahrer:
                return platz
        raise WertungsFehler(f"Fahrer {fahrer} steht nicht in der Tabelle der Liga {self.liga}")


# ---------------------------------------------------------------------------
# Live-Meisterschaftsstand (Punkt 73)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Livezeile:
    """Eine Zeile des Meisterschaftsstands waehrend eines Rennens.

    ``punkte`` ist der Stand **einschliesslich** der Punkte, die dieser
    Fahrer fuer seine derzeitige Position bekaeme; ``zuwachs`` sind genau
    diese Punkte. ``veraenderung`` sagt, wie viele Plaetze er in der
    Meisterschaft gewinnt oder verliert, wenn das Rennen so ausgeht -
    positiv heisst nach vorn.
    """

    fahrer: int
    platz: int
    punkte: int
    zuwachs: int
    platz_vorher: int
    punkte_vorher: int
    # Punkt 95: In welcher Liga dieser Fahrer steht. In der Ligasicht ist
    # das immer dieselbe, in der Weltsicht unterscheidet sie die Zeilen.
    liga: int = 0

    @property
    def veraenderung(self) -> int:
        return self.platz_vorher - self.platz


def livewertung(
    konfiguration: Konfiguration,
    tabelle: Tabelle,
    ergebnisse: list[Rennergebnis],
) -> list[Livezeile]:
    """Der Meisterschaftsstand, als waere das Rennen jetzt zu Ende.

    Rein rechnerisch und ohne Nebenwirkung: Die Tabelle bleibt, wie sie
    ist. Das Rennen laeuft ja noch - was hier steht, ist eine Vorschau auf
    den Stand, wenn es so ausginge. Erst am Rennende schreibt
    ``verbuche`` den Stand wirklich fort.

    Qualifyingpunkte und die schnellste Runde zaehlen mit, weil sie
    genauso in ``punkte_fuer`` stehen (GDD 13).

    :param tabelle: der Stand **vor** diesem Rennen
    :param ergebnisse: die derzeitige Lage im Rennen je Fahrer
    """
    vorher = {e.fahrer: platz for platz, e in enumerate(tabelle.stand(), start=1)}
    punkte_vorher = {f: e.punkte for f, e in tabelle.eintraege.items()}

    zuwachs = {e.fahrer: punkte_fuer(konfiguration, tabelle.liga, e) for e in ergebnisse}
    platzierungen = {e.fahrer: e.rennplatz for e in ergebnisse}
    beteiligt = set(punkte_vorher) | set(zuwachs)

    def schluessel(fahrer: int) -> tuple:
        # Wie ``stand``: Punkte zuerst; bei Gleichstand liegt vorn, wer im
        # laufenden Rennen weiter vorn ist - das ist die Zahl, die sich
        # gerade aendert.
        gesamt = punkte_vorher.get(fahrer, 0) + zuwachs.get(fahrer, 0)
        return (-gesamt, platzierungen.get(fahrer, 10**6), fahrer)

    zeilen = []
    for platz, fahrer in enumerate(sorted(beteiligt, key=schluessel), start=1):
        zeilen.append(
            Livezeile(
                fahrer=fahrer,
                platz=platz,
                punkte=punkte_vorher.get(fahrer, 0) + zuwachs.get(fahrer, 0),
                zuwachs=zuwachs.get(fahrer, 0),
                platz_vorher=vorher.get(fahrer, platz),
                punkte_vorher=punkte_vorher.get(fahrer, 0),
                liga=tabelle.liga,
            )
        )
    return zeilen


def weltlivewertung(
    konfiguration: Konfiguration,
    tabellen: dict[int, Tabelle],
    liga: int,
    ergebnisse: list[Rennergebnis],
) -> list[Livezeile]:
    """Die Meisterschaft ueber alle Ligen, waehrend ein Rennen laeuft.

    Wie ``livewertung``, nur ueber alle Tabellen: Zu den Punkten bis zu
    diesem Rennen kommt der Zuwachs der Fahrer, die gerade fahren.

    **Nur eine Liga faehrt.** Beim gefuehrten Wochenende laufen die
    uebrigen erst nach dem eigenen Rennen (siehe ``Wochenendlauf``);
    ihre Zeilen stehen hier deshalb auf dem Stand vor diesem Wochenende.
    Der Weltstand waehrend des Rennens ist damit eine Vorschau, die sich
    am Ende des Wochenendes noch einmal bewegt.

    Rein rechnerisch und ohne Nebenwirkung - die Tabellen bleiben, wie
    sie sind.
    """
    vorher = {
        eintrag.fahrer: platz
        for platz, (_liga, eintrag) in enumerate(
            weltstand(konfiguration, tabellen), start=1
        )
    }
    punkte_vorher: dict[int, int] = {}
    liga_von: dict[int, int] = {}
    platzierungen_vorher: dict[int, list[int]] = {}
    for nummer, tabelle in tabellen.items():
        for eintrag in tabelle.eintraege.values():
            punkte_vorher[eintrag.fahrer] = eintrag.punkte
            liga_von[eintrag.fahrer] = nummer
            platzierungen_vorher[eintrag.fahrer] = eintrag.platzierungen

    zuwachs = {e.fahrer: punkte_fuer(konfiguration, liga, e) for e in ergebnisse}
    platzierungen = {e.fahrer: e.rennplatz for e in ergebnisse}
    for fahrer in zuwachs:
        liga_von.setdefault(fahrer, liga)

    def schluessel(fahrer: int) -> tuple:
        # Wie ``weltstand``: Punkte, dann die hoehere Liga. Bei
        # Gleichstand innerhalb einer Liga entscheidet, wer im laufenden
        # Rennen weiter vorn ist - das ist die Zahl, die sich gerade
        # aendert; fuer die uebrigen Ligen die bisherigen Platzierungen.
        gesamt = punkte_vorher.get(fahrer, 0) + zuwachs.get(fahrer, 0)
        return (
            -gesamt,
            liga_von.get(fahrer, liga),
            platzierungen.get(fahrer, 10**6),
            [-anzahl for anzahl in platzierungen_vorher.get(fahrer, ())],
            fahrer,
        )

    beteiligt = set(punkte_vorher) | set(zuwachs)
    return [
        Livezeile(
            fahrer=fahrer,
            platz=platz,
            punkte=punkte_vorher.get(fahrer, 0) + zuwachs.get(fahrer, 0),
            zuwachs=zuwachs.get(fahrer, 0),
            platz_vorher=vorher.get(fahrer, platz),
            punkte_vorher=punkte_vorher.get(fahrer, 0),
            liga=liga_von.get(fahrer, liga),
        )
        for platz, fahrer in enumerate(sorted(beteiligt, key=schluessel), start=1)
    ]


# ---------------------------------------------------------------------------
# Auf- und Abstieg
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Wechsel:
    """Ein Fahrer wechselt die Liga (GDD 13)."""

    fahrer: int
    von_liga: int
    nach_liga: int

    @property
    def ist_aufstieg(self) -> bool:
        return self.nach_liga < self.von_liga


def auf_und_abstieg(
    konfiguration: Konfiguration, tabellen: dict[int, Tabelle]
) -> tuple[Wechsel, ...]:
    """Bestimmt alle Ligawechsel einer Wechselrunde (GDD 13, Punkt 95).

    Die Top 3 einer Liga steigen auf, die letzten 3 ab - entschieden nach
    der Gesamttabelle seit Saisonbeginn. Liga 1 kennt keinen Aufstieg, die
    unterste keinen Abstieg. Gewechselt wird alle ``alle_rennen`` Rennen;
    ``vollziehe`` traegt das Ergebnis in die Tabellen ein.
    """
    aufsteiger = konfiguration.wert("auf_abstieg", "aufsteiger")
    absteiger = konfiguration.wert("auf_abstieg", "absteiger")
    hoechste = 1
    niedrigste = konfiguration.wert("ligen", "anzahl")

    wechsel: list[Wechsel] = []
    for liga in sorted(tabellen):
        stand = tabellen[liga].stand()
        if liga > hoechste:
            for eintrag in stand[:aufsteiger]:
                wechsel.append(Wechsel(eintrag.fahrer, liga, liga - 1))
        if liga < niedrigste:
            for eintrag in stand[-absteiger:]:
                wechsel.append(Wechsel(eintrag.fahrer, liga, liga + 1))
    return tuple(wechsel)


def weltstand(
    konfiguration: Konfiguration, tabellen: dict[int, Tabelle]
) -> list[tuple[int, Eintrag]]:
    """Die Meisterschaft ueber alle Ligen, bester zuerst (Punkt 95).

    Geliefert werden Paare ``(liga, eintrag)``. Bei Punktgleichheit liegt
    vorn, wer in der hoeheren Liga faehrt - dort ist derselbe Punktestand
    gegen staerkere Gegner geholt. Danach gilt dieselbe Regel wie in der
    Ligatabelle: mehr Siege, dann mehr zweite Plaetze und so weiter.
    """
    del konfiguration  # die Regel steht fest, sie braucht keinen Wert
    paare = [
        (liga, eintrag)
        for liga, tabelle in tabellen.items()
        for eintrag in tabelle.eintraege.values()
    ]
    return sorted(
        paare,
        key=lambda paar: (
            -paar[1].punkte,
            paar[0],
            [-anzahl for anzahl in paar[1].platzierungen],
            paar[1].fahrer,
        ),
    )


def weltplatz_von(
    konfiguration: Konfiguration, tabellen: dict[int, Tabelle], fahrer: int
) -> int:
    """Der Platz eines Fahrers in der Meisterschaft ueber alle Ligen."""
    for platz, (_liga, eintrag) in enumerate(weltstand(konfiguration, tabellen), start=1):
        if eintrag.fahrer == fahrer:
            return platz
    raise WertungsFehler(f"Fahrer {fahrer} steht in keiner Tabelle")


def vollziehe(tabellen: dict[int, Tabelle], wechsel: tuple[Wechsel, ...]) -> None:
    """Traegt die Wechsel in die Tabellen ein (Punkt 95).

    Der Eintrag wandert mitsamt seinen Punkten in die neue Liga: Die
    Meisterschaft laeuft ueber alle Ligen, ein Aufstieg loescht also
    nichts. Ab dem naechsten Rennen zaehlt er nach der Leiter seiner
    neuen Liga.

    Erst werden alle Eintraege herausgenommen, dann alle eingesetzt -
    sonst schoebe ein Aufsteiger einen Absteiger derselben Runde aus der
    Tabelle, je nachdem, in welcher Reihenfolge die Wechsel stehen.
    """
    unterwegs: list[tuple[Wechsel, Eintrag]] = []
    for eintrag_wechsel in wechsel:
        tabelle = tabellen.get(eintrag_wechsel.von_liga)
        if tabelle is None or eintrag_wechsel.fahrer not in tabelle.eintraege:
            raise WertungsFehler(
                f"Fahrer {eintrag_wechsel.fahrer} steht nicht in Liga "
                f"{eintrag_wechsel.von_liga}"
            )
        unterwegs.append((eintrag_wechsel, tabelle.eintraege.pop(eintrag_wechsel.fahrer)))
    for eintrag_wechsel, eintrag in unterwegs:
        ziel = tabellen.get(eintrag_wechsel.nach_liga)
        if ziel is None:
            raise WertungsFehler(f"Liga {eintrag_wechsel.nach_liga} gibt es nicht")
        ziel.eintraege[eintrag.fahrer] = eintrag


def wechselrennen(konfiguration: Konfiguration) -> int:
    """Nach wie vielen Rennen auf- und abgestiegen wird (Punkt 95)."""
    return int(konfiguration.wert("auf_abstieg", "alle_rennen"))


def ist_wechselrennen(konfiguration: Konfiguration, rennen: int) -> bool:
    """Ob nach diesem Rennen gewechselt wird."""
    takt = wechselrennen(konfiguration)
    return takt > 0 and rennen > 0 and rennen % takt == 0


def pruefe_ligastaerken(konfiguration: Konfiguration, tabellen: dict[int, Tabelle]) -> None:
    """Prueft, dass jede Liga voll besetzt ist - sonst geht der Wechsel schief."""
    erwartet = konfiguration.wert("ligen", "autos_je_liga")
    for liga, tabelle in tabellen.items():
        if len(tabelle.eintraege) != erwartet:
            raise WertungsFehler(
                f"Liga {liga} hat {len(tabelle.eintraege)} Fahrer, erwartet {erwartet}"
            )
