"""Seite fuer die Sponsoren (GDD 10).

Links die sechs Plaetze mit ihrem Stand - belegt oder frei -, rechts alle
Angebote fuer den gewaehlten Platz. Die Spalten lassen sich durch einen
Klick auf die Ueberschrift sortieren; Zahlen werden dabei als Zahlen
verglichen und nicht als Text.

GDD 10: "Sechs Plaetze mit je 3 bis 10 Angeboten, 3 bis 10 Wochen gueltig,
Laufzeit 3 bis 25 Rennen." Ein Platz traegt hoechstens einen Vertrag.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import sponsoren as kern_sponsoren
from rennmanager.kern.karriere import Karriere
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import SortierbareZeile as Zeile

FARBE_BELEGT = QColor("#2e7d32")
FARBE_FREI = QColor("#8b93a1")


def euro(betrag: float) -> str:
    return f"{betrag:,.0f} €".replace(",", ".")


class Sponsorenseite(QWidget):
    """Die sechs Plaetze und die Angebote dazu (GDD 10)."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        karriere: Karriere,
        seedquelle: Seedquelle,
        popularitaet=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._karriere = karriere
        self._seedquelle = seedquelle
        # Punkt 5: Wie bekannt der Spieler ist, bewegt die Angebote.
        self._popularitaet = popularitaet
        self._angebote: dict[str, tuple[kern_sponsoren.Angebot, ...]] = {}

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_plaetze())
        teiler.addWidget(self._baue_angebote())
        teiler.setStretchFactor(0, 2)
        teiler.setStretchFactor(1, 3)
        spalte.addWidget(teiler, stretch=1)

        self.wuerfle_angebote()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._hinweis = QLabel()
        self._hinweis.setWordWrap(True)
        zeile.addWidget(self._hinweis, stretch=1)
        return zeile

    def _baue_plaetze(self) -> QWidget:
        self._platzkasten = QGroupBox("Plaetze")
        spalte = QVBoxLayout(self._platzkasten)
        self._plaetze = QTreeWidget()
        self._plaetze.setHeaderLabels(
            ["Platz", "Stand", "Sponsor", "Je Rennen", "Rest", "Angebote"]
        )
        self._plaetze.setRootIsDecorated(False)
        self._plaetze.setAlternatingRowColors(True)
        self._plaetze.setSortingEnabled(True)
        self._plaetze.currentItemChanged.connect(self._zeige_angebote)
        spalte.addWidget(self._plaetze)

        self._kuendigen = QLabel(
            "Ein laufender Vertrag blockiert den Platz, bis er auslaeuft (GDD 10)."
        )
        self._kuendigen.setWordWrap(True)
        spalte.addWidget(self._kuendigen)
        return self._platzkasten

    def _baue_angebote(self) -> QWidget:
        self._angebotskasten = QGroupBox("Angebote")
        spalte = QVBoxLayout(self._angebotskasten)
        self._liste = QTreeWidget()
        # Die drei Praemien kommen auf den Grundbetrag obendrauf (GDD 10);
        # das Plus im Kopf sagt es, damit niemand sie fuer Gesamtbetraege
        # haelt - bei praemie_sieg = 1,00 sind Grundbetrag und Siegpraemie
        # gleich gross.
        self._liste.setHeaderLabels(
            [
                "Sponsor",
                "Je Rennen",
                "+ Sieg",
                "+ Top 3",
                "+ Top 10",
                "Sieg gesamt",
                "Laufzeit",
                "Stand",
            ]
        )
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        self._liste.setSortingEnabled(True)
        spalte.addWidget(self._liste)

        self._unterschreiben = QPushButton("Angebot annehmen")
        self._unterschreiben.clicked.connect(self._unterschreibe)
        spalte.addWidget(self._unterschreiben)
        return self._angebotskasten

    # -- Inhalt ------------------------------------------------------------
    def wuerfle_angebote(self) -> None:
        """Zieht die Angebote der laufenden Woche (GDD 10)."""
        woche = self._karriere.heute.isocalendar().week
        faktor = (
            self._popularitaet.faktor(self._karriere.fahrernummer)
            if self._popularitaet is not None
            else 1.0
        )
        self._angebote = kern_sponsoren.wuerfle_angebote(
            self._konfiguration, self._karriere.liga, woche, self._seedquelle, faktor
        )
        self.zeichne()

    def zeichne(self) -> None:
        """Baut Plaetze und Angebote neu auf."""
        gewaehlt = self._gewaehlter_platz()
        self._plaetze.setSortingEnabled(False)
        self._plaetze.clear()

        bezeichnungen = self._konfiguration.wert("sponsoren", "bezeichnung")
        belegt = 0
        for platz in kern_sponsoren.plaetze(self._konfiguration):
            vertrag = self._karriere.vertraege.get(platz)
            angebote = self._angebote.get(platz, ())
            zeile = Zeile(
                self._plaetze,
                [
                    bezeichnungen.get(platz, platz),
                    "belegt" if vertrag else "frei",
                    vertrag.angebot.name if vertrag else "",
                    euro(vertrag.angebot.grundbetrag) if vertrag else "",
                    f"{vertrag.verbleibende_rennen} Rennen" if vertrag else "",
                    str(len(angebote)),
                ],
            )
            zeile.setData(0, Qt.UserRole, platz)
            zeile.setze_sortierwert(3, vertrag.angebot.grundbetrag if vertrag else 0)
            zeile.setze_sortierwert(4, vertrag.verbleibende_rennen if vertrag else 0)
            zeile.setze_sortierwert(5, len(angebote))
            zeile.setForeground(1, FARBE_BELEGT if vertrag else FARBE_FREI)
            if vertrag:
                belegt += 1
                schrift = zeile.font(0)
                schrift.setBold(True)
                zeile.setFont(0, schrift)
            if platz == gewaehlt:
                self._plaetze.setCurrentItem(zeile)

        self._plaetze.setSortingEnabled(True)
        anzahl = len(kern_sponsoren.plaetze(self._konfiguration))
        self._platzkasten.setTitle(f"Plaetze ({belegt} von {anzahl} belegt)")
        for spalte in range(self._plaetze.columnCount()):
            self._plaetze.resizeColumnToContents(spalte)
        if self._plaetze.currentItem() is None and self._plaetze.topLevelItemCount():
            self._plaetze.setCurrentItem(self._plaetze.topLevelItem(0))
        else:
            self._zeige_angebote()

        einnahmen = sum(
            v.angebot.grundbetrag for v in self._karriere.vertraege.values() if v.laeuft
        )
        self._hinweis.setText(
            f"Sichere Einnahmen je Rennen aus laufenden Vertraegen: {euro(einnahmen)}. "
            "Ein Klick auf eine Spaltenueberschrift sortiert."
        )

    def _gewaehlter_platz(self) -> str | None:
        zeile = self._plaetze.currentItem()
        return zeile.data(0, Qt.UserRole) if zeile is not None else None

    def _zeige_angebote(self, *_) -> None:
        platz = self._gewaehlter_platz()
        self._liste.setSortingEnabled(False)
        self._liste.clear()
        if platz is None:
            self._angebotskasten.setTitle("Angebote")
            self._liste.setSortingEnabled(True)
            return

        bezeichnung = self._konfiguration.wert("sponsoren", "bezeichnung").get(platz, platz)
        vertrag = self._karriere.vertraege.get(platz)
        angebote = self._angebote.get(platz, ())
        self._angebotskasten.setTitle(f"Angebote fuer {bezeichnung} ({len(angebote)})")

        for angebot in angebote:
            laeuft = vertrag is not None and vertrag.angebot.name == angebot.name
            if laeuft:
                stand = f"laeuft, {vertrag.verbleibende_rennen} Rennen"
            elif vertrag is not None:
                stand = "Platz belegt"
            else:
                stand = "frei"
            zeile = Zeile(
                self._liste,
                [
                    angebot.name,
                    euro(angebot.grundbetrag),
                    euro(angebot.praemie_sieg),
                    euro(angebot.praemie_top3),
                    euro(angebot.praemie_top10),
                    euro(angebot.hoechstwert),
                    f"{angebot.laufzeit_rennen} Rennen",
                    stand,
                ],
            )
            zeile.setData(0, Qt.UserRole, angebot)
            for spalte, wert in (
                (1, angebot.grundbetrag),
                (2, angebot.praemie_sieg),
                (3, angebot.praemie_top3),
                (4, angebot.praemie_top10),
                (5, angebot.hoechstwert),
                (6, angebot.laufzeit_rennen),
            ):
                zeile.setze_sortierwert(spalte, wert)
            if laeuft:
                zeile.setForeground(7, FARBE_BELEGT)

        self._liste.setSortingEnabled(True)
        # Standardmaessig das lukrativste Angebot zuerst.
        self._liste.sortByColumn(1, Qt.DescendingOrder)
        for spalte in range(self._liste.columnCount()):
            self._liste.resizeColumnToContents(spalte)
        self._unterschreiben.setEnabled(vertrag is None and bool(angebote))
        if self._liste.topLevelItemCount():
            self._liste.setCurrentItem(self._liste.topLevelItem(0))

    # -- Aktionen ----------------------------------------------------------
    def _unterschreibe(self) -> None:
        zeile = self._liste.currentItem()
        angebot = zeile.data(0, Qt.UserRole) if zeile is not None else None
        if angebot is None:
            QMessageBox.information(self, "Sponsoren", "Kein Angebot gewaehlt.")
            return
        if angebot.platz in self._karriere.vertraege:
            QMessageBox.information(
                self, "Sponsoren", "Dieser Platz traegt schon einen Vertrag."
            )
            return
        self._karriere.unterschreibe(angebot)
        self.zeichne()

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def platzliste(self) -> QTreeWidget:
        return self._plaetze

    @property
    def angebotsliste(self) -> QTreeWidget:
        return self._liste

    @property
    def knopf_unterschreiben(self) -> QPushButton:
        return self._unterschreiben

    @property
    def angebote(self) -> dict[str, tuple[kern_sponsoren.Angebot, ...]]:
        return self._angebote
