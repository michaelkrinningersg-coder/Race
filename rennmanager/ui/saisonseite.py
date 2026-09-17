"""Seite fuer die Saison: Wertung, Schnellsimulation, Auf- und Abstieg (GDD 13).

Links die Tabelle der gewaehlten Liga, rechts das Ergebnis des zuletzt
gefahrenen Rennwochenendes. Ueber die Knoepfe laeuft ein einzelnes
Wochenende oder gleich die ganze Saison; die Liga des Spielers kann dabei
wahlweise ausfuehrlich gefahren werden - dann dauert sie laenger, liefert
aber einen abspielbaren Rennverlauf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import saison as kern_saison
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern.saison import Saisonlauf, Wochenende
from rennmanager.kern.welt import Welt
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration

FARBE_AUFSTIEG = QColor("#2e7d32")
FARBE_ABSTIEG = QColor("#c62828")


class Saisonseite(QWidget):
    """Faehrt die Saison und zeigt Wertung sowie Auf- und Abstieg."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        seed: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        self._lauf = Saisonlauf(
            konfiguration,
            welt,
            Seedquelle(seed),
            strecken=kern_strecke.lade_alle(konfiguration),
        )
        self._letztes: Wochenende | None = None

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_tabelle())
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._aktualisiere()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._liga = QComboBox()
        for nummer in range(1, self._konfiguration.wert("ligen", "anzahl") + 1):
            self._liga.addItem(
                f"Liga {nummer} - {self._konfiguration.ligenname(nummer)}", nummer
            )
        spieler = self._welt.spieler
        if spieler is not None:
            self._liga.setCurrentIndex(spieler.liga - 1)
        self._liga.currentIndexChanged.connect(self._aktualisiere)

        self._ausfuehrlich = QCheckBox("Spielerliga ausfuehrlich")
        self._ausfuehrlich.setToolTip(
            "Die Liga des Spielers mit Qualifying und vollem Rennverlauf fahren - "
            "langsamer, dafuer abspielbar (GDD 15)."
        )
        self._ausfuehrlich.setEnabled(spieler is not None)

        self._ein_rennen = QPushButton("Rennwochenende")
        self._ein_rennen.clicked.connect(self._fahre_eines)
        self._ganze_saison = QPushButton("Restliche Saison")
        self._ganze_saison.clicked.connect(self._fahre_rest)

        self._stand = QLabel()

        zeile.addWidget(QLabel("Liga:"))
        zeile.addWidget(self._liga)
        zeile.addWidget(self._ausfuehrlich)
        zeile.addWidget(self._ein_rennen)
        zeile.addWidget(self._ganze_saison)
        zeile.addWidget(self._stand, stretch=1)
        return zeile

    def _baue_tabelle(self) -> QWidget:
        self._tabellenkasten = QGroupBox("Saisonwertung")
        spalte = QVBoxLayout(self._tabellenkasten)
        self._tabelle = QTreeWidget()
        self._tabelle.setHeaderLabels(
            ["#", "Fahrer", "Team", "Punkte", "Siege", "Podien", "Poles", "SR", "DNF"]
        )
        self._tabelle.setRootIsDecorated(False)
        self._tabelle.setAlternatingRowColors(True)
        spalte.addWidget(self._tabelle)
        return self._tabellenkasten

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._rennkasten = QGroupBox("Letztes Rennwochenende")
        rennspalte = QVBoxLayout(self._rennkasten)
        self._rennkopf = QLabel("Noch kein Rennen gefahren.")
        self._rennkopf.setWordWrap(True)
        rennspalte.addWidget(self._rennkopf)
        self._rennliste = QTreeWidget()
        self._rennliste.setHeaderLabels(["#", "Fahrer", "Quali", "Punkte"])
        self._rennliste.setRootIsDecorated(False)
        self._rennliste.setAlternatingRowColors(True)
        rennspalte.addWidget(self._rennliste)
        spalte.addWidget(self._rennkasten, stretch=1)

        self._wechselkasten = QGroupBox("Auf- und Abstieg")
        wechselspalte = QVBoxLayout(self._wechselkasten)
        self._wechselliste = QTreeWidget()
        self._wechselliste.setHeaderLabels(["Fahrer", "Von", "Nach"])
        self._wechselliste.setRootIsDecorated(False)
        self._wechselliste.setAlternatingRowColors(True)
        wechselspalte.addWidget(self._wechselliste)
        self._wechselkasten.setVisible(False)
        spalte.addWidget(self._wechselkasten, stretch=1)
        return seite

    # -- Fahren ------------------------------------------------------------
    def _ausfuehrliche_liga(self) -> int | None:
        spieler = self._welt.spieler
        if spieler is None or not self._ausfuehrlich.isChecked():
            return None
        return spieler.liga

    def _fahre_eines(self) -> None:
        self._fahre(alle=False)

    def _fahre_rest(self) -> None:
        self._fahre(alle=True)

    def _fahre(self, alle: bool) -> None:
        if self._lauf.ist_fertig:
            return
        for knopf in (self._ein_rennen, self._ganze_saison):
            knopf.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            while True:
                nummer = self._lauf.naechstes_rennen
                self._stand.setText(f"Rennen {nummer} von {self._lauf.rennen_je_saison} laeuft ...")
                QApplication.processEvents()
                self._letztes = self._lauf.fahre_rennen(self._ausfuehrliche_liga())
                if not alle or self._lauf.ist_fertig:
                    break
        finally:
            QApplication.restoreOverrideCursor()
            for knopf in (self._ein_rennen, self._ganze_saison):
                knopf.setEnabled(not self._lauf.ist_fertig)
        self._aktualisiere()

    # -- Anzeige -----------------------------------------------------------
    def _aktualisiere(self, *_) -> None:
        liga = self._liga.currentData()
        self._zeige_tabelle(liga)
        self._zeige_rennen(liga)
        self._zeige_wechsel()
        if self._lauf.ist_fertig:
            self._stand.setText(
                f"Saison {self._lauf.jahr} beendet - {self._lauf.gefahren} Rennen gefahren."
            )
        else:
            self._stand.setText(
                f"Rennen {self._lauf.gefahren} von {self._lauf.rennen_je_saison} gefahren; "
                f"als naechstes {self._lauf.strecke_zu(self._lauf.naechstes_rennen).name}."
            )

    def _zeige_tabelle(self, liga: int) -> None:
        self._tabelle.clear()
        self._tabellenkasten.setTitle(
            f"Saisonwertung {self._lauf.jahr} - Liga {liga} "
            f"({self._konfiguration.ligenname(liga)})"
        )
        aufsteiger = self._konfiguration.wert("auf_abstieg", "aufsteiger")
        absteiger = self._konfiguration.wert("auf_abstieg", "absteiger")
        stand = self._lauf.tabelle(liga).stand()
        for platz, eintrag in enumerate(stand, start=1):
            fahrer = self._welt.fahrer[eintrag.fahrer]
            team = self._welt.team_von(fahrer)
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    str(platz),
                    fahrer.name,
                    team.name,
                    str(eintrag.punkte),
                    str(eintrag.siege),
                    str(eintrag.podien),
                    str(eintrag.poles),
                    str(eintrag.schnellste_runden),
                    str(eintrag.ausfaelle),
                ],
            )
            zeile.setForeground(0, QColor(team.farbe))
            # Wer am Saisonende auf- oder absteigt, ist farbig markiert.
            if platz <= aufsteiger and liga > 1:
                zeile.setForeground(1, FARBE_AUFSTIEG)
            elif platz > len(stand) - absteiger and liga < len(self._lauf.tabellen):
                zeile.setForeground(1, FARBE_ABSTIEG)
            if fahrer.ist_spieler:
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(self._tabelle.columnCount()):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._tabelle.columnCount()):
            self._tabelle.resizeColumnToContents(spalte)

    def _zeige_rennen(self, liga: int) -> None:
        self._rennliste.clear()
        if self._letztes is None:
            self._rennkopf.setText("Noch kein Rennen gefahren.")
            return

        ergebnis = self._letztes.liga(liga)
        art = "ausfuehrlich" if ergebnis.ausfuehrlich else "Schnellmodus"
        self._rennkopf.setText(
            f"Rennen {self._letztes.nummer} - {self._letztes.strecke} ({art})<br>"
            f"Wetter: {', '.join(ergebnis.wetter)}<br>"
            f"Siegerzeit {formatiere_dauer(ergebnis.siegerzeit_ms)} · "
            f"schnellste Runde {formatiere_dauer(ergebnis.schnellste_runde_ms)} · "
            f"{ergebnis.ueberholmanoever} Ueberholmanoever · "
            f"{ergebnis.ausfaelle} Ausfaelle"
        )
        for e in ergebnis.ergebnisse:
            fahrer = self._welt.fahrer[e.fahrer]
            punkte = kern_wertung.punkte_fuer(self._konfiguration, e)
            zeile = QTreeWidgetItem(
                self._rennliste,
                [
                    "DNF" if e.ausgefallen else str(e.rennplatz),
                    fahrer.name + (" (SR)" if e.schnellste_runde else ""),
                    str(e.qualifyingplatz),
                    str(punkte),
                ],
            )
            zeile.setForeground(0, QColor(self._welt.team_von(fahrer).farbe))
            if fahrer.ist_spieler:
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(self._rennliste.columnCount()):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._rennliste.columnCount()):
            self._rennliste.resizeColumnToContents(spalte)

    def _zeige_wechsel(self) -> None:
        self._wechselliste.clear()
        if not self._lauf.ist_fertig:
            self._wechselkasten.setVisible(False)
            return
        self._wechselkasten.setVisible(True)
        try:
            wechsel = self._lauf.auf_und_abstieg()
        except kern_saison.SaisonFehler as fehler:  # pragma: no cover - Notfall
            QMessageBox.warning(self, "Auf- und Abstieg", str(fehler))
            return
        self._wechselkasten.setTitle(f"Auf- und Abstieg ({len(wechsel)} Wechsel)")
        for w in sorted(wechsel, key=lambda w: (w.von_liga, not w.ist_aufstieg)):
            fahrer = self._welt.fahrer[w.fahrer]
            zeile = QTreeWidgetItem(
                self._wechselliste,
                [fahrer.name, f"Liga {w.von_liga}", f"Liga {w.nach_liga}"],
            )
            zeile.setForeground(2, FARBE_AUFSTIEG if w.ist_aufstieg else FARBE_ABSTIEG)
        for spalte in range(self._wechselliste.columnCount()):
            self._wechselliste.resizeColumnToContents(spalte)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def lauf(self) -> Saisonlauf:
        return self._lauf

    @property
    def tabelle(self) -> QTreeWidget:
        return self._tabelle

    @property
    def rennliste(self) -> QTreeWidget:
        return self._rennliste

    @property
    def wechselliste(self) -> QTreeWidget:
        return self._wechselliste

    @property
    def liga_auswahl(self) -> QComboBox:
        return self._liga

    @property
    def knopf_rennwochenende(self) -> QPushButton:
        return self._ein_rennen
