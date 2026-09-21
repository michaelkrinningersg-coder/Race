"""Spielstand speichern und laden (GDD 15).

"Spielstand lokal speichern und laden" (GDD 13) in SQLite (GDD 15). Eine
Datei je Spielstand; der Spieler waehlt sie ueber den Dateidialog.

Gespeichert wird alles, was sich nicht aus der Konfiguration neu bilden
laesst:

=====================  ===================================================
Tabelle                Inhalt
=====================  ===================================================
``kopf``               Seed, Saisonjahr, Version
``fahrer``             die 50 Fahrer mit Stammdaten
``fahrerwert``         ihre Einzelwerte (GDD 5, 6 und 7)
``team``               die 25 Teams
``karriere``           der Tag des Spielers und sein gewaehlter Fahrer
``tabelle``            die Saisonwertung (GDD 13)
``rekord``             Rundenrekorde je Strecke (GDD 13)
``qualirekord``        Qualifyingrekorde je Strecke (Punkt 93)
``karrierezahl``       Siege, Podien, Poles, ... je Fahrer
``saisonpunkt``        Gesamtpunkte je Saison und Fahrer
``saisonverlauf``      Punkte je Rennwochenende der laufenden Saison
``streckenbilanz``     Summen je Fahrer und Strecke (Punkt 21)
``wetterbilanz``       Summen je Fahrer und Wetterlage (Punkt 23)
``historie``           Saisons, deren Abschluss vorliegt
``historiezeile``      die Abschlusstabelle dazu, Platz fuer Platz
``kenntnis``           Streckenkenntnis je Fahrer und Strecke (GDD 6)
``popularitaet``       Bekanntheitsgrad je Fahrer (Punkt 5)
=====================  ===================================================

Die Welt wird vollstaendig abgelegt statt aus dem Seed neu gewuerfelt:
Der Editor darf sie aendern (GDD 15), und dann stimmt die gewuerfelte
nicht mehr mit der gespielten ueberein.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern import popularitaet as kern_popularitaet
from rennmanager.kern import statistik as kern_statistik
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern.auto import Auto
from rennmanager.kern.welt import Fahrer, Team, Welt

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Wird mitgeschrieben, damit sich aeltere Staende erkennen lassen.
#
# Version 12: Der Umbau aus Punkt 101 - eine Liga zu 50 Autos statt zehn
# zu je 40, feste Staerken, keine Fahrerentwicklung, kein Transfermarkt,
# kein Geld und keine Erfahrung. Ein alter Stand traegt 400 Fahrer in 10
# Ligen, ein Konto, Sponsorenvertraege und Punkte aus einer Tabelle, die
# es nicht mehr gibt; umrechnen liesse sich das nur, indem man Zahlen
# erfindet. Entscheidung des Auftraggebers: abweisen, nichts portieren.
SPIELSTAND_VERSION = 12

# Der aelteste Stand, den dieses Programm noch lesen kann.
MINDESTVERSION = 12

# Punkt 17: Autosave und Schnellspeicher liegen an einem festen Ort,
# damit sie ohne Dateidialog geschrieben werden koennen.
ORDNER = ".rennmanager"
AUTOSAVE = "autosave.sqlite"
SCHNELLSPEICHER = "schnellspeicher.sqlite"

SCHEMA = """
CREATE TABLE kopf (
    version INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    saisonjahr INTEGER NOT NULL,
    gespeichert TEXT NOT NULL
);
CREATE TABLE team (
    nummer INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    land TEXT NOT NULL,
    hersteller TEXT NOT NULL,
    herstellerfarbe TEXT NOT NULL,
    farbe TEXT NOT NULL,
    fahrer TEXT NOT NULL
);
CREATE TABLE fahrer (
    nummer INTEGER PRIMARY KEY,
    vorname TEXT NOT NULL,
    nachname TEXT NOT NULL,
    land TEXT NOT NULL,
    geburtstag TEXT NOT NULL,
    team INTEGER NOT NULL,
    kuerzel TEXT NOT NULL,
    ist_spieler INTEGER NOT NULL
);
CREATE TABLE fahrerwert (
    fahrer INTEGER NOT NULL,
    schluessel TEXT NOT NULL,
    wert INTEGER NOT NULL,
    neben_matrix INTEGER NOT NULL,
    PRIMARY KEY (fahrer, schluessel)
);
CREATE TABLE karriere (
    heute TEXT NOT NULL,
    fahrernummer INTEGER NOT NULL
);
CREATE TABLE tabelle (
    fahrer INTEGER PRIMARY KEY,
    punkte INTEGER NOT NULL,
    platzierungen TEXT NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    rennen INTEGER NOT NULL
);
CREATE TABLE saisonstand (gefahrene_rennen INTEGER NOT NULL);
CREATE TABLE rekord (
    strecke TEXT PRIMARY KEY,
    zeit_ms INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    saison INTEGER NOT NULL,
    rennen INTEGER NOT NULL
);
CREATE TABLE qualirekord (
    strecke TEXT PRIMARY KEY,
    zeit_ms INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    saison INTEGER NOT NULL,
    rennen INTEGER NOT NULL
);
CREATE TABLE karrierezahl (
    fahrer INTEGER PRIMARY KEY,
    rennen INTEGER NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    punkte INTEGER NOT NULL
);
CREATE TABLE saisonpunkt (
    saison INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    PRIMARY KEY (saison, fahrer)
);
CREATE TABLE saisonverlauf (
    rennen INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    PRIMARY KEY (rennen, fahrer)
);
CREATE TABLE streckenbilanz (
    fahrer INTEGER NOT NULL,
    strecke TEXT NOT NULL,
    rennen INTEGER NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    bester_platz INTEGER NOT NULL,
    PRIMARY KEY (fahrer, strecke)
);
CREATE TABLE wetterbilanz (
    fahrer INTEGER NOT NULL,
    lage TEXT NOT NULL,
    rennen INTEGER NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    bester_platz INTEGER NOT NULL,
    PRIMARY KEY (fahrer, lage)
);
CREATE TABLE historie (saison INTEGER PRIMARY KEY);
CREATE TABLE historiezeile (
    saison INTEGER NOT NULL,
    platz INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    rennen INTEGER NOT NULL,
    PRIMARY KEY (saison, fahrer)
);
CREATE TABLE popularitaet (
    fahrer INTEGER PRIMARY KEY,
    wert REAL NOT NULL
);
CREATE TABLE kenntnis (
    fahrer INTEGER NOT NULL,
    strecke TEXT NOT NULL,
    runden REAL NOT NULL,
    PRIMARY KEY (fahrer, strecke)
);
"""


class SpielstandFehler(Exception):
    """Der Spielstand laesst sich nicht lesen oder nicht schreiben."""


@dataclass
class Spielstand:
    """Alles, was eine Karriere ausmacht (GDD 13 und 15)."""

    seed: int
    saisonjahr: int
    welt: Welt
    karriere: kern_karriere.Karriere
    tabelle: kern_wertung.Tabelle
    statistik: kern_statistik.Statistik
    kenntnis: kern_streckenkenntnis.Streckenkenntnis
    gefahrene_rennen: int = 0
    popularitaet: kern_popularitaet.Popularitaet | None = None


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------
def _zahlen(text: str) -> tuple[int, ...]:
    return tuple(int(teil) for teil in text.split(",") if teil)


def _text(zahlen) -> str:
    return ",".join(str(zahl) for zahl in zahlen)


def _datum(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


# ---------------------------------------------------------------------------
# Speichern
# ---------------------------------------------------------------------------
def spielstandordner() -> Path:
    """Wo Autosave und Schnellspeicher liegen (Punkt 17).

    Ein fester Ort im Benutzerverzeichnis: Fuer Staende, die ohne Dialog
    geschrieben werden, braucht es einen Platz, den das Spiel kennt. Die
    von Hand gespeicherten Staende bleiben davon unberuehrt - fuer die
    fragt der Dateidialog weiter nach.
    """
    return Path.home() / ORDNER


def autosave() -> Path:
    """Der eine Autosave-Stand, der ueberschrieben wird."""
    return spielstandordner() / AUTOSAVE


def schnellspeicher() -> Path:
    """Der eine Schnellspeicherstand (F5 und F9)."""
    return spielstandordner() / SCHNELLSPEICHER


def speichere(stand: Spielstand, pfad: Path | str) -> Path:
    """Schreibt einen Spielstand als SQLite-Datei (GDD 15)."""
    pfad = Path(pfad)
    if pfad.exists():
        pfad.unlink()
    pfad.parent.mkdir(parents=True, exist_ok=True)

    # ``with sqlite3.connect(...)`` committet nur, es *schliesst nicht*.
    # Unter Windows bleibt die Datei dann offen, und das ``unlink`` oben
    # schlaegt beim naechsten Speichern fehl - gemessen im Windows-Lauf:
    # Der zweite Autosave ueberschrieb den ersten nicht mehr.
    with contextlib.closing(sqlite3.connect(pfad)) as verbindung, verbindung:
        verbindung.executescript(SCHEMA)
        _schreibe_kopf(verbindung, stand)
        _schreibe_welt(verbindung, stand.welt)
        verbindung.execute(
            "INSERT INTO karriere VALUES (?, ?)",
            (stand.karriere.heute.isoformat(), stand.karriere.fahrernummer),
        )
        _schreibe_wertung(verbindung, stand.tabelle)
        _schreibe_statistik(verbindung, stand.statistik)
        verbindung.executemany(
            "INSERT INTO kenntnis VALUES (?, ?, ?)",
            [(f, s, r) for (f, s), r in stand.kenntnis.runden.items()],
        )
        if stand.popularitaet is not None:
            verbindung.executemany(
                "INSERT INTO popularitaet VALUES (?, ?)",
                list(stand.popularitaet.werte.items()),
            )
    return pfad


def _schreibe_kopf(verbindung: sqlite3.Connection, stand: Spielstand) -> None:
    verbindung.execute(
        "INSERT INTO kopf VALUES (?, ?, ?, ?)",
        (
            SPIELSTAND_VERSION,
            stand.seed,
            stand.saisonjahr,
            dt.datetime.now().isoformat(timespec="seconds"),
        ),
    )
    verbindung.execute("INSERT INTO saisonstand VALUES (?)", (stand.gefahrene_rennen,))


def _schreibe_welt(verbindung: sqlite3.Connection, welt: Welt) -> None:
    verbindung.executemany(
        "INSERT INTO team VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                t.nummer,
                t.name,
                t.land,
                t.hersteller,
                t.herstellerfarbe,
                t.farbe,
                _text(t.fahrer),
            )
            for t in welt.teams
        ],
    )
    verbindung.executemany(
        "INSERT INTO fahrer VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                f.nummer,
                f.vorname,
                f.nachname,
                f.land,
                f.geburtstag.isoformat(),
                f.team,
                f.auto.kuerzel,
                int(f.ist_spieler),
            )
            for f in welt.fahrer
        ],
    )
    werte = []
    for f in welt.fahrer:
        werte += [(f.nummer, s, w, 0) for s, w in f.auto.werte.items()]
        werte += [(f.nummer, s, w, 1) for s, w in f.auto.wetterwerte.items()]
    verbindung.executemany("INSERT INTO fahrerwert VALUES (?, ?, ?, ?)", werte)


def _schreibe_wertung(
    verbindung: sqlite3.Connection, tabelle: kern_wertung.Tabelle
) -> None:
    verbindung.executemany(
        "INSERT INTO tabelle VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                e.fahrer,
                e.punkte,
                _text(e.platzierungen),
                e.siege,
                e.podien,
                e.poles,
                e.schnellste_runden,
                e.ausfaelle,
                e.rennen,
            )
            for e in tabelle.eintraege.values()
        ],
    )


def _bilanzzeilen(sammlung: dict) -> list[tuple]:
    return [
        (
            nummer,
            name,
            b.rennen,
            b.siege,
            b.podien,
            b.poles,
            b.schnellste_runden,
            b.ausfaelle,
            b.punkte,
            b.bester_platz,
        )
        for (nummer, name), b in sammlung.items()
    ]


def _schreibe_statistik(
    verbindung: sqlite3.Connection, statistik: kern_statistik.Statistik
) -> None:
    for name, sammlung in (("rekord", statistik.rekorde), ("qualirekord", statistik.qualirekorde)):
        verbindung.executemany(
            f"INSERT INTO {name} VALUES (?, ?, ?, ?, ?)",
            [
                (r.strecke, r.zeit_ms, r.fahrer, r.saison, r.rennen)
                for r in sammlung.values()
            ],
        )
    verbindung.executemany(
        "INSERT INTO karrierezahl VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                z.fahrer,
                z.rennen,
                z.siege,
                z.podien,
                z.poles,
                z.schnellste_runden,
                z.ausfaelle,
                z.punkte,
            )
            for z in statistik.karriere.values()
        ],
    )
    verbindung.executemany(
        "INSERT INTO saisonpunkt VALUES (?, ?, ?)",
        [(s, f, p) for (s, f), p in statistik.saisonpunkte.items()],
    )
    verbindung.executemany(
        "INSERT INTO saisonverlauf VALUES (?, ?, ?)",
        [(r, f, p) for (r, f), p in statistik.saisonverlauf.items()],
    )
    verbindung.executemany(
        "INSERT INTO streckenbilanz VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _bilanzzeilen(statistik.streckenbilanz),
    )
    verbindung.executemany(
        "INSERT INTO wetterbilanz VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _bilanzzeilen(statistik.wetterbilanz),
    )
    verbindung.executemany(
        "INSERT INTO historie VALUES (?)",
        [(a.saison,) for a in statistik.historie],
    )
    verbindung.executemany(
        "INSERT INTO historiezeile VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                a.saison,
                z.platz,
                z.fahrer,
                z.punkte,
                z.siege,
                z.podien,
                z.poles,
                z.schnellste_runden,
                z.ausfaelle,
                z.rennen,
            )
            for a in statistik.historie
            for z in a.zeilen
        ],
    )


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------
def lade(konfiguration: Konfiguration, pfad: Path | str) -> Spielstand:
    """Liest einen Spielstand aus einer SQLite-Datei (GDD 15)."""
    pfad = Path(pfad)
    if not pfad.is_file():
        raise SpielstandFehler(f"Spielstand nicht gefunden: {pfad}")

    try:
        with contextlib.closing(sqlite3.connect(pfad)) as verbindung:
            verbindung.row_factory = sqlite3.Row
            kopf = verbindung.execute("SELECT * FROM kopf").fetchone()
            if kopf is None:
                raise SpielstandFehler(f"Kein Spielstand in {pfad}")
            if kopf["version"] > SPIELSTAND_VERSION:
                raise SpielstandFehler(
                    f"Spielstand hat Version {kopf['version']}, dieses Programm "
                    f"kennt hoechstens {SPIELSTAND_VERSION}"
                )
            if kopf["version"] < MINDESTVERSION:
                raise SpielstandFehler(
                    f"Spielstand hat Version {kopf['version']}. Mit Punkt 101 ist "
                    f"die Welt auf eine Liga mit 50 Autos, feste Staerken und "
                    f"ohne Geld, Erfahrung und Transfermarkt umgestellt worden; "
                    f"ein aelterer Stand laesst sich darauf nicht umrechnen, ohne "
                    f"Zahlen zu erfinden. Das Programm liest erst ab Version "
                    f"{MINDESTVERSION}. Bitte eine neue Karriere anfangen."
                )

            welt = _lies_welt(verbindung, kopf["seed"])
            karriere = _lies_karriere(konfiguration, welt, kopf["saisonjahr"])
            zeile = verbindung.execute("SELECT * FROM karriere").fetchone()
            if zeile is not None:
                karriere.heute = _datum(zeile["heute"])
                if zeile["fahrernummer"] in karriere.fahrer:
                    karriere.fahrernummer = zeile["fahrernummer"]

            kenntnis = kern_streckenkenntnis.Streckenkenntnis(konfiguration)
            for k in verbindung.execute("SELECT * FROM kenntnis"):
                kenntnis.setze(k["fahrer"], k["strecke"], k["runden"])
            karriere.kenntnis = kenntnis

            beliebtheit = kern_popularitaet.Popularitaet(konfiguration)
            for p in verbindung.execute("SELECT * FROM popularitaet"):
                beliebtheit.setze(p["fahrer"], p["wert"])

            gefahren = verbindung.execute("SELECT * FROM saisonstand").fetchone()
            return Spielstand(
                seed=kopf["seed"],
                saisonjahr=kopf["saisonjahr"],
                welt=welt,
                karriere=karriere,
                tabelle=_lies_wertung(verbindung),
                statistik=_lies_statistik(konfiguration, verbindung),
                kenntnis=kenntnis,
                gefahrene_rennen=gefahren["gefahrene_rennen"] if gefahren else 0,
                popularitaet=beliebtheit,
            )
    except sqlite3.DatabaseError as fehler:
        raise SpielstandFehler(f"Spielstand unlesbar: {fehler}") from fehler


def _lies_welt(verbindung: sqlite3.Connection, seed: int) -> Welt:
    werte: dict[int, dict[str, int]] = {}
    wetterwerte: dict[int, dict[str, int]] = {}
    for zeile in verbindung.execute("SELECT * FROM fahrerwert"):
        ziel = wetterwerte if zeile["neben_matrix"] else werte
        ziel.setdefault(zeile["fahrer"], {})[zeile["schluessel"]] = zeile["wert"]

    fahrer = tuple(
        Fahrer(
            nummer=z["nummer"],
            vorname=z["vorname"],
            nachname=z["nachname"],
            land=z["land"],
            geburtstag=_datum(z["geburtstag"]),
            team=z["team"],
            auto=Auto(
                kuerzel=z["kuerzel"],
                name=f"{z['vorname']} {z['nachname']}",
                werte=werte.get(z["nummer"], {}),
                wetterwerte=wetterwerte.get(z["nummer"], {}),
            ),
            ist_spieler=bool(z["ist_spieler"]),
        )
        for z in verbindung.execute("SELECT * FROM fahrer ORDER BY nummer")
    )
    teams = tuple(
        Team(
            nummer=z["nummer"],
            name=z["name"],
            land=z["land"],
            hersteller=z["hersteller"],
            herstellerfarbe=z["herstellerfarbe"],
            farbe=z["farbe"],
            fahrer=_zahlen(z["fahrer"]),
        )
        for z in verbindung.execute("SELECT * FROM team ORDER BY nummer")
    )
    return Welt(teams=teams, fahrer=fahrer, seed=seed)


def _lies_karriere(
    konfiguration: Konfiguration, welt: Welt, jahr: int
) -> kern_karriere.Karriere:
    return kern_karriere.beginne(
        konfiguration, jahr, fahrer=tuple(f.nummer for f in welt.spielerfahrer)
    )


def _lies_wertung(verbindung: sqlite3.Connection) -> kern_wertung.Tabelle:
    tabelle = kern_wertung.Tabelle()
    for z in verbindung.execute("SELECT * FROM tabelle"):
        tabelle.eintraege[z["fahrer"]] = kern_wertung.Eintrag(
            fahrer=z["fahrer"],
            punkte=z["punkte"],
            platzierungen=list(_zahlen(z["platzierungen"])),
            siege=z["siege"],
            podien=z["podien"],
            poles=z["poles"],
            schnellste_runden=z["schnellste_runden"],
            ausfaelle=z["ausfaelle"],
            rennen=z["rennen"],
        )
    return tabelle


def _lies_bilanz(zeile) -> kern_statistik.Bilanz:
    return kern_statistik.Bilanz(
        rennen=zeile["rennen"],
        siege=zeile["siege"],
        podien=zeile["podien"],
        poles=zeile["poles"],
        schnellste_runden=zeile["schnellste_runden"],
        ausfaelle=zeile["ausfaelle"],
        punkte=zeile["punkte"],
        bester_platz=zeile["bester_platz"],
    )


def _lies_statistik(
    konfiguration: Konfiguration, verbindung: sqlite3.Connection
) -> kern_statistik.Statistik:
    statistik = kern_statistik.Statistik(konfiguration)
    for name, ziel in (
        ("rekord", statistik.rekorde),
        ("qualirekord", statistik.qualirekorde),
    ):
        for z in verbindung.execute(f"SELECT * FROM {name}"):
            ziel[z["strecke"]] = kern_statistik.Rekord(
                strecke=z["strecke"],
                zeit_ms=z["zeit_ms"],
                fahrer=z["fahrer"],
                saison=z["saison"],
                rennen=z["rennen"],
            )
    for z in verbindung.execute("SELECT * FROM karrierezahl"):
        statistik.karriere[z["fahrer"]] = kern_statistik.Karrierezahlen(
            fahrer=z["fahrer"],
            rennen=z["rennen"],
            siege=z["siege"],
            podien=z["podien"],
            poles=z["poles"],
            schnellste_runden=z["schnellste_runden"],
            ausfaelle=z["ausfaelle"],
            punkte=z["punkte"],
        )
    for z in verbindung.execute("SELECT * FROM saisonpunkt"):
        statistik.saisonpunkte[(z["saison"], z["fahrer"])] = z["punkte"]
    for z in verbindung.execute("SELECT * FROM saisonverlauf"):
        statistik.saisonverlauf[(z["rennen"], z["fahrer"])] = z["punkte"]
    for z in verbindung.execute("SELECT * FROM streckenbilanz"):
        statistik.streckenbilanz[(z["fahrer"], z["strecke"])] = _lies_bilanz(z)
    for z in verbindung.execute("SELECT * FROM wetterbilanz"):
        statistik.wetterbilanz[(z["fahrer"], z["lage"])] = _lies_bilanz(z)

    zeilen: dict[int, list[kern_statistik.Saisonzeile]] = {}
    for z in verbindung.execute("SELECT * FROM historiezeile ORDER BY saison, platz"):
        zeilen.setdefault(z["saison"], []).append(
            kern_statistik.Saisonzeile(
                platz=z["platz"],
                fahrer=z["fahrer"],
                punkte=z["punkte"],
                siege=z["siege"],
                podien=z["podien"],
                poles=z["poles"],
                schnellste_runden=z["schnellste_runden"],
                ausfaelle=z["ausfaelle"],
                rennen=z["rennen"],
            )
        )
    for z in verbindung.execute("SELECT * FROM historie ORDER BY saison"):
        statistik.historie.append(
            kern_statistik.Saisonabschluss(
                saison=z["saison"], zeilen=tuple(zeilen.get(z["saison"], ()))
            )
        )
    return statistik


def beschreibe(pfad: Path | str) -> str:
    """Kurzbeschreibung eines Spielstands, ohne ihn ganz zu laden."""
    pfad = Path(pfad)
    try:
        with contextlib.closing(sqlite3.connect(pfad)) as verbindung:
            verbindung.row_factory = sqlite3.Row
            kopf = verbindung.execute("SELECT * FROM kopf").fetchone()
            karriere = verbindung.execute("SELECT heute FROM karriere").fetchone()
    except sqlite3.Error as fehler:
        raise SpielstandFehler(f"{pfad} laesst sich nicht lesen: {fehler}") from fehler
    if kopf is None:
        raise SpielstandFehler(f"{pfad} enthaelt keinen Spielstand")
    heute = karriere["heute"] if karriere else "?"
    return f"Saison {kopf['saisonjahr']}, Stand {heute}, Seed {kopf['seed']}"


def aus_teilen(
    seed: int,
    saisonjahr: int,
    welt: Welt,
    karriere: kern_karriere.Karriere,
    tabelle: kern_wertung.Tabelle,
    statistik: kern_statistik.Statistik,
    kenntnis: kern_streckenkenntnis.Streckenkenntnis,
    gefahrene_rennen: int = 0,
    popularitaet: kern_popularitaet.Popularitaet | None = None,
) -> Spielstand:
    """Baut einen Spielstand aus den Teilen, die das Fenster haelt.

    Die Teile werden nicht kopiert: Gespeichert wird lesend, und eine
    halbe Kopie waere gefaehrlicher als gar keine.
    """
    return Spielstand(
        seed=seed,
        saisonjahr=saisonjahr,
        welt=welt,
        karriere=karriere,
        tabelle=tabelle,
        statistik=statistik,
        kenntnis=kenntnis,
        gefahrene_rennen=gefahrene_rennen,
        popularitaet=popularitaet,
    )
