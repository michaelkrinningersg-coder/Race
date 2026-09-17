"""Test fuer das Kalibrierwerkzeug (werkzeuge/kalibriere.py).

Das Werkzeug erzeugt die zwei Konstanten in der Balancing-Datei. Hier wird
geprueft, dass es laeuft und dass die eingetragenen Werte tatsaechlich das
Optimum sind - eine erneute Anpassung darf sie kaum verschieben.

Mit einer dritten freien Konstanten waere genau das nicht der Fall: Man
kann Endgeschwindigkeit gegen Haftung tauschen und trifft denselben
Rundenschnitt. Deshalb ist die Endgeschwindigkeit gekoppelt.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from werkzeuge import kalibriere


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


def test_zieltempo_entspricht_gdd_9(k: kf.Konfiguration) -> None:
    assert kalibriere.zieltempo(k, 0) == pytest.approx(55.0)
    assert kalibriere.zieltempo(k, 98_000) == pytest.approx(180.0)
    assert kalibriere.zieltempo(k, 100_000) == pytest.approx(181.3, abs=0.05)


def test_stuetzstellen_enthalten_die_kontrolltabelle(k: kf.Konfiguration) -> None:
    stellen = set(kalibriere.stuetzstellen(k))
    for zeile in k.wert("ligen", "kontrolle"):
        assert zeile["s_bester"] in stellen
        assert zeile["s_letzter"] in stellen


def test_hinterlegte_werte_sind_das_optimum(k: kf.Konfiguration) -> None:
    """Eine erneute Anpassung darf die Konstanten kaum noch verschieben."""
    vorher = (
        k.wert("tempo", "haftung_referenz"),
        k.wert("tempo", "anteil_bei_null"),
    )
    gefunden, abweichung = kalibriere.kalibriere(k)

    assert abweichung < 0.01, "Das Modell trifft die Kalibriertabelle nicht"
    for alt, neu in zip(vorher, gefunden, strict=True):
        assert neu == pytest.approx(alt, rel=0.02)


def test_endgeschwindigkeit_ist_an_die_haftung_gekoppelt(k: kf.Konfiguration) -> None:
    """Die Kopplung macht das Modell durch GDD 9 eindeutig bestimmbar."""
    from rennmanager.kern import auto as ka
    from rennmanager.kern import tempo as tp

    anteil = k.wert("tempo", "anteil_bei_null")
    hoechst_referenz = k.wert("tempo", "hoechstgeschwindigkeit_bei_referenz_kmh")

    bei_null = tp.grenzen_aus(k, ka.gleichverteilt(k, 0))
    assert bei_null.hoechst_kmh == pytest.approx(hoechst_referenz * anteil, rel=1e-6)
