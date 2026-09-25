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
from rennmanager.kern import gummierung as kern_gummierung
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


# Punkt 107: Wie lange die Blickpunkt-Box nach der Ziellinie noch dem
# Fahrer gehoert, der gerade angekommen ist. Zehn Sekunden - Entscheidung
# des Auftraggebers. In **Sessionzeit** gemessen wie alles hier, nicht in
# Bildschirmzeit: Bei 50-fachem Zeitraffer waere eine Sekunde Bildschirm
# fast eine Minute Session.
NACHLAUF_MS = 10_000


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
    # Punkt 88: Der Gummi-Aufschlag, den die Strecke dieser Runde bot -
    # als Anteil, also 0,0016 fuer 0,16 Prozent. Wer spaeter faehrt,
    # findet mehr vor; die Startreihenfolge ist der umgekehrte
    # Meisterschaftsstand (GDD 4).
    gummi: float = 0.0

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
class Zielankunft:
    """Wer sich gerade eingereiht hat - und was das bewegt hat (Punkt 93).

    ``verdraengt`` ist das Auto, das durch diese Ankunft einen Platz
    nach hinten gerutscht ist, ``abstand_ms`` der Vorsprung darauf.
    Reiht sich einer hinten ein, verdraengt er niemanden; dann steht
    dort ``None`` und ``abstand_ms`` ist null.
    """

    fahrt: Fahrt
    platz: int
    verdraengt: Fahrt | None
    abstand_ms: int
    neue_pole: bool


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

    def ort_auf_der_runde(self, stand: Stand, zeit_ms: float) -> float | None:
        """Wo das Auto gerade auf der Strecke ist, in Metern.

        Gebraucht fuer die Streckengrafik im Qualifying (Punkt 93, A9):
        ein Punkt, der die Runde abfaehrt. Wer in der Box steht oder
        schon im Ziel ist, hat keinen Ort - dann steht hier ``None``,
        und die Grafik zeichnet ihn nicht.

        Gezaehlt wird **beides**: die gezeitete Runde und die
        Aufwaermrunde davor. Die Aufwaermrunde lange wegzulassen war ein
        Fehler: Gemessen dauert sie 101 s gegen 98 s fuer die gezeitete,
        ein Auto ist also laenger ungezeitet auf der Strecke als
        gezeitet. Die Karte zeigte in dieser Zeit nichts - ueber eine
        ganze Session gerechnet war sie 20,8 Prozent der Zeit leer, unter
        anderem gleich am Anfang.

        **Gerechnet wird ueber die Sektorgrenzen.** Sie sind die einzigen
        Stellen, an denen Zeit und Ort beide bekannt sind; innerhalb
        eines Sektors wird linear interpoliert. Genauer geht es nicht,
        ohne das Geschwindigkeitsprofil noch einmal zu fahren - und fuer
        einen wandernden Punkt genuegt es: Der Fehler ist am groessten in
        der Mitte eines Sektors und dort hoechstens ein paar Dutzend
        Meter auf gut einem Kilometer.
        """
        fahrt = stand.fahrt
        sektoren = self.strecke.sektoren
        if not sektoren or len(fahrt.sektoren_ms) != len(sektoren):
            return None
        if stand.lage is Lage.SCHNELLE_RUNDE:
            return self._ort_ueber_sektoren(
                float(fahrt.runde_ab_ms), fahrt.sektorenden_ms, zeit_ms
            )
        if stand.lage is Lage.AUFWAERMUNG:
            return self._ort_ueber_sektoren(
                float(fahrt.beginn_ms), self._aufwaermenden(fahrt), zeit_ms
            )
        return None

    def _ort_ueber_sektoren(
        self, ab_ms: float, enden_ms: tuple[int, ...] | tuple[float, ...],
        zeit_ms: float,
    ) -> float:
        """Meter auf der Runde, aus Sektorgrenzen in Zeit und Ort."""
        uhr = ab_ms
        gelaufen = 0.0
        for sektor, ende in zip(self.strecke.sektoren, enden_ms, strict=True):
            if zeit_ms < ende:
                dauer = max(float(ende) - uhr, 1.0)
                anteil = min(max((zeit_ms - uhr) / dauer, 0.0), 1.0)
                return gelaufen + anteil * sektor.laenge_m
            uhr = float(ende)
            gelaufen += sektor.laenge_m
        return gelaufen

    @staticmethod
    def _aufwaermenden(fahrt: Fahrt) -> tuple[float, ...]:
        """Sektorgrenzen der Aufwaermrunde, in Zeit.

        Die Aufwaermrunde wird nicht gezeitet - ihre Sektorzeiten hebt
        der Kern nicht auf. Bekannt ist nur ihr Fenster: Sie fuellt genau
        die Zeit zwischen Boxenausfahrt und Beginn der gezeiteten Runde,
        und in dieser Zeit faehrt das Auto genau eine Runde
        (``qualifying.aufwaermrunden = 1``).

        Wie sich die Zeit auf die Sektoren verteilt, wird von der
        gezeiteten Runde uebernommen und auf das Fenster gestreckt: Es
        ist dieselbe Strecke, also braucht derselbe Sektor anteilig
        dieselbe Zeit. Das Auto faehrt langsamer, aber ueberall
        langsamer. Gleichmaessig zu verteilen waere die schlechtere
        Annahme - dann stuende der Punkt auf der Geraden zu frueh und in
        der Kurve zu spaet.
        """
        dauer = max(float(fahrt.runde_ab_ms - fahrt.beginn_ms), 1.0)
        gesamt = max(float(fahrt.zeit_ms), 1.0)
        ab = float(fahrt.beginn_ms)
        return tuple(
            ab + (ende - fahrt.runde_ab_ms) / gesamt * dauer
            for ende in fahrt.sektorenden_ms
        )

    # -- Was gerade passiert ist (Punkt 93) --------------------------------
    def letzte_zielankunft(self, zeit_ms: float, fenster_ms: float):
        """Die juengste Zielankunft - oder ``None``, wenn sie zu lange her ist.

        Die Zeitentafel zeigt damit, was gerade passiert ist: wer sich
        eingereiht hat, wen er dabei nach hinten geschoben hat und ob er
        die Pole uebernommen hat. ``fenster_ms`` zaehlt in **Sessionzeit**
        und nicht in Bildschirmzeit - bei 50-fachem Zeitraffer waere eine
        Sekunde Bildschirmzeit fast eine Minute Session, und der Hinweis
        staende dauernd da.

        :return: eine ``Zielankunft`` oder ``None``
        """
        angekommen = [f for f in self.fahrten if f.ziel_ms <= zeit_ms]
        if not angekommen:
            return None
        neueste = max(angekommen, key=lambda f: f.ziel_ms)
        if zeit_ms - neueste.ziel_ms > fenster_ms:
            return None

        # Der Stand **in dem Moment**, in dem er ueber die Linie kam.
        stand = sorted(angekommen, key=lambda f: (f.zeit_ms, f.reihenfolge))
        platz = stand.index(neueste) + 1
        # Wen er nach hinten geschoben hat: den, der jetzt hinter ihm
        # steht. Wer sich hinten einreiht, verdraengt niemanden.
        verdraengt = stand[platz] if platz < len(stand) else None
        return Zielankunft(
            fahrt=neueste,
            platz=platz,
            verdraengt=verdraengt,
            abstand_ms=(
                int(verdraengt.zeit_ms - neueste.zeit_ms) if verdraengt else 0
            ),
            # Pole ist neu, wenn er sich auf eins setzt und vorher schon
            # jemand anders dort stand. Der allererste Fahrer der Session
            # uebernimmt keine Pole, er eroeffnet sie.
            neue_pole=platz == 1 and len(stand) > 1,
        )

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

    # -- Punkt 107: der Fahrer im Blickpunkt -------------------------------
    def blickpunkt(self, zeit_ms: float) -> Fahrt | None:
        """Wessen Runde gerade gezeigt wird.

        Gezeigt wird, wer auf seiner gezeiteten Runde **am weitesten**
        ist - gemessen in Metern auf der Runde, nicht in Sektoren: Zwei
        Autos im selben Sektor sind verschieden weit.

        Wer gerade ins Ziel gekommen ist, behaelt den Platz noch
        ``NACHLAUF_MS`` lang. Kommen zwei kurz nacheinander an, gehoert
        der Platz dem Spaeteren.

        Seit der Nachbesserung zu Punkt 107 ist das nur noch die
        **erste Wahl**: Die Box haelt den Fahrer danach fest, bis der
        Spieler einen anderen anklickt (Entscheidung des Auftraggebers).
        Gefragt wird hier also nur, solange die Box noch leer ist.
        """
        gerade_fertig = [
            f for f in self.fahrten if 0 <= zeit_ms - f.ziel_ms <= NACHLAUF_MS
        ]
        if gerade_fertig:
            return max(gerade_fertig, key=lambda f: f.ziel_ms)

        unterwegs = [
            stand for stand in self.lage_zu(zeit_ms)
            if stand.lage is Lage.SCHNELLE_RUNDE
        ]
        if not unterwegs:
            return None
        weiteste = max(
            unterwegs, key=lambda s: self.ort_auf_der_runde(s, zeit_ms) or 0.0
        )
        return weiteste.fahrt

    @staticmethod
    def gesamt_bis(fahrt: Fahrt, nummer: int) -> int:
        """Die Gesamtzeit einer Runde bis zum Ende dieses Sektors.

        Am letzten Split ist das die **Rundenzeit** selbst und nicht die
        Summe der Sektoren: Beide werden getrennt auf ganze
        Millisekunden gerundet (siehe ``Fahrt.sektorenden_ms``). In der
        Blickpunktbox stehen letzter Split und Endzeit nebeneinander -
        eine Millisekunde Unterschied zwischen zwei Zahlen, die dasselbe
        meinen, saehe nach Fehler aus.
        """
        if nummer >= len(fahrt.sektoren_ms) - 1:
            return fahrt.zeit_ms
        return sum(fahrt.sektoren_ms[: nummer + 1])

    def splitabstand(
        self, fahrt: Fahrt, nummer: int, zeit_ms: float
    ) -> int | None:
        """Vorsprung oder Rueckstand der **Gesamtzeit** bis zu diesem Split.

        Verglichen wird gegen die schnellste bis dahin beendete Runde -
        also gegen den, der gerade die Pole haelt (Entscheidung des
        Auftraggebers). Negativ heisst schneller.

        Anders als ``splitvergleich`` misst das nicht den einzelnen
        Sektor, sondern die aufgelaufene Zeit: Die Frage ist, ob er auf
        Poleniveau liegt, nicht ob ihm ein einzelner Sektor geraten ist.

        ``None``, solange noch niemand sonst eine Runde stehen hat.
        """
        fuehrt = self.fuehrender_zu(zeit_ms, ohne=fahrt)
        if fuehrt is None:
            return None
        return self.gesamt_bis(fahrt, nummer) - self.gesamt_bis(fuehrt, nummer)

    def splitplatz(self, fahrt: Fahrt, nummer: int, zeit_ms: float) -> int:
        """Der Wievieltbeste er bis zu diesem Split ist.

        Gezaehlt werden alle, die den Split bis ``zeit_ms`` passiert
        haben - auch die, die noch unterwegs sind. Es ist also der Stand
        an dieser Stelle der Strecke, keine Hochrechnung aufs Ergebnis.
        """
        meins = self.gesamt_bis(fahrt, nummer)
        schneller = sum(
            1
            for andere in self.fahrten
            if andere is not fahrt
            and andere.sektorenden_ms[nummer] <= zeit_ms
            and self.gesamt_bis(andere, nummer) < meins
        )
        return schneller + 1

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
    strecke: Strecke,
    verlauf: kern_wetter.Wetterverlauf,
    konfiguration,
    auto,
    zeit_ms: float,
    gummi: float = 1.0,
) -> np.ndarray:
    """Grip je Streckenpunkt zu einem Zeitpunkt, mit Wetterkoennen.

    Bei Wechselhaft unterscheidet sich der Grip je Sektor (GDD 7), deshalb
    wird er punktweise aufgebaut.
    """
    zustand = verlauf.zustand_zu(zeit_ms)
    grip = np.empty(len(strecke.punkte))
    for sektor in strecke.sektoren:
        roh = verlauf.grip_zu(zeit_ms, sektor.nummer)
        # Punkt 88: Der Gummi-Aufschlag wirkt **nach** ``grip_fuer`` -
        # Gummi auf der Strecke ist keine Fahrkunst und wird deshalb
        # nicht von der Wetterfaehigkeit gedaempft.
        grip[sektor.von : sektor.bis] = (
            kern_wetter.grip_fuer(konfiguration, auto, zustand, roh) * gummi
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
    # Punkt 88: Gefahrene Auto-Runden Gummi. Waechst mit jedem Auto, das
    # drausen war - wer spaeter faehrt, findet mehr vor.
    gummistand = 0.0
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
        # Punkt 88: Der Stand, den dieses Auto vorfindet - alles, was die
        # Autos vor ihm gefahren haben. Die Schleife laeuft in der
        # Startreihenfolge und damit in der Zeit, also stimmt das.
        # Die Mischung steht im Qualifying nicht zur Wahl, sondern folgt
        # der Lage (Punkt 39) - sie wird deshalb schon hier gebraucht,
        # fuer Auftrag und Ansprechen des Gummis.
        aufwaermmisch = kern_strategie.qualifyingmischung(
            konfiguration, verlauf.zustand_zu(uhr)
        )
        gummi_faktor = kern_gummierung.faktor(
            konfiguration, gummistand, aufwaermmisch
        )
        for _ in range(aufwaermrunden):
            grip = _grip_je_punkt(
                strecke, verlauf, konfiguration, auto, uhr, gummi_faktor
            )
            uhr += fahre_runde(
                konfiguration, strecke, auto, grip, grenzen
            ).zeit_ms / kenntnis

        # Gezeitete Runde. Zustand und Grip gelten fuer den Beginn der
        # Runde - danach kann das Wetter schon gewechselt haben.
        # Die Aufwaermrunden dieses Autos zaehlen fuer seine eigene
        # gezeitete Runde schon mit - es ist ja selbst darueber gefahren.
        gummistand = kern_gummierung.naechster_stand(
            konfiguration,
            gummistand,
            verlauf.zustand_zu(uhr),
            aufwaermrunden,
            mischung=aufwaermmisch,
        )

        beginn_runde = uhr
        zustand = verlauf.zustand_zu(beginn_runde)
        misch = kern_strategie.qualifyingmischung(konfiguration, zustand)
        gummi_faktor = kern_gummierung.faktor(konfiguration, gummistand, misch)
        grip = _grip_je_punkt(
            strecke, verlauf, konfiguration, auto, beginn_runde, gummi_faktor
        )
        runde = fahre_runde(konfiguration, strecke, auto, grip, grenzen)

        # Sektorform, der Bonus aus der Q-Spalte, die Streckenkenntnis und
        # die Reifenmischung wirken auf die Zeit. Die Mischung ist im
        # Qualifying keine Wahl, sondern eine Regel (Punkt 39): immer
        # weich, im Nassen der passende Satz.
        #
        # Punkt 95: Die Form faellt je Sektor, nicht je Runde. Eine
        # Kopplung an den Platzgewinn gibt es hier nicht - im Qualifying
        # faehrt jeder allein, es gibt keine Plaetze zu gewinnen.
        mischfaktor = kern_reifen.mischungsfaktor(
            konfiguration, misch, kern_reifen.naesse_von(konfiguration, zustand)
        )
        grundfaktor = 1.0 / (
            (1.0 + qualifyingbonus(konfiguration, auto)) * kenntnis * mischfaktor
        )
        sektoren = tuple(
            int(round(
                wert
                * grundfaktor
                * kern_form.sektorform(
                    konfiguration, auto, seedquelle.zweig("runde", i), 1, nummer
                )
            ))
            for nummer, wert in enumerate(runde.sektoren_ms)
        )
        # Die Rundenzeit ist die Summe ihrer Sektoren - anders ginge es
        # nicht mehr auf, seit jeder Sektor seinen eigenen Wurf hat.
        zeit = sum(sektoren)
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
                gummi=gummi_faktor - 1.0,
            )
        )
        gummistand = kern_gummierung.naechster_stand(
            konfiguration, gummistand, zustand, 1.0, mischung=misch
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
