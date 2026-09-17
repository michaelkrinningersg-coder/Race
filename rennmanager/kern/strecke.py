"""Streckenmodell: Einlesen, Abtasten, Segmenttypen, Sektoren.

Grundlage ist GDD 3. Die Rohdaten stammen aus der TUMFTM racetrack-database
(LGPL-3.0) und liegen unveraendert unter ``daten/strecken/``; Herkunft und
Format beschreibt ``daten/strecken/HERKUNFT.md``.

Ablauf:

1. Ideallinie einlesen (geschlossene Runde, Koordinaten in Metern)
2. auf gleichmaessigen Punktabstand von rund 5 m neu abtasten
3. Kruemmungsradius je Punkt bestimmen
4. daraus den Segmenttyp ableiten: enge Kurve, Kurve, Gerade
5. zusammenhaengende Punkte gleichen Typs zu Segmenten verschmelzen
6. Geraden ab 100 m als Ueberholzonen markieren
7. die Runde in 4 Sektoren gleicher Laenge teilen

Alle Grenzwerte stehen in ``konfiguration/balancing.toml``, keiner im Code.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property
from pathlib import Path

import numpy as np


class Segmentart(IntEnum):
    """Segmenttypen laut GDD 3, geordnet nach steigendem Radius."""

    ENGE_KURVE = 0
    KURVE = 1
    GERADE = 2

    @property
    def bezeichnung(self) -> str:
        return {
            Segmentart.ENGE_KURVE: "Enge Kurve",
            Segmentart.KURVE: "Kurve",
            Segmentart.GERADE: "Gerade",
        }[self]


class StreckenFehler(Exception):
    """Eine Streckendatei fehlt oder laesst sich nicht auswerten."""


@dataclass(frozen=True)
class Segment:
    """Ein Streckenabschnitt eines Typs.

    ``von`` und ``bis`` sind Punktindizes; ``bis`` ist ausgeschlossen. Ein
    Segment kann ueber die Start/Ziel-Linie hinweg laufen, dann ist
    ``bis <= von`` und der Abschnitt setzt sich am Rundenanfang fort.
    """

    art: Segmentart
    von: int
    bis: int
    punkte: int
    laenge_m: float
    radius_min_m: float
    radius_mittel_m: float
    ist_ueberholzone: bool

    @property
    def laeuft_ueber_start(self) -> bool:
        return self.bis <= self.von


@dataclass(frozen=True)
class Sektor:
    """Einer der 4 Sektoren gleicher Laenge (GDD 3)."""

    nummer: int
    von: int
    bis: int
    laenge_m: float


@dataclass(frozen=True)
class Strecke:
    """Eine ausgewertete Strecke.

    :param punkte: Ideallinie, Form ``(N, 2)``, gleichmaessig abgetastet
    :param radius_m: Kruemmungsradius je Punkt; auf Geraden sehr gross
    :param art_je_punkt: Segmentart je Punkt als ``Segmentart``-Wert
    """

    name: str
    land: str
    charakter: str
    datei: str
    punkte: np.ndarray
    radius_m: np.ndarray
    art_je_punkt: np.ndarray
    segmente: tuple[Segment, ...]
    sektoren: tuple[Sektor, ...]
    punktabstand_m: float

    # -- Kennwerte ---------------------------------------------------------
    @property
    def laenge_m(self) -> float:
        """Rundenlaenge in Metern."""
        return len(self.punkte) * self.punktabstand_m

    @property
    def ueberholzonen(self) -> tuple[Segment, ...]:
        """Alle Geraden, die lang genug zum Ueberholen sind (GDD 3)."""
        return tuple(segment for segment in self.segmente if segment.ist_ueberholzone)

    def anteil(self, art: Segmentart) -> float:
        """Laengenanteil eines Segmenttyps an der Runde, 0 bis 1."""
        return float(np.count_nonzero(self.art_je_punkt == art) / len(self.art_je_punkt))

    @property
    def geradenanteil(self) -> float:
        """Anteil der Geraden an der Rundenlaenge.

        GDD 3 leitet die Ueberholschwierigkeit hieraus ab, nennt aber keine
        Formel. Deshalb steht hier nur der gemessene Anteil; die Umrechnung
        in eine Schwierigkeit bleibt offen (siehe ``[offen]`` in der
        Konfiguration).
        """
        return self.anteil(Segmentart.GERADE)

    @property
    def ueberholzonenanteil(self) -> float:
        """Anteil der Geraden ab 100 m an der Rundenlaenge."""
        return sum(zone.laenge_m for zone in self.ueberholzonen) / self.laenge_m

    @cached_property
    def kurvenfolgenanteil(self) -> float:
        """Anteil der Runde, der in Kurvenfolgen liegt (Punkt 15).

        Eine Kurvenfolge sind mindestens zwei Kurven hintereinander, ohne
        Gerade dazwischen - das, was die Eigenschaft ``rhythmus`` belohnt.
        Eine einzelne Kurve zwischen zwei Geraden zaehlt nicht mit.

        Gezaehlt wird auf der offenen Runde: Eine Folge, die ueber die
        Start/Ziel-Linie laeuft, faellt damit in zwei Teile. Das ist bei
        den 20 Strecken hoechstens eine und aendert den Anteil kaum.
        """
        laenge = 0.0
        lauf: list[Segment] = []
        for segment in self.segmente:
            if segment.art is Segmentart.GERADE:
                if len(lauf) >= 2:
                    laenge += sum(teil.laenge_m for teil in lauf)
                lauf = []
            else:
                lauf.append(segment)
        if len(lauf) >= 2:
            laenge += sum(teil.laenge_m for teil in lauf)
        return laenge / self.laenge_m

    @cached_property
    def kurzsegmente(self) -> tuple[Segment, ...]:
        """Segmente unter 25 m, als Hinweis auf die Datenqualitaet."""
        return tuple(segment for segment in self.segmente if segment.laenge_m < 25.0)

    def sektor_von_punkt(self, index: int) -> int:
        """Nummer des Sektors (1 bis 4), in dem ein Punkt liegt."""
        for sektor in self.sektoren:
            if sektor.von <= index < sektor.bis:
                return sektor.nummer
        raise IndexError(f"Punkt {index} liegt in keinem Sektor")


# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------
def _lies_csv(pfad: Path, spalten: int) -> np.ndarray:
    if not pfad.is_file():
        raise StreckenFehler(f"Streckendatei fehlt: {pfad}")
    try:
        werte = np.loadtxt(pfad, delimiter=",", skiprows=1, ndmin=2)
    except ValueError as fehler:
        raise StreckenFehler(f"{pfad} laesst sich nicht lesen: {fehler}") from fehler
    if werte.ndim != 2 or werte.shape[1] < spalten:
        gefunden = werte.shape[1] if werte.ndim == 2 else 0
        raise StreckenFehler(f"{pfad}: {spalten} Spalten erwartet, {gefunden} gefunden")
    if len(werte) < 4:
        raise StreckenFehler(f"{pfad}: zu wenige Punkte ({len(werte)})")
    return werte


def taste_ab(linie: np.ndarray, wunschabstand_m: float) -> tuple[np.ndarray, float]:
    """Tastet eine geschlossene Linie gleichmaessig neu ab.

    Eine geschlossene Runde laesst sich nur dann in exakt ``wunschabstand_m``
    teilen, wenn ihre Laenge ein Vielfaches davon ist. Deshalb wird die Zahl
    der Punkte gerundet und der tatsaechliche Abstand als zweiter Rueckgabewert
    gemeldet; er weicht um weniger als einen halben Punktabstand ab.

    :return: Punkte der Form ``(N, 2)`` und der tatsaechliche Punktabstand
    """
    if wunschabstand_m <= 0:
        raise ValueError("Der Punktabstand muss groesser als 0 sein")

    # Die Runde schliessen, damit auch das Stueck vom letzten zum ersten
    # Punkt abgetastet wird.
    geschlossen = np.vstack([linie, linie[:1]])
    strecken = np.linalg.norm(np.diff(geschlossen, axis=0), axis=1)
    bogenlaenge = np.concatenate([[0.0], np.cumsum(strecken)])
    gesamt = float(bogenlaenge[-1])

    anzahl = int(round(gesamt / wunschabstand_m))
    if anzahl < 4:
        raise ValueError(
            f"Die Linie ist mit {gesamt:.1f} m zu kurz fuer einen Abstand "
            f"von {wunschabstand_m} m"
        )

    abstand = gesamt / anzahl
    ziele = np.arange(anzahl) * abstand
    punkte = np.column_stack(
        [
            np.interp(ziele, bogenlaenge, geschlossen[:, 0]),
            np.interp(ziele, bogenlaenge, geschlossen[:, 1]),
        ]
    )
    return punkte, abstand


def kruemmungsradius(punkte: np.ndarray) -> np.ndarray:
    """Berechnet den Kruemmungsradius je Punkt einer geschlossenen Linie.

    Erste und zweite Ableitung ueber zentrale Differenzen; weil die Punkte
    gleichmaessig verteilt sind, ist das stabil. Auf einer Geraden wird die
    Kruemmung 0 und der Radius unendlich.

    :return: Radien in Metern, immer positiv; ``inf`` auf exakten Geraden
    """
    x, y = punkte[:, 0], punkte[:, 1]
    dx = (np.roll(x, -1) - np.roll(x, 1)) / 2.0
    dy = (np.roll(y, -1) - np.roll(y, 1)) / 2.0
    ddx = np.roll(x, -1) - 2.0 * x + np.roll(x, 1)
    ddy = np.roll(y, -1) - 2.0 * y + np.roll(y, 1)

    zaehler = np.abs(dx * ddy - dy * ddx)
    nenner = np.power(dx * dx + dy * dy, 1.5)

    with np.errstate(divide="ignore", invalid="ignore"):
        radius = np.where(zaehler > 0.0, nenner / zaehler, np.inf)
    return radius


def bestimme_art(
    radius_m: np.ndarray, enge_kurve_max_m: float, gerade_min_m: float
) -> np.ndarray:
    """Ordnet jedem Punkt seinen Segmenttyp zu (GDD 3).

    Enge Kurve bei ``r < enge_kurve_max_m``, Gerade ab ``gerade_min_m``,
    dazwischen Kurve.
    """
    art = np.full(len(radius_m), Segmentart.KURVE, dtype=np.int8)
    art[radius_m < enge_kurve_max_m] = Segmentart.ENGE_KURVE
    art[radius_m >= gerade_min_m] = Segmentart.GERADE
    return art


def _laeufe(art_je_punkt: np.ndarray) -> list[tuple[int, int]]:
    """Zerlegt die Runde in zusammenhaengende Abschnitte gleichen Typs.

    Liefert Paare ``(startindex, punktzahl)``. Laufen Anfang und Ende der
    Runde im selben Typ, werden sie zu einem Abschnitt ueber die
    Start/Ziel-Linie hinweg verbunden.
    """
    anzahl = len(art_je_punkt)
    grenzen = np.flatnonzero(art_je_punkt != np.roll(art_je_punkt, 1))

    if len(grenzen) == 0:
        # Die ganze Runde hat denselben Typ.
        return [(0, anzahl)]

    laeufe: list[tuple[int, int]] = []
    for lauf_nr, start in enumerate(grenzen):
        ende = grenzen[(lauf_nr + 1) % len(grenzen)]
        laenge = (ende - start) % anzahl or anzahl
        laeufe.append((int(start), int(laenge)))
    return laeufe


def _baue_segmente(
    art_je_punkt: np.ndarray,
    radius_m: np.ndarray,
    punktabstand_m: float,
    ueberholzone_min_m: float,
) -> tuple[Segment, ...]:
    anzahl = len(art_je_punkt)
    segmente: list[Segment] = []

    for start, laenge in _laeufe(art_je_punkt):
        indizes = (start + np.arange(laenge)) % anzahl
        radien = radius_m[indizes]
        endlich = radien[np.isfinite(radien)]
        art = Segmentart(int(art_je_punkt[start]))
        laenge_m = laenge * punktabstand_m

        segmente.append(
            Segment(
                art=art,
                von=start,
                bis=int((start + laenge) % anzahl),
                punkte=laenge,
                laenge_m=laenge_m,
                radius_min_m=float(radien.min()),
                radius_mittel_m=float(endlich.mean()) if len(endlich) else float("inf"),
                # GDD 3: Nur Geraden ab 100 m Laenge sind Ueberholzonen.
                ist_ueberholzone=art is Segmentart.GERADE and laenge_m >= ueberholzone_min_m,
            )
        )

    segmente.sort(key=lambda segment: segment.von)
    return tuple(segmente)


def _baue_sektoren(anzahl_punkte: int, punktabstand_m: float, sektoren: int) -> tuple[Sektor, ...]:
    """Teilt die Runde in Sektoren gleicher Laenge ab der Start/Ziel-Linie.

    Geht die Punktzahl nicht glatt auf, unterscheiden sich die Sektoren um
    hoechstens einen Punkt.
    """
    if sektoren < 1:
        raise ValueError("Mindestens ein Sektor")
    grenzen = [round(nummer * anzahl_punkte / sektoren) for nummer in range(sektoren + 1)]
    return tuple(
        Sektor(
            nummer=nummer + 1,
            von=grenzen[nummer],
            bis=grenzen[nummer + 1],
            laenge_m=(grenzen[nummer + 1] - grenzen[nummer]) * punktabstand_m,
        )
        for nummer in range(sektoren)
    )


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------
def datenverzeichnis(unterordner: str = "daten") -> Path:
    """Findet das Datenverzeichnis im Quellbaum oder in der gepackten .exe."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        pfad = Path(bundle) / unterordner
        if pfad.is_dir():
            return pfad
    return Path(__file__).resolve().parent.parent.parent / unterordner


def werte_aus(
    linie: np.ndarray,
    *,
    name: str = "",
    land: str = "",
    charakter: str = "",
    datei: str = "",
    abtastabstand_m: float,
    enge_kurve_max_m: float,
    gerade_min_m: float,
    ueberholzone_min_m: float,
    sektoren: int,
) -> Strecke:
    """Wertet eine Linie zur fertigen Strecke aus.

    Getrennt von :func:`lade`, damit sich das Modell auch mit erzeugten
    Linien pruefen laesst, etwa mit einem Kreis bekannten Radius.
    """
    punkte, punktabstand = taste_ab(linie, abtastabstand_m)
    radius = kruemmungsradius(punkte)
    art = bestimme_art(radius, enge_kurve_max_m, gerade_min_m)

    return Strecke(
        name=name,
        land=land,
        charakter=charakter,
        datei=datei,
        punkte=punkte,
        radius_m=radius,
        art_je_punkt=art,
        segmente=_baue_segmente(art, radius, punktabstand, ueberholzone_min_m),
        sektoren=_baue_sektoren(len(punkte), punktabstand, sektoren),
        punktabstand_m=punktabstand,
    )


def lade(konfiguration, name: str, verzeichnis: Path | str | None = None) -> Strecke:
    """Laedt eine Strecke ueber ihren Namen aus der Konfiguration.

    :param konfiguration: geladene :class:`rennmanager.konfiguration.Konfiguration`
    :param name: Streckenname laut GDD 3, z. B. ``"Monza"`` oder ``"Mexiko-Stadt"``
    """
    eintraege = {eintrag["name"]: eintrag for eintrag in konfiguration.strecken}
    if name not in eintraege:
        raise StreckenFehler(
            f"Unbekannte Strecke {name!r}; bekannt sind: {', '.join(sorted(eintraege))}"
        )
    eintrag = eintraege[name]

    wurzel = (
        Path(verzeichnis)
        if verzeichnis is not None
        else datenverzeichnis() / "strecken"
    )
    linie = konfiguration.wert("strecke", "linie")
    roh = _lies_csv(wurzel / linie / f"{eintrag['datei']}.csv", spalten=2)

    return werte_aus(
        roh[:, :2],
        name=eintrag["name"],
        land=eintrag["land"],
        charakter=eintrag["charakter"],
        datei=eintrag["datei"],
        abtastabstand_m=konfiguration.wert("strecke", "abtastabstand_m"),
        enge_kurve_max_m=konfiguration.wert("strecke", "enge_kurve_radius_max_m"),
        gerade_min_m=konfiguration.wert("strecke", "gerade_radius_min_m"),
        ueberholzone_min_m=konfiguration.wert("strecke", "ueberholzone_mindestlaenge_m"),
        sektoren=konfiguration.wert("strecke", "sektoren"),
    )


def lade_alle(konfiguration, verzeichnis: Path | str | None = None) -> tuple[Strecke, ...]:
    """Laedt alle 20 Strecken der Saison in der Reihenfolge des Kalenders."""
    return tuple(
        lade(konfiguration, eintrag["name"], verzeichnis)
        for eintrag in konfiguration.strecken
    )
