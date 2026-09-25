"""Der Fahrer, auf den es im Qualifying gerade ankommt (Punkt 107).

Eine Box unter der Streckenkarte, die genau einen Fahrer zeigt: den, der
auf seiner gezeiteten Runde am weitesten ist. Sie traegt seinen Namen,
sein Team, seine Nation mit Flagge - und darunter die Zeiten.

Waehrend er faehrt, laeuft die Rundenzeit mit. An jedem Split faellt ein
Plus oder Minus: der Vorsprung oder Rueckstand seiner **Gesamtzeit** bis
zu dieser Stelle, gegen den, der gerade die Pole haelt. Gruen ist
schneller, rot langsamer, und in Klammern steht der Platz, den er an
dieser Stelle der Strecke belegt.

Drei Regeln, alle vom Auftraggeber:

* Das Plus/Minus bleibt **zwei Drittel** der Strecke bis zum naechsten
  Split stehen; das letzte Drittel davor ist frei, damit nie eine alte
  Zahl neben einer steht, die gleich faellt.
* Der letzte Split ist die Ziellinie und bleibt ueber den ganzen
  Nachlauf stehen - sonst waere ausgerechnet die fertige Rundenzeit
  nicht zu lesen.
* Die Box gehoert einem Fahrer noch **zehn Sekunden**, nachdem er die
  Linie ueberquert hat.

Gerechnet wird hier nichts: Die vier Zahlen kommen aus
``rennmanager.kern.qualifying`` (``blickpunkt``, ``splitabstand``,
``splitplatz``, ``split_steht_noch``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.qualifying import Qualifying
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.ui.flaggen import BREITE_PX, HOEHE_PX, flagge
from rennmanager.ui.tabellen import kurzname, schriftfarbe

# Dieselben Farben wie in der Zeitentafel - gruen schneller, rot
# langsamer. Eine eigene Palette hier haette dieselbe Aussage in anderen
# Farben erzaehlt.
FARBE_SCHNELLER = QColor("#2e7d32")
FARBE_LANGSAMER = QColor("#c62828")
FARBE_BLASS = QColor("#8b93a1")

# Die laufende Rundenzeit ist der groesste Text der Box - sie ist der
# Grund, warum man hinsieht.
SCHRIFT_UHR = 20
SCHRIFT_NAME = 12


class Blickpunktbox(QGroupBox):
    """Zeigt den Fahrer, der gerade auf der Runde ist."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Auf der Runde", parent)
        self._session: Qualifying | None = None
        self._namen: dict[int, str] = {}
        self._teams: dict[int, str] = {}

        spalte = QVBoxLayout(self)

        self._flagge = QLabel()
        self._flagge.setFixedSize(BREITE_PX, HOEHE_PX)
        self._name = QLabel("-")
        schrift = QFont(self.font().family(), SCHRIFT_NAME, QFont.Bold)
        self._name.setFont(schrift)
        self._herkunft = QLabel("")
        self._herkunft.setStyleSheet(f"color: {FARBE_BLASS.name()};")

        kopf = QGridLayout()
        kopf.setContentsMargins(0, 0, 0, 0)
        kopf.addWidget(self._flagge, 0, 0)
        kopf.addWidget(self._name, 0, 1)
        kopf.addWidget(self._herkunft, 1, 0, 1, 2)
        kopf.setColumnStretch(1, 1)
        spalte.addLayout(kopf)

        self._uhr = QLabel("-")
        self._uhr.setFont(QFont(self.font().family(), SCHRIFT_UHR, QFont.Bold))
        self._uhr.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spalte.addWidget(self._uhr)

        # Je Sektor eine Zeile: Beschriftung links, Plus/Minus rechts.
        self._splits = QGridLayout()
        self._splits.setContentsMargins(0, 0, 0, 0)
        self._splitmarken: list[QLabel] = []
        self._splitwerte: list[QLabel] = []
        spalte.addLayout(self._splits)
        spalte.addStretch(1)

    # -- Fuellen ------------------------------------------------------------
    def zeige_session(self, session: Qualifying | None) -> None:
        """Nimmt eine gefahrene Session entgegen und baut die Splitzeilen."""
        self._session = session
        for marke in self._splitmarken:
            marke.deleteLater()
        for wert in self._splitwerte:
            wert.deleteLater()
        self._splitmarken = []
        self._splitwerte = []
        if session is None:
            self._leere()
            return

        for nummer in range(len(session.strecke.sektoren)):
            marke = QLabel(f"S{nummer + 1}")
            marke.setStyleSheet(f"color: {FARBE_BLASS.name()};")
            wert = QLabel(" ")
            wert.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._splits.addWidget(marke, nummer, 0)
            self._splits.addWidget(wert, nummer, 1)
            self._splitmarken.append(marke)
            self._splitwerte.append(wert)
        self._splits.setColumnStretch(1, 1)
        self._leere()

    def zeige_namen(self, namen: dict[int, str], teams: dict[int, str]) -> None:
        """Fahrernamen und Rennstaelle je Fahrernummer.

        Der Teilnehmer traegt nur Kuerzel, Farbe und Nation - Name und
        Team kommen wie in der Zeitentafel von aussen, aus der Welt.
        """
        self._namen = {nummer: kurzname(name) for nummer, name in namen.items()}
        self._teams = dict(teams)

    def zeichne(self, zeit_ms: float) -> None:
        """Setzt die Box auf den Stand dieses Augenblicks."""
        session = self._session
        if session is None:
            return
        fahrt = session.blickpunkt(zeit_ms)
        if fahrt is None:
            self._leere()
            return

        teilnehmer = session.teilnehmer[fahrt.teilnehmer]
        self._setze_kopf(teilnehmer)
        self._setze_uhr(session, fahrt, zeit_ms)
        self._setze_splits(session, fahrt, zeit_ms)

    def _leere(self) -> None:
        self.setTitle("Auf der Runde")
        self._flagge.clear()
        self._name.setText("-")
        self._name.setStyleSheet("")
        self._herkunft.setText("Gerade ist niemand auf einer gezeiteten Runde.")
        self._uhr.setText("-")
        for wert in self._splitwerte:
            wert.setText(" ")

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

    def _setze_uhr(self, session: Qualifying, fahrt, zeit_ms: float) -> None:
        """Die laufende Rundenzeit; im Ziel die endgueltige.

        Die Ziellinie trennt beide Faelle vollstaendig: ``blickpunkt``
        gibt nur her, wer entweder auf der gezeiteten Runde ist oder sie
        gerade beendet hat.
        """
        if zeit_ms < fahrt.ziel_ms:
            self.setTitle("Auf der Runde")
            self._uhr.setText(formatiere_dauer(int(zeit_ms - fahrt.runde_ab_ms)))
            self._uhr.setStyleSheet("")
            return
        # Nachlauf: Die Runde steht, die Zeit auch.
        #
        # Gemessen wird gegen den, der in **diesem** Augenblick fuehrt -
        # nicht gegen ``session.pole``. Die Pole ist das Ergebnis am
        # Ende der Session; sie hier zu nehmen hiesse, waehrend der
        # Uebertragung auf ein Ergebnis zu schauen, das noch niemand
        # kennt. Wie die Splitfarben der Zeitentafel: Die Farbe faellt
        # im Moment des Ueberfahrens und dreht sich nicht mehr um.
        self.setTitle("Runde beendet")
        self._uhr.setText(formatiere_dauer(fahrt.zeit_ms))
        fuehrt = session.fuehrender_zu(zeit_ms, ohne=fahrt)
        schneller = fuehrt is None or fahrt.zeit_ms <= fuehrt.zeit_ms
        farbe = FARBE_SCHNELLER if schneller else FARBE_LANGSAMER
        self._uhr.setStyleSheet(f"color: {farbe.name()};")

    def _setze_splits(self, session: Qualifying, fahrt, zeit_ms: float) -> None:
        for nummer, wert in enumerate(self._splitwerte):
            if not session.split_steht_noch(fahrt, nummer, zeit_ms):
                wert.setText(" ")
                wert.setStyleSheet("")
                continue
            abstand = session.splitabstand(fahrt, nummer, zeit_ms)
            platz = session.splitplatz(fahrt, nummer, zeit_ms)
            if abstand is None:
                # Noch niemand sonst hat eine Runde stehen - dann gibt es
                # nichts, wogegen zu messen waere. Der Platz steht
                # trotzdem da.
                wert.setText(f"—  (P{platz})")
                wert.setStyleSheet(f"color: {FARBE_BLASS.name()};")
                continue
            farbe = FARBE_SCHNELLER if abstand < 0 else FARBE_LANGSAMER
            wert.setText(f"{formatiere_rueckstand(abstand)}  (P{platz})")
            wert.setStyleSheet(f"color: {farbe.name()};")

    # -- Zugriff fuer Tests -------------------------------------------------
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
    def splitfelder(self) -> list[QLabel]:
        return list(self._splitwerte)

    @property
    def flaggenfeld(self) -> QLabel:
        return self._flagge
