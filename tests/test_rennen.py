"""Tests fuer die Rennsimulation (GDD 4).

Weil ein volles Rennen ueber 10 Ligen und 69 Runden laeuft, arbeiten die
meisten Tests mit wenigen Runden und kleinen Feldern. Die teuren Laeufe
stehen in Fixtures mit ``scope="module"``.
"""

from __future__ import annotations

import numpy as np
import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as ka
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import tempo as tp
from rennmanager.kern.zufall import Seedquelle

# Feldgroesse aus der Konfiguration (Punkt 95: 40 statt 30 Autos).
FELD = kf.lade().wert("rennen", "autos")


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def mittel(k, strecken) -> float:
    return rn.mittlerer_ueberholzonenanteil(k, strecken)


@pytest.fixture(scope="module")
def zandvoort(strecken) -> st.Strecke:
    return next(s for s in strecken if s.name == "Zandvoort")


@pytest.fixture(scope="module")
def rennen(k, zandvoort, mittel) -> rn.Rennverlauf:
    """Kurzes Rennen mit regulaerer Aufstellung."""
    feld = rn.starterfeld(k, spielerplatz=FELD)
    return rn.simuliere(k, zandvoort, feld, 3, Seedquelle(4711), mittel)


@pytest.fixture(scope="module")
def umgedreht(k, zandvoort, mittel) -> rn.Rennverlauf:
    """Staerkstes Auto startet hinten - erzwingt Ueberholmanoever."""
    feld = rn.starterfeld(k, umgedreht=True)
    return rn.simuliere(k, zandvoort, feld, 3, Seedquelle(4711), mittel)


# -- Startaufstellung -------------------------------------------------------
def test_startaufstellung_haelt_fuenf_meter_abstand(k) -> None:
    """GDD 4: 5 m je Platz; Platz 40 steht damit 195 m hinter Platz 1."""
    assert rn.startdistanz_m(k, 1) == 0.0
    assert rn.startdistanz_m(k, 2) == -5.0
    assert rn.startdistanz_m(k, 40) == -195.0


def test_reaktionszeit_liegt_im_vorgegebenen_band(k) -> None:
    """GDD 4: Reaktionszeit 0,100 bis 0,300 s."""
    schnellste = k.wert("start", "reaktionszeit_min_ms")
    langsamste = k.wert("start", "reaktionszeit_max_ms")
    for s in (0, 10_000, 50_000, 98_000, 100_000):
        zeit = rn.reaktionszeit_ms(k, ka.gleichverteilt(k, s))
        assert schnellste <= zeit <= langsamste


def test_bessere_reaktion_startet_frueher(k) -> None:
    schwach = rn.reaktionszeit_ms(k, ka.gleichverteilt(k, 0))
    stark = rn.reaktionszeit_ms(k, ka.gleichverteilt(k, 98_000))
    assert stark < schwach
    assert stark == k.wert("start", "reaktionszeit_min_ms")
    assert schwach == k.wert("start", "reaktionszeit_max_ms")


def test_autos_stehen_bis_zur_reaktionszeit(rennen, k) -> None:
    """Vor der Reaktionszeit bewegt sich nichts (GDD 4)."""
    am_anfang = rennen.distanzen_zu(0)
    # Die Startaufstellung: 5 m Abstand, Platz 1 auf der Linie.
    erwartet = [rn.startdistanz_m(k, t.startplatz) for t in rennen.teilnehmer]
    assert np.allclose(am_anfang, erwartet)

    # Die schnellste Reaktion betraegt 100 ms. Gemessen wird am ersten
    # Messpunkt nach dem Start - die stehen 200 ms auseinander. Bis
    # dahin hat ein Auto im Schnitt 6,5 cm zurueckgelegt; eines, das von
    # Anfang an rollte, schaffte in derselben Zeit mehrere Meter.
    #
    # Gemessen wird die **Summe** ueber das Feld, nicht jedes Auto fuer
    # sich: Seit Punkt 101 faehrt das ganze Feld auf Liga-1-Niveau, und
    # die Ueberholpruefung misst den Abstand gegen das *Zieltempo* des
    # Hintermanns statt gegen sein gefahrenes. Auf der Start-Ziel-Geraden
    # von Zandvoort liegt dieses Ziel bei ueber 100 m/s, womit die 5 m
    # Startabstand gerade als "dicht auf" gelten - in der ersten Sekunde
    # tauschen deshalb Autos die Plaetze, die kaum rollen. Ein Tausch
    # laesst die Summe unberuehrt, ein gefahrener Meter nicht.
    gefahren = rennen.distanzen_zu(200).sum() - am_anfang.sum()
    assert abs(gefahren) / len(am_anfang) < 0.15
    # Nach einer Sekunde ist das Feld unterwegs - gemessen 3,85 m je
    # Auto, also das Fuenfundzwanzigfache der ersten 200 ms.
    nach_einer_sekunde = rennen.distanzen_zu(1_000).sum() - am_anfang.sum()
    assert nach_einer_sekunde / len(am_anfang) > 3.0


def test_start_erfolgt_aus_dem_stand(rennen) -> None:
    """Kein Sprung auf Profiltempo: die Autos beschleunigen."""
    strecken_nach_2s = rennen.distanzen_zu(2_000) - rennen.distanzen_zu(0)
    strecken_nach_4s = rennen.distanzen_zu(4_000) - rennen.distanzen_zu(2_000)
    # In der zweiten Sekundenpaarung ist das Auto schneller als in der ersten.
    assert (strecken_nach_4s > strecken_nach_2s).all()


# -- Rundenzahl -------------------------------------------------------------
def test_rundenzahl_folgt_der_distanz(k, zandvoort) -> None:
    """GDD 4: Rundenzahl = Distanz durch Streckenlaenge, aufgerundet."""
    import math

    km = k.wert("rennen", "distanz_km")
    erwartet = math.ceil(km * 1000 / zandvoort.laenge_m)
    assert rn.rundenzahl(k, zandvoort) == erwartet


# -- Verlauf ----------------------------------------------------------------
def test_jedes_auto_wird_gewertet(rennen) -> None:
    """Auch Ausgefallene stehen im Ergebnis, ganz hinten (GDD 4)."""
    assert len(rennen.ergebnisse) == FELD
    angekommen = [e for e in rennen.ergebnisse if e.zeit_ms is not None]
    ausgefallen = [e for e in rennen.ergebnisse if e.zeit_ms is None]
    assert angekommen, "Mindestens ein Auto muss ankommen"
    # Ausgefallene stehen hinter allen Angekommenen.
    if ausgefallen:
        assert min(e.platz for e in ausgefallen) > max(e.platz for e in angekommen)


def test_platzierungen_sind_luckenlos(rennen) -> None:
    assert [e.platz for e in rennen.ergebnisse] == list(range(1, FELD + 1))
    assert len({e.teilnehmer for e in rennen.ergebnisse}) == FELD


def test_ausgefallene_stehen_nach_runden_und_zeit(k, zandvoort, mittel) -> None:
    """Punkt 95: mehr Runden zuerst, bei gleicher Rundenzahl die kuerzere Zeit.

    Bis dahin entschied unter gleich weit gekommenen Ausfaellen das Los.
    Der erhoehte Streckenverschleiss sorgt dafuer, dass in diesem kurzen
    Rennen ueberhaupt jemand ausfaellt. Welcher Seed dabei zwei Ausfaelle
    mit gleicher Rundenzahl liefert, haengt am ganzen Rennmodell - der
    Test sucht sich deshalb den ersten passenden, statt sich an eine Zahl
    zu binden, die die naechste Balancing-Aenderung umwirft.
    """
    feld = rn.starterfeld(k, seedquelle=Seedquelle(1))

    def paare_von(verlauf):
        ausfaelle = [e for e in verlauf.ergebnisse if e.zeit_ms is None]
        return ausfaelle, [
            (davor, danach)
            for davor, danach in zip(ausfaelle, ausfaelle[1:], strict=False)
            if davor.runden == danach.runden
        ]

    for seed in (22, 1, 5, 11, 7):
        verlauf = rn.simuliere(
            k, zandvoort, feld, 12, Seedquelle(seed), mittel, streckenverschleiss=6.0
        )
        ausfaelle, paare = paare_von(verlauf)
        if paare:
            break
    else:  # pragma: no cover - nur, wenn niemand mehr gleich weit kommt
        pytest.fail("Kein Seed lieferte zwei Ausfaelle mit gleicher Rundenzahl")

    def letzte_rundenzeit(ergebnis) -> int:
        enden = verlauf.protokolle[ergebnis.teilnehmer].rundenende_ms
        return enden[-1] if enden else 0

    # Mehr Runden stehen vorn.
    assert [e.runden for e in ausfaelle] == sorted(
        (e.runden for e in ausfaelle), reverse=True
    )
    # Und bei gleicher Rundenzahl der Schnellere.
    for davor, danach in paare:
        assert letzte_rundenzeit(davor) <= letzte_rundenzeit(danach)


def test_die_form_faellt_je_sektor_nicht_je_runde(k, zandvoort, mittel) -> None:
    """Punkt 95: Innerhalb einer Runde schwankt es jetzt sichtbar.

    Verglichen wird gegen denselben Lauf ohne Zufall: Das Verhaeltnis der
    Sektorzeiten zeigt, was der Zufall getan hat. Bei einem Wurf je Runde
    waeren die vier Verhaeltnisse einer Runde bis auf Reifenverschleiss
    und Verkehr gleich; mit einem Wurf je Sektor gehen sie auseinander.
    """
    feld = rn.starterfeld(k, seedquelle=Seedquelle(1))[:6]
    mit = rn.simuliere(k, zandvoort, feld, 4, Seedquelle(3), mittel)
    ohne = rn.simuliere(k, zandvoort, feld, 4, Seedquelle(3), mittel, ohne_zufall=True)

    spannen = []
    for i in range(len(feld)):
        for gewuerfelt, fest in zip(
            mit.protokolle[i].sektorzeiten_ms,
            ohne.protokolle[i].sektorzeiten_ms,
            strict=False,
        ):
            wenn = [a / b for a, b in zip(gewuerfelt, fest, strict=False)]
            if len(wenn) == len(zandvoort.sektoren):
                spannen.append(max(wenn) - min(wenn))

    assert spannen, "Der Test braucht vollstaendige Runden"
    # Gemessen liegen die Spannen bei 0,3 bis 0,6 %; 0,15 % lassen Luft
    # nach unten und faengt trotzdem einen Rueckfall auf einen Wurf je
    # Runde ab.
    assert sum(spannen) / len(spannen) > 0.0015


def test_sieger_faehrt_die_volle_distanz(rennen) -> None:
    assert rennen.ergebnisse[0].runden == rennen.runden


def test_rennende_bei_der_naechsten_zielueberfahrt(rennen) -> None:
    """GDD 4: Nach dem Sieger beendet jedes Auto bei seiner naechsten Ueberfahrt."""
    for ergebnis in rennen.ergebnisse:
        # Niemand faehrt mehr Runden als vorgesehen ...
        assert ergebnis.runden <= rennen.runden
        # ... und niemand hoert mehr als eine Runde frueher auf, solange er
        # nicht ueberrundet wurde.
        assert ergebnis.rundenrueckstand >= 0


def test_rueckstand_waechst_mit_dem_platz(rennen) -> None:
    rueckstaende = [
        e.rueckstand_ms for e in rennen.ergebnisse if e.rueckstand_ms is not None
    ]
    assert rueckstaende[0] == 0
    assert rueckstaende == sorted(rueckstaende)


def test_zeiten_sind_ganze_millisekunden(rennen) -> None:
    for ergebnis in rennen.ergebnisse:
        assert ergebnis.zeit_ms is None or isinstance(ergebnis.zeit_ms, int)
    for protokoll in rennen.protokolle:
        assert all(isinstance(zeit, int) for zeit in protokoll.rundenzeiten_ms)


def test_jedes_auto_hat_rundenzeiten_und_sektoren(rennen, k) -> None:
    """GDD 4: Zeitenmonitor mit letzter Runde, bester Runde, 4 Sektorzeiten."""
    sektoren = k.wert("strecke", "sektoren")
    ausgefallen = {e.teilnehmer for e in rennen.ergebnisse if e.zeit_ms is None}
    for i, protokoll in enumerate(rennen.protokolle):
        if i in ausgefallen and not protokoll.rundenzeiten_ms:
            # Wer in der ersten Runde ausfaellt, hat keine Rundenzeit.
            continue
        assert protokoll.rundenzeiten_ms, f"Auto {i} ohne Rundenzeit"
        assert protokoll.beste_runde_ms == min(protokoll.rundenzeiten_ms)
        assert protokoll.letzte_runde_ms == protokoll.rundenzeiten_ms[-1]
        for zeiten in protokoll.sektorzeiten_ms:
            assert len(zeiten) == sektoren


def test_sektorzeiten_ergeben_die_rundenzeit(rennen) -> None:
    for protokoll in rennen.protokolle:
        for runde, sektoren in zip(
            protokoll.rundenzeiten_ms, protokoll.sektorzeiten_ms, strict=True
        ):
            assert sum(sektoren) == pytest.approx(runde, abs=3)


def test_freie_fahrt_entspricht_der_einzelrunde(k, zandvoort, mittel) -> None:
    """Ein Auto allein muss im Rennen so schnell sein wie in der Einzelrunde.

    Das prueft, dass die Rennschleife dasselbe Modell benutzt wie
    rennmanager.kern.tempo und nicht heimlich langsamer oder schneller ist.
    Gefahren wird ohne Zufall, wie es GDD 9 zur Kalibrierung verlangt.
    """
    auto = ka.gleichverteilt(k, 8_400, "EIN")
    solo = tp.fahre_runde(k, zandvoort, auto)
    verlauf = rn.simuliere(
        k, zandvoort, (rn.Teilnehmer(auto=auto, startplatz=1, farbe="#fff"),),
        3, Seedquelle(1), mittel, ohne_zufall=True,
    )
    # Die erste Runde enthaelt den stehenden Start, ab der zweiten faehrt
    # das Auto fliegend.
    fliegend = verlauf.protokolle[0].rundenzeiten_ms[1]
    assert fliegend == pytest.approx(solo.zeit_ms, rel=0.001)


def test_erste_runde_ist_wegen_des_starts_langsamer(k, zandvoort, mittel) -> None:
    auto = ka.gleichverteilt(k, 8_400, "EIN")
    verlauf = rn.simuliere(
        k, zandvoort, (rn.Teilnehmer(auto=auto, startplatz=1, farbe="#fff"),),
        3, Seedquelle(1), mittel, ohne_zufall=True,
    )
    zeiten = verlauf.protokolle[0].rundenzeiten_ms
    assert zeiten[0] > zeiten[1]


# -- Ueberholen -------------------------------------------------------------
def test_ohne_tempovorteil_wird_nicht_ueberholt(k, zandvoort, mittel) -> None:
    """Gleich schnelle Autos duerfen die Reihenfolge nicht tauschen.

    Ohne Zufall sind die Autos wirklich gleich schnell; mit Zufall
    unterscheiden sie sich und duerfen sich ueberholen.
    """
    gleich = tuple(
        rn.Teilnehmer(auto=ka.gleichverteilt(k, 8_400, f"G{n:02d}"), startplatz=n, farbe="#fff")
        for n in range(1, 6)
    )
    verlauf = rn.simuliere(k, zandvoort, gleich, 2, Seedquelle(7), mittel, ohne_zufall=True)
    assert verlauf.manoever == ()


def test_umgedrehtes_feld_erzwingt_ueberholmanoever(umgedreht) -> None:
    assert len(umgedreht.manoever) > 0


def test_schnellstes_auto_arbeitet_sich_nach_vorn(umgedreht) -> None:
    """Vom letzten Platz aus muss das staerkste Auto Plaetze gutmachen."""
    staerkstes = next(
        i for i, t in enumerate(umgedreht.teilnehmer) if t.auto.kuerzel == "A01"
    )
    ergebnis = next(e for e in umgedreht.ergebnisse if e.teilnehmer == staerkstes)
    assert umgedreht.teilnehmer[staerkstes].startplatz == FELD
    assert ergebnis.platz < FELD


def test_ueberholmanoever_sind_vollstaendig_beschrieben(umgedreht) -> None:
    for manoever in umgedreht.manoever:
        assert 0 <= manoever.angreifer < umgedreht.anzahl
        assert 0 <= manoever.verteidiger < umgedreht.anzahl
        assert manoever.angreifer != manoever.verteidiger
        assert manoever.zeit_ms >= 0
        assert 1 <= manoever.runde <= umgedreht.runden


def test_erfolgschance_bleibt_im_band(k) -> None:
    einstellung = k.wert("ueberholen", "erfolg")
    schwach = ka.gleichverteilt(k, 0)
    stark = ka.gleichverteilt(k, 100_000)
    for angreifer, verteidiger in ((schwach, stark), (stark, schwach), (schwach, schwach)):
        for vorteil in (2.0, 5.0, 50.0):
            chance = rn.erfolgschance(k, angreifer, verteidiger, vorteil, 1.0)
            assert einstellung["wahrscheinlichkeit_min"] <= chance
            assert chance <= einstellung["wahrscheinlichkeit_max"]


def test_besserer_angreifer_hat_mehr_chance(k) -> None:
    schwach = ka.gleichverteilt(k, 0)
    stark = ka.gleichverteilt(k, 100_000)
    assert rn.erfolgschance(k, stark, schwach, 5.0, 1.0) > rn.erfolgschance(
        k, schwach, stark, 5.0, 1.0
    )


def test_mehr_tempovorteil_hilft(k) -> None:
    auto = ka.gleichverteilt(k, 50_000)
    assert rn.erfolgschance(k, auto, auto, 20.0, 1.0) > rn.erfolgschance(
        k, auto, auto, 2.0, 1.0
    )


def test_gleiche_werte_ergeben_faire_chance(k) -> None:
    """Beide Fahrer bei 0 - laut GDD 1 der Ausgangszustand - muss gehen."""
    null = ka.gleichverteilt(k, 0)
    chance = rn.erfolgschance(k, null, null, 2.0, 1.0)
    assert chance == pytest.approx(0.5, abs=0.01)


def test_streckenfaktor_folgt_dem_ueberholzonenanteil(k, strecken, mittel) -> None:
    monza = next(s for s in strecken if s.name == "Monza")
    budapest = next(s for s in strecken if s.name == "Budapest")
    assert rn.streckenfaktor(k, monza, mittel) > rn.streckenfaktor(k, budapest, mittel)


# -- Verlauf abspielen ------------------------------------------------------
def test_distanzen_werden_interpoliert(rennen) -> None:
    davor = rennen.distanzen_zu(10_000)
    dazwischen = rennen.distanzen_zu(10_100)
    danach = rennen.distanzen_zu(10_200)
    assert (dazwischen >= davor).all()
    assert (danach >= dazwischen).all()


def test_reihenfolge_stimmt_mit_der_distanz_ueberein(rennen) -> None:
    zeitpunkt = rennen.dauer_ms // 2
    reihenfolge = rennen.reihenfolge_zu(zeitpunkt)
    distanzen = rennen.distanzen_zu(zeitpunkt)
    assert len(reihenfolge) == FELD
    assert [distanzen[i] for i in reihenfolge] == sorted(distanzen, reverse=True)


def test_distanz_waechst_nur_beim_ueberholen_nicht(rennen) -> None:
    """Kein Auto faellt zurueck - ausser im Moment eines Ueberholmanoevers.

    Beim gelungenen Manoever tauschen die beiden Autos ihre Position
    (siehe ``_versucht_ueberholen``); der Ueberholte rutscht dabei um den
    Abstand zurueck, der zwischen ihnen lag. Das sind wenige Meter auf
    einer Runde von mehreren Kilometern. Jeder andere Rueckschritt waere
    ein Fehler.
    """
    zuwachs = np.diff(rennen.distanz_m, axis=0)
    zeiten = rennen.zeitpunkte_ms
    for bild, auto in np.argwhere(zuwachs < -1e-6):
        von, bis = zeiten[bild], zeiten[bild + 1]
        beteiligt = [
            m
            for m in rennen.manoever
            if von <= m.zeit_ms <= bis and auto in (m.angreifer, m.verteidiger)
        ]
        assert beteiligt, (
            f"Auto {auto} verliert zwischen {von} und {bis} ms "
            f"{-zuwachs[bild, auto]:.2f} m ohne Ueberholmanoever"
        )


def test_abfrage_ausserhalb_des_verlaufs_ist_gueltig(rennen) -> None:
    assert rennen.distanzen_zu(-5_000).shape == (FELD,)
    assert rennen.distanzen_zu(rennen.dauer_ms * 2).shape == (FELD,)


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiches_rennen(k, zandvoort, mittel) -> None:
    feld = rn.starterfeld(k, umgedreht=True)
    erste = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(123), mittel)
    zweite = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(123), mittel)
    assert np.array_equal(erste.distanz_m, zweite.distanz_m)
    assert erste.manoever == zweite.manoever
    assert erste.ergebnisse == zweite.ergebnisse


def test_anderer_seed_anderes_rennen(k, zandvoort, mittel) -> None:
    feld = rn.starterfeld(k, umgedreht=True)
    erste = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(123), mittel)
    zweite = rn.simuliere(k, zandvoort, feld, 2, Seedquelle(456), mittel)
    assert erste.manoever != zweite.manoever


# -- Startfeld --------------------------------------------------------------
def test_starterfeld_hat_die_feldgroesse_der_konfiguration(k) -> None:
    feld = rn.starterfeld(k)
    assert len(feld) == k.wert("rennen", "autos")
    assert sorted(t.startplatz for t in feld) == list(range(1, FELD + 1))


def test_starterfeld_spannt_das_feld_auf(k) -> None:
    """Punkt 101: von Letztem bis Bestem des Feldes."""
    from rennmanager.kern.welt import feldgrenzen

    bester, letzter = feldgrenzen(k)
    feld = rn.starterfeld(k)
    werte = [t.auto.wert("F1") for t in feld]
    assert max(werte) == bester
    assert min(werte) == letzter


def test_starterfeld_kennzeichnet_den_spieler(k) -> None:
    feld = rn.starterfeld(k, spielerplatz=7)
    spieler = [t for t in feld if t.ist_spieler]
    assert len(spieler) == 1
    assert spieler[0].startplatz == 7


def test_simulation_ohne_teilnehmer_meldet_fehler(k, zandvoort, mittel) -> None:
    with pytest.raises(ValueError, match="Teilnehmer"):
        rn.simuliere(k, zandvoort, (), 3, Seedquelle(1), mittel)


def test_simulation_ohne_runden_meldet_fehler(k, zandvoort, mittel) -> None:
    with pytest.raises(ValueError, match="Runde"):
        rn.simuliere(k, zandvoort, rn.starterfeld(k), 0, Seedquelle(1), mittel)


# --- Positionsgewinne je Runde (Punkt 1 der Manoeverzaehlung) --------------
def gleiches_feld(k, werte: list[int]) -> tuple[rn.Teilnehmer, ...]:
    """Ein Feld in der Reihenfolge der uebergebenen Staerken."""
    return tuple(
        rn.Teilnehmer(
            auto=ka.gleichverteilt(k, wert, kuerzel=f"A{i:02d}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i, wert in enumerate(werte)
    )


def test_ohne_positionswechsel_gibt_es_keine_gewinne(k, zandvoort, mittel) -> None:
    """Der Schnellste steht vorn und bleibt vorn - niemand gewinnt etwas."""
    feld = gleiches_feld(k, [60_000, 40_000, 20_000])
    verlauf = rn.simuliere(
        k, zandvoort, feld, 4, Seedquelle(1), mittel, ohne_zufall=True
    )
    assert verlauf.manoever == ()
    assert verlauf.positionsgewinne == (0, 0, 0)


def test_wer_ins_ziel_faehrt_wird_nicht_mehr_ueberholt(k, zandvoort, mittel) -> None:
    """Der Sieger steht im Ziel, waehrend die anderen noch fahren.

    Seine Distanz waechst dann nicht mehr - ohne Sonderbehandlung saehe es
    aus, als ginge das ganze Feld an ihm vorbei.
    """
    feld = gleiches_feld(k, [60_000, 40_000, 20_000])
    verlauf = rn.simuliere(
        k, zandvoort, feld, 4, Seedquelle(1), mittel, ohne_zufall=True
    )
    # Das Feld zieht auseinander: Der Zweite kommt eine knappe Minute
    # spaeter an, der Dritte wird sogar ueberrundet.
    assert verlauf.ergebnisse[1].rueckstand_ms > 30_000
    assert verlauf.ergebnisse[2].rundenrueckstand == 1
    # Trotzdem hat niemand einen Platz gewonnen - es ist keiner an einem
    # stehenden oder ueberrundeten Auto vorbeigefahren.
    assert sum(verlauf.positionsgewinne) == 0


def test_wer_sich_nach_vorn_arbeitet_sammelt_gewinne(k, zandvoort, mittel) -> None:
    """Ein starkes Auto von hinten holt jeden Platz genau einmal."""
    feld = gleiches_feld(k, [10_000, 10_000, 10_000, 90_000])
    verlauf = rn.simuliere(k, zandvoort, feld, 6, Seedquelle(2), mittel)
    ergebnis = next(e for e in verlauf.ergebnisse if e.teilnehmer == 3)
    assert ergebnis.platz == 1
    # Drei Gegner, drei Plaetze - egal wie oft unterwegs gekaempft wurde.
    assert verlauf.positionsgewinne[3] == 3


def test_duelle_innerhalb_einer_runde_zaehlen_nicht_mehrfach(k, zandvoort, mittel) -> None:
    """Der Kern von Schritt A: Positionsgewinne statt roher Vorbeigaenge.

    In einem engen Feld gehen dieselben zwei Autos in einer Runde mehrfach
    aneinander vorbei. Fuer die Erfahrung aus GDD 10 ist das *ein*
    Ueberholmanoever, nicht ein Dutzend.
    """
    feld = gleiches_feld(k, [50_000] * 10)
    verlauf = rn.simuliere(k, zandvoort, feld, 8, Seedquelle(3), mittel)
    assert len(verlauf.manoever) > 0
    assert sum(verlauf.positionsgewinne) < len(verlauf.manoever)


def test_die_gewinne_zaehlen_je_auto(k, zandvoort, mittel) -> None:
    feld = gleiches_feld(k, [50_000] * 6)
    verlauf = rn.simuliere(k, zandvoort, feld, 5, Seedquelle(4), mittel)
    assert len(verlauf.positionsgewinne) == len(feld)
    assert all(wert >= 0 for wert in verlauf.positionsgewinne)
    # Mehr Plaetze als Gegner kann niemand je Runde gewinnen.
    assert max(verlauf.positionsgewinne) <= (len(feld) - 1) * 5


# --- Duellstaerke: der Bereich du aus GDD 8 (Punkt 55) --------------------
def mit_wert(k, schluessel: str, wert: int, grund: int = 50_000) -> ka.Auto:
    werte = {f.schluessel: grund for f in k.faehigkeiten}
    werte[schluessel] = wert
    return ka.Auto("TST", "Test", werte)


def test_die_ganze_duellzeile_wirkt(k, mittel) -> None:
    """GDD 8: Der Bereich du traegt sechs Eigenschaften, nicht zwei.

    F8, D7, D8 und D15 wurden vorher berechnet, aber von nichts gelesen.
    """
    gegner = ka.gleichverteilt(k, 50_000)
    grund = rn.erfolgschance(k, ka.gleichverteilt(k, 50_000), gegner, 5.0, 1.0)
    for schluessel in ("F8", "D7", "D8", "D15"):
        stark = rn.erfolgschance(k, mit_wert(k, schluessel, 100_000), gegner, 5.0, 1.0)
        assert stark > grund, f"{schluessel} wirkt nicht im Duell"


def test_ueberholen_und_verteidigen_wiegen_am_schwersten(k) -> None:
    """GDD 8 gibt D10 und D11 je 3 von 10 - mehr als allen anderen."""
    gegner = ka.gleichverteilt(k, 50_000)
    grund = rn.erfolgschance(k, ka.gleichverteilt(k, 50_000), gegner, 5.0, 1.0)
    ueberholen = rn.erfolgschance(k, mit_wert(k, "D10", 100_000), gegner, 5.0, 1.0)
    bremsen = rn.erfolgschance(k, mit_wert(k, "D8", 100_000), gegner, 5.0, 1.0)
    assert ueberholen > bremsen > grund


def test_ein_starker_verteidiger_senkt_die_chance(k) -> None:
    angreifer = ka.gleichverteilt(k, 50_000)
    schwach = rn.erfolgschance(k, angreifer, mit_wert(k, "D11", 0), 5.0, 1.0)
    stark = rn.erfolgschance(k, angreifer, mit_wert(k, "D11", 100_000), 5.0, 1.0)
    assert stark < schwach


# --- Zieleinlauf (Punkt 67) -------------------------------------------
def test_die_anzeige_zeigt_im_ziel_dieselbe_reihenfolge_wie_die_wertung(k, strecken):
    """Wer gewinnt, steht nach dem Zieleinlauf auch oben in der Liste.

    Die Anzeige sortierte bisher allein nach zurueckgelegter Strecke. Das
    geht, solange gefahren wird - danach nicht mehr: Wer im Ziel ist,
    steht, alle anderen fahren weiter bis zur Linie. Am Ende hatte
    ausgerechnet der Letzte die groesste Strecke und stand vorn.
    """
    strecke = strecken[0]
    mittel = rn.mittlerer_ueberholzonenanteil(k, strecken)
    feld = tuple(
        rn.Teilnehmer(
            auto=ka.gleichverteilt(k, 50_000 + i * 200, kuerzel=f"A{i:02d}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i in range(12)
    )
    for seed in (1, 2, 3):
        verlauf = rn.simuliere(
            k, strecke, feld, runden=5, seedquelle=Seedquelle(seed),
            streckenmittel=mittel,
        )
        ende = float(verlauf.zeitpunkte_ms[-1])
        assert verlauf.reihenfolge_zu(ende) == [
            e.teilnehmer for e in verlauf.ergebnisse
        ]


def test_waehrend_des_rennens_entscheidet_weiter_die_strecke(k, strecken):
    """Solange niemand im Ziel ist, fuehrt wie bisher der Weiteste."""
    strecke = strecken[0]
    mittel = rn.mittlerer_ueberholzonenanteil(k, strecken)
    feld = tuple(
        rn.Teilnehmer(
            auto=ka.gleichverteilt(k, 50_000 + i * 200, kuerzel=f"A{i:02d}"),
            startplatz=i + 1,
            farbe="#888888",
        )
        for i in range(12)
    )
    verlauf = rn.simuliere(
        k, strecke, feld, runden=5, seedquelle=Seedquelle(1), streckenmittel=mittel,
    )
    mitte = float(verlauf.zeitpunkte_ms[len(verlauf.zeitpunkte_ms) // 2])
    distanzen = verlauf.distanzen_zu(mitte)
    assert verlauf.reihenfolge_zu(mitte) == sorted(
        range(verlauf.anzahl), key=lambda i: -distanzen[i]
    )


# -- Persoenlich beste Sektoren und die ideale Runde (Punkt 82) -------------
def _protokoll(runden: list[tuple[int, ...]]) -> rn.Rundenprotokoll:
    """Ein Protokoll aus reinen Zahlen - ohne ein Rennen zu fahren."""
    ende, summe = [], 0
    for sektoren in runden:
        summe += sum(sektoren)
        ende.append(summe)
    return rn.Rundenprotokoll(
        rundenzeiten_ms=[sum(s) for s in runden],
        sektorzeiten_ms=list(runden),
        rundenende_ms=ende,
    )


def test_die_besten_sektoren_kommen_aus_verschiedenen_runden() -> None:
    """Genau darum geht es: der beste S1 aus Runde 1, der beste S2 aus Runde 2."""
    protokoll = _protokoll([(30_000, 40_000), (35_000, 36_000)])
    assert protokoll.beste_sektoren_bis(1e9) == (30_000, 36_000)


def test_die_ideale_runde_ist_nie_langsamer_als_die_beste_gefahrene() -> None:
    protokoll = _protokoll([(30_000, 40_000), (35_000, 36_000)])
    assert protokoll.ideale_runde_ms(1e9) == 66_000
    assert protokoll.ideale_runde_ms(1e9) <= protokoll.beste_runde_ms


def test_die_ideale_runde_zaehlt_nur_gefahrene_runden() -> None:
    """Zum Abspielzeitpunkt zaehlt, was bis dahin gefahren war."""
    protokoll = _protokoll([(30_000, 40_000), (35_000, 36_000)])
    # Nach der ersten Runde (70 s) ist die zweite noch nicht gefahren.
    assert protokoll.beste_sektoren_bis(70_000) == (30_000, 40_000)
    assert protokoll.ideale_runde_ms(70_000) == 70_000


def test_ohne_runde_gibt_es_keine_ideale_zeit() -> None:
    protokoll = _protokoll([(30_000, 40_000)])
    assert protokoll.beste_sektoren_bis(0) == ()
    assert protokoll.ideale_runde_ms(0) is None


def test_eine_unvollstaendige_runde_ergibt_keine_rundenzeit() -> None:
    """Eine Summe aus halben Runden waere keine Rundenzeit."""
    protokoll = rn.Rundenprotokoll(
        rundenzeiten_ms=[70_000],
        sektorzeiten_ms=[(30_000,)],   # S2 fehlt, das Auto fiel aus
        rundenende_ms=[70_000],
    )
    protokoll.sektorzeiten_ms.append((31_000, 39_000))
    protokoll.rundenzeiten_ms.append(70_000)
    protokoll.rundenende_ms.append(140_000)
    # S2 gibt es nur aus der zweiten Runde - aber es gibt ihn, also zaehlt er.
    assert protokoll.beste_sektoren_bis(1e9) == (30_000, 39_000)
    assert protokoll.ideale_runde_ms(1e9) == 69_000


def test_die_besten_sektoren_kommen_aus_einem_echten_rennen(rennen) -> None:
    """Gegenprobe am gefahrenen Rennen, nicht nur an erfundenen Zahlen."""
    fuer_jeden = [
        rennen.protokolle[i].beste_sektoren_bis(rennen.dauer_ms)
        for i in range(len(rennen.teilnehmer))
    ]
    mit_sektoren = [s for s in fuer_jeden if s]
    assert mit_sektoren, "Ein gefahrenes Rennen muss Sektorzeiten haben"
    for i, sektoren in enumerate(fuer_jeden):
        ideal = rennen.protokolle[i].ideale_runde_ms(rennen.dauer_ms)
        beste = rennen.protokolle[i].beste_runde_ms
        if ideal is None or beste is None:
            continue
        assert ideal <= beste, f"Auto {i}: {ideal} > {beste}"
        assert all(s is not None for s in sektoren)


def test_die_ideale_runde_ueberholt_die_gefahrene_nicht(rennen) -> None:
    """Rundung darf keine "bestmoegliche" Runde ergeben, die langsamer ist.

    Sektoren und Rundenzeiten werden unabhaengig auf ganze Millisekunden
    gerundet; gemessen kam die Summe der Sektoren eine Millisekunde ueber
    der Rundenzeit heraus, aus der sie stammte (5:37.491 gegen 5:37.490).
    """
    kuenstlich = rn.Rundenprotokoll(
        # Die Summe der Sektoren liegt eine Millisekunde ueber der Runde.
        rundenzeiten_ms=[70_000],
        sektorzeiten_ms=[(30_000, 40_001)],
        rundenende_ms=[70_000],
    )
    assert kuenstlich.ideale_runde_ms(1e9) == 70_000

    for i in range(len(rennen.teilnehmer)):
        ideal = rennen.protokolle[i].ideale_runde_ms(rennen.dauer_ms)
        beste = rennen.protokolle[i].beste_runde_ms
        if ideal is not None and beste is not None:
            assert ideal <= beste


# -- Genauigkeit der Bildfelder (E12) ---------------------------------------
def test_die_distanzen_bleiben_doppelt_genau(rennen) -> None:
    """E12: An ``distanz_m`` haengt die Reihenfolge des ganzen Feldes.

    Gemessen ueber vierzig Runden reicht die Distanz bis 170 km; dort
    loest ``float32`` nur noch auf 15,6 mm auf, waehrend sich zwei Autos
    im selben Rennen auf 5,24 mm naeherten. Zwei Autos bekaemen dann
    denselben Wert, und wer vorn liegt, entschiede die Sortierung statt
    die Strecke - ein Fehler, den man erst im fertigen Spiel sieht und
    dann nicht mehr erklaeren kann.
    """
    assert rennen.distanz_m.dtype == np.float64


def test_der_reifenzustand_reicht_einfach_genau(rennen) -> None:
    """E12: Reine Anzeigegroesse - Balken und Prozentzahl.

    Die Simulation rechnet auf ``verschleiss``; dieses Feld wird nie
    fuer eine Entscheidung gelesen. Halbe Genauigkeit loest hier noch
    auf ein Zehnmillionstel auf und halbiert den Speicher.
    """
    assert rennen.reifenzustand.dtype == np.float32
    assert float(rennen.reifenzustand.max()) <= 1.0
    assert float(rennen.reifenzustand.min()) >= 0.0


def test_der_fortschritt_aendert_das_rennen_nicht(k, zandvoort, mittel) -> None:
    """E10: Der Rueckruf liest nur mit, er greift nicht ein."""
    feld = rn.starterfeld(k, spielerplatz=FELD)
    gemeldet: list[tuple[int, int]] = []
    ohne = rn.simuliere(k, zandvoort, feld, 3, Seedquelle(4711), mittel)
    mit = rn.simuliere(
        k, zandvoort, feld, 3, Seedquelle(4711), mittel,
        fortschritt=lambda runde, gesamt: gemeldet.append((runde, gesamt)),
    )
    assert np.array_equal(ohne.distanz_m, mit.distanz_m)
    assert ohne.ergebnisse == mit.ergebnisse
    assert gemeldet == [(1, 3), (2, 3), (3, 3)]


# -- Punkt 102: Fuehrungsrunden --------------------------------------------
def test_jede_gefahrene_runde_hat_genau_einen_fuehrenden(rennen) -> None:
    """Die Summe ueber das Feld ist die Rundenzahl - nicht mehr, nicht weniger."""
    assert sum(rennen.fuehrungsrunden()) == rennen.runden


def test_der_sieger_fuehrt_die_letzte_runde(rennen) -> None:
    """Wer als Erster ueber die Ziellinie faehrt, hat die Schlussrunde gefuehrt."""
    wer, _ende = rennen._fuehrender_je_runde[-1]
    assert wer == rennen.ergebnisse[0].teilnehmer


def test_fuehrungsrunden_wachsen_mit_dem_abspielzeitpunkt(rennen) -> None:
    """Das Blatt im Rennen zaehlt mit, statt den Endstand vorwegzunehmen."""
    stand = [sum(rennen.fuehrungsrunden(rennen.dauer_ms * a)) for a in (0.0, 0.5, 1.0)]
    assert stand[0] == 0, "Vor dem Start hat niemand eine Runde gefuehrt"
    assert 0 < stand[1] < stand[2]
    assert stand[2] == rennen.runden


def test_die_startaufstellung_zaehlt_noch_nicht(rennen) -> None:
    """Gefuehrt wird eine Runde erst, wenn sie gefahren ist."""
    assert rennen.fuehrungsrunden(0.0) == (0,) * len(rennen.teilnehmer)
    assert rennen.fuehrungswechsel(0.0) == 0


def test_gezaehlt_wird_an_der_linie_und_nicht_die_aufstellung(umgedreht) -> None:
    """Umgedrehtes Feld: Wer auf der Pole steht, fuehrt noch lange nicht.

    Die Aufstellung steht auf dem Kopf, das schwaechste Auto also vorn.
    Gemessen holt die Pace den Startplatz schon in der ersten Runde ein:
    Auto 15 startet 170 m hinter der Pole und ist trotzdem 4,5 s frueher
    an der Linie. Genau das ist der Unterschied zwischen "Startplatz 1"
    und "Runde gefuehrt" - und der Grund, warum hier die Rundenenden
    gelesen werden und nicht die Aufstellung.
    """
    pole = next(i for i, t in enumerate(umgedreht.teilnehmer) if t.startplatz == 1)
    erster, _ = umgedreht._fuehrender_je_runde[0]
    assert erster != pole
    assert sum(umgedreht.fuehrungsrunden()) == umgedreht.runden


def test_die_wechsel_zaehlen_die_uebergaenge(rennen) -> None:
    """Ein Wechsel ist, wenn zwei aufeinanderfolgende Runden verschieden
    gefuehrt werden - nicht, wie viele ueberhaupt einmal vorn lagen."""
    fuehrende = [wer for wer, _ in rennen._fuehrender_je_runde]
    erwartet = sum(
        1 for a, b in zip(fuehrende, fuehrende[1:], strict=False) if a != b
    )
    assert rennen.fuehrungswechsel() == erwartet
    # Und wer nie vorn lag, taucht in der Zaehlung nicht auf.
    gezaehlt = rennen.fuehrungsrunden()
    assert {i for i, n in enumerate(gezaehlt) if n} == set(fuehrende)
