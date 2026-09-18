"""Die Boxengasse (Punkt 39).

Die Streckendateien enthalten keine Boxengasse - nur Ideallinie,
Segmente und Sektoren. Der Auftraggeber hat entschieden, sie aus der
Geometrie abzuleiten, und zwar so, wie sie auf fast jeder echten Strecke
liegt: **parallel zur Geraden um Start und Ziel.** Sie zweigt nach der
letzten Kurvenkombination ab und fuehrt schon vor der ersten wieder auf
die Strecke, begrenzt auf 500 bis 750 Meter. Auf diesem Stueck faehrt das
Auto 80 statt Renntempo; davor bremst es, danach beschleunigt es wieder.

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
from rennmanager.kern.auto import Auto
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
_REFERENZZEITEN: dict[tuple[int, str], int] = {}


def referenzrundenzeit_ms(konfiguration: Konfiguration, strecke: Strecke) -> int:
    """Die Rundenzeit dieser Strecke bei der Referenzstaerke aus GDD 9.

    Eine reine **Streckeneigenschaft**: Sie haengt nicht davon ab, wer
    gerade faehrt. Daran wird gemessen, ob eine Boxengasse zu teuer ist -
    sonst haette jedes Auto seine eigene Boxengasse, und die Geometrie
    einer Strecke haenge am Fahrerfeld.
    """
    schluessel = (id(konfiguration), strecke.name)
    gemerkt = _REFERENZZEITEN.get(schluessel)
    if gemerkt is not None:
        return gemerkt
    referenz = konfiguration.wert("skala", "referenz")
    auto = Auto(
        kuerzel="REF",
        name="Referenz",
        werte={f.schluessel: referenz for f in konfiguration.faehigkeiten},
        wetterwerte=dict.fromkeys(konfiguration.zusatzfaehigkeiten, referenz),
    )
    grenzen = kern_tempo.grenzen_aus(konfiguration, auto)
    zeit = kern_tempo.rundenzeit_ms(
        strecke, kern_tempo.geschwindigkeitsprofil(strecke, grenzen)
    )
    _REFERENZZEITEN[schluessel] = zeit
    return zeit


def _nur_gerade(arten: np.ndarray, gerade: int, kleinste: int, groesste: int):
    """Der Abschnitt allein auf der Geraden um Start und Ziel.

    Der Rueckfall, wenn die Kurvenregel zu weit greift: Dann zweigt die
    Boxengasse erst nach der letzten Kurvenkombination ab und fuehrt schon
    vor der ersten wieder auf die Strecke.
    """
    anzahl = len(arten)
    zurueck = 0
    while zurueck < anzahl and arten[(-1 - zurueck) % anzahl] == gerade:
        zurueck += 1
    vorwaerts = 0
    while vorwaerts < anzahl and arten[vorwaerts % anzahl] == gerade:
        vorwaerts += 1

    # Gekuerzt und verlaengert wird von beiden Seiten gleich, damit Start
    # und Ziel in der Boxengasse liegen bleiben: Die Einfahrt rutscht auf
    # einer langen Geraden nach hinten, die Ausfahrt nach vorn.
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


def abschnitt(konfiguration: Konfiguration, strecke: Strecke) -> tuple[int, int]:
    """Die Punktindizes der Boxengasse, ``(von, bis)`` mit ``bis``
    ausgeschlossen.

    Die Boxengasse liegt **auf der Geraden um Start und Ziel**: Sie zweigt
    nach der letzten Kurvenkombination ab und fuehrt schon vor der ersten
    wieder auf die Strecke. Ist die Gerade laenger als noetig, rutscht die
    Einfahrt nach hinten und die Ausfahrt nach vorn; ist sie kuerzer,
    reicht die Boxengasse in die Kurven hinein.

    Zuerst stand hier eine zweite, geometrisch huebschere Regel - von der
    Geraden vor Start/Ziel durch die Kurvenkombination danach. Gemessen
    war sie auf keiner einzigen Strecke besser: Die Spanne der
    Durchfahrtsverluste ging von 15,3 bis 38,0 Sekunden statt von 14,2 bis
    31,8, und Monza kam auf 1350 Meter. Eine Regel genuegt.

    Die Obergrenze als **Anteil der Runde** trifft nur sehr kurze
    Strecken: Der Norisring mit 2260 Metern kaeme sonst auf 750 Meter
    Boxengasse bei 42,6 Sekunden Rundenzeit - ein Stopp waere teurer als
    eine ganze Runde. Mit dem Anteil landet er bei 452 Metern; alle
    anderen 19 Strecken bleiben unberuehrt.

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
    groesste = max(int(round(einstellung["max_laenge_m"] / ds)), 2)
    kleinste = min(max(int(round(einstellung["min_laenge_m"] / ds)), 2), groesste)
    von, bis = _nur_gerade(arten, gerade, kleinste, groesste)
    return _auf_zeitanteil(konfiguration, strecke, arten, gerade, von, bis, kleinste)


def _auf_zeitanteil(
    konfiguration: Konfiguration,
    strecke: Strecke,
    arten: np.ndarray,
    gerade: int,
    von: int,
    bis: int,
    kleinste: int,
) -> tuple[int, int]:
    """Kuerzt die Boxengasse, bis ein Stopp unter dem Zeitanteil bleibt.

    Der Anteil der **Laenge** sagt den Anteil der **Zeit** nicht voraus:
    Gemessen kostete Monza bei 13 % Rundenlaenge 42 % Rundenzeit,
    Catalunya bei 16 % nur 38 %. Schnelle Strecken bestrafen die
    Boxengasse staerker, weil dort der Unterschied zwischen Renntempo und
    80 km/h groesser ist. Gekappt wird deshalb direkt ueber die Zeit.

    Gemessen wird an der **Referenzrundenzeit** der Strecke, nicht an der
    des gerade fahrenden Autos - sonst haette jedes Auto seine eigene
    Boxengasse.

    Gekuerzt wird nur, wo noetig: 15 der 20 Strecken bleiben unberuehrt.
    """
    ziel = konfiguration.wert("boxenstopp", "max_anteil_rundenzeit")
    einstellung = konfiguration.wert("boxenstopp")
    mittlere_standzeit = (
        (einstellung["standzeit_min_s"] + einstellung["standzeit_max_s"]) / 2.0 * 1000.0
    )
    rundenzeit = referenzrundenzeit_ms(konfiguration, strecke)
    erlaubt = ziel * rundenzeit - mittlere_standzeit
    if erlaubt <= 0:  # pragma: no cover - so kurz ist keine Strecke
        raise BoxenstoppFehler(
            f"{strecke.name}: Schon die Standzeit sprengt {ziel:.0%} der Rundenzeit"
        )

    anzahl = len(arten)
    punkte = (bis - von) % anzahl or anzahl
    for _ in range(12):
        if _verlust_auf(konfiguration, strecke, von, bis) <= erlaubt:
            return von, bis
        if punkte <= kleinste:
            return von, bis
        punkte -= max(punkte // 20, 1)
        von, bis = _nur_gerade(arten, gerade, punkte, punkte)
    return von, bis  # pragma: no cover - zwoelf Schritte reichen immer


def _verlust_auf(
    konfiguration: Konfiguration, strecke: Strecke, von: int, bis: int
) -> int:
    """Durchfahrtsverlust eines Abschnitts beim Referenzauto."""
    referenz = konfiguration.wert("skala", "referenz")
    auto = Auto(
        kuerzel="REF",
        name="Referenz",
        werte={f.schluessel: referenz for f in konfiguration.faehigkeiten},
        wetterwerte=dict.fromkeys(konfiguration.zusatzfaehigkeiten, referenz),
    )
    grenzen = kern_tempo.grenzen_aus(konfiguration, auto)
    limit = kern_tempo.kurvenlimit(strecke, grenzen, 1.0)
    deckel = konfiguration.wert("boxenstopp", "limit_kmh") / 3.6
    if von < bis:
        limit[von:bis] = np.minimum(limit[von:bis], deckel)
    else:
        limit[von:] = np.minimum(limit[von:], deckel)
        limit[:bis] = np.minimum(limit[:bis], deckel)
    mit_box = kern_tempo.rundenzeit_ms(
        strecke, kern_tempo.geschwindigkeitsprofil(strecke, grenzen, limit=limit)
    )
    return mit_box - referenzrundenzeit_ms(konfiguration, strecke)


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
