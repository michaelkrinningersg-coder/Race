"""Boxengasse und Boxenstopp (Punkt 39).

Die Boxengasse ist nicht eingetragen, sondern **abgeleitet**: Sie liegt
auf der Geraden um Start und Ziel, ist zwischen 500 und 750 Metern lang
und ihre Durchfahrt kostet hoechstens 50 Prozent einer Rundenzeit. Die
Grenze gilt der Durchfahrt allein - die Standzeit ist Sache der
Mannschaft, nicht der Strecke.
"""

import pytest

from rennmanager.kern import boxenstopp as bx
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.auto import gleichverteilt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade


@pytest.fixture(scope="module")
def k():
    return lade()


@pytest.fixture(scope="module")
def strecken(k):
    return kern_strecke.lade_alle(k)


@pytest.fixture(scope="module")
def auto(k):
    return gleichverteilt(k, k.wert("skala", "referenz"))


def test_jede_strecke_hat_eine_boxengasse(k, strecken):
    for strecke in strecken:
        von, bis = bx.abschnitt(k, strecke)
        assert 0 <= von < len(strecke.punkte)
        assert 0 <= bis < len(strecke.punkte)


def test_die_boxengasse_laeuft_ueber_die_ziellinie(k, strecken):
    """Sie zweigt vor Start und Ziel ab und muendet danach wieder ein."""
    for strecke in strecken:
        von, bis = bx.abschnitt(k, strecke)
        assert von > bis, f"{strecke.name}: Abschnitt liegt im Rundeninneren"


def test_die_laenge_bleibt_im_band(k, strecken):
    """500 bis 750 Meter auf allen zwanzig Strecken.

    Die Toleranz ist ein Streckenpunkt: Die Boxengasse wird in Punkten
    abgesteckt, und der letzte darf das Band um seinen eigenen Abstand
    ueberschreiten.
    """
    for strecke in strecken:
        laenge = bx.laenge_m(k, strecke)
        rand = strecke.punktabstand_m
        assert 500 - rand <= laenge <= 750 + rand, f"{strecke.name}: {laenge:.0f} m"


def test_die_durchfahrt_bleibt_unter_dem_rundenanteil(k, strecken, auto):
    """Auf allen zwanzig Strecken, seit die Grenze bei 50 Prozent liegt."""
    anteil = k.wert("boxenstopp", "max_anteil_rundenzeit")
    grenzen = kern_tempo.grenzen_aus(k, auto)
    for strecke in strecken:
        runde = bx.referenzrundenzeit_ms(k, strecke)
        verlust = bx.durchfahrtsverlust_ms(k, strecke, grenzen)
        assert verlust <= anteil * runde * 1.02, (
            f"{strecke.name}: {verlust / runde:.0%} der Rundenzeit"
        )


def test_die_durchfahrt_kostet_immer_zeit(k, strecken, auto):
    grenzen = kern_tempo.grenzen_aus(k, auto)
    for strecke in strecken:
        assert bx.durchfahrtsverlust_ms(k, strecke, grenzen) > 0


def test_das_limit_gilt_nur_in_der_boxengasse(k, strecken, auto):
    strecke = strecken[0]
    grenzen = kern_tempo.grenzen_aus(k, auto)
    frei = kern_tempo.kurvenlimit(strecke, grenzen)
    gedeckelt = bx.gedeckeltes_limit(k, strecke, grenzen)
    deckel = k.wert("boxenstopp", "limit_kmh") / 3.6
    von, bis = bx.abschnitt(k, strecke)
    assert (gedeckelt[von:] <= deckel + 1e-9).all()
    assert (gedeckelt[:bis] <= deckel + 1e-9).all()
    # Ausserhalb bleibt alles, wie es war.
    assert (gedeckelt[bis:von] == frei[bis:von]).all()


def test_die_standzeit_bleibt_in_der_spanne(k):
    """Sechs bis zwoelf Sekunden - so hat es der Auftraggeber gesetzt."""
    unten = k.wert("boxenstopp", "standzeit_min_s") * 1000
    oben = k.wert("boxenstopp", "standzeit_max_s") * 1000
    werte = [bx.standzeit_ms(k, Seedquelle(n)) for n in range(200)]
    assert all(unten <= w <= oben for w in werte)
    assert min(werte) < (unten + oben) / 2 < max(werte)


def test_die_standzeit_haengt_am_seed(k):
    assert bx.standzeit_ms(k, Seedquelle(7)) == bx.standzeit_ms(k, Seedquelle(7))
    assert bx.standzeit_ms(k, Seedquelle(7)) != bx.standzeit_ms(k, Seedquelle(8))


def test_die_mittlere_standzeit_liegt_in_der_mitte(k):
    """Neun Sekunden - damit rechnet die Vorausberechnung der Strategie."""
    unten = k.wert("boxenstopp", "standzeit_min_s") * 1000
    oben = k.wert("boxenstopp", "standzeit_max_s") * 1000
    assert bx.mittlere_standzeit_ms(k) == pytest.approx((unten + oben) / 2, abs=1)
    assert bx.mittlere_standzeit_ms(k) == 9_000


def test_das_anfahren_kostet_die_halbe_beschleunigungszeit(k, auto):
    """v/a waere die ganze, rollend waere es v/(2a) - bleibt die Haelfte."""
    grenzen = kern_tempo.grenzen_aus(k, auto)
    tempo = k.wert("boxenstopp", "limit_kmh") / 3.6
    erwartet = 1000.0 * tempo / (2.0 * grenzen.laengs)
    assert bx.anfahrverlust_ms(k, grenzen) == pytest.approx(erwartet, abs=1)


def test_das_bremsen_kostet_die_halbe_bremszeit(k, auto):
    """Dasselbe mit der Bremsgrenze: Der Halt kostet an beiden Enden."""
    grenzen = kern_tempo.grenzen_aus(k, auto)
    tempo = k.wert("boxenstopp", "limit_kmh") / 3.6
    erwartet = 1000.0 * tempo / (2.0 * grenzen.brems)
    assert bx.bremsverlust_ms(k, grenzen) == pytest.approx(erwartet, abs=1)


def test_der_halt_ist_bremsen_plus_anfahren(k, auto):
    grenzen = kern_tempo.grenzen_aus(k, auto)
    assert bx.haltverlust_ms(k, grenzen) == (
        bx.bremsverlust_ms(k, grenzen) + bx.anfahrverlust_ms(k, grenzen)
    )


def test_ein_auto_mit_besseren_bremsen_verliert_weniger(k, auto):
    """Gerechnet wird mit der Grenze dieses Autos, nicht mit einer Pauschale."""
    from dataclasses import replace

    grenzen = kern_tempo.grenzen_aus(k, auto)
    staerker = replace(grenzen, brems=grenzen.brems * 1.5)
    assert bx.bremsverlust_ms(k, staerker) < bx.bremsverlust_ms(k, grenzen)


def test_der_ganze_stopp_ist_die_summe_seiner_teile(k, strecken, auto):
    strecke = strecken[0]
    grenzen = kern_tempo.grenzen_aus(k, auto)
    quelle = Seedquelle(3)
    gesamt = bx.stoppverlust_ms(k, strecke, grenzen, quelle)
    assert gesamt == (
        bx.durchfahrtsverlust_ms(k, strecke, grenzen)
        + bx.standzeit_ms(k, quelle)
        + bx.haltverlust_ms(k, grenzen)
    )


def test_der_deckel_macht_nirgends_schneller(k, strecken, auto):
    """In der Boxengasse wird nie schneller gefahren als auf der Strecke."""
    grenzen = kern_tempo.grenzen_aus(k, auto)
    for strecke in strecken:
        frei = kern_tempo.kurvenlimit(strecke, grenzen)
        gedeckelt = bx.gedeckeltes_limit(k, strecke, grenzen)
        assert (gedeckelt <= frei + 1e-9).all(), strecke.name


def test_wo_die_strecke_schon_langsam_ist_gilt_ihr_tempo_minus_abzug(k, strecken, auto):
    """80 km/h gilt nur, wo die Strecke ueberhaupt schneller waere.

    Sonst gilt das Streckentempo minus 5 Prozent. In Liga 1 kommt das nie
    vor - die Boxengasse liegt auf der Geraden um Start und Ziel -, in den
    unteren Ligen schon: Dort faehrt das schwaechste Auto dort
    stellenweise nur 29 km/h.
    """
    import numpy as np

    abzug = 1.0 - k.wert("boxenstopp", "abzug_unter_limit")
    deckel = k.wert("boxenstopp", "limit_kmh") / 3.6
    grenzen = kern_tempo.grenzen_aus(k, auto)
    getroffen = 0
    for strecke in strecken:
        frei = kern_tempo.kurvenlimit(strecke, grenzen)
        gedeckelt = bx.gedeckeltes_limit(k, strecke, grenzen)
        von, bis = bx.abschnitt(k, strecke)
        anzahl = len(strecke.art_je_punkt)
        stellen = np.r_[np.arange(von, anzahl), np.arange(0, bis)]
        langsam = stellen[frei[stellen] < deckel]
        schnell = stellen[frei[stellen] >= deckel]
        assert np.allclose(gedeckelt[langsam], frei[langsam] * abzug)
        assert np.allclose(gedeckelt[schnell], deckel)
        getroffen += len(langsam)
    # Mit dem Referenzauto liegt die ganze Gasse ueber dem Limit.
    assert getroffen == 0


def test_in_der_untersten_liga_greift_der_abzug(k, strecken):
    """Dort ist das Auto stellenweise langsamer als 80 km/h."""
    import numpy as np

    from rennmanager.kern import rennen as kern_rennen

    feld = kern_rennen.starterfeld(k, 20)
    schwaechstes = min((t.auto for t in feld), key=lambda a: sum(a.werte.values()))
    grenzen = kern_tempo.grenzen_aus(k, schwaechstes)
    deckel = k.wert("boxenstopp", "limit_kmh") / 3.6
    getroffen = 0
    for strecke in strecken:
        frei = kern_tempo.kurvenlimit(strecke, grenzen)
        von, bis = bx.abschnitt(k, strecke)
        anzahl = len(strecke.art_je_punkt)
        stellen = np.r_[np.arange(von, anzahl), np.arange(0, bis)]
        getroffen += int((frei[stellen] < deckel).sum())
    assert getroffen > 0, "In Liga 20 muss es Stellen unter dem Limit geben"


def test_auch_in_der_untersten_liga_kostet_die_durchfahrt(k, strecken):
    """Ohne den Abzug waere ein Stopp dort an manchen Stellen umsonst."""
    from rennmanager.kern import rennen as kern_rennen

    feld = kern_rennen.starterfeld(k, 20)
    schwaechstes = min((t.auto for t in feld), key=lambda a: sum(a.werte.values()))
    grenzen = kern_tempo.grenzen_aus(k, schwaechstes)
    for strecke in strecken:
        assert bx.durchfahrtsverlust_ms(k, strecke, grenzen) > 0, strecke.name
