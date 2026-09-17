"""Seite fuer eine einzelne Runde ohne Zufall.

Zeigt das Geschwindigkeitsprofil eines Autos auf einer Strecke, die
Rundenzeit in Tausendsteln, die vier Sektorzeiten und - auf der
Referenzstrecke - den Abgleich mit der Kalibrierfunktion aus GDD 9.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import auto as kern_auto
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern.strecke import Strecke, StreckenFehler
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.streckenansicht import Streckenansicht


class Rundenseite(QWidget):
    """Waehlt Strecke und Eigenschaftsniveau und faehrt eine Runde."""

    def __init__(self, konfiguration: Konfiguration, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._strecken: dict[str, Strecke] = {}
        self._ergebnis: kern_tempo.Rundenergebnis | None = None

        self._ansicht = Streckenansicht()

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_steuerung())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._ansicht)
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._aktualisiere()

    # -- Aufbau ------------------------------------------------------------
    def _baue_steuerung(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._auswahl = QComboBox()
        referenz = self._konfiguration.wert("kalibrierung", "referenzstrecke")
        for nummer, eintrag in enumerate(self._konfiguration.strecken):
            beschriftung = f"{eintrag['nummer']:>2}  {eintrag['name']}"
            if eintrag["name"] == referenz:
                beschriftung += "  (Referenz)"
            self._auswahl.addItem(beschriftung, eintrag["name"])
            if eintrag["name"] == referenz:
                self._auswahl.setCurrentIndex(nummer)
        self._auswahl.currentIndexChanged.connect(self._aktualisiere)

        maximum = self._konfiguration.wert("skala", "maximum")
        self._wert = QSpinBox()
        self._wert.setRange(self._konfiguration.wert("skala", "minimum"), maximum)
        self._wert.setSingleStep(1_000)
        self._wert.setGroupSeparatorShown(True)
        self._wert.setValue(0)

        self._regler = QSlider(Qt.Horizontal)
        self._regler.setRange(self._wert.minimum(), maximum)
        self._regler.setValue(0)
        self._regler.setMinimumWidth(240)

        # Regler und Zahlenfeld zeigen denselben Wert.
        self._regler.valueChanged.connect(self._wert.setValue)
        self._wert.valueChanged.connect(self._regler.setValue)
        self._wert.valueChanged.connect(self._aktualisiere)

        zeile.addWidget(QLabel("Strecke:"))
        zeile.addWidget(self._auswahl)
        zeile.addSpacing(16)
        zeile.addWidget(QLabel("Alle Eigenschaften auf:"))
        zeile.addWidget(self._wert)
        zeile.addWidget(self._regler)
        zeile.addStretch(1)
        return zeile

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._zeiten = QFormLayout()
        kasten = QGroupBox("Runde")
        kasten.setLayout(self._zeiten)
        spalte.addWidget(kasten)

        self._abgleich = QFormLayout()
        self._abgleichkasten = QGroupBox("Abgleich mit GDD 9")
        self._abgleichkasten.setLayout(self._abgleich)
        spalte.addWidget(self._abgleichkasten)

        self._grenzen = QFormLayout()
        grenzkasten = QGroupBox("Physikalische Grenzen")
        grenzkasten.setLayout(self._grenzen)
        spalte.addWidget(grenzkasten)

        spalte.addStretch(1)
        return seite

    # -- Inhalt ------------------------------------------------------------
    def _lade_strecke(self, name: str) -> Strecke | None:
        if name not in self._strecken:
            try:
                self._strecken[name] = kern_strecke.lade(self._konfiguration, name)
            except StreckenFehler:
                return None
        return self._strecken[name]

    def _aktualisiere(self, *_) -> None:
        name = self._auswahl.currentData()
        strecke = self._lade_strecke(name) if name else None
        if strecke is None:
            return

        s = self._wert.value()
        auto = kern_auto.gleichverteilt(self._konfiguration, s)
        self._ergebnis = kern_tempo.fahre_runde(self._konfiguration, strecke, auto)
        self._ansicht.zeige_tempo(strecke, self._ergebnis.profil)

        self._fuelle_zeiten(strecke, self._ergebnis)
        self._fuelle_abgleich(strecke, self._ergebnis, s)
        self._fuelle_grenzen(auto)

    def _fuelle_zeiten(self, strecke: Strecke, ergebnis: kern_tempo.Rundenergebnis) -> None:
        self._leere(self._zeiten)
        self._zeiten.addRow("Rundenzeit:", self._fett(formatiere_dauer(ergebnis.zeit_ms)))
        for nummer, zeit in enumerate(ergebnis.sektoren_ms, start=1):
            self._zeiten.addRow(f"Sektor {nummer}:", QLabel(formatiere_dauer(zeit)))
        self._zeiten.addRow("Schnitt:", QLabel(f"{ergebnis.schnitt_kmh:.2f} km/h"))
        self._zeiten.addRow(
            "Hoechstgeschwindigkeit:", QLabel(f"{ergebnis.hoechstgeschwindigkeit_kmh:.0f} km/h")
        )
        langsamste = float(ergebnis.profil.min()) * kern_tempo.KMH_JE_MS
        self._zeiten.addRow("Langsamster Punkt:", QLabel(f"{langsamste:.0f} km/h"))
        self._zeiten.addRow("Rundenlaenge:", QLabel(f"{strecke.laenge_m:,.0f} m".replace(",", ".")))

    def _fuelle_abgleich(
        self, strecke: Strecke, ergebnis: kern_tempo.Rundenergebnis, s: int
    ) -> None:
        self._leere(self._abgleich)
        referenz = self._konfiguration.wert("kalibrierung", "referenzstrecke")
        if strecke.name != referenz:
            self._abgleichkasten.setTitle("Abgleich mit GDD 9")
            hinweis = QLabel(
                f"Die Kalibrierung aus GDD 9 gilt fuer die Referenzstrecke "
                f"{referenz}. Auf anderen Strecken weicht der Schnitt ab - "
                f"hier faehrt dasselbe Auto {ergebnis.schnitt_kmh:.1f} km/h."
            )
            hinweis.setWordWrap(True)
            self._abgleich.addRow(hinweis)
            return

        self._abgleichkasten.setTitle(f"Abgleich mit GDD 9 auf {referenz}")
        soll = self._konfiguration.wert("kalibrierung", "basis_kmh") + self._konfiguration.wert(
            "kalibrierung", "spanne_kmh"
        ) * math.sqrt(s / self._konfiguration.wert("skala", "referenz"))
        abweichung = ergebnis.schnitt_kmh - soll

        self._abgleich.addRow("Formel v(S):", QLabel(f"{soll:.2f} km/h"))
        self._abgleich.addRow("Gefahren:", QLabel(f"{ergebnis.schnitt_kmh:.2f} km/h"))
        self._abgleich.addRow("Abweichung:", QLabel(f"{abweichung:+.3f} km/h"))

    def _fuelle_grenzen(self, auto: kern_auto.Auto) -> None:
        self._leere(self._grenzen)
        grenzen = kern_tempo.grenzen_aus(self._konfiguration, auto)
        erdbeschleunigung = 9.81
        for beschriftung, wert in (
            ("Querhaftung Kurve:", grenzen.quer),
            ("Querhaftung enge Kurve:", grenzen.quer_eng),
            ("Bremsen:", grenzen.brems),
            ("Beschleunigen:", grenzen.laengs),
        ):
            self._grenzen.addRow(
                beschriftung,
                QLabel(f"{wert:.2f} m/s²   ({wert / erdbeschleunigung:.2f} g)"),
            )
        self._grenzen.addRow(
            "Endgeschwindigkeit:", QLabel(f"{grenzen.hoechst_kmh:.0f} km/h")
        )

    # -- Hilfen ------------------------------------------------------------
    @staticmethod
    def _fett(text: str) -> QLabel:
        marke = QLabel(f"<b>{text}</b>")
        marke.setTextFormat(Qt.RichText)
        return marke

    @staticmethod
    def _leere(formular: QFormLayout) -> None:
        while formular.rowCount():
            formular.removeRow(0)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def ergebnis(self) -> kern_tempo.Rundenergebnis | None:
        return self._ergebnis

    @property
    def auswahl(self) -> QComboBox:
        return self._auswahl

    @property
    def wert(self) -> QSpinBox:
        return self._wert
