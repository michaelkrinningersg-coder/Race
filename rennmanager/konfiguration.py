"""Laden und Pruefen der Balancing-Konfiguration.

Arbeitsregel: Alle Balancing-Werte stehen zentral in
``konfiguration/balancing.toml``; im Code steht kein einziger davon. Dieses
Modul liest die Dateien, prueft sie gegen die Vorgaben des GDD und meldet
Luecken, statt sie stillschweigend zu fuellen.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BALANCING_DATEI = "balancing.toml"
HERSTELLER_DATEI = "hersteller.toml"

# Vorgaben aus dem GDD, gegen die geprueft wird.
ANZAHL_FAHRZEUG_UPGRADES = 16       # GDD 5
ANZAHL_FAHRER_EIGENSCHAFTEN = 16    # GDD 6
ANZAHL_MIT_GELDANTEIL = 18          # GDD 9: "18 Faehigkeiten haben einen Geldanteil"
ANZAHL_STRECKEN = 20                # GDD 3
ANZAHL_LIGEN = 20                   # GDD 12
ANZAHL_HERSTELLER = 20              # GDD 12
ANZAHL_EREIGNISSE = 35              # GDD 14
ANZAHL_DEFEKTE = 20                 # GDD 14
ANZAHL_WETTERZUSTAENDE = 5          # GDD 7
ANZAHL_PUNKTERAENGE = 20            # GDD 13
WAEHRUNGEN = {"G", "E", "Z"}        # Geld, Erfahrung, Zeit


class KonfigurationsFehler(Exception):
    """Die Konfiguration widerspricht den Vorgaben des GDD."""


@dataclass(frozen=True)
class Faehigkeit:
    """Ein Fahrzeug-Upgrade (F1-F16) oder eine Fahrer-Eigenschaft (D1-D16)."""

    schluessel: str
    name: str
    waehrung: tuple[str, ...]
    gewichte: dict[str, int]
    zusatz: dict[str, Any] = field(default_factory=dict)

    @property
    def ist_fahrzeug(self) -> bool:
        return self.schluessel.startswith("F")

    @property
    def hat_geldanteil(self) -> bool:
        return "G" in self.waehrung

    def gewicht(self, bereich: str) -> int:
        """Gewicht in einem Wirkungsbereich; nicht genannte Bereiche sind 0."""
        return self.gewichte.get(bereich, 0)


@dataclass(frozen=True)
class Hersteller:
    schluessel: str
    name: str
    farbe: str


@dataclass(frozen=True)
class Konfiguration:
    """Die geladene und gepruefte Konfiguration."""

    roh: dict[str, Any]
    fahrzeug: tuple[Faehigkeit, ...]
    fahrer: tuple[Faehigkeit, ...]
    hersteller: tuple[Hersteller, ...]
    hersteller_bestaetigt: bool
    quelle: Path

    # -- Zugriff -----------------------------------------------------------
    def wert(self, *pfad: str, standard: Any = ...) -> Any:
        """Liest einen Wert ueber seinen Pfad, z. B. ``wert("start", "abstand_m")``."""
        knoten: Any = self.roh
        for teil in pfad:
            if not isinstance(knoten, dict) or teil not in knoten:
                if standard is ...:
                    raise KeyError(" -> ".join(pfad))
                return standard
            knoten = knoten[teil]
        return knoten

    @property
    def faehigkeiten(self) -> tuple[Faehigkeit, ...]:
        """Alle 32 Faehigkeiten, Fahrzeug zuerst."""
        return self.fahrzeug + self.fahrer

    def faehigkeit(self, schluessel: str) -> Faehigkeit:
        for eintrag in self.faehigkeiten:
            if eintrag.schluessel == schluessel:
                return eintrag
        raise KeyError(f"Unbekannte Faehigkeit: {schluessel}")

    @property
    def zusatzfaehigkeiten(self) -> tuple[str, ...]:
        """Fahrer-Eigenschaften neben der Wirkungsmatrix.

        Das sind die fuenf Wetterfaehigkeiten aus GDD 7 und der
        Reifenfluesterer. Sie haben keine Zeile in der Wirkungsmatrix und
        gehen nicht in den Durchschnitt der Basiseigenschaften ein (GDD 4).
        """
        wetter = tuple(
            eintrag["schluessel"] for eintrag in self.wert("wetter", "faehigkeit", "liste")
        )
        weitere = self.wert("reifen", "fluesterer", "schluessel", standard=None)
        return wetter + ((weitere,) if weitere else ())

    @property
    def bereiche(self) -> tuple[str, ...]:
        return tuple(self.wert("wirkungsmatrix", "bereiche"))

    @property
    def strecken(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.wert("strecke", "liste"))

    @property
    def offene_punkte(self) -> dict[str, str]:
        """Im GDD nicht festgelegte Angaben, die noch geklaert werden muessen."""
        return dict(self.wert("offen", standard={}))

    def ligenname(self, liga: int) -> str:
        """Ligenname aus Stufe und Nummer, z. B. ``"Bronze 5"`` fuer Liga 20."""
        for gruppe in self.wert("ligen", "namen"):
            if gruppe["von_liga"] <= liga <= gruppe["bis_liga"]:
                return f"{gruppe['stufe']} {liga - gruppe['von_liga'] + 1}"
        raise ValueError(f"Liga ausserhalb des gueltigen Bereichs: {liga}")


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------
def konfigurationsverzeichnis() -> Path:
    """Findet das Verzeichnis mit den Konfigurationsdateien.

    Im Quellbaum liegt es neben dem Paket, in der mit PyInstaller gebauten
    .exe unter dem entpackten Bundle-Verzeichnis.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        pfad = Path(bundle) / "konfiguration"
        if pfad.is_dir():
            return pfad
    return Path(__file__).resolve().parent.parent / "konfiguration"


def lade(verzeichnis: Path | str | None = None) -> Konfiguration:
    """Laedt und prueft die Konfiguration.

    :raises KonfigurationsFehler: wenn eine Datei fehlt, unlesbar ist oder
        den Vorgaben des GDD widerspricht.
    """
    ordner = Path(verzeichnis) if verzeichnis is not None else konfigurationsverzeichnis()
    roh = _lies_toml(ordner / BALANCING_DATEI)
    hersteller_roh = _lies_toml(ordner / HERSTELLER_DATEI)

    fahrzeug = _lies_faehigkeiten(roh, "fahrzeug", "F", ANZAHL_FAHRZEUG_UPGRADES)
    fahrer = _lies_faehigkeiten(roh, "fahrer", "D", ANZAHL_FAHRER_EIGENSCHAFTEN)
    hersteller = _lies_hersteller(hersteller_roh)

    konfiguration = Konfiguration(
        roh=roh,
        fahrzeug=fahrzeug,
        fahrer=fahrer,
        hersteller=hersteller,
        hersteller_bestaetigt=bool(hersteller_roh.get("bestaetigt", False)),
        quelle=ordner,
    )
    _pruefe(konfiguration)
    return konfiguration


def _lies_toml(pfad: Path) -> dict[str, Any]:
    if not pfad.is_file():
        raise KonfigurationsFehler(f"Konfigurationsdatei fehlt: {pfad}")
    try:
        with pfad.open("rb") as datei:
            return tomllib.load(datei)
    except tomllib.TOMLDecodeError as fehler:
        raise KonfigurationsFehler(f"{pfad} ist kein gueltiges TOML: {fehler}") from fehler


def _lies_faehigkeiten(
    roh: dict[str, Any], abschnitt: str, praefix: str, erwartet: int
) -> tuple[Faehigkeit, ...]:
    eintraege = roh.get(abschnitt)
    if not isinstance(eintraege, list):
        raise KonfigurationsFehler(f"Abschnitt [[{abschnitt}]] fehlt oder ist keine Liste")

    faehigkeiten: list[Faehigkeit] = []
    for nummer, eintrag in enumerate(eintraege, start=1):
        schluessel = eintrag.get("schluessel", "")
        erwarteter_schluessel = f"{praefix}{nummer}"
        if schluessel != erwarteter_schluessel:
            raise KonfigurationsFehler(
                f"[[{abschnitt}]] Nr. {nummer}: erwartet {erwarteter_schluessel}, "
                f"gefunden {schluessel!r}"
            )
        waehrung = tuple(eintrag.get("waehrung", ()))
        unbekannt = set(waehrung) - WAEHRUNGEN
        if unbekannt:
            raise KonfigurationsFehler(
                f"{schluessel}: unbekannte Waehrung {sorted(unbekannt)}; "
                f"erlaubt sind {sorted(WAEHRUNGEN)}"
            )
        if not waehrung:
            raise KonfigurationsFehler(f"{schluessel}: keine Waehrung angegeben")

        zusatz = {
            name: wert
            for name, wert in eintrag.items()
            if name not in {"schluessel", "name", "waehrung", "gewichte"}
        }
        faehigkeiten.append(
            Faehigkeit(
                schluessel=schluessel,
                name=eintrag.get("name", schluessel),
                waehrung=waehrung,
                gewichte=dict(eintrag.get("gewichte", {})),
                zusatz=zusatz,
            )
        )

    if len(faehigkeiten) != erwartet:
        raise KonfigurationsFehler(
            f"[[{abschnitt}]]: {erwartet} Eintraege erwartet, {len(faehigkeiten)} gefunden"
        )
    return tuple(faehigkeiten)


def _lies_hersteller(roh: dict[str, Any]) -> tuple[Hersteller, ...]:
    eintraege = roh.get("hersteller")
    if not isinstance(eintraege, list):
        raise KonfigurationsFehler("[[hersteller]] fehlt oder ist keine Liste")
    return tuple(
        Hersteller(
            schluessel=eintrag["schluessel"],
            name=eintrag["name"],
            farbe=eintrag["farbe"],
        )
        for eintrag in eintraege
    )


# ---------------------------------------------------------------------------
# Pruefungen gegen das GDD
# ---------------------------------------------------------------------------
def _pruefe(k: Konfiguration) -> None:
    _pruefe_wirkungsmatrix(k)
    _pruefe_tempo(k)
    _pruefe_wetterprofile(k)
    _pruefe_geldanteil(k)
    _pruefe_strecken(k)
    _pruefe_ligen(k)
    _pruefe_wetter(k)
    _pruefe_wertung(k)
    _pruefe_listenlaenge(k, ("ereignisse", "liste"), ANZAHL_EREIGNISSE, "E")
    _pruefe_listenlaenge(k, ("defekte", "liste"), ANZAHL_DEFEKTE, "X")

    if len(k.hersteller) != ANZAHL_HERSTELLER:
        raise KonfigurationsFehler(
            f"{ANZAHL_HERSTELLER} Hersteller erwartet, {len(k.hersteller)} gefunden"
        )


def _pruefe_wirkungsmatrix(k: Konfiguration) -> None:
    bereiche = set(k.bereiche)
    if not bereiche:
        raise KonfigurationsFehler("[wirkungsmatrix] nennt keine Bereiche")
    minimum = k.wert("wirkungsmatrix", "gewicht_min")
    maximum = k.wert("wirkungsmatrix", "gewicht_max")

    for faehigkeit in k.faehigkeiten:
        unbekannt = set(faehigkeit.gewichte) - bereiche
        if unbekannt:
            raise KonfigurationsFehler(
                f"{faehigkeit.schluessel}: unbekannter Wirkungsbereich {sorted(unbekannt)}"
            )
        for bereich, gewicht in faehigkeit.gewichte.items():
            if not isinstance(gewicht, int) or not minimum <= gewicht <= maximum:
                raise KonfigurationsFehler(
                    f"{faehigkeit.schluessel}.{bereich}: Gewicht {gewicht!r} liegt "
                    f"ausserhalb von {minimum} bis {maximum}"
                )
        # GDD 8: "Jede Eigenschaft wirkt mindestens in einem Bereich."
        if not any(gewicht > 0 for gewicht in faehigkeit.gewichte.values()):
            raise KonfigurationsFehler(
                f"{faehigkeit.schluessel} wirkt in keinem Bereich"
            )

    # Jeder Bereich braucht mindestens eine wirkende Faehigkeit, sonst laesst
    # er sich nicht normieren (GDD 8: "innerhalb eines Bereichs normiert").
    for bereich in k.bereiche:
        if not any(f.gewicht(bereich) > 0 for f in k.faehigkeiten):
            raise KonfigurationsFehler(
                f"Wirkungsbereich {bereich!r}: keine Faehigkeit wirkt darauf"
            )


def _pruefe_tempo(k: Konfiguration) -> None:
    """Prueft das Geschwindigkeitsmodell (GDD 4 und 9)."""
    anteil = k.wert("tempo", "anteil_bei_null")
    if not 0.0 < anteil < 1.0:
        raise KonfigurationsFehler(
            f"tempo.anteil_bei_null muss zwischen 0 und 1 liegen, ist {anteil}"
        )
    if k.wert("tempo", "haftung_referenz") <= 0:
        raise KonfigurationsFehler("tempo.haftung_referenz muss groesser als 0 sein")

    # GDD 9: Die Endgeschwindigkeit ist getrennt bis 400 km/h skaliert.
    hoechst = k.wert("tempo", "hoechstgeschwindigkeit_bei_referenz_kmh")
    grenzwert = k.wert("kalibrierung", "endgeschwindigkeit_max_kmh")
    if hoechst != grenzwert:
        raise KonfigurationsFehler(
            f"tempo.hoechstgeschwindigkeit_bei_referenz_kmh ({hoechst}) und "
            f"kalibrierung.endgeschwindigkeit_max_kmh ({grenzwert}) muessen "
            "uebereinstimmen"
        )
    # Die Endgeschwindigkeit bei S = 0 ergibt sich aus der Kopplung an
    # anteil_bei_null und liegt damit zwangslaeufig darunter.

    # Die Verhaeltnisse muessen positiv sein, sonst faehrt niemand.
    for name in (
        "faktor_enge_kurve",
        "faktor_kurve",
        "faktor_bremsen",
        "faktor_beschleunigen",
    ):
        if k.wert("tempo", name) <= 0:
            raise KonfigurationsFehler(f"tempo.{name} muss groesser als 0 sein")

    referenzstrecke = k.wert("kalibrierung", "referenzstrecke")
    namen = {eintrag["name"] for eintrag in k.strecken}
    if referenzstrecke not in namen:
        raise KonfigurationsFehler(
            f"Referenzstrecke {referenzstrecke!r} steht nicht in der Streckenliste"
        )


def _pruefe_wetterprofile(k: Konfiguration) -> None:
    """Jede Strecke braucht genau ein Wetterprofil (Entscheidung zu Punkt 4)."""
    profile = k.wert("wetter", "profil", standard=None)
    if profile is None:
        return

    kette = set(k.wert("wetter", "kette"))
    zugeordnet: dict[str, str] = {}
    for name, profil in profile.items():
        if set(profil["gewichte"]) != kette:
            raise KonfigurationsFehler(
                f"Wetterprofil {name!r} deckt nicht alle Wetterlagen ab"
            )
        for strecke in profil["strecken"]:
            if strecke in zugeordnet:
                raise KonfigurationsFehler(
                    f"Strecke {strecke!r} steht in den Profilen {zugeordnet[strecke]!r} "
                    f"und {name!r}"
                )
            zugeordnet[strecke] = name

    namen = {eintrag["name"] for eintrag in k.strecken}
    ohne = namen - set(zugeordnet)
    if ohne:
        raise KonfigurationsFehler(f"Strecken ohne Wetterprofil: {sorted(ohne)}")
    unbekannt = set(zugeordnet) - namen
    if unbekannt:
        raise KonfigurationsFehler(f"Wetterprofil nennt unbekannte Strecken: {sorted(unbekannt)}")


def _pruefe_geldanteil(k: Konfiguration) -> None:
    mit_geld = [f.schluessel for f in k.faehigkeiten if f.hat_geldanteil]
    if len(mit_geld) != ANZAHL_MIT_GELDANTEIL:
        raise KonfigurationsFehler(
            f"GDD 9 nennt {ANZAHL_MIT_GELDANTEIL} Faehigkeiten mit Geldanteil, "
            f"gefunden sind {len(mit_geld)}: {mit_geld}"
        )


def _pruefe_strecken(k: Konfiguration) -> None:
    strecken = k.strecken
    if len(strecken) != ANZAHL_STRECKEN:
        raise KonfigurationsFehler(
            f"{ANZAHL_STRECKEN} Strecken erwartet, {len(strecken)} gefunden"
        )
    nummern = [strecke["nummer"] for strecke in strecken]
    if nummern != list(range(1, ANZAHL_STRECKEN + 1)):
        raise KonfigurationsFehler("Die Strecken sind nicht von 1 bis 20 durchnummeriert")

    enge_kurve = k.wert("strecke", "enge_kurve_radius_max_m")
    gerade = k.wert("strecke", "gerade_radius_min_m")
    if not enge_kurve < gerade:
        raise KonfigurationsFehler(
            "Der Radius der engen Kurve muss kleiner sein als der Radius der Geraden"
        )


def _pruefe_ligen(k: Konfiguration) -> None:
    anzahl = k.wert("ligen", "anzahl")
    if anzahl != ANZAHL_LIGEN:
        raise KonfigurationsFehler(f"{ANZAHL_LIGEN} Ligen erwartet, {anzahl} gefunden")

    abgedeckt: set[int] = set()
    for gruppe in k.wert("ligen", "namen"):
        abgedeckt.update(range(gruppe["von_liga"], gruppe["bis_liga"] + 1))
    fehlend = set(range(1, anzahl + 1)) - abgedeckt
    if fehlend:
        raise KonfigurationsFehler(f"Ohne Ligennamen: {sorted(fehlend)}")


def _pruefe_wetter(k: Konfiguration) -> None:
    kette = k.wert("wetter", "kette")
    zustaende = k.wert("wetter", "zustand")
    if len(kette) != ANZAHL_WETTERZUSTAENDE:
        raise KonfigurationsFehler(
            f"{ANZAHL_WETTERZUSTAENDE} Wetterzustaende erwartet, {len(kette)} gefunden"
        )
    fehlend = set(kette) - set(zustaende)
    if fehlend:
        raise KonfigurationsFehler(f"Wetterzustand ohne Werte: {sorted(fehlend)}")
    ueberzaehlig = set(zustaende) - set(kette)
    if ueberzaehlig:
        raise KonfigurationsFehler(f"Wetterzustand nicht in der Kette: {sorted(ueberzaehlig)}")

    wetterfaehigkeiten = k.wert("wetter", "faehigkeit", "liste")
    abgedeckt = {eintrag["wetter"] for eintrag in wetterfaehigkeiten}
    if abgedeckt != set(kette):
        raise KonfigurationsFehler(
            "Zu jedem Wetter gehoert genau eine Wetterfaehigkeit (GDD 7); "
            f"ohne Faehigkeit: {sorted(set(kette) - abgedeckt)}"
        )


def _pruefe_wertung(k: Konfiguration) -> None:
    punkte = k.wert("wertung", "punkte_rennen")
    if len(punkte) != ANZAHL_PUNKTERAENGE:
        raise KonfigurationsFehler(
            f"Punkte fuer {ANZAHL_PUNKTERAENGE} Plaetze erwartet, {len(punkte)} gefunden"
        )
    if any(davor < danach for davor, danach in zip(punkte, punkte[1:], strict=False)):
        raise KonfigurationsFehler("Die Rennpunkte muessen von Platz 1 an fallen")

    quali = k.wert("wertung", "punkte_qualifying")
    if len(quali) != 3:
        raise KonfigurationsFehler(
            f"Qualifying-Punkte fuer 3 Plaetze erwartet, {len(quali)} gefunden"
        )

    autos = k.wert("rennen", "autos")
    if len(punkte) > autos:
        raise KonfigurationsFehler(
            f"Mehr Punkteraenge ({len(punkte)}) als Autos im Rennen ({autos})"
        )


def _pruefe_listenlaenge(
    k: Konfiguration, pfad: tuple[str, ...], erwartet: int, praefix: str
) -> None:
    eintraege = k.wert(*pfad)
    name = "[" + ".".join(pfad) + "]"
    if len(eintraege) != erwartet:
        raise KonfigurationsFehler(
            f"{name}: {erwartet} Eintraege erwartet, {len(eintraege)} gefunden"
        )
    erwartete_schluessel = [f"{praefix}{nummer}" for nummer in range(1, erwartet + 1)]
    gefunden = [eintrag.get("schluessel") for eintrag in eintraege]
    if gefunden != erwartete_schluessel:
        raise KonfigurationsFehler(
            f"{name}: Schluessel muessen {praefix}1 bis {praefix}{erwartet} "
            "in dieser Reihenfolge sein"
        )
