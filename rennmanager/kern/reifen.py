"""Reifenverschleiss (GDD 4).

"Reifen: Verschleiss senkt das Tempo und erhoeht die Fehlerquote; vorerst
keine Boxenstopps." Der Zustand faellt ueber die Renndistanz von 1,0
(frisch) Richtung 0,0 (abgefahren); wie schnell, haengt vom Auto ab.

Zwei Eigenschaften greifen an verschiedenen Stellen an:

* Der Bereich ``ve`` der Wirkungsmatrix - getragen von F10
  Reifenhaltbarkeit, F14, F16 und D14 Reifenmanagement - bestimmt, wie
  schnell die Reifen abbauen.
* Der **Reifenfluesterer** bestimmt, wie sehr abgebaute Reifen wehtun. Er
  senkt nicht den Verschleiss, sondern dessen Wirkung: Mit ihm holt ein
  Fahrer aus schlechten Reifen noch Zeit heraus.

Dass beide getrennt sind, ist der Grund, warum sich in der zweiten
Rennhaelfte ueberhaupt noch etwas bewegt: Ein Auto, das seine Reifen
schont, ist frueh langsamer und spaet schneller als eines, das sie
verheizt - die Linien kreuzen sich.

Der Streckenfaktor kommt aus der Querbeschleunigung der Runde, das Wetter
ueber den Multiplikator aus GDD 7.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern.auto import Auto, bereichswert
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.tempo import leistungsanteil
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Schluessel der neuen Fahrereigenschaft in Auto.wetterwerte - sie steht
# wie die Wetterfaehigkeiten ausserhalb der Wirkungsmatrix.
FLUESTERER = "reifenfluesterer"


class ReifenFehler(Exception):
    """Die Reifen lassen sich so nicht rechnen."""


def streckenfaktor(konfiguration: Konfiguration, strecke: Strecke, mittelwert: float) -> float:
    """Wie hart eine Strecke die Reifen nimmt (Entscheidung zu Punkt 10).

    Grundlage ist die Querbeschleunigung ueber die Runde - die Summe von
    1/Radius je Meter -, normiert auf den Mittelwert aller Strecken. Sie
    trennt schnelle Kurven von engen, was der blosse Kurvenanteil nicht
    leistet.
    """
    if konfiguration.wert("reifen", "streckenfaktor", "grundlage") != "querbeschleunigung":
        raise ValueError("Nur die Grundlage 'querbeschleunigung' ist umgesetzt")
    return querbeschleunigung(strecke) / max(mittelwert, 1e-9)


def wirksamer_streckenfaktor(konfiguration: Konfiguration, wert: float) -> float:
    """Was vom Streckenfaktor beim **Verschleiss** ankommt (Punkt 92).

    Der rohe Faktor spannt ueber die zwanzig Strecken von 1,263
    (Zandvoort) bis 0,537 (Monza) - das 2,35fache. So weit auseinander
    lassen sich die Stoppzahlen nicht mehr einfangen: Monza kommt mit
    einem Stopp aus und braucht nie einen zweiten, Zandvoort schafft
    keinen Zwei-Stopp mehr. Der Exponent zieht die Spanne zusammen, ohne
    die Reihenfolge der Strecken anzutasten.

    Er wirkt **nur hier**, nicht auf den Faktor selbst: Die Anzeige und
    ``weich_hoechstens_streckenfaktor`` vergleichen weiter gegen den
    rohen Wert - sonst faellt die Weich-Regel auf allen zwanzig Strecken
    weg, weil keine mehr ueber 1,15 kaeme.
    """
    exponent = float(
        konfiguration.wert("reifen", "streckenfaktor").get("verschleiss_exponent", 1.0)
    )
    if exponent == 1.0 or wert <= 0.0:
        return wert
    return float(wert**exponent)


def querbeschleunigung(strecke: Strecke) -> float:
    """Mittlere Kruemmung der Runde, 1/m."""
    radius = np.clip(strecke.radius_m, 1.0, None)
    return float((1.0 / radius).sum() * strecke.punktabstand_m / strecke.laenge_m)


def mittlere_querbeschleunigung(strecken) -> float:
    """Bezugsgroesse des Streckenfaktors ueber alle Strecken."""
    werte = [querbeschleunigung(strecke) for strecke in strecken]
    return sum(werte) / len(werte)


@dataclass(frozen=True)
class Mischung:
    """Eine Reifenmischung (Punkt 39)."""

    schluessel: str
    name: str
    kuerzel: str
    farbe: str
    # Faktor aufs Tempo bei frischen Reifen, gemessen an "hart" = 1,0.
    tempo: float
    # Faktor auf den Verschleiss - wer schneller faehrt, haelt kuerzer.
    verschleiss: float
    # Fuer welche Naesse sie gebaut ist: 0 trocken, 1 voll unter Wasser.
    naesse: float


def mischungen(konfiguration: Konfiguration) -> tuple[Mischung, ...]:
    """Alle Mischungen aus der Konfiguration, in ihrer Reihenfolge."""
    return tuple(
        Mischung(**zeile)
        for zeile in konfiguration.wert("reifen", "mischungen", "liste")
    )


def mischung(konfiguration: Konfiguration, schluessel: str) -> Mischung:
    """Eine Mischung ueber ihren Schluessel."""
    for eine in mischungen(konfiguration):
        if eine.schluessel == schluessel:
            return eine
    raise ReifenFehler(f"Unbekannte Reifenmischung: {schluessel}")


def standardmischung(konfiguration: Konfiguration) -> Mischung:
    """Die Mischung, mit der gefahren wird, wenn keine gewaehlt wurde.

    Die mittlere der Trockenmischungen - sie steht in der Konfiguration
    an dritter Stelle von unten. Gebraucht wird sie ueberall dort, wo noch
    keine Strategie vorliegt: in Tests, im Editor und in der Kalibrierung.
    """
    alle = mischungen(konfiguration)
    trocken = [m for m in alle if m.naesse == 0.0]
    if not trocken:  # pragma: no cover - es gibt immer Trockenmischungen
        raise ReifenFehler("Keine Trockenmischung in der Konfiguration")
    return trocken[len(trocken) // 2]


def naesse_von(konfiguration: Konfiguration, wetter) -> float:
    """Wie nass diese Wetterlage ist - 0 trocken bis 1 unter Wasser.

    Mehrere Lagen zugleich (das Wetter kann je Sektor wechseln, GDD 7):
    Es zaehlt die nasseste, denn danach richtet sich die Reifenwahl.
    """
    tabelle = konfiguration.wert("reifen", "mischungen", "naesse_je_lage")
    if isinstance(wetter, str):
        wetter = (wetter,)
    return max((float(tabelle.get(lage, 0.0)) for lage in wetter), default=0.0)


def _fehlgriff(konfiguration: Konfiguration, misch: Mischung, naesse: float) -> float:
    """Wie weit die Mischung an der Lage vorbeigeht, 0 bis 1."""
    return abs(naesse - misch.naesse)


def haltbarkeit(konfiguration: Konfiguration, auto: Auto) -> float:
    """Wie weit dieses Auto seine Reifen traegt, als Faktor um 1,0.

    Aus dem Bereich ``ve`` der Wirkungsmatrix (F10 Reifenhaltbarkeit,
    F14, F16, D14 Reifenmanagement).
    """
    einstellung = konfiguration.wert("reifen", "verschleiss")
    anteil = min(
        leistungsanteil(
            bereichswert(konfiguration, auto, "ve"), konfiguration.wert("skala", "referenz")
        ),
        1.0,
    )
    bei_null = einstellung["verschleiss_bei_null"]
    bei_referenz = einstellung["verschleiss_bei_referenz"]
    ueber_distanz = bei_null + anteil * (bei_referenz - bei_null)
    return bei_referenz / max(ueber_distanz, 1e-6)


def stintweite_m(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    streckenfaktor_wert: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
) -> float:
    """Wie weit ein Satz dieser Mischung traegt, in Metern.

    **Nicht mehr an der Renndistanz.** Vorher war der Verschleiss durch
    die Renndistanz geteilt, ein Satz hielt also per Konstruktion genau
    ein Rennen - Boxenstopps waeren sinnlos gewesen. Jetzt traegt ein
    Stint eine feste Strecke, und wie viele Stopps ein Rennen kostet,
    ergibt sich daraus: Liga 1 faehrt 293 km, Liga 20 nur 100.
    """
    einstellung = konfiguration.wert("reifen", "mischungen")
    strafe = 1.0 + einstellung["naesse_strafe_verschleiss"] * _fehlgriff(
        konfiguration, misch, naesse
    )
    wirksam = wirksamer_streckenfaktor(konfiguration, streckenfaktor_wert)
    teiler = misch.verschleiss * wirksam * wetterfaktor * strafe
    return (
        einstellung["stint_basis_m"]
        * haltbarkeit(konfiguration, auto)
        / max(teiler, 1e-6)
    )


def mit_streuung(
    konfiguration: Konfiguration, misch: Mischung, seedquelle: Seedquelle
) -> Mischung:
    """Dieselbe Mischung mit den kleinen Wuerfen eines Rennens.

    Der Auftraggeber hat es so festgelegt: Je Fahrer, Mischung und Rennen
    wird gewuerfelt - ``streuung_verschleiss`` auf den
    **Verschleissfaktor** und ``streuung_tempo`` auf den **Tempofaktor**.
    Die Vorausberechnung der Varianten kennt beide **nicht**; geplant wird
    auf den Sollwerten. Dass Plan und Rennen dadurch auseinanderlaufen,
    ist so gewollt: Eine Strategie geht mal knapper auf als auf dem
    Papier, und zwei Autos auf derselben Folge fahren nicht dieselbe
    Runde.

    Zwei getrennte Zweige, damit ein Satz nicht zugleich schneller **und**
    haltbarer herauskommt - das waere kein Zufall mehr, sondern ein
    besserer Reifen.
    """
    einstellung = konfiguration.wert("reifen", "verschleiss")
    fuer_verschleiss = einstellung["streuung_verschleiss"]
    fuer_tempo = einstellung["streuung_tempo"]
    if fuer_verschleiss <= 0.0 and fuer_tempo <= 0.0:
        return misch
    zweig = seedquelle.zweig(misch.schluessel)
    auf_verschleiss = float(
        zweig.zweig("verschleiss").generator().uniform(-fuer_verschleiss, fuer_verschleiss)
    )
    auf_tempo = float(
        zweig.zweig("tempo").generator().uniform(-fuer_tempo, fuer_tempo)
    )
    return replace(
        misch,
        verschleiss=max(misch.verschleiss + auf_verschleiss, 1e-6),
        tempo=max(misch.tempo + auf_tempo, 1e-6),
    )


def verschleiss_je_meter(
    konfiguration: Konfiguration,
    auto: Auto,
    misch: Mischung,
    streckenfaktor_wert: float = 1.0,
    wetterfaktor: float = 1.0,
    naesse: float = 0.0,
) -> float:
    """Wie stark der Reifenzustand je gefahrenem Meter faellt.

    Der Kehrwert der Stintweite: Nach ``stintweite_m`` Metern steht der
    Zustand bei 0.
    """
    return 1.0 / max(
        stintweite_m(
            konfiguration, auto, misch, streckenfaktor_wert, wetterfaktor, naesse
        ),
        1.0,
    )


def mischungsfaktor(
    konfiguration: Konfiguration, misch: Mischung, naesse: float = 0.0
) -> float:
    """Faktor aufs Tempo durch die Mischungswahl (Punkt 39).

    Der Zeitgewinn der Mischung, gemindert um den Fehlgriff: Ein
    Trockenreifen im Starkregen verliert zweistellig, ein Regenreifen auf
    trockener Strecke ebenso.
    """
    strafe = konfiguration.wert(
        "reifen", "mischungen", "naesse_strafe_tempo"
    ) * _fehlgriff(konfiguration, misch, naesse)
    return misch.tempo * (1.0 - strafe)


def zustand(verschleiss: float) -> float:
    """Reifenzustand aus dem aufgelaufenen Verschleiss, 1,0 bis 0,0."""
    return float(np.clip(1.0 - verschleiss, 0.0, 1.0))


def _daempfung(konfiguration: Konfiguration, auto: Auto) -> float:
    """Wie stark der Reifenfluesterer die Wirkung des Abbaus senkt, 0 bis 1."""
    einstellung = konfiguration.wert("reifen", "fluesterer")
    anteil = min(
        leistungsanteil(auto.wetterwert(FLUESTERER), konfiguration.wert("skala", "referenz")),
        1.0,
    )
    return einstellung["max_daempfung"] * anteil


def grip(konfiguration: Konfiguration, zustandswert: float) -> float:
    """Der Grip bei diesem Restprofil - die Kurve aus Punkt 39.

    **Das Optimum liegt bei 80 % Restprofil, nicht bei 100.** Ein frischer
    Reifen muss erst arbeiten; danach faellt er erst flach und gegen Ende
    steil ab. Bei null ist noch ein Viertel des Startgrips uebrig - ein
    abgefahrener Reifen ist langsam, aber nicht unfahrbar.

    Das ist die wichtigste Aenderung am Reifenmodell: Erst dadurch ist ein
    langer Stint etwas wert und ein frueher Stopp ein Risiko. Die alte
    Parabel fiel ab der ersten Runde und machte jeden Stopp zum Gewinn.
    """
    einstellung = konfiguration.wert("reifen", "verschleiss")
    stellen = einstellung["zustand_stuetzstellen"]
    werte = einstellung["grip_stuetzstellen"]
    # np.interp will aufsteigende x-Werte; die Tabelle laeuft absteigend.
    return float(
        np.interp(
            float(np.clip(zustandswert, 0.0, 1.0)), list(reversed(stellen)),
            list(reversed(werte))
        )
    )


def bestgrip(konfiguration: Konfiguration) -> float:
    """Der Grip im Optimum - die Bezugsgroesse der Kurve."""
    return max(konfiguration.wert("reifen", "verschleiss", "grip_stuetzstellen"))


def tempofaktor(konfiguration: Konfiguration, auto: Auto, verschleiss: float) -> float:
    """Faktor auf das Tempo bei diesem Verschleiss (GDD 4, Punkt 39).

    Gemessen am Optimum der Kurve: Im Optimum 1,0, davor und danach
    weniger. Der Reifenfluesterer senkt den Verlust um bis zu 60 % - er
    aendert die Kurve nicht, nur ihre Wirkung.
    """
    anteil = grip(konfiguration, zustand(verschleiss)) / bestgrip(konfiguration)
    return 1.0 - (1.0 - anteil) * (1.0 - _daempfung(konfiguration, auto))


def fehlerfaktor(konfiguration: Konfiguration, auto: Auto, verschleiss: float) -> float:
    """Multiplikator auf die Fehlerquote bei diesem Verschleiss (GDD 4).

    Dieselbe Kurve wie das Tempo: Abgefahrene Reifen kosten nicht nur
    Zeit, sie machen Fehler - und zwar ab derselben Stelle. Frueher hing
    die Fehlerquote an einer eigenen Parabel und stieg schon, waehrend die
    Reifen noch besser wurden.
    """
    einstellung = konfiguration.wert("reifen", "verschleiss")
    anteil = grip(konfiguration, zustand(verschleiss)) / bestgrip(konfiguration)
    boden = min(einstellung["grip_stuetzstellen"]) / bestgrip(konfiguration)
    # 0 im Optimum, 1 am Kurvenboden.
    tiefe = (1.0 - anteil) / max(1.0 - boden, 1e-6)
    zuschlag = einstellung["fehlerzuschlag_voll"] * tiefe
    return 1.0 + zuschlag * (1.0 - _daempfung(konfiguration, auto))
