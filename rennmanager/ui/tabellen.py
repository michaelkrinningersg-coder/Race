"""Gemeinsame Bausteine fuer die Tabellen der Oberflaeche."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QMenu, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

# Punkt 95: Teamfarben sind fuer die Punkte auf der Streckenkarte gemacht
# (GDD 4 und 12). Als **Schrift** auf hellem Grund fallen die hellen
# darunter aus: Reines Gelb auf Weiss bringt ein Kontrastverhaeltnis von
# 1,12:1 - gemessen sind 32 der 100 Teams unter dem Wert, den man zum
# Lesen braucht. Fuer Tabellen wird die Farbe deshalb so weit
# abgedunkelt, bis sie 4,5:1 erreicht (WCAG AA fuer normalen Text).
# Farbton und Saettigung bleiben, nur die Helligkeit sinkt - das Team
# behaelt seine Farbe, sie wird nur dunkler. Auf der Karte, im
# Rueckstandsdiagramm und im Punkteverlauf bleibt die Farbe unberuehrt:
# Dort sind es Flaechen und Linien, keine Buchstaben.
MINDESTKONTRAST = 4.5
# Der helle Grund, gegen den gerechnet wird. Die Zeilen wechseln zwischen
# Weiss und einem Hauch Grau; Weiss ist der schlechtere der beiden Faelle.
GRUND = "#ffffff"


def setze_breiten(tabelle: QTreeWidget, proben, rand: int = 16) -> None:
    """Spaltenbreiten **einmal** aus Probetexten setzen (D1).

    Die Rennanzeige rief bisher in jedem Bild ``resizeColumnToContents``
    fuer jede Spalte jeder Tabelle auf - gemessen 37 Aufrufe je Bild und
    damit 62 Prozent der Zeit, die ein Bild kostet. Qt misst dafuer jede
    einzelne Zelle der Spalte neu.

    Gebraucht wird das nicht: Was in einer Spalte breitestenfalls steht,
    laesst sich vorher sagen. Eine Rundenzeit ist nie laenger als
    ``1:23:45.678``, und die Namen der dreissig Fahrer stehen beim
    Rennstart fest. Ein Probetext je Spalte genuegt also, einmal
    ausgemessen.

    Nebenbei hoert das Zittern auf: Die Spalten sprangen bisher fuenfmal
    je Sekunde in der Breite, sobald ein Wert eine Stelle mehr bekam.

    :param proben: je Spalte ein Probetext; ``None`` laesst die Spalte,
        wie sie ist (fuer Spalten mit eigener Breite, etwa dem
        Reifenbalken)
    """
    metrik = QFontMetrics(tabelle.font())
    kopfmetrik = QFontMetrics(tabelle.header().font())
    kopf = tabelle.headerItem()
    for spalte, probe in enumerate(proben):
        if probe is None:
            continue
        breite = metrik.horizontalAdvance(probe)
        if kopf is not None:
            breite = max(breite, kopfmetrik.horizontalAdvance(kopf.text(spalte)))
        tabelle.setColumnWidth(spalte, breite + rand)


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


def fahrernummer(zeile: QTreeWidgetItem) -> int | None:
    """Die Fahrernummer, die an einer Zeile haengt - Spalte 0, UserRole."""
    return zeile.data(0, Qt.UserRole)


def verbinde_fahrerkarte(liste, oeffne, nummer_von=fahrernummer) -> None:
    """Doppelklick und Rechtsklick auf eine Zeile oeffnen die Fahrerkarte.

    Der **Einfachklick** bleibt frei: Er waehlt die Zeile aus und steuert
    damit den Steckbrief der Weltseite und die hervorgehobene Linie im
    Punkteverlauf. Der Doppelklick kommt oben drauf, und weil man einen
    Doppelklick nicht sieht, steht dasselbe im Rechtsklick-Menue.

    :param oeffne: bekommt die Fahrernummer
    :param nummer_von: liest sie aus einer Zeile; ohne Angabe aus
        Spalte 0 unter ``Qt.UserRole``. Die Rangliste im Rennen fuehrt
        dort die Startnummer im Feld und braucht deshalb eine eigene.
    """

    def doppelklick(zeile, _spalte: int = 0) -> None:
        # Null ist eine gueltige Fahrernummer - der Spieler hat sie. Ein
        # ``if nummer:`` liess ausgerechnet seine Karte nicht aufgehen.
        nummer = nummer_von(zeile)
        if nummer is not None:
            oeffne(int(nummer))

    def menue(stelle) -> None:
        zeile = liste.itemAt(stelle)
        if zeile is None or nummer_von(zeile) is None:
            return
        klappe = QMenu(liste)
        eintrag = klappe.addAction("Fahrerkarte oeffnen")
        if klappe.exec(liste.viewport().mapToGlobal(stelle)) is eintrag:
            doppelklick(zeile)

    liste.itemDoubleClicked.connect(doppelklick)
    liste.setContextMenuPolicy(Qt.CustomContextMenu)
    liste.customContextMenuRequested.connect(menue)


def _leuchtdichte(farbe: QColor) -> float:
    """Relative Leuchtdichte nach WCAG 2.1."""

    def kanal(wert: float) -> float:
        return wert / 12.92 if wert <= 0.03928 else ((wert + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * kanal(farbe.redF())
        + 0.7152 * kanal(farbe.greenF())
        + 0.0722 * kanal(farbe.blueF())
    )


def kontrast(farbe: QColor, grund: str = GRUND) -> float:
    """Kontrastverhaeltnis zweier Farben, zwischen 1 und 21."""
    hell, dunkel = sorted(
        (_leuchtdichte(farbe), _leuchtdichte(QColor(grund))), reverse=True
    )
    return (hell + 0.05) / (dunkel + 0.05)


@lru_cache(maxsize=512)
def _abgedunkelt(name: str) -> QColor:
    farbe = QColor(name)
    if not farbe.isValid():
        return QColor("#0b0b0b")
    farbton, saettigung, helligkeit, deckung = farbe.getHsl()
    while helligkeit > 0 and kontrast(farbe) < MINDESTKONTRAST:
        helligkeit = max(0, helligkeit - 2)
        farbe = QColor.fromHsl(farbton, saettigung, helligkeit, deckung)
    return farbe


def schriftfarbe(farbe) -> QColor:
    """Eine Teamfarbe, dunkel genug zum Lesen auf hellem Grund.

    Farben, die von sich aus dunkel genug sind, kommen unveraendert
    zurueck - zwei Drittel der Teams merken nichts davon.
    """
    return QColor(_abgedunkelt(QColor(farbe).name()))


def kurzname(name: str) -> str:
    """"Michael Krinninger" wird zu "M. Krinninger" (Punkt 98).

    Der Nachname steht voll da - er ist das, was man sucht -, der
    Vorname nur als Anfangsbuchstabe: In einer Liste mit vierzig Zeilen
    kosten ausgeschriebene Vornamen eine halbe Spaltenbreite und tragen
    nichts zur Unterscheidung bei. Zwei Meier trennt der Vorname, und
    dafuer reicht sein erster Buchstabe.

    Ein Name ohne Leerzeichen bleibt, wie er ist; ein leerer bleibt leer.
    """
    name = (name or "").strip()
    if " " not in name:
        return name
    vorname, nachname = name.split(" ", 1)
    return f"{vorname[0]}. {nachname}" if vorname else nachname
