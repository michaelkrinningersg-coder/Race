"""Misst, was ein Rennen im Aufbau und in der Anzeige kostet (E13).

Ein Messwerkzeug, **kein Test**: Es baut ein Rennen auf, spielt es in der
Rennseite ab und schreibt auf, wie lange beides dauert. Damit laesst sich
jede Aenderung an der Simulation oder der Anzeige vorher und nachher
belegen, statt sie zu behaupten.

Gemessen wird dreierlei:

* **Der Aufbau** - Strecke laden, Welt erzeugen, simulieren, anzeigen.
  Das ist die Wartezeit vor dem ersten Bild.
* **Ein Bild der Anzeige**, einmal vollstaendig und einmal ohne die
  Tabellen. Der Unterschied sagt, wo die Zeit liegt: In der ersten
  Messung (Punkt 86) kostete die Streckenkarte 0,10 ms und die Tabellen
  14,08 ms.
* **Der Fingerabdruck** des Rennens - eine Zahl aus Distanzen,
  Rundenzeiten und Ergebnissen. Wer die Rennschleife schneller macht,
  ohne das Verhalten zu aendern, muss denselben Fingerabdruck
  herausbekommen. ``tests/test_rennfingerabdruck.py`` haelt ihn fest.

Aufruf:
    python -m werkzeuge.profil_rennen
    python -m werkzeuge.profil_rennen --runden 10     kuerzer
    python -m werkzeuge.profil_rennen --profil        mit cProfile-Listen
    python -m werkzeuge.profil_rennen --nur-aufbau    ohne Qt
    python -m werkzeuge.profil_rennen --fingerabdruck nur die Kennzahl
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import os
import pstats
import time

import numpy as np

from rennmanager import konfiguration as kf
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import welt as kern_welt
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.zufall import Seedquelle

STRECKE = "Zandvoort"
LIGA = 1
RUNDEN = 40
WELTSEED = 1
RENNSEED = 4711
BILDER = 150


def fingerabdruck(verlauf: kern_rennen.Rennverlauf) -> str:
    """Eine Kennzahl, die sich aendert, sobald sich das Rennen aendert.

    Genommen wird, woran ein Spieler einen Unterschied merken wuerde:
    jede Distanz jedes Autos zu jedem Bild, alle Rundenzeiten, alle
    Sektorzeiten und die Ergebnisse. Ein einziges verschobenes Bit faellt
    damit auf.

    Die Distanzen gehen als ``float64`` in den Hash, unabhaengig davon,
    wie sie gespeichert sind - sonst aenderte allein ein anderer
    Speichertyp die Kennzahl, obwohl das Rennen dasselbe ist.
    """
    hasch = hashlib.sha256()
    hasch.update(np.ascontiguousarray(verlauf.distanz_m, dtype=np.float64).tobytes())
    for protokoll in verlauf.protokolle:
        hasch.update(repr(protokoll.rundenzeiten_ms).encode())
        hasch.update(repr(protokoll.sektorzeiten_ms).encode())
        hasch.update(repr(protokoll.rundenende_ms).encode())
    for ergebnis in verlauf.ergebnisse:
        hasch.update(repr(ergebnis).encode())
    for stopp in verlauf.boxenstopps:
        hasch.update(repr(stopp).encode())
    for zwischenfall in verlauf.zwischenfaelle:
        hasch.update(repr(zwischenfall).encode())
    return hasch.hexdigest()[:16]


def baue(runden: int) -> tuple:
    """Das Rennen aufbauen und dabei die Stationen stoppen."""
    zeiten: dict[str, float] = {}

    t0 = time.perf_counter()
    konfiguration = kf.lade()
    zeiten["Konfiguration laden"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    strecke = kern_strecke.lade(konfiguration, STRECKE)
    zeiten["Strecke laden"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    welt = kern_welt.erzeuge(konfiguration, Seedquelle(WELTSEED))
    zeiten["Welt erzeugen"] = time.perf_counter() - t0

    feld = kern_welt.starterfeld(welt, LIGA)
    haupt = Seedquelle(RENNSEED)
    rundendauer = kern_tempo.fahre_runde(konfiguration, strecke, feld[0].auto).zeit_ms

    t0 = time.perf_counter()
    wetter = kern_wetter.wuerfle(
        konfiguration, strecke.name, rundendauer * runden, rundendauer,
        haupt.zweig("rennwetter"),
    )
    verlauf = kern_rennen.simuliere(
        konfiguration, strecke, feld, runden, haupt.zweig("rennen"),
        kern_rennen.mittlerer_ueberholzonenanteil(konfiguration, (strecke,)),
        wetter=wetter,
    )
    zeiten["Rennen simulieren"] = time.perf_counter() - t0
    return konfiguration, welt, strecke, verlauf, zeiten


def zeige_aufbau(verlauf, zeiten: dict[str, float]) -> None:
    print("=== Aufbau ===")
    for name, wert in zeiten.items():
        print(f"{name:>22}: {wert * 1000:9.1f} ms")
    print(f"{'Summe':>22}: {sum(zeiten.values()) * 1000:9.1f} ms")
    print()
    speicher = sum(
        feld.nbytes
        for feld in (verlauf.distanz_m, verlauf.reifenzustand)
        if feld is not None
    )
    print(f"{'Autos':>22}: {verlauf.anzahl}")
    print(f"{'Runden':>22}: {verlauf.runden}")
    print(f"{'Bilder':>22}: {len(verlauf.zeitpunkte_ms)}")
    print(f"{'Renndauer':>22}: {verlauf.dauer_ms / 1000:9.1f} s")
    print(f"{'Bildfelder':>22}: {speicher / 1e6:9.1f} MB "
          f"({verlauf.distanz_m.dtype})")
    print(f"{'Zwischenfaelle':>22}: {len(verlauf.zwischenfaelle)}")
    print(f"{'Boxenstopps':>22}: {len(verlauf.boxenstopps)}")
    print(f"{'Fingerabdruck':>22}: {fingerabdruck(verlauf)}")


def zeige_profil(titel: str, profil: cProfile.Profile, zeilen: int = 20) -> None:
    strom = io.StringIO()
    pstats.Stats(profil, stream=strom).sort_stats("tottime").print_stats(zeilen)
    print(f"\n=== Profil: {titel} (Eigenzeit) ===")
    print(strom.getvalue())


def miss_anzeige(konfiguration, welt, strecke, verlauf, bilder: int, profilieren: bool):
    """Ein Bild der Rennseite, einmal ganz und einmal ohne Tabellen."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from rennmanager.ui.rennseite import Rennseite

    anwendung = QApplication.instance() or QApplication([])
    seite = Rennseite(konfiguration, welt, None)

    t0 = time.perf_counter()
    seite.zeige_verlauf(verlauf, strecke, None, tabelle=None)
    seite._halte_an()
    aufbau = time.perf_counter() - t0

    schritt = verlauf.dauer_ms / bilder

    def durchlauf() -> float:
        for i in range(5):
            seite._springe(i * schritt)
        t = time.perf_counter()
        for i in range(bilder):
            seite._springe(i * schritt)
        return (time.perf_counter() - t) / bilder

    voll = durchlauf()

    # Die Tabellen abklemmen, indem der Anzeigetakt unerreichbar wird.
    echt_takt = seite._anzeige_takt_ms
    seite._anzeige_takt_ms = float("inf")
    seite._letzte_tabellen_ms = 0.0
    t0 = time.perf_counter()
    for i in range(bilder):
        seite._zeit_ms = i * schritt
        seite._zeichne()
    karte = (time.perf_counter() - t0) / bilder
    seite._anzeige_takt_ms = echt_takt

    print("\n=== Wiedergabe ===")
    print(f"{'zeige_verlauf()':>22}: {aufbau * 1000:9.1f} ms")
    print(f"{'Ein Bild, ganz':>22}: {voll * 1000:9.2f} ms  ({1 / voll:7.1f} Bilder/s)")
    print(f"{'davon nur die Karte':>22}: {karte * 1000:9.2f} ms  ({1 / karte:7.1f} Bilder/s)")
    anteil = (voll - karte) / voll * 100 if voll > 0 else 0.0
    print(f"{'Tabellen':>22}: {(voll - karte) * 1000:9.2f} ms  ({anteil:5.0f} %)")

    if profilieren:
        profil = cProfile.Profile()
        profil.enable()
        for i in range(bilder):
            seite._springe(i * schritt)
        profil.disable()
        zeige_profil(f"Anzeige, {bilder} Bilder", profil)
    anwendung.processEvents()


def main() -> None:
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument("--runden", type=int, default=RUNDEN)
    zerleger.add_argument("--bilder", type=int, default=BILDER)
    zerleger.add_argument("--profil", action="store_true",
                          help="cProfile-Listen mit ausgeben")
    zerleger.add_argument("--nur-aufbau", action="store_true",
                          help="ohne die Anzeige messen (braucht kein Qt)")
    zerleger.add_argument("--fingerabdruck", action="store_true",
                          help="nur die Kennzahl ausgeben")
    argumente = zerleger.parse_args()

    if argumente.fingerabdruck:
        *_, verlauf, _ = baue(argumente.runden)
        print(fingerabdruck(verlauf))
        return

    if argumente.profil:
        profil = cProfile.Profile()
        profil.enable()
        konfiguration, welt, strecke, verlauf, zeiten = baue(argumente.runden)
        profil.disable()
        zeige_aufbau(verlauf, zeiten)
        zeige_profil(f"Aufbau, {argumente.runden} Runden", profil)
    else:
        konfiguration, welt, strecke, verlauf, zeiten = baue(argumente.runden)
        zeige_aufbau(verlauf, zeiten)

    if not argumente.nur_aufbau:
        miss_anzeige(konfiguration, welt, strecke, verlauf,
                     argumente.bilder, argumente.profil)


if __name__ == "__main__":
    main()
