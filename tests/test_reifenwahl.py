"""Die Reifenwahl vor dem Rennen (Punkt 39).

Der Spieler fuehrt zwei Fahrer; welche Mischungsfolge jeder von ihnen
faehrt, darf er waehlen - aber nur aus dem, was die Vorausberechnung als
tragfaehig ermittelt hat, und nur **vor** dem Start. Der Rennverlauf wird
in einem Stueck gerechnet und danach nur noch abgespielt; ein Eingriff
mitten im Rennen muesste ihn ab dieser Stelle neu rechnen.
"""

import pytest

from rennmanager.kern import karriere as kk
from rennmanager.kern import saison as ks
from rennmanager.kern import strategie as sg
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import welt as kern_welt
from rennmanager.kern.zufall import Seedquelle

SEED = 99


@pytest.fixture(scope="module")
def k(kleine_konfiguration):
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``."""
    return kleine_konfiguration


@pytest.fixture(scope="module")
def strecken(k):
    return kern_strecke.lade_alle(k)


@pytest.fixture(scope="module")
def welt(k):
    return kern_welt.erzeuge(k, Seedquelle(SEED).zweig("welt"))


def frischer_lauf(k, welt, strecken):
    karriere = kk.beginne(
        k, 2026, fahrer=tuple(f.nummer for f in welt.spielerfahrer)
    )
    lauf = ks.Saisonlauf(
        k, welt, Seedquelle(SEED), jahr=2026, strecken=strecken, karriere=karriere
    )
    return ks.Wochenendlauf(lauf)


@pytest.fixture(scope="module")
def nach_qualifying(k, welt, strecken):
    """Ein Wochenende bis zur Reifenwahl - einmal fuer alle Tests."""
    wochenende = frischer_lauf(k, welt, strecken)
    wochenende.fahre_qualifying()
    return wochenende


# -- Was zur Wahl steht -----------------------------------------------------
def test_vor_dem_qualifying_gibt_es_nichts_zu_waehlen(k, welt, strecken):
    wochenende = frischer_lauf(k, welt, strecken)
    with pytest.raises(ks.SaisonFehler):
        wochenende.strategiewahl()


def test_die_wahl_nennt_wetter_und_varianten(nach_qualifying):
    vor = nach_qualifying.strategiewahl()
    assert vor.strategien.varianten
    assert vor.strategien.lagen
    assert len(vor.teilnehmer) == len(vor.strategien.je_auto)


def test_zweimal_gefragt_ist_zweimal_dasselbe(nach_qualifying):
    """Der Blick auf die Wahl darf das Rennen nicht veraendern (GDD 15)."""
    erst = nach_qualifying.strategiewahl()
    nochmal = nach_qualifying.strategiewahl()
    assert erst is nochmal
    assert erst.wetter.zustaende == nochmal.wetter.zustaende


def test_jede_angebotene_variante_ist_erlaubt(nach_qualifying):
    vor = nach_qualifying.strategiewahl()
    runden = nach_qualifying.runden
    nass = not vor.strategien.pflicht_zwei
    for variante in vor.strategien.varianten:
        strategie = sg.Strategie(variante.mischungen, variante.stopps)
        assert sg.ist_erlaubt(
            nach_qualifying.lauf.konfiguration, strategie, runden, nass=nass
        )


def test_die_varianten_stehen_nach_rennzeit(nach_qualifying):
    zeiten = [v.zeit_ms for v in nach_qualifying.strategiewahl().strategien.varianten]
    assert zeiten == sorted(zeiten)


# -- Waehlen ----------------------------------------------------------------
def test_die_wahl_kommt_im_rennen_an(k, welt, strecken):
    wochenende = frischer_lauf(k, welt, strecken)
    wochenende.fahre_qualifying()
    vor = wochenende.strategiewahl()
    eigene = [f.nummer for f in welt.spielerfahrer]
    gewaehlt = vor.strategien.varianten[0]
    wochenende.waehle_reifen(
        eigene[0], sg.Strategie(gewaehlt.mischungen, gewaehlt.stopps)
    )

    verlauf = wochenende.fahre_rennen()
    stelle = [t.nummer for t in verlauf.teilnehmer].index(eigene[0])
    stopps = [b for b in verlauf.stopps_von(stelle) if not b.notstopp]

    # Gefahren wird die gewaehlte Folge, und zwar von vorn: die
    # Startmischung und jeder Wechsel stehen so in der Wahl.
    gefahren = [verlauf.mischung_zu(0)[stelle]] + [b.nach for b in stopps]
    assert gefahren == [m.kuerzel for m in gewaehlt.mischungen[: len(gefahren)]]

    # Frueher als gewaehlt kommt niemand herein ...
    assert all(gewaehlt.stopps[n] <= b.runde for n, b in enumerate(stopps))
    # ... und oefter auch nicht.
    assert len(stopps) <= len(gewaehlt.stopps)
    # Dass es *weniger* sein duerfen, ist die Regel
    # ``planstopp_ab_restprofil``: Ueber der Schwelle wird nicht
    # gewechselt, sondern Runde um Runde weitergefahren, und wer schon
    # einmal gewechselt hat, faehrt den guten Satz bis ins Ziel. Das gilt
    # fuer den Spieler wie fuer die KI - gemessen faellt in diesem Lauf
    # der zweite von zwei geplanten Stopps weg, weil der frische Satz
    # nach drei Runden noch bei 88 Prozent steht.


@pytest.fixture(scope="module")
def ohne_wahl_gefahren(k, welt, strecken):
    """Ein Wochenende ohne Reifenwahl, ganz gefahren - einmal fuer beide Tests.

    Punkt 77: Zwei Tests rechneten dafuer je ein eigenes Wochenende,
    gemessen zwoelf Sekunden das Stueck. Der Blick auf die Wahl vor dem
    Start aendert am Rennen nichts (GDD 15) und wird hier aufgehoben,
    damit der zweite Test danach noch etwas zu waehlen versucht.
    """
    wochenende = frischer_lauf(k, welt, strecken)
    wochenende.fahre_qualifying()
    assert wochenende.reifenwahl == {}
    vor = wochenende.strategiewahl()
    return wochenende, wochenende.fahre_rennen(), vor


def test_ohne_wahl_entscheidet_das_team(ohne_wahl_gefahren):
    _wochenende, verlauf, _vor = ohne_wahl_gefahren
    assert verlauf.boxenstopps, "Ohne Wahl muss trotzdem gestoppt werden"


def test_die_wahl_laesst_sich_zurueckgeben(k, welt, strecken):
    wochenende = frischer_lauf(k, welt, strecken)
    wochenende.fahre_qualifying()
    vor = wochenende.strategiewahl()
    eigene = welt.spielerfahrer[0].nummer
    gewaehlt = vor.strategien.varianten[0]
    wochenende.waehle_reifen(eigene, sg.Strategie(gewaehlt.mischungen, gewaehlt.stopps))
    assert eigene in wochenende.reifenwahl
    wochenende.waehle_reifen(eigene, None)
    assert eigene not in wochenende.reifenwahl


def test_eine_unerlaubte_strategie_wird_abgewiesen(k, welt, strecken):
    """Nur ein Stopp weniger als erlaubt - und schon geht es nicht."""
    wochenende = frischer_lauf(k, welt, strecken)
    wochenende.fahre_qualifying()
    wochenende.strategiewahl()
    eigene = welt.spielerfahrer[0].nummer
    from rennmanager.kern import reifen as kern_reifen

    hart = kern_reifen.mischung(k, "hart")
    with pytest.raises(sg.StrategieFehler):
        wochenende.waehle_reifen(eigene, sg.Strategie((hart,), ()))


def test_nach_dem_start_steht_die_wahl_fest(welt, ohne_wahl_gefahren):
    """Der Verlauf ist gerechnet; ein Eingriff kaeme zu spaet."""
    wochenende, _verlauf, vor = ohne_wahl_gefahren
    gewaehlt = vor.strategien.varianten[0]
    with pytest.raises(ks.SaisonFehler):
        wochenende.waehle_reifen(
            welt.spielerfahrer[0].nummer,
            sg.Strategie(gewaehlt.mischungen, gewaehlt.stopps),
        )


# -- Das Qualifying ---------------------------------------------------------
def test_im_qualifying_wird_immer_weich_gefahren(k):
    """Keine Wahl, sondern eine Regel des Auftraggebers."""
    from rennmanager.kern import reifen as kern_reifen

    trocken = [m for m in kern_reifen.mischungen(k) if m.naesse == 0.0]
    weichster = max(trocken, key=lambda m: m.tempo)
    assert sg.qualifyingmischung(k, "trocken") == weichster
    assert sg.qualifyingmischung(k, "heiss") == weichster


def test_im_nassen_qualifying_gilt_der_passende_satz(k):
    assert sg.qualifyingmischung(k, "wechselhaft").schluessel == "intermediate"
    assert sg.qualifyingmischung(k, "regen").schluessel == "regen"
    assert sg.qualifyingmischung(k, "starkregen").schluessel == "regen"


def test_die_qualifyingfahrt_nennt_ihre_mischung(nach_qualifying):
    session = nach_qualifying.qualifying
    kuerzel = {f.mischung for f in session.fahrten}
    assert kuerzel
    assert "" not in kuerzel
