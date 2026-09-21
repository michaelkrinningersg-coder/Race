"""Konstanten und freie Helfer der Boxenstopp-Tests (Punkt 39).

Die Fixtures stehen nebenan in ``conftest.py``; hier steht nur, was sich
importieren laesst, ohne mit einem Testparameter gleichen Namens zu
kollidieren.
"""

from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import strategie as sg
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.zufall import Seedquelle

# Ein kurzes Rennen: die Stopps interessieren, nicht die Renndistanz.
RUNDEN = 24
# Ein Seed, dessen Rennwetter auf dieser Strecke durchgehend trocken ist.
# Beide Modelle wuerfeln es aus demselben Zweig, koennen es aber nicht
# entgegennehmen - also wird es hier ausgesucht statt gesetzt.
TROCKEN = 0
# Streckenverschleiss der Tests: hoch genug, dass ein Satz bis zur
# geplanten Stopprunde unter die Verschiebeschwelle faellt - und seit dem
# Zwangsstopp bei 30 % Restprofil auch hoch genug, dass dieser greift.
#
# **Roh, nicht wirksam** (Punkt 92): Der Streckenfaktor geht mit
# ``verschleiss_exponent`` in den Verschleiss ein, hier also als
# Wurzel. Die 9,0 wirken wie die 3,0, auf die diese Tests eingestellt
# sind; ``test_die_testkonstanten_wirken_wie_gedacht`` haelt das fest,
# damit ein geaenderter Exponent hier auffaellt und nicht erst drei
# Reihen weiter.
VERSCHLEISS = 9.0
# Wer pruefen will, dass ein **geplanter** Stopp in seiner Runde gefahren
# wird, braucht einen Satz, der bis dahin ueber 30 % bleibt - sonst kommt
# vorher der Zwangsstopp. Gemessen: 1,5 laesst in Runde 8 noch 47 % und
# in Runde 16 noch 63 % uebrig.
#
# Die Verschiebeschwelle muss fuer solche Tests aus dem Weg (Fixture
# ``ohne_verschiebung``). Sonst haengt die Stopprunde an einem
# Balancing-Wert: Mit 0,75 fiel der Stopp in Runde 16, mit 0,65 in
# Runde 17 - dieselbe Mechanik, andere Zahl. Dass verschoben wird, prueft
# ``test_ein_zu_guter_satz_verschiebt_den_stopp`` eigens, und zwar gegen
# die Schwelle aus der Konfiguration statt gegen eine feste Runde.
VERSCHLEISS_PLANSTOPP = 2.25   # wirkt wie 1,5
# Und andersherum: So schonend, dass ein fuer Runde 8 geplanter Stopp
# sicher verschoben wird. Gemessen ueber acht Faktoren von 0,3 bis 2,5
# faellt der Stopp immer dorthin, wo der Satz die Schwelle reisst - bei
# 0,8 ist das Runde 10 mit 63 bis 65 % Restprofil. Bei 0,3 traegt der
# Satz das ganze Rennen und es wird gar nicht gestoppt, bei 1,0 liegt er
# in Runde 8 schon genau auf der Schwelle.
VERSCHLEISS_MILD = 0.64        # wirkt wie 0,8


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
