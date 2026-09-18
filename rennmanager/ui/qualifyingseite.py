"""Seite fuer das Qualifying (GDD 4).

Zeigt die Fahrten in der Reihenfolge, in der sie stattfinden, und sortiert
sie live ins Ranking ein. Die Sektorzeiten stehen mit Vorzeichen gegen die
jeweils aktuelle Bestzeit: schneller in Gruen, langsamer in Rot.

Die Seite rechnet nichts: Sie bekommt eine gefahrene Session von aussen -
vom gefuehrten Rennwochenende (Punkt 12) - und macht daraus eine
Uebertragung.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.qualifying import Qualifying
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import verbinde_fahrerkarte

FARBE_SCHNELLER = QColor("#2e7d32")
FARBE_LANGSAMER = QColor("#c62828")


class Qualifyingseite(QWidget):
    """Zeigt ein gefahrenes Qualifying mit Live-Einsortierung."""

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

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_fortschritt())

        inhalt = QHBoxLayout()
        inhalt.addWidget(self._baue_rangliste(), stretch=3)
        inhalt.addWidget(self._baue_seitenspalte(), stretch=2)
        spalte.addLayout(inhalt, stretch=1)

    # -- Aufbau ------------------------------------------------------------
    def _baue_fortschritt(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._regler = QSlider(Qt.Horizontal)
        self._regler.setEnabled(False)
        self._regler.valueChanged.connect(self._zeichne)
        self._stand = QLabel("Noch kein Qualifying gefahren")

        self._alle = QPushButton("Alle Fahrten")
        self._alle.setEnabled(False)
        self._alle.clicked.connect(lambda: self._regler.setValue(self._regler.maximum()))

        zeile.addWidget(QLabel("Gefahrene Laeufe:"))
        zeile.addWidget(self._regler, stretch=1)
        zeile.addWidget(self._stand)
        zeile.addWidget(self._alle)
        return zeile

    def _baue_rangliste(self) -> QWidget:
        kasten = QGroupBox("Ranking")
        spalte = QVBoxLayout(kasten)
        self._rangliste = QTreeWidget()
        self._rangliste.setHeaderLabels(
            ["Pos", "Auto", "Zeit", "Rueckstand", "S1", "S2", "S3", "S4", "Wetter", "Form"]
        )
        self._rangliste.setRootIsDecorated(False)
        self._rangliste.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._rangliste, self.fahrerkarte_gewuenscht.emit)
        spalte.addWidget(self._rangliste)
        return kasten

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
        kasten = QGroupBox("Startaufstellung fuers Rennen")
        kasten_spalte = QVBoxLayout(kasten)
        kasten_spalte.addWidget(self._aufstellung)
        spalte.addWidget(kasten, stretch=1)
        return seite

    # -- Session uebernehmen -----------------------------------------------
    def zeige_session(self, session: Qualifying) -> None:
        """Uebernimmt ein gefahrenes Qualifying und spielt es ab."""
        self._session = session
        self._regler.setRange(0, len(session.fahrten))
        self._regler.setEnabled(True)
        self._alle.setEnabled(True)
        self._fuelle_wetter()
        self._fuelle_aufstellung()
        self._regler.setValue(len(session.fahrten))
        self._zeichne()

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self, *_) -> None:
        if self._session is None:
            return
        anzahl = self._regler.value()
        stand = self._session.stand_nach(anzahl)
        self._stand.setText(f"{anzahl} von {len(self._session.fahrten)}")

        self._rangliste.clear()
        if not stand:
            return
        bestzeit = stand[0].zeit_ms
        beste_sektoren = [
            min(fahrt.sektoren_ms[nummer] for fahrt in stand)
            for nummer in range(len(stand[0].sektoren_ms))
        ]

        for platz, fahrt in enumerate(stand, start=1):
            teilnehmer = self._session.teilnehmer[fahrt.teilnehmer]
            spalten = [
                str(platz),
                teilnehmer.kuerzel,
                formatiere_dauer(fahrt.zeit_ms),
                "" if platz == 1 else formatiere_rueckstand(fahrt.zeit_ms - bestzeit),
            ]
            spalten += [formatiere_dauer(wert) for wert in fahrt.sektoren_ms]
            spalten += [fahrt.zustand, f"{(fahrt.tagesform - 1) * 100:+.1f}%"]

            zeile = QTreeWidgetItem(self._rangliste, spalten)
            zeile.setForeground(1, QColor(teilnehmer.farbe))
            zeile.setData(0, Qt.UserRole, teilnehmer.nummer)
            # Sektorzeiten mit +/- in Gruen und Rot gegen die Bestzeit (GDD 4).
            for nummer, wert in enumerate(fahrt.sektoren_ms):
                spalte = 4 + nummer
                if wert <= beste_sektoren[nummer]:
                    zeile.setForeground(spalte, FARBE_SCHNELLER)
                else:
                    zeile.setForeground(spalte, FARBE_LANGSAMER)
                    zeile.setText(
                        spalte,
                        f"{formatiere_dauer(wert)} "
                        f"{formatiere_rueckstand(wert - beste_sektoren[nummer])}",
                    )
            if teilnehmer.ist_spieler:
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(self._rangliste.columnCount()):
                    zeile.setFont(spalte, schrift)

        for spalte in range(self._rangliste.columnCount()):
            self._rangliste.resizeColumnToContents(spalte)

    def _fuelle_wetter(self) -> None:
        self._leere(self._wetterfeld)
        verlauf = self._session.wetter
        self._wetterfeld.addRow("Start:", QLabel(verlauf.startzustand))
        self._wetterfeld.addRow("Wechsel:", QLabel(str(verlauf.wechsel)))
        self._wetterfeld.addRow("Verlauf:", QLabel(" → ".join(verlauf.zustaende)))
        self._wetterfeld.addRow(
            "Dauer der Session:", QLabel(formatiere_dauer(self._session.dauer_ms))
        )

    def _fuelle_aufstellung(self) -> None:
        self._aufstellung.clear()
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
