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

Der Deckel gilt nur, wo die Strecke ueberhaupt schneller waere: Gerechnet
wird mit dem Minimum aus Streckenlimit und dem Ligalimit. In Liga 1
liegt die Boxengasse deshalb durchgehend am Deckel; in Liga 10 auf zwei
der zwanzig Strecken nicht: In Spa sind 6 der 100 Gassenpunkte schon von
sich aus langsamer als die 70 km/h dieser Liga - dort faehrt das Auto
sein eigenes Tempo.

Ein ganzer Stopp besteht aus vier Posten:

* dem **Durchfahrtsverlust** - der Differenz der beiden Rundenzeiten, mit
  und ohne Deckel,
* dem **Bremsen** bis zum Stillstand,
* der **Standzeit** von 6 bis 12 Sekunden,
* dem **Anfahren** aus dem Stand.

Bremsen und Anfahren kommen aus den Grenzen dieses Autos, nicht aus einer
Pauschale. Sie muessen ausdruecklich gerechnet werden: Das
Geschwindigkeitsprofil hat die Bremszonen schon eingerechnet und bremst
deshalb ohne Zeitverlust - fuer einen Halt in der Box stimmt das nicht.

**Zwei Wege, ein Ergebnis.** Im Zeitraffer faehrt das Auto die Boxengasse
wirklich langsamer - man sieht es kriechen - und steht wirklich. Im
Schnellmodus ohne Darstellung ist derselbe Stopp ein einzelner Zeitabzug.
Beide muessen dasselbe ergeben, sonst kaeme dieselbe Saison je nach
Ansicht anders heraus; ein Test haelt das fest.
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
    eine ganze Runde. Mit dem Anteil landet er bei 515 Metern; alle
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

    Die Grenze gilt der **Durchfahrt allein**, nicht dem ganzen Stopp. So
    hat es der Auftraggeber entschieden, als die Standzeit von 3-10 auf
    6-12 Sekunden stieg: Die Standzeit ist Sache der Mannschaft, die
    Boxengasse ist Sache der Strecke. Waere sie eingerechnet, wuerde die
    Gasse kuerzer, nur weil das Reifenwechseln laenger dauert - Spielberg
    fiel damit von 610 auf 480 Meter.

    Gekuerzt wird nur, wo noetig: 19 der 20 Strecken bleiben unberuehrt,
    allein der Norisring wird von 750 auf 515 Meter gestutzt.
    """
    ziel = konfiguration.wert("boxenstopp", "max_anteil_rundenzeit")
    erlaubt = ziel * referenzrundenzeit_ms(konfiguration, strecke)

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
    limit = _decke_ab(
        konfiguration, kern_tempo.kurvenlimit(strecke, grenzen, 1.0), von, bis
    )
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
def limit_ms(konfiguration: Konfiguration) -> float:
    """Das Boxenlimit, in m/s.

    Punkt 101: Eine Liga, ein Limit - die Staffelung nach Ligen ist mit
    den Ligen weggefallen.
    """
    return konfiguration.wert("boxenstopp", "limit_kmh") / 3.6


def _decke_ab(
    konfiguration: Konfiguration,
    limit: np.ndarray,
    von: int,
    bis: int,
):
    """Setzt das Boxentempo auf dem Abschnitt, in m/s.

    Zwei Faelle, beide vom Auftraggeber:

    * Wo die Strecke **schneller** waere als das Limit, gilt das Limit.
    * Wo sie ohnehin **langsamer** ist, gilt ihr eigenes Tempo minus
      einem kleinen Abzug. Ohne ihn kostete die Boxengasse dort gar
      nichts, wo die Strecke ohnehin langsam ist: In Spa faehrt das
      schwaechste Auto auf der Start-Ziel-Geraden stellenweise nur
      53 km/h, in Yas Marina 52.
    """
    deckel = limit_ms(konfiguration)
    abzug = 1.0 - konfiguration.wert("boxenstopp", "abzug_unter_limit")

    def setze(teil: np.ndarray) -> np.ndarray:
        return np.where(teil < deckel, teil * abzug, deckel)

    if von < bis:
        limit[von:bis] = setze(limit[von:bis])
    else:
        limit[von:] = setze(limit[von:])
        limit[:bis] = setze(limit[:bis])
    return limit


def gedeckeltes_limit(
    konfiguration: Konfiguration,
    strecke: Strecke,
    grenzen: Grenzen,
    grip=1.0,
) -> np.ndarray:
    """Das Kurvenlimit mit gedeckelter Boxengasse, in m/s."""
    von, bis = abschnitt(konfiguration, strecke)
    return _decke_ab(
        konfiguration, kern_tempo.kurvenlimit(strecke, grenzen, grip), von, bis
    )


def durchfahrtsverlust_ms(
    konfiguration: Konfiguration,
    strecke: Strecke,
    grenzen: Grenzen,
    grip=1.0,
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


def anfahrverlust_ms(
    konfiguration: Konfiguration, grenzen: Grenzen
) -> int:
    """Was das Anfahren aus dem Stand kostet, in Millisekunden.

    ``durchfahrtsverlust_ms`` rechnet, als rollte das Auto mit dem
    Boxenlimit durch. Wer aber steht, muss erst wieder auf dieses Limit
    beschleunigen. Bis dahin vergeht ``v / a``; dieselbe Strecke haette
    rollend ``v / (2a)`` gedauert - die Differenz ist genau die Haelfte
    davon.

    Gerechnet wird mit der Beschleunigungsgrenze des Autos aus GDD 9,
    nicht mit einer eigenen Zahl: Ein Auto mit mehr Antrieb kommt schneller
    aus der Box.
    """
    tempo = limit_ms(konfiguration)
    return int(round(1000.0 * tempo / (2.0 * max(grenzen.laengs, 1e-6))))


def bremsverlust_ms(
    konfiguration: Konfiguration, grenzen: Grenzen
) -> int:
    """Was das Bremsen bis zum Stillstand kostet, in Millisekunden.

    Das Gegenstueck zum Anfahren, mit der Bremsgrenze statt der
    Beschleunigungsgrenze: ``v / b`` zum Stehen, rollend waeren es
    ``v / (2b)`` gewesen. Die Simulation bildet das nicht von selbst ab -
    sie bremst ohne Zeitverlust, weil das Geschwindigkeitsprofil die
    Bremszonen schon eingerechnet hat. Fuer den Halt in der Box muss der
    Posten deshalb ausdruecklich dazu.
    """
    tempo = limit_ms(konfiguration)
    return int(round(1000.0 * tempo / (2.0 * max(grenzen.brems, 1e-6))))


def haltverlust_ms(
    konfiguration: Konfiguration, grenzen: Grenzen
) -> int:
    """Bremsen und Anfahren zusammen - was der Halt selbst kostet."""
    return bremsverlust_ms(konfiguration, grenzen) + anfahrverlust_ms(
        konfiguration, grenzen
    )


def mittlere_standzeit_ms(konfiguration: Konfiguration) -> int:
    """Die Standzeit, mit der **vor** dem Rennen gerechnet wird.

    Die Mitte der Spanne. Wer die Strategien vorausrechnet, kennt die
    einzelnen Wuerfe noch nicht - er braucht eine Zahl, und die Mitte ist
    die einzige, die keine Strategie bevorzugt.
    """
    einstellung = konfiguration.wert("boxenstopp")
    mitte = (einstellung["standzeit_min_s"] + einstellung["standzeit_max_s"]) / 2.0
    return int(round(mitte * 1000.0))


def standzeit_ms(konfiguration: Konfiguration, seedquelle: Seedquelle) -> int:
    """Wie lange das Auto steht - 6 bis 12 Sekunden, gewuerfelt.

    Aus dem Seed, damit derselbe Seed dasselbe Rennen ergibt (GDD 15).
    Die Spanne ist die des Auftraggebers und meint das reine Stehen;
    Bremsen und Anfahren stehen daneben.
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
    """Was ein ganzer Stopp kostet: Durchfahrt, Bremsen, Stehen, Anfahren.

    Das ist der Abzug, den der Schnellmodus bucht. Im Zeitraffer faehrt
    das Auto dieselbe Strecke wirklich langsamer, steht dieselbe Zeit und
    beschleunigt danach wieder - alle drei Posten muessen dasselbe
    ergeben, sonst faehrt dieselbe Strategie in den beiden Modi
    verschiedene Rennen.
    """
    return (
        durchfahrtsverlust_ms(konfiguration, strecke, grenzen, grip)
        + standzeit_ms(konfiguration, seedquelle)
        + haltverlust_ms(konfiguration, grenzen)
    )
