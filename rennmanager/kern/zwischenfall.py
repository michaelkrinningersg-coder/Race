"""Fehler, Unfaelle und Defekte (GDD 4 und 14).

Drei Arten von Zwischenfaellen, jede mit eigener Haeufigkeit und Wirkung:

* **Fehler** kosten einmalig Zeit. Wie oft sie passieren, kommt aus dem
  Bereich ``fe`` der Wirkungsmatrix, skaliert mit dem Wetter (GDD 7) und
  dem Reifenzustand (GDD 4).
* **Unfaelle** sind sehr selten und nur moeglich, wenn zwei Autos weniger
  als 30 m auseinander sind. Mal scheidet ein Auto aus, mal beide; je
  Rennen wird eine Obergrenze von 0 bis 5 Ausfaellen gewuerfelt.
* **Defekte** sind selten, aber haeufiger als Unfaelle. Sie senken
  Fahrzeugwerte bis zur Reparatur; die 20 moeglichen stehen in GDD 14.

Alle Raten stehen in der Konfiguration; die Entscheidungen dazu sind in
OFFENE_PUNKTE.md begruendet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto, bereichswert
from rennmanager.kern.tempo import leistungsanteil

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


# Eigenschaft neben der Wirkungsmatrix (Punkt 13).
MATERIALGEFUEHL = "materialgefuehl"


class Art:
    """Die drei Arten von Zwischenfaellen."""

    FEHLER = "fehler"
    UNFALL = "unfall"
    DEFEKT = "defekt"


@dataclass(frozen=True)
class Zwischenfall:
    """Ein Ereignis waehrend des Rennens, fuer Anzeige und Statistik."""

    art: str
    zeit_ms: int
    teilnehmer: int
    runde: int
    # Nur bei Fehlern: verlorene Zeit. Nur bei Defekten: Schluessel aus
    # GDD 14. Nur bei Unfaellen: der beteiligte Gegner.
    zeitverlust_ms: int = 0
    defekt: str = ""
    gegner: int | None = None
    ausgefallen: bool = False

    @property
    def beschreibung(self) -> str:
        if self.art == Art.FEHLER:
            return f"Fehler, {self.zeitverlust_ms / 1000:.1f} s verloren"
        if self.art == Art.DEFEKT:
            return f"Defekt {self.defekt}"
        return "Unfall, ausgeschieden" if self.ausgefallen else "Unfall, weitergefahren"


# ---------------------------------------------------------------------------
# Fehler
# ---------------------------------------------------------------------------
def fehlerrate_je_runde(
    konfiguration: Konfiguration,
    auto: Auto,
    wetterfaktor: float = 1.0,
    reifenfaktor: float = 1.0,
) -> float:
    """Wahrscheinlichkeit eines Fehlers je Runde (GDD 4).

    Grundlage ist der Bereich ``fe`` der Wirkungsmatrix - getragen von D1
    Konzentration, D12 Konstanz, D15 Nervenstaerke, F15 Elektronik und F7
    Fahrwerk. Wetter und Reifenzustand skalieren sie.
    """
    einstellung = konfiguration.wert("fehler")
    anteil = min(
        leistungsanteil(
            bereichswert(konfiguration, auto, "fe"), konfiguration.wert("skala", "referenz")
        ),
        1.0,
    )
    grundrate = einstellung["rate_bei_null"] + anteil * (
        einstellung["rate_bei_maximum"] - einstellung["rate_bei_null"]
    )
    return min(grundrate * wetterfaktor * reifenfaktor, 1.0)


def zeitverlust_ms(konfiguration: Konfiguration, wuerfel=None) -> int:
    """Wie lange ein Auto nach einem Fehler steht (GDD 4, Punkt 61).

    Eine **feste** Zeit, keine Spanne - so hat es der Auftraggeber
    entschieden. Sie wird im Rennen nicht als Zeitabzug verrechnet,
    sondern als Stillstand: Das Auto geht auf 0 km/h, steht diese Zeit und
    faehrt danach mit seiner eigenen Beschleunigungskurve wieder an. Was
    ein Fehler wirklich kostet, ist deshalb mehr als diese Zahl.

    :param wuerfel: wird nicht mehr gebraucht; das Feld bleibt, damit
        bestehende Aufrufe unveraendert durchlaufen.
    """
    return int(konfiguration.wert("fehler", "zeitverlust_ms"))


# ---------------------------------------------------------------------------
# Defekte
# ---------------------------------------------------------------------------
def materialgefuehl(konfiguration: Konfiguration, auto: Auto) -> float:
    """Faktor auf die Defektrate aus der Eigenschaft ``materialgefuehl``.

    Die Fahrerseite der Zuverlaessigkeit (Punkt 13): F14 bestimmt, wie oft
    ein Auto kaputtgeht, dieser Wert senkt es zusaetzlich - wer das
    Material spuert, faehrt es nicht kaputt. Die Eigenschaft steht neben
    der Wirkungsmatrix aus GDD 8; fehlt sie, gilt 0 (GDD 1).
    """
    einstellung = konfiguration.wert("materialgefuehl")
    anteil = min(
        leistungsanteil(
            auto.wetterwert(MATERIALGEFUEHL), konfiguration.wert("skala", "referenz")
        ),
        1.0,
    )
    bei_null = einstellung["faktor_bei_null"]
    return bei_null + anteil * (einstellung["faktor_bei_maximum"] - bei_null)


def defektrate_je_runde(konfiguration: Konfiguration, auto: Auto, runden: int) -> float:
    """Wahrscheinlichkeit eines Defekts je Runde (GDD 4).

    Die Entscheidung nennt eine Rate je Auto und Rennen; sie wird hier auf
    die Runden verteilt. Getragen wird sie vom Bereich ``ve``, also vor
    allem von F14 Zuverlaessigkeit - und seit Punkt 13 zusaetzlich vom
    Materialgefuehl des Fahrers.
    """
    einstellung = konfiguration.wert("defekte", "rate")
    anteil = min(
        leistungsanteil(
            bereichswert(konfiguration, auto, "ve"), konfiguration.wert("skala", "referenz")
        ),
        1.0,
    )
    je_rennen = einstellung["je_auto_und_rennen_bei_null"] + anteil * (
        einstellung["je_auto_und_rennen_bei_maximum"]
        - einstellung["je_auto_und_rennen_bei_null"]
    )
    return je_rennen * materialgefuehl(konfiguration, auto) / max(runden, 1)


def waehle_defekt(konfiguration: Konfiguration, wuerfel) -> dict:
    """Zieht einen der 20 Defekte aus GDD 14."""
    liste = konfiguration.wert("defekte", "liste")
    return liste[int(wuerfel.integers(0, len(liste)))]


def tempofaktor_defekte(konfiguration: Konfiguration, defekte: list[dict]) -> float:
    """Wie stark aktive Defekte das Tempo senken.

    GDD 14: "alle aktiven Defekte zusammen senken den Fahrzeugzustand um
    hoechstens 50 %". Die Einzelwirkungen betreffen Fahrzeugwerte; fuer die
    Fahrt wird ihre Summe als Tempoverlust angesetzt.
    """
    verlust = 0.0
    for defekt in defekte:
        verlust += sum(-wirkung["faktor"] for wirkung in defekt["wirkung"])
    grenze = konfiguration.wert("defekte", "max_gesamtmalus")
    return 1.0 - min(verlust, grenze)


def defekt_von(konfiguration: Konfiguration, schluessel: str) -> dict:
    """Ein Defekt aus GDD 14 anhand seines Schluessels."""
    for defekt in konfiguration.wert("defekte", "liste"):
        if defekt["schluessel"] == schluessel:
            return defekt
    raise KeyError(f"Unbekannter Defekt: {schluessel}")


def wertfaktoren(konfiguration: Konfiguration, defekte: list[dict]) -> dict[str, float]:
    """Faktoren je Fahrzeugwert, solange diese Defekte offen sind (GDD 14).

    Anders als ``tempofaktor_defekte``, das die Summe als Tempoverlust
    ansetzt, wirken die Defekte hier auf die einzelnen Werte, die GDD 14
    nennt. Die Deckelung bei 50 % gilt weiterhin fuer die Summe: Reicht
    sie darueber, werden alle Einzelwirkungen im selben Verhaeltnis
    verkleinert.
    """
    verlust = sum(
        -wirkung["faktor"] for defekt in defekte for wirkung in defekt["wirkung"]
    )
    grenze = konfiguration.wert("defekte", "max_gesamtmalus")
    daempfung = min(grenze / verlust, 1.0) if verlust > grenze else 1.0

    faktoren: dict[str, float] = {}
    for defekt in defekte:
        for wirkung in defekt["wirkung"]:
            ziel = wirkung["ziel"]
            faktoren[ziel] = faktoren.get(ziel, 1.0) * (
                1.0 + wirkung["faktor"] * daempfung
            )
    return faktoren


def reparaturkosten(konfiguration: Konfiguration, defekt: dict, liga: int) -> int:
    """Was die Reparatur eines Defekts kostet (GDD 14).

    "Reparatur kostet nur Geld (Stufe x Liga-Faktor) und wirkt sofort."
    Der Liga-Faktor ist die Siegpraemie der Liga; die Entscheidung dazu
    steht in OFFENE_PUNKTE.md, Punkt 18.
    """
    from rennmanager.kern.einnahmen import siegpraemie

    anteil = konfiguration.wert("defekte", "reparatur", "anteil_siegpraemie_je_stufe")
    return int(round(defekt["kostenstufe"] * anteil * siegpraemie(konfiguration, liga)))


# ---------------------------------------------------------------------------
# Unfaelle
# ---------------------------------------------------------------------------
def ausfallgrenze(konfiguration: Konfiguration, wuerfel) -> int:
    """Obergrenze der Ausfaelle in diesem Rennen, 0 bis 5 (GDD 4)."""
    einstellung = konfiguration.wert("unfaelle")
    return int(wuerfel.integers(einstellung["ausfaelle_min"], einstellung["ausfaelle_max"] + 1))


def unfallrate(
    konfiguration: Konfiguration, dauer_s: float, wetterfaktor: float = 1.0
) -> float:
    """Unfallwahrscheinlichkeit fuer eine Zeitspanne in Reichweite.

    GDD 4: "sehr selten und nur bei weniger als 30 m Abstand". Die Rate
    gilt je Sekunde, nicht je Zeitschritt - sonst haengt die Haeufigkeit an
    der Schrittweite der Simulation statt am Spiel. In einem Probelauf mit
    einer Rate je Schritt fielen alle fuenf erlaubten Ausfaelle bereits in
    der ersten Runde.
    """
    je_sekunde = konfiguration.wert("unfaelle", "rate", "je_sekunde_in_reichweite")
    return je_sekunde * dauer_s * wetterfaktor


def beide_betroffen(konfiguration: Konfiguration, wuerfel) -> bool:
    """GDD 4: "mal scheidet ein Auto aus, mal beide"."""
    return bool(wuerfel.random() < konfiguration.wert("unfaelle", "rate", "anteil_beide_autos"))
