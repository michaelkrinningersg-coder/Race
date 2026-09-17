"""Welt: 600 Autos, 150 Teams, 20 Ligen (GDD 12).

Eine Welt wird einmal pro Karriere aus einem Seed erzeugt und bleibt dann
bestehen. Sie enthaelt:

* **600 Autos** - 20 Ligen zu je 30. Die Staerke eines Autos liegt
  zwischen dem Letzten und dem Besten seiner Liga, wie es die
  Kalibriertabelle in GDD 9 vorgibt, plus Rauschen.
* **150 Teams** zu je 4 Autos eines Herstellers. Die vier Autos eines
  Teams koennen in verschiedenen Ligen fahren; Teams und Hersteller sind
  ueber alle Ligen verteilt, nicht zwingend gleichmaessig.
* **Fahrer** mit fiktivem Namen, Herkunftsland und Geburtsdatum.

Das Profil eines Autos streut um seinen Mittelwert (GDD 12), sodass es
Regenspezialisten, Qualifying-Experten und Reifenschoner gibt. Die KI
verbessert sich vorerst nicht.
"""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

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
    liga: int
    auto: Auto
    ist_spieler: bool = False

    @property
    def name(self) -> str:
        return f"{self.vorname} {self.nachname}"

    @property
    def kuerzel(self) -> str:
        return self.auto.kuerzel

    def alter_am(self, tag: dt.date) -> int:
        """Alter in Jahren. Das GDD altert vorerst nicht, die Anzeige
        braucht den Wert trotzdem."""
        jahre = tag.year - self.geburtstag.year
        if (tag.month, tag.day) < (self.geburtstag.month, self.geburtstag.day):
            jahre -= 1
        return jahre


@dataclass(frozen=True)
class Team:
    """Ein Team mit vier Autos eines Herstellers (GDD 12)."""

    nummer: int
    name: str
    land: str
    hersteller: str
    # GDD 12 gibt Hersteller und Team je eine Farbe; die Punkte im Rennen
    # tragen die Teamfarbe (GDD 4).
    herstellerfarbe: str
    farbe: str
    budget: int
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

    def liga(self, nummer: int) -> tuple[Fahrer, ...]:
        """Die Fahrer einer Liga, vom staerksten zum schwaechsten."""
        return tuple(
            sorted(
                (f for f in self.fahrer if f.liga == nummer),
                key=lambda f: -sum(f.auto.werte.values()),
            )
        )

    def team_von(self, fahrer: Fahrer) -> Team:
        return self.teams[fahrer.team]

    @property
    def spieler(self) -> Fahrer | None:
        return next((f for f in self.fahrer if f.ist_spieler), None)

    def teamkollegen(self, fahrer: Fahrer) -> tuple[Fahrer, ...]:
        """Die uebrigen Fahrer desselben Teams (GDD 12: Spieler plus 3 KI)."""
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


def _staerken(konfiguration: Konfiguration, liga: int, anzahl: int) -> list[int]:
    """Staerken einer Liga, vom Besten zum Letzten (GDD 9)."""
    kontrolle = {z["liga"]: z for z in konfiguration.wert("ligen", "kontrolle")}
    if liga in kontrolle:
        bester = kontrolle[liga]["s_bester"]
        letzter = kontrolle[liga]["s_letzter"]
    else:
        # Zwischen den Stuetzstellen aus GDD 9 wird interpoliert: Das
        # Tempo waechst je Liga um einen festen Betrag, der Wert S ergibt
        # sich daraus durch Umkehren der Kalibrierfunktion.
        bester = _wert_zu_tempo(konfiguration, _bestes_tempo(konfiguration, liga))
        letzter = _wert_zu_tempo(konfiguration, _letztes_tempo(konfiguration, liga))
    return [
        round(letzter + (bester - letzter) * nummer / (anzahl - 1))
        for nummer in range(anzahl - 1, -1, -1)
    ]


def _bestes_tempo(konfiguration: Konfiguration, liga: int) -> float:
    basis = konfiguration.wert("ligen", "bester_liga20_kmh")
    zuwachs = konfiguration.wert("ligen", "zuwachs_je_liga_kmh")
    return basis + zuwachs * (konfiguration.wert("ligen", "anzahl") - liga)


def _letztes_tempo(konfiguration: Konfiguration, liga: int) -> float:
    if liga == konfiguration.wert("ligen", "anzahl"):
        return konfiguration.wert("ligen", "letzter_liga20_kmh")
    return _bestes_tempo(konfiguration, liga + 1) - konfiguration.wert(
        "ligen", "ueberlappung_kmh"
    )


def _wert_zu_tempo(konfiguration: Konfiguration, tempo_kmh: float) -> int:
    """Kehrt die Kalibrierfunktion aus GDD 9 um: v(S) -> S."""
    basis = konfiguration.wert("kalibrierung", "basis_kmh")
    spanne = konfiguration.wert("kalibrierung", "spanne_kmh")
    referenz = konfiguration.wert("skala", "referenz")
    anteil = max((tempo_kmh - basis) / spanne, 0.0)
    return int(round(referenz * anteil * anteil))


def _kuerzel(nachname: str, vergeben: set[str]) -> str:
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
    for zahl in range(100, 1000):  # pragma: no cover - bei 600 Fahrern unnoetig
        vorschlag = f"{sauber[0]}{zahl % 100:02d}"
        if vorschlag not in vergeben:
            vergeben.add(vorschlag)
            return vorschlag
    raise WeltFehler("Kein freies Kuerzel mehr")  # pragma: no cover


def _teamfarbe(grundfarbe: str, nummer: int, anzahl: int) -> str:
    """Eigene Teamfarbe, aus der Herstellerfarbe abgewandelt (GDD 12).

    Das GDD gibt Hersteller und Team je eine Farbe. Weil 150 Teams auf 20
    Hersteller kommen, wird die Herstellerfarbe je Team in der Helligkeit
    verschoben - die Marke bleibt erkennbar, die Teams unterscheidbar.
    """
    rot = int(grundfarbe[1:3], 16)
    gruen = int(grundfarbe[3:5], 16)
    blau = int(grundfarbe[5:7], 16)
    # Bis zu 8 Stufen zwischen dunkler und heller als die Grundfarbe.
    stufe = (nummer % 8) - 3.5
    faktor = 1.0 + stufe * 0.11
    del anzahl

    def an(wert: int) -> int:
        return max(0, min(255, round(wert * faktor)))

    return f"#{an(rot):02x}{an(gruen):02x}{an(blau):02x}"


def _wuerfle_werte(
    konfiguration: Konfiguration, mittelwert: int, wuerfel, zusatz: list[str]
) -> tuple[dict[str, int], dict[str, int]]:
    """Profil eines Autos (GDD 12).

    Zwei Ebenen, damit echte Spezialisten entstehen:

    1. Ein Faktor je **Wirkungsbereich** - er macht den Fahrer, der in
       engen Kurven glaenzt und auf Geraden Mittelmass ist. Jede
       Faehigkeit erbt ihn gewichtet nach ihrer Zeile der Wirkungsmatrix.
    2. Darauf das **Rauschen je Einzelwert** aus GDD 12.

    Ohne die erste Ebene mittelt sich das Rauschen im Bereichsmittel weg:
    Aus +/-25 % je Einzelwert wurden gemessen nur 20 % Spanne zwischen dem
    staerksten und dem schwaechsten Bereich eines Fahrers.
    """
    streuung = konfiguration.wert("ki", "profil_streuung")
    bereichs_streuung = konfiguration.wert("ki", "bereichs_streuung")
    wetter_streuung = konfiguration.wert("ki", "wetter_streuung")
    kleinster = konfiguration.wert("skala", "minimum")
    groesster = konfiguration.wert("skala", "maximum")

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
        """Schneidet auf die Skala und holt zurueck, was das Kappen nimmt.

        In Liga 1 liegt die Ligastaerke nahe am Skalenmaximum aus GDD 9.
        Ohne Ausgleich fielen dort die hohen Werte eines Spezialisten weg
        und sein Mittel saenke unter den Wert, den die Kalibriertabelle
        vorgibt - gemessen um 5 %, also gut 3 km/h.
        """
        ziel = mittelwert
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
        return {s: int(round(min(max(w, kleinster), groesster))) for s, w in aktuell.items()}

    # Die Bereichsfaktoren werden auf den Mittelwert 1 normiert. Ein
    # Spezialist ist damit eine Frage der *Form*, nicht der Staerke: Er
    # verteilt seine Ligastaerke um, statt mehr oder weniger davon zu
    # haben. Ohne das rutschte der schwaechste Fahrer einer Liga um rund
    # 10 % unter den Wert, den die Kalibriertabelle in GDD 9 vorgibt.
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
    spielerliga: int | None = None,
    saisonjahr: int = 2026,
) -> Welt:
    """Erzeugt eine vollstaendige Welt (GDD 12).

    :param spielerliga: Liga, in der der Spieler faehrt. Ohne Angabe ein
        reines KI-Feld; ueblich ist die Startliga aus der Konfiguration.
    :param saisonjahr: Bezugsjahr fuer die Geburtsdaten
    """
    namen = lade_namen(konfiguration)
    ligen = konfiguration.wert("ligen", "anzahl")
    je_liga = konfiguration.wert("ligen", "autos_je_liga")
    team_anzahl = konfiguration.wert("teams", "anzahl")
    je_team = konfiguration.wert("teams", "autos_je_team")

    gesamt = ligen * je_liga
    if team_anzahl * je_team != gesamt:
        raise WeltFehler(
            f"{team_anzahl} Teams zu je {je_team} Autos ergeben {team_anzahl * je_team}, "
            f"gebraucht werden {gesamt}"
        )

    wuerfel = seedquelle.zweig("welt").generator()
    zusatz = list(konfiguration.zusatzfaehigkeiten)

    # Alle 600 Plaetze mit ihrer Liga und Staerke aufbauen.
    plaetze: list[tuple[int, int]] = []
    for liga in range(1, ligen + 1):
        plaetze.extend((liga, staerke) for staerke in _staerken(konfiguration, liga, je_liga))

    # Die Plaetze auf die Teams verteilen. Weil gemischt wird, fahren die
    # vier Autos eines Teams meist in verschiedenen Ligen - genau wie es
    # GDD 12 erlaubt.
    reihenfolge = list(wuerfel.permutation(len(plaetze)))
    teamplaetze = [
        [plaetze[reihenfolge[team * je_team + n]] for n in range(je_team)]
        for team in range(team_anzahl)
    ]

    fahrer = _erzeuge_fahrer(
        konfiguration, namen, teamplaetze, zusatz, wuerfel, saisonjahr, spielerliga
    )
    teams = _erzeuge_teams(konfiguration, namen, teamplaetze, fahrer, wuerfel)
    return Welt(teams=teams, fahrer=tuple(fahrer), seed=seedquelle.seed)


def _erzeuge_fahrer(
    konfiguration, namen, teamplaetze, zusatz, wuerfel, saisonjahr, spielerliga
) -> list[Fahrer]:
    vornamen = namen["fahrer"]["vornamen"]
    nachnamen = namen["fahrer"]["nachnamen"]
    europa = namen["fahrer"]["laender"]["europa"]
    nordamerika = namen["fahrer"]["laender"]["nordamerika"]
    anteil_na = konfiguration.wert("fahrernamen", "anteil_nordamerika")
    alter_min = konfiguration.wert("fahrernamen", "alter_min")
    alter_max = konfiguration.wert("fahrernamen", "alter_max")
    # Stichtag fuers Alter ist der Saisonstart aus GDD 2.
    stichtag = dt.date(
        saisonjahr,
        konfiguration.wert("kalender", "saisonstart_monat"),
        konfiguration.wert("kalender", "saisonstart_tag"),
    )

    vergeben: set[tuple[str, str]] = set()
    kuerzel_vergeben: set[str] = set()
    fahrer: list[Fahrer] = []
    je_team = konfiguration.wert("teams", "autos_je_team")

    # Der Spieler bekommt den letzten Platz seiner Liga (GDD 1: alle Werte
    # auf 0, also hinterste Reihe).
    spielernummer = None
    if spielerliga is not None:
        kandidaten = [
            team * je_team + n
            for team, plaetze in enumerate(teamplaetze)
            for n, (liga, _) in enumerate(plaetze)
            if liga == spielerliga
        ]
        if not kandidaten:
            raise WeltFehler(f"Keine Plaetze in Liga {spielerliga}")
        # Der schwaechste Platz dieser Liga.
        spielernummer = min(
            kandidaten,
            key=lambda nummer: teamplaetze[nummer // je_team][nummer % je_team][1],
        )

    for team, plaetze in enumerate(teamplaetze):
        for n, (liga, staerke) in enumerate(plaetze):
            nummer = team * je_team + n
            ist_spieler = nummer == spielernummer

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
            alter = int(wuerfel.integers(alter_min, alter_max + 1))
            # Das Alter gilt zum Saisonstart (GDD 12). Der Geburtstag liegt
            # deshalb im Jahr *vor* dem Stichtag minus Alter - vom 1. Januar
            # aus gerechnet waere jeder, der spaeter im Jahr Geburtstag hat,
            # am Saisonstart noch ein Jahr juenger als gewuerfelt.
            geburtstag = stichtag.replace(year=stichtag.year - alter) - dt.timedelta(
                days=int(wuerfel.integers(0, 365))
            )

            # Der Spieler startet laut GDD 1 mit allen Werten auf 0.
            if ist_spieler:
                werte = {f.schluessel: 0 for f in konfiguration.faehigkeiten}
                wetterwerte = dict.fromkeys(zusatz, 0)
            else:
                werte, wetterwerte = _wuerfle_werte(konfiguration, staerke, wuerfel, zusatz)

            fahrer.append(
                Fahrer(
                    nummer=nummer,
                    vorname=paar[0],
                    nachname=paar[1],
                    land=land,
                    geburtstag=geburtstag,
                    team=team,
                    liga=liga,
                    auto=Auto(
                        kuerzel=_kuerzel(paar[1], kuerzel_vergeben),
                        name=f"{paar[0]} {paar[1]}",
                        werte=werte,
                        wetterwerte=wetterwerte,
                    ),
                    ist_spieler=ist_spieler,
                )
            )
    return fahrer


def _erzeuge_teams(konfiguration, namen, teamplaetze, fahrer, wuerfel) -> tuple[Team, ...]:
    erste = namen["team"]["erste_teile"]
    zweite = namen["team"]["zweite_teile"]
    laender = namen["fahrer"]["laender"]["europa"] + namen["fahrer"]["laender"]["nordamerika"]
    hersteller = konfiguration.hersteller
    je_team = konfiguration.wert("teams", "autos_je_team")

    in_siegpraemien = konfiguration.wert("teams", "budget_in_siegpraemien")
    streuung = konfiguration.wert("teams", "budget_streuung")
    praemien = {
        int(liga): betrag
        for liga, betrag in konfiguration.wert("preisgeld", "siegpraemie_euro").items()
    }

    vergeben: set[str] = set()
    teams: list[Team] = []
    for nummer, plaetze in enumerate(teamplaetze):
        while True:
            name = (
                f"{erste[int(wuerfel.integers(0, len(erste)))]} "
                f"{zweite[int(wuerfel.integers(0, len(zweite)))]}"
            )
            if name not in vergeben:
                vergeben.add(name)
                break

        marke = hersteller[int(wuerfel.integers(0, len(hersteller)))]
        # Das Budget folgt den Ligen, in denen die vier Autos fahren
        # (GDD 10: bei der KI nur Anzeige).
        grundlage = sum(_siegpraemie(praemien, liga) for liga, _ in plaetze) / len(plaetze)
        faktor = 1.0 + float(wuerfel.uniform(-streuung, streuung))
        teams.append(
            Team(
                nummer=nummer,
                name=name,
                land=laender[int(wuerfel.integers(0, len(laender)))],
                hersteller=marke.name,
                herstellerfarbe=marke.farbe,
                farbe=_teamfarbe(marke.farbe, nummer, len(teamplaetze)),
                budget=int(round(grundlage * in_siegpraemien * faktor)),
                fahrer=tuple(nummer * je_team + n for n in range(len(plaetze))),
            )
        )
    del fahrer
    return tuple(teams)


def _siegpraemie(praemien: dict[int, int], liga: int) -> float:
    """Siegpraemie einer Liga; zwischen den Stuetzstellen logarithmisch."""
    if liga in praemien:
        return float(praemien[liga])
    stuetzen = sorted(praemien)
    werte = [praemien[s] for s in stuetzen]
    return float(np.exp(np.interp(liga, stuetzen, np.log(werte))))


# ---------------------------------------------------------------------------
# Anschluss ans Rennen
# ---------------------------------------------------------------------------
def starterfeld(welt: Welt, liga: int, reihenfolge: tuple[int, ...] | None = None):
    """Baut aus einer Liga der Welt das Starterfeld fuers Rennen.

    :param reihenfolge: Startaufstellung als Fahrernummern, Pole zuerst -
        ueblich das Ergebnis des Qualifyings. Ohne Angabe nach Staerke.
    """
    from rennmanager.kern.rennen import Teilnehmer

    fahrer = welt.liga(liga)
    if reihenfolge is None:
        geordnet = fahrer
    else:
        nach_nummer = {f.nummer: f for f in fahrer}
        fehlend = set(nach_nummer) - set(reihenfolge)
        if fehlend:
            raise WeltFehler(f"Die Aufstellung nennt nicht alle Fahrer der Liga {liga}")
        geordnet = tuple(nach_nummer[nummer] for nummer in reihenfolge)

    return tuple(
        Teilnehmer(
            auto=f.auto,
            startplatz=platz,
            # GDD 4: Autos als Punkte in Teamfarbe.
            farbe=welt.team_von(f).farbe,
            ist_spieler=f.ist_spieler,
        )
        for platz, f in enumerate(geordnet, start=1)
    )
