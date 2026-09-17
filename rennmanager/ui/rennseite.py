"""Seite fuer ein Rennen: Strecke, Seitenleiste, Zeitenmonitor, Zeitraffer.

Der Verlauf wird vorab berechnet (GDD 15); diese Seite spielt ihn nur ab.
Deshalb kostet auch 100-facher Zeitraffer nichts - es wird lediglich in
groesseren Schritten aus dem fertigen Verlauf gelesen.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import rennen as kern_rennen
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern.rennen import Rennverlauf
from rennmanager.kern.zeit import (
    formatiere_dauer,
    formatiere_rueckstand,
    formatiere_runden_rueckstand,
)
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.streckenansicht import Streckenansicht

# Takt der Wiedergabe. Der Zeitraffer vervielfacht die Rennzeit je Takt,
# nicht die Zahl der Takte - die Anzeige bleibt damit gleich fluessig.
TAKT_MS = 40


class Rennseite(QWidget):
    """Berechnet ein Rennen und spielt es ab."""

    def __init__(self, konfiguration: Konfiguration, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._strecken: dict[str, kern_strecke.Strecke] = {}
        self._verlauf: Rennverlauf | None = None
        self._zeit_ms = 0.0
        self._laeuft = False

        self._ansicht = Streckenansicht()
        self._uhr = QTimer(self)
        self._uhr.setInterval(TAKT_MS)
        self._uhr.timeout.connect(self._takt)

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_steuerung())
        spalte.addLayout(self._baue_wiedergabe())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._ansicht)
        teiler.addWidget(self._baue_seitenleiste())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

    # -- Aufbau ------------------------------------------------------------
    def _baue_steuerung(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._auswahl = QComboBox()
        for eintrag in self._konfiguration.strecken:
            self._auswahl.addItem(f"{eintrag['nummer']:>2}  {eintrag['name']}", eintrag["name"])

        self._liga = QComboBox()
        for zeile_kontrolle in self._konfiguration.wert("ligen", "kontrolle"):
            nummer = zeile_kontrolle["liga"]
            self._liga.addItem(f"Liga {nummer} - {self._konfiguration.ligenname(nummer)}", nummer)
        self._liga.setCurrentIndex(0)

        self._seed = QSpinBox()
        self._seed.setRange(0, 2**31 - 1)
        self._seed.setValue(4711)
        self._seed.setGroupSeparatorShown(True)

        self._runden = QSpinBox()
        self._runden.setRange(1, 200)
        self._runden.setValue(5)

        self._umgedreht = QComboBox()
        self._umgedreht.addItem("Aufstellung nach Staerke", False)
        self._umgedreht.addItem("Staerkster startet hinten", True)

        self._starten = QPushButton("Rennen berechnen")
        self._starten.clicked.connect(self._berechne)

        for beschriftung, feld in (
            ("Strecke:", self._auswahl),
            ("Liga:", self._liga),
            ("Runden:", self._runden),
            ("Seed:", self._seed),
            ("", self._umgedreht),
        ):
            if beschriftung:
                zeile.addWidget(QLabel(beschriftung))
            zeile.addWidget(feld)
        zeile.addWidget(self._starten)
        zeile.addStretch(1)
        return zeile

    def _baue_wiedergabe(self) -> QHBoxLayout:
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
        self._fortschritt = QProgressBar()
        self._fortschritt.setTextVisible(False)

        zeile.addWidget(self._abspielen)
        zeile.addWidget(self._zurueck)
        zeile.addWidget(QLabel("Zeitraffer:"))
        zeile.addWidget(self._raffer)
        zeile.addWidget(self._sofort)
        zeile.addWidget(self._uhrzeit)
        zeile.addWidget(self._fortschritt, stretch=1)
        return zeile

    def _baue_seitenleiste(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        # GDD 4: Positionen, Gesamtzeit des Fuehrenden, Rueckstand der uebrigen
        self._rangliste = QTreeWidget()
        self._rangliste.setHeaderLabels(["Pos", "Auto", "Rd", "Zeit / Rueckstand"])
        self._rangliste.setRootIsDecorated(False)
        self._rangliste.setAlternatingRowColors(True)
        kasten = QGroupBox("Rangliste")
        kasten_spalte = QVBoxLayout(kasten)
        kasten_spalte.addWidget(self._rangliste)
        spalte.addWidget(kasten, stretch=3)

        # GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten
        self._monitor = QTreeWidget()
        self._monitor.setHeaderLabels(
            ["Auto", "Letzte Rd", "Beste Rd", "S1", "S2", "S3", "S4"]
        )
        self._monitor.setRootIsDecorated(False)
        self._monitor.setAlternatingRowColors(True)
        monitorkasten = QGroupBox("Zeitenmonitor")
        monitor_spalte = QVBoxLayout(monitorkasten)
        monitor_spalte.addWidget(self._monitor)
        spalte.addWidget(monitorkasten, stretch=2)
        return seite

    # -- Rennen berechnen --------------------------------------------------
    def _lade_strecke(self, name: str) -> kern_strecke.Strecke:
        if name not in self._strecken:
            self._strecken[name] = kern_strecke.lade(self._konfiguration, name)
        return self._strecken[name]

    def _mittlerer_anteil(self) -> float:
        alle = [self._lade_strecke(e["name"]) for e in self._konfiguration.strecken]
        return kern_rennen.mittlerer_ueberholzonenanteil(self._konfiguration, alle)

    def _berechne(self) -> None:
        self._halte_an()
        self._starten.setEnabled(False)
        self._starten.setText("Berechne ...")
        try:
            strecke = self._lade_strecke(self._auswahl.currentData())
            liga = self._liga.currentData()
            feld = kern_rennen.starterfeld(
                self._konfiguration,
                liga,
                spielerplatz=self._konfiguration.wert("rennen", "autos"),
                umgedreht=self._umgedreht.currentData(),
            )
            self._verlauf = kern_rennen.simuliere(
                self._konfiguration,
                strecke,
                feld,
                self._runden.value(),
                Seedquelle(self._seed.value()),
                self._mittlerer_anteil(),
            )
        finally:
            self._starten.setEnabled(True)
            self._starten.setText("Rennen berechnen")

        self._ansicht.zeige(strecke)
        self._fortschritt.setRange(0, max(self._verlauf.dauer_ms, 1))
        for knopf in (self._abspielen, self._zurueck, self._sofort):
            knopf.setEnabled(True)
        self._springe(0)

    # -- Wiedergabe --------------------------------------------------------
    def _umschalten(self) -> None:
        if self._laeuft:
            self._halte_an()
        else:
            self._laeuft = True
            self._abspielen.setText("Pause")
            self._uhr.start()

    def _halte_an(self) -> None:
        self._laeuft = False
        self._uhr.stop()
        self._abspielen.setText("Start")

    def _springe(self, zeit_ms: float) -> None:
        self._zeit_ms = zeit_ms
        self._zeichne()

    def _zum_ende(self) -> None:
        """GDD 4: Sofortergebnis."""
        if self._verlauf is not None:
            self._halte_an()
            self._springe(self._verlauf.dauer_ms)

    def _takt(self) -> None:
        if self._verlauf is None:
            return
        self._zeit_ms += TAKT_MS * self._raffer.currentData()
        if self._zeit_ms >= self._verlauf.dauer_ms:
            self._zeit_ms = self._verlauf.dauer_ms
            self._halte_an()
        self._zeichne()

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self) -> None:
        if self._verlauf is None:
            return
        verlauf = self._verlauf
        zeit = self._zeit_ms
        self._uhrzeit.setText(formatiere_dauer(int(zeit)))
        self._fortschritt.setValue(int(zeit))

        distanzen = verlauf.distanzen_zu(zeit)
        reihenfolge = verlauf.reihenfolge_zu(zeit)

        self._ansicht.zeige_autos(
            [
                (
                    float(distanzen[i]),
                    verlauf.teilnehmer[i].kuerzel,
                    verlauf.teilnehmer[i].farbe,
                    verlauf.teilnehmer[i].ist_spieler,
                )
                for i in reihenfolge
            ]
        )
        self._fuelle_rangliste(verlauf, reihenfolge, distanzen, zeit)
        self._fuelle_monitor(verlauf, reihenfolge)

    def _fuelle_rangliste(
        self, verlauf: Rennverlauf, reihenfolge: list[int], distanzen, zeit: float
    ) -> None:
        """GDD 4: Gesamtzeit des Fuehrenden, Rueckstand der uebrigen."""
        self._rangliste.clear()
        laenge = verlauf.strecke.laenge_m
        fuehrender = reihenfolge[0]
        vorne = float(distanzen[fuehrender])

        for platz, i in enumerate(reihenfolge, start=1):
            teilnehmer = verlauf.teilnehmer[i]
            distanz = float(distanzen[i])
            runde = min(int(max(distanz, 0.0) // laenge) + 1, verlauf.runden)

            if i == fuehrender:
                text = formatiere_dauer(int(zeit))
            else:
                rueckstandsrunden = int((vorne - distanz) // laenge)
                if rueckstandsrunden >= 1:
                    text = formatiere_runden_rueckstand(rueckstandsrunden)
                else:
                    # Rueckstand in Zeit: Strecke geteilt durch das Tempo des
                    # Fuehrenden an dieser Stelle.
                    tempo = self._tempo_naeherung(verlauf, fuehrender, zeit)
                    text = formatiere_rueckstand(int((vorne - distanz) / max(tempo, 1e-6) * 1000))

            zeile = QTreeWidgetItem(
                self._rangliste, [str(platz), teilnehmer.kuerzel, str(runde), text]
            )
            zeile.setForeground(1, QColor(teilnehmer.farbe))
            if teilnehmer.ist_spieler:
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(4):
                    zeile.setFont(spalte, schrift)
        for spalte in range(4):
            self._rangliste.resizeColumnToContents(spalte)

    @staticmethod
    def _tempo_naeherung(verlauf: Rennverlauf, i: int, zeit: float) -> float:
        """Tempo eines Autos aus zwei benachbarten Bildern, in m/s."""
        bild = verlauf.bild_zu(zeit)
        if bild >= len(verlauf.zeitpunkte_ms) - 1:
            bild = max(0, len(verlauf.zeitpunkte_ms) - 2)
        dt = (verlauf.zeitpunkte_ms[bild + 1] - verlauf.zeitpunkte_ms[bild]) / 1000.0
        return float(verlauf.distanz_m[bild + 1, i] - verlauf.distanz_m[bild, i]) / max(dt, 1e-6)

    def _fuelle_monitor(self, verlauf: Rennverlauf, reihenfolge: list[int]) -> None:
        """GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten."""
        self._monitor.clear()
        for i in reihenfolge[:10]:
            protokoll = verlauf.protokolle[i]
            sektoren = protokoll.sektorzeiten_ms[-1] if protokoll.sektorzeiten_ms else ()
            spalten = [
                verlauf.teilnehmer[i].kuerzel,
                formatiere_dauer(protokoll.letzte_runde_ms) if protokoll.letzte_runde_ms else "-",
                formatiere_dauer(protokoll.beste_runde_ms) if protokoll.beste_runde_ms else "-",
            ]
            spalten += [formatiere_dauer(zeit) for zeit in sektoren]
            spalten += ["-"] * (7 - len(spalten))
            zeile = QTreeWidgetItem(self._monitor, spalten)
            zeile.setForeground(0, QColor(verlauf.teilnehmer[i].farbe))
        for spalte in range(7):
            self._monitor.resizeColumnToContents(spalte)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def verlauf(self) -> Rennverlauf | None:
        return self._verlauf

    @property
    def zeit_ms(self) -> float:
        return self._zeit_ms
