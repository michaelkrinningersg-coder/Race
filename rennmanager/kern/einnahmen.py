"""Preisgeld, Erfahrung und Startgeld (GDD 10).

Geld und Erfahrung kommen aus Rennen und Sponsoren. Das Geld ist das
Teambudget des Spielers und fliesst nur in Upgrades und Reparaturen; es
gibt keine laufenden Kosten, keine Schulden und keinen Bankrott.

Die Siegpraemie ist fuer die Ligen 20, 15, 10, 5 und 1 vorgegeben und wird
dazwischen logarithmisch interpoliert (Entscheidung zu Punkt 12): Das GDD
begruendet die Preisgelder relativ - "ein Top-3-Fahrer soll das Niveau der
naechsten Liga in etwa 1,5 Saisons erreichen" -, also muss auch die
Interpolation ueber das Verhaeltnis laufen.

Die Anteile der Plaetze fallen geometrisch von Platz 3 (65 %) auf Platz 30
(5 %); Platz 1 und 2 sind mit 100 % und 80 % vorgegeben.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class EinnahmenFehler(Exception):
    """Eine Liga oder ein Platz liegt ausserhalb des Gueltigen."""


def siegpraemie(konfiguration: Konfiguration, liga: int) -> int:
    """Siegpraemie einer Liga in Euro (GDD 10)."""
    stuetzen = {
        int(nummer): betrag
        for nummer, betrag in konfiguration.wert("preisgeld", "siegpraemie_euro").items()
    }
    if liga in stuetzen:
        return int(stuetzen[liga])

    verfahren = konfiguration.wert("preisgeld", "interpolation", "verfahren")
    if verfahren != "logarithmisch":
        raise EinnahmenFehler("Nur die Interpolation 'logarithmisch' ist umgesetzt")

    geordnet = sorted(stuetzen)
    if not geordnet[0] <= liga <= geordnet[-1]:
        raise EinnahmenFehler(f"Liga {liga} liegt ausserhalb der Preisgeldtabelle")

    # Nachbarstuetzstellen suchen und im Logarithmus interpolieren.
    unten = max(n for n in geordnet if n <= liga)
    oben = min(n for n in geordnet if n >= liga)
    anteil = (liga - unten) / (oben - unten)
    log = math.log(stuetzen[unten]) + anteil * (
        math.log(stuetzen[oben]) - math.log(stuetzen[unten])
    )
    return int(round(math.exp(log)))


def anteil(konfiguration: Konfiguration, platz: int) -> float:
    """Anteil eines Platzes an der Siegpraemie (GDD 10).

    Platz 1 bis 3 und Platz 30 sind vorgegeben; dazwischen faellt der
    Anteil geometrisch, also mit gleichbleibendem Verhaeltnis je Platz.
    """
    vorgabe = {
        int(nummer): wert
        for nummer, wert in konfiguration.wert("preisgeld", "anteil").items()
    }
    autos = konfiguration.wert("rennen", "autos")
    if not 1 <= platz <= autos:
        raise EinnahmenFehler(f"Platz {platz} gibt es bei {autos} Autos nicht")
    if platz in vorgabe and platz != max(vorgabe):
        return float(vorgabe[platz])

    kurve = konfiguration.wert("preisgeld", "anteil_kurve")
    if kurve["verfahren"] != "geometrisch":
        raise EinnahmenFehler("Nur die Anteilskurve 'geometrisch' ist umgesetzt")

    von, bis = kurve["von_platz"], kurve["bis_platz"]
    oben, unten = float(vorgabe[von]), float(vorgabe[bis])
    verhaeltnis = (unten / oben) ** (1.0 / (bis - von))
    return oben * verhaeltnis ** (platz - von)


def preisgeld(konfiguration: Konfiguration, liga: int, platz: int) -> int:
    """Preisgeld fuer eine Platzierung in Euro (GDD 10)."""
    return int(round(siegpraemie(konfiguration, liga) * anteil(konfiguration, platz)))


def startgeld(konfiguration: Konfiguration, liga: int) -> int:
    """Startgeld fuer jeden Teilnehmer (GDD 10)."""
    return int(
        round(
            siegpraemie(konfiguration, liga)
            * konfiguration.wert("preisgeld", "startgeld", "anteil_siegpraemie")
        )
    )


def preisgeldtopf(konfiguration: Konfiguration, liga: int) -> int:
    """Was ein Rennen an Preisgeld und Startgeld insgesamt ausschuettet."""
    autos = konfiguration.wert("rennen", "autos")
    return sum(preisgeld(konfiguration, liga, platz) for platz in range(1, autos + 1)) + (
        startgeld(konfiguration, liga) * autos
    )


# ---------------------------------------------------------------------------
# Erfahrung
# ---------------------------------------------------------------------------
def sieg_erfahrung(konfiguration: Konfiguration, liga: int) -> int:
    """EP fuer einen Sieg. GDD 10: "EP-Betraege = Preisgeld durch 10"."""
    teiler = konfiguration.wert("erfahrung", "teiler_gegenueber_preisgeld")
    return int(round(siegpraemie(konfiguration, liga) / teiler))


def erfahrung_fuer(
    konfiguration: Konfiguration,
    liga: int,
    platz: int,
    ueberholmanoever: int = 0,
    sessions: int = 2,
) -> int:
    """Erfahrung aus einem Rennwochenende (GDD 10).

    Drei Bestandteile: ein Grundbetrag je Session, ein Platzierungsbonus
    nach derselben Kurve wie das Preisgeld und ein Bonus je gelungenem
    Ueberholmanoever.

    :param sessions: Qualifying und Rennen zaehlen je einmal
    """
    einstellung = konfiguration.wert("erfahrung", "betraege")
    grundlage = sieg_erfahrung(konfiguration, liga)

    grund = grundlage * einstellung["grundbetrag_je_session"] * sessions
    platzierung = (
        grundlage * anteil(konfiguration, platz) * einstellung["platzierung_nach_tabelle"]
    )
    ueberholen = grundlage * einstellung["je_ueberholmanoever"] * ueberholmanoever
    return int(round(grund + platzierung + ueberholen))


def wetter_erfahrung(
    konfiguration: Konfiguration, liga: int, kilometer: float, platz: int | None = None
) -> int:
    """EP fuer den Topf eines Wetters (GDD 10).

    "Eigener Topf je Wetter, nur fuer die passende Wetterfaehigkeit
    nutzbar; Verdienst je gefahrenem km im jeweiligen Wetter plus
    Platzierungsbonus."
    """
    grundlage = sieg_erfahrung(konfiguration, liga)
    je_km = konfiguration.wert("erfahrung", "wetter", "betrag", "je_km_anteil_sieg_ep")
    betrag = grundlage * je_km * kilometer
    if platz is not None:
        betrag += grundlage * je_km * kilometer * anteil(konfiguration, platz)
    return int(round(betrag))


def startkapital(konfiguration: Konfiguration) -> int:
    """GDD 10: Startkapital 1.000 Euro."""
    return int(konfiguration.wert("kosten", "startkapital_euro"))


def starterfahrung(konfiguration: Konfiguration) -> int:
    """Der Erfahrungssockel zum Start (Entscheidung des Auftraggebers).

    Das GDD kennt ihn nicht - er wurde noetig, als ein belegter Tag auch
    Erfahrung zu kosten begann (Punkt 66). Ohne ihn liesse sich vor dem
    ersten Rennen kein einziger Tag belegen.
    """
    return int(konfiguration.wert("kosten", "startkapital_erfahrung"))
