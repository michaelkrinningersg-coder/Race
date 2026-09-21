"""Tests fuer das Grundgeruest der Oberflaeche.

Fenster, Seed, offene Punkte, Pruefmodus - dazu die Seiten, die
nur rechnen und zeichnen: Strecke, Runde, Tempo.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QTreeWidget  # noqa: E402

from rennmanager import __version__  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402


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
    assert "50 Autos" in ausgabe
    # Punkt 101: Der Pruefmodus nennt die Spanne des einen Feldes.
    assert "Rundenzeitspanne" in ausgabe


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


# --- Punkt 95: Teamfarben als Schrift -------------------------------------
def test_helle_teamfarben_werden_fuer_die_schrift_abgedunkelt(konfig) -> None:
    """Gelb auf Weiss ist keine Schrift mehr.

    Die Teamfarbe ist fuer die Punkte auf der Streckenkarte gemacht
    (GDD 4 und 12). Als Kuerzel in einer Tabelle muss sie lesbar sein;
    ``schriftfarbe`` dunkelt sie dafuer ab, ohne den Farbton zu drehen.
    """
    from PySide6.QtGui import QColor

    from rennmanager.ui.tabellen import MINDESTKONTRAST, kontrast, schriftfarbe

    gelb = "#fff82e"
    assert kontrast(QColor(gelb)) < 2.0, "Testfarbe ist schon lesbar"
    lesbar = schriftfarbe(gelb)
    assert kontrast(lesbar) >= MINDESTKONTRAST
    # Derselbe Farbton, nur dunkler.
    assert lesbar.hslHue() == QColor(gelb).hslHue()
    assert lesbar.lightness() < QColor(gelb).lightness()

    # Was dunkel genug ist, bleibt unveraendert.
    dunkel = "#0e294b"
    assert schriftfarbe(dunkel).name() == dunkel


def test_jede_teamfarbe_ist_in_der_tabelle_lesbar(grosse_konfiguration) -> None:
    """Keine der Teamfarben darf in einer Tabelle untergehen.

    Hier geht es um die Farben selbst, also um die **echte** Welt mit
    ihren 25 Teams - die kleine Testwelt hat zu wenige, um etwas zu
    beweisen.

    Seit Punkt 101 traegt jedes Team die Farbe seines Herstellers; geprueft
    werden damit genau die 25 Farben aus ``hersteller.toml``.
    """
    from rennmanager.kern import welt as kern_welt
    from rennmanager.kern.zufall import Seedquelle
    from rennmanager.ui.tabellen import MINDESTKONTRAST, kontrast, schriftfarbe

    konfig = grosse_konfiguration
    welt = kern_welt.erzeuge(konfig, Seedquelle(0).zweig("welt"))
    assert len(welt.teams) == konfig.wert("teams", "anzahl")
    schlechteste = min(kontrast(schriftfarbe(t.farbe)) for t in welt.teams)
    assert schlechteste >= MINDESTKONTRAST


# --- Punkt 98: Vorname abgekuerzt, Nachname voll --------------------------
def test_der_kurzname_kuerzt_nur_den_vornamen() -> None:
    """"Michael Krinninger" wird zu "M. Krinninger"."""
    from rennmanager.ui.tabellen import kurzname

    assert kurzname("Michael Krinninger") == "M. Krinninger"
    # Mehrteilige Nachnamen bleiben ganz - gekuerzt wird nur das Erste.
    assert kurzname("Jean-Luc de la Vega") == "J. de la Vega"
    # Wer nur einen Namen hat, behaelt ihn; leer bleibt leer.
    assert kurzname("Meier") == "Meier"
    assert kurzname("") == ""
    assert kurzname(None) == ""
