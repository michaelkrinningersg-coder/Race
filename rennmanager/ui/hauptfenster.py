"""Hauptfenster der Anwendung.

Stand des Geruests (Schritt 1): Das Fenster zeigt, welche Konfiguration
geladen wurde, erlaubt die Eingabe eines Seeds fuer spaetere Simulationen
(GDD 15: Seed-Eingabe als Balancing-Werkzeug) und listet die im GDD noch
offenen Angaben auf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager import __version__
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.qualifyingseite import Qualifyingseite
from rennmanager.ui.rennseite import Rennseite
from rennmanager.ui.rundenseite import Rundenseite
from rennmanager.ui.streckenseite import Streckenseite

# Qt-Spinboxen rechnen mit 32-Bit-Ganzzahlen; der Hauptseed wird in der
# Oberflaeche deshalb auf diesen Bereich begrenzt.
SEED_MAX = 2**31 - 1


class Hauptfenster(QMainWindow):
    """Fenster mit Konfigurationsuebersicht und Seed-Eingabe."""

    def __init__(self, konfiguration: Konfiguration) -> None:
        super().__init__()
        self._konfiguration = konfiguration
        self._seedquelle = Seedquelle(0)

        self.setWindowTitle(f"Rennmanager {__version__}")
        self.resize(900, 640)

        self._baue_menue()
        self.setCentralWidget(self._baue_inhalt())
        self.statusBar().showMessage(
            f"Konfiguration geladen aus {konfiguration.quelle}"
        )

    # -- Aufbau ------------------------------------------------------------
    def _baue_menue(self) -> None:
        datei = self.menuBar().addMenu("&Datei")
        beenden = QAction("&Beenden", self)
        beenden.setShortcut("Ctrl+Q")
        beenden.triggered.connect(self.close)
        datei.addAction(beenden)

        hilfe = self.menuBar().addMenu("&Hilfe")
        ueber = QAction("&Ueber Rennmanager", self)
        ueber.triggered.connect(self._zeige_ueber)
        hilfe.addAction(ueber)

    def _baue_inhalt(self) -> QWidget:
        self._reiter = QTabWidget()
        self._reiter.addTab(self._baue_uebersichtsseite(), "Uebersicht")
        self._streckenseite = Streckenseite(self._konfiguration)
        self._reiter.addTab(self._streckenseite, "Strecke")
        self._rundenseite = Rundenseite(self._konfiguration)
        self._reiter.addTab(self._rundenseite, "Runde")
        self._qualifyingseite = Qualifyingseite(self._konfiguration)
        self._reiter.addTab(self._qualifyingseite, "Qualifying")
        self._rennseite = Rennseite(self._konfiguration)
        self._reiter.addTab(self._rennseite, "Rennen")
        return self._reiter

    def _baue_uebersichtsseite(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.addWidget(self._baue_uebersicht())
        spalte.addWidget(self._baue_seedbereich())
        spalte.addWidget(self._baue_offene_punkte(), stretch=1)
        return seite

    def _baue_uebersicht(self) -> QGroupBox:
        k = self._konfiguration
        kasten = QGroupBox("Geladene Konfiguration")
        formular = QFormLayout(kasten)
        formular.addRow("GDD-Version:", QLabel(str(k.wert("gdd_version"))))
        formular.addRow(
            "Ligen:",
            QLabel(
                f"{k.wert('ligen', 'anzahl')} "
                f"({k.ligenname(1)} bis {k.ligenname(k.wert('ligen', 'anzahl'))}), "
                f"je {k.wert('ligen', 'autos_je_liga')} Autos"
            ),
        )
        formular.addRow(
            "Strecken:",
            QLabel(f"{len(k.strecken)} (TUMFTM, LGPL-3.0, mitgeliefert)"),
        )
        formular.addRow(
            "Fahrzeug-Upgrades:", QLabel(f"{len(k.fahrzeug)} (F1 bis F16)")
        )
        formular.addRow(
            "Fahrer-Eigenschaften:", QLabel(f"{len(k.fahrer)} (D1 bis D16)")
        )
        formular.addRow(
            "Ereignisse / Defekte:",
            QLabel(
                f"{len(k.wert('ereignisse', 'liste'))} / "
                f"{len(k.wert('defekte', 'liste'))}"
            ),
        )

        hersteller_text = f"{len(k.hersteller)}"
        if not k.hersteller_bestaetigt:
            hersteller_text += "  (Platzhalterliste, noch nicht bestaetigt)"
        formular.addRow("Hersteller:", QLabel(hersteller_text))
        return kasten

    def _baue_seedbereich(self) -> QGroupBox:
        kasten = QGroupBox("Seed")
        zeile = QHBoxLayout(kasten)

        self._seed_eingabe = QSpinBox()
        self._seed_eingabe.setRange(0, SEED_MAX)
        self._seed_eingabe.setValue(0)
        self._seed_eingabe.setGroupSeparatorShown(True)
        self._seed_eingabe.valueChanged.connect(self._seed_geaendert)

        neuer_seed = QPushButton("Neuer Seed")
        neuer_seed.clicked.connect(self._wuerfle_seed)

        self._seed_hinweis = QLabel()
        self._seed_hinweis.setTextInteractionFlags(Qt.TextSelectableByMouse)

        zeile.addWidget(QLabel("Hauptseed:"))
        zeile.addWidget(self._seed_eingabe)
        zeile.addWidget(neuer_seed)
        zeile.addWidget(self._seed_hinweis, stretch=1)

        self._seed_geaendert(0)
        return kasten

    def _baue_offene_punkte(self) -> QGroupBox:
        offen = self._konfiguration.offene_punkte
        kasten = QGroupBox(f"Im GDD noch nicht festgelegt ({len(offen)})")
        spalte = QVBoxLayout(kasten)

        baum = QTreeWidget()
        baum.setHeaderLabels(["Thema", "Fehlende Angabe"])
        baum.setRootIsDecorated(False)
        baum.setAlternatingRowColors(True)
        for thema, beschreibung in sorted(offen.items()):
            QTreeWidgetItem(baum, [thema, beschreibung])
        baum.resizeColumnToContents(0)
        spalte.addWidget(baum)
        return kasten

    # -- Reaktionen --------------------------------------------------------
    def _seed_geaendert(self, wert: int) -> None:
        self._seedquelle = Seedquelle(wert)
        beispiel = self._seedquelle.zweig("saison", 1).zweig("rennen", 1).zweig("wetter")
        self._seed_hinweis.setText(
            f"Beispielzweig {beispiel.bezeichnung} "
            f"-> {beispiel.abgeleiteter_seed}"
        )

    def _wuerfle_seed(self) -> None:
        self._seed_eingabe.setValue(Seedquelle.zufaellig().seed % (SEED_MAX + 1))

    @property
    def streckenseite(self) -> Streckenseite:
        """Die Seite mit der Streckendarstellung."""
        return self._streckenseite

    @property
    def rundenseite(self) -> Rundenseite:
        """Die Seite mit Geschwindigkeitsprofil und Rundenzeit."""
        return self._rundenseite

    @property
    def qualifyingseite(self) -> Qualifyingseite:
        """Die Seite mit dem Qualifying."""
        return self._qualifyingseite

    @property
    def rennseite(self) -> Rennseite:
        """Die Seite mit der Rennsimulation."""
        return self._rennseite

    @property
    def seedquelle(self) -> Seedquelle:
        """Der aktuell eingestellte Hauptseed."""
        return self._seedquelle

    def _zeige_ueber(self) -> None:
        QMessageBox.about(
            self,
            "Ueber Rennmanager",
            f"<b>Rennmanager {__version__}</b><br><br>"
            "Motorsport-Manager mit sichtbarer Rennsimulation.<br>"
            f"Grundlage: Game Design Dokument v{self._konfiguration.wert('gdd_version')}.<br><br>"
            "Streckendaten: TUMFTM/racetrack-database (LGPL-3.0).",
        )
