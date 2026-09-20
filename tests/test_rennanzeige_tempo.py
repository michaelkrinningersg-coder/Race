"""Die Anzeige darf nicht wieder langsam werden (D1, D2, D9).

Diese Tests pruefen keine Inhalte, sondern **Arbeitsaufwand**. Gemessen
kostete ein Bild der Rennanzeige 14,18 ms, davon 99 Prozent die Tabellen;
drei Eingriffe brachten es auf 3,79 ms. Ohne Wachhunde waere das in drei
Monaten wieder weg, und niemand wuesste, wann es passiert ist.

Gezaehlt wird deshalb, was die Anzeige je Bild **tut**: wie oft sie Qt
Spalten ausmessen laesst und wie oft sie eine Tabelle neu fuellt. Eine
Zeitmessung stuende hier falsch - sie haengt an der Maschine und wuerde
auf einem langsamen Rechner grundlos rot.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QTreeWidget  # noqa: E402

from rennmanager.ui import rennseite as rs  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from tests.oberflaeche import kurzes_rennen, schlage_blatt_auf  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    from tests.conftest import verkleinert

    return verkleinert()


@pytest.fixture
def seite(qtbot, konfig):
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    gezeigt = kurzes_rennen(fenster)
    gezeigt._halte_an()
    return gezeigt


class _Zaehler:
    """Zaehlt Aufrufe einer Methode, ohne sie abzuklemmen."""

    def __init__(self, monkeypatch, ziel, name: str) -> None:
        self.anzahl = 0
        echt = getattr(ziel, name)

        def gezaehlt(*argumente, **schluessel):
            self.anzahl += 1
            return echt(*argumente, **schluessel)

        monkeypatch.setattr(ziel, name, gezaehlt)


# -- D1: Spalten werden nicht je Bild ausgemessen ---------------------------
def test_kein_bild_misst_spalten_aus(seite, monkeypatch) -> None:
    """D1: ``resizeColumnToContents`` war 62 Prozent eines Bildes.

    Qt misst dafuer jede Zelle der Spalte. Gebraucht wird es nicht - die
    Breiten stehen seit ``zeige_verlauf`` fest.
    """
    zaehler = _Zaehler(monkeypatch, QTreeWidget, "resizeColumnToContents")
    for anteil in (0.1, 0.3, 0.5, 0.7, 0.9):
        seite._springe(seite.verlauf.dauer_ms * anteil)
    assert zaehler.anzahl == 0


def test_die_spalten_haben_eine_breite(seite) -> None:
    """Ohne das Ausmessen muessen sie trotzdem lesbar sein."""
    for tabelle in (seite.rangliste, seite.monitor, seite.ideal):
        for spalte in range(tabelle.columnCount()):
            assert tabelle.columnWidth(spalte) > 0, f"Spalte {spalte} ist unsichtbar"


def test_die_spaltenbreite_zittert_nicht(seite) -> None:
    """Sie sprangen fuenfmal je Sekunde, sobald ein Wert laenger wurde."""
    seite._springe(0)
    vorher = [seite.rangliste.columnWidth(s) for s in range(seite.rangliste.columnCount())]
    seite._springe(seite.verlauf.dauer_ms)
    assert [seite.rangliste.columnWidth(s) for s in range(seite.rangliste.columnCount())] == vorher


# -- D2: nur das sichtbare Blatt --------------------------------------------
def test_nur_das_sichtbare_blatt_wird_gefuellt(seite, monkeypatch) -> None:
    """D2: Vier der fuenf Tabellen sieht man nie gleichzeitig."""
    zaehler = {
        name: _Zaehler(monkeypatch, rs.Rennseite, f"_fuelle_{name}")
        for name in ("rangliste", "monitor", "ideal", "meisterschaft", "ticker")
    }
    seite.blaetter_rechts.setCurrentIndex(rs.BLATT_MONITOR)
    for anteil in (0.2, 0.4, 0.6, 0.8):
        seite._springe(seite.verlauf.dauer_ms * anteil)

    assert zaehler["rangliste"].anzahl == 4, "Die Rangliste steht immer da"
    assert zaehler["monitor"].anzahl == 4, "Das offene Blatt muss mitlaufen"
    for verdeckt in ("ideal", "meisterschaft", "ticker"):
        assert zaehler[verdeckt].anzahl == 0, f"{verdeckt} ist verdeckt und wurde gefuellt"


def test_ein_anderes_blatt_laeuft_dann_mit(seite, monkeypatch) -> None:
    """Und umgekehrt: Wer aufschlaegt, wird gefuellt, der Rest nicht."""
    zaehler = {
        name: _Zaehler(monkeypatch, rs.Rennseite, f"_fuelle_{name}")
        for name in ("monitor", "ideal")
    }
    seite.blaetter_rechts.setCurrentIndex(rs.BLATT_IDEAL)
    for anteil in (0.3, 0.6):
        seite._springe(seite.verlauf.dauer_ms * anteil)
    assert zaehler["ideal"].anzahl >= 2
    assert zaehler["monitor"].anzahl == 0


def test_ein_frisch_aufgeschlagenes_blatt_steht_sofort_da(seite) -> None:
    """Sonst bliebe es leer, bis der naechste Takt faellig ist."""
    seite._springe(seite.verlauf.dauer_ms)
    schlage_blatt_auf(seite, "ideal")
    assert seite.ideal.topLevelItemCount() > 0


# -- D9: der Takt deckelt auch in Echtzeit ----------------------------------
def test_der_takt_deckelt_auch_in_echtzeit(seite, monkeypatch) -> None:
    """D9: In Rennzeit allein war der Takt ab Stufe 50x wirkungslos.

    Zwei Takte kurz hintereinander springen im Zeitraffer weit in der
    Rennzeit - die Schwelle greift dort nie. Der Echtzeitdeckel schon:
    Was innerhalb desselben Taktfensters kommt, wird nicht noch einmal
    gefuellt.
    """
    zaehler = _Zaehler(monkeypatch, rs.Rennseite, "_fuelle_rangliste")
    seite._erzwinge_fuellung()
    seite._zeichne()
    assert zaehler.anzahl == 1

    # Ein grosser Sprung in der Rennzeit, aber ohne Echtzeit dazwischen.
    for schritt in range(1, 6):
        seite._zeit_ms = seite.verlauf.dauer_ms * schritt / 6
        seite._zeichne()
    assert zaehler.anzahl == 1, "Der Echtzeitdeckel hat nicht gehalten"


def test_ein_sprung_umgeht_beide_deckel(seite, monkeypatch) -> None:
    """Was der Spieler anstoesst, soll sofort zu sehen sein."""
    zaehler = _Zaehler(monkeypatch, rs.Rennseite, "_fuelle_rangliste")
    for anteil in (0.1, 0.2, 0.3, 0.4):
        seite._springe(seite.verlauf.dauer_ms * anteil)
    assert zaehler.anzahl == 4
