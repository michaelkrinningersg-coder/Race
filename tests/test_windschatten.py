"""Tests fuer den Windschatten und das Ueberrunden (Punkte 7 und 12).

Der Windschatten ist neu - GDD 4 kennt ihn nicht, er ist mit dem
Auftraggeber abgestimmt. Das Ueberrunden dagegen war schon richtig: Wer
ueberrundet, wird nicht aufgehalten. Diese Datei haelt beides fest.
"""

from __future__ import annotations

import statistics

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import rennen as kr
from rennmanager.kern import strecke as st
from rennmanager.kern import windschatten as ws
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecke(k) -> st.Strecke:
    return st.lade(k, "Monza")


def mit_sog(k, wert: int, grund: int = 50_000, kuerzel: str = "REF") -> ka.Auto:
    auto = ka.gleichverteilt(k, grund, kuerzel=kuerzel)
    wetterwerte = dict(auto.wetterwerte)
    wetterwerte[ws.WINDSCHATTEN] = wert
    return ka.Auto(auto.kuerzel, auto.name, auto.werte, wetterwerte)


# --- Das Fenster ----------------------------------------------------------
def test_der_sog_reicht_bis_30_meter(k) -> None:
    """Abgestimmt: von 30 m bis auf gleiche Hoehe."""
    auto = mit_sog(k, 0)
    fenster = k.wert("windschatten", "fenster_m")
    assert fenster == 30.0
    assert ws.faktor(k, auto, 0.5) > 1.0
    assert ws.faktor(k, auto, fenster) == 1.0
    assert ws.faktor(k, auto, fenster + 10.0) == 1.0


def test_auf_gleicher_hoehe_gibt_es_keinen_sog(k) -> None:
    """Wer neben dem anderen faehrt, steht nicht mehr in seinem Sog."""
    auto = mit_sog(k, 50_000)
    assert ws.faktor(k, auto, 0.0) == 1.0
    assert ws.faktor(k, auto, -5.0) == 1.0


def test_der_sog_waechst_je_naeher_das_auto_faehrt(k) -> None:
    auto = mit_sog(k, 50_000)
    werte = [ws.faktor(k, auto, abstand) for abstand in (25.0, 15.0, 5.0, 1.0)]
    assert werte == sorted(werte)


def test_der_gewinn_haelt_die_abgestimmten_grenzen(k) -> None:
    """Punkt 48: +1,0 % bei 0, +2,5 % bei vollem Wert."""
    einstellung = k.wert("windschatten")
    referenz = k.wert("skala", "referenz")
    assert ws.gewinn(k, mit_sog(k, 0)) == pytest.approx(einstellung["gewinn_bei_null"])
    assert ws.gewinn(k, mit_sog(k, referenz)) == pytest.approx(
        einstellung["gewinn_bei_maximum"]
    )


def test_eine_fehlende_eigenschaft_gilt_als_null(k) -> None:
    ohne = ka.Auto("X", "Ohne Zusatz", ka.gleichverteilt(k, 50_000).werte)
    assert ws.gewinn(k, ohne) == ws.gewinn(k, mit_sog(k, 0))


# --- Im Rennen ------------------------------------------------------------
def feld(k, wert_sog: int, anzahl: int = 12) -> tuple[kr.Teilnehmer, ...]:
    """Ein Feld gleich starker Autos, das sich nur im Sog unterscheidet."""
    return tuple(
        kr.Teilnehmer(
            auto=mit_sog(k, wert_sog, kuerzel=f"A{i:02d}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i in range(anzahl)
    )


def test_mehr_sog_bringt_mehr_ueberholmanoever(k, strecke) -> None:
    """Der Sog hebt den Tempovorteil - und damit die Erfolgschance (GDD 4).

    Gemessen ueber mehrere Seeds: Die Aussage ist systematisch, das
    einzelne Rennen aber nicht. Mit nur einem Seed ging der Test lange
    zufaellig auf und kippte, als sich der Reifenverschleiss aenderte -
    obwohl der Sog gemessen 1971 auf 3184 Manoever hebt.
    """
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    referenz = k.wert("skala", "referenz")

    def manoever(wert: int) -> int:
        return sum(
            len(
                kr.simuliere(
                    k, strecke, feld(k, wert), runden=6, seedquelle=Seedquelle(seed),
                    streckenmittel=mittel,
                ).manoever
            )
            for seed in range(1, 6)
        )

    assert manoever(referenz) > manoever(0)


def test_ohne_zufall_gibt_es_keinen_sog(k, strecke) -> None:
    """GDD 9 kalibriert das einzelne Auto auf freier Strecke."""
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    lauf = kr._Lauf(
        k, strecke, feld(k, k.wert("skala", "referenz"), anzahl=2), runden=3,
        seedquelle=Seedquelle(1), streckenmittel=mittel, ohne_zufall=True,
    )
    assert not lauf.sog_gewinn.any()


# --- Ueberrunden (Punkt 12) -----------------------------------------------
def gemischtes_feld(k, anzahl: int = 10) -> tuple[kr.Teilnehmer, ...]:
    """Ein sehr starkes Auto gegen lauter schwache - so wird ueberrundet."""
    werte = [98_000] + [10_000] * (anzahl - 1)
    return tuple(
        kr.Teilnehmer(
            auto=ka.gleichverteilt(k, wert, kuerzel=f"A{i:02d}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i, wert in enumerate(werte)
    )


def test_wer_ueberrundet_wird_nicht_aufgehalten(k, strecke) -> None:
    """Punkt 12 und Punkt 68: Der Ueberrundende verliert nichts - er gewinnt.

    Frueher stand hier, der Verkehr aendere ueberhaupt nichts: Der Sog hing
    an der *zurueckgelegten Distanz*, und ein Ueberrundeter liegt eine ganze
    Runde zurueck. Seit Punkt 68 zaehlt die Position auf der Strecke: Der
    Ueberrundende bekommt Sog, der Ueberrundete nicht. Der Verkehr darf ihn
    also schneller machen - aufhalten darf er ihn in keiner Runde.
    """
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    im_verkehr = kr.simuliere(
        k, strecke, gemischtes_feld(k), runden=12, seedquelle=Seedquelle(5),
        streckenmittel=mittel,
    )
    # Es wurde wirklich ueberrundet.
    assert max(e.rundenrueckstand for e in im_verkehr.ergebnisse) > 0

    allein = kr.simuliere(
        k, strecke, gemischtes_feld(k)[:1], runden=12, seedquelle=Seedquelle(5),
        streckenmittel=mittel,
    )
    zeiten = list(
        zip(
            im_verkehr.protokolle[0].rundenzeiten_ms,
            allein.protokolle[0].rundenzeiten_ms,
            strict=True,
        )
    )
    # Keine einzige Runde kostet Zeit ...
    assert all(mit_verkehr <= frei for mit_verkehr, frei in zeiten)
    # ... und in den Runden, in denen er ueberrundet, bringt der Sog etwas.
    assert min(mit_verkehr - frei for mit_verkehr, frei in zeiten) < 0


def test_der_ueberrundende_faellt_in_keiner_runde_ab(k, strecke) -> None:
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    verlauf = kr.simuliere(
        k, strecke, gemischtes_feld(k), runden=12, seedquelle=Seedquelle(5),
        streckenmittel=mittel,
    )
    # Die ersten Runden sind langsamer, weil der Reifen erst ins
    # Grifffenster hineinlaufen muss (Optimum bei 85 % Restprofil) - das
    # ist gewollt und kein Verkehr. Gemessen wird ab der vierten Runde.
    zeiten = verlauf.protokolle[0].rundenzeiten_ms[3:]
    mittelwert = statistics.median(zeiten)
    # Nur die Ermuedung und die nachlassenden Bremsen duerfen bremsen -
    # kein Verkehr. Ein Stau hinter einem Ueberrundeten kostete sofort
    # mehrere Prozent.
    assert max(zeiten) < mittelwert * 1.02


# --- Nachlauf des Ueberschusses -------------------------------------------
def test_nachlauf_steht_in_der_konfiguration(k) -> None:
    """50 m voll, danach die Haelfte - beides zentral eingestellt."""
    assert ws.nachlauf_m(k) == pytest.approx(50.0)
    assert ws.nachlauf_anteil(k) == pytest.approx(0.5)
    assert ws.nachlauf_anteil_ueberholter(k) == pytest.approx(0.5)


def _lauf_auf_gerader_strecke(k, strecke, nachlauf_m: float):
    """Ein Lauf, in dem ein Auto gerade vorbeigekommen ist.

    Der Nachlauf laesst sich von aussen kaum beobachten - er steckt im
    Zieltempo eines einzelnen Zeitschritts. Deshalb hier weiss: Lauf
    bauen, ein Auto auf eine Gerade stellen und ihm einen aufgebrauchten
    Sog verpassen, so wie es nach einem Ueberholmanoever aussieht.
    """
    k.roh["windschatten"]["nachlauf_m"] = nachlauf_m
    mittel = kr.mittlerer_ueberholzonenanteil(k, (strecke,))
    lauf = kr._Lauf(
        k, strecke, feld(k, k.wert("skala", "referenz"), anzahl=2), runden=3,
        seedquelle=Seedquelle(1), streckenmittel=mittel,
    )
    # Auf eine Gerade stellen, weit genug auseinander fuer keinen Sog.
    geraden = np.flatnonzero(lauf.geradennummer >= 0)
    stelle = int(geraden[len(geraden) // 2])
    lauf.distanz[:] = [stelle * lauf.ds, stelle * lauf.ds - 400.0]
    lauf.aktiv[:] = True
    return lauf, stelle


def test_nachlauf_hebt_das_tempo_nach_dem_vorbeifahren(k, strecke) -> None:
    """Wer vorbei ist, faellt nicht schlagartig auf sein freies Tempo."""
    lauf, stelle = _lauf_auf_gerader_strecke(k, strecke, nachlauf_m=50.0)
    ohne = lauf._ziel_tempo(0)[0]

    # So sieht es aus, wenn dieses Auto gerade vorbeigekommen ist.
    nummer = int(lauf.geradennummer[stelle])
    lauf.sog_verbraucht[0] = int(lauf._gerade_id(0, nummer))
    lauf.sog_nachlauf_wert[0] = 0.02
    lauf.sog_nachlauf_bis[0] = lauf.distanz[0] + 50.0
    lauf.sog_nachlauf_erst[0] = 1.0
    lauf.sog_nachlauf_dann[0] = 0.5
    mit = lauf._ziel_tempo(0)[0]

    assert mit > ohne
    assert mit == pytest.approx(ohne * 1.02)


def test_nach_50_m_bleibt_die_haelfte(k, strecke) -> None:
    """Der volle Ueberschuss endet nach 50 m, die Haelfte laeuft weiter."""
    lauf, stelle = _lauf_auf_gerader_strecke(k, strecke, nachlauf_m=50.0)
    nummer = int(lauf.geradennummer[stelle])
    lauf.sog_verbraucht[0] = int(lauf._gerade_id(0, nummer))
    lauf.sog_nachlauf_wert[0] = 0.02
    lauf.sog_nachlauf_erst[0] = 1.0
    lauf.sog_nachlauf_dann[0] = 0.5
    # Die 50 m sind schon vorbei.
    lauf.sog_nachlauf_bis[0] = lauf.distanz[0] - 1.0
    halb = lauf._ziel_tempo(0)[0]

    lauf.sog_nachlauf_wert[0] = 0.0
    ohne = lauf._ziel_tempo(0)[0]
    assert halb == pytest.approx(ohne * 1.01)


def test_der_ueberholte_bekommt_erst_spaeter_und_nur_die_haelfte(k, strecke) -> None:
    """Waehrend der ersten 50 m gar nichts, danach die Haelfte davon."""
    lauf, stelle = _lauf_auf_gerader_strecke(k, strecke, nachlauf_m=50.0)
    nummer = int(lauf.geradennummer[stelle])
    lauf.sog_verbraucht[0] = int(lauf._gerade_id(0, nummer))
    lauf.sog_nachlauf_wert[0] = 0.02
    lauf.sog_nachlauf_erst[0] = 0.0
    lauf.sog_nachlauf_dann[0] = 0.5 * 0.5

    lauf.sog_nachlauf_bis[0] = lauf.distanz[0] + 50.0
    frueh = lauf._ziel_tempo(0)[0]
    lauf.sog_nachlauf_bis[0] = lauf.distanz[0] - 1.0
    spaet = lauf._ziel_tempo(0)[0]

    assert spaet == pytest.approx(frueh * 1.005)


def test_ausserhalb_der_geraden_laeuft_nichts_nach(k, strecke) -> None:
    """Der Nachlauf endet mit der Geraden - spaetestens beim Anbremsen."""
    lauf, stelle = _lauf_auf_gerader_strecke(k, strecke, nachlauf_m=50.0)
    ohne = lauf._ziel_tempo(0)[0]
    # Eine fremde Gerade: der Nachlauf gehoert nicht hierher.
    lauf.sog_verbraucht[0] = int(lauf._gerade_id(0, int(lauf.geradennummer[stelle]))) + 1
    lauf.sog_nachlauf_wert[0] = 0.02
    lauf.sog_nachlauf_bis[0] = lauf.distanz[0] + 50.0
    lauf.sog_nachlauf_erst[0] = 1.0
    lauf.sog_nachlauf_dann[0] = 0.5
    assert lauf._ziel_tempo(0)[0] == pytest.approx(ohne)
