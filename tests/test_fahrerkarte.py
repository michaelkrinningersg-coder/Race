"""Tests fuer die Fahrerkarte.

Die Karte rechnet nichts - sie liest zusammen, was Welt, Auto, Statistik,
Streckenkenntnis und Popularitaet ohnehin fuehren. Getestet wird deshalb
zweierlei: dass sie das Richtige liest, und dass man sie aus jeder Liste
mit Fahrernamen aufbekommt.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import charakter as kern_charakter
from rennmanager.kern import kalender as kern_kalender

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QFormLayout, QLabel  # noqa: E402

from rennmanager.ui.fahrerkarte import Fahrerkarte  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.laufbahnansicht import Laufbahnansicht  # noqa: E402


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


def zeichne(widget) -> QImage:
    widget.resize(600, 300)
    bild = QImage(widget.size(), QImage.Format_ARGB32)
    widget.render(bild)
    return bild


def formularwerte(formular: QFormLayout) -> dict[str, str]:
    """Die Zeilen eines Steckbriefs als Wortpaare."""
    werte = {}
    for zeile in range(formular.rowCount()):
        marke = formular.itemAt(zeile, QFormLayout.ItemRole.LabelRole)
        feld = formular.itemAt(zeile, QFormLayout.ItemRole.FieldRole)
        if marke is not None and feld is not None:
            werte[marke.widget().text()] = feld.widget().text()
    return werte


# --- Aufbau ---------------------------------------------------------------
def test_karte_hat_sechs_reiter(fenster) -> None:
    """Fuenf aus dem ersten Bau, dazu die Wetterbilanz aus Punkt 23."""
    karte = fenster.oeffne_fahrerkarte(fenster.welt.spieler.nummer)
    namen = [karte.blaetter.tabText(i) for i in range(karte.blaetter.count())]
    assert namen == [
        "Steckbrief",
        "Werte",
        "Saison",
        "Laufbahn",
        "Strecken",
        "Wetter",
    ]
    assert karte.windowTitle().startswith(fenster.welt.spieler.name)
    # Nicht modal: Das Hauptfenster bleibt bedienbar.
    assert not karte.isModal()


def test_karte_zeigt_person_und_charakter(fenster, konfig) -> None:
    fahrer = fenster.welt.fahrer[7]
    karte = fenster.oeffne_fahrerkarte(fahrer.nummer)
    steckbrief = karte.blaetter.widget(0)
    texte = " ".join(marke.text() for marke in steckbrief.findChildren(QLabel))
    assert fahrer.land in texte
    assert fenster.welt.team_von(fahrer).name in texte
    assert kern_charakter.profil(konfig, fahrer.auto) in texte


def test_karte_misst_das_alter_wie_die_weltseite(fenster, konfig) -> None:
    """Zwei Seiten duerfen nicht zwei Alter fuer denselben Fahrer nennen."""
    fahrer = fenster.welt.fahrer[3]
    stichtag = kern_kalender.saisonstart(konfig, fenster.jahr)
    karte = fenster.oeffne_fahrerkarte(fahrer.nummer)
    assert karte._alter() == fahrer.alter_am(stichtag)

    seite = fenster.weltseite
    seite.liga_auswahl.setCurrentIndex(fahrer.liga)
    kopf = [
        seite.liste.headerItem().text(s) for s in range(seite.liste.columnCount())
    ]
    for stelle in range(seite.liste.topLevelItemCount()):
        zeile = seite.liste.topLevelItem(stelle)
        if zeile.data(0, Qt.UserRole) == fahrer.nummer:
            assert zeile.text(kopf.index("Alter")) == str(karte._alter())
            break
    else:  # pragma: no cover - der Fahrer muss in seiner Liga stehen
        raise AssertionError("Fahrer nicht in der Liste seiner Liga")


# --- Werte ----------------------------------------------------------------
def test_werte_zeigen_alle_eigenschaften(fenster, konfig) -> None:
    karte = fenster.oeffne_fahrerkarte(11)
    liste = karte.werteliste
    aeste = {
        liste.topLevelItem(i).text(0): liste.topLevelItem(i)
        for i in range(liste.topLevelItemCount())
    }
    assert len(aeste) == 4

    bereiche = next(a for name, a in aeste.items() if name.startswith("Wirkungsbereiche"))
    assert bereiche.childCount() == len(konfig.bereiche)
    fahrzeug = next(a for name, a in aeste.items() if name.startswith("Fahrzeug"))
    fahrer = next(a for name, a in aeste.items() if name.startswith("Fahrer "))
    assert fahrzeug.childCount() + fahrer.childCount() == len(konfig.faehigkeiten)
    daneben = next(a for name, a in aeste.items() if name.startswith("Neben der Matrix"))
    assert daneben.childCount() == len(konfig.zusatzfaehigkeiten)


def test_balken_messen_gegen_den_groessten_des_astes(fenster) -> None:
    """Gegen die Skala (0 bis 100.000) waere jeder Balken unsichtbar."""
    from rennmanager.ui.tabellen import Balkenzeichner

    karte = fenster.oeffne_fahrerkarte(11)
    ast = karte.werteliste.topLevelItem(0)
    anteile = [
        ast.child(i).data(2, Balkenzeichner.ANTEILSROLLE)
        for i in range(ast.childCount())
    ]
    assert max(anteile) == pytest.approx(1.0)
    assert min(anteile) > 0.0


# --- Saison und Laufbahn --------------------------------------------------
def test_saison_und_verlauf_fuellen_sich_nach_dem_rennen(fenster, konfig) -> None:
    fenster.saisonseite.lauf.fahre_rennen()
    fenster.saisonseite._aktualisiere()
    fenster.saisonseite.lauf.fahre_rennen()
    fenster.saisonseite._aktualisiere()

    liga = fenster.welt.spieler.liga
    erster = fenster.saisonseite.lauf.tabelle(liga).stand()[0]
    karte = fenster.oeffne_fahrerkarte(erster.fahrer)

    werte = formularwerte(karte.blaetter.widget(2).findChild(QFormLayout))
    assert werte["Punkte:"] == str(erster.punkte)
    assert werte["Rennen:"] == "2"
    assert werte["Platz:"].startswith("1 von")

    # Das Diagramm zeigt die ganze Liga, hervorgehoben ist genau einer.
    verlauf = karte.punkteverlauf
    assert verlauf.rennen == 2
    assert len(verlauf._reihen) == konfig.wert("ligen", "autos_je_liga")
    assert len(verlauf._hervorgehoben) == 1
    stelle = verlauf._hervorgehoben[0]
    assert verlauf._reihen[stelle][2][-1] == erster.punkte


def test_laufbahn_bleibt_vor_dem_saisonwechsel_leer(fenster) -> None:
    """GDD 13: Die Historie entsteht erst beim Saisonwechsel."""
    karte = fenster.oeffne_fahrerkarte(5)
    assert karte.laufbahn.saisons == 0
    zeichne(karte.laufbahn)


def test_laufbahn_zeigt_jede_abgeschlossene_saison(fenster, konfig) -> None:
    from tests.test_ui import fahre_saison_zu_ende

    nummer = fenster.welt.spieler.nummer
    for _ in range(2):
        fahre_saison_zu_ende(konfig, fenster.saisonseite)
        fenster.saisonseite.knopf_naechste_saison.click()
        # Der Wechsel baut das Fenster sonst erst nach der Rueckkehr in die
        # Ereignisschleife neu auf.
        fenster._baue_neu_auf()

    karte = fenster.oeffne_fahrerkarte(nummer)
    bahn = fenster.statistik.laufbahn(nummer)
    assert karte.laufbahn.saisons == len(bahn) == 2
    zeichne(karte.laufbahn)


def test_rundenrekorde_sind_nur_die_eigenen(fenster) -> None:
    fenster.saisonseite.lauf.fahre_rennen()
    fenster.saisonseite._aktualisiere()
    halter = {r.fahrer for r in fenster.statistik.rekorde.values()}
    nummer = next(iter(halter))

    karte = fenster.oeffne_fahrerkarte(nummer)
    eigene = [
        r for r in fenster.statistik.rekorde.values() if r.fahrer == nummer
    ]
    assert karte.rekordliste.topLevelItemCount() == len(eigene)
    assert karte.rekordliste.topLevelItemCount() > 0


# --- Strecken -------------------------------------------------------------
def test_strecken_zeigen_kenntnis_und_heimstrecke(fenster, konfig) -> None:
    from rennmanager.kern import heimstrecke as kern_heimstrecke

    strecken = fenster.saisonseite.lauf.strecken
    # Ein Fahrer, der eine Heimstrecke hat - sonst sagt der Test nichts.
    fahrer = next(
        f for f in fenster.welt.fahrer
        if any(kern_heimstrecke.ist_heimstrecke(f.land, s) for s in strecken)
    )
    karte = fenster.oeffne_fahrerkarte(fahrer.nummer)
    liste = karte.streckenliste
    assert liste.topLevelItemCount() == len(strecken)

    heim = [s.name for s in strecken if kern_heimstrecke.ist_heimstrecke(fahrer.land, s)]
    fett = [
        liste.topLevelItem(i).text(0)
        for i in range(liste.topLevelItemCount())
        if liste.topLevelItem(i).font(0).bold()
    ]
    assert set(fett) == set(heim)


# --- Oeffnen aus den Listen -----------------------------------------------
def test_doppelklick_oeffnet_aus_jeder_liste(fenster) -> None:
    """Welt, Saison, Qualifying, Rennen und Statistik koennen es alle."""
    fenster.saisonseite.lauf.fahre_rennen()
    fenster.saisonseite._aktualisiere()
    fenster.statistikseite.aktualisiere()

    listen = [
        fenster.weltseite.liste,
        fenster.saisonseite.tabelle,
        fenster.saisonseite.rennliste,
        fenster.statistikseite.tabelle,
    ]
    for liste in listen:
        zeile = liste.topLevelItem(0)
        assert zeile is not None
        nummer = zeile.data(0, Qt.UserRole)
        assert nummer, f"Zeile ohne Fahrernummer in {liste}"
        liste.itemDoubleClicked.emit(zeile, 0)
        assert nummer in fenster._karten
        assert fenster._karten[nummer].fahrer.nummer == nummer


def test_doppelklick_im_rennen_findet_den_fahrer(qtbot, konfig) -> None:
    """Die Rangliste fuehrt die Startnummer im Feld, nicht die des Fahrers."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    from tests.test_ui import _kurzes_rennen

    seite = _kurzes_rennen(fenster)
    seite._halte_an()
    seite._springe(seite.verlauf.dauer_ms * 0.6)

    zeile = seite.rangliste.topLevelItem(0)
    stelle = zeile.data(0, Qt.UserRole)
    erwartet = seite.verlauf.teilnehmer[stelle].nummer
    assert erwartet, "Der Teilnehmer traegt keine Fahrernummer"

    seite.rangliste.itemDoubleClicked.emit(zeile, 0)
    assert erwartet in fenster._karten
    assert fenster._karten[erwartet].fahrer.nummer == erwartet


def test_zweiter_doppelklick_oeffnet_kein_zweites_fenster(fenster) -> None:
    erste = fenster.oeffne_fahrerkarte(9)
    assert fenster.oeffne_fahrerkarte(9) is erste


def test_saisonwechsel_schliesst_offene_karten(fenster, konfig) -> None:
    """Nach Auf- und Abstieg ist die Welt eine neue."""
    from tests.test_ui import fahre_saison_zu_ende

    fenster.oeffne_fahrerkarte(4)
    assert fenster._karten

    fahre_saison_zu_ende(konfig, fenster.saisonseite)
    fenster.saisonseite.knopf_naechste_saison.click()
    fenster._baue_neu_auf()
    assert fenster._karten == {}


def test_karte_ohne_statistik_und_kenntnis_stuerzt_nicht_ab(qtbot, konfig) -> None:
    """Die Karte muss auch ohne gefahrene Saison aufgehen."""
    from rennmanager.kern import welt as kern_welt
    from rennmanager.kern.zufall import Seedquelle

    welt = kern_welt.erzeuge(konfig, Seedquelle(1))
    karte = Fahrerkarte(konfig, welt, welt.fahrer[2].nummer)
    qtbot.addWidget(karte)
    assert karte.blaetter.count() == 6
    assert karte.streckenliste.topLevelItemCount() == 0
    assert karte.rekordliste.topLevelItemCount() == 0
    assert karte.punkteverlauf.rennen == 0
    # Die Wetterlagen stehen auch ohne Statistik da, nur ohne Zahlen.
    assert karte.wetterliste.topLevelItemCount() == len(
        konfig.wert("wetter", "kette")
    )
    assert karte.wetterliste.topLevelItem(0).text(2) == ""


# --- Laufbahndiagramm ------------------------------------------------------
def test_laufbahn_stellt_liga_1_nach_oben(qtbot) -> None:
    ansicht = Laufbahnansicht(20)
    qtbot.addWidget(ansicht)
    ansicht.resize(400, 200)
    ansicht.zeige([(2026, 20, 3), (2027, 18, 1), (2028, 15, 7)])
    assert ansicht.saisons == 3

    from rennmanager.ui.diagramm import flaeche_in
    from rennmanager.ui.laufbahnansicht import (
        RAND_LINKS,
        RAND_OBEN,
        RAND_RECHTS,
        RAND_UNTEN,
    )

    flaeche = flaeche_in(400, 200, RAND_LINKS, RAND_RECHTS, RAND_OBEN, RAND_UNTEN)
    assert ansicht._y(flaeche, 1) < ansicht._y(flaeche, 20)
    assert ansicht._y(flaeche, 1) == pytest.approx(flaeche.top())
    assert ansicht._y(flaeche, 20) == pytest.approx(flaeche.bottom())
    zeichne(ansicht)


def test_laufbahn_mit_einer_saison_steht_mittig(qtbot) -> None:
    ansicht = Laufbahnansicht(20)
    qtbot.addWidget(ansicht)
    ansicht.resize(400, 200)
    ansicht.zeige([(2026, 20, 5)])
    zeichne(ansicht)
    assert ansicht.saisons == 1
