"""Start der Qt-Anwendung."""

from __future__ import annotations

import sys

from rennmanager import __version__
from rennmanager.kern import auto as kern_auto
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.konfiguration import KonfigurationsFehler, lade

# Prueft nur, ob die Konfiguration gefunden und gelesen werden kann, und
# beendet sich dann. Der Build nutzt das, um die fertige .exe zu testen,
# ohne dass ein Fenster geoeffnet werden muss.
PRUEFMODUS = "--pruefe"


def pruefe() -> int:
    """Laedt die Konfiguration und meldet das Ergebnis auf der Konsole."""
    try:
        konfiguration = lade()
    except KonfigurationsFehler as fehler:
        print(f"Konfiguration fehlerhaft: {fehler}", file=sys.stderr)
        return 2

    print(f"Rennmanager {__version__}")
    print(f"Konfiguration: {konfiguration.quelle}")
    print(f"GDD-Version:   {konfiguration.wert('gdd_version')}")
    print(
        f"Geladen:       {konfiguration.wert('ligen', 'anzahl')} Ligen, "
        f"{len(konfiguration.strecken)} Strecken, "
        f"{len(konfiguration.faehigkeiten)} Faehigkeiten, "
        f"{len(konfiguration.hersteller)} Hersteller"
    )
    try:
        strecken = kern_strecke.lade_alle(konfiguration)
    except kern_strecke.StreckenFehler as fehler:
        print(f"Streckendaten fehlerhaft: {fehler}", file=sys.stderr)
        return 3

    gesamt = sum(s.laenge_m for s in strecken)
    zonen = sum(len(s.ueberholzonen) for s in strecken)
    print(
        f"Strecken:      {len(strecken)} ausgewertet, {gesamt / 1000:.1f} km, "
        f"{zonen} Ueberholzonen"
    )
    # Eine Runde ohne Zufall auf der Referenzstrecke: prueft zugleich, ob
    # das Geschwindigkeitsmodell kalibriert ist (GDD 9).
    name = konfiguration.wert("kalibrierung", "referenzstrecke")
    referenz = next(s for s in strecken if s.name == name)
    s_wert = konfiguration.wert("skala", "referenz")
    runde = kern_tempo.fahre_runde(
        konfiguration, referenz, kern_auto.gleichverteilt(konfiguration, s_wert)
    )
    soll = konfiguration.wert("kalibrierung", "v_bei_referenz_kmh")
    print(
        f"Kalibrierung:  {name} bei S={s_wert}: "
        f"{formatiere_dauer(runde.zeit_ms)}, {runde.schnitt_kmh:.2f} km/h "
        f"(Soll {soll:.2f}, Abweichung {runde.schnitt_kmh - soll:+.2f})"
    )
    print(f"Offene Punkte: {len(konfiguration.offene_punkte)}")
    return 0


def starte(argumente: list[str] | None = None) -> int:
    """Startet die Anwendung und liefert den Rueckgabewert des Prozesses."""
    argv = list(argumente) if argumente is not None else list(sys.argv)
    if PRUEFMODUS in argv[1:]:
        return pruefe()

    # Qt erst hier importieren, damit der Pruefmodus ohne Bildschirm und
    # ohne Qt-Systembibliotheken auskommt.
    from PySide6.QtWidgets import QApplication, QMessageBox

    from rennmanager.ui.hauptfenster import Hauptfenster

    anwendung = QApplication(argv)
    anwendung.setApplicationName("Rennmanager")
    anwendung.setOrganizationName("Rennmanager")

    try:
        konfiguration = lade()
    except KonfigurationsFehler as fehler:
        QMessageBox.critical(
            None,
            "Konfiguration fehlerhaft",
            f"Die Balancing-Konfiguration konnte nicht geladen werden:\n\n{fehler}",
        )
        return 2

    fenster = Hauptfenster(konfiguration)
    fenster.show()
    return anwendung.exec()
