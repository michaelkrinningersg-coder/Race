"""Fahrer holen - Vertraege, Gehalt und Abloese (Punkt 7).

Im GDD steht dazu nichts; die Regeln kommen vollstaendig vom
Auftraggeber:

* **Potentiale sind voll sichtbar.** Wer wen holt, ist keine Frage der
  Information, sondern des Geldes und der Ueberzeugung. Dieses Modul
  rechnet deshalb offen mit dem Potential aus ``talent.py``.
* **Transferfenster im Winter.** Verpflichtet wird zwischen den Saisons,
  zusammen mit Ruecktritten und Newgens. Frei ist, wessen Vertrag
  auslaeuft, und jeder Newgen des Jahrgangs.
* **Gehalt plus Abloese.** Ein Gehalt je Saison laeuft aus dem Konto;
  wer noch unter Vertrag steht, kostet zusaetzlich eine einmalige
  Abloese ans abgebende Team.
* **Ein Fahrer kann ablehnen.** Er waegt ab: Ligahoehe, Staerke des
  Autos, das er bekaeme, sein Gehalt gemessen an seinem Marktwert - und
  je bekannter er ist, desto mehr will er.

**Der Haken, der das Ganze interessant macht:** Ein neuer Fahrer bringt
ein leeres, nicht upgegradetes Auto mit (Entscheidung des Auftraggebers,
siehe ``karriere.fahrer_geht``). Wer einen Star holt, setzt ihn also in
ein Auto mit lauter Nullen - und muss ihn dafuer bezahlen. Einen eigenen
Fahrer zu halten und sein Auto ueber Jahre aufzubauen ist die Alternative.

Vertragslaufzeiten haengen wie das Ruecktrittsalter an Seed und
Fahrernummer: Sie stehen damit von Anfang an fest, ueberleben jeden
Spielstand und muessen nicht gespeichert werden (GDD 15). Nur was der
Spieler selbst unterschreibt, wird festgehalten.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rennmanager.kern import talent as kern_talent
from rennmanager.kern.auto import gesamtwert
from rennmanager.kern.welt import Fahrer, Welt
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class TransferFehler(Exception):
    """Dieser Transfer laesst sich so nicht durchfuehren."""


@dataclass(frozen=True)
class Angebot:
    """Was ein Team einem Fahrer bietet."""

    fahrer: int
    gehalt: int
    abloese: int
    laufzeit: int

    @property
    def gesamtkosten(self) -> int:
        """Was der Wechsel ueber die ganze Laufzeit kostet."""
        return self.abloese + self.gehalt * self.laufzeit


@dataclass(frozen=True)
class Antwort:
    """Die Antwort eines Fahrers auf ein Angebot."""

    angenommen: bool
    grund: str
    # Wie deutlich es war: ueber 0 heisst angenommen.
    ueberzeugung: float = 0.0


# ---------------------------------------------------------------------------
# Vertraege
# ---------------------------------------------------------------------------
def vertragsende(
    konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle, jahr: int
) -> int:
    """Das Jahr, nach dem der Vertrag dieses Fahrers auslaeuft.

    Aus dem Seed abgeleitet und rollierend: Jeder Vertrag laeuft zwischen
    ``laufzeit_min`` und ``laufzeit_max`` Saisons, und wenn er ausgelaufen
    ist, folgt der naechste. So ist in jedem Winter ein Teil des Feldes
    frei, ohne dass irgendwo eine Liste gefuehrt wuerde.
    """
    einstellung = konfiguration.wert("transfer")
    start = konfiguration.wert("kalender", "startjahr")
    wuerfel = seedquelle.zweig("vertrag", nummer).generator()
    ende = start
    # Ein paar Zyklen reichen: Laengere Karrieren als 60 Jahre gibt es
    # nicht, und jeder Zyklus deckt mindestens eine Saison ab.
    for _ in range(64):
        ende += int(
            wuerfel.integers(einstellung["laufzeit_min"], einstellung["laufzeit_max"] + 1)
        )
        if ende >= jahr:
            return ende
    return ende  # pragma: no cover - ausserhalb jeder Spieldauer


def ist_frei(
    konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle, jahr: int
) -> bool:
    """Ob dieser Fahrer im Winter vor ``jahr`` ohne Vertrag dasteht."""
    return vertragsende(konfiguration, nummer, seedquelle, jahr) == jahr


def restlaufzeit(
    konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle, jahr: int
) -> int:
    """Wie viele Saisons der Vertrag noch laeuft - 0 heisst frei."""
    return max(vertragsende(konfiguration, nummer, seedquelle, jahr) - jahr, 0)


# ---------------------------------------------------------------------------
# Was ein Fahrer kostet
# ---------------------------------------------------------------------------
def marktwert(
    konfiguration: Konfiguration,
    fahrer: Fahrer,
    talent: kern_talent.Talent,
    alter: int,
) -> int:
    """Das Gehalt je Saison, das dieser Fahrer verlangt.

    Drei Groessen: was er **jetzt** kann, was er **noch werden** kann, und
    wie alt er ist. Ein junges Talent ist billig im Gehalt und teuer in
    der Abloese - genau die Abwaegung, die den Transfermarkt ausmacht.
    """
    einstellung = konfiguration.wert("transfer")
    skala = konfiguration.wert("skala", "maximum")
    jetzt = gesamtwert(konfiguration, fahrer.auto) / skala
    spaeter = talent.gipfelstaerke / skala

    anteil = (
        jetzt * einstellung["gewicht_koennen"]
        + spaeter * einstellung["gewicht_potential"]
    ) / (einstellung["gewicht_koennen"] + einstellung["gewicht_potential"])

    # Junge Fahrer verlangen weniger, auch wenn sie viel koennen: Sie
    # haben noch nichts bewiesen.
    reif = min(max((alter - konfiguration.wert("fahrernamen", "alter_min")) / 10.0, 0.0), 1.0)
    jugendrabatt = 1.0 - einstellung["jugendrabatt"] * (1.0 - reif)

    voll = einstellung["grundgehalt"] * (1.0 + anteil * einstellung["gehaltsspanne"])
    return int(round(voll * jugendrabatt))


def abloese(konfiguration: Konfiguration, gehalt: int, restlaufzeit: int) -> int:
    """Was das abgebende Team fuer einen laufenden Vertrag verlangt.

    Null, wenn der Vertrag auslaeuft - dann ist der Fahrer frei. Sonst
    ein Vielfaches des Jahresgehalts je verbleibender Saison.
    """
    if restlaufzeit <= 0:
        return 0
    je_saison = konfiguration.wert("transfer", "abloese_je_saison")
    return int(round(gehalt * je_saison * restlaufzeit))


def angebot(
    konfiguration: Konfiguration,
    welt: Welt,
    nummer: int,
    jahr: int,
    seedquelle: Seedquelle,
    gehalt: int | None = None,
    laufzeit: int | None = None,
) -> Angebot:
    """Das Angebot, das ein Fahrer erwartet - Grundlage zum Verhandeln.

    :param gehalt: ein eigenes Gebot. Ohne Angabe genau sein Marktwert.
    """
    fahrer = welt.fahrer[nummer]
    stichtag_alter = _alter(konfiguration, fahrer, jahr)
    talent = kern_talent.talent(konfiguration, nummer, seedquelle)
    verlangt = marktwert(konfiguration, fahrer, talent, stichtag_alter)
    geboten = verlangt if gehalt is None else int(gehalt)
    rest = restlaufzeit(konfiguration, nummer, seedquelle, jahr)
    return Angebot(
        fahrer=nummer,
        gehalt=geboten,
        abloese=abloese(konfiguration, verlangt, rest),
        laufzeit=laufzeit
        if laufzeit is not None
        else konfiguration.wert("transfer", "laufzeit_min"),
    )


# ---------------------------------------------------------------------------
# Ob er will
# ---------------------------------------------------------------------------
def pruefe(
    konfiguration: Konfiguration,
    welt: Welt,
    nummer: int,
    angebot: Angebot,
    ziel_liga: int,
    ziel_auto_wert: float,
    jahr: int,
    seedquelle: Seedquelle,
    bekanntheit: float = 0.0,
) -> Antwort:
    """Ob dieser Fahrer das Angebot annimmt.

    Er waegt drei Dinge gegeneinander:

    * **Liga** - eine Liga hoeher ist ein Aufstieg, eine tiefer ein
      Rueckschritt. Gemessen an der Zahl der Ligen, damit ein Sprung von
      Liga 3 nach 2 so viel zaehlt wie einer von 19 nach 18.
    * **Auto** - was er bekaeme, gegen das, was er faehrt. Ein neuer
      Fahrer bringt ein leeres Auto mit, deshalb ist das beim Spieler
      fast immer ein Minus - Geld muss es ausgleichen.
    * **Geld** - das Gebot gegen seinen Marktwert.

    Je bekannter er ist, desto mehr muss zusammenkommen (Punkt 5).

    :param ziel_auto_wert: Gesamtwert des Autos, das er faehrt, wenn er
        unterschreibt
    :param bekanntheit: sein Popularitaetsanteil, 0 bis 1
    """
    einstellung = konfiguration.wert("transfer")
    fahrer = welt.fahrer[nummer]
    skala = konfiguration.wert("skala", "maximum")
    ligen = konfiguration.wert("ligen", "anzahl")

    ligavorteil = (fahrer.liga - ziel_liga) / ligen
    autovorteil = (ziel_auto_wert - gesamtwert(konfiguration, fahrer.auto)) / skala

    talent = kern_talent.talent(konfiguration, nummer, seedquelle)
    verlangt = marktwert(
        konfiguration, fahrer, talent, _alter(konfiguration, fahrer, jahr)
    )
    geldvorteil = (angebot.gehalt - verlangt) / max(verlangt, 1)

    ueberzeugung = (
        ligavorteil * einstellung["gewicht_liga"]
        + autovorteil * einstellung["gewicht_auto"]
        + geldvorteil * einstellung["gewicht_geld"]
    )
    schwelle = einstellung["schwelle"] * (
        1.0 + einstellung["anspruch_bekanntheit"] * max(bekanntheit, 0.0)
    )

    if ueberzeugung >= schwelle:
        return Antwort(True, "Er unterschreibt.", ueberzeugung - schwelle)
    return Antwort(
        False, _grund(ligavorteil, autovorteil, geldvorteil), ueberzeugung - schwelle
    )


def _grund(ligavorteil: float, autovorteil: float, geldvorteil: float) -> str:
    """Woran es lag - der schwaechste der drei Punkte."""
    if ligavorteil < 0:
        return "Er will nicht in eine tiefere Liga."
    if autovorteil < 0 and geldvorteil <= 0:
        return "Das Auto ist schwaecher als seins, und das Geld gleicht es nicht aus."
    if geldvorteil <= 0:
        return "Das Gehalt liegt unter seinem Marktwert."
    return "Das Angebot reicht ihm nicht."


# ---------------------------------------------------------------------------
# Wer im Winter zu haben ist
# ---------------------------------------------------------------------------
def verfuegbare(
    konfiguration: Konfiguration,
    welt: Welt,
    jahr: int,
    seedquelle: Seedquelle,
    newgens: tuple[int, ...] = (),
) -> tuple[int, ...]:
    """Wer in diesem Transferfenster zu haben ist.

    Frei sind alle, deren Vertrag mit dieser Saison auslaeuft, und jeder
    Newgen des Jahrgangs - der hat noch nirgends unterschrieben. Die
    eigenen Fahrer stehen nicht darin: Man verpflichtet nicht, wen man
    schon hat.

    Wer noch unter Vertrag steht, ist damit nicht unerreichbar - er
    kostet nur eine Abloese (siehe ``angebot``).
    """
    eigene = {f.nummer for f in welt.spielerfahrer}
    frei = {
        f.nummer
        for f in welt.fahrer
        if f.nummer not in eigene
        and ist_frei(konfiguration, f.nummer, seedquelle, jahr)
    }
    frei.update(nummer for nummer in newgens if nummer not in eigene)
    return tuple(sorted(frei))


def _alter(konfiguration: Konfiguration, fahrer: Fahrer, jahr: int) -> int:
    from rennmanager.kern import kalender as kern_kalender

    return fahrer.alter_am(kern_kalender.saisonstart(konfiguration, jahr))
