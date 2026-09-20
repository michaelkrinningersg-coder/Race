"""Zeigt, wie ein Feld der Liga 1 seine Boxenstopps verteilt (Punkt 39).

Ein Balancing-Werkzeug, **kein Test**: Es faehrt fuenf Rennen und schreibt
auf, wer auf welcher Mischung startet, in welcher Runde er stoppt und
wieviel Profil dann noch auf den Reifen war. Damit laesst sich beurteilen,
ob die Strategie plausible Stintlaengen hervorbringt - und ob das Feld
dabei auseinandergeht oder alle dasselbe fahren.

**Die fuenf Strecken** sind nicht ausgesucht, sondern gezogen: nach dem
Streckenfaktor aus GDD 3, also danach, wie hart eine Strecke die Reifen
nimmt. Genommen werden das Maximum, das 75er Perzentil, der Median, das
25er Perzentil und das Minimum. So steht am Ende nebeneinander, was die
Spanne der zwanzig Strecken hergibt.

**Nur trocken oder heiss.** Regen wuerfe die Mischungswahl ueber den
Haufen - dann faehrt jeder Regenreifen, und ueber Stintlaengen sagt der
Lauf nichts mehr. Das Wetter wird deshalb so lange neu gewuerfelt, bis
kein Abschnitt nass ist; welcher Seed das war, steht in der Ausgabe.

Aufruf:
    python -m werkzeuge.boxenstopps
    python -m werkzeuge.boxenstopps --strecken 3   nur drei Strecken
    python -m werkzeuge.boxenstopps --seed 7       anderer Weltseed
"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from dataclasses import dataclass

from rennmanager import konfiguration as kf
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import strategie as kern_strategie
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import welt as kern_welt
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern.zufall import Seedquelle

LIGA = 1
# Lagen, unter denen die Trockenmischungen ueberhaupt zur Wahl stehen.
TROCKEN = {"trocken", "heiss"}
# So viele Seeds werden hoechstens probiert, bis das Wetter trocken bleibt.
WETTERVERSUCHE = 200


@dataclass(frozen=True)
class Streckenwahl:
    """Eine Strecke und warum sie in der Auswahl steht."""

    rolle: str
    strecke: kern_strecke.Strecke
    faktor: float


def perzentil(werte: list[float], anteil: float) -> float:
    """Das Perzentil nach der Methode 'naechster Rang'.

    Bei zwanzig Strecken soll eine **vorhandene** Strecke herauskommen und
    nicht ein interpolierter Wert, den keine hat.
    """
    geordnet = sorted(werte)
    stelle = min(int(round(anteil * (len(geordnet) - 1))), len(geordnet) - 1)
    return geordnet[stelle]


def waehle_strecken(konfiguration: kf.Konfiguration, anzahl: int = 5) -> list[Streckenwahl]:
    """Die Strecken nach Reifenabnutzung: Maximum, 75, Median, 25, Minimum."""
    strecken = kern_strecke.lade_alle(konfiguration)
    mittel = kern_reifen.mittlere_querbeschleunigung(strecken)
    faktoren = {
        s.name: kern_reifen.streckenfaktor(konfiguration, s, mittel) for s in strecken
    }
    nach_faktor = sorted(strecken, key=lambda s: faktoren[s.name])
    rollen = [
        ("hoechste Abnutzung", 1.00),
        ("75er Perzentil", 0.75),
        ("Median", 0.50),
        ("25er Perzentil", 0.25),
        ("niedrigste Abnutzung", 0.00),
    ][:anzahl]
    gewaehlt = []
    for rolle, anteil in rollen:
        stelle = min(int(round(anteil * (len(nach_faktor) - 1))), len(nach_faktor) - 1)
        strecke = nach_faktor[stelle]
        gewaehlt.append(Streckenwahl(rolle, strecke, faktoren[strecke.name]))
    return gewaehlt


def trockenes_wetter(
    konfiguration: kf.Konfiguration,
    strecke: kern_strecke.Strecke,
    dauer_ms: int,
    rundendauer_ms: int,
) -> tuple[kern_wetter.Wetterverlauf, int]:
    """Wuerfelt so lange, bis das ganze Rennen trocken oder heiss bleibt.

    Gewuerfelt statt gesetzt: So laeuft dieselbe Funktion wie im Spiel,
    und die Griplagen je Sektor stimmen. Zurueck kommt auch der Seed, der
    getroffen hat - damit der Lauf wiederholbar bleibt.
    """
    for seed in range(WETTERVERSUCHE):
        verlauf = kern_wetter.wuerfle(
            konfiguration, strecke.name, dauer_ms, rundendauer_ms,
            Seedquelle(seed).zweig("rennwetter"),
        )
        if set(verlauf.zustaende) <= TROCKEN:
            return verlauf, seed
    raise SystemExit(
        f"Auf {strecke.name} blieb in {WETTERVERSUCHE} Versuchen kein Rennen trocken"
    )


def fahre(
    konfiguration: kf.Konfiguration,
    wahl: Streckenwahl,
    welt: kern_welt.Welt,
    streckenmittel: float,
    seed: int,
) -> dict:
    """Ein Rennen der Liga 1 auf dieser Strecke, trocken."""
    strecke = wahl.strecke
    runden = kern_rennen.rundenzahl(konfiguration, strecke, LIGA)
    feld = kern_welt.starterfeld(welt, LIGA)
    grundrunde = kern_tempo.fahre_runde(konfiguration, strecke, feld[0].auto).zeit_ms
    wetter, wetterseed = trockenes_wetter(
        konfiguration, strecke, int(grundrunde * runden), int(grundrunde)
    )
    quelle = Seedquelle(seed)
    strategien = kern_strategie.feldstrategien(
        konfiguration, [t.auto for t in feld], strecke, runden, wahl.faktor,
        wetter, quelle.zweig("strategie"), LIGA,
    )
    verlauf = kern_rennen.simuliere(
        konfiguration, strecke, feld, runden, quelle.zweig("rennen"), streckenmittel,
        wetter=wetter,
        streckenverschleiss=wahl.faktor,
        strategien=strategien.je_auto,
        mischungspflicht=strategien.pflicht_zwei,
        liga=LIGA,
    )
    return {
        "wahl": wahl,
        "runden": runden,
        "wetter": wetter,
        "wetterseed": wetterseed,
        "strategien": strategien,
        "verlauf": verlauf,
        "feld": feld,
    }


def zeige(lauf: dict) -> None:
    """Schreibt einen Lauf als Tabelle - je Fahrer eine Zeile."""
    wahl: Streckenwahl = lauf["wahl"]
    verlauf = lauf["verlauf"]
    runden = lauf["runden"]
    lagen = "/".join(dict.fromkeys(lauf["wetter"].zustaende))

    print()
    print("=" * 78)
    print(
        f"{wahl.strecke.name} - {wahl.rolle}  "
        f"(Streckenfaktor {wahl.faktor:.3f}, {wahl.strecke.laenge_m / 1000:.2f} km, "
        f"{runden} Runden)"
    )
    strategien = lauf["strategien"]
    print(
        f"Wetter: {lagen}  (Seed {lauf['wetterseed']})   "
        f"Mischungspflicht: {'ja' if strategien.pflicht_zwei else 'nein'}"
    )
    # Punkt 91: Der Planer laesst eine Handvoll Varianten zu; die Autos
    # ziehen daraus. Beide Zahlen gehoeren nebeneinander - wenn von
    # zwanzig zugelassenen Varianten nur drei gezogen werden, liegt das
    # am Feld, nicht am Planer.
    gezogen = Counter(n for n in strategien.gewaehlt if n >= 0)
    print(
        f"Varianten: {len(strategien.varianten)} zugelassen, "
        f"{strategien.strategiezahl} davon gefahren"
    )
    for nummer, wie_oft in sorted(gezogen.items()):
        v = strategien.varianten[nummer]
        rueckstand = (v.zeit_ms - strategien.varianten[0].zeit_ms) / 1000.0
        print(
            f"   {v.folge:18s} Stopps {str(list(v.stopps)):14s} "
            f"+{rueckstand:5.1f} s   {wie_oft:2d} Autos"
        )
    # Wer ausfaellt, stoppt nicht mehr - ohne diese Spalte sieht eine Null
    # in "Stopps" nach einer Strategie aus, die es gar nicht gab. Nicht ins
    # Ziel gekommen ist, wer ausgefallen ist; weniger Runden als der Erste
    # heisst nur ueberrundet.
    gefahren = {e.teilnehmer: e.runden for e in verlauf.ergebnisse}
    ausgefallen = {
        i for i in range(len(verlauf.teilnehmer)) if verlauf.ausfallzeit(i) is not None
    }
    print("-" * 90)
    print(
        f"{'Auto':5s} {'Start':5s} {'Stopps':6s}  {'Runde (Rest %)':32s} "
        f"{'Folge':18s} {'Ende':8s}"
    )
    print("-" * 90)

    for i, teilnehmer in enumerate(verlauf.teilnehmer):
        stopps = verlauf.stopps_von(i)
        folge = "-".join(
            [stopps[0].von] + [b.nach for b in stopps] if stopps
            else [verlauf.mischung_zu(0)[i]]
        )
        wann = "  ".join(
            f"{b.runde:2d}/{runden} ({b.restprofil * 100:4.1f}%)"
            + ("!" if b.notstopp else "")
            for b in stopps
        )
        weit = gefahren.get(i, 0)
        ende = f"aus R{weit}" if i in ausgefallen else f"Ziel {weit}"
        print(
            f"{teilnehmer.kuerzel:5s} {teilnehmer.startplatz:5d} "
            f"{len(stopps):6d}  {wann:32s} {folge:18s} {ende:8s}"
        )

    alle = verlauf.boxenstopps
    if not alle:
        print("Kein einziger Stopp.")
        return
    reste = sorted(b.restprofil * 100 for b in alle)
    runden_der_stopps = sorted(b.runde for b in alle)
    im_ziel = [i for i in range(len(verlauf.teilnehmer)) if i not in ausgefallen]
    je_auto = [len(verlauf.stopps_von(i)) for i in im_ziel]
    print("-" * 90)
    print(
        f"Im Ziel: {len(im_ziel)} von {len(verlauf.teilnehmer)}   "
        f"Stopps je Auto im Ziel: {min(je_auto)}-{max(je_auto)}, "
        f"Median {statistics.median(je_auto):.1f}   "
        f"Notstopps: {sum(1 for b in alle if b.notstopp)}"
    )
    # Die Spanne allein verschweigt, wo das Feld wirklich liegt: "1-5"
    # kann heissen, dass alle drei fahren und einer ausreisst, oder dass
    # sich das Feld gleichmaessig verteilt. Deshalb die ganze Verteilung.
    verteilung = Counter(je_auto)
    print(
        "Verteilung: "
        + "   ".join(
            f"{zahl} Stopps: {verteilung[zahl]:2d} Autos "
            f"({verteilung[zahl] / len(je_auto) * 100:4.1f} %)"
            for zahl in sorted(verteilung)
        )
    )
    # Punkt 92: Was der Planer vorhatte und was daraus wurde. Die beiden
    # Zeilen gehen auseinander, weil planstopp_ab_restprofil einen Stopp
    # wieder streicht, wenn der Satz an dem Tag noch zu gut dafuer ist -
    # wer schon gewechselt hat, faehrt den guten Satz bis ins Ziel. Ohne
    # diesen Vergleich sieht es so aus, als plane der Planer falsch.
    geplant = Counter(
        len(strategien.varianten[n].stopps) if n >= 0 else 0
        for i, n in enumerate(strategien.gewaehlt)
        if i in set(im_ziel)
    )
    print(
        "Davon geplant: "
        + "   ".join(
            f"{zahl} Stopps: {geplant[zahl]:2d} Autos "
            f"({geplant[zahl] / max(sum(geplant.values()), 1) * 100:4.1f} %)"
            for zahl in sorted(geplant)
        )
    )
    print(
        f"Restprofil beim Stopp: min {reste[0]:.1f} %  "
        f"25 % {perzentil(reste, 0.25):.1f} %  "
        f"Median {statistics.median(reste):.1f} %  "
        f"75 % {perzentil(reste, 0.75):.1f} %  "
        f"max {reste[-1]:.1f} %"
    )
    print(
        f"Stopprunde: {runden_der_stopps[0]}-{runden_der_stopps[-1]}, "
        f"Median {statistics.median(runden_der_stopps):.0f} von {runden}"
    )
    haeufigkeit: dict[str, int] = {}
    for i in im_ziel:
        stopps = verlauf.stopps_von(i)
        folge = "-".join([stopps[0].von] + [b.nach for b in stopps]) if stopps else "-"
        haeufigkeit[folge] = haeufigkeit.get(folge, 0) + 1
    gereiht = sorted(haeufigkeit.items(), key=lambda paar: -paar[1])
    print("Mischungsfolgen im Ziel: " + ", ".join(f"{folge} x{zahl}" for folge, zahl in gereiht))

    # Ein Zwangsstopp zieht einen frischen Satz auf. Will der Plan ihn
    # kurz darauf schon wieder abgeben, wandert gutes Profil in den Muell
    # - und wenn dabei nicht einmal die Mischung wechselt, war der Stopp
    # ganz umsonst. Genau dagegen steht planstopp_ab_restprofil; diese
    # Zeile zeigt, ob die Schwelle passt.
    danach = []
    for i in range(len(verlauf.teilnehmer)):
        stopps = verlauf.stopps_von(i)
        for vorher, nachher in zip(stopps, stopps[1:], strict=False):
            if vorher.notstopp and not nachher.notstopp:
                danach.append(nachher)
    if danach:
        umsonst = sum(1 for b in danach if b.von == b.nach)
        print(
            f"Planstopp direkt nach einem Zwangsstopp: {len(danach)}, "
            f"Median {statistics.median(b.restprofil * 100 for b in danach):.1f} % Restprofil, "
            f"{umsonst} davon ohne Mischungswechsel"
        )

    # Wer durchfaehrt, ohne zu stoppen, schleicht am Ende auf blankem
    # Gummi - das faellt in der Tabelle nur auf, wenn man danach sucht.
    am_ende = verlauf.reifen_zu(verlauf.dauer_ms)
    ohne_stopp = [i for i in im_ziel if not verlauf.stopps_von(i)]
    if ohne_stopp:
        blank = [i for i in ohne_stopp if am_ende[i] <= 0.05]
        print(
            f"Ohne Stopp im Ziel: {len(ohne_stopp)} "
            f"({', '.join(verlauf.teilnehmer[i].kuerzel for i in ohne_stopp)})"
            + (f", davon {len(blank)} auf blankem Reifen" if blank else "")
        )


def main() -> None:
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument("--strecken", type=int, default=5, help="wie viele Strecken")
    zerleger.add_argument("--seed", type=int, default=1, help="Seed fuer Welt und Rennen")
    argumente = zerleger.parse_args()

    konfiguration = kf.lade()
    strecken = kern_strecke.lade_alle(konfiguration)
    streckenmittel = kern_rennen.mittlerer_ueberholzonenanteil(konfiguration, strecken)
    welt = kern_welt.erzeuge(
        konfiguration, Seedquelle(argumente.seed).zweig("welt"), spielerliga=LIGA
    )
    gewaehlt = waehle_strecken(konfiguration, argumente.strecken)

    print(f"Liga {LIGA}, {len(kern_welt.starterfeld(welt, LIGA))} Autos, Weltseed {argumente.seed}")
    print("Strecken nach Reifenabnutzung (Streckenfaktor aus GDD 3):")
    for wahl in gewaehlt:
        print(f"  {wahl.faktor:6.3f}  {wahl.strecke.name:12s} {wahl.rolle}")

    for wahl in gewaehlt:
        zeige(fahre(konfiguration, wahl, welt, streckenmittel, argumente.seed))


if __name__ == "__main__":
    main()
