"""Tests fuer den Reifenverschleiss (GDD 4)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import reifen as rf
from rennmanager.kern import strecke as st
from rennmanager.kern.auto import Auto

DISTANZ = 200_000.0


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


def mit(k, schluessel: str, wert: int, grund: int = 50_000) -> Auto:
    """Auto mit einem abweichenden Wert; Schluessel auch aus den Zusatzwerten."""
    werte = {f.schluessel: grund for f in k.faehigkeiten}
    zusatz = {rf.FLUESTERER: grund}
    if schluessel in werte:
        werte[schluessel] = wert
    else:
        zusatz[schluessel] = wert
    return Auto("TST", "Test", werte, zusatz)


# -- Zustand und Wirkung ----------------------------------------------------
def test_frische_reifen_kosten_nichts(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    assert rf.zustand(0.0) == 1.0
    # Punkt 39: Ein frischer Reifen ist **nicht** der schnellste - das
    # Optimum liegt bei 85 % Restprofil. Er ist aber nah dran.
    assert rf.tempofaktor(k, auto, 0.0) < 1.0
    assert rf.tempofaktor(k, auto, 0.15) == pytest.approx(1.0)


def test_abgefahrene_reifen_kosten_tempo(k) -> None:
    """GDD 4: Verschleiss senkt das Tempo und erhoeht die Fehlerquote."""
    auto = mit(k, rf.FLUESTERER, 0)
    einstellung = k.wert("reifen", "verschleiss")
    boden = min(einstellung["grip_stuetzstellen"]) / rf.bestgrip(k)
    assert rf.tempofaktor(k, auto, 1.0) == pytest.approx(boden)
    assert rf.fehlerfaktor(k, auto, 1.0) == pytest.approx(
        1.0 + einstellung["fehlerzuschlag_voll"]
    )


def test_der_grip_hat_sein_optimum_bei_fuenfundachtzig_prozent(k) -> None:
    """Punkt 39: Ein frischer Reifen muss erst arbeiten.

    Genau das macht einen langen Stint wertvoll und einen fruehen Stopp
    riskant. Die alte Parabel fiel ab der ersten Runde. Das Optimum steht
    in der Konfiguration (Kurve "optimum_bei_85"), nicht hier.
    """
    einstellung = k.wert("reifen", "verschleiss")
    bestes_profil = max(
        zip(
            einstellung["grip_stuetzstellen"],
            einstellung["zustand_stuetzstellen"],
            strict=True,
        )
    )[1]
    werte = [(rf.grip(k, z / 100.0), z) for z in range(101)]
    assert max(werte)[1] == round(bestes_profil * 100)
    assert rf.grip(k, 1.0) < rf.grip(k, bestes_profil)
    assert rf.grip(k, 0.95) > rf.grip(k, 1.0)
    # Am Boden bleibt die unterste Stuetzstelle - deutlich unter der Haelfte
    # des frischen Reifens.
    assert rf.grip(k, 0.0) == pytest.approx(min(einstellung["grip_stuetzstellen"]))
    assert rf.grip(k, 0.0) < rf.grip(k, 1.0) / 2.0


def test_die_fehlerquote_folgt_derselben_kurve(k) -> None:
    """Abgefahrene Reifen kosten Zeit **und** machen Fehler - ab derselben
    Stelle. Frueher stieg die Fehlerquote schon, waehrend die Reifen noch
    besser wurden."""
    auto = mit(k, rf.FLUESTERER, 0)
    im_optimum = rf.fehlerfaktor(k, auto, 0.15)
    frisch = rf.fehlerfaktor(k, auto, 0.0)
    abgefahren = rf.fehlerfaktor(k, auto, 0.9)
    assert im_optimum == pytest.approx(1.0)
    assert frisch > im_optimum
    assert abgefahren > frisch


def test_der_abfall_wird_gegen_ende_steiler(k) -> None:
    """Die Form der Kurve: ab dem Optimum nimmt der Gripverlust zu.

    Frueher stand hier eine Parabel, die schon ab dem ersten Meter fiel.
    Jetzt faellt der Grip erst ab dem Optimum bei 85 %, dann flach, und
    gegen Ende steil.
    """
    stufen = [0.85, 0.65, 0.45, 0.25, 0.05]
    grips = [rf.grip(k, z) for z in stufen]
    # Ab dem Optimum faellt er durchgehend.
    assert grips == sorted(grips, reverse=True)
    # Und je Fuenftel immer staerker.
    schritte = [grips[i] - grips[i + 1] for i in range(len(grips) - 1)]
    assert schritte == sorted(schritte)


def test_gute_reifenwerte_bauen_langsamer_ab(k) -> None:
    """Der Bereich ve traegt den Verschleiss - vor allem F10 und D14."""
    m = rf.standardmischung(k)
    schwach = rf.verschleiss_je_meter(k, ka.gleichverteilt(k, 0), m)
    stark = rf.verschleiss_je_meter(k, ka.gleichverteilt(k, 98_000), m)
    assert stark < schwach


def test_der_verschleiss_haengt_an_der_strecke_nicht_an_der_renndistanz(k) -> None:
    """Punkt 39: Genau darum gibt es ueberhaupt Boxenstopps.

    Vorher war die Rate durch die Renndistanz geteilt, ein Satz hielt
    also per Konstruktion ein Rennen - egal ob 100 oder 300 Kilometer.
    Jetzt traegt ein Stint eine feste Strecke, und wie viele Stopps ein
    Rennen kostet, ergibt sich daraus.
    """
    auto = ka.gleichverteilt(k, 50_000)
    m = rf.standardmischung(k)
    weite = rf.stintweite_m(k, auto, m)
    assert rf.verschleiss_je_meter(k, auto, m) == pytest.approx(1.0 / weite)
    # Nach der Stintweite sind die Reifen genau hin.
    assert rf.zustand(rf.verschleiss_je_meter(k, auto, m) * weite) == pytest.approx(
        0.0, abs=1e-9
    )
    # Auf halber Strecke noch halb da.
    assert rf.zustand(
        rf.verschleiss_je_meter(k, auto, m) * weite / 2
    ) == pytest.approx(0.5)


def test_weiche_mischungen_halten_kuerzer(k) -> None:
    """Wer schneller faehrt, haelt kuerzer - das ist die ganze Abwaegung."""
    auto = ka.gleichverteilt(k, 50_000)
    trocken = [m for m in rf.mischungen(k) if m.naesse == 0.0]
    weiten = [rf.stintweite_m(k, auto, m) for m in trocken]
    tempi = [rf.mischungsfaktor(k, m) for m in trocken]
    # Nach Tempo geordnet faellt die Stintweite monoton.
    paare = sorted(zip(tempi, weiten, strict=True), reverse=True)
    assert [w for _, w in paare] == sorted(w for _, w in paare)


def test_eine_unpassende_mischung_kostet_tempo_und_haelt_kuerzer(k) -> None:
    """Trockenreifen im Starkregen, Regenreifen auf trockener Strecke."""
    auto = ka.gleichverteilt(k, 50_000)
    trocken = rf.standardmischung(k)
    regen = rf.mischung(k, "regen")

    # Trocken auf trocken schlaegt Regen auf trocken.
    assert rf.mischungsfaktor(k, trocken, 0.0) > rf.mischungsfaktor(k, regen, 0.0)
    assert rf.stintweite_m(k, auto, trocken, naesse=0.0) > rf.stintweite_m(
        k, auto, regen, naesse=0.0
    )
    # Und umgekehrt unter Wasser.
    assert rf.mischungsfaktor(k, regen, 1.0) > rf.mischungsfaktor(k, trocken, 1.0)
    assert rf.stintweite_m(k, auto, regen, naesse=1.0) > rf.stintweite_m(
        k, auto, trocken, naesse=1.0
    )


def test_die_naesse_kommt_aus_der_wetterlage(k) -> None:
    assert rf.naesse_von(k, "trocken") == 0.0
    assert rf.naesse_von(k, "starkregen") == 1.0
    # Mehrere Lagen zugleich: Es zaehlt die nasseste.
    assert rf.naesse_von(k, ("trocken", "regen")) == rf.naesse_von(k, "regen")


def test_wetter_und_strecke_skalieren_den_verschleiss(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    m = rf.standardmischung(k)
    normal = rf.verschleiss_je_meter(k, auto, m)
    hart = rf.verschleiss_je_meter(k, auto, m, streckenfaktor_wert=1.3)
    heiss = rf.verschleiss_je_meter(k, auto, m, wetterfaktor=1.4)
    assert hart == pytest.approx(normal * 1.3)
    assert heiss == pytest.approx(normal * 1.4)


# -- Reifenfluesterer -------------------------------------------------------
def test_fluesterer_senkt_die_wirkung_nicht_den_verschleiss(k) -> None:
    """Der Unterschied zu D14: D14 bremst den Abbau, der Fluesterer seine Folgen."""
    ohne = mit(k, rf.FLUESTERER, 0)
    mit_koennen = mit(k, rf.FLUESTERER, 100_000)

    # Gleicher Verschleiss ...
    m = rf.standardmischung(k)
    assert rf.verschleiss_je_meter(k, ohne, m) == pytest.approx(
        rf.verschleiss_je_meter(k, mit_koennen, m)
    )
    # ... aber geringere Wirkung.
    assert rf.tempofaktor(k, mit_koennen, 1.0) > rf.tempofaktor(k, ohne, 1.0)
    assert rf.fehlerfaktor(k, mit_koennen, 1.0) < rf.fehlerfaktor(k, ohne, 1.0)


def test_fluesterer_daempft_hoechstens_wie_vorgegeben(k) -> None:
    max_daempfung = k.wert("reifen", "fluesterer", "max_daempfung")
    einstellung = k.wert("reifen", "verschleiss")
    voller_verlust = 1.0 - min(einstellung["grip_stuetzstellen"]) / rf.bestgrip(k)
    bester = mit(k, rf.FLUESTERER, 100_000)
    assert 1.0 - rf.tempofaktor(k, bester, 1.0) == pytest.approx(
        voller_verlust * (1.0 - max_daempfung), rel=0.02
    )


def test_d14_und_fluesterer_wirken_verschieden(k) -> None:
    """Beide helfen, aber an verschiedenen Stellen."""
    schoner = mit(k, "D14", 100_000)
    fluesterer = mit(k, rf.FLUESTERER, 100_000)

    # D14 senkt den Abbau ...
    m = rf.standardmischung(k)
    assert rf.verschleiss_je_meter(k, schoner, m) < rf.verschleiss_je_meter(
        k, fluesterer, m
    )
    # ... der Fluesterer die Wirkung bei gleichem Abbau.
    assert rf.tempofaktor(k, fluesterer, 0.8) > rf.tempofaktor(k, schoner, 0.8)


# -- Streckenfaktor ---------------------------------------------------------
def test_streckenfaktor_trennt_enge_von_schnellen_kurven(k, strecken) -> None:
    """Entscheidung zu Punkt 10: Grundlage ist die Querbeschleunigung."""
    mittel = rf.mittlere_querbeschleunigung(strecken)
    faktor = {s.name: rf.streckenfaktor(k, s, mittel) for s in strecken}

    # Zandvoort ist eng, Monza schnell.
    assert faktor["Zandvoort"] > faktor["Monza"]
    # Suzuka hat viele, aber schnelle Kurven - deutlich unter Zandvoort.
    assert faktor["Suzuka"] < faktor["Zandvoort"]
    # Catalunya nennt GDD 3 ausdruecklich beim Reifenverschleiss.
    assert faktor["Catalunya"] > 1.0


def test_streckenfaktor_ist_auf_den_mittelwert_normiert(k, strecken) -> None:
    mittel = rf.mittlere_querbeschleunigung(strecken)
    faktoren = [rf.streckenfaktor(k, s, mittel) for s in strecken]
    assert sum(faktoren) / len(faktoren) == pytest.approx(1.0, abs=0.05)
