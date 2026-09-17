"""Tests fuer das Zufallssystem (GDD 11)."""

from __future__ import annotations

import statistics

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import form as fm
from rennmanager.kern.auto import Auto
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


def mit_wert(k, schluessel: str, wert: int, grund: int = 50_000) -> Auto:
    werte = {f.schluessel: grund for f in k.faehigkeiten}
    werte[schluessel] = wert
    return Auto("TST", "Test", werte)


# -- Tagesform --------------------------------------------------------------
def test_tagesform_liegt_in_der_grenze(k) -> None:
    """GDD 11: Streuung 3 %, begrenzt auf +/- 8 %."""
    grenze = k.wert("zufall", "tagesform", "grenze")
    auto = ka.gleichverteilt(k, 50_000)
    for seed in range(500):
        faktor = fm.tagesform(k, auto, Seedquelle(seed))
        assert 1.0 - grenze <= faktor <= 1.0 + grenze


def test_tagesform_streut_wie_vorgegeben(k) -> None:
    einstellung = k.wert("zufall", "tagesform")
    # Ohne D16 wird nichts gedaempft, die Streuung bleibt unveraendert.
    auto = mit_wert(k, "D16", 0)
    werte = [fm.tagesform(k, auto, Seedquelle(seed)) for seed in range(2_000)]
    assert statistics.mean(werte) == pytest.approx(1.0, abs=0.005)
    assert statistics.stdev(werte) == pytest.approx(einstellung["sigma"], rel=0.1)


def test_mentale_staerke_daempft_nur_die_schlechte_seite(k) -> None:
    """GDD 11: D16 begrenzt nur die negative Seite der Tagesform."""
    schwach = mit_wert(k, "D16", 0)
    stark = mit_wert(k, "D16", 100_000)

    schlecht_schwach, schlecht_stark, gut_schwach, gut_stark = [], [], [], []
    for seed in range(600):
        a = fm.tagesform(k, schwach, Seedquelle(seed))
        b = fm.tagesform(k, stark, Seedquelle(seed))
        (schlecht_schwach if a < 1 else gut_schwach).append(a)
        (schlecht_stark if b < 1 else gut_stark).append(b)

    # Schlechte Tage fallen mit starker Psyche milder aus ...
    assert statistics.mean(schlecht_stark) > statistics.mean(schlecht_schwach)
    # ... gute Tage bleiben unberuehrt.
    assert statistics.mean(gut_stark) == pytest.approx(statistics.mean(gut_schwach), abs=1e-9)


# -- Eigenschafts-Zufall ----------------------------------------------------
def test_eigenschaftszufall_bleibt_in_der_grenze(k) -> None:
    """GDD 11: Streuung 2 %, begrenzt auf +/- 5 % - dazu die Tagesform."""
    grenze_wert = k.wert("zufall", "eigenschaft", "grenze")
    grenze_tag = k.wert("zufall", "tagesform", "grenze")
    grund = 50_000
    auto = ka.gleichverteilt(k, grund)

    for seed in range(200):
        gewuerfelt = fm.wuerfle(k, auto, Seedquelle(seed)).auto
        for f in k.faehigkeiten:
            spanne = (1 + grenze_wert) * (1 + grenze_tag) if f.schluessel.startswith("D") else (
                1 + grenze_wert
            )
            assert gewuerfelt.wert(f.schluessel) <= grund * spanne + 1


def test_tagesform_traegt_nur_die_fahrerwerte(k) -> None:
    """GDD 11: 'Ein Faktor auf alle Fahrerwerte' - nicht auf das Fahrzeug."""
    grund = 50_000
    auto = ka.gleichverteilt(k, grund)
    # Ueber viele Wuerfe muessen die Fahrerwerte der Tagesform folgen,
    # die Fahrzeugwerte nicht.
    fahrer, fahrzeug, formen = [], [], []
    for seed in range(400):
        ergebnis = fm.wuerfle(k, auto, Seedquelle(seed))
        formen.append(ergebnis.tagesform)
        fahrer.append(statistics.mean(ergebnis.auto.wert(f"D{n}") for n in range(1, 17)))
        fahrzeug.append(statistics.mean(ergebnis.auto.wert(f"F{n}") for n in range(1, 17)))

    # Der Zusammenhang mit der Tagesform ist bei den Fahrerwerten stark ...
    assert statistics.correlation(formen, fahrer) > 0.9
    # ... und bei den Fahrzeugwerten praktisch nicht vorhanden.
    assert abs(statistics.correlation(formen, fahrzeug)) < 0.2


def test_werte_bleiben_auf_der_skala(k) -> None:
    kleinster = k.wert("skala", "minimum")
    groesster = k.wert("skala", "maximum")
    for grund in (0, 100_000):
        auto = ka.gleichverteilt(k, grund)
        for seed in range(50):
            gewuerfelt = fm.wuerfle(k, auto, Seedquelle(seed)).auto
            for f in k.faehigkeiten:
                assert kleinster <= gewuerfelt.wert(f.schluessel) <= groesster


def test_wetterfaehigkeiten_werden_mitgewuerfelt(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    gewuerfelt = fm.wuerfle(k, auto, Seedquelle(1)).auto
    assert set(gewuerfelt.wetterwerte) == set(auto.wetterwerte)
    assert gewuerfelt.wetterwerte != auto.wetterwerte


def test_qualifying_und_rennen_wuerfeln_getrennt(k) -> None:
    """GDD 11: vor Qualifying und erneut vor dem Rennen."""
    auto = ka.gleichverteilt(k, 50_000)
    haupt = Seedquelle(4711)
    quali = fm.wuerfle(k, auto, haupt.zweig("qualifying"))
    rennen = fm.wuerfle(k, auto, haupt.zweig("rennen"))
    assert quali.tagesform != rennen.tagesform
    assert quali.auto.werte != rennen.auto.werte


def test_gleicher_seed_gleicher_wurf(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    erste = fm.wuerfle(k, auto, Seedquelle(9))
    zweite = fm.wuerfle(k, auto, Seedquelle(9))
    assert erste.auto.werte == zweite.auto.werte
    assert erste.tagesform == zweite.tagesform


# -- Rundenform -------------------------------------------------------------
def test_rundenform_streut_wie_vorgegeben(k) -> None:
    """GDD 11: Streuung 0,3 % auf die Rundenzeit."""
    sigma = k.wert("zufall", "rundenform", "sigma")
    auto = mit_wert(k, "D12", 0)
    werte = [fm.rundenform(k, auto, Seedquelle(seed), 1) for seed in range(2_000)]
    assert statistics.mean(werte) == pytest.approx(1.0, abs=0.001)
    assert statistics.stdev(werte) == pytest.approx(sigma, rel=0.1)


def test_konstanz_verkleinert_die_streuung(k) -> None:
    """GDD 11: 'verkleinert durch D12 Konstanz'."""
    schwach = mit_wert(k, "D12", 0)
    stark = mit_wert(k, "D12", 100_000)
    streuung_schwach = statistics.stdev(
        fm.rundenform(k, schwach, Seedquelle(seed), 1) for seed in range(1_000)
    )
    streuung_stark = statistics.stdev(
        fm.rundenform(k, stark, Seedquelle(seed), 1) for seed in range(1_000)
    )
    assert streuung_stark < streuung_schwach

    max_anteil = k.wert("zufall", "rundenform", "daempfung", "max_anteil")
    assert streuung_stark == pytest.approx(streuung_schwach * (1 - max_anteil), rel=0.15)


def test_jede_runde_wird_neu_gewuerfelt(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    quelle = Seedquelle(5)
    werte = {fm.rundenform(k, auto, quelle, runde) for runde in range(1, 20)}
    assert len(werte) == 19


# -- E3 Motivationsschub (GDD 14) ------------------------------------------
def test_ein_tagesformbonus_hebt_nur_den_mittelwert(k) -> None:
    """E3 hebt den Mittelwert der Tagesform, nicht die Streuung."""
    auto = mit_wert(k, "D16", 0)
    ohne = [fm.tagesform(k, auto, Seedquelle(seed)) for seed in range(2_000)]
    mit = [fm.tagesform(k, auto, Seedquelle(seed), 0.03) for seed in range(2_000)]

    assert all(m == pytest.approx(o + 0.03) for o, m in zip(ohne, mit, strict=True))
    assert statistics.mean(mit) == pytest.approx(statistics.mean(ohne) + 0.03)
    assert statistics.stdev(mit) == pytest.approx(statistics.stdev(ohne))


def test_der_tagesformbonus_geht_in_die_gewuerfelten_werte(k) -> None:
    """Die Tagesform traegt die Fahrerwerte - also hebt E3 sie mit."""
    auto = mit_wert(k, "D16", 0)
    ohne = fm.wuerfle(k, auto, Seedquelle(3))
    mit = fm.wuerfle(k, auto, Seedquelle(3), 0.05)

    assert mit.tagesform == pytest.approx(ohne.tagesform + 0.05)
    # Dieselben Eigenschafts-Wuerfe, nur die Tagesform ist hoeher.
    assert mit.auto.wert("D1") > ohne.auto.wert("D1")
    # Fahrzeugwerte traegt die Tagesform nicht (GDD 11).
    assert mit.auto.wert("F1") == ohne.auto.wert("F1")


def test_ohne_bonus_bleibt_alles_wie_zuvor(k) -> None:
    """Der neue Parameter darf die bisherigen Wuerfe nicht verschieben."""
    auto = ka.gleichverteilt(k, 50_000)
    assert fm.wuerfle(k, auto, Seedquelle(9), 0.0) == fm.wuerfle(k, auto, Seedquelle(9))
