"""Das Jahr als Band (Punkt 7).

GDD 2 macht Zeit zur Kapazitaet: Jeder nutzbare Tag hat zwei Plaetze,
einen fuer den Fahrer und einen fuer die Werkstatt, und ein Tag, der
vorbei ist, ohne belegt zu sein, ist verloren. In einer Liste von 365
Zeilen sieht man das nicht. Als Band schon: Wo Luecken bleiben, ist Zeit
liegen geblieben.

Jeder Tag ist ein schmaler Streifen, jede Woche eine Spalte - Montag
oben, Sonntag unten, sodass das Rennwochenende immer am gleichen Platz
steht. Die Farbe sagt, was der Tag ist:

=================  ==========================================
Renntag            der Sonntag, an dem gefahren wird
Qualifying         der Samstag davor
Reise              die Tage, die das Wochenende kostet
Verloren           was E29 Reisechaos genommen hat (GDD 14)
Voll belegt        beide Plaetze genutzt
Halb belegt        ein Platz genutzt
Frei               nutzbar und ungenutzt - das, was wehtut
=================  ==========================================

Gezeichnet wird mit ``QPainter``, wie im ganzen Projekt: PySide6 bringt
keine Diagrammbibliothek mit, und eine zusaetzliche Abhaengigkeit muesste
in die .exe.
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from rennmanager.kern.kalender import Tagesart, wochentag

# Flaeche und Schrift aus der Referenzpalette des Diagrammleitfadens.
FLAECHE = QColor("#fcfcfb")
TEXT_ZWEITRANGIG = QColor("#52514e")
RAHMEN = QColor("#dedcd6")

# Die Zustaende eines Tages. Renntag und Qualifying tragen die Farben, die
# die Karriereseite schon benutzt; belegt und frei kommen aus der
# Statuspalette, weil sie "genutzt" und "vertan" bedeuten.
FARBEN = {
    "rennen": QColor("#c62828"),
    "qualifying": QColor("#eda100"),
    "reise": QColor("#8b93a1"),
    "verloren": QColor("#7b1fa2"),
    "voll": QColor("#2e7d32"),
    "halb": QColor("#85c88a"),
    "frei": QColor("#e6e4de"),
}
BESCHRIFTUNG = {
    "rennen": "Rennen",
    "qualifying": "Qualifying",
    "reise": "Reise",
    "verloren": "verloren (E29)",
    "voll": "beide Plaetze belegt",
    "halb": "ein Platz belegt",
    "frei": "frei und ungenutzt",
}

TAGE_JE_SPALTE = 7
RAND = 4
LEGENDE_HOEHE = 18
# Sieben Zeilen plus Legende: darunter wird ein Tag zwei Pixel hoch.
MINDESTHOEHE = 7 * 9 + LEGENDE_HOEHE + 2 * RAND
# Die senkrechte Marke des heutigen Tages steht einen Streifen breit vor.
HEUTE = QColor("#0b0b0b")


class Kalenderstreifen(QWidget):
    """Zeigt ein Karrierejahr als Band aus Tagesstreifen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._zustaende: dict[dt.date, str] = {}
        self._tage: list[dt.date] = []
        self._versatz = 0
        self._heute: dt.date | None = None
        self.setMinimumHeight(MINDESTHOEHE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    # -- Daten -------------------------------------------------------------
    def zeige(self, karriere) -> None:
        """Liest den Zustand jedes Tages aus einer Karriere."""
        if karriere is None:
            self._tage = []
            self._zustaende = {}
            self._versatz = 0
            self._heute = None
            self.update()
            return

        # Wie viele Plaetze an einem Tag schon belegt sind. Der laufende
        # Tag steht in ``belegt``, die vergangenen in den Buchungen.
        belegt: dict[dt.date, int] = {}
        for buchung in karriere.buchungen:
            if buchung.platz:
                belegt[buchung.datum] = belegt.get(buchung.datum, 0) + 1

        self._heute = karriere.heute
        self._tage = [tag.datum for tag in karriere.saison.tage]
        # Der 1. Januar ist selten ein Montag. Ohne Versatz stuende der
        # Renn-Sonntag mal in Zeile 3, mal in Zeile 6, und das Band haette
        # kein Muster; mit Versatz liegt jede Spalte auf einer Woche und
        # das Rennwochenende immer ganz unten.
        self._versatz = self._tage[0].weekday() if self._tage else 0
        self._zustaende = {
            tag.datum: self._zustand(tag, karriere, belegt.get(tag.datum, 0))
            for tag in karriere.saison.tage
        }
        self.update()

    @staticmethod
    def _zustand(tag, karriere, belegt: int) -> str:
        if tag.art is Tagesart.RENNEN:
            return "rennen"
        if tag.art is Tagesart.QUALIFYING:
            return "qualifying"
        if tag.art is Tagesart.REISE:
            return "reise"
        if tag.datum in karriere.verlorene_tage:
            return "verloren"
        if belegt >= 2:
            return "voll"
        if belegt == 1:
            return "halb"
        return "frei"

    def zaehle(self) -> dict[str, int]:
        """Wie viele Tage auf jeden Zustand fallen - fuer die Legende."""
        gezaehlt = dict.fromkeys(FARBEN, 0)
        for zustand in self._zustaende.values():
            gezaehlt[zustand] += 1
        return gezaehlt

    # -- Zeichnen ----------------------------------------------------------
    def paintEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        maler = QPainter(self)
        maler.fillRect(self.rect(), FLAECHE)
        if not self._tage:
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            maler.drawText(self.rect(), Qt.AlignCenter, "Keine Karriere geladen.")
            return

        band = self._bandflaeche()
        breite = band.width() / max(self._spalten(), 1)
        hoehe = band.height() / TAGE_JE_SPALTE

        maler.setPen(Qt.NoPen)
        for nummer, datum in enumerate(self._tage):
            spalte, zeile = divmod(nummer + self._versatz, TAGE_JE_SPALTE)
            # Zwei Pixel Luft zwischen den Streifen - kein Rahmen um sie.
            feld = QRectF(
                band.left() + spalte * breite,
                band.top() + zeile * hoehe,
                max(breite - 1.0, 1.0),
                max(hoehe - 1.0, 1.0),
            )
            maler.setBrush(FARBEN[self._zustaende[datum]])
            maler.drawRect(feld)

        if self._heute is not None and self._heute in self._zustaende:
            stelle = self._tage.index(self._heute) + self._versatz
            spalte = stelle // TAGE_JE_SPALTE
            x = band.left() + spalte * breite
            maler.setPen(QPen(HEUTE, 1.0))
            maler.drawLine(int(x), int(band.top()), int(x), int(band.bottom()))

        self._zeichne_legende(maler, band)

    def _spalten(self) -> int:
        gesamt = len(self._tage) + self._versatz
        return (gesamt + TAGE_JE_SPALTE - 1) // TAGE_JE_SPALTE

    def _bandflaeche(self) -> QRectF:
        return QRectF(
            RAND,
            RAND,
            max(self.width() - 2 * RAND, 1.0),
            max(self.height() - 2 * RAND - LEGENDE_HOEHE, 1.0),
        )

    def _zeichne_legende(self, maler: QPainter, band: QRectF) -> None:
        gezaehlt = self.zaehle()
        masse = QFontMetrics(maler.font())
        x = band.left()
        y = band.bottom() + LEGENDE_HOEHE - 4
        for zustand, farbe in FARBEN.items():
            if not gezaehlt[zustand]:
                continue
            maler.setPen(Qt.NoPen)
            maler.setBrush(farbe)
            maler.drawRect(QRectF(x, y - 8, 8, 8))
            text = f"{BESCHRIFTUNG[zustand]} {gezaehlt[zustand]}"
            maler.setPen(QPen(TEXT_ZWEITRANGIG))
            maler.drawText(int(x + 12), int(y), text)
            x += 12 + masse.horizontalAdvance(text) + 14

    # -- Mouseover ---------------------------------------------------------
    def mouseMoveEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        datum = self._tag_an(ereignis.position().x(), ereignis.position().y())
        if datum is None:
            QToolTip.hideText()
            return
        zustand = self._zustaende[datum]
        QToolTip.showText(
            ereignis.globalPosition().toPoint(),
            f"{wochentag(datum)} {datum:%d.%m.%Y} - {BESCHRIFTUNG[zustand]}",
            self,
        )

    def _tag_an(self, x: float, y: float) -> dt.date | None:
        band = self._bandflaeche()
        if not band.contains(x, y):
            return None
        breite = band.width() / max(self._spalten(), 1)
        hoehe = band.height() / TAGE_JE_SPALTE
        spalte = int((x - band.left()) / breite)
        zeile = int((y - band.top()) / hoehe)
        stelle = spalte * TAGE_JE_SPALTE + zeile - self._versatz
        return self._tage[stelle] if 0 <= stelle < len(self._tage) else None
