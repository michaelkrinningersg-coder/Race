"""Seite fuer die Welt: Ligen, Teams und Fahrer (GDD 12)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.welt import Welt
from rennmanager.konfiguration import Konfiguration

SAISONSTART = None  # wird aus der Konfiguration gefuellt


class Weltseite(QWidget):
    """Zeigt die 20 Ligen mit ihren 30 Fahrern und die Teams."""

    def __init__(
        self, konfiguration: Konfiguration, welt: Welt, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_fahrerliste())
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._zeige_liga()

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
        self._liga.currentIndexChanged.connect(self._zeige_liga)

        zeile.addWidget(QLabel("Liga:"))
        zeile.addWidget(self._liga)
        zeile.addWidget(
            QLabel(
                f"{len(self._welt.fahrer)} Fahrer · {len(self._welt.teams)} Teams · "
                f"Seed {self._welt.seed}"
            )
        )
        zeile.addStretch(1)
        return zeile

    def _baue_fahrerliste(self) -> QWidget:
        kasten = QGroupBox("Fahrer")
        spalte = QVBoxLayout(kasten)
        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(
            ["#", "Kuerzel", "Fahrer", "Land", "Alter", "Team", "Hersteller", "Staerke"]
        )
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        self._liste.currentItemChanged.connect(self._zeige_fahrer)
        spalte.addWidget(self._liste)
        return kasten

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._steckbrief = QFormLayout()
        kasten = QGroupBox("Fahrer und Team")
        kasten.setLayout(self._steckbrief)
        spalte.addWidget(kasten)

        self._profil = QTreeWidget()
        self._profil.setHeaderLabels(["Bereich", "Wert"])
        self._profil.setRootIsDecorated(False)
        self._profil.setAlternatingRowColors(True)
        profilkasten = QGroupBox("Profil")
        profil_spalte = QVBoxLayout(profilkasten)
        profil_spalte.addWidget(self._profil)
        spalte.addWidget(profilkasten, stretch=1)
        return seite

    # -- Inhalt ------------------------------------------------------------
    def _zeige_liga(self, *_) -> None:
        self._liste.clear()
        liga = self._liga.currentData()
        for platz, fahrer in enumerate(self._welt.liga(liga), start=1):
            team = self._welt.team_von(fahrer)
            staerke = sum(fahrer.auto.werte.values()) / len(fahrer.auto.werte)
            zeile = QTreeWidgetItem(
                self._liste,
                [
                    str(platz),
                    fahrer.kuerzel,
                    fahrer.name,
                    fahrer.land,
                    str(fahrer.alter_am(self._saisonstart())),
                    team.name,
                    team.hersteller,
                    f"{staerke:,.0f}".replace(",", "."),
                ],
            )
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            zeile.setForeground(1, QColor(team.farbe))
            if fahrer.ist_spieler:
                schrift = zeile.font(2)
                schrift.setBold(True)
                for spalte in range(self._liste.columnCount()):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._liste.columnCount()):
            self._liste.resizeColumnToContents(spalte)
        if self._liste.topLevelItemCount():
            self._liste.setCurrentItem(self._liste.topLevelItem(0))

    def _saisonstart(self):
        import datetime as dt

        return dt.date(
            2026,
            self._konfiguration.wert("kalender", "saisonstart_monat"),
            self._konfiguration.wert("kalender", "saisonstart_tag"),
        )

    def _zeige_fahrer(self, jetzt, _davor=None) -> None:
        self._leere(self._steckbrief)
        self._profil.clear()
        if jetzt is None:
            return

        fahrer = self._welt.fahrer[jetzt.data(0, Qt.UserRole)]
        team = self._welt.team_von(fahrer)
        kollegen = ", ".join(f.name for f in self._welt.teamkollegen(fahrer))

        for beschriftung, wert in (
            ("Fahrer:", fahrer.name),
            ("Land:", fahrer.land),
            ("Geboren:", fahrer.geburtstag.strftime("%d.%m.%Y")),
            ("Liga:", f"{fahrer.liga} - {self._konfiguration.ligenname(fahrer.liga)}"),
            ("Team:", f"{team.name} ({team.land})"),
            ("Hersteller:", team.hersteller),
            ("Teambudget:", f"{team.budget:,} €".replace(",", ".")),
            ("Teamkollegen:", kollegen),
        ):
            marke = QLabel(wert)
            marke.setWordWrap(True)
            self._steckbrief.addRow(beschriftung, marke)

        # Profil ueber die Wirkungsbereiche - daran sieht man, ob jemand
        # Regenspezialist oder Reifenschoner ist (GDD 12).
        from rennmanager.kern.auto import bereichswerte

        bezeichnung = self._konfiguration.wert("wirkungsmatrix", "bezeichnung")
        for bereich, wert in bereichswerte(self._konfiguration, fahrer.auto).items():
            QTreeWidgetItem(
                self._profil,
                [bezeichnung.get(bereich, bereich), f"{wert:,.0f}".replace(",", ".")],
            )
        for schluessel, wert in fahrer.auto.wetterwerte.items():
            QTreeWidgetItem(
                self._profil, [schluessel, f"{wert:,.0f}".replace(",", ".")]
            )
        for spalte in range(2):
            self._profil.resizeColumnToContents(spalte)

    @staticmethod
    def _leere(formular: QFormLayout) -> None:
        while formular.rowCount():
            formular.removeRow(0)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def liste(self) -> QTreeWidget:
        return self._liste

    @property
    def liga_auswahl(self) -> QComboBox:
        return self._liga
