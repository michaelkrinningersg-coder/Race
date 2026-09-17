"""Seite fuer die Statistiken (GDD 13).

"Rundenrekorde je Strecke und Liga in Tausendsteln. Karriere: Siege,
Podien, Pole-Positions, schnellste Runden, Gesamtpunkte je Liga und
Saison. Historie aller Saisons und Ligen."

Drei Ansichten in einer Seite, umschaltbar:

* **Rundenrekorde** - je Strecke die schnellste Runde jeder Liga
* **Bestenliste** - die Karrierezahlen aller Fahrer, nach einem Merkmal
  geordnet
* **Historie** - der Endstand einer Saison in einer Liga
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.statistik import Statistik
from rennmanager.kern.welt import Welt
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.konfiguration import Konfiguration

REKORDE = "rekorde"
BESTENLISTE = "bestenliste"
HISTORIE = "historie"

# Merkmale der Bestenliste - Schluessel in Karrierezahlen, Anzeigename.
MERKMALE = (
    ("siege", "Siege"),
    ("punkte", "Punkte"),
    ("podien", "Podien"),
    ("poles", "Pole-Positions"),
    ("schnellste_runden", "Schnellste Runden"),
    ("rennen", "Rennen"),
    ("ausfaelle", "Ausfaelle"),
)


class Statistikseite(QWidget):
    """Rundenrekorde, Karrierezahlen und Historie."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        statistik: Statistik,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        self._statistik = statistik

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())
        spalte.addWidget(self._baue_tabelle(), stretch=1)
        # Blendet die Filter aus, die zur Startansicht nicht gehoeren, und
        # fuellt die Tabelle.
        self._ansicht_gewechselt()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._ansicht = QComboBox()
        self._ansicht.addItem("Rundenrekorde je Strecke und Liga", REKORDE)
        self._ansicht.addItem("Bestenliste der Karriere", BESTENLISTE)
        self._ansicht.addItem("Historie aller Saisons", HISTORIE)
        self._ansicht.currentIndexChanged.connect(self._ansicht_gewechselt)

        # Je Ansicht ein eigener zweiter Filter.
        self._strecke = QComboBox()
        for eintrag in self._konfiguration.strecken:
            self._strecke.addItem(f"{eintrag['nummer']:>2}  {eintrag['name']}", eintrag["name"])
        self._strecke.currentIndexChanged.connect(self.aktualisiere)

        self._merkmal = QComboBox()
        for schluessel, name in MERKMALE:
            self._merkmal.addItem(name, schluessel)
        self._merkmal.currentIndexChanged.connect(self.aktualisiere)

        self._saison = QComboBox()
        self._saison.currentIndexChanged.connect(self.aktualisiere)

        self._hinweis = QLabel()

        zeile.addWidget(QLabel("Ansicht:"))
        zeile.addWidget(self._ansicht)
        zeile.addWidget(self._strecke)
        zeile.addWidget(self._merkmal)
        zeile.addWidget(self._saison)
        zeile.addWidget(self._hinweis, stretch=1)
        return zeile

    def _baue_tabelle(self) -> QWidget:
        self._kasten = QGroupBox("Statistik")
        spalte = QVBoxLayout(self._kasten)
        self._tabelle = QTreeWidget()
        self._tabelle.setRootIsDecorated(False)
        self._tabelle.setAlternatingRowColors(True)
        spalte.addWidget(self._tabelle)
        return self._kasten

    # -- Anzeige -----------------------------------------------------------
    def _ansicht_gewechselt(self, *_) -> None:
        art = self._ansicht.currentData()
        self._strecke.setVisible(art == REKORDE)
        self._merkmal.setVisible(art == BESTENLISTE)
        self._saison.setVisible(art == HISTORIE)
        self.aktualisiere()

    def aktualisiere(self, *_) -> None:
        """Liest die Statistik neu ein - nach jedem Rennwochenende noetig."""
        self._fuelle_saisons()
        art = self._ansicht.currentData()
        self._tabelle.clear()
        if art == REKORDE:
            self._zeige_rekorde()
        elif art == BESTENLISTE:
            self._zeige_bestenliste()
        else:
            self._zeige_historie()
        for spalte in range(self._tabelle.columnCount()):
            self._tabelle.resizeColumnToContents(spalte)

    def _fuelle_saisons(self) -> None:
        saisons = list(self._statistik.saisons)
        vorhanden = [self._saison.itemData(i) for i in range(self._saison.count())]
        if vorhanden == saisons:
            return
        gewaehlt = self._saison.currentData()
        self._saison.blockSignals(True)
        self._saison.clear()
        for jahr in saisons:
            self._saison.addItem(f"Saison {jahr}", jahr)
        if gewaehlt in saisons:
            self._saison.setCurrentIndex(saisons.index(gewaehlt))
        self._saison.blockSignals(False)

    def _zeige_rekorde(self) -> None:
        strecke = self._strecke.currentData()
        self._kasten.setTitle(f"Rundenrekorde - {strecke}")
        self._tabelle.setColumnCount(6)
        self._tabelle.setHeaderLabels(
            ["Liga", "Zeit", "Rueckstand", "Fahrer", "Saison", "Rennen"]
        )

        rekorde = self._statistik.rekorde_je_strecke(strecke)
        if not rekorde:
            self._hinweis.setText("Noch keine Runde gefahren.")
            return
        self._hinweis.setText(f"{len(self._statistik.rekorde)} Rekorde insgesamt")

        bestzeit = rekorde[0].zeit_ms
        for rekord in rekorde:
            fahrer = self._welt.fahrer[rekord.fahrer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    f"{rekord.liga} - {self._konfiguration.ligenname(rekord.liga)}",
                    formatiere_dauer(rekord.zeit_ms),
                    "" if rekord.zeit_ms == bestzeit
                    else formatiere_rueckstand(rekord.zeit_ms - bestzeit),
                    fahrer.name,
                    str(rekord.saison),
                    str(rekord.rennen),
                ],
            )
            self._faerbe(zeile, fahrer)

    def _zeige_bestenliste(self) -> None:
        merkmal = self._merkmal.currentData()
        name = dict(MERKMALE)[merkmal]
        self._kasten.setTitle(f"Bestenliste nach {name}")
        self._tabelle.setColumnCount(10)
        self._tabelle.setHeaderLabels(
            [
                "#",
                "Fahrer",
                "Liga",
                "Rennen",
                "Siege",
                "Podien",
                "Poles",
                "SR",
                "DNF",
                "Punkte",
            ]
        )

        beste = self._statistik.bestenliste(merkmal, anzahl=50)
        if not beste:
            self._hinweis.setText("Noch kein Rennen gefahren.")
            return
        self._hinweis.setText(f"{len(self._statistik.karriere)} Fahrer gewertet")

        for platz, zahlen in enumerate(beste, start=1):
            fahrer = self._welt.fahrer[zahlen.fahrer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    str(platz),
                    fahrer.name,
                    str(fahrer.liga),
                    str(zahlen.rennen),
                    str(zahlen.siege),
                    str(zahlen.podien),
                    str(zahlen.poles),
                    str(zahlen.schnellste_runden),
                    str(zahlen.ausfaelle),
                    str(zahlen.punkte),
                ],
            )
            self._faerbe(zeile, fahrer)

    def _zeige_historie(self) -> None:
        jahr = self._saison.currentData()
        self._tabelle.setColumnCount(4)
        self._tabelle.setHeaderLabels(["Liga", "Meister", "Punkte", "Zweiter"])
        if jahr is None:
            self._kasten.setTitle("Historie")
            self._hinweis.setText("Noch keine Saison abgeschlossen.")
            return

        self._kasten.setTitle(f"Historie - Saison {jahr}")
        self._hinweis.setText(f"{len(self._statistik.saisons)} abgeschlossene Saisons")
        for liga in range(1, self._konfiguration.wert("ligen", "anzahl") + 1):
            abschluss = self._statistik.abschluss(jahr, liga)
            if abschluss is None:
                continue
            meister = self._welt.fahrer[abschluss.meister]
            zweiter = (
                self._welt.fahrer[abschluss.reihenfolge[1]].name
                if len(abschluss.reihenfolge) > 1
                else ""
            )
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    f"{liga} - {self._konfiguration.ligenname(liga)}",
                    meister.name,
                    str(abschluss.punkte[0]),
                    zweiter,
                ],
            )
            self._faerbe(zeile, meister)

    def _faerbe(self, zeile: QTreeWidgetItem, fahrer) -> None:
        zeile.setForeground(0, QColor(self._welt.team_von(fahrer).farbe))
        zeile.setData(0, Qt.UserRole, fahrer.nummer)
        if fahrer.ist_spieler:
            schrift = zeile.font(1)
            schrift.setBold(True)
            for spalte in range(self._tabelle.columnCount()):
                zeile.setFont(spalte, schrift)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def tabelle(self) -> QTreeWidget:
        return self._tabelle

    @property
    def ansicht(self) -> QComboBox:
        return self._ansicht

    @property
    def streckenauswahl(self) -> QComboBox:
        return self._strecke

    @property
    def merkmalauswahl(self) -> QComboBox:
        return self._merkmal
