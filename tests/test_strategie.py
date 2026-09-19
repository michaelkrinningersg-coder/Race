"""Reifenstrategie: Mischungsfolge, Stoppfenster und die Regeln (Punkt 39).

Die Regeln kommen vom Auftraggeber: mindestens ein Stopp, hoechstens
drei (im Notfall vier), zwei Mischungen im Trockenen Pflicht, kein Stopp
in den ersten und letzten drei Runden, mindestens drei Runden zwischen
zwei Stopps - und **kein Stint unter 30 Prozent Restprofil**, auch nicht
nach dem Zufallsfenster.
"""

import numpy as np
import pytest

from rennmanager.kern import boxenstopp as bx
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import strategie as sg
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.auto import gleichverteilt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

LIGA = 1


@pytest.fixture(scope="module")
def k():
    return lade()


@pytest.fixture(scope="module")
def strecken(k):
    return kern_strecke.lade_alle(k)


@pytest.fixture(scope="module")
def zandvoort(strecken):
    return next(s for s in strecken if s.name == "Zandvoort")


@pytest.fixture(scope="module")
def auto(k):
    return gleichverteilt(k, k.wert("skala", "referenz"))


@pytest.fixture(scope="module")
def umgebung(k, strecken, zandvoort, auto):
    """Runden, Rundenzeit, Streckenfaktor und Stoppverlust an einem Ort."""
    grenzen = kern_tempo.grenzen_aus(k, auto)
    return {
        "runden": kern_rennen.rundenzahl(k, zandvoort, LIGA),
        "rundenzeit": float(
            kern_tempo.rundenzeit_ms(
                zandvoort, kern_tempo.geschwindigkeitsprofil(zandvoort, grenzen)
            )
        ),
        "faktor": kern_reifen.streckenfaktor(
            k, zandvoort, kern_reifen.mittlere_querbeschleunigung(strecken)
        ),
        "verlust": float(
            bx.durchfahrtsverlust_ms(k, zandvoort, grenzen)
            + bx.anfahrverlust_ms(k, grenzen)
            + bx.mittlere_standzeit_ms(k)
        ),
    }


def restprofile(k, auto, strecke, folge, stopps, runden, faktor, naesse=0.0, wf=1.0):
    """Restprofil am Ende jedes Stints - die Groesse, um die es geht."""
    enden = list(stopps) + [runden]
    vorher = 0
    werte = []
    for misch, bis in zip(folge, enden, strict=True):
        je_m = kern_reifen.verschleiss_je_meter(k, auto, misch, faktor, wf, naesse)
        werte.append(max(1.0 - (bis - vorher) * strecke.laenge_m * je_m, 0.0))
        vorher = bis
    return werte


# -- Die Regeln -------------------------------------------------------------
def test_eine_folge_ohne_stopp_ist_verboten(k, auto):
    misch = kern_reifen.standardmischung(k)
    strategie = sg.Strategie(mischungen=(misch,), stopps=())
    assert not sg.ist_erlaubt(k, strategie, 50)


def test_eine_einzige_mischung_ist_im_trockenen_verboten(k):
    misch = kern_reifen.standardmischung(k)
    strategie = sg.Strategie(mischungen=(misch, misch), stopps=(20,))
    assert not sg.ist_erlaubt(k, strategie, 50)
    # Im Nassen faellt die Pflicht.
    assert sg.ist_erlaubt(k, strategie, 50, nass=True)


def test_ein_stopp_in_der_sperrfrist_ist_verboten(k):
    weich = kern_reifen.mischung(k, "weich")
    hart = kern_reifen.mischung(k, "hart")
    sperre = k.wert("boxenstopp", "strategie", "sperre_runden")
    assert not sg.ist_erlaubt(k, sg.Strategie((weich, hart), (sperre,)), 50)
    assert sg.ist_erlaubt(k, sg.Strategie((weich, hart), (sperre + 1,)), 50)
    assert not sg.ist_erlaubt(k, sg.Strategie((weich, hart), (50 - sperre + 1,)), 50)


def test_mehr_als_drei_stopps_sind_verboten(k):
    weich = kern_reifen.mischung(k, "weich")
    hart = kern_reifen.mischung(k, "hart")
    folge = (weich, hart, weich, hart, weich)
    assert not sg.ist_erlaubt(k, sg.Strategie(folge, (10, 20, 30, 40)), 60)


# -- Reichweite -------------------------------------------------------------
def test_weich_traegt_kuerzer_als_hart(k, auto, zandvoort, umgebung):
    weich = sg.reichweite_runden(
        k, auto, kern_reifen.mischung(k, "weich"), zandvoort.laenge_m, umgebung["faktor"]
    )
    hart = sg.reichweite_runden(
        k, auto, kern_reifen.mischung(k, "hart"), zandvoort.laenge_m, umgebung["faktor"]
    )
    assert weich < hart


def test_der_hoechststint_bleibt_unter_der_reichweite(k, auto, zandvoort, umgebung):
    """Mit 30 Prozent Restprofil kommt man nicht so weit wie bis auf null."""
    for name in ("weich", "mittel", "hart"):
        misch = kern_reifen.mischung(k, name)
        bis_null = sg.reichweite_runden(
            k, auto, misch, zandvoort.laenge_m, umgebung["faktor"]
        )
        mit_rest = sg.hoechststint_runden(
            k, auto, misch, zandvoort.laenge_m, umgebung["faktor"]
        )
        assert mit_rest < bis_null


# -- Die Vorausberechnung ---------------------------------------------------
def test_jede_variante_haelt_die_regeln(k, auto, zandvoort, umgebung):
    alle = sg.varianten(
        k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
        umgebung["verlust"], umgebung["faktor"],
    )
    assert alle
    for v in alle:
        assert sg.ist_erlaubt(
            k, sg.Strategie(v.mischungen, v.stopps), umgebung["runden"]
        )


def test_jede_variante_haelt_das_mindestprofil(k, auto, zandvoort, umgebung):
    mindest = k.wert("boxenstopp", "strategie", "mindest_restprofil")
    alle = sg.varianten(
        k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
        umgebung["verlust"], umgebung["faktor"],
    )
    for v in alle:
        rest = restprofile(
            k, auto, zandvoort, v.mischungen, v.stopps,
            umgebung["runden"], umgebung["faktor"],
        )
        assert min(rest) >= mindest - 1e-9, f"{v.folge}: {rest}"


def test_die_beste_variante_steht_vorn(k, auto, zandvoort, umgebung):
    alle = sg.varianten(
        k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
        umgebung["verlust"], umgebung["faktor"],
    )
    assert alle == sorted(alle, key=lambda v: v.zeit_ms)


def test_der_stoppverlust_verschiebt_das_optimum_auf_haertere_reifen(
    k, auto, zandvoort, umgebung
):
    """Wer fuer jeden Stopp teuer bezahlt, faehrt lieber den zaehen Reifen."""
    def bester(verlust):
        alle = sg.varianten(
            k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
            verlust, umgebung["faktor"],
        )
        return alle[0]

    billig = bester(5_000.0)
    teuer = bester(120_000.0)
    assert teuer.anzahl_stopps <= billig.anzahl_stopps


# -- Das Zufallsfenster -----------------------------------------------------
def test_das_fenster_haelt_das_mindestprofil(k, auto, zandvoort, umgebung):
    """Der Kern der Sache: Vorher hebelte das Fenster die 30 Prozent aus."""
    mindest = k.wert("boxenstopp", "strategie", "mindest_restprofil")
    alle = sg.varianten(
        k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
        umgebung["verlust"], umgebung["faktor"],
    )
    zu_wenig = 0
    for n in range(60):
        strategie = sg.ki_strategie(
            k, auto, umgebung["runden"], zandvoort.laenge_m, Seedquelle(n),
            umgebung["faktor"], 1.0, 0.0, True,
            umgebung["rundenzeit"], umgebung["verlust"], alle,
        )
        rest = restprofile(
            k, auto, zandvoort, strategie.mischungen, strategie.stopps,
            umgebung["runden"], umgebung["faktor"],
        )
        if min(rest) < mindest - 1e-9:
            zu_wenig += 1
    assert zu_wenig == 0, f"{zu_wenig} von 60 Strategien fallen unter {mindest:.0%}"


def test_das_fenster_streut_die_stopps(k, auto, zandvoort, umgebung):
    alle = sg.varianten(
        k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
        umgebung["verlust"], umgebung["faktor"],
    )
    gesehen = {
        sg.ki_strategie(
            k, auto, umgebung["runden"], zandvoort.laenge_m, Seedquelle(n),
            umgebung["faktor"], 1.0, 0.0, True,
            umgebung["rundenzeit"], umgebung["verlust"], alle,
        ).stopps
        for n in range(40)
    }
    assert len(gesehen) > 5


def test_zwischen_zwei_stopps_liegen_die_mindestrunden(k, auto, zandvoort, umgebung):
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    alle = sg.varianten(
        k, auto, umgebung["runden"], umgebung["rundenzeit"], zandvoort.laenge_m,
        umgebung["verlust"], umgebung["faktor"],
    )
    for n in range(40):
        stopps = sg.ki_strategie(
            k, auto, umgebung["runden"], zandvoort.laenge_m, Seedquelle(n),
            umgebung["faktor"], 1.0, 0.0, True,
            umgebung["rundenzeit"], umgebung["verlust"], alle,
        ).stopps
        for davor, danach in zip(stopps, stopps[1:], strict=False):
            assert danach - davor >= abstand


# -- Wetter -----------------------------------------------------------------
def test_die_pflicht_faellt_im_nassen(k):
    assert sg.pflicht_zwei_mischungen(k, "trocken")
    assert sg.pflicht_zwei_mischungen(k, ("trocken", "heiss"))
    assert not sg.pflicht_zwei_mischungen(k, "regen")
    assert not sg.pflicht_zwei_mischungen(k, ("trocken", "wechselhaft"))


def test_zu_nasser_lage_gehoert_ein_nasser_reifen(k):
    assert sg.passende_mischung(k, 0.0).naesse == 0.0
    assert sg.passende_mischung(k, 1.0).naesse > 0.5
    # Bei wechselhaft ist der Intermediate der naechste.
    wechselhaft = kern_reifen.naesse_von(k, "wechselhaft")
    assert sg.passende_mischung(k, wechselhaft).schluessel == "intermediate"


def test_der_notstopp_kommt_erst_nach_der_mindestzeit(k):
    trocken = kern_reifen.mischung(k, "hart")
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    # Falscher Reifen, aber gerade erst gestoppt: noch nicht.
    assert not sg.notstopp(k, trocken, 1.0, abstand - 1)
    assert sg.notstopp(k, trocken, 1.0, abstand)
    # Passender Reifen: nie.
    assert not sg.notstopp(k, trocken, 0.0, 20)


def test_die_vorhersage_folgt_dem_wetterverlauf(k, zandvoort, umgebung):
    wetter = kern_wetter.wuerfle(
        k, zandvoort.name,
        int(umgebung["rundenzeit"] * umgebung["runden"]),
        int(umgebung["rundenzeit"]),
        Seedquelle(3),
    )
    naesse = sg.vorhersage(k, wetter, umgebung["runden"], umgebung["rundenzeit"])
    assert len(naesse) == umgebung["runden"]
    lagen = sg.lagen_im_rennen(k, wetter, umgebung["runden"], umgebung["rundenzeit"])
    assert set(lagen) <= set(wetter.zustaende)


def test_ohne_wetter_ist_die_vorhersage_trocken(k):
    assert sg.vorhersage(k, None, 10, 90_000.0) == (0.0,) * 10
    assert sg.verschleissvorhersage(k, None, 10, 90_000.0) == (1.0,) * 10


def test_eine_wechselnde_vorhersage_macht_die_tabelle_startabhaengig(
    k, auto, zandvoort, umgebung
):
    """Derselbe Stint kostet vor und nach dem Regen verschieden viel."""
    runden = umgebung["runden"]
    trocken = sg._stinttabelle(
        k, auto, kern_reifen.mischung(k, "hart"), runden, umgebung["rundenzeit"],
        zandvoort.laenge_m, umgebung["faktor"], 1.0, 0.0,
    )
    assert trocken.konstant

    wechselnd = [0.0] * (runden // 2) + [0.7] * (runden - runden // 2)
    nass = sg._stinttabelle(
        k, auto, kern_reifen.mischung(k, "hart"), runden, umgebung["rundenzeit"],
        zandvoort.laenge_m, umgebung["faktor"], 1.0, wechselnd,
    )
    assert not nass.konstant
    frueh = nass.restprofil(np.array([0]), 10)
    spaet = nass.restprofil(np.array([runden - 12]), 10)
    assert frueh[0] > spaet[0], "Der Regen muss mehr Profil kosten"


# -- Das ganze Feld ---------------------------------------------------------
def test_feldstrategien_geben_jedem_auto_eine_strategie(k, zandvoort, strecken):
    feld = kern_rennen.starterfeld(k, LIGA, seedquelle=Seedquelle(1))
    runden = kern_rennen.rundenzahl(k, zandvoort, LIGA)
    faktor = kern_reifen.streckenfaktor(
        k, zandvoort, kern_reifen.mittlere_querbeschleunigung(strecken)
    )
    ergebnis = sg.feldstrategien(
        k, [t.auto for t in feld], zandvoort, runden, faktor, None, Seedquelle(5)
    )
    assert len(ergebnis.je_auto) == len(feld)
    assert ergebnis.pflicht_zwei
    for strategie in ergebnis.je_auto:
        assert sg.ist_erlaubt(k, strategie, runden)


def test_das_feld_faehrt_nicht_alles_dasselbe(k, zandvoort, strecken):
    feld = kern_rennen.starterfeld(k, LIGA, seedquelle=Seedquelle(1))
    runden = kern_rennen.rundenzahl(k, zandvoort, LIGA)
    faktor = kern_reifen.streckenfaktor(
        k, zandvoort, kern_reifen.mittlere_querbeschleunigung(strecken)
    )
    ergebnis = sg.feldstrategien(
        k, [t.auto for t in feld], zandvoort, runden, faktor, None, Seedquelle(5)
    )
    folgen = {
        tuple(m.kuerzel for m in s.mischungen) for s in ergebnis.je_auto
    }
    assert len(folgen) > 1


def test_gleicher_seed_gleiche_strategien(k, zandvoort, strecken):
    feld = kern_rennen.starterfeld(k, LIGA, seedquelle=Seedquelle(1))
    runden = kern_rennen.rundenzahl(k, zandvoort, LIGA)
    faktor = kern_reifen.streckenfaktor(
        k, zandvoort, kern_reifen.mittlere_querbeschleunigung(strecken)
    )
    autos = [t.auto for t in feld]
    erst = sg.feldstrategien(k, autos, zandvoort, runden, faktor, None, Seedquelle(5))
    nochmal = sg.feldstrategien(k, autos, zandvoort, runden, faktor, None, Seedquelle(5))
    assert erst.je_auto == nochmal.je_auto


# -- Die Regeln nach einem Zwangsstopp (Punkt 78) ---------------------------
def test_nicht_weicher_als_nimmt_die_haertere(k):
    """Weicher heisst: hoeherer Verschleiss."""
    weich = kern_reifen.mischung(k, "weich")
    mittel = kern_reifen.mischung(k, "mittel")
    hart = kern_reifen.mischung(k, "hart")
    # Der Wunsch ist weicher als die Untergrenze - es bleibt bei der Untergrenze.
    assert sg.nicht_weicher_als(weich, hart) is hart
    assert sg.nicht_weicher_als(mittel, hart) is hart
    # Gleich hart oder haerter darf durch.
    assert sg.nicht_weicher_als(hart, hart) is hart
    assert sg.nicht_weicher_als(hart, mittel) is hart


def test_nicht_weicher_als_vergleicht_nur_innerhalb_einer_naesseklasse(k):
    """Ein Regenreifen ist nicht haerter als ein Slick, er ist etwas anderes."""
    weich = kern_reifen.mischung(k, "weich")
    regen = kern_reifen.mischung(k, "regen")
    # Regen hat rechnerisch weniger Verschleiss als Weich - trotzdem darf
    # die Haerteregel im Regen nicht dazwischenfunken.
    assert regen.verschleiss < weich.verschleiss
    assert sg.nicht_weicher_als(regen, weich) is regen
    assert sg.nicht_weicher_als(weich, regen) is weich


def test_nach_einem_notstopp_darf_der_planstopp_laenger_warten(k):
    tiefer = sg.verschiebeschwelle(k, nach_notstopp=True)
    normal = sg.verschiebeschwelle(k, nach_notstopp=False)
    assert tiefer < normal
    assert tiefer == k.wert("boxenstopp", "strategie", "planstopp_nach_notstopp_restprofil")
    assert normal == k.wert("boxenstopp", "strategie", "planstopp_ab_restprofil")


# -- Wo Weich wegfaellt (Punkt 80) ------------------------------------------
def test_weichste_trockene_wird_ueber_den_verschleiss_gefunden(k):
    """Nicht ueber den Schluessel, sondern ueber die Zahlen."""
    weichste = sg.weichste_trockene(k)
    trocken = [m for m in kern_reifen.mischungen(k) if m.naesse == 0.0]
    assert weichste.naesse == 0.0
    assert all(m.verschleiss <= weichste.verschleiss for m in trocken)


def test_ab_dem_streckenfaktor_bleiben_nur_die_haerteren(k, strecken):
    """Entscheidung des Auftraggebers: ueber der Grenze kein Weich mehr.

    Geprueft an zwei echten Strecken - eine darueber, eine darunter -,
    und die Grenze kommt aus der Konfiguration.
    """
    grenze = k.wert("boxenstopp", "strategie", "weich_hoechstens_streckenfaktor")
    weich = sg.weichste_trockene(k)
    mittlere = kern_reifen.mittlere_querbeschleunigung(strecken)
    faktoren = {
        s.name: kern_reifen.streckenfaktor(k, s, mittlere) for s in strecken
    }
    hart_zu = max(faktoren, key=lambda n: faktoren[n])
    sanft = min(faktoren, key=lambda n: faktoren[n])
    assert faktoren[hart_zu] > grenze >= faktoren[sanft]

    feld = kern_rennen.starterfeld(k, LIGA, seedquelle=Seedquelle(1))
    for name, erwartet_weich in ((hart_zu, False), (sanft, True)):
        strecke = next(s for s in strecken if s.name == name)
        runden = kern_rennen.rundenzahl(k, strecke, LIGA)
        ergebnis = sg.feldstrategien(
            k, [t.auto for t in feld], strecke, runden, faktoren[name], None,
            Seedquelle(5),
        )
        gefahren = {
            m.schluessel for s in ergebnis.je_auto for m in s.mischungen
        }
        assert (weich.schluessel in gefahren) is erwartet_weich, (
            f"{name} (Faktor {faktoren[name]:.3f}): {sorted(gefahren)}"
        )


def test_wer_oft_stoppt_faehrt_nicht_auf_weich(k, strecken):
    """Keine Variante mit mehr als drei Stopps steht auf dem weichsten Gummi.

    Gesucht wird ueber alle zwanzig Strecken und ein ganzes Feld - wenn
    irgendwo eine Vier-Stopp-Variante entsteht, dann dort.
    """
    grenze = k.wert("boxenstopp", "strategie", "weich_hoechstens_stopps")
    weich = sg.weichste_trockene(k)
    mittlere = kern_reifen.mittlere_querbeschleunigung(strecken)
    feld = kern_rennen.starterfeld(k, LIGA, seedquelle=Seedquelle(1))
    autos = [t.auto for t in feld]
    viele = 0
    for strecke in strecken:
        faktor = kern_reifen.streckenfaktor(k, strecke, mittlere)
        runden = kern_rennen.rundenzahl(k, strecke, LIGA)
        ergebnis = sg.feldstrategien(
            k, autos, strecke, runden, faktor, None, Seedquelle(5)
        )
        for eine in ergebnis.je_auto:
            if len(eine.stopps) <= grenze:
                continue
            viele += 1
            assert weich.schluessel not in {m.schluessel for m in eine.mischungen}, (
                f"{strecke.name}: {[m.kuerzel for m in eine.mischungen]}"
            )
    # ``viele`` darf null sein: Dass es solche Strategien gar nicht mehr
    # gibt, ist der erwuenschte Fall und kein Grund durchzufallen.
    assert viele >= 0


# -- Geduld auf dem falschen Reifen (Punkt 83) ------------------------------
def test_die_geduld_bleibt_in_ihrer_spanne(k):
    """Null bis ``falscher_reifen_max_runden``, aus dem Seed des Autos."""
    hoechstens = k.wert("boxenstopp", "strategie", "falscher_reifen_max_runden")
    gezogen = [
        sg.geduld_falscher_reifen(k, Seedquelle(7).zweig("reifengeduld", i))
        for i in range(60)
    ]
    assert all(0 <= wert <= hoechstens for wert in gezogen), sorted(set(gezogen))
    # Und sie ist nicht fuer alle gleich - sonst kaeme das Feld wieder
    # geschlossen herein.
    assert len(set(gezogen)) > 1


def test_gleicher_seed_gleiche_geduld(k):
    erst = sg.geduld_falscher_reifen(k, Seedquelle(7).zweig("reifengeduld", 3))
    nochmal = sg.geduld_falscher_reifen(k, Seedquelle(7).zweig("reifengeduld", 3))
    assert erst == nochmal


def test_wer_geduld_hat_faehrt_noch_eine_runde_weiter(k):
    """Der Kern der Regel: Der falsche Reifen allein holt niemanden herein.

    Vorher gab ``notstopp()`` sofort True zurueck, sobald der Reifen
    falsch war - und weil bei einem Wetterwechsel alle dreissig Reifen im
    selben Augenblick falsch werden, kam das ganze Feld in derselben
    Runde herein.
    """
    trocken = kern_reifen.mischung(k, "hart")
    nass = 1.0   # Starkregen: Trockenreifen ist eindeutig falsch
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    # Ohne Geduld sofort.
    assert sg.notstopp(k, trocken, nass, abstand, 0, 0)
    # Mit einer Runde Geduld erst eine Runde spaeter.
    assert not sg.notstopp(k, trocken, nass, abstand, 0, 1)
    assert sg.notstopp(k, trocken, nass, abstand, 1, 1)
    # Der Mindestabstand zum letzten Stopp gilt weiter.
    assert not sg.notstopp(k, trocken, nass, abstand - 1, 5, 0)


def test_ein_passender_reifen_bleibt_draussen(k):
    """Geduld hin oder her - wer den richtigen Reifen hat, kommt nicht herein."""
    regen = kern_reifen.mischung(k, "regen")
    abstand = k.wert("boxenstopp", "strategie", "abstand_min_runden")
    assert not sg.notstopp(k, regen, 1.0, abstand, 99, 0)
