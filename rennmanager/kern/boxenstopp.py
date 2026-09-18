"""Die Boxengasse (Punkt 39).

Die Streckendateien enthalten keine Boxengasse - nur Ideallinie,
Segmente und Sektoren. Der Auftraggeber hat entschieden, sie aus der
Geometrie abzuleiten, und zwar so, wie sie auf fast jeder echten Strecke
liegt: **parallel zur Geraden um Start und Ziel.** Ist die Gerade danach
lang, fuehrt sie schon vor der ersten Kurvenkombination wieder auf die
Strecke; ist die Gerade davor lang, zweigt sie erst nach der letzten ab.
Dazwischen gilt eine Spanne von 500 bis 1000 Metern. Auf diesem Stueck
faehrt das Auto 80 statt Renntempo; davor bremst es, danach beschleunigt
es wieder.

Ohne die Spanne wird es absurd: Gemessen kam Monza mit der ganzen
Start-Ziel-Geraden auf 1350 Meter und 44 Sekunden Durchfahrt - mehr als
eine halbe Rundenzeit -, waehrend Silverstone bei 45 Metern landete, weil
Start/Ziel dort kurz vor dem Kurveneingang liegt.

**Gerechnet wird mit derselben Physik wie sonst.** Statt eine Formel fuer
den Zeitverlust zu erfinden, wird das Kurvenlimit auf dem Abschnitt
gedeckelt und dasselbe Geschwindigkeitsprofil wie immer gefahren (GDD 4:
Vorwaerts mit der Beschleunigungsgrenze, rueckwaerts mit der
Bremsgrenze). Bremsen und Beschleunigen entstehen dadurch von allein, und
zwar mit den Werten **dieses** Autos: Ein Auto mit starken Bremsen
verliert in der Boxengasse weniger.

Der **Durchfahrtsverlust** ist die Differenz der beiden Rundenzeiten, mit
und ohne Deckel. Dazu kommt die **Standzeit** von 3 bis 10 Sekunden.

**Zwei Wege, ein Ergebnis.** Im Zeitraffer faehrt das Auto die Boxengasse
wirklich langsamer - man sieht es kriechen. Im Schnellmodus ohne
Darstellung ist derselbe Stopp ein einzelner Zeitabzug: Durchfahrtsverlust
plus Standzeit. Beide muessen auf die Millisekunde dasselbe ergeben, sonst
kaeme dieselbe Saison je nach Ansicht anders heraus; ein Test haelt das
fest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.strecke import Segmentart, Strecke
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.kern.tempo import Grenzen
    from rennmanager.konfiguration import Konfiguration


class BoxenstoppFehler(Exception):
    """Die Boxengasse laesst sich auf dieser Strecke nicht bestimmen."""


# ---------------------------------------------------------------------------
# Wo die Boxengasse liegt
# ---------------------------------------------------------------------------
def abschnitt(konfiguration: Konfiguration, strecke: Strecke) -> tuple[int, int]:
    """Die Punktindizes der Boxengasse, ``(von, bis)`` mit ``bis``
    ausgeschlossen.

    Start und Ziel liegen auf Punkt 0, und die Boxengasse laeuft parallel
    dazu - also auf der Geraden um Start/Ziel herum. Die Regel des
    Auftraggebers:

    * Ist die Gerade **nach** Start/Ziel lang, fuehrt die Boxengasse schon
      **vor** der ersten Kurvenkombination wieder auf die Strecke.
    * Ist die Gerade **vor** Start/Ziel lang, zweigt sie erst **nach** der
      letzten Kurvenkombination ab.
    * Dazwischen: mindestens ``min_laenge_m``, hoechstens ``max_laenge_m``.

    Die Untergrenze braucht es, weil Start/Ziel nicht ueberall mitten auf
    einer langen Geraden liegt: In Silverstone endet sie 45 Meter dahinter,
    und ohne Untergrenze waere die Boxengasse 45 Meter lang. Dann wird in
    die Kurvenkombination hinein verlaengert.

    Der Abschnitt laeuft ueber die Start/Ziel-Linie hinweg; dann ist
    ``von > bis`` und er setzt sich am Rundenanfang fort - dieselbe
    Schreibweise, die ``Segment`` schon benutzt.
    """
    arten = np.asarray(strecke.art_je_punkt)
    anzahl = len(arten)
    if anzahl < 3:  # pragma: no cover - Streckendateien sind lang
        raise BoxenstoppFehler(f"{strecke.name} hat zu wenige Punkte")
    gerade = int(Segmentart.GERADE)
    if not (arten == gerade).any():  # pragma: no cover - jede Strecke hat Geraden
        raise BoxenstoppFehler(f"{strecke.name} hat keine Gerade")

    einstellung = konfiguration.wert("boxenstopp")
    ds = strecke.punktabstand_m
    kleinste = max(int(round(einstellung["min_laenge_m"] / ds)), 2)
    groesste = max(int(round(einstellung["max_laenge_m"] / ds)), kleinste)

    # Zuerst: wie weit reicht die Gerade um Start/Ziel nach hinten und
    # nach vorn? Liegt Start/Ziel in einer Kurve, sind beide null.
    zurueck = 0
    while zurueck < anzahl and arten[(-1 - zurueck) % anzahl] == gerade:
        zurueck += 1
    vorwaerts = 0
    while vorwaerts < anzahl and arten[vorwaerts % anzahl] == gerade:
        vorwaerts += 1

    # Auf die erlaubte Laenge bringen: erst kuerzen, dann verlaengern.
    # Gekuerzt wird von beiden Seiten gleich, damit Start und Ziel in der
    # Boxengasse liegen bleiben - die Einfahrt rutscht auf einer langen
    # Geraden nach hinten, die Ausfahrt nach vorn.
    while zurueck + vorwaerts > groesste:
        if zurueck >= vorwaerts:
            zurueck -= 1
        else:
            vorwaerts -= 1
    while zurueck + vorwaerts < kleinste:
        if zurueck <= vorwaerts:
            zurueck += 1
        else:
            vorwaerts += 1

    return (-zurueck) % anzahl, vorwaerts % anzahl


def laenge_m(konfiguration: Konfiguration, strecke: Strecke) -> float:
    """Wie lang die Boxengasse ist."""
    von, bis = abschnitt(konfiguration, strecke)
    punkte = (bis - von) % len(strecke.art_je_punkt) or len(strecke.art_je_punkt)
    return punkte * strecke.punktabstand_m


# ---------------------------------------------------------------------------
# Was sie kostet
# ---------------------------------------------------------------------------
def gedeckeltes_limit(
    konfiguration: Konfiguration, strecke: Strecke, grenzen: Grenzen, grip=1.0
) -> np.ndarray:
    """Das Kurvenlimit mit gedeckelter Boxengasse, in m/s."""
    limit = kern_tempo.kurvenlimit(strecke, grenzen, grip)
    tempo_kmh = konfiguration.wert("boxenstopp", "limit_kmh")
    deckel = tempo_kmh / 3.6
    von, bis = abschnitt(konfiguration, strecke)
    if von < bis:
        limit[von:bis] = np.minimum(limit[von:bis], deckel)
    else:
        limit[von:] = np.minimum(limit[von:], deckel)
        limit[:bis] = np.minimum(limit[:bis], deckel)
    return limit


def durchfahrtsverlust_ms(
    konfiguration: Konfiguration, strecke: Strecke, grenzen: Grenzen, grip=1.0
) -> int:
    """Was die Durchfahrt kostet, ohne Standzeit - in Millisekunden.

    Die Differenz zweier Rundenzeiten: einmal frei gefahren, einmal mit
    dem Deckel auf der Boxengasse. Beide aus demselben Profil, also mit
    Bremsen davor und Beschleunigen danach.
    """
    frei = kern_tempo.geschwindigkeitsprofil(strecke, grenzen, grip)
    mit_box = kern_tempo.geschwindigkeitsprofil(
        strecke,
        grenzen,
        grip,
        limit=gedeckeltes_limit(konfiguration, strecke, grenzen, grip),
    )
    return kern_tempo.rundenzeit_ms(strecke, mit_box) - kern_tempo.rundenzeit_ms(
        strecke, frei
    )


def standzeit_ms(konfiguration: Konfiguration, seedquelle: Seedquelle) -> int:
    """Wie lange das Auto steht - 3 bis 10 Sekunden, gewuerfelt.

    Aus dem Seed, damit derselbe Seed dasselbe Rennen ergibt (GDD 15).
    Die Spanne ist die des Auftraggebers: Ein guter Stopp ist unter vier
    Sekunden, ein verpatzter kostet das Doppelte.
    """
    einstellung = konfiguration.wert("boxenstopp")
    wuerfel = seedquelle.generator()
    sekunden = float(
        wuerfel.uniform(einstellung["standzeit_min_s"], einstellung["standzeit_max_s"])
    )
    return int(round(sekunden * 1000.0))


def stoppverlust_ms(
    konfiguration: Konfiguration,
    strecke: Strecke,
    grenzen: Grenzen,
    seedquelle: Seedquelle,
    grip=1.0,
) -> int:
    """Was ein ganzer Stopp kostet: Durchfahrt plus Standzeit.

    Das ist der Abzug, den der Schnellmodus bucht. Im Zeitraffer faehrt
    das Auto dieselbe Strecke wirklich langsamer und steht dieselbe Zeit -
    beides muss auf die Millisekunde dasselbe ergeben.
    """
    return durchfahrtsverlust_ms(
        konfiguration, strecke, grenzen, grip
    ) + standzeit_ms(konfiguration, seedquelle)
