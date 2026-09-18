"""Generationswechsel: Ruecktritte, Nachruecken, Newgens, Entwicklung (Punkt 35).

Die Regeln kommen vom Auftraggeber: Jeder Fahrer hat ein gewuerfeltes
Ruecktrittsalter, je Winter tritt hoechstens eine feste Zahl ab, die
frei gewordenen Plaetze werden **von unten nach Platzierung** aufgefuellt,
und die Newgens steigen in Liga 20 ein. Entwickelt wird jeder nach
**seinem eigenen Talent** - der Ligakorridor aus GDD 9 gilt nur noch beim
Weltstart.
"""

import pytest

from rennmanager.kern import generationen as gen
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import welt as kern_welt
from rennmanager.kern.auto import gesamtwert
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade


@pytest.fixture(scope="module")
def k():
    return lade()


@pytest.fixture(scope="module")
def quelle():
    return Seedquelle(2024)


@pytest.fixture(scope="module")
def welt(k, quelle):
    return kern_welt.erzeuge(k, quelle.zweig("welt"), spielerliga=20)


@pytest.fixture(scope="module")
def startjahr(k):
    return k.wert("kalender", "startjahr")


# -- Ruecktrittsalter -------------------------------------------------------
def test_das_ruecktrittsalter_bleibt_in_der_spanne(k, quelle):
    unten = k.wert("generationen", "ruecktritt_min")
    oben = k.wert("generationen", "ruecktritt_max")
    werte = [gen.ruecktrittsalter(k, n, quelle) for n in range(300)]
    assert all(unten <= w <= oben for w in werte)
    assert len(set(werte)) > 1, "Alle hoeren im selben Alter auf"


def test_es_steht_von_anfang_an_fest(k, quelle):
    """Aus dem Seed statt gespeichert - derselbe Seed, dieselbe Welt (GDD 15)."""
    erst = gen.ruecktrittsalter(k, 17, quelle)
    gen.ruecktrittsalter(k, 99, quelle)
    assert gen.ruecktrittsalter(k, 17, quelle) == erst


def test_ein_anderer_seed_gibt_andere_karrieren(k):
    eine = [gen.ruecktrittsalter(k, n, Seedquelle(1)) for n in range(50)]
    andere = [gen.ruecktrittsalter(k, n, Seedquelle(2)) for n in range(50)]
    assert eine != andere


# -- Wer faellig ist --------------------------------------------------------
def test_am_weltstart_ist_kaum_jemand_faellig(k, welt, quelle, startjahr):
    dran = gen.faellige(k, welt, startjahr, quelle)
    assert len(dran) < len(welt.fahrer) // 4


def test_spaeter_werden_es_mehr(k, welt, quelle, startjahr):
    frueh = len(gen.faellige(k, welt, startjahr, quelle))
    spaet = len(gen.faellige(k, welt, startjahr + 15, quelle))
    assert spaet > frueh


def test_auch_die_eigenen_vier_koennen_faellig_werden(k, welt, quelle, startjahr):
    """Seit der Spieler Teamchef ist, altern seine Fahrer wie alle anderen."""
    eigene = {f.nummer for f in welt.spielerfahrer}
    assert eigene
    ueber_die_jahre = set()
    for jahr in range(startjahr, startjahr + 40):
        ueber_die_jahre.update(f.nummer for f in gen.faellige(k, welt, jahr, quelle))
    assert eigene & ueber_die_jahre, "Die eigenen Fahrer hoeren nie auf"


def test_wer_faellig_ist_hat_sein_alter_erreicht(k, welt, quelle, startjahr):
    jahr = startjahr + 10
    stichtag = kern_kalender.saisonstart(k, jahr)
    for fahrer in gen.faellige(k, welt, jahr, quelle):
        assert fahrer.alter_am(stichtag) >= gen.ruecktrittsalter(k, fahrer.nummer, quelle)


# -- Ruecktritte ------------------------------------------------------------
def test_die_obergrenze_je_winter_wird_gehalten(k, welt, quelle, startjahr):
    hoechstens = k.wert("generationen", "ruecktritte_je_saison_max")
    for jahr in (startjahr, startjahr + 10, startjahr + 25):
        gehen, _ = gen.ruecktritte(k, welt, jahr, quelle)
        assert len(gehen) <= hoechstens


def test_wer_warten_muss_wird_gezaehlt(k, welt, quelle, startjahr):
    jahr = startjahr + 25
    gehen, aufgeschoben = gen.ruecktritte(k, welt, jahr, quelle)
    dran = gen.faellige(k, welt, jahr, quelle)
    assert len(gehen) + aufgeschoben == len(dran)


def test_die_aeltesten_gehen_zuerst(k, welt, quelle, startjahr):
    """Wer am weitesten ueber seiner Grenze ist, hoert zuerst auf."""
    jahr = startjahr + 25
    stichtag = kern_kalender.saisonstart(k, jahr)
    gehen, aufgeschoben = gen.ruecktritte(k, welt, jahr, quelle)
    if not aufgeschoben:
        pytest.skip("In diesem Jahr muss niemand warten")
    dran = gen.faellige(k, welt, jahr, quelle)
    geht = {f.nummer for f in gehen}

    def ueberzug(f):
        return f.alter_am(stichtag) - gen.ruecktrittsalter(k, f.nummer, quelle)

    kleinster_gehender = min(ueberzug(f) for f in gehen)
    groesster_bleibender = max(
        ueberzug(f) for f in dran if f.nummer not in geht
    )
    assert kleinster_gehender >= groesster_bleibender


def test_derselbe_seed_dieselben_ruecktritte(k, welt, quelle, startjahr):
    jahr = startjahr + 12
    erst, _ = gen.ruecktritte(k, welt, jahr, quelle)
    nochmal, _ = gen.ruecktritte(k, welt, jahr, quelle)
    assert [f.nummer for f in erst] == [f.nummer for f in nochmal]


# -- Newgens ----------------------------------------------------------------
def test_ein_newgen_ist_jung_und_vollstaendig(k, quelle, startjahr):
    neu = gen.newgen(
        k, nummer=9000, team=0, liga=20, jahr=startjahr + 5,
        seedquelle=quelle.zweig("jahrgang", startjahr + 5),
        seedquelle_talent=quelle,
        vergebene_namen=set(), vergebene_kuerzel=set(),
    )
    stichtag = kern_kalender.saisonstart(k, startjahr + 5)
    assert neu.nummer == 9000
    assert neu.liga == 20
    assert neu.name and neu.land
    assert 15 <= neu.alter_am(stichtag) <= 25
    assert len(neu.auto.werte) == len(k.faehigkeiten)


def test_zwei_newgens_bekommen_verschiedene_namen(k, quelle, startjahr):
    namen: set[tuple[str, str]] = set()
    kuerzel: set[str] = set()
    erzeugt = []
    for n in range(12):
        neu = gen.newgen(
            k, nummer=9000 + n, team=0, liga=20, jahr=startjahr + 5,
            seedquelle=quelle.zweig("jahrgang", startjahr + 5),
            seedquelle_talent=quelle,
            vergebene_namen=namen, vergebene_kuerzel=kuerzel,
        )
        namen.add((neu.vorname, neu.name) if hasattr(neu, "vorname") else (neu.name, ""))
        kuerzel.add(neu.auto.kuerzel)
        erzeugt.append(neu)
    assert len({f.auto.kuerzel for f in erzeugt}) == len(erzeugt)


def test_das_talent_haengt_an_der_fahrernummer_nicht_am_jahrgang(k, quelle, startjahr):
    """Sonst erbte ein Newgen das Talent seines Vorgaengers."""
    from rennmanager.kern import talent as kern_talent

    erst = gen.newgen(
        k, nummer=9100, team=0, liga=20, jahr=startjahr + 3,
        seedquelle=quelle.zweig("jahrgang", startjahr + 3),
        seedquelle_talent=quelle, vergebene_namen=set(), vergebene_kuerzel=set(),
    )
    spaeter = gen.newgen(
        k, nummer=9100, team=0, liga=20, jahr=startjahr + 9,
        seedquelle=quelle.zweig("jahrgang", startjahr + 9),
        seedquelle_talent=quelle, vergebene_namen=set(), vergebene_kuerzel=set(),
    )
    # Andere Geburtstage - also auch andere Talente, obwohl die Nummer gleich ist.
    assert erst.geburtstag != spaeter.geburtstag
    eines = kern_talent.talent(k, 9100, erst.geburtstag, quelle)
    anderes = kern_talent.talent(k, 9100, spaeter.geburtstag, quelle)
    assert eines.potential != anderes.potential


# -- Entwicklung ------------------------------------------------------------
def test_die_entwicklung_laesst_das_feld_vollstaendig(k, welt, quelle, startjahr):
    danach = gen.entwickelt(k, welt, startjahr + 1, quelle)
    assert len(danach.fahrer) == len(welt.fahrer)
    assert [f.nummer for f in danach.fahrer] == [f.nummer for f in welt.fahrer]


def test_junge_fahrer_werden_besser(k, welt, quelle, startjahr):
    """Gegen ihr Potential hin - so hat es der Auftraggeber festgelegt."""
    from rennmanager.kern import talent as kern_talent

    stichtag = kern_kalender.saisonstart(k, startjahr)
    danach = gen.entwickelt(k, welt, startjahr + 1, quelle)
    besser = 0
    geprueft = 0
    for vorher, nachher in zip(welt.fahrer, danach.fahrer, strict=True):
        if vorher.alter_am(stichtag) > 22:
            continue
        talent = kern_talent.talent(k, vorher.nummer, vorher.geburtstag, quelle)
        if gesamtwert(k, vorher.auto) >= max(talent.potential.values()):
            continue
        geprueft += 1
        if gesamtwert(k, nachher.auto) > gesamtwert(k, vorher.auto):
            besser += 1
    assert geprueft > 10
    assert besser / geprueft > 0.8, f"Nur {besser}/{geprueft} junge Fahrer besser"


def test_derselbe_seed_dieselbe_entwicklung(k, welt, quelle, startjahr):
    erst = gen.entwickelt(k, welt, startjahr + 1, quelle)
    nochmal = gen.entwickelt(k, welt, startjahr + 1, quelle)
    assert [gesamtwert(k, f.auto) for f in erst.fahrer] == [
        gesamtwert(k, f.auto) for f in nochmal.fahrer
    ]


# -- Der ganze Winter -------------------------------------------------------
def test_der_winter_haelt_das_feld_vollzaehlig(k, welt, quelle, startjahr):
    danach, bericht = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    assert len(danach.fahrer) == len(welt.fahrer)
    for liga in range(1, k.wert("ligen", "anzahl") + 1):
        assert len(danach.liga(liga)) == k.wert("rennen", "autos")
    assert bericht.jahr == startjahr + 10


def test_fuer_jeden_ruecktritt_kommt_ein_newgen(k, welt, quelle, startjahr):
    _danach, bericht = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    assert len(bericht.newgens) == len(bericht.zurueckgetreten)
    assert bericht.wechsel == len(bericht.zurueckgetreten)


def test_der_newgen_erbt_nummer_und_teamplatz(k, welt, quelle, startjahr):
    """Die Nummer bleibt, der Fahrer dahinter ist ein anderer.

    So bleiben die Teams bei vier Autos (GDD 12), und ein frei gewordener
    Platz im Spielerteam gehoert weiter dem Spieler.
    """
    danach, bericht = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    if not bericht.zurueckgetreten:
        pytest.skip("In diesem Winter trat niemand zurueck")
    assert set(bericht.newgens) == set(bericht.zurueckgetreten)
    vorher = {f.nummer: f for f in welt.fahrer}
    nachher = {f.nummer: f for f in danach.fahrer}
    for nummer in bericht.zurueckgetreten:
        alt_f, neu_f = vorher[nummer], nachher[nummer]
        assert neu_f.geburtstag != alt_f.geburtstag, "Derselbe Mensch faehrt weiter"
        assert neu_f.team == alt_f.team
        assert neu_f.ist_spieler == alt_f.ist_spieler


def test_die_newgens_steigen_unten_ein(k, welt, quelle, startjahr):
    danach, bericht = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    if not bericht.newgens:
        pytest.skip("In diesem Winter kam niemand nach")
    neue = set(bericht.newgens)
    ligen = {f.liga for f in danach.fahrer if f.nummer in neue}
    unterste = k.wert("ligen", "anzahl")
    assert max(ligen) == unterste
    assert min(ligen) >= unterste - 2


def test_nachgerueckt_wird_immer_nach_oben(k, welt, quelle, startjahr):
    """Der Eintrag lautet (Nummer, alte Liga, neue Liga)."""
    _danach, bericht = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    if not bericht.nachgerueckt:
        pytest.skip("In diesem Winter rueckte niemand nach")
    for nummer, vorher, nachher in bericht.nachgerueckt:
        assert nachher < vorher, f"Fahrer {nummer}: {vorher} -> {nachher}"


def test_der_bestplatzierte_rueckt_zuerst_nach(k, welt, quelle, startjahr):
    """Nach Platzierung aufgefuellt, nicht nach Staerke.

    Geprueft mit einer Kunstwelt: Alle bekommen denselben schlechten
    Platz, einer den ersten. Rueckt aus seiner Liga jemand auf, muss er
    es sein - selbst wenn er der Schwaechste der Liga ist.
    """
    jahr = startjahr + 10
    _ohne, bericht_ohne = gen.naechste_generation(k, welt, jahr, quelle)
    if not bericht_ohne.nachgerueckt:
        pytest.skip("In diesem Winter rueckte niemand nach")

    platzierungen = {f.nummer: 30 for f in welt.fahrer}
    # Der Schwaechste einer Liga, die jemanden nach oben abgibt.
    abgebende = {vorher for _, vorher, _ in bericht_ohne.nachgerueckt}
    liga = min(abgebende)
    schwaechster = min(welt.liga(liga), key=lambda f: gesamtwert(k, f.auto))
    platzierungen[schwaechster.nummer] = 1

    _mit, bericht_mit = gen.naechste_generation(k, welt, jahr, quelle, platzierungen)
    aus_der_liga = [
        nummer for nummer, vorher, _ in bericht_mit.nachgerueckt if vorher == liga
    ]
    assert aus_der_liga, "Aus dieser Liga rueckt jetzt niemand mehr auf"
    assert aus_der_liga[0] == schwaechster.nummer


def test_derselbe_seed_derselbe_winter(k, welt, quelle, startjahr):
    erst, bericht_erst = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    nochmal, bericht_nochmal = gen.naechste_generation(k, welt, startjahr + 10, quelle)
    assert bericht_erst == bericht_nochmal
    assert [f.nummer for f in erst.fahrer] == [f.nummer for f in nochmal.fahrer]
