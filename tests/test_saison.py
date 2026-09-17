"""Tests fuer den Saisonlauf (GDD 13).

Ein Rennwochenende umfasst alle 20 Ligen; im Schnellmodus dauert es
wenige Sekunden, mit ausfuehrlich gefahrener Spielerliga deutlich
laenger. Die teuren Laeufe stehen deshalb in Fixtures mit
``scope="module"`` und werden von mehreren Tests genutzt.
"""

from __future__ import annotations

import datetime as dt

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


# --- Was das Rennwochenende der Karriere bringt (GDD 10 und 14) ----------
def spielerkarriere(k, welt, wert: int = 20_000) -> kk.Karriere:
    """Eine Karriere fuer den Spieler der Welt, mit brauchbaren Werten."""
    spieler = welt.spieler
    werte = dict.fromkeys([f.schluessel for f in k.faehigkeiten], wert)
    werte.update(dict.fromkeys(k.zusatzfaehigkeiten, wert))
    return kk.beginne(k, 2026, spieler.liga, werte, fahrernummer=spieler.nummer)


def lauf_mit_karriere(k, welt, strecken, karriere, seed: int = SEED) -> sa.Saisonlauf:
    return sa.Saisonlauf(
        k, welt, Seedquelle(seed), jahr=2026, strecken=strecken, karriere=karriere
    )


def test_karriere_und_saison_teilen_eine_streckenkenntnis(k, welt, strecken):
    """GDD 6 kennt einen Stand je Fahrer und Strecke - nicht zwei."""
    karriere = spielerkarriere(k, welt)
    eigene = karriere.kenntnis
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    assert karriere.kenntnis is lauf.kenntnis
    assert karriere.kenntnis is not eigene


def test_das_rennwochenende_zahlt_preisgeld_und_erfahrung(k, welt, strecken):
    """GDD 10: Preisgeld, Startgeld und Erfahrung kommen vom Rennen."""
    from rennmanager.kern import einnahmen as ke

    karriere = spielerkarriere(k, welt)
    vorher = karriere.konto
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    ergebnis = lauf.fahre_rennen().liga(karriere.liga).ergebnis_von(karriere.fahrernummer)

    manoever = lauf.wochenenden[0].liga(karriere.liga).manoever_je_fahrer.get(
        karriere.fahrernummer, 0
    )
    erwartet = ke.preisgeld(k, karriere.liga, ergebnis.rennplatz) + ke.startgeld(
        k, karriere.liga
    )
    assert karriere.konto.geld - vorher.geld == erwartet
    assert karriere.konto.erfahrung - vorher.erfahrung == ke.erfahrung_fuer(
        k, karriere.liga, ergebnis.rennplatz, manoever
    )


def test_gefahrene_kilometer_fuellen_die_wettertoepfe(k, welt, strecken):
    """GDD 10: eigener EP-Topf je Wetter, Verdienst je gefahrenem km."""
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    wochenende = lauf.fahre_rennen()

    kilometer = wochenende.liga(karriere.liga).kilometer_je_fahrer[karriere.fahrernummer]
    assert kilometer
    assert set(karriere.konto.wetter_erfahrung) == set(kilometer)
    assert all(betrag > 0 for betrag in karriere.konto.wetter_erfahrung.values())


def test_defekte_aus_dem_rennen_bleiben_offen(k, welt, strecken):
    """GDD 14: Defekte laufen bis zur Reparatur, also ueber das Rennen hinaus."""
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    wochenende = sa.Ligawochenende(
        liga=karriere.liga,
        ergebnisse=(wt.Rennergebnis(karriere.fahrernummer, 7, 9),),
        wetter=("trocken",),
        siegerzeit_ms=1,
        schnellste_runde_ms=1,
        ueberholmanoever=0,
        ausfaelle=0,
        defekte_je_fahrer={karriere.fahrernummer: ("X1", "X13")},
    )
    lauf._verbuche_karriere(wochenende, karriere.fahrernummer)

    assert [d["schluessel"] for d in karriere.defekte] == ["X1", "X13"]
    assert {p[0] for p in karriere.offene_reparaturen} == {"X1", "X13"}


def test_das_rennen_meldet_defekte_je_fahrer(k, welt, strecken):
    """Ueber 20 Ligen faellt in einem Wochenende immer etwas aus."""
    lauf = neuer_lauf(k, welt, strecken)
    wochenende = lauf.fahre_rennen()
    schluessel = {d["schluessel"] for d in k.wert("defekte", "liste")}
    gemeldet = [
        defekt
        for liga in wochenende.ligen.values()
        for defekte in liga.defekte_je_fahrer.values()
        for defekt in defekte
    ]
    assert gemeldet
    assert set(gemeldet) <= schluessel


def test_manoever_je_fahrer_ergeben_die_summe_der_liga(wochenende, ausfuehrlich):
    for liga in (wochenende.liga(LIGA), ausfuehrlich.wochenenden[0].liga(LIGA)):
        assert sum(liga.manoever_je_fahrer.values()) == liga.ueberholmanoever


def test_kilometer_je_fahrer_passen_zur_renndistanz(k, strecken, wochenende):
    """Wer durchfaehrt, hat die volle Distanz im Buch."""
    from rennmanager.kern import rennen as kr

    liga = wochenende.liga(LIGA)
    voll = kr.rundenzahl(k, strecken[0], LIGA) * strecken[0].laenge_m / 1000.0
    gefahren = [
        sum(eintrag.values()) for eintrag in liga.kilometer_je_fahrer.values()
    ]
    assert len(gefahren) == k.wert("ligen", "autos_je_liga")
    assert max(gefahren) == pytest.approx(voll, rel=1e-6)
    assert all(km <= voll + 1e-6 for km in gefahren)


# --- Streckenkenntnis des Spielers (GDD 6) --------------------------------
def test_die_streckenkenntnis_des_spielers_waechst_mit_dem_rennen(k, welt, strecken):
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    name = strecken[0].name
    assert karriere.kenntnis.stand(karriere.fahrernummer, name) == 0.0

    lauf.fahre_rennen()
    gewachsen = karriere.kenntnis.stand(karriere.fahrernummer, name)
    assert gewachsen > 0.0
    # Die KI steht fest, solange sie sich nicht entwickelt (GDD 12).
    assert karriere.kenntnisfaktor(name) == lauf.kenntnis.tempofaktor(
        karriere.fahrernummer, name
    )


def test_jeder_fahrer_wird_genau_einmal_verbucht(k, welt, strecken):
    """Der Spieler bucht ueber die Karriere - aber nur einmal."""
    karriere = spielerkarriere(k, welt)
    mit = lauf_mit_karriere(k, welt, strecken, karriere)
    mit.fahre_rennen()

    ohne = neuer_lauf(k, welt, strecken)
    ohne.fahre_rennen()
    name = strecken[0].name
    assert mit.kenntnis.stand(karriere.fahrernummer, name) == pytest.approx(
        ohne.kenntnis.stand(karriere.fahrernummer, name)
    )


def test_e10_hebt_den_kenntniszuwachs(k, welt, strecken):
    """E10 Testfahrt geglueckt: +20 % auf die naechste Strecke (GDD 14)."""
    ohne = spielerkarriere(k, welt)
    lauf_mit_karriere(k, welt, strecken, ohne).fahre_rennen()

    mit = spielerkarriere(k, welt)
    mit._loese_ereignis_aus("E10")
    lauf_mit_karriere(k, welt, strecken, mit).fahre_rennen()

    name = strecken[0].name
    zuschlag = ev.eintrag(k, "E10")["wirkung"][0]["faktor"]
    assert mit.kenntnis.stand(mit.fahrernummer, name) == pytest.approx(
        ohne.kenntnis.stand(ohne.fahrernummer, name) * (1.0 + zuschlag)
    )


# --- E3 Motivationsschub (GDD 14) ----------------------------------------
def test_der_tagesformbonus_trifft_nur_den_spieler(k, welt, strecken):
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    feld = welt.liga(karriere.liga)
    assert lauf.tagesformbonus(karriere.liga, feld) == (0.0,) * len(feld)

    karriere._loese_ereignis_aus("E3")
    bonus = ev.eintrag(k, "E3")["wirkung"][0]["faktor"]
    gesetzt = lauf.tagesformbonus(karriere.liga, feld)
    assert gesetzt.count(bonus) == 1
    assert gesetzt[[f.nummer for f in feld].index(karriere.fahrernummer)] == bonus
    # Andere Ligen bleiben unberuehrt - die KI hat keine Ereignisse.
    andere = welt.liga(karriere.liga - 1)
    assert lauf.tagesformbonus(karriere.liga - 1, andere) == (0.0,) * len(andere)


def test_e3_macht_den_spieler_schneller(k, welt, strecken):
    """Ein hoeherer Tagesform-Mittelwert muss im Ergebnis ankommen."""
    ohne = spielerkarriere(k, welt, wert=60_000)
    lauf_ohne = lauf_mit_karriere(k, welt, strecken, ohne)
    platz_ohne = (
        lauf_ohne.fahre_rennen().liga(ohne.liga).ergebnis_von(ohne.fahrernummer)
    )

    mit = spielerkarriere(k, welt, wert=60_000)
    mit._loese_ereignis_aus("E3")
    lauf_mit = lauf_mit_karriere(k, welt, strecken, mit)
    platz_mit = lauf_mit.fahre_rennen().liga(mit.liga).ergebnis_von(mit.fahrernummer)

    assert platz_mit.rennplatz <= platz_ohne.rennplatz
    # Die uebrigen Ligen duerfen sich davon nicht ruehren (GDD 15).
    for liga in lauf_ohne.wochenenden[0].ligen:
        if liga == ohne.liga:
            continue
        assert lauf_mit.wochenenden[0].liga(liga) == lauf_ohne.wochenenden[0].liga(liga)


# --- Kalender und Rennwochenende (GDD 2) ---------------------------------
def test_das_rennen_findet_an_seinem_renntag_statt(k, welt, strecken):
    """GDD 2: Rennen 1 ist der erste Sonntag ab dem 1. Maerz."""
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    assert karriere.heute == dt.date(2026, 1, 1)

    renntag = lauf.renntag(1)
    assert renntag == karriere.saison.renntage[0]
    lauf.fahre_rennen()
    # Der Renntag ist vorbei; der naechste Tag gehoert wieder der Planung.
    assert karriere.heute == renntag + dt.timedelta(days=1)


def test_jedes_rennen_schiebt_den_kalender_einen_zyklus_weiter(k, welt, strecken):
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    for nummer in range(1, 4):
        lauf.fahre_rennen()
        assert karriere.heute == lauf.renntag(nummer) + dt.timedelta(days=1)
        # GDD 2: 10 nutzbare Tage je 14-Tage-Zyklus.
        assert karriere.offene_tage == k.wert("kalender", "nutzbare_tage_je_zyklus")


def test_wer_vorher_zum_rennen_springt_verliert_keinen_tag(k, welt, strecken):
    """Erst planen, dann fahren - der Kalender steht dann schon richtig."""
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    karriere.bis_zum_rennen()
    assert karriere.heute == lauf.renntag(1)
    assert lauf.offene_tage_vor_dem_rennen == 0

    lauf.fahre_rennen()
    assert lauf.gefahren == 1


def test_ereignisse_der_uebersprungenen_tage_wirken_noch_im_rennen(k, welt, strecken):
    """Der Kalender laeuft vor dem Rennen hoch, nicht danach (GDD 14)."""
    karriere = spielerkarriere(k, welt)
    lauf = lauf_mit_karriere(k, welt, strecken, karriere)
    # E5 Genialer Mechaniker, drei Tage vor dem ersten Rennen.
    karriere.ereignisplan = {lauf.renntag(1) - dt.timedelta(days=3): ("E5",)}

    lauf.fahre_rennen()
    assert [m.schluessel for m in karriere.meldungen] == ["E5"]
    # Es lief beim Rennen schon, zaehlt also ein Rennwochenende herunter.
    assert lauf.karriere.lage.aktive[0].rest == 2


def test_ohne_karriere_gibt_es_keinen_kalender(k, welt, strecken):
    lauf = neuer_lauf(k, welt, strecken)
    assert lauf.renntag(1) is None
    assert lauf.offene_tage_vor_dem_rennen == 0
    lauf.fahre_rennen()
    assert lauf.gefahren == 1


# --- Saisonwechsel (GDD 13) -----------------------------------------------
def abgeschlossener_lauf(k, welt, strecken, karriere=None, jahr=None) -> sa.Saisonlauf:
    """Ein Saisonlauf, dessen 20 Rennen als gefahren gelten.

    Die 20 mal 20 Rennen wirklich zu fahren dauert anderthalb Minuten je
    Saison; fuer den Wechsel selbst zaehlt allein, dass die Tabellen voll
    sind und der Stand am Saisonende steht.
    """
    lauf = sa.Saisonlauf(
        k,
        welt,
        Seedquelle(SEED),
        jahr=jahr,
        strecken=strecken,
        tabellen=volle_tabellen(k, welt),
        vorgefahren=k.wert("kalender", "rennen_je_saison"),
        karriere=karriere,
    )
    assert lauf.ist_fertig
    return lauf


def test_der_saisonwechsel_zaehlt_das_jahr_hoch(k, welt, strecken):
    lauf = abgeschlossener_lauf(k, welt, strecken)
    assert lauf.jahr == k.wert("kalender", "startjahr")
    neu = lauf.naechste_saison()
    assert neu.jahr == lauf.jahr + 1
    assert neu.gefahren == 0
    assert not neu.ist_fertig
    # Frische Tabellen, aber dieselbe Statistik und Streckenkenntnis.
    assert all(not t.eintraege for t in neu.tabellen.values())
    assert neu.statistik is lauf.statistik
    assert neu.kenntnis is lauf.kenntnis


def test_drei_saisons_lassen_jede_liga_voll_besetzt(k, welt, strecken):
    """GDD 13: Jeder Aufsteiger ersetzt einen Absteiger."""
    je_liga = k.wert("ligen", "autos_je_liga")
    lauf = abgeschlossener_lauf(k, welt, strecken)
    for _ in range(3):
        lauf = lauf.naechste_saison()
        groessen = {}
        for f in lauf.welt.fahrer:
            groessen[f.liga] = groessen.get(f.liga, 0) + 1
        assert set(groessen.values()) == {je_liga}
        assert len(lauf.welt.fahrer) == k.wert("ligen", "anzahl") * je_liga
        lauf.tabellen = volle_tabellen(k, lauf.welt)
        lauf.vorgefahren = k.wert("kalender", "rennen_je_saison")


def test_die_historie_traegt_jede_saison_vollstaendig(k, welt, strecken):
    """Die Tabelle wird geleert - was bleiben soll, steht in der Historie."""
    lauf = abgeschlossener_lauf(k, welt, strecken)
    erste = lauf.jahr
    stand = lauf.tabelle(LIGA).stand()
    neu = lauf.naechste_saison()

    abschluss = neu.statistik.abschluss(erste, LIGA)
    assert abschluss is not None
    assert len(abschluss.zeilen) == len(stand)
    for platz, (zeile, eintrag) in enumerate(
        zip(abschluss.zeilen, stand, strict=True), start=1
    ):
        assert zeile.platz == platz
        assert zeile.fahrer == eintrag.fahrer
        assert zeile.punkte == eintrag.punkte
        assert zeile.siege == eintrag.siege
        assert zeile.podien == eintrag.podien
        assert zeile.poles == eintrag.poles
        assert zeile.rennen == eintrag.rennen
    assert abschluss.reihenfolge == tuple(e.fahrer for e in stand)
    assert abschluss.platz_von(abschluss.meister) == 1


def test_die_karriere_nimmt_alles_mit_was_ueberdauert(k, welt, strecken):
    """GDD 10 und 14: Konto, Werte, Vertraege, Defekte und Ereignisse."""
    karriere = spielerkarriere(k, welt)
    karriere.konto = karriere.konto.mit(geld=5_000, erfahrung=800)
    karriere.uebernimm_defekte(("X1",))
    karriere._loese_ereignis_aus("E5")  # F14 +10 %, drei Rennwochenenden
    karriere.verlorene_tage.add(karriere.heute)
    karriere.werte["F1"] = 33_000

    lauf = abgeschlossener_lauf(k, welt, strecken, karriere)
    kenntnis_vorher = dict(lauf.kenntnis.runden)
    lauf.naechste_saison()

    assert karriere.konto.geld == 6_000  # Startkapital 1.000 plus 5.000
    assert karriere.konto.erfahrung == 800
    assert karriere.werte["F1"] == 33_000
    assert [d["schluessel"] for d in karriere.defekte] == ["X1"]
    assert [a.schluessel for a in karriere.lage.aktive] == ["E5"]
    assert lauf.kenntnis.runden == kenntnis_vorher
    # Neu sind Kalender und Jahr; die verlorenen Tage gehoerten zum alten.
    assert karriere.saison.jahr == lauf.jahr + 1
    assert karriere.heute == dt.date(lauf.jahr + 1, 1, 1)
    assert karriere.verlorene_tage == set()


def test_der_spieler_wechselt_mit_seiner_liga(k, strecken):
    """Nach dem Aufstieg faehrt die Karriere in der neuen Liga."""
    welt = kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=5)
    karriere = spielerkarriere(k, welt)
    lauf = abgeschlossener_lauf(k, welt, strecken, karriere)
    # Die Tabelle ist nach Staerke geordnet; der Spieler steht mit lauter
    # Nullen hinten und steigt ab.
    assert lauf.tabelle(5).platz_von(karriere.fahrernummer) > 27

    neu = lauf.naechste_saison()
    assert neu.welt.spieler.liga == 6
    assert karriere.liga == 6


def test_ein_sprung_zurueck_faellt_auf(k, welt):
    karriere = spielerkarriere(k, welt)
    with pytest.raises(kk.KarriereFehler, match="liegt nicht nach"):
        karriere.naechste_saison(karriere.saison.jahr, karriere.liga)


def test_der_wechsel_braucht_eine_gefahrene_saison(k, welt, strecken):
    lauf = neuer_lauf(k, welt, strecken)
    with pytest.raises(sa.SaisonFehler, match="Auf- und Abstieg"):
        lauf.naechste_saison()


# --- Das gefuehrte Rennwochenende (Punkt 12) ------------------------------
@pytest.fixture(scope="module")
def gefuehrt(k, welt, strecken) -> sa.Wochenendlauf:
    """Dasselbe Wochenende, in Etappen gefahren."""
    lauf = neuer_lauf(k, welt, strecken)
    wochenendlauf = sa.Wochenendlauf(lauf, LIGA)
    wochenendlauf.fahre_qualifying()
    wochenendlauf.fahre_rennen()
    wochenendlauf.schliesse_ab()
    return wochenendlauf


def test_gefuehrt_und_am_stueck_ergeben_dasselbe(gefuehrt, ausfuehrlich, k):
    """Der Kern der Sache: Derselbe Seed, dasselbe Rennen (GDD 15).

    Das gefuehrte Wochenende faengt mit der Liga des Spielers an und
    haengt die 19 anderen hinten dran; ``fahre_rennen`` geht von Liga 1
    bis 20 durch. Herauskommen muss beides Mal dasselbe - sonst haengt das
    Ergebnis an der Reihenfolge, und ein Seed sagt nichts mehr.
    """
    am_stueck = ausfuehrlich.wochenenden[0]
    in_etappen = gefuehrt.wochenende

    assert in_etappen.nummer == am_stueck.nummer
    assert in_etappen.strecke == am_stueck.strecke
    assert set(in_etappen.ligen) == set(am_stueck.ligen)

    for liga in sorted(am_stueck.ligen):
        eine = am_stueck.liga(liga)
        andere = in_etappen.liga(liga)
        assert andere == eine, f"Liga {liga} weicht ab"

    # Auch das Abspielbare muss deckungsgleich sein.
    assert in_etappen.qualifying.aufstellung == am_stueck.qualifying.aufstellung
    assert in_etappen.verlauf.ergebnisse == am_stueck.verlauf.ergebnisse
    assert in_etappen.verlauf.positionsgewinne == am_stueck.verlauf.positionsgewinne


def test_gefuehrt_fuehrt_die_saison_genauso_weiter(gefuehrt, ausfuehrlich, welt):
    """Tabelle, Statistik, Kenntnis und Popularitaet muessen gleich stehen."""
    for liga in sorted(ausfuehrlich.tabellen):
        eine = ausfuehrlich.tabelle(liga).stand()
        andere = gefuehrt.lauf.tabelle(liga).stand()
        assert andere == eine, f"Tabelle der Liga {liga} weicht ab"

    assert gefuehrt.lauf.gefahren == ausfuehrlich.gefahren == 1
    assert gefuehrt.lauf.naechstes_rennen == ausfuehrlich.naechstes_rennen

    strecke = ausfuehrlich.wochenenden[0].strecke
    for fahrer in welt.fahrer:
        assert gefuehrt.lauf.kenntnis.stand(
            fahrer.nummer, strecke
        ) == pytest.approx(ausfuehrlich.kenntnis.stand(fahrer.nummer, strecke))
        assert gefuehrt.lauf.popularitaet.stand(
            fahrer.nummer
        ) == pytest.approx(ausfuehrlich.popularitaet.stand(fahrer.nummer))


def test_die_etappen_muessen_in_der_reihenfolge_kommen(k, welt, strecken):
    lauf = sa.Wochenendlauf(neuer_lauf(k, welt, strecken), LIGA)
    with pytest.raises(sa.WochenendFehler):
        lauf.fahre_rennen()
    lauf.fahre_qualifying()
    with pytest.raises(sa.WochenendFehler):
        lauf.schliesse_ab()


def test_eine_etappe_zweimal_gefahren_bleibt_dieselbe(k, welt, strecken):
    """Ein zweiter Klick darf das Wochenende nicht neu wuerfeln."""
    lauf = sa.Wochenendlauf(neuer_lauf(k, welt, strecken), LIGA)
    assert lauf.fahre_qualifying() is lauf.fahre_qualifying()
    assert lauf.fahre_rennen() is lauf.fahre_rennen()
    assert lauf.schliesse_ab() is lauf.schliesse_ab()
    assert lauf.lauf.gefahren == 1


def test_das_wochenende_kennt_strecke_und_runden_vor_dem_fahren(k, welt, strecken):
    """Die Vorschau im gefuehrten Reiter braucht das, bevor gefahren wird."""
    saisonlauf = neuer_lauf(k, welt, strecken)
    lauf = sa.Wochenendlauf(saisonlauf, LIGA)
    assert lauf.nummer == 1
    assert lauf.strecke.name == k.strecken[0]["name"]
    assert lauf.runden > 0
    assert not lauf.ist_gefahren
    # Ohne Karriere gibt es keinen Kalender, also auch kein Datum.
    assert lauf.renntag is None


def test_unbekannte_liga_wird_abgewiesen(k, welt, strecken):
    with pytest.raises(sa.SaisonFehler):
        sa.Wochenendlauf(neuer_lauf(k, welt, strecken), 99)
