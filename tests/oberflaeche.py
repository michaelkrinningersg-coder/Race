"""Gemeinsame Helfer der Oberflaechen-Tests.

Kein Testmodul, sondern das, was sich mehrere teilen: ein kurzes Rennen,
ein gefahrenes Qualifying, eine beendete Saison und zwei Griffe, die ohne
feste Weltgroesse auskommen.

Die Datei entstand beim Aufteilen von ``test_ui.py`` (Punkt 77): Verteilt
der Testlauf je Datei auf die Kerne, bestimmt die laengste Datei, wie
lange der ganze Lauf dauert. Die Helfer mussten dafuer aus dem Testmodul
heraus, sonst importierten die neuen Dateien einander quer.
"""

from __future__ import annotations

import pytest

from rennmanager.kern import wertung as wt

pytest.importorskip("PySide6")


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


def weiter(seite, mal: int = 1) -> None:
    """Klickt "Weiter" und wartet auf die Hintergrundrechnung (E10).

    Seit E10 laeuft das Rennen in einem eigenen Thread, damit das Fenster
    waehrend der elf Sekunden ansprechbar bleibt. Ein Test, der direkt
    nach dem Klick nachsieht, findet deshalb noch nichts - er muss
    warten, so wie der Spieler auch wartet, nur ohne zuzusehen.
    """
    for _ in range(mal):
        seite.knopf_weiter.click()
        seite.warte_auf_rechnung()


def schlage_blatt_auf(seite, name: str):
    """Oeffnet eines der vier rechten Blaetter der Rennseite (D2).

    Seit D2 fuellt die Rennseite nur noch das Blatt, das man auch sieht:
    Zeitenmonitor, Bestmoegliche Runde, Meisterschaft und Meldungen
    liegen in einem Reiter, und alle vier in jedem Bild zu fuellen
    kostete ein Drittel der Zeit, die ein Bild braucht. Ein Test, der
    aus einem Blatt liest, muss es also aufschlagen - genau wie der
    Spieler.

    :param name: monitor, ideal, meisterschaft oder ticker
    """
    from rennmanager.ui import rennseite as rs

    blatt = {
        "monitor": rs.BLATT_MONITOR,
        "ideal": rs.BLATT_IDEAL,
        "meisterschaft": rs.BLATT_MEISTERSCHAFT,
        "ticker": rs.BLATT_TICKER,
    }[name]
    seite.blaetter_rechts.setCurrentIndex(blatt)
    # setCurrentIndex meldet nichts, wenn das Blatt schon oben lag -
    # dann muss die Fuellung von Hand angestossen werden.
    seite._erzwinge_fuellung()
    seite._zeichne()
    return seite.blaetter_rechts.currentWidget()


def kurzes_rennen(fenster, runden: int = 2, umgedreht: bool = False):
    """Rechnet ein kurzes Rennen und gibt es der Rennanzeige.

    Die Rennseite rechnet seit Punkt 12 nichts mehr - sie spielt ab, was
    ihr das gefuehrte Wochenende reicht. Ein echtes Wochenende dauert 19
    Runden und 17 Sekunden; die Anzeige-Tests brauchen das nicht, also
    kommt hier ein Zweirundenrennen aus dem Kern.
    """
    verlauf, strecke = rennverlauf(fenster, runden, umgedreht)
    seite = fenster.rennseite
    seite.zeige_verlauf(verlauf, strecke)
    return seite


def rennverlauf(fenster, runden: int = 2, umgedreht: bool = False):
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


def gefahrenes_qualifying(fenster):
    """Faehrt das Qualifying des naechsten Wochenendes (Punkt 12).

    Eigene Regler hat die Qualifyingseite seit Punkt 12 nicht mehr; sie
    zeigt, was das gefuehrte Wochenende ihr reicht. Das Qualifying selbst
    dauert nur Bruchteile einer Sekunde.
    """
    weiter(fenster.wochenendeseite)
    return fenster.qualifyingseite


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
