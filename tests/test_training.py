"""Trainingsprogramme ueber mehrere Tage (Punkt 84).

Der Auftraggeber hat entschieden: Die nutzbaren Tage zwischen zwei
Rennen werden zur Waehrung, ein Programm laeuft fuenf bis zehn Tage und
nie ueber ein Rennwochenende hinweg, ein Abbruch zahlt anteilig, und
einen Bonus fuers Durchhalten gibt es nicht.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import entwicklung as kern_entwicklung
from rennmanager.kern import training as tr


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def mit_zeit(k):
    """Eine Faehigkeit, die wirklich einen Tag kostet."""
    return next(f for f in k.faehigkeiten if kern_entwicklung.braucht_tag(f))


@pytest.fixture(scope="module")
def ohne_zeit(k):
    return next(f for f in k.faehigkeiten if not kern_entwicklung.braucht_tag(f))


# -- Der Zuwachs ------------------------------------------------------------
def test_zehn_tage_bringen_anderthalb_buchungen(k) -> None:
    """Der Anreiz, ohne den niemand ein Programm buchen wuerde.

    Eine Einzelbuchung belegt denselben Platz fuer denselben Rennabstand
    und bringt einen Tageszuwachs. Brachte ein Zehn-Tage-Programm
    dasselbe, waere es strikt schlechter - es kann ja abbrechen.
    """
    wert = 50_000
    einzeln = kern_entwicklung.tageszuwachs(k, wert)
    anteil = k.wert("zeitmodell", "training", "tag_anteil")
    zehn = tr.zuwachs(k, wert, 10)
    assert zehn > einzeln, f"{zehn} <= {einzeln} - das Programm lohnt sich nicht"
    # 10 * 0,15 = 1,5 Buchungen, auf ganze Kaufschritte abgerundet.
    schritt = k.wert("zeitmodell", "kaufschritt")
    erwartet = int(10 * einzeln * anteil) // schritt * schritt
    assert zehn == erwartet


def test_der_zuwachs_waechst_mit_den_tagen(k) -> None:
    wert = 50_000
    reihe = [tr.zuwachs(k, wert, tage) for tage in range(0, 11)]
    assert reihe[0] == 0
    assert reihe == sorted(reihe)
    assert reihe[10] > reihe[5]


def test_der_zuwachs_bleibt_auf_ganzen_kaufschritten(k) -> None:
    """Bruchteile eines +10-Schritts gibt es nicht (GDD 9)."""
    schritt = k.wert("zeitmodell", "kaufschritt")
    for wert in (0, 1_000, 50_000, 99_000):
        for tage in range(0, 11):
            assert tr.zuwachs(k, wert, tage) % schritt == 0


# -- Die Spanne -------------------------------------------------------------
def test_die_spanne_kommt_aus_der_konfiguration(k) -> None:
    kuerzeste, laengste = tr.spanne(k)
    assert kuerzeste == k.wert("zeitmodell", "training", "min_tage")
    assert laengste == k.wert("zeitmodell", "training", "max_tage")
    assert 0 < kuerzeste <= laengste


def test_ein_programm_passt_immer_in_einen_rennabstand(k) -> None:
    """Entscheidung des Auftraggebers: nie ueber ein Rennwochenende hinweg.

    Zwischen zwei Rennen liegen zehn nutzbare Tage; waere ``max_tage``
    groesser, reichte ein Programm darueber hinaus.
    """
    from rennmanager.kern import kalender as kern_kalender

    saison = kern_kalender.erzeuge(k, 2026)
    renntage = [t.datum for t in saison.tage if t.art is kern_kalender.Tagesart.RENNEN]
    kuerzester = min(
        len(saison.nutzbare_tage(von, bis))
        for von, bis in zip(renntage, renntage[1:], strict=False)
    )
    assert tr.spanne(k)[1] <= kuerzester, (
        f"max_tage {tr.spanne(k)[1]} passt nicht in {kuerzester} nutzbare Tage"
    )


@pytest.mark.parametrize("tage", [0, 1, 4, 11, 30])
def test_ausserhalb_der_spanne_gibt_es_kein_programm(k, mit_zeit, tage: int) -> None:
    with pytest.raises(tr.TrainingsFehler):
        tr.plane(k, mit_zeit, 50_000, tage)


def test_ohne_zeitanteil_gibt_es_kein_programm(k, ohne_zeit) -> None:
    """Wer sofort kaufen kann, braucht keine Tage."""
    with pytest.raises(tr.TrainingsFehler):
        tr.plane(k, ohne_zeit, 50_000, 10)


# -- Was ein Programm kostet und bringt -------------------------------------
def test_das_programm_kostet_wie_die_einzelschritte(k, mit_zeit) -> None:
    """Je +10-Schritt derselbe Preis - ein Programm bringt nur mehr davon."""
    wert = 50_000
    programm = tr.plane(k, mit_zeit, wert, 10)
    schritt = k.wert("zeitmodell", "kaufschritt")
    geld = erfahrung = 0
    for stelle in range(programm.von, programm.nach, schritt):
        einzeln = kern_entwicklung.schrittkosten(k, mit_zeit, stelle)
        geld += einzeln[0]
        erfahrung += einzeln[1]
    assert (programm.geld, programm.erfahrung) == (geld, erfahrung)
    assert programm.braucht_tag


# -- Der Abbruch ------------------------------------------------------------
def test_ein_abbruch_zahlt_die_geleisteten_tage(k, mit_zeit) -> None:
    """Entscheidung des Auftraggebers: anteilig, was gelaufen ist."""
    wert = 50_000
    nach_neun = tr.abrechnung(k, mit_zeit, wert, 9)
    voll = tr.plane(k, mit_zeit, wert, 10)
    assert nach_neun.nach - nach_neun.von == tr.zuwachs(k, wert, 9)
    assert nach_neun.nach < voll.nach


def test_ohne_geleisteten_tag_bringt_der_abbruch_nichts(k, mit_zeit) -> None:
    leer = tr.abrechnung(k, mit_zeit, 50_000, 0)
    assert leer.nach == leer.von
    assert (leer.geld, leer.erfahrung) == (0, 0)


def test_ein_durchgelaufenes_programm_zahlt_wie_geplant(k, mit_zeit) -> None:
    """Kein Bonus fuers Durchhalten - die Abrechnung ist dieselbe Rechnung."""
    wert = 50_000
    assert tr.abrechnung(k, mit_zeit, wert, 10).nach == tr.plane(k, mit_zeit, wert, 10).nach


# -- Das Programm selbst ----------------------------------------------------
def test_ein_programm_zaehlt_seine_tage_mit() -> None:
    import datetime as dt

    tage = tuple(dt.date(2026, 3, 2) + dt.timedelta(days=n) for n in range(5))
    programm = tr.Programm(faehigkeit="f", platz="fahrer", tage=tage)
    assert (programm.dauer, programm.geleistet, programm.laeuft) == (5, 0, True)
    for erwartet in range(1, 6):
        programm = programm.mit_tag()
        assert programm.geleistet == erwartet
    assert not programm.laeuft
    # Ueber die Dauer hinaus zaehlt nichts mehr mit.
    assert programm.mit_tag().geleistet == 5
    assert programm.letzter_tag == tage[-1]


# -- In der Karriere --------------------------------------------------------
def _karriere(k):
    from rennmanager.kern import karriere as kk
    from rennmanager.kern.zufall import Seedquelle

    return kk.beginne(k, 2026, liga=20, fahrer=(1, 2, 3, 4), seedquelle=Seedquelle(7))


def _zeitfaehigkeit(k, karriere):
    """Eine Faehigkeit mit Zeitanteil, die gerade nicht gesperrt ist."""
    gesperrt = karriere.gesperrt()
    return next(
        f.schluessel
        for f in k.faehigkeiten
        if kern_entwicklung.braucht_tag(f) and f.schluessel not in gesperrt
    )


def test_die_freien_tage_sind_der_vorrat(k) -> None:
    """Bis Punkt 84 wurden sie angezeigt und von nichts verbraucht."""
    c = _karriere(k)
    vorher = len(c.freie_trainingstage())
    assert vorher > 0
    c.starte_programm(_zeitfaehigkeit(k, c), 5)
    assert len(c.freie_trainingstage()) == vorher - 5


def test_ein_programm_belegt_den_platz(k) -> None:
    from rennmanager.kern import karriere as kk

    c = _karriere(k)
    name = _zeitfaehigkeit(k, c)
    c.starte_programm(name, 5)
    assert c.platz_fuer(name) in c.belegt
    # Und ein zweites auf demselben Platz geht nicht.
    with pytest.raises(kk.KarriereFehler):
        c.starte_programm(name, 5)


def test_mehr_tage_als_frei_gibt_es_nicht(k) -> None:
    from rennmanager.kern import karriere as kk

    c = _karriere(k)
    name = _zeitfaehigkeit(k, c)
    frei = len(c.freie_trainingstage())
    if frei >= tr.spanne(k)[1]:
        pytest.skip("Genug Tage frei - dieser Fall braucht einen knappen Vorrat")
    with pytest.raises(kk.KarriereFehler):
        c.starte_programm(name, tr.spanne(k)[1])


def test_ein_durchgelaufenes_programm_hebt_den_wert(k) -> None:
    """Der Kern der Sache: Tage rein, Wert raus."""
    from rennmanager.kern import karriere as kk

    c = _karriere(k)
    name = _zeitfaehigkeit(k, c)
    vorher = c.wert(name)
    programm = c.starte_programm(name, 5)
    erwartet = tr.zuwachs(k, vorher, 5)

    # So viele Tage weiter, bis das Programm vorbei ist.
    for _ in range(40):
        if not c.programme.get(c.fahrernummer):
            break
        try:
            c.tag_weiter()
        except kk.KarriereFehler:
            break

    assert not c.programme.get(c.fahrernummer), "Das Programm laeuft noch"
    assert c.wert(name) == vorher + erwartet, (
        f"{name}: {vorher} -> {c.wert(name)}, erwartet +{erwartet}"
    )
    assert programm.dauer == 5
    # Der Platz ist wieder frei.
    assert c.platz_fuer(name) not in c.belegt


def test_ein_programm_ueberlebt_kein_rennwochenende(k) -> None:
    """Entscheidung des Auftraggebers: nie darueber hinweg.

    Am Renntag werden die Plaetze frei (Punkt 69); ein Programm darf dann
    nicht als Leiche stehenbleiben.
    """
    from rennmanager.kern import karriere as kk
    from rennmanager.kern.kalender import Tagesart

    c = _karriere(k)
    c.starte_programm(_zeitfaehigkeit(k, c), 5)
    for _ in range(60):
        war_renntag = c.tag.art is Tagesart.RENNEN
        try:
            c.tag_weiter()
        except kk.KarriereFehler:
            break
        if war_renntag:
            break
    assert not any(c.programme.values()), "Nach dem Renntag ist kein Programm mehr offen"


def test_ein_programm_uebersteht_speichern_und_laden(k, tmp_path) -> None:
    """Sonst waeren die eingesetzten Tage nach dem Laden still verloren."""
    from rennmanager.kern import spielstand as sp

    c = _karriere(k)
    name = _zeitfaehigkeit(k, c)
    c.starte_programm(name, 5)
    c.tag_weiter()
    vorher = list(c.laufende_programme)
    assert vorher, "Das Programm muss noch laufen"

    from rennmanager.kern import statistik as kern_statistik
    from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
    from rennmanager.kern import welt as kern_welt
    from rennmanager.kern.zufall import Seedquelle

    welt = kern_welt.erzeuge(k, Seedquelle(7).zweig("welt"), spielerliga=20)
    stand = sp.aus_teilen(
        seed=7,
        saisonjahr=2026,
        welt=welt,
        karriere=c,
        tabellen={},
        statistik=kern_statistik.Statistik(k),
        kenntnis=kern_streckenkenntnis.Streckenkenntnis(k),
        gefahrene_rennen=0,
    )
    datei = sp.speichere(stand, tmp_path / "stand.sqlite")
    geladen = sp.lade(k, datei)

    nachher = geladen.karriere.programme.get(c.fahrernummer, [])
    assert nachher == vorher, f"{nachher} != {vorher}"
    # Und der Platz ist nach dem Laden weiter belegt.
    assert c.platz_fuer(name) in geladen.karriere.belegt
