"""Rhythmus: Vorteil in Kurvenfolgen (Punkt 15).

Manche Strecken bestehen aus Kurven, die ohne Gerade ineinander uebergehen
- Zandvoort und Budapest sind solche, Monza ist das Gegenteil. Wer den
Rhythmus hat, faehrt dort besser; wer ihn nicht hat, verliert.

Zwei Terme, beide auf -1 bis +1 gebracht und miteinander multipliziert:

* **Strecke**: der Kurvenfolgenanteil aus ``strecke.kurvenfolgenanteil``
  gegen den Mittelwert aller 20 Strecken. Gemessen reicht er von 0,23x
  (Monza) bis 1,77x (Zandvoort).
* **Fahrer**: -1 bei Wert 0, 0 bei der Haelfte des Leistungsanteils, +1
  bei vollem Wert.

Das Ergebnis ist ein Faktor auf die Querbeschleunigung in normalen Kurven
(``quer``), nicht auf enge: Kurvenfolgen sind fliessende Passagen. Er wird
auf die ``Grenzen`` gelegt, bevor das Geschwindigkeitsprofil gebildet wird
- der Vorteil faellt damit von selbst dort an, wo wirklich Kurven liegen.

Die Eigenschaft ``rhythmus`` steht neben der Wirkungsmatrix aus GDD 8,
damit Gesamtwert, Bereichswerte und die Kalibriertabelle aus GDD 9
unberuehrt bleiben. Auch der Faktor selbst gehoert zu dem, was
``ohne_zufall`` abschaltet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.tempo import leistungsanteil

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Eigenschaft neben der Wirkungsmatrix; fehlt sie, gilt 0 (GDD 1).
RHYTHMUS = "rhythmus"


def mittlerer_kurvenfolgenanteil(strecken: tuple[Strecke, ...]) -> float:
    """Mittelwert ueber alle Strecken, Bezugsgroesse des Streckenterms."""
    if not strecken:
        return 0.0
    return sum(strecke.kurvenfolgenanteil for strecke in strecken) / len(strecken)


def streckenterm(strecke: Strecke, mittel: float) -> float:
    """Wie kurvenreich diese Strecke gegen den Schnitt ist, -1 bis +1."""
    if mittel <= 0.0:
        return 0.0
    return min(max(strecke.kurvenfolgenanteil / mittel - 1.0, -1.0), 1.0)


def fahrerterm(konfiguration: Konfiguration, auto: Auto) -> float:
    """Wie gut dieser Fahrer den Rhythmus hat, -1 bis +1."""
    anteil = min(
        leistungsanteil(auto.wetterwert(RHYTHMUS), konfiguration.wert("skala", "referenz")),
        1.0,
    )
    return 2.0 * anteil - 1.0


def faktor(
    konfiguration: Konfiguration, auto: Auto, strecke: Strecke, mittel: float
) -> float:
    """Faktor auf die Querbeschleunigung in Kurven."""
    max_anteil = konfiguration.wert("rhythmus", "max_anteil_quer")
    return 1.0 + max_anteil * fahrerterm(konfiguration, auto) * streckenterm(strecke, mittel)
