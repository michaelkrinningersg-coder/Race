"""Punkteverlauf einer Saison (Punkt 9).

Jede Linie ist ein Fahrer, die Hoehe sein aufsummierter Punktestand nach
jedem Rennwochenende. Man sieht dem Bild an, wann eine Meisterschaft
entschieden war und wann sie kippte.

Wie im Rueckstandsdiagramm gilt **Fokus und Kontext**: Bei 30 Linien
traegt Farbe keine Identitaet mehr, deshalb liegt das Feld grau im
Hintergrund und hervorgehoben sind hoechstens zwei, am Linienende direkt
beschriftet. Wer das ist, haengt am Ort: auf der Saisonseite der Spieler
und der in der Tabelle gewaehlte Fahrer, auf der Fahrerkarte der eine,
um den es dort geht. Der Hinweis ueber dem Bild sagt es jeweils.

Gezeichnet wird der Verlauf der **laufenden** Saison; er kommt aus
``statistik.Statistik.punktestand``. Beim Saisonwechsel wird er geleert,
der Endstand steht dann in der Historie.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

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

RAND_LINKS = 44
RAND_RECHTS = 64
RAND_OBEN = 22
RAND_UNTEN = 26


class Punkteansicht(QWidget):
    """Zeichnet den Punktestand aller Fahrer einer Liga ueber die Saison."""

    HINWEIS = "Punktestand je Rennwochenende - grau das Feld, farbig Spieler und Auswahl"

    def __init__(self, hinweis: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Je Fahrer: Kuerzel, Farbe und der aufsummierte Stand je Rennen.
        self._reihen: list[tuple[str, str, tuple[int, ...]]] = []
        self._hervorgehoben: list[int] = []
        # Wer hervorgehoben ist, haengt am Ort: Auf der Saisonseite sind es
        # Spieler und Auswahl, auf der Fahrerkarte nur dieser eine Fahrer.
        self._hinweis = hinweis if hinweis is not None else self.HINWEIS
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # -- Daten -------------------------------------------------------------
    def zeige(self, reihen) -> None:
        """Uebernimmt je Fahrer Kuerzel, Farbe und Punktestand je Rennen."""
        self._reihen = [
            (kuerzel, farbe, tuple(stand)) for kuerzel, farbe, stand in reihen
        ]
        self.update()

    def hebe_hervor(self, stellen) -> None:
        """Welche Reihen als Linie hervortreten - hoechstens zwei."""
        self._hervorgehoben = list(stellen)[:HOECHSTENS_FOKUS]
        self.update()

    @property
    def rennen(self) -> int:
        return max((len(stand) for _, _, stand in self._reihen), default=0)

    @property
    def hoechster(self) -> int:
        return max((max(stand, default=0) for _, _, stand in self._reihen), default=0)

    # -- Zeichnen ----------------------------------------------------------
    def paintEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        maler.fillRect(self.rect(), FLAECHE)

        if self.rennen < 2:
            zeichne_hinweis(
                maler, self.rect(), "Der Verlauf beginnt nach dem zweiten Rennen."
            )
            return

        flaeche = flaeche_in(
            self.width(), self.height(), RAND_LINKS, RAND_RECHTS, RAND_OBEN, RAND_UNTEN
        )
        hoechster = max(self.hoechster, 1)
        self._zeichne_gitter(maler, flaeche, hoechster)

        for stelle, (_kuerzel, _farbe, stand) in enumerate(self._reihen):
            if stelle in self._hervorgehoben:
                continue
            x, y = self._punkte(flaeche, hoechster, stand)
            zeichne_linie(maler, x, y, FELD, BREITE_FELD)

        masse = QFontMetrics(maler.font())
        for stelle in self._hervorgehoben:
            if not 0 <= stelle < len(self._reihen):
                continue
            kuerzel, farbe, stand = self._reihen[stelle]
            x, y = self._punkte(flaeche, hoechster, stand)
            zeichne_linie(maler, x, y, QColor(farbe), BREITE_FOKUS)
            maler.setPen(QPen(QColor(farbe)))
            maler.drawText(
                int(flaeche.right() + 6),
                int(y[-1] + masse.ascent() / 2),
                f"{kuerzel} {stand[-1]}",
            )

        maler.setPen(QPen(TEXT_ZWEITRANGIG))
        maler.drawText(int(flaeche.left()), int(flaeche.top() - 6), self._hinweis)

    def _punkte(self, flaeche, hoechster: int, stand: tuple[int, ...]):
        """Die Linie eines Fahrers als zwei Listen von Bildpunkten."""
        letzte = max(self.rennen - 1, 1)
        x = [
            flaeche.left() + rennen / letzte * flaeche.width()
            for rennen in range(len(stand))
        ]
        y = [
            flaeche.bottom() - wert / hoechster * flaeche.height() for wert in stand
        ]
        return x, y

    def _zeichne_gitter(self, maler: QPainter, flaeche, hoechster: int) -> None:
        masse = QFontMetrics(maler.font())
        for anteil in (0.0, 0.5, 1.0):
            y = flaeche.bottom() - anteil * flaeche.height()
            maler.setPen(QPen(GITTER, 1.0))
            maler.drawLine(int(flaeche.left()), int(y), int(flaeche.right()), int(y))
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            text = f"{int(anteil * hoechster)}"
            maler.drawText(
                int(flaeche.left() - 6 - masse.horizontalAdvance(text)),
                int(y + masse.ascent() / 2),
                text,
            )
        for rennen in (1, self.rennen):
            anteil = (rennen - 1) / max(self.rennen - 1, 1)
            x = flaeche.left() + anteil * flaeche.width()
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            text = f"R{rennen}"
            versatz = 0 if rennen == 1 else -masse.horizontalAdvance(text)
            maler.drawText(
                int(x + versatz), int(flaeche.bottom() + masse.height()), text
            )
