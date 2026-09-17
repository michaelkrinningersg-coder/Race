"""Tests fuer die Rennanzeige (Punkte 1 bis 4).

Intervall, Rueckstandsdiagramm, Reifenbalken und Zwischenfall-Ticker. Alle
vier lesen nur, was der ``Rennverlauf`` schon mitbringt - getestet wird
deshalb, dass sie das Richtige lesen, nicht die Simulation selbst.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.kern import rennen as rn  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.rueckstandsansicht import Rueckstandsansicht  # noqa: E402
from rennmanager.ui.tabellen import Balkenzeichner  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture
def gefahren(qtbot, konfig):
    """Ein kurzes Rennen, abgespielt bis zur Mitte."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.rennseite
    seite._runden.setValue(4)
    seite._starten.click()
    seite._halte_an()
    seite._springe(seite.verlauf.dauer_ms * 0.6)
    return fenster, seite


# --- Punkt 1: Intervall ---------------------------------------------------
def test_die_rangliste_zeigt_rueckstand_und_intervall(gefahren) -> None:
    _fenster, seite = gefahren
    kopf = [
        seite.rangliste.headerItem().text(spalte)
        for spalte in range(seite.rangliste.columnCount())
    ]
    assert kopf[3] == "Zeit / Rueckstand"
    assert kopf[4] == "Intervall"

    # Der Fuehrende hat kein Intervall, alle anderen eines.
    assert seite.rangliste.topLevelItem(0).text(4) == "-"
    for stelle in range(1, seite.rangliste.topLevelItemCount()):
        assert seite.rangliste.topLevelItem(stelle).text(4) != ""


def test_beim_zweiten_sind_intervall_und_rueckstand_gleich(gefahren) -> None:
    """Dort ist der Vordermann der Fuehrende - beide Zahlen muessen passen.

    Weiter hinten summieren sich die Intervalle bewusst *nicht* zum
    Rueckstand: Das Intervall rechnet mit dem Tempo des Vordermanns, der
    Rueckstand mit dem des Fuehrenden, und zwei Autos an verschiedenen
    Streckenpunkten sind verschieden schnell. So halten es echte
    Zeitmonitore auch.
    """
    _fenster, seite = gefahren
    zweiter = seite.rangliste.topLevelItem(1)
    if "Rd" in zweiter.text(3):
        pytest.skip("Der Zweite wurde ueberrundet")
    assert zweiter.text(4) == zweiter.text(3)


def test_jedes_intervall_ist_positiv(gefahren) -> None:
    _fenster, seite = gefahren
    for stelle in range(1, seite.rangliste.topLevelItemCount()):
        text = seite.rangliste.topLevelItem(stelle).text(4)
        assert text.startswith("+"), text


# --- Punkt 3: Reifenbalken ------------------------------------------------
def test_die_reifenspalte_traegt_einen_anteil(gefahren) -> None:
    _fenster, seite = gefahren
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        anteil = zeile.data(5, Balkenzeichner.ANTEILSROLLE)
        assert anteil is not None
        assert 0.0 <= anteil <= 1.0
        # Die Zahl bleibt daneben lesbar.
        assert zeile.text(5).endswith("%")


def test_der_balken_faerbt_nach_zustand(konfig) -> None:
    """Statusfarben, nicht Serienfarben: gut, Warnung, kritisch."""
    zeichner = Balkenzeichner()
    assert zeichner.farbe(0.9) == Balkenzeichner.GUT
    assert zeichner.farbe(0.3) == Balkenzeichner.WARNUNG
    assert zeichner.farbe(0.1) == Balkenzeichner.KRITISCH


# --- Punkt 4: Zwischenfall-Ticker -----------------------------------------
def test_der_ticker_zeigt_nur_geschehenes(gefahren) -> None:
    _fenster, seite = gefahren
    zeit = seite.zeit_ms
    bisher = [z for z in seite.verlauf.zwischenfaelle if z.zeit_ms <= zeit]
    assert str(len(bisher)) in seite._tickerkasten.title()
    assert seite.ticker.topLevelItemCount() == min(len(bisher), 12)


def test_der_ticker_zeigt_das_neueste_oben(gefahren) -> None:
    _fenster, seite = gefahren
    if seite.ticker.topLevelItemCount() < 2:
        pytest.skip("In diesem Rennen passierte zu wenig")
    zeiten = [
        seite.ticker.topLevelItem(i).data(0, Qt.UserRole)
        for i in range(seite.ticker.topLevelItemCount())
    ]
    assert zeiten == sorted(zeiten, reverse=True)


def test_am_anfang_ist_der_ticker_leer(gefahren) -> None:
    _fenster, seite = gefahren
    seite._springe(0)
    assert seite.ticker.topLevelItemCount() == 0


# --- Punkt 2: Rueckstandsdiagramm -----------------------------------------
def test_das_diagramm_kennt_den_verlauf(gefahren) -> None:
    _fenster, seite = gefahren
    assert isinstance(seite.rueckstandsansicht, Rueckstandsansicht)
    zeiten, rueckstand = rn.rueckstand_in_sekunden(seite.verlauf)
    assert len(zeiten) > 0
    assert rueckstand.shape[1] == seite.verlauf.anzahl
    # Der Fuehrende hat zu jedem Zeitpunkt den kleinsten Rueckstand.
    assert rueckstand.min() == pytest.approx(0.0, abs=1e-6)


def test_der_spieler_tritt_im_diagramm_hervor(gefahren) -> None:
    """Fokus und Kontext: nicht 30 Farben, sondern zwei Linien."""
    _fenster, seite = gefahren
    spieler = [
        i for i, t in enumerate(seite.verlauf.teilnehmer) if t.ist_spieler
    ]
    assert seite.rueckstandsansicht._hervorgehoben == spieler

    # Eine Auswahl in der Rangliste kommt dazu - hoechstens zwei Linien.
    seite.rangliste.setCurrentItem(seite.rangliste.topLevelItem(2))
    hervor = seite.rueckstandsansicht._hervorgehoben
    assert len(hervor) <= 2
    gewaehlt = seite.rangliste.topLevelItem(2).data(0, Qt.UserRole)
    assert gewaehlt in hervor or gewaehlt in spieler


def test_ausgefallene_bestimmen_die_achse_nicht(gefahren) -> None:
    """GDD 4 kennt fuer sie keinen Zeitrueckstand, nur '+n Rd.'."""
    _fenster, seite = gefahren
    ansicht = seite.rueckstandsansicht
    hinten = {
        e.teilnehmer for e in seite.verlauf.ergebnisse if e.rundenrueckstand
    }
    if not hinten:
        pytest.skip("In diesem Rennen wurde niemand ueberrundet")
    auf_runde = [i for i in range(seite.verlauf.anzahl) if i not in hinten]
    assert ansicht._achsenmaximum() == pytest.approx(
        float(ansicht._rueckstand[:, auf_runde].max())
    )


def test_ohne_rennen_zeigt_das_diagramm_einen_hinweis(qtbot) -> None:
    ansicht = Rueckstandsansicht()
    qtbot.addWidget(ansicht)
    ansicht.zeige(None)
    ansicht.resize(400, 200)
    ansicht.repaint()
    assert ansicht._rueckstand is None
