"""Tests fuer die Oberflaeche.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import __version__
from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

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

    assert seite.liga_auswahl.count() == konfig.wert("ligen", "anzahl")
    assert seite.liste.topLevelItemCount() == konfig.wert("ligen", "autos_je_liga")
    # Die Liste beginnt beim staerksten Fahrer.
    assert seite.liste.topLevelItem(0).text(0) == "1"


def test_weltseite_wechselt_die_liga(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    seite.liga_auswahl.setCurrentIndex(0)
    oben = [seite.liste.topLevelItem(i).text(2) for i in range(5)]
    seite.liga_auswahl.setCurrentIndex(19)
    unten = [seite.liste.topLevelItem(i).text(2) for i in range(5)]
    assert oben != unten


def test_weltseite_zeigt_das_profil(qtbot, konfig: kf.Konfiguration) -> None:
    """Am Profil sieht man Regenspezialisten und Reifenschoner (GDD 12)."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite

    seite.liste.setCurrentItem(seite.liste.topLevelItem(0))
    profil = seite._profil
    bereiche = [profil.topLevelItem(i).text(0) for i in range(profil.topLevelItemCount())]
    assert len(bereiche) == len(konfig.bereiche) + len(konfig.zusatzfaehigkeiten)
    assert "Reifenfluesterer".lower() in [b.lower() for b in bereiche]


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
