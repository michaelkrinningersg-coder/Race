"""Das Wetter einer Saison (Punkt 39, Erweiterung zu GDD 7).

GDD 7 wuerfelt das Wetter je Session aus festen Gewichten des
Streckenprofils. Der Auftraggeber wollte eine Ebene darueber: **Jede
Saison bekommt ihr eigenes Wetter.** Es gibt Jahre, in denen es viel
regnet, und Jahre, in denen kaum ein Rennen nass wird - und je Strecke
ein Band, wie wahrscheinlich wechselhaftes Wetter dort ueberhaupt ist.

Drei Regeln, alle vom Auftraggeber:

* Je Strecke ein **Band der Wechselneigung**, aus dem jede Saison neu
  gewuerfelt wird. In der Wueste praktisch null, sonst bis zu 40 %.
* **Hoechstens zwei Wechsel je Rennen**, und immer nur **eine Stufe** der
  Kette aus GDD 7.
* Ueber eine Saison sollen **75 bis 85 % der Rennen rein trocken oder
  heiss** ablaufen, ohne einen einzigen Wechsel.

Die Wechselneigung ist nicht dasselbe wie die Nasswahrscheinlichkeit: Sie
sagt, wie oft sich das Wetter *waehrend* eines Rennens dreht. Ein Rennen
kann durchgehend im Regen stattfinden, ohne einen Wechsel zu haben.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class WettersaisonFehler(Exception):
    """Die Wetterbaender passen nicht zur Konfiguration."""


@dataclass(frozen=True)
class Saisonwetter:
    """Wie das Wetter in dieser Saison auf diesem Profil steht."""

    profil: str
    jahr: int
    # Gewicht je Zustand, schon auf 1 normiert.
    verteilung: dict[str, float]
    # Wahrscheinlichkeit, dass ein Rennen ueberhaupt einen Wechsel hat.
    wechselneigung: float

    def zustand(self, wuerfel) -> str:
        """Wuerfelt die Grundlage eines Rennens dieser Saison."""
        namen = list(self.verteilung)
        anteile = np.array([self.verteilung[n] for n in namen], dtype=float)
        return namen[int(wuerfel.choice(len(namen), p=anteile / anteile.sum()))]


def baender(konfiguration: Konfiguration, profil: str) -> dict:
    """Die Baender eines Streckenprofils."""
    alle = konfiguration.wert("wetter", "profil")
    if profil not in alle:
        raise WettersaisonFehler(f"Unbekanntes Wetterprofil: {profil}")
    eintrag = alle[profil]
    if "band" not in eintrag:
        raise WettersaisonFehler(f"Profil {profil} hat keine Baender")
    return eintrag["band"]


def wuerfle_saison(
    konfiguration: Konfiguration, profil: str, jahr: int, seedquelle: Seedquelle
) -> Saisonwetter:
    """Wuerfelt das Wetter eines Profils fuer eine Saison.

    Der Zweig haengt an Profil und Jahr, nicht an der Aufrufreihenfolge:
    Dieselbe Saison hat dasselbe Wetter, egal wann danach gefragt wird
    (GDD 15).
    """
    band = baender(konfiguration, profil)
    wuerfel = seedquelle.zweig("saisonwetter", jahr).zweig(profil).generator()

    kette = list(konfiguration.wert("wetter", "kette"))
    gewichte = {}
    for zustand in kette:
        unten, oben = band.get(zustand, [0, 0])
        gewichte[zustand] = float(wuerfel.uniform(unten, oben))
    summe = sum(gewichte.values())
    if summe <= 0:  # pragma: no cover - Notbremse
        raise WettersaisonFehler(f"Profil {profil} wuerfelt lauter Nullen")

    unten, oben = band["wechselneigung"]
    return Saisonwetter(
        profil=profil,
        jahr=jahr,
        verteilung={z: g / summe for z, g in gewichte.items()},
        wechselneigung=float(wuerfel.uniform(unten, oben)),
    )


def saisonwetter(
    konfiguration: Konfiguration, jahr: int, seedquelle: Seedquelle
) -> dict[str, Saisonwetter]:
    """Das Wetter aller Profile fuer eine Saison."""
    return {
        profil: wuerfle_saison(konfiguration, profil, jahr, seedquelle)
        for profil in konfiguration.wert("wetter", "profil")
    }


def fuer_strecke(
    konfiguration: Konfiguration,
    streckenname: str,
    jahr: int,
    seedquelle: Seedquelle,
) -> Saisonwetter:
    """Das Saisonwetter, das fuer diese Strecke gilt."""
    return wuerfle_saison(
        konfiguration,
        kern_wetter.profil_von(konfiguration, streckenname),
        jahr,
        seedquelle,
    )


def rennwetter(
    saison: Saisonwetter,
    konfiguration: Konfiguration,
    seedquelle: Seedquelle,
) -> tuple[str, ...]:
    """Die Wetterlagen eines Rennens, in ihrer Reihenfolge.

    Ein Eintrag heisst: durchgehend dieselbe Lage. Zwei oder drei heissen
    ein oder zwei Wechsel - immer nur **eine Stufe** der Kette, so hat es
    der Auftraggeber festgelegt. Ein Sprung von trocken auf Starkregen
    gibt es nicht.
    """
    wuerfel = seedquelle.generator()
    kette = list(konfiguration.wert("wetter", "kette"))
    hoechstens = konfiguration.wert("wetter", "saison", "wechsel_max")

    lagen = [saison.zustand(wuerfel)]
    if float(wuerfel.random()) >= saison.wechselneigung:
        return tuple(lagen)

    anzahl = int(wuerfel.integers(1, hoechstens + 1))
    for _ in range(anzahl):
        stelle = kette.index(lagen[-1])
        richtungen = [r for r in (-1, 1) if 0 <= stelle + r < len(kette)]
        schritt = richtungen[int(wuerfel.integers(0, len(richtungen)))]
        lagen.append(kette[stelle + schritt])
    return tuple(lagen)
