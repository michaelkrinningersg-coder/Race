"""Tests fuer die Saisonwertung und den Auf- und Abstieg (GDD 13)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import wertung as wt


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


def ergebnis(fahrer: int, platz: int, **rest) -> wt.Rennergebnis:
    rest.setdefault("qualifyingplatz", platz)
    return wt.Rennergebnis(fahrer=fahrer, rennplatz=platz, **rest)


def wochenende(anzahl: int, reihenfolge: list[int]) -> list[wt.Rennergebnis]:
    """Ein Rennen, in dem die genannten Fahrer in dieser Reihenfolge landen."""
    assert len(reihenfolge) == anzahl
    return [ergebnis(fahrer, platz) for platz, fahrer in enumerate(reihenfolge, start=1)]


# --- Punkte ---------------------------------------------------------------
def test_punktetabelle_entspricht_dem_gdd(k):
    # GDD 13: 40-35-30-25-20-18-16-14-12-11-10-9-8-7-6-5-4-3-2-1
    erwartet = [40, 35, 30, 25, 20, 18, 16, 14, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    for platz, punkte in enumerate(erwartet, start=1):
        assert wt.rennpunkte(k, platz) == punkte


def test_ab_platz_21_gibt_es_keine_rennpunkte(k):
    autos = k.wert("rennen", "autos")
    assert wt.rennpunkte(k, 21) == 0
    assert wt.rennpunkte(k, autos) == 0


def test_qualifying_bringt_nur_den_ersten_drei_punkte(k):
    assert [wt.qualifyingpunkte(k, platz) for platz in (1, 2, 3, 4)] == [5, 3, 1, 0]


def test_schnellste_runde_zaehlt_auch_ohne_zielankunft(k):
    # GDD 13 nennt das ausdruecklich.
    ausgefallen = wt.Rennergebnis(
        fahrer=0, rennplatz=30, qualifyingplatz=25, schnellste_runde=True, ausgefallen=True
    )
    assert wt.punkte_fuer(k, ausgefallen) == k.wert("wertung", "punkte_schnellste_runde")


def test_punkte_eines_wochenendes_summieren_sich(k):
    # Sieg (40) + Pole (5) + schnellste Runde (3)
    bestes = wt.Rennergebnis(fahrer=0, rennplatz=1, qualifyingplatz=1, schnellste_runde=True)
    assert wt.punkte_fuer(k, bestes) == 48


# --- Tabelle --------------------------------------------------------------
def test_tabelle_summiert_ueber_mehrere_rennen(k):
    tabelle = wt.Tabelle(liga=5)
    tabelle.verbuche(k, [ergebnis(1, 1), ergebnis(2, 2)])
    tabelle.verbuche(k, [ergebnis(1, 3), ergebnis(2, 1)])

    stand = {e.fahrer: e for e in tabelle.stand()}
    assert stand[1].punkte == (40 + 5) + (30 + 1)
    assert stand[2].punkte == (35 + 3) + (40 + 5)
    assert stand[1].siege == 1 and stand[2].siege == 1
    assert stand[1].rennen == 2


def test_gleichstand_entscheidet_die_bessere_platzierung(k):
    """GDD 13: mehr Siege, dann mehr zweite Plaetze und so weiter."""
    tabelle = wt.Tabelle(liga=5)
    # Beide kommen auf 40+35 = 75 Rennpunkte, ohne Qualifying-Punkte.
    tabelle.verbuche(k, [ergebnis(1, 1, qualifyingplatz=10), ergebnis(2, 2, qualifyingplatz=11)])
    tabelle.verbuche(k, [ergebnis(1, 2, qualifyingplatz=10), ergebnis(2, 1, qualifyingplatz=11)])
    # Bis hierhin voellig gleich; jetzt bekommt Fahrer 2 einen Sieg mehr
    # und Fahrer 1 dafuer zwei dritte Plaetze - gleiche Punkte, anderer Rang.
    tabelle.verbuche(k, [ergebnis(1, 3, qualifyingplatz=10), ergebnis(2, 1, qualifyingplatz=11)])
    tabelle.verbuche(k, [ergebnis(1, 1, qualifyingplatz=10), ergebnis(2, 3, qualifyingplatz=11)])

    stand = tabelle.stand()
    assert stand[0].punkte == stand[1].punkte
    assert stand[0].siege == 2 and stand[1].siege == 2
    # Gleiche Siege, gleiche Punkte: es entscheidet die Zahl der zweiten Plaetze.
    assert stand[0].platzierungen[1] >= stand[1].platzierungen[1]


def test_platz_von_meldet_unbekannte_fahrer(k):
    tabelle = wt.Tabelle(liga=5)
    tabelle.verbuche(k, [ergebnis(1, 1)])
    assert tabelle.platz_von(1) == 1
    with pytest.raises(wt.WertungsFehler):
        tabelle.platz_von(99)


# --- Auf- und Abstieg -----------------------------------------------------
@pytest.fixture
def volle_tabellen(k) -> dict[int, wt.Tabelle]:
    """20 Ligen zu je 30 Fahrern; Fahrernummer = Liga * 100 + Rang."""
    autos = k.wert("ligen", "autos_je_liga")
    tabellen = {}
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        tabelle = wt.Tabelle(liga)
        tabelle.verbuche(k, wochenende(autos, [liga * 100 + n for n in range(autos)]))
        tabellen[liga] = tabelle
    return tabellen


def test_top_drei_steigen_auf_und_letzte_drei_ab(k, volle_tabellen):
    wechsel = wt.auf_und_abstieg(k, volle_tabellen)
    nach_liga = {}
    for w in wechsel:
        nach_liga.setdefault(w.von_liga, []).append(w)

    # Liga 10 schickt drei nach oben und drei nach unten.
    zehn = nach_liga[10]
    assert sorted(w.fahrer for w in zehn if w.ist_aufstieg) == [1000, 1001, 1002]
    assert sorted(w.fahrer for w in zehn if not w.ist_aufstieg) == [1027, 1028, 1029]
    assert {w.nach_liga for w in zehn if w.ist_aufstieg} == {9}
    assert {w.nach_liga for w in zehn if not w.ist_aufstieg} == {11}


def test_liga_eins_kennt_keinen_aufstieg_und_liga_zwanzig_keinen_abstieg(k, volle_tabellen):
    wechsel = wt.auf_und_abstieg(k, volle_tabellen)
    letzte = k.wert("ligen", "anzahl")
    assert not [w for w in wechsel if w.von_liga == 1 and w.ist_aufstieg]
    assert not [w for w in wechsel if w.von_liga == letzte and not w.ist_aufstieg]
    # Aber Liga 1 steigt ab und Liga 20 steigt auf.
    assert len([w for w in wechsel if w.von_liga == 1]) == 3
    assert len([w for w in wechsel if w.von_liga == letzte]) == 3


def test_jede_liga_bleibt_gleich_stark(k, volle_tabellen):
    """Je Liga gehen genauso viele raus wie rein - sonst platzt das Feld."""
    wechsel = wt.auf_und_abstieg(k, volle_tabellen)
    saldo = dict.fromkeys(volle_tabellen, 0)
    for w in wechsel:
        saldo[w.von_liga] -= 1
        saldo[w.nach_liga] += 1
    assert set(saldo.values()) == {0}


def test_kein_fahrer_wechselt_zweimal(k, volle_tabellen):
    wechsel = wt.auf_und_abstieg(k, volle_tabellen)
    fahrer = [w.fahrer for w in wechsel]
    assert len(fahrer) == len(set(fahrer))


def test_unvollstaendige_liga_faellt_auf(k, volle_tabellen):
    wt.pruefe_ligastaerken(k, volle_tabellen)
    del volle_tabellen[7].eintraege[700]
    with pytest.raises(wt.WertungsFehler, match="Liga 7"):
        wt.pruefe_ligastaerken(k, volle_tabellen)
