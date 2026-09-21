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


def test_das_feld(k: kf.Konfiguration) -> None:
    """Punkt 101: 50 Autos, 25 Teams zu je zwei."""
    assert k.wert("rennen", "autos") == 50
    assert k.wert("teams", "anzahl") == 25
    assert k.wert("teams", "autos_je_team") == 2
    assert k.wert("hersteller", "anzahl") == 25


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
    """Punkt 101: eine feste Tabelle, je Platz ein Wert."""
    punkte = k.wert("wertung", "punkte_je_platz")
    assert len(punkte) == k.wert("rennen", "autos")
    assert punkte[:5] == [100, 90, 80, 76, 72]
    assert punkte[-1] == 1
    assert k.wert("wertung", "anteil_schnellste_runde") == 0.01
    assert k.wert("wertung", "anteil_qualifying") == [0.015, 0.005, 0.0025]


def test_die_tabelle_bleibt_bis_zum_letzten_platz_positiv(k: kf.Konfiguration) -> None:
    """Sonst faellt es erst mitten in einer Saison auf."""
    from rennmanager.kern import wertung as wt

    assert wt.rennpunkte(k, k.wert("rennen", "autos")) >= 1
    assert wt.rennpunkte(k, 1) == 100


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
    # Punkt 95: Die dritte Ebene faellt je Sektor, nicht je Runde.
    assert k.wert("zufall", "rundenform", "sigma") == 0.005
    assert k.wert("zufall", "rundenform", "je_sektor") is True
    assert k.wert("zufall", "rundenform", "verkleinert_durch") == "D12"
    assert k.wert("zufall", "rundenform", "kopplung", "bei_einem_platz") == 0.75


def test_defekte(k: kf.Konfiguration) -> None:
    assert len(k.wert("defekte", "liste")) == kf.ANZAHL_DEFEKTE
    assert k.wert("defekte", "max_gesamtmalus") == 0.50


def test_defekte_verweisen_auf_bekannte_upgrades(k: kf.Konfiguration) -> None:
    bekannt = {f.schluessel for f in k.fahrzeug}
    for defekt in k.wert("defekte", "liste"):
        for wirkung in defekt["wirkung"]:
            assert wirkung["ziel"] in bekannt, f"{defekt['schluessel']}: {wirkung['ziel']}"
            assert wirkung["faktor"] < 0, f"{defekt['schluessel']} muss ein Malus sein"


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
        ("unfaelle", "rate", "je_sekunde_in_reichweite"),
        ("defekte", "rate", "je_auto_und_rennen_bei_null"),
        ("reifen", "verschleiss", "verlauf"),
        ("reifen", "fluesterer", "max_daempfung"),
        ("reifen", "streckenfaktor", "grundlage"),
        ("ermuedung", "beginn_anteil_distanz"),
        ("streckenkenntnis", "anfang", "anteil"),
        ("feld", "spanne_rundenzeit"),
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


def test_kalibrierung_stuetzpunkte(k: kf.Konfiguration) -> None:
    """GDD 9: v(0) = 55, v(98.000) = 180, v(100.000) ~ 181,3 km/h."""
    assert _tempo(k, 0) == pytest.approx(k.wert("kalibrierung", "v_bei_0_kmh"))
    assert _tempo(k, k.wert("skala", "referenz")) == pytest.approx(
        k.wert("kalibrierung", "v_bei_referenz_kmh")
    )
    assert _tempo(k, k.wert("skala", "maximum")) == pytest.approx(
        k.wert("kalibrierung", "v_bei_maximum_kmh"), abs=0.05
    )


def test_die_feldgrenzen_stehen_auf_der_skala(k: kf.Konfiguration) -> None:
    """Punkt 101: Der Beste faehrt den Anker, der Letzte 4 % langsamer."""
    from rennmanager.kern.welt import feldgrenzen

    bester, letzter = feldgrenzen(k)
    assert bester == k.wert("skala", "referenz")
    assert letzter == 87_445
    spanne = _tempo(k, bester) / _tempo(k, letzter) - 1.0
    assert spanne == pytest.approx(k.wert("feld", "spanne_rundenzeit"), abs=0.0005)


def test_ein_falsches_s_letzter_faellt_auf(k: kf.Konfiguration) -> None:
    """Die Pruefung rechnet die Spanne aus der Kalibrierung nach."""
    import copy
    from dataclasses import replace

    roh = copy.deepcopy(k.roh)
    roh["feld"]["s_letzter"] = 80_000
    with pytest.raises(kf.KonfigurationsFehler, match="s_letzter"):
        kf._pruefe(replace(k, roh=roh))


def test_renndistanz(k: kf.Konfiguration) -> None:
    """Das Feld faehrt 290 km."""
    assert k.wert("rennen", "distanz_km") == 290


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
