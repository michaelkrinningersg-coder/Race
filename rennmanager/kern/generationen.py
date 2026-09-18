"""Ruecktritt, Newgens und die Entwicklung der KI (Punkt 35).

Bis hierher waren die 600 Fahrer aus GDD 12 unveraenderlich: dieselben
Namen, dieselben Werte, dasselbe Alter, Saison fuer Saison. Dieses Modul
macht aus ihnen Generationen.

Vier Regeln, alle vom Auftraggeber entschieden:

* **Ruecktritt** zwischen 34 und 42, je Fahrer einmal gestreut.
* **Ein Newgen je Ruecktritt.** Newgens steigen ganz unten ein, in
  Liga 20; die vorhandenen Fahrer fuellen nach oben auf.
* **Die Ligen duerfen nicht auseinanderlaufen.** Die Ligastaerke bleibt
  der Korridor aus GDD 9; gewachsen wird *innerhalb* einer Liga.
* **Der Spieler altert nicht** und tritt nicht zurueck (GDD 1).

Das Ruecktrittsalter wird nicht gespeichert, sondern aus Seed und
Fahrernummer abgeleitet. Es steht damit von Anfang an fest, ueberlebt
jeden Spielstand und macht denselben Seed zur selben Welt (GDD 15).

**Die Welle im ersten Winter.** Die Startwelt wuerfelt Alter von 18 bis
42 (GDD 12). Mit einer Grenze zwischen 34 und 42 waeren im ersten Winter
gemessen 152 Fahrer ueber ihrer Grenze - ein Viertel des Feldes auf
einmal. Eine Obergrenze je Saison verteilt das auf mehrere Jahre; wer
nicht drankommt, tritt im naechsten Winter zurueck. Im Dauerbetrieb liegt
die Zahl ohnehin darunter.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import welt as kern_welt
from rennmanager.kern.auto import Auto, gesamtwert
from rennmanager.kern.welt import Fahrer, Welt
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class GenerationenFehler(Exception):
    """Der Generationswechsel laesst sich so nicht vollziehen."""


@dataclass(frozen=True)
class Winterbericht:
    """Was ein Generationswechsel bewegt hat - fuer Anzeige und Messung."""

    jahr: int
    zurueckgetreten: tuple[int, ...]
    newgens: tuple[int, ...]
    # Wer aufgerueckt ist, weil vor ihm ein Platz frei wurde.
    nachgerueckt: tuple[tuple[int, int, int], ...] = ()
    # Wie viele ueber ihrer Grenze waren, aber wegen der Obergrenze warten.
    aufgeschoben: int = 0

    @property
    def wechsel(self) -> int:
        return len(self.zurueckgetreten)


# ---------------------------------------------------------------------------
# Ruecktritt
# ---------------------------------------------------------------------------
def ruecktrittsalter(
    konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle
) -> int:
    """Das Alter, mit dem dieser Fahrer aufhoert.

    Aus dem Seed abgeleitet statt gespeichert: So steht es von Anfang an
    fest, ueberlebt jeden Spielstand und macht denselben Seed zur selben
    Welt (GDD 15).
    """
    kleinstes = konfiguration.wert("generationen", "ruecktritt_min")
    groesstes = konfiguration.wert("generationen", "ruecktritt_max")
    wuerfel = seedquelle.zweig("ruecktritt", nummer).generator()
    return int(wuerfel.integers(kleinstes, groesstes + 1))


def faellige(
    konfiguration: Konfiguration, welt: Welt, jahr: int, seedquelle: Seedquelle
) -> tuple[Fahrer, ...]:
    """Alle, die zum Stichtag des Jahres ueber ihrer Grenze sind.

    Der Spieler ist nie dabei: Sein Alter steht fest und seine Karriere
    endet nicht (GDD 1).
    """
    stichtag = kern_kalender.saisonstart(konfiguration, jahr)
    return tuple(
        fahrer
        for fahrer in welt.fahrer
        if not fahrer.ist_spieler
        and fahrer.alter_am(stichtag)
        >= ruecktrittsalter(konfiguration, fahrer.nummer, seedquelle)
    )


def ruecktritte(
    konfiguration: Konfiguration, welt: Welt, jahr: int, seedquelle: Seedquelle
) -> tuple[tuple[Fahrer, ...], int]:
    """Wer diesen Winter aufhoert - hoechstens so viele wie erlaubt.

    Zuerst die Aeltesten: Wer am weitesten ueber seiner Grenze ist, geht
    zuerst. Bei gleichem Abstand entscheidet die Fahrernummer, damit
    derselbe Seed dieselbe Welt ergibt.

    :return: die Zurueckgetretenen und die Zahl derer, die warten muessen
    """
    stichtag = kern_kalender.saisonstart(konfiguration, jahr)
    dran = faellige(konfiguration, welt, jahr, seedquelle)
    geordnet = sorted(
        dran,
        key=lambda f: (
            -(
                f.alter_am(stichtag)
                - ruecktrittsalter(konfiguration, f.nummer, seedquelle)
            ),
            -f.alter_am(stichtag),
            f.nummer,
        ),
    )
    hoechstens = konfiguration.wert("generationen", "ruecktritte_je_saison_max")
    return tuple(geordnet[:hoechstens]), max(len(geordnet) - hoechstens, 0)


# ---------------------------------------------------------------------------
# Die Alterskurve
# ---------------------------------------------------------------------------
def formfaktor(konfiguration: Konfiguration, alter: int) -> float:
    """Wo ein Fahrer in seiner Laufbahn steht, als Faktor um 1,0.

    Aufbau bis zum Gipfel, dann ein Plateau, dann der Abbau. Der Wert ist
    nicht absolut gemeint - gerechnet wird der **Schritt** von einem Jahr
    zum naechsten (siehe ``jahresschritt``), und die Liga wird danach auf
    ihre Staerke aus GDD 9 zurueckgeholt.
    """
    einstieg = konfiguration.wert("fahrernamen", "alter_min")
    gipfel = konfiguration.wert("generationen", "gipfel_alter")
    abbau = konfiguration.wert("generationen", "abbau_ab_alter")
    ende = konfiguration.wert("generationen", "ruecktritt_max")
    unten = konfiguration.wert("generationen", "faktor_bei_einstieg")
    zuletzt = konfiguration.wert("generationen", "faktor_bei_ruecktritt")

    if alter <= einstieg:
        return unten
    if alter < gipfel:
        anteil = (alter - einstieg) / (gipfel - einstieg)
        return unten + (1.0 - unten) * anteil
    if alter <= abbau:
        return 1.0
    if alter >= ende:
        return zuletzt
    anteil = (alter - abbau) / (ende - abbau)
    return 1.0 + (zuletzt - 1.0) * anteil


def jahresschritt(konfiguration: Konfiguration, alter: int) -> float:
    """Wie sich die Werte eines Fahrers in einem Jahr aendern.

    Der Quotient zweier Punkte der Kurve, nicht die Kurve selbst: Sonst
    muesste jeder Fahrer seinen Grundwert mitfuehren und haette zwei
    Wahrheiten - den gespeicherten und den gefahrenen.
    """
    vorher = formfaktor(konfiguration, alter)
    if vorher <= 0:  # pragma: no cover - die Kurve wird nie null
        return 1.0
    return formfaktor(konfiguration, alter + 1) / vorher


# ---------------------------------------------------------------------------
# Newgens
# ---------------------------------------------------------------------------
def newgen(
    konfiguration: Konfiguration,
    nummer: int,
    team: int,
    liga: int,
    staerke: int,
    jahr: int,
    seedquelle: Seedquelle,
    vergebene_namen: set[tuple[str, str]],
    vergebene_kuerzel: set[str],
) -> Fahrer:
    """Ein neuer Fahrer fuer die unterste Liga.

    Gebaut wie die 600 aus GDD 12, nur jung: Name, Land und Werte kommen
    aus denselben Listen und derselben Streuung.
    """
    namen = kern_welt.lade_namen(konfiguration)
    vornamen = namen["fahrer"]["vornamen"]
    nachnamen = namen["fahrer"]["nachnamen"]
    gruppen = namen["fahrer"]["laender"]
    europa = gruppen["europa"]
    nordamerika = gruppen["nordamerika"]
    anteil_na = konfiguration.wert("fahrernamen", "anteil_nordamerika")

    wuerfel = seedquelle.zweig("newgen", nummer).generator()
    for _ in range(1000):
        paar = (
            vornamen[int(wuerfel.integers(0, len(vornamen)))],
            nachnamen[int(wuerfel.integers(0, len(nachnamen)))],
        )
        if paar not in vergebene_namen:
            break
    else:  # pragma: no cover - bei 600 Fahrern und langen Listen unnoetig
        raise GenerationenFehler("Keine freien Namen mehr fuer einen Newgen")
    vergebene_namen.add(paar)

    land = (
        nordamerika[int(wuerfel.integers(0, len(nordamerika)))]
        if wuerfel.random() < anteil_na
        else europa[int(wuerfel.integers(0, len(europa)))]
    )
    alter = int(
        wuerfel.integers(
            konfiguration.wert("generationen", "newgen_alter_min"),
            konfiguration.wert("generationen", "newgen_alter_max") + 1,
        )
    )
    stichtag = kern_kalender.saisonstart(konfiguration, jahr)
    geburtstag = stichtag.replace(year=stichtag.year - alter) - dt.timedelta(
        days=int(wuerfel.integers(0, 365))
    )

    zusatz = list(konfiguration.zusatzfaehigkeiten)
    werte, wetterwerte = kern_welt.wuerfle_werte(
        konfiguration, staerke, wuerfel, zusatz
    )
    return Fahrer(
        nummer=nummer,
        vorname=paar[0],
        nachname=paar[1],
        land=land,
        geburtstag=geburtstag,
        team=team,
        liga=liga,
        auto=Auto(
            kuerzel=kern_welt.kuerzel_fuer(paar[1], vergebene_kuerzel),
            name=f"{paar[0]} {paar[1]}",
            werte=werte,
            wetterwerte=wetterwerte,
        ),
    )


# ---------------------------------------------------------------------------
# Entwicklung mit Normierung
# ---------------------------------------------------------------------------
def entwickelt(
    konfiguration: Konfiguration, welt: Welt, jahr: int
) -> Welt:
    """Altert alle KI-Fahrer und holt jede Liga auf ihre Staerke zurueck.

    Zwei Schritte. Erst bekommt jeder Fahrer seinen Jahresschritt aus der
    Alterskurve - der Junge wird besser, der Alte schlechter. Danach wird
    die Liga auf den Korridor aus GDD 9 **normiert**: Die Staerken der
    Liga sind dieselben wie vorher, nur verteilt sie die Rangfolge neu.

    Ohne den zweiten Schritt liefen die Ligen auseinander, und die
    Kalibrierung aus GDD 9 waere nach ein paar Jahren nichts mehr wert.
    """
    stichtag = kern_kalender.saisonstart(konfiguration, jahr)
    je_liga = konfiguration.wert("ligen", "autos_je_liga")
    neu: dict[int, Fahrer] = {}

    for liga in sorted({f.liga for f in welt.fahrer}):
        feld = [f for f in welt.fahrer if f.liga == liga]
        # Vorlaeufige Staerke nach dem Jahresschritt. Der Spieler bleibt
        # aussen vor: Er entwickelt sich ueber GDD 1 und 2, nicht ueber
        # die Alterskurve.
        vorlaeufig = {}
        for fahrer in feld:
            wert = gesamtwert(konfiguration, fahrer.auto)
            schritt = (
                1.0
                if fahrer.ist_spieler
                else jahresschritt(konfiguration, fahrer.alter_am(stichtag))
            )
            vorlaeufig[fahrer.nummer] = wert * schritt

        ziele = kern_welt.ligastaerken(konfiguration, liga, je_liga)
        geordnet = sorted(feld, key=lambda f: (-vorlaeufig[f.nummer], f.nummer))
        for platz, fahrer in enumerate(geordnet):
            if fahrer.ist_spieler:
                neu[fahrer.nummer] = fahrer
                continue
            ziel = ziele[platz] if platz < len(ziele) else ziele[-1]
            neu[fahrer.nummer] = replace(
                fahrer, auto=_auf_ziel(konfiguration, fahrer.auto, ziel)
            )

    return Welt(
        teams=welt.teams,
        fahrer=tuple(neu[f.nummer] for f in welt.fahrer),
        seed=welt.seed,
    )


def _auf_ziel(konfiguration: Konfiguration, auto: Auto, ziel: float) -> Auto:
    """Hebt oder senkt ein Auto auf einen Zielmittelwert.

    Derselbe Faktor auf alles: Das Profil des Fahrers - worin er stark und
    worin er schwach ist - bleibt, nur sein Niveau wandert.

    Das Kappen an der Skala wird ausgeglichen, sonst kaeme der Beste einer
    Liga nie auf sein Soll: Gemessen hat er 28 seiner 32 Werte dicht unter
    der Decke, und ihn um 5 % anzuheben brachte ohne Ausgleich nur 0,6 %.
    Ueber dreissig Saisons sank Liga 1 dadurch 2,7 % unter ihren Wert aus
    GDD 9.
    """
    jetzt = gesamtwert(konfiguration, auto)
    faktor = (ziel / jetzt) if jetzt > 0 else 1.0
    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")
    return replace(
        auto,
        werte=kern_welt.auf_skala(
            konfiguration, {s: w * faktor for s, w in auto.werte.items()}, ziel
        ),
        # Die Eigenschaften neben der Matrix zaehlen nicht zum
        # Gesamtwert (GDD 4) - sie wandern nur mit, ohne Ausgleich.
        wetterwerte={
            s: int(min(max(round(w * faktor), kleinster), groesster))
            for s, w in auto.wetterwerte.items()
        },
    )


# ---------------------------------------------------------------------------
# Der ganze Winterschritt
# ---------------------------------------------------------------------------
def naechste_generation(
    konfiguration: Konfiguration,
    welt: Welt,
    jahr: int,
    seedquelle: Seedquelle,
    platzierungen: dict[int, int] | None = None,
) -> tuple[Welt, Winterbericht]:
    """Ruecktritte, Nachruecken, Newgens und Entwicklung in einem Schritt.

    Der Reihe nach:

    1. Wer ueber seiner Grenze ist, hoert auf - hoechstens so viele, wie
       die Obergrenze je Winter zulaesst.
    2. Die frei gewordenen Plaetze werden **von unten aufgefuellt**, und
       zwar **nach der Platzierung** der abgelaufenen Saison: Wer seine
       Liga gewonnen hat, rueckt zuerst nach. Ohne Platzierungen - vor dem
       ersten Rennen - entscheidet die Staerke.
    3. Die Newgens fuellen von unten auf: erst Liga 20, und wenn es mehr
       sind, als dort Platz haben, auch Liga 19 und weiter.
    4. Alle altern um ein Jahr, und jede Liga wird auf ihre Staerke aus
       GDD 9 zurueckgeholt.

    Aufgerufen wird das **nach** dem gewoehnlichen Auf- und Abstieg: Der
    regelt, wer sich sportlich hoch- oder runtergefahren hat; hier geht es
    um die Plaetze, die niemand mehr besetzt.

    :param platzierungen: je Fahrernummer sein Platz in der abgelaufenen
        Saison (1 ist der beste). Fehlt er, zaehlt die Staerke.
    """
    gehen, aufgeschoben = ruecktritte(konfiguration, welt, jahr, seedquelle)
    weg = {f.nummer for f in gehen}
    plaetze = platzierungen or {}

    bleibend = [f for f in welt.fahrer if f.nummer not in weg]
    ligen = sorted({f.liga for f in welt.fahrer})
    je_liga = konfiguration.wert("ligen", "autos_je_liga")
    unterste = max(ligen)

    def guete(fahrer: Fahrer) -> tuple:
        """Wer zuerst nachrueckt: der Bestplatzierte, sonst der Staerkste."""
        platz = plaetze.get(fahrer.nummer)
        if platz is None:
            return (1, -gesamtwert(konfiguration, fahrer.auto), fahrer.nummer)
        return (0, platz, fahrer.nummer)

    # Schritt 2: von oben nach unten auffuellen. Wer in Liga 3 aufhoert,
    # zieht den Ersten aus Liga 4 nach, der wiederum den Ersten aus Liga 5.
    nach_liga = {f.nummer: f.liga for f in bleibend}
    nachgerueckt: list[tuple[int, int, int]] = []
    for liga in ligen:
        if liga == unterste:
            continue
        while sum(1 for n in nach_liga.values() if n == liga) < je_liga:
            # Aus der naechsten besetzten Liga darunter - nicht nur aus
            # L+1. Sonst blieben Loecher in der Mitte haengen, wenn die
            # Liga direkt darunter selbst schon leer gelaufen ist, und die
            # Newgens landeten mittendrin statt unten.
            darunter = []
            for tiefer in range(liga + 1, unterste + 1):
                darunter = [f for f in bleibend if nach_liga[f.nummer] == tiefer]
                if darunter:
                    break
            if not darunter:  # pragma: no cover - alle unteren Ligen leer
                break
            bester = min(darunter, key=guete)
            nachgerueckt.append((bester.nummer, nach_liga[bester.nummer], liga))
            nach_liga[bester.nummer] = liga

    fahrer = [replace(f, liga=nach_liga[f.nummer]) for f in bleibend]

    # Schritt 3: Die Newgens fuellen von unten auf - erst Liga 20, und
    # wenn es mehr sind, als dort Platz haben, auch Liga 19 und weiter.
    namen = {(f.vorname, f.nachname) for f in fahrer}
    kuerzel = {f.auto.kuerzel for f in fahrer}
    neue = []
    offen = []
    for liga in sorted(ligen, reverse=True):
        fehlt = je_liga - sum(1 for f in fahrer if f.liga == liga)
        offen.extend([liga] * fehlt)
    if len(offen) != len(gehen):  # pragma: no cover - Notbremse
        raise GenerationenFehler(
            f"{len(gehen)} Ruecktritte, aber {len(offen)} freie Plaetze"
        )
    for stelle, (alter_fahrer, liga) in enumerate(zip(gehen, offen, strict=True)):
        ziele = kern_welt.ligastaerken(konfiguration, liga, je_liga)
        # Der Newgen erbt den Teamplatz des Zurueckgetretenen - so bleiben
        # die Teams bei vier Autos (GDD 12).
        neue.append(
            newgen(
                konfiguration,
                nummer=alter_fahrer.nummer,
                team=alter_fahrer.team,
                liga=liga,
                staerke=ziele[-1 - min(stelle, len(ziele) - 1)],
                jahr=jahr,
                seedquelle=seedquelle.zweig("generation", jahr),
                vergebene_namen=namen,
                vergebene_kuerzel=kuerzel,
            )
        )

    zusammen = sorted(fahrer + neue, key=lambda f: f.nummer)
    gealtert = _spieler_bleibt_jung(
        konfiguration, Welt(teams=welt.teams, fahrer=tuple(zusammen), seed=welt.seed)
    )
    return (
        entwickelt(konfiguration, gealtert, jahr),
        Winterbericht(
            jahr=jahr,
            zurueckgetreten=tuple(f.nummer for f in gehen),
            newgens=tuple(f.nummer for f in neue),
            nachgerueckt=tuple(nachgerueckt),
            aufgeschoben=aufgeschoben,
        ),
    )


def _spieler_bleibt_jung(konfiguration: Konfiguration, welt: Welt) -> Welt:
    """Schiebt den Geburtstag des Spielers um ein Jahr vor (GDD 1).

    Der Auftraggeber hat entschieden: Sein Alter bleibt fest und seine
    Karriere endet nicht. Statt das Alter ueberall zu einem Sonderfall zu
    machen, wandert sein Geburtstag mit - dann stimmt jede Anzeige und
    jede Rechnung von allein.
    """
    spieler = welt.spieler
    if spieler is None:
        return welt
    try:
        neuer = spieler.geburtstag.replace(year=spieler.geburtstag.year + 1)
    except ValueError:  # 29. Februar
        neuer = spieler.geburtstag.replace(
            year=spieler.geburtstag.year + 1, day=28
        )
    return Welt(
        teams=welt.teams,
        fahrer=tuple(
            replace(f, geburtstag=neuer) if f.ist_spieler else f for f in welt.fahrer
        ),
        seed=welt.seed,
    )
