"""Tests fuer die Welt: 400 Autos, 100 Teams, 10 Ligen (GDD 12, Punkt 95)."""

from __future__ import annotations

import datetime as dt
import statistics
from collections import Counter

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import welt as w
from rennmanager.kern.auto import bereichswert, pruefe
from rennmanager.kern.zufall import Seedquelle


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


SEED = 4711


@pytest.fixture(scope="module")
def welt(k) -> w.Welt:
    return w.erzeuge(k, Seedquelle(SEED), spielerliga=k.wert("ligen", "startliga"))


# -- Umfang -----------------------------------------------------------------
def test_vierhundert_autos_in_zehn_ligen(welt, k) -> None:
    """Punkt 95: 10 Ligen x 40 Autos = 400 Autos."""
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
def test_die_potentialleiter_folgt_der_kalibriertabelle(welt, k) -> None:
    """GDD 9 beschreibt jetzt die **Potentiale**, nicht die Startwerte.

    Seit die Werte aus dem Talent kommen (Punkt 35), steht jeder Fahrer
    auf seinem eigenen Laufbahnpunkt und damit unter seinem Potential -
    die Startwerte liegen deshalb unter der Kontrolltabelle. Was die
    Tabelle weiter beschreibt, ist die Leiter der Potentiale: Sortiert
    man alle 600, kommt sie zurueck.
    """
    from rennmanager.kern import talent as kern_talent

    quelle = Seedquelle(SEED)
    je_liga = k.wert("ligen", "autos_je_liga")
    potentiale = sorted(
        (
            kern_talent.talent(k, f.nummer, f.geburtstag, quelle).gipfelstaerke
            for f in welt.fahrer
            if not f.ist_spieler
        ),
        reverse=True,
    )
    for zeile in k.wert("ligen", "kontrolle"):
        anfang = (zeile["liga"] - 1) * je_liga
        feld = potentiale[anfang : anfang + je_liga]
        if not feld:
            continue
        soll = (zeile["s_bester"] + zeile["s_letzter"]) / 2
        assert statistics.mean(feld) == pytest.approx(soll, rel=0.25)


def test_jeder_steht_auf_seinem_eigenen_laufbahnpunkt(welt, k) -> None:
    """Der Grund fuer den Umbau: Vorher passten Wert und Talent nicht.

    Gemessen hatte der Beste in Liga 1 den Wert 98130 bei einem Potential
    von 70000 - er wurde ab der ersten Saison schlechter. Jetzt ist die
    Abweichung null: Wert = Potential mal Reife mal Zielfaktor.
    """
    from rennmanager.kern import generationen as kern_generationen
    from rennmanager.kern import talent as kern_talent
    from rennmanager.kern.auto import gesamtwert

    quelle = Seedquelle(SEED)
    stichtag = kern_kalender.saisonstart(k, 2026)
    for fahrer in welt.fahrer:
        if fahrer.ist_spieler:
            continue
        talent = kern_talent.talent(k, fahrer.nummer, fahrer.geburtstag, quelle)
        soll = kern_talent.stand_mit(
            k,
            talent,
            fahrer.alter_am(stichtag),
            kern_generationen.ruecktrittsalter(k, fahrer.nummer, quelle),
        )
        assert gesamtwert(k, fahrer.auto) == pytest.approx(soll, abs=1.0)


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
    for liga in (1, 5, 10):
        werte = [sum(f.auto.werte.values()) for f in welt.liga(liga)]
        assert werte == sorted(werte, reverse=True)


def test_profile_streuen_um_den_mittelwert(welt, k) -> None:
    """Zwei Ebenen: Bereichsprofil (Punkt 37) und Rauschen (GDD 12).

    Die Grenze ist das Produkt beider Streuungen; mehr kann nicht
    herauskommen.
    """
    rauschen = k.wert("ki", "profil_streuung")
    bereich = k.wert("ki", "bereichs_streuung")
    untere = (1 - bereich) * (1 - rauschen)
    obere = (1 + bereich) * (1 + rauschen)
    # Gemessen wird gegen den **eigenen** Mittelwert des Fahrers, und der
    # ist selbst gewuerfelt: Faellt er niedrig aus, steht der hoechste
    # Einzelwert weiter darueber, als das Produkt beider Streuungen
    # hergibt. Ueber 1.980 KI-Fahrer aus fuenf Weltseeds gemessen lagen
    # die Extreme bei 1,769 (nominal 1,625) und 0,496 (nominal 0,525);
    # die Zuschlaege decken das ab.
    zuschlag_oben, zuschlag_unten = 1.12, 0.92
    # Ohne den Spieler: Sein Team startet ohne Karriere bei null, und
    # seit Punkt 95 steht es in Liga 10 - ein Mittelwert von 0 hat keine
    # Streuung, an der sich etwas messen liesse.
    ki = [f for f in welt.liga(10) if not f.ist_spieler]
    for fahrer in ki:
        werte = list(fahrer.auto.werte.values())
        mittel = statistics.mean(werte)
        assert min(werte) >= mittel * untere * zuschlag_unten
        assert max(werte) <= mittel * obere * zuschlag_oben
    # Und die Spezialisierung unterscheidet sich wirklich je Fahrer.
    regen = [f.auto.wetterwert("regenfahren") / max(f.auto.wert("D1"), 1) for f in ki]
    assert max(regen) - min(regen) > 0.2


def test_das_bereichsprofil_macht_spezialisten(welt, k) -> None:
    """Entscheidung zu Punkt 37: Ohne die zweite Ebene mittelt sich die
    Streuung im Bereichsmittel weg - gemessen blieben von +/-25 % je
    Einzelwert nur 20 % Spanne zwischen dem staerksten und dem
    schwaechsten Bereich eines Fahrers."""
    from rennmanager.kern.auto import bereichswerte

    spannen = []
    for fahrer in welt.liga(10):
        if fahrer.ist_spieler:   # startet bei null, siehe oben
            continue
        bereiche = list(bereichswerte(k, fahrer.auto).values())
        spannen.append((max(bereiche) - min(bereiche)) / statistics.mean(bereiche))
    assert statistics.mean(spannen) > 0.30


def test_das_bereichsprofil_aendert_die_staerke_nicht(welt, k) -> None:
    """Ein Spezialist verteilt seine Staerke um, statt mehr davon zu haben.

    Das Kappen an der Skala aus GDD 9 wird ausgeglichen: In Liga 1 liegt
    die Staerke nahe am Maximum, und ohne Ausgleich fielen dort die hohen
    Werte weg - der Fahrer landete 5 % unter seinem Sollwert, also gut
    3 km/h zu langsam. Geprueft wird das am Talentprofil: Es traegt
    denselben Mittelwert wie das Potential, auf das es skaliert wurde.
    """
    from rennmanager.kern import talent as kern_talent

    quelle = Seedquelle(SEED)
    for liga in (1, 5, 10):
        for fahrer in welt.liga(liga)[:5]:
            if fahrer.ist_spieler:
                continue
            talent = kern_talent.talent(k, fahrer.nummer, fahrer.geburtstag, quelle)
            werte, _ = kern_talent.profil(k, talent, talent.gipfelstaerke)
            assert statistics.mean(werte.values()) == pytest.approx(
                talent.gipfelstaerke, abs=1
            )


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
    """Das Alter gilt zum Saisonstart und haelt die Spanne exakt ein.

    Vom 1. Januar aus gerechnet war jeder, der spaeter im Jahr Geburtstag
    hat, am Saisonstart noch ein Jahr juenger als gewuerfelt - im Feld
    standen dann 17-Jaehrige, obwohl die Konfiguration 18 als Minimum
    nennt.
    """
    stichtag = dt.date(
        2026,
        k.wert("kalender", "saisonstart_monat"),
        k.wert("kalender", "saisonstart_tag"),
    )
    alter = [f.alter_am(stichtag) for f in welt.fahrer]
    assert min(alter) == k.wert("fahrernamen", "alter_min")
    assert max(alter) == k.wert("fahrernamen", "alter_max")


# -- Spieler ----------------------------------------------------------------
def test_alle_eigenen_fahrer_starten_auf_dem_startwert(welt, k) -> None:
    """Punkt 95: vier Fahrer auf dem Startwert in der Startliga.

    Bis dahin waren es vier Fahrer auf 0 (GDD 1). Seit die unterste Liga
    bei S = 20.000 beginnt, traegt das nicht mehr - siehe
    ``startwert_spieler`` in der Konfiguration.
    """
    eigene = welt.spielerfahrer
    start = k.wert("kosten", "startwert_spieler")
    assert len(eigene) == k.wert("teams", "autos_je_team")
    for fahrer in eigene:
        assert fahrer.liga == k.wert("ligen", "startliga")
        assert set(fahrer.auto.werte.values()) == {start}
        assert set(fahrer.auto.wetterwerte.values()) == {start}


def test_dem_spieler_gehoert_ein_ganzes_team(welt) -> None:
    """Alle vier Autos eines Teams gehoeren dem Chef - keine KI dazwischen."""
    eigene = welt.spielerfahrer
    assert len({f.team for f in eigene}) == 1
    kollegen = welt.teamkollegen(eigene[0])
    assert len(kollegen) == 3
    assert all(f.ist_spieler for f in kollegen)
    assert welt.spielerteam is welt.teams[eigene[0].team]


def test_das_spielerteam_nimmt_der_liga_keine_plaetze(welt, k) -> None:
    """Getauscht statt neu verteilt: Jede Liga behaelt ihre 30 Plaetze."""
    je_liga = k.wert("ligen", "autos_je_liga")
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        assert len(welt.liga(liga)) == je_liga
    for team in welt.teams:
        assert len(team.fahrer) == k.wert("teams", "autos_je_team")


def test_der_spieler_faehrt_zunaechst_in_einer_liga(welt, k) -> None:
    """Alle vier stehen am Anfang unten - daher genau eine Spielerliga."""
    assert welt.spielerligen() == (k.wert("ligen", "startliga"),)


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
    for liga in (1, 5, 10):
        farben = {welt.team_von(f).farbe for f in welt.liga(liga)}
        assert len(farben) >= 20


def test_teamfarbe_ist_nicht_die_herstellerfarbe(welt) -> None:
    """GDD 12 gibt Hersteller und Team je eine eigene Farbe."""
    abweichend = sum(1 for team in welt.teams if team.farbe != team.herstellerfarbe)
    assert abweichend > len(welt.teams) * 0.8


def test_budget_waechst_mit_der_liga(welt, k) -> None:
    """GDD 10: KI-Budgets sind Anzeige; sie folgen der Siegpraemie der Liga."""
    from rennmanager.kern import einnahmen as ke

    def mittlere_liga(team) -> float:
        return statistics.mean(welt.fahrer[i].liga for i in team.fahrer)

    anzahl = k.wert("ligen", "anzahl")
    oben = [t.budget for t in welt.teams if mittlere_liga(t) <= 3]
    unten = [t.budget for t in welt.teams if mittlere_liga(t) >= anzahl - 2]
    assert oben and unten

    # Das Budget ist ein festes Vielfaches der Siegpraemie. Gemessen wird
    # deshalb gegen deren Verhaeltnis und nicht gegen eine Zahl, die beim
    # naechsten Balancing daneben liegt.
    erwartet = ke.siegpraemie(k, 2) / ke.siegpraemie(k, anzahl - 1)
    gemessen = statistics.mean(oben) / statistics.mean(unten)
    assert gemessen > 1.0
    assert 0.5 < gemessen / erwartet < 2.0


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiche_welt(k) -> None:
    """GDD 12: Alles per Seed erzeugt."""
    erste = w.erzeuge(k, Seedquelle(99), spielerliga=10)
    zweite = w.erzeuge(k, Seedquelle(99), spielerliga=10)
    assert [f.name for f in erste.fahrer] == [f.name for f in zweite.fahrer]
    assert [t.name for t in erste.teams] == [t.name for t in zweite.teams]
    assert erste.fahrer[0].auto.werte == zweite.fahrer[0].auto.werte


def test_anderer_seed_andere_welt(k) -> None:
    erste = w.erzeuge(k, Seedquelle(99), spielerliga=10)
    zweite = w.erzeuge(k, Seedquelle(100), spielerliga=10)
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


def test_starterfeld_kennzeichnet_die_eigenen_fahrer(welt, k) -> None:
    feld = w.starterfeld(welt, k.wert("ligen", "startliga"))
    assert sum(1 for t in feld if t.ist_spieler) == k.wert("teams", "autos_je_team")


def test_bereichswerte_lassen_sich_bilden(welt, k) -> None:
    """Die erzeugten Autos muessen durch die Wirkungsmatrix passen."""
    for fahrer in welt.liga(10)[:5]:
        for bereich in k.bereiche:
            assert bereichswert(k, fahrer.auto, bereich) >= 0
