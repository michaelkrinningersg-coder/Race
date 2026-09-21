"""Die Strecke gummiert ein (Punkt 88).

Entscheidungen des Auftraggebers: hoechstens +1,5 % Grip, Halbwert bei
500 Auto-Runden, nichts ueberlebt vom Qualifying ins Rennen, Regen
waescht allmaehlich ab und wechselhaft nur sehr wenig, und der Spieler
sieht es.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import gummierung as gu
from rennmanager.kern import qualifying as ql
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import tempo as tp
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.zufall import Seedquelle

LIGA = 10


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def zandvoort(k) -> st.Strecke:
    return st.lade(k, "Zandvoort")


@pytest.fixture(scope="module")
def mittel(k) -> float:
    return rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))


def _trockenes_wetter(k, zandvoort, dauer_ms: int) -> kern_wetter.Wetterverlauf:
    """Ein Wetterverlauf, der von Anfang bis Ende trocken bleibt."""
    for seed in range(200):
        verlauf = kern_wetter.wuerfle(
            k, zandvoort.name, dauer_ms, 90_000, Seedquelle(seed)
        )
        if set(verlauf.zustaende) <= {"trocken", "heiss"}:
            return verlauf
    pytest.skip("Kein trockener Wetterverlauf gefunden")


# -- Die Formel -------------------------------------------------------------
def test_die_gruene_strecke_gibt_nichts_dazu(k) -> None:
    """Der Anker aus GDD 9 haengt daran: Bei null ist der Faktor genau 1."""
    assert gu.faktor(k, 0.0) == 1.0
    assert gu.anteil(k, 0.0) == 0.0


def test_der_aufschlag_waechst_und_saettigt(k) -> None:
    hoechstens = k.wert("strecke", "gummierung", "max_anteil")
    reihe = [gu.anteil(k, n) for n in (0, 100, 300, 1000, 5000, 100_000)]
    assert reihe == sorted(reihe)
    assert reihe[-1] < hoechstens
    assert reihe[-1] == pytest.approx(hoechstens, rel=1e-6)
    # Die erste Haelfte der Saettigung liegt beim Halbwert.
    halbwert = k.wert("strecke", "gummierung", "halbwert_runden")
    assert gu.anteil(k, halbwert) == pytest.approx(hoechstens * 0.632, rel=0.01)


def test_trocken_und_heiss_bauen_auf(k) -> None:
    assert gu.je_runde(k, "trocken") > 0
    assert gu.je_runde(k, "heiss") > 0


def test_regen_waescht_ab_wechselhaft_nur_sehr_wenig(k) -> None:
    """Entscheidung des Auftraggebers."""
    assert gu.je_runde(k, "starkregen") < gu.je_runde(k, "regen") < 0
    assert -0.2 < gu.je_runde(k, "wechselhaft") < 0
    # "Sehr sehr wenig" heisst: um Groessenordnungen weniger als Regen.
    assert abs(gu.je_runde(k, "wechselhaft")) < abs(gu.je_runde(k, "regen")) / 10


def test_der_stand_faellt_nie_unter_null(k) -> None:
    assert gu.naechster_stand(k, 0.0, "starkregen", 100) == 0.0
    assert gu.naechster_stand(k, 10.0, "starkregen", 100) == 0.0


def test_nach_dem_regen_baut_es_sich_wieder_auf(k) -> None:
    """Entscheidung des Auftraggebers: kein dauerhafter Verlust."""
    stand = gu.naechster_stand(k, 0.0, "trocken", 600)
    nass = gu.naechster_stand(k, stand, "regen", 120)
    assert nass < stand
    wieder = gu.naechster_stand(k, nass, "trocken", 120)
    assert wieder > nass


# -- Was das an Rundenzeit bedeutet -----------------------------------------
def test_ein_prozent_grip_ist_rund_eine_sekunde(k, zandvoort) -> None:
    """Die Faustregel, auf der die Balancing-Entscheidung stand.

    Der Grip geht quadratisch ins Kurvenlimit (GDD 3), ein Prozent Grip
    bringt also mehr als ein Prozent Rundenzeit.
    """
    auto = rn.starterfeld(k)[0].auto
    gruen = tp.fahre_runde(k, zandvoort, auto, grip=1.0).zeit_ms
    ein_prozent = tp.fahre_runde(k, zandvoort, auto, grip=1.01).zeit_ms
    assert 700 < gruen - ein_prozent < 1000


# -- Im Rennen --------------------------------------------------------------
def test_ein_trockenes_rennen_gummiert_ein(k, zandvoort, mittel) -> None:
    feld = rn.starterfeld(k)
    wetter = _trockenes_wetter(k, zandvoort, 12 * 130_000)
    verlauf = rn.simuliere(
        k, zandvoort, feld, 12, Seedquelle(4711), mittel, wetter=wetter
    )
    assert verlauf.gummierung is not None
    assert verlauf.gummierung_zu(0) == 0.0
    assert verlauf.gummierung_zu(verlauf.dauer_ms) > 0
    # Gut dreissig Auto-Runden je Runde, also mehrere hundert am Ende.
    assert verlauf.gummierung_zu(verlauf.dauer_ms) > 200


def test_ein_regenrennen_gummiert_nicht(k, zandvoort, mittel) -> None:
    feld = rn.starterfeld(k)
    nass = kern_wetter.wuerfle(
        k, zandvoort.name, 8 * 130_000, 130_000, Seedquelle(11)
    )
    if set(nass.zustaende) <= {"trocken", "heiss"}:
        pytest.skip("Dieser Wurf war trocken")
    verlauf = rn.simuliere(k, zandvoort, feld, 8, Seedquelle(4711), mittel, wetter=nass)
    trocken_dabei = {"trocken", "heiss"} & set(nass.zustaende)
    if not trocken_dabei:
        assert verlauf.gummierung_zu(verlauf.dauer_ms) == 0.0


def test_ohne_wetter_bleibt_die_strecke_gruen(k, zandvoort, mittel) -> None:
    """Der Laborfall: Kalibrierung und Tests rechnen ohne Wetter.

    Im Spiel hat jedes Rennen eines - dort greift die Gummierung immer.
    """
    verlauf = rn.simuliere(k, zandvoort, rn.starterfeld(k), 3,
                           Seedquelle(4711), mittel)
    assert verlauf.gummierung is None
    assert verlauf.gummierung_zu(0.0) == 0.0


# -- Im Qualifying ----------------------------------------------------------
def test_wer_spaeter_faehrt_findet_mehr_gummi(k, zandvoort) -> None:
    """GDD 4: Die Startreihenfolge ist der umgekehrte Meisterschaftsstand."""
    feld = rn.starterfeld(k)
    for seed in range(60):
        session = ql.fahre(k, zandvoort, feld, Seedquelle(seed))
        if set(session.wetter.zustaende) <= {"trocken", "heiss"}:
            break
    else:
        pytest.skip("Keine trockene Session gefunden")

    gummi = [f.gummi for f in session.fahrten]
    assert gummi == sorted(gummi), "Der Stand muss ueber die Session wachsen"
    assert gummi[0] < gummi[-1]
    # Die Entscheidung war: spuerbar, aber nicht entscheidend.
    assert 0.0005 < gummi[-1] - gummi[0] < 0.004


def test_das_qualifying_faengt_gruen_an(k, zandvoort) -> None:
    """Entscheidung des Auftraggebers: nichts ueberlebt von vorher."""
    session = ql.fahre(k, zandvoort, rn.starterfeld(k), Seedquelle(0))
    assert session.fahrten[0].gummi < 0.0001


# -- Reifenart (Entscheidung des Auftraggebers: Bezug Mittel, Exponent 0,5) --
def test_weich_traegt_mehr_auf_als_hart(k) -> None:
    """Gummi auf der Strecke **ist** abgefahrener Reifen."""
    from rennmanager.kern import reifen as kern_reifen

    m = {x.kuerzel: x for x in kern_reifen.mischungen(k)}
    assert gu.auftrag(k, m["W"]) > gu.auftrag(k, m["M"]) > gu.auftrag(k, m["H"])
    # Die Bezugsmischung ist genau eins - sonst verschoebe sich der
    # gemessene Verlauf aus Punkt 88 ohne Absicht.
    assert gu.auftrag(k, m["M"]) == pytest.approx(1.0)
    assert gu.auftrag(k, None) == 1.0


def test_der_auftrag_folgt_dem_verschleiss(k) -> None:
    """Keine zweite Tabelle: Er kommt aus [reifen.mischungen]."""
    from rennmanager.kern import reifen as kern_reifen

    bezug = next(
        x.verschleiss
        for x in kern_reifen.mischungen(k)
        if x.kuerzel == k.wert("strecke", "gummierung", "bezugsmischung")
    )
    for m in kern_reifen.mischungen(k):
        assert gu.auftrag(k, m) == pytest.approx(m.verschleiss / bezug, rel=1e-9)


def test_weich_holt_mehr_heraus_als_hart(k) -> None:
    """Der zweite Teil: das Ansprechen auf liegenden Gummi."""
    from rennmanager.kern import reifen as kern_reifen

    m = {x.kuerzel: x for x in kern_reifen.mischungen(k)}
    assert gu.anteil(k, 1200, m["W"]) > gu.anteil(k, 1200, m["M"])
    assert gu.anteil(k, 1200, m["M"]) > gu.anteil(k, 1200, m["H"])


def test_das_ansprechen_ist_gedaempfter_als_der_auftrag(k) -> None:
    """Der Exponent unter eins ist die ganze Aussage.

    Dass ein weicher Reifen mehr Gummi liegen laesst, ist direkt. Dass er
    sich besser darin einarbeitet, ist der schwaechere Zusammenhang.
    """
    from rennmanager.kern import reifen as kern_reifen

    m = {x.kuerzel: x for x in kern_reifen.mischungen(k)}
    for kuerzel in ("W", "H"):
        abstand_auftrag = abs(gu.auftrag(k, m[kuerzel]) - 1.0)
        abstand_ansprechen = abs(gu.ansprechen(k, m[kuerzel]) - 1.0)
        assert abstand_ansprechen < abstand_auftrag


def test_auf_gruener_strecke_bringt_die_mischung_keinen_gummi(k) -> None:
    """Null mal Ansprechen ist null - fuer jede Mischung."""
    from rennmanager.kern import reifen as kern_reifen

    for m in kern_reifen.mischungen(k):
        assert gu.faktor(k, 0.0, m) == 1.0


def test_die_mischung_waescht_nicht_staerker_ab(k) -> None:
    """Abgewaschen wird vom Regen, nicht vom Reifen.

    Ohne diese Grenze wuerde ein Intermediate - Verschleiss 1,10 -
    staerker abwaschen als ein Regenreifen, und das ergaebe keinen Sinn.
    """
    from rennmanager.kern import reifen as kern_reifen

    m = {x.kuerzel: x for x in kern_reifen.mischungen(k)}
    ohne = gu.naechster_stand(k, 1000.0, "starkregen", 10)
    for kuerzel in ("W", "H", "I", "R"):
        assert gu.naechster_stand(k, 1000.0, "starkregen", 10, m[kuerzel]) == ohne


def test_ein_weiches_feld_gummiert_schneller_ein(k, zandvoort, mittel) -> None:
    """Der Effekt muss im fertigen Rennen ankommen, nicht nur in der Formel."""
    from rennmanager.kern import reifen as kern_reifen
    from rennmanager.kern import strategie as kern_strategie

    m = {x.kuerzel: x for x in kern_reifen.mischungen(k)}
    feld = rn.starterfeld(k)
    wetter = _trockenes_wetter(k, zandvoort, 10 * 130_000)

    def stand(kuerzel: str) -> float:
        strategien = tuple(
            kern_strategie.Strategie(mischungen=(m[kuerzel],), stopps=())
            for _ in feld
        )
        verlauf = rn.simuliere(
            k, zandvoort, feld, 10, Seedquelle(4711), mittel,
            wetter=wetter, strategien=strategien,
        )
        return verlauf.gummierung_zu(verlauf.dauer_ms)

    assert stand("W") > stand("M") > stand("H")


# -- Der Spieler sieht es (Entscheidung des Auftraggebers) ------------------
def test_die_anzeige_zeigt_den_gummistand(qtbot, k, zandvoort, mittel) -> None:
    pytest.importorskip("PySide6")
    from rennmanager.ui.rennseite import Rennseite

    feld = rn.starterfeld(k)
    wetter = _trockenes_wetter(k, zandvoort, 12 * 130_000)
    verlauf = rn.simuliere(
        k, zandvoort, feld, 12, Seedquelle(4711), mittel, wetter=wetter
    )
    seite = Rennseite(k, None, None)
    qtbot.addWidget(seite)
    seite.zeige_verlauf(verlauf, zandvoort, None, tabelle=None)
    seite._halte_an()

    seite._springe(0)
    assert "+0.00 %" in seite._wetteranzeige.text()
    seite._springe(verlauf.dauer_ms)
    assert "Strecke +" in seite._wetteranzeige.text()
    assert "+0.00 %" not in seite._wetteranzeige.text()


def test_das_qualifying_zeigt_den_gummistand(qtbot, k, zandvoort) -> None:
    pytest.importorskip("PySide6")
    from rennmanager.ui.qualifyingseite import Qualifyingseite

    session = ql.fahre(k, zandvoort, rn.starterfeld(k), Seedquelle(0))
    seite = Qualifyingseite(k)
    qtbot.addWidget(seite)
    seite.zeige_session(session)

    seite._springe(0)
    anfang = seite._gummianzeige.text()
    seite._springe(session.dauer_ms)
    assert seite._gummianzeige.text() != anfang, "Der Stand muss mitlaufen"


# -- Die gruene Strecke frisst Reifen (Punkt 90) ----------------------------
def test_die_gruene_strecke_frisst_am_meisten(k) -> None:
    """Bei null ist der Verschleissfaktor der Gruen-Wert, nicht 1,0.

    Anders als der Grip, der auf gruener Strecke genau 1,0 sein muss
    (der Anker aus GDD 9 haengt daran), faengt der Verschleiss oben an:
    Rauer Asphalt schmirgelt.
    """
    gruen = k.wert("strecke", "gummierung", "verschleiss_gruen")
    assert gu.verschleissfaktor(k, 0.0) == pytest.approx(gruen)
    assert gruen > 1.0


def test_der_verschleiss_faellt_und_saettigt(k) -> None:
    einstellung = k.wert("strecke", "gummierung")
    reihe = [gu.verschleissfaktor(k, n) for n in (0, 100, 300, 1000, 5000, 100_000)]
    assert reihe == sorted(reihe, reverse=True), "Er darf nie wieder steigen"
    assert reihe[-1] == pytest.approx(einstellung["verschleiss_voll"], abs=1e-6)
    assert all(wert >= einstellung["verschleiss_voll"] for wert in reihe)


def test_der_erste_stint_ist_rund_ein_fuenftel_kuerzer(k) -> None:
    """Die Entscheidung des Auftraggebers in einer Zahl.

    Ein 20-Runden-Stint zu Beginn soll rund 18 Runden werden, am Ende
    rund 21 - also ein Verhaeltnis um 1,2.
    """
    verhaeltnis = gu.verschleissfaktor(k, 0.0) / gu.verschleissfaktor(k, 100_000)
    assert 1.15 <= verhaeltnis <= 1.30


def test_die_mischung_aendert_am_asphalt_nichts(k) -> None:
    """Wie stark die Strecke schmirgelt, ist keine Eigenschaft des Reifens."""
    import inspect

    assert "mischung" not in inspect.signature(gu.verschleissfaktor).parameters


def test_der_stand_steigt_mit_der_feldgroesse(k) -> None:
    eines = gu.stand_je_runde(k, 1, "trocken")
    dreissig = gu.stand_je_runde(k, 30, "trocken")
    assert dreissig == pytest.approx(30 * eines)
    assert gu.stand_je_runde(k, 30, "regen") < 0.0


def test_ein_rennen_frisst_am_anfang_mehr_als_am_ende(k, zandvoort, mittel) -> None:
    """Der gefahrene Beleg: derselbe Satz, frueher mehr Abrieb je Runde.

    Gemessen wird der Reifenzustand des Fuehrenden nach jeder Runde -
    dazwischen darf kein Stopp liegen, deshalb faehrt das Feld ohne
    Strategie. Das Wetter muss **durchgehend trocken** sein: Ein
    Umschwung auf heiss hebt den Wetterfaktor und wuerde den
    Streckeneffekt ueberdecken.
    """
    for seed in range(200):
        wetter = kern_wetter.wuerfle(
            k, zandvoort.name, 20 * 130_000, 90_000, Seedquelle(seed)
        )
        if set(wetter.zustaende) == {"trocken"}:
            break
    else:  # pragma: no cover - Notbremse
        pytest.skip("Kein durchgehend trockener Wetterverlauf gefunden")

    verlauf = rn.simuliere(
        k, zandvoort, rn.starterfeld(k), 20, Seedquelle(4711), mittel,
        wetter=wetter,
    )
    marken = verlauf.protokolle[0].rundenende_ms
    zustand = [1.0] + [float(verlauf.reifen_zu(zeit)[0]) for zeit in marken]
    abrieb = [vorher - nachher for vorher, nachher in zip(zustand, zustand[1:], strict=False)]
    # Gemessen faellt er von 3,91 auf 3,41 Prozent je Runde - rund 13 %,
    # genau das Stueck der Kurve, das 546 Auto-Runden hergeben.
    assert abrieb[0] > abrieb[-1] * 1.10
    # Und er faellt durchgehend, nicht nur am Rand.
    assert abrieb == sorted(abrieb, reverse=True)
