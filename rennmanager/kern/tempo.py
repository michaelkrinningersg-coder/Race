"""Geschwindigkeitsprofil und Rundenzeit.

Setzt das Geschwindigkeitsmodell aus GDD 4 um:

1. Kurvenlimit aus dem Radius: ``v = sqrt(a_quer * r)``. Welche
   Eigenschaften die Querbeschleunigung tragen, sagt die Wirkungsmatrix -
   enge Kurven ueber den Bereich ``ek``, Kurven ueber ``k``.
2. Hoechstgeschwindigkeit auf Geraden aus dem Bereich ``g``, getrennt
   skaliert bis 400 km/h (GDD 9).
3. Vorwaertsdurchlauf mit der Beschleunigungsgrenze (Bereich ``bplus``),
   Rueckwaertsdurchlauf mit der Bremsgrenze (Bereich ``bminus``).

Wetter und Reifen kommen in den Schritten 5 und 6 dazu; dieses Modul
rechnet ohne Zufall und ist damit genau das, was GDD 9 zur Kalibrierung
verlangt.

Jede physikalische Grenze folgt derselben Form wie die Kalibrierfunktion:

    grenze(S) = basis + spanne * sqrt(S / referenz)

Alle Konstanten stehen in ``konfiguration/balancing.toml``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern.auto import Auto, bereichswerte
from rennmanager.kern.strecke import Segmentart, Strecke

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

KMH_JE_MS = 3.6
# Zwei Umlaeufe genuegen, damit sich Beschleunigen und Bremsen ueber die
# Start/Ziel-Linie hinweg ausbreiten; der zweite aendert nichts mehr.
UMLAEUFE = 2


@dataclass(frozen=True)
class Grenzen:
    """Die physikalischen Grenzen eines Autos, aus seinen Werten abgeleitet.

    :param quer_eng: Querbeschleunigung in engen Kurven, m/s^2
    :param quer: Querbeschleunigung in Kurven und schnellen Boegen, m/s^2
    :param laengs: Beschleunigungsgrenze, m/s^2
    :param brems: Bremsgrenze, m/s^2 (positiv)
    :param hoechst: Hoechstgeschwindigkeit, m/s
    """

    quer_eng: float
    quer: float
    laengs: float
    brems: float
    hoechst: float

    @property
    def hoechst_kmh(self) -> float:
        return self.hoechst * KMH_JE_MS


def leistungsanteil(s: float, referenz: float) -> float:
    """p = sqrt(S / referenz) - die Groesse, in der GDD 9 linear rechnet."""
    return math.sqrt(max(s, 0.0) / referenz)


def _grenze(s: float, basis: float, spanne: float, referenz: float) -> float:
    """grenze(S) = basis + spanne * p, linear im Leistungsanteil."""
    return basis + spanne * leistungsanteil(s, referenz)


def haftung(s: float, referenzwert: float, anteil_bei_null: float, referenz: float) -> float:
    """Haftungsniveau in m/s^2.

    Quadratisch in p, damit das Kurvenlimit ``sqrt(a * r)`` linear in p
    wird - so wie es die Kalibrierfunktion aus GDD 9 verlangt.
    """
    anteil = anteil_bei_null + (1.0 - anteil_bei_null) * leistungsanteil(s, referenz)
    return referenzwert * anteil * anteil


def grenzen_aus(konfiguration: Konfiguration, auto: Auto) -> Grenzen:
    """Leitet die physikalischen Grenzen eines Autos aus seinen Werten ab.

    Grundlage ist ein gemeinsames Haftungsniveau

        a(S) = basis + spanne * sqrt(S / referenz)

    aus dem sich die vier Beschleunigungsgrenzen ueber feste Faktoren
    ergeben. Die Faktoren bilden ab, was am Auto physikalisch
    zusammenhaengt: Bremsen kann mehr als Querhaftung, weil Luftwiderstand
    mithilft; enge Kurven bieten weniger, weil der Abtrieb mit dem Tempo
    waechst; Beschleunigen ist am staerksten begrenzt.

    Getrennt bleiben die Faehigkeiten trotzdem, denn jede Grenze zieht ihr
    ``S`` aus einem eigenen Wirkungsbereich (GDD 8): enge Kurven aus ``ek``,
    Kurven aus ``k``, Beschleunigen aus ``bplus``, Bremsen aus ``bminus``.
    Ein Auto mit starken Bremsen und schwachem Antritt faehrt deshalb
    anders als eines mit umgekehrtem Profil.
    """
    bereich = bereichswerte(konfiguration, auto)
    referenz = konfiguration.wert("skala", "referenz")
    referenzwert = konfiguration.wert("tempo", "haftung_referenz")
    anteil_bei_null = konfiguration.wert("tempo", "anteil_bei_null")

    def grenze(s: float, faktor_name: str) -> float:
        niveau = haftung(s, referenzwert, anteil_bei_null, referenz)
        return niveau * konfiguration.wert("tempo", faktor_name)

    hoechst_referenz = konfiguration.wert("tempo", "hoechstgeschwindigkeit_bei_referenz_kmh")
    # Dieselbe Kopplung wie bei der Haftung, damit GDD 9 das Modell
    # eindeutig festlegt (siehe Kommentar in balancing.toml).
    hoechst_basis = hoechst_referenz * anteil_bei_null

    return Grenzen(
        quer_eng=grenze(bereich["ek"], "faktor_enge_kurve"),
        quer=grenze(bereich["k"], "faktor_kurve"),
        laengs=grenze(bereich["bplus"], "faktor_beschleunigen"),
        brems=grenze(bereich["bminus"], "faktor_bremsen"),
        # Die Endgeschwindigkeit wird laut GDD 9 getrennt skaliert.
        hoechst=_grenze(
            bereich["g"], hoechst_basis, hoechst_referenz - hoechst_basis, referenz
        )
        / KMH_JE_MS,
    )


def kurvenlimit(strecke: Strecke, grenzen: Grenzen) -> np.ndarray:
    """Hoechstmoegliche Geschwindigkeit je Punkt aus Radius und Querhaftung.

    ``v = sqrt(a_quer * r)``; die Hoechstgeschwindigkeit begrenzt zusaetzlich.
    """
    quer = np.where(
        strecke.art_je_punkt == Segmentart.ENGE_KURVE,
        grenzen.quer_eng,
        grenzen.quer,
    )
    # Auf exakten Geraden ist der Radius unendlich; dort greift allein die
    # Hoechstgeschwindigkeit.
    with np.errstate(invalid="ignore"):
        limit = np.sqrt(quer * strecke.radius_m)
    return np.minimum(np.nan_to_num(limit, posinf=grenzen.hoechst), grenzen.hoechst)


def geschwindigkeitsprofil(strecke: Strecke, grenzen: Grenzen) -> np.ndarray:
    """Berechnet die Geschwindigkeit je Streckenpunkt in m/s.

    Vorwaertsdurchlauf mit der Beschleunigungsgrenze, Rueckwaertsdurchlauf
    mit der Bremsgrenze (GDD 4). Weil die Runde geschlossen ist, laufen
    beide Durchgaenge zweimal herum.
    """
    v = kurvenlimit(strecke, grenzen)
    anzahl = len(v)
    ds = strecke.punktabstand_m

    # Vorwaerts: schneller werden geht nur mit der Beschleunigungsgrenze.
    zuwachs = 2.0 * grenzen.laengs * ds
    for _ in range(UMLAEUFE):
        for i in range(anzahl):
            naechster = (i + 1) % anzahl
            moeglich = math.sqrt(v[i] * v[i] + zuwachs)
            if moeglich < v[naechster]:
                v[naechster] = moeglich

    # Rueckwaerts: vor einer Kurve muss rechtzeitig gebremst werden.
    abnahme = 2.0 * grenzen.brems * ds
    for _ in range(UMLAEUFE):
        for i in range(anzahl - 1, -1, -1):
            naechster = (i + 1) % anzahl
            moeglich = math.sqrt(v[naechster] * v[naechster] + abnahme)
            if moeglich < v[i]:
                v[i] = moeglich

    return v


def rundenzeit_ms(strecke: Strecke, profil: np.ndarray) -> int:
    """Rundenzeit in ganzen Millisekunden.

    Zwischen zwei Punkten wird gleichmaessige Beschleunigung angenommen;
    dann ist die Fahrzeit exakt ``2 * ds / (v1 + v2)``.
    """
    v_naechster = np.roll(profil, -1)
    summe = 2.0 * strecke.punktabstand_m / (profil + v_naechster)
    return int(round(float(summe.sum()) * 1000.0))


def sektorzeiten_ms(strecke: Strecke, profil: np.ndarray) -> tuple[int, ...]:
    """Zeit je Sektor in ganzen Millisekunden (GDD 4: 4 Sektorzeiten).

    Die Summe der Sektorzeiten kann durch das Runden um wenige
    Millisekunden von der Rundenzeit abweichen; massgeblich ist die
    Rundenzeit.
    """
    v_naechster = np.roll(profil, -1)
    dauer = 2.0 * strecke.punktabstand_m / (profil + v_naechster)
    return tuple(
        int(round(float(dauer[sektor.von : sektor.bis].sum()) * 1000.0))
        for sektor in strecke.sektoren
    )


def durchschnittstempo_kmh(strecke: Strecke, zeit_ms: int) -> float:
    """Rundenschnitt in km/h - die Groesse, auf die GDD 9 kalibriert."""
    return strecke.laenge_m / (zeit_ms / 1000.0) * KMH_JE_MS


@dataclass(frozen=True)
class Rundenergebnis:
    """Das Ergebnis einer gefahrenen Runde ohne Zufall."""

    zeit_ms: int
    sektoren_ms: tuple[int, ...]
    schnitt_kmh: float
    hoechstgeschwindigkeit_kmh: float
    profil: np.ndarray


def fahre_runde(konfiguration: Konfiguration, strecke: Strecke, auto: Auto) -> Rundenergebnis:
    """Faehrt eine Runde ohne Zufall und liefert Zeit und Profil."""
    grenzen = grenzen_aus(konfiguration, auto)
    profil = geschwindigkeitsprofil(strecke, grenzen)
    zeit = rundenzeit_ms(strecke, profil)
    return Rundenergebnis(
        zeit_ms=zeit,
        sektoren_ms=sektorzeiten_ms(strecke, profil),
        schnitt_kmh=durchschnittstempo_kmh(strecke, zeit),
        hoechstgeschwindigkeit_kmh=float(profil.max()) * KMH_JE_MS,
        profil=profil,
    )
