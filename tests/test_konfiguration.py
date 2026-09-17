"""Tests fuer die Balancing-Konfiguration.

Zwei Arten von Pruefungen:

1. Struktur - laedt die Datei und entspricht sie den Vorgaben des GDD?
2. Zahlen - reproduzieren die hinterlegten Konstanten die Kontrolltabellen
   aus GDD 9? Die Formeln stehen hier nur zur Pruefung der Konfiguration;
   der Simulationskern setzt sie spaeter selbst um.
"""

from __future__ import annotations

import math
import tomllib

import pytest

from rennmanager import konfiguration as kf


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


# -- Struktur ---------------------------------------------------------------
def test_konfiguration_laedt(k: kf.Konfiguration) -> None:
    assert k.wert("gdd_version") == "1.0"
    assert k.wert("schema_version") == 1


def test_anzahl_faehigkeiten(k: kf.Konfiguration) -> None:
    assert len(k.fahrzeug) == kf.ANZAHL_FAHRZEUG_UPGRADES
    assert len(k.fahrer) == kf.ANZAHL_FAHRER_EIGENSCHAFTEN
    assert [f.schluessel for f in k.fahrzeug] == [f"F{n}" for n in range(1, 17)]
    assert [f.schluessel for f in k.fahrer] == [f"D{n}" for n in range(1, 17)]


def test_achtzehn_faehigkeiten_mit_geldanteil(k: kf.Konfiguration) -> None:
    """GDD 9: '18 Faehigkeiten haben einen Geldanteil'."""
    mit_geld = [f.schluessel for f in k.faehigkeiten if f.hat_geldanteil]
    assert len(mit_geld) == kf.ANZAHL_MIT_GELDANTEIL
    # Alle 16 Fahrzeug-Upgrades plus D3 Fitness und D16 Mentale Staerke.
    assert set(mit_geld) == {f"F{n}" for n in range(1, 17)} | {"D3", "D16"}


def test_wirkungsmatrix_stichproben(k: kf.Konfiguration) -> None:
    """Stichproben gegen die Tabellen in GDD 8."""
    assert k.faehigkeit("F1").gewicht("g") == 3
    assert k.faehigkeit("F1").gewicht("bplus") == 2
    assert k.faehigkeit("F1").gewicht("q") == 3
    assert k.faehigkeit("F1").gewicht("k") == 0
    assert k.faehigkeit("F13").gewicht("ek") == 3
    assert k.faehigkeit("D5").gewicht("ek") == 3
    assert k.faehigkeit("D15").gewicht("q") == 3
    assert k.faehigkeit("D16").gewicht("fe") == 1


def test_jeder_bereich_hat_wirkende_faehigkeiten(k: kf.Konfiguration) -> None:
    for bereich in k.bereiche:
        wirkend = [f.schluessel for f in k.faehigkeiten if f.gewicht(bereich) > 0]
        assert wirkend, f"Bereich {bereich} ohne wirkende Faehigkeit"


def test_ligennamen(k: kf.Konfiguration) -> None:
    """GDD 12: Platin/Gold/Silber/Bronze mit je 5 Stufen, Startliga Bronze 5."""
    assert k.ligenname(1) == "Platin 1"
    assert k.ligenname(5) == "Platin 5"
    assert k.ligenname(6) == "Gold 1"
    assert k.ligenname(11) == "Silber 1"
    assert k.ligenname(16) == "Bronze 1"
    assert k.ligenname(20) == "Bronze 5"
    assert k.ligenname(k.wert("ligen", "startliga")) == "Bronze 5"


def test_strecken(k: kf.Konfiguration) -> None:
    assert len(k.strecken) == kf.ANZAHL_STRECKEN
    namen = [strecke["name"] for strecke in k.strecken]
    assert namen[0] == "Sakhir"
    assert namen[-1] == "Yas Marina"
    # GDD 16: Monaco, Imola und Mugello sind bewusst nicht dabei.
    assert not {"Monaco", "Imola", "Mugello"} & set(namen)


def test_segmentgrenzen(k: kf.Konfiguration) -> None:
    """GDD 3: enge Kurve < 60 m, Kurve 60-300 m, Gerade >= 300 m."""
    assert k.wert("strecke", "enge_kurve_radius_max_m") == 60.0
    assert k.wert("strecke", "gerade_radius_min_m") == 300.0
    assert k.wert("strecke", "abtastabstand_m") == 5.0
    assert k.wert("strecke", "ueberholzone_mindestlaenge_m") == 100.0
    assert k.wert("strecke", "sektoren") == 4


def test_ueberholbedingungen(k: kf.Konfiguration) -> None:
    """GDD 4: Abstand < 0,05 s und mindestens 2 km/h Tempovorteil."""
    assert k.wert("ueberholen", "max_abstand_s") == 0.05
    assert k.wert("ueberholen", "min_tempovorteil_kmh") == 2.0
    assert k.wert("unfaelle", "max_abstand_m") == 30.0
    assert k.wert("unfaelle", "ausfaelle_max") == 5


def test_punkte(k: kf.Konfiguration) -> None:
    """GDD 13: 40-35-30-25-20-18-... fuer die Plaetze 1 bis 20."""
    punkte = k.wert("wertung", "punkte_rennen")
    assert punkte == [40, 35, 30, 25, 20, 18, 16, 14, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    assert k.wert("wertung", "punkte_schnellste_runde") == 3
    assert k.wert("wertung", "punkte_qualifying") == [5, 3, 1]


def test_wetterzustaende(k: kf.Konfiguration) -> None:
    """GDD 7: 5 Zustaende, Grip-Faktoren wie in der Tabelle."""
    zustand = k.wert("wetter", "zustand")
    assert zustand["trocken"]["grip"] == 1.00
    assert zustand["heiss"]["grip"] == 0.97
    assert zustand["regen"]["grip"] == 0.85
    assert zustand["starkregen"]["grip"] == 0.72
    assert zustand["wechselhaft"]["grip_min"] == 0.90
    assert zustand["wechselhaft"]["grip_max"] == 1.00
    # GDD 7: Die Kette ist nach Naesse geordnet, nicht nach Grip - Heiss
    # liegt mit 0,97 unter Trocken. Ein Wechsel geht immer nur um eine Stufe.
    assert k.wert("wetter", "kette") == [
        "starkregen",
        "regen",
        "wechselhaft",
        "trocken",
        "heiss",
    ]
    assert k.wert("wetter", "wechsel_min") == 0
    assert k.wert("wetter", "wechsel_max") == 3
    assert k.wert("wetter", "wechsel_schrittweite") == 1


def test_zufallsebenen(k: kf.Konfiguration) -> None:
    """GDD 11: drei Ebenen mit Streuung und Grenze."""
    assert k.wert("zufall", "tagesform", "sigma") == 0.03
    assert k.wert("zufall", "tagesform", "grenze") == 0.08
    assert k.wert("zufall", "eigenschaft", "sigma") == 0.02
    assert k.wert("zufall", "eigenschaft", "grenze") == 0.05
    assert k.wert("zufall", "rundenform", "sigma") == 0.003
    assert k.wert("zufall", "rundenform", "verkleinert_durch") == "D12"


def test_ereignisse_und_defekte(k: kf.Konfiguration) -> None:
    assert len(k.wert("ereignisse", "liste")) == kf.ANZAHL_EREIGNISSE
    assert len(k.wert("defekte", "liste")) == kf.ANZAHL_DEFEKTE
    assert k.wert("defekte", "max_gesamtmalus") == 0.50


def test_defekte_verweisen_auf_bekannte_upgrades(k: kf.Konfiguration) -> None:
    bekannt = {f.schluessel for f in k.fahrzeug}
    for defekt in k.wert("defekte", "liste"):
        for wirkung in defekt["wirkung"]:
            assert wirkung["ziel"] in bekannt, f"{defekt['schluessel']}: {wirkung['ziel']}"
            assert wirkung["faktor"] < 0, f"{defekt['schluessel']} muss ein Malus sein"


def test_ereignisse_verweisen_auf_bekannte_ziele(k: kf.Konfiguration) -> None:
    faehigkeiten = {f.schluessel for f in k.faehigkeiten}
    wetterfaehigkeiten = {
        eintrag["schluessel"] for eintrag in k.wert("wetter", "faehigkeit", "liste")
    }
    sonstige = {
        "fahrertraining",
        "tagesform_mittelwert",
        "geld",
        "erfahrung",
        "streckenkenntnis_naechste",
        "kalendertage",
    }
    erlaubt = faehigkeiten | wetterfaehigkeiten | sonstige
    for ereignis in k.wert("ereignisse", "liste"):
        for wirkung in ereignis["wirkung"]:
            assert wirkung["ziel"] in erlaubt, f"{ereignis['schluessel']}: {wirkung['ziel']}"


def test_hersteller(k: kf.Konfiguration) -> None:
    assert len(k.hersteller) == kf.ANZAHL_HERSTELLER
    assert len({h.name for h in k.hersteller}) == kf.ANZAHL_HERSTELLER
    assert all(h.farbe.startswith("#") and len(h.farbe) == 7 for h in k.hersteller)


def test_offene_punkte_sind_dokumentiert(k: kf.Konfiguration) -> None:
    """Luecken im GDD stehen unter [offen] und werden nicht erfunden.

    Seit dem 2026-09-17 sind alle 20 Punkte entschieden, der Abschnitt ist
    also leer. Kommt spaeter ein Punkt hinzu, muss er beschrieben sein.
    """
    assert all(isinstance(text, str) and text for text in k.offene_punkte.values())


def test_entscheidungen_stehen_in_der_konfiguration(k: kf.Konfiguration) -> None:
    """Die 20 Entscheidungen aus OFFENE_PUNKTE.md sind hinterlegt."""
    for pfad in (
        ("ueberholschwierigkeit", "grundlage"),
        ("ueberholen", "erfolg", "form"),
        ("wetter", "profil"),
        ("wetter", "naesse", "verzoegerung_runden"),
        ("fehler", "rate_bei_null"),
        ("unfaelle", "rate", "je_annaeherung"),
        ("defekte", "rate", "je_auto_und_rennen_bei_null"),
        ("reifen", "verschleiss", "verlauf"),
        ("reifen", "streckenfaktor", "grundlage"),
        ("ermuedung", "beginn_anteil_distanz"),
        ("preisgeld", "interpolation", "verfahren"),
        ("preisgeld", "anteil_kurve", "verfahren"),
        ("preisgeld", "startgeld", "anteil_siegpraemie"),
        ("erfahrung", "betraege", "grundbetrag_je_session"),
        ("erfahrung", "wetter", "betrag", "je_km_anteil_sieg_ep"),
        ("kosten", "k0_faktor", "verfahren"),
        ("defekte", "reparatur", "anteil_siegpraemie_je_stufe"),
        ("sponsoren", "betraege", "grundbetrag_alle_plaetze"),
        ("ereignisse", "betraege", "E7"),
    ):
        assert k.wert(*pfad) is not None, " -> ".join(pfad)


def test_jede_strecke_hat_genau_ein_wetterprofil(k: kf.Konfiguration) -> None:
    profile = k.wert("wetter", "profil")
    zugeordnet = [name for profil in profile.values() for name in profil["strecken"]]
    assert sorted(zugeordnet) == sorted(eintrag["name"] for eintrag in k.strecken)
    for name, profil in profile.items():
        assert sum(profil["gewichte"].values()) == 100, name


def test_geschwindigkeitsmodell_ist_hinterlegt(k: kf.Konfiguration) -> None:
    """Die drei gefitteten Konstanten und die festen Verhaeltnisse."""
    assert k.wert("tempo", "haftung_referenz") > 0
    assert 0.0 < k.wert("tempo", "anteil_bei_null") < 1.0
    # Die Endgeschwindigkeit bei S = 0 wird gekoppelt, nicht hinterlegt.
    assert "hoechstgeschwindigkeit_basis_kmh" not in k.wert("tempo")
    assert k.wert("tempo", "hoechstgeschwindigkeit_bei_referenz_kmh") == 400.0
    # Bremsen kann mehr als Querhaftung, Beschleunigen weniger, enge Kurven
    # bieten weniger als schnelle.
    assert k.wert("tempo", "faktor_bremsen") > k.wert("tempo", "faktor_kurve")
    assert k.wert("tempo", "faktor_beschleunigen") < k.wert("tempo", "faktor_kurve")
    assert k.wert("tempo", "faktor_enge_kurve") < k.wert("tempo", "faktor_kurve")


# -- Zahlen: Kontrolltabellen aus GDD 9 -------------------------------------
def _tempo(k: kf.Konfiguration, s: float) -> float:
    """v(S) = basis + spanne * sqrt(S / referenz)."""
    basis = k.wert("kalibrierung", "basis_kmh")
    spanne = k.wert("kalibrierung", "spanne_kmh")
    referenz = k.wert("skala", "referenz")
    return basis + spanne * math.sqrt(s / referenz)


def _kosten(k: kf.Konfiguration, s: float) -> float:
    """K(S) = k0 * (1 + S / teiler) ^ exponent."""
    return k.wert("kosten", "k0_geld") * (
        1 + s / k.wert("kosten", "teiler")
    ) ** k.wert("kosten", "exponent")


def test_kalibrierung_stuetzpunkte(k: kf.Konfiguration) -> None:
    """GDD 9: v(0) = 55, v(98.000) = 180, v(100.000) ~ 181,3 km/h."""
    assert _tempo(k, 0) == pytest.approx(k.wert("kalibrierung", "v_bei_0_kmh"))
    assert _tempo(k, k.wert("skala", "referenz")) == pytest.approx(
        k.wert("kalibrierung", "v_bei_referenz_kmh")
    )
    assert _tempo(k, k.wert("skala", "maximum")) == pytest.approx(
        k.wert("kalibrierung", "v_bei_maximum_kmh"), abs=0.05
    )


def test_kalibrierung_reproduziert_die_ligatabelle(k: kf.Konfiguration) -> None:
    """Die S-Werte aus GDD 9 ergeben die dort genannten Geschwindigkeiten."""
    for zeile in k.wert("ligen", "kontrolle"):
        assert _tempo(k, zeile["s_bester"]) == pytest.approx(
            zeile["bester_kmh"], abs=0.05
        ), f"Liga {zeile['liga']} Bester"
        assert _tempo(k, zeile["s_letzter"]) == pytest.approx(
            zeile["letzter_kmh"], abs=0.05
        ), f"Liga {zeile['liga']} Letzter"


def test_ligastufen_haben_den_richtigen_abstand(k: kf.Konfiguration) -> None:
    """GDD 9: +6,32 km/h je Liga, Ueberlappung 0,3 km/h, Feldbreite 6,62 km/h."""
    bester20 = k.wert("ligen", "bester_liga20_kmh")
    zuwachs = k.wert("ligen", "zuwachs_je_liga_kmh")
    ueberlappung = k.wert("ligen", "ueberlappung_kmh")

    def bester(liga: int) -> float:
        return bester20 + zuwachs * (20 - liga)

    def letzter(liga: int) -> float:
        if liga == 20:
            return k.wert("ligen", "letzter_liga20_kmh")
        return bester(liga + 1) - ueberlappung

    for zeile in k.wert("ligen", "kontrolle"):
        liga = zeile["liga"]
        assert bester(liga) == pytest.approx(zeile["bester_kmh"], abs=0.05)
        assert letzter(liga) == pytest.approx(zeile["letzter_kmh"], abs=0.05)

    # Feldbreite: zwischen dem Besten und dem Letzten derselben Liga
    assert bester(10) - letzter(10) == pytest.approx(6.62, abs=0.01)


def test_kosten_reproduzieren_die_tabelle(k: kf.Konfiguration) -> None:
    """GDD 9: naechster Schritt 55 EUR bei S = 157 bis 790 EUR bei S = 98.130."""
    for zeile in k.wert("kosten", "kontrolle"):
        assert _kosten(k, zeile["s"]) == pytest.approx(
            zeile["naechster_schritt_euro"], rel=0.02
        ), zeile["bezeichnung"]


def test_kostensumme_reproduziert_die_tabelle(k: kf.Konfiguration) -> None:
    """Die Summe aller +10-Schritte ab 0 trifft die Werte aus GDD 9."""
    schritt = k.wert("zeitmodell", "kaufschritt")
    for zeile in k.wert("kosten", "kontrolle"):
        summe = sum(_kosten(k, s) for s in range(0, zeile["s"], schritt))
        assert summe == pytest.approx(zeile["summe_ab_0_euro"], rel=0.03), zeile[
            "bezeichnung"
        ]


def test_renndistanz(k: kf.Konfiguration) -> None:
    """GDD 4: Liga 20 = 100 km, je Liga +10 km, Liga 1 = 290 km."""
    basis = k.wert("rennen", "distanz_liga20_km")
    zuwachs = k.wert("rennen", "distanz_zuwachs_je_liga_km")
    assert basis == 100
    assert basis + zuwachs * (20 - 1) == 290


# -- Fehlermeldungen --------------------------------------------------------
def test_fehlendes_verzeichnis_meldet_fehler(tmp_path) -> None:
    with pytest.raises(kf.KonfigurationsFehler, match="fehlt"):
        kf.lade(tmp_path)


def test_falsche_anzahl_upgrades_meldet_fehler(tmp_path) -> None:
    quelle = kf.konfigurationsverzeichnis()
    text = (quelle / kf.BALANCING_DATEI).read_text(encoding="utf-8")
    # F16 entfernen: der letzte [[fahrzeug]]-Block vor [[fahrer]]
    beschnitten = text.replace(
        '[[fahrzeug]]\nschluessel = "F16"', '[[unbenutzt]]\nschluessel = "F16"'
    )
    (tmp_path / kf.BALANCING_DATEI).write_text(beschnitten, encoding="utf-8")
    (tmp_path / kf.HERSTELLER_DATEI).write_text(
        (quelle / kf.HERSTELLER_DATEI).read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(kf.KonfigurationsFehler, match="16 Eintraege erwartet"):
        kf.lade(tmp_path)


def test_unbekannter_wirkungsbereich_meldet_fehler(tmp_path) -> None:
    quelle = kf.konfigurationsverzeichnis()
    text = (quelle / kf.BALANCING_DATEI).read_text(encoding="utf-8")
    text = text.replace("gewichte = { g = 3, bplus = 2, q = 3 }", "gewichte = { xy = 3 }")
    (tmp_path / kf.BALANCING_DATEI).write_text(text, encoding="utf-8")
    (tmp_path / kf.HERSTELLER_DATEI).write_text(
        (quelle / kf.HERSTELLER_DATEI).read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(kf.KonfigurationsFehler, match="Wirkungsbereich"):
        kf.lade(tmp_path)


def test_kaputtes_toml_meldet_fehler(tmp_path) -> None:
    (tmp_path / kf.BALANCING_DATEI).write_text("das ist [kein toml", encoding="utf-8")
    with pytest.raises(kf.KonfigurationsFehler, match="gueltiges TOML"):
        kf.lade(tmp_path)


def test_dateien_sind_gueltiges_toml() -> None:
    ordner = kf.konfigurationsverzeichnis()
    for name in (kf.BALANCING_DATEI, kf.HERSTELLER_DATEI):
        with (ordner / name).open("rb") as datei:
            assert tomllib.load(datei)
