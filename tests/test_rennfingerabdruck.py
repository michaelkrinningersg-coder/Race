"""Dass ein Rennen reproduzierbar ist (E13).

Ein Rennen muss bei gleichem Seed gleich ausgehen - das ist eine
Arbeitsregel und die Grundlage jeder Messung. Diese Tests pruefen das,
und zwar an dem, was ein Spieler sieht: Rundenzeiten, Sektorzeiten,
Ergebnisse, Stopps, Zwischenfaelle.

**Warum hier keine feste Kennzahl mehr steht.** Bis zum 20.09.2026 hielt
diese Datei zwei Hashwerte fest, die ueber alle rohen ``float64``-Werte
eines Rennens gebildet waren - 670.000 Zahlen. Auf der Maschine, auf der
sie entstanden, war das ein scharfes Werkzeug: E1 bis E8 liessen sich
damit als bitgenau verhaltensgleich belegen. Als CI-Anker war es ein
Fehlentwurf. Die Tests laufen auf Linux **und** Windows, mit nicht
festgenagelter NumPy-Version; verschiedene Rechner nehmen verschiedene
SIMD-Pfade und liefern in der letzten Stelle andere Bits. Der Anker
musste dort rot werden, ohne dass am Rennen irgendetwas falsch war -
und ein Test, der aus einem Grund rot wird, den er nicht meint, ist
schlimmer als kein Test.

Die Kennzahl selbst gibt es weiter, im Werkzeug, wo sie hingehoert:

    python -m werkzeuge.profil_rennen --fingerabdruck

Vor und nach einer Aenderung **auf derselben Maschine** aufgerufen sagt
sie auf das Bit genau, ob sich am Rennen etwas geaendert hat. Genau so
wurde sie gebraucht, und genau dafuer ist sie richtig.

Der maschinenunabhaengige Anker fuer die Physik ist die Kalibrierung
(GDD 9): ``python -m rennmanager --pruefe`` und
``tests/test_kalibrierwerkzeug.py`` halten Zandvoort bei S=98.000 auf
180,00 km/h fest. Die rechnet eine einzelne Runde ohne Zufall und ohne
Verkehr und haengt damit an keiner Maschine.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf
from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as st
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.zufall import Seedquelle

LIGA = 10
RUNDEN = 3
SEED = 4711


@pytest.fixture(scope="module")
def k() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def zandvoort(k) -> st.Strecke:
    return st.lade(k, "Zandvoort")


@pytest.fixture(scope="module")
def mittel(k) -> float:
    return rn.mittlerer_ueberholzonenanteil(k, st.lade_alle(k))


def _rennen(k, zandvoort, mittel, seed: int = SEED, wetter=None) -> rn.Rennverlauf:
    feld = rn.starterfeld(k)
    return rn.simuliere(
        k, zandvoort, feld, RUNDEN, Seedquelle(seed), mittel, wetter=wetter
    )


def _sichtbares(verlauf: rn.Rennverlauf) -> tuple:
    """Alles, woran ein Spieler einen Unterschied merken wuerde.

    Bewusst **ohne** die rohen Distanzen: Die sind Gleitkomma und damit
    das Einzige an einem Rennen, was von Rechner zu Rechner in der
    letzten Stelle abweichen darf. Was hier steht, sind ganze
    Millisekunden und ganze Plaetze - wenn sich daran etwas aendert, hat
    sich das Rennen geaendert.
    """
    return (
        tuple(
            (
                tuple(p.rundenzeiten_ms),
                tuple(p.sektorzeiten_ms),
                tuple(p.rundenende_ms),
            )
            for p in verlauf.protokolle
        ),
        verlauf.ergebnisse,
        tuple((b.teilnehmer, b.runde, b.zeit_ms, b.von, b.nach)
              for b in verlauf.boxenstopps),
        tuple((z.art, z.zeit_ms, z.teilnehmer, z.runde) for z in verlauf.zwischenfaelle),
    )


def test_derselbe_seed_ergibt_dasselbe_rennen(k, zandvoort, mittel) -> None:
    """Die Arbeitsregel: Jede Simulation ist ueber ihren Seed reproduzierbar."""
    assert _sichtbares(_rennen(k, zandvoort, mittel)) == _sichtbares(
        _rennen(k, zandvoort, mittel)
    )


def test_derselbe_seed_ergibt_dieselben_distanzen(k, zandvoort, mittel) -> None:
    """Auf **einer** Maschine sogar auf das Bit genau.

    Zwischen zwei Rechnern darf das abweichen, zwischen zwei Laeufen auf
    demselben nicht - sonst waere irgendwo ein Zufall im Spiel, der
    nicht am Seed haengt.
    """
    import numpy as np

    erste = _rennen(k, zandvoort, mittel)
    zweite = _rennen(k, zandvoort, mittel)
    assert np.array_equal(erste.distanz_m, zweite.distanz_m)


def test_mit_wetter_bleibt_es_reproduzierbar(k, zandvoort, mittel) -> None:
    """Der Wetterpfad hat eigene Wuerfe (Grip je Sektor, Uebergaenge)."""
    def lauf():
        return _rennen(
            k, zandvoort, mittel,
            wetter=kern_wetter.wuerfle(k, zandvoort.name, 600_000, 90_000, Seedquelle(7)),
        )

    assert _sichtbares(lauf()) == _sichtbares(lauf())


def test_ein_anderer_seed_ergibt_ein_anderes_rennen(k, zandvoort, mittel) -> None:
    """Ohne das waere die Reproduzierbarkeit oben wertlos."""
    assert _sichtbares(_rennen(k, zandvoort, mittel)) != _sichtbares(
        _rennen(k, zandvoort, mittel, seed=SEED + 1)
    )


def test_das_rennen_ist_plausibel(k, zandvoort, mittel) -> None:
    """Ein grober Rahmen, der auf jedem Rechner gilt.

    Kein Anker auf die Millisekunde - dafuer ist die Kalibrierung da -,
    aber genug, um zu merken, wenn die Physik ausgehebelt wurde.
    """
    verlauf = _rennen(k, zandvoort, mittel)
    assert len(verlauf.ergebnisse) == len(verlauf.teilnehmer)
    runden = [ms for p in verlauf.protokolle for ms in p.rundenzeiten_ms]
    assert runden, "Es wurde keine einzige Runde gefahren"
    # Zandvoort faehrt ein Liga-10-Auto in gut anderthalb Minuten.
    assert 60_000 < min(runden) < 180_000
    assert max(runden) < 600_000, "Eine Runde ueber zehn Minuten ist keine Runde"
