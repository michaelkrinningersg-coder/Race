"""Ein schmales Band, das den Wetterverlauf einer Session zeigt (Punkt 93).

A13 und B43 sind derselbe Wunsch, einmal fuers Qualifying und einmal
fuers Rennen: **wo war es trocken, wo nass.** Die Wiedergabeleiste sagt,
wo man gerade ist; das Band darunter sagt, was dort galt - und vor allem,
was noch kommt. Ein Regenabschnitt in Minute 40 ist der Grund, warum eine
Strategie aufgeht oder nicht, und bisher sah man ihn erst, wenn man
hineinfuhr.

Gezeichnet wird ein Rechteck je Abschnitt, in der Breite seiner Dauer.
Die Farben kommen aus der Referenzpalette des Diagrammleitfadens und
steigen von trocken nach nass durch: Sand, Gelb, Graublau, Blau,
Dunkelblau. Sie sind **sequenziell**, nicht kategorial - "wie nass" ist
eine Groesse mit Richtung, keine Menge von Namen.

Das Band rechnet nichts: Es bekommt einen ``Wetterverlauf`` und eine
Dauer und macht daraus ein Bild.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

# Sequenziell von trocken nach nass. Eine unbekannte Lage bekommt Grau -
# sichtbar, aber ohne Aussage.
FARBEN = {
    "trocken": QColor("#e8e3d5"),
    "heiss": QColor("#e8c26a"),
    "wechselhaft": QColor("#9fb3c8"),
    "regen": QColor("#5b83a8"),
    "starkregen": QColor("#2f4f70"),
}
FARBE_UNBEKANNT = QColor("#c4c1b8")
# Die Marke, die den gerade gezeigten Zeitpunkt anzeigt.
FARBE_MARKE = QColor("#0b0b0b")
HOEHE = 14


class Wetterband(QWidget):
    """Der Wetterverlauf als Farbstreifen, mit einer Marke fuer das Jetzt."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self._verlauf = None
        self._dauer_ms = 0
        self._marke_ms = 0.0
        self.setFixedHeight(HOEHE)
        self.setToolTip(
            "Der Wetterverlauf der Session: hell ist trocken, dunkel ist nass. "
            "Der Strich zeigt, wo die Wiedergabe gerade steht."
        )

    def zeige(self, verlauf, dauer_ms: int) -> None:
        """Uebernimmt einen Wetterverlauf und seine Dauer."""
        self._verlauf = verlauf
        self._dauer_ms = max(int(dauer_ms), 1)
        self._marke_ms = 0.0
        self.update()

    def setze_marke(self, zeit_ms: float) -> None:
        """Verschiebt den Strich, ohne das Band neu aufzubauen."""
        self._marke_ms = max(0.0, min(float(zeit_ms), float(self._dauer_ms)))
        self.update()

    @property
    def abschnitte(self) -> tuple[tuple[str, int, int], ...]:
        """Je Abschnitt Lage, Beginn und Ende in Millisekunden.

        Als Eigenschaft und nicht nur im ``paintEvent``, damit sich
        pruefen laesst, was das Band zeigt - ein gemaltes Rechteck laesst
        sich schlecht befragen.
        """
        if self._verlauf is None or not self._verlauf.abschnitte:
            return ()
        grenzen = [int(a.ab_ms) for a in self._verlauf.abschnitte] + [self._dauer_ms]
        return tuple(
            (abschnitt.zustand, grenzen[n], max(grenzen[n + 1], grenzen[n]))
            for n, abschnitt in enumerate(self._verlauf.abschnitte)
        )

    @staticmethod
    def farbe_fuer(zustand: str) -> QColor:
        return FARBEN.get(zustand, FARBE_UNBEKANNT)

    def paintEvent(self, ereignis) -> None:  # noqa: N802 - Qt gibt den Namen vor
        maler = QPainter(self)
        maler.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        breite = self.width()
        hoehe = self.height()
        abschnitte = self.abschnitte
        if not abschnitte:
            maler.fillRect(0, 0, breite, hoehe, FARBE_UNBEKANNT)
            return

        for zustand, von, bis in abschnitte:
            links = von / self._dauer_ms * breite
            rechts = bis / self._dauer_ms * breite
            maler.fillRect(
                QRectF(links, 0.0, max(rechts - links, 1.0), float(hoehe)),
                self.farbe_fuer(zustand),
            )
        x = self._marke_ms / self._dauer_ms * breite
        maler.setPen(FARBE_MARKE)
        maler.drawLine(int(x), 0, int(x), hoehe)
