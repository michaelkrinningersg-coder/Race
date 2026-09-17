"""Zufallssystem: Tagesform, Eigenschafts-Zufall, Rundenform (GDD 11).

Drei Ebenen gelten fuer Spieler und KI gleichermassen:

===================  ==============================  =====================
Ebene                Wann gewuerfelt                 Worauf
===================  ==============================  =====================
Tagesform            vor Qualifying, erneut vor       ein Faktor auf alle
                     dem Rennen                       Fahrerwerte
Eigenschafts-Zufall  vor Qualifying, erneut vor       jeder einzelne Wert
                     dem Rennen
Rundenform           jede Runde                       die Rundenzeit
===================  ==============================  =====================

Qualifying und Rennen bekommen eigene Zweige der Seedquelle, damit beide
getrennt gewuerfelt werden und ein zusaetzlicher Wurf an einer Stelle die
uebrigen nicht verschiebt.

D16 Mentale Staerke begrenzt nur die negative Seite der Tagesform, D12
Konstanz verkleinert die Streuung der Rundenform.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto
from rennmanager.kern.tempo import leistungsanteil
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Fahrer-Eigenschaften heissen D1 bis D16; nur sie traegt die Tagesform.
FAHRER_PRAEFIX = "D"


@dataclass(frozen=True)
class Sessionform:
    """Das Ergebnis der beiden Wuerfe vor einer Session.

    :param auto: das Auto mit gewuerfelten Werten, so wie es faehrt
    :param tagesform: der gezogene Faktor, fuer die Anzeige
    """

    auto: Auto
    tagesform: float


def _begrenzt(wert: float, grenze: float) -> float:
    return min(max(wert, -grenze), grenze)


def tagesform(
    konfiguration: Konfiguration,
    auto: Auto,
    seedquelle: Seedquelle,
    mittelwert: float = 0.0,
) -> float:
    """Zieht den Tagesform-Faktor eines Autos (GDD 11).

    Streuung 3 %, begrenzt auf +/- 8 %. Eine schlechte Tagesform wird durch
    D16 Mentale Staerke gedaempft, eine gute nicht.

    :param mittelwert: Zuschlag auf den Mittelwert der Verteilung (E3
        Motivationsschub aus GDD 14). Er verschiebt allein das Ergebnis;
        Streuung, Grenze und die Daempfung durch D16 bleiben, wie GDD 11
        sie nennt - E3 hebt den *Mittelwert*, nicht die Spanne.
    """
    einstellung = konfiguration.wert("zufall", "tagesform")
    wuerfel = seedquelle.generator()
    abweichung = _begrenzt(float(wuerfel.normal(0.0, einstellung["sigma"])), einstellung["grenze"])

    if abweichung < 0.0:
        daempfung = einstellung["daempfung"]
        anteil = leistungsanteil(
            auto.wert(daempfung["faehigkeit"]), konfiguration.wert("skala", "referenz")
        )
        abweichung *= 1.0 - daempfung["max_anteil"] * min(anteil, 1.0)
    return 1.0 + mittelwert + abweichung


def wuerfle(
    konfiguration: Konfiguration,
    auto: Auto,
    seedquelle: Seedquelle,
    tagesformbonus: float = 0.0,
) -> Sessionform:
    """Wuerfelt Tagesform und Eigenschafts-Zufall fuer eine Session.

    Die Tagesform wirkt laut GDD 11 auf alle Fahrerwerte, der
    Eigenschafts-Zufall auf jeden einzelnen Wert - auch auf die des
    Fahrzeugs und auf die Wetterfaehigkeiten.

    :param tagesformbonus: Zuschlag auf den Tagesform-Mittelwert (E3)
    """
    faktor = tagesform(
        konfiguration, auto, seedquelle.zweig("tagesform"), tagesformbonus
    )
    einstellung = konfiguration.wert("zufall", "eigenschaft")
    wuerfel = seedquelle.zweig("eigenschaft").generator()

    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")

    def gewuerfelt(schluessel: str, wert: int, mit_tagesform: bool) -> int:
        abweichung = _begrenzt(
            float(wuerfel.normal(0.0, einstellung["sigma"])), einstellung["grenze"]
        )
        neu = wert * (1.0 + abweichung)
        if mit_tagesform:
            neu *= faktor
        return int(round(min(max(neu, kleinster), groesster)))

    werte = {
        schluessel: gewuerfelt(schluessel, wert, schluessel.startswith(FAHRER_PRAEFIX))
        for schluessel, wert in auto.werte.items()
    }
    # Die Wetterfaehigkeiten gehoeren dem Fahrer, also traegt sie die
    # Tagesform ebenfalls.
    wetterwerte = {
        schluessel: gewuerfelt(schluessel, wert, True)
        for schluessel, wert in auto.wetterwerte.items()
    }
    return Sessionform(
        auto=Auto(auto.kuerzel, auto.name, werte, wetterwerte), tagesform=faktor
    )


def rundenform(
    konfiguration: Konfiguration, auto: Auto, seedquelle: Seedquelle, runde: int
) -> float:
    """Faktor auf die Rundenzeit einer einzelnen Runde (GDD 11).

    Streuung 0,3 %, verkleinert durch D12 Konstanz. Der Rueckgabewert ist
    ein Faktor auf die *Zeit*: groesser als 1 bedeutet langsamer.
    """
    einstellung = konfiguration.wert("zufall", "rundenform")
    daempfung = einstellung["daempfung"]
    anteil = leistungsanteil(
        auto.wert(daempfung["faehigkeit"]), konfiguration.wert("skala", "referenz")
    )
    sigma = einstellung["sigma"] * (1.0 - daempfung["max_anteil"] * min(anteil, 1.0))

    wuerfel = seedquelle.zweig("runde", runde).generator()
    return 1.0 + float(wuerfel.normal(0.0, sigma))
