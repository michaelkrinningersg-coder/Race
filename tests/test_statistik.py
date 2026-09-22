"""Tests fuer Statistiken und Historie (GDD 13, Punkt 101).

"Rundenrekorde je Strecke in Tausendsteln. Karriere: Siege, Podien,
Pole-Positions, schnellste Runden, Gesamtpunkte je Saison. Historie
aller Saisons."
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

    Acht Autos statt fuenfzig. Geprueft wird, *ob* die Logik stimmt -
    dafuer genuegt das kleine Feld.
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
    assert statistik.melde_runde("Monza", 84_276, fahrer=1, saison=2026, rennen=1)
    rekord = statistik.rekord("Monza")
    assert rekord.zeit_ms == 84_276
    assert rekord.fahrer == 1


def test_nur_schnellere_runden_werden_rekord(statistik):
    statistik.melde_runde("Monza", 84_276, 1, 2026, 1)
    assert not statistik.melde_runde("Monza", 84_300, 2, 2026, 2)
    assert not statistik.melde_runde("Monza", 84_276, 2, 2026, 2)
    assert statistik.melde_runde("Monza", 84_275, 2, 2026, 3)
    assert statistik.rekord("Monza").fahrer == 2


def test_rekorde_gelten_je_strecke(statistik):
    """Punkt 101: eine Liga, also je Strecke genau ein Rekord."""
    statistik.melde_runde("Monza", 60_000, 1, 2026, 1)
    statistik.melde_runde("Spa", 90_000, 3, 2026, 2)

    assert statistik.rekord("Monza").zeit_ms == 60_000
    assert statistik.rekord("Spa").zeit_ms == 90_000
    assert statistik.rekord("Sakhir") is None


def test_die_qualirunde_steht_neben_der_rennrunde(statistik):
    """Punkt 93 (A17): getrennt gefuehrt - sonst faellt der Rennrekord nie."""
    statistik.melde_runde("Monza", 84_000, 1, 2026, 1)
    statistik.melde_qualirunde("Monza", 82_000, 2, 2026, 1)
    assert statistik.rekord("Monza").zeit_ms == 84_000
    assert statistik.qualirekord("Monza").zeit_ms == 82_000


def test_unsinnige_zeiten_werden_nicht_eingetragen(statistik):
    assert not statistik.melde_runde("Monza", 0, 1, 2026, 1)
    assert not statistik.melde_runde("Monza", -5, 1, 2026, 1)
    assert statistik.rekord("Monza") is None


# --- Karrierezahlen -------------------------------------------------------
def test_ein_wochenende_fuellt_die_karrierezahlen(k, statistik):
    statistik.verbuche_wochenende(
        saison=2026,
        rennen=1,
        strecke="Monza",
        ergebnisse=ergebnisse((7, 1, 1, True), (8, 2, 3), (9, 25, 30)),
        schnellste_runde_ms=84_000,
    )
    sieger = statistik.zahlen(7)
    assert (sieger.rennen, sieger.siege, sieger.podien, sieger.poles) == (1, 1, 1, 1)
    assert sieger.schnellste_runden == 1
    assert sieger.punkte == (
        wt.rennpunkte(k, 1) + wt.qualifyingpunkte(k, 1) + wt.punkte_schnellste_runde(k)
    )

    zweiter = statistik.zahlen(8)
    assert (zweiter.siege, zweiter.podien, zweiter.poles) == (0, 1, 0)
    assert zweiter.punkte == wt.rennpunkte(k, 2) + wt.qualifyingpunkte(k, 3)

    letzter = statistik.zahlen(9)
    assert letzter.punkte == 0
    assert letzter.podien == 0


def test_ausfaelle_werden_gezaehlt(k, statistik):
    aus = wt.Rennergebnis(fahrer=1, rennplatz=30, qualifyingplatz=5, ausgefallen=True)
    statistik.verbuche_wochenende(2026, 1, "Monza", (aus,))
    assert statistik.zahlen(1).ausfaelle == 1


def test_zahlen_summieren_sich_ueber_saisons(k, statistik):
    for saison in (2026, 2027):
        statistik.verbuche_wochenende(saison, 1, "Monza", ergebnisse((7, 1)))
    assert statistik.zahlen(7).rennen == 2
    assert statistik.zahlen(7).siege == 2
    assert statistik.zahlen(7).siegquote == 1.0


def test_punkte_werden_je_saison_gefuehrt(k, statistik):
    """Je Saison eine Summe - die Historie haelt sie ueber das Jahr hinaus."""
    statistik.verbuche_wochenende(2026, 1, "Monza", ergebnisse((7, 1, 9)))
    statistik.verbuche_wochenende(2026, 2, "Spa", ergebnisse((7, 2, 9)))
    statistik.verbuche_wochenende(2027, 1, "Monza", ergebnisse((7, 2, 9)))
    assert statistik.punkte_in(2026, 7) == wt.rennpunkte(k, 1) + wt.rennpunkte(k, 2)
    assert statistik.punkte_in(2027, 7) == wt.rennpunkte(k, 2)
    assert statistik.punkte_in(2025, 7) == 0


def test_bestenliste_ordnet_nach_dem_merkmal(k, statistik):
    statistik.verbuche_wochenende(2026, 1, "Monza", ergebnisse((1, 1), (2, 2), (3, 3)))
    statistik.verbuche_wochenende(2026, 2, "Spa", ergebnisse((2, 1), (1, 2), (3, 3)))
    statistik.verbuche_wochenende(2026, 3, "Spa", ergebnisse((2, 1), (3, 2), (1, 3)))

    nach_siegen = statistik.bestenliste("siege", anzahl=3)
    assert [z.fahrer for z in nach_siegen] == [2, 1, 3]
    nach_podien = statistik.bestenliste("podien", anzahl=3)
    assert all(z.podien == 3 for z in nach_podien)


def test_gleichstand_entscheiden_die_punkte(k, statistik):
    """Sonst stuenden bei gleicher Siegzahl die Fahrernummern durcheinander."""
    statistik.verbuche_wochenende(2026, 1, "Monza", ergebnisse((1, 1, 9), (2, 1, 1)))
    beste = statistik.bestenliste("siege", anzahl=2)
    assert [z.fahrer for z in beste] == [2, 1]
    assert beste[0].punkte > beste[1].punkte


def test_unbekanntes_merkmal_faellt_auf(statistik):
    with pytest.raises(stt.StatistikFehler):
        statistik.bestenliste("lieblingsfarbe")


# --- Historie -------------------------------------------------------------
def test_saisonabschluss_kommt_in_die_historie(k, statistik):
    tabelle = wt.Tabelle()
    tabelle.verbuche(k, ergebnisse((10, 1), (11, 2)))
    statistik.schliesse_saison(2026, tabelle)

    assert statistik.saisons == (2026,)
    abschluss = statistik.abschluss(2026)
    assert abschluss.meister == 10
    assert abschluss.platz_von(11) == 2
    assert abschluss.platz_von(99) is None
    assert statistik.abschluss(2027) is None


def test_titel_und_laufbahn_lassen_sich_nachschlagen(k, statistik):
    for saison, gewinner in ((2026, 7), (2027, 7), (2028, 8)):
        tabelle = wt.Tabelle()
        tabelle.verbuche(k, ergebnisse((gewinner, 1), (7 if gewinner != 7 else 8, 2)))
        statistik.schliesse_saison(saison, tabelle)

    titel = statistik.titel_von(7)
    assert [a.saison for a in titel] == [2026, 2027]
    assert statistik.laufbahn(7) == ((2026, 1), (2027, 1), (2028, 2))


# --- Zusammenspiel mit dem Saisonlauf -------------------------------------
def test_der_saisonlauf_fuellt_die_statistik(k):
    """Ein Rennwochenende muss Rekorde, Karriere und Punkte fuellen."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(2).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(2), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    assert len(lauf.statistik.rekorde) == 1
    assert len(lauf.statistik.karriere) == len(welt.fahrer)

    rekord = lauf.statistik.rekord(wochenende.strecke)
    assert rekord.zeit_ms == wochenende.schnellste_runde_ms
    assert rekord.saison == 2026 and rekord.rennen == 1

    # Und die Punkte stehen doppelt: in der Tabelle und in der Statistik.
    for eintrag in lauf.tabelle.stand():
        assert lauf.statistik.punkte_in(2026, eintrag.fahrer) == eintrag.punkte


def test_die_streckenkenntnis_steht_fest(k):
    """Punkt 101: Sie waechst nicht mehr - ein Rennen aendert sie nicht."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(2).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(2), jahr=2026, strecken=strecken)
    vorher = dict(lauf.kenntnis.runden)
    lauf.fahre_rennen()
    assert lauf.kenntnis.runden == vorher


# -- Punkt 102: Fuehrungsrunden --------------------------------------------
def test_die_fuehrungsrunden_eines_rennens_landen_in_der_karriere(k):
    """Was das Rennmodell zaehlt, muss auch in den Zahlen ankommen."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(4).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(4), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    gemeldet = wochenende.fuehrungsrunden_je_fahrer
    assert gemeldet, "Irgendwer muss gefuehrt haben"
    for fahrer, anzahl in gemeldet.items():
        assert lauf.statistik.zahlen(fahrer).fuehrungsrunden == anzahl


def test_jede_runde_hat_genau_einen_fuehrenden(k):
    """Die Summe ist die Renndistanz - daraus wird auch der Nenner."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(4).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(4), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    runden = sum(wochenende.fuehrungsrunden_je_fahrer.values())
    assert runden > 0
    # Jeder Starter bekommt die Distanz als gefahrene Runden - auch der,
    # der nie vorn lag. Sonst haette der Anteil keinen Nenner.
    for ergebnis in wochenende.ergebnisse:
        zahlen = lauf.statistik.zahlen(ergebnis.fahrer)
        assert zahlen.gefahrene_runden == runden
    letzter = lauf.statistik.zahlen(wochenende.ergebnisse[-1].fahrer)
    assert letzter.fuehrungsanteil == 0.0


def test_der_anteil_haengt_an_den_gefahrenen_runden(k):
    zahlen = stt.Karrierezahlen(fahrer=1, fuehrungsrunden=30, gefahrene_runden=120)
    assert zahlen.fuehrungsanteil == pytest.approx(0.25)
    # Ohne gefahrene Runden gibt es keinen Anteil - und keine Division.
    assert stt.Karrierezahlen(fahrer=2).fuehrungsanteil == 0.0


def test_die_abschlusstabelle_traegt_die_fuehrungsrunden_der_saison(k):
    """Beim Saisonwechsel wandert die Zahl in die Historie."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(4).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(4), jahr=2026, strecken=strecken)
    lauf.fahre_saison()
    lauf.schliesse_ab()

    abschluss = lauf.statistik.abschluss(2026)
    assert abschluss is not None
    gesamt = sum(z.fuehrungsrunden for z in abschluss.zeilen)
    # Ueber die ganze Saison: so viele Runden, wie gefahren wurden.
    erwartet = sum(
        sum(w.fuehrungsrunden_je_fahrer.values()) for w in lauf.wochenenden
    )
    assert gesamt == erwartet
    # Der Meister hat in aller Regel am meisten gefuehrt - aber nicht
    # zwingend; gesichert ist nur, dass die Zahl zur Saison passt.
    for zeile in abschluss.zeilen:
        assert zeile.fuehrungsrunden == lauf.statistik.saisonfuehrung.get(
            (2026, zeile.fahrer), 0
        )


# -- Vorschlag 16: Fuehrungsrunden je Strecke und Wetterlage ----------------
def test_die_fuehrungsrunden_stehen_auch_in_der_streckenbilanz(k):
    """Dieselbe Zahl noch einmal dort, wo sie zustande kam."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(4).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(4), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    runden = sum(wochenende.fuehrungsrunden_je_fahrer.values())
    for fahrer, anzahl in wochenende.fuehrungsrunden_je_fahrer.items():
        bilanz = lauf.statistik.strecke_von(fahrer, wochenende.strecke)
        assert bilanz.fuehrungsrunden == anzahl
    # Und der Nenner steht bei jedem Starter, auch beim Letzten.
    for ergebnis in wochenende.ergebnisse:
        bilanz = lauf.statistik.strecke_von(ergebnis.fahrer, wochenende.strecke)
        assert bilanz.gefahrene_runden == runden


def test_die_fuehrungsrunden_stehen_auch_in_der_wetterbilanz(k):
    """Nach dem ersten Rennen ist die Lage des Rennens voll belegt."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(4).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(4), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()

    lage = wochenende.vorherrschendes_wetter
    assert lage, "Jedes Rennen hat eine vorherrschende Lage (Punkt 23)"
    runden = sum(wochenende.fuehrungsrunden_je_fahrer.values())
    gesamt = sum(
        lauf.statistik.wetter_von(e.fahrer, lage).fuehrungsrunden
        for e in wochenende.ergebnisse
    )
    assert gesamt == runden


def test_zwei_strecken_teilen_die_fuehrungsrunden_auf(k):
    """Die Summe ueber die Strecken ist die Karrierezahl - nicht mehr."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(4).zweig("welt"))
    lauf = sa.Saisonlauf(k, welt, Seedquelle(4), jahr=2026, strecken=strecken)
    erstes = lauf.fahre_rennen()
    zweites = lauf.fahre_rennen()
    assert erstes.strecke != zweites.strecke, "Zwei verschiedene Strecken"

    for fahrer in (e.fahrer for e in zweites.ergebnisse):
        zahlen = lauf.statistik.zahlen(fahrer)
        je_strecke = lauf.statistik.strecken_von(fahrer)
        assert sum(b.fuehrungsrunden for b in je_strecke.values()) == (
            zahlen.fuehrungsrunden
        )
        assert sum(b.gefahrene_runden for b in je_strecke.values()) == (
            zahlen.gefahrene_runden
        )


def test_ohne_strecke_und_lage_bleiben_die_bilanzen_leer(statistik):
    """Der alte Aufrufweg fuehrt weiter nur die Karrierezahlen.

    Wichtig, damit ``verbuche_fuehrungsrunden`` nicht heimlich Bilanzen
    anlegt, die nie ein Rennen gesehen haben.
    """
    statistik.verbuche_fuehrungsrunden(2026, {1: 10}, [1, 2])
    assert statistik.zahlen(1).fuehrungsrunden == 10
    assert not statistik.streckenbilanz
    assert not statistik.wetterbilanz


def test_der_anteil_einer_bilanz_haengt_an_den_gefahrenen_runden():
    bilanz = stt.Bilanz(rennen=2, fuehrungsrunden=15, gefahrene_runden=60)
    assert bilanz.fuehrungsanteil == pytest.approx(0.25)
    # Ohne Nenner kein Anteil - und keine Division durch null.
    assert stt.Bilanz(rennen=1).fuehrungsanteil == 0.0
