"""Start der Qt-Anwendung."""

from __future__ import annotations

import sys

from rennmanager import __version__
from rennmanager.kern import auto as kern_auto
from rennmanager.kern import einnahmen as kern_einnahmen
from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import schnellsimulation as kern_schnell
from rennmanager.kern import spielstand as kern_spielstand
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import streckenkenntnis as kern_kenntnis
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import KonfigurationsFehler, lade

# Prueft nur, ob die Konfiguration gefunden und gelesen werden kann, und
# beendet sich dann. Der Build nutzt das, um die fertige .exe zu testen,
# ohne dass ein Fenster geoeffnet werden muss.
PRUEFMODUS = "--pruefe"


def euro(betrag: int) -> str:
    """Betrag mit Punkt als Tausendertrennzeichen."""
    return f"{betrag:,} EUR".replace(",", ".")


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
    # Ein Kurzrennen ueber zwei Runden: prueft die Rennschleife im Bundle.
    verlauf = kern_rennen.simuliere(
        konfiguration,
        referenz,
        kern_rennen.starterfeld(konfiguration, 20, umgedreht=True),
        2,
        Seedquelle(1),
        kern_rennen.mittlerer_ueberholzonenanteil(konfiguration, strecken),
    )
    sieger = verlauf.ergebnisse[0]
    print(
        f"Rennen:        {len(verlauf.teilnehmer)} Autos, 2 Runden, Sieger "
        f"{verlauf.teilnehmer[sieger.teilnehmer].kuerzel} in "
        f"{formatiere_dauer(sieger.zeit_ms)}, {sum(verlauf.positionsgewinne)} "
        f"Ueberholmanoever ({len(verlauf.manoever)} Vorbeigaenge)"
    )
    # Ein Rennwochenende im Schnellmodus und seine Wertung: prueft die
    # Bausteine der Saison (GDD 13) im fertigen Bundle.
    feld = kern_rennen.starterfeld(konfiguration, 20, seedquelle=Seedquelle(2))
    schnell = kern_schnell.fahre_wochenende(
        konfiguration,
        20,
        referenz,
        feld,
        2,
        Seedquelle(2),
        kern_rennen.mittlerer_ueberholzonenanteil(konfiguration, strecken),
    )
    tabelle = kern_wertung.Tabelle(20)
    tabelle.verbuche(konfiguration, schnell.ergebnisse)
    bester = tabelle.stand()[0]
    print(
        f"Schnellmodus:  {len(schnell.ergebnisse)} Autos, 2 Runden, Sieger "
        f"{feld[bester.fahrer].kuerzel} in {formatiere_dauer(schnell.siegerzeit_ms)}, "
        f"{bester.punkte} Punkte, {schnell.ueberholmanoever} Ueberholmanoever"
    )
    jahr = kern_karriere.startjahr(konfiguration)
    saison = kern_kalender.erzeuge(konfiguration, jahr)
    print(
        f"Kalender:      {len(saison.renntage)} Rennen vom "
        f"{saison.erstes_rennen:%d.%m.} bis {saison.letztes_rennen:%d.%m.}, "
        f"{len(saison.vorsaison)} Tage Vorsaison, "
        f"{len(saison.nachsaison)} Tage Nachsaison"
    )
    print(
        f"Wirtschaft:    Siegpraemie Liga 20 {euro(kern_einnahmen.siegpraemie(konfiguration, 20))}"
        f", Liga 1 {euro(kern_einnahmen.siegpraemie(konfiguration, 1))}"
        f", Startkapital {euro(kern_einnahmen.startkapital(konfiguration))}"
    )
    # Ereignisse einer Saison: prueft GDD 14 im Bundle.
    plan = kern_ereignis.plane_saison(konfiguration, saison, Seedquelle(3))
    gezogen = sum(len(liste) for liste in plan.values())
    print(
        f"Ereignisse:    {len(kern_ereignis.liste(konfiguration))} moeglich, "
        f"{gezogen} in der Saison {jahr} mit Seed 3, "
        f"{len(kern_ereignis.zyklen(konfiguration, saison))} Zyklen"
    )
    # Streckenkenntnis (GDD 6) und Spielstand (GDD 15).
    voll = konfiguration.wert("streckenkenntnis", "volle_kenntnis_runden")
    # Was neben der Wirkungsmatrix aus GDD 8 steht (Punkt 48).
    neben = konfiguration.zusatzfaehigkeiten
    print(
        f"Eigenschaften: {len(neben)} neben der Matrix, davon "
        f"{len(konfiguration.fahrzeugzusatz)} am Fahrzeug"
    )
    print(
        "Ueber Distanz: Ermuedung bis "
        f"{konfiguration.wert('ermuedung', 'tempoverlust_am_ende_bei_null') * 100:.1f} %, "
        "Kaltreifen bis "
        f"{konfiguration.wert('kaltreifen', 'tempoverlust_bei_null') * 100:.1f} %, "
        "Bremse bis "
        f"{konfiguration.wert('bremskuehlung', 'verlust_am_ende_bei_null') * 100:.1f} %"
    )
    print(
        "Verkehr:       Windschatten bis "
        f"{konfiguration.wert('windschatten', 'gewinn_bei_maximum') * 100:.1f} % "
        f"innerhalb {konfiguration.wert('windschatten', 'fenster_m'):.0f} m, "
        "Rhythmus +/- "
        f"{konfiguration.wert('rhythmus', 'max_anteil_quer') * 100:.1f} % quer"
    )
    print(
        f"Kenntnis:      bis {kern_kenntnis.bonus(konfiguration, voll) * 100:.2f} % Tempo "
        f"nach {voll} Runden"
    )
    print(
        f"Spielstand:    SQLite, Version {kern_spielstand.SPIELSTAND_VERSION}, "
        f"{len([z for z in kern_spielstand.SCHEMA.split('CREATE TABLE')[1:]])} Tabellen"
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
    # Punkt 11: Beim Start fragt das Spiel, wer der Spieler ist. Wer
    # abbricht, faehrt mit dem gewuerfelten Fahrer weiter - die Welt steht
    # schon, es fehlt nur der Name.
    fenster.neue_karriere()
    return anwendung.exec()
