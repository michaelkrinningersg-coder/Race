"""Darstellung einer Strecke.

GDD 4 legt fest: die Strecke als Linie. Diese Ansicht zeichnet die
Ideallinie und faerbt sie nach Segmenttyp, damit die Einteilung aus GDD 3
nachvollziehbar wird. Dazu kommen die Sektorgrenzen und die Start/Ziel-Linie.

Die Farben sind reine Darstellung und gehoeren deshalb nicht in die
Balancing-Konfiguration.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from rennmanager.kern.strecke import Segmentart, Strecke

FARBE_HINTERGRUND = QColor("#1b1d21")
FARBE_TEXT = QColor("#d8dbe0")
FARBE_SEGMENT = {
    Segmentart.ENGE_KURVE: QColor("#e05252"),
    Segmentart.KURVE: QColor("#e0a53f"),
    Segmentart.GERADE: QColor("#5aa9e6"),
}
FARBE_UEBERHOLZONE = QColor("#6ee7a0")
FARBE_SEKTORGRENZE = QColor("#8b93a1")
FARBE_START = QColor("#ffffff")
# Farbverlauf fuer das Geschwindigkeitsprofil: langsam nach schnell.
FARBEN_TEMPO = [
    QColor("#2c3e88"),
    QColor("#5aa9e6"),
    QColor("#6ee7a0"),
    QColor("#e0d13f"),
    QColor("#e05252"),
]

RAND_PX = 28
PUNKT_RADIUS_PX = 6.0
# Wer nicht auf seiner gezeiteten Runde ist, wird blasser gezeichnet -
# im Qualifying die Aufwaermrunde. Die Teamfarbe bleibt erkennbar, der
# Punkt tritt aber hinter den zurueck, auf den es gerade ankommt.
DECKKRAFT_GEDAEMPFT = 90
SPIELER_RING_PX = 2.5
# Seitlicher Versatz bei Duellen, damit sich Punkte nicht decken (GDD 4).
DUELL_VERSATZ_PX = 5.0
# Punkt 58: Der in Rangliste oder Zeitenmonitor gewaehlte Fahrer bekommt
# einen goldenen Kreis um seinen Punkt.
FARBE_AUSWAHL = QColor("#f2b705")
AUSWAHL_RING_PX = 2.5
AUSWAHL_ABSTAND_PX = 3.5
LINIENSTAERKE_PX = 3.4
ZONENSTAERKE_PX = 11.0


class Streckenansicht(QWidget):
    """Zeichnet eine Strecke als Linie, eingefaerbt nach Segmenttyp."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._strecke: Strecke | None = None
        self._zeige_ueberholzonen = True
        self._tempo: np.ndarray | None = None
        self._autos: list[tuple[float, str, str, bool]] = []
        # Punkt 58: Das Kuerzel des gewaehlten Fahrers, oder "".
        self._hervorgehoben = ""
        self.setMinimumSize(420, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(True)

    # -- Steuerung ---------------------------------------------------------
    def zeige(self, strecke: Strecke | None) -> None:
        """Legt die dargestellte Strecke fest und loescht ein Tempoprofil."""
        self._strecke = strecke
        self._tempo = None
        self.update()

    def zeige_tempo(self, strecke: Strecke, profil: np.ndarray) -> None:
        """Faerbt die Linie nach der Geschwindigkeit statt nach Segmenttyp.

        :param profil: Geschwindigkeit je Streckenpunkt in m/s
        """
        if len(profil) != len(strecke.punkte):
            raise ValueError("Das Tempoprofil passt nicht zur Strecke")
        self._strecke = strecke
        self._tempo = profil
        self.update()

    @property
    def zeigt_tempo(self) -> bool:
        return self._tempo is not None

    def zeige_autos(self, autos: list[tuple]) -> None:
        """Setzt die Autos, die als Punkte gezeichnet werden (GDD 4).

        :param autos: je Auto ``(Distanz auf der Runde in m, Kuerzel,
            Farbe, ist_spieler)``, dahinter wahlweise ``gedaempft``.
            Gedaempft heisst blasser - im Qualifying faehrt so, wer auf
            der Aufwaermrunde ist und noch nicht gezeitet wird.
        """
        self._autos = autos
        self.update()

    def hebe_hervor(self, kuerzel: str) -> None:
        """Umkreist den Punkt dieses Autos golden; "" nimmt die Marke weg."""
        if kuerzel == self._hervorgehoben:
            return
        self._hervorgehoben = kuerzel or ""
        self.update()

    @property
    def hervorgehoben(self) -> str:
        return self._hervorgehoben

    def setze_ueberholzonen_sichtbar(self, sichtbar: bool) -> None:
        self._zeige_ueberholzonen = sichtbar
        self.update()

    @property
    def strecke(self) -> Strecke | None:
        return self._strecke

    # -- Zeichnen ----------------------------------------------------------
    def paintEvent(self, ereignis) -> None:  # noqa: N802 (Qt-Namensschema)
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        maler.fillRect(self.rect(), FARBE_HINTERGRUND)

        if self._strecke is None:
            self._zeichne_hinweis(maler, "Keine Strecke gewaehlt")
            return

        umrechnung = self._umrechnung(self._strecke.punkte)
        if umrechnung is None:
            self._zeichne_hinweis(maler, "Die Strecke laesst sich nicht darstellen")
            return

        bild = self._bildpunkte(self._strecke.punkte, umrechnung)
        if self._tempo is not None:
            self._zeichne_tempo(maler, bild, self._tempo)
        else:
            # Die Ueberholzonen liegen als breite Spur unter der Linie, sonst
            # wuerden sie die Segmentfarben verdecken.
            if self._zeige_ueberholzonen:
                self._zeichne_ueberholzonen(maler, bild)
            self._zeichne_segmente(maler, bild)
        self._zeichne_sektorgrenzen(maler, bild)
        self._zeichne_start(maler, bild)
        if self._autos:
            self._zeichne_autos(maler, umrechnung)
        self._zeichne_legende(maler)

    def _umrechnung(self, punkte: np.ndarray) -> tuple[float, float, float] | None:
        """Liefert (Faktor, Verschiebung x, Verschiebung y) fuer die Anzeige."""
        breite = self.width() - 2 * RAND_PX
        hoehe = self.height() - 2 * RAND_PX
        if breite <= 0 or hoehe <= 0:
            return None

        min_x, min_y = punkte.min(axis=0)
        max_x, max_y = punkte.max(axis=0)
        spanne_x = max(max_x - min_x, 1e-6)
        spanne_y = max(max_y - min_y, 1e-6)

        # Seitenverhaeltnis erhalten, sonst waere die Streckenform verzerrt.
        faktor = min(breite / spanne_x, hoehe / spanne_y)
        versatz_x = RAND_PX + (breite - spanne_x * faktor) / 2 - min_x * faktor
        # Die y-Achse zeigt in der Anzeige nach unten, in den Daten nach oben.
        versatz_y = RAND_PX + (hoehe - spanne_y * faktor) / 2 + max_y * faktor
        return faktor, versatz_x, versatz_y

    @staticmethod
    def _bildpunkte(punkte: np.ndarray, umrechnung: tuple[float, float, float]) -> np.ndarray:
        faktor, versatz_x, versatz_y = umrechnung
        return np.column_stack(
            [punkte[:, 0] * faktor + versatz_x, versatz_y - punkte[:, 1] * faktor]
        )

    def _zeichne_segmente(self, maler: QPainter, bild: np.ndarray) -> None:
        """Zeichnet die Linie abschnittsweise in der Farbe des Segmenttyps."""
        assert self._strecke is not None
        anzahl = len(bild)
        for segment in self._strecke.segmente:
            indizes = (segment.von + np.arange(segment.punkte + 1)) % anzahl
            pfad = self._pfad(bild[indizes])
            stift = QPen(FARBE_SEGMENT[segment.art], LINIENSTAERKE_PX)
            stift.setCapStyle(Qt.RoundCap)
            stift.setJoinStyle(Qt.RoundJoin)
            maler.setPen(stift)
            maler.drawPath(pfad)

    def _zeichne_ueberholzonen(self, maler: QPainter, bild: np.ndarray) -> None:
        """Hebt die Geraden ab 100 m hervor (GDD 3)."""
        assert self._strecke is not None
        anzahl = len(bild)
        farbe = QColor(FARBE_UEBERHOLZONE)
        farbe.setAlpha(70)
        stift = QPen(farbe, ZONENSTAERKE_PX)
        stift.setCapStyle(Qt.RoundCap)
        maler.setPen(stift)
        for zone in self._strecke.ueberholzonen:
            indizes = (zone.von + np.arange(zone.punkte + 1)) % anzahl
            maler.drawPath(self._pfad(bild[indizes]))

    def _zeichne_sektorgrenzen(self, maler: QPainter, bild: np.ndarray) -> None:
        assert self._strecke is not None
        maler.setFont(QFont(self.font().family(), 9, QFont.Bold))
        for sektor in self._strecke.sektoren:
            self._zeichne_quermarke(maler, bild, sektor.von, FARBE_SEKTORGRENZE, 11.0, staerke=2.0)
            # Die Beschriftung sitzt in der Mitte des Sektors.
            mitte = (sektor.von + sektor.bis) // 2 % len(bild)
            punkt = QPointF(*bild[mitte])
            feld = QRectF(punkt.x() - 13, punkt.y() - 9, 26, 18)
            maler.setPen(Qt.NoPen)
            maler.setBrush(QColor(FARBE_HINTERGRUND.red(), FARBE_HINTERGRUND.green(),
                                  FARBE_HINTERGRUND.blue(), 210))
            maler.drawRoundedRect(feld, 4, 4)
            maler.setBrush(Qt.NoBrush)
            maler.setPen(QPen(FARBE_SEKTORGRENZE))
            maler.drawText(feld, Qt.AlignCenter, f"S{sektor.nummer}")

    def _zeichne_start(self, maler: QPainter, bild: np.ndarray) -> None:
        self._zeichne_quermarke(maler, bild, 0, FARBE_START, 13.0, staerke=2.5)

    def _zeichne_quermarke(
        self,
        maler: QPainter,
        bild: np.ndarray,
        index: int,
        farbe: QColor,
        laenge: float,
        staerke: float = 1.6,
    ) -> None:
        """Zeichnet einen Strich quer zur Fahrtrichtung."""
        anzahl = len(bild)
        hier = bild[index % anzahl]
        naechster = bild[(index + 1) % anzahl]
        richtung = naechster - hier
        betrag = float(np.hypot(*richtung))
        if betrag < 1e-9:
            return
        quer = np.array([-richtung[1], richtung[0]]) / betrag * laenge / 2

        maler.setPen(QPen(farbe, staerke))
        maler.drawLine(
            QPointF(hier[0] - quer[0], hier[1] - quer[1]),
            QPointF(hier[0] + quer[0], hier[1] + quer[1]),
        )

    def _zeichne_tempo(self, maler: QPainter, bild: np.ndarray, profil: np.ndarray) -> None:
        """Zeichnet die Linie Stueck fuer Stueck in der Farbe des Tempos."""
        langsamste = float(profil.min())
        schnellste = float(profil.max())
        spanne = max(schnellste - langsamste, 1e-6)

        stift = QPen(FARBE_SEGMENT[Segmentart.GERADE], LINIENSTAERKE_PX + 1.0)
        stift.setCapStyle(Qt.RoundCap)
        anzahl = len(bild)
        for i in range(anzahl):
            naechster = (i + 1) % anzahl
            anteil = (float(profil[i]) - langsamste) / spanne
            stift.setColor(self._tempofarbe(anteil))
            maler.setPen(stift)
            maler.drawLine(QPointF(*bild[i]), QPointF(*bild[naechster]))

    @staticmethod
    def _tempofarbe(anteil: float) -> QColor:
        """Mischt die Farbe zwischen den Stuetzfarben des Verlaufs."""
        anteil = min(max(anteil, 0.0), 1.0)
        stelle = anteil * (len(FARBEN_TEMPO) - 1)
        unten = int(stelle)
        if unten >= len(FARBEN_TEMPO) - 1:
            return FARBEN_TEMPO[-1]
        rest = stelle - unten
        von, bis = FARBEN_TEMPO[unten], FARBEN_TEMPO[unten + 1]
        return QColor(
            round(von.red() + (bis.red() - von.red()) * rest),
            round(von.green() + (bis.green() - von.green()) * rest),
            round(von.blue() + (bis.blue() - von.blue()) * rest),
        )

    def _zeichne_autos(self, maler: QPainter, umrechnung: tuple[float, float, float]) -> None:
        """Zeichnet die Autos als Punkte in Teamfarbe mit Kuerzel (GDD 4).

        **Immer zentriert auf der Linie**, auch beim Ueberholen - zur Not
        uebereinander. Ein frueherer Entwurf schob dicht gedraengte Punkte
        quer zur Fahrtrichtung auseinander; auf Wunsch des Auftraggebers
        steht jeder Punkt jetzt genau dort, wo das Auto faehrt. Wer
        vorn liegt, wird zuletzt gezeichnet und liegt damit obenauf.

        Ein Kuerzel wird nur gesetzt, wenn dafuer Platz ist; der Spieler
        und der gerade gewaehlte Fahrer haben Vorrang.
        """
        assert self._strecke is not None
        orte = [self._ort_auf_der_linie(distanz) for distanz, *_ in self._autos]
        bild = self._bildpunkte(np.array(orte), umrechnung)
        stellen = [bild[nummer] for nummer in range(len(self._autos))]

        # Von hinten nach vorn zeichnen, damit der Fuehrende obenauf liegt.
        for nummer in range(len(stellen) - 1, -1, -1):
            stelle = stellen[nummer]
            _, kuerzel, farbe, ist_spieler, *rest = self._autos[nummer]
            ton = QColor(farbe)
            if rest and rest[0]:
                ton.setAlpha(DECKKRAFT_GEDAEMPFT)
            maler.setBrush(ton)
            maler.setPen(QPen(FARBE_START, SPIELER_RING_PX) if ist_spieler else QPen(Qt.NoPen))
            maler.drawEllipse(QPointF(*stelle), PUNKT_RADIUS_PX, PUNKT_RADIUS_PX)
            if kuerzel and kuerzel == self._hervorgehoben:
                # Der gewaehlte Fahrer bekommt einen goldenen Kreis -
                # so findet man sein Auto im Feld wieder.
                maler.setBrush(Qt.NoBrush)
                maler.setPen(QPen(FARBE_AUSWAHL, AUSWAHL_RING_PX))
                maler.drawEllipse(
                    QPointF(*stelle),
                    PUNKT_RADIUS_PX + AUSWAHL_ABSTAND_PX,
                    PUNKT_RADIUS_PX + AUSWAHL_ABSTAND_PX,
                )
        maler.setBrush(Qt.NoBrush)

        self._zeichne_kuerzel(maler, stellen)

    def _zeichne_kuerzel(self, maler: QPainter, stellen: list[np.ndarray]) -> None:
        """Setzt die Kuerzel, wo Platz ist; das des Spielers immer."""
        maler.setFont(QFont(self.font().family(), 7, QFont.Bold))
        breite, hoehe = 30.0, 12.0

        # Der gewaehlte Fahrer zuerst, dann der Spieler, dann von vorn
        # nach hinten.
        def vorrang(n: int) -> tuple:
            return (
                self._autos[n][1] != self._hervorgehoben,
                not self._autos[n][3],
                n,
            )

        reihenfolge = sorted(range(len(stellen)), key=vorrang)
        belegt: list[QRectF] = []
        for nummer in reihenfolge:
            stelle = stellen[nummer]
            feld = QRectF(
                stelle[0] - breite / 2,
                stelle[1] - PUNKT_RADIUS_PX - hoehe - 2,
                breite,
                hoehe,
            )
            ist_spieler = self._autos[nummer][3]
            gewaehlt = self._autos[nummer][1] == self._hervorgehoben
            if (
                not ist_spieler
                and not gewaehlt
                and any(feld.intersects(anderes) for anderes in belegt)
            ):
                continue
            belegt.append(feld)
            if gewaehlt:
                maler.setPen(QPen(FARBE_AUSWAHL))
            else:
                maler.setPen(QPen(FARBE_START if ist_spieler else FARBE_TEXT))
            maler.drawText(feld, Qt.AlignCenter, self._autos[nummer][1])

    def _ort_auf_der_linie(self, distanz: float) -> np.ndarray:
        """Punkt auf der Ideallinie zu einer Distanz, zwischen den Punkten."""
        assert self._strecke is not None
        punkte = self._strecke.punkte
        anzahl = len(punkte)
        stelle = (distanz % self._strecke.laenge_m) / self._strecke.punktabstand_m
        hier = int(stelle) % anzahl
        dort = (hier + 1) % anzahl
        rest = stelle - int(stelle)
        return punkte[hier] + rest * (punkte[dort] - punkte[hier])

    def _querrichtung(self, distanz: float) -> np.ndarray:
        """Einheitsvektor quer zur Fahrtrichtung, in Bildkoordinaten."""
        assert self._strecke is not None
        punkte = self._strecke.punkte
        anzahl = len(punkte)
        hier = int((distanz % self._strecke.laenge_m) / self._strecke.punktabstand_m) % anzahl
        richtung = punkte[(hier + 1) % anzahl] - punkte[hier]
        betrag = float(np.hypot(*richtung)) or 1.0
        # Die y-Achse ist in der Anzeige gespiegelt.
        return np.array([-richtung[1], -richtung[0]]) / betrag

    def _zeichne_legende(self, maler: QPainter) -> None:
        assert self._strecke is not None
        maler.setFont(QFont(self.font().family(), 8))
        if self._tempo is not None:
            langsamste = float(self._tempo.min()) * 3.6
            schnellste = float(self._tempo.max()) * 3.6
            eintraege = [
                (FARBEN_TEMPO[0], f"{langsamste:.0f} km/h"),
                (FARBEN_TEMPO[len(FARBEN_TEMPO) // 2], "Tempo"),
                (FARBEN_TEMPO[-1], f"{schnellste:.0f} km/h"),
            ]
        else:
            eintraege = [
                (FARBE_SEGMENT[Segmentart.ENGE_KURVE], "Enge Kurve"),
                (FARBE_SEGMENT[Segmentart.KURVE], "Kurve"),
                (FARBE_SEGMENT[Segmentart.GERADE], "Gerade"),
            ]
            if self._zeige_ueberholzonen:
                eintraege.append((FARBE_UEBERHOLZONE, "Ueberholzone"))

        y = 8.0
        for farbe, beschriftung in eintraege:
            maler.setPen(QPen(farbe, 3))
            maler.drawLine(QPointF(8, y + 7), QPointF(26, y + 7))
            maler.setPen(QPen(FARBE_TEXT))
            maler.drawText(QRectF(32, y, 120, 14), Qt.AlignVCenter | Qt.AlignLeft, beschriftung)
            y += 15

    def _zeichne_hinweis(self, maler: QPainter, text: str) -> None:
        maler.setPen(QPen(FARBE_TEXT))
        maler.drawText(self.rect(), Qt.AlignCenter, text)

    @staticmethod
    def _pfad(bild: np.ndarray) -> QPainterPath:
        pfad = QPainterPath(QPointF(*bild[0]))
        for punkt in bild[1:]:
            pfad.lineTo(QPointF(*punkt))
        return pfad
