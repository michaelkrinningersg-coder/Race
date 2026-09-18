"""Tests fuer die Oberflaeche.

Die Tests laufen mit ``QT_QPA_PLATFORM=offscreen`` und brauchen keinen
Bildschirm; die Konfiguration dafuer steht in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest

from rennmanager import __version__
from rennmanager import konfiguration as kf
from rennmanager.kern import wertung as wt

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QTreeWidget  # noqa: E402

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.tabellen import SortierbareZeile as Zeile  # noqa: E402


@pytest.fixture(scope="module")
def konfig(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: Die Oberflaechen-Tests laufen auf der kleinen Welt.

    Jeder dieser Tests baut ein ganzes ``Hauptfenster`` - und damit eine
    Welt, eine Karriere und alle Seiten. In voller Groesse sind das 600
    Fahrer je Fenster, 86-mal in dieser Datei. Geprueft wird hier, ob die
    Oberflaeche das Richtige liest und zeichnet; dafuer genuegen drei
    Ligen zu je vier Autos. Wo die Groesse selbst Gegenstand ist, steht
    ``grosse_konfiguration``.
    """
    return kleine_konfiguration


@pytest.fixture(scope="module")
def grosse_konfiguration() -> kf.Konfiguration:
    """Die echte Konfiguration mit 20 Ligen zu je 30 Autos."""
    return kf.lade()


# --- Helfer, die ohne feste Weltgroesse auskommen (Punkt 77) --------------
def waehle_liga(auswahl, liga: int) -> None:
    """Waehlt eine Liga ueber ihre **Nummer**, nicht ueber den Listenplatz.

    Feste Indizes trafen in der kleinen Welt ins Leere: ``setCurrentIndex(10)``
    liess die Liste einfach leer, und der Test fiel weit spaeter mit einem
    ``NoneType`` um die Ohren.
    """
    index = auswahl.findData(liga)
    assert index >= 0, f"Liga {liga} steht nicht in der Auswahl"
    auswahl.setCurrentIndex(index)


def ein_fahrer(fenster, anteil: float = 0.5):
    """Irgendein Fahrer aus dem Feld - anteilig statt an fester Stelle."""
    fahrer = fenster.welt.fahrer
    return fahrer[min(int(len(fahrer) * anteil), len(fahrer) - 1)]


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


# -- Rennanzeige ------------------------------------------------------------
def _kurzes_rennen(fenster, runden: int = 2, umgedreht: bool = False):
    """Rechnet ein kurzes Rennen und gibt es der Rennanzeige.

    Die Rennseite rechnet seit Punkt 12 nichts mehr - sie spielt ab, was
    ihr das gefuehrte Wochenende reicht. Ein echtes Wochenende dauert 19
    Runden und 17 Sekunden; die Anzeige-Tests brauchen das nicht, also
    kommt hier ein Zweirundenrennen aus dem Kern.
    """
    verlauf, strecke = _rennverlauf(fenster, runden, umgedreht)
    seite = fenster.rennseite
    seite.zeige_verlauf(verlauf, strecke)
    return seite


def _rennverlauf(fenster, runden: int = 2, umgedreht: bool = False):
    """Nur der Lauf, ohne Anzeige - damit er sich teilen laesst.

    Punkt 77: Wer denselben Lauf in zwanzig Tests zeigt, soll ihn einmal
    rechnen. Gemessen kostet ein Vierrundenrennen 4,8 Sekunden.
    """
    from rennmanager.kern import rennen as kern_rennen
    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.kern import tempo as kern_tempo
    from rennmanager.kern import welt as kern_welt
    from rennmanager.kern import wetter as kern_wetter
    from rennmanager.kern.zufall import Seedquelle

    liga = fenster.welt.spieler.liga
    strecke = kern_strecke.lade(fenster._konfiguration, fenster._konfiguration.strecken[0]["name"])
    feld = kern_welt.starterfeld(fenster.welt, liga)
    if umgedreht:
        anzahl = len(feld)
        feld = tuple(
            kern_rennen.Teilnehmer(
                auto=t.auto,
                startplatz=anzahl + 1 - t.startplatz,
                farbe=t.farbe,
                ist_spieler=t.ist_spieler,
                nummer=t.nummer,
            )
            for t in feld
        )
    haupt = Seedquelle(4711)
    # Das Wetter gehoert dazu (GDD 7); ohne es stuende im Rennen "None".
    rundendauer = kern_tempo.fahre_runde(
        fenster._konfiguration, strecke, feld[0].auto
    ).zeit_ms
    verlauf = kern_rennen.simuliere(
        fenster._konfiguration,
        strecke,
        feld,
        runden,
        haupt.zweig("rennen"),
        kern_rennen.mittlerer_ueberholzonenanteil(fenster._konfiguration, (strecke,)),
        wetter=kern_wetter.wuerfle(
            fenster._konfiguration,
            strecke.name,
            rundendauer * runden,
            rundendauer,
            haupt.zweig("rennwetter"),
        ),
    )
    return verlauf, strecke


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
    seite = _kurzes_rennen(fenster)
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
    # Erst wenn jemand hinschaut: Sonst liefe im Hintergrund ein Rennen,
    # das keiner sieht, und waere vorbei, bevor man den Reiter oeffnet.
    assert not seite._laeuft
    fenster.show()
    fenster._reiter.setCurrentWidget(fenster._wochenendeseite)
    fenster._wochenendeseite._blaetter.setCurrentWidget(seite)
    assert seite.isVisible()
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
def _gefahrenes_qualifying(fenster):
    """Faehrt das Qualifying des naechsten Wochenendes (Punkt 12).

    Eigene Regler hat die Qualifyingseite seit Punkt 12 nicht mehr; sie
    zeigt, was das gefuehrte Wochenende ihr reicht. Das Qualifying selbst
    dauert nur Bruchteile einer Sekunde.
    """
    fenster.wochenendeseite.knopf_weiter.click()
    return fenster.qualifyingseite


def test_qualifyingseite_faehrt_eine_session(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _gefahrenes_qualifying(fenster)

    assert seite.session is not None
    assert len(seite.session.fahrten) == konfig.wert("rennen", "autos")
    assert len(seite.session.aufstellung) == konfig.wert("rennen", "autos")


def test_qualifying_sortiert_live_ein(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 4: Live-Einsortierung ins Ranking."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _gefahrenes_qualifying(fenster)

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
    seite = _gefahrenes_qualifying(fenster)

    assert seite._aufstellung.topLevelItemCount() == konfig.wert("rennen", "autos")
    assert seite._aufstellung.topLevelItem(0).text(0) == "1"
    assert seite._wetterfeld.rowCount() > 0


def test_qualifying_rueckstand_nur_ab_platz_zwei(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _gefahrenes_qualifying(fenster)
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

    zeilen = min(5, konfig.wert("ligen", "autos_je_liga"))

    def namen() -> list[str]:
        return [seite.liste.topLevelItem(i).text(2) for i in range(zeilen)]

    waehle_liga(seite.liga_auswahl, 1)
    oben = namen()
    waehle_liga(seite.liga_auswahl, konfig.wert("ligen", "anzahl"))
    assert oben != namen()


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

    liga = fenster.welt.spieler.liga
    erwartet = {f.kuerzel for f in fenster.welt.liga(liga)}
    assert {t.kuerzel for t in seite.verlauf.teilnehmer} == erwartet


def test_gefahren_wird_die_liga_des_spielers(qtbot, konfig: kf.Konfiguration) -> None:
    """Seit Punkt 12 gibt es keine Ligawahl mehr - gefahren wird die eigene."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    gefuehrt = fenster.wochenendeseite
    assert gefuehrt.wochenende.liga == fenster.welt.spieler.liga

    gefuehrt.knopf_weiter.click()
    kuerzel = {t.kuerzel for t in gefuehrt.qualifyingseite.session.teilnehmer}
    assert kuerzel == {f.kuerzel for f in fenster.welt.liga(fenster.welt.spieler.liga)}


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

    seite.lauf.fahre_rennen()
    seite._aktualisiere()

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
    seite.lauf.fahre_rennen()
    seite._aktualisiere()

    zeilen = konfig.wert("ligen", "autos_je_liga")

    def namen() -> set[str]:
        return {seite.tabelle.topLevelItem(i).text(1) for i in range(zeilen)}

    waehle_liga(seite.liga_auswahl, 1)
    assert seite.liga_auswahl.currentData() == 1
    erste = namen()
    waehle_liga(seite.liga_auswahl, konfig.wert("ligen", "anzahl"))
    assert not erste & namen()


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


def fahre_saison_zu_ende(konfig, seite) -> None:
    """Setzt die Saison auf beendet, ohne 400 Rennen zu fahren."""
    lauf = seite.lauf
    lauf.tabellen = {
        liga: wt.Tabelle(liga) for liga in range(1, konfig.wert("ligen", "anzahl") + 1)
    }
    for liga, tabelle in lauf.tabellen.items():
        tabelle.verbuche(
            konfig,
            [
                wt.Rennergebnis(fahrer=f.nummer, rennplatz=platz, qualifyingplatz=platz)
                for platz, f in enumerate(lauf.welt.liga(liga), start=1)
            ],
        )
    lauf.vorgefahren = konfig.wert("kalender", "rennen_je_saison")
    seite._aktualisiere()


def test_saisonseite_zeigt_den_abschluss(qtbot, konfig: kf.Konfiguration) -> None:
    """Nach Rennen 20: Meister, eigene Bilanz und der Knopf zum Wechsel."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    assert not seite.knopf_naechste_saison.isEnabled()

    fahre_saison_zu_ende(konfig, seite)
    assert seite.knopf_naechste_saison.isEnabled()
    assert not seite.knopf_restliche_saison.isEnabled()
    text = seite.abschlusstext.text()
    assert fenster.welt.spieler.name in text
    assert f"Liga {fenster.welt.spieler.liga}" in text
    # Alle 20 Ligen haben einen Meister.
    assert text.count("Punkte") >= konfig.wert("ligen", "anzahl")
    assert seite.wechselliste.topLevelItemCount() > 0


def test_saisonseite_wechselt_ins_naechste_jahr(qtbot, konfig: kf.Konfiguration) -> None:
    """GDD 13: Auf- und Abstieg, dann beginnt die naechste Saison."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    jahr = seite.lauf.jahr
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
    # Die Welt ist eine neue; jede Liga ist weiter voll besetzt.
    groessen = {}
    for f in fenster.welt.fahrer:
        groessen[f.liga] = groessen.get(f.liga, 0) + 1
    assert set(groessen.values()) == {konfig.wert("ligen", "autos_je_liga")}
    # Die Statistik hat die abgeschlossene Saison behalten.
    assert fenster.statistik.saisons == (jahr,)
    assert neue.liga_auswahl.currentData() == fenster.welt.spieler.liga


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
    ziel = ein_fahrer(fenster)
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


def test_editor_zeigt_je_fahrer_die_rundenzeit(qtbot, konfig: kf.Konfiguration) -> None:
    """Trocken und ohne jeden Wurf - so laesst sich vergleichen."""
    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.kern import tempo as kern_tempo
    from rennmanager.kern.zeit import formatiere_dauer

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite
    # Liga 1 gibt es in jeder Weltgroesse, und der Spieler faehrt nie dort.
    waehle_liga(seite.liga_auswahl, 1)

    name = seite.streckenauswahl.currentData()
    strecke = kern_strecke.lade(konfig, name)
    zeile = seite.liste.topLevelItem(0)
    fahrer = fenster.welt.fahrer[zeile.data(0, Qt.UserRole)]

    frei = kern_tempo.fahre_runde(konfig, strecke, fahrer.auto).zeit_ms
    kenntnis = fenster._kenntnis.tempofaktor(fahrer.nummer, name)
    assert zeile.text(5) == formatiere_dauer(int(round(frei / kenntnis)))


def test_editor_rechnet_die_zeiten_je_strecke_neu(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite
    # Liga 1 gibt es in jeder Weltgroesse, und der Spieler faehrt nie dort.
    waehle_liga(seite.liga_auswahl, 1)

    def zeiten() -> list[str]:
        return [
            seite.liste.topLevelItem(i).text(5)
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
    # Liga 1 gibt es in jeder Weltgroesse, und der Spieler faehrt nie dort.
    waehle_liga(seite.liga_auswahl, 1)

    zeiten = [
        seite.liste.topLevelItem(i).data(5, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
    ]
    rueckstaende = [
        seite.liste.topLevelItem(i).data(6, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
    ]
    bestzeit = min(zeiten)
    assert rueckstaende == [zeit - bestzeit for zeit in zeiten]
    # Genau eine Zeile ist die Bestzeit und hat keinen Rueckstand.
    leer = [
        i
        for i in range(seite.liste.topLevelItemCount())
        if seite.liste.topLevelItem(i).text(6) == ""
    ]
    assert len(leer) == 1


def test_editor_sortiert_nach_rundenzeit(qtbot, konfig: kf.Konfiguration) -> None:
    """Wer auf dieser Strecke am schnellsten ist, muss nicht der Staerkste sein."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite
    # Liga 1 gibt es in jeder Weltgroesse, und der Spieler faehrt nie dort.
    waehle_liga(seite.liga_auswahl, 1)

    seite.liste.sortByColumn(5, Qt.AscendingOrder)
    zeiten = [
        seite.liste.topLevelItem(i).data(5, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
    ]
    assert zeiten == sorted(zeiten)


def test_editor_rechnet_nach_einer_aenderung_neu(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.editorseite
    # Liga 1 gibt es in jeder Weltgroesse, und der Spieler faehrt nie dort.
    waehle_liga(seite.liga_auswahl, 1)

    zeile = seite.liste.topLevelItem(0)
    seite.liste.setCurrentItem(zeile)
    nummer = zeile.data(0, Qt.UserRole)
    vorher = zeile.data(5, Zeile.SORTIERROLLE)

    # Auf den Hoechstwert statt auf feste 90 000: In Liga 1 stehen die
    # Fahrer schon darueber, und der Test maass dann das Gegenteil.
    for schluessel in seite.felder:
        seite.felder[schluessel].setValue(seite.felder[schluessel].maximum())
    seite.knopf_uebernehmen.click()

    nachher = next(
        seite.liste.topLevelItem(i).data(5, Zeile.SORTIERROLLE)
        for i in range(seite.liste.topLevelItemCount())
        if seite.liste.topLevelItem(i).data(0, Qt.UserRole) == nummer
    )
    assert nachher < vorher


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


# -- Fahrersuche (Punkt 18) --------------------------------------------------
def test_die_suche_kennt_alle_600_fahrer(qtbot, konfig) -> None:
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
    """Nach Auf- und Abstieg stehen die Ligen anders - die Suche auch."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fahre_saison_zu_ende(konfig, fenster.saisonseite)
    fenster.saisonseite.knopf_naechste_saison.click()
    qtbot.wait(20)

    suche = fenster.fahrersuche
    assert suche.vervollstaendigung.model().rowCount() == len(fenster.welt.fahrer)
    spieler = fenster.welt.spieler
    gefunden = suche.treffer(spieler.name)
    assert spieler.nummer in gefunden
    # Die Zeile nennt die neue Liga.
    zeilen = [
        z for z in suche._nummer_zu if suche._nummer_zu[z] == spieler.nummer
    ]
    assert f"Liga {spieler.liga} " in zeilen[0]


def test_die_suche_nennt_liga_und_team(qtbot, konfig) -> None:
    """Nachnamen gibt es zweimal - die Zeile muss sie auseinanderhalten."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    fahrer = ein_fahrer(fenster, 0.8)
    team = fenster.welt.team_von(fahrer)

    from rennmanager.ui.fahrersuche import eintrag

    zeile = eintrag(konfig, fahrer, team)
    assert fahrer.name in zeile
    assert fahrer.kuerzel in zeile
    assert f"Liga {fahrer.liga}" in zeile
    assert team.name in zeile


def test_fahrertreffer_stehen_vor_teamtreffern(qtbot, grosse_konfiguration) -> None:
    """Die Suche trifft auch Teams - aber der Fahrer geht vor.

    Dieser eine Test braucht die **grosse** Welt: Dass sich ein Nachname
    und ein Teamname ueberschneiden, ist eine Frage der Menge. Unter zwoelf
    Fahrern und drei Teams kommt es schlicht nicht vor.
    """
    fenster = Hauptfenster(grosse_konfiguration)
    qtbot.addWidget(fenster)
    suche = fenster.fahrersuche

    # Ein Nachname, der zugleich in einem Teamnamen steckt. Welcher das
    # ist, haengt an der Welt - also aus ihr geholt statt eingetippt.
    fahrer = next(
        f
        for f in fenster.welt.fahrer
        if any(f.nachname in team.name for team in fenster.welt.teams)
    )
    gefunden = suche.treffer(fahrer.nachname)
    # Denselben Nachnamen gibt es unter 600 Fahrern oefter - die Aussage
    # ist die Reihenfolge: Wer ueber den Namen passt, steht vor jedem, der
    # nur ueber den Teamnamen hereinkommt.
    assert fahrer.nummer in gefunden
    ueber_team = [
        stelle
        for stelle, nummer in enumerate(gefunden)
        if fahrer.nachname.casefold() not in fenster.welt.fahrer[nummer].nachname.casefold()
    ]
    assert not ueber_team or gefunden.index(fahrer.nummer) < min(ueber_team)

    # Und die Teamtreffer sind trotzdem dabei. Gesucht wird ein
    # Teamname aus der Welt selbst - ein fest eingetragener haenge sonst
    # daran, in welcher Reihenfolge die Welt ihre Namen vergibt.
    mannschaft = next(
        team
        for team in fenster.welt.teams
        if not any(f.nachname in team.name for f in fenster.welt.fahrer)
    )
    erstes_wort = mannschaft.name.split()[0]
    ueber_team = suche.treffer(erstes_wort)
    assert len(ueber_team) > 1
    namen = {fenster.welt.team_von(fenster.welt.fahrer[n]).name for n in ueber_team}
    assert mannschaft.name in namen
