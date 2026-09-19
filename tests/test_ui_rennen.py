"""Tests fuer Rennanzeige und Qualifying.

Beide spielen seit Punkt 12 nur ab, was der Kern ihnen reicht. Sie
stehen zusammen in einer Datei, weil das Qualifying die Aufstellung
des Rennens bestimmt.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from tests.oberflaeche import gefahrenes_qualifying, kurzes_rennen  # noqa: E402


def test_rennseite_berechnet_ein_rennen(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)

    assert seite.verlauf is not None
    assert len(seite.verlauf.teilnehmer) == konfig.wert("rennen", "autos")
    assert len(seite.verlauf.ergebnisse) == konfig.wert("rennen", "autos")


def test_rennseite_spielt_den_verlauf_ab(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)

    seite._springe(0)
    anfang = seite.verlauf.distanzen_zu(seite.zeit_ms).copy()
    seite._springe(seite.verlauf.dauer_ms / 2)
    mitte = seite.verlauf.distanzen_zu(seite.zeit_ms)
    assert (mitte > anfang).all()


def test_sofortergebnis_springt_ans_ende(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: Zeitraffer bis 100x und Sofortergebnis."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)

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
    seite = kurzes_rennen(fenster)

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
    seite = kurzes_rennen(fenster)
    seite._springe(seite.verlauf.dauer_ms / 2)

    from rennmanager.ui.rennseite import SPALTE_ZEIT

    liste = seite._rangliste
    autos = konfig.wert("rennen", "autos")
    assert liste.topLevelItemCount() == autos
    oben = min(5, autos)
    assert [liste.topLevelItem(i).text(0) for i in range(oben)] == [
        str(platz) for platz in range(1, oben + 1)
    ]
    # Der Fuehrende zeigt seine Gesamtzeit, die uebrigen einen Abstand.
    # Seit Punkt 76 steht dazwischen die Spalte mit dem Positionspfeil -
    # die Nummer kommt deshalb aus dem Modul und nicht aus dem Kopf.
    assert not liste.topLevelItem(0).text(SPALTE_ZEIT).startswith(("+", "-"))
    assert liste.topLevelItem(1).text(SPALTE_ZEIT).startswith(("+", "-"))


def test_zeitenmonitor_zeigt_runden_und_sektoren(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._zum_ende()

    from rennmanager.ui.rennseite import MONITOR_BESTE, MONITOR_LETZTE, MONITOR_SPALTEN

    monitor = seite._monitor
    assert monitor.columnCount() == MONITOR_SPALTEN
    assert monitor.topLevelItemCount() > 0
    erste = monitor.topLevelItem(0)
    assert erste.text(MONITOR_LETZTE) != "-"
    assert erste.text(MONITOR_BESTE) != "-"


def test_rennansicht_zeichnet_die_autos(qtbot, konfig: kf.Konfiguration) -> None:
    from rennmanager.ui.streckenansicht import Streckenansicht

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fenster.resize(1200, 800)
    seite = kurzes_rennen(fenster)
    seite._springe(seite.verlauf.dauer_ms / 2)

    ansicht = seite.findChild(Streckenansicht)
    assert ansicht is not None
    assert len(ansicht._autos) == konfig.wert("rennen", "autos")
    assert not ansicht.grab().isNull()


def test_wiedergabe_stoppt_am_ende(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)

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
    seite = kurzes_rennen(fenster)
    assert konfig.wert("zeitraffer", "automatisch_starten")
    # Erst wenn jemand hinschaut: Sonst liefe im Hintergrund ein Rennen,
    # das keiner sieht, und waere vorbei, bevor man den Reiter oeffnet.
    assert not seite._laeuft
    fenster.show()
    fenster._reiter.setCurrentWidget(fenster._wochenendeseite)
    fenster._wochenendeseite._blaetter.setCurrentWidget(seite)
    assert seite.isVisible()
    assert seite._laeuft
    seite._halte_an()


def test_das_rennen_startet_mit_der_eingestellten_stufe(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """Entscheidung des Auftraggebers: jedes Rennen faengt in Echtzeit an.

    Geprueft wird gegen ``start_stufe`` aus der Konfiguration, nicht gegen
    die Eins - die Stufe ist ein Einstellwert und darf sich aendern, ohne
    dass dieser Test darueber stolpert.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._halte_an()

    assert seite._raffer.currentData() == konfig.wert("zeitraffer", "start_stufe")


def test_die_startstufe_gibt_es_wirklich(konfig: kf.Konfiguration) -> None:
    """Sonst faengt jedes Rennen still auf der langsamsten Stufe an."""
    assert konfig.wert("zeitraffer", "start_stufe") in konfig.wert("zeitraffer", "stufen")


def test_rennen_zeigt_das_wetter(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._halte_an()
    seite._springe(seite.verlauf.dauer_ms / 2)

    assert seite.verlauf.wetter is not None
    assert seite._wetteranzeige.text() != "-"
    assert seite.verlauf.wetter.zustand_zu(seite.zeit_ms) in seite._wetteranzeige.text()


def test_qualifyingseite_faehrt_eine_session(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)

    assert seite.session is not None
    assert len(seite.session.fahrten) == konfig.wert("rennen", "autos")
    assert len(seite.session.aufstellung) == konfig.wert("rennen", "autos")


def test_qualifying_sortiert_live_ein(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: Live-Einsortierung ins Ranking."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)

    autos = konfig.wert("rennen", "autos")
    seite._regler.setValue(1)
    assert seite._rangliste.topLevelItemCount() == 1
    mitte = max(2, autos // 2)
    seite._regler.setValue(mitte)
    assert seite._rangliste.topLevelItemCount() == mitte
    seite._regler.setValue(seite._regler.maximum())
    assert seite._rangliste.topLevelItemCount() == konfig.wert("rennen", "autos")


def test_qualifying_zeigt_aufstellung_und_wetter(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)

    assert seite._aufstellung.topLevelItemCount() == konfig.wert("rennen", "autos")
    assert seite._aufstellung.topLevelItem(0).text(0) == "1"
    assert seite._wetterfeld.rowCount() > 0


def test_qualifying_rueckstand_nur_ab_platz_zwei(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)
    seite._regler.setValue(seite._regler.maximum())

    liste = seite._rangliste
    assert liste.topLevelItem(0).text(3) == ""
    assert liste.topLevelItem(1).text(3).startswith("+")


def test_die_aufstellung_kommt_aus_dem_qualifying(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """GDD 4: Aufstellung nach Qualifying - im gefuehrten Wochenende immer.

    Frueher war das eine von drei Einstellungen. Seit Punkt 12 gibt es
    keine Wahl mehr: Gefahren wird, was das Qualifying ergeben hat.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    gefuehrt = fenster.wochenendeseite
    gefuehrt.knopf_weiter.click()   # Qualifying
    gefuehrt.knopf_weiter.click()   # Rennen
    seite = fenster.rennseite
    seite._halte_an()

    assert seite.qualifying is not None
    # Wer die Pole geholt hat, startet von Platz 1.
    pole = seite.qualifying.aufstellung[0]
    kuerzel = seite.qualifying.teilnehmer[pole].kuerzel
    erster = next(t for t in seite.verlauf.teilnehmer if t.startplatz == 1)
    assert erster.kuerzel == kuerzel
