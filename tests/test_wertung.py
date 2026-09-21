"""Tests fuer die Saisonwertung (GDD 13, Punkt 101)."""

from __future__ import annotations

import math

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import wertung as wt


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


def ergebnis(fahrer: int, platz: int, **rest) -> wt.Rennergebnis:
    rest.setdefault("qualifyingplatz", platz)
    return wt.Rennergebnis(fahrer=fahrer, rennplatz=platz, **rest)


# --- Punkte ---------------------------------------------------------------
def test_die_tabelle_steht_wie_vorgegeben(k):
    """Punkt 101: 100, 90, 80, 76, 72, dann 70 bis 20, dann 19 bis 1."""
    punkte = list(wt.punktetabelle(k))
    assert len(punkte) == k.wert("rennen", "autos") == 50
    assert punkte[:7] == [100, 90, 80, 76, 72, 70, 68]
    # Platz 6 bis 31 in Zweierschritten.
    assert all(a - b == 2 for a, b in zip(punkte[5:30], punkte[6:31], strict=True))
    assert punkte[30] == 20
    # Danach 19 bis 1 in Einerschritten.
    assert punkte[31:] == list(range(19, 0, -1))


def test_die_punkte_fallen_von_platz_eins_an(k):
    punkte = wt.punktetabelle(k)
    assert list(punkte) == sorted(punkte, reverse=True)
    assert len(set(punkte)) == len(punkte)


def test_jeder_platz_bekommt_punkte_ausserhalb_des_feldes_keine(k):
    """Punkt 101: Alle 50 Plaetze zaehlen, auch die der Ausgefallenen."""
    autos = k.wert("rennen", "autos")
    assert wt.rennpunkte(k, autos) == 1
    assert wt.rennpunkte(k, autos + 1) == 0
    assert wt.rennpunkte(k, 0) == 0


def test_siegerpunkte_sind_der_erste_wert_der_tabelle(k):
    assert wt.siegerpunkte(k) == wt.rennpunkte(k, 1) == 100


def test_die_zusatzpunkte_sind_anteile_der_siegerpunkte(k):
    """Aufgerundet, mindestens 1."""
    sieg = wt.siegerpunkte(k)
    anteil = k.wert("wertung", "anteil_schnellste_runde")
    assert wt.punkte_schnellste_runde(k) == max(1, math.ceil(sieg * anteil))
    for platz, teil in enumerate(k.wert("wertung", "anteil_qualifying"), start=1):
        assert wt.qualifyingpunkte(k, platz) == max(1, math.ceil(sieg * teil))
    assert wt.qualifyingpunkte(k, 4) == 0
    # Mit den Anteilen aus der Konfiguration: 1 fuer die schnellste Runde
    # und 2/1/1 im Qualifying.
    assert wt.punkte_schnellste_runde(k) == 1
    assert [wt.qualifyingpunkte(k, p) for p in (1, 2, 3)] == [2, 1, 1]


def test_schnellste_runde_zaehlt_auch_ohne_zielankunft(k):
    # GDD 13 nennt das ausdruecklich - und auch der Platz eines
    # Ausgefallenen bekommt Punkte.
    ausgefallen = wt.Rennergebnis(
        fahrer=0, rennplatz=30, qualifyingplatz=25, schnellste_runde=True, ausgefallen=True
    )
    assert wt.punkte_fuer(k, ausgefallen) == (
        wt.rennpunkte(k, 30) + wt.punkte_schnellste_runde(k)
    )


def test_punkte_eines_wochenendes_summieren_sich(k):
    # Sieg (100) + Pole (2) + schnellste Runde (1)
    bestes = wt.Rennergebnis(fahrer=0, rennplatz=1, qualifyingplatz=1, schnellste_runde=True)
    assert wt.punkte_fuer(k, bestes) == 103


# --- Tabelle --------------------------------------------------------------
def test_tabelle_summiert_ueber_mehrere_rennen(k):
    tabelle = wt.Tabelle()
    tabelle.verbuche(k, [ergebnis(1, 1), ergebnis(2, 2)])
    tabelle.verbuche(k, [ergebnis(1, 3), ergebnis(2, 1)])

    stand = {e.fahrer: e for e in tabelle.stand()}
    sieg = wt.rennpunkte(k, 1)
    quali = [wt.qualifyingpunkte(k, platz) for platz in (1, 2, 3)]
    assert stand[1].punkte == (sieg + quali[0]) + (wt.rennpunkte(k, 3) + quali[2])
    assert stand[2].punkte == (wt.rennpunkte(k, 2) + quali[1]) + (sieg + quali[0])
    assert stand[1].siege == 1 and stand[2].siege == 1
    assert stand[1].rennen == 2


def test_gleichstand_entscheidet_die_bessere_platzierung(k):
    """GDD 13: mehr Siege, dann mehr zweite Plaetze und so weiter."""
    tabelle = wt.Tabelle()
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
    tabelle = wt.Tabelle()
    tabelle.verbuche(k, [ergebnis(1, 1)])
    assert tabelle.platz_von(1) == 1
    with pytest.raises(wt.WertungsFehler):
        tabelle.platz_von(99)


def test_eine_unvollstaendige_tabelle_faellt_auf(k):
    """Vor dem Wechsel in die naechste Saison muss das Feld vollzaehlig sein."""
    autos = k.wert("rennen", "autos")
    tabelle = wt.Tabelle()
    tabelle.verbuche(
        k, [ergebnis(nummer, nummer + 1) for nummer in range(autos)]
    )
    wt.pruefe_feldgroesse(k, tabelle)
    del tabelle.eintraege[0]
    with pytest.raises(wt.WertungsFehler, match="49"):
        wt.pruefe_feldgroesse(k, tabelle)


# --- Punkt 73: Live-Meisterschaftsstand -----------------------------------
def test_die_livewertung_zaehlt_die_punkte_der_lage_dazu(k) -> None:
    """Stand bis hierher plus die Punkte fuer die derzeitige Position."""
    tabelle = wt.Tabelle()
    tabelle.verbuche(
        k,
        [
            wt.Rennergebnis(fahrer=1, rennplatz=1, qualifyingplatz=1),
            wt.Rennergebnis(fahrer=2, rennplatz=2, qualifyingplatz=2),
        ],
    )
    vorher = {f: e.punkte for f, e in tabelle.eintraege.items()}

    # Jetzt liegt der Zweite vorn.
    lage = [
        wt.Rennergebnis(fahrer=2, rennplatz=1, qualifyingplatz=2),
        wt.Rennergebnis(fahrer=1, rennplatz=2, qualifyingplatz=1),
    ]
    zeilen = wt.livewertung(k, tabelle, lage)
    stand = {z.fahrer: z for z in zeilen}

    for nummer, zeile in stand.items():
        erwartet = next(e for e in lage if e.fahrer == nummer)
        assert zeile.zuwachs == wt.punkte_fuer(k, erwartet)
        assert zeile.punkte == vorher[nummer] + zeile.zuwachs


def test_die_livewertung_laesst_die_tabelle_unberuehrt(k) -> None:
    """Eine Vorschau - das Rennen laeuft ja noch."""
    tabelle = wt.Tabelle()
    tabelle.verbuche(k, [wt.Rennergebnis(fahrer=1, rennplatz=1, qualifyingplatz=1)])
    vorher = tabelle.eintraege[1].punkte
    wt.livewertung(k, tabelle, [wt.Rennergebnis(fahrer=1, rennplatz=1, qualifyingplatz=1)])
    assert tabelle.eintraege[1].punkte == vorher


def test_die_veraenderung_sagt_die_gewonnenen_plaetze(k) -> None:
    """Punkt 73: positiv heisst nach vorn."""
    tabelle = wt.Tabelle()
    tabelle.verbuche(
        k,
        [
            wt.Rennergebnis(fahrer=1, rennplatz=1, qualifyingplatz=1),
            wt.Rennergebnis(fahrer=2, rennplatz=2, qualifyingplatz=2),
        ],
    )
    # Der Zweite gewinnt dieses Rennen deutlich und zieht vorbei.
    zeilen = wt.livewertung(
        k,
        tabelle,
        [
            wt.Rennergebnis(fahrer=2, rennplatz=1, qualifyingplatz=1,
                            schnellste_runde=True),
            wt.Rennergebnis(fahrer=1, rennplatz=20, qualifyingplatz=20),
        ],
    )
    zwei = next(z for z in zeilen if z.fahrer == 2)
    eins = next(z for z in zeilen if z.fahrer == 1)
    assert zwei.veraenderung > 0
    assert eins.veraenderung < 0
    assert zwei.platz == 1


def test_die_schnellste_runde_zaehlt_mit(k) -> None:
    tabelle = wt.Tabelle()
    ohne = wt.livewertung(
        k, tabelle, [wt.Rennergebnis(fahrer=1, rennplatz=5, qualifyingplatz=5)]
    )[0]
    mit = wt.livewertung(
        k,
        tabelle,
        [wt.Rennergebnis(fahrer=1, rennplatz=5, qualifyingplatz=5,
                         schnellste_runde=True)],
    )[0]
    assert mit.zuwachs > ohne.zuwachs
