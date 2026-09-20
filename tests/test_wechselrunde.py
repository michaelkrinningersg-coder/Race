"""Auf- und Abstieg mitten in der Saison (Punkt 95).

Bis dahin wurde nur am Saisonende gewechselt. Jetzt geht es alle fuenf
Rennen: Die besten drei einer Liga steigen auf, die letzten drei ab,
entschieden nach der Gesamttabelle seit Saisonbeginn. Die gesammelten
Punkte wandern mit - die Meisterschaft laeuft ueber alle Ligen.

Gefahren wird auf der kleinen Welt aus ``conftest`` (Punkt 77); der Takt
schrumpft dort im selben Verhaeltnis mit, es wird also nach jedem Rennen
gewechselt.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import saison as sa
from rennmanager.kern import strecke as st
from rennmanager.kern import welt as kw
from rennmanager.kern.zufall import Seedquelle

SEED = 12


@pytest.fixture(scope="module")
def k(kleine_konfiguration) -> kf.Konfiguration:
    return kleine_konfiguration


@pytest.fixture(scope="module")
def strecken(k) -> tuple[st.Strecke, ...]:
    return st.lade_alle(k)


@pytest.fixture(scope="module")
def welt(kleine_welt) -> kw.Welt:
    return kleine_welt


# --- Auf- und Abstieg mitten in der Saison (Punkt 95) ----------------------
def test_alle_fuenf_rennen_wird_gewechselt(k, welt, strecken) -> None:
    """Punkt 95: nicht erst am Saisonende, sondern im gesetzten Takt."""
    takt = k.wert("auf_abstieg", "alle_rennen")
    lauf = sa.Saisonlauf(k, welt, Seedquelle(SEED), jahr=2026, strecken=strecken)
    gewechselt = []
    for _ in range(k.wert("kalender", "rennen_je_saison")):
        wochenende = lauf.fahre_rennen()
        if wochenende.ist_wechselrunde:
            gewechselt.append(wochenende.nummer)
    assert gewechselt == [n for n in range(1, lauf.rennen_je_saison + 1) if n % takt == 0]


def test_der_aufsteiger_nimmt_seine_punkte_mit(k, welt, strecken) -> None:
    """Punkt 95: Die Meisterschaft laeuft ueber alle Ligen - ein Aufstieg
    loescht nichts, er hebt nur die Sprosse fuer die naechsten Rennen."""
    lauf = sa.Saisonlauf(k, welt, Seedquelle(SEED), jahr=2026, strecken=strecken)
    wochenende = lauf.fahre_rennen()
    assert wochenende.wechsel, "Der Test braucht eine Wechselrunde"

    aufsteiger = next(w for w in wochenende.wechsel if w.ist_aufstieg)
    # Aus der alten Liga heraus, in der neuen drin - mit demselben Stand.
    assert aufsteiger.fahrer not in lauf.tabelle(aufsteiger.von_liga).eintraege
    eintrag = lauf.tabelle(aufsteiger.nach_liga).eintraege[aufsteiger.fahrer]
    assert eintrag.punkte > 0
    assert eintrag.rennen == 1
    # Und die Welt weiss es auch, sonst faehre das naechste Rennen mit
    # einer Aufstellung, die zur Tabelle nicht mehr passt.
    assert lauf.welt.fahrer[aufsteiger.fahrer].liga == aufsteiger.nach_liga


def test_die_ligen_bleiben_nach_dem_wechsel_voll(k, welt, strecken) -> None:
    lauf = sa.Saisonlauf(k, welt, Seedquelle(SEED), jahr=2026, strecken=strecken)
    lauf.fahre_rennen()
    je_liga = k.wert("ligen", "autos_je_liga")
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        assert len(lauf.tabelle(liga).eintraege) == je_liga
        assert len(lauf.welt.liga(liga)) == je_liga
