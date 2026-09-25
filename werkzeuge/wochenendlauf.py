"""Faehrt Rennwochenenden und fotografiert sie an festen Stellen.

Ein Messwerkzeug: Es spielt das **gefuehrte Rennwochenende** der
Oberflaeche - Vorschau, Qualifying, Rennen, Ergebnis - und legt dabei
Bilder ab:

* je Wochenende ein Bild vom **Ende des Qualifyings**, also mit der
  vollstaendigen Zeitentafel,
* je Wochenende fuenf Bilder vom Rennen: aus dem **Stand** (Rennzeit 0,
  alle Autos noch auf ihren Startplaetzen) und nach 25, 50, 75 und
  100 Prozent der Renndauer,
* mit ``--blatt fuehrung`` dabei nicht der Zeitenmonitor, sondern ein
  anderes der rechten Blaetter - etwa die Fuehrungsrunden (Punkt 102),
  die ueber das Rennen mitwachsen.

Fotografiert wird das **ganze Hauptfenster** mit dem Reiter, der gerade
oben liegt - also genau das Bild, das der Spieler vor sich haette.
Gezeichnet wird das echte Widget, nichts nachgebaut.

Das Wetter laesst sich festhalten (``--wetter trocken``). Dafuer wird
**nicht** der Code angefasst, sondern die Konfiguration: Die Gewichte
aller Klimaprofile gehen auf die gewuenschte Lage, und die Zahl der
Wechsel geht auf null. Das Wetter wird also weiter ganz normal
gewuerfelt - es kann nur nichts anderes herauskommen.

Gefahren wird die Welt, die das Spiel beim Start baut (Hauptseed 0) -
also genau das Feld, das der Spieler vor sich hat.

Aufruf:
    python -m werkzeuge.wochenendlauf --ordner messungen --rennen 3
    python -m werkzeuge.wochenendlauf --wetter heiss
"""

from __future__ import annotations

import argparse
import os
from copy import deepcopy
from dataclasses import replace as ersetze
from pathlib import Path

# Das Werkzeug laeuft ohne Bildschirm; die Bilder entstehen trotzdem.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


from PySide6.QtWidgets import QApplication  # noqa: E402

from rennmanager.kern.zeit import formatiere_dauer  # noqa: E402
from rennmanager.konfiguration import Konfiguration, lade  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402

# Die Stellen im Rennen, an denen fotografiert wird - als Anteil der
# Renndauer. Null ist das Standbild vor dem Start.
MARKEN = (0.0, 0.25, 0.50, 0.75, 1.0)

# Fenstergroesse der Bilder. Kleiner wird die Rangliste unleserlich,
# groesser passt auf keinen Bildschirm mehr.
BREITE = 1920
HOEHE = 1080


def festes_wetter(konfiguration: Konfiguration, lage: str) -> Konfiguration:
    """Eine Konfiguration, in der jede Session dieselbe Wetterlage hat.

    Gewuerfelt wird weiter - nur ist die Verteilung entartet und die Zahl
    der Wechsel null. So bleibt der Weg durch den Kern derselbe wie im
    Spiel, und es gibt keinen Sonderpfad, der nur hier gilt.
    """
    kette = konfiguration.wert("wetter", "kette")
    if lage not in kette:
        raise SystemExit(f"{lage!r} steht nicht in der Wetterkette {kette}")

    roh = deepcopy(konfiguration.roh)
    roh["wetter"]["wechsel_min"] = 0
    roh["wetter"]["wechsel_max"] = 0
    for profil in roh["wetter"]["profil"].values():
        profil["gewichte"] = {zustand: (1 if zustand == lage else 0) for zustand in kette}
    return ersetze(konfiguration, roh=roh)


def fotografiere(fenster: Hauptfenster, ziel: Path) -> None:
    """Zeichnet das Fenster in eine PNG-Datei.

    ``grab()`` statt ``render()`` auf ein eigenes QImage: Ohne Bildschirm
    liefert Qt sonst ein Bild, dem der Fensterhintergrund fehlt.
    """
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bild = fenster.grab().toImage()
    if not bild.save(str(ziel)):
        raise SystemExit(f"Konnte {ziel} nicht schreiben")


def _weiter(seite) -> None:
    """Klickt "Weiter" und wartet auf die Hintergrundrechnung (E10)."""
    seite.knopf_weiter.click()
    seite.warte_auf_rechnung()


BLAETTER = {
    "monitor": 0,
    "ideal": 1,
    "meisterschaft": 2,
    "ticker": 3,
    "boxenbilanz": 4,
    "fuehrung": 5,
}


def fahre_wochenende(
    app: QApplication,
    fenster: Hauptfenster,
    ordner: Path,
    nummer: int,
    blatt: str = "",
) -> dict:
    """Ein ganzes Wochenende, mit Bildern an den sechs Stellen."""
    seite = fenster.wochenendeseite
    strecke = seite.wochenende.strecke.name
    marke = f"{nummer:02d}_{strecke.replace(' ', '-')}"
    bericht = {"rennen": nummer, "strecke": strecke}

    # --- Qualifying ----------------------------------------------------
    _weiter(seite)
    quali = fenster.qualifyingseite
    quali._zum_ende()
    app.processEvents()
    fotografiere(fenster, ordner / f"{marke}_1_qualifying.png")
    session = quali.session
    bericht["polezeit"] = formatiere_dauer(session.pole.zeit_ms)
    bericht["qualiwetter"] = session.wetter.zustaende

    # --- Rennen --------------------------------------------------------
    _weiter(seite)
    rennen = fenster.rennseite
    rennen._halte_an()
    if blatt:
        rennen.blaetter_rechts.setCurrentIndex(BLAETTER[blatt])
    verlauf = rennen.verlauf
    for stelle, anteil in enumerate(MARKEN, start=2):
        rennen._springe(verlauf.dauer_ms * anteil)
        # Ein frisch aufgeschlagenes Blatt fuellt sich erst im naechsten
        # Takt (D2); hier wird nicht abgespielt, also von Hand.
        rennen._erzwinge_fuellung()
        rennen._zeichne()
        app.processEvents()
        fotografiere(
            fenster, ordner / f"{marke}_{stelle}_rennen_{int(anteil * 100):03d}.png"
        )
    sieger = verlauf.ergebnisse[0]
    fuehrung = verlauf.fuehrungsrunden()
    bericht["fuehrung"] = {
        verlauf.teilnehmer[i].kuerzel: n
        for i, n in sorted(enumerate(fuehrung), key=lambda paar: -paar[1])
        if n
    }
    bericht["wechsel"] = verlauf.fuehrungswechsel()
    bericht["runden"] = seite.wochenende.runden
    bericht["dauer"] = formatiere_dauer(int(verlauf.dauer_ms))
    bericht["rennwetter"] = verlauf.wetter.zustaende
    bericht["sieger"] = verlauf.teilnehmer[sieger.teilnehmer].kuerzel
    bericht["siegerzeit"] = formatiere_dauer(sieger.zeit_ms)
    bericht["ausfaelle"] = sum(1 for e in verlauf.ergebnisse if e.zeit_ms is None)

    # --- Ergebnis, dann das naechste Wochenende aufrufen ----------------
    _weiter(seite)
    app.processEvents()
    _weiter(seite)
    return bericht


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--ordner", default="messungen/wochenenden")
    zerleger.add_argument("--rennen", type=int, default=3, help="wie viele Wochenenden")
    zerleger.add_argument(
        "--wetter",
        default="trocken",
        help="Wetterlage, die festgehalten wird; 'gewuerfelt' laesst sie frei",
    )
    zerleger.add_argument(
        "--blatt",
        default="",
        help="rechtes Blatt der Rennseite: monitor, ideal, meisterschaft, "
        "ticker, boxenbilanz oder fuehrung",
    )
    argumente = zerleger.parse_args()

    konfiguration = lade()
    if argumente.wetter != "gewuerfelt":
        konfiguration = festes_wetter(konfiguration, argumente.wetter)

    app = QApplication.instance() or QApplication([])
    fenster = Hauptfenster(konfiguration)
    fenster.resize(BREITE, HOEHE)
    fenster.show()
    # Auf den gefuehrten Reiter schalten - sonst fotografiert das Werkzeug
    # die Uebersicht, die beim Start oben liegt.
    reiter = fenster._reiter
    reiter.setCurrentIndex(reiter.indexOf(fenster.wochenendeseite))
    app.processEvents()

    ordner = Path(argumente.ordner)
    print(f"Wetter: {argumente.wetter}, Ordner: {ordner}\n")
    for nummer in range(1, argumente.rennen + 1):
        bericht = fahre_wochenende(app, fenster, ordner, nummer, argumente.blatt)
        print(
            f"Rennen {bericht['rennen']}: {bericht['strecke']}, "
            f"{bericht['runden']} Runden\n"
            f"  Qualifying {bericht['qualiwetter']}, Pole {bericht['polezeit']}\n"
            f"  Rennen     {bericht['rennwetter']}, Sieger {bericht['sieger']} "
            f"in {bericht['siegerzeit']}, {bericht['ausfaelle']} Ausfaelle\n"
            f"  Renndauer  {bericht['dauer']}\n"
            f"  Fuehrung   {bericht['fuehrung']}, {bericht['wechsel']} Wechsel"
        )

    bilder = sorted(ordner.glob("*.png"))
    print(f"\n{len(bilder)} Bilder in {ordner}")
    fenster.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
