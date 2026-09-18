"""Talent, Generationen und der Teamchef (Punkt 35).

Drei Dinge werden hier festgehalten:

* **Das Talent** - jeder Fahrer hat sein eigenes Potential, sein eigenes
  Tempo und sein eigenes Gipfelalter, alles aus dem Seed abgeleitet.
* **Der Teamchef** - dem Spieler gehoert ein ganzes Team mit vier Autos,
  und seine Fahrer altern und treten zurueck wie alle anderen.
* **Jedes Auto gehoert seinem Fahrer** - entwickelt wird einzeln, und
  wer geht, nimmt sein Auto mit.
"""

from __future__ import annotations

import datetime as dt

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import generationen as kg
from rennmanager.kern import karriere as kk
from rennmanager.kern import talent as kt
from rennmanager.kern import transfer as tr
from rennmanager.kern import welt as kw
from rennmanager.kern.auto import gesamtwert
from rennmanager.kern.zufall import Seedquelle

SEED = 12


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def quelle() -> Seedquelle:
    return Seedquelle(SEED)


@pytest.fixture(scope="module")
def welt(k: kf.Konfiguration) -> kw.Welt:
    return kw.erzeuge(k, Seedquelle(SEED).zweig("welt"), spielerliga=20)


# -- Talent ------------------------------------------------------------------
def test_dasselbe_talent_bei_gleichem_seed(k, quelle) -> None:
    """Abgeleitet statt gespeichert: derselbe Seed, dasselbe Talent."""
    einmal = kt.talent(k, 42, quelle)
    nochmal = kt.talent(k, 42, Seedquelle(SEED))
    assert einmal == nochmal
    assert kt.talent(k, 43, quelle) != einmal


def test_potentiale_folgen_der_leiter_der_welt(k, quelle) -> None:
    """Sortiert man alle Potentiale, kommt die Leiter aus GDD 9 zurueck.

    Damit bleibt die Zusammensetzung des Feldes ueber die Generationen
    dieselbe - ein Jahrgang laeuft weder nach oben noch nach unten davon.
    """
    je_liga = k.wert("ligen", "autos_je_liga")
    anzahl = je_liga * k.wert("ligen", "anzahl")
    potentiale = sorted(
        (kt.talent(k, nummer, quelle).gipfelstaerke for nummer in range(anzahl)),
        reverse=True,
    )
    leiter = kt._leiter(k)
    assert len(leiter) == anzahl
    for liga in (1, 5, 10, 15):
        anfang = (liga - 1) * je_liga
        soll = sum(leiter[anfang : anfang + je_liga]) / je_liga
        ist = sum(potentiale[anfang : anfang + je_liga]) / je_liga
        assert ist == pytest.approx(soll, rel=0.15)


def test_die_baender_werden_eingehalten(k, quelle) -> None:
    einstellung = k.wert("talent")
    for nummer in range(0, 300, 7):
        talent = kt.talent(k, nummer, quelle)
        assert einstellung["gipfel_min"] <= talent.gipfelalter <= einstellung["gipfel_max"]
        assert talent.abbaualter >= einstellung["abbau_min"]
        # Der Abbau kann nie vor dem Gipfel liegen.
        assert talent.abbaualter > talent.gipfelalter
        assert 0.0 < talent.schrittmass <= 0.95


def test_wer_frueh_seinen_gipfel_hat_waechst_schneller(k) -> None:
    """Das Schrittmass kommt aus dem Gipfelalter, nicht aus dem Nichts."""
    frueh = kt._schrittmass(k, gipfelalter=23, tempo=1.0)
    spaet = kt._schrittmass(k, gipfelalter=33, tempo=1.0)
    assert frueh > spaet
    # Das Tempo des Fahrers kommt obendrauf.
    assert kt._schrittmass(k, 28, tempo=2.0) > kt._schrittmass(k, 28, tempo=0.3)


def test_ein_junger_fahrer_waechst_auf_sein_potential_zu(k, quelle, welt) -> None:
    """Lueckenschluss: Jedes Jahr ein Anteil des Abstands."""
    fahrer = next(f for f in welt.liga(20) if not f.ist_spieler)
    talent = kt.talent(k, fahrer.nummer, quelle)
    ruecktritt = kg.ruecktrittsalter(k, fahrer.nummer, quelle)

    auto = fahrer.auto
    abstaende = []
    for _ in range(6):
        auto = kt.gewachsen(k, auto, talent, alter=20, ruecktrittsalter=ruecktritt)
        abstaende.append(abs(talent.gipfelstaerke - gesamtwert(k, auto)))

    # Der Abstand wird Jahr fuer Jahr kleiner und ueberschiesst nie.
    assert abstaende == sorted(abstaende, reverse=True)
    assert abstaende[-1] < abstaende[0]


def test_ein_alter_fahrer_baut_ab(k, quelle, welt) -> None:
    """Ab dem Abbaualter sinkt das Ziel - dieselbe Luecke, andere Richtung."""
    fahrer = next(f for f in welt.liga(5) if not f.ist_spieler)
    talent = kt.talent(k, fahrer.nummer, quelle)
    ruecktritt = max(kg.ruecktrittsalter(k, fahrer.nummer, quelle), talent.abbaualter + 2)

    auf_dem_gipfel = kt.gewachsen(
        k, fahrer.auto, talent, alter=talent.abbaualter, ruecktrittsalter=ruecktritt
    )
    danach = kt.gewachsen(
        k, auf_dem_gipfel, talent, alter=ruecktritt, ruecktrittsalter=ruecktritt
    )
    assert gesamtwert(k, danach) < gesamtwert(k, auf_dem_gipfel)

    # Am Ende der Laufbahn steht der Zielfaktor aus der Konfiguration.
    zuletzt = kt.zielfaktor(k, talent, ruecktritt, ruecktritt)
    assert zuletzt == pytest.approx(k.wert("generationen", "faktor_bei_ruecktritt"))
    assert kt.zielfaktor(k, talent, talent.abbaualter, ruecktritt) == 1.0


# -- Teamchef ----------------------------------------------------------------
def test_dem_spieler_gehoeren_vier_autos_in_liga_zwanzig(k, welt) -> None:
    eigene = welt.spielerfahrer
    assert len(eigene) == k.wert("teams", "autos_je_team")
    assert {f.liga for f in eigene} == {k.wert("ligen", "startliga")}
    assert len({f.team for f in eigene}) == 1
    assert all(set(f.auto.werte.values()) == {0} for f in eigene)


def test_auch_eigene_fahrer_werden_faellig(k, welt, quelle) -> None:
    """Der Sonderfall 'Der Spieler altert nicht' ist weg."""
    # Ein eigener Fahrer, weit ueber seiner Grenze: Er muss auftauchen.
    grenze = kg.ruecktrittsalter(k, welt.spielerfahrer[0].nummer, quelle)
    alt = dt.date(2027 - grenze - 3, 1, 1)
    gealtert = kw.mit_fahrerdaten(
        welt, {welt.spielerfahrer[0].nummer: {"geburtstag": alt}}
    )
    faellig = {f.nummer for f in kg.faellige(k, gealtert, 2027, quelle)}
    assert welt.spielerfahrer[0].nummer in faellig


def test_ein_newgen_auf_einem_eigenen_platz_bleibt_beim_spieler(k, welt, quelle) -> None:
    """Das Team behaelt seine vier Autos - nur sitzen andere darin."""
    eigener = welt.spielerfahrer[0]
    alt = dt.date(2027 - kg.ruecktrittsalter(k, eigener.nummer, quelle) - 9, 1, 1)
    gealtert = kw.mit_fahrerdaten(welt, {eigener.nummer: {"geburtstag": alt}})

    neue, bericht = kg.naechste_generation(k, gealtert, 2027, quelle)
    assert eigener.nummer in bericht.zurueckgetreten
    assert eigener.nummer in bericht.newgens
    nachfolger = neue.fahrer[eigener.nummer]
    assert nachfolger.ist_spieler
    assert nachfolger.name != eigener.name
    assert len(neue.spielerfahrer) == k.wert("teams", "autos_je_team")


# -- Jedes Auto gehoert seinem Fahrer ---------------------------------------
def test_jedes_auto_wird_einzeln_entwickelt(k) -> None:
    karriere = kk.beginne(k, 2026, 20, fahrer=(400, 401, 402, 403), fahrernummer=400)
    assert karriere.fahrer == (400, 401, 402, 403)

    karriere.werte["F1"] = 5_000
    assert karriere.werte_von(400)["F1"] == 5_000
    assert karriere.werte_von(401)["F1"] == 0

    karriere.waehle_fahrer(401)
    assert karriere.werte["F1"] == 0
    with pytest.raises(kk.KarriereFehler, match="gehoert nicht zum Team"):
        karriere.waehle_fahrer(999)


def test_belegte_plaetze_gelten_je_auto(k) -> None:
    """An einem Tag wird an einem Auto gearbeitet - jedes hat eigene Plaetze."""
    karriere = kk.beginne(k, 2026, 20, fahrer=(400, 401), fahrernummer=400)
    karriere.belegt.add("Werkstatt")
    assert karriere.belegt == {"Werkstatt"}
    karriere.waehle_fahrer(401)
    assert karriere.belegt == set()


def test_ein_neuer_fahrer_bringt_ein_leeres_auto_mit(k) -> None:
    """Entscheidung des Auftraggebers: Das Auto geht mit seinem Fahrer."""
    karriere = kk.beginne(k, 2026, 20, fahrer=(400, 401), fahrernummer=400)
    karriere.werte["F1"] = 60_000
    karriere.belegt.add("Werkstatt")

    karriere.fahrer_geht(400, nachfolger=404)
    assert karriere.fahrer == (401, 404)
    assert karriere.werte_von(404)["F1"] == 0
    assert karriere.belegte_plaetze[404] == set()
    # Die Auswahl wandert auf den Nachfolger, nicht ins Leere.
    assert karriere.fahrernummer == 404


def test_ohne_nachfolger_rueckt_die_auswahl_weiter(k) -> None:
    karriere = kk.beginne(k, 2026, 20, fahrer=(400, 401), fahrernummer=400)
    karriere.fahrer_geht(400)
    assert karriere.fahrer == (401,)
    assert karriere.fahrernummer == 401


# -- Fahrer holen (Punkt 7) --------------------------------------------------
def test_vertraege_laufen_aus_und_folgen_aufeinander(k, quelle) -> None:
    """Abgeleitet statt gespeichert - und in jedem Winter ist einer frei."""
    einstellung = k.wert("transfer")
    ende = tr.vertragsende(k, 17, quelle, 2030)
    assert ende >= 2030
    assert tr.vertragsende(k, 17, Seedquelle(SEED), 2030) == ende
    # Der Vertrag danach faengt spaeter an, aber nicht beliebig spaeter.
    spaeter = tr.vertragsende(k, 17, quelle, ende + 1)
    assert einstellung["laufzeit_min"] <= spaeter - ende <= einstellung["laufzeit_max"]
    assert tr.restlaufzeit(k, 17, quelle, ende) == 0
    assert tr.ist_frei(k, 17, quelle, ende)


def test_im_winter_ist_ein_teil_des_feldes_frei(k, welt, quelle) -> None:
    frei = tr.verfuegbare(k, welt, 2027, quelle)
    assert 0 < len(frei) < len(welt.fahrer)
    # Die eigenen Fahrer verpflichtet man nicht.
    assert not set(frei) & {f.nummer for f in welt.spielerfahrer}
    # Newgens des Jahrgangs sind immer dabei.
    newgen = next(f.nummer for f in welt.fahrer if f.nummer not in frei and not f.ist_spieler)
    assert newgen in tr.verfuegbare(k, welt, 2027, quelle, newgens=(newgen,))


def test_ein_starker_fahrer_kostet_mehr(k, welt, quelle) -> None:
    oben = max(welt.liga(1), key=lambda f: gesamtwert(k, f.auto))
    unten = min(welt.liga(20), key=lambda f: gesamtwert(k, f.auto))
    assert (
        tr.angebot(k, welt, oben.nummer, 2027, quelle).gehalt
        > tr.angebot(k, welt, unten.nummer, 2027, quelle).gehalt
    )


def test_ein_freier_fahrer_kostet_keine_abloese(k, welt, quelle) -> None:
    frei = tr.verfuegbare(k, welt, 2027, quelle)[0]
    assert tr.angebot(k, welt, frei, 2027, quelle).abloese == 0
    # Wer noch laeuft, kostet - und zwar je Restjahr.
    gebunden = next(
        f.nummer for f in welt.fahrer if tr.restlaufzeit(k, f.nummer, quelle, 2027) > 0
    )
    gebundenes = tr.angebot(k, welt, gebunden, 2027, quelle)
    assert gebundenes.abloese > 0
    assert gebundenes.gesamtkosten > gebundenes.gehalt * gebundenes.laufzeit


def test_ein_fahrer_geht_nicht_fuer_nichts_in_eine_tiefere_liga(k, welt, quelle) -> None:
    """Entscheidung des Auftraggebers: Er darf ablehnen."""
    oben = max(welt.liga(2), key=lambda f: gesamtwert(k, f.auto))
    fair = tr.angebot(k, welt, oben.nummer, 2027, quelle)
    antwort = tr.pruefe(
        k, welt, oben.nummer, fair, ziel_liga=20, ziel_auto_wert=0.0,
        jahr=2027, seedquelle=quelle,
    )
    assert not antwort.angenommen
    assert "tiefere Liga" in antwort.grund


def test_genug_geld_ueberzeugt_auch_ohne_auto(k, welt, quelle) -> None:
    """Der Spieler setzt jeden in ein leeres Auto - Geld muss das wettmachen."""
    fahrer = welt.liga(19)[0]
    mager = tr.angebot(k, welt, fahrer.nummer, 2027, quelle)
    assert not tr.pruefe(
        k, welt, fahrer.nummer, mager, ziel_liga=20, ziel_auto_wert=0.0,
        jahr=2027, seedquelle=quelle,
    ).angenommen

    reichlich = tr.angebot(
        k, welt, fahrer.nummer, 2027, quelle, gehalt=mager.gehalt * 20
    )
    antwort = tr.pruefe(
        k, welt, fahrer.nummer, reichlich, ziel_liga=19, ziel_auto_wert=0.0,
        jahr=2027, seedquelle=quelle,
    )
    assert antwort.angenommen
    assert antwort.ueberzeugung > 0


def test_wer_bekannt_ist_will_mehr(k, welt, quelle) -> None:
    """Popularitaet aus Punkt 5 macht einen Fahrer anspruchsvoller."""
    fahrer = welt.liga(19)[0]
    gebot = tr.angebot(k, welt, fahrer.nummer, 2027, quelle, gehalt=1_400_000)
    ohne = tr.pruefe(
        k, welt, fahrer.nummer, gebot, ziel_liga=19, ziel_auto_wert=0.0,
        jahr=2027, seedquelle=quelle, bekanntheit=0.0,
    )
    mit = tr.pruefe(
        k, welt, fahrer.nummer, gebot, ziel_liga=19, ziel_auto_wert=0.0,
        jahr=2027, seedquelle=quelle, bekanntheit=1.0,
    )
    assert mit.ueberzeugung < ohne.ueberzeugung
