"""Auto: Eigenschaftswerte und ihre Wirkung je Bereich.

Ein Auto im Sinne der Simulation ist die Einheit aus Fahrzeug und Fahrer:
16 Fahrzeug-Upgrades (F1 bis F16, GDD 5) und 16 Fahrer-Eigenschaften
(D1 bis D16, GDD 6), alle auf der Skala 0 bis 100.000.

Die Wirkungsmatrix aus GDD 8 fasst diese 32 Werte je Wirkungsbereich zu
einem einzigen Wert zusammen - dem gewichteten Mittel. GDD 9 nennt genau
diesen Wert ``S`` und leitet daraus die Geschwindigkeit ab.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class AutoFehler(Exception):
    """Die Eigenschaftswerte eines Autos sind unvollstaendig oder ungueltig."""


@dataclass(frozen=True)
class Auto:
    """Ein Auto mit allen Eigenschaftswerten.

    :param werte: Wert je Faehigkeit, Schluessel ``F1`` bis ``F16`` und
        ``D1`` bis ``D16``, jeweils 0 bis 100.000
    :param wetterwerte: Wert je Wetterfaehigkeit (GDD 7), etwa
        ``"regenfahren"``. Sie stehen getrennt, weil sie keine Zeile in der
        Wirkungsmatrix haben und nicht in den Durchschnitt der
        Basiseigenschaften eingehen (GDD 4).
    """

    kuerzel: str
    name: str
    werte: dict[str, int] = field(default_factory=dict)
    wetterwerte: dict[str, int] = field(default_factory=dict)

    def wert(self, schluessel: str) -> int:
        try:
            return self.werte[schluessel]
        except KeyError:
            raise AutoFehler(f"{self.kuerzel}: Faehigkeit {schluessel} fehlt") from None

    def wetterwert(self, schluessel: str) -> int:
        """Wert einer Wetterfaehigkeit; nicht gesetzte gelten als 0."""
        return self.wetterwerte.get(schluessel, 0)


def pruefe(konfiguration: Konfiguration, auto: Auto) -> None:
    """Prueft, ob ein Auto alle Faehigkeiten innerhalb der Skala hat."""
    erwartet = {f.schluessel for f in konfiguration.faehigkeiten}
    fehlend = erwartet - set(auto.werte)
    if fehlend:
        raise AutoFehler(f"{auto.kuerzel}: Faehigkeiten fehlen: {sorted(fehlend)}")
    unbekannt = set(auto.werte) - erwartet
    if unbekannt:
        raise AutoFehler(f"{auto.kuerzel}: unbekannte Faehigkeiten: {sorted(unbekannt)}")

    bekannt = {
        eintrag["schluessel"] for eintrag in konfiguration.wert("wetter", "faehigkeit", "liste")
    }
    unbekanntes_wetter = set(auto.wetterwerte) - bekannt
    if unbekanntes_wetter:
        raise AutoFehler(
            f"{auto.kuerzel}: unbekannte Wetterfaehigkeiten: {sorted(unbekanntes_wetter)}"
        )

    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")
    for quelle in (auto.werte, auto.wetterwerte):
        for schluessel, wert in quelle.items():
            if not kleinster <= wert <= groesster:
                raise AutoFehler(
                    f"{auto.kuerzel}.{schluessel}: {wert} liegt ausserhalb "
                    f"von {kleinster} bis {groesster}"
                )


def gleichverteilt(konfiguration: Konfiguration, s: int, kuerzel: str = "REF") -> Auto:
    """Erzeugt ein Auto, bei dem jede Faehigkeit denselben Wert hat.

    Dient der Kalibrierung: GDD 9 rechnet mit ``S`` als gewichtetem Mittel
    der Eigenschaften, und bei durchgehend gleichen Werten ist jedes
    gewichtete Mittel genau dieser Wert - unabhaengig von den Gewichten.
    """
    return Auto(
        kuerzel=kuerzel,
        name=f"Referenz S={s}",
        werte={f.schluessel: int(s) for f in konfiguration.faehigkeiten},
        wetterwerte={
            eintrag["schluessel"]: int(s)
            for eintrag in konfiguration.wert("wetter", "faehigkeit", "liste")
        },
    )


def bereichswert(konfiguration: Konfiguration, auto: Auto, bereich: str) -> float:
    """Gewichtetes Mittel der Eigenschaften in einem Wirkungsbereich.

    GDD 8: "Gewicht 0-3, innerhalb eines Bereichs normiert." Faehigkeiten
    ohne Gewicht in diesem Bereich zaehlen nicht mit.

    :param bereich: Kuerzel aus der Wirkungsmatrix, z. B. ``"ek"`` oder ``"g"``
    """
    if bereich not in konfiguration.bereiche:
        raise AutoFehler(f"Unbekannter Wirkungsbereich: {bereich!r}")

    summe = 0.0
    gewichte = 0
    for faehigkeit in konfiguration.faehigkeiten:
        gewicht = faehigkeit.gewicht(bereich)
        if gewicht:
            summe += gewicht * auto.wert(faehigkeit.schluessel)
            gewichte += gewicht

    if gewichte == 0:  # pragma: no cover - von der Konfigurationspruefung ausgeschlossen
        raise AutoFehler(f"Auf {bereich!r} wirkt keine Faehigkeit")
    return summe / gewichte


def bereichswerte(konfiguration: Konfiguration, auto: Auto) -> dict[str, float]:
    """Alle Bereichswerte eines Autos auf einmal."""
    return {
        bereich: bereichswert(konfiguration, auto, bereich)
        for bereich in konfiguration.bereiche
    }


def gesamtwert(konfiguration: Konfiguration, auto: Auto) -> float:
    """Mittelwert ueber alle 32 Faehigkeiten, ungewichtet.

    GDD 4 braucht ihn beim Gleichstand auf die Millisekunde: "vorne liegt,
    wer den hoeheren Durchschnitt der Basiseigenschaften (ohne Zufall) hat".
    """
    werte = [auto.wert(f.schluessel) for f in konfiguration.faehigkeiten]
    return sum(werte) / len(werte)
