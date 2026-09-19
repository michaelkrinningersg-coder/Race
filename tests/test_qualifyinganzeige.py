"""Tests fuer das abspielbare Qualifying (Punkt 85).

Die Seite rechnet nichts - getestet wird, dass sie zum richtigen
Zeitpunkt das Richtige zeigt: Anfangsstellung, mitlaufende Zeit,
Live-Einsortierung, die drei Splitfarben und die Aufstellung, die erst am
Ende steht.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.kern import qualifying as ql  # noqa: E402
from rennmanager.kern import rennen as rn  # noqa: E402
from rennmanager.kern import strecke as st  # noqa: E402
from rennmanager.kern.zufall import Seedquelle  # noqa: E402
from rennmanager.ui import qualifyingseite as qs  # noqa: E402

LIGA = 10


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def session(konfig) -> ql.Qualifying:
    strecke = st.lade(konfig, "Catalunya")
    feld = rn.starterfeld(konfig, LIGA)
    return ql.fahre(konfig, strecke, feld, Seedquelle(4711))


@pytest.fixture
def seite(qtbot, konfig, session) -> qs.Qualifyingseite:
    """Jeder Test bekommt eine frische Seite mit derselben Session."""
    widget = qs.Qualifyingseite(konfig)
    qtbot.addWidget(widget)
    widget.zeige_session(session)
    return widget


def _zeilen(seite) -> list[list[str]]:
    liste = seite._rangliste
    return [
        [zeile.text(spalte) for spalte in range(liste.columnCount())]
        for zeile in (liste.topLevelItem(i) for i in range(liste.topLevelItemCount()))
    ]



def _spalte_lage(session) -> int:
    """Die Lage steht hinter den Sektoren - deren Zahl kommt aus der Strecke."""
    return qs.SPALTE_SEKTOR_AB + len(session.fahrten[0].sektoren_ms)


def _zeile_von(seite, session, fahrt) -> list[str]:
    kuerzel = session.teilnehmer[fahrt.teilnehmer].kuerzel
    return next(z for z in _zeilen(seite) if z[qs.SPALTE_AUTO] == kuerzel)


def _farben(seite, session, fahrt) -> list[str]:
    """Die Farbe je Sektorspalte als Hex - leer, wo keine gesetzt ist."""
    liste = seite._rangliste
    kuerzel = session.teilnehmer[fahrt.teilnehmer].kuerzel
    zeile = next(
        liste.topLevelItem(i)
        for i in range(liste.topLevelItemCount())
        if liste.topLevelItem(i).text(qs.SPALTE_AUTO) == kuerzel
    )
    werte = []
    for nummer in range(len(fahrt.sektoren_ms)):
        spalte = qs.SPALTE_SEKTOR_AB + nummer
        pinsel = zeile.foreground(spalte)
        # Eine Zelle ohne gesetzte Farbe traegt Qt.NoBrush - deren
        # color() ist Schwarz und waere sonst nicht von einer echten
        # Farbe zu unterscheiden.
        if not zeile.text(spalte) or pinsel.style() == Qt.NoBrush:
            werte.append("")
            continue
        werte.append(pinsel.color().name())
    return werte


# -- Anfangsstellung --------------------------------------------------------
def test_nach_dem_laden_steht_die_session_auf_anfang(seite, session) -> None:
    """Wunsch des Auftraggebers: nach dem Laden auf Anfang, pausiert."""
    assert seite.zeit_ms == 0
    assert not seite.laeuft
    assert seite._abspielen.text() == "Start"


def test_am_anfang_steht_noch_keine_zeit_da(seite, session) -> None:
    zeilen = _zeilen(seite)
    assert len(zeilen) == len(session.fahrten)
    assert all(zeile[qs.SPALTE_ZEIT] == "" for zeile in zeilen)
    assert all(zeile[qs.SPALTE_POS] == "" for zeile in zeilen)


def test_die_zeitrafferstufen_sind_dieselben_wie_im_rennen(seite, konfig) -> None:
    stufen = [seite._raffer.itemData(i) for i in range(seite._raffer.count())]
    assert stufen == list(konfig.wert("zeitraffer", "stufen"))
    assert seite._raffer.currentData() == konfig.wert("zeitraffer", "start_stufe")


# -- Wiedergabe -------------------------------------------------------------
def test_start_und_pause_schalten_die_uhr(seite) -> None:
    seite._abspielen.click()
    assert seite.laeuft and seite._abspielen.text() == "Pause"
    seite._abspielen.click()
    assert not seite.laeuft and seite._abspielen.text() == "Start"


def test_ein_takt_bringt_die_sessionzeit_voran(seite, konfig) -> None:
    seite._takt()
    assert seite.zeit_ms == konfig.wert("zeitraffer", "takt_ms") * seite._raffer.currentData()


def test_sofortergebnis_springt_ans_ende_und_haelt_an(seite, session) -> None:
    seite._abspielen.click()
    seite._sofort.click()
    assert seite.zeit_ms == session.dauer_ms
    assert not seite.laeuft


def test_anfang_setzt_zurueck(seite, session) -> None:
    seite._sofort.click()
    seite._zurueck.click()
    assert seite.zeit_ms == 0
    assert all(zeile[qs.SPALTE_ZEIT] == "" for zeile in _zeilen(seite))


# -- Live-Einsortierung -----------------------------------------------------
def test_die_zeit_laeuft_auf_der_schnellen_runde_mit(seite, session) -> None:
    """Sobald einer auf seiner Runde ist, sieht man die Zeit laufen.

    Zwei Zeitpunkte auf derselben Runde muessen verschiedene Zeiten
    zeigen - sonst stuende dort eine Zahl, die sich nicht bewegt.
    """
    fahrt = session.fahrten[0]
    spalte = _spalte_lage(session)

    seite._springe(fahrt.runde_ab_ms + 30_000)
    frueh = _zeile_von(seite, session, fahrt)
    seite._springe(fahrt.runde_ab_ms + 60_000)
    spaet = _zeile_von(seite, session, fahrt)

    assert frueh[spalte] == ql.Lage.SCHNELLE_RUNDE.bezeichnung
    assert frueh[qs.SPALTE_ZEIT] and spaet[qs.SPALTE_ZEIT]
    assert frueh[qs.SPALTE_ZEIT] != spaet[qs.SPALTE_ZEIT]


def test_vor_der_ausfahrt_steht_das_auto_in_der_box(seite, session) -> None:
    letzter = session.fahrten[-1]
    seite._springe(0)
    zeile = _zeile_von(seite, session, letzter)
    assert zeile[_spalte_lage(session)] == ql.Lage.WARTET.bezeichnung
    assert zeile[qs.SPALTE_ZEIT] == ""


def test_wer_faehrt_hat_noch_keine_position(seite, session) -> None:
    fahrt = session.fahrten[0]
    seite._springe(fahrt.runde_ab_ms + 30_000)
    laufend = [z for z in _zeilen(seite) if z[qs.SPALTE_ZEIT] and z[qs.SPALTE_POS] == ""]
    assert laufend, "Einer muss unterwegs sein"
    assert all(z[qs.SPALTE_RUECKSTAND] == "" for z in laufend)


def test_wer_durch_ist_bekommt_seine_position(seite, session) -> None:
    dritter = session.fahrten[2]
    seite._springe(dritter.ziel_ms)
    zeilen = _zeilen(seite)
    mit_position = [z for z in zeilen if z[qs.SPALTE_POS]]
    assert [z[qs.SPALTE_POS] for z in mit_position] == ["1", "2", "3"]


def test_am_ende_steht_das_ganze_feld_mit_position(seite, session) -> None:
    seite._sofort.click()
    zeilen = _zeilen(seite)
    assert [z[qs.SPALTE_POS] for z in zeilen] == [
        str(platz) for platz in range(1, len(session.fahrten) + 1)
    ]
    assert zeilen[0][qs.SPALTE_RUECKSTAND] == ""


# -- Aufstellung ------------------------------------------------------------
def test_die_aufstellung_bleibt_bis_zum_ende_leer(seite, session) -> None:
    """Entscheidung des Auftraggebers: erst am Ende fuellen."""
    assert seite._aufstellung.topLevelItemCount() == 0
    seite._springe(session.fahrten[-2].ziel_ms)
    assert seite._aufstellung.topLevelItemCount() == 0


def test_die_aufstellung_steht_nach_der_letzten_runde(seite, session) -> None:
    seite._sofort.click()
    assert seite._aufstellung.topLevelItemCount() == len(session.fahrten)
    assert seite._aufstellungskasten.title() == "Startaufstellung fuers Rennen"


def test_ein_sprung_zurueck_leert_die_aufstellung_wieder(seite) -> None:
    seite._sofort.click()
    seite._zurueck.click()
    assert seite._aufstellung.topLevelItemCount() == 0


# -- Die drei Splitfarben ---------------------------------------------------
def test_ungefahrene_sektoren_bleiben_leer(seite, session) -> None:
    fahrt = session.fahrten[0]
    seite._springe(fahrt.sektorenden_ms[0])
    werte = _farben(seite, session, fahrt)
    assert werte[0] != "" and werte[1] == "" and werte[-1] == ""


def test_der_beste_split_ist_lila(seite, session) -> None:
    seite._sofort.click()
    lila = session.beste_splits_zu(session.dauer_ms)
    for nummer, halter in enumerate(lila):
        fahrt = next(f for f in session.fahrten if f.teilnehmer == halter)
        assert _farben(seite, session, fahrt)[nummer] == qs.FARBE_BESTER.name()


def test_lila_haelt_je_sektor_genau_einer(seite, session) -> None:
    seite._sofort.click()
    for nummer in range(len(session.fahrten[0].sektoren_ms)):
        traeger = [
            f
            for f in session.fahrten
            if _farben(seite, session, f)[nummer] == qs.FARBE_BESTER.name()
        ]
        assert len(traeger) == 1


def test_langsamer_als_der_fuehrende_ist_rot_schneller_gruen(seite, session) -> None:
    seite._sofort.click()
    lila = session.beste_splits_zu(session.dauer_ms)
    geprueft = 0
    for fahrt in session.fahrten:
        werte = _farben(seite, session, fahrt)
        for nummer, farbe in enumerate(werte):
            if lila[nummer] == fahrt.teilnehmer:
                continue
            abstand = session.splitvergleich(fahrt, nummer)
            if abstand is None:
                assert farbe == ""
                continue
            erwartet = qs.FARBE_LANGSAMER if abstand > 0 else qs.FARBE_SCHNELLER
            assert farbe == erwartet.name()
            geprueft += 1
    assert geprueft > 0


def test_neben_dem_split_steht_der_abstand(seite, session) -> None:
    """Die Farbe allein traegt die Aussage nicht - die Zahl steht daneben."""
    seite._sofort.click()
    zweiter = session.fahrten[1]
    zeile = _zeile_von(seite, session, zweiter)
    abstand = session.splitvergleich(zweiter, 0)
    assert abstand is not None
    assert zeile[qs.SPALTE_SEKTOR_AB].count(":") >= 1
    assert zeile[qs.SPALTE_SEKTOR_AB].endswith(
        ("+" if abstand > 0 else "-") + f"{abs(abstand) / 1000:.3f}"
    )


def test_der_erste_fahrer_hat_keine_splitfarbe(seite, session) -> None:
    """Wer als Erster faehrt, misst sich gegen niemanden - ausser lila."""
    seite._springe(session.fahrten[0].ziel_ms)
    erster = session.fahrten[0]
    lila = session.beste_splits_zu(session.fahrten[0].ziel_ms)
    werte = _farben(seite, session, erster)
    for nummer, farbe in enumerate(werte):
        assert lila[nummer] == erster.teilnehmer
        assert farbe == qs.FARBE_BESTER.name()
