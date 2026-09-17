"""Tests fuer den Saisonlauf (GDD 13).

Ein Rennwochenende umfasst alle 20 Ligen; im Schnellmodus dauert es
wenige Sekunden, mit ausfuehrlich gefahrener Spielerliga deutlich
laenger. Die teuren Laeufe stehen deshalb in Fixtures mit
``scope="module"`` und werden von mehreren Tests genutzt.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import ereignis as ev
from rennmanager.kern import karriere as kk
from rennmanager.kern import saison as sa
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern import wertung as wt
from rennmanager.kern.zufall import Seedquelle

SEED = 12
LIGA = 20


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def welt(k) -> kw.Welt:
    return kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=LIGA)


def neuer_lauf(k, welt, strecken, seed: int = SEED) -> sa.Saisonlauf:
    return sa.Saisonlauf(k, welt, Seedquelle(seed), jahr=2026, strecken=strecken)


@pytest.fixture(scope="module")
def lauf(k, welt, strecken) -> sa.Saisonlauf:
    """Ein Saisonlauf mit einem gefahrenen Wochenende im Schnellmodus."""
    lauf = neuer_lauf(k, welt, strecken)
    lauf.fahre_rennen()
    return lauf


@pytest.fixture(scope="module")
def wochenende(lauf) -> sa.Wochenende:
    return lauf.wochenenden[0]


# --- Kalender und Stand ---------------------------------------------------
def test_die_saison_folgt_dem_streckenkalender(k, welt, strecken):
    lauf = neuer_lauf(k, welt, strecken)
    assert lauf.rennen_je_saison == k.wert("kalender", "rennen_je_saison")
    assert lauf.naechstes_rennen == 1
    assert lauf.strecke_zu(1).name == k.strecken[0]["name"]
    assert lauf.strecke_zu(lauf.rennen_je_saison).name == k.strecken[-1]["name"]
    with pytest.raises(sa.SaisonFehler):
        lauf.strecke_zu(lauf.rennen_je_saison + 1)


def test_zu_wenige_strecken_fallen_auf(k, welt, strecken):
    with pytest.raises(sa.SaisonFehler, match="Strecken"):
        sa.Saisonlauf(k, welt, Seedquelle(SEED), strecken=strecken[:5])


def test_nach_dem_ersten_rennen_steht_der_stand(lauf, wochenende):
    assert lauf.gefahren == 1
    assert lauf.naechstes_rennen == 2
    assert not lauf.ist_fertig
    assert wochenende.nummer == 1
    assert wochenende.strecke == lauf.strecke_zu(1).name


# --- Wertung ueber alle Ligen ---------------------------------------------
def test_jedes_wochenende_wertet_alle_ligen(k, lauf, wochenende):
    ligen = k.wert("ligen", "anzahl")
    autos = k.wert("ligen", "autos_je_liga")
    assert sorted(wochenende.ligen) == list(range(1, ligen + 1))
    for liga in range(1, ligen + 1):
        ergebnis = wochenende.liga(liga)
        assert len(ergebnis.ergebnisse) == autos
        assert [e.rennplatz for e in ergebnis.ergebnisse] == list(range(1, autos + 1))
        assert len(lauf.tabelle(liga).eintraege) == autos
    wt.pruefe_ligastaerken(k, lauf.tabellen)


def test_die_ergebnisse_nennen_weltweite_fahrernummern(lauf, wochenende, welt):
    """Ohne diese Uebersetzung stuenden 20 Ligen mit denselben Nummern
    in derselben Tabelle."""
    for liga, ergebnis in wochenende.ligen.items():
        nummern = [e.fahrer for e in ergebnis.ergebnisse]
        assert sorted(nummern) == sorted(f.nummer for f in welt.liga(liga))
        assert all(welt.fahrer[nummer].liga == liga for nummer in nummern)


def test_punkte_stimmen_mit_der_wertung_ueberein(k, lauf, wochenende):
    """Nach einem Rennen muss die Tabelle genau die Wochenendpunkte zeigen."""
    ergebnis = wochenende.liga(LIGA)
    tabelle = lauf.tabelle(LIGA)
    for einzeln in ergebnis.ergebnisse:
        eintrag = tabelle.eintraege[einzeln.fahrer]
        assert eintrag.punkte == wt.punkte_fuer(k, einzeln)
        assert eintrag.rennen == 1


def test_ein_zweites_rennen_summiert_sich(k, welt, strecken):
    lauf = neuer_lauf(k, welt, strecken)
    lauf.fahre_rennen()
    erste = {f: e.punkte for f, e in lauf.tabelle(LIGA).eintraege.items()}
    lauf.fahre_rennen()
    assert lauf.gefahren == 2
    assert lauf.wochenenden[1].strecke == lauf.strecke_zu(2).name
    for fahrer, eintrag in lauf.tabelle(LIGA).eintraege.items():
        assert eintrag.rennen == 2
        assert eintrag.punkte >= erste[fahrer]


# --- Zufall ---------------------------------------------------------------
def test_gleicher_seed_gleiche_saison(k, welt, strecken, wochenende):
    zweiter = neuer_lauf(k, welt, strecken)
    zweiter.fahre_rennen()
    assert zweiter.wochenenden[0].ligen == wochenende.ligen


def test_anderer_seed_andere_saison(k, welt, strecken, wochenende):
    anderer = neuer_lauf(k, welt, strecken, seed=SEED + 1)
    anderer.fahre_rennen()
    assert anderer.wochenenden[0].ligen != wochenende.ligen


# --- Ausfuehrliche Liga ---------------------------------------------------
@pytest.fixture(scope="module")
def ausfuehrlich(k, welt, strecken) -> sa.Saisonlauf:
    """Dasselbe Wochenende, aber die Spielerliga voll simuliert."""
    lauf = neuer_lauf(k, welt, strecken)
    lauf.fahre_rennen(ausfuehrliche_liga=LIGA)
    return lauf


def test_ausfuehrliche_liga_liefert_einen_abspielbaren_verlauf(k, ausfuehrlich):
    wochenende = ausfuehrlich.wochenenden[0]
    assert wochenende.ausfuehrliche_liga == LIGA
    assert wochenende.verlauf is not None
    assert wochenende.qualifying is not None
    assert wochenende.liga(LIGA).ausfuehrlich
    # Der Verlauf muss zur Wertung passen.
    assert len(wochenende.verlauf.teilnehmer) == k.wert("ligen", "autos_je_liga")
    assert wochenende.verlauf.strecke.name == wochenende.strecke


def test_startaufstellung_kommt_aus_dem_qualifying(ausfuehrlich, welt):
    """Der Qualifying-Platz in der Wertung muss der Startplatz sein."""
    wochenende = ausfuehrlich.wochenenden[0]
    quali = wochenende.qualifying
    feld = kw.starterfeld(welt, LIGA)
    fahrer = welt.liga(LIGA)
    for ergebnis in wochenende.liga(LIGA).ergebnisse:
        i = quali.aufstellung[ergebnis.qualifyingplatz - 1]
        assert fahrer[i].nummer == ergebnis.fahrer
        assert feld[i].auto is fahrer[i].auto


def test_die_uebrigen_ligen_bleiben_unberuehrt(ausfuehrlich, wochenende):
    """Ob die Spielerliga schnell oder ausfuehrlich faehrt, darf die
    anderen 19 Ligen nicht veraendern - sonst waere eine Saison nicht
    wiederholbar (GDD 15)."""
    for liga, ergebnis in wochenende.ligen.items():
        if liga == LIGA:
            continue
        assert ausfuehrlich.wochenenden[0].liga(liga) == ergebnis


def test_unbekannte_liga_faellt_auf(k, welt, strecken):
    lauf = neuer_lauf(k, welt, strecken)
    with pytest.raises(sa.SaisonFehler, match="Liga 99"):
        lauf.fahre_rennen(ausfuehrliche_liga=99)


# --- Saisonende -----------------------------------------------------------
def test_auf_und_abstieg_erst_nach_dem_letzten_rennen(lauf):
    with pytest.raises(sa.SaisonFehler, match="Auf- und Abstieg"):
        lauf.auf_und_abstieg()


def volle_tabellen(k, welt) -> dict[int, wt.Tabelle]:
    """Tabellen, in denen jede Liga nach Staerke geordnet ist."""
    tabellen = {}
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        tabelle = wt.Tabelle(liga)
        tabelle.verbuche(
            k,
            [
                wt.Rennergebnis(fahrer=f.nummer, rennplatz=platz, qualifyingplatz=platz)
                for platz, f in enumerate(welt.liga(liga), start=1)
            ],
        )
        tabellen[liga] = tabelle
    return tabellen


def test_ligawechsel_lassen_jede_liga_voll_besetzt(k, welt):
    wechsel = wt.auf_und_abstieg(k, volle_tabellen(k, welt))
    neu = sa.wende_wechsel_an(welt, wechsel)
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        assert len([f for f in neu.fahrer if f.liga == liga]) == k.wert(
            "ligen", "autos_je_liga"
        )
    # Genau die Wechsler haben eine andere Liga.
    geaendert = {f.nummer for f in neu.fahrer if f.liga != welt.fahrer[f.nummer].liga}
    assert geaendert == {w.fahrer for w in wechsel}


def test_ligawechsel_lassen_teams_und_autos_unangetastet(k, welt):
    """GDD 13: Auf- und Abstieg gelten fuer Fahrer, nicht fuer Teams."""
    neu = sa.wende_wechsel_an(welt, wt.auf_und_abstieg(k, volle_tabellen(k, welt)))
    assert neu.teams == welt.teams
    assert neu.seed == welt.seed
    for alt, jetzt in zip(welt.fahrer, neu.fahrer, strict=True):
        assert jetzt.nummer == alt.nummer
        assert jetzt.team == alt.team
        assert jetzt.auto is alt.auto


def test_doppelter_wechsel_faellt_auf(welt):
    doppelt = (wt.Wechsel(0, 5, 4), wt.Wechsel(0, 5, 6))
    with pytest.raises(sa.SaisonFehler):
        sa.wende_wechsel_an(welt, doppelt)


def test_ungleicher_wechsel_faellt_auf(welt):
    """Ein Aufstieg ohne Gegenstueck wuerde eine Liga sprengen."""
    einzeln = (wt.Wechsel(welt.liga(10)[0].nummer, 10, 9),)
    with pytest.raises(sa.SaisonFehler, match="Liga"):
        sa.wende_wechsel_an(welt, einzeln)


# --- Die Werte des Spielers -----------------------------------------------
def test_die_entwicklung_des_spielers_kommt_im_rennen_an(k, welt, strecken):
    """GDD 1: Der Spieler faengt bei 0 an und entwickelt sich.

    Seine Werte stehen in der Karriere, gefahren wird aber mit denen der
    Welt - ohne diese Naht bliebe die ganze Entwicklung aus Schritt 8
    wirkungslos, der Spieler fuehre dauerhaft mit Nullen.
    """
    spieler = welt.spieler
    karriere = kk.beginne(
        k, 2026, spieler.liga, fahrernummer=spieler.nummer
    )
    karriere.konto = karriere.konto.mit(geld=10_000_000, erfahrung=1_000_000)
    for _ in range(50):
        karriere.kaufe("F1")
    assert karriere.werte["F1"] > 0
    assert welt.fahrer[spieler.nummer].auto.wert("F1") == 0

    lauf = neuer_lauf(k, welt, strecken)
    lauf.karriere = karriere
    autos = lauf.spielerautos(spieler.liga)
    assert autos[ev.RENNEN][spieler.nummer].wert("F1") == karriere.werte["F1"]

    feld = kw.starterfeld(welt, spieler.liga, autos=autos[ev.RENNEN])
    eigen = next(t for t in feld if t.ist_spieler)
    assert eigen.auto.wert("F1") == karriere.werte["F1"]
    # Kuerzel und Name bleiben - die Seitenleiste im Rennen zeigt sie.
    assert eigen.auto.kuerzel == spieler.kuerzel


def test_ereignisse_und_defekte_wirken_im_rennen(k, welt, strecken):
    """GDD 14: Sie senken Werte - also muessen sie ins Feld durchschlagen."""
    spieler = welt.spieler
    werte = dict.fromkeys([f.schluessel for f in k.faehigkeiten], 20_000)
    werte.update(dict.fromkeys(k.zusatzfaehigkeiten, 20_000))
    karriere = kk.beginne(
        k, 2026, spieler.liga, werte, fahrernummer=spieler.nummer
    )
    karriere._loese_ereignis_aus("E1")  # D2 -15 %, D1 -10 %
    karriere.uebernimm_defekte(("X1",))  # F1 -2,5 %

    lauf = neuer_lauf(k, welt, strecken)
    lauf.karriere = karriere
    autos = lauf.spielerautos(spieler.liga)
    rennen = autos[ev.RENNEN][spieler.nummer]
    assert rennen.wert("D2") == 17_000
    assert rennen.wert("F1") == 19_500


def test_ein_ereignis_nur_im_qualifying_wirkt_auch_nur_dort(k, welt, strecken):
    """E12 aus GDD 14 gilt nur im Qualifying - das Rennfeld muss davon
    unberuehrt bleiben."""
    spieler = welt.spieler
    werte = dict.fromkeys([f.schluessel for f in k.faehigkeiten], 20_000)
    werte.update(dict.fromkeys(k.zusatzfaehigkeiten, 20_000))
    karriere = kk.beginne(
        k, 2026, spieler.liga, werte, fahrernummer=spieler.nummer
    )
    karriere._loese_ereignis_aus("E12")  # D1 -5 %, nur Qualifying

    lauf = neuer_lauf(k, welt, strecken)
    lauf.karriere = karriere
    autos = lauf.spielerautos(spieler.liga)
    assert autos["qualifying"][spieler.nummer].wert("D1") == 19_000
    assert autos[ev.RENNEN][spieler.nummer].wert("D1") == 20_000


def test_ohne_karriere_faehrt_die_welt_wie_gewuerfelt(k, welt, strecken):
    lauf = neuer_lauf(k, welt, strecken)
    assert lauf.spielerautos(welt.spieler.liga) == {}
