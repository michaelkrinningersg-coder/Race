"""Tests fuer Karriereseite, Sponsoren, Startdialog und Spielstand.

Was zwischen zwei Rennen passiert: Tage belegen, Sponsoren
unterschreiben, eine Karriere beginnen, speichern und laden.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402


# -- Karriereseite ----------------------------------------------------------
def test_karriereseite_startet_am_ersten_januar(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    karriere = fenster.karriereseite.karriere

    from rennmanager.kern import kassenbuch as kern_kassenbuch

    assert karriere.heute.month == 1 and karriere.heute.day == 1
    # Seit Punkt 72 zahlt das Teambudget in Raten; die erste liegt am
    # ersten Tag schon auf dem Konto.
    rate = kern_kassenbuch.monatsrate(konfig, karriere.teambudget)
    assert rate > 0
    assert karriere.konto.geld == konfig.wert("kosten", "startkapital_euro") + rate
    assert karriere.liga == fenster.welt.spieler.liga


def test_karriereseite_listet_alle_faehigkeiten(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    liste = fenster.karriereseite.liste
    erwartet = len(konfig.faehigkeiten) + len(konfig.zusatzfaehigkeiten)
    assert liste.topLevelItemCount() == erwartet


def test_tag_belegen_ueber_die_oberflaeche(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 2: zwei Plaetze je Tag, einer fuer den Fahrer, einer fuer die Werkstatt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.karriereseite

    seite.waehle("D1")
    seite._belege_tag()
    assert seite.karriere.wert("D1") == 10

    seite.waehle("F10")
    seite._belege_tag()
    assert seite.karriere.wert("F10") == 10
    assert len(seite.karriere.belegt) == 2


def test_der_belegte_platz_haelt_bis_zum_rennen(qtbot, konfig: kf.Konfiguration) -> None:
    """Punkt 66: Ein Tageswechsel gibt den Platz **nicht** mehr frei.

    Vorher liess sich an jedem Tag bis zum Rennen ein weiterer Schritt
    belegen; jetzt gibt es je Rennabstand einen Trainings- und einen
    Werkstattschritt.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.karriereseite

    seite.waehle("D1")
    seite._belege_tag()
    assert seite.karriere.belegt
    seite._tag_weiter()
    assert seite.karriere.belegt
    # Erst der Tag nach dem Rennen raeumt die Plaetze wieder frei.
    seite.karriere.bis_zum_rennen()
    seite.karriere.verbuche_rennen(platz=1)
    assert seite.karriere.belegt
    seite.karriere.tag_weiter()
    assert not seite.karriere.belegt


def test_sofortkauf_ueber_die_oberflaeche(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.karriereseite

    vorher = seite.karriere.konto.geld
    seite.waehle("F1")
    seite._kaufe()
    assert seite.karriere.wert("F1") == 10
    assert seite.karriere.konto.geld < vorher
    # Ein Sofortkauf verbraucht keinen Tagesplatz.
    assert not seite.karriere.belegt


def test_sprung_zum_rennen_ueber_die_oberflaeche(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.karriereseite

    seite._zum_rennen()
    assert seite.karriere.heute == seite.karriere.saison.erstes_rennen
    assert seite.karriere.tag.art.name == "RENNEN"


def test_karriereseite_zeigt_den_sponsorenstand(qtbot, konfig: kf.Konfiguration) -> None:
    """Die Auswahl steht im eigenen Reiter; hier nur noch der Stand."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    plaetze = len(konfig.wert("sponsoren", "plaetze"))
    assert str(plaetze) in fenster.karriereseite._sponsorenstand.text()


# --- Sponsoren ------------------------------------------------------------
def test_sponsorenseite_zeigt_alle_plaetze(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 10: sechs Plaetze, am Anfang alle frei."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.sponsorenseite

    plaetze = konfig.wert("sponsoren", "plaetze")
    assert seite.platzliste.topLevelItemCount() == len(plaetze)
    staende = {
        seite.platzliste.topLevelItem(i).text(1)
        for i in range(seite.platzliste.topLevelItemCount())
    }
    assert staende == {"frei"}


def test_sponsorenseite_zeigt_die_angebote_des_gewaehlten_platzes(
    qtbot, konfig: kf.Konfiguration
) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.sponsorenseite

    for stelle in range(seite.platzliste.topLevelItemCount()):
        zeile = seite.platzliste.topLevelItem(stelle)
        seite.platzliste.setCurrentItem(zeile)
        platz = zeile.data(0, Qt.UserRole)
        erwartet = len(seite.angebote[platz])
        assert seite.angebotsliste.topLevelItemCount() == erwartet
        assert erwartet >= konfig.wert("sponsoren", "angebote_je_platz_min")


def test_sponsorenseite_sortiert_nach_spalten(qtbot, konfig: kf.Konfiguration) -> None:
    """Zahlen muessen als Zahlen sortieren, nicht als Text."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.sponsorenseite
    liste = seite.angebotsliste

    def betraege() -> list[int]:
        return [
            liste.topLevelItem(i).data(1, Qt.UserRole + 1)
            for i in range(liste.topLevelItemCount())
        ]

    liste.sortByColumn(1, Qt.AscendingOrder)
    aufsteigend = betraege()
    assert aufsteigend == sorted(aufsteigend)

    liste.sortByColumn(1, Qt.DescendingOrder)
    absteigend = betraege()
    assert absteigend == sorted(absteigend, reverse=True)
    # Und das sind wirklich verschiedene Betraege, nicht alle gleich.
    assert len(set(absteigend)) > 1


def test_sponsor_unterschreiben_belegt_den_platz(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.sponsorenseite

    zeile = seite.platzliste.topLevelItem(0)
    seite.platzliste.setCurrentItem(zeile)
    platz = zeile.data(0, Qt.UserRole)
    seite.angebotsliste.setCurrentItem(seite.angebotsliste.topLevelItem(0))
    seite.knopf_unterschreiben.click()

    assert platz in fenster.karriereseite.karriere.vertraege
    # Der Platz steht jetzt auf "belegt" und nimmt kein zweites Angebot.
    belegt = [
        seite.platzliste.topLevelItem(i)
        for i in range(seite.platzliste.topLevelItemCount())
        if seite.platzliste.topLevelItem(i).data(0, Qt.UserRole) == platz
    ][0]
    assert belegt.text(1) == "belegt"
    seite.platzliste.setCurrentItem(belegt)
    assert not seite.knopf_unterschreiben.isEnabled()


# -- Startdialog (Punkt 11) --------------------------------------------------
def test_startdialog_fragt_teamname_und_vier_fahrer(qtbot, konfig) -> None:
    """Punkt 11: Der Teamchef benennt sein Team und seine vier Fahrer."""
    from rennmanager.ui.startdialog import Startdialog

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    dialog = Startdialog(konfig, fenster.jahr, vorgabe=fenster.welt.spielerfahrer)
    qtbot.addWidget(dialog)

    # Ein Reiter je Auto, und die bisherigen Fahrer stehen als Vorgabe drin.
    anzahl = konfig.wert("teams", "autos_je_team")
    assert dialog.fahrerreiter.count() == anzahl
    for stelle, eigener in enumerate(fenster.welt.spielerfahrer):
        assert dialog.vornamefeld(stelle).text() == eigener.vorname
        assert dialog.nachnamefeld(stelle).text() == eigener.nachname
        assert dialog.landauswahl(stelle).currentText() == eigener.land

    # Die Liga steht nicht zur Wahl - nur die vier Laenderlisten.
    from PySide6.QtWidgets import QComboBox, QLabel

    assert len(dialog.findChildren(QComboBox)) == anzahl
    texte = " ".join(marke.text() for marke in dialog.findChildren(QLabel))
    assert f"Liga {konfig.wert('ligen', 'startliga')}" in texte


def test_startdialog_braucht_teamname_und_alle_namen(qtbot, konfig) -> None:
    from rennmanager.ui.startdialog import Startdialog

    dialog = Startdialog(konfig, 2026)
    qtbot.addWidget(dialog)
    anzahl = konfig.wert("teams", "autos_je_team")
    assert not dialog.knopf_beginnen.isEnabled()

    dialog.teamnamefeld.setText("Krinninger Racing")
    for stelle in range(anzahl):
        assert not dialog.knopf_beginnen.isEnabled()
        dialog.vornamefeld(stelle).setText(f"Jan{stelle}")
        dialog.nachnamefeld(stelle).setText(f"Berger{stelle}")
    assert dialog.knopf_beginnen.isEnabled()

    # Leerzeichen allein zaehlen nicht - weder beim Team noch beim Fahrer.
    dialog.nachnamefeld(anzahl - 1).setText("   ")
    assert not dialog.knopf_beginnen.isEnabled()
    dialog.nachnamefeld(anzahl - 1).setText("Berger")
    assert dialog.knopf_beginnen.isEnabled()
    dialog.teamnamefeld.setText("  ")
    assert not dialog.knopf_beginnen.isEnabled()


def test_startdialog_bietet_nur_laender_der_welt_an(qtbot, konfig) -> None:
    """Der Spieler soll kein Land tragen, das es sonst nirgends gibt."""
    from rennmanager.ui.startdialog import Startdialog

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    angeboten = set(Startdialog.laender(konfig))
    gefahren = {f.land for f in fenster.welt.fahrer}
    assert gefahren <= angeboten


def test_neue_karriere_setzt_alles_auf_anfang(qtbot, konfig) -> None:
    """GDD 1: Der Spieler faengt bei null an."""
    import datetime as dt

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.saisonseite.lauf.fahre_rennen()
    assert fenster.saisonseite.lauf.gefahren == 1

    fenster.beginne_neue_karriere(
        {
            "team": "Weidinger Racing",
            "fahrer": [
                {
                    "vorname": "Jonas",
                    "nachname": f"Weidinger{stelle}",
                    "land": "Oesterreich",
                    "geburtstag": dt.date(2005, 4, 12),
                }
                for stelle in range(konfig.wert("teams", "autos_je_team"))
            ],
        }
    )

    eigene = fenster.welt.spielerfahrer
    assert len(eigene) == konfig.wert("teams", "autos_je_team")
    assert fenster.welt.spielerteam.name == "Weidinger Racing"
    for stelle, spieler in enumerate(eigene):
        assert spieler.name == f"Jonas Weidinger{stelle}"
        assert spieler.land == "Oesterreich"
        assert spieler.geburtstag == dt.date(2005, 4, 12)
        assert spieler.liga == konfig.wert("ligen", "startliga")
        # Das Auto traegt den neuen Namen, die Werte bleiben auf 0.
        assert spieler.auto.name == f"Jonas Weidinger{stelle}"
        assert set(spieler.auto.werte.values()) == {0}
    spieler = eigene[0]

    # Saison, Statistik und Karriere stehen wieder am Anfang.
    assert fenster.saisonseite.lauf.gefahren == 0
    assert fenster.statistik.saisons == ()
    assert fenster.statistik.zahlen(spieler.nummer).rennen == 0
    assert fenster.karriere.heute.month == 1 and fenster.karriere.heute.day == 1
    assert fenster.jahr == konfig.wert("kalender", "startjahr")


def test_neue_karriere_zeigt_den_namen_ueberall(qtbot, konfig) -> None:
    import datetime as dt

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.beginne_neue_karriere(
        {
            "team": "Holtkamp Motorsport",
            "fahrer": [
                {
                    "vorname": "Mara",
                    "nachname": "Holtkamp",
                    "land": "Niederlande",
                    "geburtstag": dt.date(2004, 7, 1),
                }
            ],
        }
    )

    seite = fenster.weltseite
    seite.liga_auswahl.setCurrentIndex(konfig.wert("ligen", "startliga"))
    namen = {
        seite.liste.topLevelItem(i).text(2)
        for i in range(seite.liste.topLevelItemCount())
    }
    assert "Mara Holtkamp" in namen

    # Und im gefuehrten Wochenende.
    vorschau = fenster.wochenendeseite.vorschauliste
    gezeigt = {
        vorschau.topLevelItem(i).text(1) for i in range(vorschau.topLevelItemCount())
    }
    assert "Mara Holtkamp" in gezeigt


# --- Speichern und Laden --------------------------------------------------
def test_fenster_speichert_und_laedt_einen_spielstand(
    qtbot, konfig: kf.Konfiguration, tmp_path
) -> None:
    """GDD 15: Spielstand lokal speichern und laden."""
    from rennmanager.kern import spielstand as kern_spielstand

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)

    # Etwas tun, das sich wiedererkennen laesst.
    karriere = fenster.karriereseite.karriere
    karriere.kaufe("F1")
    karriere.uebernimm_defekte(("X7",))
    fenster.saisonseite.lauf.fahre_rennen()
    fenster.saisonseite._aktualisiere()

    pfad = tmp_path / "stand.sqlite"
    kern_spielstand.speichere(fenster.spielstand(), pfad)

    # Ein frisches Fenster kennt davon nichts ...
    zweites = Hauptfenster(konfig)
    qtbot.addWidget(zweites)
    assert zweites.karriereseite.karriere.werte["F1"] == 0
    assert zweites.saisonseite.lauf.gefahren == 0

    # ... bis der Stand geladen ist.
    zweites.uebernimm(kern_spielstand.lade(konfig, pfad))
    assert zweites.karriereseite.karriere.werte["F1"] == karriere.werte["F1"]
    assert [d["schluessel"] for d in zweites.karriereseite.karriere.defekte] == ["X7"]
    assert zweites.saisonseite.lauf.gefahren == 1
    assert zweites.welt == fenster.welt
    # Die Statistik des Wochenendes ist ebenfalls da.
    assert len(zweites.statistik.rekorde) == konfig.wert("ligen", "anzahl")


def test_geladener_stand_laesst_sich_weiterfahren(
    qtbot, konfig: kf.Konfiguration, tmp_path
) -> None:
    from rennmanager.kern import spielstand as kern_spielstand

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.saisonseite.lauf.fahre_rennen()
    fenster.saisonseite._aktualisiere()
    pfad = tmp_path / "stand.sqlite"
    kern_spielstand.speichere(fenster.spielstand(), pfad)

    zweites = Hauptfenster(konfig)
    qtbot.addWidget(zweites)
    zweites.uebernimm(kern_spielstand.lade(konfig, pfad))
    zweites.saisonseite.lauf.fahre_rennen()
    zweites.saisonseite._aktualisiere()

    assert zweites.saisonseite.lauf.gefahren == 2
    # Die Punkte aus dem geladenen Rennen sind noch da.
    spieler = zweites.welt.spieler
    assert zweites.saisonseite.lauf.tabelle(spieler.liga).eintraege[spieler.nummer].rennen == 2


# -- Autosave und Schnellspeicher (Punkt 17) --------------------------------
def test_autosave_nach_jedem_tageswechsel(qtbot, konfig, spielstandordner) -> None:
    """GDD 2: Ein Tag ist vorbei - der Stand soll ihn ueberleben."""
    from rennmanager.kern import spielstand as kern_spielstand

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    assert not kern_spielstand.autosave().exists()

    fenster.karriereseite._tag_weiter()
    assert kern_spielstand.autosave().is_file()

    # Der Stand passt zum Kalender - und wird beim naechsten Tag ersetzt.
    stand = kern_spielstand.lade(konfig, kern_spielstand.autosave())
    assert stand.karriere.heute == fenster.karriere.heute
    fenster.karriereseite._tag_weiter()
    zweiter = kern_spielstand.lade(konfig, kern_spielstand.autosave())
    assert zweiter.karriere.heute == fenster.karriere.heute > stand.karriere.heute


def test_autosave_nach_dem_rennwochenende(qtbot, konfig) -> None:
    from rennmanager.kern import spielstand as kern_spielstand

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    for _ in range(3):
        fenster.wochenendeseite.knopf_weiter.click()

    stand = kern_spielstand.lade(konfig, kern_spielstand.autosave())
    assert stand.gefahrene_rennen == 1


def test_schnellspeichern_und_schnellladen(qtbot, konfig) -> None:
    """F5 und F9 - ohne Dialog, damit man ein Wochenende neu fahren kann."""
    from rennmanager.kern import spielstand as kern_spielstand

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.karriereseite.waehle("D1")
    fenster.karriereseite._belege_tag()
    vorher = fenster.karriere.wert("D1")
    assert vorher > 0

    assert fenster.schnellspeichern() == kern_spielstand.schnellspeicher()
    assert kern_spielstand.schnellspeicher().is_file()

    # Weiterspielen, dann zurueck auf den Schnellspeicherstand. Der
    # Fahrerplatz ist seit Punkt 66 bis zum Rennen belegt - also die
    # Werkstatt.
    fenster.karriereseite._tag_weiter()
    fenster.karriereseite.waehle("F10")
    fenster.karriereseite._belege_tag()
    assert fenster.karriere.wert("F10") > 0

    assert fenster.schnellladen()
    assert fenster.karriere.wert("D1") == vorher
    assert fenster.karriere.wert("F10") == 0


def test_schnellladen_ohne_stand_meldet_sich(qtbot, konfig, monkeypatch) -> None:
    """Wer F9 drueckt, ohne je F5 gedrueckt zu haben, bekommt eine Meldung."""
    from PySide6.QtWidgets import QMessageBox

    gemeldet = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kw: gemeldet.append(args[2])
    )
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)

    assert not fenster.schnellladen()
    assert gemeldet and "nicht gefunden" in gemeldet[0]


def test_die_tastenkuerzel_sind_gesetzt(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    kuerzel = {
        aktion.text().replace("&", ""): aktion.shortcut().toString()
        for menue in fenster.menuBar().findChildren(type(fenster.menuBar().actions()[0].menu()))
        for aktion in menue.actions()
        if aktion.text()
    }
    assert kuerzel["Schnellspeichern"] == "F5"
    assert kuerzel["Schnellladen"] == "F9"
    assert kuerzel["Neue Karriere ..."] == "Ctrl+N"
