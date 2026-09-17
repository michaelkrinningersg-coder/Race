"""Tests fuer die Einzelereignisse (GDD 14).

"Ereignisse werden beim Tageswechsel ausgeloest, 0-2 je 14-Tage-Zyklus,
und betreffen Spieler und KI gleichermassen. Sie wirken zeitweise oder -
klein - dauerhaft. Ausgeloest werden sie nur in den ersten 4 Tagen eines
Zyklus."
"""

from __future__ import annotations

import datetime as dt

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import ereignis as ev
from rennmanager.kern import kalender as kl
from rennmanager.kern import karriere as kk
from rennmanager.kern.zufall import Seedquelle

TAG = dt.date(2026, 3, 2)


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def saison(k) -> kl.Saison:
    return kl.erzeuge(k, 2026)


# --- Katalog --------------------------------------------------------------
def test_alle_35_ereignisse_sind_verwendbar(k):
    """Jedes Ereignis muss sich ausloesen und beschreiben lassen."""
    lage = ev.Lage(k)
    for e in ev.liste(k):
        aktiv = lage.loese_aus(e["schluessel"], TAG)
        assert aktiv.name
        assert aktiv.beschreibung(k)
        assert isinstance(aktiv.dauer, ev.Dauer)
    assert len({e["schluessel"] for e in ev.liste(k)}) == 35


def test_unbekanntes_ereignis_faellt_auf(k):
    with pytest.raises(ev.EreignisFehler):
        ev.eintrag(k, "E99")


def test_jede_dauerart_kommt_vor(k):
    arten = {ev.dauer_von(e) for e in ev.liste(k)}
    assert arten == set(ev.Dauer)


# --- Auslosung ------------------------------------------------------------
def test_zyklen_enden_auf_den_renntagen(k, saison):
    """Das Ausloesefenster muss in die freien Tage nach dem Rennen fallen."""
    bloecke = ev.zyklen(k, saison)
    enden = {block[-1] for block in bloecke}
    assert set(saison.renntage) <= enden


def test_zyklen_decken_das_ganze_jahr_ab(k, saison):
    bloecke = ev.zyklen(k, saison)
    tage = [datum for block in bloecke for datum in block]
    assert tage == [tag.datum for tag in saison.tage]


def test_hoechstens_zwei_ereignisse_je_zyklus(k, saison):
    hoechst = k.wert("ereignisse", "je_zyklus_max")
    for seed in range(20):
        for nummer, tage in enumerate(ev.zyklen(k, saison)):
            gezogen = ev.plane_zyklus(k, tage, Seedquelle(seed).zweig("zyklus", nummer))
            assert len(gezogen) <= hoechst


def test_ereignisse_liegen_nur_im_ausloesefenster(k, saison):
    fenster = k.wert("ereignisse", "ausloesefenster_tage")
    for seed in range(10):
        for nummer, tage in enumerate(ev.zyklen(k, saison)):
            erlaubt = set(tage[:fenster])
            for ausloesung in ev.plane_zyklus(
                k, tage, Seedquelle(seed).zweig("zyklus", nummer)
            ):
                assert ausloesung.datum in erlaubt


def test_innerhalb_eines_zyklus_kein_ereignis_doppelt(k, saison):
    for seed in range(30):
        for nummer, tage in enumerate(ev.zyklen(k, saison)):
            gezogen = ev.plane_zyklus(k, tage, Seedquelle(seed).zweig("zyklus", nummer))
            schluessel = [a.schluessel for a in gezogen]
            assert len(schluessel) == len(set(schluessel))


def test_gleicher_seed_gleiche_saison(k, saison):
    erste = ev.plane_saison(k, saison, Seedquelle(3))
    zweite = ev.plane_saison(k, saison, Seedquelle(3))
    assert erste == zweite
    assert ev.plane_saison(k, saison, Seedquelle(4)) != erste


def test_vor_und_nachsaison_bekommen_ebenfalls_ereignisse(k, saison):
    """Zusammen sind sie rund ein Viertel des Jahres."""
    vor, nach = 0, 0
    for seed in range(10):
        plan = ev.plane_saison(k, saison, Seedquelle(seed))
        vor += sum(1 for datum in plan if datum < saison.erstes_rennen)
        nach += sum(1 for datum in plan if datum > saison.letztes_rennen)
    assert vor > 0
    assert nach > 0


# --- Wirkung --------------------------------------------------------------
def test_zeitweise_faktoren_gelten_nur_solange_das_ereignis_laeuft(k):
    lage = ev.Lage(k)
    lage.loese_aus("E1", TAG)  # Erkaeltung: D2 -15 %, D1 -10 %, 1 Wochenende
    assert lage.faktoren()["D2"] == pytest.approx(0.85)
    assert lage.faktoren()["D1"] == pytest.approx(0.90)

    lage.nach_rennwochenende()
    assert lage.faktoren() == {}
    assert lage.laufende == ()


def test_nur_qualifying_wirkt_nicht_im_rennen(k):
    lage = ev.Lage(k)
    lage.loese_aus("E12", TAG)  # Schlecht geschlafen: D1 -5 %, nur Qualifying
    assert lage.faktoren(ev.QUALIFYING)["D1"] == pytest.approx(0.95)
    assert "D1" not in lage.faktoren(ev.RENNEN)


def test_bis_reparatur_laeuft_bis_zur_reparatur(k):
    lage = ev.Lage(k)
    lage.loese_aus("E8", TAG)  # Motorschaden im Test: F1 -5 %
    for _ in range(10):
        lage.nach_rennwochenende()
        lage.nach_zyklus()
    assert lage.faktoren()["F1"] == pytest.approx(0.95)
    assert [a.schluessel for a in lage.offene_reparaturen] == ["E8"]

    lage.repariere("E8")
    assert lage.faktoren() == {}


def test_nicht_reparierbares_faellt_auf(k):
    lage = ev.Lage(k)
    lage.loese_aus("E1", TAG)
    with pytest.raises(ev.EreignisFehler):
        lage.repariere("E1")


def test_sperren_werden_gemeldet(k):
    lage = ev.Lage(k)
    lage.loese_aus("E6", TAG)  # Teilelieferung: F5 und F6 nicht entwickelbar
    assert lage.gesperrt() == frozenset({"F5", "F6"})
    lage.nach_zyklus()
    assert lage.gesperrt() == frozenset()


def test_zyklen_und_wochenenden_zaehlen_getrennt(k):
    lage = ev.Lage(k)
    lage.loese_aus("E6", TAG)  # 1 Zyklus
    lage.loese_aus("E1", TAG)  # 1 Rennwochenende
    lage.nach_rennwochenende()
    assert [a.schluessel for a in lage.laufende] == ["E6"]


def test_dauerhafte_wirkungen_laufen_nicht_mit(k):
    """E11 aendert D8 dauerhaft - als Faktor darf es nicht auch noch wirken."""
    lage = ev.Lage(k)
    lage.loese_aus("E11", TAG)
    assert lage.faktoren() == {}
    assert lage.laufende == ()


def test_ein_ereignis_kann_dauerhaft_und_zeitweise_zugleich_sein(k):
    """E23 Hitzetraining: Hitzeresistenz dauerhaft, D2 fuer ein Wochenende."""
    lage = ev.Lage(k)
    lage.loese_aus("E23", TAG)
    faktoren = lage.faktoren()
    assert faktoren["D2"] == pytest.approx(0.95)
    assert "hitzeresistenz" not in faktoren


def test_dauerhafter_zuwachs_folgt_dem_zeitmodell(k):
    """Entscheidung zu Punkt 34: max(+10, +1 %), wie ein Tag in GDD 2."""
    schritt = k.wert("ereignisse", "dauerhaft", "mindestschritt")
    assert ev.dauerhafter_zuwachs(k, 0, 0.01) == schritt
    assert ev.dauerhafter_zuwachs(k, 500, 0.01) == schritt
    assert ev.dauerhafter_zuwachs(k, 98_000, 0.01) == 980
    # Andere Prozentsaetze skalieren den Mindestschritt mit.
    assert ev.dauerhafter_zuwachs(k, 0, 0.02) == 2 * schritt
    assert ev.dauerhafter_zuwachs(k, 0, -0.005) == -schritt // 2
    assert ev.dauerhafter_zuwachs(k, 98_000, -0.005) == -490


def test_zweimal_ausloesen_frischt_auf_statt_zu_stapeln(k):
    lage = ev.Lage(k)
    lage.loese_aus("E2", TAG)
    lage.nach_rennwochenende()
    assert lage.laufende[0].rest == 1
    lage.loese_aus("E2", TAG + dt.timedelta(days=20))
    assert len(lage.laufende) == 1
    assert lage.laufende[0].rest == 2


# --- Zusammenspiel mit der Karriere ---------------------------------------
def test_ohne_seedquelle_gibt_es_keine_ereignisse(k):
    c = kk.beginne(k, 2026, liga=20)
    assert c.ereignisplan == {}
    for _ in range(40):
        c.tag_weiter()
    assert c.meldungen == []


def test_eine_saison_loest_ereignisse_aus(k):
    c = kk.beginne(k, 2026, liga=20, seedquelle=Seedquelle(4711))
    geplant = sum(len(v) for v in c.ereignisplan.values())
    assert geplant > 0
    while c.heute < c.saison.tage[-1].datum:
        c.tag_weiter()
        if c.tag.art is kl.Tagesart.RENNEN:
            c.verbuche_rennen(platz=15)
    # Jedes geplante Ereignis muss auch gemeldet worden sein.
    assert len(c.meldungen) == geplant


def test_einmaliges_geld_landet_auf_dem_konto(k):
    c = kk.beginne(k, 2026, liga=20)
    vorher = c.konto.geld
    meldung = c._loese_ereignis_aus("E7")  # Sponsorbonus
    assert meldung.geld > 0
    assert c.konto.geld == vorher + meldung.geld


def test_einmalige_erfahrung_landet_auf_dem_konto(k):
    c = kk.beginne(k, 2026, liga=20)
    meldung = c._loese_ereignis_aus("E9")  # Mentor-Tipp
    assert meldung.erfahrung > 0
    assert c.konto.erfahrung == meldung.erfahrung


def test_dauerhaftes_ereignis_hebt_den_wert_selbst(k):
    c = kk.beginne(k, 2026, liga=20)
    assert c.werte["D8"] == 0
    c._loese_ereignis_aus("E11")  # Fahrsicherheitstraining: D8 +1 % dauerhaft
    assert c.werte["D8"] == k.wert("ereignisse", "dauerhaft", "mindestschritt")


def test_gesperrtes_laesst_sich_nicht_entwickeln(k):
    c = kk.beginne(k, 2026, liga=20)
    c._loese_ereignis_aus("E6")  # F5 und F6 nicht entwickelbar
    assert {"F5", "F6"} <= c.gesperrt()
    with pytest.raises(kk.KarriereFehler, match="gesperrt"):
        c.belege_tag("F5")
    # F1 geht weiterhin.
    c.kaufe("F1")


def test_trainingsverletzung_sperrt_das_ganze_fahrertraining(k):
    """E2 sperrt 'fahrertraining', nicht eine einzelne Faehigkeit."""
    c = kk.beginne(k, 2026, liga=20)
    c._loese_ereignis_aus("E2")
    gesperrt = c.gesperrt()
    assert "D1" in gesperrt and "D2" in gesperrt
    assert "F1" not in gesperrt
    with pytest.raises(kk.KarriereFehler, match="gesperrt"):
        c.belege_tag("D1")


def test_reisechaos_kostet_zwei_nutzbare_tage(k):
    c = kk.beginne(k, 2026, liga=20)
    vorher = c.offene_tage
    c._loese_ereignis_aus("E29")
    assert len(c.verlorene_tage) == 2
    assert c.offene_tage == vorher - 2
    # Der naechste verlorene Tag laesst sich nicht belegen.
    while c.heute not in c.verlorene_tage:
        c.tag_weiter()
    assert not c.heute_nutzbar
    with pytest.raises(kk.KarriereFehler, match="ausgefallen"):
        c.belege_tag("D1")


def test_fahrwerte_tragen_ereignisse_und_defekte(k):
    werte = dict.fromkeys([f.schluessel for f in k.faehigkeiten], 10_000)
    werte.update(dict.fromkeys(k.zusatzfaehigkeiten, 10_000))
    c = kk.beginne(k, 2026, liga=20, werte=werte)

    c._loese_ereignis_aus("E1")  # D2 -15 %, D1 -10 %
    c.uebernimm_defekte(("X1",))  # F1 -2,5 %

    fahrwerte = c.fahrwerte()
    assert fahrwerte["D2"] == 8_500
    assert fahrwerte["D1"] == 9_000
    assert fahrwerte["F1"] == 9_750
    # Der gespeicherte Wert bleibt unberuehrt.
    assert c.werte["D2"] == 10_000


def test_defekte_lassen_sich_reparieren(k):
    c = kk.beginne(k, 2026, liga=20)
    c.uebernimm_defekte(("X13",))
    assert len(c.offene_reparaturen) == 1

    kosten = c.reparaturkosten("X13")
    vorher = c.konto.geld
    assert c.repariere("X13") == kosten
    assert c.konto.geld == vorher - kosten
    assert c.offene_reparaturen == ()


def test_reparatur_ohne_geld_scheitert(k):
    c = kk.beginne(k, 2026, liga=1)  # teure Liga, kleines Startkapital
    c.uebernimm_defekte(("X13",))
    with pytest.raises(kk.KarriereFehler, match="Konto"):
        c.repariere("X13")


def test_ereignis_bis_reparatur_kostet_ebenfalls(k):
    c = kk.beginne(k, 2026, liga=20)
    c._loese_ereignis_aus("E8")  # Motorschaden im Test
    assert [s for s, _, _ in c.offene_reparaturen] == ["E8"]
    c.repariere("E8")
    assert c.offene_reparaturen == ()
    assert "F1" not in c.faktoren()


def test_kopie_teilt_den_zustand_nicht(k):
    c = kk.beginne(k, 2026, liga=20)
    c._loese_ereignis_aus("E1")
    c.uebernimm_defekte(("X1",))

    kopie = kk.kopiere(c)
    kopie.lage.nach_rennwochenende()
    kopie.defekte.clear()
    kopie.verlorene_tage.add(dt.date(2026, 5, 5))

    assert c.lage.laufende
    assert c.defekte
    assert not c.verlorene_tage
