"""Die Umgebung der Boxenstopp-Tests (Punkt 39).

Vier Dateien teilen sich dieselbe Strecke, dasselbe Feld und dieselbe
Konfiguration. Aufgeteilt wurden sie, weil der Testlauf je Datei auf die
Kerne verteilt wird: Eine Datei mit vierzehn Vierundzwanzig-Runden-Rennen
bestimmte sonst allein, wie lange der ganze Lauf dauert.
"""

import pytest

from rennmanager.kern import rennen as rn
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern.zufall import Seedquelle
from tests.boxenstopp.hilfen import VERSCHLEISS


@pytest.fixture(scope="module")
def k(kleine_konfiguration):
    """Punkt 77: laeuft auf der kleinen Welt aus ``conftest``.

    Drei Ligen zu je vier Autos statt zwanzig zu je dreissig. Geprueft
    wird, *ob* die Logik stimmt - dafuer genuegt das kleine Feld.
    """
    return kleine_konfiguration


@pytest.fixture(scope="module")
def ohne_verschiebung(k):
    """Dieselbe Konfiguration, nur ohne die Verschiebung des Planstopps.

    Punkt 39 verschiebt einen geplanten Stopp, solange das Restprofil
    ueber der Schwelle liegt. Wer den **Preis** eines Stopps messen will,
    braucht einen Satz ohne Verschleiss - und der wuerde ewig
    verschoben. Die Schwelle auf 1,0 heisst: nie verschieben, denn mehr
    als volles Profil gibt es nicht.
    """
    from copy import deepcopy
    from dataclasses import replace as ersetze

    roh = deepcopy(k.roh)
    roh["boxenstopp"]["strategie"]["planstopp_ab_restprofil"] = 1.0
    return ersetze(k, roh=roh)


@pytest.fixture(scope="module")
def strecken(k):
    return kern_strecke.lade_alle(k)


@pytest.fixture(scope="module")
def monza(strecken):
    return next(s for s in strecken if s.name == "Monza")


@pytest.fixture(scope="module")
def umgebung(k, strecken, monza):
    """Ueberholzonenanteil und ein Streckenverschleiss, der Stopps erzwingt.

    Monza nimmt die Reifen von sich aus kaum her (Faktor 0,54); ein Satz
    traegt dort ueber die ganze Testdistanz. Seit ein geplanter Stopp
    verschoben wird, solange das Restprofil ueber der Schwelle liegt,
    kaeme in diesen Tests gar kein Stopp mehr zustande. Der erhoehte
    Faktor macht die Stopps faellig - geprueft wird hier der
    Stoppmechanismus, nicht die Streckenwirkung.
    """
    return (rn.mittlerer_ueberholzonenanteil(k, strecken), VERSCHLEISS)


@pytest.fixture(scope="module")
def feld(k):
    return rn.starterfeld(k, seedquelle=Seedquelle(1))
