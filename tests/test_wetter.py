"""Tests fuer das Wetter (GDD 7)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import wetter as wt
from rennmanager.kern.zufall import Seedquelle

RUNDE_MS = 90_000
DAUER_MS = RUNDE_MS * 30


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


def wuerfle(k, seed: int, strecke: str = "Spa") -> wt.Wetterverlauf:
    return wt.wuerfle(k, strecke, DAUER_MS, RUNDE_MS, Seedquelle(seed))


# -- Wuerfeln ---------------------------------------------------------------
def test_wetter_kennt_nur_die_fuenf_zustaende(k) -> None:
    kette = set(k.wert("wetter", "kette"))
    for seed in range(30):
        assert set(wuerfle(k, seed).zustaende) <= kette


def test_hoechstens_drei_wechsel(k) -> None:
    """GDD 7: Anzahl der Wechsel 0 bis 3."""
    for seed in range(50):
        verlauf = wuerfle(k, seed)
        assert k.wert("wetter", "wechsel_min") <= verlauf.wechsel
        assert verlauf.wechsel <= k.wert("wetter", "wechsel_max")


def test_jeder_wechsel_geht_nur_eine_stufe(k) -> None:
    """GDD 7: Starkregen - Regen - Wechselhaft - Trocken - Heiss."""
    kette = k.wert("wetter", "kette")
    schrittweite = k.wert("wetter", "wechsel_schrittweite")
    for seed in range(50):
        zustaende = wuerfle(k, seed).zustaende
        for davor, danach in zip(zustaende, zustaende[1:], strict=False):
            abstand = abs(kette.index(danach) - kette.index(davor))
            assert abstand == schrittweite, f"{davor} -> {danach}"


def test_wechsel_liegen_in_der_session(k) -> None:
    for seed in range(20):
        verlauf = wuerfle(k, seed)
        assert verlauf.abschnitte[0].ab_ms == 0
        zeiten = [abschnitt.ab_ms for abschnitt in verlauf.abschnitte]
        assert zeiten == sorted(zeiten)
        assert all(0 <= zeit <= DAUER_MS for zeit in zeiten)


def test_gleicher_seed_gleiches_wetter(k) -> None:
    assert wuerfle(k, 7).zustaende == wuerfle(k, 7).zustaende


def test_klimaprofil_wirkt_auf_den_startzustand(k) -> None:
    """Entscheidung zu Punkt 4: regenreiche Strecken sind haeufiger nass."""
    nass = {"regen", "starkregen"}
    spa = sum(1 for seed in range(200) if wuerfle(k, seed, "Spa").startzustand in nass)
    sakhir = sum(1 for seed in range(200) if wuerfle(k, seed, "Sakhir").startzustand in nass)
    assert spa > sakhir


def test_unbekannte_strecke_meldet_fehler(k) -> None:
    with pytest.raises(wt.WetterFehler, match="Wetterprofil"):
        wt.wuerfle(k, "Monaco", DAUER_MS, RUNDE_MS, Seedquelle(1))


# -- Grip -------------------------------------------------------------------
def test_grip_entspricht_der_tabelle(k) -> None:
    """GDD 7: Trocken 1,00 bis Starkregen 0,72."""
    for seed in range(40):
        verlauf = wuerfle(k, seed)
        abschnitt = verlauf.abschnitte[0]
        einstellung = k.wert("wetter", "zustand", abschnitt.zustand)
        if "grip" in einstellung:
            assert all(wert == einstellung["grip"] for wert in abschnitt.grip_je_sektor)
        else:
            assert all(
                einstellung["grip_min"] <= wert <= einstellung["grip_max"]
                for wert in abschnitt.grip_je_sektor
            )


def test_wechselhaft_schwankt_je_sektor(k) -> None:
    """GDD 7: Bei Wechselhaft schwankt der Grip je Sektor."""
    gefunden = False
    for seed in range(200):
        verlauf = wuerfle(k, seed)
        for abschnitt in verlauf.abschnitte:
            if abschnitt.zustand == "wechselhaft":
                gefunden = True
                assert len(set(abschnitt.grip_je_sektor)) > 1
    assert gefunden, "In 200 Wuerfen kam nie Wechselhaft vor"


def test_streckennaesse_folgt_verzoegert(k) -> None:
    """GDD 7: Der Grip springt nicht, sondern naehert sich ueber drei Runden an."""
    verlauf = next(wuerfle(k, seed) for seed in range(50) if wuerfle(k, seed).wechsel >= 1)
    wechsel = verlauf.abschnitte[1]
    davor = verlauf.abschnitte[0].grip_je_sektor[0]
    danach = wechsel.grip_je_sektor[0]
    if davor == danach:
        pytest.skip("Dieser Wechsel aendert den Grip nicht")

    # Direkt beim Wechsel gilt noch der alte Wert ...
    assert verlauf.grip_zu(wechsel.ab_ms, 1) == pytest.approx(davor)
    # ... nach dem Uebergang der neue ...
    assert verlauf.grip_zu(wechsel.ab_ms + verlauf.uebergang_ms, 1) == pytest.approx(danach)
    # ... und dazwischen etwas dazwischen.
    mitte = verlauf.grip_zu(wechsel.ab_ms + verlauf.uebergang_ms / 2, 1)
    assert min(davor, danach) < mitte < max(davor, danach)


def test_uebergang_dauert_drei_runden(k) -> None:
    verlauf = wuerfle(k, 3)
    assert verlauf.uebergang_ms == k.wert("wetter", "naesse", "verzoegerung_runden") * RUNDE_MS


# -- Wetterfaehigkeiten -----------------------------------------------------
def test_wetterkoennen_daempft_den_gripverlust(k) -> None:
    """GDD 7: bis zu 60 % weniger Verlust bei 100.000."""
    ohne = ka.gleichverteilt(k, 0)
    mit = ka.gleichverteilt(k, 100_000)
    roh = k.wert("wetter", "zustand", "starkregen")["grip"]

    grip_ohne = wt.grip_fuer(k, ohne, "starkregen", roh)
    grip_mit = wt.grip_fuer(k, mit, "starkregen", roh)
    assert grip_ohne == pytest.approx(roh)
    assert grip_mit > grip_ohne

    max_daempfung = k.wert("wetter", "faehigkeit", "max_daempfung")
    assert grip_mit == pytest.approx(1.0 - (1.0 - roh) * (1.0 - max_daempfung), abs=0.005)


def test_trockenroutine_gibt_einen_kleinen_bonus(k) -> None:
    """GDD 7: bei Trocken gibt die Faehigkeit einen kleinen Tempobonus."""
    ohne = wt.grip_fuer(k, ka.gleichverteilt(k, 0), "trocken", 1.0)
    mit = wt.grip_fuer(k, ka.gleichverteilt(k, 100_000), "trocken", 1.0)
    assert ohne == pytest.approx(1.0)
    assert mit > 1.0
    assert mit == pytest.approx(1.0 + k.wert("wetter", "trockenbonus", "max_anteil"), abs=0.001)


def test_kuehlung_wirkt_zusaetzlich_bei_hitze(k) -> None:
    """GDD 7 und 8: Bei Hitze wirkt zusaetzlich F16 Kuehlung."""
    from rennmanager.kern.auto import Auto

    grundwerte = {f.schluessel: 0 for f in k.faehigkeiten}
    wetterwerte = {
        e["schluessel"]: 0 for e in k.wert("wetter", "faehigkeit", "liste")
    }
    roh = k.wert("wetter", "zustand", "heiss")["grip"]

    ohne = Auto("A", "ohne", dict(grundwerte), dict(wetterwerte))
    mit_kuehlung = dict(grundwerte)
    mit_kuehlung["F16"] = 100_000
    besser = Auto("B", "mit", mit_kuehlung, dict(wetterwerte))

    assert wt.grip_fuer(k, besser, "heiss", roh) > wt.grip_fuer(k, ohne, "heiss", roh)
    # Bei Regen wirkt F16 nicht.
    nass = k.wert("wetter", "zustand", "regen")["grip"]
    assert wt.grip_fuer(k, besser, "regen", nass) == pytest.approx(
        wt.grip_fuer(k, ohne, "regen", nass)
    )


def test_fehlerfaktor_wird_gedaempft(k) -> None:
    """GDD 7: Die Wetterfaehigkeit senkt auch den Fehlerzuwachs."""
    roh = k.wert("wetter", "zustand", "starkregen")["fehlerquote"]
    ohne = wt.fehlerfaktor(k, ka.gleichverteilt(k, 0), "starkregen")
    mit = wt.fehlerfaktor(k, ka.gleichverteilt(k, 100_000), "starkregen")
    assert ohne == pytest.approx(roh)
    assert 1.0 < mit < ohne


def test_verschleissfaktor_kommt_aus_der_tabelle(k) -> None:
    assert wt.verschleissfaktor(k, "heiss") == 1.4
    assert wt.verschleissfaktor(k, "starkregen") == 0.7
    assert wt.verschleissfaktor(k, "trocken") == 1.0


def test_jedes_wetter_hat_ein_koennen(k) -> None:
    for zustand in k.wert("wetter", "kette"):
        assert wt.faehigkeit_zu(k, zustand)
