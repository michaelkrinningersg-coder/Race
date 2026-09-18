"""Tests fuer Block 2 der Oberflaeche: Kalenderstreifen, Charakter, Punkte.

Die drei Sichten fuegen dem Spiel keine Mechanik hinzu - sie lesen, was
Karriere, Auto und Statistik schon fuehren. Getestet wird deshalb, dass
sie das Richtige lesen und dass sie zeichnen, ohne zu stuerzen.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import charakter as kern_charakter
from rennmanager.kern.auto import Auto

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QFormLayout  # noqa: E402

from rennmanager.ui.diagramm import HOECHSTENS_FOKUS
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.kalenderstreifen import (  # noqa: E402
    FARBEN,
    TAGE_JE_SPALTE,
    Kalenderstreifen,
)
from rennmanager.ui.punkteansicht import Punkteansicht  # noqa: E402


@pytest.fixture(scope="module")
def konfig(kleine_konfiguration) -> kf.Konfiguration:
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``.

    Drei Ligen zu je vier Autos statt zwanzig zu je dreissig. Geprueft
    wird, *ob* die Logik stimmt - dafuer genuegt das kleine Feld, und ein
    Rennwochenende kostet 1,5 statt 54 Sekunden.
    """
    return kleine_konfiguration


def zeichne(widget) -> QImage:
    """Zeichnet ein Widget in ein Bild - der Test auf "stuerzt nicht"."""
    widget.resize(600, 260)
    bild = QImage(widget.size(), QImage.Format_ARGB32)
    widget.render(bild)
    return bild


def alle_werte(konfig: kf.Konfiguration, wert: int) -> dict[str, int]:
    """Jede Faehigkeit auf denselben Wert - der Ausgangspunkt der Profile."""
    return {f.schluessel: wert for f in konfig.faehigkeiten}


# --- Punkt 7: Kalenderstreifen -------------------------------------------
def test_kalenderstreifen_kennt_jeden_tag_der_saison(qtbot, konfig) -> None:
    """Jeder Tag des Karrierejahres bekommt genau einen Zustand."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    streifen = fenster.karriereseite.kalenderstreifen

    tage = len(fenster.karriere.saison.tage)
    gezaehlt = streifen.zaehle()
    assert sum(gezaehlt.values()) == tage
    assert set(gezaehlt) == set(FARBEN)
    # 20 Rennen, 20 Qualifyings - so sieht der Kalender aus GDD 2 aus.
    assert gezaehlt["rennen"] == konfig.wert("kalender", "rennen_je_saison")
    assert gezaehlt["qualifying"] == konfig.wert("kalender", "rennen_je_saison")


def buchbar(karriere, platz: str) -> str:
    """Eine Faehigkeit, die heute einen Platz kostet - fuer den Test.

    Fest verdrahten liesse sich das nicht: Was einen Tag kostet, haengt am
    Stand der Werte (GDD 2), und ein Fehlgriff liefe in einen modalen
    Dialog, den der Test nicht wegklicken kann.
    """
    schluessel = [f.schluessel for f in karriere.konfiguration.faehigkeiten]
    schluessel += list(karriere.konfiguration.zusatzfaehigkeiten)
    for eintrag in schluessel:
        try:
            entwicklung = karriere.vorschau(eintrag)
        except Exception:  # noqa: BLE001 - gesperrt oder unbekannt
            continue
        if entwicklung.braucht_tag and karriere.platz_fuer(eintrag) == platz:
            return eintrag
    raise AssertionError(f"Keine Faehigkeit fuer den Platz {platz}")


def test_kalenderstreifen_zeigt_belegte_tage(qtbot, konfig) -> None:
    """Wer einen Tag verplant, sieht ihn im Band belegt (GDD 2).

    Ein Tag hat zwei Plaetze - einen belegt, ist er halb, beide belegt,
    ist er voll.
    """
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.karriereseite
    streifen = seite.kalenderstreifen
    davor = streifen.zaehle()
    assert davor["halb"] == 0
    assert davor["voll"] == 0

    seite.waehle(buchbar(seite.karriere, "werkstatt"))
    seite._belege_tag()
    assert streifen.zaehle()["halb"] == 1

    seite.waehle(buchbar(seite.karriere, "fahrer"))
    seite._belege_tag()
    danach = streifen.zaehle()
    assert danach["voll"] == 1
    assert danach["halb"] == 0
    assert danach["frei"] == davor["frei"] - 1


def test_kalenderstreifen_ohne_karriere_stuerzt_nicht_ab(qtbot) -> None:
    streifen = Kalenderstreifen()
    qtbot.addWidget(streifen)
    streifen.zeige(None)
    assert streifen.zaehle() == dict.fromkeys(FARBEN, 0)
    zeichne(streifen)


def test_kalenderstreifen_nennt_jeden_tag_unter_dem_zeiger(qtbot, konfig) -> None:
    """Der Mouseover uebersetzt jede Bildstelle zurueck in ihr Datum."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    streifen = fenster.karriereseite.kalenderstreifen
    streifen.resize(1200, 90)

    band = streifen._bandflaeche()
    breite = band.width() / streifen._spalten()
    hoehe = band.height() / TAGE_JE_SPALTE
    for nummer, datum in enumerate(streifen._tage):
        spalte, zeile = divmod(nummer + streifen._versatz, TAGE_JE_SPALTE)
        x = band.left() + (spalte + 0.5) * breite
        y = band.top() + (zeile + 0.5) * hoehe
        assert streifen._tag_an(x, y) == datum

    # Ausserhalb des Bandes und in den leeren Zellen vor dem 1. Januar
    # gibt es keinen Tag.
    assert streifen._tag_an(-5.0, -5.0) is None
    assert streifen._tag_an(band.left() + 1.0, band.top() + 1.0) is None


def test_kalenderstreifen_stellt_die_woche_auf(qtbot, konfig) -> None:
    """Montag oben, Sonntag unten - das Rennen steht immer ganz unten."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    streifen = fenster.karriereseite.kalenderstreifen

    zeile_von = {
        zustand: {
            (nummer + streifen._versatz) % TAGE_JE_SPALTE
            for nummer, datum in enumerate(streifen._tage)
            if streifen._zustaende[datum] == zustand
        }
        for zustand in ("rennen", "qualifying")
    }
    assert zeile_von["rennen"] == {6}
    assert zeile_von["qualifying"] == {5}


# --- Punkt 32: Charakterprofil -------------------------------------------
def test_charakter_nennt_staerke_und_schwaeche(konfig) -> None:
    """Gemessen wird gegen das eigene Mittel, nicht gegen die Skala."""
    werte = alle_werte(konfig, 1000)
    # F1 zieht an einem Bereich der Matrix (GDD 8): hoch gesetzt muss er
    # als Staerke auftauchen, niedrig gesetzt als Schwaeche.
    stark = Auto(name="Stark", kuerzel="STK", werte={**werte, "F1": 6000})
    schwach = Auto(name="Schwach", kuerzel="SCH", werte={**werte, "F1": 10})

    assert kern_charakter.staerken(konfig, stark)
    assert kern_charakter.schwaechen(konfig, schwach)
    satz = kern_charakter.profil(konfig, stark)
    assert satz.endswith(".")
    assert satz[0].isupper()


def test_charakter_bleibt_beim_spieler_ohne_werte_leer(konfig) -> None:
    """GDD 1: Der Spieler beginnt auf lauter Nullen."""
    leer = Auto(name="Spieler", kuerzel="SPL", werte=alle_werte(konfig, 0))
    assert "Noch kein Profil" in kern_charakter.profil(konfig, leer)


def test_charakter_ist_ausgeglichen_wenn_alles_gleich_ist(konfig) -> None:
    gleich = Auto(name="Mittel", kuerzel="MIT", werte=alle_werte(konfig, 50000))
    assert kern_charakter.profil(konfig, gleich).startswith("Ausgeglichen")


def test_steckbrief_zeigt_den_charakter(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.weltseite
    seite.liste.setCurrentItem(seite.liste.topLevelItem(0))

    marke = QFormLayout.ItemRole.LabelRole
    feld = QFormLayout.ItemRole.FieldRole
    beschriftungen = [
        seite._steckbrief.itemAt(i, marke).widget().text()
        for i in range(seite._steckbrief.rowCount())
    ]
    assert "Charakter:" in beschriftungen
    stelle = beschriftungen.index("Charakter:")
    text = seite._steckbrief.itemAt(stelle, feld).widget().text()
    fahrer = fenster.welt.fahrer[seite.liste.topLevelItem(0).data(0, Qt.UserRole)]
    assert text == kern_charakter.profil(konfig, fahrer.auto)


# --- Punkt 9: Punkteverlauf ----------------------------------------------
def test_punkteverlauf_waechst_mit_jedem_rennen(qtbot, konfig) -> None:
    """Der Stand ist aufsummiert und darf nie fallen."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    ansicht = seite.punkteansicht

    assert ansicht.rennen == 0
    seite.lauf.fahre_rennen()
    seite._aktualisiere()
    seite.lauf.fahre_rennen()
    seite._aktualisiere()
    assert ansicht.rennen == 2

    autos = konfig.wert("ligen", "autos_je_liga")
    assert len(ansicht._reihen) == autos
    for _kuerzel, _farbe, stand in ansicht._reihen:
        assert len(stand) == 2
        assert list(stand) == sorted(stand)
    # Der Tabellenerste fuehrt auch im Diagramm.
    assert ansicht.hoechster == int(seite.tabelle.topLevelItem(0).text(3))


def test_punkteverlauf_hebt_spieler_und_auswahl_hervor(qtbot, konfig) -> None:
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    seite.lauf.fahre_rennen()
    seite._aktualisiere()
    ansicht = seite.punkteansicht

    eigene = fenster.welt.spielerfahrer
    seite.liga_auswahl.setCurrentIndex(eigene[0].liga - 1)
    # Ohne Auswahl treten die eigenen Fahrer dieser Liga hervor.
    seite.tabelle.setCurrentItem(None)
    in_der_liga = sum(1 for f in eigene if f.liga == eigene[0].liga)
    assert len(ansicht._hervorgehoben) == in_der_liga

    # Mit Auswahl einer mehr - und nie mehr als das Team plus einen.
    letzte = seite.tabelle.topLevelItem(seite.tabelle.topLevelItemCount() - 1)
    seite.tabelle.setCurrentItem(letzte)
    assert len(ansicht._hervorgehoben) <= HOECHSTENS_FOKUS
    ansicht.hebe_hervor(list(range(HOECHSTENS_FOKUS + 3)))
    assert len(ansicht._hervorgehoben) == HOECHSTENS_FOKUS


def test_punkteverlauf_zeichnet_und_haelt_den_leeren_fall_aus(qtbot) -> None:
    ansicht = Punkteansicht()
    qtbot.addWidget(ansicht)
    # Leer: nur der Hinweis, kein Absturz.
    zeichne(ansicht)

    ansicht.zeige([("AAA", "#1f77b4", (0, 10, 25)), ("BBB", "#c62828", (18, 18, 33))])
    ansicht.hebe_hervor([1])
    assert ansicht.rennen == 3
    assert ansicht.hoechster == 33
    zeichne(ansicht)


def test_punkteverlauf_wird_beim_saisonwechsel_geleert(qtbot, konfig) -> None:
    """GDD 13: Der Endstand wandert in die Historie, der Verlauf faengt neu an."""
    from tests.test_ui import fahre_saison_zu_ende

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = fenster.saisonseite
    seite.lauf.fahre_rennen()
    seite._aktualisiere()
    assert seite.punkteansicht.rennen == 1

    fahre_saison_zu_ende(konfig, seite)
    seite.knopf_naechste_saison.click()
    # Das Fenster baut die Seite erst nach der Rueckkehr in die
    # Ereignisschleife neu auf.
    qtbot.wait(20)
    assert fenster.saisonseite.punkteansicht.rennen == 0


# -- Punkt 55: Gekaufte Upgrades muessen in der Anzeige ankommen -------------
def _spielerfenster(qtbot, konfig):
    from rennmanager.ui.hauptfenster import Hauptfenster

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    return fenster


def test_anzeigewelt_traegt_die_entwickelten_autos(qtbot, konfig) -> None:
    """Ein Kauf hebt den Wert - und die Anzeige zeigt ihn auch.

    Die Welt haelt nur die leere Huelle; entwickelt wird in der Karriere.
    Ohne Zusammenfuehren stuende im Steckbrief ewig der Anfangsstand.
    """
    fenster = _spielerfenster(qtbot, konfig)
    nummer = fenster.welt.spielerfahrer[0].nummer
    schluessel = konfig.faehigkeiten[0].schluessel
    karriere = fenster.karriere
    karriere.waehle_fahrer(nummer)
    karriere.konto = karriere.konto.mit(geld=5_000_000, erfahrung=5_000)

    vorher = fenster.anzeigewelt.fahrer[nummer].auto.werte[schluessel]
    karriere.kaufe(schluessel)
    nachher = fenster.anzeigewelt.fahrer[nummer].auto.werte[schluessel]

    assert nachher > vorher
    assert nachher == karriere.werte_von(nummer)[schluessel]
    # Die Ausgangswelt bleibt, wie sie war - aus ihr startet eine neue
    # Karriere wieder bei null.
    assert fenster.welt.fahrer[nummer].auto.werte[schluessel] == vorher


def test_kauf_trifft_nur_den_gewaehlten_fahrer(qtbot, konfig) -> None:
    """Jedes Auto gehoert seinem Fahrer; der Kollege bleibt unberuehrt."""
    fenster = _spielerfenster(qtbot, konfig)
    eigene = fenster.welt.spielerfahrer
    schluessel = konfig.faehigkeiten[0].schluessel
    karriere = fenster.karriere
    karriere.waehle_fahrer(eigene[0].nummer)
    karriere.konto = karriere.konto.mit(geld=5_000_000, erfahrung=5_000)
    vorher = fenster.anzeigewelt.fahrer[eigene[1].nummer].auto.werte[schluessel]

    karriere.kaufe(schluessel)

    assert fenster.anzeigewelt.fahrer[eigene[1].nummer].auto.werte[schluessel] == vorher


def test_fremde_fahrer_behalten_ihre_werte(qtbot, konfig) -> None:
    """Nur die eigenen Autos kommen aus der Karriere, alle anderen nicht."""
    fenster = _spielerfenster(qtbot, konfig)
    eigene = {f.nummer for f in fenster.welt.spielerfahrer}
    fremd = next(f for f in fenster.welt.fahrer if f.nummer not in eigene)
    assert fenster.anzeigewelt.fahrer[fremd.nummer].auto.werte == fremd.auto.werte


def test_weltseite_zieht_nach_einem_kauf_nach(qtbot, konfig) -> None:
    """Die Weltseite haelt die Welt fest - sie muss sie neu bekommen."""
    fenster = _spielerfenster(qtbot, konfig)
    nummer = fenster.welt.spielerfahrer[0].nummer
    schluessel = konfig.faehigkeiten[0].schluessel
    karriere = fenster.karriere
    karriere.waehle_fahrer(nummer)
    karriere.konto = karriere.konto.mit(geld=5_000_000, erfahrung=5_000)
    karriere.kaufe(schluessel)
    fenster.karriereseite.werte_geaendert.emit()

    seite = fenster.weltseite
    gezeigt = seite._welt.fahrer[nummer].auto.werte[schluessel]
    assert gezeigt == karriere.werte_von(nummer)[schluessel]
