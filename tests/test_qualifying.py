"""Tests fuer das Qualifying (GDD 4)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import qualifying as ql
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern.zufall import Seedquelle

LIGA = 10


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def strecke(k) -> st.Strecke:
    return st.lade(k, "Catalunya")


@pytest.fixture(scope="module")
def feld(k) -> tuple[rn.Teilnehmer, ...]:
    return rn.starterfeld(k)


@pytest.fixture(scope="module")
def session(k, strecke, feld) -> ql.Qualifying:
    return ql.fahre(k, strecke, feld, Seedquelle(4711))


# -- Ablauf -----------------------------------------------------------------
def test_jedes_auto_faehrt_genau_eine_gezeitete_runde(session, feld) -> None:
    assert len(session.fahrten) == len(feld)
    assert {f.teilnehmer for f in session.fahrten} == set(range(len(feld)))
    assert all(f.zeit_ms > 0 for f in session.fahrten)


def test_autos_starten_nacheinander(session, k) -> None:
    """GDD 4: Jedes Auto faehrt allein - aber ueberlappend gestartet.

    Ohne Ueberlappung dauerte eine Session 30 mal zwei Runden; das Wetter
    haette dann mehr Einfluss als die Fahrleistung.
    """
    abstaende = [
        danach.beginn_ms - davor.beginn_ms
        for davor, danach in zip(session.fahrten, session.fahrten[1:], strict=False)
    ]
    assert abstaende, "Es muss mehr als ein Auto fahren"
    # Alle Abstaende gleich und positiv.
    assert max(abstaende) - min(abstaende) <= 1
    assert min(abstaende) > 0


def test_aufwaermrunde_kostet_zeit(session, k) -> None:
    """Die ungezeitete Runde verbraucht Sessionzeit, wird aber nicht gewertet."""
    for fahrt in session.fahrten:
        # Zwischen Beginn und Zielankunft liegen Aufwaermrunde und gezeitete
        # Runde, also deutlich mehr als nur die gewertete Zeit.
        assert fahrt.ziel_ms - fahrt.beginn_ms > fahrt.zeit_ms


def test_sektorzeiten_ergeben_die_rundenzeit(session, k) -> None:
    sektoren = k.wert("strecke", "sektoren")
    for fahrt in session.fahrten:
        assert len(fahrt.sektoren_ms) == sektoren
        assert sum(fahrt.sektoren_ms) == pytest.approx(fahrt.zeit_ms, abs=5)


def test_zeiten_sind_ganze_millisekunden(session) -> None:
    for fahrt in session.fahrten:
        assert isinstance(fahrt.zeit_ms, int)
        assert all(isinstance(wert, int) for wert in fahrt.sektoren_ms)


# -- Startreihenfolge -------------------------------------------------------
def test_erstes_rennen_faehrt_nach_qualifyingstaerke(k, feld) -> None:
    """GDD 4: im ersten Rennen aufsteigend nach Qualifying-Faehigkeit."""
    reihenfolge = ql.startreihenfolge(k, feld)
    staerken = [ql.qualifyingstaerke(k, feld[i]) for i in reihenfolge]
    assert staerken == sorted(staerken)


def test_meisterschaftsfuehrender_faehrt_zuletzt(k, feld) -> None:
    """GDD 4: umgekehrter Meisterschaftsstand."""
    meisterschaft = tuple(range(len(feld)))
    reihenfolge = ql.startreihenfolge(k, feld, meisterschaft)
    assert reihenfolge[-1] == meisterschaft[0]
    assert reihenfolge[0] == meisterschaft[-1]


def test_unvollstaendige_meisterschaft_meldet_fehler(k, feld) -> None:
    with pytest.raises(ValueError, match="genau einmal"):
        ql.startreihenfolge(k, feld, (0, 1, 2))


# -- Aufstellung ------------------------------------------------------------
def test_aufstellung_folgt_den_zeiten(session) -> None:
    zeiten = [
        next(f for f in session.fahrten if f.teilnehmer == i).zeit_ms
        for i in session.aufstellung
    ]
    assert zeiten == sorted(zeiten)


def test_aufstellung_enthaelt_jedes_auto_einmal(session, feld) -> None:
    assert sorted(session.aufstellung) == list(range(len(feld)))
    assert session.startplatz(session.aufstellung[0]) == 1


def test_pole_ist_die_schnellste_runde(session) -> None:
    assert session.pole.zeit_ms == min(f.zeit_ms for f in session.fahrten)


# -- Live-Einsortierung -----------------------------------------------------
def test_zwischenstand_waechst_mit_den_fahrten(session) -> None:
    """GDD 4: Live-Einsortierung ins Ranking."""
    assert session.stand_nach(0) == ()
    assert len(session.stand_nach(1)) == 1
    assert len(session.stand_nach(10)) == 10
    assert len(session.stand_nach(len(session.fahrten))) == len(session.fahrten)


def test_zwischenstand_ist_nach_zeit_geordnet(session) -> None:
    stand = session.stand_nach(12)
    assert [f.zeit_ms for f in stand] == sorted(f.zeit_ms for f in stand)


def test_bestzeit_verbessert_sich_nur(session) -> None:
    """Die aktuelle Bestzeit kann nie schlechter werden."""
    bisher = None
    for anzahl in range(1, len(session.fahrten) + 1):
        beste = session.bestzeit_nach(anzahl)
        if bisher is not None:
            assert beste <= bisher
        bisher = beste
    assert session.bestzeit_nach(0) is None


# -- Wetter und Zufall ------------------------------------------------------
def test_session_hat_ein_wetter(session, k) -> None:
    assert session.wetter.startzustand in k.wert("wetter", "kette")
    assert all(f.zustand in k.wert("wetter", "kette") for f in session.fahrten)


def test_nasses_wetter_macht_langsamer(k, strecke, feld) -> None:
    """Der Grip-Faktor senkt das Tempo (GDD 7)."""
    trockene = []
    nasse = []
    for seed in range(40):
        session = ql.fahre(k, strecke, feld, Seedquelle(seed))
        ziel = trockene if session.pole.zustand in ("trocken", "heiss") else nasse
        ziel.append(session.pole.zeit_ms)
    assert trockene and nasse
    assert min(nasse) > min(trockene)


def test_tagesform_ist_je_auto_verschieden(session) -> None:
    formen = {round(f.tagesform, 9) for f in session.fahrten}
    assert len(formen) > 1


def test_qualifyingbonus_waechst_mit_dem_koennen(k, feld) -> None:
    """GDD 8: Die Q-Spalte ist ein zusaetzliches Gewicht fuer die Runde."""
    from rennmanager.kern import auto as ka

    schwach = ql.qualifyingbonus(k, ka.gleichverteilt(k, 0))
    stark = ql.qualifyingbonus(k, ka.gleichverteilt(k, 100_000))
    assert schwach == pytest.approx(0.0)
    assert stark == pytest.approx(k.wert("qualifying", "bonus", "max_anteil"), rel=0.02)


def test_gleicher_seed_gleiches_qualifying(k, strecke, feld) -> None:
    erste = ql.fahre(k, strecke, feld, Seedquelle(77))
    zweite = ql.fahre(k, strecke, feld, Seedquelle(77))
    assert erste.aufstellung == zweite.aufstellung
    assert erste.fahrten == zweite.fahrten


def test_anderer_seed_anderes_qualifying(k, strecke, feld) -> None:
    erste = ql.fahre(k, strecke, feld, Seedquelle(77))
    zweite = ql.fahre(k, strecke, feld, Seedquelle(78))
    assert erste.fahrten != zweite.fahrten


def test_ohne_teilnehmer_meldet_fehler(k, strecke) -> None:
    with pytest.raises(ValueError, match="Teilnehmer"):
        ql.fahre(k, strecke, (), Seedquelle(1))


def test_staerkere_autos_stehen_meist_vorn(k, strecke, feld) -> None:
    """Der Zufall darf die Rangfolge stoeren, aber nicht umkehren."""
    plaetze = []
    for seed in range(12):
        session = ql.fahre(k, strecke, feld, Seedquelle(seed))
        # Teilnehmer 0 ist das staerkste Auto des Feldes.
        plaetze.append(session.startplatz(0))
    assert sum(plaetze) / len(plaetze) < len(feld) / 3


def _kunst_session(session: ql.Qualifying) -> ql.Qualifying:
    """Eine Session aus vier von Hand gesetzten Fahrten.

    Vier Autos, die nacheinander ins Ziel kommen und sich dabei
    gegenseitig ueberholen - das braucht die Uebertragung, um zu zeigen,
    dass der eingefrorene Vergleich etwas anderes ist als der gegen die
    Pole. Die Reihenfolge der Sektoren ist so gelegt, dass der Dritte
    seine Runde faehrt, waehrend noch der Erste fuehrt.
    """
    entwurf = (
        # (Sektorzeit, Zielzeit) - der Erste ist langsam und fuehrt trotzdem
        (31_000, 200_000),
        (30_000, 400_000),
        (30_500, 350_000),
        (29_000, 500_000),
    )
    fahrten = tuple(
        ql.Fahrt(
            teilnehmer=nummer,
            reihenfolge=nummer + 1,
            beginn_ms=ziel - 8 * sektor,
            ziel_ms=ziel,
            zeit_ms=4 * sektor,
            sektoren_ms=(sektor,) * 4,
            tagesform=1.0,
            zustand="Trocken",
            grip=1.0,
        )
        for nummer, (sektor, ziel) in enumerate(entwurf)
    )
    aufstellung = tuple(
        f.teilnehmer for f in sorted(fahrten, key=lambda f: f.zeit_ms)
    )
    return replace(
        session,
        fahrten=fahrten,
        aufstellung=aufstellung,
        dauer_ms=max(f.ziel_ms for f in fahrten),
    )


# -- Uebertragung (Punkt 85) ------------------------------------------------
def test_die_gezeitete_runde_beginnt_nach_der_aufwaermrunde(session) -> None:
    """Zwischen Ausfahrt und schneller Runde liegt die Aufwaermrunde."""
    for fahrt in session.fahrten:
        assert fahrt.beginn_ms < fahrt.runde_ab_ms < fahrt.ziel_ms
        assert fahrt.ziel_ms - fahrt.runde_ab_ms == fahrt.zeit_ms


def test_der_letzte_sektor_endet_im_ziel(session) -> None:
    """Sektoren und Rundenzeit runden getrennt - das Ziel entscheidet.

    Sonst laege das Ende des letzten Sektors ein bis zwei Millisekunden
    neben dem Ziel, und ein Auto waere fuer einen Takt im Ziel, ohne
    seinen letzten Sektor gesetzt zu haben.
    """
    for fahrt in session.fahrten:
        enden = fahrt.sektorenden_ms
        assert len(enden) == len(fahrt.sektoren_ms)
        assert enden[-1] == fahrt.ziel_ms
        assert list(enden) == sorted(enden)
        assert enden[0] > fahrt.runde_ab_ms


def test_die_lage_durchlaeuft_alle_vier_zustaende(session) -> None:
    fahrt = session.fahrten[0]
    lagen = [
        session._stand_zu(fahrt, fahrt.beginn_ms - 1).lage,
        session._stand_zu(fahrt, fahrt.beginn_ms).lage,
        session._stand_zu(fahrt, fahrt.runde_ab_ms).lage,
        session._stand_zu(fahrt, fahrt.ziel_ms).lage,
    ]
    assert lagen == [ql.Lage.WARTET, ql.Lage.AUFWAERMUNG, ql.Lage.SCHNELLE_RUNDE, ql.Lage.ZIEL]


def test_am_anfang_hat_noch_niemand_eine_zeit(session, feld) -> None:
    """Zum Sessionbeginn faehrt hoechstens der Erste seine Aufwaermrunde."""
    stand = session.lage_zu(0)
    assert len(stand) == len(feld)
    assert all(s.zeit_ms is None for s in stand)
    unterwegs = [s for s in stand if s.lage is not ql.Lage.WARTET]
    assert len(unterwegs) == 1
    assert unterwegs[0].lage is ql.Lage.AUFWAERMUNG


def test_am_ende_steht_das_feld_in_der_reihenfolge_der_aufstellung(session) -> None:
    stand = session.lage_zu(session.dauer_ms)
    assert all(s.ist_fertig for s in stand)
    assert tuple(s.fahrt.teilnehmer for s in stand) == session.aufstellung


def test_die_zeit_laeuft_auf_der_schnellen_runde_mit(session) -> None:
    fahrt = session.fahrten[0]
    mitte = fahrt.runde_ab_ms + fahrt.zeit_ms // 2
    stand = session._stand_zu(fahrt, mitte)
    assert stand.lage is ql.Lage.SCHNELLE_RUNDE
    assert stand.zeit_ms == fahrt.zeit_ms // 2
    assert 0 < stand.sektoren < len(fahrt.sektoren_ms)


def test_fertige_stehen_ueber_den_laufenden(session) -> None:
    """Wer seine Runde stehen hat, steht ueber jedem, der noch faehrt."""
    fahrt = session.fahrten[3]
    stand = session.lage_zu(fahrt.runde_ab_ms + 1)
    lagen = [s.lage for s in stand]
    gruppen = [ql.Lage.ZIEL, ql.Lage.SCHNELLE_RUNDE, ql.Lage.AUFWAERMUNG, ql.Lage.WARTET]
    folge = [gruppen.index(lage) for lage in lagen]
    assert folge == sorted(folge)
    assert ql.Lage.ZIEL in lagen and ql.Lage.WARTET in lagen


def test_der_erste_fahrer_hat_keinen_vergleich(session) -> None:
    """Wer als Erster faehrt, misst sich gegen niemanden."""
    erster = session.fahrten[0]
    assert all(
        session.splitvergleich(erster, nummer) is None
        for nummer in range(len(erster.sektoren_ms))
    )


def test_der_vergleich_friert_im_moment_des_ueberfahrens_ein(session) -> None:
    """Entscheidung des Auftraggebers: wie im Fernsehen.

    Gemessen wird gegen den, der in dem Moment vorn lag - nicht gegen
    den, der am Ende der Session vorn liegt. Beides faellt auseinander,
    sobald jemand den damaligen Fuehrenden unterbietet, ohne die Pole zu
    erreichen. Die gebaute Session zeigt genau diesen Fall; ein Seed
    liefert ihn nicht zuverlaessig, weil das Wetter der Session ihn
    verdecken kann.
    """
    kunst = _kunst_session(session)
    langsam, _, mittel, schnell = kunst.fahrten
    # Der Dritte faehrt seine Sektoren, waehrend noch der Erste fuehrt.
    assert kunst.fuehrender_zu(mittel.sektorenden_ms[0], ohne=mittel) is langsam
    assert kunst.pole is schnell

    eingefroren = kunst.splitvergleich(mittel, 0)
    gegen_pole = mittel.sektoren_ms[0] - schnell.sektoren_ms[0]
    assert eingefroren < 0, "schneller als der damalige Fuehrende"
    assert gegen_pole > 0, "langsamer als die spaetere Pole"


def test_der_vergleich_misst_gegen_den_fuehrenden_zu_dem_zeitpunkt(session) -> None:
    for fahrt in session.fahrten:
        for nummer in range(len(fahrt.sektoren_ms)):
            zeit = fahrt.sektorenden_ms[nummer]
            fuehrt = session.fuehrender_zu(zeit, ohne=fahrt)
            wert = session.splitvergleich(fahrt, nummer)
            if fuehrt is None:
                assert wert is None
            else:
                assert wert == fahrt.sektoren_ms[nummer] - fuehrt.sektoren_ms[nummer]


def test_eine_laufende_runde_fuehrt_nicht(session) -> None:
    """Erst wenn die Runde steht, ist sie vergleichbar."""
    erster = session.fahrten[0]
    assert session.fuehrender_zu(erster.ziel_ms - 1) is None
    assert session.fuehrender_zu(erster.ziel_ms) is erster


def test_lila_haelt_je_sektor_genau_einer(session) -> None:
    stand = session.beste_splits_zu(session.dauer_ms)
    assert len(stand) == len(session.fahrten[0].sektoren_ms)
    for nummer, halter in enumerate(stand):
        bestzeit = min(f.sektoren_ms[nummer] for f in session.fahrten)
        fahrt = next(f for f in session.fahrten if f.teilnehmer == halter)
        assert fahrt.sektoren_ms[nummer] == bestzeit


def test_lila_wandert_beim_abspielen_weiter(session) -> None:
    """Der beste Split ist Live-Stand, kein Endergebnis.

    Frueh in der Session haelt ihn jemand anderes als am Ende - sonst
    waere die Farbe schon beim Laden entschieden.
    """
    frueh = session.beste_splits_zu(session.fahrten[2].ziel_ms)
    spaet = session.beste_splits_zu(session.dauer_ms)
    assert any(a is not None for a in frueh)
    assert frueh != spaet


def test_ohne_gefahrenen_sektor_gibt_es_kein_lila(session) -> None:
    assert all(halter is None for halter in session.beste_splits_zu(0))


# -- Was gerade passiert ist (Punkt 93) -------------------------------------
def test_die_letzte_zielankunft_nennt_platz_und_verdraengten(k, strecke) -> None:
    session = ql.fahre(k, strecke, rn.starterfeld(k), Seedquelle(0))
    fenster = k.wert("qualifying", "hervorhebung_ms")
    for fahrt in sorted(session.fahrten, key=lambda f: f.ziel_ms):
        ankunft = session.letzte_zielankunft(fahrt.ziel_ms, fenster)
        assert ankunft is not None
        if ankunft.fahrt is not fahrt:
            continue  # zwei in derselben Millisekunde
        # Der Platz stimmt mit dem Stand in diesem Augenblick ueberein.
        bisher = sorted(
            (f for f in session.fahrten if f.ziel_ms <= fahrt.ziel_ms),
            key=lambda f: (f.zeit_ms, f.reihenfolge),
        )
        assert ankunft.platz == bisher.index(fahrt) + 1
        if ankunft.platz == len(bisher):
            assert ankunft.verdraengt is None, "Hinten reiht man sich ein"
            assert ankunft.abstand_ms == 0
        else:
            assert ankunft.verdraengt is bisher[ankunft.platz]
            assert ankunft.abstand_ms > 0


def test_ausserhalb_des_fensters_gibt_es_keine_ankunft(k, strecke) -> None:
    """Sonst stuende der letzte Wechsel bis zum Sessionende da."""
    session = ql.fahre(k, strecke, rn.starterfeld(k), Seedquelle(0))
    fenster = k.wert("qualifying", "hervorhebung_ms")
    letzte = max(f.ziel_ms for f in session.fahrten)
    assert session.letzte_zielankunft(letzte, fenster) is not None
    assert session.letzte_zielankunft(letzte + fenster + 1, fenster) is None
    # Und vor der ersten Ankunft gibt es nichts zu melden.
    erste = min(f.ziel_ms for f in session.fahrten)
    assert session.letzte_zielankunft(erste - 1, fenster) is None


def test_der_erste_eroeffnet_die_pole_statt_sie_zu_uebernehmen(k, strecke) -> None:
    session = ql.fahre(k, strecke, rn.starterfeld(k), Seedquelle(0))
    fenster = k.wert("qualifying", "hervorhebung_ms")
    erste = min(session.fahrten, key=lambda f: f.ziel_ms)
    ankunft = session.letzte_zielankunft(erste.ziel_ms, fenster)
    assert ankunft is not None and ankunft.platz == 1
    assert not ankunft.neue_pole, "Vorher stand dort niemand"
