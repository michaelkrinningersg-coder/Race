"""Welt: 50 Autos, 25 Teams, ein Feld (GDD 12, Punkt 101).

Eine Welt wird einmal pro Karriere aus einem Seed erzeugt und bleibt dann
bestehen. Sie enthaelt:

* **50 Autos** in einem einzigen Feld. Ihre Staerke steht fest und
  aendert sich nie: Sie faellt gleichmaessig vom Besten zum Letzten, von
  ``feld.s_bester`` bis ``feld.s_letzter``. Der Beste faehrt damit den
  Anker der Kalibrierung - in Zandvoort 180,00 km/h -, der Letzte
  braucht fuer dieselbe Runde 4 % laenger.
* **25 Teams** zu je zwei Autos, eines je Hersteller. Die Teams stehen
  auf der Leiter untereinander: Wer Rang 1 zieht, bekommt die Plaetze 1
  und 2, Rang 2 die Plaetze 3 und 4 und so fort. Die beiden Autos eines
  Teams sind also Nachbarn, wie in einer echten Rennserie.
* **Fahrer** mit fiktivem Namen, Herkunftsland und Geburtsdatum.

Das Profil eines Autos streut um seine Staerke (GDD 12), sodass es
Regenspezialisten, Qualifying-Experten und Reifenschoner gibt. Es
verteilt die Staerke nur um, es schenkt keine dazu: Wer vorne steht,
steht vorne.

Punkt 101 hat Talente, Potentiale, Alterung und Auf- und Abstieg
gestrichen. Niemand entwickelt sich mehr - weder die KI noch der
Spieler.
"""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class WeltFehler(Exception):
    """Die Welt laesst sich mit dieser Konfiguration nicht erzeugen."""


@dataclass(frozen=True)
class Fahrer:
    """Ein Fahrer mit Namen, Herkunft und Auto (GDD 12)."""

    nummer: int
    vorname: str
    nachname: str
    land: str
    geburtstag: dt.date
    team: int
    auto: Auto
    ist_spieler: bool = False

    @property
    def name(self) -> str:
        return f"{self.vorname} {self.nachname}"

    @property
    def kuerzel(self) -> str:
        return self.auto.kuerzel

    def alter_am(self, tag: dt.date) -> int:
        """Alter in Jahren. Seit Punkt 101 altert niemand mehr; die
        Anzeige braucht den Wert trotzdem."""
        jahre = tag.year - self.geburtstag.year
        if (tag.month, tag.day) < (self.geburtstag.month, self.geburtstag.day):
            jahre -= 1
        return jahre


@dataclass(frozen=True)
class Team:
    """Ein Team mit zwei Autos eines Herstellers (GDD 12, Punkt 101)."""

    nummer: int
    name: str
    land: str
    hersteller: str
    # GDD 12 gibt Hersteller und Team je eine Farbe. Seit Punkt 101 faehrt
    # jeder Hersteller genau ein Team, die beiden sind damit dieselbe.
    herstellerfarbe: str
    farbe: str
    fahrer: tuple[int, ...]

    @property
    def kuerzel(self) -> str:
        """Drei Buchstaben aus dem ersten Namensteil, fuer enge Spalten."""
        return self.name.split()[0][:3].upper()


@dataclass(frozen=True)
class Welt:
    """Alle Teams und Fahrer einer Karriere."""

    teams: tuple[Team, ...]
    fahrer: tuple[Fahrer, ...]
    seed: int

    def mit_autos(self, autos: dict[int, Auto]) -> Welt:
        """Dieselbe Welt, aber mit diesen Autos bei diesen Fahrern.

        Genutzt vom Editor (GDD 15) und von allem, was ein Auto fuer eine
        Session austauscht, ohne die Welt selbst zu aendern.
        """
        if not autos:
            return self
        return replace(
            self,
            fahrer=tuple(
                replace(f, auto=autos[f.nummer]) if f.nummer in autos else f
                for f in self.fahrer
            ),
        )

    @property
    def feld(self) -> tuple[Fahrer, ...]:
        """Alle Fahrer, vom staerksten zum schwaechsten."""
        return tuple(sorted(self.fahrer, key=lambda f: -sum(f.auto.werte.values())))

    def team_von(self, fahrer: Fahrer) -> Team:
        return self.teams[fahrer.team]

    @property
    def spielerfahrer(self) -> tuple[Fahrer, ...]:
        """Die Fahrer des Spielerteams, in Startnummernfolge.

        Seit Punkt 101 sind es zwei.
        """
        return tuple(f for f in self.fahrer if f.ist_spieler)

    @property
    def spielerteam(self) -> Team | None:
        """Das Team, das dem Spieler gehoert."""
        eigene = self.spielerfahrer
        return self.teams[eigene[0].team] if eigene else None

    @property
    def spieler(self) -> Fahrer | None:
        """Der erste Fahrer des Spielerteams.

        Bleibt fuer alles, was genau einen Fahrer braucht - etwa die
        Ueberschrift eines Fensters. Wer beide meint, nimmt
        ``spielerfahrer``.
        """
        return next((f for f in self.fahrer if f.ist_spieler), None)

    def teamkollegen(self, fahrer: Fahrer) -> tuple[Fahrer, ...]:
        """Die uebrigen Fahrer desselben Teams (Punkt 101: zwei je Team)."""
        team = self.teams[fahrer.team]
        return tuple(self.fahrer[i] for i in team.fahrer if i != fahrer.nummer)


# ---------------------------------------------------------------------------
# Erzeugen
# ---------------------------------------------------------------------------
def lade_namen(konfiguration: Konfiguration) -> dict:
    """Liest die Namenslisten neben der Balancing-Datei."""
    pfad = Path(konfiguration.quelle) / konfiguration.wert("namen", "datei")
    if not pfad.is_file():
        raise WeltFehler(f"Namensdatei fehlt: {pfad}")
    with pfad.open("rb") as datei:
        return tomllib.load(datei)


def feldgrenzen(konfiguration: Konfiguration) -> tuple[int, int]:
    """Die Spanne des Feldes als ``(s_bester, s_letzter)`` (Punkt 101)."""
    return (
        int(konfiguration.wert("feld", "s_bester")),
        int(konfiguration.wert("feld", "s_letzter")),
    )


def feldstaerken(konfiguration: Konfiguration, anzahl: int | None = None) -> list[int]:
    """Die Staerken des Feldes, vom Besten zum Letzten (Punkt 101).

    Gleichmaessig verteilt zwischen den beiden Grenzen. Bei einem Auto
    bekommt es die Staerke des Besten.
    """
    if anzahl is None:
        anzahl = konfiguration.wert("rennen", "autos")
    if anzahl < 1:
        raise WeltFehler(f"Ein Feld braucht mindestens ein Auto, gefragt sind {anzahl}")
    bester, letzter = feldgrenzen(konfiguration)
    if anzahl == 1:
        return [bester]
    return [
        round(letzter + (bester - letzter) * nummer / (anzahl - 1))
        for nummer in range(anzahl - 1, -1, -1)
    ]


def kuerzel_fuer(nachname: str, vergeben: set[str]) -> str:
    """Drei Buchstaben, die im ganzen Feld nur einmal vorkommen.

    Im Rennen stehen die Kuerzel neben den Punkten (GDD 4); zwei gleiche
    waeren dort nicht auseinanderzuhalten.
    """
    sauber = "".join(zeichen for zeichen in nachname.upper() if zeichen.isalpha())
    vorschlaege = [sauber[:3]]
    if len(sauber) >= 3:
        vorschlaege.append(sauber[:2] + sauber[-1])
        vorschlaege.append(sauber[0] + sauber[2:4])
    vorschlaege += [f"{sauber[:2]}{ziffer}" for ziffer in range(1, 10)]

    for vorschlag in vorschlaege:
        if len(vorschlag) == 3 and vorschlag not in vergeben:
            vergeben.add(vorschlag)
            return vorschlag
    # Notnagel: durchnummerieren, bis etwas frei ist.
    for zahl in range(100, 1000):  # pragma: no cover - bei 50 Fahrern unnoetig
        vorschlag = f"{sauber[0]}{zahl % 100:02d}"
        if vorschlag not in vergeben:
            vergeben.add(vorschlag)
            return vorschlag
    raise WeltFehler("Kein freies Kuerzel mehr")  # pragma: no cover


def auf_skala(
    konfiguration: Konfiguration, werte: dict[str, float], ziel: float
) -> dict[str, int]:
    """Schneidet Werte auf die Skala und holt zurueck, was das Kappen nimmt.

    Das Feld liegt dicht unter dem Skalenmaximum aus GDD 9. Ohne Ausgleich
    fielen dort die hohen Werte eines Spezialisten weg und sein Mittel
    saenke unter die Staerke, die ihm zusteht - er waere langsamer, weil
    er ein Profil hat.

    :param ziel: der Mittelwert, den die Werte danach haben sollen
    """
    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")
    aktuell = dict(werte)
    for _ in range(8):
        geschnitten = {
            s: min(max(w, kleinster), groesster) for s, w in aktuell.items()
        }
        ist = sum(geschnitten.values()) / len(geschnitten)
        if ziel <= 0 or abs(ist - ziel) < 0.5:
            return {s: int(round(w)) for s, w in geschnitten.items()}
        # Nur die Werte anheben, die noch Luft haben.
        frei = {s: w for s, w in geschnitten.items() if kleinster < w < groesster}
        if not frei:
            return {s: int(round(w)) for s, w in geschnitten.items()}
        fehlt = (ziel - ist) * len(geschnitten)
        faktor = 1.0 + fehlt / sum(frei.values())
        aktuell = {
            s: (w * faktor if s in frei else geschnitten[s])
            for s, w in geschnitten.items()
        }
    return {
        s: int(round(min(max(w, kleinster), groesster))) for s, w in aktuell.items()
    }


def wuerfle_werte(
    konfiguration: Konfiguration, mittelwert: int, wuerfel, zusatz: list[str]
) -> tuple[dict[str, int], dict[str, int]]:
    """Profil eines Autos (GDD 12).

    Zwei Ebenen, damit echte Spezialisten entstehen:

    1. Ein Faktor je **Wirkungsbereich** - er macht den Fahrer, der in
       engen Kurven glaenzt und auf Geraden Mittelmass ist. Jede
       Faehigkeit erbt ihn gewichtet nach ihrer Zeile der Wirkungsmatrix.
    2. Darauf das **Rauschen je Einzelwert** aus GDD 12.

    Ohne die erste Ebene mittelt sich das Rauschen im Bereichsmittel weg.

    Beide Ebenen sind auf den Mittelwert normiert: Ein Spezialist
    verteilt seine Staerke um, statt mehr oder weniger davon zu haben.
    Seit Punkt 101 sind sie klein genug, dass die Leiter des Feldes
    darunter sichtbar bleibt (siehe ``[ki]``).
    """
    streuung = konfiguration.wert("ki", "profil_streuung")
    bereichs_streuung = konfiguration.wert("ki", "bereichs_streuung")
    wetter_streuung = konfiguration.wert("ki", "wetter_streuung")

    bereichsfaktor = {
        bereich: 1.0 + float(wuerfel.uniform(-bereichs_streuung, bereichs_streuung))
        for bereich in konfiguration.bereiche
    }

    def profilfaktor(faehigkeit) -> float:
        """Der Bereichsfaktor einer Faehigkeit, nach ihren Gewichten."""
        summe = sum(faehigkeit.gewichte.values())
        if not summe:
            return 1.0
        return (
            sum(bereichsfaktor[bereich] * gewicht
                for bereich, gewicht in faehigkeit.gewichte.items())
            / summe
        )

    def gestreut(profil: float, breite: float) -> float:
        rauschen = 1.0 + float(wuerfel.uniform(-breite, breite))
        return mittelwert * profil * rauschen

    def begrenzt(werte: dict[str, float]) -> dict[str, int]:
        return auf_skala(konfiguration, werte, mittelwert)

    faktoren = {f.schluessel: profilfaktor(f) for f in konfiguration.faehigkeiten}
    mittel = sum(faktoren.values()) / len(faktoren)
    werte = begrenzt(
        {
            schluessel: gestreut(faktor / mittel, streuung)
            for schluessel, faktor in faktoren.items()
        }
    )
    # Die Wetterfaehigkeiten stehen neben der Matrix; sie haben keinen
    # Bereich, aus dem sie einen Faktor erben koennten, und streuen
    # deshalb fuer sich - dafuer breiter.
    wetterwerte = begrenzt(
        {schluessel: gestreut(1.0, wetter_streuung) for schluessel in zusatz}
    )
    return werte, wetterwerte


def erzeuge(
    konfiguration: Konfiguration,
    seedquelle: Seedquelle,
    mit_spieler: bool = True,
    saisonjahr: int = 2026,
) -> Welt:
    """Erzeugt eine vollstaendige Welt (GDD 12, Punkt 101).

    :param mit_spieler: ob eines der Teams dem Spieler gehoert. Ohne das
        ein reines KI-Feld, wie es die Anzeige zum Blaettern braucht.
    :param saisonjahr: Bezugsjahr fuer die Geburtsdaten
    """
    namen = lade_namen(konfiguration)
    autos = konfiguration.wert("rennen", "autos")
    team_anzahl = konfiguration.wert("teams", "anzahl")
    je_team = konfiguration.wert("teams", "autos_je_team")

    if team_anzahl * je_team != autos:
        raise WeltFehler(
            f"{team_anzahl} Teams zu je {je_team} Autos ergeben {team_anzahl * je_team}, "
            f"gebraucht werden {autos}"
        )
    if len(konfiguration.hersteller) < team_anzahl:
        raise WeltFehler(
            f"{team_anzahl} Teams brauchen ebenso viele Hersteller, "
            f"vorhanden sind {len(konfiguration.hersteller)}"
        )

    wuerfel = seedquelle.zweig("welt").generator()
    zusatz = list(konfiguration.zusatzfaehigkeiten)

    spielerteam = int(wuerfel.integers(0, team_anzahl)) if mit_spieler else None

    # Punkt 101: Die Teams stehen als Ganzes auf der Leiter. Welcher Rang
    # welchem Team gehoert, entscheidet der Seed; das Team auf Rang r
    # bekommt die Plaetze (r-1)*je_team + 1 bis r*je_team. Die beiden
    # Autos eines Teams sind dadurch Nachbarn - ein Team ist stark oder
    # schwach, nicht beides zugleich.
    raenge = list(range(team_anzahl))
    wuerfel.shuffle(raenge)
    leiter = feldstaerken(konfiguration, autos)
    staerke_je_fahrer = {
        team * je_team + platz: leiter[rang * je_team + platz]
        for rang, team in enumerate(raenge)
        for platz in range(je_team)
    }

    fahrer = _erzeuge_fahrer(
        konfiguration,
        namen,
        staerke_je_fahrer,
        zusatz,
        wuerfel,
        saisonjahr,
        spielerteam,
        seedquelle,
    )
    teams = _erzeuge_teams(konfiguration, namen, team_anzahl, je_team, fahrer, wuerfel)
    return Welt(teams=teams, fahrer=tuple(fahrer), seed=seedquelle.seed)


def startalter(konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle) -> int:
    """Das Alter dieses Fahrers (GDD 12).

    Am Seed und an der Fahrernummer, nicht an der Aufrufreihenfolge. Seit
    Punkt 101 altert niemand mehr, der Wert gilt also fuer immer.
    """
    wuerfel = seedquelle.zweig("startalter", nummer).generator()
    return int(
        wuerfel.integers(
            konfiguration.wert("fahrernamen", "alter_min"),
            konfiguration.wert("fahrernamen", "alter_max") + 1,
        )
    )


def startgeburtstag(
    konfiguration: Konfiguration, nummer: int, seedquelle: Seedquelle, saisonjahr: int
) -> dt.date:
    """Der Geburtstag dieses Fahrers (GDD 12).

    Das Alter gilt zum Saisonstart. Der Geburtstag liegt deshalb im Jahr
    *vor* dem Stichtag minus Alter - vom 1. Januar aus gerechnet waere
    jeder, der spaeter im Jahr Geburtstag hat, am Saisonstart noch ein
    Jahr juenger als gewuerfelt.
    """
    stichtag = dt.date(
        saisonjahr,
        konfiguration.wert("kalender", "saisonstart_monat"),
        konfiguration.wert("kalender", "saisonstart_tag"),
    )
    alter = startalter(konfiguration, nummer, seedquelle)
    wuerfel = seedquelle.zweig("geburtstag", nummer).generator()
    return stichtag.replace(year=stichtag.year - alter) - dt.timedelta(
        days=int(wuerfel.integers(0, 365))
    )


def _erzeuge_fahrer(
    konfiguration, namen, staerke_je_fahrer, zusatz, wuerfel, saisonjahr,
    spielerteam, seedquelle
) -> list[Fahrer]:
    vornamen = namen["fahrer"]["vornamen"]
    nachnamen = namen["fahrer"]["nachnamen"]
    europa = namen["fahrer"]["laender"]["europa"]
    nordamerika = namen["fahrer"]["laender"]["nordamerika"]
    anteil_na = konfiguration.wert("fahrernamen", "anteil_nordamerika")
    vergeben: set[tuple[str, str]] = set()
    kuerzel_vergeben: set[str] = set()
    fahrer: list[Fahrer] = []
    je_team = konfiguration.wert("teams", "autos_je_team")
    teams = len(staerke_je_fahrer) // je_team

    for team in range(teams):
        for n in range(je_team):
            nummer = team * je_team + n

            # Namen bleiben eindeutig.
            while True:
                paar = (
                    vornamen[int(wuerfel.integers(0, len(vornamen)))],
                    nachnamen[int(wuerfel.integers(0, len(nachnamen)))],
                )
                if paar not in vergeben:
                    vergeben.add(paar)
                    break

            land = (
                nordamerika[int(wuerfel.integers(0, len(nordamerika)))]
                if wuerfel.random() < anteil_na
                else europa[int(wuerfel.integers(0, len(europa)))]
            )
            geburtstag = startgeburtstag(
                konfiguration, nummer, seedquelle, saisonjahr
            )

            # Punkt 101: Der Spieler faehrt dieselbe Leiter wie alle
            # anderen. Er kauft nichts mehr dazu, also bekommt er auch
            # keinen eigenen Startwert.
            werte, wetterwerte = wuerfle_werte(
                konfiguration, staerke_je_fahrer[nummer], wuerfel, zusatz
            )

            fahrer.append(
                Fahrer(
                    nummer=nummer,
                    vorname=paar[0],
                    nachname=paar[1],
                    land=land,
                    geburtstag=geburtstag,
                    team=team,
                    auto=Auto(
                        kuerzel=kuerzel_fuer(paar[1], kuerzel_vergeben),
                        name=f"{paar[0]} {paar[1]}",
                        werte=werte,
                        wetterwerte=wetterwerte,
                    ),
                    ist_spieler=team == spielerteam,
                )
            )
    return fahrer


def _erzeuge_teams(
    konfiguration, namen, team_anzahl, je_team, fahrer, wuerfel
) -> tuple[Team, ...]:
    erste = namen["team"]["erste_teile"]
    zweite = namen["team"]["zweite_teile"]
    laender = namen["fahrer"]["laender"]["europa"] + namen["fahrer"]["laender"]["nordamerika"]

    # Punkt 101: Jeder Hersteller faehrt genau ein Team. Welcher welches
    # ist, entscheidet der Seed.
    marken = list(konfiguration.hersteller)
    wuerfel.shuffle(marken)

    vergeben: set[str] = set()
    teams: list[Team] = []
    for nummer in range(team_anzahl):
        eigene = [fahrer[nummer * je_team + n] for n in range(je_team)]
        while True:
            name = (
                f"{erste[int(wuerfel.integers(0, len(erste)))]} "
                f"{zweite[int(wuerfel.integers(0, len(zweite)))]}"
            )
            if name not in vergeben:
                vergeben.add(name)
                break

        marke = marken[nummer]
        teams.append(
            Team(
                nummer=nummer,
                name=name,
                land=laender[int(wuerfel.integers(0, len(laender)))],
                hersteller=marke.name,
                herstellerfarbe=marke.farbe,
                farbe=marke.farbe,
                fahrer=tuple(f.nummer for f in eigene),
            )
        )
    return tuple(teams)


# ---------------------------------------------------------------------------
# Anschluss ans Rennen
# ---------------------------------------------------------------------------
def mit_fahrerwerten(
    welt: Welt, aenderungen: dict[int, tuple[dict[str, int], dict[str, int]]]
) -> Welt:
    """Eine neue Welt mit geaenderten Werten einzelner Fahrer.

    ``Welt``, ``Fahrer`` und ``Auto`` sind unveraenderlich; wer Werte
    aendern will, baut die Welt neu. Genutzt vom Editor (GDD 15:
    Balancing-Werkzeuge), dessen Aenderungen dauerhaft sind und mit dem
    Spielstand gespeichert werden.

    :param aenderungen: je Fahrernummer ein Paar aus Werten und
        Wetterwerten
    """
    unbekannt = set(aenderungen) - {f.nummer for f in welt.fahrer}
    if unbekannt:
        raise WeltFehler(f"Unbekannte Fahrernummern: {sorted(unbekannt)}")

    fahrer = []
    for f in welt.fahrer:
        if f.nummer not in aenderungen:
            fahrer.append(f)
            continue
        werte, wetterwerte = aenderungen[f.nummer]
        fahrer.append(
            replace(
                f,
                auto=Auto(
                    kuerzel=f.auto.kuerzel,
                    name=f.auto.name,
                    werte=dict(werte),
                    wetterwerte=dict(wetterwerte),
                ),
            )
        )
    return Welt(teams=welt.teams, fahrer=tuple(fahrer), seed=welt.seed)


def mit_fahrerdaten(welt: Welt, aenderungen: dict[int, dict]) -> Welt:
    """Eine neue Welt mit geaenderten Stammdaten (Name, Land, Geburtstag).

    Das Team bleibt aussen vor: Ein Wechsel dort spraenge die
    Teamgroessen aus GDD 12.
    """
    erlaubt = {"vorname", "nachname", "land", "geburtstag"}
    fahrer = []
    for f in welt.fahrer:
        felder = aenderungen.get(f.nummer)
        if not felder:
            fahrer.append(f)
            continue
        unbekannt = set(felder) - erlaubt
        if unbekannt:
            raise WeltFehler(f"Diese Stammdaten lassen sich nicht aendern: {sorted(unbekannt)}")
        neu = replace(f, **felder)
        # Der Anzeigename des Autos haengt am Fahrernamen.
        fahrer.append(replace(neu, auto=replace(neu.auto, name=neu.name)))
    return Welt(teams=welt.teams, fahrer=tuple(fahrer), seed=welt.seed)


def mit_teamname(welt: Welt, team: int, name: str) -> Welt:
    """Eine neue Welt, in der ein Team anders heisst.

    Der Teamchef benennt sein Team selbst (Punkt 11). Alles andere am
    Team - Hersteller, Farben, Fahrer - bleibt, wie die Welt es
    gewuerfelt hat.
    """
    if not 0 <= team < len(welt.teams):
        raise WeltFehler(f"Team {team} gibt es nicht")
    sauber = name.strip()
    if not sauber:
        raise WeltFehler("Ein Team braucht einen Namen")
    return Welt(
        teams=tuple(
            replace(mannschaft, name=sauber) if nummer == team else mannschaft
            for nummer, mannschaft in enumerate(welt.teams)
        ),
        fahrer=welt.fahrer,
        seed=welt.seed,
    )


def starterfeld(
    welt: Welt,
    reihenfolge: tuple[int, ...] | None = None,
    autos: dict[int, Auto] | None = None,
):
    """Baut aus der Welt das Starterfeld fuers Rennen.

    :param reihenfolge: Startaufstellung als Fahrernummern, Pole zuerst -
        ueblich das Ergebnis des Qualifyings. Ohne Angabe nach Staerke.
    :param autos: Autos, die je Fahrernummer an die Stelle des
        hinterlegten treten. So kommen Defekte und Tagesform ins Rennen,
        ohne die Reihenfolge des Feldes zu verschieben - die richtet sich
        weiter nach der Welt.
    """
    from rennmanager.kern.rennen import Teilnehmer

    fahrer = welt.feld
    if reihenfolge is None:
        geordnet = fahrer
    else:
        nach_nummer = {f.nummer: f for f in fahrer}
        fehlend = set(nach_nummer) - set(reihenfolge)
        if fehlend:
            raise WeltFehler("Die Aufstellung nennt nicht alle Fahrer des Feldes")
        geordnet = tuple(nach_nummer[nummer] for nummer in reihenfolge)

    ersatz = autos or {}
    return tuple(
        Teilnehmer(
            auto=ersatz.get(f.nummer, f.auto),
            startplatz=platz,
            # GDD 4: Autos als Punkte in Teamfarbe.
            farbe=welt.team_von(f).farbe,
            ist_spieler=f.ist_spieler,
            nummer=f.nummer,
        )
        for platz, f in enumerate(geordnet, start=1)
    )
