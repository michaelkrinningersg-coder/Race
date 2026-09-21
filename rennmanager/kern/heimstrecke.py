"""Heimstrecke: ein kleiner Bonus im eigenen Land (Punkt 2).

Die Strecken tragen ihr Land (GDD 3), die Fahrer ihres (GDD 12) - mehr
braucht es nicht. Wer im eigenen Land faehrt, bekommt einen Zuschlag von
0,5 bis 1,0 Prozent auf **fuenf Eigenschaften**, die jedes Rennwochenende
neu gezogen werden. Welche fuenf es sind, steht damit nicht fest: Mal
trifft es die Bremsen, mal die Nerven.

Gezogen wird aus allen Eigenschaften eines Autos - den 32 der
Wirkungsmatrix aus GDD 8 und denen daneben (Wetterfaehigkeiten,
Reifenfluesterer und die fuenf aus Punkt 48).

**Nicht jeder hat eine Heimstrecke.** Die 20 Strecken liegen in 17
Laendern, die 400 Fahrer kommen aus 32. Wer kein Land mit Strecke hat,
geht leer aus - so mit dem Auftraggeber abgestimmt. Gemessen betrifft der
Bonus 150 der 400 Fahrer.

Der Bonus greift wie die entwickelten Werte des Spielers: ueber
``welt.starterfeld(..., autos=...)``. Die Reihenfolge des Feldes bleibt
davon unberuehrt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


def ist_heimstrecke(land: str, strecke: Strecke) -> bool:
    """Ob diese Strecke im Land des Fahrers liegt."""
    return bool(land) and land == strecke.land


def heimfahrer(fahrer, strecke: Strecke) -> tuple:
    """Alle Fahrer eines Feldes, die hier zu Hause sind."""
    return tuple(f for f in fahrer if ist_heimstrecke(f.land, strecke))


def gezogene_eigenschaften(
    konfiguration: Konfiguration, auto: Auto, seedquelle: Seedquelle
) -> tuple[str, ...]:
    """Die Eigenschaften, die dieses Wochenende den Bonus bekommen.

    Ohne Zuruecklegen gezogen und sortiert zurueckgegeben, damit die
    Anzeige eine feste Reihenfolge hat.
    """
    anzahl = int(konfiguration.wert("heimstrecke", "eigenschaften"))
    topf = sorted(auto.werte) + sorted(auto.wetterwerte)
    if not topf:
        return ()
    wuerfel = seedquelle.generator()
    gezogen = wuerfel.choice(len(topf), size=min(anzahl, len(topf)), replace=False)
    return tuple(sorted(topf[int(stelle)] for stelle in gezogen))


def mit_bonus(
    konfiguration: Konfiguration, auto: Auto, seedquelle: Seedquelle
) -> Auto:
    """Dasselbe Auto, mit dem Heimbonus auf fuenf Eigenschaften."""
    einstellung = konfiguration.wert("heimstrecke")
    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")
    gezogen = set(gezogene_eigenschaften(konfiguration, auto, seedquelle))
    if not gezogen:
        return auto

    # Ein eigener Zweig fuer die Hoehe, damit sie sich nicht mit der
    # Auswahl verschiebt.
    wuerfel = seedquelle.zweig("hoehe").generator()

    def gehoben(schluessel: str, wert: int) -> int:
        if schluessel not in gezogen:
            return wert
        zuschlag = float(
            wuerfel.uniform(einstellung["bonus_min"], einstellung["bonus_max"])
        )
        return int(round(min(max(wert * (1.0 + zuschlag), kleinster), groesster)))

    return Auto(
        kuerzel=auto.kuerzel,
        name=auto.name,
        werte={s: gehoben(s, w) for s, w in auto.werte.items()},
        wetterwerte={s: gehoben(s, w) for s, w in auto.wetterwerte.items()},
    )
