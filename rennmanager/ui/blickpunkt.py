"""Der Fahrer, auf den man im Qualifying gerade schaut (Punkt 107).

Eine Box unter der Streckenkarte, die genau einen Fahrer zeigt. Sie
traegt seinen Namen, sein Team, seine Nation mit Flagge - und darunter
die Zeiten.

Welcher Fahrer? Zu Beginn der, der als Erster auf seine gezeitete
Runde geht (``Qualifying.blickpunkt``). Danach **haelt** die Box ihn
fest, bis der Spieler im Zeitenmonitor einen anderen anklickt -
Entscheidung des Auftraggebers in der Nachbesserung zu Punkt 107. Einen
automatischen Wechsel gibt es nicht mehr.

Waehrend er faehrt, laeuft die Rundenzeit mit. Jeder Split, den er
passiert hat, bleibt stehen - **dauerhaft**, nicht mehr nur zwei
Drittel des Weges bis zum naechsten:

* links die Gesamtzeit bis zu diesem Split, immer schwarz,
* rechts daneben der Vorsprung oder Rueckstand dieser Gesamtzeit auf
  den, der gerade fuehrt, und in Klammern der Platz an dieser Stelle -
  diese beiden gruen, wenn er schneller ist, rot, wenn langsamer.

Im Ziel steht dasselbe noch einmal neben der grossen Endzeit: die Zeit
schwarz, Abstand und Platz in der Farbe.

Gerechnet wird hier nichts: Die Zahlen kommen aus
``rennmanager.kern.qualifying`` (``blickpunkt``, ``gesamt_bis``,
``splitabstand``, ``splitplatz``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.qualifying import Fahrt, Qualifying
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.ui.flaggen import BREITE_PX, HOEHE_PX, flagge
from rennmanager.ui.tabellen import kurzname, schriftfarbe

# Dieselben Farben wie in der Zeitentafel - gruen schneller, rot
# langsamer. Eine eigene Palette hier haette dieselbe Aussage in anderen
# Farben erzaehlt.
FARBE_SCHNELLER = QColor("#2e7d32")
FARBE_LANGSAMER = QColor("#c62828")
FARBE_BLASS = QColor("#8b93a1")

# Die Rundenzeit ist der groesste Text der Box - sie ist der Grund,
# warum man hinsieht.
SCHRIFT_UHR = 20
SCHRIFT_NAME = 12

SPALTE_MARKE = 0
SPALTE_ZEIT = 1
SPALTE_ABSTAND = 2


class Blickpunktbox(QGroupBox):
    """Zeigt einen Fahrer mit seinen Splits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Auf der Runde", parent)
        self._session: Qualifying | None = None
        self._fahrt: Fahrt | None = None
        self._namen: dict[int, str] = {}
        self._teams: dict[int, str] = {}

        spalte = QVBoxLayout(self)

        self._flagge = QLabel()
        self._flagge.setFixedSize(BREITE_PX, HOEHE_PX)
        self._name = QLabel("-")
        self._name.setFont(QFont(self.font().family(), SCHRIFT_NAME, QFont.Bold))
        self._herkunft = QLabel("")
        self._herkunft.setStyleSheet(f"color: {FARBE_BLASS.name()};")

        kopf = QGridLayout()
        kopf.setContentsMargins(0, 0, 0, 0)
        kopf.addWidget(self._flagge, 0, 0)
        kopf.addWidget(self._name, 0, 1)
        kopf.addWidget(self._herkunft, 1, 0, 1, 2)
        kopf.setColumnStretch(1, 1)
        spalte.addLayout(kopf)

        # Die grosse Zeit, und im Ziel daneben Abstand und Platz.
        uhrzeile = QHBoxLayout()
        uhrzeile.addStretch(1)
        self._uhr = QLabel("-")
        self._uhr.setFont(QFont(self.font().family(), SCHRIFT_UHR, QFont.Bold))
        self._uhr.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._endabstand = QLabel("")
        self._endabstand.setFont(
            QFont(self.font().family(), SCHRIFT_NAME, QFont.Bold)
        )
        self._endabstand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        uhrzeile.addWidget(self._uhr)
        uhrzeile.addSpacing(12)
        uhrzeile.addWidget(self._endabstand)
        spalte.addLayout(uhrzeile)

        # Je Sektor eine Zeile: Marke, Gesamtzeit, Abstand mit Platz.
        self._splits = QGridLayout()
        self._splits.setContentsMargins(0, 0, 0, 0)
        self._splits.setHorizontalSpacing(16)
        self._splitmarken: list[QLabel] = []
        self._splitzeiten: list[QLabel] = []
        self._splitwerte: list[QLabel] = []
        spalte.addLayout(self._splits)
        spalte.addStretch(1)

    # -- Fuellen ------------------------------------------------------------
    def zeige_session(self, session: Qualifying | None) -> None:
        """Nimmt eine gefahrene Session entgegen und baut die Splitzeilen.

        Eine neue Session faengt ohne Fahrer an - der alte gehoert zu
        einem anderen Wochenende.
        """
        self._session = session
        self._fahrt = None
        for feld in self._splitmarken + self._splitzeiten + self._splitwerte:
            feld.deleteLater()
        self._splitmarken = []
        self._splitzeiten = []
        self._splitwerte = []
        if session is None:
            self._leere()
            return

        for nummer in range(len(session.strecke.sektoren)):
            marke = QLabel(f"S{nummer + 1}")
            marke.setStyleSheet(f"color: {FARBE_BLASS.name()};")
            zeit = QLabel(" ")
            zeit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            wert = QLabel(" ")
            wert.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._splits.addWidget(marke, nummer, SPALTE_MARKE)
            self._splits.addWidget(zeit, nummer, SPALTE_ZEIT)
            self._splits.addWidget(wert, nummer, SPALTE_ABSTAND)
            self._splitmarken.append(marke)
            self._splitzeiten.append(zeit)
            self._splitwerte.append(wert)
        self._splits.setColumnStretch(SPALTE_ABSTAND, 1)
        self._leere()

    def zeige_namen(self, namen: dict[int, str], teams: dict[int, str]) -> None:
        """Fahrernamen und Rennstaelle je Fahrernummer.

        Der Teilnehmer traegt nur Kuerzel, Farbe und Nation - Name und
        Team kommen wie in der Zeitentafel von aussen, aus der Welt.
        """
        self._namen = {nummer: kurzname(name) for nummer, name in namen.items()}
        self._teams = dict(teams)

    def waehle(self, teilnehmer: int) -> None:
        """Der Spieler hat einen Fahrer angeklickt - der gehoert jetzt hierher.

        ``teilnehmer`` ist die Stelle im Feld der Session. Er bleibt, bis
        der naechste Klick kommt.
        """
        if self._session is None:
            return
        self._fahrt = next(
            (f for f in self._session.fahrten if f.teilnehmer == teilnehmer),
            self._fahrt,
        )

    def zeichne(self, zeit_ms: float) -> None:
        """Setzt die Box auf den Stand dieses Augenblicks."""
        session = self._session
        if session is None:
            return
        # Nur solange noch niemand in der Box steht, waehlt die Session
        # selbst. Danach haelt die Box ihren Fahrer.
        if self._fahrt is None:
            self._fahrt = session.blickpunkt(zeit_ms)
        fahrt = self._fahrt
        if fahrt is None:
            self._leere()
            return

        self._setze_kopf(session.teilnehmer[fahrt.teilnehmer])
        self._setze_uhr(session, fahrt, zeit_ms)
        self._setze_splits(session, fahrt, zeit_ms)

    def _leere(self) -> None:
        self.setTitle("Auf der Runde")
        self._flagge.clear()
        self._name.setText("-")
        self._name.setStyleSheet("")
        self._herkunft.setText("Gerade ist niemand auf einer gezeiteten Runde.")
        self._uhr.setText("-")
        self._endabstand.setText("")
        for feld in self._splitzeiten + self._splitwerte:
            feld.setText(" ")

    def _setze_kopf(self, teilnehmer) -> None:
        """Vorname als Buchstabe, Nachname, darunter Rennstall und Nation."""
        symbol = flagge(teilnehmer.land)
        if symbol.isNull():
            self._flagge.clear()
        else:
            self._flagge.setPixmap(symbol.pixmap(BREITE_PX, HOEHE_PX))
        self._flagge.setToolTip(teilnehmer.land)

        self._name.setText(
            self._namen.get(teilnehmer.nummer) or teilnehmer.kuerzel
        )
        self._name.setStyleSheet(
            f"color: {schriftfarbe(teilnehmer.farbe).name()};"
        )
        teile = [self._teams.get(teilnehmer.nummer, ""), teilnehmer.land]
        self._herkunft.setText(" · ".join(t for t in teile if t))

    def _setze_uhr(self, session: Qualifying, fahrt: Fahrt, zeit_ms: float) -> None:
        """Die Rundenzeit - schwarz; im Ziel daneben Abstand und Platz."""
        if zeit_ms < fahrt.beginn_ms:
            # Angeklickt, bevor er losfaehrt: Er steht noch in der Box.
            self.setTitle("In der Box")
            self._uhr.setText("-")
            self._endabstand.setText("")
            return
        if zeit_ms < fahrt.runde_ab_ms:
            self.setTitle("Auf der Aufwaermrunde")
            self._uhr.setText("-")
            self._endabstand.setText("")
            return
        if zeit_ms < fahrt.ziel_ms:
            self.setTitle("Auf der Runde")
            self._uhr.setText(formatiere_dauer(int(zeit_ms - fahrt.runde_ab_ms)))
            self._endabstand.setText("")
            return
        self.setTitle("Runde beendet")
        self._uhr.setText(formatiere_dauer(fahrt.zeit_ms))
        # Die Endzeit ist der letzte Split: dieselben Zahlen wie dort.
        letzter = len(session.strecke.sektoren) - 1
        self._schreibe_abstand(self._endabstand, session, fahrt, letzter, zeit_ms)

    def _setze_splits(self, session: Qualifying, fahrt: Fahrt, zeit_ms: float) -> None:
        """Jeder passierte Split bleibt stehen, jeder kommende ist leer."""
        enden = fahrt.sektorenden_ms
        for nummer, (zeit, wert) in enumerate(
            zip(self._splitzeiten, self._splitwerte, strict=True)
        ):
            if zeit_ms < enden[nummer]:
                zeit.setText(" ")
                wert.setText(" ")
                continue
            zeit.setText(formatiere_dauer(session.gesamt_bis(fahrt, nummer)))
            self._schreibe_abstand(wert, session, fahrt, nummer, zeit_ms)

    @staticmethod
    def _schreibe_abstand(
        feld: QLabel, session: Qualifying, fahrt: Fahrt, nummer: int, zeit_ms: float
    ) -> None:
        """Abstand und Platz an einem Split, in der Farbe des Vergleichs.

        Gemessen wird gegen den, der in **diesem** Augenblick fuehrt -
        nicht gegen die Pole am Ende der Session, die waehrend der
        Uebertragung noch niemand kennt.
        """
        abstand = session.splitabstand(fahrt, nummer, zeit_ms)
        platz = session.splitplatz(fahrt, nummer, zeit_ms)
        if abstand is None:
            # Noch niemand sonst hat eine Runde stehen - dann gibt es
            # nichts, wogegen zu messen waere. Der Platz steht trotzdem.
            feld.setText(f"—  (P{platz})")
            feld.setStyleSheet(f"color: {FARBE_BLASS.name()};")
            return
        farbe = FARBE_SCHNELLER if abstand <= 0 else FARBE_LANGSAMER
        feld.setText(f"{formatiere_rueckstand(abstand)}  (P{platz})")
        feld.setStyleSheet(f"color: {farbe.name()};")

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def fahrt(self) -> Fahrt | None:
        return self._fahrt

    @property
    def namensfeld(self) -> QLabel:
        return self._name

    @property
    def herkunftsfeld(self) -> QLabel:
        return self._herkunft

    @property
    def uhr(self) -> QLabel:
        return self._uhr

    @property
    def endabstand(self) -> QLabel:
        return self._endabstand

    @property
    def splitzeiten(self) -> list[QLabel]:
        return list(self._splitzeiten)

    @property
    def splitfelder(self) -> list[QLabel]:
        return list(self._splitwerte)

    @property
    def flaggenfeld(self) -> QLabel:
        return self._flagge
