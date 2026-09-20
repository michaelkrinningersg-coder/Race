"""Der Boxenstopp im Rennmodell (Punkt 39).

Ob ueberhaupt gestoppt wird, wann, und was der Stopp mit den Reifen
und der Mischung macht.
"""

import pytest

from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as rn
from rennmanager.kern import strategie as sg
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import (
    RUNDEN,
    VERSCHLEISS,
    VERSCHLEISS_MILD,
    VERSCHLEISS_PLANSTOPP,
    strategie_mit,
)


# -- Der Stopp im Rennen ----------------------------------------------------
def test_ohne_strategie_wird_nicht_gestoppt(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
    )
    assert verlauf.boxenstopps == ()


def test_der_geplante_stopp_wird_gefahren(ohne_verschiebung, monza, feld, umgebung):
    """Der geplante Stopp faellt in die geplante Runde.

    Zwei Dinge muessen dafuer aus dem Weg. Der **Streckenverschleiss**:
    Mit dem sonst ueblichen Faktor kaeme das Auto schon in Runde 6 wegen
    abgefahrener Reifen herein - das prueft der Zwangsstopp-Test weiter
    unten. Und die **Verschiebeschwelle**: Sie haengt an einem
    Balancing-Wert, und der darf nicht bestimmen, ob dieser Test durch
    ist. Wann verschoben wird, prueft der naechste Test.
    """
    mittel, _verschleiss = umgebung
    k = ohne_verschiebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=VERSCHLEISS_PLANSTOPP,
        strategien=tuple(strategie_mit(k, (8, 16)) for _ in range(3)),
    )
    for i in range(3):
        stopps = verlauf.stopps_von(i)
        assert [b.runde for b in stopps] == [8, 16]
        assert [b.von for b in stopps] == ["W", "H"]
        assert [b.nach for b in stopps] == ["H", "W"]
        assert all(not b.notstopp for b in stopps)


@pytest.fixture(scope="module")
def einzelstopp(k, monza, feld, umgebung):
    """Ein Auto, ein geplanter Stopp in Runde 12 - einmal gefahren.

    Punkt 77: Reifen und Mischung wurden vorher in zwei getrennten
    Laeufen geprueft, die sich nur in der Mischungspflicht unterschieden.
    Die aendert am Fahren nichts, also genuegt ein Lauf fuer beides - das
    spart gemessen acht Sekunden.
    """
    mittel, verschleiss = umgebung
    return rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(strategie_mit(k, (12,)),),
        mischungspflicht=True,
    )


def test_der_stopp_setzt_die_reifen_zurueck(einzelstopp):
    stopp = einzelstopp.stopps_von(0)[0]
    davor = einzelstopp.reifen_zu(stopp.zeit_ms - 1_000)[0]
    danach = einzelstopp.reifen_zu(stopp.zeit_ms + 20_000)[0]
    assert davor < 1.0
    assert danach > davor


def test_die_mischung_steht_im_verlauf(einzelstopp):
    stopp = einzelstopp.stopps_von(0)[0]
    assert einzelstopp.mischung_zu(0)[0] == "W"
    assert einzelstopp.mischung_zu(stopp.zeit_ms + 20_000)[0] == "H"
    assert einzelstopp.gefahrene_mischungen(0, einzelstopp.dauer_ms) == ("W", "H")
    assert einzelstopp.mischungspflicht


def test_ein_zu_guter_satz_verschiebt_den_stopp(k, monza, feld, umgebung):
    """Ein Satz ueber der Schwelle wird nicht abgegeben, sondern weitergefahren.

    Geplant ist Runde 8. Bei diesem milden Verschleiss traegt der Satz
    dort noch weit mehr Profil, als die Schwelle zulaesst - also faehrt
    das Auto Runde um Runde weiter, bis es darunter faellt.

    Geprueft wird gegen den Wert **aus der Konfiguration**, nicht gegen
    eine ausgerechnete Runde: ``planstopp_ab_restprofil`` ist ein
    Balancing-Wert, und wenn der Auftraggeber ihn dreht, soll sich die
    Stopprunde verschieben duerfen - die Regel dahinter nicht.
    """
    mittel, _verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:3], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=VERSCHLEISS_MILD,
        strategien=tuple(strategie_mit(k, (8, 16)) for _ in range(3)),
    )
    schwelle = k.wert("boxenstopp", "strategie", "planstopp_ab_restprofil")
    for i in range(3):
        stopps = verlauf.stopps_von(i)
        assert stopps, "Zwei Mischungen sind Pflicht - ganz ausfallen darf der Stopp nicht"
        assert stopps[0].runde > 8, "Ein Satz ueber der Schwelle gehoert nicht in die Box"
        assert stopps[0].restprofil <= schwelle


# -- Zwangsstopp bei abgefahrenem Reifen ------------------------------------
def test_der_abgefahrene_reifen_zwingt_zum_stopp(k, monza, feld, umgebung):
    """Entscheidung des Auftraggebers: unter 30 % Restprofil herein.

    Vorher zwang nur das Wetter. Ein Auto, dessen Satz vor der geplanten
    Stopprunde durch war, schlich den Rest des Rennens auf blankem Gummi
    - gemessen ueber fuenf Strecken drei bis vier Autos je Rennen.
    """
    mittel, verschleiss = umgebung
    ohne_plan = sg.Strategie(mischungen=(kern_reifen.mischung(k, "weich"),), stopps=())
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(ohne_plan,),
    )
    stopps = verlauf.stopps_von(0)
    assert stopps, "Ein durchgefahrener Satz muss das Auto hereinzwingen"
    schwelle = k.wert("boxenstopp", "strategie", "notstopp_ab_restprofil")
    assert all(b.notstopp for b in stopps)
    assert stopps[0].restprofil < schwelle


def test_in_den_letzten_runden_wird_nicht_mehr_gestoppt(k, monza, feld, umgebung):
    """Dieselbe Sperre wie fuer jeden anderen Stopp: die letzten Runden."""
    mittel, verschleiss = umgebung
    ohne_plan = sg.Strategie(mischungen=(kern_reifen.mischung(k, "weich"),), stopps=())
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(ohne_plan,),
    )
    sperre = k.wert("boxenstopp", "strategie", "sperre_runden")
    assert all(b.runde <= RUNDEN - sperre for b in verlauf.boxenstopps)


def test_zwischen_zwei_zwangsstopps_liegt_der_mindestabstand(k, monza, feld, umgebung):
    """Sonst kaeme ein Auto mit sehr hohem Verschleiss Runde um Runde herein."""
    mittel, verschleiss = umgebung
    ohne_plan = sg.Strategie(mischungen=(kern_reifen.mischung(k, "weich"),), stopps=())
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(ohne_plan,),
    )
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    runden = [b.runde for b in verlauf.stopps_von(0)]
    assert all(b - a >= abstand for a, b in zip(runden, runden[1:], strict=False))


# -- Nach dem Zwangsstopp ---------------------------------------------------
def test_nach_einem_zwangsstopp_wird_es_nicht_wieder_weicher(k, monza, feld, umgebung):
    """Entscheidung des Auftraggebers: kein Rueckschritt auf weicheren Gummi.

    Das Auto startet auf Weich und faehrt den Satz ab; der Zwangsstopp
    legt Hart auf. Der Plan will danach wieder Weich - das gibt es nicht
    mehr, denn zwei Mischungen sind zu dem Zeitpunkt schon gefahren.
    """
    mittel, verschleiss = umgebung
    weich = kern_reifen.mischung(k, "weich")
    nur_weich = sg.Strategie(mischungen=(weich, weich, weich), stopps=(12, 18))
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(nur_weich,),
    )
    stopps = verlauf.stopps_von(0)
    zwang = [b for b in stopps if b.notstopp]
    assert zwang, "Bei diesem Verschleiss muss der Satz das Auto hereinzwingen"
    assert zwang[0].nach == "H", "Der Zwangsstopp nimmt im Trockenen die haerteste"
    # Alles, was danach kommt, bleibt auf Hart - obwohl der Plan Weich sagt.
    danach = [b for b in stopps if b.runde > zwang[0].runde]
    assert danach, "Der Plan sieht nach dem Zwangsstopp noch einen Stopp vor"
    assert all(b.nach == "H" for b in danach), [b.nach for b in danach]


def test_die_mischungspflicht_geht_der_haerteregel_vor(k, monza, feld, umgebung):
    """Sonst liesse sich die Pflicht nach einem Zwangsstopp nicht erfuellen.

    Wer auf Hart startet und dessen Zwangsstopp wieder Hart auflegt, hat
    erst **eine** Mischung gefahren. Die zweite kann dann nur weicher
    sein - hier muss die Haerteregel weichen.
    """
    mittel, verschleiss = umgebung
    hart = kern_reifen.mischung(k, "hart")
    mittelhart = kern_reifen.mischung(k, "mittel")
    plan = sg.Strategie(mischungen=(hart, mittelhart, mittelhart), stopps=(12, 18))
    verlauf = rn.simuliere(
        k, monza, feld[:1], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=(plan,),
        mischungspflicht=True,
    )
    stopps = verlauf.stopps_von(0)
    zwang = [b for b in stopps if b.notstopp]
    assert zwang and zwang[0].nach == "H"
    assert "M" in verlauf.gefahrene_mischungen(0, verlauf.dauer_ms), (
        "Die zweite Mischung muss kommen duerfen, sonst ist die Pflicht nicht erfuellbar"
    )


def test_nach_einem_zwangsstopp_wartet_der_planstopp_laenger(k, monza, feld, umgebung):
    """Der frische Satz wird nicht schon bei 65 Prozent wieder abgegeben.

    Entscheidung des Auftraggebers: nach einem Zwangsstopp erst unter
    60 Prozent. Geprueft wird gegen den Wert aus der Konfiguration.
    """
    mittel, verschleiss = umgebung
    verlauf = rn.simuliere(
        k, monza, feld[:4], RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss,
        strategien=tuple(strategie_mit(k, (8, 16)) for _ in range(4)),
    )
    tiefer = k.wert("boxenstopp", "strategie", "planstopp_nach_notstopp_restprofil")
    geprueft = 0
    for i in range(4):
        stopps = verlauf.stopps_von(i)
        for vorher, nachher in zip(stopps, stopps[1:], strict=False):
            if vorher.notstopp and not nachher.notstopp:
                assert nachher.restprofil <= tiefer, (
                    f"Auto {i}, Runde {nachher.runde}: {nachher.restprofil:.3f} > {tiefer}"
                )
                geprueft += 1
    assert geprueft, "Kein Planstopp nach einem Zwangsstopp - der Test prueft nichts"


def test_die_testkonstanten_wirken_wie_gedacht(k):
    """Punkt 92: Der Exponent darf die Testkonstanten nicht entwerten.

    Die drei Streckenfaktoren dieser Tests sind auf eine **Wirkung**
    eingestellt - 3,0 erzwingt Stopps, 1,5 laesst einen geplanten Stopp
    zu, 0,8 verschiebt ihn. Seit der Streckenfaktor mit einem Exponenten
    in den Verschleiss eingeht, sind die eingetippten Zahlen die rohen.
    Aendert jemand den Exponenten, faellt es hier auf und nicht erst in
    drei Tests weiter unten, die dann raetselhaft anderes messen.
    """
    wirkt = kern_reifen.wirksamer_streckenfaktor
    assert wirkt(k, VERSCHLEISS) == pytest.approx(3.0, abs=0.01)
    assert wirkt(k, VERSCHLEISS_PLANSTOPP) == pytest.approx(1.5, abs=0.01)
    assert wirkt(k, VERSCHLEISS_MILD) == pytest.approx(0.8, abs=0.01)
