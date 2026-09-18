"""Konstanten und freie Helfer der Boxenstopp-Tests (Punkt 39).

Die Fixtures stehen nebenan in ``conftest.py``; hier steht nur, was sich
importieren laesst, ohne mit einem Testparameter gleichen Namens zu
kollidieren.
"""

from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import strategie as sg
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.zufall import Seedquelle

LIGA = 1
# Ein kurzes Rennen: die Stopps interessieren, nicht die Renndistanz.
RUNDEN = 24
# Ein Seed, dessen Rennwetter auf dieser Strecke durchgehend trocken ist.
# Beide Modelle wuerfeln es aus demselben Zweig, koennen es aber nicht
# entgegennehmen - also wird es hier ausgesucht statt gesetzt.
TROCKEN = 0
# Streckenverschleiss der Tests: hoch genug, dass ein Satz bis zur
# geplanten Stopprunde unter die Verschiebeschwelle faellt - und seit dem
# Zwangsstopp bei 30 % Restprofil auch hoch genug, dass dieser greift.
VERSCHLEISS = 3.0
# Dazwischen liegt ein schmales Fenster: Wer pruefen will, dass ein
# **geplanter** Stopp wirklich in seiner Runde gefahren wird, braucht
# einen Satz, der bis dahin unter 75 % faellt (sonst wird der Stopp
# verschoben), aber ueber 30 % bleibt (sonst kommt vorher der
# Zwangsstopp). Gemessen: 1,5 trifft das, 1,0 und 2,0 nicht.
VERSCHLEISS_PLANSTOPP = 1.5


def strategie_mit(k, stopps):
    """Zwei verschiedene Mischungen, feste Stopprunden."""
    weich = kern_reifen.mischung(k, "weich")
    hart = kern_reifen.mischung(k, "hart")
    folge = tuple((weich if n % 2 == 0 else hart) for n in range(len(stopps) + 1))
    return sg.Strategie(mischungen=folge, stopps=tuple(stopps))


def rennwetter(k, monza, feld, seed):
    """Das Wetter, das der Schnellmodus sich selbst wuerfelt.

    Er zieht es aus ``zweig("rennwetter")``; dieselbe Rechnung hier ergibt
    denselben Verlauf. Ohne das vergleicht ein Test nur zwei verschiedene
    Rennsonntage.
    """
    from rennmanager.kern import wetter as kern_wetter

    grund = sum(
        kern_tempo.fahre_runde(k, monza, t.auto).zeit_ms for t in feld
    ) / len(feld)
    return kern_wetter.wuerfle(
        k, monza.name, int(grund * RUNDEN), int(grund), Seedquelle(seed).zweig("rennwetter")
    )
