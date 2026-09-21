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
from functools import cached_property
from pathlib import Path
from typing import Any

BALANCING_DATEI = "balancing.toml"
HERSTELLER_DATEI = "hersteller.toml"

# Vorgaben aus dem GDD, gegen die geprueft wird.
ANZAHL_FAHRZEUG_UPGRADES = 16       # GDD 5
ANZAHL_FAHRER_EIGENSCHAFTEN = 16    # GDD 6
ANZAHL_MIT_GELDANTEIL = 18          # GDD 9: "18 Faehigkeiten haben einen Geldanteil"
ANZAHL_STRECKEN = 20                # GDD 3
ANZAHL_HERSTELLER = 25              # GDD 12, seit Punkt 101 einer je Team
ANZAHL_DEFEKTE = 20                 # GDD 14
ANZAHL_WETTERZUSTAENDE = 5          # GDD 7
WAEHRUNGEN = {"G", "E", "Z"}        # Geld, Erfahrung, Zeit

# Wem eine Eigenschaft neben der Wirkungsmatrix gehoert.
TRAEGER_FAHRER = "fahrer"
TRAEGER_FAHRZEUG = "fahrzeug"


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

    @cached_property
    def zusatzeintraege(self) -> tuple[dict[str, Any], ...]:
        """Alle Eigenschaften neben der Wirkungsmatrix, mit ihren Angaben.

        Drei Quellen, eine Liste: die fuenf Wetterfaehigkeiten aus GDD 7,
        der Reifenfluesterer und die Eigenschaften aus
        ``[[zusatzfaehigkeit.liste]]``. Keine von ihnen hat eine Zeile in
        der Wirkungsmatrix; sie gehen deshalb nicht in den Durchschnitt
        der Basiseigenschaften ein (GDD 4) und lassen die Kalibrierung aus
        GDD 9 unberuehrt.

        ``traeger`` steht in jedem Eintrag, auch wenn die Quelle ihn nicht
        nennt: Wetterfaehigkeiten und Reifenfluesterer gehoeren dem Fahrer.
        """
        eintraege = list(self.wert("wetter", "faehigkeit", "liste"))
        fluesterer = self.wert("reifen", "fluesterer", standard=None)
        if fluesterer and fluesterer.get("schluessel"):
            eintraege.append(fluesterer)
        eintraege.extend(self.wert("zusatzfaehigkeit", "liste", standard=[]))
        return tuple(
            {**eintrag, "traeger": eintrag.get("traeger", TRAEGER_FAHRER)}
            for eintrag in eintraege
        )

    @property
    def zusatzfaehigkeiten(self) -> tuple[str, ...]:
        """Die Schluessel aller Eigenschaften neben der Wirkungsmatrix."""
        return tuple(eintrag["schluessel"] for eintrag in self.zusatzeintraege)

    def zusatzeintrag(self, schluessel: str) -> dict[str, Any]:
        """Die Angaben zu einer Eigenschaft neben der Matrix."""
        for eintrag in self.zusatzeintraege:
            if eintrag["schluessel"] == schluessel:
                return eintrag
        raise KeyError(schluessel)

    @cached_property
    def fahrzeugzusatz(self) -> frozenset[str]:
        """Die Eigenschaften neben der Matrix, die dem Fahrzeug gehoeren.

        Sie traegt die Tagesform nicht (GDD 11 nennt nur Fahrerwerte) und
        sie belegen den Werkstattplatz, nicht den Fahrerplatz (GDD 2).
        """
        return frozenset(
            eintrag["schluessel"]
            for eintrag in self.zusatzeintraege
            if eintrag["traeger"] == TRAEGER_FAHRZEUG
        )

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
    _pruefe_feld(k)
    _pruefe_wetter(k)
    _pruefe_wertung(k)
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


def _pruefe_feld(k: Konfiguration) -> None:
    """Prueft die Spanne des Feldes gegen die Kalibrierung (Punkt 101).

    Der Beste faehrt den Ankerwert, der Letzte eine um
    ``spanne_rundenzeit`` laengere Runde. Weil jede Grenze des
    Tempomodells linear im Leistungsanteil ``p = sqrt(S / referenz)``
    steht, ist die Rundenzeit umgekehrt proportional dazu - ``s_letzter``
    laesst sich damit aus der Spanne ausrechnen. Stimmen die beiden Zahlen
    in der Konfiguration nicht ueberein, hat jemand an einer gedreht und
    an der anderen nicht.
    """
    bester = float(k.wert("feld", "s_bester"))
    letzter = float(k.wert("feld", "s_letzter"))
    referenz = float(k.wert("skala", "referenz"))
    maximum = float(k.wert("skala", "maximum"))
    if not 0 < letzter < bester <= maximum:
        raise KonfigurationsFehler(
            f"Das Feld braucht 0 < s_letzter ({letzter:.0f}) < s_bester "
            f"({bester:.0f}) <= Skalenmaximum ({maximum:.0f})"
        )

    basis = float(k.wert("kalibrierung", "basis_kmh"))
    spanne_kmh = float(k.wert("kalibrierung", "spanne_kmh"))
    spanne = float(k.wert("feld", "spanne_rundenzeit"))
    if not 0 < spanne < 1:
        raise KonfigurationsFehler(
            f"spanne_rundenzeit muss zwischen 0 und 1 liegen, gefunden {spanne}"
        )
    v_bester = basis + spanne_kmh * (bester / referenz) ** 0.5
    p_letzter = (v_bester / (1.0 + spanne) - basis) / spanne_kmh
    erwartet = round(p_letzter * p_letzter * referenz)
    if erwartet != int(letzter):
        raise KonfigurationsFehler(
            f"Bei {spanne:.1%} Rundenzeitspanne gehoert s_letzter auf {erwartet}, "
            f"in der Konfiguration steht {int(letzter)}"
        )

    autos = k.wert("rennen", "autos")
    teams = k.wert("teams", "anzahl")
    je_team = k.wert("teams", "autos_je_team")
    if teams * je_team != autos:
        raise KonfigurationsFehler(
            f"{teams} Teams zu je {je_team} Autos ergeben {teams * je_team}, "
            f"im Rennen stehen {autos}"
        )


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
    """Prueft die Punktetabelle aus Punkt 101.

    Sie muss fuer jeden Platz des Feldes einen Wert nennen, von Platz 1 an
    fallen und nirgends unter 1 rutschen - sonst faellt das erst mitten in
    einer Saison auf.
    """
    autos = k.wert("rennen", "autos")
    punkte = list(k.wert("wertung", "punkte_je_platz"))
    if len(punkte) != autos:
        raise KonfigurationsFehler(
            f"Die Punktetabelle nennt {len(punkte)} Plaetze, im Rennen stehen {autos}"
        )
    if any(davor <= danach for davor, danach in zip(punkte, punkte[1:], strict=False)):
        raise KonfigurationsFehler("Die Rennpunkte muessen von Platz 1 an fallen")
    if punkte[-1] < 1:
        raise KonfigurationsFehler(
            f"Der Letzte bekaeme {punkte[-1]} Punkte; die Tabelle endet bei mindestens 1"
        )

    quali = k.wert("wertung", "anteil_qualifying")
    if not quali:
        raise KonfigurationsFehler("Ohne Qualifying-Anteile gibt es keine Polepunkte")
    if any(davor < danach for davor, danach in zip(quali, quali[1:], strict=False)):
        raise KonfigurationsFehler("Die Qualifying-Anteile muessen von Platz 1 an fallen")
    if len(quali) > autos:
        raise KonfigurationsFehler(
            f"Mehr Qualifying-Raenge ({len(quali)}) als Autos im Rennen ({autos})"
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
