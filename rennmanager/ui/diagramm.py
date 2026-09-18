"""Gemeinsame Bausteine der gezeichneten Diagramme.

Gezeichnet wird im ganzen Projekt mit ``QPainter``: PySide6 bringt
``QtCharts`` nicht mit, und eine zusaetzliche Abhaengigkeit muesste in die
.exe. Was sich alle Diagramme teilen - Toene, Raender und das Ziehen einer
Linie durch viele Punkte -, steht hier, damit sie gleich aussehen.

**Fokus und Kontext.** Die Diagramme dieses Spiels zeigen 30 Reihen. Bei
so vielen traegt Farbe keine Identitaet mehr: Benachbarte Toene sind nicht
auseinanderzuhalten, fuer Farbenblinde erst gar nicht. Das Feld liegt
deshalb immer grau im Hintergrund, und hervorgehoben wird nur eine
Handvoll Linien, die am Ende direkt beschriftet sind - so haengt die
Identitaet nicht an der Farbe allein.

Seit der Spieler Teamchef ist, sind es bis zu fuenf: seine **vier**
Fahrer und ein in der Tabelle gewaehlter. Die vier eigenen tragen
Abstufungen **einer** Teamfarbe (siehe ``welt._teamfarbe``) und lesen
sich deshalb als ein Block, nicht als vier Einzelne - der gewaehlte
Fahrer setzt sich mit seiner eigenen Farbe davon ab.

Die Toene kommen aus der Referenzpalette des Diagrammleitfadens; dasselbe
Bild zeichnet ``werkzeuge/rennverlauf.py`` mit matplotlib.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

FLAECHE = QColor("#fcfcfb")
TEXT = QColor("#0b0b0b")
TEXT_ZWEITRANGIG = QColor("#52514e")
GITTER = QColor("#dedcd6")
# Das Feld im Hintergrund: eine Stufe dunkler als das Gitter, damit die
# Linien zu erkennen sind, ohne mit den hervorgehobenen zu konkurrieren.
FELD = QColor("#c4c1b8")

# Hervorgehobene Linien sind 2 px, das Feld 1 px - so will es der
# Leitfaden: duenne Marken, zurueckgenommenes Gitter.
BREITE_FELD = 1.0
BREITE_FOKUS = 2.0
# Hoechstens so viele Linien treten hervor: die vier Autos des
# Spielerteams (GDD 12: autos_je_team) und ein gewaehlter Fahrer.
HOECHSTENS_FOKUS = 5


def flaeche_in(
    breite: int, hoehe: int, links: int, rechts: int, oben: int, unten: int
) -> QRectF:
    """Die Zeichenflaeche eines Diagramms ohne seine Raender."""
    return QRectF(
        links,
        oben,
        max(breite - links - rechts, 1.0),
        max(hoehe - oben - unten, 1.0),
    )


def zeichne_linie(maler: QPainter, x, y, farbe: QColor, breite: float) -> None:
    """Zieht eine Linie durch viele Punkte, ausgeduennt auf die Bildbreite.

    Ein Rennverlauf hat bis zu 30.000 Bildpunkte je Auto. Mehr Punkte als
    das Bild Pixel hat bringen nichts aufs Bild und kosten nur Zeit.
    """
    if len(x) < 2:
        return
    maler.setPen(QPen(farbe, breite, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    pixel = max(int(maler.device().width()), 1)
    schritt = max(1, len(x) // pixel)
    stellen = list(range(0, len(x), schritt))
    if stellen[-1] != len(x) - 1:
        stellen.append(len(x) - 1)
    for erste, zweite in zip(stellen, stellen[1:], strict=False):
        maler.drawLine(int(x[erste]), int(y[erste]), int(x[zweite]), int(y[zweite]))


def zeichne_hinweis(maler: QPainter, rechteck, text: str) -> None:
    """Der Platzhalter, solange es nichts zu zeichnen gibt."""
    maler.setPen(QPen(TEXT))
    maler.drawText(rechteck, Qt.AlignCenter, text)
