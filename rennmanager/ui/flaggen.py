"""Mini-Flaggen der Nationen fuer die Fahrertabellen (Punkt 105).

Jede Tabelle, in der Fahrer stehen, zeigt neben dem Namen die Flagge
seiner Nation. Sie steht **im Namensfeld**, nicht in einer eigenen
Spalte: Die Rangliste der Rennseite braucht schon 1195 px fuer ihre 16
Spalten und bekommt 802 (siehe OFFENE_PUNKTE, Vorschlag 23); eine Spalte
mehr haette das verschlimmert. Als Symbol im Namensfeld kostet die
Flagge einmalig die Symbolbreite.

**Gezeichnet, nicht geladen.** Naheliegend waeren die Unicode-Flaggen
(\\U0001F1E9\\U0001F1EA und so weiter), aber Windows hat keine
Flaggenglyphen: Segoe UI Emoji zeigt dort zwei Buchstaben in Kaestchen
statt einer Flagge, und Windows ist die Zielplattform (GDD 15).
Bilddateien waeren die Alternative, kosteten aber zwei Dutzend Dateien
im Bundle und eine Lizenzfrage. Also malt dieses Modul sie selbst - mit
denselben Mitteln wie die Streckenkarte.

**Was das nicht kann.** Bei 16 mal 11 Pixeln fallen Flaggen zusammen,
die sich nur durch ein Wappen unterscheiden: Italien und Mexiko sind
beide gruen-weiss-rot senkrecht, Slowenien ohne Wappen sieht aus wie
Russland, Kroatien fehlt das Schachbrett, Spanien und Portugal fehlt das
Emblem, Kanada das Ahornblatt. Dagegen hilft nur der Name daneben oder
im Tooltip - beides gibt es in den Tabellen ohnehin.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap, QPolygonF

# Groesse in der Tabellenzeile. Hoehe zu Breite wie 2:3, also die uebliche
# Flaggenform; groesser sprengt die Zeilenhoehe, kleiner wird matschig.
BREITE_PX = 16
HOEHE_PX = 11

# Waagerechte Streifen, von oben nach unten.
WAAGERECHT = {
    "Bulgarien": ("#ffffff", "#00966e", "#d62612"),
    "Deutschland": ("#000000", "#dd0000", "#ffce00"),
    "Estland": ("#0072ce", "#000000", "#ffffff"),
    "Kroatien": ("#ff0000", "#ffffff", "#171796"),
    # Lettland traegt einen schmalen weissen Streifen in der Mitte; bei
    # elf Pixeln Hoehe waeren drei gleiche Streifen falsch.
    "Lettland": ("#9e3039", "#9e3039", "#ffffff", "#9e3039", "#9e3039"),
    "Litauen": ("#fdb913", "#006a44", "#c1272d"),
    "Luxemburg": ("#ed2939", "#ffffff", "#00a1de"),
    "Niederlande": ("#ae1c28", "#ffffff", "#21468b"),
    "Oesterreich": ("#ed2939", "#ffffff", "#ed2939"),
    "Polen": ("#ffffff", "#dc143c"),
    "Russland": ("#ffffff", "#0039a6", "#d52b1e"),
    "Slowakei": ("#ffffff", "#0b4ea2", "#ee1c25"),
    "Slowenien": ("#ffffff", "#0000ff", "#ff0000"),
    "Spanien": ("#aa151b", "#f1bf00", "#aa151b"),
    "Ungarn": ("#cd2a3e", "#ffffff", "#436f4d"),
}

# Senkrechte Streifen, von links nach rechts.
SENKRECHT = {
    "Belgien": ("#000000", "#fdda24", "#ef3340"),
    "Frankreich": ("#002395", "#ffffff", "#ed2939"),
    "Irland": ("#169b62", "#ffffff", "#ff883e"),
    "Italien": ("#008c45", "#f4f9ff", "#cd212a"),
    "Kanada": ("#d80621", "#ffffff", "#d80621"),
    "Mexiko": ("#006847", "#ffffff", "#ce1126"),
    "Portugal": ("#046a38", "#046a38", "#da291c"),
    "Rumaenien": ("#002b7f", "#fcd116", "#ce1126"),
}

# Nordkreuz: Grundfarbe, Kreuzfarbe. Der senkrechte Balken sitzt links.
NORDKREUZ = {
    "Daenemark": ("#c8102e", "#ffffff"),
    "Finnland": ("#ffffff", "#003580"),
    "Island": ("#02529c", "#ffffff"),
    "Norwegen": ("#ba0c2f", "#ffffff"),
    "Schweden": ("#006aa7", "#fecc00"),
}

# Der Rahmen. Ohne ihn verschwindet jede Flagge mit weissem Rand auf dem
# hellen Tabellengrund - Finnland und Polen waeren nur noch halb da.
FARBE_RAHMEN = QColor(0, 0, 0, 70)


def _nordkreuz(maler: QPainter, feld: QRectF, grund: str, kreuz: str) -> None:
    maler.fillRect(feld, QColor(grund))
    balken = max(HOEHE_PX * 0.27, 2.0)
    maler.fillRect(
        QRectF(feld.x(), feld.y() + (HOEHE_PX - balken) / 2, BREITE_PX, balken),
        QColor(kreuz),
    )
    maler.fillRect(
        QRectF(feld.x() + BREITE_PX * 0.32 - balken / 2, feld.y(), balken, HOEHE_PX),
        QColor(kreuz),
    )


def _schweiz(maler: QPainter, feld: QRectF) -> None:
    maler.fillRect(feld, QColor("#d52b1e"))
    balken = 3.0
    maler.fillRect(
        QRectF(feld.x() + BREITE_PX / 2 - balken / 2, feld.y() + 2, balken, HOEHE_PX - 4),
        QColor("#ffffff"),
    )
    maler.fillRect(
        QRectF(feld.x() + 4.0, feld.y() + HOEHE_PX / 2 - balken / 2, BREITE_PX - 8, balken),
        QColor("#ffffff"),
    )


def _union_jack(maler: QPainter, feld: QRectF) -> None:
    """Stark vereinfacht - die Diagonalen sind nur angedeutet."""
    maler.fillRect(feld, QColor("#012169"))
    maler.setPen(QColor("#ffffff"))
    x, y = int(feld.x()), int(feld.y())
    maler.drawLine(x, y, x + BREITE_PX, y + HOEHE_PX)
    maler.drawLine(x, y + HOEHE_PX, x + BREITE_PX, y)
    maler.setPen(Qt.NoPen)
    maler.fillRect(QRectF(feld.x(), feld.y() + HOEHE_PX / 2 - 1.5, BREITE_PX, 3),
                   QColor("#ffffff"))
    maler.fillRect(QRectF(feld.x() + BREITE_PX / 2 - 1.5, feld.y(), 3, HOEHE_PX),
                   QColor("#ffffff"))
    maler.fillRect(QRectF(feld.x(), feld.y() + HOEHE_PX / 2 - 0.75, BREITE_PX, 1.5),
                   QColor("#c8102e"))
    maler.fillRect(QRectF(feld.x() + BREITE_PX / 2 - 0.75, feld.y(), 1.5, HOEHE_PX),
                   QColor("#c8102e"))


def _streifen_mit_ecke(
    maler: QPainter, feld: QRectF, streifen: str, ecke: QRectF, eckfarbe: str,
    zahl: int,
) -> None:
    """Weisser Grund, farbige Streifen, farbige Ecke - USA und Griechenland."""
    maler.fillRect(feld, QColor("#ffffff"))
    hoehe = HOEHE_PX / (zahl * 2 - 1)
    for i in range(zahl):
        maler.fillRect(
            QRectF(feld.x(), feld.y() + i * hoehe * 2, BREITE_PX, hoehe),
            QColor(streifen),
        )
    maler.fillRect(ecke, QColor(eckfarbe))


def _male(maler: QPainter, land: str, feld: QRectF) -> bool:
    """Malt eine Flagge in das Feld; False, wenn die Nation unbekannt ist."""
    maler.setPen(Qt.NoPen)
    if land in WAAGERECHT:
        farben = WAAGERECHT[land]
        hoehe = HOEHE_PX / len(farben)
        for i, farbe in enumerate(farben):
            maler.fillRect(
                QRectF(feld.x(), feld.y() + i * hoehe, BREITE_PX, hoehe + 0.5),
                QColor(farbe),
            )
    elif land in SENKRECHT:
        farben = SENKRECHT[land]
        breite = BREITE_PX / len(farben)
        for i, farbe in enumerate(farben):
            maler.fillRect(
                QRectF(feld.x() + i * breite, feld.y(), breite + 0.5, HOEHE_PX),
                QColor(farbe),
            )
    elif land in NORDKREUZ:
        _nordkreuz(maler, feld, *NORDKREUZ[land])
    elif land == "Schweiz":
        _schweiz(maler, feld)
    elif land == "Grossbritannien":
        _union_jack(maler, feld)
    elif land == "Tschechien":
        # Weiss oben, rot unten, blauer Keil am Mast.
        maler.fillRect(
            QRectF(feld.x(), feld.y(), BREITE_PX, HOEHE_PX / 2 + 0.5),
            QColor("#ffffff"),
        )
        maler.fillRect(
            QRectF(feld.x(), feld.y() + HOEHE_PX / 2, BREITE_PX, HOEHE_PX / 2),
            QColor("#d7141a"),
        )
        keil = QPolygonF([
            QPointF(feld.x(), feld.y()),
            QPointF(feld.x() + BREITE_PX * 0.5, feld.y() + HOEHE_PX / 2),
            QPointF(feld.x(), feld.y() + HOEHE_PX),
        ])
        maler.setBrush(QColor("#11457e"))
        maler.drawPolygon(keil)
        maler.setBrush(Qt.NoBrush)
    elif land == "USA":
        _streifen_mit_ecke(
            maler, feld, "#b31942",
            QRectF(feld.x(), feld.y(), BREITE_PX * 0.42, HOEHE_PX * 0.54),
            "#0a3161", 7,
        )
    elif land == "Griechenland":
        _streifen_mit_ecke(
            maler, feld, "#0d5eaf",
            QRectF(feld.x(), feld.y(), HOEHE_PX * 0.55, HOEHE_PX * 0.55),
            "#0d5eaf", 5,
        )
    else:
        return False
    maler.setPen(FARBE_RAHMEN)
    maler.drawRect(feld.adjusted(0, 0, -1, -1))
    return True


@lru_cache(maxsize=128)
def flagge(land: str) -> QIcon:
    """Das Symbol zu einer Nation; leer, wenn sie kein Muster hat.

    Zwischengespeichert: Die Rangliste zeichnet fuenfzig Zeilen in jedem
    Bild neu, und ein QIcon je Zeile und Bild waere Arbeit fuer nichts.
    Ein leeres ``QIcon`` ist ein gueltiger Wert - Qt laesst den Platz
    dann einfach frei.
    """
    bild = QImage(BREITE_PX, HOEHE_PX, QImage.Format_ARGB32)
    bild.fill(QColor(0, 0, 0, 0))
    maler = QPainter(bild)
    maler.setRenderHint(QPainter.Antialiasing, False)
    erkannt = _male(maler, land, QRectF(0, 0, BREITE_PX, HOEHE_PX))
    maler.end()
    if not erkannt:
        return QIcon()
    return QIcon(QPixmap.fromImage(bild))


def setze_flagge(zeile, spalte: int, land: str) -> None:
    """Setzt Flagge und Tooltip einer Nation in eine Tabellenzelle.

    Der Tooltip traegt den Namen, weil die Flagge ihn bei dieser Groesse
    nicht immer hergibt: Italien und Mexiko zum Beispiel sind beide
    gruen-weiss-rot senkrecht.
    """
    if not land:
        return
    symbol = flagge(land)
    if symbol.isNull():
        return
    zeile.setIcon(spalte, symbol)
    zeile.setToolTip(spalte, land)


def bekannte_nationen() -> frozenset[str]:
    """Alle Nationen, fuer die es ein Muster gibt - fuer die Tests."""
    return frozenset(
        set(WAAGERECHT) | set(SENKRECHT) | set(NORDKREUZ)
        | {"Schweiz", "Grossbritannien", "USA", "Griechenland", "Tschechien"}
    )
