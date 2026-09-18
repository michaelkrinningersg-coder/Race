"""Rennsimulation mit mehreren Autos.

Setzt Start, Folgen, Ueberholen und Zeitmessung aus GDD 4 um.

GDD 15 verlangt, die Geschwindigkeitsprofile vorab zu berechnen und die
Anzeige nur Positionen auslesen zu lassen. Genau so ist es aufgebaut: Jedes
Auto bekommt aus ``rennmanager.kern.tempo`` sein freies Profil ueber die
Runde, danach laeuft das Rennen einmal komplett durch und legt die
Positionen in festen Abstaenden ab. Die Oberflaeche spielt diesen Verlauf
nur noch ab - auch 100-facher Zeitraffer kostet sie nichts.

Das freie Profil ist dabei die Obergrenze. Interaktion entsteht durch zwei
Regeln aus GDD 4:

* Ist der Abstand zum Vordermann kleiner als 0,05 s, faehrt das hintere
  Auto dessen Tempo - ueberholen darf es nur in einer Ueberholzone.
* In einer Ueberholzone wird bei mindestens 2 km/h Tempovorteil ein
  Ueberholversuch gewuerfelt.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import boxenstopp as kern_boxenstopp
from rennmanager.kern import form as kern_form
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import strategie as kern_strategie
from rennmanager.kern import tempoverlauf as kern_tempoverlauf
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern import windschatten as kern_windschatten
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.auto import Auto, bereichswert, gesamtwert
from rennmanager.kern.strecke import Segmentart, Strecke
from rennmanager.kern.tempo import KMH_JE_MS, geschwindigkeitsprofil, grenzen_aus, leistungsanteil
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Wirkungsbereich aus GDD 8, der das Duell traegt (Punkt 55).
BEREICH_DUELL = "du"


@dataclass(frozen=True)
class Teilnehmer:
    """Ein Auto am Start, mit Anzeigedaten und Startplatz.

    :param nummer: Fahrernummer aus der Welt, damit die Oberflaeche von
        einer Zeile der Rangliste zum Fahrer zurueckfindet. Die Simulation
        liest sie nie; ein Feld aus ``starterfeld`` dieses Moduls hat
        keinen Fahrer dahinter und behaelt die 0.
    """

    auto: Auto
    startplatz: int
    farbe: str
    ist_spieler: bool = False
    nummer: int = 0

    @property
    def kuerzel(self) -> str:
        return self.auto.kuerzel


@dataclass
class Rundenprotokoll:
    """Zeiten eines Autos, fortlaufend gefuellt (GDD 4: Zeitenmonitor)."""

    rundenzeiten_ms: list[int] = field(default_factory=list)
    sektorzeiten_ms: list[tuple[int, ...]] = field(default_factory=list)
    # Wann jede Runde zu Ende war, in Rennzeit. Ohne das weiss die
    # Anzeige nicht, welche Runden zum Abspielzeitpunkt schon gefahren
    # sind - sie zeigte immer die Zeiten vom Rennende.
    rundenende_ms: list[int] = field(default_factory=list)

    @property
    def beste_runde_ms(self) -> int | None:
        return min(self.rundenzeiten_ms) if self.rundenzeiten_ms else None

    @property
    def letzte_runde_ms(self) -> int | None:
        return self.rundenzeiten_ms[-1] if self.rundenzeiten_ms else None

    def gefahren_bis(self, zeit_ms: float) -> int:
        """Wie viele Runden bis zu diesem Zeitpunkt fertig waren."""
        if not self.rundenende_ms:
            # Ein Protokoll aus einem Stand ohne Rundenenden: dann gilt
            # alles als gefahren, wie es die Anzeige bisher tat.
            return len(self.rundenzeiten_ms)
        return int(bisect_right(self.rundenende_ms, zeit_ms))

    def stand_zu(self, zeit_ms: float) -> tuple[int | None, int | None, tuple[int, ...]]:
        """Letzte Runde, beste Runde und ihre Sektorzeiten zum Zeitpunkt.

        :return: (letzte Rundenzeit, beste Rundenzeit, Sektoren der
            letzten Runde); alles ``None`` beziehungsweise leer, solange
            noch keine Runde fertig ist.
        """
        bis = self.gefahren_bis(zeit_ms)
        if bis <= 0:
            return None, None, ()
        zeiten = self.rundenzeiten_ms[:bis]
        sektoren = self.sektorzeiten_ms[bis - 1] if bis <= len(self.sektorzeiten_ms) else ()
        return zeiten[-1], min(zeiten), sektoren


@dataclass(frozen=True)
class Ueberholmanoever:
    """Ein gelungenes Ueberholmanoever, fuer Statistik und Erfahrung."""

    zeit_ms: int
    angreifer: int
    verteidiger: int
    runde: int


@dataclass(frozen=True)
class Boxenstopp:
    """Ein gefahrener Boxenstopp (Punkt 39).

    ``restprofil`` ist der Reifenzustand beim Wechsel, 1,0 frisch bis
    0,0 abgefahren - dieselbe Groesse, die die Rangliste als Balken
    zeigt. ``notstopp`` unterscheidet den geplanten Stopp von dem, den
    ein Wetterwechsel erzwungen hat.
    """

    teilnehmer: int
    runde: int
    zeit_ms: int
    von: str
    nach: str
    restprofil: float
    standzeit_ms: int
    notstopp: bool = False


@dataclass(frozen=True)
class Ergebnis:
    """Das Ergebnis eines Autos am Rennende."""

    teilnehmer: int
    platz: int
    runden: int
    zeit_ms: int | None
    rueckstand_ms: int | None
    rundenrueckstand: int


@dataclass(frozen=True)
class Rennverlauf:
    """Der fertig berechnete Rennverlauf.

    :param zeitpunkte_ms: Zeitpunkte der festgehaltenen Bilder
    :param distanz_m: Form ``(Bilder, Autos)``, zurueckgelegte Strecke
    :param ausgefallen: Form ``(Bilder, Autos)``, ob das Auto noch faehrt
    """

    strecke: Strecke
    teilnehmer: tuple[Teilnehmer, ...]
    runden: int
    wetter: kern_wetter.Wetterverlauf | None
    tagesform: tuple[float, ...]
    zeitpunkte_ms: np.ndarray
    distanz_m: np.ndarray
    ausgefallen: np.ndarray
    protokolle: tuple[Rundenprotokoll, ...]
    manoever: tuple[Ueberholmanoever, ...]
    # Je Auto: wie viele fahrende Gegner es ueber die Runden hinweg hinter
    # sich gebracht hat. Anders als ``manoever`` zaehlt das keine Duelle
    # mit, die innerhalb einer Runde hin und her gehen - deshalb haengt die
    # Erfahrung aus GDD 10 hieran und nicht an den rohen Vorbeigaengen.
    positionsgewinne: tuple[int, ...]
    zwischenfaelle: tuple[kern_zwischenfall.Zwischenfall, ...]
    reifenzustand: np.ndarray
    ergebnisse: tuple[Ergebnis, ...]
    dauer_ms: int
    # Punkt 39: Welche Mischung jedes Auto in jedem Bild faehrt, als
    # Index in ``mischungen``. Form ``(Bilder, Autos)``. Ohne Strategie
    # steht ueberall die Startmischung.
    mischungsindex: np.ndarray | None = None
    # Die Kuerzel in der Reihenfolge der Indizes.
    mischungen: tuple[str, ...] = ()
    boxenstopps: tuple[Boxenstopp, ...] = ()
    # Ob in diesem Rennen zwei Mischungen Pflicht sind (Punkt 39). Bei
    # Regen, Starkregen und wechselhaftem Wetter ist die Pflicht
    # aufgehoben.
    mischungspflicht: bool = False

    @property
    def anzahl(self) -> int:
        return len(self.teilnehmer)

    def bild_zu(self, zeit_ms: float) -> int:
        """Index des letzten Bildes, das nicht nach ``zeit_ms`` liegt."""
        return int(np.clip(np.searchsorted(self.zeitpunkte_ms, zeit_ms, "right") - 1,
                           0, len(self.zeitpunkte_ms) - 1))

    def zwischenfaelle_von(self, teilnehmer: int) -> tuple[kern_zwischenfall.Zwischenfall, ...]:
        """Alle Zwischenfaelle eines Autos - fuer die Anzeige im Ranking."""
        return tuple(z for z in self.zwischenfaelle if z.teilnehmer == teilnehmer)

    @cached_property
    def _ausfallzeiten(self) -> tuple[int | None, ...]:
        """Wann jedes Auto ausgefallen ist, in Millisekunden."""
        zeiten: list[int | None] = []
        for i in range(self.anzahl):
            spalte = self.ausgefallen[:, i]
            treffer = np.flatnonzero(spalte)
            zeiten.append(
                int(self.zeitpunkte_ms[int(treffer[0])]) if len(treffer) else None
            )
        return tuple(zeiten)

    def ausfallzeit(self, teilnehmer: int) -> int | None:
        """Wann dieses Auto ausgefallen ist, oder ``None``."""
        return self._ausfallzeiten[teilnehmer]

    def reifen_zu(self, zeit_ms: float) -> np.ndarray:
        """Reifenzustand je Auto zu einem Zeitpunkt, 1,0 frisch bis 0,0."""
        return self.reifenzustand[self.bild_zu(zeit_ms)]

    def mischung_zu(self, zeit_ms: float) -> tuple[str, ...]:
        """Welche Mischung jedes Auto zu diesem Zeitpunkt faehrt (Punkt 39)."""
        if self.mischungsindex is None or not self.mischungen:
            return ("",) * self.anzahl
        zeile = self.mischungsindex[self.bild_zu(zeit_ms)]
        return tuple(self.mischungen[int(stelle)] for stelle in zeile)

    def stopps_von(self, teilnehmer: int) -> tuple[Boxenstopp, ...]:
        """Alle Boxenstopps eines Autos, in der Reihenfolge des Rennens."""
        return tuple(b for b in self.boxenstopps if b.teilnehmer == teilnehmer)

    def gefahrene_mischungen(self, teilnehmer: int, zeit_ms: float) -> tuple[str, ...]:
        """Welche Mischungen ein Auto bis zu diesem Zeitpunkt gefahren hat.

        Die Rangliste braucht das fuer die Mischungspflicht: Sie ist
        erfuellt, sobald hier zwei verschiedene Kuerzel stehen.
        """
        if self.mischungsindex is None or not self.mischungen:
            return ()
        bis = self.bild_zu(zeit_ms)
        spalte = self.mischungsindex[: bis + 1, teilnehmer]
        gesehen: list[str] = []
        for stelle in spalte:
            kuerzel = self.mischungen[int(stelle)]
            if kuerzel not in gesehen:
                gesehen.append(kuerzel)
        return tuple(gesehen)

    def distanzen_zu(self, zeit_ms: float) -> np.ndarray:
        """Zurueckgelegte Strecke je Auto, zwischen den Bildern interpoliert."""
        bild = self.bild_zu(zeit_ms)
        if bild >= len(self.zeitpunkte_ms) - 1:
            return self.distanz_m[-1]
        davor = float(self.zeitpunkte_ms[bild])
        danach = float(self.zeitpunkte_ms[bild + 1])
        anteil = (zeit_ms - davor) / max(danach - davor, 1e-9)
        return self.distanz_m[bild] + anteil * (self.distanz_m[bild + 1] - self.distanz_m[bild])

    @cached_property
    def _ergebnis_je_auto(self) -> dict[int, Ergebnis]:
        """Das Schlussergebnis, nach Teilnehmernummer greifbar."""
        return {e.teilnehmer: e for e in self.ergebnisse}

    def im_ziel_zu(self, teilnehmer: int, zeit_ms: float) -> bool:
        """Ob dieses Auto zu diesem Zeitpunkt schon im Ziel war."""
        ergebnis = self._ergebnis_je_auto.get(teilnehmer)
        return (
            ergebnis is not None
            and ergebnis.zeit_ms is not None
            and ergebnis.zeit_ms <= zeit_ms
        )

    def reihenfolge_zu(self, zeit_ms: float) -> list[int]:
        """Positionen zum Zeitpunkt: wer am weitesten ist, fuehrt (GDD 4).

        Solange gefahren wird, entscheidet die zurueckgelegte Strecke. Wer
        im Ziel ist, steht dagegen fest: absolvierte Runden absteigend,
        bei gleicher Rundenzahl die Zielzeit aufsteigend - und immer vor
        denen, die noch fahren.

        Das ist keine Feinheit: Ein Auto im Ziel steht, ein anderes faehrt
        weiter. Ohne diese Regel zieht der Zweite auf den letzten Metern
        an einem Sieger vorbei, der schon ueber der Linie ist, weil seine
        Strecke noch waechst.
        """
        distanzen = self.distanzen_zu(zeit_ms)
        ergebnisse = self._ergebnis_je_auto

        def schluessel(i: int) -> tuple:
            ergebnis = ergebnisse.get(i)
            if (
                ergebnis is not None
                and ergebnis.zeit_ms is not None
                and ergebnis.zeit_ms <= zeit_ms
            ):
                return (0, -ergebnis.runden, ergebnis.zeit_ms, 0.0)
            return (1, 0, 0, -float(distanzen[i]))

        return sorted(range(self.anzahl), key=schluessel)


# ---------------------------------------------------------------------------
# Startaufstellung
# ---------------------------------------------------------------------------
def reaktionszeit_ms(konfiguration: Konfiguration, auto: Auto) -> int:
    """Reaktionszeit am Start, 0,100 bis 0,300 s (GDD 4).

    Je hoeher der Bereich ``st`` - getragen vor allem von D4 Reaktion/Start -,
    desto kuerzer die Reaktion.
    """
    schnellste = konfiguration.wert("start", "reaktionszeit_min_ms")
    langsamste = konfiguration.wert("start", "reaktionszeit_max_ms")
    anteil = leistungsanteil(
        bereichswert(konfiguration, auto, "st"), konfiguration.wert("skala", "referenz")
    )
    return int(round(langsamste - (langsamste - schnellste) * min(anteil, 1.0)))


def startdistanz_m(konfiguration: Konfiguration, startplatz: int) -> float:
    """Abstand hinter der Startlinie; Platz 1 steht darauf (GDD 4)."""
    return -konfiguration.wert("start", "abstand_m") * (startplatz - 1)


def rundenzahl(konfiguration: Konfiguration, strecke: Strecke, liga: int) -> int:
    """Rundenzahl = Distanz durch Streckenlaenge, aufgerundet (GDD 4)."""
    basis = konfiguration.wert("rennen", "distanz_liga20_km")
    zuwachs = konfiguration.wert("rennen", "distanz_zuwachs_je_liga_km")
    distanz_km = basis + zuwachs * (konfiguration.wert("ligen", "anzahl") - liga)
    return max(1, math.ceil(distanz_km * 1000.0 / strecke.laenge_m))


# ---------------------------------------------------------------------------
# Ueberholen
# ---------------------------------------------------------------------------
def streckenfaktor(konfiguration: Konfiguration, strecke: Strecke, mittelwert: float) -> float:
    """Wie leicht sich auf dieser Strecke ueberholen laesst.

    Entscheidung zu Punkt 2: aus dem Anteil der Ueberholzonen an der
    Rundenlaenge, normiert auf den Mittelwert aller Strecken.
    """
    if konfiguration.wert("ueberholschwierigkeit", "grundlage") != "ueberholzonenanteil":
        raise ValueError("Nur die Grundlage 'ueberholzonenanteil' ist umgesetzt")
    return strecke.ueberholzonenanteil / max(mittelwert, 1e-9)


def erfolgschance(
    konfiguration: Konfiguration,
    angreifer: Auto,
    verteidiger: Auto,
    tempovorteil_kmh: float,
    faktor: float,
) -> float:
    """Erfolgschance eines Ueberholversuchs (GDD 4).

    Entscheidung zu Punkt 3: logistische Form. Sie bleibt auch dann
    sinnvoll, wenn beide Fahrer bei 0 stehen - was laut GDD 1 der
    Ausgangszustand ist.

    Das Koennen kommt aus dem Wirkungsbereich ``du`` der Matrix aus GDD 8
    (Punkt 55). Vorher standen dort allein D10 und D11; die uebrigen vier
    Eigenschaften der Zeile - F8 Bremsanlage, D7 Geraden, D8 Bremsen und
    D15 Nervenstaerke - wurden berechnet, aber von nichts gelesen. Innerhalb
    des Bereichs wiegen D10 und D11 mit je 3 von 10 weiterhin am
    schwersten, wie GDD 8 es vorgibt.
    """
    einstellung = konfiguration.wert("ueberholen", "erfolg")
    skala = konfiguration.wert("skala", "maximum")
    mindestvorteil = konfiguration.wert("ueberholen", "min_tempovorteil_kmh")

    koennen = bereichswert(konfiguration, angreifer, BEREICH_DUELL) - bereichswert(
        konfiguration, verteidiger, BEREICH_DUELL
    )
    argument = einstellung["gewicht_koennen"] * koennen / skala + einstellung[
        "gewicht_tempo"
    ] * (tempovorteil_kmh - mindestvorteil) / einstellung["tempo_bezug_kmh"]
    wahrscheinlichkeit = 1.0 / (1.0 + math.exp(-argument)) * faktor
    return float(
        np.clip(
            wahrscheinlichkeit,
            einstellung["wahrscheinlichkeit_min"],
            einstellung["wahrscheinlichkeit_max"],
        )
    )


def rueckstand_in_sekunden(verlauf: Rennverlauf) -> tuple[np.ndarray, np.ndarray]:
    """Echter Zeitrueckstand jedes Autos auf den Fuehrenden.

    Nicht der Abstand in Metern geteilt durch irgendein Tempo: Gemessen
    wird, wann ein Auto den Punkt erreicht hat, an dem der Fuehrende gerade
    ist. Das ist derselbe Rueckstand, den die Seitenleiste zeigt, nur ueber
    die ganze Renndauer.

        rueckstand_i(t) = t_i(d_fuehrend(t)) - t

    Ein Auto erreicht die Stelle, an der der Fuehrende gerade ist, spaeter
    als dieser - der Rueckstand ist also die Zeit, die es noch braucht.

    Weil die Distanz jedes Autos monoton waechst, laesst sich ``t_i`` durch
    Umkehrung der Distanzkurve bestimmen.

    :return: Zeitachse in Sekunden und Rueckstaende der Form
        ``(Bilder, Autos)``
    """
    distanz = verlauf.distanz_m
    alle_zeiten = verlauf.zeitpunkte_ms / 1000.0
    vorne_gesamt = distanz.max(axis=1)

    # Gezeichnet wird nur bis zur Ankunft des Siegers - danach stehen die
    # Autos nach und nach still. Zum Nachschlagen dient aber der ganze
    # Verlauf: Die uebrigen fahren bis zu ihrer eigenen Zielueberfahrt
    # weiter und erreichen die Stelle des Siegers tatsaechlich. So wird
    # nichts extrapoliert.
    siegerzeit = verlauf.ergebnisse[0].zeit_ms / 1000.0
    bis = int(np.searchsorted(alle_zeiten, siegerzeit, "right"))
    zeiten = alle_zeiten[:bis]
    vorne = vorne_gesamt[:bis]

    rueckstand = np.empty((len(zeiten), verlauf.anzahl))
    for i in range(verlauf.anzahl):
        eigene = distanz[:, i]
        werte = np.interp(vorne, eigene, alle_zeiten) - zeiten

        # Ein ueberrundetes Auto erreicht die Endstelle des Siegers nie.
        # Dort ist ein Zeitrueckstand nicht mehr definiert - laut GDD 4
        # heisst es dann "+1 Rd.". Statt einen Randwert zu zeichnen, bleibt
        # die Linie beim letzten gueltigen Wert stehen.
        gueltig = vorne <= eigene[-1]
        if not gueltig.all():
            letzter = int(np.flatnonzero(gueltig)[-1]) if gueltig.any() else 0
            werte[letzter + 1 :] = werte[letzter]
        rueckstand[:, i] = werte
    return zeiten, rueckstand


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
class _Lauf:
    """Zustand waehrend der Simulation.

    Eigene Klasse, damit die Schleife lesbar bleibt und die vielen
    Zustandsfelder nicht als lose Variablen herumliegen.
    """

    def __init__(
        self,
        konfiguration: Konfiguration,
        strecke: Strecke,
        teilnehmer: tuple[Teilnehmer, ...],
        runden: int,
        seedquelle: Seedquelle,
        streckenmittel: float,
        wetter: kern_wetter.Wetterverlauf | None = None,
        ohne_zufall: bool = False,
        streckenverschleiss: float = 1.0,
        kenntnisfaktor: tuple[float, ...] | None = None,
        tagesformbonus: tuple[float, ...] | None = None,
        rhythmusfaktor: tuple[float, ...] | None = None,
        mischungen: tuple[kern_reifen.Mischung, ...] | None = None,
        strategien: tuple[kern_strategie.Strategie, ...] | None = None,
        mischungspflicht: bool = False,
        liga: int | None = None,
    ) -> None:
        self.mischungspflicht = mischungspflicht
        self.liga = liga
        self.k = konfiguration
        self.strecke = strecke
        self.teilnehmer = teilnehmer
        self.runden = runden
        self.anzahl = len(teilnehmer)
        self.seedquelle = seedquelle
        self.wuerfel = seedquelle.zweig("rennen").generator()
        self.wetter = wetter

        self.ds = strecke.punktabstand_m
        self.laenge = strecke.laenge_m
        self.punkte = len(strecke.punkte)
        self.faktor = streckenfaktor(konfiguration, strecke, streckenmittel)

        # Freies Profil je Auto: die Obergrenze ohne andere Autos.
        # Vor dem Rennen wird neu gewuerfelt: Tagesform und
        # Eigenschafts-Zufall, getrennt vom Qualifying (GDD 11).
        self.ohne_zufall = ohne_zufall
        if tagesformbonus is None:
            tagesformbonus = (0.0,) * self.anzahl
        elif len(tagesformbonus) != self.anzahl:
            raise ValueError(
                f"Tagesformbonus fuer {len(tagesformbonus)} Autos, "
                f"im Feld stehen {self.anzahl}"
            )
        if ohne_zufall:
            self.autos = [t.auto for t in teilnehmer]
            self.tagesform = (1.0,) * self.anzahl
        else:
            formen = [
                kern_form.wuerfle(
                    konfiguration,
                    t.auto,
                    seedquelle.zweig("form", nummer),
                    tagesformbonus[nummer],
                )
                for nummer, t in enumerate(teilnehmer)
            ]
            self.autos = [form.auto for form in formen]
            self.tagesform = tuple(form.tagesform for form in formen)

        # Der Rhythmus aus Punkt 15 wirkt auf die Querbeschleunigung in
        # Kurven, bevor das Profil gebildet wird - der Vorteil faellt damit
        # von selbst dort an, wo wirklich Kurven liegen.
        if rhythmusfaktor is not None and len(rhythmusfaktor) != self.anzahl:
            raise ValueError(
                f"Rhythmusfaktor fuer {len(rhythmusfaktor)} Autos, "
                f"im Feld stehen {self.anzahl}"
            )
        grenzen = [grenzen_aus(konfiguration, auto) for auto in self.autos]
        if rhythmusfaktor is not None and not ohne_zufall:
            grenzen = [
                replace(g, quer=g.quer * faktor)
                for g, faktor in zip(grenzen, rhythmusfaktor, strict=True)
            ]
        self.profile = np.array([geschwindigkeitsprofil(strecke, g) for g in grenzen])
        # Grip je Auto und Sektor, gegen die Wetterfaehigkeiten gerechnet.
        # Er wird beim Rundenwechsel neu gesetzt, weil sich das Wetter
        # waehrend des Rennens aendern kann (GDD 7).
        self.grip = np.ones(self.anzahl)
        self.sektorgrenzen = np.array([sektor.von for sektor in strecke.sektoren])
        # Rundenform: je Auto und Runde ein Faktor auf die Rundenzeit
        # (GDD 11). Als Tempofaktor ist es der Kehrwert.
        self.tempoform = np.ones(self.anzahl)
        # Fuer den stehenden Start und das Wiederbeschleunigen hinter einem
        # langsameren Auto.
        self.laengs = np.array([g.laengs for g in grenzen])
        self.ist_zone = np.zeros(self.punkte, dtype=bool)
        for zone in strecke.ueberholzonen:
            indizes = (zone.von + np.arange(zone.punkte)) % self.punkte
            self.ist_zone[indizes] = True
        # Nummer der Geraden je Streckenpunkt, -1 ausserhalb. Der
        # Windschatten wirkt nur auf Geraden und je Gerade nur einmal
        # (Punkt 7), dafuer muss die Simulation sie auseinanderhalten.
        self.geradennummer = np.full(self.punkte, -1, dtype=int)
        geraden = [seg for seg in strecke.segmente if seg.art is Segmentart.GERADE]
        for nummer, segment in enumerate(geraden):
            indizes = (segment.von + np.arange(segment.punkte)) % self.punkte
            self.geradennummer[indizes] = nummer
        self.geraden_je_runde = max(len(geraden), 1)

        self.distanz = np.array(
            [startdistanz_m(konfiguration, t.startplatz) for t in teilnehmer]
        )
        self.reaktion = np.array(
            [reaktionszeit_ms(konfiguration, auto) for auto in self.autos]
        )
        self.tempo = np.zeros(self.anzahl)
        self.aktiv = np.ones(self.anzahl, dtype=bool)
        self.im_ziel = np.zeros(self.anzahl, dtype=bool)
        self.zielzeit: list[int | None] = [None] * self.anzahl

        self.protokolle = tuple(Rundenprotokoll() for _ in range(self.anzahl))
        self.manoever: list[Ueberholmanoever] = []
        # Positionsgewinne je Runde: Wer lag zu Rundenbeginn vor mir, und
        # wen davon habe ich bis zum Rundenende hinter mir gelassen? Zu
        # Beginn ist das die Startaufstellung. Ein ausgefallener Gegner
        # zaehlt nicht mit - an ihm ist niemand vorbeigefahren.
        startplaetze = np.array([t.startplatz for t in teilnehmer])
        self.vorne_bei_rundenbeginn = startplaetze[None, :] < startplaetze[:, None]
        self.positionsgewinne = np.zeros(self.anzahl, dtype=int)
        # Letzte Ueberfahrt je Auto: Startlinie und Sektorgrenzen.
        self.linienzeit = np.zeros(self.anzahl)
        self.markenzeit = np.zeros(self.anzahl)
        self.runden_gefahren = np.zeros(self.anzahl, dtype=int)
        self.naechster_sektor = np.zeros(self.anzahl, dtype=int)
        self.sektor_puffer: list[list[int]] = [[] for _ in range(self.anzahl)]

        self.marken = np.array(
            [sektor.von * self.ds for sektor in strecke.sektoren[1:]] + [self.laenge]
        )

        self.max_abstand_s = konfiguration.wert("ueberholen", "max_abstand_s")
        self.unfall_abstand_m = konfiguration.wert("unfaelle", "max_abstand_m")
        self.dt_s = konfiguration.wert("simulation", "zeitschritt_ms") / 1000.0
        # Der Wetter-Multiplikator auf Fehler und Unfaelle (GDD 7).
        self.wetter_fehlerfaktor = 1.0
        # Der Wetter-Multiplikator auf den Verschleiss (GDD 7). Der
        # Aufschlag fuer den falschen Reifen steckt nicht hier, sondern in
        # der Verschleissrate je Auto - sonst kaeme er zweimal.
        self.wetter_verschleiss = 1.0
        self.min_vorteil = konfiguration.wert("ueberholen", "min_tempovorteil_kmh") / KMH_JE_MS
        self.sieger_zeit: float | None = None
        self.laufende_nummer = np.arange(self.anzahl)
        self.index = np.zeros(self.anzahl, dtype=int)
        # --- Reifen (GDD 4) -------------------------------------------
        renndistanz = runden * self.laenge
        # Der Verschleiss ist zwar nicht zufaellig, macht die Rundenzeit
        # aber vom Rennfortschritt abhaengig. GDD 9 kalibriert auf einer
        # festen Rundenzeit, deshalb faellt er im zufallsfreien Modus mit
        # weg - sonst waere ein Auto im Rennen langsamer als in der
        # Einzelrunde und die Kalibrierung liefe ins Leere.
        # Punkt 39: Der Verschleiss haengt an der Strecke und der
        # Mischung, nicht mehr an der Renndistanz - sonst hielte ein Satz
        # per Konstruktion genau ein Rennen und Stopps waeren sinnlos.
        self.strategien = list(strategien) if strategien is not None else None
        if self.strategien is not None and len(self.strategien) != self.anzahl:
            raise ValueError(
                f"Strategien fuer {len(self.strategien)} Autos, "
                f"im Feld stehen {self.anzahl}"
            )
        # Punkt 39: Je Fahrer und Mischung ein kleiner Verschleisswurf,
        # jedes Rennen neu. Er steht nicht in der Vorausberechnung der
        # Varianten - deshalb wird er hier gezogen und nicht dort.
        self._streuung: list[dict[str, kern_reifen.Mischung]] = [
            {} for _ in range(self.anzahl)
        ]
        gewaehlt = (
            [s.mischungen[0] for s in self.strategien]
            if self.strategien is not None
            else list(
                mischungen
                if mischungen is not None
                else [kern_reifen.standardmischung(konfiguration)] * self.anzahl
            )
        )
        self.mischungen = [self._gestreut(i, m) for i, m in enumerate(gewaehlt)]
        self.streckenverschleiss = streckenverschleiss
        # Wie nass es gerade ist. Die Rate haengt daran, deshalb wird sie
        # neu gesetzt, sobald sich die Lage oder die Mischung aendert.
        self.naesse_jetzt = (
            kern_reifen.naesse_von(konfiguration, wetter.startzustand)
            if wetter is not None
            else 0.0
        )
        self.verschleiss_je_meter = np.zeros(self.anzahl)
        if not ohne_zufall:
            for i in range(self.anzahl):
                self._setze_verschleissrate(i)
        self.verschleiss = np.zeros(self.anzahl)
        self.reifen_tempo = np.ones(self.anzahl)
        self.reifen_fehler = np.ones(self.anzahl)
        self._richte_boxengasse_ein(grenzen)

        # --- Ueber die Distanz (Punkte 9, 11 und 20) ------------------
        # Ermuedung, kalte Reifen und nachlassende Bremsen haengen alle an
        # der schon gefahrenen Distanz. Die Betraege je Auto stehen fest;
        # sie werden hier einmal geholt, damit die Schleife nur noch
        # rechnet. Wie Reifen und Streckenkenntnis fallen sie im
        # zufallsfreien Modus weg - GDD 9 kalibriert die blanke Runde.
        self.renndistanz = float(renndistanz)
        self.ermuedung_beginn = konfiguration.wert("ermuedung", "beginn_anteil_distanz")
        self.aufwaermstrecke = (
            konfiguration.wert("kaltreifen", "aufwaermstrecke_runden") * self.laenge
        )
        self.ermuedung_verlust = np.zeros(self.anzahl)
        self.kaltreifen_verlust = np.zeros(self.anzahl)
        # Zweites Profil mit der Bremsgrenze des Rennendes. Die
        # Bremskuehlung senkt die *Grenze*, nicht das Tempo: Was sie
        # kostet, haengt davon ab, wie viel auf der Strecke gebremst wird.
        # Zwischen beiden Profilen wird nach gefahrener Distanz gemischt.
        self.profil_ende = self.profile
        if not ohne_zufall:
            self.ermuedung_verlust = np.array(
                [
                    kern_tempoverlauf.ermuedungsverlust(konfiguration, auto)
                    for auto in self.autos
                ]
            )
            self.kaltreifen_verlust = np.array(
                [
                    kern_tempoverlauf.kaltreifenverlust(konfiguration, auto)
                    for auto in self.autos
                ]
            )
            self.profil_ende = np.array(
                [
                    geschwindigkeitsprofil(
                        strecke,
                        replace(
                            g,
                            brems=kern_tempoverlauf.bremsgrenze_am_ende(
                                konfiguration, auto, g.brems
                            ),
                        ),
                    )
                    for auto, g in zip(self.autos, grenzen, strict=True)
                ]
            )

        # --- Windschatten (Punkt 7) -----------------------------------
        # Der Sog haengt am Abstand zum Vordermann und gilt je Gerade
        # einmal. ``sog_verbraucht`` merkt sich, auf welcher Geraden
        # welcher Runde ein Auto ihn schon aufgebraucht hat - das ist der
        # Fall, sobald es einmal auf gleicher Hoehe war, also vorbeikam.
        # Wie Reifen und Streckenkenntnis faellt er im zufallsfreien Modus
        # weg: GDD 9 kalibriert das einzelne Auto auf freier Strecke.
        self.sog_gewinn = np.zeros(self.anzahl)
        if not ohne_zufall:
            self.sog_gewinn = np.array(
                [kern_windschatten.gewinn(konfiguration, auto) for auto in self.autos]
            )
        self.sog_fenster = kern_windschatten.fenster_m(konfiguration)
        self.sog_verbraucht = np.full(self.anzahl, -1, dtype=int)
        # Nachlauf: Wer vorbei ist, faellt nicht schlagartig aus dem Sog.
        # ``sog_nachlauf_bis`` ist die Distanz, bis zu der der Ueberschuss
        # in voller Hoehe gilt; danach bleibt sein halber Teil bis zum
        # Ende derselben Geraden, also bis zum Anbremsen.
        self.sog_nachlauf_m = kern_windschatten.nachlauf_m(konfiguration)
        self.sog_nachlauf_anteil = kern_windschatten.nachlauf_anteil(konfiguration)
        self.sog_nachlauf_ueberholter = kern_windschatten.nachlauf_anteil_ueberholter(
            konfiguration
        )
        self.sog_nachlauf_bis = np.zeros(self.anzahl)
        self.sog_nachlauf_wert = np.zeros(self.anzahl)
        # Zwei Stufen, je Auto ein Faktor auf den Ueberschuss: bis
        # ``sog_nachlauf_bis`` die erste, danach die zweite. Der
        # Ueberholende faehrt 1,0 und dann die Haelfte, der Ueberholte
        # zunaechst gar nichts und danach die Haelfte davon.
        self.sog_nachlauf_erst = np.zeros(self.anzahl)
        self.sog_nachlauf_dann = np.zeros(self.anzahl)
        # Der Ueberschuss dieses Zeitschritts - beim Vorbeifahren wird er
        # in den Nachlauf uebernommen.
        self.sog_jetzt = np.zeros(self.anzahl)

        # --- Zwischenfaelle (GDD 4 und 14) ----------------------------
        self.zwischenfaelle: list[kern_zwischenfall.Zwischenfall] = []
        self.defekt_tempo = np.ones(self.anzahl)
        self.defekte_je_auto: list[list[dict]] = [[] for _ in range(self.anzahl)]
        # Zeit, die ein Auto nach einem Fehler noch steht.
        self.pause_ms = np.zeros(self.anzahl)
        self.ausfaelle = 0
        self.ausfallgrenze = (
            0 if ohne_zufall else kern_zwischenfall.ausfallgrenze(konfiguration, self.wuerfel)
        )

        # --- Streckenkenntnis (GDD 6) ---------------------------------
        # Ein fester Faktor je Auto ueber die ganze Session. Wie der
        # Reifenverschleiss faellt er im zufallsfreien Modus weg, weil
        # GDD 9 die Kalibrierung auf der blanken Runde festlegt.
        self.kenntnis_tempo = np.ones(self.anzahl)
        if kenntnisfaktor is not None and not ohne_zufall:
            if len(kenntnisfaktor) != self.anzahl:
                raise ValueError(
                    f"Kenntnisfaktor fuer {len(kenntnisfaktor)} Autos, "
                    f"im Feld stehen {self.anzahl}"
                )
            self.kenntnis_tempo = np.array(kenntnisfaktor, dtype=float)

        self._setze_rundenform(0)
        self._setze_grip(0.0)

    def _setze_verschleissrate(self, i: int) -> None:
        """Wie schnell dieses Auto gerade Profil verliert, je Meter.

        Die Naesse geht hier ein, nicht als Faktor obendrauf: Sonst
        gaelte ein Intermediate der Rechnung erst als passend und dann
        noch einmal als Fehlgriff. Der reine Wetterfaktor aus GDD 7 kommt
        getrennt dazu, weil er nicht an der Mischung haengt.
        """
        if self.ohne_zufall:
            return
        self.verschleiss_je_meter[i] = kern_reifen.verschleiss_je_meter(
            self.k,
            self.autos[i],
            self.mischungen[i],
            self.streckenverschleiss,
            1.0,
            self.naesse_jetzt,
        )

    # -- Boxenstopps (Punkt 39) -------------------------------------------
    def _gestreut(self, i: int, misch: kern_reifen.Mischung) -> kern_reifen.Mischung:
        """Die Mischung mit dem Verschleisswurf dieses Fahrers.

        Je Fahrer und Mischung genau ein Wurf je Rennen: Wer zweimal auf
        dieselbe Mischung wechselt, bekommt beide Male denselben Satz -
        sonst wuerfelte jeder Stopp die Haltbarkeit neu.
        """
        if self.ohne_zufall:
            return misch
        bekannt = self._streuung[i].get(misch.schluessel)
        if bekannt is None:
            bekannt = kern_reifen.mit_streuung(
                self.k, misch, self.seedquelle.zweig("reifenstreuung", i)
            )
            self._streuung[i][misch.schluessel] = bekannt
        return bekannt

    def _richte_boxengasse_ein(self, grenzen) -> None:
        """Legt Boxenprofil, Stoppfenster und Standzeiten an.

        Das Boxenprofil ist dasselbe Geschwindigkeitsprofil wie sonst,
        nur mit dem Deckel von 80 km/h auf der Boxengasse. Es traegt das
        Bremsen davor und das Beschleunigen danach schon in sich - der
        Zeitverlust entsteht also von selbst und muss nicht aufaddiert
        werden. Genau diese Differenz rechnet
        ``boxenstopp.durchfahrtsverlust_ms`` dem Schnellmodus vor.
        """
        self.faehrt_stopps = self.strategien is not None and not self.ohne_zufall
        self.boxenstopps: list[Boxenstopp] = []
        self.bremsverlust = np.array(
            [kern_boxenstopp.bremsverlust_ms(self.k, g, self.liga) for g in grenzen],
            dtype=float,
        )
        # Das Fenster des naechsten Stopps, in gefahrenen Metern. Es
        # bleibt nach dem Wechsel stehen, bis das Auto die Boxengasse
        # verlassen hat - sonst faehrt es mit vollem Tempo heraus und der
        # halbe Zeitverlust faellt unter den Tisch.
        self.box_von_m = np.full(self.anzahl, np.inf)
        self.box_bis_m = np.full(self.anzahl, -np.inf)
        # Ob in diesem Fenster noch gewechselt wird.
        self.box_offen = np.zeros(self.anzahl, dtype=bool)
        # Ob das Fenster einem Wetterwechsel gilt und nicht dem Plan.
        self.box_notstopp = np.zeros(self.anzahl, dtype=bool)
        # In welcher Runde das offene Fenster liegt - 0 heisst: keines.
        self.box_runde = np.zeros(self.anzahl, dtype=int)
        self.stint = np.zeros(self.anzahl, dtype=int)
        self.stopp_nummer = np.zeros(self.anzahl, dtype=int)
        self.runde_letzter_stopp = np.zeros(self.anzahl, dtype=int)
        if not self.faehrt_stopps:
            self.profil_box = self.profile
            return

        von, bis = kern_boxenstopp.abschnitt(self.k, self.strecke)
        if von <= bis:  # pragma: no cover - alle 20 Strecken laufen ueber die Linie
            raise kern_boxenstopp.BoxenstoppFehler(
                f"Die Boxengasse von {self.strecke.name} laeuft nicht ueber die Linie"
            )
        self.profil_box = np.array(
            [
                geschwindigkeitsprofil(
                    self.strecke,
                    g,
                    limit=kern_boxenstopp.gedeckeltes_limit(
                        self.k, self.strecke, g, liga=self.liga
                    ),
                )
                for g in grenzen
            ]
        )
        # Das Fenster ist nicht der Abschnitt selbst: Gebremst wird lange
        # davor, beschleunigt lange danach. Beides steht schon im
        # Boxenprofil, also wird das Fenster daraus abgelesen - der
        # Bereich um die Ziellinie, in dem sich die beiden Profile
        # unterscheiden. In Suzuka sind das 100 Meter Abschnitt vor der
        # Linie, aber 400 Meter Bremsweg.
        self.box_vor_linie_m = np.zeros(self.anzahl)
        self.box_nach_linie_m = np.zeros(self.anzahl)
        for i in range(self.anzahl):
            anders = np.abs(self.profil_box[i] - self.profile[i]) > 1e-6
            nach = int(np.argmin(anders)) if not anders.all() else self.punkte
            rueckwaerts = anders[::-1]
            vor = int(np.argmin(rueckwaerts)) if not rueckwaerts.all() else self.punkte
            self.box_vor_linie_m[i] = vor * self.ds
            self.box_nach_linie_m[i] = nach * self.ds
            self._plane_stopp(i)

    def _setze_fenster(self, i: int, runde: int, notstopp: bool) -> None:
        """Oeffnet das Boxenfenster um die Ziellinie dieser Runde."""
        linie = runde * self.laenge
        self.box_von_m[i] = linie - self.box_vor_linie_m[i]
        self.box_bis_m[i] = linie + self.box_nach_linie_m[i]
        self.box_offen[i] = True
        self.box_notstopp[i] = notstopp
        self.box_runde[i] = runde

    def _schliesse_fenster(self, i: int) -> None:
        self.box_von_m[i] = np.inf
        self.box_bis_m[i] = -np.inf
        self.box_offen[i] = False
        self.box_notstopp[i] = False
        self.box_runde[i] = 0

    def _plane_stopp(self, i: int) -> None:
        """Legt das Boxenfenster fuer den naechsten geplanten Stopp."""
        if not self.faehrt_stopps:
            return
        stopps = self.strategien[i].stopps
        stelle = int(self.stopp_nummer[i])
        if stelle >= len(stopps):
            self._schliesse_fenster(i)
            return
        self._setze_fenster(i, stopps[stelle], False)

    def _raeume_boxengasse(self) -> None:
        """Wer die Ausfahrt hinter sich hat, bekommt sein naechstes Fenster.

        Das Fenster bleibt bis hierher stehen, damit die Ausfahrt noch auf
        dem gedeckelten Profil gefahren wird.
        """
        if not self.faehrt_stopps:
            return
        fertig = (self.distanz >= self.box_bis_m) & ~self.box_offen
        for i in np.flatnonzero(fertig):
            self._plane_stopp(int(i))

    def _wechsle_reifen(self, i: int, ueberfahrt: float, neu, notstopp: bool) -> None:
        """Faehrt den Stopp: Standzeit, frische Reifen, neue Mischung."""
        neu = self._gestreut(i, neu)
        standzeit = kern_boxenstopp.standzeit_ms(
            self.k, self.seedquelle.zweig("standzeit", i, len(self.boxenstopps))
        )
        alt = self.mischungen[i]
        self.boxenstopps.append(
            Boxenstopp(
                teilnehmer=i,
                runde=int(self.runden_gefahren[i]),
                zeit_ms=int(round(ueberfahrt)),
                von=alt.kuerzel,
                nach=neu.kuerzel,
                restprofil=float(np.clip(1.0 - self.verschleiss[i], 0.0, 1.0)),
                standzeit_ms=standzeit,
                notstopp=notstopp,
            )
        )
        self.mischungen[i] = neu
        self.verschleiss[i] = 0.0
        self._setze_verschleissrate(i)
        self._setze_reifen(i)
        # Die Standzeit laeuft ueber dieselbe Uhr wie die Pause nach einem
        # Fehler: Das Auto steht, die anderen fahren vorbei. Dazu der
        # Bremsverlust: Die Simulation bremst ohne Zeitverlust, weil das
        # Geschwindigkeitsprofil die Bremszonen schon eingerechnet hat -
        # fuer den Halt in der Box muss er deshalb ausdruecklich dazu. Das
        # Anfahren danach entsteht von selbst, es steckt in der
        # Beschleunigungsgrenze.
        halt = standzeit + self.bremsverlust[i]
        self.pause_ms[i] = max(float(self.pause_ms[i]), float(halt))
        self.runde_letzter_stopp[i] = int(self.runden_gefahren[i])

    def _pruefe_boxenstopp(self, i: int, ueberfahrt: float) -> None:
        """Geplanter Stopp oder Notstopp wegen Wetterwechsels (Punkt 39).

        Laeuft bei jeder Ueberfahrt der Ziellinie - dort steht die Box.
        Ist das Fenster offen, wird gewechselt; sonst wird geprueft, ob das
        Wetter einen ausserplanmaessigen Stopp erzwingt. Der wird fuer die
        **naechste** Runde angesetzt, nicht fuer diese: Der Fahrer merkt
        es auf der Strecke und kommt eine Runde spaeter herein - vorher
        haette das Auto die Boxengasse schon mit vollem Tempo passiert.
        """
        if not self.faehrt_stopps or self.im_ziel[i] or not self.aktiv[i]:
            return
        # Wer das Rennen hinter sich hat, kommt nicht mehr herein - auch
        # nicht, wenn der Sieger eben erst durchgefahren ist.
        if self.runden_gefahren[i] >= self.runden or self.sieger_zeit is not None:
            return

        runde = int(self.runden_gefahren[i])
        if self.box_offen[i] and self.box_von_m[i] <= runde * self.laenge < self.box_bis_m[i]:
            self._fahre_stopp(i, ueberfahrt)
            return
        # Kommt der geplante Stopp naechste Runde, der Satz ist aber noch
        # zu gut? Dann eine Runde weiter - so lange, bis er unter die
        # Schwelle faellt. Entschieden wird das **eine Runde vorher**:
        # Sonst faehrt das Auto schon langsam in die Boxengasse ein und
        # dann doch daran vorbei.
        if self._verschiebt_planstopp(i, runde):
            return
        # Der Auftraggeber hat die Frist gesetzt: hoechstens drei Runden
        # auf dem falschen Reifen, und mindestens drei Runden zwischen
        # zwei Stopps. Das gilt auch, wenn noch ein geplanter Stopp
        # aussteht: Der Notstopp geht vor und schiebt den geplanten nach
        # hinten - sonst faehrt ein Auto mit drei Planstopps das ganze
        # Rennen auf Trockenreifen durch den Regen.
        if self.wetter is None or self.box_notstopp[i]:
            return
        naesse = kern_reifen.naesse_von(self.k, self.wetter.zustand_zu(ueberfahrt))
        seit = runde - int(self.runde_letzter_stopp[i])
        if not kern_strategie.notstopp(self.k, self.mischungen[i], naesse, seit):
            return
        if kern_strategie.passende_mischung(self.k, naesse).kuerzel == self.mischungen[i].kuerzel:
            return
        if runde + 1 > self.runden - self.k.wert("boxenstopp", "strategie", "sperre_runden"):
            # So kurz vor Schluss wird durchgefahren.
            return
        self._setze_fenster(i, runde + 1, True)

    def _zur_lage(self, geplant, ueberfahrt: float):
        """Der geplante Reifen - oder der passende, wenn er nicht mehr passt."""
        if self.wetter is None:
            return geplant
        naesse = kern_reifen.naesse_von(self.k, self.wetter.zustand_zu(ueberfahrt))
        grenze = self.k.wert("boxenstopp", "strategie", "eignungsgrenze")
        if abs(geplant.naesse - naesse) <= grenze:
            return geplant
        return kern_strategie.passende_mischung(self.k, naesse)

    def _verschiebt_planstopp(self, i: int, runde: int) -> bool:
        """Schiebt einen geplanten Stopp, solange der Satz zu gut dafuer ist.

        Der Auftraggeber hat die Schwelle gesetzt: Ueber
        ``planstopp_ab_restprofil`` wird nicht gewechselt, sondern Runde
        um Runde weitergefahren. Gerechnet wird mit dem Profil, das am
        Ende der **naechsten** Runde uebrig sein wird - denn dort liegt
        der Stopp.

        Ein Notstopp wird nie verschoben: Der falsche Reifen wird nicht
        besser, wenn man laenger darauf faehrt.
        """
        if not self.box_offen[i] or self.box_notstopp[i]:
            return False
        if int(self.box_runde[i]) != runde + 1:
            return False
        schwelle = self.k.wert("boxenstopp", "strategie", "planstopp_ab_restprofil")
        naechste = float(
            self.verschleiss[i]
            + self.verschleiss_je_meter[i] * self.laenge * self.wetter_verschleiss
        )
        if 1.0 - naechste <= schwelle:
            return False

        einstellung = self.k.wert("boxenstopp", "strategie")
        spaeteste = self.runden - einstellung["sperre_runden"]
        if runde + 2 <= spaeteste:
            self._setze_fenster(i, runde + 2, False)
            return True

        # Weiter geht es nicht. Wer schon gewechselt hat, faehrt einfach
        # durch - der Satz traegt ja. Wer noch auf seinem ersten steht,
        # muss trotzdem herein: Zwei Mischungen sind Pflicht, und die
        # Verschiebung darf die Regel nicht aushebeln.
        gewechselt = any(b.teilnehmer == i for b in self.boxenstopps)
        if gewechselt or not self.mischungspflicht:
            self.stopp_nummer[i] = len(self.strategien[i].stopps)
            self._schliesse_fenster(i)
            return True
        if int(self.box_runde[i]) != spaeteste:
            self._setze_fenster(i, spaeteste, False)
            return True
        return False

    def _fahre_stopp(self, i: int, ueberfahrt: float) -> None:
        """Wechselt an der Box - geplant oder wegen des Wetters."""
        if self.box_notstopp[i]:
            naesse = (
                kern_reifen.naesse_von(self.k, self.wetter.zustand_zu(ueberfahrt))
                if self.wetter is not None
                else 0.0
            )
            neu = kern_strategie.passende_mischung(self.k, naesse)
            self._wechsle_reifen(i, ueberfahrt, neu, True)
            self.box_offen[i] = False
            self._schiebe_stopp(i)
            return

        strategie = self.strategien[i]
        stelle = min(int(self.stint[i]) + 1, len(strategie.mischungen) - 1)
        self.stint[i] = stelle
        self.stopp_nummer[i] += 1
        geplant = strategie.mischungen[stelle]
        # Der Plan steht vor dem Rennen, das Wetter kann sich seither
        # gedreht haben. Passt der geplante Reifen nicht mehr zur Lage,
        # kommt der auf, der passt - sonst faehrt ein Auto bei einem
        # Planstopp im Regen wieder Slicks auf und muss zwei Runden
        # spaeter zum Notstopp herein.
        self._wechsle_reifen(i, ueberfahrt, self._zur_lage(geplant, ueberfahrt), False)
        # Das Fenster bleibt bis zur Ausfahrt stehen; erst danach wird der
        # naechste Stopp geplant (siehe _raeume_boxengasse).
        self.box_offen[i] = False

    def _schiebe_stopp(self, i: int) -> None:
        """Haelt den Mindestabstand nach einem Notstopp ein.

        Der geplante Stopp rutscht so weit nach hinten, dass zwischen zwei
        Stopps die Mindestrunden liegen. Passt er dann nicht mehr ins
        Rennen, faellt er weg - das Auto hat ja eben frische Reifen
        bekommen.
        """
        stopps = list(self.strategien[i].stopps)
        stelle = int(self.stopp_nummer[i])
        if stelle >= len(stopps):
            return
        einstellung = self.k.wert("boxenstopp", "strategie")
        frueheste = int(self.runden_gefahren[i]) + einstellung["abstand_min_runden"]
        if stopps[stelle] >= frueheste:
            return
        if frueheste > self.runden - einstellung["sperre_runden"]:
            self.stopp_nummer[i] = len(stopps)
        else:
            stopps[stelle] = frueheste
            self.strategien[i] = replace(self.strategien[i], stopps=tuple(stopps))

    def _setze_grip(self, zeit_ms: float) -> None:
        """Grip je Auto zum Zeitpunkt, mit Wetterkoennen (GDD 7).

        Der Grip wirkt als Faktor auf das Tempo; die Beschleunigungsgrenze
        skaliert deshalb quadratisch mit - genau wie im Profil.
        """
        if self.wetter is None:
            return
        zustand = self.wetter.zustand_zu(zeit_ms)
        self.wetter_fehlerfaktor = float(
            self.k.wert("wetter", "zustand", zustand)["fehlerquote"]
        )
        # Punkt 39: Das Wetter zehrt an den Reifen (GDD 7), und wer den
        # falschen Reifen fuer die Lage faehrt, zusaetzlich. Bisher stand
        # beides nur im Schnellmodus - in der vollen Simulation kostete
        # ein Regenrennen gar nichts.
        #
        # Der Aufschlag fuer den falschen Reifen steckt in
        # ``verschleiss_je_meter`` selbst, sobald man ihm die Naesse
        # nennt; er darf deshalb **nicht** noch einmal obendrauf. Ohne
        # Naesse rechnet die Funktion mit trockener Strecke, und ein
        # Intermediate gilt ihr dann schon als Fehlgriff.
        self.wetter_verschleiss = float(kern_wetter.verschleissfaktor(self.k, zustand))
        naesse = kern_reifen.naesse_von(self.k, zustand)
        if naesse != self.naesse_jetzt:
            self.naesse_jetzt = naesse
            for i in range(self.anzahl):
                self._setze_verschleissrate(i)
                self._setze_reifen(i)
        # Im Rennen wird der Grip ueber die Sektoren gemittelt: Die Autos
        # sind gleichzeitig an verschiedenen Stellen der Runde.
        roh = sum(
            self.wetter.grip_zu(zeit_ms, sektor.nummer) for sektor in self.strecke.sektoren
        ) / len(self.strecke.sektoren)
        self.grip = np.array(
            [kern_wetter.grip_fuer(self.k, auto, zustand, roh) for auto in self.autos]
        )

    def _setze_rundenform(self, runde: int) -> None:
        """Zieht fuer jedes Auto die Rundenform dieser Runde (GDD 11)."""
        if self.ohne_zufall:
            return
        faktoren = [
            kern_form.rundenform(self.k, auto, self.seedquelle.zweig("rundenform", i), runde)
            for i, auto in enumerate(self.autos)
        ]
        # Der Wurf gilt der Rundenzeit; als Tempofaktor ist es der Kehrwert.
        self.tempoform = 1.0 / np.array(faktoren)

    # -- ein Zeitschritt ---------------------------------------------------
    def schritt(self, zeit_ms: int, dt: float) -> None:
        ende_ms = zeit_ms + dt * 1000.0
        # Faellt die Reaktionszeit mitten in den Schritt, faehrt das Auto
        # nur den Rest davon. Sonst gingen Unterschiede unter 50 ms
        # verloren - die Spanne betraegt laut GDD 4 aber nur 200 ms.
        wirksam = np.clip((ende_ms - self.reaktion) / 1000.0, 0.0, dt)

        ziel = self._ziel_tempo(zeit_ms)
        # Aus dem Stand und hinter einem langsameren Auto wird mit der
        # eigenen Beschleunigungsgrenze aufgeholt, nicht gesprungen. Der
        # Grip senkt auch sie, und zwar quadratisch (siehe kern.tempo).
        self.tempo = np.minimum(ziel, self.tempo + self.laengs * self.grip**2 * dt)
        self.tempo = np.where(wirksam > 0.0, self.tempo, 0.0)

        vorher = self.distanz.copy()
        faehrt = self.aktiv & ~self.im_ziel
        self.distanz[faehrt] += self.tempo[faehrt] * wirksam[faehrt]

        # Reifen bauen mit jedem gefahrenen Meter ab (GDD 4). Das Wetter
        # zehrt mit (GDD 7), und der falsche Reifen fuer die Lage zehrt
        # zusaetzlich (Punkt 39) - beides steckt in
        # ``wetter_verschleiss`` und wird beim Rundenwechsel gesetzt.
        self.verschleiss += (
            (self.distanz - vorher) * self.verschleiss_je_meter * self.wetter_verschleiss
        )
        # Eine angefangene Pause nach einem Fehler laeuft ab.
        self.pause_ms = np.maximum(self.pause_ms - dt * 1000.0, 0.0)

        self._pruefe_marken(vorher, zeit_ms, dt)
        # Wer die Boxengasse verlassen hat, bekommt sein naechstes Fenster.
        self._raeume_boxengasse()

    def _ziel_tempo(self, zeit_ms: int) -> np.ndarray:
        """Tempo, das ein Auto anstrebt: freies Profil, gedeckelt durch
        Folgen und Ueberholen (GDD 4).

        Die teuren Teile sind ueber alle Autos auf einmal gerechnet; die
        Schleife laeuft nur ueber die wenigen Paare, die sich tatsaechlich
        nahe genug sind.
        """
        # Vor Ablauf der Reaktionszeit steht das Auto (GDD 4).
        # Wer nach einem Fehler noch steht, faehrt nicht (GDD 4).
        faehrt = self.aktiv & ~self.im_ziel & (self.pause_ms <= 0.0)

        # Zwischen den Profilpunkten wird linear interpoliert. Ohne das
        # zielt ein Auto auf das Tempo des schon passierten Punktes und
        # hinkt durch die Beschleunigungsgrenze dauerhaft einen Punkt
        # hinterher - auf einer Runde kostet das ueber eine Sekunde.
        stelle = np.maximum(self.distanz, 0.0) / self.ds
        index = np.mod(np.floor(stelle).astype(int), self.punkte)
        danach = np.mod(index + 1, self.punkte)
        rest = stelle - np.floor(stelle)

        self.index = index
        hier = self.profile[self.laufende_nummer, index]
        dort = self.profile[self.laufende_nummer, danach]

        # Anteil der Renndistanz - daran haengen die drei Verlaeufe aus
        # kern.tempoverlauf.
        anteil = (
            np.clip(self.distanz / self.renndistanz, 0.0, 1.0)
            if self.renndistanz > 0.0
            else np.zeros(self.anzahl)
        )
        if self.profil_ende is not self.profile:
            # Die Bremsen lassen ueber die Distanz nach (Punkt 20).
            ende_hier = self.profil_ende[self.laufende_nummer, index]
            ende_dort = self.profil_ende[self.laufende_nummer, danach]
            hier = hier + anteil * (ende_hier - hier)
            dort = dort + anteil * (ende_dort - dort)

        # Punkt 39: Wer zum Stopp hereinkommt, faehrt vom Bremspunkt vor
        # der Boxengasse bis zur Ausfahrt danach auf dem gedeckelten
        # Profil. Alles andere daran bleibt, wie es ist - das Boxenprofil
        # unterscheidet sich vom freien nur an dieser Stelle der Runde.
        if self.faehrt_stopps:
            in_box = (self.distanz >= self.box_von_m) & (self.distanz < self.box_bis_m)
            if in_box.any():
                hier = np.where(in_box, self.profil_box[self.laufende_nummer, index], hier)
                dort = np.where(in_box, self.profil_box[self.laufende_nummer, danach], dort)

        # Ermuedung ab der halben Distanz (GDD 8, Bereich er) und kalte
        # Reifen in der ersten Runde (Punkt 48).
        offen = max(1.0 - self.ermuedung_beginn, 1e-9)
        fortschritt = np.clip((anteil - self.ermuedung_beginn) / offen, 0.0, 1.0)
        ermuedung_tempo = 1.0 - self.ermuedung_verlust * fortschritt
        kalt = (
            np.clip(1.0 - np.maximum(self.distanz, 0.0) / self.aufwaermstrecke, 0.0, 1.0)
            if self.aufwaermstrecke > 0.0
            else np.zeros(self.anzahl)
        )
        kaltreifen_tempo = 1.0 - self.kaltreifen_verlust * kalt

        # Grip aus dem Wetter, Rundenform, Reifenzustand, aktive Defekte
        # und die Streckenkenntnis wirken alle als Faktor aufs Tempo.
        frei = (
            (hier + rest * (dort - hier))
            * self.grip
            * self.tempoform
            * self.reifen_tempo
            * self.defekt_tempo
            * self.kenntnis_tempo
            * ermuedung_tempo
            * kaltreifen_tempo
        )
        ziel = np.where(faehrt, frei, 0.0)

        # Reihenfolge nach zurueckgelegter Strecke; danach steht fest, wer
        # vor wem faehrt.
        reihenfolge = np.argsort(-self.distanz)
        vorne = reihenfolge[:-1]
        hinten = reihenfolge[1:]

        abstand_m = self.distanz[vorne] - self.distanz[hinten]

        # --- Windschatten (Punkt 7) -----------------------------------
        # Im Fenster von 30 m bis auf gleiche Hoehe steigt das moegliche
        # Tempo des Verfolgers, dicht dahinter am staerksten. Nur auf
        # Geraden, und je Gerade nur einmal: Wer einmal auf gleicher Hoehe
        # war, ist aus dem Sog heraus.
        #
        # Der Sog wirkt auf ``ziel``, bevor die Folgeregel greift. Damit
        # waechst der Tempovorteil, mit dem gleich das Ueberholen
        # gewuerfelt wird - genau dafuer ist er da.
        self.sog_jetzt[:] = 0.0
        if self.sog_fenster > 0.0:
            # Der Sog haengt an der Position **auf der Runde**, nicht an
            # der gesamt gefahrenen Strecke: Wer einen Ueberrundeten
            # einholt, faehrt hinter ihm her und bekommt seinen Sog, auch
            # wenn zwischen beiden auf dem Papier eine ganze Runde liegt.
            # Verkehr, Ueberholen und Unfaelle bleiben davon unberuehrt -
            # die rechnen weiter auf der Gesamtdistanz.
            sog_hinten, sog_vorne, lueck = self._sogpaare()
            gerade = self.geradennummer[index[sog_hinten]]
            # Wer ueberrundet wird, bekommt vom Ueberrundenden nichts:
            # Liegt der Vordermann eine gute halbe Runde weiter, ist er
            # eine Runde voraus - dann ist es sein Sog, nicht meiner.
            wird_ueberrundet = (
                self.distanz[sog_vorne] - self.distanz[sog_hinten] > self.laenge * 0.5
            )
            im_fenster = (
                faehrt[sog_hinten]
                & faehrt[sog_vorne]
                & (lueck > 0.0)
                & (lueck < self.sog_fenster)
                & ~wird_ueberrundet
                & (gerade >= 0)
                & (self._gerade_id(sog_hinten, gerade) != self.sog_verbraucht[sog_hinten])
            )
            if im_fenster.any():
                anteil = np.where(im_fenster, 1.0 - lueck / self.sog_fenster, 0.0)
                self.sog_jetzt[sog_hinten] = self.sog_gewinn[sog_hinten] * anteil
                ziel[sog_hinten] = ziel[sog_hinten] * (1.0 + self.sog_jetzt[sog_hinten])

        # --- Nachlauf des Windschattens -------------------------------
        # Der Ueberschuss endet nicht in dem Augenblick, in dem das Auto
        # vorbei ist: Er gilt noch ``sog_nachlauf_m`` Meter voll und
        # danach zur Haelfte, bis dieselbe Gerade zu Ende ist. Sobald das
        # Profil faellt, wird angebremst - dort ist Schluss, sonst traege
        # das Auto zu viel Tempo in die Kurve.
        if self.sog_nachlauf_m > 0.0:
            jetzt = self.geradennummer[index]
            kennung = self.runden_gefahren * self.geraden_je_runde + np.maximum(jetzt, 0)
            ueberschuss = self.sog_nachlauf_wert * np.where(
                self.distanz <= self.sog_nachlauf_bis,
                self.sog_nachlauf_erst,
                self.sog_nachlauf_dann,
            )
            laeuft_nach = (
                faehrt
                & (jetzt >= 0)
                & (kennung == self.sog_verbraucht)
                & (dort >= hier)
                & (ueberschuss > 0.0)
            )
            if laeuft_nach.any():
                ziel = np.where(laeuft_nach, ziel * (1.0 + ueberschuss), ziel)

        # Unfaelle haengen allein am Abstand (GDD 4: unter 30 m), nicht am
        # engeren Fenster fuers Ueberholen.
        in_reichweite = (
            faehrt[hinten] & faehrt[vorne] & (abstand_m < self.unfall_abstand_m)
        )
        for paar in np.flatnonzero(in_reichweite):
            self._prueft_unfall(int(hinten[paar]), int(vorne[paar]), zeit_ms)

        tempo_hinten = ziel[hinten]
        # Nur Paare betrachten, bei denen beide fahren und der Abstand
        # unter der Schwelle aus GDD 4 liegt.
        nah = (
            faehrt[hinten]
            & faehrt[vorne]
            & (tempo_hinten > 0.0)
            & (abstand_m < tempo_hinten * self.max_abstand_s)
        )
        if not nah.any():
            return ziel

        # Ein Auto tauscht je Zeitschritt hoechstens einmal die Position,
        # sonst rechnet die Schleife mit veralteten Abstaenden weiter.
        getauscht: set[int] = set()
        for paar in np.flatnonzero(nah):
            i = int(hinten[paar])
            j = int(vorne[paar])
            if i in getauscht or j in getauscht:
                continue
            if not (self.aktiv[i] and self.aktiv[j]):
                continue
            vorteil = ziel[i] - ziel[j]
            if (
                vorteil >= self.min_vorteil
                and self.ist_zone[index[i]]
                and self._versucht_ueberholen(i, j, vorteil, zeit_ms)
            ):
                getauscht.update((i, j))
                # Vorbei heisst: einmal auf gleicher Hoehe gewesen. Damit
                # ist der Sog auf dieser Geraden aufgebraucht (Punkt 7).
                nummer = int(self.geradennummer[index[i]])
                if nummer >= 0:
                    kennung = int(self._gerade_id(i, nummer))
                    # Was der Sog gerade hergab, laeuft noch nach: beim
                    # Ueberholenden voll und dann zur Haelfte, beim
                    # Ueberholten erst gar nicht und danach mit der
                    # Haelfte davon. Beide haengen an derselben Marke,
                    # damit die zweite Stufe fuer beide zugleich beginnt.
                    marke = self.distanz[i] + self.sog_nachlauf_m
                    ueberschuss = float(self.sog_jetzt[i])
                    self.sog_verbraucht[i] = kennung
                    self.sog_nachlauf_wert[i] = ueberschuss
                    self.sog_nachlauf_bis[i] = marke
                    self.sog_nachlauf_erst[i] = 1.0
                    self.sog_nachlauf_dann[i] = self.sog_nachlauf_anteil
                    # Der Ueberholte faehrt auf dieser Geraden ebenfalls
                    # den Nachlauf - und damit keinen vollen Sog mehr.
                    self.sog_verbraucht[j] = int(self._gerade_id(j, nummer))
                    self.sog_nachlauf_wert[j] = ueberschuss
                    self.sog_nachlauf_bis[j] = marke
                    self.sog_nachlauf_erst[j] = 0.0
                    self.sog_nachlauf_dann[j] = (
                        self.sog_nachlauf_anteil * self.sog_nachlauf_ueberholter
                    )
                continue
            # Sonst bleibt das schnellere Auto dahinter und faehrt dessen
            # Tempo (GDD 4).
            if ziel[j] < ziel[i]:
                ziel[i] = ziel[j]
        return ziel

    def _sogpaare(self):
        """Wer faehrt auf der Runde direkt hinter wem (Punkt 68)?

        Anders als beim Verkehr wird hier die Position **auf der Strecke**
        genommen. Sonst sieht ein Auto seinen Vordermann nur, solange
        beide auf derselben Runde sind - ein Ueberrundeter liegt auf der
        Gesamtdistanz eine ganze Runde zurueck und waere nie in Reichweite,
        obwohl er direkt vor der Nase faehrt.

        :return: (hinten, vorne, Luecke in Metern) je Auto
        """
        auf_der_runde = np.mod(np.maximum(self.distanz, 0.0), self.laenge)
        ordnung = np.argsort(auf_der_runde)
        hinten = ordnung
        vorne = np.roll(ordnung, -1)
        lueck = np.mod(auf_der_runde[vorne] - auf_der_runde[hinten], self.laenge)
        return hinten, vorne, lueck

    def _gerade_id(self, autos, gerade):
        """Eindeutige Kennung einer Geraden in einer Runde.

        Die Geradennummer allein genuegt nicht: Dieselbe Gerade kommt in
        jeder Runde wieder, und der Sog steht je Gerade *und Runde* einmal
        zu. Eine Gerade, die ueber die Start/Ziel-Linie laeuft, zaehlt
        dabei als zwei - das betrifft je Strecke hoechstens eine.
        """
        return self.runden_gefahren[autos] * self.geraden_je_runde + gerade

    def _prueft_unfall(self, hinten: int, vorne: int, zeit_ms: int) -> bool:
        """Wuerfelt einen Unfall zwischen zwei nahen Autos (GDD 4).

        "Sehr selten und nur bei weniger als 30 m Abstand; mal scheidet ein
        Auto aus, mal beide; je Rennen wird eine Obergrenze von 0 bis 5
        Ausfaellen gewuerfelt."
        """
        if self.ohne_zufall or self.ausfaelle >= self.ausfallgrenze:
            return False
        if not (self.aktiv[hinten] and self.aktiv[vorne]):
            return False

        rate = kern_zwischenfall.unfallrate(self.k, self.dt_s, self.wetter_fehlerfaktor)
        if self.wuerfel.random() >= rate:
            return False

        beide = kern_zwischenfall.beide_betroffen(self.k, self.wuerfel)
        betroffen = [hinten, vorne] if beide else [hinten]
        runde = int(self.runden_gefahren[hinten]) + 1
        for i in betroffen:
            if self.ausfaelle >= self.ausfallgrenze:
                break
            self.aktiv[i] = False
            self.tempo[i] = 0.0
            self.ausfaelle += 1
            self.zwischenfaelle.append(
                kern_zwischenfall.Zwischenfall(
                    art=kern_zwischenfall.Art.UNFALL,
                    zeit_ms=zeit_ms,
                    teilnehmer=i,
                    runde=runde,
                    gegner=vorne if i == hinten else hinten,
                    ausgefallen=True,
                )
            )
        return True

    def _wuerfle_rundenereignisse(self, i: int, ueberfahrt: float) -> None:
        """Fehler und Defekte einer abgeschlossenen Runde (GDD 4 und 14)."""
        if self.ohne_zufall:
            return
        runde = int(self.runden_gefahren[i])
        auto = self.autos[i]

        # Fehler kosten einmalig Zeit; Wetter und abgefahrene Reifen
        # erhoehen die Wahrscheinlichkeit.
        rate = kern_zwischenfall.fehlerrate_je_runde(
            self.k, auto, self.wetter_fehlerfaktor, float(self.reifen_fehler[i])
        )
        if self.wuerfel.random() < rate:
            verlust = kern_zwischenfall.zeitverlust_ms(self.k, self.wuerfel)
            self.pause_ms[i] = verlust
            self.zwischenfaelle.append(
                kern_zwischenfall.Zwischenfall(
                    art=kern_zwischenfall.Art.FEHLER,
                    zeit_ms=int(round(ueberfahrt)),
                    teilnehmer=i,
                    runde=runde,
                    zeitverlust_ms=verlust,
                )
            )

        # Defekte senken Fahrzeugwerte bis zur Reparatur.
        if self.wuerfel.random() < kern_zwischenfall.defektrate_je_runde(
            self.k, auto, self.runden
        ):
            defekt = kern_zwischenfall.waehle_defekt(self.k, self.wuerfel)
            self.defekte_je_auto[i].append(defekt)
            self.defekt_tempo[i] = kern_zwischenfall.tempofaktor_defekte(
                self.k, self.defekte_je_auto[i]
            )
            self.zwischenfaelle.append(
                kern_zwischenfall.Zwischenfall(
                    art=kern_zwischenfall.Art.DEFEKT,
                    zeit_ms=int(round(ueberfahrt)),
                    teilnehmer=i,
                    runde=runde,
                    defekt=str(defekt["schluessel"]),
                )
            )

    def _zaehle_positionsgewinne(self, i: int) -> None:
        """Wen dieses Auto in der abgelaufenen Runde hinter sich gelassen hat.

        Verglichen wird der Stand zu Rundenbeginn mit dem am Rundenende.
        Ein Duell, das innerhalb einer Runde mehrfach hin und her geht,
        zaehlt damit einmal - oder gar nicht, wenn es am Ende steht wie am
        Anfang. Genau so zaehlt auch der Schnellmodus aus GDD 13, und nur
        so sind die Erfahrungswerte aus GDD 10 zwischen beiden Modellen
        vergleichbar.

        Zwei Gruppen zaehlen nicht mit, obwohl die Distanz es so aussehen
        laesst: **Ausgefallene** stehen am Streckenrand, und **Autos im
        Ziel** fahren nicht mehr weiter. An beiden ist niemand
        vorbeigefahren - sie bleiben nur zurueck, waehrend die anderen
        weiterfahren.
        """
        faehrt_noch = self.aktiv & ~self.im_ziel
        jetzt_vorne = self.distanz > self.distanz[i]
        ueberholt = self.vorne_bei_rundenbeginn[i] & ~jetzt_vorne & faehrt_noch
        self.positionsgewinne[i] += int(np.count_nonzero(ueberholt))
        self.vorne_bei_rundenbeginn[i] = jetzt_vorne

    def _setze_reifen(self, i: int) -> None:
        """Rechnet den Reifenzustand eines Autos in Tempo und Fehlerquote um.

        Im zufallsfreien Modus bleibt beides bei 1,0. Seit die Gripkurve
        ihr Optimum bei 80 % Restprofil hat (Punkt 39), heisst "kein
        Verschleiss" naemlich nicht mehr "voller Grip": Ein frischer
        Reifen steht bei 0,94, und die Kalibrierrunde aus GDD 9 waere
        damit 6 % zu langsam.
        """
        if self.ohne_zufall:
            return
        auto = self.autos[i]
        # Punkt 39: Die Mischung selbst traegt einen Tempofaktor - weich
        # ist schneller als hart, ein Regenreifen im Trockenen langsamer.
        # Er stand bisher nur in der Vorausberechnung der Strategie; im
        # Rennen fuhren alle fuenf Mischungen gleich schnell, und die
        # ganze Abwaegung "schneller, aber kuerzer" fand nicht statt.
        misch = kern_reifen.mischungsfaktor(self.k, self.mischungen[i], self.naesse_jetzt)
        self.reifen_tempo[i] = misch * kern_reifen.tempofaktor(
            self.k, auto, float(self.verschleiss[i])
        )
        self.reifen_fehler[i] = kern_reifen.fehlerfaktor(self.k, auto, float(self.verschleiss[i]))

    def _versucht_ueberholen(self, hinten: int, vorne: int, vorteil: float, zeit_ms: int) -> bool:
        chance = erfolgschance(
            self.k,
            self.teilnehmer[hinten].auto,
            self.teilnehmer[vorne].auto,
            vorteil * KMH_JE_MS,
            self.faktor,
        )
        if self.wuerfel.random() >= chance:
            return False

        # Kein Zusammenstoss, kein Rempeln: die Autos tauschen die
        # Reihenfolge, indem der Angreifer knapp vorbeizieht (GDD 4).
        self.distanz[hinten], self.distanz[vorne] = (
            self.distanz[vorne] + 0.01,
            self.distanz[hinten],
        )
        self.manoever.append(
            Ueberholmanoever(
                zeit_ms=zeit_ms,
                angreifer=hinten,
                verteidiger=vorne,
                runde=int(self.distanz[hinten] // self.laenge) + 1,
            )
        )
        return True

    def _pruefe_marken(self, vorher: np.ndarray, zeit_ms: int, dt: float) -> None:
        """Erfasst Sektor- und Linienueberfahrten auf die Millisekunde genau.

        Die Distanz zaehlt ab der Start/Ziel-Linie: Platz 1 steht darauf,
        die uebrigen dahinter. Eine Runde ist voll, sobald die Distanz ein
        Vielfaches der Rundenlaenge ueberschreitet - wer weiter hinten
        startet, faehrt dafuer entsprechend weiter.

        In den allermeisten Schritten faellt keine Marke; deshalb wird
        zuerst ueber alle Autos auf einmal geprueft und nur bei Treffern
        weitergerechnet.
        """
        naechste_marke = self.runden_gefahren * self.laenge + self.marken[self.naechster_sektor]
        treffer = (self.distanz >= naechste_marke) & (self.distanz > vorher) & ~self.im_ziel
        treffer &= self.aktiv
        if not treffer.any():
            return

        for i in np.flatnonzero(treffer):
            i = int(i)
            # In einem Schritt koennen mehrere Marken fallen.
            while not self.im_ziel[i]:
                marke = (
                    self.runden_gefahren[i] * self.laenge
                    + self.marken[self.naechster_sektor[i]]
                )
                if self.distanz[i] < marke:
                    break

                # GDD 4: "Linienueberfahrten interpoliert" - zwischen zwei
                # Schritten wird gleichmaessiges Tempo angenommen.
                anteil = (marke - vorher[i]) / (self.distanz[i] - vorher[i])
                ueberfahrt = zeit_ms + anteil * dt * 1000.0

                self.sektor_puffer[i].append(int(round(ueberfahrt - self.markenzeit[i])))
                self.markenzeit[i] = ueberfahrt

                if self.naechster_sektor[i] == len(self.marken) - 1:
                    self._runde_fertig(i, ueberfahrt)
                else:
                    self.naechster_sektor[i] += 1

    def _runde_fertig(self, i: int, ueberfahrt: float) -> None:
        """Haelt Runden- und Sektorzeiten fest und prueft das Rennende."""
        protokoll = self.protokolle[i]
        protokoll.rundenzeiten_ms.append(int(round(ueberfahrt - self.linienzeit[i])))
        protokoll.sektorzeiten_ms.append(tuple(self.sektor_puffer[i]))
        protokoll.rundenende_ms.append(int(round(ueberfahrt)))

        self.sektor_puffer[i] = []
        self.linienzeit[i] = ueberfahrt
        self.runden_gefahren[i] += 1
        self.naechster_sektor[i] = 0
        self._zaehle_positionsgewinne(i)

        # Jede Runde wird die Rundenform neu gezogen (GDD 11); das Wetter
        # kann sich inzwischen geaendert haben (GDD 7).
        if not self.ohne_zufall:
            self.tempoform[i] = 1.0 / kern_form.rundenform(
                self.k, self.autos[i], self.seedquelle.zweig("rundenform", i),
                int(self.runden_gefahren[i]),
            )
        self._setze_grip(ueberfahrt)
        # Reifenzustand und Zwischenfaelle werden je Runde nachgezogen.
        self._setze_reifen(i)
        # Punkt 39: Der Wechsel liegt auf der Ziellinie - dort steht die
        # Box. Er kommt vor den Rundenereignissen, damit die Fehlerquote
        # der neuen Runde schon zu den frischen Reifen passt.
        self._pruefe_boxenstopp(i, ueberfahrt)
        self._wuerfle_rundenereignisse(i, ueberfahrt)

        if self.runden_gefahren[i] >= self.runden and self.sieger_zeit is None:
            self.sieger_zeit = ueberfahrt

        # GDD 4: Sobald der Sieger im Ziel ist, beendet jedes andere Auto
        # das Rennen bei seiner naechsten Ueberfahrt der Ziellinie.
        if self.runden_gefahren[i] >= self.runden or self.sieger_zeit is not None:
            self.im_ziel[i] = True
            self.zielzeit[i] = int(round(ueberfahrt))

    @property
    def alle_fertig(self) -> bool:
        return bool((self.im_ziel | ~self.aktiv).all())


def _ergebnisse(
    lauf: _Lauf, konfiguration: Konfiguration, seedquelle: Seedquelle
) -> tuple[Ergebnis, ...]:
    """Bildet die Schlusswertung.

    GDD 4: Bei Gleichstand auf die Millisekunde liegt vorne, wer den
    hoeheren Durchschnitt der Basiseigenschaften hat; sonst entscheidet
    das Los.
    """
    los = seedquelle.zweig("gleichstand").generator()
    zufallsmarke = {i: float(los.random()) for i in range(lauf.anzahl)}

    def schluessel(i: int) -> tuple:
        runden = lauf.runden_gefahren[i]
        zeit = lauf.zielzeit[i]
        return (
            0 if zeit is not None else 1,       # Zielankunft vor Ausfall
            -runden,                            # mehr Runden ist besser
            zeit if zeit is not None else 0,    # frueher im Ziel ist besser
            -gesamtwert(konfiguration, lauf.teilnehmer[i].auto),
            zufallsmarke[i],
        )

    reihenfolge = sorted(range(lauf.anzahl), key=schluessel)
    sieger = reihenfolge[0]
    siegerzeit = lauf.zielzeit[sieger]
    siegerrunden = lauf.runden_gefahren[sieger]

    ergebnisse = []
    for platz, i in enumerate(reihenfolge, start=1):
        zeit = lauf.zielzeit[i]
        runden = lauf.runden_gefahren[i]
        rueckstand = None
        if zeit is not None and siegerzeit is not None and runden == siegerrunden:
            rueckstand = zeit - siegerzeit
        ergebnisse.append(
            Ergebnis(
                teilnehmer=i,
                platz=platz,
                runden=runden,
                zeit_ms=zeit,
                rueckstand_ms=rueckstand,
                rundenrueckstand=siegerrunden - runden,
            )
        )
    return tuple(ergebnisse)


def mittlerer_ueberholzonenanteil(konfiguration: Konfiguration, strecken) -> float:
    """Mittelwert ueber alle Strecken, Bezugsgroesse des Streckenfaktors."""
    anteile = [strecke.ueberholzonenanteil for strecke in strecken]
    return sum(anteile) / len(anteile)


def simuliere(
    konfiguration: Konfiguration,
    strecke: Strecke,
    teilnehmer: tuple[Teilnehmer, ...],
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    wetter: kern_wetter.Wetterverlauf | None = None,
    ohne_zufall: bool = False,
    streckenverschleiss: float = 1.0,
    kenntnisfaktor: tuple[float, ...] | None = None,
    tagesformbonus: tuple[float, ...] | None = None,
    rhythmusfaktor: tuple[float, ...] | None = None,
    hoechstdauer_ms: int | None = None,
    strategien: tuple[kern_strategie.Strategie, ...] | None = None,
    mischungspflicht: bool = False,
    liga: int | None = None,
) -> Rennverlauf:
    """Faehrt ein ganzes Rennen und liefert den fertigen Verlauf.

    :param streckenmittel: mittlerer Ueberholzonenanteil aller Strecken,
        Bezugsgroesse fuer den Streckenfaktor beim Ueberholen
    :param wetter: Wetterverlauf der Session (GDD 7); ohne Angabe wird
        trocken mit Grip 1,0 gefahren
    :param streckenverschleiss: Reifenfaktor der Strecke (GDD 3), aus
        rennmanager.kern.reifen.streckenfaktor
    :param kenntnisfaktor: Tempofaktor aus der Streckenkenntnis je Auto
        (GDD 6), aus rennmanager.kern.streckenkenntnis. Ohne Angabe faehrt
        jedes Auto ohne Kenntnisbonus.
    :param tagesformbonus: Zuschlag auf den Tagesform-Mittelwert je Auto
        (E3 Motivationsschub aus GDD 14). Ohne Angabe faehrt jedes Auto
        ohne Zuschlag.
    :param rhythmusfaktor: Faktor auf die Querbeschleunigung in Kurven je
        Auto (Punkt 15), aus rennmanager.kern.rhythmus. Ohne Angabe faehrt
        jedes Auto ohne Rhythmusvorteil.
    :param ohne_zufall: laesst Tagesform, Eigenschafts-Zufall, Rundenform,
        Fehler, Unfaelle, Defekte, Reifenverschleiss und Streckenkenntnis
        weg - also
        alles, was eine Rennrunde von der kalibrierten Einzelrunde
        abweichen laesst. GDD 9 kalibriert ausdruecklich ohne Zufall, und
        fuer die Massensimulation aus GDD 15 ist es ebenfalls noetig.
    :param hoechstdauer_ms: Notbremse gegen ein Rennen, das nie endet
    :param strategien: Mischungsfolge und Stopprunden je Auto (Punkt 39),
        aus rennmanager.kern.strategie. Ohne Angabe faehrt jedes Auto das
        ganze Rennen auf einem Satz - das brauchen die Kalibrierung und
        die aelteren Tests.
    :param mischungspflicht: ob in diesem Rennen zwei Mischungen Pflicht
        sind. Nur fuer die Anzeige; gefahren wird, was in ``strategien``
        steht.
    :param liga: bestimmt das Boxenlimit (Punkt 39). Liga 1 bis 5 faehrt
        80 km/h, die unteren Ligen weniger. Ohne Angabe gilt der
        Grundwert.
    """
    if not teilnehmer:
        raise ValueError("Ohne Teilnehmer gibt es kein Rennen")
    if runden < 1:
        raise ValueError("Ein Rennen geht ueber mindestens eine Runde")

    lauf = _Lauf(
        konfiguration, strecke, teilnehmer, runden, seedquelle, streckenmittel,
        wetter, ohne_zufall, streckenverschleiss, kenntnisfaktor, tagesformbonus,
        rhythmusfaktor, strategien=strategien, mischungspflicht=mischungspflicht,
        liga=liga,
    )
    # Punkt 39: Die Mischung wird als Index gefuehrt, nicht als Kuerzel -
    # ein Bild je 200 Millisekunden mal 30 Autos waere sonst eine
    # Zeichenkettenwolke.
    kuerzel = tuple(m.kuerzel for m in kern_reifen.mischungen(konfiguration))
    stelle_von = {k: n for n, k in enumerate(kuerzel)}

    def mischungszeile() -> np.ndarray:
        return np.array([stelle_von[m.kuerzel] for m in lauf.mischungen], dtype=np.int8)
    schritt_ms = konfiguration.wert("simulation", "zeitschritt_ms")
    bild_ms = konfiguration.wert("simulation", "bildschritt_ms")
    dt = schritt_ms / 1000.0
    je_bild = max(1, round(bild_ms / schritt_ms))

    if hoechstdauer_ms is None:
        # Grosszuegig: selbst das langsamste Auto braucht keine zehn Stunden.
        hoechstdauer_ms = 10 * 60 * 60 * 1000

    zeitpunkte = [0]
    distanzen = [lauf.distanz.copy()]
    ausgefallen = [~lauf.aktiv.copy()]
    reifen = [np.ones(lauf.anzahl)]
    mischungsbilder = [mischungszeile()]

    zeit_ms = 0
    nummer = 0
    while not lauf.alle_fertig and zeit_ms < hoechstdauer_ms:
        lauf.schritt(zeit_ms, dt)
        zeit_ms += schritt_ms
        nummer += 1
        if nummer % je_bild == 0:
            zeitpunkte.append(zeit_ms)
            distanzen.append(lauf.distanz.copy())
            ausgefallen.append(~lauf.aktiv.copy())
            reifen.append(np.clip(1.0 - lauf.verschleiss, 0.0, 1.0))
            mischungsbilder.append(mischungszeile())

    # Das letzte Bild immer festhalten, damit der Zielstand sichtbar ist.
    if zeitpunkte[-1] != zeit_ms:
        zeitpunkte.append(zeit_ms)
        distanzen.append(lauf.distanz.copy())
        ausgefallen.append(~lauf.aktiv.copy())
        reifen.append(np.clip(1.0 - lauf.verschleiss, 0.0, 1.0))
        mischungsbilder.append(mischungszeile())

    return Rennverlauf(
        strecke=strecke,
        teilnehmer=teilnehmer,
        runden=runden,
        wetter=wetter,
        tagesform=lauf.tagesform,
        zeitpunkte_ms=np.array(zeitpunkte),
        distanz_m=np.array(distanzen),
        ausgefallen=np.array(ausgefallen),
        protokolle=lauf.protokolle,
        manoever=tuple(lauf.manoever),
        positionsgewinne=tuple(int(n) for n in lauf.positionsgewinne),
        zwischenfaelle=tuple(lauf.zwischenfaelle),
        reifenzustand=np.array(reifen),
        ergebnisse=_ergebnisse(lauf, konfiguration, seedquelle),
        dauer_ms=zeit_ms,
        mischungsindex=np.array(mischungsbilder),
        mischungen=kuerzel,
        boxenstopps=tuple(lauf.boxenstopps),
        mischungspflicht=mischungspflicht,
    )


# ---------------------------------------------------------------------------
# Startfeld
# ---------------------------------------------------------------------------
def starterfeld(
    konfiguration: Konfiguration,
    liga: int,
    spielerplatz: int | None = None,
    umgedreht: bool = False,
    seedquelle: Seedquelle | None = None,
) -> tuple[Teilnehmer, ...]:
    """Baut ein Feld aus 30 Autos fuer eine Liga.

    Die Staerken sind gleichmaessig zwischen dem Letzten und dem Besten der
    Liga verteilt, wie es die Kalibriertabelle in GDD 9 vorgibt. Mit einer
    Seedquelle streuen die Einzelwerte zusaetzlich um ihren Mittelwert
    (GDD 12: "Einzelwerte streuen +/- 25 % um den Mittelwert, z. B.
    Regenspezialist, Qualifying-Experte, Reifenschoner"). Erst dadurch
    unterscheiden sich die Autos im Profil und nicht nur in der Staerke -
    ohne das faehrt jedes seine Reifen gleich schnell ab.

    Fahrer, Teams und die vollstaendige KI-Erzeugung kommen in Schritt 7;
    bis dahin dienen die Herstellerfarben als Platzhalter.

    :param spielerplatz: Startplatz des Spielers, ``None`` fuer ein reines
        KI-Feld
    :param umgedreht: Das staerkste Auto startet hinten - nuetzlich, um das
        Ueberholen zu pruefen
    :param seedquelle: ohne Angabe hat jedes Auto ueberall denselben Wert
    """
    kontrolle = {zeile["liga"]: zeile for zeile in konfiguration.wert("ligen", "kontrolle")}
    if liga not in kontrolle:
        bekannt = ", ".join(str(nummer) for nummer in sorted(kontrolle))
        raise ValueError(
            f"Fuer Liga {liga} liegt kein Kontrollwert vor; vorhanden sind {bekannt}"
        )

    zeile = kontrolle[liga]
    schwaechster = zeile["s_letzter"]
    staerkster = zeile["s_bester"]
    anzahl = konfiguration.wert("rennen", "autos")
    hersteller = konfiguration.hersteller
    streuung = konfiguration.wert("ki", "profil_streuung")
    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")

    # Die zusaetzlichen Fahrereigenschaften ausserhalb der Wirkungsmatrix:
    # die fuenf Wetterfaehigkeiten (GDD 7) und der Reifenfluesterer.
    zusatz = list(konfiguration.zusatzfaehigkeiten)

    teilnehmer = []
    for nummer in range(1, anzahl + 1):
        anteil = (anzahl - nummer) / (anzahl - 1)
        s = round(schwaechster + (staerkster - schwaechster) * anteil)
        startplatz = anzahl + 1 - nummer if umgedreht else nummer

        if seedquelle is None:
            wert_von = dict.fromkeys(
                [f.schluessel for f in konfiguration.faehigkeiten] + zusatz, s
            )
        else:
            wuerfel = seedquelle.zweig("profil", nummer).generator()

            def gestreut(mittelwert: int = s, wuerfel=wuerfel) -> int:
                faktor = 1.0 + float(wuerfel.uniform(-streuung, streuung))
                return int(round(min(max(mittelwert * faktor, kleinster), groesster)))

            wert_von = {f.schluessel: gestreut() for f in konfiguration.faehigkeiten}
            wert_von.update({schluessel: gestreut() for schluessel in zusatz})

        teilnehmer.append(
            Teilnehmer(
                auto=Auto(
                    kuerzel=f"A{nummer:02d}",
                    name=f"Auto {nummer}",
                    werte={
                        f.schluessel: wert_von[f.schluessel]
                        for f in konfiguration.faehigkeiten
                    },
                    wetterwerte={schluessel: wert_von[schluessel] for schluessel in zusatz},
                ),
                startplatz=startplatz,
                farbe=hersteller[(nummer - 1) % len(hersteller)].farbe,
                ist_spieler=startplatz == spielerplatz,
            )
        )
    return tuple(teilnehmer)
