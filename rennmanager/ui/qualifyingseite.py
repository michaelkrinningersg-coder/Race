"""Seite fuer das Qualifying (GDD 4).

Seit Punkt 85 ist das Qualifying eine **Uebertragung** wie das Rennen:
dieselbe Wiedergabeleiste, dieselben Zeitrafferstufen, nach dem Laden auf
Anfang. Die Uhr laeuft ueber die ganze Session, die Autos fahren
ueberlappend, und wer seine gezeitete Runde beendet, sortiert sich in dem
Moment ein, in dem er ueber die Linie kommt.

Vorher stand hier ein Regler "Gefahrene Laeufe": Man konnte die Session
laufweise durchblaettern, aber nicht zusehen. Der Unterschied ist, dass
man jetzt die Zeit mitlaufen sieht, waehrend einer auf der Runde ist.

Die Splits sind dreifarbig (Entscheidung des Auftraggebers):

* **Lila** haelt, wer den Sektor bis zu diesem Augenblick am schnellsten
  gefahren ist. Das ist Live-Stand und wandert weiter, sobald ihn jemand
  unterbietet.
* **Gruen** und **Rot** messen gegen den Fuehrenden - und zwar gegen
  den, der fuehrte, **als der Split fiel**. Wie im Fernsehen: Die Farbe
  friert im Moment des Ueberfahrens ein und dreht sich nicht mehr um,
  wenn spaeter jemand schneller ist.

Die Seite rechnet nichts: Sie bekommt eine gefahrene Session von aussen -
vom gefuehrten Rennwochenende (Punkt 12) - und macht daraus ein Bild.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.qualifying import Lage, Qualifying
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import verbinde_fahrerkarte

FARBE_SCHNELLER = QColor("#2e7d32")
FARBE_LANGSAMER = QColor("#c62828")
# Punkt 82: dasselbe Lila wie fuer den schnellsten Sektor im Rennen.
FARBE_BESTER = QColor("#8e24aa")

SPALTE_POS = 0
SPALTE_AUTO = 1
SPALTE_ZEIT = 2
SPALTE_RUECKSTAND = 3
SPALTE_SEKTOR_AB = 4


class Qualifyingseite(QWidget):
    """Spielt ein gefahrenes Qualifying als Zeitenmonitor ab."""

    # Doppelklick auf eine Zeile: Das Fenster oeffnet die Fahrerkarte.
    fahrerkarte_gewuenscht = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._session: Qualifying | None = None
        self._zeit_ms = 0.0
        self._laeuft = False
        # Punkt 62: Die Tabelle wird seltener nachgezogen als die Uhr -
        # sonst springen dreissig Zeilen schneller um, als sie zu lesen
        # sind. Die Uhr oben laeuft trotzdem in jedem Takt weiter.
        self._anzeige_takt_ms = konfiguration.wert("zeitraffer", "anzeige_takt_ms")
        self._letzte_tabelle_ms: float | None = None

        self._takt_ms = konfiguration.wert("zeitraffer", "takt_ms")
        self._uhr = QTimer(self)
        self._uhr.setInterval(self._takt_ms)
        self._uhr.timeout.connect(self._takt)

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_wiedergabe())

        inhalt = QHBoxLayout()
        inhalt.addWidget(self._baue_rangliste(), stretch=3)
        inhalt.addWidget(self._baue_seitenspalte(), stretch=2)
        spalte.addLayout(inhalt, stretch=1)

    # -- Aufbau ------------------------------------------------------------
    def _baue_wiedergabe(self) -> QHBoxLayout:
        """Dieselbe Leiste wie im Rennen - Wunsch des Auftraggebers."""
        zeile = QHBoxLayout()

        self._abspielen = QPushButton("Start")
        self._abspielen.setEnabled(False)
        self._abspielen.clicked.connect(self._umschalten)

        self._zurueck = QPushButton("Anfang")
        self._zurueck.setEnabled(False)
        self._zurueck.clicked.connect(lambda: self._springe(0))

        self._raffer = QComboBox()
        for stufe in self._konfiguration.wert("zeitraffer", "stufen"):
            self._raffer.addItem(f"{stufe}x", stufe)

        self._sofort = QPushButton("Sofortergebnis")
        self._sofort.setEnabled(False)
        self._sofort.clicked.connect(self._zum_ende)

        self._uhrzeit = QLabel("0:00.000")
        self._stand = QLabel("Noch kein Qualifying gefahren")
        self._fortschritt = QProgressBar()
        self._fortschritt.setTextVisible(False)

        zeile.addWidget(self._abspielen)
        zeile.addWidget(self._zurueck)
        zeile.addWidget(QLabel("Zeitraffer:"))
        zeile.addWidget(self._raffer)
        zeile.addWidget(self._sofort)
        zeile.addWidget(self._uhrzeit)
        zeile.addWidget(self._stand)
        zeile.addWidget(self._fortschritt, stretch=1)
        return zeile

    def _baue_rangliste(self) -> QWidget:
        kasten = QGroupBox("Zeitenmonitor")
        spalte = QVBoxLayout(kasten)
        self._rangliste = QTreeWidget()
        self._rangliste.setHeaderLabels(self._kopfzeilen(4))
        self._rangliste.setRootIsDecorated(False)
        self._rangliste.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._rangliste, self.fahrerkarte_gewuenscht.emit)
        spalte.addWidget(self._rangliste)
        return kasten

    @staticmethod
    def _kopfzeilen(sektoren: int) -> list[str]:
        kopf = ["Pos", "Auto", "Zeit", "Rueckstand"]
        kopf += [f"S{nummer + 1}" for nummer in range(sektoren)]
        return kopf + ["Lage", "Wetter", "Form"]

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._wetterfeld = QFormLayout()
        wetterkasten = QGroupBox("Wetter der Session")
        wetterkasten.setLayout(self._wetterfeld)
        spalte.addWidget(wetterkasten)

        self._aufstellung = QTreeWidget()
        self._aufstellung.setHeaderLabels(["Startplatz", "Auto", "Zeit"])
        self._aufstellung.setRootIsDecorated(False)
        self._aufstellung.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._aufstellung, self.fahrerkarte_gewuenscht.emit)
        # Entscheidung des Auftraggebers: Die Aufstellung fuellt sich erst
        # am Ende. Vorher stuende dort das Ergebnis, auf das die
        # Uebertragung gerade zulaeuft.
        self._aufstellungskasten = QGroupBox("Startaufstellung fuers Rennen")
        kasten_spalte = QVBoxLayout(self._aufstellungskasten)
        kasten_spalte.addWidget(self._aufstellung)
        spalte.addWidget(self._aufstellungskasten, stretch=1)
        return seite

    # -- Session uebernehmen -----------------------------------------------
    def zeige_session(self, session: Qualifying) -> None:
        """Uebernimmt ein gefahrenes Qualifying und stellt es auf Anfang."""
        self._session = session
        self._halte_an()
        sektoren = len(session.fahrten[0].sektoren_ms) if session.fahrten else 4
        self._rangliste.setHeaderLabels(self._kopfzeilen(sektoren))
        self._fortschritt.setRange(0, max(session.dauer_ms, 1))
        for knopf in (self._abspielen, self._zurueck, self._sofort):
            knopf.setEnabled(True)
        self._waehle_zeitraffer()
        self._fuelle_wetter()
        self._leere_aufstellung()
        self._springe(0)

    def _waehle_zeitraffer(self) -> None:
        """Dieselbe Startstufe wie im Rennen (Punkt 81): Echtzeit."""
        stufen = self._konfiguration.wert("zeitraffer", "stufen")
        start = self._konfiguration.wert("zeitraffer", "start_stufe")
        self._raffer.setCurrentIndex(stufen.index(start) if start in stufen else 0)

    # -- Wiedergabe ---------------------------------------------------------
    def _umschalten(self) -> None:
        if self._laeuft:
            self._halte_an()
            return
        self._laeuft = True
        self._abspielen.setText("Pause")
        self._uhr.start()

    def _halte_an(self) -> None:
        self._laeuft = False
        self._uhr.stop()
        self._abspielen.setText("Start")

    def _springe(self, zeit_ms: float) -> None:
        self._zeit_ms = zeit_ms
        # Ein Sprung soll sofort zu sehen sein, nicht erst im naechsten Takt.
        self._letzte_tabelle_ms = None
        self._zeichne()

    def _zum_ende(self) -> None:
        """GDD 4: Sofortergebnis."""
        if self._session is not None:
            self._halte_an()
            self._springe(self._session.dauer_ms)

    def _takt(self) -> None:
        if self._session is None:
            return
        self._zeit_ms += self._takt_ms * self._raffer.currentData()
        if self._zeit_ms >= self._session.dauer_ms:
            self._zeit_ms = self._session.dauer_ms
            self._halte_an()
            self._letzte_tabelle_ms = None
        self._zeichne()

    def _tabelle_faellig(self, zeit: float) -> bool:
        """Gemessen in Sessionzeit, nicht in Echtzeit (wie im Rennen)."""
        davor = self._letzte_tabelle_ms
        if davor is None or abs(zeit - davor) >= self._anzeige_takt_ms:
            self._letzte_tabelle_ms = zeit
            return True
        return False

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self) -> None:
        if self._session is None:
            return
        zeit = self._zeit_ms
        self._uhrzeit.setText(formatiere_dauer(int(zeit)))
        self._fortschritt.setValue(int(zeit))
        if not self._tabelle_faellig(zeit):
            return

        session = self._session
        stand = session.lage_zu(zeit)
        fertig = [s for s in stand if s.ist_fertig]
        self._stand.setText(f"{len(fertig)} von {len(session.fahrten)} Runden gefahren")
        bestzeit = fertig[0].zeit_ms if fertig else None
        lila = session.beste_splits_zu(zeit)

        self._rangliste.clear()
        # Die Position gilt nur fuer stehende Runden - wer noch faehrt,
        # hat noch keine. lage_zu() liefert die Fertigen zuerst, der
        # Zaehler laeuft also einfach mit.
        platz = 0
        for zeile in stand:
            if zeile.ist_fertig:
                platz += 1
            self._fuelle_zeile(zeile, platz if zeile.ist_fertig else None, bestzeit, lila)
        for spalte in range(self._rangliste.columnCount()):
            self._rangliste.resizeColumnToContents(spalte)

        # Die Aufstellung steht erst, wenn der Letzte durch ist.
        if len(fertig) == len(session.fahrten):
            self._fuelle_aufstellung()
        else:
            self._leere_aufstellung()

    def _fuelle_zeile(self, stand, platz: int | None, bestzeit: int | None, lila) -> None:
        session = self._session
        fahrt = stand.fahrt
        teilnehmer = session.teilnehmer[fahrt.teilnehmer]
        unterwegs = stand.lage is not Lage.WARTET

        spalten = [
            str(platz) if platz is not None else "",
            teilnehmer.kuerzel,
            formatiere_dauer(stand.zeit_ms) if stand.zeit_ms is not None else "",
            (
                formatiere_rueckstand(stand.zeit_ms - bestzeit)
                if stand.ist_fertig and bestzeit is not None and stand.zeit_ms > bestzeit
                else ""
            ),
        ]
        spalten += ["" for _ in fahrt.sektoren_ms]
        spalten += [
            stand.lage.bezeichnung,
            fahrt.zustand if unterwegs else "",
            f"{(fahrt.tagesform - 1) * 100:+.1f}%" if unterwegs else "",
        ]

        zeile = QTreeWidgetItem(self._rangliste, spalten)
        zeile.setForeground(SPALTE_AUTO, QColor(teilnehmer.farbe))
        zeile.setData(SPALTE_POS, Qt.UserRole, teilnehmer.nummer)
        self._faerbe_splits(zeile, stand, lila)

        # Eine laufende Runde ist keine Zeit, sondern eine Behauptung -
        # deshalb steht sie kursiv da, bis sie im Ziel steht.
        if stand.lage is Lage.SCHNELLE_RUNDE:
            schrift = zeile.font(SPALTE_ZEIT)
            schrift.setItalic(True)
            zeile.setFont(SPALTE_ZEIT, schrift)
        if teilnehmer.ist_spieler:
            schrift = zeile.font(SPALTE_AUTO)
            schrift.setBold(True)
            for spalte in range(self._rangliste.columnCount()):
                zeile.setFont(spalte, schrift)

    def _faerbe_splits(self, zeile: QTreeWidgetItem, stand, lila) -> None:
        """Traegt die gesetzten Splits ein und faerbt sie."""
        fahrt = stand.fahrt
        for nummer in range(stand.sektoren):
            spalte = SPALTE_SEKTOR_AB + nummer
            wert = fahrt.sektoren_ms[nummer]
            zeile.setText(spalte, formatiere_dauer(wert))

            if nummer < len(lila) and lila[nummer] == fahrt.teilnehmer:
                zeile.setForeground(spalte, FARBE_BESTER)
                continue
            abstand = self._session.splitvergleich(fahrt, nummer)
            if abstand is None:
                continue
            zeile.setForeground(
                spalte, FARBE_LANGSAMER if abstand > 0 else FARBE_SCHNELLER
            )
            zeile.setText(
                spalte, f"{formatiere_dauer(wert)} {formatiere_rueckstand(abstand)}"
            )

    def _fuelle_wetter(self) -> None:
        self._leere(self._wetterfeld)
        verlauf = self._session.wetter
        self._wetterfeld.addRow("Start:", QLabel(verlauf.startzustand))
        self._wetterfeld.addRow("Wechsel:", QLabel(str(verlauf.wechsel)))
        self._wetterfeld.addRow("Verlauf:", QLabel(" → ".join(verlauf.zustaende)))
        self._wetterfeld.addRow(
            "Dauer der Session:", QLabel(formatiere_dauer(self._session.dauer_ms))
        )

    def _leere_aufstellung(self) -> None:
        if self._aufstellung.topLevelItemCount():
            self._aufstellung.clear()
        self._aufstellungskasten.setTitle(
            "Startaufstellung fuers Rennen (steht nach der letzten Runde)"
        )

    def _fuelle_aufstellung(self) -> None:
        self._aufstellungskasten.setTitle("Startaufstellung fuers Rennen")
        if self._aufstellung.topLevelItemCount():
            return
        for platz, i in enumerate(self._session.aufstellung, start=1):
            fahrt = next(f for f in self._session.fahrten if f.teilnehmer == i)
            teilnehmer = self._session.teilnehmer[i]
            zeile = QTreeWidgetItem(
                self._aufstellung,
                [str(platz), teilnehmer.kuerzel, formatiere_dauer(fahrt.zeit_ms)],
            )
            zeile.setForeground(1, QColor(teilnehmer.farbe))
            zeile.setData(0, Qt.UserRole, teilnehmer.nummer)
        for spalte in range(3):
            self._aufstellung.resizeColumnToContents(spalte)

    @staticmethod
    def _leere(formular: QFormLayout) -> None:
        while formular.rowCount():
            formular.removeRow(0)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def session(self) -> Qualifying | None:
        return self._session

    @property
    def zeit_ms(self) -> float:
        return self._zeit_ms

    @property
    def laeuft(self) -> bool:
        return self._laeuft
