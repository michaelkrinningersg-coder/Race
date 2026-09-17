"""Tests fuer Geschwindigkeitsprofil und Rundenzeit (GDD 4 und 9).

Der wichtigste Test ist test_kalibrierung_trifft_gdd_9: Er prueft, ob ein
Auto mit durchgehend gleichen Werten auf der Referenzstrecke genau den
Schnitt faehrt, den die Kalibrierfunktion aus GDD 9 vorschreibt.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import strecke as st
from rennmanager.kern import tempo as tp


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def referenz(k) -> st.Strecke:
    return st.lade(k, k.wert("kalibrierung", "referenzstrecke"))


def zieltempo(k, s: float) -> float:
    """v(S) = 55 + 125 * sqrt(S / 98.000) aus GDD 9."""
    return k.wert("kalibrierung", "basis_kmh") + k.wert("kalibrierung", "spanne_kmh") * math.sqrt(
        s / k.wert("skala", "referenz")
    )


# -- Kalibrierung gegen GDD 9 ----------------------------------------------
def test_kalibrierung_trifft_gdd_9(k, referenz) -> None:
    """Alle zehn Kontrollwerte aus der Ligatabelle in GDD 9."""
    for zeile in k.wert("ligen", "kontrolle"):
        for rolle in ("bester", "letzter"):
            s = zeile[f"s_{rolle}"]
            ergebnis = tp.fahre_runde(k, referenz, ka.gleichverteilt(k, s))
            assert ergebnis.schnitt_kmh == pytest.approx(zieltempo(k, s), abs=0.05), (
                f"Liga {zeile['liga']}, {rolle}, S={s}"
            )


@pytest.mark.parametrize("s", [0, 1_000, 12_000, 37_000, 71_000, 95_000, 100_000])
def test_kalibrierung_haelt_auch_zwischen_den_stuetzstellen(k, referenz, s: int) -> None:
    """Werte, die bei der Anpassung nicht benutzt wurden."""
    ergebnis = tp.fahre_runde(k, referenz, ka.gleichverteilt(k, s))
    assert ergebnis.schnitt_kmh == pytest.approx(zieltempo(k, s), abs=0.05)


def test_endgeschwindigkeit_erreicht_400_in_liga_1(k, referenz) -> None:
    """GDD 4: hoechstens 400 km/h in Liga 1."""
    grenzwert = k.wert("kalibrierung", "endgeschwindigkeit_max_kmh")
    bei_referenz = tp.grenzen_aus(k, ka.gleichverteilt(k, k.wert("skala", "referenz")))
    assert bei_referenz.hoechst_kmh == pytest.approx(grenzwert, abs=0.5)

    # Auch am oberen Ende der Skala bleibt es knapp darueber, nicht doppelt.
    bei_maximum = tp.grenzen_aus(k, ka.gleichverteilt(k, k.wert("skala", "maximum")))
    assert grenzwert <= bei_maximum.hoechst_kmh <= grenzwert * 1.03


def test_hoeherer_wert_ist_immer_schneller(k, referenz) -> None:
    zeiten = [
        tp.fahre_runde(k, referenz, ka.gleichverteilt(k, s)).zeit_ms
        for s in range(0, 100_001, 5_000)
    ]
    assert zeiten == sorted(zeiten, reverse=True)


# -- Physik des Profils -----------------------------------------------------
def test_kurvenlimit_folgt_der_wurzelformel(k) -> None:
    """v = sqrt(a_quer * r) auf einem Kreis mit bekanntem Radius."""
    radius = 150.0
    winkel = np.linspace(0.0, 2 * math.pi, 3_000, endpoint=False)
    kreis = np.column_stack([radius * np.cos(winkel), radius * np.sin(winkel)])
    strecke = st.werte_aus(
        kreis,
        abtastabstand_m=k.wert("strecke", "abtastabstand_m"),
        enge_kurve_max_m=k.wert("strecke", "enge_kurve_radius_max_m"),
        gerade_min_m=k.wert("strecke", "gerade_radius_min_m"),
        ueberholzone_min_m=k.wert("strecke", "ueberholzone_mindestlaenge_m"),
        sektoren=k.wert("strecke", "sektoren"),
    )
    grenzen = tp.grenzen_aus(k, ka.gleichverteilt(k, 50_000))
    limit = tp.kurvenlimit(strecke, grenzen)
    erwartet = min(math.sqrt(grenzen.quer * radius), grenzen.hoechst)
    assert limit.mean() == pytest.approx(erwartet, rel=0.01)


def test_profil_haelt_das_kurvenlimit_ein(k, referenz) -> None:
    grenzen = tp.grenzen_aus(k, ka.gleichverteilt(k, 62_470))
    profil = tp.geschwindigkeitsprofil(referenz, grenzen)
    assert (profil <= tp.kurvenlimit(referenz, grenzen) + 1e-9).all()
    assert (profil <= grenzen.hoechst + 1e-9).all()
    assert (profil > 0).all()


def test_profil_haelt_beschleunigung_und_bremsen_ein(k, referenz) -> None:
    """Zwischen zwei Punkten darf sich v^2 nur um 2*a*ds aendern (GDD 4)."""
    grenzen = tp.grenzen_aus(k, ka.gleichverteilt(k, 62_470))
    profil = tp.geschwindigkeitsprofil(referenz, grenzen)
    ds = referenz.punktabstand_m
    v2 = profil**2
    aenderung = np.roll(v2, -1) - v2

    assert aenderung.max() <= 2 * grenzen.laengs * ds + 1e-6
    assert -aenderung.max() <= 2 * grenzen.brems * ds + 1e-6


def test_profil_laeuft_ueber_die_startlinie_hinweg(k) -> None:
    """Die Runde ist geschlossen; am Startpunkt darf kein Sprung stehen."""
    strecke = st.lade(k, "Monza")
    grenzen = tp.grenzen_aus(k, ka.gleichverteilt(k, 62_470))
    profil = tp.geschwindigkeitsprofil(strecke, grenzen)
    ds = strecke.punktabstand_m
    sprung = abs(profil[0] ** 2 - profil[-1] ** 2)
    assert sprung <= 2 * max(grenzen.laengs, grenzen.brems) * ds + 1e-6


def test_schwaechere_bremsen_kosten_zeit(k) -> None:
    """D8 Bremsen und F8 Bremsanlage muessen sich auswirken."""
    strecke = st.lade(k, "Zandvoort")
    werte = {f.schluessel: 50_000 for f in k.faehigkeiten}
    stark = tp.fahre_runde(k, strecke, ka.Auto("A", "stark", dict(werte)))

    schwach = dict(werte)
    schwach["D8"] = 0
    schwach["F8"] = 0
    langsam = tp.fahre_runde(k, strecke, ka.Auto("B", "schwach", schwach))
    assert langsam.zeit_ms > stark.zeit_ms


def test_eigenschaften_wirken_streckenabhaengig(k) -> None:
    """Endgeschwindigkeit zaehlt auf Monza mehr als auf Zandvoort."""
    monza = st.lade(k, "Monza")
    zandvoort = st.lade(k, "Zandvoort")
    grund = {f.schluessel: 50_000 for f in k.faehigkeiten}

    schnell_geradeaus = dict(grund)
    for schluessel in ("F1", "F4", "F6", "D7"):
        schnell_geradeaus[schluessel] = 90_000

    def gewinn(strecke) -> float:
        basis = tp.fahre_runde(k, strecke, ka.Auto("A", "Basis", dict(grund))).zeit_ms
        besser = tp.fahre_runde(k, strecke, ka.Auto("B", "Gerade", dict(schnell_geradeaus))).zeit_ms
        return (basis - besser) / basis

    assert gewinn(monza) > gewinn(zandvoort)


# -- Zeitmessung ------------------------------------------------------------
def test_rundenzeit_ist_ganze_millisekunden(k, referenz) -> None:
    ergebnis = tp.fahre_runde(k, referenz, ka.gleichverteilt(k, 30_000))
    assert isinstance(ergebnis.zeit_ms, int)
    assert all(isinstance(zeit, int) for zeit in ergebnis.sektoren_ms)


def test_sektorzeiten_ergeben_die_rundenzeit(k, referenz) -> None:
    """GDD 4: 4 Sektorzeiten. Durch das Runden bleibt ein kleiner Rest."""
    ergebnis = tp.fahre_runde(k, referenz, ka.gleichverteilt(k, 30_000))
    assert len(ergebnis.sektoren_ms) == k.wert("strecke", "sektoren")
    assert sum(ergebnis.sektoren_ms) == pytest.approx(ergebnis.zeit_ms, abs=5)


def test_schnitt_passt_zur_rundenzeit(k, referenz) -> None:
    ergebnis = tp.fahre_runde(k, referenz, ka.gleichverteilt(k, 30_000))
    erwartet = referenz.laenge_m / (ergebnis.zeit_ms / 1000.0) * 3.6
    assert ergebnis.schnitt_kmh == pytest.approx(erwartet)


def test_rundenzeit_ist_reproduzierbar(k, referenz) -> None:
    """Ohne Zufall muss dieselbe Eingabe dieselbe Zeit liefern."""
    auto = ka.gleichverteilt(k, 44_000)
    zeiten = {tp.fahre_runde(k, referenz, auto).zeit_ms for _ in range(5)}
    assert len(zeiten) == 1


def test_rundenzeiten_sind_plausibel(k) -> None:
    """Ein Auto auf Liga-1-Niveau bleibt in realistischen Groessenordnungen."""
    for name, min_s, max_s in (("Monza", 70, 100), ("Spa", 100, 135), ("Norisring", 35, 60)):
        ergebnis = tp.fahre_runde(k, st.lade(k, name), ka.gleichverteilt(k, 98_130))
        sekunden = ergebnis.zeit_ms / 1000.0
        assert min_s < sekunden < max_s, f"{name}: {sekunden:.1f} s"


def test_schnelle_strecken_sind_schneller(k) -> None:
    """Der Schnitt muss dem Charakter der Strecke folgen (GDD 3)."""
    auto = ka.gleichverteilt(k, 62_470)
    schnitt = {
        name: tp.fahre_runde(k, st.lade(k, name), auto).schnitt_kmh
        for name in ("Monza", "Spa", "Suzuka", "Zandvoort")
    }
    assert schnitt["Monza"] > schnitt["Spa"] > schnitt["Suzuka"] > schnitt["Zandvoort"]
