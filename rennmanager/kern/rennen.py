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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import form as kern_form
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.auto import Auto, bereichswert, gesamtwert
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.tempo import KMH_JE_MS, geschwindigkeitsprofil, grenzen_aus, leistungsanteil
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


@dataclass(frozen=True)
class Teilnehmer:
    """Ein Auto am Start, mit Anzeigedaten und Startplatz."""

    auto: Auto
    startplatz: int
    farbe: str
    ist_spieler: bool = False

    @property
    def kuerzel(self) -> str:
        return self.auto.kuerzel


@dataclass
class Rundenprotokoll:
    """Zeiten eines Autos, fortlaufend gefuellt (GDD 4: Zeitenmonitor)."""

    rundenzeiten_ms: list[int] = field(default_factory=list)
    sektorzeiten_ms: list[tuple[int, ...]] = field(default_factory=list)

    @property
    def beste_runde_ms(self) -> int | None:
        return min(self.rundenzeiten_ms) if self.rundenzeiten_ms else None

    @property
    def letzte_runde_ms(self) -> int | None:
        return self.rundenzeiten_ms[-1] if self.rundenzeiten_ms else None


@dataclass(frozen=True)
class Ueberholmanoever:
    """Ein gelungenes Ueberholmanoever, fuer Statistik und Erfahrung."""

    zeit_ms: int
    angreifer: int
    verteidiger: int
    runde: int


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
    ergebnisse: tuple[Ergebnis, ...]
    dauer_ms: int

    @property
    def anzahl(self) -> int:
        return len(self.teilnehmer)

    def bild_zu(self, zeit_ms: float) -> int:
        """Index des letzten Bildes, das nicht nach ``zeit_ms`` liegt."""
        return int(np.clip(np.searchsorted(self.zeitpunkte_ms, zeit_ms, "right") - 1,
                           0, len(self.zeitpunkte_ms) - 1))

    def distanzen_zu(self, zeit_ms: float) -> np.ndarray:
        """Zurueckgelegte Strecke je Auto, zwischen den Bildern interpoliert."""
        bild = self.bild_zu(zeit_ms)
        if bild >= len(self.zeitpunkte_ms) - 1:
            return self.distanz_m[-1]
        davor = float(self.zeitpunkte_ms[bild])
        danach = float(self.zeitpunkte_ms[bild + 1])
        anteil = (zeit_ms - davor) / max(danach - davor, 1e-9)
        return self.distanz_m[bild] + anteil * (self.distanz_m[bild + 1] - self.distanz_m[bild])

    def reihenfolge_zu(self, zeit_ms: float) -> list[int]:
        """Positionen zum Zeitpunkt: wer am weitesten ist, fuehrt (GDD 4)."""
        distanzen = self.distanzen_zu(zeit_ms)
        return sorted(range(self.anzahl), key=lambda i: -distanzen[i])


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
    """
    einstellung = konfiguration.wert("ueberholen", "erfolg")
    skala = konfiguration.wert("skala", "maximum")
    mindestvorteil = konfiguration.wert("ueberholen", "min_tempovorteil_kmh")

    koennen = angreifer.wert("D10") - verteidiger.wert("D11")
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
    ) -> None:
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
        if ohne_zufall:
            self.autos = [t.auto for t in teilnehmer]
            self.tagesform = (1.0,) * self.anzahl
        else:
            formen = [
                kern_form.wuerfle(konfiguration, t.auto, seedquelle.zweig("form", nummer))
                for nummer, t in enumerate(teilnehmer)
            ]
            self.autos = [form.auto for form in formen]
            self.tagesform = tuple(form.tagesform for form in formen)

        grenzen = [grenzen_aus(konfiguration, auto) for auto in self.autos]
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
        self.min_vorteil = konfiguration.wert("ueberholen", "min_tempovorteil_kmh") / KMH_JE_MS
        self.sieger_zeit: float | None = None
        self.laufende_nummer = np.arange(self.anzahl)
        self.index = np.zeros(self.anzahl, dtype=int)
        self._setze_rundenform(0)
        self._setze_grip(0.0)

    def _setze_grip(self, zeit_ms: float) -> None:
        """Grip je Auto zum Zeitpunkt, mit Wetterkoennen (GDD 7).

        Der Grip wirkt als Faktor auf das Tempo; die Beschleunigungsgrenze
        skaliert deshalb quadratisch mit - genau wie im Profil.
        """
        if self.wetter is None:
            return
        zustand = self.wetter.zustand_zu(zeit_ms)
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
        self._pruefe_marken(vorher, zeit_ms, dt)

    def _ziel_tempo(self, zeit_ms: int) -> np.ndarray:
        """Tempo, das ein Auto anstrebt: freies Profil, gedeckelt durch
        Folgen und Ueberholen (GDD 4).

        Die teuren Teile sind ueber alle Autos auf einmal gerechnet; die
        Schleife laeuft nur ueber die wenigen Paare, die sich tatsaechlich
        nahe genug sind.
        """
        # Vor Ablauf der Reaktionszeit steht das Auto (GDD 4).
        faehrt = self.aktiv & ~self.im_ziel

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
        # Wetter (Grip) und Rundenform wirken beide als Faktor aufs Tempo.
        frei = (hier + rest * (dort - hier)) * self.grip * self.tempoform
        ziel = np.where(faehrt, frei, 0.0)

        # Reihenfolge nach zurueckgelegter Strecke; danach steht fest, wer
        # vor wem faehrt.
        reihenfolge = np.argsort(-self.distanz)
        vorne = reihenfolge[:-1]
        hinten = reihenfolge[1:]

        abstand_m = self.distanz[vorne] - self.distanz[hinten]
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
            vorteil = ziel[i] - ziel[j]
            if (
                vorteil >= self.min_vorteil
                and self.ist_zone[index[i]]
                and self._versucht_ueberholen(i, j, vorteil, zeit_ms)
            ):
                getauscht.update((i, j))
                continue
            # Sonst bleibt das schnellere Auto dahinter und faehrt dessen
            # Tempo (GDD 4).
            if ziel[j] < ziel[i]:
                ziel[i] = ziel[j]
        return ziel

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

        self.sektor_puffer[i] = []
        self.linienzeit[i] = ueberfahrt
        self.runden_gefahren[i] += 1
        self.naechster_sektor[i] = 0

        # Jede Runde wird die Rundenform neu gezogen (GDD 11); das Wetter
        # kann sich inzwischen geaendert haben (GDD 7).
        if not self.ohne_zufall:
            self.tempoform[i] = 1.0 / kern_form.rundenform(
                self.k, self.autos[i], self.seedquelle.zweig("rundenform", i),
                int(self.runden_gefahren[i]),
            )
        self._setze_grip(ueberfahrt)

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
    hoechstdauer_ms: int | None = None,
) -> Rennverlauf:
    """Faehrt ein ganzes Rennen und liefert den fertigen Verlauf.

    :param streckenmittel: mittlerer Ueberholzonenanteil aller Strecken,
        Bezugsgroesse fuer den Streckenfaktor beim Ueberholen
    :param wetter: Wetterverlauf der Session (GDD 7); ohne Angabe wird
        trocken mit Grip 1,0 gefahren
    :param ohne_zufall: laesst Tagesform, Eigenschafts-Zufall und
        Rundenform weg. GDD 9 kalibriert ausdruecklich ohne Zufall, und
        fuer die Massensimulation aus GDD 15 ist es ebenfalls noetig.
    :param hoechstdauer_ms: Notbremse gegen ein Rennen, das nie endet
    """
    if not teilnehmer:
        raise ValueError("Ohne Teilnehmer gibt es kein Rennen")
    if runden < 1:
        raise ValueError("Ein Rennen geht ueber mindestens eine Runde")

    lauf = _Lauf(
        konfiguration, strecke, teilnehmer, runden, seedquelle, streckenmittel,
        wetter, ohne_zufall,
    )
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

    # Das letzte Bild immer festhalten, damit der Zielstand sichtbar ist.
    if zeitpunkte[-1] != zeit_ms:
        zeitpunkte.append(zeit_ms)
        distanzen.append(lauf.distanz.copy())
        ausgefallen.append(~lauf.aktiv.copy())

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
        ergebnisse=_ergebnisse(lauf, konfiguration, seedquelle),
        dauer_ms=zeit_ms,
    )


# ---------------------------------------------------------------------------
# Startfeld
# ---------------------------------------------------------------------------
def starterfeld(
    konfiguration: Konfiguration,
    liga: int,
    spielerplatz: int | None = None,
    umgedreht: bool = False,
) -> tuple[Teilnehmer, ...]:
    """Baut ein Feld aus 30 Autos fuer eine Liga.

    Vorlaeufig: Die Staerken sind gleichmaessig zwischen dem Letzten und
    dem Besten der Liga verteilt, wie es die Kalibriertabelle in GDD 9
    vorgibt, und jedes Auto hat ueberall denselben Wert. Die richtige
    KI-Erzeugung mit Profilstreuung, Fahrern und Teams kommt in Schritt 7;
    bis dahin dienen die Herstellerfarben als Platzhalter.

    :param spielerplatz: Startplatz des Spielers, ``None`` fuer ein reines
        KI-Feld
    :param umgedreht: Das staerkste Auto startet hinten - nuetzlich, um das
        Ueberholen zu pruefen
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

    teilnehmer = []
    for nummer in range(1, anzahl + 1):
        anteil = (anzahl - nummer) / (anzahl - 1)
        s = round(schwaechster + (staerkster - schwaechster) * anteil)
        startplatz = anzahl + 1 - nummer if umgedreht else nummer
        teilnehmer.append(
            Teilnehmer(
                auto=Auto(
                    kuerzel=f"A{nummer:02d}",
                    name=f"Auto {nummer}",
                    werte={f.schluessel: s for f in konfiguration.faehigkeiten},
                ),
                startplatz=startplatz,
                farbe=hersteller[(nummer - 1) % len(hersteller)].farbe,
                ist_spieler=startplatz == spielerplatz,
            )
        )
    return tuple(teilnehmer)
