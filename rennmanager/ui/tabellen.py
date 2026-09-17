"""Gemeinsame Bausteine fuer die Tabellen der Oberflaeche."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyledItemDelegate, QTreeWidgetItem


class SortierbareZeile(QTreeWidgetItem):
    """Eine Zeile, die sich nach hinterlegten Schluesseln sortiert.

    Ohne das vergleicht Qt die angezeigten Texte: "1.200 EUR" stuende dann
    vor "900 EUR" und "1:24.887" vor "59.412".
    """

    SORTIERROLLE = Qt.UserRole + 1

    def setze_sortierwert(self, spalte: int, wert) -> None:
        self.setData(spalte, self.SORTIERROLLE, wert)

    def __lt__(self, andere: QTreeWidgetItem) -> bool:  # noqa: D105
        spalte = self.treeWidget().sortColumn() if self.treeWidget() else 0
        eigen = self.data(spalte, self.SORTIERROLLE)
        fremd = andere.data(spalte, self.SORTIERROLLE)
        if eigen is None or fremd is None:
            return self.text(spalte) < andere.text(spalte)
        return eigen < fremd


class Balkenzeichner(QStyledItemDelegate):
    """Zeichnet einen Anteil von 0 bis 1 als Balken statt als Zahl.

    Ein Balken liest sich im Vorbeifahren schneller als "63 %" - genau das
    braucht die Rangleiste im Rennen, wo dreissig Zeilen im Zeitraffer
    vorbeilaufen. Der Wert steht unter ``ANTEILSROLLE`` an der Zelle; der
    Text bleibt daneben stehen, damit die Zahl ablesbar und die Spalte
    sortierbar bleibt.

    Die Farbe folgt der Statuspalette, nicht der Serienpalette: Der Balken
    sagt "gut" oder "kritisch", nicht "Auto Nummer drei".
    """

    ANTEILSROLLE = Qt.UserRole + 2

    # Statusfarben aus der Referenzpalette des Diagrammleitfadens.
    GUT = QColor("#2e7d32")
    WARNUNG = QColor("#eda100")
    KRITISCH = QColor("#c62828")
    SPUR = QColor("#dedcd6")

    def __init__(self, parent=None, warnung: float = 0.4, kritisch: float = 0.2) -> None:
        super().__init__(parent)
        self._warnung = warnung
        self._kritisch = kritisch

    def farbe(self, anteil: float) -> QColor:
        if anteil <= self._kritisch:
            return self.KRITISCH
        if anteil <= self._warnung:
            return self.WARNUNG
        return self.GUT

    def paint(self, maler, option, index) -> None:  # noqa: D102 - Qt-Name
        anteil = index.data(self.ANTEILSROLLE)
        if anteil is None:
            super().paint(maler, option, index)
            return

        super().paint(maler, option, index)
        anteil = min(max(float(anteil), 0.0), 1.0)
        flaeche = option.rect.adjusted(3, 5, -3, -5)
        breite = max(flaeche.width() - 34, 6)

        maler.save()
        maler.setPen(Qt.NoPen)
        maler.setBrush(self.SPUR)
        maler.drawRoundedRect(flaeche.x(), flaeche.y(), breite, flaeche.height(), 2, 2)
        maler.setBrush(self.farbe(anteil))
        maler.drawRoundedRect(
            flaeche.x(), flaeche.y(), int(breite * anteil), flaeche.height(), 2, 2
        )
        maler.restore()
