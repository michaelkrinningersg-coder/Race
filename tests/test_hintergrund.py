"""Rechnen im Hintergrund (E10).

Ein Rennen kostet gemessen elf Sekunden. Lief es im Oberflaechen-Thread,
reagierte das Fenster so lange auf nichts - und ein Fenster, das nicht
reagiert, sieht abgestuerzt aus. Hier wird geprueft, dass die Rechnung
wirklich nebenher laeuft, dass sie meldet, wie weit sie ist, und dass ein
Fehler darin nicht still verschwindet.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.hintergrund import Rechenlauf  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    from tests.conftest import verkleinert

    return verkleinert()


@pytest.fixture
def laeufe():
    """Haelt die Threads fest und wartet am Ende auf sie.

    Ein ``QThread``, der eingesammelt wird, waehrend er noch laeuft,
    bringt den ganzen Prozess um: "QThread: Destroyed while thread is
    still running". Das Signal ``fertig`` faellt naemlich noch **in**
    ``run()``, also bevor der Faden wirklich zu Ende ist.
    """
    gestartet: list[Rechenlauf] = []
    yield gestartet
    for lauf in gestartet:
        lauf.wait(5000)


# -- Der Arbeitsfaden selbst ------------------------------------------------
def test_ein_lauf_liefert_sein_ergebnis(qtbot, laeufe) -> None:
    lauf = Rechenlauf(lambda melde: 6 * 7)
    laeufe.append(lauf)
    with qtbot.waitSignal(lauf.fertig, timeout=5000) as gefangen:
        lauf.start()
    assert gefangen.args == [42]
    lauf.wait(5000)
    assert lauf.ergebnis == 42


def test_ein_lauf_meldet_seinen_fortschritt(qtbot, laeufe) -> None:
    def arbeit(melde):
        for runde in range(1, 4):
            melde(runde, 3)
        return "fertig"

    lauf = Rechenlauf(arbeit)
    laeufe.append(lauf)
    gemeldet: list[tuple[int, int]] = []
    lauf.fortschritt.connect(lambda a, b: gemeldet.append((a, b)))
    with qtbot.waitSignal(lauf.fertig, timeout=5000):
        lauf.start()
    qtbot.waitUntil(lambda: len(gemeldet) == 3, timeout=5000)
    assert gemeldet == [(1, 3), (2, 3), (3, 3)]


def test_ein_fehler_im_faden_kommt_an(qtbot, laeufe) -> None:
    """Sonst stuende die Oberflaeche ewig auf "rechnet"."""

    def arbeit(_melde):
        raise ValueError("Boxengasse gesperrt")

    lauf = Rechenlauf(arbeit)
    laeufe.append(lauf)
    with qtbot.waitSignal(lauf.fehlgeschlagen, timeout=5000) as gefangen:
        lauf.start()
    assert "Boxengasse gesperrt" in gefangen.args[0]
    assert "ValueError" in gefangen.args[1]


# -- Das Rennwochenende -----------------------------------------------------
def test_das_rennen_laeuft_im_hintergrund(qtbot, konfig) -> None:
    """Nach dem Klick rechnet es noch - der Schritt steht still."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.wochenendeseite
    seite.knopf_weiter.click()          # Qualifying, laeuft sofort durch
    seite.warte_auf_rechnung()

    seite.knopf_weiter.click()          # Rennen, geht in den Hintergrund
    assert seite._rechnung is not None, "Das Rennen rechnet nicht nebenher"
    assert not seite.knopf_weiter.isEnabled()
    assert seite._rechenbalken.isVisibleTo(seite)

    seite.warte_auf_rechnung()
    assert seite._rechnung is None
    assert seite.knopf_weiter.isEnabled()
    assert fenster.rennseite.verlauf is not None


def test_ein_zweiter_klick_stoert_die_rechnung_nicht(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.wochenendeseite
    seite.knopf_weiter.click()
    seite.warte_auf_rechnung()

    seite.knopf_weiter.click()
    laufend = seite._rechnung
    seite._naechster_schritt()          # am Knopf vorbei, wie ein Tastendruck
    assert seite._rechnung is laufend, "Es wurde ein zweites Rennen gestartet"
    seite.warte_auf_rechnung()
    assert fenster.rennseite.verlauf is not None


def test_der_balken_verschwindet_wieder(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.wochenendeseite
    assert not seite._rechenbalken.isVisibleTo(seite)
    seite.knopf_weiter.click()
    seite.warte_auf_rechnung()
    seite.knopf_weiter.click()
    seite.warte_auf_rechnung()
    assert not seite._rechenbalken.isVisibleTo(seite)
