"""Der Fingerabdruck eines Rennens (E13).

Dieser Test misst nichts und prueft keine Regel - er haelt **eine Zahl**
fest. Jede Aenderung an der Rennschleife, die schneller sein soll, ohne
das Verhalten zu aendern (E1 bis E8), muss denselben Fingerabdruck
herausbekommen. Faellt er, hat sich das Rennen veraendert; dann ist die
Aenderung entweder falsch oder eine Entscheidung, die der Auftraggeber
treffen muss.

Die Kennzahl kommt aus ``werkzeuge.profil_rennen`` - absichtlich
dieselbe Funktion, die das Messwerkzeug ausgibt. Waere sie hier noch
einmal geschrieben, koennten Werkzeug und Test auseinanderlaufen und
verschiedene Zahlen nennen.

Gefahren wird mit dem **grossen** Feld: Dreissig Autos erzeugen Verkehr,
Windschatten und Zwischenfaelle, und genau diese Pfade werden
beschleunigt. Mit vier Autos bliebe die halbe Rennschleife ungeprueft.
Drei Runden reichen dafuer und kosten rund eine Sekunde.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.zufall import Seedquelle
from werkzeuge.profil_rennen import fingerabdruck

LIGA = 10
RUNDEN = 3
SEED = 4711

# Gemessen am 20.09.2026 vor den Aenderungen aus E1 bis E8.
TROCKEN = "2a1a688770a4f5c3"
MIT_WETTER = "cc13f96a73e1d246"


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def zandvoort(k) -> st.Strecke:
    return st.lade(k, "Zandvoort")


@pytest.fixture(scope="module")
def mittel(k) -> float:
    return rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))


def _rennen(k, zandvoort, mittel, wetter=None) -> rn.Rennverlauf:
    feld = rn.starterfeld(k, LIGA)
    return rn.simuliere(
        k, zandvoort, feld, RUNDEN, Seedquelle(SEED), mittel, wetter=wetter
    )


def test_das_rennen_hat_denselben_fingerabdruck_wie_vorher(k, zandvoort, mittel) -> None:
    """Der Anker fuer E1 bis E8."""
    assert fingerabdruck(_rennen(k, zandvoort, mittel)) == TROCKEN


def test_auch_mit_wetter_bleibt_der_fingerabdruck(k, zandvoort, mittel) -> None:
    """Der Wetterpfad wird gesondert angefasst (Grip je Sektor)."""
    verlauf = _rennen(
        k, zandvoort, mittel,
        wetter=kern_wetter.wuerfle(k, zandvoort.name, 600_000, 90_000, Seedquelle(7)),
    )
    assert fingerabdruck(verlauf) == MIT_WETTER


def test_derselbe_seed_ergibt_denselben_fingerabdruck(k, zandvoort, mittel) -> None:
    """Ohne das waere der Anker oben wertlos."""
    erste = _rennen(k, zandvoort, mittel)
    zweite = _rennen(k, zandvoort, mittel)
    assert fingerabdruck(erste) == fingerabdruck(zweite)


def test_ein_anderer_seed_aendert_den_fingerabdruck(k, zandvoort, mittel) -> None:
    """Und ohne das merkte der Anker keinen Unterschied."""
    feld = rn.starterfeld(k, LIGA)
    anders = rn.simuliere(k, zandvoort, feld, RUNDEN, Seedquelle(SEED + 1), mittel)
    assert fingerabdruck(anders) != TROCKEN
