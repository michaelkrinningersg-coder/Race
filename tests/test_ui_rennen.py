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
from tests.oberflaeche import (  # noqa: E402
    gefahrenes_qualifying,
    kurzes_rennen,
    schlage_blatt_auf,
    weiter,
)


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
    """GDD 4: Live-Einsortierung ins Ranking.

    Punkt 85: Getrieben wird das jetzt von der Sessionuhr, nicht mehr von
    einem Regler "Gefahrene Laeufe". Die Tabelle zeigt immer alle Autos -
    gezaehlt wird deshalb, wer schon eine Position hat.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)
    session = seite.session
    autos = konfig.wert("rennen", "autos")

    def mit_position() -> int:
        liste = seite._rangliste
        return sum(
            1
            for i in range(liste.topLevelItemCount())
            if liste.topLevelItem(i).text(0)
        )

    assert seite._rangliste.topLevelItemCount() == autos
    seite._springe(0)
    assert mit_position() == 0
    seite._springe(session.fahrten[0].ziel_ms)
    assert mit_position() == 1
    mitte = max(2, autos // 2)
    seite._springe(session.fahrten[mitte - 1].ziel_ms)
    assert mit_position() == mitte
    seite._sofort.click()
    assert mit_position() == autos


def test_qualifying_zeigt_aufstellung_und_wetter(qtbot, konfig: kf.Konfiguration) -> None:
    """Das Wetter steht sofort, die Aufstellung erst am Ende (Punkt 85)."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)

    assert seite._wetterfeld.rowCount() > 0
    assert seite._aufstellung.topLevelItemCount() == 0

    seite._sofort.click()
    assert seite._aufstellung.topLevelItemCount() == konfig.wert("rennen", "autos")
    assert seite._aufstellung.topLevelItem(0).text(0) == "1"


def test_qualifying_rueckstand_nur_ab_platz_zwei(qtbot, konfig: kf.Konfiguration) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)
    seite._sofort.click()

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
    weiter(gefuehrt, 2)   # Qualifying, dann Rennen
    seite = fenster.rennseite
    seite._halte_an()

    assert seite.qualifying is not None
    # Wer die Pole geholt hat, startet von Platz 1.
    pole = seite.qualifying.aufstellung[0]
    kuerzel = seite.qualifying.teilnehmer[pole].kuerzel
    erster = next(t for t in seite.verlauf.teilnehmer if t.startplatz == 1)
    assert erster.kuerzel == kuerzel


# -- Die vier Blaetter rechts (Punkt 82) ------------------------------------
def test_die_meldungen_sind_ein_blatt_und_keine_fussleiste(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """Punkt 82: Der Ticker nahm den Tabellen unten Hoehe weg.

    Punkt 93 hat die Boxenbilanz danebengestellt, deshalb steht hier
    kein vollstaendiger Vergleich mehr, sondern die Reihenfolge der
    ersten vier: Wer ein Blatt dazwischenschiebt, soll das merken, wer
    eines anhaengt, nicht.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._halte_an()

    ueberschriften = [
        seite.blaetter_rechts.tabText(i) for i in range(seite.blaetter_rechts.count())
    ]
    assert ueberschriften[:4] == [
        "Zeitenmonitor", "Bestmoegliche Runde", "Meisterschaft", "Meldungen",
    ]
    # Der Ticker haengt wirklich in den Blaettern, nicht mehr daneben.
    assert seite.ticker.isAncestorOf(seite.ticker)
    assert seite.blaetter_rechts.isAncestorOf(seite.ticker)


@pytest.mark.parametrize(
    ("blatt", "spalte"),
    [("rangliste", 3), ("monitor", 2), ("ideal", 2), ("meisterschaft", 3)],
)
def test_jedes_blatt_hat_eine_teamspalte(
    qtbot, konfig: kf.Konfiguration, blatt: str, spalte: int
) -> None:
    """Punkt 82: Wer fuer wen faehrt, stand bisher nirgends im Rennen.

    Die Ueberschrift steht in allen vier Blaettern. Gefuellt sind hier
    nur drei: Die Meisterschaft bleibt ohne Saisontabelle leer, und ein
    Testrennen hat keine Saison.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._zum_ende()
    seite._halte_an()

    if blatt in ("monitor", "ideal", "meisterschaft"):
        schlage_blatt_auf(seite, blatt)
    liste = getattr(seite, blatt)
    assert liste.headerItem().text(spalte) == "Team"
    if blatt == "meisterschaft":
        return
    gefuellt = [
        liste.topLevelItem(i).text(spalte) for i in range(liste.topLevelItemCount())
    ]
    assert gefuellt, f"{blatt} ist leer"
    assert any(gefuellt), f"{blatt}: keine einzige Teamspalte gefuellt"


def test_der_schnellste_sektor_des_feldes_ist_lila(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """Punkt 82: Wer den Sektor haelt, bekommt ihn lila - genau einer je Sektor.

    Geprueft wird gegen die Farbe aus dem Modul, nicht gegen einen
    wiederholten Farbwert.
    """
    from rennmanager.ui.rennseite import FARBE_BESTER_SEKTOR, MONITOR_SEKTOR

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    # Ohne gefahrene Runden gibt es keine Sektorzeiten - seit Punkt 81
    # startet die Anzeige in Echtzeit und steht beim Anhalten noch am Start.
    seite._zum_ende()
    seite._halte_an()

    monitor = seite.monitor
    lila_je_sektor: dict[int, int] = {}
    for i in range(monitor.topLevelItemCount()):
        zeile = monitor.topLevelItem(i)
        for sektor in range(monitor.columnCount() - MONITOR_SEKTOR):
            spalte = MONITOR_SEKTOR + sektor
            if zeile.text(spalte) in ("", "-"):
                continue
            if zeile.foreground(spalte).color().name() == FARBE_BESTER_SEKTOR:
                lila_je_sektor[sektor] = lila_je_sektor.get(sektor, 0) + 1
    assert lila_je_sektor, "Kein einziger Sektor ist lila"
    for sektor, anzahl in lila_je_sektor.items():
        assert anzahl == 1, f"Sektor {sektor + 1}: {anzahl} lila statt einem"


def test_die_bestmoegliche_runde_ist_nie_langsamer_als_die_gefahrene(
    qtbot, konfig: kf.Konfiguration
) -> None:
    """Punkt 82: Aus den besten Sektoren kann nur eine bessere Runde werden."""
    from rennmanager.ui.rennseite import IDEAL_BESTE, IDEAL_MOEGLICH

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = kurzes_rennen(fenster)
    seite._zum_ende()
    seite._halte_an()

    schlage_blatt_auf(seite, "ideal")
    geprueft = 0
    for i in range(seite.ideal.topLevelItemCount()):
        zeile = seite.ideal.topLevelItem(i)
        beste, moeglich = zeile.text(IDEAL_BESTE), zeile.text(IDEAL_MOEGLICH)
        if "-" in (beste, moeglich) or not beste or not moeglich:
            continue
        # Die Texte sind m:ss.mmm - so verglichen stimmt die Reihenfolge.
        assert moeglich <= beste, f"{zeile.text(0)}: {moeglich} > {beste}"
        geprueft += 1
    assert geprueft, "Kein Auto mit beiden Zeiten - der Test prueft nichts"
