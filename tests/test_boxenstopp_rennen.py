"""Boxenstopps im Rennmodell und im Schnellmodus (Punkt 39).

Der Zeitraffer faehrt die Boxengasse wirklich langsam ab und steht die
Standzeit; der Schnellmodus bucht dieselbe Differenz. Beide muessen
dieselbe Strategie fahren und im selben Zeitrahmen ankommen.
"""

import pytest

from rennmanager.kern import boxenstopp as bx
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as rn
from rennmanager.kern import schnellsimulation as schnell
from rennmanager.kern import strategie as sg
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

LIGA = 1
# Ein kurzes Rennen: die Stopps interessieren, nicht die Renndistanz.
RUNDEN = 24
# Ein Seed, dessen Rennwetter auf dieser Strecke durchgehend trocken ist.
# Beide Modelle wuerfeln es aus demselben Zweig, koennen es aber nicht
# entgegennehmen - also wird es hier ausgesucht statt gesetzt.
TROCKEN = 0
# Streckenverschleiss der Tests: hoch genug, dass ein Satz bis zur
# geplanten Stopprunde unter die Verschiebeschwelle faellt.
VERSCHLEISS = 3.0


@pytest.fixture(scope="module")
def k():
    return lade()


@pytest.fixture(scope="module")
def ohne_verschiebung(k):
    """Dieselbe Konfiguration, nur ohne die Verschiebung des Planstopps.

    Punkt 39 verschiebt einen geplanten Stopp, solange das Restprofil
    ueber der Schwelle liegt. Wer den **Preis** eines Stopps messen will,
    braucht einen Satz ohne Verschleiss - und der wuerde ewig
    verschoben. Die Schwelle auf 1,0 heisst: nie verschieben, denn mehr
    als volles Profil gibt es nicht.
    """
    from copy import deepcopy
    from dataclasses import replace as ersetze

    roh = deepcopy(k.roh)
    roh["boxenstopp"]["strategie"]["planstopp_ab_restprofil"] = 1.0
    return ersetze(k, roh=roh)


@pytest.fixture(scope="module")
def strecken(k):
    return kern_strecke.lade_alle(k)


@pytest.fixture(scope="module")
def monza(strecken):
    return next(s for s in strecken if s.name == "Monza")


@pytest.fixture(scope="module")
def umgebung(k, strecken, monza):
    """Ueberholzonenanteil und ein Streckenverschleiss, der Stopps erzwingt.

    Monza nimmt die Reifen von sich aus kaum her (Faktor 0,54); ein Satz
    traegt dort ueber die ganze Testdistanz. Seit ein geplanter Stopp
    verschoben wird, solange das Restprofil ueber der Schwelle liegt,
    kaeme in diesen Tests gar kein Stopp mehr zustande. Der erhoehte
    Faktor macht die Stopps faellig - geprueft wird hier der
    Stoppmechanismus, nicht die Streckenwirkung.
    """
    return (rn.mittlerer_ueberholzonenanteil(k, strecken), VERSCHLEISS)


@pytest.fixture(scope="module")
def feld(k):
    return rn.starterfeld(k, LIGA, seedquelle=Seedquelle(1))


def strategie_mit(k, stopps):
    """Zwei verschiedene Mischungen, feste Stopprunden."""
    weich = kern_reifen.mischung(k, "weich")
    hart = kern_reifen.mischung(k, "hart")
    folge = tuple((weich if n % 2 == 0 else hart) for n in range(len(stopps) + 1))
    return sg.Strategie(mischungen=folge, stopps=tuple(stopps))


# -- Der Stopp im Rennen ----------------------------------------------------
def test_ohne_strategie_wird_nicht_gestoppt(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
    )
    assert verlauf.boxenstopps == ()


def test_der_geplante_stopp_wird_gefahren(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=tuple(strategie_mit(k, (8, 16)) for _ in range(3)),
    )
    for i in range(3):
        stopps = verlauf.stopps_von(i)
        assert [b.runde for b in stopps] == [8, 16]
        assert [b.von for b in stopps] == ["W", "H"]
        assert [b.nach for b in stopps] == ["H", "W"]
        assert all(not b.notstopp for b in stopps)


def test_der_stopp_setzt_die_reifen_zurueck(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(strategie_mit(k, (12,)),),
    )
    stopp = verlauf.stopps_von(0)[0]
    davor = verlauf.reifen_zu(stopp.zeit_ms - 1_000)[0]
    danach = verlauf.reifen_zu(stopp.zeit_ms + 20_000)[0]
    assert davor < 1.0
    assert danach > davor


def test_die_mischung_steht_im_verlauf(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(strategie_mit(k, (12,)),),
        mischungspflicht=True,
    )
    stopp = verlauf.stopps_von(0)[0]
    assert verlauf.mischung_zu(0)[0] == "W"
    assert verlauf.mischung_zu(stopp.zeit_ms + 20_000)[0] == "H"
    assert verlauf.gefahrene_mischungen(0, verlauf.dauer_ms) == ("W", "H")
    assert verlauf.mischungspflicht


def test_ein_stopp_kostet_durchfahrt_halt_und_standzeit(
    ohne_verschiebung, monza, feld, umgebung
):
    """Der Preis eines Stopps muss der sein, den boxenstopp.py ausrechnet.

    Gemessen an einem Satz, der praktisch nicht abbaut - sonst
    ueberlagert der frische Reifen nach dem Stopp alles andere.

    Die Toleranz von zwei Sekunden ist die Koernung der Simulation: Sie
    rechnet in Schritten von 50 Millisekunden, beschleunigt aus der Box
    mit der eigenen Grenze statt mit der des Profils, und das Bremsen bis
    zum Stillstand wird als Standzeit gebucht, waehrend das Profil die
    Bremszone schon eingerechnet hat. Auf einen Stopp von rund vierzig
    Sekunden sind das vier Prozent.
    """
    from dataclasses import replace

    mittel, verschleiss = umgebung
    glatt = replace(kern_reifen.mischung(ohne_verschiebung, "hart"), verschleiss=1e-6)
    ohne = rn.simuliere(
        ohne_verschiebung, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(sg.Strategie(mischungen=(glatt,), stopps=()),),
    )
    mit = rn.simuliere(
        ohne_verschiebung, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(sg.Strategie(mischungen=(glatt, glatt), stopps=(12,)),),
    )
    grenzen = kern_tempo.grenzen_aus(ohne_verschiebung, feld[0].auto)
    erwartet = (
        bx.durchfahrtsverlust_ms(ohne_verschiebung, monza, grenzen)
        + bx.haltverlust_ms(ohne_verschiebung, grenzen)
        + mit.boxenstopps[0].standzeit_ms
    )
    gemessen = mit.ergebnisse[0].zeit_ms - ohne.ergebnisse[0].zeit_ms
    assert gemessen == pytest.approx(erwartet, abs=2_000)


def test_in_der_boxengasse_wird_langsam_gefahren(
    ohne_verschiebung, monza, feld, umgebung
):
    """Die Runde des Stopps ist laenger als die davor - auch ohne Standzeit."""
    from dataclasses import replace

    mittel, verschleiss = umgebung
    glatt = replace(kern_reifen.mischung(ohne_verschiebung, "hart"), verschleiss=1e-6)
    mit = rn.simuliere(
        ohne_verschiebung, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(sg.Strategie(mischungen=(glatt, glatt), stopps=(12,)),),
    )
    runden = mit.protokolle[0].rundenzeiten_ms
    # Runde 12 traegt die Einfahrt, Runde 13 Standzeit und Ausfahrt.
    assert runden[11] > runden[9]
    assert runden[12] > runden[9]
    assert runden[13] == pytest.approx(runden[9], rel=0.02)


def test_am_rennende_wird_nicht_mehr_gestoppt(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(strategie_mit(k, (RUNDEN - 1,)),),
    )
    for b in verlauf.boxenstopps:
        assert b.runde < RUNDEN


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiche_stopps(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    strategien = tuple(strategie_mit(k, (8, 16)) for _ in range(5))

    def lauf():
        return rn.simuliere(
            k, monza, feld[:5], RUNDEN, Seedquelle(2), mittel,
            streckenverschleiss=verschleiss, strategien=strategien,
        )

    assert lauf().boxenstopps == lauf().boxenstopps


def test_die_streuung_macht_zwei_gleiche_plaene_verschieden(k, monza, feld, umgebung):
    """Punkt 39: je Fahrer und Mischung ein kleiner Verschleisswurf.

    Frueh gestoppt, damit beim Wechsel ueberhaupt noch Profil da ist -
    bei diesem Streckenverschleiss ist ein Satz nach zehn Runden hin, und
    auf null sieht man keine Streuung mehr.
    """
    mittel, verschleiss = umgebung
    strategien = tuple(strategie_mit(k, (5,)) for _ in range(6))
    verlauf = rn.simuliere(
        k, monza, feld[:6], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss, strategien=strategien,
    )
    reste = {round(b.restprofil, 6) for b in verlauf.boxenstopps}
    assert len(reste) > 1


def test_die_streuung_bleibt_in_ihren_spannen(k):
    """Zwei getrennte Wuerfe: Verschleiss und Tempo, jeder in seiner Spanne."""
    fuer_verschleiss = k.wert("reifen", "verschleiss", "streuung_verschleiss")
    fuer_tempo = k.wert("reifen", "verschleiss", "streuung_tempo")
    misch = kern_reifen.mischung(k, "mittel")
    gestreut = [kern_reifen.mit_streuung(k, misch, Seedquelle(n)) for n in range(100)]
    assert all(
        abs(m.verschleiss - misch.verschleiss) <= fuer_verschleiss + 1e-12
        for m in gestreut
    )
    assert all(abs(m.tempo - misch.tempo) <= fuer_tempo + 1e-12 for m in gestreut)
    assert len({m.verschleiss for m in gestreut}) > 50
    assert len({m.tempo for m in gestreut}) > 50


def test_verschleiss_und_tempo_streuen_unabhaengig(k):
    """Sonst waere ein Satz mal rundum besser, mal rundum schlechter."""
    misch = kern_reifen.mischung(k, "mittel")
    gestreut = [kern_reifen.mit_streuung(k, misch, Seedquelle(n)) for n in range(200)]
    besser_haltbar = [m.verschleiss < misch.verschleiss for m in gestreut]
    schneller = [m.tempo > misch.tempo for m in gestreut]
    beides = sum(1 for a, b in zip(besser_haltbar, schneller, strict=True) if a and b)
    # Bei Unabhaengigkeit rund ein Viertel; ein Zusammenhang faellt auf.
    assert 0.15 <= beides / len(gestreut) <= 0.35


# -- Zeitraffer und Schnellmodus -------------------------------------------
def rennwetter(k, monza, feld, seed):
    """Das Wetter, das der Schnellmodus sich selbst wuerfelt.

    Er zieht es aus ``zweig("rennwetter")``; dieselbe Rechnung hier ergibt
    denselben Verlauf. Ohne das vergleicht ein Test nur zwei verschiedene
    Rennsonntage.
    """
    from rennmanager.kern import wetter as kern_wetter

    grund = sum(
        kern_tempo.fahre_runde(k, monza, t.auto).zeit_ms for t in feld
    ) / len(feld)
    return kern_wetter.wuerfle(
        k, monza.name, int(grund * RUNDEN), int(grund), Seedquelle(seed).zweig("rennwetter")
    )


def test_beide_modi_fahren_dieselbe_strategie(k, monza, feld, umgebung):
    """Dieselbe Strategie, dieselben Stopprunden und Mischungen."""
    mittel, verschleiss = umgebung
    strategien = tuple(strategie_mit(k, (8, 16)) for _ in feld)
    voll = rn.simuliere(
        k, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel,
        wetter=rennwetter(k, monza, feld, TROCKEN),
        streckenverschleiss=verschleiss, strategien=strategien,
    )
    flott = schnell.fahre_wochenende(
        k, LIGA, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel, verschleiss,
        strategien=strategien,
    )
    for i in range(len(feld)):
        gefahren = [(b.runde, b.von, b.nach) for b in voll.stopps_von(i)]
        assert gefahren == [(8, "W", "H"), (16, "H", "W")]
    assert flott.siegerzeit_ms > 0


def test_beide_modi_kosten_die_stopps_gleich_viel(k, monza, feld, umgebung):
    """Der Schnellmodus darf durch Stopps nicht anders verlieren als der Zeitraffer.

    Verglichen wird der **Unterschied**, den die Stopps machen: einmal
    ein Rennen ohne, einmal mit. Die Modelle selbst liegen ohnehin nur
    auf zwei Prozent beieinander (siehe test_schnellsimulation), deshalb
    zaehlt hier nur der Zuwachs.

    Gefahren wird ein **trockenes** Rennen. Sobald das Wetter wechselt,
    entscheidet jedes Auto selbst ueber Notstopps, und die beiden Modelle
    fragen das Wetter an verschiedenen Stellen: die volle Simulation zur
    Ueberfahrt jedes einzelnen Autos, der Schnellmodus einmal je Runde
    beim Fuehrenden. Dann faellt die Zahl der Notstopps auseinander - das
    ist der Preis des Schnellmodus und keine Abweichung, die sich
    wegrechnen liesse.
    """
    mittel, verschleiss = umgebung
    hart = kern_reifen.mischung(k, "hart")
    ohne = sg.Strategie(mischungen=(hart,), stopps=())
    mit = strategie_mit(k, (8, 16))

    wetter = rennwetter(k, monza, feld, TROCKEN)
    assert len(wetter.zustaende) == 1, "Der Test braucht ein Rennen ohne Wetterwechsel"

    def zeiten(strategie):
        voll = rn.simuliere(
            k, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel, wetter=wetter,
            streckenverschleiss=verschleiss,
            strategien=tuple(strategie for _ in feld),
        )
        flott = schnell.fahre_wochenende(
            k, LIGA, monza, feld, RUNDEN, Seedquelle(TROCKEN), mittel, verschleiss,
            strategien=tuple(strategie for _ in feld),
        )
        return voll.ergebnisse[0].zeit_ms, flott.siegerzeit_ms

    voll_ohne, flott_ohne = zeiten(ohne)
    voll_mit, flott_mit = zeiten(mit)
    zuwachs_voll = voll_mit - voll_ohne
    zuwachs_flott = flott_mit - flott_ohne
    # Zwei Stopps kosten rund eine Minute; fuenf Sekunden Unterschied
    # zwischen den Modellen sind die Koernung beider Rechnungen.
    assert zuwachs_voll == pytest.approx(zuwachs_flott, abs=10_000)


# -- Wetterwechsel ----------------------------------------------------------
def test_der_falsche_reifen_zwingt_zum_notstopp(k, monza, feld, strecken, umgebung):
    """Hoechstens drei Runden auf dem falschen Reifen - so der Auftraggeber."""
    from rennmanager.kern import wetter as kern_wetter

    mittel, verschleiss = umgebung
    wetter = kern_wetter.Wetterverlauf(
        abschnitte=(
            kern_wetter.Abschnitt(
                zustand="starkregen",
                ab_ms=0,
                grip_je_sektor=(0.7,) * len(monza.sektoren),
            ),
        ),
        uebergang_ms=0,
    )
    trocken = kern_reifen.mischung(k, "hart")
    verlauf = rn.simuliere(
        k, monza, feld[:4], RUNDEN, Seedquelle(2), mittel, wetter=wetter,
        streckenverschleiss=verschleiss,
        strategien=tuple(
            sg.Strategie(mischungen=(trocken, trocken), stopps=(18,)) for _ in range(4)
        ),
    )
    notstopps = [b for b in verlauf.boxenstopps if b.notstopp]
    assert notstopps, "Im Starkregen muss auf Regenreifen gewechselt werden"
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    for b in notstopps:
        assert b.nach == "R"
        assert b.runde <= abstand + 2
