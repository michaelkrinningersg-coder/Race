"""Tests fuer die Welt: 600 Autos, 150 Teams, 20 Ligen (GDD 12)."""

from __future__ import annotations

import datetime as dt
import statistics
from collections import Counter

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import welt as w
from rennmanager.kern.auto import bereichswert, pruefe
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def welt(k) -> w.Welt:
    return w.erzeuge(k, Seedquelle(4711), spielerliga=k.wert("ligen", "startliga"))


# -- Umfang -----------------------------------------------------------------
def test_sechshundert_autos_in_zwanzig_ligen(welt, k) -> None:
    """GDD 1: 20 Ligen x 30 Autos = 600 Autos."""
    ligen = k.wert("ligen", "anzahl")
    je_liga = k.wert("ligen", "autos_je_liga")
    assert len(welt.fahrer) == ligen * je_liga
    besetzung = Counter(f.liga for f in welt.fahrer)
    assert sorted(besetzung) == list(range(1, ligen + 1))
    assert set(besetzung.values()) == {je_liga}


def test_hundertfuenfzig_teams_mit_je_vier_autos(welt, k) -> None:
    """GDD 12: 150 Teams mit je 4 Autos eines Herstellers."""
    assert len(welt.teams) == k.wert("teams", "anzahl")
    for team in welt.teams:
        assert len(team.fahrer) == k.wert("teams", "autos_je_team")
    # Jeder Fahrer gehoert genau einem Team.
    zugeordnet = [nummer for team in welt.teams for nummer in team.fahrer]
    assert sorted(zugeordnet) == list(range(len(welt.fahrer)))


def test_teams_fahren_in_verschiedenen_ligen(welt) -> None:
    """GDD 12: Die 4 Autos eines Teams koennen in verschiedenen Ligen fahren."""
    gemischt = sum(
        1
        for team in welt.teams
        if len({welt.fahrer[i].liga for i in team.fahrer}) > 1
    )
    assert gemischt > len(welt.teams) * 0.8


def test_hersteller_sind_ueber_die_ligen_verteilt(welt, k) -> None:
    """GDD 12: verteilt, aber nicht zwingend gleichmaessig."""
    marken = {team.hersteller for team in welt.teams}
    assert len(marken) == k.wert("hersteller", "anzahl")


# -- Staerke ----------------------------------------------------------------
def test_ligastaerke_folgt_der_kalibriertabelle(welt, k) -> None:
    """GDD 9: Staerke zwischen dem Letzten und dem Besten der Liga."""
    for zeile in k.wert("ligen", "kontrolle"):
        mittel = [
            statistics.mean(f.auto.werte.values()) for f in welt.liga(zeile["liga"])
        ]
        # Das Rauschen der Profilstreuung laesst etwas Spielraum.
        assert min(mittel) == pytest.approx(zeile["s_letzter"], abs=4_000)
        assert max(mittel) == pytest.approx(zeile["s_bester"], abs=4_000)


def test_hoehere_ligen_sind_staerker(welt, k) -> None:
    mittel = {
        liga: statistics.mean(
            statistics.mean(f.auto.werte.values()) for f in welt.liga(liga)
        )
        for liga in range(1, k.wert("ligen", "anzahl") + 1)
    }
    werte = [mittel[liga] for liga in sorted(mittel)]
    assert werte == sorted(werte, reverse=True)


def test_liga_ist_nach_staerke_geordnet(welt) -> None:
    for liga in (1, 10, 20):
        werte = [sum(f.auto.werte.values()) for f in welt.liga(liga)]
        assert werte == sorted(werte, reverse=True)


def test_profile_streuen_um_den_mittelwert(welt, k) -> None:
    """GDD 12: Einzelwerte streuen +/- 25 % - es gibt also Spezialisten."""
    streuung = k.wert("ki", "profil_streuung")
    for fahrer in welt.liga(10):
        werte = list(fahrer.auto.werte.values())
        mittel = statistics.mean(werte)
        assert min(werte) >= mittel * (1 - streuung) * 0.95
        assert max(werte) <= mittel * (1 + streuung) * 1.05
    # Und die Spezialisierung unterscheidet sich wirklich je Fahrer.
    regen = [f.auto.wetterwert("regenfahren") / max(f.auto.wert("D1"), 1) for f in welt.liga(10)]
    assert max(regen) - min(regen) > 0.2


def test_alle_autos_sind_gueltig(welt, k) -> None:
    for fahrer in welt.fahrer:
        pruefe(k, fahrer.auto)


def test_wetterfaehigkeiten_und_fluesterer_sind_gesetzt(welt, k) -> None:
    erwartet = {e["schluessel"] for e in k.wert("wetter", "faehigkeit", "liste")}
    erwartet.add("reifenfluesterer")
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
    stichtag = dt.date(2026, 3, 1)
    alter = [f.alter_am(stichtag) for f in welt.fahrer]
    assert min(alter) >= k.wert("fahrernamen", "alter_min") - 1
    assert max(alter) <= k.wert("fahrernamen", "alter_max") + 1


# -- Spieler ----------------------------------------------------------------
def test_spieler_startet_mit_allen_werten_auf_null(welt, k) -> None:
    """GDD 1: Der Spieler startet mit allen Werten auf 0 in Liga 20."""
    spieler = welt.spieler
    assert spieler is not None
    assert spieler.liga == k.wert("ligen", "startliga")
    assert set(spieler.auto.werte.values()) == {0}
    assert set(spieler.auto.wetterwerte.values()) == {0}


def test_spieler_hat_drei_ki_teamkollegen(welt) -> None:
    """GDD 12: Der Spieler faehrt in einem Team mit 3 KI-Fahrern."""
    kollegen = welt.teamkollegen(welt.spieler)
    assert len(kollegen) == 3
    assert not any(f.ist_spieler for f in kollegen)


def test_ohne_spielerliga_gibt_es_nur_ki(k) -> None:
    nur_ki = w.erzeuge(k, Seedquelle(1))
    assert nur_ki.spieler is None
    assert not any(f.ist_spieler for f in nur_ki.fahrer)


# -- Teams ------------------------------------------------------------------
def test_teamnamen_sind_eindeutig(welt) -> None:
    namen = [team.name for team in welt.teams]
    assert len(set(namen)) == len(namen)


def test_teamfarben_unterscheiden_sich_je_liga(welt) -> None:
    """GDD 4: Autos als Punkte in Teamfarbe - im Rennen muss man sie trennen."""
    for liga in (1, 10, 20):
        farben = {welt.team_von(f).farbe for f in welt.liga(liga)}
        assert len(farben) >= 20


def test_teamfarbe_ist_nicht_die_herstellerfarbe(welt) -> None:
    """GDD 12 gibt Hersteller und Team je eine eigene Farbe."""
    abweichend = sum(1 for team in welt.teams if team.farbe != team.herstellerfarbe)
    assert abweichend > len(welt.teams) * 0.8


def test_budget_waechst_mit_der_liga(welt) -> None:
    """GDD 10: KI-Budgets sind Anzeige; sie sollen zur Liga passen."""

    def mittlere_liga(team) -> float:
        return statistics.mean(welt.fahrer[i].liga for i in team.fahrer)

    oben = [t.budget for t in welt.teams if mittlere_liga(t) <= 6]
    unten = [t.budget for t in welt.teams if mittlere_liga(t) >= 15]
    assert oben and unten
    assert statistics.mean(oben) > statistics.mean(unten) * 5


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiche_welt(k) -> None:
    """GDD 12: Alles per Seed erzeugt."""
    erste = w.erzeuge(k, Seedquelle(99), spielerliga=20)
    zweite = w.erzeuge(k, Seedquelle(99), spielerliga=20)
    assert [f.name for f in erste.fahrer] == [f.name for f in zweite.fahrer]
    assert [t.name for t in erste.teams] == [t.name for t in zweite.teams]
    assert erste.fahrer[0].auto.werte == zweite.fahrer[0].auto.werte


def test_anderer_seed_andere_welt(k) -> None:
    erste = w.erzeuge(k, Seedquelle(99), spielerliga=20)
    zweite = w.erzeuge(k, Seedquelle(100), spielerliga=20)
    assert [f.name for f in erste.fahrer] != [f.name for f in zweite.fahrer]


# -- Anschluss ans Rennen ---------------------------------------------------
def test_starterfeld_aus_der_welt(welt, k) -> None:
    feld = w.starterfeld(welt, 10)
    assert len(feld) == k.wert("ligen", "autos_je_liga")
    assert sorted(t.startplatz for t in feld) == list(range(1, len(feld) + 1))
    # Die Punkte tragen die Teamfarbe (GDD 4).
    kuerzel_zu_farbe = {welt.team_von(f).farbe for f in welt.liga(10)}
    assert {t.farbe for t in feld} <= kuerzel_zu_farbe


def test_starterfeld_nimmt_eine_aufstellung_an(welt) -> None:
    fahrer = welt.liga(10)
    umgedreht = tuple(f.nummer for f in reversed(fahrer))
    feld = w.starterfeld(welt, 10, umgedreht)
    assert feld[0].auto.kuerzel == fahrer[-1].kuerzel


def test_unvollstaendige_aufstellung_meldet_fehler(welt) -> None:
    with pytest.raises(w.WeltFehler, match="Aufstellung"):
        w.starterfeld(welt, 10, (0, 1, 2))


def test_starterfeld_kennzeichnet_den_spieler(welt, k) -> None:
    feld = w.starterfeld(welt, k.wert("ligen", "startliga"))
    assert sum(1 for t in feld if t.ist_spieler) == 1


def test_bereichswerte_lassen_sich_bilden(welt, k) -> None:
    """Die erzeugten Autos muessen durch die Wirkungsmatrix passen."""
    for fahrer in welt.liga(10)[:5]:
        for bereich in k.bereiche:
            assert bereichswert(k, fahrer.auto, bereich) >= 0
