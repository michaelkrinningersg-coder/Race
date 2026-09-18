"""Tests fuer Zeitmodell, Kosten, Einnahmen und Sponsoren (GDD 2, 9, 10)."""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import einnahmen as ei
from rennmanager.kern import entwicklung as ew
from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import karriere as kr
from rennmanager.kern import sponsoren as sp
from rennmanager.kern.entwicklung import EntwicklungsFehler, Konto
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


# -- Zeitmodell -------------------------------------------------------------
def test_ein_tag_bringt_zehn_oder_ein_prozent(k) -> None:
    """GDD 2: Wert steigt um max(+10, +1 % des aktuellen Werts)."""
    assert ew.tageszuwachs(k, 0) == 10
    assert ew.tageszuwachs(k, 999) == 10
    assert ew.tageszuwachs(k, 1_000) == 10
    assert ew.tageszuwachs(k, 5_000) == 50
    assert ew.tageszuwachs(k, 98_000) == 980


def test_zuwachs_ist_immer_ein_vielfaches_des_kaufschritts(k) -> None:
    schritt = k.wert("zeitmodell", "kaufschritt")
    for wert in range(0, 100_001, 733):
        assert ew.tageszuwachs(k, wert) % schritt == 0


def test_waehrung_entscheidet_ueber_den_tag(k) -> None:
    """GDD 2: Nur Geld/EP ist sofort kaufbar, mit Z braucht es einen Tag."""
    assert ew.braucht_tag(k.faehigkeit("D1"))    # Z
    assert ew.braucht_tag(k.faehigkeit("F10"))   # G + Z
    assert not ew.braucht_tag(k.faehigkeit("F1"))   # G
    assert not ew.braucht_tag(k.faehigkeit("D5"))   # E


def test_plaetze_trennen_fahrer_und_werkstatt(k) -> None:
    """GDD 2: ein Platz fuer den Fahrer, einer fuer die Werkstatt."""
    assert ew.ist_fahrertraining(k.faehigkeit("D1"))
    assert not ew.ist_fahrertraining(k.faehigkeit("F1"))


# -- Kosten -----------------------------------------------------------------
def test_kostenfaktoren_mitteln_sich_zu_eins(k) -> None:
    """Sonst waeren alle Faehigkeiten pauschal teurer oder billiger."""
    faktoren = k.k0_faktoren
    assert sum(faktoren.values()) / len(faktoren) == pytest.approx(1.0)


def test_breite_faehigkeiten_kosten_mehr(k) -> None:
    """Entscheidung zu Punkt 17: Faktor aus der Wirkungsbreite."""
    breit = k.faehigkeit("F9")    # wirkt auf ek, k, bplus, bminus, q
    schmal = k.faehigkeit("F16")  # nur ve
    assert ew.k0_faktor(k, breit) > ew.k0_faktor(k, schmal)


def test_schrittkosten_treffen_die_tabelle_aus_gdd_9(k) -> None:
    """K(S) = K0 * (1 + S/1000)^0,6, hier je Faehigkeit skaliert."""
    for schluessel in ("F1", "F6", "F9"):
        faehigkeit = k.faehigkeit(schluessel)
        faktor = ew.k0_faktor(k, faehigkeit)
        for s, soll in ((157, 55), (8_400, 190), (29_170, 390), (98_130, 790)):
            geld, _ = ew.schrittkosten(k, faehigkeit, s)
            assert geld == pytest.approx(soll * faktor, rel=0.02), f"{schluessel} bei {s}"


def test_kostensumme_trifft_die_tabelle(k) -> None:
    faehigkeit = k.faehigkeit("F1")
    faktor = ew.k0_faktor(k, faehigkeit)
    for s, soll in ((157, 820), (8_400, 110_000), (98_130, 4_900_000)):
        geld, _ = ew.kosten_bis(k, faehigkeit, s)
        assert geld == pytest.approx(soll * faktor, rel=0.03)


def test_waehrung_bestimmt_was_bezahlt_wird(k) -> None:
    geld, ep = ew.schrittkosten(k, k.faehigkeit("F1"), 0)  # nur G
    assert geld > 0 and ep == 0
    geld, ep = ew.schrittkosten(k, k.faehigkeit("D5"), 0)  # nur E
    assert geld == 0 and ep > 0
    geld, ep = ew.schrittkosten(k, k.faehigkeit("F3"), 0)  # G + E
    assert geld > 0 and ep > 0


def test_achtzehn_faehigkeiten_kosten_geld(k) -> None:
    """GDD 9: 18 Faehigkeiten haben einen Geldanteil."""
    mit_geld = [
        f for f in k.faehigkeiten if ew.schrittkosten(k, f, 0)[0] > 0
    ]
    assert len(mit_geld) == kf.ANZAHL_MIT_GELDANTEIL


def test_tag_bei_reiner_zeit_kostet_kein_geld_aber_erfahrung(k) -> None:
    """Punkt 69: Wer Zeit einsetzt, gibt auch etwas Erfahrung dazu."""
    plan = ew.plane_tag(k, k.faehigkeit("D1"), 0)
    assert plan.geld == 0
    assert plan.erfahrung > 0
    assert plan.zuwachs == 10


def test_tag_bei_zeit_und_geld_kostet_je_schritt(k) -> None:
    """GDD 2: Der Tag schaltet den Zuwachs frei, Geld wird zusaetzlich fuer
    jeden +10-Schritt bezahlt."""
    faehigkeit = k.faehigkeit("F10")
    plan = ew.plane_tag(k, faehigkeit, 5_000)
    schritte = plan.zuwachs // k.wert("zeitmodell", "kaufschritt")
    assert schritte == 5
    erwartet = sum(
        ew.schrittkosten(k, faehigkeit, 5_000 + n * 10)[0] for n in range(schritte)
    )
    assert plan.geld == erwartet


def test_sofortkauf_nur_ohne_zeitanteil(k) -> None:
    with pytest.raises(EntwicklungsFehler, match="braucht einen Tag"):
        ew.plane_kauf(k, k.faehigkeit("D1"), 0)
    with pytest.raises(EntwicklungsFehler, match="sofort kaufbar"):
        ew.plane_tag(k, k.faehigkeit("F1"), 0)


def test_am_maximum_geht_nichts_mehr(k) -> None:
    with pytest.raises(EntwicklungsFehler, match="Maximum"):
        ew.plane_kauf(k, k.faehigkeit("F1"), k.wert("skala", "maximum"))


# -- Konto ------------------------------------------------------------------
def test_konto_kennt_keine_schulden(k) -> None:
    """GDD 10: keine Schulden, kein Bankrott - ohne Geld geht nichts."""
    konto = Konto(geld=10)
    plan = ew.plane_kauf(k, k.faehigkeit("F1"), 0)
    assert not ew.ist_bezahlbar(konto, plan)
    with pytest.raises(EntwicklungsFehler, match="nicht gedeckt"):
        ew.buche(konto, plan)


def test_wettertopf_zahlt_getrennt(k) -> None:
    """GDD 10: eigener Topf je Wetter, nur fuer die passende Faehigkeit."""
    plan = ew.als_wettertopf(ew.plane_kauf(k, k.faehigkeit("D5"), 0), "regen")
    ohne = Konto(erfahrung=10_000)
    assert not ew.ist_bezahlbar(ohne, plan)
    mit = Konto(wetter_erfahrung={"regen": 10_000})
    assert ew.ist_bezahlbar(mit, plan)
    assert ew.buche(mit, plan).wetter_topf("regen") < 10_000


# -- Einnahmen --------------------------------------------------------------
def test_siegpraemien_treffen_die_stuetzstellen(k) -> None:
    for liga, betrag in k.wert("preisgeld", "siegpraemie_euro").items():
        assert ei.siegpraemie(k, int(liga)) == betrag


def test_siegpraemie_waechst_mit_der_liga(k) -> None:
    werte = [ei.siegpraemie(k, liga) for liga in range(20, 0, -1)]
    assert werte == sorted(werte)


def test_logarithmische_interpolation_haelt_das_verhaeltnis(k) -> None:
    """Entscheidung zu Punkt 12: gleichmaessiger Faktor je Liga."""
    verhaeltnisse = [
        ei.siegpraemie(k, liga - 1) / ei.siegpraemie(k, liga) for liga in range(20, 15, -1)
    ]
    assert max(verhaeltnisse) - min(verhaeltnisse) < 0.02


def test_anteile_treffen_die_vorgaben(k) -> None:
    """GDD 10: P1 100 %, P2 80 %, P3 65 %, P30 5 %."""
    assert ei.anteil(k, 1) == pytest.approx(1.00)
    assert ei.anteil(k, 2) == pytest.approx(0.80)
    assert ei.anteil(k, 3) == pytest.approx(0.65)
    assert ei.anteil(k, 30) == pytest.approx(0.05)


def test_anteile_fallen_monoton(k) -> None:
    werte = [ei.anteil(k, platz) for platz in range(1, 31)]
    assert werte == sorted(werte, reverse=True)


def test_platz_ausserhalb_meldet_fehler(k) -> None:
    with pytest.raises(ei.EinnahmenFehler, match="Platz"):
        ei.anteil(k, 31)


def test_erfahrung_folgt_dem_preisgeld(k) -> None:
    """GDD 10: EP-Betraege = Preisgeld durch 10."""
    teiler = k.wert("erfahrung", "teiler_gegenueber_preisgeld")
    assert ei.sieg_erfahrung(k, 10) == pytest.approx(
        ei.siegpraemie(k, 10) / teiler, rel=0.001
    )


def test_erfahrung_belohnt_platz_und_ueberholen(k) -> None:
    ohne = ei.erfahrung_fuer(k, 20, platz=20, ueberholmanoever=0)
    mit_manoever = ei.erfahrung_fuer(k, 20, platz=20, ueberholmanoever=10)
    besser = ei.erfahrung_fuer(k, 20, platz=1, ueberholmanoever=0)
    assert mit_manoever > ohne
    assert besser > ohne
    # Auch der Letzte bekommt etwas - sonst kaeme ein Anfaenger nie in Gang.
    assert ohne > 0


def test_startgeld_ist_ein_sockel(k) -> None:
    """Entscheidung zu Punkt 14: 5 % der Siegpraemie fuer jeden Teilnehmer.

    Das ist genau so viel wie der Anteil fuer Platz 30, der laut GDD 10
    ebenfalls 5 % betraegt - der Letzte bekommt damit das Doppelte des
    Sockels, der Sieger 105 % statt 100 %.
    """
    for liga in (20, 10, 1):
        assert ei.startgeld(k, liga) == ei.preisgeld(k, liga, 30)
        assert ei.startgeld(k, liga) < ei.preisgeld(k, liga, 1) / 10


def test_startkapital(k) -> None:
    assert ei.startkapital(k) == 1_000


# -- Sponsoren --------------------------------------------------------------
def test_sechs_plaetze_mit_drei_bis_zehn_angeboten(k) -> None:
    """GDD 10: Sechs Plaetze, je 3 bis 10 Angebote."""
    for seed in range(12):
        angebote = sp.wuerfle_angebote(k, 10, 1, Seedquelle(seed))
        assert set(angebote) == set(sp.plaetze(k))
        assert len(angebote) == 6
        for liste in angebote.values():
            assert (
                k.wert("sponsoren", "angebote_je_platz_min")
                <= len(liste)
                <= k.wert("sponsoren", "angebote_je_platz_max")
            )


def test_laufzeit_und_gueltigkeit_im_band(k) -> None:
    """GDD 10: Laufzeit 3 bis 25 Rennen, Angebot 3 bis 10 Wochen gueltig."""
    angebote = sp.wuerfle_angebote(k, 10, 5, Seedquelle(1))
    for liste in angebote.values():
        for angebot in liste:
            assert (
                k.wert("sponsoren", "laufzeit_rennen_min")
                <= angebot.laufzeit_rennen
                <= k.wert("sponsoren", "laufzeit_rennen_max")
            )
            assert (
                5 + k.wert("sponsoren", "angebot_gueltig_wochen_min")
                <= angebot.gueltig_bis_woche
                <= 5 + k.wert("sponsoren", "angebot_gueltig_wochen_max")
            )


def test_angebote_skalieren_mit_der_liga(k) -> None:
    """GDD 10: hoehere Ligen bringen bessere Sponsoren."""
    unten = sp.wuerfle_angebote(k, 20, 1, Seedquelle(3))
    oben = sp.wuerfle_angebote(k, 1, 1, Seedquelle(3))
    assert max(a.grundbetrag for a in oben["auto_haupt"]) > max(
        a.grundbetrag for a in unten["auto_haupt"]
    ) * 100


def test_hauptsponsor_zahlt_am_meisten(k) -> None:
    for liga in (20, 10, 1):
        haupt = sp.grundbetrag_je_platz(k, liga, "auto_haupt")
        for platz in ("anzug", "helm", "muetze", "auto_neben_1"):
            assert haupt > sp.grundbetrag_je_platz(k, liga, platz)


def test_praemien_steigen_mit_der_platzierung(k) -> None:
    angebot = sp.wuerfle_angebote(k, 10, 1, Seedquelle(1))["auto_haupt"][0]
    assert angebot.verguetung(1) > angebot.verguetung(3) > angebot.verguetung(10)
    assert angebot.verguetung(10) > angebot.verguetung(11)
    assert angebot.verguetung(11) == angebot.grundbetrag


def test_vertraege_laufen_ab(k) -> None:
    angebot = sp.wuerfle_angebote(k, 10, 1, Seedquelle(1))["helm"][0]
    vertraege = {"helm": sp.unterschreibe(angebot)}
    assert vertraege["helm"].verbleibende_rennen == angebot.laufzeit_rennen
    for _ in range(angebot.laufzeit_rennen):
        assert sp.auszahlung(vertraege, 5) > 0
        vertraege = sp.nach_rennen(vertraege)
    assert vertraege == {}
    assert sp.auszahlung(vertraege, 5) == 0


def test_unbekannter_platz_meldet_fehler(k) -> None:
    with pytest.raises(sp.SponsorenFehler, match="Sponsorenplatz"):
        sp.grundbetrag_je_platz(k, 10, "kofferraum")


# -- Karriere ---------------------------------------------------------------
def test_karriere_startet_am_ersten_januar(k) -> None:
    c = kr.beginne(k, 2026, liga=20)
    assert c.heute.month == 1 and c.heute.day == 1
    assert c.konto.geld == ei.startkapital(k)
    assert set(c.werte.values()) == {0}


def test_tag_belegen_hebt_den_wert(k) -> None:
    c = kr.beginne(k, 2026, liga=20)
    # Ein belegter Tag kostet seit Punkt 69 auch etwas Erfahrung.
    c.konto = c.konto.mit(erfahrung=1_000)
    c.belege_tag("D1")
    assert c.wert("D1") == 10
    # Derselbe Platz geht heute nicht noch einmal.
    with pytest.raises(kr.KarriereFehler, match="belegt"):
        c.belege_tag("D2")
    # Der Werkstattplatz ist aber frei.
    c.belege_tag("F10")
    assert c.wert("F10") == 10


def test_an_rennwochenenden_laesst_sich_nichts_belegen(k) -> None:
    c = kr.beginne(k, 2026, liga=20)
    c.bis_zum_rennen()
    with pytest.raises(kr.KarriereFehler, match="nicht nutzbar"):
        c.belege_tag("D1")


def test_sprung_zum_rennen(k) -> None:
    c = kr.beginne(k, 2026, liga=20)
    tage = c.bis_zum_rennen()
    assert c.heute == c.saison.erstes_rennen
    assert tage == (c.saison.erstes_rennen - c.saison.tage[0].datum).days


def test_rennen_bringt_geld_und_erfahrung(k) -> None:
    c = kr.beginne(k, 2026, liga=20)
    vorher = c.konto.geld
    c.verbuche_rennen(platz=5, ueberholmanoever=3, kilometer_je_wetter={"regen": 100.0})
    assert c.konto.geld > vorher
    assert c.konto.erfahrung > 0
    assert c.konto.wetter_topf("regen") > 0


def test_sponsorengeld_kommt_dazu(k) -> None:
    ohne = kr.beginne(k, 2026, liga=10)
    ohne.verbuche_rennen(platz=1)

    mit = kr.beginne(k, 2026, liga=10)
    angebot = sp.wuerfle_angebote(k, 10, 1, Seedquelle(1))["auto_haupt"][0]
    mit.unterschreibe(angebot)
    mit.verbuche_rennen(platz=1)
    assert mit.konto.geld > ohne.konto.geld


def test_wetterfaehigkeiten_zahlen_aus_ihrem_topf(k) -> None:
    c = kr.beginne(k, 2026, liga=20)
    vorschau = c.vorschau("regenfahren")
    assert vorschau.wettertopf == "regen"
    assert vorschau.erfahrung > 0


# -- Zeit kostet auch Erfahrung (Punkt 69) ---------------------------------
def test_wer_zeit_einsetzt_zahlt_auch_erfahrung(k) -> None:
    """Jede Faehigkeit, die einen Tag kostet, kostet auch etwas EP."""
    zeit = [f for f in k.faehigkeiten if ew.ZEIT in f.waehrung]
    assert zeit, "Es muss Faehigkeiten geben, die Zeit kosten"
    for faehigkeit in zeit:
        _, erfahrung = ew.schrittkosten(k, faehigkeit, 0)
        assert erfahrung > 0, faehigkeit.schluessel


def test_die_erfahrung_waechst_mit_jedem_kauf(k) -> None:
    """Die Zeit bleibt ein Tag, die Erfahrung steigt ueber die Kurve."""
    faehigkeit = next(
        f for f in k.faehigkeiten
        if ew.ZEIT in f.waehrung and ew.ERFAHRUNG not in f.waehrung
    )
    werte = [ew.schrittkosten(k, faehigkeit, wert)[1] for wert in (0, 20_000, 90_000)]
    assert werte == sorted(werte)
    assert werte[0] < werte[-1]
    # Ein Tag bleibt ein Tag - die Zeit skaliert nicht mit.
    assert ew.braucht_tag(faehigkeit)


def test_wer_schon_erfahrung_zahlt_zahlt_nicht_doppelt(k) -> None:
    """('E','Z') behaelt den vollen EP-Satz, nicht Satz plus Zuschlag."""
    beide = next(
        f for f in k.faehigkeiten
        if ew.ZEIT in f.waehrung and ew.ERFAHRUNG in f.waehrung
    )
    einstellung = k.wert("kosten")
    faktor = ew.k0_faktor(k, beide)
    erwartet = round(einstellung["k0_erfahrung"] * faktor)
    assert ew.schrittkosten(k, beide, 0)[1] == erwartet


# -- Ein Rennwochenende zaehlt einmal (Punkt 70) ---------------------------
def test_ereignisse_zaehlen_je_rennen_nicht_je_fahrer(k) -> None:
    """Vier eigene Autos im selben Rennen sind ein Rennwochenende.

    Die Lage gehoert dem Team. Wurde sie bei jedem Auto weitergezaehlt,
    lief jedes Ereignis viermal so schnell ab.
    """
    c = kr.beginne(k, 2026, liga=20, fahrer=(1, 2, 3, 4))
    schluessel = next(
        eintrag["schluessel"]
        for eintrag in kern_ereignis.liste(k)
        if kern_ereignis.dauer_von(eintrag) is kern_ereignis.Dauer.RENNWOCHENENDEN
        and eintrag["dauer"]["anzahl"] > 1
    )
    c.lage.loese_aus(schluessel, c.heute)
    offen = c.lage.laufende[0].rest

    for stelle, fahrer in enumerate((1, 2, 3, 4)):
        c.verbuche_rennen(platz=5, fahrer=fahrer, zaehle_rennwochenende=stelle == 0)

    assert c.lage.laufende[0].rest == offen - 1


def test_ein_sponsorenvertrag_laeuft_seine_rennen(k) -> None:
    """Punkt 70: Ein Vertrag ueber N Rennen zahlt genau N-mal."""
    c = kr.beginne(k, 2026, liga=20)
    angebot = next(
        iter(sp.wuerfle_angebote(k, 20, 0, Seedquelle(3)).values())
    )[0]
    c.unterschreibe(angebot)
    gezahlt = 0
    for _ in range(angebot.laufzeit_rennen + 5):
        if sp.auszahlung(c.vertraege, 5) > 0:
            gezahlt += 1
        c.verbuche_rennen(platz=5)
    assert gezahlt == angebot.laufzeit_rennen
