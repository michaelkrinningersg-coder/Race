"""Gemeinsame Bausteine fuer die Tabellen der Oberflaeche."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem


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
