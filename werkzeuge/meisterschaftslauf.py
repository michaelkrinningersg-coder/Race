"""Faehrt das erste Rennwochenende und legt den Meisterschaftsstand ab.

Ein Messwerkzeug zu Punkt 95: Es baut eine vollstaendige Welt (10 Ligen,
400 Autos), beginnt die Karriere des Spielers in der untersten Liga und
faehrt sein erstes Wochenende - Qualifying und Rennen - so, wie es das
gefuehrte Wochenende der Oberflaeche tut.

Danach nimmt es dieselbe ``Rennseite``, die im Spiel laeuft, stellt sie
auf das Blatt "Meisterschaft" und fotografiert die Tabelle an fuenf
Stellen:

* nach dem Qualifying (Rennzeit 0 - die Qualifyingpunkte stehen schon
  drin, gefahren ist noch nichts)
* nach 25, 50, 75 und 100 Prozent der Renndistanz

Jede Stelle einmal in der eigenen Liga und einmal als Weltmeisterschaft
ueber alle zehn Ligen ("Alle Ligen"). Gezeichnet wird das echte Widget,
nicht ein nachgebautes Bild - so zeigt der Lauf auch, was der Spieler
tatsaechlich zu sehen bekaeme.

Aufruf:
    python -m werkzeuge.meisterschaftslauf --ordner messungen --seed 0
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# Das Werkzeug laeuft ohne Bildschirm; die Bilder entstehen trotzdem.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import karriere as kern_karriere  # noqa: E402
from rennmanager.kern import popularitaet as kern_popularitaet  # noqa: E402
from rennmanager.kern import saison as kern_saison  # noqa: E402
from rennmanager.kern import statistik as kern_statistik  # noqa: E402
from rennmanager.kern import strecke as kern_strecke  # noqa: E402
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis  # noqa: E402
from rennmanager.kern import welt as kern_welt  # noqa: E402
from rennmanager.kern.zeit import formatiere_dauer  # noqa: E402
from rennmanager.kern.zufall import Seedquelle  # noqa: E402
from rennmanager.konfiguration import lade  # noqa: E402
from rennmanager.ui.karriereseite import beginne as beginne_karriere  # noqa: E402
from rennmanager.ui.rennseite import (  # noqa: E402
    BLATT_MEISTERSCHAFT,
    WELT_SPITZE,
    WELT_UMFELD,
    Rennseite,
)

# Die fuenf Messpunkte als Anteil der Renndauer. Null ist das Standbild
# unmittelbar vor dem Start - der Stand nach dem Qualifying.
ANTEILE = (0.0, 0.25, 0.50, 0.75, 1.00)
# Beschriftung der fuenf Messpunkte.
TITEL = {
    0.0: "Meisterschaft nach dem Qualifying",
    0.25: "Meisterschaft bei 25 % Renndistanz",
    0.50: "Meisterschaft bei 50 % Renndistanz",
    0.75: "Meisterschaft bei 75 % Renndistanz",
    1.00: "Meisterschaft im Ziel",
}


def baue_lauf(konfiguration, seed: int):
    """Welt, Karriere und Saisonlauf wie beim Start des Spiels."""
    seedquelle = Seedquelle(seed)
    welt = kern_welt.erzeuge(
        konfiguration,
        seedquelle.zweig("welt"),
        spielerliga=konfiguration.wert("ligen", "startliga"),
    )
    jahr = kern_karriere.startjahr(konfiguration)
    statistik = kern_statistik.Statistik(konfiguration)
    kenntnis = kern_streckenkenntnis.Streckenkenntnis(
        konfiguration, seedquelle=seedquelle.zweig("lerntempo")
    )
    popularitaet = kern_popularitaet.Popularitaet(konfiguration)
    popularitaet.anfang(
        tuple(f.nummer for f in welt.fahrer), seedquelle.zweig("popularitaet")
    )
    kern_streckenkenntnis.setze_ki_anfang(
        konfiguration,
        welt,
        kenntnis,
        tuple(e["name"] for e in konfiguration.strecken),
        seedquelle.zweig("kikenntnis"),
    )
    karriere = beginne_karriere(
        konfiguration, welt, seedquelle.zweig("karriere", jahr), jahr
    )
    lauf = kern_saison.Saisonlauf(
        konfiguration,
        welt,
        seedquelle,
        jahr=jahr,
        strecken=kern_strecke.lade_alle(konfiguration),
        statistik=statistik,
        kenntnis=kenntnis,
        karriere=karriere,
        popularitaet=popularitaet,
    )
    return lauf, karriere


def fahre_wochenende(lauf, liga: int):
    """Qualifying und Rennen der Liga des Spielers, in den Etappen der Oberflaeche."""
    wochenende = kern_saison.Wochenendlauf(lauf, liga)
    qualifying = wochenende.fahre_qualifying()
    # Die Reifenwahl bleibt bei der Vorausberechnung - gemessen wird die
    # Tabelle, nicht die Strategie.
    wochenende.strategiewahl()
    verlauf = wochenende.fahre_rennen()
    return wochenende, qualifying, verlauf


def baue_seite(konfiguration, lauf, karriere, wochenende) -> Rennseite:
    """Die echte Rennseite mit dem gefahrenen Wochenende darin."""
    seite = Rennseite(konfiguration, lauf.welt, karriere)
    seite.resize(1600, 900)
    seite.zeige_verlauf(
        wochenende.verlauf,
        wochenende.rahmen.strecke,
        wochenende.qualifying,
        tabelle=lauf.tabelle(wochenende.liga),
        tabellen=lauf.tabellen,
    )
    # Das Blatt, um das es geht - sonst fuellt die Seite es gar nicht (D2).
    seite._monitorblaetter.setCurrentIndex(BLATT_MEISTERSCHAFT)
    return seite


def baue_rahmen(seite: Rennseite):
    """Haengt die Meisterschaftstabelle in einen eigenen Bilderrahmen um.

    Im Reiter der Rennseite bestimmt das Fenster die Groesse, und was
    nicht hineinpasst, verschwindet hinter Rollbalken. Fuer das Bild soll
    umgekehrt die Tabelle die Groesse bestimmen. Gezeigt wird dabei
    dasselbe Widget, das auch im Spiel laeuft - nur mit einer
    Bildunterschrift darueber.
    """
    rahmen = QWidget()
    rahmen.setAutoFillBackground(True)
    spalte = QVBoxLayout(rahmen)
    spalte.setContentsMargins(14, 12, 14, 12)
    spalte.setSpacing(4)
    ueberschrift = QLabel()
    ueberschrift.setStyleSheet("font-size: 15px; font-weight: bold;")
    unterzeile = QLabel()
    unterzeile.setStyleSheet("font-size: 12px; color: #52514e;")
    spalte.addWidget(ueberschrift)
    spalte.addWidget(unterzeile)
    spalte.addWidget(seite._meisterschaft)
    return rahmen, ueberschrift, unterzeile


def fotografiere(rahmen, baum, ziel: Path) -> int:
    """Legt die Tabelle als PNG ab und liefert die Zahl ihrer Zeilen."""
    zeilen = baum.topLevelItemCount()
    baum.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    baum.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    for spalte in range(baum.columnCount()):
        baum.resizeColumnToContents(spalte)
    rand = 2 * baum.frameWidth()
    breite = sum(baum.columnWidth(s) for s in range(baum.columnCount())) + rand + 2
    hoehe = baum.header().height() + rand + 2
    for stelle in range(zeilen):
        hoehe += baum.sizeHintForRow(stelle)
    baum.setFixedSize(breite, hoehe)
    rahmen.adjustSize()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    rahmen.grab().save(str(ziel))
    return zeilen


def vorlauf(lauf, liga: int, bis: int) -> None:
    """Faehrt die Rennen vor dem gemessenen komplett durch.

    Erst danach haben alle zehn Ligen Punkte - vor dem ersten Rennen
    steht die Weltmeisterschaft ueberall auf null, und die Weltansicht
    zeigt nur die eine Liga, die gerade faehrt.
    """
    for nummer in range(1, bis):
        wochenende = kern_saison.Wochenendlauf(lauf, liga)
        wochenende.fahre_qualifying()
        wochenende.fahre_rennen()
        wochenende.schliesse_ab()
        print(f"  Rennen {nummer} gefahren: {wochenende.rahmen.strecke.name}")


def messlauf(konfiguration, seed: int, ordner: Path, rennen: int) -> None:
    lauf, karriere = baue_lauf(konfiguration, seed)
    liga = karriere.liga
    print(
        f"Welt: {konfiguration.wert('ligen', 'anzahl')} Ligen, "
        f"{len(lauf.welt.fahrer) - 1} Fahrer, Spieler in Liga {liga}"
    )
    if rennen > 1:
        vorlauf(lauf, liga, rennen)

    wochenende, _qualifying, verlauf = fahre_wochenende(lauf, liga)
    strecke = wochenende.rahmen.strecke
    # Das Rennfeld steht in der Reihenfolge des Qualifyings (saison.startfeld):
    # Index 0 ist die Pole. ``qualifying.aufstellung`` zaehlt dagegen im Feld
    # der Session und passt hier nicht.
    pole = verlauf.teilnehmer[0]
    print(
        f"Rennen {rennen}: {strecke.name}, {verlauf.runden} Runden, "
        f"Dauer {formatiere_dauer(verlauf.dauer_ms)}, Pole {pole.kuerzel}"
    )

    seite = baue_seite(konfiguration, lauf, karriere, wochenende)
    rahmen, ueberschrift, unterzeile = baue_rahmen(seite)
    for anteil in ANTEILE:
        seite._springe(anteil * verlauf.dauer_ms)
        for welt in (False, True):
            seite._alle_ligen.setChecked(welt)
            seite._zeige_meisterschaft_neu()
            sicht = (
                f"Weltmeisterschaft ueber alle "
                f"{konfiguration.wert('ligen', 'anzahl')} Ligen - Spitze "
                f"{WELT_SPITZE} und je {WELT_UMFELD} Zeilen um die eigenen Fahrer"
                if welt
                else f"Nur Liga {liga} - alle {konfiguration.wert('ligen', 'autos_je_liga')} Autos"
            )
            ueberschrift.setText(TITEL[anteil])
            unterzeile.setText(
                f"Rennen {rennen} - {strecke.name} - {seite._rundenstand.text()} - "
                f"{seite._uhrzeit.text()}   |   {sicht}"
            )
            name = "welt" if welt else "liga"
            ziel = ordner / f"r{rennen}_meisterschaft_{int(anteil * 100):03d}_{name}.png"
            zeilen = fotografiere(rahmen, seite._meisterschaft, ziel)
            print(
                f"  {int(anteil * 100):3d} %  {name:5s}  {zeilen:3d} Zeilen  -> {ziel.name}"
            )
    rahmen.deleteLater()
    seite.deleteLater()


def main(argv: list[str] | None = None) -> None:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--seed", type=int, default=0, help="Seed der Welt")
    zerleger.add_argument(
        "--ordner", type=Path, default=Path("messungen"), help="Zielordner der Bilder"
    )
    zerleger.add_argument(
        "--rennen",
        type=int,
        default=1,
        help="Welches Rennen der Saison gemessen wird; die davor laufen komplett durch",
    )
    argumente = zerleger.parse_args(argv)

    anwendung = QApplication.instance() or QApplication([])
    konfiguration = lade()
    argumente.ordner.mkdir(parents=True, exist_ok=True)
    messlauf(konfiguration, argumente.seed, argumente.ordner, argumente.rennen)
    del anwendung


if __name__ == "__main__":
    main()
