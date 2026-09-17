"""Spielstand speichern und laden (GDD 15).

"Spielstand lokal speichern und laden" (GDD 13) in SQLite (GDD 15). Eine
Datei je Spielstand; der Spieler waehlt sie ueber den Dateidialog.

Gespeichert wird alles, was sich nicht aus der Konfiguration neu bilden
laesst:

=====================  ===================================================
Tabelle                Inhalt
=====================  ===================================================
``kopf``               Seed, Saisonjahr, Spielerliga, Version
``fahrer``             die 600 Fahrer mit Stammdaten und Liga
``fahrerwerte``        ihre Einzelwerte (GDD 5, 6 und 7)
``team``               die 150 Teams
``karriere``           Tag, Konto, Vertraege des Spielers
``karrierewerte``      die Werte des Spielers
``buchung``            was der Spieler an welchem Tag getan hat
``ereignis``           laufende Ereignisse (GDD 14)
``defekt``             offene Defekte (GDD 14)
``verlorener_tag``     Tage, die E29 gekostet hat
``meldung``            Ereignismeldungen, fuer die Anzeige
``tabelle``            die Saisonwertung aller Ligen (GDD 13)
``rekord``             Rundenrekorde je Strecke und Liga (GDD 13)
``karrierezahl``       Siege, Podien, Poles, ... je Fahrer
``saisonpunkt``        Gesamtpunkte je Saison, Liga und Fahrer
``historie``           Saison und Liga, deren Abschluss vorliegt
``historiezeile``      die Abschlusstabelle dazu, Platz fuer Platz
``kenntnis``           Streckenkenntnis je Fahrer und Strecke (GDD 6)
``popularitaet``       Bekanntheitsgrad je Fahrer (Punkt 5)
=====================  ===================================================

Die Welt wird vollstaendig abgelegt statt aus dem Seed neu gewuerfelt:
Nach dem ersten Auf- und Abstieg stimmt die gewuerfelte Welt nicht mehr
mit der gespielten ueberein.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern import popularitaet as kern_popularitaet
from rennmanager.kern import sponsoren as kern_sponsoren
from rennmanager.kern import statistik as kern_statistik
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.auto import Auto
from rennmanager.kern.entwicklung import Konto
from rennmanager.kern.welt import Fahrer, Team, Welt

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Wird mitgeschrieben, damit sich aeltere Staende erkennen lassen.
#
# Version 2: Die Historie traegt je Saison und Liga die vollstaendige
# Abschlusstabelle (Tabelle ``historiezeile``) statt nur Reihenfolge und
# Punkte. Staende der Version 1 werden weiter gelesen; die Zahlen, die es
# dort nicht gab, bleiben auf 0.
# Version 3: Die Popularitaet je Fahrer (Punkt 5) in der Tabelle
# ``popularitaet``. Aeltere Staende werden gelesen; die Popularitaet ist
# dort leer und wird beim naechsten Start neu gewuerfelt.
SPIELSTAND_VERSION = 3
HISTORIE_AB_VERSION = 2
POPULARITAET_AB_VERSION = 3

SCHEMA = """
CREATE TABLE kopf (
    version INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    saisonjahr INTEGER NOT NULL,
    spielerliga INTEGER NOT NULL,
    gespeichert TEXT NOT NULL
);
CREATE TABLE team (
    nummer INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    land TEXT NOT NULL,
    hersteller TEXT NOT NULL,
    herstellerfarbe TEXT NOT NULL,
    farbe TEXT NOT NULL,
    budget INTEGER NOT NULL,
    fahrer TEXT NOT NULL
);
CREATE TABLE fahrer (
    nummer INTEGER PRIMARY KEY,
    vorname TEXT NOT NULL,
    nachname TEXT NOT NULL,
    land TEXT NOT NULL,
    geburtstag TEXT NOT NULL,
    team INTEGER NOT NULL,
    liga INTEGER NOT NULL,
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
    liga INTEGER NOT NULL,
    fahrernummer INTEGER NOT NULL,
    geld INTEGER NOT NULL,
    erfahrung INTEGER NOT NULL,
    belegt TEXT NOT NULL
);
CREATE TABLE wettertopf (wetter TEXT PRIMARY KEY, erfahrung INTEGER NOT NULL);
CREATE TABLE karrierewert (schluessel TEXT PRIMARY KEY, wert INTEGER NOT NULL);
CREATE TABLE vertrag (
    platz TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    grundbetrag INTEGER NOT NULL,
    praemie_sieg INTEGER NOT NULL,
    praemie_top3 INTEGER NOT NULL,
    praemie_top10 INTEGER NOT NULL,
    laufzeit_rennen INTEGER NOT NULL,
    gueltig_bis_woche INTEGER NOT NULL,
    verbleibende_rennen INTEGER NOT NULL
);
CREATE TABLE buchung (
    datum TEXT NOT NULL,
    platz TEXT NOT NULL,
    faehigkeit TEXT NOT NULL,
    von INTEGER NOT NULL,
    nach INTEGER NOT NULL,
    geld INTEGER NOT NULL,
    erfahrung INTEGER NOT NULL
);
CREATE TABLE ereignisplan (datum TEXT NOT NULL, schluessel TEXT NOT NULL);
CREATE TABLE ereignis (
    schluessel TEXT NOT NULL,
    ausgeloest_am TEXT NOT NULL,
    rest INTEGER NOT NULL
);
CREATE TABLE defekt (schluessel TEXT NOT NULL);
CREATE TABLE verlorener_tag (datum TEXT PRIMARY KEY);
CREATE TABLE meldung (
    datum TEXT NOT NULL,
    schluessel TEXT NOT NULL,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    geld INTEGER NOT NULL,
    erfahrung INTEGER NOT NULL
);
CREATE TABLE tabelle (
    liga INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    platzierungen TEXT NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    rennen INTEGER NOT NULL,
    PRIMARY KEY (liga, fahrer)
);
CREATE TABLE saisonstand (gefahrene_rennen INTEGER NOT NULL);
CREATE TABLE rekord (
    strecke TEXT NOT NULL,
    liga INTEGER NOT NULL,
    zeit_ms INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    saison INTEGER NOT NULL,
    rennen INTEGER NOT NULL,
    PRIMARY KEY (strecke, liga)
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
    liga INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    PRIMARY KEY (saison, liga, fahrer)
);
CREATE TABLE historie (
    saison INTEGER NOT NULL,
    liga INTEGER NOT NULL,
    PRIMARY KEY (saison, liga)
);
CREATE TABLE historiezeile (
    saison INTEGER NOT NULL,
    liga INTEGER NOT NULL,
    platz INTEGER NOT NULL,
    fahrer INTEGER NOT NULL,
    punkte INTEGER NOT NULL,
    siege INTEGER NOT NULL,
    podien INTEGER NOT NULL,
    poles INTEGER NOT NULL,
    schnellste_runden INTEGER NOT NULL,
    ausfaelle INTEGER NOT NULL,
    rennen INTEGER NOT NULL,
    PRIMARY KEY (saison, liga, fahrer)
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
    tabellen: dict[int, kern_wertung.Tabelle]
    statistik: kern_statistik.Statistik
    kenntnis: kern_streckenkenntnis.Streckenkenntnis
    gefahrene_rennen: int = 0
    popularitaet: kern_popularitaet.Popularitaet | None = None

    @property
    def spielerliga(self) -> int:
        return self.karriere.liga


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
def speichere(stand: Spielstand, pfad: Path | str) -> Path:
    """Schreibt einen Spielstand als SQLite-Datei (GDD 15)."""
    pfad = Path(pfad)
    if pfad.exists():
        pfad.unlink()
    pfad.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(pfad) as verbindung:
        verbindung.executescript(SCHEMA)
        _schreibe_kopf(verbindung, stand)
        _schreibe_welt(verbindung, stand.welt)
        _schreibe_karriere(verbindung, stand.karriere)
        _schreibe_wertung(verbindung, stand)
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
        "INSERT INTO kopf VALUES (?, ?, ?, ?, ?)",
        (
            SPIELSTAND_VERSION,
            stand.seed,
            stand.saisonjahr,
            stand.spielerliga,
            dt.datetime.now().isoformat(timespec="seconds"),
        ),
    )
    verbindung.execute("INSERT INTO saisonstand VALUES (?)", (stand.gefahrene_rennen,))


def _schreibe_welt(verbindung: sqlite3.Connection, welt: Welt) -> None:
    verbindung.executemany(
        "INSERT INTO team VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                t.nummer,
                t.name,
                t.land,
                t.hersteller,
                t.herstellerfarbe,
                t.farbe,
                t.budget,
                _text(t.fahrer),
            )
            for t in welt.teams
        ],
    )
    verbindung.executemany(
        "INSERT INTO fahrer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                f.nummer,
                f.vorname,
                f.nachname,
                f.land,
                f.geburtstag.isoformat(),
                f.team,
                f.liga,
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


def _schreibe_karriere(verbindung: sqlite3.Connection, k: kern_karriere.Karriere) -> None:
    verbindung.execute(
        "INSERT INTO karriere VALUES (?, ?, ?, ?, ?, ?)",
        (
            k.heute.isoformat(),
            k.liga,
            k.fahrernummer,
            k.konto.geld,
            k.konto.erfahrung,
            ",".join(sorted(k.belegt)),
        ),
    )
    verbindung.executemany(
        "INSERT INTO wettertopf VALUES (?, ?)", list(k.konto.wetter_erfahrung.items())
    )
    verbindung.executemany(
        "INSERT INTO karrierewert VALUES (?, ?)", list(k.werte.items())
    )
    verbindung.executemany(
        "INSERT INTO vertrag VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                platz,
                v.angebot.name,
                v.angebot.grundbetrag,
                v.angebot.praemie_sieg,
                v.angebot.praemie_top3,
                v.angebot.praemie_top10,
                v.angebot.laufzeit_rennen,
                v.angebot.gueltig_bis_woche,
                v.verbleibende_rennen,
            )
            for platz, v in k.vertraege.items()
        ],
    )
    verbindung.executemany(
        "INSERT INTO buchung VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (b.datum.isoformat(), b.platz, b.faehigkeit, b.von, b.nach, b.geld, b.erfahrung)
            for b in k.buchungen
        ],
    )
    verbindung.executemany(
        "INSERT INTO ereignisplan VALUES (?, ?)",
        [
            (datum.isoformat(), schluessel)
            for datum, liste in k.ereignisplan.items()
            for schluessel in liste
        ],
    )
    verbindung.executemany(
        "INSERT INTO ereignis VALUES (?, ?, ?)",
        [(a.schluessel, a.ausgeloest_am.isoformat(), a.rest) for a in k.lage.aktive],
    )
    verbindung.executemany(
        "INSERT INTO defekt VALUES (?)", [(d["schluessel"],) for d in k.defekte]
    )
    verbindung.executemany(
        "INSERT INTO verlorener_tag VALUES (?)",
        [(datum.isoformat(),) for datum in sorted(k.verlorene_tage)],
    )
    verbindung.executemany(
        "INSERT INTO meldung VALUES (?, ?, ?, ?, ?, ?)",
        [
            (m.datum.isoformat(), m.schluessel, m.name, m.text, m.geld, m.erfahrung)
            for m in k.meldungen
        ],
    )


def _schreibe_wertung(verbindung: sqlite3.Connection, stand: Spielstand) -> None:
    zeilen = []
    for liga, tabelle in stand.tabellen.items():
        for eintrag in tabelle.eintraege.values():
            zeilen.append(
                (
                    liga,
                    eintrag.fahrer,
                    eintrag.punkte,
                    _text(eintrag.platzierungen),
                    eintrag.siege,
                    eintrag.podien,
                    eintrag.poles,
                    eintrag.schnellste_runden,
                    eintrag.ausfaelle,
                    eintrag.rennen,
                )
            )
    verbindung.executemany(
        "INSERT INTO tabelle VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", zeilen
    )


def _schreibe_statistik(
    verbindung: sqlite3.Connection, statistik: kern_statistik.Statistik
) -> None:
    verbindung.executemany(
        "INSERT INTO rekord VALUES (?, ?, ?, ?, ?, ?)",
        [
            (r.strecke, r.liga, r.zeit_ms, r.fahrer, r.saison, r.rennen)
            for r in statistik.rekorde.values()
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
        "INSERT INTO saisonpunkt VALUES (?, ?, ?, ?)",
        [(s, li, f, p) for (s, li, f), p in statistik.saisonpunkte.items()],
    )
    verbindung.executemany(
        "INSERT INTO historie VALUES (?, ?)",
        [(a.saison, a.liga) for a in statistik.historie],
    )
    verbindung.executemany(
        "INSERT INTO historiezeile VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                a.saison,
                a.liga,
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
    """Liest einen Spielstand zurueck (GDD 15)."""
    pfad = Path(pfad)
    if not pfad.is_file():
        raise SpielstandFehler(f"Spielstand nicht gefunden: {pfad}")

    try:
        with sqlite3.connect(pfad) as verbindung:
            verbindung.row_factory = sqlite3.Row
            kopf = verbindung.execute("SELECT * FROM kopf").fetchone()
            if kopf is None:
                raise SpielstandFehler(f"{pfad} enthaelt keinen Spielstand")
            if kopf["version"] > SPIELSTAND_VERSION:
                raise SpielstandFehler(
                    f"Der Spielstand hat Version {kopf['version']}, dieses Programm "
                    f"kennt hoechstens {SPIELSTAND_VERSION}"
                )

            welt = _lies_welt(verbindung, kopf["seed"])
            karriere = _lies_karriere(konfiguration, verbindung, kopf["saisonjahr"])
            tabellen = _lies_wertung(konfiguration, verbindung)
            statistik = _lies_statistik(konfiguration, verbindung, kopf["version"])
            kenntnis = kern_streckenkenntnis.Streckenkenntnis(
                konfiguration,
                {
                    (z["fahrer"], z["strecke"]): z["runden"]
                    for z in verbindung.execute("SELECT * FROM kenntnis")
                },
            )
            karriere.kenntnis = kenntnis
            popular = kern_popularitaet.Popularitaet(konfiguration)
            if kopf["version"] >= POPULARITAET_AB_VERSION:
                popular.werte = {
                    z["fahrer"]: z["wert"]
                    for z in verbindung.execute("SELECT * FROM popularitaet")
                }
            gefahren = verbindung.execute("SELECT * FROM saisonstand").fetchone()
    except sqlite3.Error as fehler:
        # Eine gueltige SQLite-Datei, die kein Spielstand ist, faellt hier
        # auf - der Spieler soll keinen Datenbankfehler zu sehen bekommen.
        raise SpielstandFehler(f"{pfad} ist kein Spielstand: {fehler}") from fehler

    return Spielstand(
        seed=kopf["seed"],
        saisonjahr=kopf["saisonjahr"],
        welt=welt,
        karriere=karriere,
        tabellen=tabellen,
        statistik=statistik,
        kenntnis=kenntnis,
        gefahrene_rennen=gefahren["gefahrene_rennen"] if gefahren else 0,
        popularitaet=popular,
    )


def _lies_welt(verbindung: sqlite3.Connection, seed: int) -> Welt:
    teams = tuple(
        Team(
            nummer=z["nummer"],
            name=z["name"],
            land=z["land"],
            hersteller=z["hersteller"],
            herstellerfarbe=z["herstellerfarbe"],
            farbe=z["farbe"],
            budget=z["budget"],
            fahrer=_zahlen(z["fahrer"]),
        )
        for z in verbindung.execute("SELECT * FROM team ORDER BY nummer")
    )

    werte: dict[int, dict[str, int]] = {}
    wetterwerte: dict[int, dict[str, int]] = {}
    for z in verbindung.execute("SELECT * FROM fahrerwert"):
        ziel = wetterwerte if z["neben_matrix"] else werte
        ziel.setdefault(z["fahrer"], {})[z["schluessel"]] = z["wert"]

    fahrer = tuple(
        Fahrer(
            nummer=z["nummer"],
            vorname=z["vorname"],
            nachname=z["nachname"],
            land=z["land"],
            geburtstag=_datum(z["geburtstag"]),
            team=z["team"],
            liga=z["liga"],
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
    return Welt(teams=teams, fahrer=fahrer, seed=seed)


def _lies_karriere(
    konfiguration: Konfiguration, verbindung: sqlite3.Connection, jahr: int
) -> kern_karriere.Karriere:
    z = verbindung.execute("SELECT * FROM karriere").fetchone()
    if z is None:
        raise SpielstandFehler("Der Spielstand enthaelt keine Karriere")

    werte = {
        e["schluessel"]: e["wert"] for e in verbindung.execute("SELECT * FROM karrierewert")
    }
    karriere = kern_karriere.beginne(
        konfiguration, jahr, z["liga"], werte, fahrernummer=z["fahrernummer"]
    )
    karriere.heute = _datum(z["heute"])
    karriere.belegt = {teil for teil in z["belegt"].split(",") if teil}

    toepfe = {
        e["wetter"]: e["erfahrung"] for e in verbindung.execute("SELECT * FROM wettertopf")
    }
    karriere.konto = Konto(
        geld=z["geld"], erfahrung=z["erfahrung"], wetter_erfahrung=toepfe
    )

    karriere.vertraege = {
        v["platz"]: kern_sponsoren.Vertrag(
            angebot=kern_sponsoren.Angebot(
                platz=v["platz"],
                name=v["name"],
                grundbetrag=v["grundbetrag"],
                praemie_sieg=v["praemie_sieg"],
                praemie_top3=v["praemie_top3"],
                praemie_top10=v["praemie_top10"],
                laufzeit_rennen=v["laufzeit_rennen"],
                gueltig_bis_woche=v["gueltig_bis_woche"],
            ),
            verbleibende_rennen=v["verbleibende_rennen"],
        )
        for v in verbindung.execute("SELECT * FROM vertrag")
    }

    karriere.buchungen = [
        kern_karriere.Tagesbuchung(
            datum=_datum(b["datum"]),
            platz=b["platz"],
            faehigkeit=b["faehigkeit"],
            von=b["von"],
            nach=b["nach"],
            geld=b["geld"],
            erfahrung=b["erfahrung"],
        )
        for b in verbindung.execute("SELECT * FROM buchung")
    ]

    plan: dict[dt.date, list[str]] = {}
    for e in verbindung.execute("SELECT * FROM ereignisplan"):
        plan.setdefault(_datum(e["datum"]), []).append(e["schluessel"])
    karriere.ereignisplan = {datum: tuple(liste) for datum, liste in plan.items()}

    karriere.lage = kern_ereignis.Lage(
        konfiguration,
        [
            _lies_ereignis(konfiguration, e["schluessel"], e["ausgeloest_am"], e["rest"])
            for e in verbindung.execute("SELECT * FROM ereignis")
        ],
    )
    karriere.defekte = [
        kern_zwischenfall.defekt_von(konfiguration, d["schluessel"])
        for d in verbindung.execute("SELECT * FROM defekt")
    ]
    karriere.verlorene_tage = {
        _datum(t["datum"]) for t in verbindung.execute("SELECT * FROM verlorener_tag")
    }
    karriere.meldungen = [
        kern_karriere.Meldung(
            datum=_datum(m["datum"]),
            schluessel=m["schluessel"],
            name=m["name"],
            text=m["text"],
            geld=m["geld"],
            erfahrung=m["erfahrung"],
        )
        for m in verbindung.execute("SELECT * FROM meldung")
    ]
    return karriere


def _lies_ereignis(
    konfiguration: Konfiguration, schluessel: str, ausgeloest_am: str, rest: int
) -> kern_ereignis.Aktiv:
    eintrag = kern_ereignis.eintrag(konfiguration, schluessel)
    return kern_ereignis.Aktiv(
        schluessel=schluessel,
        name=eintrag["name"],
        ausgeloest_am=_datum(ausgeloest_am),
        dauer=kern_ereignis.dauer_von(eintrag),
        rest=rest,
        wirkung=tuple(eintrag["wirkung"]),
    )


def _lies_wertung(
    konfiguration: Konfiguration, verbindung: sqlite3.Connection
) -> dict[int, kern_wertung.Tabelle]:
    tabellen = {
        liga: kern_wertung.Tabelle(liga)
        for liga in range(1, konfiguration.wert("ligen", "anzahl") + 1)
    }
    for z in verbindung.execute("SELECT * FROM tabelle"):
        tabellen.setdefault(z["liga"], kern_wertung.Tabelle(z["liga"])).eintraege[
            z["fahrer"]
        ] = kern_wertung.Eintrag(
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
    return tabellen


def _lies_statistik(
    konfiguration: Konfiguration, verbindung: sqlite3.Connection, version: int
) -> kern_statistik.Statistik:
    statistik = kern_statistik.Statistik(konfiguration)
    for z in verbindung.execute("SELECT * FROM rekord"):
        statistik.rekorde[(z["strecke"], z["liga"])] = kern_statistik.Rekord(
            strecke=z["strecke"],
            liga=z["liga"],
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
        statistik.saisonpunkte[(z["saison"], z["liga"], z["fahrer"])] = z["punkte"]
    statistik.historie = _lies_historie(verbindung, version)
    return statistik


def _lies_historie(
    verbindung: sqlite3.Connection, version: int
) -> list[kern_statistik.Saisonabschluss]:
    """Die Abschlusstabellen aller Saisons (GDD 13).

    Staende bis Version 1 kannten nur Reihenfolge und Punkte; die uebrigen
    Zahlen bleiben dort auf 0.
    """
    if version < HISTORIE_AB_VERSION:
        return [
            kern_statistik.Saisonabschluss(
                saison=z["saison"],
                liga=z["liga"],
                zeilen=tuple(
                    kern_statistik.Saisonzeile(fahrer=fahrer, platz=platz, punkte=punkte)
                    for platz, (fahrer, punkte) in enumerate(
                        zip(_zahlen(z["reihenfolge"]), _zahlen(z["punkte"]), strict=True),
                        start=1,
                    )
                ),
            )
            for z in verbindung.execute("SELECT * FROM historie ORDER BY saison, liga")
        ]

    zeilen: dict[tuple[int, int], list[kern_statistik.Saisonzeile]] = {}
    for z in verbindung.execute(
        "SELECT * FROM historiezeile ORDER BY saison, liga, platz"
    ):
        zeilen.setdefault((z["saison"], z["liga"]), []).append(
            kern_statistik.Saisonzeile(
                fahrer=z["fahrer"],
                platz=z["platz"],
                punkte=z["punkte"],
                siege=z["siege"],
                podien=z["podien"],
                poles=z["poles"],
                schnellste_runden=z["schnellste_runden"],
                ausfaelle=z["ausfaelle"],
                rennen=z["rennen"],
            )
        )
    return [
        kern_statistik.Saisonabschluss(
            saison=z["saison"],
            liga=z["liga"],
            zeilen=tuple(zeilen.get((z["saison"], z["liga"]), ())),
        )
        for z in verbindung.execute("SELECT * FROM historie ORDER BY saison, liga")
    ]


def beschreibe(pfad: Path | str) -> str:
    """Kurzbeschreibung eines Spielstands, ohne ihn ganz zu laden."""
    pfad = Path(pfad)
    try:
        with sqlite3.connect(pfad) as verbindung:
            verbindung.row_factory = sqlite3.Row
            kopf = verbindung.execute("SELECT * FROM kopf").fetchone()
            karriere = verbindung.execute("SELECT heute FROM karriere").fetchone()
    except sqlite3.Error as fehler:
        raise SpielstandFehler(f"{pfad} laesst sich nicht lesen: {fehler}") from fehler
    if kopf is None:
        raise SpielstandFehler(f"{pfad} enthaelt keinen Spielstand")
    heute = karriere["heute"] if karriere else "?"
    return (
        f"Saison {kopf['saisonjahr']}, Liga {kopf['spielerliga']}, Stand {heute}, "
        f"Seed {kopf['seed']}"
    )


def aus_teilen(
    seed: int,
    saisonjahr: int,
    welt: Welt,
    karriere: kern_karriere.Karriere,
    tabellen: dict[int, kern_wertung.Tabelle],
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
        tabellen=tabellen,
        statistik=statistik,
        kenntnis=kenntnis,
        gefahrene_rennen=gefahrene_rennen,
        popularitaet=popularitaet,
    )
