"""Seite zur Streckenauswahl mit Ansicht, Kennwerten und Segmentliste."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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

from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern.strecke import Segmentart, Strecke, StreckenFehler
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.streckenansicht import Streckenansicht

# Ab diesem Radius ist eine Zahl in der Segmentliste nicht mehr aussagekraeftig.
RADIUS_ALS_GERADE_M = 5_000.0


class Streckenseite(QWidget):
    """Waehlt eine Strecke, zeigt sie an und listet ihre Segmente."""

    def __init__(self, konfiguration: Konfiguration, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._strecke: Strecke | None = None
        # Einmal geladene Strecken werden behalten; das Auswerten kostet
        # spuerbar Zeit und die Daten aendern sich nicht.
        self._zwischenspeicher: dict[str, Strecke] = {}

        # Die Ansicht entsteht zuerst, weil die Auswahlzeile sie schon verbindet.
        self._ansicht = Streckenansicht()

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_auswahl())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._ansicht)
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        # currentData() liefert den Streckennamen, currentText() die
        # Anzeige mit vorangestellter Nummer.
        self._waehle(self._auswahl.currentData())

    # -- Aufbau ------------------------------------------------------------
    def _baue_auswahl(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._auswahl = QComboBox()
        for eintrag in self._konfiguration.strecken:
            self._auswahl.addItem(f"{eintrag['nummer']:>2}  {eintrag['name']}", eintrag["name"])
        self._auswahl.currentIndexChanged.connect(
            lambda index: self._waehle(self._auswahl.itemData(index))
        )

        self._zonen_schalter = QCheckBox("Ueberholzonen hervorheben")
        self._zonen_schalter.setChecked(True)
        self._zonen_schalter.toggled.connect(self._ansicht.setze_ueberholzonen_sichtbar)

        zeile.addWidget(QLabel("Strecke:"))
        zeile.addWidget(self._auswahl)
        zeile.addWidget(self._zonen_schalter)
        zeile.addStretch(1)
        return zeile

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._kennwerte = QFormLayout()
        kasten = QGroupBox("Kennwerte")
        kasten.setLayout(self._kennwerte)
        spalte.addWidget(kasten)

        self._segmentliste = QTreeWidget()
        self._segmentliste.setHeaderLabels(["Sekt.", "Typ", "Laenge", "engster Radius"])
        self._segmentliste.setRootIsDecorated(False)
        self._segmentliste.setAlternatingRowColors(True)
        segmente = QGroupBox("Segmente")
        segmente_spalte = QVBoxLayout(segmente)
        segmente_spalte.addWidget(self._segmentliste)
        spalte.addWidget(segmente, stretch=1)
        return seite

    # -- Inhalt ------------------------------------------------------------
    def _waehle(self, name: str | None) -> None:
        if not name:
            return
        if name not in self._zwischenspeicher:
            try:
                self._zwischenspeicher[name] = kern_strecke.lade(self._konfiguration, name)
            except StreckenFehler as fehler:
                self._zeige_fehler(str(fehler))
                return
        self._strecke = self._zwischenspeicher[name]
        self._ansicht.zeige(self._strecke)
        self._fuelle_kennwerte(self._strecke)
        self._fuelle_segmente(self._strecke)

    def _fuelle_kennwerte(self, strecke: Strecke) -> None:
        self._leere(self._kennwerte)
        zonen = strecke.ueberholzonen
        laengste = max((zone.laenge_m for zone in zonen), default=0.0)

        zeilen = [
            ("Land:", strecke.land),
            ("Charakter:", strecke.charakter),
            ("Rundenlaenge:", f"{strecke.laenge_m:,.0f} m".replace(",", ".")),
            ("Punkte:", f"{len(strecke.punkte)} im Abstand {strecke.punktabstand_m:.2f} m"),
            ("Segmente:", str(len(strecke.segmente))),
            (
                "Enge Kurve / Kurve / Gerade:",
                f"{strecke.anteil(Segmentart.ENGE_KURVE):.0%} / "
                f"{strecke.anteil(Segmentart.KURVE):.0%} / "
                f"{strecke.geradenanteil:.0%}",
            ),
            ("Ueberholzonen:", f"{len(zonen)}, laengste {laengste:,.0f} m".replace(",", ".")),
            ("Engster Radius:", f"{strecke.radius_m.min():.0f} m"),
            ("Sektorlaenge:", f"rund {strecke.sektoren[0].laenge_m:,.0f} m".replace(",", ".")),
        ]
        if strecke.kurzsegmente:
            zeilen.append(
                (
                    "Segmente unter 25 m:",
                    f"{len(strecke.kurzsegmente)} (Datenqualitaet, siehe offene Punkte)",
                )
            )
        for beschriftung, wert in zeilen:
            self._kennwerte.addRow(beschriftung, QLabel(wert))

    def _fuelle_segmente(self, strecke: Strecke) -> None:
        self._segmentliste.clear()
        for segment in strecke.segmente:
            # Der engste Punkt bestimmt das Tempo, nicht der Mittelwert.
            # Sehr grosse Radien sind als Zahl nutzlos.
            radius = (
                "gerade"
                if segment.radius_min_m >= RADIUS_ALS_GERADE_M
                else f"{segment.radius_min_m:.0f} m"
            )
            zeile = QTreeWidgetItem(
                self._segmentliste,
                [
                    f"S{strecke.sektor_von_punkt(segment.von)}",
                    segment.art.bezeichnung,
                    f"{segment.laenge_m:.0f} m",
                    radius,
                ],
            )
            if segment.ist_ueberholzone:
                zeile.setText(1, f"{segment.art.bezeichnung} (Ueberholzone)")
        for spalte in range(self._segmentliste.columnCount()):
            self._segmentliste.resizeColumnToContents(spalte)

    def _zeige_fehler(self, text: str) -> None:
        self._strecke = None
        self._ansicht.zeige(None)
        self._leere(self._kennwerte)
        self._kennwerte.addRow("Fehler:", QLabel(text))
        self._segmentliste.clear()

    @staticmethod
    def _leere(formular: QFormLayout) -> None:
        while formular.rowCount():
            formular.removeRow(0)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def strecke(self) -> Strecke | None:
        return self._strecke

    @property
    def auswahl(self) -> QComboBox:
        return self._auswahl
