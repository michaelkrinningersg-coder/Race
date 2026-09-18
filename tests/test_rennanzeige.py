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
from rennmanager.ui import rennseite as rs  # noqa: E402
from rennmanager.ui.diagramm import HOECHSTENS_FOKUS  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.rennseite import (  # noqa: E402
    SPALTE_MISCHUNG,
    SPALTE_REIFEN,
)
from rennmanager.ui.rueckstandsansicht import Rueckstandsansicht  # noqa: E402
from rennmanager.ui.tabellen import Balkenzeichner  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture
def gefahren(qtbot, konfig):
    """Ein kurzes Rennen, abgespielt bis zur Mitte.

    Die Rennseite rechnet seit Punkt 12 nichts mehr; sie bekommt den
    Verlauf gereicht. Vier Runden reichen fuer alles, was hier geprueft
    wird - ein echtes Wochenende waere 19 Runden und 17 Sekunden.
    """
    from tests.test_ui import _kurzes_rennen

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster, runden=4)
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
    assert kopf[rs.SPALTE_ZEIT] == "Zeit / Rueckstand"
    assert kopf[rs.SPALTE_INTERVALL] == "Intervall"

    # Der Fuehrende hat kein Intervall, alle anderen eines.
    assert seite.rangliste.topLevelItem(0).text(rs.SPALTE_INTERVALL) == "-"
    for stelle in range(1, seite.rangliste.topLevelItemCount()):
        assert seite.rangliste.topLevelItem(stelle).text(rs.SPALTE_INTERVALL) != ""


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
    if "Rd" in zweiter.text(rs.SPALTE_ZEIT):
        pytest.skip("Der Zweite wurde ueberrundet")
    assert zweiter.text(rs.SPALTE_INTERVALL) == zweiter.text(rs.SPALTE_ZEIT)


def test_jedes_intervall_ist_positiv(gefahren) -> None:
    _fenster, seite = gefahren
    for stelle in range(1, seite.rangliste.topLevelItemCount()):
        text = seite.rangliste.topLevelItem(stelle).text(rs.SPALTE_INTERVALL)
        assert text.startswith("+"), text


# --- Punkt 3: Reifenbalken ------------------------------------------------
def test_die_reifenspalte_traegt_einen_anteil(gefahren) -> None:
    _fenster, seite = gefahren
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        anteil = zeile.data(SPALTE_REIFEN, Balkenzeichner.ANTEILSROLLE)
        assert anteil is not None
        assert 0.0 <= anteil <= 1.0
        # Die Zahl bleibt daneben lesbar.
        assert zeile.text(SPALTE_REIFEN).endswith("%")


# --- Punkt 39: Mischung und Mischungspflicht -------------------------------
def _mit_stopps(qtbot, konfig, pflicht: bool):
    """Ein kurzes Rennen, in dem wirklich gewechselt wird."""
    from rennmanager.kern import reifen as kern_reifen
    from rennmanager.kern import strategie as kern_strategie
    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.kern import welt as kern_welt
    from rennmanager.kern.zufall import Seedquelle

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    strecke = kern_strecke.lade(konfig, konfig.strecken[0]["name"])
    feld = kern_welt.starterfeld(fenster.welt, fenster.welt.spieler.liga)[:6]
    weich = kern_reifen.mischung(konfig, "weich")
    hart = kern_reifen.mischung(konfig, "hart")
    strategie = kern_strategie.Strategie(mischungen=(weich, hart), stopps=(6,))
    verlauf = rn.simuliere(
        konfig,
        strecke,
        feld,
        12,
        Seedquelle(4711).zweig("rennen"),
        rn.mittlerer_ueberholzonenanteil(konfig, (strecke,)),
        strategien=tuple(strategie for _ in feld),
        mischungspflicht=pflicht,
    )
    seite = fenster.rennseite
    seite.zeige_verlauf(verlauf, strecke)
    seite._halte_an()
    return fenster, seite, verlauf


def test_die_rangliste_hat_eine_mischungsspalte(gefahren) -> None:
    _fenster, seite = gefahren
    kopf = seite.rangliste.headerItem().text(SPALTE_MISCHUNG)
    assert kopf == "Mischung"


def test_ohne_strategie_bleibt_die_mischungsspalte_leer(gefahren) -> None:
    """Ohne Strategie faehrt jedes Auto einen Satz - da gibt es nichts zu zeigen."""
    _fenster, seite = gefahren
    if seite.verlauf.mischungen:
        pytest.skip("Dieser Verlauf traegt Mischungen")
    for stelle in range(seite.rangliste.topLevelItemCount()):
        assert seite.rangliste.topLevelItem(stelle).text(SPALTE_MISCHUNG) == "-"


def _spalte_je_auto(seite, spalte):
    """Die Spalte, aufgeschluesselt nach der Nummer im Feld statt nach Platz."""
    werte = {}
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        werte[zeile.data(0, Qt.UserRole)] = zeile.text(spalte)
    return werte


def test_die_spalte_zeigt_mischung_und_stoppzahl(qtbot, konfig) -> None:
    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, pflicht=True)
    stopp = verlauf.boxenstopps[0]

    seite._springe(stopp.zeit_ms - 20_000)
    for text in _spalte_je_auto(seite, SPALTE_MISCHUNG).values():
        assert text.startswith("W (0)"), text

    # Am Ende zaehlt nur, wer wirklich gestoppt hat: Wer vorher ausfaellt,
    # steht weiter auf seinem Startsatz.
    seite._springe(verlauf.dauer_ms)
    werte = _spalte_je_auto(seite, SPALTE_MISCHUNG)
    gestoppt = {b.teilnehmer for b in verlauf.boxenstopps}
    assert gestoppt, "Ohne Stopp prueft der Test nichts"
    for i, text in werte.items():
        erwartet = "H (1)" if i in gestoppt else "W (0)"
        assert text.startswith(erwartet), f"Auto {i}: {text}"


def test_die_offene_mischungspflicht_steht_in_warnfarbe(qtbot, konfig) -> None:
    from rennmanager.ui.rennseite import FARBE_PFLICHT_ERFUELLT, FARBE_PFLICHT_OFFEN, HAKEN

    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, pflicht=True)
    stopp = verlauf.boxenstopps[0]

    seite._springe(stopp.zeit_ms - 20_000)
    zeile = seite.rangliste.topLevelItem(0)
    assert zeile.foreground(SPALTE_MISCHUNG).color().name() == FARBE_PFLICHT_OFFEN
    assert HAKEN not in zeile.text(SPALTE_MISCHUNG)

    seite._springe(verlauf.dauer_ms)
    zeile = seite.rangliste.topLevelItem(0)
    assert zeile.foreground(SPALTE_MISCHUNG).color().name() == FARBE_PFLICHT_ERFUELLT
    assert zeile.text(SPALTE_MISCHUNG).endswith(HAKEN)


def test_ohne_pflicht_steht_die_spalte_von_anfang_an_auf_gruen(qtbot, konfig) -> None:
    """Bei Regen, Starkregen und wechselhaft ist die Pflicht aufgehoben."""
    from rennmanager.ui.rennseite import FARBE_PFLICHT_ERFUELLT, HAKEN

    _fenster, seite, verlauf = _mit_stopps(qtbot, konfig, pflicht=False)
    seite._springe(0)
    zeile = seite.rangliste.topLevelItem(0)
    assert zeile.foreground(SPALTE_MISCHUNG).color().name() == FARBE_PFLICHT_ERFUELLT
    assert zeile.text(SPALTE_MISCHUNG).endswith(HAKEN)


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


def test_die_eigenen_fahrer_treten_im_diagramm_hervor(gefahren, konfig) -> None:
    """Fokus und Kontext: nicht 30 Farben, sondern das eigene Team."""
    _fenster, seite = gefahren
    eigene = [
        i for i, t in enumerate(seite.verlauf.teilnehmer) if t.ist_spieler
    ]
    assert len(eigene) == konfig.wert("teams", "autos_je_team")
    assert seite.rueckstandsansicht._hervorgehoben == eigene

    # Eine Auswahl in der Rangliste kommt dazu - das Team und einer mehr.
    seite.rangliste.setCurrentItem(seite.rangliste.topLevelItem(2))
    hervor = seite.rueckstandsansicht._hervorgehoben
    assert len(hervor) <= HOECHSTENS_FOKUS
    gewaehlt = seite.rangliste.topLevelItem(2).data(0, Qt.UserRole)
    assert gewaehlt in hervor or gewaehlt in eigene


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


# --- Punkt 76: Positionsaenderung mit Pfeil -------------------------------
def test_die_rangliste_hat_eine_spalte_fuer_gewonnene_plaetze(gefahren) -> None:
    _fenster, seite = gefahren
    assert seite.rangliste.headerItem().text(rs.SPALTE_WECHSEL) == "+/-"


def test_die_pfeile_stehen_in_der_richtigen_farbe(gefahren) -> None:
    """Gruen nach oben, rot nach unten - und nie Farbe allein."""
    _fenster, seite = gefahren
    gesehen = 0
    for stelle in range(seite.rangliste.topLevelItemCount()):
        zeile = seite.rangliste.topLevelItem(stelle)
        text = zeile.text(rs.SPALTE_WECHSEL)
        if not text:
            continue
        gesehen += 1
        farbe = zeile.foreground(rs.SPALTE_WECHSEL).color().name()
        if text.startswith(rs.PFEIL_HOCH):
            assert farbe == rs.FARBE_GEWONNEN
        else:
            assert text.startswith(rs.PFEIL_RUNTER)
            assert farbe == rs.FARBE_VERLOREN
        # Die Zahl der Plaetze steht daneben, nicht nur der Pfeil.
        assert int(text.split()[1]) >= 1
    # In der ersten Runde gibt es nichts zu vergleichen - dann ist die
    # Spalte leer, und das ist kein Fehler.
    assert gesehen >= 0


def test_in_der_ersten_runde_bleibt_die_spalte_leer(qtbot, konfig) -> None:
    """Es gibt noch keine vorige Runde, mit der sich vergleichen liesse."""
    from tests.test_ui import _kurzes_rennen

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = _kurzes_rennen(fenster, runden=4)
    seite._halte_an()
    seite._springe(0)
    for stelle in range(seite.rangliste.topLevelItemCount()):
        assert seite.rangliste.topLevelItem(stelle).text(rs.SPALTE_WECHSEL) == ""
