"""Was ein Fahrer werden kann - Potential, Tempo und Alterskurve (Punkt 35).

Bis hierher fuhren alle 600 Fahrer **dieselbe** Alterskurve: Aufbau bis
28, Plateau bis 33, danach Abbau. Innerhalb einer Liga entschied damit
allein das Alter, wer vorne stand, und die Ligen wurden ueber die Saisons
zu Altersklassen statt zu Leistungsklassen. Gemessen ueber dreissig
Jahre: Liga 1 bestand nur noch aus 38- bis 43-Jaehrigen.

Dieses Modul gibt jedem Fahrer stattdessen ein eigenes **Talent**:

* ein **Potential je Eigenschaft** - alle 32 Werte der Wirkungsmatrix und
  alle Zusatzfaehigkeiten daneben, jede fuer sich,
* ein **Entwicklungstempo**,
* ein **Gipfelalter** und ein **Abbaualter**.

Nichts davon wird gespeichert. Alles haengt an Seed und Fahrernummer und
steht damit von Anfang an fest - derselbe Seed ergibt dieselbe Welt, und
kein Spielstand muss eine Zeile mehr tragen (GDD 15).

**Das Potential steht auf der absoluten Skala, nicht relativ zur Liga.**
Die Ligaleiter aus GDD 9 ist extrem: Liga 1 reicht bis 98130, der Letzte
in Liga 20 hat 6. Ein Potential als Prozentaufschlag auf das
Einstiegsniveau koennte niemanden je nach oben bringen - ein Newgen in
Liga 20 waere fuer immer ein Liga-20-Fahrer. Gezogen wird deshalb aus der
**Staerkeleiter der ganzen Welt**: Jeder Newgen wuerfelt einen Rang unter
allen 600 Plaetzen. Damit bleibt die Zusammensetzung des Feldes ueber die
Generationen dieselbe, ohne dass irgendetwas normiert werden muss.

**Gewachsen wird als Lueckenschluss.** Jedes Jahr holt ein Wert einen
Anteil des Abstands zu seinem Ziel auf. Das traegt von 6 nach 98130
genauso wie von 50000 nach 60000 - ein fester Prozentsatz je Jahr taete
das nicht. Dasselbe Verfahren macht auch den Abbau: Ab dem Abbaualter
sinkt das **Ziel**, und die Luecke schliesst sich nach unten. Ein
Mechanismus fuer beides.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from rennmanager.kern import welt as kern_welt
from rennmanager.kern.auto import Auto
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


@dataclass(frozen=True)
class Talent:
    """Das Talent eines Fahrers - abgeleitet, nicht gespeichert."""

    nummer: int
    # Je Eigenschaft der Wert, den dieser Fahrer hoechstens erreicht.
    potential: dict[str, int]
    wetterpotential: dict[str, int]
    # Anteil des Abstands, den ein Jahr aufholt (schon mit dem Tempo
    # dieses Fahrers und seinem Gipfelalter verrechnet).
    schrittmass: float
    gipfelalter: int
    abbaualter: int

    @property
    def gipfelstaerke(self) -> float:
        """Der Gesamtwert, den dieser Fahrer auf seinem Gipfel haette."""
        return sum(self.potential.values()) / len(self.potential)


# ---------------------------------------------------------------------------
# Die Staerkeleiter der Welt
# ---------------------------------------------------------------------------
# Die Leiter haengt nur an der Konfiguration und wird bei jedem Winter
# fuer jeden Fahrer gebraucht. Die Konfiguration traegt ein dict und ist
# deshalb nicht hashbar, ``lru_cache`` scheidet aus; gemerkt wird sie
# darum am Objekt selbst.
_LEITERN: dict[int, tuple[float, ...]] = {}


def _leiter(konfiguration: Konfiguration) -> tuple[float, ...]:
    """Alle Ligastaerken aus GDD 9 als eine Leiter, absteigend.

    600 Werte von 98130 (Bester in Liga 1) bis 6 (Letzter in Liga 20).
    Aus ihr wuerfelt ein Newgen sein Potential.
    """
    gemerkt = _LEITERN.get(id(konfiguration))
    if gemerkt is not None:
        return gemerkt
    ligen = konfiguration.wert("ligen", "anzahl")
    je_liga = konfiguration.wert("ligen", "autos_je_liga")
    werte: list[float] = []
    for liga in range(1, ligen + 1):
        werte.extend(kern_welt.ligastaerken(konfiguration, liga, je_liga))
    leiter = tuple(sorted(werte, reverse=True))
    _LEITERN[id(konfiguration)] = leiter
    return leiter


def gipfelstaerke(konfiguration: Konfiguration, wuerfel) -> float:
    """Zieht eine erreichbare Gesamtstaerke aus der Leiter der Welt.

    Gleichverteilt ueber die **Raenge**, nicht ueber die Werte: So hat
    jeder Jahrgang dieselbe Zusammensetzung wie das Feld, aus dem er
    nachrueckt. Ohne das liefe die Welt ueber die Generationen entweder
    nach oben oder nach unten davon.
    """
    leiter = _leiter(konfiguration)
    return leiter[int(wuerfel.integers(0, len(leiter)))]


# ---------------------------------------------------------------------------
# Das Talent eines Fahrers
# ---------------------------------------------------------------------------
def talent(konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle) -> Talent:
    """Das Talent dieses Fahrers, aus Seed und Fahrernummer.

    Der Zweig heisst nach seiner Sache, nicht nach der Aufrufreihenfolge -
    dasselbe Talent kommt heraus, egal wann danach gefragt wird.
    """
    einstellung = konfiguration.wert("talent")
    wuerfel = seedquelle.zweig("talent", nummer).generator()

    gipfel = gipfelstaerke(konfiguration, wuerfel)
    potential, wetterpotential = kern_welt.wuerfle_werte(
        konfiguration, int(round(gipfel)), wuerfel, list(konfiguration.zusatzfaehigkeiten)
    )

    gipfelalter = int(
        wuerfel.integers(einstellung["gipfel_min"], einstellung["gipfel_max"] + 1)
    )
    # Das Abbaualter kann nicht vor dem Gipfel liegen. Beide Baender
    # ueberschneiden sich (23-33 und 28-38), deshalb wird hier geschoben
    # statt neu gewuerfelt - ein zweiter Wurf haenge sonst am ersten und
    # der Seed ergaebe nicht mehr dieselbe Welt.
    abbaualter = max(
        int(wuerfel.integers(einstellung["abbau_min"], einstellung["abbau_max"] + 1)),
        gipfelalter + 1,
    )
    tempo = float(wuerfel.uniform(einstellung["tempo_min"], einstellung["tempo_max"]))

    return Talent(
        nummer=nummer,
        potential=potential,
        wetterpotential=wetterpotential,
        schrittmass=_schrittmass(konfiguration, gipfelalter, tempo),
        gipfelalter=gipfelalter,
        abbaualter=abbaualter,
    )


def _schrittmass(konfiguration: Konfiguration, gipfelalter: int, tempo: float) -> float:
    """Welchen Anteil des Abstands ein Jahr aufholt.

    Abgeleitet statt frei gewaehlt: Wer mit 23 seinen Gipfel hat, muss in
    fuenf Jahren dorthin, wer ihn mit 33 hat, hat fuenfzehn Zeit. Das
    Tempo des Fahrers kommt obendrauf. So braucht es keine eigene
    Wachstumskonstante, und Gipfelalter und Tempo tun beide echte Arbeit.
    """
    einstieg = konfiguration.wert("fahrernamen", "alter_min")
    reife = konfiguration.wert("talent", "reife_am_gipfel")
    jahre = max(gipfelalter - einstieg, 1)
    grund = 1.0 - (1.0 - reife) ** (1.0 / jahre)
    return min(grund * tempo, 0.95)


# ---------------------------------------------------------------------------
# Die Alterskurve - nur noch fuer den Abbau
# ---------------------------------------------------------------------------
def zielfaktor(
    konfiguration: Konfiguration, talent: Talent, alter: int, ruecktrittsalter: int
) -> float:
    """Wie viel seines Potentials ein Fahrer in diesem Alter noch anstrebt.

    Bis zum Abbaualter das ganze; danach sinkt es bis zum persoenlichen
    Ruecktrittsalter auf ``faktor_bei_ruecktritt``. Der Lueckenschluss
    zieht die Werte dann von allein nach unten - derselbe Mechanismus wie
    beim Wachsen.
    """
    if alter <= talent.abbaualter:
        return 1.0
    zuletzt = konfiguration.wert("generationen", "faktor_bei_ruecktritt")
    ende = max(ruecktrittsalter, talent.abbaualter + 1)
    anteil = min((alter - talent.abbaualter) / (ende - talent.abbaualter), 1.0)
    return 1.0 + (zuletzt - 1.0) * anteil


def gewachsen(
    konfiguration: Konfiguration,
    auto: Auto,
    talent: Talent,
    alter: int,
    ruecktrittsalter: int,
) -> Auto:
    """Ein Jahr Entwicklung: jeder Wert holt seinen Abstand zum Ziel auf.

    Das Ziel ist das Potential, ab dem Abbaualter nach unten gedaempft.
    Liegt ein Wert schon darueber - beim Abbau oder wenn ein Spieler ihn
    hochtrainiert hat -, schliesst sich die Luecke nach unten. Ein
    Mechanismus fuer Aufbau und Abbau.
    """
    faktor = zielfaktor(konfiguration, talent, alter, ruecktrittsalter)
    anteil = talent.schrittmass
    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")

    def geschritten(wert: int, ziel: float) -> int:
        neu = wert + (ziel * faktor - wert) * anteil
        return int(min(max(round(neu), kleinster), groesster))

    return replace(
        auto,
        werte={
            s: geschritten(w, talent.potential.get(s, w)) for s, w in auto.werte.items()
        },
        wetterwerte={
            s: geschritten(w, talent.wetterpotential.get(s, w))
            for s, w in auto.wetterwerte.items()
        },
    )
