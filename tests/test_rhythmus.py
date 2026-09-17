"""Tests fuer Rhythmus, Materialgefuehl und Heimstrecke (Punkte 15, 13 und 2)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import heimstrecke as hs
from rennmanager.kern import rhythmus as rh
from rennmanager.kern import strecke as st
from rennmanager.kern import zwischenfall as zf
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


def mit_zusatz(k, schluessel: str, wert: int, grund: int = 50_000) -> ka.Auto:
    auto = ka.gleichverteilt(k, grund)
    wetterwerte = dict(auto.wetterwerte)
    wetterwerte[schluessel] = wert
    return ka.Auto(auto.kuerzel, auto.name, auto.werte, wetterwerte)


# --- Rhythmus (Punkt 15) --------------------------------------------------
def test_der_kurvenfolgenanteil_trennt_die_strecken(k, strecken) -> None:
    """Zandvoort ist eine Kurvenfolge, Monza sind Geraden."""
    nach_name = {s.name: s.kurvenfolgenanteil for s in strecken}
    assert nach_name["Zandvoort"] > nach_name["Monza"] * 3
    assert all(0.0 <= wert <= 1.0 for wert in nach_name.values())


def test_eine_einzelne_kurve_zaehlt_nicht_als_folge(k, strecken) -> None:
    """Eine Kurve zwischen zwei Geraden ist keine Folge."""
    for strecke in strecken:
        assert strecke.kurvenfolgenanteil <= 1.0 - strecke.geradenanteil + 1e-9


def test_der_rhythmus_hilft_auf_kurvenstrecken_und_kostet_auf_geraden(k, strecken) -> None:
    mittel = rh.mittlerer_kurvenfolgenanteil(strecken)
    zandvoort = next(s for s in strecken if s.name == "Zandvoort")
    monza = next(s for s in strecken if s.name == "Monza")
    referenz = k.wert("skala", "referenz")

    stark = mit_zusatz(k, rh.RHYTHMUS, referenz)
    schwach = mit_zusatz(k, rh.RHYTHMUS, 0)
    assert rh.faktor(k, stark, zandvoort, mittel) > 1.0
    assert rh.faktor(k, schwach, zandvoort, mittel) < 1.0
    # Auf Monza dreht sich das Bild um.
    assert rh.faktor(k, stark, monza, mittel) < 1.0
    assert rh.faktor(k, schwach, monza, mittel) > 1.0


def test_der_rhythmus_bleibt_in_den_abgestimmten_grenzen(k, strecken) -> None:
    """Punkt 48: hoechstens 1,5 % auf die Querbeschleunigung."""
    mittel = rh.mittlerer_kurvenfolgenanteil(strecken)
    grenze = k.wert("rhythmus", "max_anteil_quer")
    referenz = k.wert("skala", "referenz")
    for strecke in strecken:
        for wert in (0, referenz // 2, referenz):
            faktor = rh.faktor(k, mit_zusatz(k, rh.RHYTHMUS, wert), strecke, mittel)
            assert abs(faktor - 1.0) <= grenze + 1e-9


def test_mittelmass_faehrt_ueberall_gleich(k, strecken) -> None:
    """Bei der Haelfte des Leistungsanteils ist der Fahrerterm null."""
    mittel = rh.mittlerer_kurvenfolgenanteil(strecken)
    # p = 0,5 heisst S = referenz / 4.
    auto = mit_zusatz(k, rh.RHYTHMUS, k.wert("skala", "referenz") // 4)
    for strecke in strecken:
        assert rh.faktor(k, auto, strecke, mittel) == pytest.approx(1.0)


# --- Materialgefuehl (Punkt 13) -------------------------------------------
def test_materialgefuehl_senkt_die_defektrate(k) -> None:
    """Punkt 48: Faktor 1,0 bei 0, 0,6 bei vollem Wert."""
    einstellung = k.wert("materialgefuehl")
    referenz = k.wert("skala", "referenz")
    assert zf.materialgefuehl(k, mit_zusatz(k, zf.MATERIALGEFUEHL, 0)) == pytest.approx(
        einstellung["faktor_bei_null"]
    )
    assert zf.materialgefuehl(
        k, mit_zusatz(k, zf.MATERIALGEFUEHL, referenz)
    ) == pytest.approx(einstellung["faktor_bei_maximum"])

    schwach = zf.defektrate_je_runde(k, mit_zusatz(k, zf.MATERIALGEFUEHL, 0), 50)
    stark = zf.defektrate_je_runde(k, mit_zusatz(k, zf.MATERIALGEFUEHL, referenz), 50)
    assert stark < schwach
    assert stark / schwach == pytest.approx(einstellung["faktor_bei_maximum"])


def test_f14_bleibt_die_fahrzeugseite(k) -> None:
    """Das Materialgefuehl ersetzt den Bereich ve nicht, es kommt dazu."""
    gut = ka.gleichverteilt(k, 98_000)
    schlecht = ka.gleichverteilt(k, 0)
    assert zf.defektrate_je_runde(k, gut, 50) < zf.defektrate_je_runde(k, schlecht, 50)


# --- Heimstrecke (Punkt 2) ------------------------------------------------
def test_die_heimstrecke_kommt_aus_dem_land(k, strecken) -> None:
    monza = next(s for s in strecken if s.name == "Monza")
    assert hs.ist_heimstrecke("Italien", monza)
    assert not hs.ist_heimstrecke("Finnland", monza)
    assert not hs.ist_heimstrecke("", monza)


def test_der_bonus_trifft_genau_fuenf_eigenschaften(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    anzahl = k.wert("heimstrecke", "eigenschaften")
    for seed in range(20):
        quelle = Seedquelle(seed)
        gezogen = hs.gezogene_eigenschaften(k, auto, quelle)
        assert len(gezogen) == anzahl
        assert len(set(gezogen)) == anzahl

        neu = hs.mit_bonus(k, auto, quelle)
        alt_alle = auto.werte | auto.wetterwerte
        neu_alle = neu.werte | neu.wetterwerte
        geaendert = {s for s in alt_alle if neu_alle[s] != alt_alle[s]}
        assert geaendert == set(gezogen)


def test_der_bonus_haelt_die_abgestimmten_grenzen(k) -> None:
    """Abgestimmt: 0,5 bis 1,0 Prozent."""
    einstellung = k.wert("heimstrecke")
    auto = ka.gleichverteilt(k, 50_000)
    for seed in range(20):
        quelle = Seedquelle(seed)
        neu = hs.mit_bonus(k, auto, quelle)
        alt_alle = auto.werte | auto.wetterwerte
        neu_alle = neu.werte | neu.wetterwerte
        for schluessel in hs.gezogene_eigenschaften(k, auto, quelle):
            anteil = neu_alle[schluessel] / alt_alle[schluessel] - 1.0
            assert einstellung["bonus_min"] - 1e-4 <= anteil <= einstellung["bonus_max"] + 1e-4


def test_jedes_wochenende_werden_andere_gezogen(k) -> None:
    """Abgestimmt: die fuenf werden je Rennwochenende neu gezogen."""
    auto = ka.gleichverteilt(k, 50_000)
    saetze = {hs.gezogene_eigenschaften(k, auto, Seedquelle(seed)) for seed in range(20)}
    assert len(saetze) > 15


def test_der_bonus_bleibt_auf_der_skala(k) -> None:
    auto = ka.gleichverteilt(k, k.wert("skala", "maximum"))
    neu = hs.mit_bonus(k, auto, Seedquelle(1))
    groesster = k.wert("skala", "maximum")
    assert all(wert <= groesster for wert in (neu.werte | neu.wetterwerte).values())
