"""Tests fuer die Streckenkenntnis (GDD 6).

"Je Strecke steigt ein Kenntniswert mit jedem Start und jeder gefahrenen
Runde. Der Zuwachs streut zufaellig: +/-75 % je Start und zusaetzlich
+/-50 % je Runde. Der Wert gibt einen kleinen Tempobonus mit Obergrenze
(bis +1,5 %, voll nach etwa 1.000 Runden)."
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


# --- Zuwachs --------------------------------------------------------------
def test_ohne_runden_kein_zuwachs(k):
    assert sk.zuwachs(k, 0, Seedquelle(1)) == 0.0
    assert sk.zuwachs(k, -5, Seedquelle(1)) == 0.0


def test_der_zuwachs_liegt_im_moeglichen_bereich(k):
    """Start- und Rundenstreuung stapeln sich multiplikativ."""
    start = k.wert("streckenkenntnis", "streuung_je_start")
    runde = k.wert("streckenkenntnis", "streuung_je_runde")
    runden = 20
    for seed in range(30):
        wert = sk.zuwachs(k, runden, Seedquelle(seed))
        assert 0.0 <= wert <= runden * (1 + start) * (1 + runde)


def test_im_mittel_entspricht_der_zuwachs_den_runden(k):
    """Beide Streuungen sind symmetrisch, der Erwartungswert also 1."""
    runden = 40
    werte = [sk.zuwachs(k, runden, Seedquelle(seed)) for seed in range(400)]
    mittel = sum(werte) / len(werte)
    assert mittel == pytest.approx(runden, rel=0.06)


def test_der_zuwachs_streut_wirklich(k):
    """Zwei Fahrer mit gleicher Historie duerfen nicht gleich dastehen."""
    werte = {sk.zuwachs(k, 25, Seedquelle(seed)) for seed in range(20)}
    assert len(werte) == 20


def test_gleicher_seed_gleicher_zuwachs(k):
    assert sk.zuwachs(k, 30, Seedquelle(9)) == sk.zuwachs(k, 30, Seedquelle(9))


# --- Stand fuehren --------------------------------------------------------
def test_kenntnis_haengt_am_paar_aus_fahrer_und_strecke(k):
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.verbuche(fahrer=3, strecke="Monza", runden=50, seedquelle=Seedquelle(1))

    assert kenntnis.stand(3, "Monza") > 0.0
    assert kenntnis.stand(3, "Spa") == 0.0
    assert kenntnis.stand(4, "Monza") == 0.0


def test_sessions_summieren_sich(k):
    kenntnis = sk.Streckenkenntnis(k)
    erste = kenntnis.verbuche(1, "Spa", 30, Seedquelle(1))
    zweite = kenntnis.verbuche(1, "Spa", 30, Seedquelle(2))
    assert kenntnis.stand(1, "Spa") == pytest.approx(erste + zweite)


def test_tempofaktor_ist_eins_ohne_kenntnis(k):
    kenntnis = sk.Streckenkenntnis(k)
    assert kenntnis.tempofaktor(1, "Spa") == 1.0


def test_tempofaktor_waechst_mit_der_kenntnis(k):
    hoechst = k.wert("streckenkenntnis", "max_bonus")
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.setze(1, "Spa", k.wert("streckenkenntnis", "volle_kenntnis_runden"))
    assert kenntnis.tempofaktor(1, "Spa") == pytest.approx(1.0 + hoechst)


def test_ein_ganzes_feld_bekommt_verschiedene_zuwaechse(k):
    """Je Fahrer ein eigener Zweig - sonst lernen alle gleich schnell."""
    feld = tuple(range(30))
    kenntnis = sk.Streckenkenntnis(k)
    kenntnis.verbuche_feld(feld, "Monza", 24, Seedquelle(5))

    staende = {kenntnis.stand(nummer, "Monza") for nummer in feld}
    assert len(staende) == len(feld)
    faktoren = kenntnis.tempofaktoren(feld, "Monza")
    assert len(faktoren) == len(feld)
    assert all(faktor > 1.0 for faktor in faktoren)


def test_eine_saison_bringt_nur_einen_bruchteil_der_vollen_kenntnis(k):
    """20 Rennwochenenden auf 20 Strecken - nach einer Saison ist kein
    Fahrer auf einer Strecke auch nur nahe an der Obergrenze."""
    kenntnis = sk.Streckenkenntnis(k)
    # Qualifying (2 Runden) plus Rennen (24 Runden) auf derselben Strecke.
    kenntnis.verbuche(1, "Monza", 2, Seedquelle(1).zweig("quali"))
    kenntnis.verbuche(1, "Monza", 24, Seedquelle(1).zweig("rennen"))
    voll = k.wert("streckenkenntnis", "volle_kenntnis_runden")
    assert kenntnis.stand(1, "Monza") < voll * 0.2
    assert kenntnis.bonus(1, "Monza") < k.wert("streckenkenntnis", "max_bonus") * 0.2


# --- Wirkung in der Simulation --------------------------------------------
@pytest.fixture(scope="module")
def zandvoort(k):
    return st.lade(k, "Zandvoort")


@pytest.fixture(scope="module")
def feld(k):
    return rn.starterfeld(k, liga=10)


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
