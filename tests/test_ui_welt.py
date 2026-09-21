"""Tests fuer Weltseite, Saisonseite und Editor.

Drei Seiten auf dieselbe Welt: Die eine zeigt sie, die zweite fuehrt
die Saison darueber, die dritte aendert sie. Die Fahrersuche steht
dabei, weil sie dieselben Namen liest.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.tabellen import SortierbareZeile as Zeile  # noqa: E402
from tests.oberflaeche import (  # noqa: E402
    ein_fahrer,
    fahre_saison_zu_ende,
    kurzes_rennen,
)


# -- Weltseite --------------------------------------------------------------
def test_fenster_erzeugt_eine_welt(qtbot, konfig: kf.Konfiguration) -> None:
    """Punkt 101: ein Feld aus 50 Autos, 25 Teams zu zweit."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    welt = fenster.welt

    assert len(welt.fahrer) == konfig.wert("rennen", "autos")
    assert len(welt.teams) == konfig.wert("teams", "anzahl")
    assert welt.spieler is not None
    # Der Spieler hat seit Punkt 101 genau zwei Autos.
    assert len(welt.spielerfahrer) == konfig.wert("teams", "autos_je_team")


def test_weltseite_zeigt_das_ganze_feld(qtbot, konfig: kf.Konfiguration) -> None:
    """Punkt 101: keine Ligawahl mehr - alle stehen in einer Liste."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    assert not hasattr(seite, "liga_auswahl")
    assert seite.liste.topLevelItemCount() == len(fenster.welt.fahrer)
    # Die Liste beginnt beim staerksten Fahrer und zaehlt durch.
    plaetze = [
        seite.liste.topLevelItem(i).text(0)
        for i in range(seite.liste.topLevelItemCount())
    ]
    assert plaetze == [str(i) for i in range(1, len(fenster.welt.fahrer) + 1)]


def test_weltseite_ordnet_nach_staerke(qtbot, konfig: kf.Konfiguration) -> None:
    """Platz 1 ist der staerkste Fahrer, der letzte der schwaechste."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    staerken = [
        float(seite.liste.topLevelItem(i).text(7).replace(".", "").replace(",", "."))
        for i in range(seite.liste.topLevelItemCount())
    ]
    assert staerken == sorted(staerken, reverse=True)


def test_weltseite_zeigt_alle_einzelwerte_als_spalten(qtbot, konfig: kf.Konfiguration) -> None:
    """Die 32 Werte aus GDD 5 und 6 plus die Faehigkeiten daneben."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    vorher = seite.liste.columnCount()
    seite.alle_werte.setChecked(True)
    kopf = [seite.liste.headerItem().text(i) for i in range(seite.liste.columnCount())]

    erwartet = [f.schluessel for f in konfig.faehigkeiten] + list(konfig.zusatzfaehigkeiten)
    assert seite.liste.columnCount() == vorher + len(erwartet)
    assert kopf[-len(erwartet):] == erwartet

    # Die Werte stehen auch wirklich drin.
    zeile = seite.liste.topLevelItem(0)
    fahrer = fenster.welt.fahrer[zeile.data(0, Qt.UserRole)]
    stelle = kopf.index("F1")
    assert zeile.text(stelle).replace(".", "") == str(fahrer.auto.werte["F1"])


def test_weltseite_zeigt_das_profil(qtbot, konfig: kf.Konfiguration) -> None:
    """Am Profil sieht man Regenspezialisten und Reifenschoner (GDD 12)."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    seite.liste.setCurrentItem(seite.liste.topLevelItem(0))
    profil = seite._profil
    gruppen = {
        profil.topLevelItem(i).text(0): profil.topLevelItem(i)
        for i in range(profil.topLevelItemCount())
    }
    assert len(gruppen) == 4

    bereiche = next(g for name, g in gruppen.items() if name.startswith("Wirkungsbereiche"))
    assert bereiche.childCount() == len(konfig.bereiche)

    fahrzeug = next(g for name, g in gruppen.items() if name.startswith("Fahrzeug"))
    fahrerwerte = next(g for name, g in gruppen.items() if name.startswith("Fahrer "))
    assert fahrzeug.childCount() + fahrerwerte.childCount() == len(konfig.faehigkeiten)
    assert fahrzeug.child(0).text(0).startswith("F1 ")

    weitere = next(g for name, g in gruppen.items() if name.startswith("Neben der Matrix"))
    assert weitere.childCount() == len(konfig.zusatzfaehigkeiten)
    namen = [weitere.child(i).text(0) for i in range(weitere.childCount())]
    assert "Reifenfluesterer" in namen


def test_rennen_nutzt_die_fahrer_der_welt(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._halte_an()

    erwartet = {f.kuerzel for f in fenster.welt.fahrer}
    assert {t.kuerzel for t in seite.verlauf.teilnehmer} == erwartet


def test_gefahren_wird_das_ganze_feld(qtbot, konfig: kf.Konfiguration) -> None:
    """Punkt 101: Es gibt nur noch ein Feld - das faehrt mit."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    gefuehrt = fenster.wochenendeseite

    gefuehrt.knopf_weiter.click()
    kuerzel = {t.kuerzel for t in gefuehrt.qualifyingseite.session.teilnehmer}
    assert kuerzel == {f.kuerzel for f in fenster.welt.fahrer}


# --- Saison ---------------------------------------------------------------
def test_saisonseite_startet_leer(qtbot, konfig: kf.Konfiguration) -> None:
    """Punkt 101: eine Tabelle, keine Ligawahl."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite

    assert not hasattr(seite, "liga_auswahl")
    assert seite.lauf.gefahren == 0
    assert seite.lauf.naechstes_rennen == 1
    # Vor dem ersten Rennen ist die Tabelle leer.
    assert seite.tabelle.topLevelItemCount() == 0
    assert seite.rennliste.topLevelItemCount() == 0


def test_saisonseite_faehrt_ein_rennwochenende(qtbot, konfig: kf.Konfiguration) -> None:
    """Ein Klick faehrt das Feld und fuellt Tabelle und Ergebnis."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite

    seite.lauf.fahre_rennen()
    seite._aktualisiere()

    autos = konfig.wert("rennen", "autos")
    assert seite.lauf.gefahren == 1
    assert seite.tabelle.topLevelItemCount() == autos
    assert seite.rennliste.topLevelItemCount() == autos
    # Der Tabellenerste hat die meisten Punkte.
    punkte = [int(seite.tabelle.topLevelItem(i).text(3)) for i in range(autos)]
    assert punkte == sorted(punkte, reverse=True)


def test_saisonseite_zeigt_das_ganze_feld_in_der_tabelle(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """Punkt 101: Jeder Platz bekommt Punkte, jeder steht in der Tabelle."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    seite.lauf.fahre_rennen()
    seite._aktualisiere()

    assert seite.tabelle.topLevelItemCount() == len(fenster.welt.fahrer)
    # Auch der Letzte hat gepunktet.
    letzte = seite.tabelle.topLevelItem(seite.tabelle.topLevelItemCount() - 1)
    assert int(letzte.text(3)) >= 1
    # Und die Plaetze zaehlen lueckenlos durch.
    plaetze = [
        seite.tabelle.topLevelItem(i).text(0)
        for i in range(seite.tabelle.topLevelItemCount())
    ]
    assert plaetze == [str(i) for i in range(1, len(fenster.welt.fahrer) + 1)]


def test_saisonseite_zeigt_den_kalenderstand(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 2: Das Rennen findet an seinem Renntag statt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite

    renntag = seite.lauf.renntag(1)
    text = seite.kalenderzeile.text()
    assert f"{renntag:%d.%m.%Y}" in text
    assert "verfallen" in text

    seite.lauf.fahre_rennen()
    seite._aktualisiere()
    assert fenster.karriere.heute > renntag
    assert f"{seite.lauf.renntag(2):%d.%m.%Y}" in seite.kalenderzeile.text()


def test_saisonseite_zeigt_den_abschluss(qtbot, konfig: kf.Konfiguration) -> None:
    """Am Saisonende: Meister, eigene Bilanz und der Knopf zum Wechsel."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    assert not seite.knopf_naechste_saison.isEnabled()

    fahre_saison_zu_ende(konfig, seite)
    assert seite.knopf_naechste_saison.isEnabled()
    assert not seite.knopf_restliche_saison.isEnabled()
    text = seite.abschlusstext.text()
    assert fenster.welt.spieler.name in text
    assert "Punkte" in text


def test_saisonseite_wechselt_ins_naechste_jahr(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 13: Die Saison wird abgeschlossen, dann beginnt die naechste."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    jahr = seite.lauf.jahr
    vorher = [f.nummer for f in fenster.welt.feld]
    fahre_saison_zu_ende(konfig, seite)

    seite.knopf_naechste_saison.click()
    # Das Fenster baut sich erst nach der Rueckkehr in die Ereignisschleife
    # neu auf - sonst riss es sich die Seite unter dem Klick weg.
    qtbot.wait(20)

    neue = fenster.saisonseite
    assert neue.lauf.jahr == jahr + 1
    assert neue.lauf.gefahren == 0
    assert fenster.karriere.saison.jahr == jahr + 1
    assert fenster.karriere.heute.year == jahr + 1
    # Punkt 101: feste Fahrer - dasselbe Feld in derselben Reihenfolge.
    assert [f.nummer for f in fenster.welt.feld] == vorher
    # Die Statistik hat die abgeschlossene Saison behalten.
    assert fenster.statistik.saisons == (jahr,)
    assert neue.tabelle.topLevelItemCount() == 0


# --- Editor ---------------------------------------------------------------
def _erster_ki(seite, fenster):
    """Die erste Zeile der Editorliste, die keinem Spielerauto gehoert.

    Frueher hiess das "Liga 1" - dort fuhr der Spieler nie. Seit Punkt 101
    steht sein Team mitten im einen Feld, also wird gesucht statt gesetzt.
    """
    for stelle in range(seite.liste.topLevelItemCount()):
        zeile = seite.liste.topLevelItem(stelle)
        if not fenster.welt.fahrer[zeile.data(0, Qt.UserRole)].ist_spieler:
            seite.liste.setCurrentItem(zeile)
            return zeile
    raise AssertionError("Kein KI-Fahrer in der Liste")


def test_editor_zeigt_alle_werte_des_fahrers(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 15 nennt eine Debug-Ansicht unter den Balancing-Werkzeugen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    erwartet = {f.schluessel for f in konfig.faehigkeiten} | set(konfig.zusatzfaehigkeiten)
    assert set(seite.felder) == erwartet
    assert set(seite.kenntnisfelder) == {e["name"] for e in konfig.strecken}

    # Der geladene Fahrer steht mit seinen echten Werten in den Feldern.
    zeile = seite.liste.currentItem()
    fahrer = fenster.welt.fahrer[zeile.data(0, Qt.UserRole)]
    if not fahrer.ist_spieler:
        assert seite.felder["F1"].value() == fahrer.auto.wert("F1")
        assert seite.felder["regenfahren"].value() == fahrer.auto.wetterwert("regenfahren")


def test_editor_sucht_nach_namen(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    ziel = ein_fahrer(fenster)
    seite.suche.setText(ziel.nachname)
    namen = {
        seite.liste.topLevelItem(i).text(1) for i in range(seite.liste.topLevelItemCount())
    }
    assert ziel.name in namen
    assert seite.liste.topLevelItemCount() < len(fenster.welt.fahrer)


def test_editor_aendert_werte_dauerhaft(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    # Einen KI-Fahrer waehlen - der Spieler faehrt nie ganz vorn.
    zeile = _erster_ki(seite, fenster)
    nummer = zeile.data(0, Qt.UserRole)
    assert not fenster.welt.fahrer[nummer].ist_spieler

    seite.felder["F1"].setValue(77_000)
    seite.felder["regenfahren"].setValue(66_000)
    seite.kenntnisfelder["Monza"].setValue(500)
    seite.knopf_uebernehmen.click()

    assert seite.welt.fahrer[nummer].auto.wert("F1") == 77_000
    assert seite.welt.fahrer[nummer].auto.wetterwert("regenfahren") == 66_000
    assert fenster._kenntnis.stand(nummer, "Monza") == 500


def test_editor_aendert_stammdaten(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    zeile = _erster_ki(seite, fenster)
    nummer = zeile.data(0, Qt.UserRole)

    vorname, nachname, land, _geburtstag = seite.stammdaten
    vorname.setText("Ada")
    nachname.setText("Lovelace")
    land.setText("Grossbritannien")
    seite.knopf_uebernehmen.click()

    geaendert = seite.welt.fahrer[nummer]
    assert geaendert.name == "Ada Lovelace"
    assert geaendert.land == "Grossbritannien"
    # Team und Kuerzel bleiben, wie die Welt sie vergeben hat.
    assert geaendert.team == fenster.welt.fahrer[nummer].team
    assert geaendert.kuerzel == fenster.welt.fahrer[nummer].kuerzel


def test_editor_gibt_die_geaenderte_welt_ans_fenster(qtbot, konfig: kf.Konfiguration) -> None:
    """Beim Verlassen des Reiters uebernimmt das Fenster die neue Welt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite
    reiter = fenster._reiter

    zeile = _erster_ki(seite, fenster)
    nummer = zeile.data(0, Qt.UserRole)
    seite.felder["F1"].setValue(55_000)
    seite.knopf_uebernehmen.click()
    assert fenster.welt.fahrer[nummer].auto.wert("F1") != 55_000

    reiter.setCurrentIndex(reiter.indexOf(fenster.weltseite))
    assert fenster.welt.fahrer[nummer].auto.wert("F1") == 55_000


def test_editor_aendert_auch_den_spieler(qtbot, konfig: kf.Konfiguration) -> None:
    """Punkt 101: Es gibt keine Karrierewerte mehr - alles steht in der Welt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    seite._springe_zum_spieler()
    spieler = fenster.welt.spieler
    assert seite.liste.currentItem().data(0, Qt.UserRole) == spieler.nummer
    assert seite.felder["F1"].value() == spieler.auto.wert("F1")

    seite.felder["F1"].setValue(12_345)
    seite.knopf_uebernehmen.click()
    assert seite.welt.fahrer[spieler.nummer].auto.wert("F1") == 12_345


def test_editierte_werte_kommen_im_rennen_an(qtbot, konfig: kf.Konfiguration) -> None:
    """Der eigentliche Zweck: Was im Editor steht, faehrt auch so."""
    from rennmanager.kern import welt as kern_welt

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    zeile = _erster_ki(seite, fenster)
    nummer = zeile.data(0, Qt.UserRole)
    for schluessel in seite.felder:
        seite.felder[schluessel].setValue(90_000)
    seite.knopf_uebernehmen.click()
    fenster.uebernimm_welt(seite.welt)

    feld = kern_welt.starterfeld(fenster.welt)
    kuerzel = fenster.welt.fahrer[nummer].kuerzel
    gefahren = next(t for t in feld if t.auto.kuerzel == kuerzel)
    assert gefahren.auto.wert("F1") == 90_000


def test_editor_zeigt_je_fahrer_die_rundenzeit(qtbot, konfig: kf.Konfiguration) -> None:
    """Trocken und ohne jeden Wurf - so laesst sich vergleichen."""
    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.kern import tempo as kern_tempo
    from rennmanager.kern.zeit import formatiere_dauer

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    name = seite.streckenauswahl.currentData()
    strecke = kern_strecke.lade(konfig, name)
    zeile = seite.liste.topLevelItem(0)
    fahrer = fenster.welt.fahrer[zeile.data(0, Qt.UserRole)]

    frei = kern_tempo.fahre_runde(konfig, strecke, fahrer.auto).zeit_ms
    kenntnis = fenster._kenntnis.tempofaktor(fahrer.nummer, name)
    assert zeile.text(4) == formatiere_dauer(int(round(frei / kenntnis)))


def test_editor_rechnet_die_zeiten_je_strecke_neu(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    def zeiten() -> list[str]:
        return [
            seite.liste.topLevelItem(i).text(4)
            for i in range(seite.liste.topLevelItemCount())
        ]

    erste = zeiten()
    seite.streckenauswahl.setCurrentIndex(seite.streckenauswahl.findData("Monza"))
    monza = zeiten()
    seite.streckenauswahl.setCurrentIndex(seite.streckenauswahl.findData("Spa"))
    assert monza != erste
    assert zeiten() != monza
    # Der Kasten nennt die Strecke, damit klar ist, worauf sich die Zeit bezieht.
    assert "Spa" in seite._listenkasten.title()


def test_editor_zeigt_den_rueckstand_zur_bestzeit(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    zeiten = [
        seite.liste.topLevelItem(i).data(4, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
    ]
    rueckstaende = [
        seite.liste.topLevelItem(i).data(5, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
    ]
    bestzeit = min(zeiten)
    assert rueckstaende == [zeit - bestzeit for zeit in zeiten]
    # Genau eine Zeile ist die Bestzeit und hat keinen Rueckstand.
    leer = [
        i
        for i in range(seite.liste.topLevelItemCount())
        if seite.liste.topLevelItem(i).text(5) == ""
    ]
    assert len(leer) == 1


def test_editor_sortiert_nach_rundenzeit(qtbot, konfig: kf.Konfiguration) -> None:
    """Wer auf dieser Strecke am schnellsten ist, muss nicht der Staerkste sein."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    seite.liste.sortByColumn(4, Qt.AscendingOrder)
    zeiten = [
        seite.liste.topLevelItem(i).data(4, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
    ]
    assert zeiten == sorted(zeiten)


def test_editor_rechnet_nach_einer_aenderung_neu(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    # Der **langsamste** Fahrer, nicht der schnellste: Der Beste steht
    # schon am oberen Ende der Skala - ihn dorthin zu setzen aendert nichts.
    seite.liste.sortByColumn(4, Qt.AscendingOrder)
    zeile = seite.liste.topLevelItem(seite.liste.topLevelItemCount() - 1)
    seite.liste.setCurrentItem(zeile)
    nummer = zeile.data(0, Qt.UserRole)
    vorher = zeile.data(4, Zeile.SORTIERROLLE)

    # Auf den Hoechstwert statt auf feste 90 000: Das Feld steht seit
    # Punkt 101 dicht unter dem Maximum.
    for schluessel in seite.felder:
        seite.felder[schluessel].setValue(seite.felder[schluessel].maximum())
    seite.knopf_uebernehmen.click()

    nachher = next(
        seite.liste.topLevelItem(i).data(4, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
        if seite.liste.topLevelItem(i).data(0, Qt.UserRole) == nummer
    )
    assert nachher < vorher


# -- Fahrersuche (Punkt 18) --------------------------------------------------
def test_die_suche_kennt_alle_fahrer(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    suche = fenster.fahrersuche
    assert suche.vervollstaendigung.model().rowCount() == len(fenster.welt.fahrer)


def test_die_suche_findet_teiltreffer(qtbot, konfig) -> None:
    """Wer nur den halben Nachnamen tippt, soll ihn trotzdem finden."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    suche = fenster.fahrersuche
    fahrer = ein_fahrer(fenster, 0.4)

    assert fahrer.nummer in suche.treffer(fahrer.nachname)
    assert fahrer.nummer in suche.treffer(fahrer.nachname[2:-1])
    assert fahrer.nummer in suche.treffer(fahrer.nachname.upper())
    assert fahrer.nummer in suche.treffer(fahrer.kuerzel)
    assert suche.treffer("   ") == ()
    assert suche.treffer("Gibtesnicht") == ()


def test_die_eingabetaste_oeffnet_die_fahrerkarte(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    suche = fenster.fahrersuche
    fahrer = ein_fahrer(fenster, 0.6)

    suche.feld.setText(fahrer.name)
    suche.feld.returnPressed.emit()

    assert fahrer.nummer in fenster._karten
    assert fenster._karten[fahrer.nummer].fahrer.nummer == fahrer.nummer
    # Danach ist das Feld wieder leer, fuer die naechste Suche.
    assert suche.feld.text() == ""


def test_die_suche_laeuft_ins_leere_ohne_treffer(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    suche = fenster.fahrersuche

    suche.feld.setText("Zzzz Nichtvorhanden")
    suche.feld.returnPressed.emit()
    assert fenster._karten == {}
    # Die Eingabe bleibt stehen, damit man sie berichtigen kann.
    assert suche.feld.text() == "Zzzz Nichtvorhanden"


def test_die_suche_zieht_nach_dem_saisonwechsel_nach(qtbot, konfig) -> None:
    """Nach dem Saisonwechsel liest die Suche die neue Welt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fahre_saison_zu_ende(konfig, fenster.saisonseite)
    fenster.saisonseite.knopf_naechste_saison.click()
    qtbot.wait(20)

    suche = fenster.fahrersuche
    assert suche.vervollstaendigung.model().rowCount() == len(fenster.welt.fahrer)
    spieler = fenster.welt.spieler
    assert spieler.nummer in suche.treffer(spieler.name)


def test_die_suche_nennt_kuerzel_und_team(qtbot, konfig) -> None:
    """Nachnamen gibt es zweimal - die Zeile muss sie auseinanderhalten."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fahrer = ein_fahrer(fenster, 0.8)
    team = fenster.welt.team_von(fahrer)

    from rennmanager.ui.fahrersuche import eintrag

    zeile = eintrag(konfig, fahrer, team)
    assert fahrer.name in zeile
    assert fahrer.kuerzel in zeile
    assert team.name in zeile


def test_fahrertreffer_stehen_vor_teamtreffern(qtbot, konfig) -> None:
    """Die Suche trifft auch Teams - aber der Fahrer geht vor.

    Die Ueberschneidung wird hier gemacht statt gesucht: Seit Punkt 101
    stehen nur noch 50 Fahrer 25 Teams gegenueber, und dass sich ein
    Nachname und ein Teamname zufaellig decken, kommt in dieser Menge
    nicht mehr vor.
    """
    from rennmanager.kern import welt as kern_welt

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)

    # Einen Fahrer nehmen und ein **fremdes** Team nach ihm benennen.
    fahrer = ein_fahrer(fenster, 0.4)
    eigenes = fenster.welt.team_von(fahrer).nummer
    fremdes = next(t for t in fenster.welt.teams if t.nummer != eigenes)
    welt = kern_welt.mit_teamname(fenster.welt, fremdes.nummer, f"{fahrer.nachname} Racing")
    fenster.uebernimm_welt(welt)

    suche = fenster.fahrersuche
    gefunden = suche.treffer(fahrer.nachname)
    assert fahrer.nummer in gefunden
    # Wer ueber den Namen passt, steht vor jedem, der nur ueber den
    # Teamnamen hereinkommt.
    ueber_team = [
        stelle
        for stelle, nummer in enumerate(gefunden)
        if fahrer.nachname.casefold() not in welt.fahrer[nummer].nachname.casefold()
    ]
    assert ueber_team
    assert gefunden.index(fahrer.nummer) < min(ueber_team)
    # Und die Teamtreffer sind trotzdem dabei.
    namen = {welt.team_von(welt.fahrer[n]).name for n in gefunden}
    assert f"{fahrer.nachname} Racing" in namen
