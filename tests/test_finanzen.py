"""Tests fuer Kassenbuch, Monatsbudget und Finanzseite (Punkt 72).

Das Kassenbuch rechnet nichts aus, was die Karriere nicht ohnehin bucht -
getestet wird deshalb vor allem, dass es **vollstaendig** ist: Der Saldo
aller Buchungen muss den Kontostand ergeben. Faellt eine Buchung aus,
faellt der Test.
"""

from __future__ import annotations

import datetime as dt

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import karriere as kr
from rennmanager.kern import kassenbuch as kb


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


# -- Das Buch selbst --------------------------------------------------------
def test_eine_nullbuchung_wird_nicht_geschrieben() -> None:
    """Sonst fuellt sich das Buch mit Zeilen, die nichts aussagen."""
    buch = kb.Kassenbuch()
    assert buch.buche(dt.date(2026, 1, 1), 0, kb.RENNEN, kb.PREISGELD) is None
    assert len(buch) == 0


def test_das_vorzeichen_trennt_einnahme_und_ausgabe() -> None:
    buch = kb.Kassenbuch()
    buch.buche(dt.date(2026, 1, 1), 1_000, kb.RENNEN, kb.PREISGELD)
    buch.buche(dt.date(2026, 1, 2), -400, kb.WERKSTATT, kb.REPARATUR)
    assert buch.einnahmen() == 1_000
    assert buch.ausgaben() == 400
    assert buch.saldo() == 600


def test_der_zeitraum_grenzt_beidseitig_ein() -> None:
    buch = kb.Kassenbuch()
    for tag in (1, 5, 9):
        buch.buche(dt.date(2026, 1, tag), 100, kb.RENNEN, kb.PREISGELD)
    assert len(buch.im_zeitraum(dt.date(2026, 1, 5), dt.date(2026, 1, 9))) == 2
    assert len(buch.im_zeitraum(bis=dt.date(2026, 1, 5))) == 2
    assert len(buch.im_zeitraum(von=dt.date(2026, 1, 5))) == 2


def test_die_hauptkategorien_stehen_in_fester_reihenfolge() -> None:
    """Die Anzeige soll nicht je nach Buchungsreihenfolge umspringen."""
    buch = kb.Kassenbuch()
    buch.buche(dt.date(2026, 1, 1), -100, kb.PERSONAL, kb.GEHALT)
    buch.buche(dt.date(2026, 1, 1), 100, kb.RENNEN, kb.PREISGELD)
    assert list(buch.nach_kategorien()) == [kb.RENNEN, kb.PERSONAL]


def test_unbekannte_kategorien_verschwinden_nicht() -> None:
    buch = kb.Kassenbuch()
    buch.buche(dt.date(2026, 1, 1), 100, "Sonstiges", "Fundsache")
    assert "Sonstiges" in buch.nach_kategorien()


# -- Das Monatsbudget (Punkt 72) -------------------------------------------
def test_die_monatsrate_ist_ein_zwoelftel(k) -> None:
    assert kb.monatsrate(k, 12_000_000) == 1_000_000
    assert kb.monatsrate(k, 0) == 0


def test_jeder_monat_bringt_genau_eine_rate(k) -> None:
    """Auch wer viele Tage am Stueck weiterschaltet, bekommt keine doppelt."""
    c = kr.beginne(k, 2026, liga=10, teambudget=12_000_000)
    for _ in range(90):  # 1. Januar bis Ende Maerz
        c.tag_weiter()
    raten = [
        b for b in c.kassenbuch.buchungen if b.unterkategorie == kb.MONATSBUDGET
    ]
    assert {b.datum.month for b in raten} == {1, 2, 3, 4}
    assert len(raten) == 4


def test_ein_sprung_zum_rennen_verschluckt_keine_rate(k) -> None:
    """``bis_zum_rennen`` ueberspringt Wochen - die Raten muessen kommen."""
    c = kr.beginne(k, 2026, liga=10, teambudget=12_000_000)
    c.bis_zum_rennen()
    raten = [
        b for b in c.kassenbuch.buchungen if b.unterkategorie == kb.MONATSBUDGET
    ]
    assert len(raten) >= 2


def test_ohne_budget_gibt_es_keine_raten(k) -> None:
    c = kr.beginne(k, 2026, liga=10)
    for _ in range(60):
        c.tag_weiter()
    assert not [
        b for b in c.kassenbuch.buchungen if b.unterkategorie == kb.MONATSBUDGET
    ]


# -- Vollstaendigkeit -------------------------------------------------------
def test_der_saldo_des_buchs_ist_der_kontostand(k) -> None:
    """Der Kern des Ganzen: keine Geldbewegung ohne Buchung.

    Gefahren wird ein Stueck Karriere mit allem, was Geld bewegt -
    Startkapital, Monatsraten, ein belegter Tag, ein Sofortkauf, ein
    Rennen mit Preis- und Startgeld.
    """
    c = kr.beginne(k, 2026, liga=10, teambudget=12_000_000)
    c.konto = c.konto.mit(erfahrung=500_000)
    c.belege_tag("F10")
    # Eine Faehigkeit, die sich sofort kaufen laesst - also ohne Zeit.
    sofort = next(f for f in k.faehigkeiten if "Z" not in f.waehrung)
    c.kaufe(sofort.schluessel)
    for _ in range(45):
        c.tag_weiter()
    c.verbuche_rennen(platz=3)
    assert c.kassenbuch.saldo() == c.konto.geld


def test_ein_kauf_steht_unter_entwicklung(k) -> None:
    c = kr.beginne(k, 2026, liga=10)
    c.konto = c.konto.mit(geld=5_000_000, erfahrung=500_000)
    c.belege_tag("F10")
    unter = {
        b.unterkategorie
        for b in c.kassenbuch.buchungen
        if b.hauptkategorie == kb.ENTWICKLUNG
    }
    assert unter == {kb.FAHRZEUG}


def test_ein_rennen_trennt_preisgeld_startgeld_und_sponsoren(k) -> None:
    c = kr.beginne(k, 2026, liga=10)
    c.verbuche_rennen(platz=1)
    kategorien = {
        (b.hauptkategorie, b.unterkategorie) for b in c.kassenbuch.buchungen
    }
    assert (kb.RENNEN, kb.PREISGELD) in kategorien
    assert (kb.RENNEN, kb.STARTGELD) in kategorien


# -- Die Oberflaeche --------------------------------------------------------
pytest.importorskip("PySide6")


def _seite(qtbot, karriere, konfiguration):
    from rennmanager.ui.finanzseite import Finanzseite

    seite = Finanzseite(konfiguration, karriere)
    qtbot.addWidget(seite)
    return seite


def test_die_seite_zeigt_die_hauptkategorien(qtbot, k) -> None:
    c = kr.beginne(k, 2026, liga=10, teambudget=12_000_000)
    c.verbuche_rennen(platz=1)
    seite = _seite(qtbot, c, k)
    assert kb.TEAM in seite.hauptkategorien()
    assert kb.RENNEN in seite.hauptkategorien()


def test_ohne_karriere_stuerzt_die_seite_nicht_ab(qtbot, k) -> None:
    seite = _seite(qtbot, None, k)
    assert seite.hauptkategorien() == ()


def test_der_zeitraum_laesst_sich_auf_eine_saison_einengen(qtbot, k) -> None:
    c = kr.beginne(k, 2026, liga=10, teambudget=12_000_000)
    for _ in range(40):
        c.tag_weiter()
    seite = _seite(qtbot, c, k)
    # "Ganze Karriere" plus die Saison, in der gebucht wurde.
    assert seite.zeitraum.count() == 2
    seite.zeitraum.setCurrentIndex(1)
    assert seite.hauptkategorien()


def test_jede_unterkategorie_traegt_ihre_einzelbuchungen(qtbot, k) -> None:
    c = kr.beginne(k, 2026, liga=10, teambudget=12_000_000)
    for _ in range(40):
        c.tag_weiter()
    seite = _seite(qtbot, c, k)
    baum = seite.baum
    ast = baum.topLevelItem(0)
    assert ast.childCount() >= 1
    assert ast.child(0).childCount() >= 1
