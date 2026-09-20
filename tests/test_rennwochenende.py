"""Tests fuer das gefuehrte Rennwochenende (Punkt 12).

Der Reiter fuehrt durch Vorschau, Qualifying, Rennen und Ergebnis. Er
rechnet nichts selbst - die Arbeit macht ``kern.saison.Wochenendlauf``,
geprueft in ``test_saison.py``. Hier geht es um die Fuehrung: dass die
Schritte in der richtigen Reihenfolge kommen, dass die Vorschau nichts
bewegt und dass am Ende die Saison wirklich einen Schritt weiter ist.

Ein volles Wochenende dauert rund 22 Sekunden; die Fixture faehrt es
einmal und teilt es sich.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.rennwochenendeseite import SCHRITTE, WEITER  # noqa: E402
from tests.oberflaeche import waehle_liga

# Punkt 77: Diese Datei ist auf Wunsch des Auftraggebers stillgelegt.
# Geprueft wird erst wieder, wenn ein einzelnes Rennwochenende sauber
# steht. Die Tests bleiben stehen - ein Entfernen dieser Marke holt sie
# zurueck.
pytestmark = pytest.mark.skip(
    reason="Punkt 77: stillgelegt, bis ein einzelnes Rennwochenende sauber steht"
)


@pytest.fixture(scope="module")
def konfig(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``.

    Drei Ligen zu je vier Autos statt zwanzig zu je dreissig. Geprueft
    wird, *ob* die Logik stimmt - dafuer genuegt das kleine Feld, und ein
    Rennwochenende kostet 1,5 statt 54 Sekunden.
    """
    return kleine_konfiguration


@pytest.fixture
def fenster(qtbot, konfig):
    haupt = Hauptfenster(konfig)
    qtbot.addWidget(haupt)
    return haupt


@pytest.fixture(scope="module")
def gefahren(konfig):
    """Ein ganzes Wochenende, durchgeklickt - einmal fuer alle Tests."""
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    haupt = Hauptfenster(konfig)
    seite = haupt.wochenendeseite
    vorher = {
        "heute": haupt.karriere.heute,
        "gefahren": haupt.saisonseite.lauf.gefahren,
    }
    for _ in range(3):
        seite.knopf_weiter.click()
    return haupt, seite, vorher


# --- Der Reiter ersetzt Qualifying und Rennen -----------------------------
def test_die_alten_reiter_sind_weg(fenster) -> None:
    reiter = fenster._reiter
    namen = [reiter.tabText(i) for i in range(reiter.count())]
    assert "Rennwochenende" in namen
    assert "Qualifying" not in namen
    assert "Rennen" not in namen
    # Die Saison bleibt ein eigener Reiter.
    assert "Saison" in namen
    assert namen.index("Rennwochenende") < namen.index("Saison")


def test_die_saisonseite_faehrt_kein_einzelnes_wochenende_mehr(fenster) -> None:
    seite = fenster.saisonseite
    assert not hasattr(seite, "knopf_rennwochenende")
    assert seite.knopf_restliche_saison.isEnabled()


# --- Schritt 1: Vorschau --------------------------------------------------
def test_die_vorschau_bewegt_nichts(fenster) -> None:
    """GDD 2: Wer nur hinsieht, darf keine nutzbaren Tage verlieren."""
    seite = fenster.wochenendeseite
    assert seite.schritt == 0
    assert fenster.karriere.heute.month == 1 and fenster.karriere.heute.day == 1
    assert fenster.saisonseite.lauf.gefahren == 0
    assert seite.knopf_weiter.text() == WEITER[0]


def test_die_vorschau_nennt_strecke_runden_und_renntag(fenster, konfig) -> None:
    seite = fenster.wochenendeseite
    lauf = seite.wochenende
    assert lauf.nummer == 1
    assert lauf.strecke.name == konfig.strecken[0]["name"]
    assert lauf.runden > 0
    assert lauf.renntag == fenster.saisonseite.lauf.renntag(1)
    assert lauf.strecke.name in seite._ueberschrift.text()


def test_vor_dem_ersten_rennen_steht_das_feld_nach_staerke(fenster, konfig) -> None:
    """Es gibt noch keine Tabelle - leer bleiben darf der Kasten nicht."""
    seite = fenster.wochenendeseite
    liste = seite.vorschauliste
    assert liste.topLevelItemCount() == konfig.wert("ligen", "autos_je_liga")
    assert liste.topLevelItem(0).text(3) == "-"
    assert "Staerke" in seite._standkasten.title()

    spieler = fenster.welt.spieler
    nummern = [
        liste.topLevelItem(i).data(0, Qt.UserRole)
        for i in range(liste.topLevelItemCount())
    ]
    assert spieler.nummer in nummern
    erwartet = [f.nummer for f in fenster.welt.liga(spieler.liga)]
    assert nummern == erwartet


# --- Die Schritte in der Reihenfolge --------------------------------------
def test_die_vier_schritte_laufen_der_reihe_nach(gefahren) -> None:
    _fenster, seite, _vorher = gefahren
    assert len(SCHRITTE) == len(WEITER) == 4
    assert seite.schritt == 3
    assert seite.wochenende.qualifying is not None
    assert seite.wochenende.verlauf is not None
    assert seite.wochenende.ist_gefahren


def test_das_qualifying_fuellt_die_qualifyingseite(gefahren, konfig) -> None:
    _fenster, seite, _vorher = gefahren
    session = seite.qualifyingseite.session
    assert session is not None
    autos = konfig.wert("ligen", "autos_je_liga")
    assert len(session.fahrten) == autos
    assert len(session.aufstellung) == autos


def test_das_rennen_fuellt_die_rennseite(gefahren, konfig) -> None:
    _fenster, seite, _vorher = gefahren
    verlauf = seite.rennseite.verlauf
    assert verlauf is not None
    assert len(verlauf.teilnehmer) == konfig.wert("ligen", "autos_je_liga")
    assert verlauf.strecke.name == seite.wochenende.strecke.name
    # Die Aufstellung kommt aus dem Qualifying (GDD 4).
    pole = seite.wochenende.qualifying.aufstellung[0]
    erster = next(t for t in verlauf.teilnehmer if t.startplatz == 1)
    assert erster.kuerzel == seite.wochenende.qualifying.teilnehmer[pole].kuerzel


# --- Schritt 4: Ergebnis --------------------------------------------------
def test_erst_der_abschluss_bewegt_die_saison(gefahren) -> None:
    """GDD 2 und 13: Der Kalender springt, die Tabelle fuellt sich."""
    fenster, _seite, vorher = gefahren
    assert fenster.saisonseite.lauf.gefahren == vorher["gefahren"] + 1
    assert fenster.karriere.heute > vorher["heute"]


def test_das_ergebnis_zeigt_rennen_und_tabelle(gefahren, konfig) -> None:
    fenster, seite, _vorher = gefahren
    autos = konfig.wert("ligen", "autos_je_liga")
    assert seite.ergebnisliste.topLevelItemCount() == autos
    assert seite.tabellenliste.topLevelItemCount() == autos

    # Der Tabellenerste hat die meisten Punkte.
    punkte = [
        int(seite.tabellenliste.topLevelItem(i).text(2)) for i in range(autos)
    ]
    assert punkte == sorted(punkte, reverse=True)

    # Die Bilanz nennt den Spieler mit Namen.
    texte = " ".join(
        seite._bilanz.itemAt(i, seite._bilanz.ItemRole.LabelRole).widget().text()
        for i in range(seite._bilanz.rowCount())
    )
    assert fenster.welt.spieler.name in texte


def test_das_ergebnis_passt_zur_saisontabelle(gefahren) -> None:
    fenster, seite, _vorher = gefahren
    liga = fenster.welt.spieler.liga
    stand = fenster.saisonseite.lauf.tabelle(liga).stand()
    gezeigt = [
        seite.tabellenliste.topLevelItem(i).data(0, Qt.UserRole)
        for i in range(seite.tabellenliste.topLevelItemCount())
    ]
    assert gezeigt == [e.fahrer for e in stand]


def test_die_saisonseite_zieht_nach(gefahren) -> None:
    """Das gefuehrte Wochenende meldet sich; die Saisonseite liest neu."""
    fenster, _seite, _vorher = gefahren
    liga = fenster.welt.spieler.liga
    waehle_liga(fenster.saisonseite.liga_auswahl, liga)
    tabelle = fenster.saisonseite.tabelle
    assert tabelle.topLevelItemCount() > 0
    assert fenster.saisonseite.rennliste.topLevelItemCount() > 0


def test_danach_steht_das_naechste_wochenende_bereit(gefahren) -> None:
    fenster, seite, _vorher = gefahren
    assert seite.knopf_weiter.text() == WEITER[3]
    seite.knopf_weiter.click()
    assert seite.schritt == 0
    assert seite.wochenende.nummer == 2
    assert not seite.wochenende.ist_gefahren
    # Die Vorschau zeigt jetzt die echte Tabelle.
    assert "Staerke" not in seite._standkasten.title()
    assert seite.vorschauliste.topLevelItem(0).text(3) != "-"


# --- Saisonende -----------------------------------------------------------
def test_am_saisonende_ist_der_knopf_aus(fenster, konfig) -> None:
    """Nach Rennen 20 gibt es hier nichts mehr zu fahren (GDD 13).

    Der Wechsel ins naechste Jahr steht im Reiter Saison; hier steht nur,
    dass die Saison gefahren ist.
    """
    from tests.oberflaeche import fahre_saison_zu_ende

    seite = fenster.wochenendeseite
    # Setzt denselben Saisonlauf auf beendet, den auch die Seite haelt.
    fahre_saison_zu_ende(konfig, fenster.saisonseite)
    assert fenster.saisonseite.lauf.ist_fertig
    seite._rueste_zu()

    assert seite.wochenende is None
    assert not seite.knopf_weiter.isEnabled()
    assert str(fenster.saisonseite.lauf.jahr) in seite._ueberschrift.text()
    assert seite.vorschauliste.topLevelItemCount() == 0
