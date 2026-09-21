"""Kalibriert das Geschwindigkeitsmodell gegen GDD 9.

GDD 9 verlangt: "Kalibriert wird ohne Zufall auf einer kurvigen
Referenzstrecke: Der Beste in Liga 20 faehrt 60 km/h Schnitt, der Beste in
Liga 1 180 km/h bei rund 98.000", nach der Funktion

(Das Zitat stammt aus dem GDD und nennt noch die zwanzig Ligen von damals.
Kalibriert wird gegen die **Funktion**, nicht gegen eine Ligazahl; seit
Punkt 101 gibt es ueberhaupt nur noch ein Feld.)

    v(S) = 55 + 125 * sqrt(S / 98.000)   [km/h]

Dieses Werkzeug sucht die drei freien Konstanten des Geschwindigkeitsmodells
so, dass ein Auto mit durchgehend gleichen Werten ``S`` auf der
Referenzstrecke genau diesen Schnitt faehrt:

    haftung_referenz   Haftungsniveau bei S = 98.000
    anteil_bei_null    Anteil dessen, was das Auto bei S = 0 kann

Alle uebrigen Groessen des Modells sind Verhaeltnisse und bleiben fest.
Mehr als zwei freie Konstanten waeren nicht bestimmbar: Man kann
Endgeschwindigkeit gegen Haftung tauschen und trifft denselben
Rundenschnitt. Deshalb ist die Endgeschwindigkeit bei S = 0 an dasselbe
anteil_bei_null gekoppelt.

Aufruf:
    python -m werkzeuge.kalibriere            zeigt das Ergebnis
    python -m werkzeuge.kalibriere --schreiben traegt es in die Konfiguration ein
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

from rennmanager.kern import auto as kern_auto
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.konfiguration import BALANCING_DATEI, Konfiguration, lade


# Stuetzstellen der Anpassung: die beiden Enden des Feldes plus ein Raster
# ueber die ganze Skala, damit die Kurve auf ganzer Laenge passt und nicht
# nur an zwei Punkten.
#
# Punkt 101: Frueher standen hier die zehn Ligapaare aus
# ``ligen.kontrolle``. Das Feld hat jetzt nur noch zwei Eckwerte - das
# Raster traegt die Anpassung, wie schon vorher zwischen den Ligen.
def feldstellen(konfiguration: Konfiguration) -> list[int]:
    """Die beiden Enden des Feldes (GDD 9, Punkt 101)."""
    return [
        konfiguration.wert("feld", "s_letzter"),
        konfiguration.wert("feld", "s_bester"),
    ]


def stuetzstellen(konfiguration: Konfiguration) -> list[int]:
    maximum = konfiguration.wert("skala", "maximum")
    raster = [round(maximum * (n / 12) ** 2) for n in range(13)]
    return sorted(set(feldstellen(konfiguration) + raster))


def zieltempo(konfiguration: Konfiguration, s: float) -> float:
    """v(S) aus GDD 9."""
    return konfiguration.wert("kalibrierung", "basis_kmh") + konfiguration.wert(
        "kalibrierung", "spanne_kmh"
    ) * math.sqrt(s / konfiguration.wert("skala", "referenz"))


def _abweichung(
    konfiguration: Konfiguration,
    strecke: kern_strecke.Strecke,
    autos: list[kern_auto.Auto],
    werte: tuple[float, float],
) -> float:
    """Mittlere quadratische Abweichung vom Zieltempo, in km/h."""
    haftung_referenz, anteil = werte
    if haftung_referenz <= 0 or not 0.0 < anteil < 1.0:
        return float("inf")

    konfiguration.roh["tempo"]["haftung_referenz"] = haftung_referenz
    konfiguration.roh["tempo"]["anteil_bei_null"] = anteil

    summe = 0.0
    for auto in autos:
        ergebnis = kern_tempo.fahre_runde(konfiguration, strecke, auto)
        s = kern_auto.gesamtwert(konfiguration, auto)
        summe += (ergebnis.schnitt_kmh - zieltempo(konfiguration, s)) ** 2
    return summe / len(autos)


def _nelder_mead(
    ziel, start: tuple[float, ...], schritt: tuple[float, ...],
    durchgaenge: int = 200,
) -> tuple[tuple[float, ...], float]:
    """Kleiner Nelder-Mead-Simplex, damit das Werkzeug ohne SciPy auskommt."""
    ecken = [list(start)]
    for achse, weite in enumerate(schritt):
        ecke = list(start)
        ecke[achse] += weite
        ecken.append(ecke)
    werte = [ziel(tuple(ecke)) for ecke in ecken]

    for _ in range(durchgaenge):
        reihenfolge = sorted(range(len(ecken)), key=lambda i: werte[i])
        ecken = [ecken[i] for i in reihenfolge]
        werte = [werte[i] for i in reihenfolge]
        if abs(werte[-1] - werte[0]) < 1e-9:
            break

        mitte = [sum(achse) / len(achse) for achse in zip(*ecken[:-1], strict=True)]
        spiegel = [2 * m - s for m, s in zip(mitte, ecken[-1], strict=True)]
        wert_spiegel = ziel(tuple(spiegel))

        if wert_spiegel < werte[0]:
            weit = [3 * m - 2 * s for m, s in zip(mitte, ecken[-1], strict=True)]
            wert_weit = ziel(tuple(weit))
            ecken[-1], werte[-1] = (
                (weit, wert_weit) if wert_weit < wert_spiegel else (spiegel, wert_spiegel)
            )
        elif wert_spiegel < werte[-2]:
            ecken[-1], werte[-1] = spiegel, wert_spiegel
        else:
            eng = [(m + s) / 2 for m, s in zip(mitte, ecken[-1], strict=True)]
            wert_eng = ziel(tuple(eng))
            if wert_eng < werte[-1]:
                ecken[-1], werte[-1] = eng, wert_eng
            else:
                for i in range(1, len(ecken)):
                    ecken[i] = [(a + b) / 2 for a, b in zip(ecken[0], ecken[i], strict=True)]
                    werte[i] = ziel(tuple(ecken[i]))

    beste = min(range(len(ecken)), key=lambda i: werte[i])
    return tuple(ecken[beste]), werte[beste]


def kalibriere(konfiguration: Konfiguration) -> tuple[tuple[float, float], float]:
    """Sucht die drei Konstanten und liefert sie mit der Restabweichung."""
    name = konfiguration.wert("kalibrierung", "referenzstrecke")
    strecke = kern_strecke.lade(konfiguration, name)
    autos = [kern_auto.gleichverteilt(konfiguration, s) for s in stuetzstellen(konfiguration)]

    start = (
        konfiguration.wert("tempo", "haftung_referenz"),
        konfiguration.wert("tempo", "anteil_bei_null"),
    )
    ziel = lambda werte: _abweichung(konfiguration, strecke, autos, werte)  # noqa: E731
    return _nelder_mead(ziel, start, schritt=(5.0, 0.08))


def schreibe(werte: tuple[float, float], ordner: Path) -> None:
    """Traegt die gefundenen Konstanten in die Balancing-Datei ein."""
    pfad = ordner / BALANCING_DATEI
    text = pfad.read_text(encoding="utf-8")
    for name, wert, stellen in (
        ("haftung_referenz", werte[0], 3),
        ("anteil_bei_null", werte[1], 4),
    ):
        muster = re.compile(rf"^{name} = .*$", re.M)
        text, anzahl = muster.subn(f"{name} = {wert:.{stellen}f}", text)
        if anzahl != 1:
            raise SystemExit(f"{name} steht {anzahl}-mal in {pfad}, erwartet genau einmal")
    pfad.write_text(text, encoding="utf-8")


def bericht(konfiguration: Konfiguration) -> None:
    """Stellt Ist und Soll auf der Referenzstrecke gegenueber."""
    name = konfiguration.wert("kalibrierung", "referenzstrecke")
    strecke = kern_strecke.lade(konfiguration, name)
    print(f"\nReferenzstrecke: {name}, {strecke.laenge_m:.0f} m\n")
    print(f"{'S':>8}{'Ist km/h':>10}{'Soll km/h':>11}{'Abw.':>8}{'Rundenzeit':>13}{'vmax':>8}")

    from rennmanager.kern.zeit import formatiere_dauer

    groesste = 0.0
    for s in stuetzstellen(konfiguration):
        ergebnis = kern_tempo.fahre_runde(
            konfiguration, strecke, kern_auto.gleichverteilt(konfiguration, s)
        )
        soll = zieltempo(konfiguration, s)
        abweichung = ergebnis.schnitt_kmh - soll
        groesste = max(groesste, abs(abweichung))
        marke = " <- Feld" if s in feldstellen(konfiguration) else ""
        print(
            f"{s:>8}{ergebnis.schnitt_kmh:>10.2f}{soll:>11.2f}{abweichung:>+8.2f}"
            f"{formatiere_dauer(ergebnis.zeit_ms):>13}"
            f"{ergebnis.hoechstgeschwindigkeit_kmh:>8.0f}{marke}"
        )
    print(f"\nGroesste Abweichung: {groesste:.2f} km/h")


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument(
        "--schreiben", action="store_true", help="Ergebnis in die Konfiguration eintragen"
    )
    argumente = zerleger.parse_args()

    konfiguration = lade()
    print("Kalibriere gegen GDD 9 ...")
    werte, abweichung = kalibriere(konfiguration)
    print(
        f"  haftung_referenz                 = {werte[0]:.3f} m/s^2\n"
        f"  anteil_bei_null                  = {werte[1]:.4f}\n"
        f"  mittlere quadratische Abweichung = {abweichung:.4f} (km/h)^2"
    )

    if argumente.schreiben:
        schreibe(werte, konfiguration.quelle)
        print(f"\nEingetragen in {konfiguration.quelle / BALANCING_DATEI}")
        konfiguration = lade()

    bericht(konfiguration)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
