"""Spritverbrauch und Masse: Das Auto wird ueber das Rennen leichter.

Bis hierher kannte das Tempomodell keine Masse. Ein Auto bestand aus fuenf
Grenzen - Querbeschleunigung in engen und in normalen Kurven,
Beschleunigen, Bremsen, Hoechstgeschwindigkeit -, und die stammen aus den
Eigenschaftswerten. Diese Grenzen gelten jetzt fuer das **leere** Auto:
Qualifying und Kalibrierung (GDD 9) fahren ohne Sprit, und dort bleibt
alles, wie es war.

Im Rennen kommt der Sprit dazu, und er wirkt, wie Masse physikalisch
wirkt. Mit ``mu = m_leer / m`` - 1,0 beim leeren Auto, rund 0,89 mit
vollem Tank:

=========================  =========================  =======================
Grenze                     mit Sprit                  weil
=========================  =========================  =======================
Beschleunigen              ``a * mu``                 F = m * a; die Kraft
                                                      des Motors bleibt
Bremsen, Kurven            ``a * (1 - alpha +         die Haftung waechst
                           alpha * mu)``              mit dem Gewicht mit,
                                                      der Abtrieb nicht
Hoechstgeschwindigkeit     unveraendert               Leistung gegen
                                                      Luftwiderstand
=========================  =========================  =======================

``alpha`` ist der Anteil der Haftung, den der Abtrieb traegt. Der
mechanische Grip - Reibwert mal Gewicht - waechst mit der Masse mit und
kuerzt sich heraus; nur der Abtrieb tut das nicht. Ein leichteres Auto
verzoegert deshalb staerker und hat einen **kuerzeren Bremsweg**
(``v^2 / 2a``), und bei gleichem Tempo zerrt eine **kleinere Fliehkraft**
(``m * v^2 / r``) an ihm - es kommt schneller um die Kurve. In engen
Kurven ist das Tempo niedrig und der Abtrieb klein, dort ist ``alpha``
kleiner.

Der Reifen spuert die Masse ebenfalls: Mehr Last heisst mehr Abrieb. Der
Auftraggeber hat entschieden, dass sich der Abrieb damit nur **verteilt**
und nicht waechst - gemessen wird gegen die **mittlere** Masse des
Rennens. Der schwere Start frisst mehr, das leichte Ende weniger, und was
ein Satz ueber das ganze Rennen hergibt, bleibt dasselbe. Die kalibrierten
Stoppzahlen gelten damit weiter.

Getankt wird, was ein Fahrer fuer die Renndistanz braucht, plus eine
Reserve. Der Sprit reicht also immer; wer sparsam faehrt - das haengt am
**Materialgefuehl** -, traegt das ganze Rennen weniger mit sich herum.

Alle Zahlen stehen im Abschnitt ``[sprit]`` von ``balancing.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern.auto import Auto
from rennmanager.kern.tempo import Grenzen, leistungsanteil

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Die Eigenschaft neben der Wirkungsmatrix, die den Verbrauch traegt.
# Dieselbe wie fuer die Defektrate (Punkt 13): Wer das Material spuert,
# faehrt es nicht kaputt - und verbrennt weniger.
MATERIALGEFUEHL = "materialgefuehl"
METER_JE_KM = 1000.0


@dataclass(frozen=True)
class Tank:
    """Der Sprit eines Autos fuer ein Rennen.

    :param start_kg: was beim Start im Tank ist
    :param verbrauch_kg_je_m: was ein gefahrener Meter kostet
    """

    start_kg: float
    verbrauch_kg_je_m: float

    def menge_kg(self, gefahren_m):
        """Was nach so vielen gefahrenen Metern noch im Tank ist.

        Nimmt eine Zahl oder ein Feld. Leerer als leer wird der Tank
        nicht; bei der Reserve kommt es dazu aber nie.
        """
        rest = self.start_kg - self.verbrauch_kg_je_m * np.maximum(gefahren_m, 0.0)
        return np.maximum(rest, 0.0)


def _einstellung(konfiguration: Konfiguration) -> dict:
    return konfiguration.wert("sprit")


def verbrauchsfaktor(konfiguration: Konfiguration, auto: Auto) -> float:
    """Faktor auf den mittleren Verbrauch aus dem Materialgefuehl.

    +5 % beim Wert 0, -5 % beim Hoechstwert - linear im Leistungsanteil
    ``p = sqrt(S / referenz)``, wie alle Eigenschaften neben der
    Wirkungsmatrix (siehe ``tempoverlauf``).
    """
    einstellung = _einstellung(konfiguration)
    anteil = min(
        leistungsanteil(
            auto.wetterwert(MATERIALGEFUEHL), konfiguration.wert("skala", "referenz")
        ),
        1.0,
    )
    bei_null = einstellung["verbrauch_faktor_bei_null"]
    bei_maximum = einstellung["verbrauch_faktor_bei_maximum"]
    return bei_null + (bei_maximum - bei_null) * anteil


def verbrauch_kg_je_m(konfiguration: Konfiguration, auto: Auto) -> float:
    """Was dieses Auto je gefahrenem Meter verbrennt."""
    je_km = _einstellung(konfiguration)["verbrauch_kg_je_km"]
    return je_km / METER_JE_KM * verbrauchsfaktor(konfiguration, auto)


def tank(konfiguration: Konfiguration, auto: Auto, renndistanz_m: float) -> Tank:
    """Getankt wird, was die Distanz braucht, plus die Reserve."""
    verbrauch = verbrauch_kg_je_m(konfiguration, auto)
    reserve = _einstellung(konfiguration)["reserve_anteil"]
    return Tank(
        start_kg=verbrauch * max(renndistanz_m, 0.0) * (1.0 + reserve),
        verbrauch_kg_je_m=verbrauch,
    )


def massenanteil(konfiguration: Konfiguration, sprit_kg):
    """``mu = m_leer / m`` - 1,0 fuer das leere Auto, kleiner mit Sprit."""
    leer = _einstellung(konfiguration)["masse_leer_kg"]
    return leer / (leer + np.maximum(sprit_kg, 0.0))


def haftungsanteil(mu, abtriebsanteil: float):
    """Was von der Haftung bei dieser Masse uebrig ist.

    Der mechanische Teil waechst mit dem Gewicht mit und bleibt je
    Kilogramm gleich; nur der Abtriebsteil wird auf mehr Masse verteilt.
    """
    return 1.0 - abtriebsanteil + abtriebsanteil * mu


def grenzen_mit_sprit(
    konfiguration: Konfiguration, grenzen: Grenzen, sprit_kg: float
) -> Grenzen:
    """Die Grenzen des leeren Autos, mit so viel Sprit an Bord.

    Ohne Sprit kommt dasselbe Objekt zurueck - so bleibt der
    Bezugszustand aus GDD 9 unangetastet, auch auf die letzte Stelle.
    """
    if sprit_kg <= 0.0:
        return grenzen
    einstellung = _einstellung(konfiguration)
    mu = float(massenanteil(konfiguration, sprit_kg))
    haftung = haftungsanteil(mu, einstellung["abtriebsanteil"])
    haftung_eng = haftungsanteil(mu, einstellung["abtriebsanteil_enge_kurve"])
    return replace(
        grenzen,
        quer_eng=grenzen.quer_eng * haftung_eng,
        quer=grenzen.quer * haftung,
        laengs=grenzen.laengs * mu,
        brems=grenzen.brems * haftung,
    )


def mittlere_masse_kg(
    konfiguration: Konfiguration, tank_: Tank, renndistanz_m: float
) -> float:
    """Die Masse, gegen die der Abrieb gemessen wird.

    Der Sprit nimmt linear mit der Strecke ab; das Mittel ueber das
    Rennen ist deshalb das Mittel aus Start und Ziel.
    """
    leer = _einstellung(konfiguration)["masse_leer_kg"]
    ziel = float(tank_.menge_kg(renndistanz_m))
    return leer + (tank_.start_kg + ziel) / 2.0


def abriebfaktor(
    konfiguration: Konfiguration, tank_: Tank, gefahren_m, renndistanz_m: float
):
    """Faktor auf den Reifenabrieb: aktuelle gegen mittlere Masse.

    Ueber das ganze Rennen gemittelt ist er genau 1,0 - der Abrieb
    verteilt sich nur um (Entscheidung des Auftraggebers).
    """
    leer = _einstellung(konfiguration)["masse_leer_kg"]
    masse = leer + tank_.menge_kg(gefahren_m)
    return masse / mittlere_masse_kg(konfiguration, tank_, renndistanz_m)


def abrieb_je_runde(
    konfiguration: Konfiguration, auto: Auto, runden: int, rundenlaenge_m: float
) -> tuple[float, ...]:
    """Der Faktor der Masse auf den Abrieb, fuer jede Rennrunde.

    Gefragt wird zur **Mitte** jeder Runde - dieselbe Wahl wie bei der
    Gummivorhersage der Strategie (Punkt 90). Der Planer kennt den Sprit:
    Er steht vor dem Rennen fest, anders als der Grip der Strecke.
    """
    renndistanz_m = runden * rundenlaenge_m
    tank_ = tank(konfiguration, auto, renndistanz_m)
    return tuple(
        float(
            abriebfaktor(konfiguration, tank_, (n + 0.5) * rundenlaenge_m, renndistanz_m)
        )
        for n in range(runden)
    )
