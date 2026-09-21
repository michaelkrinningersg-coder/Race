"""Tests fuer die Streckenkenntnis (GDD 6, Punkt 101).

"Je Strecke steigt ein Kenntniswert ... Der Wert gibt einen kleinen
Tempobonus mit Obergrenze (bis +1,5 %, voll nach etwa 1.000 Runden)."

Seit Punkt 101 **waechst** er nicht mehr: Er wird einmal bei der
Welterzeugung je Fahrer und Strecke gewuerfelt und bleibt dann.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import streckenkenntnis as sk
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


# --- Bonus ----------------------------------------------------------------
def test_ohne_kenntnis_gibt_es_keinen_bonus(k):
    assert sk.bonus(k, 0.0) == 0.0


def test_voller_bonus_nach_der_genannten_rundenzahl(k):
    voll = k.wert("streckenkenntnis", "volle_kenntnis_runden")
    hoechst = k.wert("streckenkenntnis", "max_bonus")
    assert sk.bonus(k, voll) == pytest.approx(hoechst)
    # Darueber hinaus waechst nichts mehr.
    assert sk.bonus(k, voll * 10) == pytest.approx(hoechst)


def test_der_bonus_waechst_gleichmaessig(k):
    voll = k.wert("streckenkenntnis", "volle_kenntnis_runden")
    hoechst = k.wert("streckenkenntnis", "max_bonus")
    assert sk.bonus(k, voll / 2) == pytest.approx(hoechst / 2)
    assert sk.bonus(k, voll / 4) == pytest.approx(hoechst / 4)


def test_negative_staende_geben_keinen_malus(k):
    assert sk.bonus(k, -100.0) == 0.0


# --- Stand fuehren --------------------------------------------------------
def test_kenntnis_haengt_am_paar_aus_fahrer_und_strecke(k):
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.setze(3, "Monza", 50)

    assert kenntnis.stand(3, "Monza") == 50.0
    assert kenntnis.stand(3, "Spa") == 0.0
    assert kenntnis.stand(4, "Monza") == 0.0


def test_tempofaktor_ist_eins_ohne_kenntnis(k):
    kenntnis = sk.Streckenkenntnis(k)
    assert kenntnis.tempofaktor(1, "Spa") == 1.0


def test_tempofaktor_waechst_mit_der_kenntnis(k):
    hoechst = k.wert("streckenkenntnis", "max_bonus")
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.setze(1, "Spa", k.wert("streckenkenntnis", "volle_kenntnis_runden"))
    assert kenntnis.tempofaktor(1, "Spa") == pytest.approx(1.0 + hoechst)


def test_der_anfangsstand_streut_je_fahrer_und_strecke(k):
    """Je Fahrer ein eigener Zweig - sonst stuenden alle gleich da."""
    feld = tuple(range(30))
    strecken = ("Monza", "Spa")
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.setze_anfang(feld, strecken, Seedquelle(5))

    staende = {kenntnis.stand(nummer, "Monza") for nummer in feld}
    assert len(staende) == len(feld)
    # Und derselbe Fahrer kennt sich nicht ueberall gleich gut aus.
    assert kenntnis.stand(0, "Monza") != kenntnis.stand(0, "Spa")
    faktoren = kenntnis.tempofaktoren(feld, "Monza")
    assert len(faktoren) == len(feld)
    assert all(faktor > 1.0 for faktor in faktoren)


def test_der_anfangsstand_liegt_um_seinen_anteil(k):
    """Punkt 101: im Mittel ein Anteil der vollen Kenntnis, breit gestreut."""
    einstellung = k.wert("streckenkenntnis", "anfang")
    voll = k.wert("streckenkenntnis", "volle_kenntnis_runden")
    mitte = einstellung["anteil"] * voll
    breite = einstellung["streuung"]
    feld = tuple(range(200))
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.setze_anfang(feld, ("Monza",), Seedquelle(5))

    staende = [kenntnis.stand(nummer, "Monza") for nummer in feld]
    assert min(staende) >= mitte * (1 - breite) - 1e-6
    assert max(staende) <= mitte * (1 + breite) + 1e-6
    assert sum(staende) / len(staende) == pytest.approx(mitte, rel=0.12)


def test_derselbe_seed_gibt_denselben_anfangsstand(k):
    erste, zweite = sk.Streckenkenntnis(k), sk.Streckenkenntnis(k)
    erste.setze_anfang((1, 2, 3), ("Monza",), Seedquelle(7))
    zweite.setze_anfang((1, 2, 3), ("Monza",), Seedquelle(7))
    assert erste.runden == zweite.runden


def test_das_ganze_feld_bekommt_seinen_stand(k, kleine_welt, kleine_konfiguration):
    """Punkt 101: auch der Spieler - er faengt nicht mehr bei null an."""
    kenntnis = sk.Streckenkenntnis(kleine_konfiguration)
    sk.setze_feldanfang(
        kleine_konfiguration, kleine_welt, kenntnis, ("Monza",), Seedquelle(3)
    )
    for fahrer in kleine_welt.fahrer:
        assert kenntnis.stand(fahrer.nummer, "Monza") > 0.0


# --- Wirkung in der Simulation --------------------------------------------
@pytest.fixture(scope="module")
def zandvoort(k):
    return st.lade(k, "Zandvoort")


@pytest.fixture(scope="module")
def feld(k):
    return rn.starterfeld(k)


def test_kenntnis_macht_im_rennen_schneller(k, zandvoort, feld):
    """Der Bonus muss in der Rundenzeit ankommen, nicht nur im Wert."""
    mittel = rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))
    hoechst = k.wert("streckenkenntnis", "max_bonus")

    ohne = rn.simuliere(k, zandvoort, feld, 3, Seedquelle(2), mittel)
    mit = rn.simuliere(
        k,
        zandvoort,
        feld,
        3,
        Seedquelle(2),
        mittel,
        kenntnisfaktor=(1.0 + hoechst,) * len(feld),
    )
    # Alle Autos gleich stark bevorteilt: der Sieger muss um den vollen
    # Bonus schneller sein.
    assert mit.ergebnisse[0].zeit_ms < ohne.ergebnisse[0].zeit_ms
    verhaeltnis = mit.ergebnisse[0].zeit_ms / ohne.ergebnisse[0].zeit_ms
    assert verhaeltnis == pytest.approx(1.0 / (1.0 + hoechst), rel=0.01)


def test_kenntnis_bleibt_bei_der_kalibrierung_aussen_vor(k, zandvoort, feld):
    """GDD 9 kalibriert auf der blanken Runde - ohne_zufall muss den
    Kenntnisbonus deshalb ebenso wegnehmen wie den Reifenverschleiss."""
    mittel = rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))
    kenntnis = (1.0 + k.wert("streckenkenntnis", "max_bonus"),) * len(feld)

    ohne = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(2), mittel, ohne_zufall=True)
    mit = rn.simuliere(
        k, zandvoort, feld, 2, Seedquelle(2), mittel, ohne_zufall=True, kenntnisfaktor=kenntnis
    )
    assert mit.ergebnisse[0].zeit_ms == ohne.ergebnisse[0].zeit_ms


def test_falsche_feldgroesse_faellt_auf(k, zandvoort, feld):
    mittel = rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))
    with pytest.raises(ValueError, match="Kenntnisfaktor"):
        rn.simuliere(k, zandvoort, feld, 2, Seedquelle(1), mittel, kenntnisfaktor=(1.0, 1.0))
