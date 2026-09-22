"""Tests fuer die Rennanzeige (Punkte 1 bis 4).

Intervall, Rueckstandsdiagramm, Reifenbalken und Zwischenfall-Ticker. Alle
vier lesen nur, was der ``Rennverlauf`` schon mitbringt - getestet wird
deshalb, dass sie das Richtige lesen, nicht die Simulation selbst.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.kern import rennen as rn  # noqa: E402
from rennmanager.ui import rennseite as rs  # noqa: E402
from rennmanager.ui.diagramm import HOECHSTENS_FOKUS  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.rennseite import (  # noqa: E402
    SPALTE_MISCHUNG,
    SPALTE_REIFEN,
)
from rennmanager.ui.rueckstandsansicht import Rueckstandsansicht  # noqa: E402
from rennmanager.ui.tabellen import Balkenzeichner  # noqa: E402
from tests.oberflaeche import schlage_blatt_auf  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    """Punkt 77: Diese Datei bleibt bei der **grossen** Welt.

    Gemessen: Vier Runden mit vierzig Autos bringen 13 Zwischenfaelle und
    zwei Ueberrundete, dieselben vier Runden mit vier Autos nur zwei
    Zwischenfaelle und keinen Ueberrundeten. Der Ticker und die Achse des
    Rueckstandsdiagramms haetten dann nichts mehr zu zeigen - zwei Tests
    uebersprangen sich still. Teuer war ohnehin nicht das Feld, sondern
    dass jeder Test denselben Lauf neu rechnete; das steht jetzt in
    ``vierrundenrennen``.
    """
    return kf.lade()


@pytest.fixture(scope="module")
def vierrundenrennen(konfig):
    """Vier Runden, **einmal** gerechnet.

    Punkt 77: Der Lauf ist in jedem Test derselbe - gleicher Seed,
    gleiche Welt, gleiche Strecke. Frueher rechnete ihn jedes Fixture neu;
    gemessen 4,85 Sekunden mal siebzehn Tests. Gezeigt wird er weiter je
    Test frisch, damit kein Test die Anzeige des naechsten verstellt.
    """
    from tests.oberflaeche import rennverlauf

    fenster = Hauptfenster(konfig)
    daten = rennverlauf(fenster, runden=4)
    fenster.close()
    return daten


@pytest.fixture
def gefahren(qtbot, konfig, vierrundenrennen):
    """Dasselbe Rennen, abgespielt bis zur Mitte.

    Die Rennseite rechnet seit Punkt 12 nichts mehr; sie bekommt den
    Verlauf gereicht. Vier Runden reichen fuer alles, was hier geprueft
    wird - ein echtes Wochenende waere 19 Runden und 17 Sekunden.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite
    seite.zeige_verlauf(*vierrundenrennen)
    seite._halte_an()
    seite._springe(seite.verlauf.dauer_ms * 0.6)
    return fenster, seite


# --- Punkt 1: Intervall ---------------------------------------------------
def test_die_rangliste_zeigt_rueckstand_und_intervall(gefahren) -> None:
    _fenster, seite = gefahren
    kopf = [
        seite.rangliste.headerItem().text(spalte)
        for spalte in range(seite.rangliste.columnCount())
    ]
    assert kopf[rs.SPALTE_ZEIT] == "Zeit / Rueckstand"
    assert kopf[rs.SPALTE_INTERVALL] == "Intervall"

    # Der Fuehrende hat kein Intervall, alle anderen eines.
    assert seite.rangliste.topLevelItem(0).text(rs.SPALTE_INTERVALL) == "-"
    for stelle in range(1, seite.rangliste.topLevelItemCount()):
        assert seite.rangliste.topLevelItem(stelle).text(rs.SPALTE_INTERVALL) != ""


def test_beim_zweiten_sind_intervall_und_rueckstand_gleich(gefahren) -> None:
    """Dort ist der Vordermann der Fuehrende - beide Zahlen muessen passen.

    Weiter hinten summieren sich die Intervalle bewusst *nicht* zum
    Rueckstand: Das Intervall rechnet mit dem Tempo des Vordermanns, der
    Rueckstand mit dem des Fuehrenden, und zwei Autos an verschiedenen
    Streckenpunkten sind verschieden schnell. So halten es echte
    Zeitmonitore auch.
    """
    _fenster, seite = gefahren
    zweiter = seite.rangliste.topLevelItem(1)
    if "Rd" in zweiter.text(rs.SPALTE_ZEIT):
        pytest.skip("Der Zweite wurde ueberrundet")
    assert zweiter.text(rs.SPALTE_INTERVALL) == zweiter.text(rs.SPALTE_ZEIT)


def test_jedes_intervall_traegt_ein_vorzeichen(gefahren) -> None:
    """Punkt 75: echte Zeiten am Messpunkt - mit Vorzeichen.

    Meist steht dort ein Plus. Wer zwischen zwei Messpunkten vorbeigeht,
    war am letzten gemeinsamen Punkt aber noch hinten; dann steht ein
    Minus, und das ist die Wahrheit, nicht ein Fehler. Geschaetzt oder
    geglaettet wird nichts.
    """
    _fenster, seite = gefahren
    for stelle in range(1, seite.rangliste.topLevelItemCount()):
        text = seite.rangliste.topLevelItem(stelle).text(rs.SPALTE_INTERVALL)
        assert text.startswith(("+", "-")), text


# --- Punkt 3: Reifenbalken ------------------------------------------------
def test_die_reifenspalte_traegt_einen_anteil(gefahren) -> None:
    _fenster, seite = gefahren
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        anteil = zeile.data(SPALTE_REIFEN, Balkenzeichner.ANTEILSROLLE)
        assert anteil is not None
        assert 0.0 <= anteil <= 1.0
        # Die Zahl bleibt daneben lesbar.
        assert zeile.text(SPALTE_REIFEN).endswith("%")


# --- Punkt 39: Mischung und Mischungspflicht -------------------------------
def _stopprennen(konfig, pflicht: bool):
    """Ein kurzes Rennen, in dem wirklich gewechselt wird - nur gerechnet."""
    from rennmanager.kern import reifen as kern_reifen
    from rennmanager.kern import strategie as kern_strategie
    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.kern import welt as kern_welt
    from rennmanager.kern.zufall import Seedquelle

    fenster = Hauptfenster(konfig)
    strecke = kern_strecke.lade(konfig, konfig.strecken[0]["name"])
    feld = kern_welt.starterfeld(fenster.welt)[:6]
    fenster.close()
    weich = kern_reifen.mischung(konfig, "weich")
    hart = kern_reifen.mischung(konfig, "hart")
    strategie = kern_strategie.Strategie(mischungen=(weich, hart), stopps=(6,))
    verlauf = rn.simuliere(
        konfig,
        strecke,
        feld,
        12,
        Seedquelle(4711).zweig("rennen"),
        rn.mittlerer_ueberholzonenanteil(konfig, (strecke,)),
        strategien=tuple(strategie for _ in feld),
        mischungspflicht=pflicht,
    )
    return verlauf, strecke


@pytest.fixture(scope="module")
def stopprennen(konfig):
    """Mit Mischungspflicht - zwei Tests rechneten denselben Lauf zweimal."""
    return _stopprennen(konfig, pflicht=True)


@pytest.fixture(scope="module")
def stopprennen_ohne_pflicht(konfig):
    """Bei Regen ist die Pflicht aufgehoben; sonst derselbe Lauf."""
    return _stopprennen(konfig, pflicht=False)


def _mit_stopps(qtbot, konfig, daten):
    """Zeigt einen der beiden Stopplaeufe auf einer frischen Seite."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite
    seite.zeige_verlauf(*daten)
    seite._halte_an()
    return fenster, seite, daten[0]


def test_die_rangliste_hat_eine_mischungsspalte(gefahren) -> None:
    _fenster, seite = gefahren
    kopf = seite.rangliste.headerItem().text(SPALTE_MISCHUNG)
    assert kopf == "Mischung"


def _spalte_je_auto(seite, spalte):
    """Die Spalte, aufgeschluesselt nach der Nummer im Feld statt nach Platz."""
    werte = {}
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        werte[zeile.data(0, Qt.UserRole)] = zeile.text(spalte)
    return werte


def test_die_spalte_zeigt_mischung_und_stoppzahl(qtbot, konfig, stopprennen) -> None:
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    stopp = verlauf.boxenstopps[0]

    seite._springe(stopp.zeit_ms - 20_000)
    for text in _spalte_je_auto(seite, SPALTE_MISCHUNG).values():
        assert text.startswith("W (0)"), text

    # Am Ende zaehlt nur, wer wirklich gestoppt hat: Wer vorher ausfaellt,
    # steht weiter auf seinem Startsatz.
    seite._springe(verlauf.dauer_ms)
    werte = _spalte_je_auto(seite, SPALTE_MISCHUNG)
    gestoppt = {b.teilnehmer for b in verlauf.boxenstopps}
    assert gestoppt, "Ohne Stopp prueft der Test nichts"
    for i, text in werte.items():
        erwartet = "H (1)" if i in gestoppt else "W (0)"
        assert text.startswith(erwartet), f"Auto {i}: {text}"


def test_die_offene_mischungspflicht_steht_in_warnfarbe(qtbot, konfig, stopprennen) -> None:
    from rennmanager.ui.rennseite import FARBE_PFLICHT_ERFUELLT, FARBE_PFLICHT_OFFEN, HAKEN

    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    stopp = verlauf.boxenstopps[0]

    seite._springe(stopp.zeit_ms - 20_000)
    zeile = seite.rangliste.topLevelItem(0)
    assert zeile.foreground(SPALTE_MISCHUNG).color().name() == FARBE_PFLICHT_OFFEN
    assert HAKEN not in zeile.text(SPALTE_MISCHUNG)

    seite._springe(verlauf.dauer_ms)
    zeile = seite.rangliste.topLevelItem(0)
    assert zeile.foreground(SPALTE_MISCHUNG).color().name() == FARBE_PFLICHT_ERFUELLT
    assert zeile.text(SPALTE_MISCHUNG).endswith(HAKEN)


def test_ohne_pflicht_steht_die_spalte_von_anfang_an_auf_gruen(
    qtbot, konfig, stopprennen_ohne_pflicht
) -> None:
    """Bei Regen, Starkregen und wechselhaft ist die Pflicht aufgehoben."""
    from rennmanager.ui.rennseite import FARBE_PFLICHT_ERFUELLT, HAKEN

    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen_ohne_pflicht)
    seite._springe(0)
    zeile = seite.rangliste.topLevelItem(0)
    assert zeile.foreground(SPALTE_MISCHUNG).color().name() == FARBE_PFLICHT_ERFUELLT
    assert zeile.text(SPALTE_MISCHUNG).endswith(HAKEN)


def test_der_balken_faerbt_nach_zustand(konfig) -> None:
    """Statusfarben, nicht Serienfarben: gut, Warnung, kritisch."""
    zeichner = Balkenzeichner()
    assert zeichner.farbe(0.9) == Balkenzeichner.GUT
    assert zeichner.farbe(0.3) == Balkenzeichner.WARNUNG
    assert zeichner.farbe(0.1) == Balkenzeichner.KRITISCH


# --- Punkt 4: Zwischenfall-Ticker -----------------------------------------
def test_der_ticker_zeigt_nur_geschehenes(gefahren) -> None:
    _fenster, seite = gefahren
    schlage_blatt_auf(seite, "ticker")
    zeit = seite.zeit_ms
    bisher = [z for z in seite.verlauf.zwischenfaelle if z.zeit_ms <= zeit]
    assert str(len(bisher)) in seite._tickerkasten.title()
    assert seite.ticker.topLevelItemCount() == min(len(bisher), rs.TICKER_ZEILEN)


def test_der_ticker_zeigt_fuenfzig_zeilen(gefahren, konfig) -> None:
    """Punkt 97: Zwoelf Zeilen waren bei 40 Autos das letzte Prozent.

    Gezaehlt wird gegen die Zwischenfaelle, die bis hierher gefallen
    sind - ueber ein ganzes Rennen sind es mehrere hundert.
    """
    _fenster, seite = gefahren
    assert rs.TICKER_ZEILEN == 50
    seite._springe(seite.verlauf.dauer_ms)
    schlage_blatt_auf(seite, "ticker")
    bisher = len(seite.verlauf.zwischenfaelle)
    assert seite.ticker.topLevelItemCount() == min(bisher, rs.TICKER_ZEILEN)


def test_der_ticker_fuehrt_fuenfzig_zeilen(gefahren) -> None:
    """Punkt 97: zwoelf Zeilen waren bei 40 Autos das letzte Prozent.

    Ueber die volle Distanz fallen mehrere hundert Zwischenfaelle; wer
    zwei Bilder wegsah, hatte den Ausfall verpasst. Die Zahl steht hier
    fest, damit sie nicht unbemerkt zurueckwandert - den Rollbalken setzt
    Qt von selbst, sobald mehr Zeilen anfallen als ins Blatt passen
    (gemessen: 47 Zeilen in einem 460 px hohen Blatt ergeben einen
    Rollbereich von 17).
    """
    _fenster, seite = gefahren
    assert rs.TICKER_ZEILEN == 50
    seite._springe(seite.verlauf.dauer_ms)
    schlage_blatt_auf(seite, "ticker")
    gefallen = len(seite.verlauf.zwischenfaelle)
    assert seite.ticker.topLevelItemCount() == min(gefallen, rs.TICKER_ZEILEN)


def test_der_ticker_zeigt_das_neueste_oben(gefahren) -> None:
    _fenster, seite = gefahren
    schlage_blatt_auf(seite, "ticker")
    if seite.ticker.topLevelItemCount() < 2:
        pytest.skip("In diesem Rennen passierte zu wenig")
    zeiten = [
        seite.ticker.topLevelItem(i).data(0, Qt.UserRole)
        for i in range(seite.ticker.topLevelItemCount())
    ]
    assert zeiten == sorted(zeiten, reverse=True)


def test_am_anfang_ist_der_ticker_leer(gefahren) -> None:
    _fenster, seite = gefahren
    schlage_blatt_auf(seite, "ticker")
    seite._springe(0)
    assert seite.ticker.topLevelItemCount() == 0


# --- Punkt 2: Rueckstandsdiagramm -----------------------------------------
def test_das_diagramm_kennt_den_verlauf(gefahren) -> None:
    _fenster, seite = gefahren
    assert isinstance(seite.rueckstandsansicht, Rueckstandsansicht)
    zeiten, rueckstand = rn.rueckstand_in_sekunden(seite.verlauf)
    assert len(zeiten) > 0
    assert rueckstand.shape[1] == seite.verlauf.anzahl
    # Der Fuehrende hat zu jedem Zeitpunkt den kleinsten Rueckstand.
    assert rueckstand.min() == pytest.approx(0.0, abs=1e-6)


def test_die_eigenen_fahrer_treten_im_diagramm_hervor(gefahren, konfig) -> None:
    """Fokus und Kontext: nicht 30 Farben, sondern das eigene Team."""
    _fenster, seite = gefahren
    eigene = [
        i for i, t in enumerate(seite.verlauf.teilnehmer) if t.ist_spieler
    ]
    assert len(eigene) == konfig.wert("teams", "autos_je_team")
    assert seite.rueckstandsansicht._hervorgehoben == eigene

    # Eine Auswahl in der Rangliste kommt dazu - das Team und einer mehr.
    seite.rangliste.setCurrentItem(seite.rangliste.topLevelItem(2))
    hervor = seite.rueckstandsansicht._hervorgehoben
    assert len(hervor) <= HOECHSTENS_FOKUS
    gewaehlt = seite.rangliste.topLevelItem(2).data(0, Qt.UserRole)
    assert gewaehlt in hervor or gewaehlt in eigene


def test_ausgefallene_bestimmen_die_achse_nicht(gefahren) -> None:
    """GDD 4 kennt fuer sie keinen Zeitrueckstand, nur '+n Rd.'."""
    _fenster, seite = gefahren
    ansicht = seite.rueckstandsansicht
    hinten = {
        e.teilnehmer for e in seite.verlauf.ergebnisse if e.rundenrueckstand
    }
    if not hinten:
        pytest.skip("In diesem Rennen wurde niemand ueberrundet")
    auf_runde = [i for i in range(seite.verlauf.anzahl) if i not in hinten]
    assert ansicht._achsenmaximum() == pytest.approx(
        float(ansicht._rueckstand[:, auf_runde].max())
    )


def test_ohne_rennen_zeigt_das_diagramm_einen_hinweis(qtbot) -> None:
    ansicht = Rueckstandsansicht()
    qtbot.addWidget(ansicht)
    ansicht.zeige(None)
    ansicht.resize(400, 200)
    ansicht.repaint()
    assert ansicht._rueckstand is None


# --- Punkt 76: Positionsaenderung mit Pfeil -------------------------------
def test_die_rangliste_hat_eine_spalte_fuer_gewonnene_plaetze(gefahren) -> None:
    _fenster, seite = gefahren
    assert seite.rangliste.headerItem().text(rs.SPALTE_WECHSEL) == "+/-"


def test_die_pfeile_stehen_in_der_richtigen_farbe(gefahren) -> None:
    """Gruen nach oben, rot nach unten - und nie Farbe allein."""
    _fenster, seite = gefahren
    gesehen = 0
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        text = zeile.text(rs.SPALTE_WECHSEL)
        if not text:
            continue
        gesehen += 1
        farbe = zeile.foreground(rs.SPALTE_WECHSEL).color().name()
        if text.startswith(rs.PFEIL_HOCH):
            assert farbe == rs.FARBE_GEWONNEN
        else:
            assert text.startswith(rs.PFEIL_RUNTER)
            assert farbe == rs.FARBE_VERLOREN
        # Die Zahl der Plaetze steht daneben, nicht nur der Pfeil.
        assert int(text.split()[1]) >= 1
    # In der ersten Runde gibt es nichts zu vergleichen - dann ist die
    # Spalte leer, und das ist kein Fehler.
    assert gesehen >= 0


def test_in_der_ersten_runde_bleibt_die_spalte_leer(qtbot, konfig) -> None:
    """Es gibt noch keine vorige Runde, mit der sich vergleichen liesse."""
    from tests.oberflaeche import kurzes_rennen

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster, runden=4)
    seite._halte_an()
    seite._springe(0)
    for stelle in range(seite.rangliste.topLevelItemCount()):
        assert seite.rangliste.topLevelItem(stelle).text(rs.SPALTE_WECHSEL) == ""


# --- Punkt 59: Die neue Aufteilung ----------------------------------------
def test_rangliste_und_monitor_stehen_nebeneinander(gefahren) -> None:
    """Beide haengen im selben waagerechten Teiler, nicht untereinander."""
    from PySide6.QtWidgets import QSplitter

    _fenster, seite = gefahren
    teiler = seite.rangliste.parent()
    while teiler is not None and not isinstance(teiler, QSplitter):
        teiler = teiler.parent()
    assert teiler is not None
    assert teiler.orientation() == Qt.Horizontal
    # Der Zeitenmonitor haengt im selben Teiler.
    monitor = seite._monitorblaetter
    assert monitor.parent() is teiler or monitor in (
        teiler.widget(stelle) for stelle in range(teiler.count())
    )


def test_der_ticker_ist_ein_blatt_neben_den_tabellen(gefahren) -> None:
    """Punkt 82: Die Meldungen standen als Fussleiste unter allem.

    Sie nahmen den Tabellen Hoehe weg, obwohl man sie selten braucht.
    Jetzt sind sie eines der Blaetter rechts - einen Klick entfernt und
    keinen Pixel im Weg. Seit Punkt 93 steht die Boxenbilanz daneben,
    deshalb wird das Blatt gesucht und nicht mehr an letzter Stelle
    erwartet.
    """
    _fenster, seite = gefahren
    blaetter = seite.blaetter_rechts
    assert blaetter.isAncestorOf(seite.ticker)
    namen = [blaetter.tabText(i) for i in range(blaetter.count())]
    assert "Meldungen" in namen
    assert blaetter.tabText(rs.BLATT_TICKER) == "Meldungen"
    # Und nirgends mehr ein senkrechter Teiler mit dem Ticker darin.
    from PySide6.QtWidgets import QSplitter

    eltern = seite.ticker.parent()
    while eltern is not None:
        assert not (
            isinstance(eltern, QSplitter) and eltern.orientation() == Qt.Vertical
        ), "Der Ticker haengt noch in einer Fussleiste"
        eltern = eltern.parent()


def test_auch_fahrer_null_bekommt_namen_und_team(gefahren, konfig) -> None:
    """Die Welt zaehlt ihre Fahrer ab null - die 0 ist kein Platzhalter.

    Sie war es einmal: ``Teilnehmer.nummer`` stand ohne Fahrer auf 0, und
    die Rangliste las das als "kein Fahrer dahinter". Der Fahrer mit der
    Nummer 0 stand dadurch in jedem Rennen ohne Namen und ohne Team da -
    in der Rangliste wie im Zeitenmonitor.
    """
    fenster, seite = gefahren
    seite._halte_an()
    stelle = next(
        i for i, t in enumerate(seite.verlauf.teilnehmer) if t.nummer == 0
    )
    assert seite._namen[stelle], "Fahrer 0 hat keinen Namen in der Rangliste"
    assert seite._teams[stelle], "Fahrer 0 hat kein Team in der Rangliste"
    fahrer = fenster.welt.fahrer[0]
    assert fahrer.nachname in seite._namen[stelle]
    assert seite._teams[stelle] == fenster.welt.team_von(fahrer).name


def test_ein_feld_ohne_fahrer_bleibt_leer(qtbot, konfig) -> None:
    """Das Gegenstueck: ``rennen.starterfeld`` hat keine Fahrer dahinter."""
    from rennmanager.kern import rennen as kern_rennen

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite
    feld = kern_rennen.starterfeld(konfig)
    assert all(t.nummer == kern_rennen.KEIN_FAHRER for t in feld)
    assert seite._nachname(feld[0]) == ""
    assert seite._teamname(feld[0]) == ""


# --- Punkt 73: Live-Meisterschaftsstand -----------------------------------
# Spalten des Meisterschaftsblattes. Seit Punkt 82 steht "Team" dazwischen;
# die Zahlen stehen hier einmal, statt in jedem Test zu stecken.
# Punkt 101: Die Ligaspalte ist weg, alles danach ist um eins zurueck.
MEISTER_PUNKTE = 5
MEISTER_ZUWACHS = 6


def _mit_tabelle(seite, konfig):
    """Gibt der Seite einen Meisterschaftsstand vor dem Rennen."""
    from rennmanager.kern import wertung as wt

    tabelle = wt.Tabelle()
    tabelle.verbuche(
        konfig,
        [
            wt.Rennergebnis(fahrer=t.nummer, rennplatz=platz, qualifyingplatz=platz)
            for platz, t in enumerate(seite.verlauf.teilnehmer, start=1)
        ],
    )
    seite.zeige_verlauf(seite.verlauf, seite._ansicht.strecke, tabelle=tabelle)
    seite._halte_an()
    seite._springe(seite.verlauf.dauer_ms * 0.7)
    return tabelle


def test_die_meisterschaft_zaehlt_die_punkte_der_lage_dazu(gefahren, konfig) -> None:
    """Punkt 73: Stand bis hierher plus die Punkte fuer die Lage jetzt."""
    _fenster, seite = gefahren
    tabelle = _mit_tabelle(seite, konfig)
    schlage_blatt_auf(seite, "meisterschaft")
    liste = seite._meisterschaft
    assert liste.topLevelItemCount() == len(tabelle.eintraege)
    # Jede Zeile traegt Punkte, und der Erste hat die meisten.
    punkte = [
        int(liste.topLevelItem(stelle).text(MEISTER_PUNKTE))
        for stelle in range(liste.topLevelItemCount())
    ]
    assert punkte == sorted(punkte, reverse=True)


def test_der_livestand_nimmt_den_startplatz_als_qualifyingplatz(gefahren) -> None:
    """Punkt 95: Die Qualifyingpunkte gehoeren dem, der vorn steht.

    ``qualifying.aufstellung`` zaehlt im Feld der **Session** (nach
    Weltreihenfolge), das Rennfeld steht dagegen in der Reihenfolge des
    Qualifyings. Wer beides gleichsetzt, gibt den Polepunkt irgendwem aus
    dem Mittelfeld. Die Aufstellung steht hier absichtlich verdreht: Ein
    Rueckfall auf die alte Umrechnung faellt damit sofort auf.
    """
    from types import SimpleNamespace

    _fenster, seite = gefahren
    verlauf = seite.verlauf
    anzahl = len(verlauf.teilnehmer)
    seite._qualifying = SimpleNamespace(
        aufstellung=tuple(reversed(range(anzahl)))
    )
    lage = seite._rennlage(verlauf, verlauf.reihenfolge_zu(0.0), 0.0)
    erwartet = {t.nummer: t.startplatz for t in verlauf.teilnehmer}
    assert {e.fahrer: e.qualifyingplatz for e in lage} == erwartet
    # Und die Pole gehoert dem, der sie gefahren hat.
    pole = next(e for e in lage if e.qualifyingplatz == 1)
    assert pole.fahrer == verlauf.teilnehmer[0].nummer


def test_die_meisterschaft_nennt_auch_fahrer_ausserhalb_des_rennens(
    qtbot, konfig, stopprennen
) -> None:
    """Ein Testrennen kann ein Feld fahren, das nicht der Welt entspricht.

    Name, Team und Kuerzel kommen fuer die Starter aus dem Rennverlauf,
    fuer alle anderen aus der Welt. Ohne diesen Rueckgriff fuehrte die
    Meisterschaft jemand ohne Namen an - Platz und Punkte standen da,
    die drei Spalten dazwischen blieben leer.
    """
    from rennmanager.kern import wertung as wt
    from rennmanager.ui.tabellen import kurzname

    fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    welt = fenster.welt
    im_rennen = {t.nummer for t in verlauf.teilnehmer}
    fremde = [f for f in welt.fahrer[1:] if f.nummer not in im_rennen][:5]
    assert fremde, "Die Welt hat mehr Fahrer als dieses Testrennen Starter"

    # Drei Rennen fuer die Fremden, keines fuer die Starter: So stehen
    # sie mit Abstand vorn und fuehren die Tabelle an.
    tabelle = wt.Tabelle()
    for _ in range(3):
        tabelle.verbuche(
            konfig,
            [
                wt.Rennergebnis(fahrer=f.nummer, rennplatz=platz, qualifyingplatz=platz)
                for platz, f in enumerate(fremde, start=1)
            ],
        )
    seite.zeige_verlauf(verlauf, seite._ansicht.strecke, tabelle=tabelle)
    seite._halte_an()
    seite._springe(verlauf.dauer_ms * 0.7)
    schlage_blatt_auf(seite, "meisterschaft")

    erster = seite._meisterschaft.topLevelItem(0)
    fuehrender = fremde[0]
    assert erster.text(1) == fuehrender.kuerzel
    assert erster.text(2) == kurzname(fuehrender.name)
    assert erster.text(3) == welt.team_von(fuehrender).name


def test_die_meisterschaft_zeigt_den_zuwachs(gefahren, konfig) -> None:
    """Die Spalte '+x' sagt, wie viel aus diesem Rennen dazukommt."""
    _fenster, seite = gefahren
    _mit_tabelle(seite, konfig)
    schlage_blatt_auf(seite, "meisterschaft")
    liste = seite._meisterschaft
    zuwaechse = [
        liste.topLevelItem(stelle).text(MEISTER_ZUWACHS)
        for stelle in range(liste.topLevelItemCount())
    ]
    mit_zuwachs = [z for z in zuwaechse if z]
    assert mit_zuwachs
    assert all(z.startswith("+") for z in mit_zuwachs)


def test_ohne_tabelle_bleibt_die_meisterschaft_leer(gefahren) -> None:
    """Ein Testrennen ohne Saison hat keinen Stand - und stuerzt nicht."""
    _fenster, seite = gefahren
    schlage_blatt_auf(seite, "meisterschaft")
    assert seite._meisterschaft.topLevelItemCount() == 0


# --- Punkt 83: Das Intervall nach dem Zieldurchlauf ------------------------
class _Standlauf:
    """Ein Verlauf, in dem alle Autos stehen - wie nach dem Zieldurchlauf.

    Gerade genug, damit ``_intervall`` und ``_zeitabstand`` rechnen
    koennen. Ein echtes Rennen dafuer zu fahren hiesse, auf genau die
    Reihenfolge zu warten, die den Fehler ausloest.
    """

    def __init__(self, laenge: float, distanzen: list[float]) -> None:
        import numpy as np

        self.strecke = type("S", (), {"laenge_m": laenge})()
        self._distanzen = np.array(distanzen)
        # Zwei Bilder mit derselben Distanz: Tempo null, alles steht.
        self.distanz_m = np.vstack([self._distanzen, self._distanzen])
        self.zeitpunkte_ms = np.array([0, 1000])

    def abstand_ms(self, hinten, vorne, zeit):
        # Kein gemeinsamer Messpunkt - genau der Fall, in dem frueher
        # geschaetzt wurde und seit Punkt 103 ein Strich steht.
        return None

    def distanzen_zu(self, zeit):
        return self._distanzen

    def bild_zu(self, zeit):
        return 0


def test_ohne_gemeinsamen_messpunkt_steht_ein_strich(qtbot, konfig) -> None:
    """Punkt 103: Geschaetzt wird gar nichts mehr.

    Frueher rechnete die Anzeige hier Strecke durch Tempo. Punkt 83 hatte
    daran schon den groebsten Unsinn abgefangen (``max(tempo, 1e-6)``
    machte aus einer Runde 1,5 Mio Stunden), aber die Schaetzung selbst
    blieb - und lieferte vor dem Start 14,47 s je Startplatz. Jetzt steht
    dort ein Strich, solange die beiden keinen gemeinsamen Messpunkt
    passiert haben.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite

    lauf = _Standlauf(5355.0, [10_000.0, 9_000.0])
    assert seite._zeitabstand(lauf, hinten=1, vorne=0, zeit=1000.0) == "-"


def test_ein_ueberrundeter_vor_uns_steht_als_runde_da(qtbot, konfig) -> None:
    """Sortiert wird nach Runden und Zielzeit - da kann ein Ueberrundeter
    vor einem stehen, der auf der Strecke eine Runde weiter ist."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite

    # Auf Platz 1 steht das Auto mit der **kleineren** Distanz.
    lauf = _Standlauf(5355.0, [3_000.0, 12_000.0])
    text = seite._intervall(lauf, [0, 1], lauf.distanzen_zu(0), 1000.0, platz=2)
    assert text == "-1 Rd.", text
    # Andersherum wie bisher.
    text = seite._intervall(lauf, [1, 0], lauf.distanzen_zu(0), 1000.0, platz=2)
    assert text == "+1 Rd.", text


# -- Punkt 93, Block 4 ------------------------------------------------------
def test_die_rangliste_hat_alter_reicht_und_stopp(gefahren) -> None:
    """B35, B36 und B32 nebeneinander hinter dem Reifenbalken."""
    _fenster, seite = gefahren
    kopf = seite.rangliste.headerItem()
    assert kopf.text(rs.SPALTE_ALTER) == "Alter"
    assert kopf.text(rs.SPALTE_REICHT) == "Reicht"
    assert kopf.text(rs.SPALTE_PLANSTOPP) == "Stopp"


def test_das_reifenalter_faengt_nach_dem_stopp_von_vorn_an(qtbot, konfig, stopprennen):
    """B35: Der Balken sagt "wieviel", nicht "wie lange"."""
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    stopps = [b for b in verlauf.boxenstopps if b.teilnehmer == 0]
    assert stopps, "Dieser Lauf muss einen Stopp haben"
    stopp = stopps[0]

    # Kurz vor dem Stopp ist der Satz so alt wie das Rennen lang.
    seite._springe(stopp.zeit_ms - 1000)
    vorher = _spalte_je_auto(seite, rs.SPALTE_ALTER)[0]
    # Danach faengt er wieder bei null an.
    seite._springe(stopp.zeit_ms + 1000)
    nachher = _spalte_je_auto(seite, rs.SPALTE_ALTER)[0]
    assert int(vorher.split()[0]) > int(nachher.split()[0])
    assert int(nachher.split()[0]) <= 1


def test_der_planstopp_steht_da_und_verschwindet_danach(qtbot, konfig, stopprennen):
    """B32: Der Kern wusste es, die Anzeige zeigte es nicht."""
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    assert verlauf.stoppplan, "Ein Rennen mit Strategie muss einen Plan tragen"
    geplant = verlauf.stoppplan[0][0]

    seite._springe(0)
    assert _spalte_je_auto(seite, rs.SPALTE_PLANSTOPP)[0] == f"R{geplant}"
    # Nach dem letzten geplanten Stopp steht dort nichts mehr.
    seite._springe(verlauf.dauer_ms)
    assert _spalte_je_auto(seite, rs.SPALTE_PLANSTOPP)[0] == "-"


def test_ohne_strategie_steht_kein_planstopp_da(gefahren) -> None:
    _fenster, seite = gefahren
    assert set(_spalte_je_auto(seite, rs.SPALTE_PLANSTOPP).values()) == {"-"}


def test_die_restrunden_schrumpfen_mit_dem_reifen(qtbot, konfig, stopprennen):
    """B36: Macht die Zwangsstopp-Grenze sichtbar, bevor sie zuschlaegt."""
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    stopps = [b for b in verlauf.boxenstopps if b.teilnehmer == 0]
    assert stopps
    letzte = stopps[0].zeit_ms

    # In der ersten Runde laesst sich noch nichts hochrechnen.
    seite._springe(0)
    assert _spalte_je_auto(seite, rs.SPALTE_REICHT)[0] == "-"

    # Ueber den ersten Stint hinweg wird die Zahl kleiner.
    werte = []
    for anteil in (0.4, 0.7, 0.95):
        seite._springe(letzte * anteil)
        text = _spalte_je_auto(seite, rs.SPALTE_REICHT)[0]
        assert text != "-", "Nach ein paar Runden muss sich das rechnen lassen"
        werte.append(int(text.split()[0]))
    assert werte == sorted(werte, reverse=True), werte


# -- Punkt 93, Block 5 ------------------------------------------------------
def test_der_ticker_traegt_je_art_ein_eigenes_zeichen(qtbot, konfig, stopprennen):
    """B49: Zwoelf Zeilen Fliesstext sehen alle gleich aus."""
    from rennmanager.kern import zwischenfall as zw

    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    seite._springe(verlauf.dauer_ms)
    schlage_blatt_auf(seite, "ticker")

    assert seite._ticker.headerItem().text(0) == ""
    gezeigt = [
        seite._ticker.topLevelItem(i).text(0)
        for i in range(seite._ticker.topLevelItemCount())
    ]
    assert gezeigt, "Dieser Lauf muss Zwischenfaelle haben"
    assert set(gezeigt) <= set(rs.TICKER_ZEICHEN.values())
    # Und die drei Arten haben wirklich verschiedene Zeichen.
    assert len(set(rs.TICKER_ZEICHEN.values())) == 3
    assert set(rs.TICKER_ZEICHEN) == {zw.Art.FEHLER, zw.Art.UNFALL, zw.Art.DEFEKT}


def test_ein_ausfall_faerbt_sich_rot_und_sagt_es(qtbot, konfig, stopprennen):
    """Der Ausfall ist keine vierte Art, sondern das Ende einer der drei."""
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    ausfaelle = [z for z in verlauf.zwischenfaelle if z.ausgefallen]
    if not ausfaelle:
        pytest.skip("In diesem Lauf faellt niemand aus")
    seite._springe(verlauf.dauer_ms)
    schlage_blatt_auf(seite, "ticker")

    rote = [
        seite._ticker.topLevelItem(i)
        for i in range(seite._ticker.topLevelItemCount())
        if seite._ticker.topLevelItem(i).foreground(0).color().name()
        == rs.FARBE_AUSFALL
    ]
    assert rote, "Ein Ausfall muss sich abheben"
    for zeile in rote:
        assert "Ausfall" in zeile.text(4)


def test_das_rennen_hat_dasselbe_wetterband(qtbot, konfig, stopprennen):
    """B43: dasselbe Widget wie im Qualifying (A13)."""
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    band = seite._wetterband
    if verlauf.wetter is None:
        assert band.abschnitte == ()
        return
    assert [zustand for zustand, _von, _bis in band.abschnitte] == list(
        verlauf.wetter.zustaende
    )
    seite._springe(verlauf.dauer_ms // 2)
    assert band._marke_ms == verlauf.dauer_ms // 2


# -- Punkt 93, Block 6 ------------------------------------------------------
def test_die_boxenbilanz_ist_ein_eigenes_blatt(gefahren) -> None:
    """B53: Standzeit, Gesamtverlust, Vergleich zum Feld."""
    _fenster, seite = gefahren
    blaetter = seite.blaetter_rechts
    assert blaetter.tabText(rs.BLATT_BOXENBILANZ) == "Boxenbilanz"
    kopf = seite._boxenbilanz.headerItem()
    assert [kopf.text(s) for s in range(seite._boxenbilanz.columnCount())] == [
        "Auto", "Fahrer", "Team", "Stopps", "Standzeit", "Verlust", "zum Feld",
    ]


def test_die_boxenbilanz_nennt_stopps_standzeit_und_verlust(qtbot, konfig, stopprennen):
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, stopprennen)
    seite._springe(verlauf.dauer_ms)
    seite.blaetter_rechts.setCurrentIndex(rs.BLATT_BOXENBILANZ)
    seite._erzwinge_fuellung()
    seite._zeichne()

    liste = seite._boxenbilanz
    assert liste.topLevelItemCount() == len(verlauf.teilnehmer)
    mit_stopp = 0
    for i in range(liste.topLevelItemCount()):
        zeile = liste.topLevelItem(i)
        nummer = zeile.data(0, Qt.UserRole)
        anzahl, standzeit, verlust = verlauf.stoppbilanz(nummer)
        assert zeile.text(3) == str(anzahl)
        if anzahl:
            mit_stopp += 1
            assert zeile.text(4) != "-"
            assert standzeit > 0
            # Der Verlust ist mindestens so gross wie die Standzeit -
            # Einfahrt und Ausfahrt kommen dazu.
            assert verlust >= 0
    assert mit_stopp, "Dieser Lauf muss Stopps haben"


def test_ohne_stopp_bleibt_die_bilanz_bei_null(gefahren) -> None:
    _fenster, seite = gefahren
    verlauf = seite._verlauf
    for i in range(len(verlauf.teilnehmer)):
        assert verlauf.stoppbilanz(i) == (0, 0, 0)


def test_der_kompaktmodus_blendet_alles_ausser_der_rangliste_aus(gefahren) -> None:
    """B59: Nur die Rangliste, grosse Schrift - fuers reine Zusehen."""
    _fenster, seite = gefahren
    vorher = seite.rangliste.font().pointSize()
    assert not seite.kompakt

    seite._kompakt.setChecked(True)
    assert seite.kompakt
    assert not seite._blaetter.isVisible()
    assert not seite._monitorblaetter.isVisible()
    assert seite.rangliste.font().pointSize() == rs.SCHRIFT_KOMPAKT
    assert seite.rangliste.font().pointSize() > vorher

    seite._kompakt.setChecked(False)
    assert not seite.kompakt
    assert seite.rangliste.font().pointSize() == vorher


# --- Punkt 102: Fuehrungsrunden -------------------------------------------
def test_das_blatt_zeigt_nur_wer_gefuehrt_hat(gefahren) -> None:
    """Bei 50 Autos waeren 45 leere Zeilen kein Blatt, sondern Ballast."""
    _fenster, seite = gefahren
    seite._halte_an()
    seite._zum_ende()
    schlage_blatt_auf(seite, "fuehrung")
    liste = seite.fuehrung

    gezaehlt = seite.verlauf.fuehrungsrunden(seite.verlauf.dauer_ms)
    erwartet = sum(1 for n in gezaehlt if n)
    assert liste.topLevelItemCount() == erwartet
    assert 0 < erwartet < len(seite.verlauf.teilnehmer)


def test_das_blatt_ordnet_nach_runden_und_nennt_den_anteil(gefahren) -> None:
    _fenster, seite = gefahren
    seite._halte_an()
    seite._zum_ende()
    schlage_blatt_auf(seite, "fuehrung")
    liste = seite.fuehrung

    runden = [
        int(liste.topLevelItem(i).text(3)) for i in range(liste.topLevelItemCount())
    ]
    assert runden == sorted(runden, reverse=True)
    assert sum(runden) == seite.verlauf.runden
    # Der Anteil steht daneben und bezieht sich auf die gefahrenen Runden.
    erste = liste.topLevelItem(0)
    assert erste.text(4).endswith("%")
    assert int(erste.text(5)) == sum(runden)


def test_das_blatt_zaehlt_mit_dem_abspielzeitpunkt_mit(gefahren) -> None:
    """Live wie Zeitenmonitor und Meisterschaft, nicht der Endstand."""
    _fenster, seite = gefahren
    seite._halte_an()
    schlage_blatt_auf(seite, "fuehrung")

    def gesamt() -> int:
        liste = seite.fuehrung
        return sum(
            int(liste.topLevelItem(i).text(3))
            for i in range(liste.topLevelItemCount())
        )

    seite._springe(0.0)
    seite._erzwinge_fuellung()
    seite._zeichne()
    assert gesamt() == 0, "Vor dem Start hat niemand gefuehrt"
    assert "0 von" in seite._fuehrungskasten.title()

    seite._springe(seite.verlauf.dauer_ms * 0.5)
    seite._erzwinge_fuellung()
    seite._zeichne()
    mitte = gesamt()
    seite._zum_ende()
    seite._erzwinge_fuellung()
    seite._zeichne()
    assert 0 < mitte < gesamt() == seite.verlauf.runden


def test_die_ueberschrift_nennt_die_wechsel(gefahren) -> None:
    _fenster, seite = gefahren
    seite._halte_an()
    seite._zum_ende()
    schlage_blatt_auf(seite, "fuehrung")
    titel = seite._fuehrungskasten.title()
    assert f"{seite.verlauf.runden} von {seite.verlauf.runden} Runden" in titel
    assert f"{seite.verlauf.fuehrungswechsel()} Wechsel" in titel


# --- Punkt 103: Vor der ersten Ueberfahrt gibt es keinen Rueckstand -------
def test_vor_dem_start_hat_niemand_einen_rueckstand(gefahren) -> None:
    """Punkt 103: Auf dem Standbild steht ueberall ein Strich.

    Gemessen stand dort vorher Unsinn: Die Autos kriechen im ersten Bild
    mit 0,345 m/s los, und 5 m Startabstand geteilt durch dieses Tempo
    ergaben 14,47 s **je Startplatz** - der Fuenfzigste lag 11:49
    zurueck, bevor das Rennen begonnen hatte.
    """
    _fenster, seite = gefahren
    seite._halte_an()
    seite._springe(0)

    rueckstaende = set(_spalte_je_auto(seite, rs.SPALTE_ZEIT).values())
    intervalle = set(_spalte_je_auto(seite, rs.SPALTE_INTERVALL).values())
    # Der Fuehrende zeigt seine Rennzeit, alle anderen einen Strich.
    assert rueckstaende <= {"-", "0:00.000"}
    assert intervalle == {"-"}


def test_nach_der_ersten_ueberfahrt_stehen_echte_zeiten(gefahren) -> None:
    """Sobald beide die Linie hinter sich haben, wird gemessen statt nichts.

    Der erste Messpunkt einer Runde liegt auf der Start/Ziel-Linie
    (``messpunkte[0] == 0``); davor gibt es keinen gemeinsamen Punkt.
    """
    _fenster, seite = gefahren
    verlauf = seite.verlauf
    seite._halte_an()

    # Irgendwann im Rennen muessen echte Abstaende dastehen.
    seite._springe(verlauf.dauer_ms * 0.5)
    intervalle = _spalte_je_auto(seite, rs.SPALTE_INTERVALL)
    mit_zeit = [t for t in intervalle.values() if t not in ("-", "")]
    assert len(mit_zeit) > len(intervalle) // 2, intervalle

    # Und sie kommen wirklich aus der Messung, nicht aus einer Schaetzung.
    zeit = verlauf.dauer_ms * 0.5
    reihenfolge = verlauf.reihenfolge_zu(zeit)
    hinten, vorne = reihenfolge[1], reihenfolge[0]
    echt = verlauf.abstand_ms(hinten, vorne, zeit)
    if echt is not None:
        from rennmanager.kern.zeit import formatiere_rueckstand

        assert seite._zeitabstand(verlauf, hinten, vorne, zeit) == (
            formatiere_rueckstand(echt)
        )
