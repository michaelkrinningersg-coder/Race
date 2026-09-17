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
from rennmanager.kern import rennen as kern_rennen  # noqa: E402
from rennmanager.kern import strecke as kern_strecke  # noqa: E402
from rennmanager.kern import tempo as kern_tempo  # noqa: E402
from rennmanager.kern import wetter as kern_wetter  # noqa: E402
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

    feld = kern_rennen.starterfeld(konfiguration, liga, spielerplatz=None)
    session = kern_qualifying.fahre(konfiguration, strecke, feld, haupt.zweig("qualifying"))

    # Aufstellung nach Qualifying (GDD 4).
    gestartet = tuple(
        kern_rennen.Teilnehmer(
            auto=feld[i].auto, startplatz=platz, farbe=feld[i].farbe,
            ist_spieler=feld[i].ist_spieler,
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
        konfiguration, strecke, gestartet, runden, haupt.zweig("rennen"), mittel, wetter=wetter
    )
    return session, verlauf


def rueckstand_in_sekunden(verlauf) -> tuple[np.ndarray, np.ndarray]:
    """Echter Zeitrueckstand jedes Autos auf den Fuehrenden.

    Nicht der Abstand in Metern geteilt durch irgendein Tempo: Gemessen
    wird, wann ein Auto den Punkt erreicht hat, an dem der Fuehrende gerade
    ist. Das ist derselbe Rueckstand, den die Seitenleiste zeigt, nur ueber
    die ganze Renndauer.

        rueckstand_i(t) = t_i(d_fuehrend(t)) - t

    Ein Auto erreicht die Stelle, an der der Fuehrende gerade ist, spaeter
    als dieser - der Rueckstand ist also die Zeit, die es noch braucht.

    Weil die Distanz jedes Autos monoton waechst, laesst sich ``t_i`` durch
    Umkehrung der Distanzkurve bestimmen.

    :return: Zeitachse in Sekunden und Rueckstaende der Form
        ``(Bilder, Autos)``
    """
    distanz = verlauf.distanz_m
    alle_zeiten = verlauf.zeitpunkte_ms / 1000.0
    vorne_gesamt = distanz.max(axis=1)

    # Gezeichnet wird nur bis zur Ankunft des Siegers - danach stehen die
    # Autos nach und nach still. Zum Nachschlagen dient aber der ganze
    # Verlauf: Die uebrigen fahren bis zu ihrer eigenen Zielueberfahrt
    # weiter und erreichen die Stelle des Siegers tatsaechlich. So wird
    # nichts extrapoliert.
    siegerzeit = verlauf.ergebnisse[0].zeit_ms / 1000.0
    bis = int(np.searchsorted(alle_zeiten, siegerzeit, "right"))
    zeiten = alle_zeiten[:bis]
    vorne = vorne_gesamt[:bis]

    rueckstand = np.empty((len(zeiten), verlauf.anzahl))
    for i in range(verlauf.anzahl):
        eigene = distanz[:, i]
        werte = np.interp(vorne, eigene, alle_zeiten) - zeiten

        # Ein ueberrundetes Auto erreicht die Endstelle des Siegers nie.
        # Dort ist ein Zeitrueckstand nicht mehr definiert - laut GDD 4
        # heisst es dann "+1 Rd.". Statt einen Randwert zu zeichnen, bleibt
        # die Linie beim letzten gueltigen Wert stehen.
        gueltig = vorne <= eigene[-1]
        if not gueltig.all():
            letzter = int(np.flatnonzero(gueltig)[-1]) if gueltig.any() else 0
            werte[letzter + 1 :] = werte[letzter]
        rueckstand[:, i] = werte
    return zeiten, rueckstand


def zeichne(konfiguration, session, verlauf, ziel: Path) -> None:
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
    _titel(bild, achse, konfiguration, session, verlauf)
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
    achse.set_ylim(float(rueckstand.max()) * 1.02, -float(rueckstand.max()) * 0.02)

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


def _titel(bild, achse, konfiguration, session, verlauf) -> None:
    liga = konfiguration.ligenname(
        next(
            z["liga"]
            for z in konfiguration.wert("ligen", "kontrolle")
            if z["s_bester"] == max(t.auto.wert("F1") for t in session.teilnehmer)
        )
    )
    sieger = verlauf.teilnehmer[verlauf.ergebnisse[0].teilnehmer]
    achse.set_title(
        f"Rennverlauf {verlauf.strecke.name} - {liga}",
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
    zeichne(konfiguration, session, verlauf, argumente.datei)
    print(f"  Diagramm: {argumente.datei}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
