"""Rueckstandsdiagramm eines Rennens (Punkt 2).

Jede Linie ist ein Auto, die Hoehe ist sein Zeitrueckstand auf den
Fuehrenden. Kreuzen sich zwei Linien, hat sich die Reihenfolge geaendert -
man sieht dem Bild an, wo im Rennen etwas passiert ist.

Gezeichnet wird mit ``QPainter``, nicht mit einer Diagrammbibliothek:
PySide6 bringt ``QtCharts`` nicht mit, und eine zusaetzliche Abhaengigkeit
muesste in die .exe. ``streckenansicht.py`` zeichnet aus demselben Grund
selbst.

**Fokus und Kontext statt 30 Farben.** Bei 30 Linien ist Farbe als
Traeger der Identitaet wertlos - benachbarte Toene sind nicht mehr
auseinanderzuhalten, und fuer Farbenblinde erst gar nicht. Das Feld liegt
deshalb als dünne graue Linien im Hintergrund; hervorgehoben und direkt
beschriftet sind nur zwei: das Auto des Spielers und das in der Rangliste
gewaehlte. Beide tragen ihre Teamfarbe, und weil sie beschriftet sind,
haengt die Identitaet nicht an der Farbe allein.

Toene, Raender und das Ziehen einer Linie kommen aus ``ui/diagramm.py``;
dasselbe Bild zeichnet ``werkzeuge/rennverlauf.py`` mit matplotlib.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from rennmanager.kern.rennen import Rennverlauf, rueckstand_in_sekunden
from rennmanager.ui.diagramm import (
    BREITE_FELD,
    BREITE_FOKUS,
    FELD,
    FLAECHE,
    GITTER,
    HOECHSTENS_FOKUS,
    TEXT_ZWEITRANGIG,
    flaeche_in,
    zeichne_hinweis,
    zeichne_linie,
)

RAND_LINKS = 56
RAND_RECHTS = 64
RAND_OBEN = 22
RAND_UNTEN = 30


class Rueckstandsansicht(QWidget):
    """Zeichnet den Rueckstand aller Autos ueber die Rennzeit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._verlauf: Rennverlauf | None = None
        self._zeiten: np.ndarray | None = None
        self._rueckstand: np.ndarray | None = None
        self._hervorgehoben: list[int] = []
        self._marke_ms: float | None = None
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(False)

    # -- Daten -------------------------------------------------------------
    def zeige(self, verlauf: Rennverlauf | None) -> None:
        """Uebernimmt einen Rennverlauf und rechnet die Rueckstaende aus.

        Die Rechnung laeuft einmal je Rennen, nicht je Bild: Das Diagramm
        zeigt den ganzen Verlauf, nur die Zeitmarke wandert.
        """
        self._verlauf = verlauf
        if verlauf is None:
            self._zeiten = None
            self._rueckstand = None
        else:
            self._zeiten, self._rueckstand = rueckstand_in_sekunden(verlauf)
        self.update()

    def hebe_hervor(self, teilnehmer: list[int]) -> None:
        """Welche Autos als Linie hervortreten - hoechstens zwei."""
        self._hervorgehoben = list(teilnehmer)[:HOECHSTENS_FOKUS]
        self.update()

    def setze_marke(self, zeit_ms: float | None) -> None:
        """Die senkrechte Linie, die den Stand der Wiedergabe zeigt."""
        self._marke_ms = zeit_ms
        self.update()

    # -- Zeichnen ----------------------------------------------------------
    def paintEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        maler.fillRect(self.rect(), FLAECHE)

        if self._zeiten is None or self._rueckstand is None or not len(self._zeiten):
            zeichne_hinweis(maler, self.rect(), "Noch kein Rennen gefahren.")
            return

        flaeche = flaeche_in(
            self.width(), self.height(), RAND_LINKS, RAND_RECHTS, RAND_OBEN, RAND_UNTEN
        )
        dauer = float(self._zeiten[-1]) or 1.0
        groesster = self._achsenmaximum()

        self._zeichne_gitter(maler, flaeche, dauer, groesster)
        self._zeichne_feld(maler, flaeche, dauer, groesster)
        self._zeichne_hervorgehobene(maler, flaeche, dauer, groesster)
        self._zeichne_marke(maler, flaeche, dauer)
        self._zeichne_legende(maler, flaeche)

    def _achsenmaximum(self) -> float:
        """Der grosse Rueckstand, auf den die Achse skaliert.

        **Ueberrundete und Ausgefallene zaehlen nicht mit.** GDD 4 kennt
        fuer sie keinen Zeitrueckstand, sondern "+n Rd."; die Seitenleiste
        zeigt ihnen deshalb auch keine Sekunden. Ihre Kurve bleibt beim
        letzten gueltigen Wert stehen, und der ist willkuerlich - er soll
        die Achse nicht bestimmen. Ihre Linien laufen am unteren Rand.

        Dass ein Feld weit auseinanderliegt, ist damit *nicht* behoben und
        soll es auch nicht sein: In Liga 20 reicht die Ligastaerke von 0
        bis 157, das letzte Auto liegt dort gemessen 328 s hinter dem
        Sieger. Das ist die Liga, nicht das Diagramm.
        """
        runde = {
            e.teilnehmer: e.rundenrueckstand for e in self._verlauf.ergebnisse
        }
        auf_runde = [
            i for i in range(self._rueckstand.shape[1]) if not runde.get(i, 0)
        ]
        werte = self._rueckstand[:, auf_runde] if auf_runde else self._rueckstand
        return float(np.nanmax(werte)) or 1.0

    def _bis_zur_marke(self) -> int:
        """Wie viele Stuetzstellen bis zum Stand der Wiedergabe gehoeren.

        Das Diagramm zeigt nur, was schon gefahren ist - sonst stuende dem
        Zuschauer der ganze Rennausgang vor Augen, waehrend die
        Uebertragung noch in Runde drei laeuft. Ohne Marke (etwa im
        Standbild ohne Wiedergabe) gilt der ganze Verlauf.
        """
        if self._marke_ms is None or self._zeiten is None:
            return len(self._zeiten) if self._zeiten is not None else 0
        bis = int(np.searchsorted(self._zeiten, self._marke_ms / 1000.0, "right"))
        # Mindestens zwei Punkte, sonst gibt es keine Linie zu zeichnen.
        return max(bis, 2)

    def _stelle(self, flaeche: QRectF, dauer: float, groesster: float, i: int):
        """Die Linie eines Autos als Folge von Bildpunkten.

        Was ueber die Achse hinausgeht, liegt am Rand - abgeschnitten wird
        nichts, es ist nur nicht mehr aufgeloest. Die Linie endet dort, wo
        die Wiedergabe steht.
        """
        bis = self._bis_zur_marke()
        x = flaeche.left() + self._zeiten[:bis] / dauer * flaeche.width()
        anteil = np.clip(self._rueckstand[:bis, i] / groesster, 0.0, 1.0)
        y = flaeche.top() + anteil * flaeche.height()
        return x, y

    def _zeichne_feld(self, maler, flaeche, dauer, groesster) -> None:
        for i in range(self._rueckstand.shape[1]):
            if i in self._hervorgehoben:
                continue
            x, y = self._stelle(flaeche, dauer, groesster, i)
            zeichne_linie(maler, x, y, FELD, BREITE_FELD)

    def _zeichne_hervorgehobene(self, maler, flaeche, dauer, groesster) -> None:
        masse = QFontMetrics(maler.font())
        for i in self._hervorgehoben:
            if not 0 <= i < self._rueckstand.shape[1]:
                continue
            teilnehmer = self._verlauf.teilnehmer[i]
            farbe = QColor(teilnehmer.farbe)
            x, y = self._stelle(flaeche, dauer, groesster, i)
            zeichne_linie(maler, x, y, farbe, BREITE_FOKUS)
            # Direkt am Linienende beschriftet - so haengt die Identitaet
            # nicht an der Farbe allein.
            maler.setPen(QPen(farbe))
            maler.drawText(
                int(flaeche.right() + 6),
                int(float(y[-1]) + masse.ascent() / 2),
                teilnehmer.kuerzel,
            )

    def _zeichne_gitter(self, maler, flaeche, dauer, groesster) -> None:
        maler.setPen(QPen(GITTER, 1.0))
        masse = QFontMetrics(maler.font())
        for anteil in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = flaeche.top() + anteil * flaeche.height()
            maler.setPen(QPen(GITTER, 1.0))
            maler.drawLine(int(flaeche.left()), int(y), int(flaeche.right()), int(y))
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            text = f"{anteil * groesster:.0f} s"
            maler.drawText(
                int(flaeche.left() - 8 - masse.horizontalAdvance(text)),
                int(y + masse.ascent() / 2),
                text,
            )
        for anteil in (0.0, 0.5, 1.0):
            x = flaeche.left() + anteil * flaeche.width()
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            minuten = anteil * dauer / 60.0
            maler.drawText(int(x), int(flaeche.bottom() + masse.height()), f"{minuten:.0f} min")

    def _zeichne_marke(self, maler, flaeche, dauer) -> None:
        if self._marke_ms is None:
            return
        anteil = min(max(self._marke_ms / 1000.0 / dauer, 0.0), 1.0)
        x = flaeche.left() + anteil * flaeche.width()
        maler.setPen(QPen(TEXT_ZWEITRANGIG, 1.0))
        maler.drawLine(int(x), int(flaeche.top()), int(x), int(flaeche.bottom()))

    def _zeichne_legende(self, maler, flaeche) -> None:
        maler.setPen(QPen(TEXT_ZWEITRANGIG))
        maler.drawText(
            int(flaeche.left()),
            int(flaeche.top() - 6),
            "Rueckstand auf den Fuehrenden in Sekunden - grau das Feld, "
            "farbig Spieler und Auswahl; Ueberrundete liegen am unteren Rand",
        )
