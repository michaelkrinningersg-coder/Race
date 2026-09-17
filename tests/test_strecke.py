"""Tests fuer das Streckenmodell (GDD 3).

Die Geometrie wird zuerst gegen erzeugte Formen mit bekanntem Ergebnis
geprueft - ein Kreis hat ueberall denselben Radius, ein Oval aus zwei
Geraden und zwei Halbkreisen hat genau vier Segmente. Erst danach kommen
die echten Streckendaten.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import strecke as st
from rennmanager.kern.strecke import Segmentart, StreckenFehler

ABTASTABSTAND = 5.0
ENGE_KURVE_MAX = 60.0
GERADE_MIN = 300.0
UEBERHOLZONE_MIN = 100.0
SEKTOREN = 4


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def alle_strecken(k: kf.Konfiguration) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


def kreis(radius: float, punkte: int = 4000) -> np.ndarray:
    winkel = np.linspace(0.0, 2.0 * math.pi, punkte, endpoint=False)
    return np.column_stack([radius * np.cos(winkel), radius * np.sin(winkel)])


def oval(gerade_m: float, radius_m: float, je_teil: int = 300) -> np.ndarray:
    """Zwei Geraden und zwei Halbkreise - ein Rundkurs mit bekanntem Aufbau."""
    bogen = np.linspace(-math.pi / 2, math.pi / 2, je_teil, endpoint=False)
    return np.vstack(
        [
            np.column_stack(
                [np.linspace(0, gerade_m, je_teil, endpoint=False), np.full(je_teil, -radius_m)]
            ),
            np.column_stack([gerade_m + radius_m * np.cos(bogen), radius_m * np.sin(bogen)]),
            np.column_stack(
                [np.linspace(gerade_m, 0, je_teil, endpoint=False), np.full(je_teil, radius_m)]
            ),
            np.column_stack(
                [radius_m * np.cos(bogen + math.pi), radius_m * np.sin(bogen + math.pi)]
            ),
        ]
    )


def werte_aus(linie: np.ndarray, **abweichend) -> st.Strecke:
    vorgaben = dict(
        abtastabstand_m=ABTASTABSTAND,
        enge_kurve_max_m=ENGE_KURVE_MAX,
        gerade_min_m=GERADE_MIN,
        ueberholzone_min_m=UEBERHOLZONE_MIN,
        sektoren=SEKTOREN,
    )
    return st.werte_aus(linie, **{**vorgaben, **abweichend})


# -- Abtasten ---------------------------------------------------------------
def test_abtasten_verteilt_gleichmaessig() -> None:
    punkte, abstand = st.taste_ab(kreis(200.0), ABTASTABSTAND)
    geschlossen = np.vstack([punkte, punkte[:1]])
    abstaende = np.linalg.norm(np.diff(geschlossen, axis=0), axis=1)
    # Alle Abstaende gleich, auch der ueber die Start/Ziel-Linie hinweg.
    assert abstaende.std() < 1e-6
    # Gemessen wird die Sehne zwischen zwei Punkten, abgetastet wird entlang
    # des Bogens; auf einer Kurve ist die Sehne minimal kuerzer.
    assert abstaende.mean() == pytest.approx(abstand, rel=1e-3)
    assert abstaende.mean() <= abstand


def test_abtasten_trifft_den_wunschabstand_fast_genau() -> None:
    """Eine geschlossene Runde geht selten glatt auf; die Abweichung ist klein."""
    for radius in (50.0, 137.0, 400.0):
        _, abstand = st.taste_ab(kreis(radius), ABTASTABSTAND)
        assert abs(abstand - ABTASTABSTAND) < ABTASTABSTAND / 2


def test_abtasten_erhaelt_die_laenge() -> None:
    radius = 250.0
    punkte, abstand = st.taste_ab(kreis(radius), ABTASTABSTAND)
    assert len(punkte) * abstand == pytest.approx(2 * math.pi * radius, rel=1e-4)


def test_abtasten_weist_ungueltigen_abstand_zurueck() -> None:
    with pytest.raises(ValueError):
        st.taste_ab(kreis(100.0), 0.0)


def test_abtasten_weist_zu_kurze_linie_zurueck() -> None:
    with pytest.raises(ValueError, match="zu kurz"):
        st.taste_ab(kreis(1.0), ABTASTABSTAND)


# -- Kruemmung --------------------------------------------------------------
@pytest.mark.parametrize("radius", [30.0, 60.0, 150.0, 300.0, 1000.0])
def test_kruemmungsradius_trifft_den_kreisradius(radius: float) -> None:
    """Auf einem Kreis muss ueberall derselbe Radius herauskommen."""
    punkte, _ = st.taste_ab(kreis(radius), ABTASTABSTAND)
    gemessen = st.kruemmungsradius(punkte)
    # Bei 5 m Punktabstand ist ein enger Kreis grob aufgeloest; 1 % genuegt.
    assert gemessen.mean() == pytest.approx(radius, rel=0.01)
    assert gemessen.std() / radius < 0.01


def test_kruemmungsradius_ist_immer_positiv() -> None:
    """Die Fahrtrichtung der Kurve spielt fuer den Segmenttyp keine Rolle."""
    punkte, _ = st.taste_ab(kreis(120.0), ABTASTABSTAND)
    rechtsherum = st.kruemmungsradius(punkte)
    linksherum = st.kruemmungsradius(punkte[::-1])
    assert (rechtsherum > 0).all()
    assert linksherum.mean() == pytest.approx(rechtsherum.mean(), rel=1e-6)


# -- Segmenttypen -----------------------------------------------------------
def test_segmentgrenzen_sind_halboffen() -> None:
    """GDD 3: enge Kurve r < 60 m, Gerade r >= 300 m."""
    radien = np.array([0.0, 59.999, 60.0, 299.999, 300.0, 1e9, np.inf])
    art = st.bestimme_art(radien, ENGE_KURVE_MAX, GERADE_MIN)
    assert list(art) == [
        Segmentart.ENGE_KURVE,
        Segmentart.ENGE_KURVE,
        Segmentart.KURVE,
        Segmentart.KURVE,
        Segmentart.GERADE,
        Segmentart.GERADE,
        Segmentart.GERADE,
    ]


def test_oval_ergibt_vier_segmente() -> None:
    strecke = werte_aus(oval(gerade_m=500.0, radius_m=100.0))
    assert len(strecke.segmente) == 4
    arten = [segment.art for segment in strecke.segmente]
    assert arten.count(Segmentart.GERADE) == 2
    assert arten.count(Segmentart.KURVE) == 2


def test_oval_hat_die_erwartete_laenge() -> None:
    gerade, radius = 500.0, 100.0
    strecke = werte_aus(oval(gerade_m=gerade, radius_m=radius))
    assert strecke.laenge_m == pytest.approx(2 * gerade + 2 * math.pi * radius, rel=1e-3)


def test_enger_kreis_ist_durchgehend_enge_kurve() -> None:
    strecke = werte_aus(kreis(40.0))
    assert len(strecke.segmente) == 1
    assert strecke.segmente[0].art is Segmentart.ENGE_KURVE
    assert strecke.anteil(Segmentart.ENGE_KURVE) == pytest.approx(1.0)


def test_weiter_kreis_ist_durchgehend_gerade() -> None:
    """Ab 300 m Radius gilt laut GDD alles als Gerade."""
    strecke = werte_aus(kreis(500.0))
    assert strecke.anteil(Segmentart.GERADE) == pytest.approx(1.0)


# -- Ueberholzonen ----------------------------------------------------------
def test_nur_lange_geraden_sind_ueberholzonen() -> None:
    """GDD 3: nur Geraden ab 100 m Laenge."""
    lang = werte_aus(oval(gerade_m=500.0, radius_m=100.0))
    assert len(lang.ueberholzonen) == 2
    assert all(zone.art is Segmentart.GERADE for zone in lang.ueberholzonen)
    assert all(zone.laenge_m >= UEBERHOLZONE_MIN for zone in lang.ueberholzonen)

    kurz = werte_aus(oval(gerade_m=60.0, radius_m=100.0))
    assert [segment for segment in kurz.segmente if segment.art is Segmentart.GERADE]
    assert kurz.ueberholzonen == ()


def test_kurven_sind_nie_ueberholzonen() -> None:
    strecke = werte_aus(kreis(150.0))
    assert strecke.ueberholzonen == ()


# -- Sektoren ---------------------------------------------------------------
def test_vier_sektoren_gleicher_laenge() -> None:
    strecke = werte_aus(oval(gerade_m=500.0, radius_m=100.0))
    assert len(strecke.sektoren) == SEKTOREN
    laengen = [sektor.laenge_m for sektor in strecke.sektoren]
    # Geht die Punktzahl nicht glatt auf, bleibt hoechstens ein Punkt Rest.
    assert max(laengen) - min(laengen) == pytest.approx(strecke.punktabstand_m, abs=1e-6)


def test_sektoren_decken_die_runde_luckenlos_ab() -> None:
    strecke = werte_aus(oval(gerade_m=500.0, radius_m=100.0))
    assert strecke.sektoren[0].von == 0
    assert strecke.sektoren[-1].bis == len(strecke.punkte)
    for davor, danach in zip(strecke.sektoren, strecke.sektoren[1:], strict=False):
        assert davor.bis == danach.von
    assert sum(s.laenge_m for s in strecke.sektoren) == pytest.approx(strecke.laenge_m)


def test_jeder_punkt_liegt_in_genau_einem_sektor() -> None:
    strecke = werte_aus(oval(gerade_m=500.0, radius_m=100.0))
    nummern = [strecke.sektor_von_punkt(i) for i in range(len(strecke.punkte))]
    assert set(nummern) == {1, 2, 3, 4}
    assert nummern[0] == 1


# -- Segmente ueber die Start/Ziel-Linie ------------------------------------
def test_segment_ueber_start_wird_nicht_zerschnitten() -> None:
    """Eine Gerade, die ueber Start/Ziel laeuft, bleibt ein Segment."""
    # Das Oval beginnt in der Mitte einer Geraden, deshalb laeuft genau ein
    # Segment ueber die Start/Ziel-Linie.
    linie = oval(gerade_m=500.0, radius_m=100.0)
    versetzt = np.roll(linie, -150, axis=0)
    strecke = werte_aus(versetzt)
    assert len(strecke.segmente) == 4
    ueber_start = [s for s in strecke.segmente if s.laeuft_ueber_start]
    assert len(ueber_start) == 1
    assert sum(s.punkte for s in strecke.segmente) == len(strecke.punkte)


def test_segmente_decken_alle_punkte_ab() -> None:
    for linie in (kreis(40.0), kreis(500.0), oval(500.0, 100.0), oval(60.0, 100.0)):
        strecke = werte_aus(linie)
        assert sum(s.punkte for s in strecke.segmente) == len(strecke.punkte)


# -- Echte Streckendaten ----------------------------------------------------
def test_alle_zwanzig_strecken_laden(alle_strecken) -> None:
    assert len(alle_strecken) == kf.ANZAHL_STRECKEN


def test_streckendateien_sind_vorhanden(k: kf.Konfiguration) -> None:
    wurzel = st.datenverzeichnis() / "strecken"
    for eintrag in k.strecken:
        for ordner in ("ideallinie", "mittellinie"):
            pfad = wurzel / ordner / f"{eintrag['datei']}.csv"
            assert pfad.is_file(), f"fehlt: {pfad}"


def test_lizenz_liegt_bei_den_daten() -> None:
    """Die Daten stehen unter LGPL-3.0 und werden mitgeliefert (GDD 3)."""
    wurzel = st.datenverzeichnis() / "strecken"
    assert (wurzel / "LICENSE").is_file()
    assert (wurzel / "HERKUNFT.md").is_file()


def test_streckenlaengen_sind_plausibel(alle_strecken) -> None:
    for strecke in alle_strecken:
        assert 2_000 < strecke.laenge_m < 8_000, f"{strecke.name}: {strecke.laenge_m:.0f} m"


@pytest.mark.parametrize(
    ("name", "erwartet_m"),
    [
        # Abgleich mit den realen Rundenlaengen; die Ideallinie ist etwas
        # kuerzer als die Mittellinie, deshalb 4 % Spielraum nach unten.
        ("Spa", 7_004),
        ("Monza", 5_793),
        ("Silverstone", 5_891),
        ("Suzuka", 5_807),
        ("Norisring", 2_300),
    ],
)
def test_rundenlaenge_passt_zur_wirklichkeit(k, name: str, erwartet_m: float) -> None:
    strecke = st.lade(k, name)
    assert 0.94 * erwartet_m <= strecke.laenge_m <= 1.02 * erwartet_m


def test_jede_strecke_hat_alle_segmenttypen(alle_strecken) -> None:
    for strecke in alle_strecken:
        for art in Segmentart:
            assert strecke.anteil(art) > 0, f"{strecke.name} ohne {art.bezeichnung}"


def test_jede_strecke_hat_ueberholzonen(alle_strecken) -> None:
    """Ohne Ueberholzone waere ein Rennen dort nicht fahrbar (GDD 4)."""
    for strecke in alle_strecken:
        assert strecke.ueberholzonen, f"{strecke.name} ohne Ueberholzone"


def test_geradenanteil_passt_zum_charakter(alle_strecken) -> None:
    """Abgleich mit den Charakterangaben aus GDD 3.

    Den hoechsten Geradenanteil hat nicht Monza, sondern der Norisring: ein
    kurzer Stadtkurs aus zwei langen Geraden und wenigen Haarnadeln. Monza
    liegt direkt dahinter, Zandvoort mit seinen Steilkurven ganz hinten.
    """
    sortiert = sorted(alle_strecken, key=lambda s: s.geradenanteil, reverse=True)
    nach_anteil = [strecke.name for strecke in sortiert]
    assert nach_anteil[:2] == ["Norisring", "Monza"]
    assert nach_anteil[-1] == "Zandvoort"


def test_budapest_hat_wenige_ueberholzonen(alle_strecken) -> None:
    """GDD 3: Budapest 'Eng, kaum Ueberholen'."""
    zonen = {strecke.name: len(strecke.ueberholzonen) for strecke in alle_strecken}
    assert zonen["Budapest"] <= zonen["Monza"]


def test_strecken_sind_geschlossene_runden(alle_strecken) -> None:
    for strecke in alle_strecken:
        luecke = float(np.linalg.norm(strecke.punkte[0] - strecke.punkte[-1]))
        assert luecke == pytest.approx(strecke.punktabstand_m, rel=0.05), strecke.name


def test_punktabstand_liegt_bei_fuenf_metern(alle_strecken, k) -> None:
    wunsch = k.wert("strecke", "abtastabstand_m")
    for strecke in alle_strecken:
        assert abs(strecke.punktabstand_m - wunsch) < 0.05, strecke.name


def test_auswertung_ist_wiederholbar(k: kf.Konfiguration) -> None:
    """Zweimal laden muss dasselbe Ergebnis liefern - die Geometrie wuerfelt nicht."""
    erste = st.lade(k, "Catalunya")
    zweite = st.lade(k, "Catalunya")
    assert np.array_equal(erste.punkte, zweite.punkte)
    assert erste.segmente == zweite.segmente
    assert erste.sektoren == zweite.sektoren


# -- Fehlerfaelle -----------------------------------------------------------
def test_unbekannte_strecke_meldet_fehler(k: kf.Konfiguration) -> None:
    with pytest.raises(StreckenFehler, match="Unbekannte Strecke"):
        st.lade(k, "Monaco")


def test_fehlende_datei_meldet_fehler(k: kf.Konfiguration, tmp_path) -> None:
    with pytest.raises(StreckenFehler, match="fehlt"):
        st.lade(k, "Monza", verzeichnis=tmp_path)


def test_unlesbare_datei_meldet_fehler(k: kf.Konfiguration, tmp_path) -> None:
    ordner = tmp_path / k.wert("strecke", "linie")
    ordner.mkdir()
    (ordner / "Monza.csv").write_text("# x_m,y_m\nkeine,zahlen\n", encoding="utf-8")
    with pytest.raises(StreckenFehler):
        st.lade(k, "Monza", verzeichnis=tmp_path)


def test_zu_wenige_punkte_melden_fehler(k: kf.Konfiguration, tmp_path) -> None:
    ordner = tmp_path / k.wert("strecke", "linie")
    ordner.mkdir()
    (ordner / "Monza.csv").write_text("# x_m,y_m\n0,0\n1,1\n", encoding="utf-8")
    with pytest.raises(StreckenFehler, match="zu wenige Punkte"):
        st.lade(k, "Monza", verzeichnis=tmp_path)
