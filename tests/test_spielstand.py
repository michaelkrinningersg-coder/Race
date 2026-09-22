"""Tests fuer Speichern und Laden (GDD 13 und 15).

"Spielstand lokal speichern und laden", als SQLite-Datei. Ein Spielstand
muss alles zurueckbringen, was sich nicht aus der Konfiguration neu bilden
laesst - vor allem die Welt, denn der Editor darf sie aendern (GDD 15),
und dann stimmt eine aus dem Seed neu gewuerfelte Welt nicht mehr mit der
gespielten ueberein.
"""

from __future__ import annotations

import sqlite3

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import karriere as kk
from rennmanager.kern import popularitaet as kp
from rennmanager.kern import saison as sa
from rennmanager.kern import spielstand as sp
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern import wertung as wt
from rennmanager.kern.zufall import Seedquelle

SEED = 4711


@pytest.fixture(scope="module")
def k(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``."""
    return kleine_konfiguration


@pytest.fixture(scope="module")
def strecken(k):
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def gespielt(k, strecken) -> sp.Spielstand:
    """Eine Karriere, in der schon etwas passiert ist."""
    haupt = Seedquelle(SEED)
    welt = kw.erzeuge(k, haupt.zweig("welt"))
    karriere = kk.beginne(
        k, 2026, fahrer=tuple(f.nummer for f in welt.spielerfahrer)
    )
    for _ in range(70):
        karriere.tag_weiter()

    beliebtheit = kp.Popularitaet(k)
    beliebtheit.anfang(
        tuple(f.nummer for f in welt.fahrer), haupt.zweig("popularitaet")
    )
    lauf = sa.Saisonlauf(
        k, welt, haupt, jahr=2026, strecken=strecken, popularitaet=beliebtheit
    )
    lauf.fahre_rennen()
    karriere.kenntnis = lauf.kenntnis

    return sp.aus_teilen(
        seed=SEED,
        saisonjahr=2026,
        welt=lauf.welt,
        karriere=karriere,
        tabelle=lauf.tabelle,
        statistik=lauf.statistik,
        kenntnis=lauf.kenntnis,
        gefahrene_rennen=lauf.gefahren,
        popularitaet=beliebtheit,
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
    assert "2026" in text and str(SEED) in text


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


def test_ein_stand_vor_dem_umbau_wird_abgewiesen(k, gespielt, tmp_path):
    """Punkte 101 und 102: Alte Staende werden abgewiesen, nichts portiert."""
    pfad = sp.speichere(gespielt, tmp_path / "stand.sqlite")
    with sqlite3.connect(pfad) as verbindung:
        verbindung.execute("UPDATE kopf SET version = ?", (sp.MINDESTVERSION - 1,))
    with pytest.raises(sp.SpielstandFehler, match="neue Karriere"):
        sp.lade(k, pfad)


# --- Welt -----------------------------------------------------------------
def test_die_welt_kommt_unveraendert_zurueck(gespielt, geladen):
    assert geladen.welt == gespielt.welt
    assert geladen.welt.spieler.nummer == gespielt.welt.spieler.nummer
    assert geladen.seed == gespielt.seed


def test_eine_im_editor_geaenderte_welt_ueberlebt_das_speichern(k, gespielt, tmp_path):
    """Genau der Fall, in dem der Seed allein nicht mehr genuegt (GDD 15)."""
    erster = gespielt.welt.feld[0]
    geaendert = kw.mit_fahrerwerten(
        gespielt.welt,
        {erster.nummer: ({s: 1234 for s in erster.auto.werte}, dict(erster.auto.wetterwerte))},
    )
    stand = sp.aus_teilen(
        gespielt.seed,
        gespielt.saisonjahr,
        geaendert,
        gespielt.karriere,
        gespielt.tabelle,
        gespielt.statistik,
        gespielt.kenntnis,
    )
    zurueck = sp.lade(k, sp.speichere(stand, tmp_path / "geaendert.sqlite"))

    frisch = kw.erzeuge(k, Seedquelle(SEED).zweig("welt"))
    assert zurueck.welt == geaendert
    assert zurueck.welt != frisch
    assert set(zurueck.welt.fahrer[erster.nummer].auto.werte.values()) == {1234}


# --- Karriere -------------------------------------------------------------
def test_der_karrierestand_kommt_zurueck(gespielt, geladen):
    alt, neu = gespielt.karriere, geladen.karriere
    assert neu.heute == alt.heute
    assert neu.fahrer == alt.fahrer
    assert neu.fahrernummer == alt.fahrernummer
    assert neu.saison.jahr == alt.saison.jahr


# --- Wertung, Statistik, Kenntnis -----------------------------------------
def test_die_tabelle_kommt_zurueck(gespielt, geladen):
    assert geladen.tabelle.eintraege == gespielt.tabelle.eintraege
    assert geladen.tabelle.stand() == gespielt.tabelle.stand()


def test_die_statistik_kommt_zurueck(gespielt, geladen):
    assert geladen.statistik.rekorde == gespielt.statistik.rekorde
    assert geladen.statistik.qualirekorde == gespielt.statistik.qualirekorde
    assert geladen.statistik.karriere == gespielt.statistik.karriere
    assert geladen.statistik.saisonpunkte == gespielt.statistik.saisonpunkte
    assert geladen.statistik.historie == gespielt.statistik.historie


def test_die_fuehrungsrunden_ueberstehen_die_runde(gespielt, geladen):
    """Punkt 102: Sie stehen in der Karrierezeile und je Saison.

    Der Vergleich der ganzen Karrierezeile oben traegt sie schon mit;
    hier steht, dass wirklich etwas darin steht - sonst pruefte er nur,
    dass zweimal dieselbe Null herauskommt.
    """
    gefuehrt = {
        f: z.fuehrungsrunden
        for f, z in geladen.statistik.karriere.items()
        if z.fuehrungsrunden
    }
    assert gefuehrt, "Nach einem gefahrenen Rennen muss jemand gefuehrt haben"
    assert geladen.statistik.saisonfuehrung == gespielt.statistik.saisonfuehrung
    assert sum(gefuehrt.values()) == sum(geladen.statistik.saisonfuehrung.values())
    # Und der Nenner kam mit: Jeder Starter hat gefahrene Runden.
    nenner = {z.gefahrene_runden for z in geladen.statistik.karriere.values()}
    assert nenner == {sum(gefuehrt.values())}


def test_die_popularitaet_kommt_zurueck(gespielt, geladen):
    assert geladen.popularitaet.werte == pytest.approx(gespielt.popularitaet.werte)


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
        tabelle=geladen.tabelle,
        vorgefahren=geladen.gefahrene_rennen,
    )
    assert lauf.gefahren == geladen.gefahrene_rennen
    assert lauf.naechstes_rennen == geladen.gefahrene_rennen + 1
    lauf.fahre_rennen()
    assert lauf.gefahren == geladen.gefahrene_rennen + 1
    # Die Punkte aus dem geladenen Stand sind noch da und es kam etwas dazu.
    for eintrag in lauf.tabelle.stand():
        assert eintrag.rennen == 2


# --- Saisonwechsel (GDD 13) -----------------------------------------------
def gefuellte_tabelle(k, welt) -> wt.Tabelle:
    tabelle = wt.Tabelle()
    letzter = len(welt.fahrer)
    tabelle.verbuche(
        k,
        [
            wt.Rennergebnis(
                fahrer=f.nummer,
                rennplatz=platz,
                qualifyingplatz=platz,
                schnellste_runde=(platz == 2),
                ausgefallen=(platz == letzter),
            )
            for platz, f in enumerate(welt.feld, start=1)
        ],
    )
    return tabelle


@pytest.fixture(scope="module")
def nach_zwei_saisons(k, strecken) -> sp.Spielstand:
    """Ein Stand, in dem schon Saisons abgeschlossen sind."""
    welt = kw.erzeuge(k, Seedquelle(SEED).zweig("welt"))
    karriere = kk.beginne(
        k, 2026, fahrer=tuple(f.nummer for f in welt.spielerfahrer)
    )
    lauf = sa.Saisonlauf(
        k, welt, Seedquelle(SEED), jahr=2026, strecken=strecken, karriere=karriere
    )
    for _ in range(2):
        lauf.tabelle = gefuellte_tabelle(k, lauf.welt)
        lauf.vorgefahren = k.wert("kalender", "rennen_je_saison")
        lauf = lauf.naechste_saison()

    return sp.aus_teilen(
        seed=SEED,
        saisonjahr=lauf.jahr,
        welt=lauf.welt,
        karriere=karriere,
        tabelle=lauf.tabelle,
        statistik=lauf.statistik,
        kenntnis=lauf.kenntnis,
        gefahrene_rennen=lauf.gefahren,
    )


def test_die_historie_kommt_vollstaendig_zurueck(k, nach_zwei_saisons, tmp_path):
    """Je Saison die ganze Abschlusstabelle."""
    geladen = sp.lade(k, sp.speichere(nach_zwei_saisons, tmp_path / "saisons.sqlite"))
    assert geladen.saisonjahr == 2028
    assert geladen.statistik.saisons == (2026, 2027)
    assert geladen.statistik.historie == nach_zwei_saisons.statistik.historie

    abschluss = geladen.statistik.abschluss(2026)
    assert len(abschluss.zeilen) == k.wert("rennen", "autos")
    assert abschluss.zeilen[0].siege == 1
    assert abschluss.zeilen[1].schnellste_runden == 1
    assert abschluss.zeilen[-1].ausfaelle == 1


def test_der_kalender_des_dritten_jahres_kommt_zurueck(k, nach_zwei_saisons, tmp_path):
    geladen = sp.lade(k, sp.speichere(nach_zwei_saisons, tmp_path / "jahr.sqlite"))
    assert geladen.karriere.saison.jahr == 2028
    assert geladen.karriere.heute.year == 2028


def test_die_bilanzen_ueberstehen_speichern_und_laden(k, gespielt, tmp_path):
    pfad = sp.speichere(gespielt, tmp_path / "bilanz.sqlite")
    geladen = sp.lade(k, pfad)
    assert geladen.statistik.streckenbilanz == gespielt.statistik.streckenbilanz
    assert geladen.statistik.wetterbilanz == gespielt.statistik.wetterbilanz
    assert geladen.statistik.streckenbilanz


def test_die_fuehrungsrunden_je_strecke_ueberstehen_die_runde(gespielt, geladen):
    """Vorschlag 16: die zwei neuen Spalten beider Bilanztabellen.

    Der Vergleich oben traegt sie mit - er verglich aber auch zwei
    Nullen, wenn nichts darin stuende. Wie bei Punkt 102 steht deshalb
    hier, dass wirklich etwas ankommt.
    """
    for name, sammlung in (
        ("Strecke", geladen.statistik.streckenbilanz),
        ("Lage", geladen.statistik.wetterbilanz),
    ):
        gefuehrt = [b for b in sammlung.values() if b.fuehrungsrunden]
        assert gefuehrt, f"Je {name} muss jemand gefuehrt haben"
        # Und der Nenner kam mit, sonst gaebe es keinen Anteil.
        assert all(b.gefahrene_runden for b in sammlung.values())
        assert all(0 < b.fuehrungsanteil <= 1 for b in gefuehrt)


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
