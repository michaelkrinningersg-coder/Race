"""Ruecktritt, Newgens und die Entwicklung der KI (Punkt 35).

Bis hierher waren die 600 Fahrer aus GDD 12 unveraenderlich: dieselben
Namen, dieselben Werte, dasselbe Alter, Saison fuer Saison. Dieses Modul
macht aus ihnen Generationen.

Vier Regeln, alle vom Auftraggeber entschieden:

* **Ruecktritt** zwischen 34 und 42, je Fahrer einmal gestreut.
* **Ein Newgen je Ruecktritt.** Newgens steigen ganz unten ein, in
  Liga 20; die vorhandenen Fahrer fuellen nach oben auf.
* **Die frei gewordenen Plaetze werden nach der Platzierung besetzt.**
  Wer seine Liga gewonnen hat, rueckt zuerst nach.
* **Jeder entwickelt sich nach seinem eigenen Talent** (siehe
  ``talent.py``). Der Ligakorridor aus GDD 9 gilt nur noch beim
  Weltstart; danach sortieren sich die Ligen ueber Auf- und Abstieg.
* **Auch die eigenen Fahrer altern und treten zurueck.** Seit der
  Spieler Teamchef ist, gibt es keinen Fahrer mehr, der ausgenommen
  waere. Sie wachsen nur nicht von allein - dafuer sorgt das Training.

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
from rennmanager.kern import talent as kern_talent
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

    Auch die eigenen: Seit der Spieler Teamchef ist, altern seine vier
    Fahrer wie alle anderen und hoeren irgendwann auf. Wer nachrueckt,
    entscheidet er (Punkt 7 - Fahrer holen).
    """
    stichtag = kern_kalender.saisonstart(konfiguration, jahr)
    return tuple(
        fahrer
        for fahrer in welt.fahrer
        if fahrer.alter_am(stichtag)
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
# Newgens
# ---------------------------------------------------------------------------
def newgen(
    konfiguration: Konfiguration,
    nummer: int,
    team: int,
    liga: int,
    jahr: int,
    seedquelle: Seedquelle,
    seedquelle_talent: Seedquelle,
    vergebene_namen: set[tuple[str, str]],
    vergebene_kuerzel: set[str],
) -> Fahrer:
    """Ein neuer Fahrer fuer die unterste Liga.

    Gebaut wie die 600 der Startwelt, nur jung: Name und Land aus
    denselben Listen, und die Werte aus **seinem** Talent in **seinem**
    Alter.

    :param seedquelle: Name, Land und Geburtstag - haengt am Jahrgang
    :param seedquelle_talent: die Hauptquelle, aus der Talent und
        Ruecktrittsalter kommen. Sie muessen an der Fahrernummer haengen
        und nicht am Jahrgang, sonst haette ein Fahrer zwei Talente.
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

    # Sein Profil ist sein Potential, herunterskaliert auf das, was er in
    # seinem Alter davon erreicht hat - genau wie bei den 600 der
    # Startwelt. Die Ligastaerke spielt keine Rolle mehr: Ein Newgen ist
    # so gut, wie sein Talent und sein Alter es hergeben, nicht so gut,
    # wie die Liga es vorsieht, in der er zufaellig landet.
    talent = kern_talent.talent(
        konfiguration, nummer, geburtstag, seedquelle_talent
    )
    werte, wetterwerte = kern_talent.profil(
        konfiguration,
        talent,
        kern_talent.stand_mit(
            konfiguration,
            talent,
            alter,
            ruecktrittsalter(konfiguration, nummer, seedquelle_talent),
        ),
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
# Entwicklung nach dem Talent
# ---------------------------------------------------------------------------
def entwickelt(
    konfiguration: Konfiguration, welt: Welt, jahr: int, seedquelle: Seedquelle
) -> Welt:
    """Altert alle Fahrer um ein Jahr, jeden nach seinem eigenen Talent.

    Frueher fuhren alle dieselbe Alterskurve, und danach wurde jede Liga
    auf ihren Korridor aus GDD 9 normiert. Beides ist weg (Entscheidung
    des Auftraggebers): Jeder Fahrer hat jetzt sein eigenes Potential, und
    seine Werte holen jedes Jahr einen Anteil des Abstands dorthin auf.

    **Der Korridor aus GDD 9 gilt nur noch beim Weltstart.** Danach
    sortieren sich die Ligen ueber Auf- und Abstieg - dann sind sie
    Leistungsklassen und nicht mehr, wie gemessen, Altersklassen.

    Das kostet die Ligatabelle aus GDD 9, und zwar deutlich. Gemessen
    ueber dreissig Saisons mit echtem Rennbetrieb, Ist gegen Soll::

        Liga  1     5    10    15     20
              84%   59%  88%  149%  5182%

    Der Grund ist strukturell: Ein Newgen-Jahrgang traegt im Schnitt ein
    Potential von rund 33000 - Liga-10-Niveau - steigt aber geschlossen
    in Liga 20 ein, deren Soll bei 82 liegt. Liga 20 ist damit kein
    schwaches Feld mehr, sondern der Talentpool der ganzen Welt.

    **Der Auftraggeber hat das so entschieden**, nachdem ihm die Zahlen
    und drei Gegenmassnahmen vorlagen. Die Ligen sind ab jetzt das, was
    die Talentverteilung aus ihnen macht; die Kontrolltabelle in
    ``[ligen] kontrolle`` beschreibt nur noch den Weltstart.

    Die Kalibrierung selbst bleibt unberuehrt: ``zieltempo(98000) =
    180,00 km/h`` ist eine Funktion der Konstanten, nicht der Welt.

    Was dafuer gewonnen ist - das Alter je Liga 1/5/10/15/20 -::

        vorher  36  38  31  26  21   (eine Alterskurve fuer alle)
        jetzt   33  32  29  26  22   (je Fahrer sein Talent)

    Liga 1 bestand vorher nur noch aus 38- bis 43-Jaehrigen. Jetzt
    erreicht ein Newgen die Spitze in im Schnitt 7,7 Jahren.
    """
    stichtag = kern_kalender.saisonstart(konfiguration, jahr)
    neu: list[Fahrer] = []
    for fahrer in welt.fahrer:
        talent = kern_talent.talent(
            konfiguration, fahrer.nummer, fahrer.geburtstag, seedquelle
        )
        if fahrer.ist_spieler:
            # Die eigenen Fahrer wachsen **nicht** von allein: Sie
            # entwickeln sich ueber das Training des Chefs (GDD 1 und 2),
            # gedeckelt durch dasselbe Potential. Das Alter nimmt es
            # ihnen aber genauso wieder - Ziel ist deshalb ihr heutiger
            # Stand, und der sinkt ab ihrem Abbaualter.
            talent = replace(
                talent,
                potential=dict(fahrer.auto.werte),
                wetterpotential=dict(fahrer.auto.wetterwerte),
            )
        neu.append(
            replace(
                fahrer,
                auto=kern_talent.gewachsen(
                    konfiguration,
                    fahrer.auto,
                    talent,
                    fahrer.alter_am(stichtag),
                    ruecktrittsalter(konfiguration, fahrer.nummer, seedquelle),
                ),
            )
        )
    return Welt(teams=welt.teams, fahrer=tuple(neu), seed=welt.seed)


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
    for alter_fahrer, liga in zip(gehen, offen, strict=True):
        # Der Newgen erbt den Teamplatz des Zurueckgetretenen - so bleiben
        # die Teams bei vier Autos (GDD 12). Faellt der Platz im
        # Spielerteam frei, gehoert auch der Nachfolger dem Spieler: Das
        # Team behaelt seine vier Autos, nur sitzen andere darin. Wen der
        # Chef stattdessen holen will, entscheidet er spaeter selbst
        # (Punkt 7 - Fahrer holen).
        neue.append(
            replace(
                newgen(
                    konfiguration,
                    nummer=alter_fahrer.nummer,
                    team=alter_fahrer.team,
                    liga=liga,
                    jahr=jahr,
                    seedquelle=seedquelle.zweig("generation", jahr),
                    seedquelle_talent=seedquelle,
                    vergebene_namen=namen,
                    vergebene_kuerzel=kuerzel,
                ),
                ist_spieler=alter_fahrer.ist_spieler,
            )
        )

    zusammen = sorted(fahrer + neue, key=lambda f: f.nummer)
    gealtert = Welt(teams=welt.teams, fahrer=tuple(zusammen), seed=welt.seed)
    return (
        entwickelt(konfiguration, gealtert, jahr, seedquelle),
        Winterbericht(
            jahr=jahr,
            zurueckgetreten=tuple(f.nummer for f in gehen),
            newgens=tuple(f.nummer for f in neue),
            nachgerueckt=tuple(nachgerueckt),
            aufgeschoben=aufgeschoben,
        ),
    )
