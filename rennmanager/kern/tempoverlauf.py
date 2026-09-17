"""Was ueber die Renndistanz nachlaesst - und was am Anfang fehlt.

Drei Wirkungen, die alle am selben Punkt haengen: der schon gefahrenen
Distanz. Sie stehen hier zusammen, weil sie dieselbe Form haben und
dieselbe Stelle der Simulation treffen wie der Reifenverschleiss.

=================  ===================================  ==================
Wirkung            Woran sie haengt                     Wann sie wirkt
=================  ===================================  ==================
Ermuedung          Wirkungsbereich ``er`` aus GDD 8     ab der halben
                                                        Distanz
Kaltreifen         Eigenschaft ``kaltreifen``           die erste Runde
Bremskuehlung      Eigenschaft ``bremskuehlung``        ueber die ganze
                                                        Distanz
=================  ===================================  ==================

Die **Ermuedung** macht den Bereich ``er`` der Wirkungsmatrix endlich
wirksam: Er wurde bisher berechnet, aber von keiner Stelle der Simulation
gelesen.

**Kaltreifen** und **Bremskuehlung** sind neue Eigenschaften neben der
Wirkungsmatrix (Punkt 48 in OFFENE_PUNKTE.md). Sie stehen bewusst
ausserhalb, damit Gesamtwert, Bereichswerte und die Kalibriertabelle aus
GDD 9 unberuehrt bleiben.

Die Bremskuehlung ist die einzige der drei, die nicht direkt aufs Tempo
geht: Sie senkt die **Bremsgrenze**. Was das kostet, haengt davon ab, wie
viel auf einer Strecke gebremst wird - auf einem Stadtkurs mehr als auf
einer Hochgeschwindigkeitsstrecke. Deshalb liefert dieses Modul dafuer
keinen Tempofaktor, sondern den Anteil, um den die Grenze gesunken ist;
``rennmanager.kern.rennen`` bildet damit ein zweites
Geschwindigkeitsprofil und mischt zwischen beiden.

Alle drei gehoeren zu dem, was ``ohne_zufall`` abschaltet: GDD 9
kalibriert die freie Einzelrunde, und die kennt weder Ermuedung noch kalte
Reifen noch heissgefahrene Bremsen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto, bereichswert
from rennmanager.kern.tempo import leistungsanteil

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Wirkungsbereich aus GDD 8, der die Ermuedung traegt.
BEREICH_ERMUEDUNG = "er"
# Eigenschaften neben der Wirkungsmatrix liegen in ``Auto.wetterwerte``;
# ``wetterwert`` liefert 0, wo eine fehlt - der Anfangswert aus GDD 1.
KALTREIFEN = "kaltreifen"
BREMSKUEHLUNG = "bremskuehlung"


def _zwischen(konfiguration: Konfiguration, s: float, bei_null: float, bei_maximum: float) -> float:
    """Linear im Leistungsanteil p = sqrt(S / referenz), wie GDD 9 rechnet."""
    anteil = min(leistungsanteil(s, konfiguration.wert("skala", "referenz")), 1.0)
    return bei_null + (bei_maximum - bei_null) * anteil


# ---------------------------------------------------------------------------
# Ermuedung (GDD 8, Bereich er)
# ---------------------------------------------------------------------------
def ermuedungsverlust(konfiguration: Konfiguration, auto: Auto) -> float:
    """Tempoverlust am Rennende, 0 bis 1."""
    einstellung = konfiguration.wert("ermuedung")
    return _zwischen(
        konfiguration,
        bereichswert(konfiguration, auto, BEREICH_ERMUEDUNG),
        einstellung["tempoverlust_am_ende_bei_null"],
        einstellung["tempoverlust_am_ende_bei_maximum"],
    )


def ermuedungsfaktor(konfiguration: Konfiguration, auto: Auto, anteil_distanz: float) -> float:
    """Faktor aufs Tempo bei diesem Anteil der Renndistanz.

    Vor ``beginn_anteil_distanz`` ist er 1,0; danach waechst der Verlust
    linear bis zum vollen Betrag im Ziel.

    :param anteil_distanz: gefahrene Distanz durch Renndistanz, 0 bis 1
    """
    beginn = konfiguration.wert("ermuedung", "beginn_anteil_distanz")
    if anteil_distanz <= beginn or beginn >= 1.0:
        return 1.0
    fortschritt = min((anteil_distanz - beginn) / (1.0 - beginn), 1.0)
    return 1.0 - ermuedungsverlust(konfiguration, auto) * fortschritt


# ---------------------------------------------------------------------------
# Kaltreifen (Punkt 48)
# ---------------------------------------------------------------------------
def kaltreifenverlust(konfiguration: Konfiguration, auto: Auto) -> float:
    """Tempoverlust in der ersten Runde, 0 bis 1."""
    einstellung = konfiguration.wert("kaltreifen")
    return _zwischen(
        konfiguration,
        auto.wetterwert(KALTREIFEN),
        einstellung["tempoverlust_bei_null"],
        einstellung["tempoverlust_bei_maximum"],
    )


def kaltreifenfaktor(
    konfiguration: Konfiguration, auto: Auto, gefahren_m: float, rundenlaenge_m: float
) -> float:
    """Faktor aufs Tempo, solange die Reifen noch kalt sind.

    Voller Verlust beim Start, linear abgebaut ueber
    ``aufwaermstrecke_runden`` Runden.
    """
    strecke = konfiguration.wert("kaltreifen", "aufwaermstrecke_runden") * rundenlaenge_m
    if strecke <= 0.0 or gefahren_m >= strecke:
        return 1.0
    rest = 1.0 - max(gefahren_m, 0.0) / strecke
    return 1.0 - kaltreifenverlust(konfiguration, auto) * rest


def kaltreifenfaktor_runde(
    konfiguration: Konfiguration, auto: Auto, runde: int, rundenlaenge_m: float
) -> float:
    """Der mittlere Kaltreifenfaktor ueber eine ganze Runde.

    Der Schnellmodus aus GDD 13 bildet je Runde *eine* Zeit und kann den
    Verlust nicht ueber die Runde abbauen. Er bekommt deshalb den
    Mittelwert ueber die Runde - so kostet dieselbe Runde in beiden
    Modellen gleich viel.

    :param runde: Rundennummer ab 1
    """
    strecke = konfiguration.wert("kaltreifen", "aufwaermstrecke_runden") * rundenlaenge_m
    if strecke <= 0.0 or rundenlaenge_m <= 0.0 or runde < 1:
        return 1.0
    von = (runde - 1) * rundenlaenge_m
    bis = runde * rundenlaenge_m
    if von >= strecke:
        return 1.0
    # Mittelwert von rest(x) = 1 - x/strecke ueber [von, min(bis, strecke)].
    ende = min(bis, strecke)
    flaeche = (ende - von) - (ende**2 - von**2) / (2.0 * strecke)
    return 1.0 - kaltreifenverlust(konfiguration, auto) * flaeche / rundenlaenge_m


# ---------------------------------------------------------------------------
# Bremskuehlung (Punkt 48)
# ---------------------------------------------------------------------------
def bremsverlust(konfiguration: Konfiguration, auto: Auto) -> float:
    """Anteil, um den die Bremsgrenze bis zum Rennende faellt, 0 bis 1."""
    einstellung = konfiguration.wert("bremskuehlung")
    return _zwischen(
        konfiguration,
        auto.wetterwert(BREMSKUEHLUNG),
        einstellung["verlust_am_ende_bei_null"],
        einstellung["verlust_am_ende_bei_maximum"],
    )


def bremsgrenze_am_ende(konfiguration: Konfiguration, auto: Auto, brems: float) -> float:
    """Die Bremsgrenze, die am Rennende noch bleibt.

    :param brems: die Bremsgrenze zu Rennbeginn in m/s^2
    """
    return brems * (1.0 - bremsverlust(konfiguration, auto))
