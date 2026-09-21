"""Der Meisterschaftsplatz eines Fahrers ueber die Jahre.

Die Liste der Saisons sagt es auch, aber erst als Linie sieht man den
Weg: ob jemand stetig nach vorn kommt, auf seinem Platz bleibt oder
durchgereicht wird.

Die Achse steht auf dem Kopf - **Platz 1 oben**, der letzte unten.

Gezeichnet wird mit ``QPainter`` wie alle Diagramme des Projekts; die
Toene kommen aus ``rennmanager.ui.diagramm``.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from rennmanager.ui.diagramm import (
    BREITE_FOKUS,
    FLAECHE,
    GITTER,
    TEXT_ZWEITRANGIG,
    flaeche_in,
    zeichne_hinweis,
    zeichne_linie,
)

# Links steht "Platz 50" an der Achse - schmaler geht es nicht, sonst
# schneidet der Rand die Beschriftung an.
RAND_LINKS = 62
RAND_RECHTS = 16
RAND_OBEN = 20
RAND_UNTEN = 26
# Der Punkt auf der Linie: gross genug, um ihn einzeln zu treffen.
PUNKT = 7


class Laufbahnansicht(QWidget):
    """Zeichnet den Platz eines Fahrers je abgeschlossener Saison."""

    def __init__(self, plaetze: int = 50, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plaetze = plaetze
        # Je Saison: Jahr und Platz.
        self._bahn: list[tuple[int, int]] = []
        self._farbe = QColor("#0b0b0b")
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # -- Daten -------------------------------------------------------------
    def zeige(self, bahn, farbe: str = "#0b0b0b") -> None:
        """Uebernimmt die Laufbahn als Folge aus Jahr und Platz."""
        self._bahn = [(jahr, platz) for jahr, platz in bahn]
        self._farbe = QColor(farbe)
        self.update()

    @property
    def saisons(self) -> int:
        return len(self._bahn)

    # -- Zeichnen ----------------------------------------------------------
    def paintEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        maler.fillRect(self.rect(), FLAECHE)

        if not self._bahn:
            zeichne_hinweis(
                maler, self.rect(), "Noch keine abgeschlossene Saison (GDD 13)."
            )
            return

        flaeche = flaeche_in(
            self.width(), self.height(), RAND_LINKS, RAND_RECHTS, RAND_OBEN, RAND_UNTEN
        )
        masse = QFontMetrics(maler.font())
        self._zeichne_gitter(maler, flaeche, masse)

        x = [self._x(flaeche, stelle) for stelle in range(len(self._bahn))]
        y = [self._y(flaeche, platz) for _, platz in self._bahn]
        if len(x) > 1:
            zeichne_linie(maler, x, y, self._farbe, BREITE_FOKUS)

        for stelle, (jahr, platz) in enumerate(self._bahn):
            maler.setBrush(self._farbe)
            maler.setPen(QPen(self._farbe))
            maler.drawEllipse(
                int(x[stelle] - PUNKT / 2), int(y[stelle] - PUNKT / 2), PUNKT, PUNKT
            )
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            text = f"P{platz}"
            maler.drawText(
                int(x[stelle] - masse.horizontalAdvance(text) / 2),
                int(y[stelle] - PUNKT),
                text,
            )
            jahrtext = str(jahr)
            maler.drawText(
                int(x[stelle] - masse.horizontalAdvance(jahrtext) / 2),
                int(flaeche.bottom() + masse.height()),
                jahrtext,
            )

    def _x(self, flaeche, stelle: int) -> float:
        """Die Saisons liegen gleichmaessig verteilt, eine allein mittig."""
        if len(self._bahn) == 1:
            return flaeche.left() + flaeche.width() / 2
        return flaeche.left() + stelle / (len(self._bahn) - 1) * flaeche.width()

    def _y(self, flaeche, platz: int) -> float:
        """Platz 1 oben, der letzte unten."""
        if self._plaetze <= 1:
            return flaeche.top() + flaeche.height() / 2
        anteil = (platz - 1) / (self._plaetze - 1)
        return flaeche.top() + anteil * flaeche.height()

    def _zeichne_gitter(self, maler: QPainter, flaeche, masse: QFontMetrics) -> None:
        for platz in (1, self._plaetze):
            y = self._y(flaeche, platz)
            maler.setPen(QPen(GITTER, 1.0))
            maler.drawLine(int(flaeche.left()), int(y), int(flaeche.right()), int(y))
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            text = f"Platz {platz}"
            maler.drawText(
                int(flaeche.left() - 6 - masse.horizontalAdvance(text)),
                int(y + masse.ascent() / 2),
                text,
            )
