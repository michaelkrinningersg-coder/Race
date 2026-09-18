"""Tests fuer Speichern und Laden (GDD 13 und 15).

"Spielstand lokal speichern und laden", als SQLite-Datei. Ein Spielstand
muss alles zurueckbringen, was sich nicht aus der Konfiguration neu bilden
laesst - vor allem die Welt, denn nach dem ersten Auf- und Abstieg stimmt
eine aus dem Seed neu gewuerfelte Welt nicht mehr mit der gespielten
ueberein.
"""

from __future__ import annotations

import sqlite3

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import karriere as kk
from rennmanager.kern import saison as sa
from rennmanager.kern import spielstand as sp
from rennmanager.kern import sponsoren as ks
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern import wertung as wt
from rennmanager.kern.zufall import Seedquelle
from tests.conftest import KLEINE_LIGEN

SEED = 4711
LIGA = KLEINE_LIGEN


@pytest.fixture(scope="module")
def k(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``.

    Drei Ligen zu je vier Autos statt zwanzig zu je dreissig. Geprueft
    wird, *ob* die Logik stimmt - dafuer genuegt das kleine Feld, und ein
    Rennwochenende kostet 1,5 statt 54 Sekunden.
    """
    return kleine_konfiguration


@pytest.fixture(scope="module")
def strecken(k):
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def gespielt(k, strecken) -> sp.Spielstand:
    """Eine Karriere, in der schon etwas passiert ist."""
    haupt = Seedquelle(SEED)
    welt = kw.erzeuge(k, haupt.zweig("welt"), spielerliga=LIGA)
    spieler = welt.spieler
    werte = dict(spieler.auto.werte)
    werte.update(spieler.auto.wetterwerte)

    karriere = kk.beginne(
        k, 2026, LIGA, werte, seedquelle=haupt.zweig("karriere"), fahrernummer=spieler.nummer
    )
    for _ in range(70):
        karriere.tag_weiter()
    karriere.uebernimm_defekte(("X5", "X13"))
    karriere.kaufe("F1")
    karriere.verbuche_rennen(platz=12, ueberholmanoever=3)

    lauf = sa.Saisonlauf(k, welt, haupt, jahr=2026, strecken=strecken)
    lauf.fahre_rennen()
    karriere.kenntnis = lauf.kenntnis

    return sp.aus_teilen(
        seed=SEED,
        saisonjahr=2026,
        welt=welt,
        karriere=karriere,
        tabellen=lauf.tabellen,
        statistik=lauf.statistik,
        kenntnis=lauf.kenntnis,
        gefahrene_rennen=lauf.gefahren,
    )


@pytest.fixture(scope="module")
def datei(gespielt, tmp_path_factory):
    """Der einmal geschriebene Spielstand; Laden ist billiger als Spielen."""
    pfad = tmp_path_factory.mktemp("spielstand") / "karriere.sqlite"
    return sp.speichere(gespielt, pfad)


@pytest.fixture(scope="module")
def geladen(k, datei) -> sp.Spielstand:
    """Nur lesen - wer den Stand veraendert, laedt sich einen eigenen."""
    return sp.lade(k, datei)


# --- Datei ----------------------------------------------------------------
def test_gespeichert_wird_eine_sqlite_datei(k, gespielt, tmp_path):
    """GDD 15 nennt SQLite ausdruecklich."""
    pfad = sp.speichere(gespielt, tmp_path / "stand.sqlite")
    assert pfad.is_file()
    with sqlite3.connect(pfad) as verbindung:
        tabellen = {
            zeile[0]
            for zeile in verbindung.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"kopf", "fahrer", "karriere", "tabelle", "rekord", "kenntnis"} <= tabellen


def test_speichern_ueberschreibt_eine_alte_datei(k, gespielt, tmp_path):
    pfad = tmp_path / "stand.sqlite"
    pfad.write_bytes(b"kein Spielstand")
    sp.speichere(gespielt, pfad)
    assert sp.lade(k, pfad).seed == SEED


def test_beschreibung_ohne_vollen_ladevorgang(k, gespielt, tmp_path):
    pfad = sp.speichere(gespielt, tmp_path / "stand.sqlite")
    text = sp.beschreibe(pfad)
    assert "2026" in text and str(SEED) in text and f"Liga {LIGA}" in text


def test_fehlende_datei_faellt_auf(k, tmp_path):
    with pytest.raises(sp.SpielstandFehler, match="nicht gefunden"):
        sp.lade(k, tmp_path / "gibtesnicht.sqlite")


def test_fremde_datei_faellt_auf(k, tmp_path):
    pfad = tmp_path / "fremd.sqlite"
    with sqlite3.connect(pfad) as verbindung:
        verbindung.execute("CREATE TABLE irgendwas (a INTEGER)")
    with pytest.raises(sp.SpielstandFehler):
        sp.lade(k, pfad)
    with pytest.raises(sp.SpielstandFehler):
        sp.beschreibe(pfad)


def test_neuere_version_faellt_auf(k, gespielt, tmp_path):
    pfad = sp.speichere(gespielt, tmp_path / "stand.sqlite")
    with sqlite3.connect(pfad) as verbindung:
        verbindung.execute("UPDATE kopf SET version = ?", (sp.SPIELSTAND_VERSION + 1,))
    with pytest.raises(sp.SpielstandFehler, match="Version"):
        sp.lade(k, pfad)


# --- Welt -----------------------------------------------------------------
def test_die_welt_kommt_unveraendert_zurueck(gespielt, geladen):
    """Nach dem ersten Auf- und Abstieg laesst sie sich nicht mehr aus dem
    Seed neu wuerfeln - sie muss also vollstaendig in der Datei stehen."""
    assert geladen.welt == gespielt.welt
    assert geladen.welt.spieler.nummer == gespielt.welt.spieler.nummer
    assert geladen.seed == gespielt.seed


def test_eine_verschobene_liga_ueberlebt_das_speichern(k, gespielt, tmp_path):
    """Genau der Fall, in dem der Seed allein nicht mehr genuegt."""
    # Die beiden untersten Ligen der Welt - in der kleinen Testwelt gibt
    # es Liga 10 nicht.
    unten = k.wert("ligen", "anzahl")
    verschoben = sa.wende_wechsel_an(
        gespielt.welt,
        (
            wt.Wechsel(gespielt.welt.liga(unten)[0].nummer, unten, unten - 1),
            wt.Wechsel(gespielt.welt.liga(unten - 1)[-1].nummer, unten - 1, unten),
        ),
    )
    stand = sp.aus_teilen(
        gespielt.seed,
        gespielt.saisonjahr,
        verschoben,
        gespielt.karriere,
        gespielt.tabellen,
        gespielt.statistik,
        gespielt.kenntnis,
    )
    pfad = sp.speichere(stand, tmp_path / "verschoben.sqlite")
    zurueck = sp.lade(k, pfad)

    frisch = kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=LIGA)
    assert zurueck.welt == verschoben
    assert zurueck.welt != frisch


# --- Karriere -------------------------------------------------------------
def test_der_karrierestand_kommt_zurueck(gespielt, geladen):
    alt, neu = gespielt.karriere, geladen.karriere
    assert neu.heute == alt.heute
    assert neu.liga == alt.liga
    assert neu.fahrernummer == alt.fahrernummer
    assert neu.konto == alt.konto
    assert neu.werte == alt.werte
    assert neu.buchungen == alt.buchungen
    assert neu.ereignisplan == alt.ereignisplan


def test_laufende_ereignisse_kommen_zurueck(gespielt, geladen):
    alt = {(a.schluessel, a.rest, a.ausgeloest_am) for a in gespielt.karriere.lage.aktive}
    neu = {(a.schluessel, a.rest, a.ausgeloest_am) for a in geladen.karriere.lage.aktive}
    assert neu == alt
    # Und sie wirken auch wieder.
    assert geladen.karriere.faktoren() == gespielt.karriere.faktoren()


def test_offene_defekte_kommen_zurueck(gespielt, geladen):
    assert geladen.karriere.defekte == gespielt.karriere.defekte
    assert geladen.karriere.offene_reparaturen == gespielt.karriere.offene_reparaturen


def test_verlorene_tage_und_meldungen_kommen_zurueck(gespielt, geladen):
    assert geladen.karriere.verlorene_tage == gespielt.karriere.verlorene_tage
    assert geladen.karriere.meldungen == gespielt.karriere.meldungen


def test_vertraege_kommen_zurueck(k, gespielt, tmp_path):
    karriere = kk.kopiere(gespielt.karriere)
    angebote = ks.wuerfle_angebote(k, LIGA, 10, Seedquelle(1))
    erstes = next(iter(angebote.values()))[0]
    karriere.unterschreibe(erstes)

    stand = sp.aus_teilen(
        gespielt.seed,
        gespielt.saisonjahr,
        gespielt.welt,
        karriere,
        gespielt.tabellen,
        gespielt.statistik,
        gespielt.kenntnis,
    )
    zurueck = sp.lade(k, sp.speichere(stand, tmp_path / "vertrag.sqlite"))
    assert zurueck.karriere.vertraege == karriere.vertraege


# --- Wertung, Statistik, Kenntnis -----------------------------------------
def test_die_tabellen_kommen_zurueck(gespielt, geladen):
    for liga, tabelle in gespielt.tabellen.items():
        assert geladen.tabellen[liga].eintraege == tabelle.eintraege
        assert geladen.tabellen[liga].stand() == tabelle.stand()


def test_die_statistik_kommt_zurueck(gespielt, geladen):
    assert geladen.statistik.rekorde == gespielt.statistik.rekorde
    assert geladen.statistik.karriere == gespielt.statistik.karriere
    assert geladen.statistik.saisonpunkte == gespielt.statistik.saisonpunkte
    assert geladen.statistik.historie == gespielt.statistik.historie


def test_die_streckenkenntnis_kommt_zurueck(gespielt, geladen):
    assert geladen.kenntnis.runden == pytest.approx(gespielt.kenntnis.runden)
    assert geladen.gefahrene_rennen == gespielt.gefahrene_rennen


def test_ein_geladener_stand_laesst_sich_weiterspielen(k, datei, strecken):
    """Der eigentliche Zweck: nach dem Laden geht es weiter."""
    geladen = sp.lade(k, datei)
    karriere = geladen.karriere
    vorher = karriere.heute
    karriere.tag_weiter()
    assert karriere.heute > vorher

    lauf = sa.Saisonlauf(
        k,
        geladen.welt,
        Seedquelle(geladen.seed),
        jahr=geladen.saisonjahr,
        strecken=strecken,
        statistik=geladen.statistik,
        kenntnis=geladen.kenntnis,
        tabellen=geladen.tabellen,
        vorgefahren=geladen.gefahrene_rennen,
    )
    assert lauf.gefahren == geladen.gefahrene_rennen
    assert lauf.naechstes_rennen == geladen.gefahrene_rennen + 1
    lauf.fahre_rennen()
    assert lauf.gefahren == geladen.gefahrene_rennen + 1
    # Die Punkte aus dem geladenen Stand sind noch da und es kam etwas dazu.
    for eintrag in lauf.tabelle(LIGA).stand():
        assert eintrag.rennen == 2


# --- Saisonwechsel (GDD 13) -----------------------------------------------
def mit_historie(k, welt, strecken, jahre: int = 2) -> sp.Spielstand:
    """Ein Stand, in dem schon Saisons abgeschlossen sind."""
    haupt = Seedquelle(SEED)
    spieler = welt.spieler
    werte = dict(spieler.auto.werte)
    werte.update(spieler.auto.wetterwerte)
    karriere = kk.beginne(
        k, 2026, spieler.liga, werte, fahrernummer=spieler.nummer
    )
    lauf = sa.Saisonlauf(k, welt, haupt, jahr=2026, strecken=strecken, karriere=karriere)
    for _ in range(jahre):
        lauf.tabellen = {
            liga: gefuellte_tabelle(k, lauf.welt, liga)
            for liga in range(1, k.wert("ligen", "anzahl") + 1)
        }
        lauf.vorgefahren = k.wert("kalender", "rennen_je_saison")
        lauf = lauf.naechste_saison()

    return sp.aus_teilen(
        seed=SEED,
        saisonjahr=lauf.jahr,
        welt=lauf.welt,
        karriere=karriere,
        tabellen=lauf.tabellen,
        statistik=lauf.statistik,
        kenntnis=lauf.kenntnis,
        gefahrene_rennen=lauf.gefahren,
    )


def gefuellte_tabelle(k, welt, liga: int) -> wt.Tabelle:
    tabelle = wt.Tabelle(liga)
    tabelle.verbuche(
        k,
        [
            wt.Rennergebnis(
                fahrer=f.nummer,
                rennplatz=platz,
                qualifyingplatz=platz,
                schnellste_runde=(platz == 2),
                ausgefallen=(platz > 28),
            )
            for platz, f in enumerate(welt.liga(liga), start=1)
        ],
    )
    return tabelle


@pytest.fixture(scope="module")
def nach_zwei_saisons(k, strecken) -> sp.Spielstand:
    welt = kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=LIGA)
    return mit_historie(k, welt, strecken)


@pytest.mark.skip(
    reason="Punkt 77: Saisonwechsel wird erst geprueft, wenn eine "
    "einzelne Saison sauber steht. Entscheidung des Auftraggebers."
)
def test_die_historie_kommt_vollstaendig_zurueck(k, nach_zwei_saisons, tmp_path):
    """Version 2: je Saison und Liga die ganze Abschlusstabelle."""
    geladen = sp.lade(k, sp.speichere(nach_zwei_saisons, tmp_path / "saisons.sqlite"))
    assert geladen.saisonjahr == 2028
    assert geladen.statistik.saisons == (2026, 2027)
    assert geladen.statistik.historie == nach_zwei_saisons.statistik.historie

    abschluss = geladen.statistik.abschluss(2026, LIGA)
    assert len(abschluss.zeilen) == k.wert("ligen", "autos_je_liga")
    assert abschluss.zeilen[0].siege == 1
    assert abschluss.zeilen[1].schnellste_runden == 1
    assert abschluss.zeilen[-1].ausfaelle == 1


@pytest.mark.skip(
    reason="Punkt 77: Saisonwechsel wird erst geprueft, wenn eine "
    "einzelne Saison sauber steht. Entscheidung des Auftraggebers."
)
def test_der_kalender_des_dritten_jahres_kommt_zurueck(k, nach_zwei_saisons, tmp_path):
    geladen = sp.lade(k, sp.speichere(nach_zwei_saisons, tmp_path / "jahr.sqlite"))
    assert geladen.karriere.saison.jahr == 2028
    assert geladen.karriere.heute.year == 2028


def mache_zu_version_1(pfad) -> None:
    """Baut einen Stand auf das Schema der Version 1 zurueck.

    Damit laesst sich pruefen, dass aeltere Staende weiter lesbar sind -
    und nicht nur, dass der Code eine Fallunterscheidung hat.
    """
    with sqlite3.connect(pfad) as verbindung:
        verbindung.row_factory = sqlite3.Row
        zeilen = list(
            verbindung.execute(
                "SELECT saison, liga, fahrer, punkte FROM historiezeile "
                "ORDER BY saison, liga, platz"
            )
        )
        alt: dict[tuple[int, int], tuple[list[int], list[int]]] = {}
        for z in zeilen:
            fahrer, punkte = alt.setdefault((z["saison"], z["liga"]), ([], []))
            fahrer.append(z["fahrer"])
            punkte.append(z["punkte"])

        verbindung.execute("DROP TABLE historiezeile")
        verbindung.execute("DROP TABLE historie")
        verbindung.execute(
            "CREATE TABLE historie (saison INTEGER NOT NULL, liga INTEGER NOT NULL, "
            "reihenfolge TEXT NOT NULL, punkte TEXT NOT NULL, PRIMARY KEY (saison, liga))"
        )
        verbindung.executemany(
            "INSERT INTO historie VALUES (?, ?, ?, ?)",
            [
                (saison, liga, ",".join(map(str, f)), ",".join(map(str, p)))
                for (saison, liga), (f, p) in alt.items()
            ],
        )
        verbindung.execute("UPDATE kopf SET version = 1")


@pytest.mark.skip(
    reason="Punkt 77: Saisonwechsel wird erst geprueft, wenn eine "
    "einzelne Saison sauber steht. Entscheidung des Auftraggebers."
)
def test_ein_stand_der_version_1_bleibt_lesbar(k, nach_zwei_saisons, tmp_path):
    pfad = sp.speichere(nach_zwei_saisons, tmp_path / "alt.sqlite")
    mache_zu_version_1(pfad)

    geladen = sp.lade(k, pfad)
    neu = nach_zwei_saisons.statistik.abschluss(2026, LIGA)
    alt = geladen.statistik.abschluss(2026, LIGA)
    assert alt.reihenfolge == neu.reihenfolge
    assert alt.punkte == neu.punkte
    assert alt.platz_von(alt.meister) == 1
    # Die Zahlen, die es in Version 1 nicht gab, bleiben auf 0.
    assert alt.zeilen[0].siege == 0
    assert alt.zeilen[0].rennen == 0


def mache_zu_version_4(pfad) -> None:
    """Baut einen Stand auf das Schema der Version 4 zurueck (ohne Bilanzen)."""
    with sqlite3.connect(pfad) as verbindung:
        verbindung.execute("DROP TABLE streckenbilanz")
        verbindung.execute("DROP TABLE wetterbilanz")
        verbindung.execute("UPDATE kopf SET version = 4")


def test_ein_stand_der_version_4_bleibt_lesbar(k, gespielt, tmp_path):
    """Punkt 21 und 23 kamen erst mit Version 5 dazu."""
    pfad = sp.speichere(gespielt, tmp_path / "v4.sqlite")
    assert gespielt.statistik.streckenbilanz
    mache_zu_version_4(pfad)

    geladen = sp.lade(k, pfad)
    # Alles andere steht noch; die Bilanzen fangen bei null an, weil die
    # einzelnen Rennen von damals nirgends aufgehoben sind.
    assert geladen.statistik.streckenbilanz == {}
    assert geladen.statistik.wetterbilanz == {}
    assert geladen.statistik.karriere.keys() == gespielt.statistik.karriere.keys()
    assert geladen.gefahrene_rennen == gespielt.gefahrene_rennen


def test_die_bilanzen_ueberstehen_speichern_und_laden(k, gespielt, tmp_path):
    pfad = sp.speichere(gespielt, tmp_path / "bilanz.sqlite")
    geladen = sp.lade(k, pfad)
    assert geladen.statistik.streckenbilanz == gespielt.statistik.streckenbilanz
    assert geladen.statistik.wetterbilanz == gespielt.statistik.wetterbilanz
    assert geladen.statistik.streckenbilanz


def test_keine_verbindung_bleibt_offen(k, gespielt, tmp_path, monkeypatch):
    """Sonst laesst sich der Stand unter Windows nicht ueberschreiben.

    ``with sqlite3.connect(...)`` committet nur, es *schliesst nicht*.
    Unter Linux stoert das nicht - eine offene Datei laesst sich dort
    loeschen. Unter Windows nicht: Gemessen im Windows-Lauf schrieb der
    zweite Autosave die Datei nicht mehr, weil das ``unlink`` am Anfang
    von ``speichere`` an der noch offenen Verbindung scheiterte.

    Der Test zaehlt deshalb selbst mit, statt sich auf das Betriebssystem
    zu verlassen.
    """
    offen = []
    echt = sqlite3.connect

    def zaehlend(*args, **kw):
        verbindung = echt(*args, **kw)
        offen.append(verbindung)
        return verbindung

    monkeypatch.setattr(sp.sqlite3, "connect", zaehlend)

    pfad = sp.speichere(gespielt, tmp_path / "offen.sqlite")
    sp.lade(k, pfad)
    sp.beschreibe(pfad)

    assert offen, "Der Test greift nur, wenn ueberhaupt verbunden wurde"
    for verbindung in offen:
        with pytest.raises(sqlite3.ProgrammingError):
            verbindung.execute("SELECT 1")


def test_ein_stand_laesst_sich_mehrfach_ueberschreiben(k, gespielt, tmp_path):
    """Genau das tut der Autosave nach jedem Tag (Punkt 17)."""
    pfad = tmp_path / "wieder.sqlite"
    sp.speichere(gespielt, pfad)
    erst = sp.lade(k, pfad)
    # Lesen und danach erneut schreiben - der Fall, der unter Windows brach.
    sp.speichere(erst, pfad)
    sp.lade(k, pfad)
    sp.speichere(gespielt, pfad)
    assert sp.lade(k, pfad).gefahrene_rennen == gespielt.gefahrene_rennen


# --- Autosave und Schnellspeicher (Punkt 17) ------------------------------
def test_die_festen_staende_liegen_an_einem_ort(spielstandordner) -> None:
    """Ohne Dialog geschrieben heisst: an einem Ort, den das Spiel kennt."""
    assert sp.autosave().parent == spielstandordner
    assert sp.schnellspeicher().parent == spielstandordner
    assert sp.autosave() != sp.schnellspeicher()
    assert sp.autosave().name == sp.AUTOSAVE
    assert sp.schnellspeicher().name == sp.SCHNELLSPEICHER


def test_der_ordner_liegt_im_benutzerverzeichnis(spielstandordner) -> None:
    """Ein fester Ort unter ``~/.rennmanager`` - kein Dialog noetig."""
    assert spielstandordner.name == sp.ORDNER == ".rennmanager"
    assert spielstandordner.parent == sp.Path.home()
