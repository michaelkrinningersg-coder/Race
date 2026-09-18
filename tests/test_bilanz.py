"""Tests fuer Block 4: Streckenbilanz, Wetterbilanz und Bestmarken.

Die Bilanzen sind **Summen**, keine Rennlisten: 600 Fahrer mal 20 Rennen
mal beliebig vielen Saisons waere ein Spielstand, der endlos waechst.
Getestet wird deshalb vor allem, dass die Summen stimmen und dass sie
nicht mit der Zahl der Saisons wachsen.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import saison as sa
from rennmanager.kern import statistik as kern_statistik
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern.wetter import Abschnitt, Wetterverlauf
from rennmanager.kern.zufall import Seedquelle

SEED = 12
LIGA = 20


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def gefahren(k):
    """Vier Rennwochenenden im Schnellmodus."""
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=LIGA)
    lauf = sa.Saisonlauf(k, welt, Seedquelle(SEED), jahr=2026, strecken=strecken)
    for _ in range(4):
        lauf.fahre_rennen()
    return lauf


# --- Die vorherrschende Wetterlage (Punkt 23) -----------------------------
def lage(*paare) -> Wetterverlauf:
    return Wetterverlauf(
        abschnitte=tuple(Abschnitt(z, ab, (1.0,)) for z, ab in paare), uebergang_ms=0
    )


def test_vorherrschend_ist_die_laengste_lage() -> None:
    """Nicht die erste und nicht die haeufigste - die laengste."""
    verlauf = lage(("regen", 0), ("trocken", 120_000))
    assert verlauf.vorherrschend(600_000) == "trocken"
    # Wird das Rennen vorher abgebrochen, war es ein Regenrennen.
    assert verlauf.vorherrschend(60_000) == "regen"


def test_vorherrschend_zaehlt_eine_lage_zusammen() -> None:
    """Trocken-Regen-Trocken ist ein trockenes Rennen."""
    verlauf = lage(("trocken", 0), ("regen", 30_000), ("trocken", 50_000))
    assert verlauf.vorherrschend(100_000) == "trocken"


def test_bei_gleichstand_gewinnt_die_fruehere() -> None:
    """Sonst haengt das Ergebnis an der Reihenfolge eines Woerterbuchs."""
    verlauf = lage(("regen", 0), ("trocken", 50_000))
    assert verlauf.vorherrschend(100_000) == "regen"


def test_eine_einzige_lage_bleibt_sie_selbst() -> None:
    assert lage(("heiss", 0)).vorherrschend(500_000) == "heiss"


def test_beide_rennmodelle_liefern_eine_lage(gefahren) -> None:
    wochenende = gefahren.wochenenden[0]
    for liga in sorted(wochenende.ligen):
        ergebnis = wochenende.liga(liga)
        assert ergebnis.vorherrschendes_wetter, f"Liga {liga} ohne Lage"
        assert ergebnis.vorherrschendes_wetter in ergebnis.wetter


# --- Die Bilanzen (Punkte 21 und 23) --------------------------------------
def test_die_summen_passen_zur_karriere(gefahren) -> None:
    """Jedes Rennen zaehlt genau einmal - je Strecke und je Wetterlage."""
    s = gefahren.statistik
    for fahrer in gefahren.welt.fahrer:
        zahlen = s.zahlen(fahrer.nummer)
        strecken = s.strecken_von(fahrer.nummer)
        wetter = s.wetterlagen_von(fahrer.nummer)
        assert sum(b.rennen for b in strecken.values()) == zahlen.rennen
        assert sum(b.rennen for b in wetter.values()) == zahlen.rennen
        assert sum(b.siege for b in strecken.values()) == zahlen.siege
        assert sum(b.punkte for b in wetter.values()) == zahlen.punkte


def test_die_bilanz_waechst_nicht_mit_den_saisons(k) -> None:
    """Der entscheidende Punkt: Summen statt Rennliste.

    Nach vier Rennen stehen 600 x 4 Streckenzeilen; nach acht Rennen auf
    denselben vier Strecken waeren es bei einer Rennliste doppelt so
    viele. Als Summe bleibt es bei 600 x 4.
    """
    strecken = st.lade_alle(k)
    welt = kw.erzeuge(k, Seedquelle(3).zweig("welt"), spielerliga=LIGA)
    lauf = sa.Saisonlauf(k, welt, Seedquelle(3), jahr=2026, strecken=strecken)
    for _ in range(2):
        lauf.fahre_rennen()
    nach_zwei = len(lauf.statistik.streckenbilanz)
    assert nach_zwei == len(welt.fahrer) * 2

    # Zwei weitere Rennen auf zwei weiteren Strecken: zwei Zeilen mehr je
    # Fahrer, nicht vier.
    for _ in range(2):
        lauf.fahre_rennen()
    assert len(lauf.statistik.streckenbilanz) == len(welt.fahrer) * 4


def test_bester_platz_und_beste_liga(k) -> None:
    from rennmanager.kern.wertung import Rennergebnis

    bilanz = kern_statistik.Bilanz()
    bilanz.verbuche(k, Rennergebnis(fahrer=1, rennplatz=7, qualifyingplatz=9), liga=20)
    assert bilanz.bester_platz == 7
    assert bilanz.beste_liga == 0  # kein Podium

    bilanz.verbuche(k, Rennergebnis(fahrer=1, rennplatz=2, qualifyingplatz=1), liga=20)
    assert bilanz.bester_platz == 2
    assert bilanz.beste_liga == 20
    assert bilanz.poles == 1

    # Ein Podium in einer staerkeren Liga zaehlt mehr, ein schwaecheres nicht.
    bilanz.verbuche(k, Rennergebnis(fahrer=1, rennplatz=3, qualifyingplatz=4), liga=5)
    assert bilanz.beste_liga == 5
    bilanz.verbuche(k, Rennergebnis(fahrer=1, rennplatz=1, qualifyingplatz=2), liga=12)
    assert bilanz.beste_liga == 5
    assert bilanz.siege == 1
    assert bilanz.bester_platz == 1


def test_ein_ausfall_verdirbt_den_besten_platz_nicht(k) -> None:
    """Wer ausfaellt, steht formal auf Platz 30 - das ist kein Ergebnis."""
    from rennmanager.kern.wertung import Rennergebnis

    bilanz = kern_statistik.Bilanz()
    bilanz.verbuche(k, Rennergebnis(fahrer=1, rennplatz=4, qualifyingplatz=4), liga=20)
    bilanz.verbuche(
        k,
        Rennergebnis(fahrer=1, rennplatz=30, qualifyingplatz=4, ausgefallen=True),
        liga=20,
    )
    assert bilanz.bester_platz == 4
    assert bilanz.ausfaelle == 1
    assert bilanz.rennen == 2


def test_quoten_ohne_rennen_sind_null() -> None:
    leer = kern_statistik.Bilanz()
    assert leer.siegquote == 0.0
    assert leer.podestquote == 0.0


def test_die_bilanz_findet_sich_von_beiden_seiten(gefahren) -> None:
    """Je Fahrer und je Strecke - dieselben Zahlen, zwei Wege."""
    s = gefahren.statistik
    strecke = gefahren.wochenenden[0].strecke
    ueber_strecke = s.bilanzen_auf(strecke)
    assert len(ueber_strecke) == len(gefahren.welt.fahrer)

    fahrer = next(iter(ueber_strecke))
    assert s.strecken_von(fahrer)[strecke] is ueber_strecke[fahrer]

    # Beim Wetter faehrt nicht jede Liga dieselbe Lage, deshalb die Probe
    # ueber die Fahrer der Spielerliga.
    lage = gefahren.wochenenden[0].liga(LIGA).vorherrschendes_wetter
    ueber_lage = s.bilanzen_bei(lage)
    ligafahrer = {f.nummer for f in gefahren.welt.liga(LIGA)}
    assert ligafahrer <= set(ueber_lage)
    assert all(b.rennen for b in ueber_lage.values())


def test_ohne_wetterangabe_bleibt_die_wetterbilanz_leer(k) -> None:
    """Alte Spielstaende kennen die Lage nicht - dann zaehlt nur die Strecke."""
    from rennmanager.kern.wertung import Rennergebnis

    s = kern_statistik.Statistik(k)
    s.verbuche_wochenende(
        saison=2026,
        rennen=1,
        liga=20,
        strecke="Sakhir",
        ergebnisse=(Rennergebnis(fahrer=1, rennplatz=1, qualifyingplatz=1),),
    )
    assert s.strecken_von(1)["Sakhir"].siege == 1
    assert s.wetterlagen_von(1) == {}


# --- Die Anzeige ----------------------------------------------------------
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.statistikseite import (  # noqa: E402
    BESTMARKEN,
    BILANZSPALTEN,
    STRECKENBILANZ,
    WETTERBILANZ,
)


@pytest.fixture
def fenster(qtbot, k):
    haupt = Hauptfenster(k)
    qtbot.addWidget(haupt)
    for _ in range(3):
        haupt.saisonseite.lauf.fahre_rennen()
    haupt.statistikseite.aktualisiere()
    return haupt


def waehle(seite, art: str) -> None:
    stellen = [seite.ansicht.itemData(i) for i in range(seite.ansicht.count())]
    seite.ansicht.setCurrentIndex(stellen.index(art))


def test_die_fahrerkarte_zeigt_die_streckenbilanz(fenster, k) -> None:
    """Punkt 21: Was er dort erreicht hat, neben dem, was er dort kann."""
    liga = fenster.welt.spieler.liga
    bester = fenster.saisonseite.lauf.tabelle(liga).stand()[0].fahrer
    karte = fenster.oeffne_fahrerkarte(bester)

    liste = karte.streckenliste
    kopf = [liste.headerItem().text(s) for s in range(liste.columnCount())]
    for spalte in BILANZSPALTEN:
        assert spalte in kopf
    assert liste.topLevelItemCount() == len(fenster.saisonseite.lauf.strecken)

    # Die drei gefahrenen Strecken tragen Zahlen, die uebrigen nicht.
    gefahrene = {w.strecke for w in fenster.saisonseite.lauf.wochenenden}
    starts = kopf.index("Starts")
    mit_zahlen = {
        liste.topLevelItem(i).text(0)
        for i in range(liste.topLevelItemCount())
        if liste.topLevelItem(i).text(starts)
    }
    assert mit_zahlen == gefahrene


def test_die_fahrerkarte_hat_einen_wetterreiter(fenster, k) -> None:
    """Punkt 23: eine Zeile je Lage aus GDD 7, auch fuer ungefahrene."""
    karte = fenster.oeffne_fahrerkarte(fenster.welt.spieler.nummer)
    namen = [karte.blaetter.tabText(i) for i in range(karte.blaetter.count())]
    assert namen[-1] == "Wetter"

    liste = karte.wetterliste
    lagen = k.wert("wetter", "kette")
    assert liste.topLevelItemCount() == len(lagen)
    assert [liste.topLevelItem(i).text(0) for i in range(len(lagen))] == list(lagen)
    # Neben jeder Lage steht die Faehigkeit dazu (GDD 7).
    assert "Trockenroutine" in liste.topLevelItem(lagen.index("trocken")).text(1)


def test_die_statistikseite_zeigt_die_streckenbilanz(fenster) -> None:
    seite = fenster.statistikseite
    waehle(seite, STRECKENBILANZ)
    strecke = seite.streckenauswahl.currentData()

    assert seite.tabelle.topLevelItemCount() == len(fenster.welt.fahrer)
    assert "Streckenbilanz" in seite._kasten.title()
    # Der Erste hat die meisten Siege.
    siege = [
        int(seite.tabelle.topLevelItem(i).text(4))
        for i in range(seite.tabelle.topLevelItemCount())
    ]
    assert siege == sorted(siege, reverse=True)
    assert sum(siege) == len(
        [w for w in fenster.saisonseite.lauf.wochenenden if w.strecke == strecke]
    ) * len(fenster.saisonseite.lauf.tabellen)


def test_die_statistikseite_zeigt_die_wetterbilanz(fenster) -> None:
    seite = fenster.statistikseite
    waehle(seite, WETTERBILANZ)
    assert "Wetterbilanz" in seite._kasten.title()
    # Ungefahrene Lagen sagen das, statt eine leere Tabelle zu zeigen.
    if not seite.tabelle.topLevelItemCount():
        assert "noch kein Rennen" in seite._hinweis.text()
    else:
        assert "Fahrer gewertet" in seite._hinweis.text()


def test_die_bestmarken_nennen_strecke_karriere_und_saison(fenster, k) -> None:
    """Punkt 25: drei Gruppen auf einer Seite."""
    seite = fenster.statistikseite
    waehle(seite, BESTMARKEN)
    marken = [
        seite.tabelle.topLevelItem(i).text(0)
        for i in range(seite.tabelle.topLevelItemCount())
    ]
    assert marken, "Nach drei Rennen muss es Bestmarken geben"
    # Je gefahrener Strecke eine schnellste Runde.
    gefahrene = {w.strecke for w in fenster.saisonseite.lauf.wochenenden}
    for strecke in gefahrene:
        assert f"Schnellste Runde in {strecke}" in marken
    assert any(m.startswith("Meiste Siege (Karriere)") for m in marken)
    # Saisonmarken erst nach einem Saisonwechsel.
    assert not any("in einer Saison" in m for m in marken)

    # Jede Marke nennt einen Fahrer, und ein Doppelklick oeffnet ihn.
    zeile = seite.tabelle.topLevelItem(0)
    assert zeile.text(2)
    assert zeile.data(0, Qt.UserRole)


def test_die_bestmarken_kennen_die_beste_saison(fenster, k) -> None:
    from tests.test_ui import fahre_saison_zu_ende

    fahre_saison_zu_ende(k, fenster.saisonseite)
    fenster.saisonseite.knopf_naechste_saison.click()
    fenster._baue_neu_auf()

    seite = fenster.statistikseite
    seite.aktualisiere()
    waehle(seite, BESTMARKEN)
    marken = [
        seite.tabelle.topLevelItem(i).text(0)
        for i in range(seite.tabelle.topLevelItemCount())
    ]
    assert "Meiste Punkte in einer Saison" in marken
    assert "Meiste Siege in einer Saison" in marken


# --- Bestmarken je Liga ---------------------------------------------------
def test_die_bestmarken_lassen_sich_je_liga_umschalten(fenster, k) -> None:
    """Insgesamt gewinnt fast immer Liga 1 - dort faehrt das staerkste Feld."""
    from rennmanager.ui.statistikseite import ALLE_LIGEN

    seite = fenster.statistikseite
    waehle(seite, BESTMARKEN)
    assert seite.bestmarkenliga.currentData() == ALLE_LIGEN
    assert seite.bestmarkenliga.count() == k.wert("ligen", "anzahl") + 1
    assert "insgesamt" in seite._kasten.title()

    # Am Anfang geht es nur vorwaerts, am Ende nur zurueck.
    assert not seite.knopf_liga_zurueck.isEnabled()
    assert seite.knopf_liga_vor.isEnabled()

    seite.knopf_liga_vor.click()
    assert seite.bestmarkenliga.currentData() == 1
    assert "Liga 1" in seite._kasten.title()
    assert seite.knopf_liga_zurueck.isEnabled()

    seite.knopf_liga_zurueck.click()
    assert seite.bestmarkenliga.currentData() == ALLE_LIGEN

    seite.bestmarkenliga.setCurrentIndex(seite.bestmarkenliga.count() - 1)
    assert not seite.knopf_liga_vor.isEnabled()
    assert seite.knopf_liga_zurueck.isEnabled()


def test_in_einer_liga_zaehlen_nur_deren_rekorde(fenster, k) -> None:
    """Die Rundenrekorde einer Ligaansicht sind die dieser Liga."""
    seite = fenster.statistikseite
    waehle(seite, BESTMARKEN)
    liga = fenster.welt.spieler.liga
    stellen = [
        seite.bestmarkenliga.itemData(i) for i in range(seite.bestmarkenliga.count())
    ]
    seite.bestmarkenliga.setCurrentIndex(stellen.index(liga))

    gefahrene = {w.strecke for w in fenster.saisonseite.lauf.wochenenden}
    zeilen = {
        seite.tabelle.topLevelItem(i).text(0): seite.tabelle.topLevelItem(i)
        for i in range(seite.tabelle.topLevelItemCount())
    }
    for strecke in gefahrene:
        marke = zeilen[f"Schnellste Runde in {strecke}"]
        assert f"Liga {liga}," in marke.text(3)
        # Und es ist wirklich der Rekord dieser Liga.
        rekord = fenster.statistik.rekord(strecke, liga)
        assert fenster.welt.fahrer[rekord.fahrer].name == marke.text(2)


def test_die_ligamarken_kommen_aus_der_historie(fenster, k) -> None:
    """Karrierezahlen wissen nicht, in welcher Liga ein Sieg fiel.

    Deshalb zaehlt die Ligaansicht aus der Historie - und dann muss der
    Karrieresieger derselbe sein wie der Saisonsieger, solange erst eine
    Saison abgeschlossen ist.
    """
    from tests.test_ui import fahre_saison_zu_ende

    fahre_saison_zu_ende(k, fenster.saisonseite)
    fenster.saisonseite.knopf_naechste_saison.click()
    fenster._baue_neu_auf()

    seite = fenster.statistikseite
    seite.aktualisiere()
    waehle(seite, BESTMARKEN)
    liga = 14
    stellen = [
        seite.bestmarkenliga.itemData(i) for i in range(seite.bestmarkenliga.count())
    ]
    seite.bestmarkenliga.setCurrentIndex(stellen.index(liga))

    zeilen = {
        seite.tabelle.topLevelItem(i).text(0): seite.tabelle.topLevelItem(i)
        for i in range(seite.tabelle.topLevelItemCount())
    }
    karriere = zeilen[f"Meiste Siege (Karriere in Liga {liga})"]
    saison = zeilen["Meiste Siege in einer Saison"]
    assert karriere.text(2) == saison.text(2)
    assert karriere.text(1) == saison.text(1)
    assert f"Liga {liga}" in saison.text(3)

    # Und die Summe stimmt mit der Historie ueberein.
    summen = fenster.statistik.karriere_in_liga(liga)
    beste = max(summen.values(), key=lambda z: z.siege)
    assert fenster.welt.fahrer[beste.fahrer].name == karriere.text(2)


def test_karriere_in_liga_summiert_nur_diese_liga(fenster, k) -> None:
    from tests.test_ui import fahre_saison_zu_ende

    fahre_saison_zu_ende(k, fenster.saisonseite)
    fenster.saisonseite.knopf_naechste_saison.click()
    fenster._baue_neu_auf()
    statistik = fenster.statistik

    gesamt = 0
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        summen = statistik.karriere_in_liga(liga)
        gesamt += sum(z.rennen for z in summen.values())
    # Jedes Rennen jedes Fahrers steckt in genau einer Liga-Summe.
    aus_historie = sum(
        zeile.rennen
        for abschluss in statistik.historie
        for zeile in abschluss.zeilen
    )
    assert gesamt == aus_historie > 0
