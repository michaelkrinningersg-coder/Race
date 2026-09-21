"""Tests fuer Fehler, Unfaelle und Defekte (GDD 4 und 14)."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import zwischenfall as zf
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def rennen(k, strecken) -> rn.Rennverlauf:
    """Ein laengeres Rennen, damit Zwischenfaelle ueberhaupt vorkommen."""
    from rennmanager.kern import reifen as rf

    zandvoort = next(s for s in strecken if s.name == "Zandvoort")
    haupt = Seedquelle(4711)
    feld = rn.starterfeld(k, seedquelle=haupt.zweig("feld"))
    verschleiss = rf.streckenfaktor(
        k, zandvoort, rf.mittlere_querbeschleunigung(strecken)
    )
    return rn.simuliere(
        k, zandvoort, feld, 12, haupt.zweig("rennen"),
        rn.mittlerer_ueberholzonenanteil(k, strecken),
        streckenverschleiss=verschleiss,
    )


# -- Fehler -----------------------------------------------------------------
def test_bessere_werte_machen_weniger_fehler(k) -> None:
    """GDD 4: Wahrscheinlichkeit aus den Eigenschaften (Bereich fe)."""
    schwach = zf.fehlerrate_je_runde(k, ka.gleichverteilt(k, 0))
    stark = zf.fehlerrate_je_runde(k, ka.gleichverteilt(k, 98_000))
    assert stark < schwach
    assert schwach == pytest.approx(k.wert("fehler", "rate_bei_null"))
    assert stark == pytest.approx(k.wert("fehler", "rate_bei_maximum"), abs=0.001)


def test_wetter_und_reifen_erhoehen_die_fehlerquote(k) -> None:
    """GDD 4: skaliert mit dem Wetter; GDD 4: Verschleiss erhoeht sie auch."""
    auto = ka.gleichverteilt(k, 50_000)
    trocken = zf.fehlerrate_je_runde(k, auto)
    nass = zf.fehlerrate_je_runde(k, auto, wetterfaktor=2.5)
    nass_und_hin = zf.fehlerrate_je_runde(k, auto, wetterfaktor=2.5, reifenfaktor=2.0)
    assert trocken < nass < nass_und_hin
    assert nass == pytest.approx(trocken * 2.5)


def test_fehlerrate_bleibt_eine_wahrscheinlichkeit(k) -> None:
    auto = ka.gleichverteilt(k, 0)
    assert zf.fehlerrate_je_runde(k, auto, wetterfaktor=100.0, reifenfaktor=100.0) <= 1.0


def test_der_zeitverlust_haelt_seinen_mittelwert(k) -> None:
    """Punkt 96: Die Tabelle wird auf ``mittelwert_ms`` normiert.

    Das ist der Grund, warum die Streuung das Balancing nicht bewegt: Ein
    Rennen verliert insgesamt so viel Zeit an Fehler wie mit der frueheren
    festen Zahl, nur ungleich verteilt.
    """
    soll = k.wert("fehler", "zeitverlust")["mittelwert_ms"]
    wuerfel = np.random.default_rng(1)
    gezogen = [zf.zeitverlust_ms(k, wuerfel) for _ in range(200_000)]
    assert np.mean(gezogen) == pytest.approx(soll, rel=0.01)
    # Ohne Wuerfel kommt der Erwartungswert zurueck - fuer alles, was
    # ohne Zufall rechnen soll (GDD 9).
    assert zf.zeitverlust_ms(k) == soll


def test_der_zeitverlust_streut_zwischen_den_grenzen(k) -> None:
    """Punkt 96: kein Fehler faellt aus der Tabelle heraus."""
    unten = zf.zeitverlust_bei(k, 0.0)
    oben = zf.zeitverlust_bei(k, 1.0)
    assert 0 < unten < oben
    wuerfel = np.random.default_rng(2)
    gezogen = [zf.zeitverlust_ms(k, wuerfel) for _ in range(20_000)]
    assert min(gezogen) >= unten
    assert max(gezogen) <= oben
    # Und es ist wirklich eine Spanne, keine Zahl mit Rauschen: Der
    # laengste Fehler kostet ein Mehrfaches des kuerzesten.
    assert oben > 4 * unten


def test_die_verteilung_steigt_monoton(k) -> None:
    """Wer weiter rechts zieht, steht laenger - sonst waere es keine Verteilung."""
    stellen = [i / 20 for i in range(21)]
    zeiten = [zf.zeitverlust_bei(k, a) for a in stellen]
    assert zeiten == sorted(zeiten)


def test_die_sigmabaender_stehen_wie_vorgegeben(k) -> None:
    """Punkt 96: die Eckwerte des Auftraggebers, um 0,9113 gestaucht.

    Vorgegeben waren Gipfel 1,20 s und die Baender 0,80/1,80 (1 Sigma),
    0,60/3,00 (2 Sigma) und 0,32/4,60 (4 Sigma). Weil die Tabelle auf
    ihren Erwartungswert normiert wird, stehen sie um denselben Faktor
    gestaucht da - das Verhaeltnis untereinander bleibt.
    """
    faktor = zf.zeitverlust_bei(k, 0.5) / 1200.0
    erwartet = {
        0.158655: 800, 0.841345: 1800,      # 1 Sigma
        0.022750: 600, 0.977250: 3000,      # 2 Sigma
        0.000032: 320, 0.999968: 4600,      # 4 Sigma
        0.0: 300, 1.0: 5000,                # harte Grenzen
    }
    for anteil, roh in erwartet.items():
        assert zf.zeitverlust_bei(k, anteil) == pytest.approx(roh * faktor, abs=2)


def test_eine_kaputte_verteilung_faellt_auf(k) -> None:
    """Ungleich lange Listen sind ein Konfigurationsfehler, kein stiller Zufall."""
    import copy
    from dataclasses import replace

    roh = copy.deepcopy(k.roh)
    roh["fehler"]["zeitverlust"]["sekunden"] = roh["fehler"]["zeitverlust"]["sekunden"][:-1]
    with pytest.raises(ValueError, match="Anteile"):
        zf.zeitverlustverteilung(replace(k, roh=roh))


# -- Defekte ----------------------------------------------------------------
def test_zuverlaessige_autos_haben_weniger_defekte(k) -> None:
    schwach = zf.defektrate_je_runde(k, ka.gleichverteilt(k, 0), 20)
    stark = zf.defektrate_je_runde(k, ka.gleichverteilt(k, 98_000), 20)
    assert stark < schwach


def test_defektrate_verteilt_sich_auf_die_runden(k) -> None:
    auto = ka.gleichverteilt(k, 0)
    je_rennen = k.wert("defekte", "rate", "je_auto_und_rennen_bei_null")
    assert zf.defektrate_je_runde(k, auto, 20) == pytest.approx(je_rennen / 20)


def test_defekt_kommt_aus_der_liste(k) -> None:
    wuerfel = np.random.default_rng(1)
    bekannt = {d["schluessel"] for d in k.wert("defekte", "liste")}
    for _ in range(100):
        assert zf.waehle_defekt(k, wuerfel)["schluessel"] in bekannt


def test_defekte_senken_das_tempo(k) -> None:
    liste = k.wert("defekte", "liste")
    assert zf.tempofaktor_defekte(k, []) == 1.0
    einer = zf.tempofaktor_defekte(k, [liste[0]])
    assert einer < 1.0
    mehrere = zf.tempofaktor_defekte(k, liste[:5])
    assert mehrere < einer


def test_gesamtmalus_ist_gedeckelt(k) -> None:
    """GDD 14: hoechstens 50 % Fahrzeugzustand."""
    grenze = k.wert("defekte", "max_gesamtmalus")
    alle = k.wert("defekte", "liste")
    assert zf.tempofaktor_defekte(k, alle) == pytest.approx(1.0 - grenze)


# -- Unfaelle ---------------------------------------------------------------
def test_ausfallgrenze_liegt_zwischen_null_und_fuenf(k) -> None:
    """GDD 4: je Rennen wird eine Obergrenze von 0 bis 5 gewuerfelt."""
    wuerfel = np.random.default_rng(1)
    werte = {zf.ausfallgrenze(k, wuerfel) for _ in range(200)}
    assert werte <= set(range(k.wert("unfaelle", "ausfaelle_min"),
                              k.wert("unfaelle", "ausfaelle_max") + 1))
    assert max(werte) == k.wert("unfaelle", "ausfaelle_max")


def test_unfallrate_haengt_an_der_zeit_nicht_am_zeitschritt(k) -> None:
    """Sonst haengt die Haeufigkeit an der Schrittweite der Simulation."""
    assert zf.unfallrate(k, 1.0) == pytest.approx(
        k.wert("unfaelle", "rate", "je_sekunde_in_reichweite")
    )
    assert zf.unfallrate(k, 0.1) == pytest.approx(zf.unfallrate(k, 1.0) / 10)
    assert zf.unfallrate(k, 1.0, wetterfaktor=2.5) == pytest.approx(
        zf.unfallrate(k, 1.0) * 2.5
    )


def test_manchmal_sind_beide_autos_betroffen(k) -> None:
    """GDD 4: mal scheidet ein Auto aus, mal beide."""
    wuerfel = np.random.default_rng(1)
    ergebnisse = [zf.beide_betroffen(k, wuerfel) for _ in range(2_000)]
    anteil = sum(ergebnisse) / len(ergebnisse)
    assert anteil == pytest.approx(k.wert("unfaelle", "rate", "anteil_beide_autos"), abs=0.03)


# -- Im Rennen --------------------------------------------------------------
def test_zwischenfaelle_sind_vollstaendig_beschrieben(rennen) -> None:
    for vorfall in rennen.zwischenfaelle:
        assert vorfall.art in (zf.Art.FEHLER, zf.Art.UNFALL, zf.Art.DEFEKT)
        assert 0 <= vorfall.teilnehmer < rennen.anzahl
        assert vorfall.zeit_ms >= 0
        assert vorfall.beschreibung


def test_ausfaelle_bleiben_unter_der_grenze(rennen, k) -> None:
    ausgefallen = [v for v in rennen.zwischenfaelle if v.ausgefallen]
    assert len(ausgefallen) <= k.wert("unfaelle", "ausfaelle_max")


def test_fehler_kosten_zeit(rennen) -> None:
    fehler = [v for v in rennen.zwischenfaelle if v.art == zf.Art.FEHLER]
    assert fehler, "In 12 Runden sollte mindestens ein Fehler passieren"
    for vorfall in fehler:
        assert vorfall.zeitverlust_ms > 0


def test_reifen_bauen_ueber_das_rennen_ab(rennen) -> None:
    """GDD 4: Verschleiss senkt das Tempo."""
    assert rennen.reifenzustand[0].min() == pytest.approx(1.0)
    letzte = rennen.reifenzustand[-1]
    assert letzte.max() < 1.0
    # Die Autos bauen unterschiedlich schnell ab - erst dadurch entstehen
    # spaete Positionswechsel.
    assert letzte.max() - letzte.min() > 0.01


def test_reifenzustand_faellt_monoton(rennen) -> None:
    aenderung = np.diff(rennen.reifenzustand, axis=0)
    assert (aenderung <= 1e-9).all()


def test_zwischenfaelle_lassen_sich_je_auto_abfragen(rennen) -> None:
    """GDD 4: im Ranking markiert, Details per Mouseover."""
    gezaehlt = Counter(v.teilnehmer for v in rennen.zwischenfaelle)
    for i in range(rennen.anzahl):
        assert len(rennen.zwischenfaelle_von(i)) == gezaehlt[i]


def test_ohne_zufall_gibt_es_keine_zwischenfaelle(k, strecken) -> None:
    """GDD 9 kalibriert ohne Zufall - dann auch ohne Pannen und Verschleiss."""
    zandvoort = next(s for s in strecken if s.name == "Zandvoort")
    feld = rn.starterfeld(k)
    verlauf = rn.simuliere(
        k, zandvoort, feld, 4, Seedquelle(1),
        rn.mittlerer_ueberholzonenanteil(k, strecken), ohne_zufall=True,
    )
    assert verlauf.zwischenfaelle == ()
    assert verlauf.reifenzustand[-1].min() == pytest.approx(1.0)


# -- Punkt 61: Der Fehler kostet Zeit im Stand ------------------------------
def test_ein_fehler_stellt_das_auto_und_laesst_es_wieder_anfahren(k) -> None:
    """Kein Zeitabzug, sondern Stillstand mit Wiederanfahren.

    Gemessen am Tempo: Es faellt auf 0, bleibt die feste Zeit dort und
    steigt danach ueber die Beschleunigungskurve wieder an - nicht
    sprunghaft auf das alte Tempo.
    """
    from rennmanager.kern import auto as kern_auto
    from rennmanager.kern import rennen as kr
    from rennmanager.kern import strecke as kern_strecke
    from rennmanager.kern.zufall import Seedquelle

    strecke = kern_strecke.lade(k, k.strecken[0]["name"])
    feld = tuple(
        kr.Teilnehmer(
            auto=kern_auto.gleichverteilt(k, 50_000, kuerzel=f"A{i}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i in range(2)
    )
    lauf = kr._Lauf(
        k, strecke, feld, runden=3, seedquelle=Seedquelle(1),
        streckenmittel=kr.mittlerer_ueberholzonenanteil(k, (strecke,)),
    )
    lauf.aktiv[:] = True
    lauf.distanz[:] = [2000.0, 500.0]
    lauf.reaktion[:] = 0.0
    for _ in range(5):  # erst einmal auf Tempo kommen
        lauf.schritt(0, 0.02)
    schnell = float(lauf.tempo[0])
    assert schnell > 0.0

    lauf.pause_ms[0] = float(zf.zeitverlust_ms(k))
    lauf.schritt(0, 0.02)
    assert lauf.tempo[0] == 0.0  # steht sofort

    # Waehrend der Pause bleibt es stehen.
    schritte = int(zf.zeitverlust_ms(k) / 20) - 1
    for _ in range(schritte):
        lauf.schritt(0, 0.02)
        assert lauf.tempo[0] == 0.0

    # Danach faehrt es wieder an - aber nicht sofort auf das alte Tempo.
    lauf.schritt(0, 0.02)
    lauf.schritt(0, 0.02)
    assert 0.0 < lauf.tempo[0] < schnell
