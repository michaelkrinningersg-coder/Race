"""Transfermarkt: Vertraege, Marktwert, Abloese und die Antwort des Fahrers.

Punkt 39 hat den Spieler zum Teamchef mit vier Fahrern gemacht; damit
braucht er einen Weg, Fahrer zu holen. Das steht nicht im GDD - die
Regeln kommen alle aus der Abstimmung mit dem Auftraggeber:

* Transferfenster im Winter, Verpflichtung kostet **Gehalt plus Abloese**.
* Der Fahrer **waegt ab**: Liga, Auto und Geld gegeneinander.
* Ein neuer Fahrer bringt ein **leeres Auto** mit - beim Spieler in
  der untersten Liga ist das Auto also fast immer ein Minus, und Geld muss es
  ausgleichen.
"""

from dataclasses import replace

import pytest

from rennmanager.kern import talent as kern_talent
from rennmanager.kern import transfer as tf
from rennmanager.kern import welt as kern_welt
from rennmanager.kern.auto import gesamtwert
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade


@pytest.fixture(scope="module")
def k():
    return lade()


@pytest.fixture(scope="module")
def quelle():
    return Seedquelle(4711)


@pytest.fixture(scope="module")
def welt(k, quelle):
    return kern_welt.erzeuge(k, quelle.zweig("welt"), spielerliga=10)


@pytest.fixture(scope="module")
def jahr(k):
    return k.wert("kalender", "startjahr") + 3


# -- Vertraege --------------------------------------------------------------
def test_jeder_vertrag_endet_irgendwann(k, quelle, jahr):
    for nummer in range(0, 600, 37):
        ende = tf.vertragsende(k, nummer, quelle, jahr)
        assert ende >= jahr


def test_dieselbe_frage_gibt_dieselbe_antwort(k, quelle, jahr):
    """Der Vertrag haengt am Seed, nicht an der Aufrufreihenfolge (GDD 15)."""
    erst = tf.vertragsende(k, 42, quelle, jahr)
    tf.vertragsende(k, 7, quelle, jahr)
    tf.vertragsende(k, 42, quelle, jahr + 5)
    assert tf.vertragsende(k, 42, quelle, jahr) == erst


def test_die_laufzeit_bleibt_in_der_spanne(k, quelle):
    """Zwischen laufzeit_min und laufzeit_max Saisons, rollierend."""
    einstellung = k.wert("transfer")
    start = k.wert("kalender", "startjahr")
    for nummer in range(0, 200, 13):
        erstes_ende = tf.vertragsende(k, nummer, quelle, start)
        dauer = erstes_ende - start
        assert einstellung["laufzeit_min"] <= dauer <= einstellung["laufzeit_max"]


def test_in_jedem_winter_ist_ein_teil_des_feldes_frei(k, welt, quelle, jahr):
    frei = [
        f.nummer for f in welt.fahrer if tf.ist_frei(k, f.nummer, quelle, jahr)
    ]
    anteil = len(frei) / len(welt.fahrer)
    # Bei Laufzeiten von 1 bis 4 Saisons wird im Mittel jeder Vierte frei.
    assert 0.10 < anteil < 0.60, f"{anteil:.0%} des Feldes frei"


def test_frei_heisst_restlaufzeit_null(k, welt, quelle, jahr):
    for f in welt.fahrer[:80]:
        rest = tf.restlaufzeit(k, f.nummer, quelle, jahr)
        assert (rest == 0) == tf.ist_frei(k, f.nummer, quelle, jahr)


# -- Was ein Fahrer kostet --------------------------------------------------
def marktwert_von(k, welt, quelle, nummer, jahr):
    fahrer = welt.fahrer[nummer]
    talent = kern_talent.talent(k, nummer, fahrer.geburtstag, quelle)
    alter = tf._alter(k, fahrer, jahr)
    return tf.marktwert(k, fahrer, talent, alter)


def test_der_bessere_fahrer_kostet_mehr(k, welt, quelle, jahr):
    liga1 = sorted(welt.liga(1), key=lambda f: -gesamtwert(k, f.auto))
    liga_unten = sorted(welt.liga(10), key=lambda f: -gesamtwert(k, f.auto))
    oben = marktwert_von(k, welt, quelle, liga1[0].nummer, jahr)
    unten = marktwert_von(k, welt, quelle, liga_unten[-1].nummer, jahr)
    assert oben > unten


def test_jeder_marktwert_ist_positiv(k, welt, quelle, jahr):
    for f in welt.fahrer[:100]:
        assert marktwert_von(k, welt, quelle, f.nummer, jahr) > 0


def test_ein_freier_fahrer_kostet_keine_abloese(k):
    assert tf.abloese(k, 1_000_000, 0) == 0
    assert tf.abloese(k, 1_000_000, 1) > 0


def test_die_abloese_waechst_mit_der_restlaufzeit(k):
    werte = [tf.abloese(k, 500_000, rest) for rest in range(5)]
    assert werte == sorted(werte)
    assert werte[4] > werte[1]


def test_das_angebot_nennt_gehalt_laufzeit_und_abloese(k, welt, quelle, jahr):
    nummer = welt.liga(10)[0].nummer
    eines = tf.angebot(k, welt, nummer, jahr, quelle)
    assert eines.fahrer == nummer
    assert eines.gehalt > 0
    assert eines.laufzeit >= k.wert("transfer", "laufzeit_min")
    assert eines.abloese >= 0
    assert eines.gesamtkosten == eines.abloese + eines.gehalt * eines.laufzeit


def test_ein_eigenes_gebot_setzt_den_marktwert_ausser_kraft(k, welt, quelle, jahr):
    nummer = welt.liga(10)[0].nummer
    ueblich = tf.angebot(k, welt, nummer, jahr, quelle)
    doppelt = tf.angebot(k, welt, nummer, jahr, quelle, gehalt=ueblich.gehalt * 2)
    assert doppelt.gehalt == ueblich.gehalt * 2
    # Die Abloese haengt am Marktwert, nicht am Gebot.
    assert doppelt.abloese == ueblich.abloese


# -- Ob er will -------------------------------------------------------------
def antwort_auf(k, welt, quelle, nummer, jahr, *, liga, autowert, gehalt, bekannt=0.0):
    eines = tf.angebot(k, welt, nummer, jahr, quelle, gehalt=gehalt)
    return tf.pruefe(k, welt, nummer, eines, liga, autowert, jahr, quelle, bekannt)


def test_niemand_geht_freiwillig_eine_liga_tiefer(k, welt, quelle, jahr):
    fahrer = welt.liga(5)[0]
    wert = gesamtwert(k, fahrer.auto)
    marktwert = marktwert_von(k, welt, quelle, fahrer.nummer, jahr)
    antwort = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=10, autowert=wert, gehalt=marktwert,
    )
    assert not antwort.angenommen
    assert "tiefere Liga" in antwort.grund


def test_eine_hoehere_liga_zieht(k, welt, quelle, jahr):
    fahrer = welt.liga(10)[0]
    marktwert = marktwert_von(k, welt, quelle, fahrer.nummer, jahr)
    antwort = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=1, autowert=gesamtwert(k, fahrer.auto), gehalt=marktwert,
    )
    assert antwort.angenommen


def test_geld_gleicht_ein_schwaecheres_auto_aus(k, welt, quelle, jahr):
    """Der Auftraggeber: Er waegt ab - also muss Geld etwas bewegen."""
    fahrer = welt.liga(10)[0]
    marktwert = marktwert_von(k, welt, quelle, fahrer.nummer, jahr)
    schwach = gesamtwert(k, fahrer.auto) * 0.5

    knausrig = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=fahrer.liga, autowert=schwach, gehalt=marktwert,
    )
    grosszuegig = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=fahrer.liga, autowert=schwach, gehalt=marktwert * 6,
    )
    assert not knausrig.angenommen
    assert grosszuegig.ueberzeugung > knausrig.ueberzeugung


def test_wer_bekannter_ist_verlangt_mehr(k, welt, quelle, jahr):
    """Punkt 5: Die Popularitaet hebt den Anspruch."""
    fahrer = welt.liga(10)[0]
    marktwert = marktwert_von(k, welt, quelle, fahrer.nummer, jahr)
    unbekannt = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=fahrer.liga - 1, autowert=gesamtwert(k, fahrer.auto),
        gehalt=marktwert, bekannt=0.0,
    )
    star = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=fahrer.liga - 1, autowert=gesamtwert(k, fahrer.auto),
        gehalt=marktwert, bekannt=1.0,
    )
    assert star.ueberzeugung < unbekannt.ueberzeugung


def test_der_grund_nennt_den_schwaechsten_punkt(k, welt, quelle, jahr):
    fahrer = welt.liga(10)[0]
    marktwert = marktwert_von(k, welt, quelle, fahrer.nummer, jahr)
    zu_wenig_geld = antwort_auf(
        k, welt, quelle, fahrer.nummer, jahr,
        liga=fahrer.liga, autowert=gesamtwert(k, fahrer.auto),
        gehalt=int(marktwert * 0.5),
    )
    assert not zu_wenig_geld.angenommen
    assert "Marktwert" in zu_wenig_geld.grund or "Angebot" in zu_wenig_geld.grund


# -- Wer zu haben ist -------------------------------------------------------
def test_die_eigenen_vier_stehen_nicht_auf_dem_markt(k, welt, quelle, jahr):
    frei = tf.verfuegbare(k, welt, jahr, quelle)
    eigene = {f.nummer for f in welt.spielerfahrer}
    assert eigene
    assert not (set(frei) & eigene)


def test_newgens_sind_immer_zu_haben(k, welt, quelle, jahr):
    """Wer eben erst aufgetaucht ist, hat noch nirgends unterschrieben."""
    irgendwer = welt.liga(1)[0].nummer
    ohne = tf.verfuegbare(k, welt, jahr, quelle)
    mit = tf.verfuegbare(k, welt, jahr, quelle, newgens=(irgendwer,))
    assert irgendwer in mit
    assert set(ohne) <= set(mit)


def test_die_liste_ist_sortiert_und_doppelfrei(k, welt, quelle, jahr):
    frei = tf.verfuegbare(k, welt, jahr, quelle)
    assert list(frei) == sorted(set(frei))


def test_wer_unter_vertrag_steht_kostet_eine_abloese(k, welt, quelle, jahr):
    """Nicht unerreichbar, nur teurer - so ist es abgestimmt."""
    gebunden = [
        f.nummer
        for f in welt.fahrer
        if not tf.ist_frei(k, f.nummer, quelle, jahr)
        and f.nummer not in {e.nummer for e in welt.spielerfahrer}
    ]
    assert gebunden
    eines = tf.angebot(k, welt, gebunden[0], jahr, quelle)
    assert eines.abloese > 0


def test_ein_freier_fahrer_ist_im_angebot_abloesefrei(k, welt, quelle, jahr):
    frei = tf.verfuegbare(k, welt, jahr, quelle)
    assert frei
    eines = tf.angebot(k, welt, frei[0], jahr, quelle)
    assert eines.abloese == 0


def test_das_talent_hebt_den_wert_eines_jungen_fahrers(k, welt, quelle, jahr):
    """Der Marktwert wiegt Koennen und Potential - nicht nur Koennen."""
    fahrer = welt.liga(10)[0]
    alter = tf._alter(k, fahrer, jahr)
    echtes = kern_talent.talent(k, fahrer.nummer, fahrer.geburtstag, quelle)
    bescheiden = replace(echtes, potential={s: 1 for s in echtes.potential})
    assert tf.marktwert(k, fahrer, echtes, alter) > tf.marktwert(
        k, fahrer, bescheiden, alter
    )
