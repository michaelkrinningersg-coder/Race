"""Tests fuer das Auto und die Wirkungsmatrix (GDD 5, 6, 8)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern.auto import Auto, AutoFehler


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


def test_gleichverteiltes_auto_hat_ueberall_denselben_bereichswert(k) -> None:
    """Grundlage der Kalibrierung: bei gleichen Werten ist jedes gewichtete
    Mittel genau dieser Wert, unabhaengig von den Gewichten."""
    auto = ka.gleichverteilt(k, 42_000)
    for bereich in k.bereiche:
        assert ka.bereichswert(k, auto, bereich) == pytest.approx(42_000)


def test_bereichswert_ist_gewichtetes_mittel(k) -> None:
    """Auf 'g' wirken laut GDD 8 F1 (3), F3 (1), F4 (3), F6 (3) und D7 (2)."""
    auto = ka.gleichverteilt(k, 0)
    werte = dict(auto.werte)
    werte["F1"] = 12_000
    auto = Auto(auto.kuerzel, auto.name, werte)

    gewichte = {f.schluessel: f.gewicht("g") for f in k.faehigkeiten if f.gewicht("g")}
    erwartet = 3 * 12_000 / sum(gewichte.values())
    assert ka.bereichswert(k, auto, "g") == pytest.approx(erwartet)


def test_faehigkeit_wirkt_nur_in_ihren_bereichen(k) -> None:
    """F1 Motorleistung wirkt laut GDD 8 auf g, bplus und q - sonst nirgends."""
    werte = {f.schluessel: 0 for f in k.faehigkeiten}
    werte["F1"] = 100_000
    auto = Auto("TST", "Test", werte)

    betroffen = {b for b in k.bereiche if ka.bereichswert(k, auto, b) > 0}
    assert betroffen == {"g", "bplus", "q"}


def test_gesamtwert_ist_ungewichtetes_mittel(k) -> None:
    """GDD 4 braucht ihn beim Gleichstand auf die Millisekunde."""
    assert ka.gesamtwert(k, ka.gleichverteilt(k, 7_500)) == pytest.approx(7_500)

    werte = {f.schluessel: 0 for f in k.faehigkeiten}
    werte["F1"] = 32_000
    assert ka.gesamtwert(k, Auto("TST", "Test", werte)) == pytest.approx(1_000)


def test_unbekannter_bereich_meldet_fehler(k) -> None:
    with pytest.raises(AutoFehler, match="Wirkungsbereich"):
        ka.bereichswert(k, ka.gleichverteilt(k, 0), "xy")


def test_fehlende_faehigkeit_meldet_fehler(k) -> None:
    werte = {f.schluessel: 0 for f in k.faehigkeiten}
    del werte["D7"]
    with pytest.raises(AutoFehler, match="fehlen"):
        ka.pruefe(k, Auto("TST", "Test", werte))


def test_unbekannte_faehigkeit_meldet_fehler(k) -> None:
    werte = {f.schluessel: 0 for f in k.faehigkeiten}
    werte["F99"] = 0
    with pytest.raises(AutoFehler, match="unbekannte"):
        ka.pruefe(k, Auto("TST", "Test", werte))


@pytest.mark.parametrize("wert", [-1, 100_001])
def test_wert_ausserhalb_der_skala_meldet_fehler(k, wert: int) -> None:
    werte = {f.schluessel: 0 for f in k.faehigkeiten}
    werte["F1"] = wert
    with pytest.raises(AutoFehler, match="ausserhalb"):
        ka.pruefe(k, Auto("TST", "Test", werte))


def test_gleichverteiltes_auto_ist_gueltig(k) -> None:
    for s in (0, 1, 50_000, 100_000):
        ka.pruefe(k, ka.gleichverteilt(k, s))
