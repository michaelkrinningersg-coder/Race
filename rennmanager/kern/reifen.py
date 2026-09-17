"""Reifenverschleiss (GDD 4).

"Reifen: Verschleiss senkt das Tempo und erhoeht die Fehlerquote; vorerst
keine Boxenstopps." Der Zustand faellt ueber die Renndistanz von 1,0
(frisch) Richtung 0,0 (abgefahren); wie schnell, haengt vom Auto ab.

Zwei Eigenschaften greifen an verschiedenen Stellen an:

* Der Bereich ``ve`` der Wirkungsmatrix - getragen von F10
  Reifenhaltbarkeit, F14, F16 und D14 Reifenmanagement - bestimmt, wie
  schnell die Reifen abbauen.
* Der **Reifenfluesterer** bestimmt, wie sehr abgebaute Reifen wehtun. Er
  senkt nicht den Verschleiss, sondern dessen Wirkung: Mit ihm holt ein
  Fahrer aus schlechten Reifen noch Zeit heraus.

Dass beide getrennt sind, ist der Grund, warum sich in der zweiten
Rennhaelfte ueberhaupt noch etwas bewegt: Ein Auto, das seine Reifen
schont, ist frueh langsamer und spaet schneller als eines, das sie
verheizt - die Linien kreuzen sich.

Der Streckenfaktor kommt aus der Querbeschleunigung der Runde, das Wetter
ueber den Multiplikator aus GDD 7.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern.auto import Auto, bereichswert
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.tempo import leistungsanteil

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Schluessel der neuen Fahrereigenschaft in Auto.wetterwerte - sie steht
# wie die Wetterfaehigkeiten ausserhalb der Wirkungsmatrix.
FLUESTERER = "reifenfluesterer"


def streckenfaktor(konfiguration: Konfiguration, strecke: Strecke, mittelwert: float) -> float:
    """Wie hart eine Strecke die Reifen nimmt (Entscheidung zu Punkt 10).

    Grundlage ist die Querbeschleunigung ueber die Runde - die Summe von
    1/Radius je Meter -, normiert auf den Mittelwert aller Strecken. Sie
    trennt schnelle Kurven von engen, was der blosse Kurvenanteil nicht
    leistet.
    """
    if konfiguration.wert("reifen", "streckenfaktor", "grundlage") != "querbeschleunigung":
        raise ValueError("Nur die Grundlage 'querbeschleunigung' ist umgesetzt")
    return querbeschleunigung(strecke) / max(mittelwert, 1e-9)


def querbeschleunigung(strecke: Strecke) -> float:
    """Mittlere Kruemmung der Runde, 1/m."""
    radius = np.clip(strecke.radius_m, 1.0, None)
    return float((1.0 / radius).sum() * strecke.punktabstand_m / strecke.laenge_m)


def mittlere_querbeschleunigung(strecken) -> float:
    """Bezugsgroesse des Streckenfaktors ueber alle Strecken."""
    werte = [querbeschleunigung(strecke) for strecke in strecken]
    return sum(werte) / len(werte)


def verschleiss_je_meter(
    konfiguration: Konfiguration,
    auto: Auto,
    renndistanz_m: float,
    streckenfaktor_wert: float = 1.0,
    wetterfaktor: float = 1.0,
) -> float:
    """Wie stark der Reifenzustand je gefahrenem Meter faellt.

    Der Wert ist so geeicht, dass ein Auto mit dem Bereich ``ve`` bei 0
    ueber die volle Renndistanz ``verschleiss_bei_null`` erreicht und eines
    bei ``referenz`` nur ``verschleiss_bei_referenz``.
    """
    einstellung = konfiguration.wert("reifen", "verschleiss")
    anteil = min(
        leistungsanteil(
            bereichswert(konfiguration, auto, "ve"), konfiguration.wert("skala", "referenz")
        ),
        1.0,
    )
    ueber_distanz = einstellung["verschleiss_bei_null"] + anteil * (
        einstellung["verschleiss_bei_referenz"] - einstellung["verschleiss_bei_null"]
    )
    return ueber_distanz * streckenfaktor_wert * wetterfaktor / max(renndistanz_m, 1.0)


def zustand(verschleiss: float) -> float:
    """Reifenzustand aus dem aufgelaufenen Verschleiss, 1,0 bis 0,0."""
    return float(np.clip(1.0 - verschleiss, 0.0, 1.0))


def _daempfung(konfiguration: Konfiguration, auto: Auto) -> float:
    """Wie stark der Reifenfluesterer die Wirkung des Abbaus senkt, 0 bis 1."""
    einstellung = konfiguration.wert("reifen", "fluesterer")
    anteil = min(
        leistungsanteil(auto.wetterwert(FLUESTERER), konfiguration.wert("skala", "referenz")),
        1.0,
    )
    return einstellung["max_daempfung"] * anteil


def tempofaktor(konfiguration: Konfiguration, auto: Auto, verschleiss: float) -> float:
    """Faktor auf das Tempo bei diesem Verschleiss (GDD 4).

    Der Verlust waechst progressiv: erst flach, gegen Ende steil. Der
    Reifenfluesterer senkt ihn um bis zu 60 %.
    """
    einstellung = konfiguration.wert("reifen", "verschleiss")
    abgefahren = 1.0 - zustand(verschleiss)
    verlust = einstellung["tempoverlust_voll"] * abgefahren ** einstellung["exponent"]
    return 1.0 - verlust * (1.0 - _daempfung(konfiguration, auto))


def fehlerfaktor(konfiguration: Konfiguration, auto: Auto, verschleiss: float) -> float:
    """Multiplikator auf die Fehlerquote bei diesem Verschleiss (GDD 4)."""
    einstellung = konfiguration.wert("reifen", "verschleiss")
    abgefahren = 1.0 - zustand(verschleiss)
    zuschlag = einstellung["fehlerzuschlag_voll"] * abgefahren ** einstellung["exponent"]
    return 1.0 + zuschlag * (1.0 - _daempfung(konfiguration, auto))
