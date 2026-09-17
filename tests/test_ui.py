"""Tests fuer die Oberflaeche.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import __version__
from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QTreeWidget  # noqa: E402

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    return kf.lade()


def test_fenster_oeffnet(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    assert __version__ in fenster.windowTitle()


def test_seed_eingabe_setzt_die_seedquelle(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)

    fenster._seed_eingabe.setValue(4711)
    assert fenster.seedquelle.seed == 4711

    fenster._seed_eingabe.setValue(99)
    assert fenster.seedquelle.seed == 99


def test_neuer_seed_bleibt_im_gueltigen_bereich(qtbot, konfig: kf.Konfiguration) -> None:
    from rennmanager.ui.hauptfenster import SEED_MAX

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    for _ in range(20):
        fenster._wuerfle_seed()
        assert 0 <= fenster.seedquelle.seed <= SEED_MAX


def test_offene_punkte_werden_angezeigt(qtbot, konfig: kf.Konfiguration) -> None:
    """Die Luecken im GDD sollen sichtbar sein, nicht nur in der Datei stehen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    # Das Fenster hat mehrere Listen; gesucht ist die auf der Uebersichtsseite.
    uebersicht = fenster._reiter.widget(0)
    baeume = uebersicht.findChildren(QTreeWidget)
    assert len(baeume) == 1
    assert baeume[0].topLevelItemCount() == len(konfig.offene_punkte)


def test_pruefmodus_laedt_die_konfiguration(capsys) -> None:
    """Der Pruefmodus des Builds meldet Erfolg und oeffnet kein Fenster."""
    from rennmanager.ui.anwendung import PRUEFMODUS, starte

    assert starte(["rennmanager", PRUEFMODUS]) == 0
    ausgabe = capsys.readouterr().out
    assert "GDD-Version" in ausgabe
    assert "20 Ligen" in ausgabe


def test_streckenseite_zeigt_die_erste_strecke(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.streckenseite
    assert seite.auswahl.count() == len(konfig.strecken)
    assert seite.strecke is not None
    assert seite.strecke.name == konfig.strecken[0]["name"]


def test_streckenwechsel_laedt_neu(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.streckenseite

    monza = next(i for i, e in enumerate(konfig.strecken) if e["name"] == "Monza")
    seite.auswahl.setCurrentIndex(monza)
    assert seite.strecke is not None
    assert seite.strecke.name == "Monza"
    assert seite.strecke.ueberholzonen


def test_streckenansicht_zeichnet_ohne_fehler(qtbot, konfig: kf.Konfiguration) -> None:
    """Das Zeichnen wird ueber grab() wirklich ausgefuehrt, nicht nur angestossen."""
    from rennmanager.ui.streckenansicht import Streckenansicht

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.resize(1000, 700)
    ansicht = fenster.streckenseite.findChild(Streckenansicht)
    assert ansicht is not None

    bild = ansicht.grab()
    assert not bild.isNull()
    assert bild.width() > 0 and bild.height() > 0


def test_streckenansicht_ohne_strecke_stuerzt_nicht_ab(qtbot) -> None:
    from rennmanager.ui.streckenansicht import Streckenansicht

    ansicht = Streckenansicht()
    qtbot.addWidget(ansicht)
    ansicht.resize(300, 200)
    ansicht.zeige(None)
    assert not ansicht.grab().isNull()


def test_rundenseite_startet_auf_der_referenzstrecke(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rundenseite
    assert seite.auswahl.currentData() == konfig.wert("kalibrierung", "referenzstrecke")
    assert seite.ergebnis is not None
    assert seite.ergebnis.zeit_ms > 0


def test_rundenseite_wird_bei_hoeherem_wert_schneller(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rundenseite

    seite.wert.setValue(0)
    langsam = seite.ergebnis.zeit_ms
    seite.wert.setValue(98_130)
    schnell = seite.ergebnis.zeit_ms
    assert schnell < langsam


def test_rundenseite_trifft_die_kalibrierung(qtbot, konfig: kf.Konfiguration) -> None:
    """Was die Seite anzeigt, muss der Formel aus GDD 9 entsprechen."""
    import math

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rundenseite
    seite.wert.setValue(62_470)

    soll = konfig.wert("kalibrierung", "basis_kmh") + konfig.wert(
        "kalibrierung", "spanne_kmh"
    ) * math.sqrt(62_470 / konfig.wert("skala", "referenz"))
    assert seite.ergebnis.schnitt_kmh == pytest.approx(soll, abs=0.05)


def test_regler_und_zahlenfeld_bleiben_gleich(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rundenseite
    seite._regler.setValue(37_000)
    assert seite.wert.value() == 37_000


def test_tempoansicht_zeichnet(qtbot, konfig: kf.Konfiguration) -> None:
    from rennmanager.ui.streckenansicht import Streckenansicht

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.resize(1000, 700)
    ansicht = fenster.rundenseite.findChild(Streckenansicht)
    assert ansicht is not None
    assert ansicht.zeigt_tempo
    assert not ansicht.grab().isNull()


def test_tempoprofil_muss_zur_strecke_passen(qtbot, konfig: kf.Konfiguration) -> None:
    import numpy as np

    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.ui.streckenansicht import Streckenansicht

    ansicht = Streckenansicht()
    qtbot.addWidget(ansicht)
    strecke = kern_strecke.lade(konfig, "Monza")
    with pytest.raises(ValueError, match="passt nicht"):
        ansicht.zeige_tempo(strecke, np.zeros(5))


# -- Rennseite --------------------------------------------------------------
def _kurzes_rennen(fenster, runden: int = 2, umgedreht: bool = False):
    """Berechnet ein moeglichst kurzes Rennen auf der Rennseite."""
    seite = fenster.rennseite
    seite._runden.setValue(runden)
    # Ohne Qualifying, das wuerde jeden Test um eine ganze Session verlaengern.
    seite._aufstellung.setCurrentIndex(2 if umgedreht else 1)
    seite._berechne()
    return seite


def test_rennseite_berechnet_ein_rennen(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)

    assert seite.verlauf is not None
    assert len(seite.verlauf.teilnehmer) == konfig.wert("rennen", "autos")
    assert len(seite.verlauf.ergebnisse) == konfig.wert("rennen", "autos")


def test_rennseite_spielt_den_verlauf_ab(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)

    seite._springe(0)
    anfang = seite.verlauf.distanzen_zu(seite.zeit_ms).copy()
    seite._springe(seite.verlauf.dauer_ms / 2)
    mitte = seite.verlauf.distanzen_zu(seite.zeit_ms)
    assert (mitte > anfang).all()


def test_sofortergebnis_springt_ans_ende(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: Zeitraffer bis 100x und Sofortergebnis."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)

    seite._springe(0)
    seite._zum_ende()
    assert seite.zeit_ms == seite.verlauf.dauer_ms


def test_zeitrafferstufen_kommen_aus_der_konfiguration(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite
    stufen = [seite._raffer.itemData(i) for i in range(seite._raffer.count())]
    assert stufen == konfig.wert("zeitraffer", "stufen")
    assert stufen[-1] == 100


def test_zeitraffer_bewegt_die_uhr_schneller(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)

    seite._raffer.setCurrentIndex(0)  # 1x
    seite._springe(0)
    seite._takt()
    langsam = seite.zeit_ms

    seite._raffer.setCurrentIndex(seite._raffer.count() - 1)  # 100x
    seite._springe(0)
    seite._takt()
    assert seite.zeit_ms == pytest.approx(langsam * 100)


def test_rangliste_zeigt_alle_autos(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: Positionen, Zeit des Fuehrenden, Rueckstand der uebrigen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)
    seite._springe(seite.verlauf.dauer_ms / 2)

    liste = seite._rangliste
    assert liste.topLevelItemCount() == konfig.wert("rennen", "autos")
    assert [liste.topLevelItem(i).text(0) for i in range(5)] == ["1", "2", "3", "4", "5"]
    # Der Fuehrende zeigt seine Gesamtzeit, die uebrigen einen Rueckstand.
    assert not liste.topLevelItem(0).text(3).startswith("+")
    assert liste.topLevelItem(1).text(3).startswith("+")


def test_zeitenmonitor_zeigt_runden_und_sektoren(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)
    seite._zum_ende()

    monitor = seite._monitor
    assert monitor.columnCount() == 7
    assert monitor.topLevelItemCount() > 0
    erste = monitor.topLevelItem(0)
    assert erste.text(1) != "-"  # letzte Runde
    assert erste.text(2) != "-"  # beste Runde


def test_rennansicht_zeichnet_die_autos(qtbot, konfig: kf.Konfiguration) -> None:
    from rennmanager.ui.streckenansicht import Streckenansicht

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.resize(1200, 800)
    seite = _kurzes_rennen(fenster)
    seite._springe(seite.verlauf.dauer_ms / 2)

    ansicht = seite.findChild(Streckenansicht)
    assert ansicht is not None
    assert len(ansicht._autos) == konfig.wert("rennen", "autos")
    assert not ansicht.grab().isNull()


def test_wiedergabe_stoppt_am_ende(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)

    seite._springe(seite.verlauf.dauer_ms - 10)
    seite._laeuft = True
    seite._raffer.setCurrentIndex(seite._raffer.count() - 1)
    seite._takt()
    assert seite.zeit_ms == seite.verlauf.dauer_ms
    assert not seite._laeuft


def test_rennen_laeuft_von_selbst_los(qtbot, konfig: kf.Konfiguration) -> None:
    """Das Rennen soll sich wie eine Uebertragung anfuehlen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)
    assert konfig.wert("zeitraffer", "automatisch_starten")
    assert seite._laeuft
    seite._halte_an()


def test_zeitraffer_wird_zur_renndauer_gewaehlt(qtbot, konfig: kf.Konfiguration) -> None:
    """Die Vorwahl muss das Rennen in ertraeglicher Zeit durchlaufen lassen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)
    seite._halte_an()

    wunsch_ms = konfig.wert("zeitraffer", "wunschdauer_s") * 1000
    stufen = konfig.wert("zeitraffer", "stufen")
    gewaehlt = seite._raffer.currentData()
    dauer = seite.verlauf.dauer_ms / gewaehlt
    assert dauer <= wunsch_ms or gewaehlt == stufen[-1]
    # Und es ist die kleinste Stufe, die das schafft.
    kleiner = [stufe for stufe in stufen if stufe < gewaehlt]
    if kleiner:
        assert seite.verlauf.dauer_ms / kleiner[-1] > wunsch_ms


def test_rennen_zeigt_das_wetter(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster)
    seite._halte_an()
    seite._springe(seite.verlauf.dauer_ms / 2)

    assert seite.verlauf.wetter is not None
    assert seite._wetteranzeige.text() != "-"
    assert seite.verlauf.wetter.zustand_zu(seite.zeit_ms) in seite._wetteranzeige.text()


# -- Qualifyingseite --------------------------------------------------------
def test_qualifyingseite_faehrt_eine_session(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.qualifyingseite
    seite._fahre()

    assert seite.session is not None
    assert len(seite.session.fahrten) == konfig.wert("rennen", "autos")
    assert len(seite.session.aufstellung) == konfig.wert("rennen", "autos")


def test_qualifying_sortiert_live_ein(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: Live-Einsortierung ins Ranking."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.qualifyingseite
    seite._fahre()

    seite._regler.setValue(1)
    assert seite._rangliste.topLevelItemCount() == 1
    seite._regler.setValue(10)
    assert seite._rangliste.topLevelItemCount() == 10
    seite._regler.setValue(seite._regler.maximum())
    assert seite._rangliste.topLevelItemCount() == konfig.wert("rennen", "autos")


def test_qualifying_zeigt_aufstellung_und_wetter(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.qualifyingseite
    seite._fahre()

    assert seite._aufstellung.topLevelItemCount() == konfig.wert("rennen", "autos")
    assert seite._aufstellung.topLevelItem(0).text(0) == "1"
    assert seite._wetterfeld.rowCount() > 0


def test_qualifying_rueckstand_nur_ab_platz_zwei(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.qualifyingseite
    seite._fahre()
    seite._regler.setValue(seite._regler.maximum())

    liste = seite._rangliste
    assert liste.topLevelItem(0).text(3) == ""
    assert liste.topLevelItem(1).text(3).startswith("+")


def test_rennen_kann_aufstellung_aus_dem_qualifying_nehmen(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """GDD 4: Aufstellung nach Qualifying."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite
    seite._runden.setValue(2)
    seite._aufstellung.setCurrentIndex(0)
    seite._berechne()
    seite._halte_an()

    assert seite.qualifying is not None
    # Wer die Pole geholt hat, startet von Platz 1.
    pole = seite.qualifying.aufstellung[0]
    kuerzel = seite.qualifying.teilnehmer[pole].kuerzel
    erster = next(t for t in seite.verlauf.teilnehmer if t.startplatz == 1)
    assert erster.kuerzel == kuerzel


# -- Weltseite --------------------------------------------------------------
def test_fenster_erzeugt_eine_welt(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 12: 600 Autos, 150 Teams, 20 Ligen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    welt = fenster.welt

    ligen = konfig.wert("ligen", "anzahl")
    assert len(welt.fahrer) == ligen * konfig.wert("ligen", "autos_je_liga")
    assert len(welt.teams) == konfig.wert("teams", "anzahl")
    assert welt.spieler is not None
    assert welt.spieler.liga == konfig.wert("ligen", "startliga")


def test_weltseite_zeigt_eine_ganze_liga(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    # 20 Ligen plus der Eintrag "Alle Ligen".
    assert seite.liga_auswahl.count() == konfig.wert("ligen", "anzahl") + 1
    assert seite.liste.topLevelItemCount() == konfig.wert("ligen", "autos_je_liga")
    # Die Liste beginnt beim staerksten Fahrer.
    assert seite.liste.topLevelItem(0).text(0) == "1"


def test_weltseite_wechselt_die_liga(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    seite.liga_auswahl.setCurrentIndex(1)
    oben = [seite.liste.topLevelItem(i).text(2) for i in range(5)]
    seite.liga_auswahl.setCurrentIndex(20)
    unten = [seite.liste.topLevelItem(i).text(2) for i in range(5)]
    assert oben != unten


def test_weltseite_zeigt_alle_600_fahrer(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    seite.liga_auswahl.setCurrentIndex(0)  # "Alle Ligen"
    assert seite.liste.topLevelItemCount() == len(fenster.welt.fahrer)
    # Eine Liga-Spalte kommt dazu, und der Platz zaehlt je Liga neu.
    kopf = [seite.liste.headerItem().text(i) for i in range(seite.liste.columnCount())]
    assert kopf[1] == "Liga"
    je_liga = konfig.wert("ligen", "autos_je_liga")
    assert seite.liste.topLevelItem(0).text(1) == "1"
    assert seite.liste.topLevelItem(je_liga).text(1) == "2"
    assert seite.liste.topLevelItem(je_liga).text(0) == "1"


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
    seite = _kurzes_rennen(fenster)
    seite._halte_an()

    liga = seite._liga.currentData()
    erwartet = {f.kuerzel for f in fenster.welt.liga(liga)}
    assert {t.kuerzel for t in seite.verlauf.teilnehmer} == erwartet


def test_rennen_startet_in_der_liga_des_spielers(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    assert fenster.rennseite._liga.currentData() == fenster.welt.spieler.liga
    assert fenster.qualifyingseite._liga.currentData() == fenster.welt.spieler.liga


# -- Karriereseite ----------------------------------------------------------
def test_karriereseite_startet_am_ersten_januar(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    karriere = fenster.karriereseite.karriere

    assert karriere.heute.month == 1 and karriere.heute.day == 1
    assert karriere.konto.geld == konfig.wert("kosten", "startkapital_euro")
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


def test_tageswechsel_gibt_die_plaetze_frei(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.karriereseite

    seite.waehle("D1")
    seite._belege_tag()
    assert seite.karriere.belegt
    seite._tag_weiter()
    assert not seite.karriere.belegt
    seite.waehle("D1")
    seite._belege_tag()
    assert seite.karriere.wert("D1") == 20


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


# --- Saison ---------------------------------------------------------------
def test_saisonseite_startet_bei_der_liga_des_spielers(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite

    assert seite.liga_auswahl.currentData() == fenster.welt.spieler.liga
    assert seite.lauf.gefahren == 0
    assert seite.lauf.naechstes_rennen == 1
    # Vor dem ersten Rennen ist die Tabelle leer und es gibt keine Wechsel.
    assert seite.tabelle.topLevelItemCount() == 0
    assert seite.rennliste.topLevelItemCount() == 0
    assert seite.wechselliste.topLevelItemCount() == 0


def test_saisonseite_faehrt_ein_rennwochenende(qtbot, konfig: kf.Konfiguration) -> None:
    """Ein Klick faehrt alle 20 Ligen und fuellt Tabelle und Ergebnis."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite

    seite.knopf_rennwochenende.click()

    autos = konfig.wert("ligen", "autos_je_liga")
    assert seite.lauf.gefahren == 1
    assert seite.tabelle.topLevelItemCount() == autos
    assert seite.rennliste.topLevelItemCount() == autos
    # Der Tabellenerste hat die meisten Punkte.
    punkte = [int(seite.tabelle.topLevelItem(i).text(3)) for i in range(autos)]
    assert punkte == sorted(punkte, reverse=True)
    # Der Auf- und Abstieg steht erst am Saisonende fest.
    assert seite.wechselliste.topLevelItemCount() == 0


def test_saisonseite_wechselt_die_liga(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    seite.knopf_rennwochenende.click()

    seite.liga_auswahl.setCurrentIndex(0)
    assert seite.liga_auswahl.currentData() == 1
    namen_liga1 = {seite.tabelle.topLevelItem(i).text(1) for i in range(20)}
    seite.liga_auswahl.setCurrentIndex(9)
    namen_liga10 = {seite.tabelle.topLevelItem(i).text(1) for i in range(20)}
    assert not namen_liga1 & namen_liga10


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
    fenster.saisonseite.knopf_rennwochenende.click()

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
    fenster.saisonseite.knopf_rennwochenende.click()
    pfad = tmp_path / "stand.sqlite"
    kern_spielstand.speichere(fenster.spielstand(), pfad)

    zweites = Hauptfenster(konfig)
    qtbot.addWidget(zweites)
    zweites.uebernimm(kern_spielstand.lade(konfig, pfad))
    zweites.saisonseite.knopf_rennwochenende.click()

    assert zweites.saisonseite.lauf.gefahren == 2
    # Die Punkte aus dem geladenen Rennen sind noch da.
    spieler = zweites.welt.spieler
    assert zweites.saisonseite.lauf.tabelle(spieler.liga).eintraege[spieler.nummer].rennen == 2


# --- Editor ---------------------------------------------------------------
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

    seite.liga_auswahl.setCurrentIndex(0)  # alle Ligen
    ziel = fenster.welt.fahrer[100]
    seite.suche.setText(ziel.nachname)
    namen = {
        seite.liste.topLevelItem(i).text(2) for i in range(seite.liste.topLevelItemCount())
    }
    assert ziel.name in namen
    assert seite.liste.topLevelItemCount() < len(fenster.welt.fahrer)


def test_editor_aendert_werte_dauerhaft(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    # Einen KI-Fahrer waehlen, damit die Karriere nicht mitspielt.
    seite.liga_auswahl.setCurrentIndex(1)
    zeile = seite.liste.topLevelItem(0)
    seite.liste.setCurrentItem(zeile)
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

    seite.liga_auswahl.setCurrentIndex(1)
    zeile = seite.liste.topLevelItem(0)
    seite.liste.setCurrentItem(zeile)
    nummer = zeile.data(0, Qt.UserRole)

    vorname, nachname, land, _geburtstag = seite.stammdaten
    vorname.setText("Ada")
    nachname.setText("Lovelace")
    land.setText("Grossbritannien")
    seite.knopf_uebernehmen.click()

    geaendert = seite.welt.fahrer[nummer]
    assert geaendert.name == "Ada Lovelace"
    assert geaendert.land == "Grossbritannien"
    # Liga, Team und Kuerzel bleiben, wie die Welt sie vergeben hat.
    assert geaendert.liga == fenster.welt.fahrer[nummer].liga
    assert geaendert.team == fenster.welt.fahrer[nummer].team
    assert geaendert.kuerzel == fenster.welt.fahrer[nummer].kuerzel


def test_editor_gibt_die_geaenderte_welt_ans_fenster(qtbot, konfig: kf.Konfiguration) -> None:
    """Beim Verlassen des Reiters uebernimmt das Fenster die neue Welt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite
    reiter = fenster._reiter

    seite.liga_auswahl.setCurrentIndex(1)
    zeile = seite.liste.topLevelItem(0)
    seite.liste.setCurrentItem(zeile)
    nummer = zeile.data(0, Qt.UserRole)
    seite.felder["F1"].setValue(55_000)
    seite.knopf_uebernehmen.click()
    assert fenster.welt.fahrer[nummer].auto.wert("F1") != 55_000

    reiter.setCurrentIndex(reiter.indexOf(fenster.weltseite))
    assert fenster.welt.fahrer[nummer].auto.wert("F1") == 55_000


def test_editor_schreibt_die_werte_des_spielers_in_die_karriere(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """Der Spieler entwickelt sich (GDD 1); seine Werte stehen in der
    Karriere, nicht in der Welt."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    seite._springe_zum_spieler()
    spieler = fenster.welt.spieler
    assert seite.liste.currentItem().data(0, Qt.UserRole) == spieler.nummer
    assert seite.felder["F1"].value() == fenster.karriereseite.karriere.werte["F1"]

    seite.felder["F1"].setValue(12_345)
    seite.knopf_uebernehmen.click()
    assert fenster.karriereseite.karriere.werte["F1"] == 12_345


def test_editierte_werte_kommen_im_rennen_an(qtbot, konfig: kf.Konfiguration) -> None:
    """Der eigentliche Zweck: Was im Editor steht, faehrt auch so."""
    from rennmanager.kern import welt as kern_welt

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite

    seite.liga_auswahl.setCurrentIndex(1)
    zeile = seite.liste.topLevelItem(0)
    seite.liste.setCurrentItem(zeile)
    nummer = zeile.data(0, Qt.UserRole)
    for schluessel in seite.felder:
        seite.felder[schluessel].setValue(90_000)
    seite.knopf_uebernehmen.click()
    fenster.uebernimm_welt(seite.welt)

    feld = kern_welt.starterfeld(fenster.welt, fenster.welt.fahrer[nummer].liga)
    kuerzel = fenster.welt.fahrer[nummer].kuerzel
    gefahren = next(t for t in feld if t.auto.kuerzel == kuerzel)
    assert gefahren.auto.wert("F1") == 90_000
