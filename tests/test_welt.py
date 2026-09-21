"""Tests fuer die Welt: 50 Autos, 25 Teams, ein Feld (GDD 12, Punkt 101)."""

from __future__ import annotations

import datetime as dt
import statistics

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import auto as kern_auto
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import welt as w
from rennmanager.kern.auto import bereichswert, gesamtwert, pruefe
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


SEED = 4711


@pytest.fixture(scope="module")
def welt(k) -> w.Welt:
    return w.erzeuge(k, Seedquelle(SEED))


# -- Umfang -----------------------------------------------------------------
def test_fuenfzig_autos_in_einem_feld(welt, k) -> None:
    """Punkt 101: 25 Teams x 2 Autos = 50 Autos, eine Liga."""
    assert len(welt.fahrer) == k.wert("rennen", "autos")
    assert len(welt.feld) == len(welt.fahrer)


def test_jedes_team_hat_zwei_autos(welt, k) -> None:
    assert len(welt.teams) == k.wert("teams", "anzahl")
    for team in welt.teams:
        assert len(team.fahrer) == k.wert("teams", "autos_je_team")
    # Jeder Fahrer gehoert genau einem Team.
    zugeordnet = [nummer for team in welt.teams for nummer in team.fahrer]
    assert sorted(zugeordnet) == list(range(len(welt.fahrer)))


def test_jeder_hersteller_faehrt_genau_ein_team(welt, k) -> None:
    """Punkt 101: 25 Hersteller, 25 Teams, eins zu eins."""
    marken = [team.hersteller for team in welt.teams]
    assert len(set(marken)) == len(marken) == k.wert("hersteller", "anzahl")


# -- Staerke ----------------------------------------------------------------
def test_die_leiter_spannt_die_feldgrenzen_auf(k) -> None:
    """Die Staerken liegen gleichmaessig zwischen beiden Grenzen."""
    bester, letzter = w.feldgrenzen(k)
    leiter = w.feldstaerken(k)
    assert len(leiter) == k.wert("rennen", "autos")
    assert leiter[0] == bester
    assert leiter[-1] == letzter
    assert leiter == sorted(leiter, reverse=True)
    schritte = {leiter[i] - leiter[i + 1] for i in range(len(leiter) - 1)}
    # Gleichmaessig heisst: alle Schritte gleich, bis auf die Rundung.
    assert max(schritte) - min(schritte) <= 1


def test_ein_auto_bekommt_die_staerke_des_besten(k) -> None:
    assert w.feldstaerken(k, 1) == [w.feldgrenzen(k)[0]]


def test_das_feld_liegt_vier_prozent_auseinander(k) -> None:
    """Punkt 101: Der Letzte braucht 4 % laenger als der Beste.

    Gemessen auf der Referenzstrecke, ohne Zufall und ohne Profil - das
    ist die Groesse, die die Konfiguration verspricht.
    """
    strecken = kern_strecke.lade_alle(k)
    zandvoort = next(
        s for s in strecken if s.name == k.wert("kalibrierung", "referenzstrecke")
    )
    bester, letzter = w.feldgrenzen(k)

    def runde(s: int) -> int:
        return kern_tempo.fahre_runde(
            k, zandvoort, kern_auto.gleichverteilt(k, s)
        ).zeit_ms

    spanne = runde(letzter) / runde(bester) - 1.0
    assert spanne == pytest.approx(k.wert("feld", "spanne_rundenzeit"), abs=0.0005)


def test_die_teams_stehen_als_ganzes_auf_der_leiter(welt, k) -> None:
    """Punkt 101: Die beiden Autos eines Teams sind Nachbarn."""
    reihenfolge = [f.nummer for f in welt.feld]
    je_team = k.wert("teams", "autos_je_team")
    for team in welt.teams:
        plaetze = sorted(reihenfolge.index(nummer) for nummer in team.fahrer)
        assert plaetze[-1] - plaetze[0] == je_team - 1


def test_das_feld_ist_nach_staerke_geordnet(welt) -> None:
    werte = [sum(f.auto.werte.values()) for f in welt.feld]
    assert werte == sorted(werte, reverse=True)


def test_jeder_traegt_eine_staerke_aus_der_leiter(welt, k) -> None:
    """Die Werte sind fest: Jeder Fahrer steht auf einer Sprosse.

    Das Profil verteilt die Staerke um, es schenkt keine dazu - der
    Mittelwert eines Autos ist genau seine Sprosse.
    """
    leiter = set(w.feldstaerken(k))
    for fahrer in welt.fahrer:
        assert round(gesamtwert(k, fahrer.auto)) in leiter


def test_profile_streuen_um_den_mittelwert(welt, k) -> None:
    """Zwei Ebenen: Bereichsprofil (Punkt 37) und Rauschen (GDD 12)."""
    rauschen = k.wert("ki", "profil_streuung")
    bereich = k.wert("ki", "bereichs_streuung")
    untere = (1 - bereich) * (1 - rauschen)
    obere = (1 + bereich) * (1 + rauschen)
    # Der Ausgleich an der Skalendecke (``auf_skala``) hebt die freien
    # Werte an, wenn hohe gekappt werden; ein kleiner Zuschlag deckt das.
    zuschlag_oben, zuschlag_unten = 1.05, 0.95
    for fahrer in welt.fahrer:
        werte = list(fahrer.auto.werte.values())
        mittel = statistics.mean(werte)
        assert min(werte) >= mittel * untere * zuschlag_unten
        assert max(werte) <= mittel * obere * zuschlag_oben
    # Und die Spezialisierung unterscheidet sich wirklich je Fahrer.
    regen = [
        f.auto.wetterwert("regenfahren") / max(f.auto.wert("D1"), 1)
        for f in welt.fahrer
    ]
    assert max(regen) - min(regen) > 0.2


def test_das_bereichsprofil_macht_spezialisten(welt, k) -> None:
    """Entscheidung zu Punkt 37: Ohne die zweite Ebene mittelt sich die
    Streuung im Bereichsmittel weg."""
    from rennmanager.kern.auto import bereichswerte

    spannen = []
    for fahrer in welt.fahrer:
        bereiche = list(bereichswerte(k, fahrer.auto).values())
        spannen.append((max(bereiche) - min(bereiche)) / statistics.mean(bereiche))
    assert statistics.mean(spannen) > 0.03


def test_das_bereichsprofil_aendert_die_staerke_nicht(k) -> None:
    """Ein Spezialist verteilt seine Staerke um, statt mehr davon zu haben.

    Das Kappen an der Skala aus GDD 9 wird ausgeglichen: Das Feld liegt
    nahe am Maximum, und ohne Ausgleich fielen dort die hohen Werte weg -
    der Fahrer waere langsamer, weil er ein Profil hat.
    """
    import numpy as np

    wuerfel = np.random.default_rng(7)
    zusatz = list(k.zusatzfaehigkeiten)
    for staerke in w.feldstaerken(k)[:5]:
        werte, _ = w.wuerfle_werte(k, staerke, wuerfel, zusatz)
        assert statistics.mean(werte.values()) == pytest.approx(staerke, abs=1)


def test_alle_autos_sind_gueltig(welt, k) -> None:
    for fahrer in welt.fahrer:
        pruefe(k, fahrer.auto)


def test_alle_eigenschaften_neben_der_matrix_sind_gesetzt(welt, k) -> None:
    """Die Wetterfaehigkeiten, der Reifenfluesterer und die fuenf aus Punkt 48."""
    erwartet = set(k.zusatzfaehigkeiten)
    assert {e["schluessel"] for e in k.wert("wetter", "faehigkeit", "liste")} <= erwartet
    assert "reifenfluesterer" in erwartet
    for fahrer in welt.fahrer:
        assert set(fahrer.auto.wetterwerte) == erwartet


# -- Fahrer -----------------------------------------------------------------
def test_namen_sind_eindeutig(welt) -> None:
    namen = [f.name for f in welt.fahrer]
    assert len(set(namen)) == len(namen)


def test_kuerzel_sind_eindeutig(welt) -> None:
    """Im Rennen stehen sie neben den Punkten (GDD 4)."""
    kuerzel = [f.kuerzel for f in welt.fahrer]
    assert len(set(kuerzel)) == len(kuerzel)
    assert all(len(k) == 3 for k in kuerzel)


def test_fahrer_kommen_aus_europa_und_nordamerika(welt, k) -> None:
    """GDD 12: Herkunft aus Europa und Nordamerika."""
    namen = w.lade_namen(k)
    erlaubt = set(namen["fahrer"]["laender"]["europa"]) | set(
        namen["fahrer"]["laender"]["nordamerika"]
    )
    laender = {f.land for f in welt.fahrer}
    assert laender <= erlaubt
    # Beide Regionen kommen vor.
    assert laender & set(namen["fahrer"]["laender"]["nordamerika"])
    assert laender & set(namen["fahrer"]["laender"]["europa"])


def test_geburtsdatum_ergibt_ein_uebliches_alter(welt, k) -> None:
    """Das Alter gilt zum Saisonstart und haelt die Spanne ein.

    Vom 1. Januar aus gerechnet war jeder, der spaeter im Jahr Geburtstag
    hat, am Saisonstart noch ein Jahr juenger als gewuerfelt.
    """
    stichtag = dt.date(
        2026,
        k.wert("kalender", "saisonstart_monat"),
        k.wert("kalender", "saisonstart_tag"),
    )
    alter = [f.alter_am(stichtag) for f in welt.fahrer]
    assert min(alter) >= k.wert("fahrernamen", "alter_min")
    assert max(alter) <= k.wert("fahrernamen", "alter_max")


# -- Spieler ----------------------------------------------------------------
def test_dem_spieler_gehoert_ein_ganzes_team(welt, k) -> None:
    """Beide Autos eines Teams gehoeren dem Chef - keine KI dazwischen."""
    eigene = welt.spielerfahrer
    assert len(eigene) == k.wert("teams", "autos_je_team")
    assert len({f.team for f in eigene}) == 1
    kollegen = welt.teamkollegen(eigene[0])
    assert len(kollegen) == k.wert("teams", "autos_je_team") - 1
    assert all(f.ist_spieler for f in kollegen)
    assert welt.spielerteam is welt.teams[eigene[0].team]


def test_der_spieler_faehrt_dieselbe_leiter_wie_alle(welt, k) -> None:
    """Punkt 101: Kein eigener Startwert mehr - er steht im Feld."""
    leiter = set(w.feldstaerken(k))
    for fahrer in welt.spielerfahrer:
        assert round(gesamtwert(k, fahrer.auto)) in leiter


def test_ohne_spieler_gibt_es_nur_ki(k) -> None:
    nur_ki = w.erzeuge(k, Seedquelle(1), mit_spieler=False)
    assert nur_ki.spieler is None
    assert not any(f.ist_spieler for f in nur_ki.fahrer)


# -- Teams ------------------------------------------------------------------
def test_teamnamen_sind_eindeutig(welt) -> None:
    namen = [team.name for team in welt.teams]
    assert len(set(namen)) == len(namen)


def test_teamfarben_lassen_sich_auseinanderhalten(welt, k) -> None:
    """GDD 4: Autos als Punkte in Teamfarbe - im Rennen muss man sie trennen."""
    farben = {team.farbe for team in welt.teams}
    assert len(farben) == k.wert("teams", "anzahl")


def test_teamfarbe_ist_die_herstellerfarbe(welt) -> None:
    """Punkt 101: Ein Hersteller, ein Team - beide tragen dieselbe Farbe."""
    for team in welt.teams:
        assert team.farbe == team.herstellerfarbe


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiche_welt(k) -> None:
    """GDD 12: Alles per Seed erzeugt."""
    erste = w.erzeuge(k, Seedquelle(99))
    zweite = w.erzeuge(k, Seedquelle(99))
    assert [f.name for f in erste.fahrer] == [f.name for f in zweite.fahrer]
    assert [t.name for t in erste.teams] == [t.name for t in zweite.teams]
    assert erste.fahrer[0].auto.werte == zweite.fahrer[0].auto.werte


def test_anderer_seed_andere_welt(k) -> None:
    erste = w.erzeuge(k, Seedquelle(99))
    zweite = w.erzeuge(k, Seedquelle(100))
    assert [f.name for f in erste.fahrer] != [f.name for f in zweite.fahrer]


# -- Anschluss ans Rennen ---------------------------------------------------
def test_starterfeld_aus_der_welt(welt, k) -> None:
    feld = w.starterfeld(welt)
    assert len(feld) == k.wert("rennen", "autos")
    assert sorted(t.startplatz for t in feld) == list(range(1, len(feld) + 1))
    # Die Punkte tragen die Teamfarbe (GDD 4).
    assert {t.farbe for t in feld} == {team.farbe for team in welt.teams}


def test_starterfeld_nimmt_eine_aufstellung_an(welt) -> None:
    fahrer = welt.feld
    umgedreht = tuple(f.nummer for f in reversed(fahrer))
    feld = w.starterfeld(welt, umgedreht)
    assert feld[0].auto.kuerzel == fahrer[-1].kuerzel


def test_unvollstaendige_aufstellung_meldet_fehler(welt) -> None:
    with pytest.raises(w.WeltFehler, match="Aufstellung"):
        w.starterfeld(welt, (0, 1, 2))


def test_starterfeld_kennzeichnet_die_eigenen_fahrer(welt, k) -> None:
    feld = w.starterfeld(welt)
    assert sum(1 for t in feld if t.ist_spieler) == k.wert("teams", "autos_je_team")


def test_bereichswerte_lassen_sich_bilden(welt, k) -> None:
    """Die erzeugten Autos muessen durch die Wirkungsmatrix passen."""
    for fahrer in welt.feld[:5]:
        for bereich in k.bereiche:
            assert bereichswert(k, fahrer.auto, bereich) >= 0
