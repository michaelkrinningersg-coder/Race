"""Einzelereignisse (GDD 14).

"Ereignisse werden beim Tageswechsel ausgeloest, 0-2 je 14-Tage-Zyklus,
und betreffen Spieler und KI gleichermassen. Sie wirken zeitweise oder -
klein - dauerhaft; 'Rennwochenende' meint immer ein Rennwochenende.
Ausgeloest werden sie nur in den ersten 4 Tagen eines Zyklus."

Umfang: Entschieden am 2026-09-17 werden Ereignisse vorerst nur fuer den
Spieler gewuerfelt (``[ereignisse.umfang] gilt_fuer_ki = false``). Die
Begruendung steht in OFFENE_PUNKTE.md, Punkt 36.

Die 35 Ereignisse aus GDD 14 kennen sechs Dauerarten und fuenf
Wirkungsarten. Dauerhafte Wirkungen aendern den Wert selbst, alle uebrigen
sind Faktoren, die nur solange gelten, wie das Ereignis laeuft:

===================  ====================================================
Dauer                Wann es endet
===================  ====================================================
``rennwochenenden``  nach so vielen Rennwochenenden
``zyklen``           nach so vielen 14-Tage-Zyklen
``nur_qualifying``   gilt nur im Qualifying des naechsten Wochenendes
``bis_reparatur``    erst wenn der Spieler dafuer zahlt (wie ein Defekt)
``sofort``           wirkt einmalig und laeuft nie
``dauerhaft``        aendert den Wert selbst und laeuft nie
===================  ====================================================

Ein einzelnes Ereignis kann beides mischen: E23 Hitzetraining hebt die
Hitzeresistenz dauerhaft und senkt D2 fuer ein Rennwochenende.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from rennmanager.kern.kalender import Saison
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Ziele, die keine Faehigkeit sind, sondern anderswo wirken.
GELD = "geld"
ERFAHRUNG = "erfahrung"
TAGESFORM = "tagesform_mittelwert"
STRECKENKENNTNIS = "streckenkenntnis_naechste"
KALENDERTAGE = "kalendertage"
FAHRERTRAINING = "fahrertraining"

SONDERZIELE = frozenset({GELD, ERFAHRUNG, TAGESFORM, STRECKENKENNTNIS, KALENDERTAGE})

QUALIFYING = "qualifying"
RENNEN = "rennen"


class EreignisFehler(Exception):
    """Das Ereignis passt nicht zur Konfiguration."""


class Dauer(Enum):
    """Wie lange ein Ereignis wirkt (GDD 14)."""

    RENNWOCHENENDEN = "rennwochenenden"
    ZYKLEN = "zyklen"
    NUR_QUALIFYING = "nur_qualifying"
    BIS_REPARATUR = "bis_reparatur"
    SOFORT = "sofort"
    DAUERHAFT = "dauerhaft"

    @property
    def bezeichnung(self) -> str:
        return {
            Dauer.RENNWOCHENENDEN: "Rennwochenenden",
            Dauer.ZYKLEN: "Zyklen",
            Dauer.NUR_QUALIFYING: "nur Qualifying",
            Dauer.BIS_REPARATUR: "bis zur Reparatur",
            Dauer.SOFORT: "sofort",
            Dauer.DAUERHAFT: "dauerhaft",
        }[self]


@dataclass(frozen=True)
class Ausloesung:
    """Ein fuer einen Tag eingeplantes Ereignis (GDD 14)."""

    datum: dt.date
    schluessel: str


@dataclass
class Aktiv:
    """Ein laufendes Ereignis eines Fahrers."""

    schluessel: str
    name: str
    ausgeloest_am: dt.date
    dauer: Dauer
    # Verbleibende Rennwochenenden bzw. Zyklen; bei den uebrigen Dauerarten
    # ohne Bedeutung.
    rest: int
    wirkung: tuple[dict, ...]

    @property
    def laeuft(self) -> bool:
        if self.dauer is Dauer.BIS_REPARATUR:
            return True
        if self.dauer in (Dauer.SOFORT, Dauer.DAUERHAFT):
            return False
        return self.rest > 0

    @property
    def reparierbar(self) -> bool:
        return self.dauer is Dauer.BIS_REPARATUR

    def beschreibung(self, konfiguration: Konfiguration) -> str:
        """Was das Ereignis bewirkt, in einem Satz fuer die Anzeige."""
        teile = [_wirkungstext(konfiguration, w) for w in self.wirkung]
        return ", ".join(teil for teil in teile if teil)


def _wirkungstext(konfiguration: Konfiguration, wirkung: dict) -> str:
    ziel = wirkung["ziel"]
    if wirkung.get("sperre"):
        return f"{ziel} gesperrt"
    if wirkung.get("einmalig"):
        return "einmalig Geld" if ziel == GELD else "einmalig Erfahrung"
    if "absolut" in wirkung:
        return f"{ziel} {wirkung['absolut']:+d}"
    anteil = wirkung.get("faktor", 0.0)
    text = f"{ziel} {anteil * 100:+.1f} %".replace(".0 %", " %")
    return text + " dauerhaft" if wirkung.get("dauerhaft") else text


# ---------------------------------------------------------------------------
# Katalog
# ---------------------------------------------------------------------------
def liste(konfiguration: Konfiguration) -> tuple[dict, ...]:
    """Die 35 Ereignisse aus GDD 14."""
    return tuple(konfiguration.wert("ereignisse", "liste"))


def eintrag(konfiguration: Konfiguration, schluessel: str) -> dict:
    for e in liste(konfiguration):
        if e["schluessel"] == schluessel:
            return e
    raise EreignisFehler(f"Unbekanntes Ereignis: {schluessel}")


def dauer_von(eintrag_: dict) -> Dauer:
    try:
        return Dauer(eintrag_["dauer"]["art"])
    except ValueError:
        raise EreignisFehler(
            f"Unbekannte Dauerart: {eintrag_['dauer']['art']}"
        ) from None


def ist_dauerhaft(eintrag_: dict, wirkung: dict) -> bool:
    """Ob diese Einzelwirkung den Wert selbst aendert (GDD 14).

    Entweder weil das ganze Ereignis dauerhaft ist oder weil die Wirkung
    es fuer sich beansprucht - E23 Hitzetraining hat beides.
    """
    return dauer_von(eintrag_) is Dauer.DAUERHAFT or bool(wirkung.get("dauerhaft"))


def dauerhafter_zuwachs(konfiguration: Konfiguration, wert: int, faktor: float) -> int:
    """Wie stark eine dauerhafte Prozentwirkung den Wert aendert.

    Entscheidung zu Punkt 34: max(+10, +1 % vom Wert), wie ein
    Entwicklungstag in GDD 2. Bei abweichenden Prozentsaetzen skaliert der
    Mindestschritt mit, damit die Ereignisse im Verhaeltnis bleiben.
    """
    einstellung = konfiguration.wert("ereignisse", "dauerhaft")
    mindest = einstellung["mindestschritt"] * abs(faktor) / einstellung["bezugsanteil"]
    betrag = max(abs(faktor) * max(wert, 0), mindest)
    return int(round(betrag)) * (1 if faktor >= 0 else -1)


def betrag(konfiguration: Konfiguration, schluessel: str) -> float:
    """Anteil an Siegpraemie bzw. Sieg-Erfahrung (Entscheidung zu Punkt 20)."""
    betraege = konfiguration.wert("ereignisse", "betraege")
    if schluessel not in betraege:
        raise EreignisFehler(f"Fuer {schluessel} ist kein Betrag hinterlegt")
    return float(betraege[schluessel])


# ---------------------------------------------------------------------------
# Auslosung
# ---------------------------------------------------------------------------
def zyklen(konfiguration: Konfiguration, saison: Saison) -> tuple[tuple[dt.date, ...], ...]:
    """Die 14-Tage-Zyklen eines Jahres, fuer Ereignisse (GDD 14).

    GDD 14 zaehlt Ereignisse je 14-Tage-Zyklus. Waehrend der Saison sind
    das die Abstaende zwischen zwei Rennen; Vor- und Nachsaison kennt
    GDD 2 dagegen nicht als Zyklen, obwohl sie zusammen rund ein Viertel
    des Jahres ausmachen. Damit dort nicht monatelang nichts passiert,
    laeuft ueber das ganze Jahr dasselbe 14-Tage-Raster. Verankert ist es
    am Tag nach dem ersten Rennen, sodass jeder Zyklus genau am Renntag
    endet und sein Ausloesefenster immer in die freien Tage danach faellt.
    """
    abstand = konfiguration.wert("kalender", "abstand_tage")
    anker = saison.erstes_rennen + dt.timedelta(days=1)
    nach_nummer: dict[int, list[dt.date]] = {}
    for tag in saison.tage:
        nummer = (tag.datum - anker).days // abstand
        nach_nummer.setdefault(nummer, []).append(tag.datum)
    return tuple(tuple(nach_nummer[nummer]) for nummer in sorted(nach_nummer))


def zyklusnummer(konfiguration: Konfiguration, saison: Saison, datum: dt.date) -> int:
    """In welchem 14-Tage-Zyklus dieser Tag liegt, ab 0 gezaehlt."""
    abstand = konfiguration.wert("kalender", "abstand_tage")
    anker = saison.erstes_rennen + dt.timedelta(days=1)
    erster = (saison.tage[0].datum - anker).days // abstand
    return (datum - anker).days // abstand - erster


def plane_zyklus(
    konfiguration: Konfiguration,
    tage: tuple[dt.date, ...],
    seedquelle: Seedquelle,
) -> tuple[Ausloesung, ...]:
    """Legt fest, welche Ereignisse in diesem Zyklus an welchem Tag kommen.

    GDD 14: 0 bis 2 je Zyklus, ausgeloest nur in den ersten vier Tagen.
    Gezogen wird gleichverteilt und ohne Zuruecklegen - sonst traefe
    dieselbe Erkaeltung zweimal in vier Tagen.
    """
    einstellung = konfiguration.wert("ereignisse")
    if not tage:
        return ()
    fenster = tage[: einstellung["ausloesefenster_tage"]]

    wuerfel = seedquelle.generator()
    anzahl = int(wuerfel.integers(einstellung["je_zyklus_min"], einstellung["je_zyklus_max"] + 1))
    if anzahl <= 0:
        return ()

    alle = [e["schluessel"] for e in liste(konfiguration)]
    ohne_zuruecklegen = konfiguration.wert(
        "ereignisse", "auswahl", "ohne_zuruecklegen_je_zyklus"
    )
    gezogen = list(
        wuerfel.choice(alle, size=min(anzahl, len(alle)), replace=not ohne_zuruecklegen)
    )
    tagesnummern = wuerfel.integers(0, len(fenster), size=len(gezogen))

    return tuple(
        Ausloesung(datum=fenster[int(nummer)], schluessel=str(schluessel))
        for nummer, schluessel in zip(tagesnummern, gezogen, strict=True)
    )


def plane_saison(
    konfiguration: Konfiguration, saison: Saison, seedquelle: Seedquelle
) -> dict[dt.date, tuple[str, ...]]:
    """Alle Ereignisse einer Saison, nach Tag geordnet.

    Wird einmal beim Karrierestart gebildet: So haengt die Auslosung nur am
    Seed und nicht daran, wie oft der Spieler einen Tag weiterschaltet.
    """
    nach_tag: dict[dt.date, list[str]] = {}
    for nummer, tage in enumerate(zyklen(konfiguration, saison)):
        for ausloesung in plane_zyklus(
            konfiguration, tage, seedquelle.zweig("zyklus", nummer)
        ):
            nach_tag.setdefault(ausloesung.datum, []).append(ausloesung.schluessel)
    return {datum: tuple(schluessel) for datum, schluessel in nach_tag.items()}


# ---------------------------------------------------------------------------
# Laufende Ereignisse
# ---------------------------------------------------------------------------
@dataclass
class Lage:
    """Alle Ereignisse, die einen Fahrer gerade betreffen (GDD 14)."""

    konfiguration: Konfiguration
    aktive: list[Aktiv] = field(default_factory=list)
    # Ereignisse, die nur im naechsten Qualifying gelten, laufen erst mit
    # dem Rennwochenende ab; bis dahin stehen sie hier mit drin.

    # -- Auslesen ----------------------------------------------------------
    @property
    def laufende(self) -> tuple[Aktiv, ...]:
        return tuple(a for a in self.aktive if a.laeuft)

    @property
    def offene_reparaturen(self) -> tuple[Aktiv, ...]:
        return tuple(a for a in self.aktive if a.reparierbar)

    def faktoren(self, session: str = RENNEN) -> dict[str, float]:
        """Faktoren je Faehigkeit, die gerade gelten.

        :param session: ``"qualifying"`` oder ``"rennen"``; Ereignisse mit
            der Dauer ``nur_qualifying`` gelten nur im Qualifying.
        """
        werte: dict[str, float] = {}
        for a in self.laufende:
            if a.dauer is Dauer.NUR_QUALIFYING and session != QUALIFYING:
                continue
            for wirkung in a.wirkung:
                ziel = wirkung["ziel"]
                if ziel in SONDERZIELE or ziel == FAHRERTRAINING:
                    continue
                if wirkung.get("sperre") or wirkung.get("einmalig"):
                    continue
                if wirkung.get("dauerhaft"):
                    # Schon in den Wert eingerechnet.
                    continue
                werte[ziel] = werte.get(ziel, 1.0) * (1.0 + wirkung.get("faktor", 0.0))
        return werte

    def gesperrt(self) -> frozenset[str]:
        """Was sich gerade nicht entwickeln laesst (E2, E6)."""
        return frozenset(
            wirkung["ziel"]
            for a in self.laufende
            for wirkung in a.wirkung
            if wirkung.get("sperre")
        )

    def tagesformbonus(self) -> float:
        """Zuschlag auf den Tagesform-Mittelwert (E3)."""
        return sum(
            wirkung.get("faktor", 0.0)
            for a in self.laufende
            for wirkung in a.wirkung
            if wirkung["ziel"] == TAGESFORM
        )

    def streckenkenntnisbonus(self) -> float:
        """Zuschlag auf die Streckenkenntnis der naechsten Strecke (E10)."""
        return sum(
            wirkung.get("faktor", 0.0)
            for a in self.laufende
            for wirkung in a.wirkung
            if wirkung["ziel"] == STRECKENKENNTNIS
        )

    def fehlende_kalendertage(self) -> int:
        """Nutzbare Tage, die dieser Zyklus verliert (E29).

        Entschieden: Es fallen die naechsten nutzbaren Tage weg, nicht die
        vor dem Rennen - getroffen wird die Kapazitaet aus GDD 2.
        """
        return -sum(
            int(wirkung.get("absolut", 0))
            for a in self.laufende
            for wirkung in a.wirkung
            if wirkung["ziel"] == KALENDERTAGE
        )

    # -- Fortschreiben -----------------------------------------------------
    def loese_aus(self, schluessel: str, datum: dt.date) -> Aktiv:
        """Startet ein Ereignis; ein laufendes wird aufgefrischt."""
        e = eintrag(self.konfiguration, schluessel)
        dauer = dauer_von(e)
        neu = Aktiv(
            schluessel=schluessel,
            name=e["name"],
            ausgeloest_am=datum,
            dauer=dauer,
            # "nur Qualifying" nennt keine Anzahl; gemeint ist das
            # naechste Rennwochenende, also eines.
            rest=int(e["dauer"].get("anzahl", 1 if dauer is Dauer.NUR_QUALIFYING else 0)),
            wirkung=tuple(e["wirkung"]),
        )
        vorher = next((a for a in self.aktive if a.schluessel == schluessel), None)
        if vorher is not None:
            self.aktive.remove(vorher)
        self.aktive.append(neu)
        return neu

    def nach_rennwochenende(self) -> None:
        """Zaehlt die Ereignisse herunter, die in Rennwochenenden laufen."""
        for a in self.aktive:
            if a.dauer in (Dauer.RENNWOCHENENDEN, Dauer.NUR_QUALIFYING):
                a.rest = max(a.rest - 1, 0)
        self._raeume_auf()

    def nach_zyklus(self) -> None:
        """Zaehlt die Ereignisse herunter, die in Zyklen laufen."""
        for a in self.aktive:
            if a.dauer is Dauer.ZYKLEN:
                a.rest = max(a.rest - 1, 0)
        self._raeume_auf()

    def repariere(self, schluessel: str) -> Aktiv:
        """Beendet ein Ereignis, das bis zur Reparatur laeuft (E8, E25)."""
        for a in self.aktive:
            if a.schluessel == schluessel and a.reparierbar:
                self.aktive.remove(a)
                return a
        raise EreignisFehler(f"{schluessel} laeuft nicht oder ist nicht reparierbar")

    def _raeume_auf(self) -> None:
        self.aktive = [a for a in self.aktive if a.laeuft]
