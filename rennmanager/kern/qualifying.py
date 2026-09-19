"""Qualifying (GDD 4).

Jedes Auto faehrt allein: eine ungezeitete Aufwaermrunde, danach eine
gezeitete Runde. Die Startreihenfolge folgt dem umgekehrten
Meisterschaftsstand; im ersten Rennen einer Saison stattdessen aufsteigend
nach durchschnittlicher Qualifying-Faehigkeit.

Die Autos starten ueberlappend: Jedes rueckt einen festen Rundenanteil
nach dem vorigen los und faehrt seine Runden trotzdem allein. Ohne das
dauerte eine Session 30 mal zwei Runden - in Spa drei Stunden, in denen
sich das Wetter zwangslaeufig mehrfach dreht.

Die Uhr laeuft ueber die ganze Session weiter, das Wetter kann sich also
waehrend des Qualifyings aendern. Anders als im Rennen, wo alle Autos
gleichzeitig unterwegs sind, traefe das hier frueh und spaet Fahrende
ungleich. Deshalb liegen die Wechsel nur in einem Fenster am Anfang und
sind in der Zahl begrenzt; die Werte stehen in der Konfiguration.

Fuer die gezeitete Runde kommt zur normalen Fahrleistung der Bereich ``q``
aus der Wirkungsmatrix hinzu (GDD 8: "die Q-Spalte ist ein zusaetzliches
Gewicht nur fuer die gezeitete Runde").
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import form as kern_form
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import strategie as kern_strategie
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.auto import bereichswert, gesamtwert
from rennmanager.kern.rennen import Teilnehmer
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.tempo import fahre_runde, grenzen_aus, leistungsanteil
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class Lage(Enum):
    """Was ein Auto zu einem Zeitpunkt der Session macht (Punkt 85).

    Die Session laeuft ueberlappend: Waehrend der eine schon im Ziel ist,
    waermt der naechste erst auf und der uebernaechste steht noch. Fuer
    die Uebertragung braucht jede dieser vier Lagen eine eigene Zeile.
    """

    WARTET = "wartet"
    AUFWAERMUNG = "aufwaermung"
    SCHNELLE_RUNDE = "schnelle_runde"
    ZIEL = "ziel"

    @property
    def bezeichnung(self) -> str:
        return {
            Lage.WARTET: "Box",
            Lage.AUFWAERMUNG: "Aufwaermrunde",
            Lage.SCHNELLE_RUNDE: "Schnelle Runde",
            Lage.ZIEL: "Im Ziel",
        }[self]


@dataclass(frozen=True)
class Fahrt:
    """Die gezeitete Runde eines Autos."""

    teilnehmer: int
    reihenfolge: int
    beginn_ms: int
    ziel_ms: int
    zeit_ms: int
    sektoren_ms: tuple[int, ...]
    tagesform: float
    zustand: str
    grip: float
    # Punkt 39: Womit die Runde gefahren wurde. Im Qualifying keine Wahl,
    # sondern eine Regel - deshalb steht das Kuerzel hier nur zur Anzeige.
    mischung: str = ""

    @property
    def runde_ab_ms(self) -> int:
        """Wann die gezeitete Runde beginnt.

        ``beginn_ms`` ist die Ausfahrt aus der Box, davor liegen noch die
        Aufwaermrunden. Die Uhr der schnellen Runde laeuft erst ab hier.
        """
        return self.ziel_ms - self.zeit_ms

    @property
    def sektorenden_ms(self) -> tuple[int, ...]:
        """Wann die einzelnen Sektoren der gezeiteten Runde fertig sind.

        Sektorzeiten und Rundenzeit werden getrennt auf ganze
        Millisekunden gerundet (GDD 15), ihre Summe muss die Rundenzeit
        also nicht auf die Millisekunde treffen. Der letzte Sektor endet
        deshalb per Definition im Ziel - die Runde ist vorbei, wenn sie
        vorbei ist, nicht wenn die Teilsummen es sagen.
        """
        enden = []
        uhr = self.runde_ab_ms
        for wert in self.sektoren_ms:
            uhr += wert
            enden.append(uhr)
        if enden:
            enden[-1] = self.ziel_ms
        return tuple(enden)


@dataclass(frozen=True)
class Stand:
    """Was ein Auto zu einem Zeitpunkt der Session macht (Punkt 85).

    :param sektoren: wie viele Sektoren der gezeiteten Runde schon fertig
        sind - im Ziel alle, in der Box keiner
    :param zeit_ms: die laufende Rundenzeit, im Ziel die endgueltige;
        ``None``, solange das Auto noch nicht auf der schnellen Runde ist
    """

    fahrt: Fahrt
    lage: Lage
    sektoren: int
    zeit_ms: int | None

    @property
    def ist_fertig(self) -> bool:
        return self.lage is Lage.ZIEL


@dataclass(frozen=True)
class Qualifying:
    """Das Ergebnis einer Qualifying-Session."""

    strecke: Strecke
    teilnehmer: tuple[Teilnehmer, ...]
    fahrten: tuple[Fahrt, ...]
    wetter: kern_wetter.Wetterverlauf
    aufstellung: tuple[int, ...]
    dauer_ms: int

    @property
    def pole(self) -> Fahrt:
        """Die schnellste Runde der Session."""
        return next(f for f in self.fahrten if f.teilnehmer == self.aufstellung[0])

    def stand_nach(self, fahrten: int) -> tuple[Fahrt, ...]:
        """Zwischenstand nach den ersten ``fahrten`` Laeufen (GDD 4).

        Bildet die Live-Einsortierung ins Ranking ab: Wer noch nicht
        gefahren ist, taucht nicht auf.
        """
        bisher = self.fahrten[: max(fahrten, 0)]
        return tuple(sorted(bisher, key=lambda f: f.zeit_ms))

    def bestzeit_nach(self, fahrten: int) -> int | None:
        stand = self.stand_nach(fahrten)
        return stand[0].zeit_ms if stand else None

    def startplatz(self, teilnehmer: int) -> int:
        return self.aufstellung.index(teilnehmer) + 1

    # -- Uebertragung (Punkt 85) -------------------------------------------
    def lage_zu(self, zeit_ms: float) -> tuple[Stand, ...]:
        """Was jedes Auto zum Zeitpunkt ``zeit_ms`` macht.

        Sortiert wie eine Zeitentafel: zuerst die beendeten Runden nach
        Zeit, darunter die, die gerade unterwegs sind - wer weiter auf
        seiner Runde ist, steht hoeher -, dann die Aufwaermrunden und
        zuletzt, wer noch in der Box steht. Es stehen immer alle Autos
        da, damit die Tabelle beim Abspielen nicht springt (Punkt 64).
        """
        staende = [self._stand_zu(fahrt, zeit_ms) for fahrt in self.fahrten]
        gruppe = {Lage.ZIEL: 0, Lage.SCHNELLE_RUNDE: 1, Lage.AUFWAERMUNG: 2, Lage.WARTET: 3}
        return tuple(
            sorted(
                staende,
                key=lambda s: (
                    gruppe[s.lage],
                    s.zeit_ms if s.lage is Lage.ZIEL else 0,
                    -s.sektoren,
                    s.zeit_ms if s.lage is Lage.SCHNELLE_RUNDE else 0,
                    s.fahrt.reihenfolge,
                ),
            )
        )

    @staticmethod
    def _stand_zu(fahrt: Fahrt, zeit_ms: float) -> Stand:
        if zeit_ms >= fahrt.ziel_ms:
            return Stand(fahrt, Lage.ZIEL, len(fahrt.sektoren_ms), fahrt.zeit_ms)
        if zeit_ms < fahrt.beginn_ms:
            return Stand(fahrt, Lage.WARTET, 0, None)
        if zeit_ms < fahrt.runde_ab_ms:
            return Stand(fahrt, Lage.AUFWAERMUNG, 0, None)
        fertig = sum(1 for ende in fahrt.sektorenden_ms if ende <= zeit_ms)
        return Stand(
            fahrt, Lage.SCHNELLE_RUNDE, fertig, int(zeit_ms - fahrt.runde_ab_ms)
        )

    def fuehrender_zu(self, zeit_ms: float, ohne: Fahrt | None = None) -> Fahrt | None:
        """Die schnellste bis dahin **beendete** Runde.

        Eine laufende Runde fuehrt nicht: Solange sie nicht steht, ist
        sie mit nichts vergleichbar.
        """
        fertig = [
            f for f in self.fahrten if f.ziel_ms <= zeit_ms and f is not ohne
        ]
        return min(fertig, key=lambda f: f.zeit_ms) if fertig else None

    def splitvergleich(self, fahrt: Fahrt, nummer: int) -> int | None:
        """Wie ein Split gegen den Fuehrenden stand, **als er fiel**.

        Entscheidung des Auftraggebers: wie im Fernsehen. Der Vergleich
        friert im Moment des Ueberfahrens ein und dreht sich nicht mehr,
        wenn spaeter jemand schneller ist. Verglichen wird der einzelne
        Sektor gegen denselben Sektor des Fuehrenden.

        ``None``, solange noch niemand sonst eine Runde stehen hat - dann
        gibt es nichts, wogegen zu messen waere.
        """
        fuehrt = self.fuehrender_zu(fahrt.sektorenden_ms[nummer], ohne=fahrt)
        if fuehrt is None:
            return None
        return fahrt.sektoren_ms[nummer] - fuehrt.sektoren_ms[nummer]

    def beste_splits_zu(self, zeit_ms: float) -> tuple[int | None, ...]:
        """Wer je Sektor bis dahin den schnellsten Split hat.

        Gibt je Sektor den Teilnehmerindex zurueck, ``None``, solange
        keiner gefahren ist. Anders als der Vergleich gegen den
        Fuehrenden laeuft das mit: Lila haelt immer genau einer je
        Sektor, und es wandert weiter, sobald es jemand unterbietet.
        """
        if not self.fahrten:
            return ()
        halter: list[int | None] = []
        for nummer in range(len(self.fahrten[0].sektoren_ms)):
            gefahren = [
                f for f in self.fahrten if f.sektorenden_ms[nummer] <= zeit_ms
            ]
            if not gefahren:
                halter.append(None)
                continue
            bester = min(
                gefahren,
                key=lambda f: (f.sektoren_ms[nummer], f.sektorenden_ms[nummer]),
            )
            halter.append(bester.teilnehmer)
        return tuple(halter)


def qualifyingstaerke(konfiguration: Konfiguration, teilnehmer: Teilnehmer) -> float:
    """Durchschnittliche Qualifying-Faehigkeit, Bereich ``q`` (GDD 8)."""
    return bereichswert(konfiguration, teilnehmer.auto, "q")


def startreihenfolge(
    konfiguration: Konfiguration,
    teilnehmer: tuple[Teilnehmer, ...],
    meisterschaft: tuple[int, ...] | None = None,
) -> tuple[int, ...]:
    """Reihenfolge, in der die Autos ihre gezeitete Runde fahren (GDD 4).

    :param meisterschaft: Meisterschaftsstand als Teilnehmerindizes, Erster
        zuerst. Ohne Angabe gilt die Regel fuer das erste Rennen einer
        Saison: aufsteigend nach durchschnittlicher Qualifying-Faehigkeit.
    """
    if meisterschaft is None:
        return tuple(
            sorted(
                range(len(teilnehmer)),
                key=lambda i: (qualifyingstaerke(konfiguration, teilnehmer[i]), i),
            )
        )

    if sorted(meisterschaft) != list(range(len(teilnehmer))):
        raise ValueError("Der Meisterschaftsstand muss alle Teilnehmer genau einmal nennen")
    # Der Erste der Wertung faehrt zuletzt.
    return tuple(reversed(meisterschaft))


def _grip_je_punkt(
    strecke: Strecke, verlauf: kern_wetter.Wetterverlauf, konfiguration, auto, zeit_ms: float
) -> np.ndarray:
    """Grip je Streckenpunkt zu einem Zeitpunkt, mit Wetterkoennen.

    Bei Wechselhaft unterscheidet sich der Grip je Sektor (GDD 7), deshalb
    wird er punktweise aufgebaut.
    """
    zustand = verlauf.zustand_zu(zeit_ms)
    grip = np.empty(len(strecke.punkte))
    for sektor in strecke.sektoren:
        roh = verlauf.grip_zu(zeit_ms, sektor.nummer)
        grip[sektor.von : sektor.bis] = kern_wetter.grip_fuer(
            konfiguration, auto, zustand, roh
        )
    return grip


def qualifyingbonus(konfiguration: Konfiguration, auto) -> float:
    """Tempobonus aus dem Bereich ``q``, nur fuer die gezeitete Runde.

    GDD 8 nennt die Q-Spalte ein zusaetzliches Gewicht, ohne die Umrechnung
    in Zeit zu nennen; die Entscheidung dazu steht in OFFENE_PUNKTE.md.
    """
    anteil = leistungsanteil(
        bereichswert(konfiguration, auto, "q"), konfiguration.wert("skala", "referenz")
    )
    return konfiguration.wert("qualifying", "bonus", "max_anteil") * min(anteil, 1.0)


def fahre(
    konfiguration: Konfiguration,
    strecke: Strecke,
    teilnehmer: tuple[Teilnehmer, ...],
    seedquelle: Seedquelle,
    meisterschaft: tuple[int, ...] | None = None,
    kenntnisfaktor: tuple[float, ...] | None = None,
    tagesformbonus: tuple[float, ...] | None = None,
    rhythmusfaktor: tuple[float, ...] | None = None,
) -> Qualifying:
    """Faehrt ein ganzes Qualifying und liefert die Startaufstellung.

    :param kenntnisfaktor: Tempofaktor aus der Streckenkenntnis je Auto
        (GDD 6). Ohne Angabe faehrt jedes Auto ohne Kenntnisbonus.
    :param tagesformbonus: Zuschlag auf den Tagesform-Mittelwert je Auto
        (E3 Motivationsschub aus GDD 14). Ohne Angabe faehrt jedes Auto
        ohne Zuschlag.
    :param rhythmusfaktor: Faktor auf die Querbeschleunigung in Kurven je
        Auto (Punkt 15). Ohne Angabe faehrt jedes Auto ohne Vorteil.
    """
    if not teilnehmer:
        raise ValueError("Ohne Teilnehmer gibt es kein Qualifying")
    if kenntnisfaktor is None:
        kenntnisfaktor = (1.0,) * len(teilnehmer)
    elif len(kenntnisfaktor) != len(teilnehmer):
        raise ValueError(
            f"Kenntnisfaktor fuer {len(kenntnisfaktor)} Autos, "
            f"im Feld stehen {len(teilnehmer)}"
        )
    if tagesformbonus is None:
        tagesformbonus = (0.0,) * len(teilnehmer)
    elif len(tagesformbonus) != len(teilnehmer):
        raise ValueError(
            f"Tagesformbonus fuer {len(tagesformbonus)} Autos, "
            f"im Feld stehen {len(teilnehmer)}"
        )
    if rhythmusfaktor is None:
        rhythmusfaktor = (1.0,) * len(teilnehmer)
    elif len(rhythmusfaktor) != len(teilnehmer):
        raise ValueError(
            f"Rhythmusfaktor fuer {len(rhythmusfaktor)} Autos, "
            f"im Feld stehen {len(teilnehmer)}"
        )

    reihenfolge = startreihenfolge(konfiguration, teilnehmer, meisterschaft)
    aufwaermrunden = konfiguration.wert("qualifying", "aufwaermrunden")
    gezeitete = konfiguration.wert("qualifying", "gezeitete_runden")

    # Fuer das Wetter wird die Dauer vorab geschaetzt: jedes Auto faehrt
    # Aufwaermrunde plus gezeitete Runde.
    schaetzrunde = fahre_runde(konfiguration, strecke, teilnehmer[0].auto).zeit_ms
    abstand_runden = konfiguration.wert("qualifying", "abstand_runden")
    abstand_ms = schaetzrunde * abstand_runden
    dauer_schaetzung = int(
        abstand_ms * (len(teilnehmer) - 1) + schaetzrunde * (aufwaermrunden + gezeitete)
    )
    verlauf = kern_wetter.wuerfle(
        konfiguration,
        strecke.name,
        dauer_schaetzung,
        schaetzrunde,
        seedquelle.zweig("wetter"),
        wechselfenster_ms=int(
            konfiguration.wert("qualifying", "wetter", "fenster_minuten") * 60_000
        ),
        wechsel_max=konfiguration.wert("qualifying", "wetter", "wechsel_max"),
    )

    fahrten: list[Fahrt] = []
    for platz, i in enumerate(reihenfolge):
        # Ueberlappender Start: jedes Auto rueckt abstand_runden nach dem
        # vorigen los und faehrt seine Runden dennoch allein.
        uhr = abstand_ms * platz
        # Eigener Wurf je Auto und Session (GDD 11).
        sessionform = kern_form.wuerfle(
            konfiguration, teilnehmer[i].auto, seedquelle.zweig("form", i), tagesformbonus[i]
        )
        auto = sessionform.auto
        beginn = uhr

        # Aufwaermrunde: ungezeitet, verbraucht aber Zeit.
        kenntnis = kenntnisfaktor[i]
        # Der Rhythmus aus Punkt 15 haengt an der Quergrenze, nicht an der
        # Zeit - deshalb faehrt das Qualifying mit fertigen Grenzen.
        grenzen = replace(
            grenzen_aus(konfiguration, auto),
            quer=grenzen_aus(konfiguration, auto).quer * rhythmusfaktor[i],
        )
        for _ in range(aufwaermrunden):
            grip = _grip_je_punkt(strecke, verlauf, konfiguration, auto, uhr)
            uhr += fahre_runde(
                konfiguration, strecke, auto, grip, grenzen
            ).zeit_ms / kenntnis

        # Gezeitete Runde. Zustand und Grip gelten fuer den Beginn der
        # Runde - danach kann das Wetter schon gewechselt haben.
        beginn_runde = uhr
        zustand = verlauf.zustand_zu(beginn_runde)
        grip = _grip_je_punkt(strecke, verlauf, konfiguration, auto, beginn_runde)
        runde = fahre_runde(konfiguration, strecke, auto, grip, grenzen)

        # Rundenform, der Bonus aus der Q-Spalte, die Streckenkenntnis und
        # die Reifenmischung wirken auf die Zeit. Die Mischung ist im
        # Qualifying keine Wahl, sondern eine Regel (Punkt 39): immer
        # weich, im Nassen der passende Satz.
        streuung = kern_form.rundenform(konfiguration, auto, seedquelle.zweig("runde", i), 1)
        misch = kern_strategie.qualifyingmischung(konfiguration, zustand)
        mischfaktor = kern_reifen.mischungsfaktor(
            konfiguration, misch, kern_reifen.naesse_von(konfiguration, zustand)
        )
        faktor = streuung / (
            (1.0 + qualifyingbonus(konfiguration, auto)) * kenntnis * mischfaktor
        )
        zeit = int(round(runde.zeit_ms * faktor))
        sektoren = tuple(int(round(wert * faktor)) for wert in runde.sektoren_ms)
        uhr += zeit

        fahrten.append(
            Fahrt(
                teilnehmer=i,
                reihenfolge=platz + 1,
                beginn_ms=int(round(beginn)),
                ziel_ms=int(round(uhr)),
                zeit_ms=zeit,
                sektoren_ms=sektoren,
                tagesform=sessionform.tagesform,
                zustand=zustand,
                grip=float(grip.mean()),
                mischung=misch.kuerzel,
            )
        )

    # Aufstellung: schnellste Runde zuerst. Bei Gleichstand auf die
    # Millisekunde entscheidet der hoehere Durchschnitt der
    # Basiseigenschaften, sonst das Los (GDD 4).
    los = seedquelle.zweig("gleichstand").generator()
    marke = {fahrt.teilnehmer: float(los.random()) for fahrt in fahrten}
    geordnet = sorted(
        fahrten,
        key=lambda f: (
            f.zeit_ms,
            -gesamtwert(konfiguration, teilnehmer[f.teilnehmer].auto),
            marke[f.teilnehmer],
        ),
    )

    return Qualifying(
        strecke=strecke,
        teilnehmer=teilnehmer,
        fahrten=tuple(fahrten),
        wetter=verlauf,
        aufstellung=tuple(fahrt.teilnehmer for fahrt in geordnet),
        dauer_ms=max(fahrt.ziel_ms for fahrt in fahrten),
    )
