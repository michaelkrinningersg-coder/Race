"""Zufallssystem: Tagesform, Eigenschafts-Zufall, Rundenform (GDD 11).

Drei Ebenen gelten fuer Spieler und KI gleichermassen:

===================  ==============================  =====================
Ebene                Wann gewuerfelt                 Worauf
===================  ==============================  =====================
Tagesform            vor Qualifying, erneut vor       ein Faktor auf alle
                     dem Rennen                       Fahrerwerte
Eigenschafts-Zufall  vor Qualifying, erneut vor       jeder einzelne Wert
                     dem Rennen
Sektorform           jeden Sektor                     die Sektorzeit
===================  ==============================  =====================

Die Sektorform hiess bis Punkt 95 Rundenform und wurde einmal je Runde
gezogen. Jetzt faellt sie in jedem der vier Sektoren neu, und ihr
Vorzeichen haengt am Platzgewinn im Sektor davor: Wer gerade Plaetze
gutgemacht hat, faehrt den naechsten mit drei Vierteln Wahrscheinlichkeit
ueber seiner Form.

Qualifying und Rennen bekommen eigene Zweige der Seedquelle, damit beide
getrennt gewuerfelt werden und ein zusaetzlicher Wurf an einer Stelle die
uebrigen nicht verschiebt.

D16 Mentale Staerke begrenzt nur die negative Seite der Tagesform, D12
Konstanz verkleinert die Streuung der Sektorform.
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
    # Neben der Matrix stehen Fahrer- und Fahrzeugeigenschaften. Die
    # Tagesform traegt nur die des Fahrers (GDD 11).
    fahrzeug = konfiguration.fahrzeugzusatz
    wetterwerte = {
        schluessel: gewuerfelt(schluessel, wert, schluessel not in fahrzeug)
        for schluessel, wert in auto.wetterwerte.items()
    }
    return Sessionform(
        auto=Auto(auto.kuerzel, auto.name, werte, wetterwerte), tagesform=faktor
    )


def streuung(konfiguration: Konfiguration, auto: Auto) -> float:
    """Die Streuung der Sektorform dieses Autos (GDD 11).

    Der Grundwert aus der Konfiguration, verkleinert durch D12 Konstanz.
    """
    einstellung = konfiguration.wert("zufall", "rundenform")
    daempfung = einstellung["daempfung"]
    anteil = leistungsanteil(
        auto.wert(daempfung["faehigkeit"]), konfiguration.wert("skala", "referenz")
    )
    return einstellung["sigma"] * (1.0 - daempfung["max_anteil"] * min(anteil, 1.0))


def gute_haelfte(konfiguration: Konfiguration, plaetze: int) -> float:
    """Wahrscheinlichkeit, dass die Form nach oben ausschlaegt (Punkt 95).

    ``plaetze`` ist der Platzgewinn im Sektor davor: positiv fuer
    gutgemachte, negativ fuer verlorene Plaetze. Bei einem gewonnenen
    Platz steht die Wahrscheinlichkeit auf dem Wert aus der Konfiguration,
    und sie naehert sich mit jedem weiteren Platz der Eins, ohne sie zu
    erreichen - ein Fahrer wird nie sicher schnell.
    """
    if plaetze == 0:
        return 0.5
    bei_einem = konfiguration.wert("zufall", "rundenform", "kopplung", "bei_einem_platz")
    rest = 2.0 - 2.0 * bei_einem
    naeherung = 0.5 * (1.0 - rest ** abs(plaetze))
    return 0.5 + naeherung if plaetze > 0 else 0.5 - naeherung


def rundenform_aus_sektoren(
    konfiguration: Konfiguration,
    auto: Auto,
    seedquelle: Seedquelle,
    runde: int,
    plaetze: int = 0,
) -> float:
    """Die Form einer ganzen Runde als Mittel ihrer Sektoren (Punkt 95).

    Fuer den Schnellmodus, der keine Sektoren fuehrt. Weil die Sektoren
    gleich lang sind, ist die Rundenzeit das Mittel ihrer Faktoren - die
    Verteilung stimmt damit mit der vollen Simulation ueberein, ohne dass
    der Schnellmodus die Runde zerlegen muesste.
    """
    anzahl = konfiguration.wert("strecke", "sektoren")
    summe = sum(
        sektorform(konfiguration, auto, seedquelle, runde, sektor, plaetze)
        for sektor in range(anzahl)
    )
    return summe / anzahl


def sektorform(
    konfiguration: Konfiguration,
    auto: Auto,
    seedquelle: Seedquelle,
    runde: int,
    sektor: int = 0,
    plaetze: int = 0,
) -> float:
    """Faktor auf die Zeit eines einzelnen Sektors (GDD 11, Punkt 95).

    Gezogen wird der Betrag ``|normal(0, sigma)|``; das Vorzeichen faellt
    mit ``gute_haelfte`` gut aus. Bei p = 0,5 ist das rechnerisch wieder
    die Normalverteilung - ohne Platzaenderung im Sektor davor aendert
    sich also nichts am bisherigen Verhalten.

    Der Rueckgabewert ist ein Faktor auf die *Zeit*: groesser als 1
    bedeutet langsamer.

    :param plaetze: Platzgewinn im Sektor davor, negativ bei Verlusten
    """
    sigma = streuung(konfiguration, auto)
    wuerfel = seedquelle.zweig("sektor", runde, sektor).generator()
    betrag = abs(float(wuerfel.normal(0.0, sigma)))
    gut = float(wuerfel.random()) < gute_haelfte(konfiguration, plaetze)
    return 1.0 - betrag if gut else 1.0 + betrag
