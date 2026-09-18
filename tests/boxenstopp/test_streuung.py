"""Reproduzierbarkeit und Streuung der Boxenstopps (Punkt 39).

Derselbe Seed muss dieselben Stopps ergeben (GDD 15) - und zwei
gleiche Plaene trotzdem verschieden ausgehen, weil Verschleiss und
Tempo je Fahrer und Mischung streuen.
"""


from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as rn
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import RUNDEN, strategie_mit


# -- Reproduzierbarkeit -----------------------------------------------------
def test_gleicher_seed_gleiche_stopps(k, monza, feld, umgebung):
    mittel, verschleiss = umgebung
    # So viele Strategien, wie Autos antreten - die Feldgroesse steht in
    # der Konfiguration und ist im Test klein.
    strategien = tuple(strategie_mit(k, (8, 16)) for _ in feld)

    def lauf():
        return rn.simuliere(
            k, monza, feld, RUNDEN, Seedquelle(2), mittel,
            streckenverschleiss=verschleiss, strategien=strategien,
        )

    assert lauf().boxenstopps == lauf().boxenstopps


def test_die_streuung_macht_zwei_gleiche_plaene_verschieden(k, monza, feld, umgebung):
    """Punkt 39: je Fahrer und Mischung ein kleiner Verschleisswurf.

    Frueh gestoppt, damit beim Wechsel ueberhaupt noch Profil da ist -
    bei diesem Streckenverschleiss ist ein Satz nach zehn Runden hin, und
    auf null sieht man keine Streuung mehr.
    """
    mittel, verschleiss = umgebung
    strategien = tuple(strategie_mit(k, (5,)) for _ in feld)
    verlauf = rn.simuliere(
        k, monza, feld, RUNDEN, Seedquelle(2), mittel,
        streckenverschleiss=verschleiss, strategien=strategien,
    )
    reste = {round(b.restprofil, 6) for b in verlauf.boxenstopps}
    assert len(reste) > 1


def test_die_streuung_bleibt_in_ihren_spannen(k):
    """Zwei getrennte Wuerfe: Verschleiss und Tempo, jeder in seiner Spanne."""
    fuer_verschleiss = k.wert("reifen", "verschleiss", "streuung_verschleiss")
    fuer_tempo = k.wert("reifen", "verschleiss", "streuung_tempo")
    misch = kern_reifen.mischung(k, "mittel")
    gestreut = [kern_reifen.mit_streuung(k, misch, Seedquelle(n)) for n in range(100)]
    assert all(
        abs(m.verschleiss - misch.verschleiss) <= fuer_verschleiss + 1e-12
        for m in gestreut
    )
    assert all(abs(m.tempo - misch.tempo) <= fuer_tempo + 1e-12 for m in gestreut)
    assert len({m.verschleiss for m in gestreut}) > 50
    assert len({m.tempo for m in gestreut}) > 50


def test_verschleiss_und_tempo_streuen_unabhaengig(k):
    """Sonst waere ein Satz mal rundum besser, mal rundum schlechter."""
    misch = kern_reifen.mischung(k, "mittel")
    gestreut = [kern_reifen.mit_streuung(k, misch, Seedquelle(n)) for n in range(200)]
    besser_haltbar = [m.verschleiss < misch.verschleiss for m in gestreut]
    schneller = [m.tempo > misch.tempo for m in gestreut]
    beides = sum(1 for a, b in zip(besser_haltbar, schneller, strict=True) if a and b)
    # Bei Unabhaengigkeit rund ein Viertel; ein Zusammenhang faellt auf.
    assert 0.15 <= beides / len(gestreut) <= 0.35
