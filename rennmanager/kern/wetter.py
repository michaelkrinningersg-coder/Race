"""Wetter je Session (GDD 7).

Fuer jede Session wird eine Wetterlage gewuerfelt, die 0- bis 3-mal
wechselt und dabei immer nur eine Stufe der Kette weitergeht:

    Starkregen - Regen - Wechselhaft - Trocken - Heiss

Jede Lage bringt einen Grip-Faktor, der das Tempo senkt, sowie
Multiplikatoren fuer Fehlerquote und Reifenverschleiss (Schritt 6). Die
Streckennaesse folgt dem Wetter verzoegert: Nach einem Wechsel naehert sich
der Grip ueber drei Runden dem neuen Wert an, statt zu springen.

Bei Wechselhaft schwankt der Grip zusaetzlich je Sektor.

Die passende Wetterfaehigkeit des Fahrers daempft den Gripverlust, bei
Trocken gibt sie stattdessen einen kleinen Tempobonus. Bei Hitze wirkt
zusaetzlich F16 Kuehlung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern.auto import Auto
from rennmanager.kern.tempo import leistungsanteil
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class WetterFehler(Exception):
    """Die Wetterkonfiguration passt nicht zur Anfrage."""


@dataclass(frozen=True)
class Abschnitt:
    """Eine Wetterlage ab einem Zeitpunkt der Session."""

    zustand: str
    ab_ms: int
    # Grip je Sektor; bei Wechselhaft schwanken die Werte, sonst sind sie gleich.
    grip_je_sektor: tuple[float, ...]


@dataclass(frozen=True)
class Wetterverlauf:
    """Das Wetter einer ganzen Session.

    :param uebergang_ms: Zeit, in der sich der Grip nach einem Wechsel dem
        neuen Wert annaehert (Streckennaesse folgt verzoegert, GDD 7)
    """

    abschnitte: tuple[Abschnitt, ...]
    uebergang_ms: int

    @property
    def startzustand(self) -> str:
        return self.abschnitte[0].zustand

    @property
    def wechsel(self) -> int:
        return len(self.abschnitte) - 1

    @property
    def zustaende(self) -> tuple[str, ...]:
        return tuple(abschnitt.zustand for abschnitt in self.abschnitte)

    def abschnitt_zu(self, zeit_ms: float) -> Abschnitt:
        """Die Wetterlage, die zu diesem Zeitpunkt gilt."""
        gueltig = self.abschnitte[0]
        for abschnitt in self.abschnitte:
            if abschnitt.ab_ms <= zeit_ms:
                gueltig = abschnitt
            else:
                break
        return gueltig

    def zustand_zu(self, zeit_ms: float) -> str:
        return self.abschnitt_zu(zeit_ms).zustand

    def vorherrschend(self, dauer_ms: int) -> str:
        """Die Lage, die am laengsten galt (Punkt 23).

        Eine Session wechselt 0- bis 3-mal (GDD 7). Fuer die Wetterbilanz
        braucht es eine Lage je Rennen, nicht den ganzen Verlauf - und die
        richtige ist die, unter der am meisten gefahren wurde, nicht die
        erste und nicht die haeufigste. Ein Rennen, das zwei Runden im
        Regen beginnt und danach trocken bleibt, war ein trockenes.

        Bei Gleichstand gewinnt die fruehere Lage; so haengt das Ergebnis
        nicht an der Reihenfolge eines Woerterbuchs.
        """
        gesamt: dict[str, int] = {}
        for stelle, abschnitt in enumerate(self.abschnitte):
            bis = (
                self.abschnitte[stelle + 1].ab_ms
                if stelle + 1 < len(self.abschnitte)
                else max(dauer_ms, abschnitt.ab_ms)
            )
            gesamt[abschnitt.zustand] = gesamt.get(abschnitt.zustand, 0) + max(
                bis - abschnitt.ab_ms, 0
            )
        reihenfolge = {a.zustand: i for i, a in enumerate(reversed(self.abschnitte))}
        return max(gesamt, key=lambda lage: (gesamt[lage], reihenfolge[lage]))

    def grip_zu(self, zeit_ms: float, sektor: int = 1) -> float:
        """Grip-Faktor zu einem Zeitpunkt, mit verzoegerter Streckennaesse.

        :param sektor: Sektornummer ab 1 (GDD 3: 4 Sektoren)
        """
        aktueller = self.abschnitt_zu(zeit_ms)
        ziel = aktueller.grip_je_sektor[(sektor - 1) % len(aktueller.grip_je_sektor)]
        if aktueller.ab_ms <= 0 or self.uebergang_ms <= 0:
            return ziel

        vorheriger = self.abschnitte[self.abschnitte.index(aktueller) - 1]
        davor = vorheriger.grip_je_sektor[(sektor - 1) % len(vorheriger.grip_je_sektor)]
        anteil = min(max((zeit_ms - aktueller.ab_ms) / self.uebergang_ms, 0.0), 1.0)
        return davor + (ziel - davor) * anteil


# ---------------------------------------------------------------------------
# Wuerfeln
# ---------------------------------------------------------------------------
def _grip_je_sektor(
    konfiguration: Konfiguration, zustand: str, sektoren: int, wuerfel
) -> tuple[float, ...]:
    einstellung = konfiguration.wert("wetter", "zustand", zustand)
    if "grip" in einstellung:
        return (float(einstellung["grip"]),) * sektoren
    # Wechselhaft: Der Grip schwankt je Sektor (GDD 7).
    unten = float(einstellung["grip_min"])
    oben = float(einstellung["grip_max"])
    return tuple(float(unten + (oben - unten) * wuerfel.random()) for _ in range(sektoren))


def profil_von(konfiguration: Konfiguration, streckenname: str) -> str:
    """Das Klimaprofil einer Strecke (Entscheidung zu Punkt 4)."""
    for name, profil in konfiguration.wert("wetter", "profil").items():
        if streckenname in profil["strecken"]:
            return name
    raise WetterFehler(f"Strecke {streckenname!r} hat kein Wetterprofil")


def wuerfle(
    konfiguration: Konfiguration,
    streckenname: str,
    dauer_ms: int,
    rundendauer_ms: int,
    seedquelle: Seedquelle,
    wechselfenster_ms: int | None = None,
    wechsel_max: int | None = None,
) -> Wetterverlauf:
    """Wuerfelt das Wetter einer Session (GDD 7).

    :param dauer_ms: geschaetzte Dauer der Session, ueber die die Wechsel
        verteilt werden
    :param rundendauer_ms: Rundenzeit, aus der sich die Verzoegerung der
        Streckennaesse in Runden ergibt
    :param wechselfenster_ms: Zeitraum ab Sessionbeginn, in dem die Wechsel
        liegen duerfen. Ohne Angabe die ganze Session.
    :param wechsel_max: Obergrenze der Wechsel. Ohne Angabe die aus GDD 7.

    Qualifying und Rennen unterscheiden sich hier: Im Rennen sind alle
    Autos gleichzeitig auf der Strecke und erleben dasselbe Wetter, im
    Qualifying faehrt jedes zu einer anderen Zeit. Deshalb bekommt das
    Qualifying ein engeres Fenster und weniger Wechsel - sonst entschiede
    die Startreihenfolge mehr als die Fahrleistung.
    """
    wuerfel = seedquelle.generator()
    kette = list(konfiguration.wert("wetter", "kette"))
    sektoren = konfiguration.wert("strecke", "sektoren")

    # Startzustand nach dem Klimaprofil der Strecke.
    gewichte = konfiguration.wert("wetter", "profil", profil_von(konfiguration, streckenname))[
        "gewichte"
    ]
    verteilung = np.array([gewichte[zustand] for zustand in kette], dtype=float)
    verteilung /= verteilung.sum()
    stelle = int(wuerfel.choice(len(kette), p=verteilung))

    obergrenze = konfiguration.wert("wetter", "wechsel_max")
    if wechsel_max is not None:
        obergrenze = min(obergrenze, wechsel_max)
    anzahl = int(
        wuerfel.integers(konfiguration.wert("wetter", "wechsel_min"), obergrenze + 1)
    )
    schrittweite = konfiguration.wert("wetter", "wechsel_schrittweite")

    start_grip = _grip_je_sektor(konfiguration, kette[stelle], sektoren, wuerfel)
    abschnitte = [Abschnitt(kette[stelle], 0, start_grip)]
    if anzahl:
        # Zeitpunkte der Wechsel sind zufaellig ueber die Session verteilt.
        fenster = min(wechselfenster_ms or dauer_ms, dauer_ms)
        zeitpunkte = sorted(int(wuerfel.random() * fenster) for _ in range(anzahl))
        for zeitpunkt in zeitpunkte:
            # Ein Wechsel geht immer nur um eine Stufe (GDD 7).
            richtung = schrittweite if wuerfel.random() < 0.5 else -schrittweite
            neu = stelle + richtung
            if not 0 <= neu < len(kette):
                neu = stelle - richtung
            if not 0 <= neu < len(kette):  # pragma: no cover - nur bei Kette der Laenge 1
                continue
            stelle = neu
            abschnitte.append(
                Abschnitt(
                    kette[stelle],
                    zeitpunkt,
                    _grip_je_sektor(konfiguration, kette[stelle], sektoren, wuerfel),
                )
            )

    verzoegerung = konfiguration.wert("wetter", "naesse", "verzoegerung_runden")
    return Wetterverlauf(tuple(abschnitte), uebergang_ms=int(verzoegerung * rundendauer_ms))


# ---------------------------------------------------------------------------
# Wirkung auf ein Auto
# ---------------------------------------------------------------------------
def faehigkeit_zu(konfiguration: Konfiguration, zustand: str) -> str:
    """Schluessel der Wetterfaehigkeit, die bei diesem Wetter zaehlt."""
    for eintrag in konfiguration.wert("wetter", "faehigkeit", "liste"):
        if eintrag["wetter"] == zustand:
            return str(eintrag["schluessel"])
    raise WetterFehler(f"Kein Wetterkoennen fuer {zustand!r} hinterlegt")


def _koennen(konfiguration: Konfiguration, auto: Auto, zustand: str) -> float:
    """Leistungsanteil des Wetterkoennens, 0 bis 1.

    Bei Hitze wirkt zusaetzlich F16 Kuehlung (GDD 7 und 8); beide zaehlen
    dann zu gleichen Teilen.
    """
    referenz = konfiguration.wert("skala", "referenz")
    anteil = leistungsanteil(
        auto.wetterwert(faehigkeit_zu(konfiguration, zustand)), referenz
    )
    if zustand == "heiss":
        kuehlung = leistungsanteil(auto.wert("F16"), referenz)
        anteil = (anteil + kuehlung) / 2.0
    return min(anteil, 1.0)


def grip_fuer(
    konfiguration: Konfiguration, auto: Auto, zustand: str, grip: float
) -> float:
    """Wirksamer Grip-Faktor eines Autos (GDD 7).

    Die passende Wetterfaehigkeit senkt den Gripverlust um bis zu 60 % bei
    100.000. Bei Trocken gibt es keinen Verlust zu daempfen; dort gibt die
    Trockenroutine stattdessen einen kleinen Tempobonus.
    """
    anteil = _koennen(konfiguration, auto, zustand)
    verlust = 1.0 - grip
    if verlust > 0.0:
        max_daempfung = konfiguration.wert("wetter", "faehigkeit", "max_daempfung")
        return 1.0 - verlust * (1.0 - max_daempfung * anteil)

    bonus = konfiguration.wert("wetter", "trockenbonus", "max_anteil")
    return grip + bonus * anteil


def fehlerfaktor(konfiguration: Konfiguration, auto: Auto, zustand: str) -> float:
    """Wirksamer Fehler-Multiplikator (GDD 7); gebraucht ab Schritt 6.

    Die Wetterfaehigkeit senkt auch den Fehlerzuwachs um bis zu 60 %.
    """
    roh = float(konfiguration.wert("wetter", "zustand", zustand)["fehlerquote"])
    zuwachs = roh - 1.0
    if zuwachs <= 0.0:
        return roh
    max_daempfung = konfiguration.wert("wetter", "faehigkeit", "max_daempfung")
    anteil = _koennen(konfiguration, auto, zustand)
    return 1.0 + zuwachs * (1.0 - max_daempfung * anteil)


def verschleissfaktor(konfiguration: Konfiguration, zustand: str) -> float:
    """Reifenverschleiss-Multiplikator des Wetters (GDD 7); ab Schritt 6."""
    return float(konfiguration.wert("wetter", "zustand", zustand)["reifenverschleiss"])
