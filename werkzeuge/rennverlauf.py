"""Zeichnet den Rueckstand aller Autos ueber die Rennzeit.

Ein Balancing-Werkzeug (GDD 15: Debug-Ansicht): Es faehrt ein Rennwochenende
und stellt dar, wie sich das Feld auseinanderzieht und wo Positionen
wechseln. Jede Linie ist ein Auto; kreuzen sich zwei Linien, hat sich die
Reihenfolge geaendert.

Die Farbe folgt dem Startplatz aus dem Qualifying - dunkel heisst von vorn
gestartet, hell von hinten. Eine helle Linie weit oben ist also ein Auto,
das sich nach vorn gearbeitet hat.

Aufruf:
    python -m werkzeuge.rennverlauf --liga 10 --strecke Spa --datei verlauf.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from rennmanager.kern import qualifying as kern_qualifying  # noqa: E402
from rennmanager.kern import reifen as kern_reifen  # noqa: E402
from rennmanager.kern import rennen as kern_rennen  # noqa: E402
from rennmanager.kern import strecke as kern_strecke  # noqa: E402
from rennmanager.kern import tempo as kern_tempo  # noqa: E402
from rennmanager.kern import wetter as kern_wetter  # noqa: E402
from rennmanager.kern.rennen import rueckstand_in_sekunden  # noqa: E402
from rennmanager.kern.zeit import formatiere_dauer  # noqa: E402
from rennmanager.kern.zufall import Seedquelle  # noqa: E402
from rennmanager.konfiguration import lade  # noqa: E402

# Flaeche und Schrift aus der Referenzpalette des Diagrammleitfadens.
FLAECHE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_ZWEITRANGIG = "#52514e"
GITTER = "#dedcd6"
# Ordinale Blaustufen 250 bis 700: hell = von hinten, dunkel = von vorn.
# Heller als Stufe 250 waere auf heller Flaeche nicht mehr kontraststark.
RAMPE = ["#86b6ef", "#5598e7", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def fahre_wochenende(konfiguration, streckenname: str, liga: int, seed: int, runden: int | None):
    """Faehrt Qualifying und Rennen und liefert beide Ergebnisse."""
    alle = kern_strecke.lade_alle(konfiguration)
    strecke = next(s for s in alle if s.name == streckenname)
    mittel = kern_rennen.mittlerer_ueberholzonenanteil(konfiguration, alle)
    haupt = Seedquelle(seed)

    # Mit Seedquelle streuen die Einzelwerte je Auto (GDD 12) - erst
    # dadurch faehrt nicht jedes Auto seine Reifen gleich schnell ab.
    feld = kern_rennen.starterfeld(
        konfiguration, liga, spielerplatz=None, seedquelle=haupt.zweig("feld")
    )
    session = kern_qualifying.fahre(konfiguration, strecke, feld, haupt.zweig("qualifying"))

    # Aufstellung nach Qualifying (GDD 4).
    gestartet = tuple(
        kern_rennen.Teilnehmer(
            auto=feld[i].auto, startplatz=platz, farbe=feld[i].farbe,
            ist_spieler=feld[i].ist_spieler, nummer=feld[i].nummer,
        )
        for platz, i in enumerate(session.aufstellung, start=1)
    )

    if runden is None:
        runden = kern_rennen.rundenzahl(konfiguration, strecke, liga)
    rundendauer = kern_tempo.fahre_runde(konfiguration, strecke, gestartet[0].auto).zeit_ms
    wetter = kern_wetter.wuerfle(
        konfiguration, strecke.name, rundendauer * runden, rundendauer,
        haupt.zweig("rennwetter"),
    )
    verlauf = kern_rennen.simuliere(
        konfiguration, strecke, gestartet, runden, haupt.zweig("rennen"), mittel,
        wetter=wetter,
        streckenverschleiss=kern_reifen.streckenfaktor(
            konfiguration, strecke, kern_reifen.mittlere_querbeschleunigung(alle)
        ),
    )
    return session, verlauf


def zeichne(konfiguration, liga: int, verlauf, ziel: Path) -> None:
    zeiten, rueckstand = rueckstand_in_sekunden(verlauf)
    anzahl = verlauf.anzahl

    farbverlauf = LinearSegmentedColormap.from_list("startplatz", RAMPE)
    bild, achse = plt.subplots(figsize=(15.5, 9.0), dpi=150)
    bild.patch.set_facecolor(FLAECHE)
    achse.set_facecolor(FLAECHE)

    # Von hinten nach vorn zeichnen, damit die Spitze obenauf liegt.
    for i in sorted(range(anzahl), key=lambda n: -verlauf.teilnehmer[n].startplatz):
        startplatz = verlauf.teilnehmer[i].startplatz
        farbe = farbverlauf(1.0 - (startplatz - 1) / max(anzahl - 1, 1))
        achse.plot(zeiten, rueckstand[:, i], color=farbe, linewidth=2.0, solid_capstyle="round")

    _beschrifte_enden(achse, zeiten, rueckstand, verlauf, farbverlauf, anzahl)
    _achsen(achse, zeiten, rueckstand)
    _titel(bild, achse, konfiguration, liga, verlauf)
    _legende(bild, farbverlauf)

    bild.savefig(ziel, facecolor=FLAECHE, bbox_inches="tight")
    plt.close(bild)


def _beschrifte_enden(achse, zeiten, rueckstand, verlauf, farbverlauf, anzahl) -> None:
    """Setzt das Kuerzel ans Ende jeder Linie, ohne Ueberlappung."""
    letzte = rueckstand[-1]
    spanne = float(letzte.max() - letzte.min()) or 1.0
    # Mindestabstand zweier Beschriftungen in Datenwerten.
    mindest = spanne / 34.0
    # Ueberrundete werden als "+n Rd." gekennzeichnet (GDD 4).
    runden_zurueck = {
        e.teilnehmer: e.rundenrueckstand for e in verlauf.ergebnisse if e.rundenrueckstand
    }

    geordnet = sorted(range(anzahl), key=lambda i: letzte[i])
    gesetzt: list[float] = []
    for i in geordnet:
        hoehe = float(letzte[i])
        if gesetzt and hoehe - gesetzt[-1] < mindest:
            hoehe = gesetzt[-1] + mindest
        gesetzt.append(hoehe)

        startplatz = verlauf.teilnehmer[i].startplatz
        beschriftung = verlauf.teilnehmer[i].kuerzel
        if i in runden_zurueck:
            beschriftung += f"  +{runden_zurueck[i]} Rd."
        achse.annotate(
            beschriftung,
            xy=(zeiten[-1], letzte[i]),
            xytext=(zeiten[-1] + spanne * 0.0, hoehe),
            textcoords="data",
            color=farbverlauf(1.0 - (startplatz - 1) / max(anzahl - 1, 1)),
            fontsize=7.5,
            fontweight="bold",
            va="center",
            ha="left",
            annotation_clip=False,
        )


def _achsen(achse, zeiten, rueckstand) -> None:
    achse.set_xlim(0, zeiten[-1] * 1.045)
    # Der Fuehrende liegt oben: die Achse zeigt nach unten.
    achse.invert_yaxis()
    # Etwas Luft unten, damit die Beschriftungen der letzten Autos nicht
    # aus dem Bild laufen.
    groesster = float(rueckstand.max())
    achse.set_ylim(groesster * 1.10, -groesster * 0.03)

    achse.set_xlabel("Verstrichene Rennzeit", color=TEXT_ZWEITRANGIG, fontsize=10)
    achse.set_ylabel("Rueckstand auf den Fuehrenden (s)", color=TEXT_ZWEITRANGIG, fontsize=10)
    achse.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda wert, _: formatiere_dauer(int(wert * 1000))[:-4])
    )
    achse.grid(True, color=GITTER, linewidth=0.7, alpha=0.9)
    achse.set_axisbelow(True)
    for rand in ("top", "right"):
        achse.spines[rand].set_visible(False)
    for rand in ("left", "bottom"):
        achse.spines[rand].set_color(GITTER)
    achse.tick_params(colors=TEXT_ZWEITRANGIG, labelsize=9)


def _titel(bild, achse, konfiguration, liga, verlauf) -> None:
    ligenname = konfiguration.ligenname(liga)
    sieger = verlauf.teilnehmer[verlauf.ergebnisse[0].teilnehmer]
    achse.set_title(
        f"Rennverlauf {verlauf.strecke.name} - Liga {liga} ({ligenname})",
        color=TEXT, fontsize=16, fontweight="bold", loc="left", pad=26,
    )
    achse.text(
        0.0, 1.015,
        f"{verlauf.runden} Runden · {len(verlauf.teilnehmer)} Autos · "
        f"Wetter {' → '.join(verlauf.wetter.zustaende)} · "
        f"{len(verlauf.manoever)} Ueberholmanoever · "
        f"Sieger {sieger.kuerzel} von Startplatz {sieger.startplatz} "
        f"in {formatiere_dauer(verlauf.ergebnisse[0].zeit_ms)}",
        transform=achse.transAxes, color=TEXT_ZWEITRANGIG, fontsize=10, va="bottom",
    )


def _zwischenfaelle(verlauf) -> str:
    """Kurzfassung der Fehler, Defekte und Unfaelle fuer die Kopfzeile."""
    from collections import Counter

    gezaehlt = Counter(z.art for z in verlauf.zwischenfaelle)
    teile = []
    for art, wort in (("fehler", "Fehler"), ("defekt", "Defekte"), ("unfall", "Unfaelle")):
        if gezaehlt[art]:
            teile.append(f"{gezaehlt[art]} {wort}")
    return ", ".join(teile) if teile else "keine Zwischenfaelle"


def _legende(bild, farbverlauf) -> None:
    """Erklaert die Farbskala: dunkel von vorn, hell von hinten gestartet."""
    achse = bild.add_axes((0.905, 0.80, 0.012, 0.13))
    farben = np.linspace(1, 0, 256).reshape(-1, 1)
    achse.imshow(farben, aspect="auto", cmap=farbverlauf)
    achse.set_xticks([])
    achse.set_yticks([0, 255])
    achse.set_yticklabels(["Startplatz 1", "Startplatz 30"], fontsize=8, color=TEXT_ZWEITRANGIG)
    achse.yaxis.tick_right()
    achse.tick_params(length=0)
    for rand in achse.spines.values():
        rand.set_visible(False)


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--strecke", default="Spa")
    zerleger.add_argument("--liga", type=int, default=10)
    zerleger.add_argument("--seed", type=int, default=4711)
    zerleger.add_argument("--runden", type=int, default=None, help="Vorgabe statt GDD-Distanz")
    zerleger.add_argument("--datei", type=Path, default=Path("rennverlauf.png"))
    argumente = zerleger.parse_args()

    konfiguration = lade()
    print(f"Faehrt {argumente.strecke}, Liga {argumente.liga}, Seed {argumente.seed} ...")
    session, verlauf = fahre_wochenende(
        konfiguration, argumente.strecke, argumente.liga, argumente.seed, argumente.runden
    )
    print(
        f"  Qualifying: Pole {verlauf.teilnehmer[0].kuerzel}, "
        f"Wetter {' -> '.join(session.wetter.zustaende)}"
    )
    print(
        f"  Rennen: {verlauf.runden} Runden, {formatiere_dauer(verlauf.dauer_ms)}, "
        f"{len(verlauf.manoever)} Manoever, "
        f"Wetter {' -> '.join(verlauf.wetter.zustaende)}"
    )
    zeichne(konfiguration, argumente.liga, verlauf, argumente.datei)
    print(f"  Diagramm: {argumente.datei}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
