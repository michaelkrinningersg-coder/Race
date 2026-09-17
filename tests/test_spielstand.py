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

SEED = 4711
LIGA = 20


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


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
    verschoben = sa.wende_wechsel_an(
        gespielt.welt,
        (
            wt.Wechsel(gespielt.welt.liga(10)[0].nummer, 10, 9),
            wt.Wechsel(gespielt.welt.liga(9)[-1].nummer, 9, 10),
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
