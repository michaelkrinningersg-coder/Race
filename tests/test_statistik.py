"""Tests fuer Statistiken und Historie (GDD 13).

"Rundenrekorde je Strecke und Liga in Tausendsteln. Karriere: Siege,
Podien, Pole-Positions, schnellste Runden, Gesamtpunkte je Liga und
Saison. Historie aller Saisons und Ligen."
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import saison as sa
from rennmanager.kern import statistik as stt
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern import wertung as wt
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``.

    Drei Ligen zu je vier Autos statt zwanzig zu je dreissig. Geprueft
    wird, *ob* die Logik stimmt - dafuer genuegt das kleine Feld, und ein
    Rennwochenende kostet 1,5 statt 54 Sekunden.
    """
    return kleine_konfiguration


@pytest.fixture
def statistik(k) -> stt.Statistik:
    return stt.Statistik(k)


def ergebnisse(*paare) -> tuple[wt.Rennergebnis, ...]:
    """(fahrer, rennplatz[, qualifyingplatz, schnellste_runde])."""
    gebaut = []
    for eintrag in paare:
        fahrer, platz = eintrag[0], eintrag[1]
        quali = eintrag[2] if len(eintrag) > 2 else platz
        schnellste = eintrag[3] if len(eintrag) > 3 else False
        gebaut.append(
            wt.Rennergebnis(
                fahrer=fahrer,
                rennplatz=platz,
                qualifyingplatz=quali,
                schnellste_runde=schnellste,
            )
        )
    return tuple(gebaut)


# --- Rundenrekorde --------------------------------------------------------
def test_die_erste_runde_ist_immer_ein_rekord(statistik):
    assert statistik.melde_runde("Monza", 10, 84_276, fahrer=1, saison=2026, rennen=1)
    rekord = statistik.rekord("Monza", 10)
    assert rekord.zeit_ms == 84_276
    assert rekord.fahrer == 1


def test_nur_schnellere_runden_werden_rekord(statistik):
    statistik.melde_runde("Monza", 10, 84_276, 1, 2026, 1)
    assert not statistik.melde_runde("Monza", 10, 84_300, 2, 2026, 2)
    assert not statistik.melde_runde("Monza", 10, 84_276, 2, 2026, 2)
    assert statistik.melde_runde("Monza", 10, 84_275, 2, 2026, 3)
    assert statistik.rekord("Monza", 10).fahrer == 2


def test_rekorde_gelten_je_strecke_und_liga(statistik):
    """GDD 13 nennt beides - Liga 1 faehrt auf derselben Strecke schneller."""
    statistik.melde_runde("Monza", 1, 60_000, 1, 2026, 1)
    statistik.melde_runde("Monza", 20, 180_000, 2, 2026, 1)
    statistik.melde_runde("Spa", 1, 90_000, 3, 2026, 2)

    assert statistik.rekord("Monza", 1).zeit_ms == 60_000
    assert statistik.rekord("Monza", 20).zeit_ms == 180_000
    assert statistik.rekord("Spa", 20) is None
    # Je Strecke schnellste Liga zuerst.
    assert [r.liga for r in statistik.rekorde_je_strecke("Monza")] == [1, 20]


def test_unsinnige_zeiten_werden_nicht_eingetragen(statistik):
    assert not statistik.melde_runde("Monza", 1, 0, 1, 2026, 1)
    assert not statistik.melde_runde("Monza", 1, -5, 1, 2026, 1)
    assert statistik.rekord("Monza", 1) is None


# --- Karrierezahlen -------------------------------------------------------
def test_ein_wochenende_fuellt_die_karrierezahlen(k, statistik):
    statistik.verbuche_wochenende(
        saison=2026,
        rennen=1,
        liga=5,
        strecke="Monza",
        ergebnisse=ergebnisse((7, 1, 1, True), (8, 2, 3), (9, 25, 30)),
        schnellste_runde_ms=84_000,
    )
    sieger = statistik.zahlen(7)
    assert (sieger.rennen, sieger.siege, sieger.podien, sieger.poles) == (1, 1, 1, 1)
    assert sieger.schnellste_runden == 1
    assert sieger.punkte == (
        wt.rennpunkte(k, 5, 1) + wt.qualifyingpunkte(k, 5, 1) + wt.punkte_schnellste_runde(k, 5)
    )

    zweiter = statistik.zahlen(8)
    assert (zweiter.siege, zweiter.podien, zweiter.poles) == (0, 1, 0)
    assert zweiter.punkte == wt.rennpunkte(k, 5, 2) + wt.qualifyingpunkte(k, 5, 3)

    letzter = statistik.zahlen(9)
    assert letzter.punkte == 0
    assert letzter.podien == 0


def test_ausfaelle_werden_gezaehlt(k, statistik):
    aus = wt.Rennergebnis(fahrer=1, rennplatz=30, qualifyingplatz=5, ausgefallen=True)
    statistik.verbuche_wochenende(2026, 1, 5, "Monza", (aus,))
    assert statistik.zahlen(1).ausfaelle == 1


def test_zahlen_summieren_sich_ueber_saisons(k, statistik):
    for saison in (2026, 2027):
        statistik.verbuche_wochenende(saison, 1, 5, "Monza", ergebnisse((7, 1)))
    assert statistik.zahlen(7).rennen == 2
    assert statistik.zahlen(7).siege == 2
    assert statistik.zahlen(7).siegquote == 1.0


def test_punkte_werden_je_saison_und_liga_gefuehrt(k, statistik):
    """GDD 13: Gesamtpunkte je Liga und Saison."""
    statistik.verbuche_wochenende(2026, 1, 5, "Monza", ergebnisse((7, 1, 9)))
    statistik.verbuche_wochenende(2027, 1, 4, "Monza", ergebnisse((7, 2, 9)))
    # Punkt 95: Die Punkte haengen an der Liga - derselbe Platz bringt
    # oben mehr als unten.
    assert statistik.punkte_in(2026, 5, 7) == wt.rennpunkte(k, 5, 1)
    assert statistik.punkte_in(2027, 4, 7) == wt.rennpunkte(k, 4, 2)
    assert statistik.punkte_in(2026, 4, 7) == 0


def test_bestenliste_ordnet_nach_dem_merkmal(k, statistik):
    statistik.verbuche_wochenende(2026, 1, 5, "Monza", ergebnisse((1, 1), (2, 2), (3, 3)))
    statistik.verbuche_wochenende(2026, 2, 5, "Spa", ergebnisse((2, 1), (1, 2), (3, 3)))
    statistik.verbuche_wochenende(2026, 3, 5, "Spa", ergebnisse((2, 1), (3, 2), (1, 3)))

    nach_siegen = statistik.bestenliste("siege", anzahl=3)
    assert [z.fahrer for z in nach_siegen] == [2, 1, 3]
    nach_podien = statistik.bestenliste("podien", anzahl=3)
    assert all(z.podien == 3 for z in nach_podien)


def test_gleichstand_entscheiden_die_punkte(k, statistik):
    """Sonst stuenden bei gleicher Siegzahl die Fahrernummern durcheinander."""
    statistik.verbuche_wochenende(2026, 1, 5, "Monza", ergebnisse((1, 1, 9), (2, 1, 1)))
    beste = statistik.bestenliste("siege", anzahl=2)
    assert [z.fahrer for z in beste] == [2, 1]
    assert beste[0].punkte > beste[1].punkte


def test_unbekanntes_merkmal_faellt_auf(statistik):
    with pytest.raises(stt.StatistikFehler):
        statistik.bestenliste("lieblingsfarbe")


# --- Historie -------------------------------------------------------------
def test_saisonabschluss_kommt_in_die_historie(k, statistik):
    tabellen = {}
    for liga in (1, 2):
        tabelle = wt.Tabelle(liga)
        tabelle.verbuche(k, ergebnisse((liga * 10, 1), (liga * 10 + 1, 2)))
        tabellen[liga] = tabelle
    statistik.schliesse_saison(2026, tabellen)

    assert statistik.saisons == (2026,)
    abschluss = statistik.abschluss(2026, 1)
    assert abschluss.meister == 10
    assert abschluss.platz_von(11) == 2
    assert abschluss.platz_von(99) is None
    assert statistik.abschluss(2027, 1) is None


def test_titel_und_laufbahn_lassen_sich_nachschlagen(k, statistik):
    for saison, liga, gewinner in ((2026, 5, 7), (2027, 4, 7), (2028, 4, 8)):
        tabelle = wt.Tabelle(liga)
        tabelle.verbuche(k, ergebnisse((gewinner, 1), (7 if gewinner != 7 else 8, 2)))
        statistik.schliesse_saison(saison, {liga: tabelle})

    titel = statistik.titel_von(7)
    assert [(a.saison, a.liga) for a in titel] == [(2026, 5), (2027, 4)]
    assert statistik.laufbahn(7) == ((2026, 5, 1), (2027, 4, 1), (2028, 4, 2))


# --- Zusammenspiel mit dem Saisonlauf -------------------------------------
def test_der_saisonlauf_fuellt_die_statistik(k):
    """Ein Rennwochenende muss Rekorde, Karriere und Punkte fuellen."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(2).zweig("welt"), spielerliga=k.wert("ligen", "anzahl"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(2), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    ligen = k.wert("ligen", "anzahl")
    assert len(lauf.statistik.rekorde) == ligen
    assert len(lauf.statistik.karriere) == len(welt.fahrer)

    # Der Rekord jeder Liga passt zur schnellsten Runde des Wochenendes.
    for liga in range(1, ligen + 1):
        rekord = lauf.statistik.rekord(wochenende.strecke, liga)
        assert rekord.zeit_ms == wochenende.liga(liga).schnellste_runde_ms
        assert rekord.saison == 2026 and rekord.rennen == 1

    # Und die Punkte stehen doppelt: in der Tabelle und in der Statistik.
    unterste = k.wert("ligen", "anzahl")
    for eintrag in lauf.tabelle(unterste).stand():
        assert (
            lauf.statistik.punkte_in(2026, unterste, eintrag.fahrer) == eintrag.punkte
        )


def test_die_streckenkenntnis_waechst_mit_dem_saisonlauf(k):
    """GDD 6: mit jedem Start und jeder gefahrenen Runde."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(2).zweig("welt"), spielerliga=k.wert("ligen", "anzahl"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(2), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    for fahrer in welt.liga(k.wert("ligen", "anzahl")):
        assert lauf.kenntnis.stand(fahrer.nummer, wochenende.strecke) > 0.0
        # Auf einer Strecke, auf der noch nicht gefahren wurde, nichts.
        assert lauf.kenntnis.stand(fahrer.nummer, strecken[-1].name) == 0.0
