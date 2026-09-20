"""Welche Strategien im Rennen unterwegs sind (Punkt 92).

Ein Klick auf die Zahl oben im Rennen oeffnet dieses Blatt. Es zeigt je
vertretener Strategie die Mischungsfolge, die geplanten Stopprunden, wie
viele Autos sie fahren - und zwei Zeiten nebeneinander:

* **Ohne Verkehr** ist die Rennzeit, die der Planer vor dem Start fuer
  diese Folge gerechnet hat: Medianfahrer, allein auf der Strecke, kein
  Gegner im Weg. Das ist die Zahl, nach der die Varianten zugelassen
  wurden.
* **Im Rennen** ist der mittlere Rueckstand der Autos, die sie
  tatsaechlich fahren, zum gerade gezeigten Zeitpunkt. Der Unterschied
  zwischen beiden Spalten ist genau das, was die Rechnung nicht kennt:
  Verkehr, Fahrer, Fehler, Zwangsstopps.

**Wer welche Strategie faehrt, bleibt geheim** - so hat es der
Auftraggeber festgelegt. Die Autonummern stecken in den Daten, damit sich
der Mittelwert bilden laesst; auf den Bildschirm kommen sie nicht.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from rennmanager.kern.rennen import Rennverlauf, rueckstand_in_sekunden

SPALTEN = ("Folge", "Stopprunden", "Autos", "Ohne Verkehr", "Im Rennen", "Unterschied")


def _sekunden(wert: float | None) -> str:
    """Ein Rueckstand als Zahl mit Vorzeichen - oder ein Strich."""
    if wert is None:
        return "-"
    if abs(wert) < 0.05:
        return "+0,0 s"
    return f"{wert:+.1f} s".replace(".", ",")


class Strategieblattfenster(QDialog):
    """Die Strategien des Feldes nebeneinander."""

    def __init__(self, verlauf: Rennverlauf, zeit_ms: float, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Strategien im Rennen")
        self.resize(640, 360)

        aufbau = QVBoxLayout(self)
        blaetter = verlauf.strategieblaetter
        kopf = QLabel(
            f"{len(blaetter)} verschiedene Strategien bei "
            f"{len(verlauf.teilnehmer)} Autos"
        )
        kopf.setStyleSheet("font-weight: bold;")
        aufbau.addWidget(kopf)

        self._baum = QTreeWidget()
        self._baum.setColumnCount(len(SPALTEN))
        self._baum.setHeaderLabels(list(SPALTEN))
        self._baum.setRootIsDecorated(False)
        aufbau.addWidget(self._baum)

        rueckstaende = self._rueckstaende(verlauf, zeit_ms)
        beste_planzeit = min(
            (b.zeit_ms for b in blaetter if b.zeit_ms is not None), default=None
        )
        beste_gefahren = min(
            (r for r in (rueckstaende.get(b.schluessel) for b in blaetter)
             if r is not None),
            default=None,
        )
        for blatt in blaetter:
            geplant = (
                None if blatt.zeit_ms is None or beste_planzeit is None
                else (blatt.zeit_ms - beste_planzeit) / 1000.0
            )
            roh = rueckstaende.get(blatt.schluessel)
            gefahren = None if roh is None or beste_gefahren is None else roh - beste_gefahren
            unterschied = (
                None if geplant is None or gefahren is None else gefahren - geplant
            )
            zeile = QTreeWidgetItem(
                [
                    blatt.folge,
                    ", ".join(str(r) for r in blatt.stopps) or "kein Stopp",
                    str(blatt.anzahl),
                    _sekunden(geplant),
                    _sekunden(gefahren),
                    _sekunden(unterschied),
                ]
            )
            for spalte in (2, 3, 4, 5):
                zeile.setTextAlignment(spalte, Qt.AlignmentFlag.AlignRight)
            self._baum.addTopLevelItem(zeile)
        for spalte in range(len(SPALTEN)):
            self._baum.resizeColumnToContents(spalte)

        fuss = QLabel(
            "„Ohne Verkehr“ ist die Rennzeit, die der Planer vor dem Start "
            "gerechnet hat: Medianfahrer, allein auf der Strecke.\n"
            "„Im Rennen“ ist der mittlere Rueckstand der Autos, die sie "
            "fahren, zum gezeigten Zeitpunkt. Der Unterschied ist, was die\n"
            "Rechnung nicht kennt: Verkehr, Fahrer, Fehler. "
            "Wer welche Strategie faehrt, bleibt geheim."
        )
        fuss.setWordWrap(True)
        aufbau.addWidget(fuss)

    @staticmethod
    def _rueckstaende(verlauf: Rennverlauf, zeit_ms: float) -> dict:
        """Mittlerer Rueckstand je Strategie, in Sekunden.

        Gerechnet wird mit ``rueckstand_in_sekunden`` - demselben echten
        Zeitrueckstand, den das Rueckstandsdiagramm zeigt, nicht aus
        Strecke geteilt durch Tempo geschaetzt. Autos, die schon
        ausgefallen sind, bleiben draussen: Ihr Rueckstand waechst ins
        Unendliche und wuerde die ganze Gruppe verzerren.
        """
        if not verlauf.strategieblaetter:
            return {}
        zeiten, werte = rueckstand_in_sekunden(verlauf)
        if not len(zeiten):
            return {}
        bild = int(np.clip(np.searchsorted(zeiten, zeit_ms / 1000.0, "right") - 1,
                           0, len(zeiten) - 1))
        ergebnis: dict = {}
        for blatt in verlauf.strategieblaetter:
            faehrt = [
                i for i in blatt.autos
                if verlauf.ausfallzeit(i) is None
                or verlauf.ausfallzeit(i) > zeit_ms
            ]
            if not faehrt:
                continue
            ergebnis[blatt.schluessel] = float(
                np.mean([werte[bild, i] for i in faehrt])
            )
        return ergebnis
