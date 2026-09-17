"""Sponsoren (GDD 10).

Sechs Plaetze: Anzug, Helm, Muetze, Auto-Hauptsponsor und zwei
Auto-Nebensponsoren. Je Platz liegen immer 3 bis 10 Angebote vor, jedes
bleibt 3 bis 10 Wochen bestehen. Die Laufzeit eines Vertrags betraegt 3
bis 25 Rennen und kann ueber das Saisonende hinausgehen.

Verguetet wird je Angebot ein Grundbetrag je Rennen plus Praemien fuer
Sieg, Top 3 und Top 10. Die Betraege skalieren mit der Liga - hoehere
Ligen bringen bessere Sponsoren und damit schnellere Entwicklung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rennmanager.kern.einnahmen import siegpraemie
from rennmanager.kern.welt import lade_namen
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class SponsorenFehler(Exception):
    """Ein Platz oder Vertrag passt nicht zur Konfiguration."""


@dataclass(frozen=True)
class Angebot:
    """Ein Sponsorenangebot fuer einen Platz (GDD 10)."""

    platz: str
    name: str
    grundbetrag: int
    praemie_sieg: int
    praemie_top3: int
    praemie_top10: int
    laufzeit_rennen: int
    # Bis zu welcher Woche das Angebot bestehen bleibt.
    gueltig_bis_woche: int

    def verguetung(self, platz: int) -> int:
        """Was das Angebot fuer eine Platzierung zahlt."""
        betrag = self.grundbetrag
        if platz == 1:
            betrag += self.praemie_sieg
        if platz <= 3:
            betrag += self.praemie_top3
        if platz <= 10:
            betrag += self.praemie_top10
        return betrag

    @property
    def hoechstwert(self) -> int:
        """Was je Rennen hoechstens herauskommt - fuer den Vergleich."""
        return self.verguetung(1)


@dataclass(frozen=True)
class Vertrag:
    """Ein laufender Vertrag."""

    angebot: Angebot
    verbleibende_rennen: int

    @property
    def laeuft(self) -> bool:
        return self.verbleibende_rennen > 0

    def nach_rennen(self) -> Vertrag:
        return Vertrag(self.angebot, max(self.verbleibende_rennen - 1, 0))


def plaetze(konfiguration: Konfiguration) -> tuple[str, ...]:
    """Die sechs Sponsorenplaetze (GDD 10)."""
    return tuple(konfiguration.wert("sponsoren", "plaetze"))


def grundbetrag_je_platz(konfiguration: Konfiguration, liga: int, platz: str) -> float:
    """Grundbetrag eines Platzes je Rennen, vor der Streuung.

    Der Gesamtbetrag aller sechs Plaetze ist ein Anteil der Siegpraemie;
    die Aufteilung gibt jedem Platz seinen Teil davon.
    """
    aufteilung = konfiguration.wert("sponsoren", "aufteilung")
    if platz not in aufteilung:
        raise SponsorenFehler(f"Unbekannter Sponsorenplatz: {platz}")
    gesamt = konfiguration.wert("sponsoren", "betraege", "grundbetrag_alle_plaetze")
    return siegpraemie(konfiguration, liga) * gesamt * aufteilung[platz]


def wuerfle_angebote(
    konfiguration: Konfiguration, liga: int, woche: int, seedquelle: Seedquelle
) -> dict[str, tuple[Angebot, ...]]:
    """Wuerfelt die aktuell vorliegenden Angebote je Platz (GDD 10)."""
    namen = lade_namen(konfiguration)["sponsor"]
    einstellung = konfiguration.wert("sponsoren")
    praemien = einstellung["betraege"]
    wuerfel = seedquelle.zweig("sponsoren", woche).generator()

    vergeben: set[str] = set()
    angebote: dict[str, tuple[Angebot, ...]] = {}
    for platz in plaetze(konfiguration):
        anzahl = int(
            wuerfel.integers(
                einstellung["angebote_je_platz_min"], einstellung["angebote_je_platz_max"] + 1
            )
        )
        grundlage = grundbetrag_je_platz(konfiguration, liga, platz)
        liste = []
        for _ in range(anzahl):
            while True:
                name = (
                    f"{namen['erste_teile'][int(wuerfel.integers(0, len(namen['erste_teile'])))]} "
                    f"{namen['zweite_teile'][int(wuerfel.integers(0, len(namen['zweite_teile'])))]}"
                )
                if name not in vergeben:
                    vergeben.add(name)
                    break

            streuung = praemien["streuung"]
            grund = grundlage * (1.0 + float(wuerfel.uniform(-streuung, streuung)))
            liste.append(
                Angebot(
                    platz=platz,
                    name=name,
                    grundbetrag=int(round(grund)),
                    praemie_sieg=int(round(grund * praemien["praemie_sieg"])),
                    praemie_top3=int(round(grund * praemien["praemie_top3"])),
                    praemie_top10=int(round(grund * praemien["praemie_top10"])),
                    laufzeit_rennen=int(
                        wuerfel.integers(
                            einstellung["laufzeit_rennen_min"],
                            einstellung["laufzeit_rennen_max"] + 1,
                        )
                    ),
                    gueltig_bis_woche=woche
                    + int(
                        wuerfel.integers(
                            einstellung["angebot_gueltig_wochen_min"],
                            einstellung["angebot_gueltig_wochen_max"] + 1,
                        )
                    ),
                )
            )
        angebote[platz] = tuple(liste)
    return angebote


def unterschreibe(angebot: Angebot) -> Vertrag:
    """Macht aus einem Angebot einen laufenden Vertrag."""
    return Vertrag(angebot=angebot, verbleibende_rennen=angebot.laufzeit_rennen)


def auszahlung(vertraege: dict[str, Vertrag], platz: int) -> int:
    """Was alle laufenden Vertraege nach einem Rennen zahlen (GDD 10)."""
    return sum(
        vertrag.angebot.verguetung(platz)
        for vertrag in vertraege.values()
        if vertrag.laeuft
    )


def nach_rennen(vertraege: dict[str, Vertrag]) -> dict[str, Vertrag]:
    """Zaehlt alle Vertraege um ein Rennen herunter; abgelaufene fallen weg."""
    weiter = {}
    for platz, vertrag in vertraege.items():
        naechster = vertrag.nach_rennen()
        if naechster.laeuft:
            weiter[platz] = naechster
    return weiter
