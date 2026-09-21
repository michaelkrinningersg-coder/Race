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

import bisect
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


# Punkt 96: Die normierten Stuetzstellen der Standzeit, je Konfiguration
# einmal gebildet. Der Skalierungsfaktor kostet eine Summe ueber die
# ganze Tabelle; gezogen wird in jedem Rennen einige hundert Mal.
_ZEITVERLUST: dict[int, tuple[tuple[float, ...], tuple[float, ...]]] = {}


def zeitverlustverteilung(
    konfiguration: Konfiguration,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Die Verteilung der Standzeit als (Anteile, Millisekunden).

    Die Tabelle in der Konfiguration beschreibt die Form - je
    Stuetzstelle den Anteil der Fehler darunter und die Sekunden dazu.
    Hier wird sie auf ``mittelwert_ms`` normiert: Der Erwartungswert der
    stueckweise linearen Umkehrfunktion wird ausgerechnet und die ganze
    Tabelle so gestaucht oder gestreckt, dass er passt.

    Das haelt die Streuung vom Balancing fern. Wer die Form aendert,
    aendert, **wie** sich die verlorene Zeit auf die Fehler verteilt -
    nicht, wie viel davon insgesamt anfaellt.
    """
    gemerkt = _ZEITVERLUST.get(id(konfiguration))
    if gemerkt is not None:
        return gemerkt

    einstellung = konfiguration.wert("fehler", "zeitverlust")
    anteile = tuple(float(a) for a in einstellung["anteil"])
    sekunden = tuple(float(s) for s in einstellung["sekunden"])
    if len(anteile) != len(sekunden):
        raise ValueError(
            f"Die Verteilung hat {len(anteile)} Anteile, aber "
            f"{len(sekunden)} Zeiten"
        )
    if len(anteile) < 2:
        raise ValueError("Die Verteilung braucht mindestens zwei Stuetzstellen")
    if list(anteile) != sorted(anteile) or anteile[0] != 0.0 or anteile[-1] != 1.0:
        raise ValueError("Die Anteile muessen von 0.0 bis 1.0 aufsteigen")

    # Erwartungswert der stueckweise linearen Umkehrfunktion: je Abschnitt
    # seine Breite im Anteil mal der mittleren Zeit darin.
    roh = sum(
        (anteile[i + 1] - anteile[i]) * (sekunden[i] + sekunden[i + 1]) / 2.0
        for i in range(len(anteile) - 1)
    )
    if roh <= 0.0:
        raise ValueError("Die Verteilung muss eine Zeit groesser null ergeben")
    faktor = float(einstellung["mittelwert_ms"]) / (roh * 1000.0)

    gemerkt = (anteile, tuple(s * 1000.0 * faktor for s in sekunden))
    _ZEITVERLUST[id(konfiguration)] = gemerkt
    return gemerkt


def zeitverlust_bei(konfiguration: Konfiguration, anteil: float) -> int:
    """Die Standzeit an einer Stelle der Verteilung, in Millisekunden.

    ``anteil`` ist der Anteil der Fehler, die kuerzer ausfallen: 0.0 ist
    die kuerzeste moegliche Standzeit, 0.5 der Gipfel, 1.0 die laengste.
    """
    anteile, werte = zeitverlustverteilung(konfiguration)
    stelle = bisect.bisect_right(anteile, anteil)
    if stelle <= 0:
        return int(round(werte[0]))
    if stelle >= len(anteile):
        return int(round(werte[-1]))
    links, rechts = anteile[stelle - 1], anteile[stelle]
    if rechts <= links:  # pragma: no cover - zwei gleiche Anteile
        return int(round(werte[stelle]))
    weg = (anteil - links) / (rechts - links)
    return int(round(werte[stelle - 1] + weg * (werte[stelle] - werte[stelle - 1])))


def zeitverlust_ms(konfiguration: Konfiguration, wuerfel=None) -> int:
    """Wie lange ein Auto nach einem Fehler steht (GDD 4, Punkte 61 und 96).

    Gezogen aus der Verteilung in ``[fehler.zeitverlust]``: Die meisten
    Fehler kosten rund eine Sekunde, ein paar wenige das Vierfache. Im
    Rennen wird das nicht als Zeitabzug verrechnet, sondern als
    Stillstand - das Auto geht auf 0 km/h, steht diese Zeit und faehrt
    danach mit seiner eigenen Beschleunigungskurve wieder an. Was ein
    Fehler wirklich kostet, ist deshalb mehr als diese Zahl.

    :param wuerfel: der Zufallsstrom des Rennens. Ohne ihn kommt der
        Erwartungswert zurueck - fuer Rechnungen, die ohne Zufall
        auskommen sollen (GDD 9).
    """
    if wuerfel is None:
        return int(round(konfiguration.wert("fehler", "zeitverlust")["mittelwert_ms"]))
    return zeitverlust_bei(konfiguration, float(wuerfel.random()))


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
