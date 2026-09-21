"""Seite fuer die Welt: Teams und Fahrer (GDD 12).

Links die Fahrerliste, rechts der Steckbrief des gewaehlten Fahrers mit
seinen 32 Einzelwerten (F1 bis F16 aus GDD 5, D1 bis D16 aus GDD 6) und
den Faehigkeiten ausserhalb der Wirkungsmatrix.

Die Liste zeigt alle 50 Fahrer, wahlweise nur mit ihren Stammdaten oder
zusaetzlich mit jedem Einzelwert als eigener Spalte.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from rennmanager.kern import charakter as kern_charakter
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern.auto import bereichswerte
from rennmanager.kern.welt import Welt
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import schriftfarbe, verbinde_fahrerkarte

# Spalten, die unabhaengig von der Eigenschaftsansicht immer stehen.
STAMMSPALTEN = ("#", "Kuerzel", "Fahrer", "Land", "Alter", "Team", "Hersteller", "Staerke")


def _zahl(wert: float) -> str:
    """Ganze Zahl mit Punkt als Tausendertrennzeichen."""
    return f"{wert:,.0f}".replace(",", ".")


class Weltseite(QWidget):
    """Zeigt die 50 Fahrer des Feldes und ihre Teams."""

    # Doppelklick auf einen Namen: Das Fenster oeffnet die Fahrerkarte.
    fahrerkarte_gewuenscht = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        jahr: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        # Das Alter wird am Stichtag der laufenden Saison gemessen; ohne
        # Jahr am Startjahr aus der Konfiguration.
        self._jahr = jahr

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_fahrerliste())
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._zeige_feld()

    # -- Nachziehen --------------------------------------------------------
    def setze_welt(self, welt: Welt) -> None:
        """Nimmt eine frische Welt an und zeichnet die Liste neu.

        Die Werte der eigenen Autos stehen in der Karriere, nicht in der
        Welt (GDD 1). Wer einen Tag belegt oder etwas kauft, aendert sie -
        und diese Seite muss das zeigen, sonst bleibt der Steckbrief auf
        dem Anfangsstand stehen.
        """
        self._welt = welt
        gewaehlt = self._liste.currentItem()
        nummer = gewaehlt.data(0, Qt.UserRole) if gewaehlt is not None else None
        self._zeige_feld()
        if nummer is None:
            return
        for stelle in range(self._liste.topLevelItemCount()):
            zeile = self._liste.topLevelItem(stelle)
            if zeile.data(0, Qt.UserRole) == nummer:
                self._liste.setCurrentItem(zeile)
                break

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        # Alle 32 Einzelwerte als Spalten - sonst stehen nur die Stammdaten
        # in der Liste und die Werte einzeln im Steckbrief.
        self._alle_werte = QCheckBox("Alle Eigenschaften")
        self._alle_werte.setToolTip(
            "Zeigt F1 bis F16 (GDD 5), D1 bis D16 (GDD 6) und die "
            "Faehigkeiten ausserhalb der Wirkungsmatrix als eigene Spalten."
        )
        self._alle_werte.toggled.connect(self._zeige_feld)

        zeile.addWidget(self._alle_werte)
        zeile.addWidget(
            QLabel(
                f"{len(self._welt.fahrer)} Fahrer · {len(self._welt.teams)} Teams · "
                f"Seed {self._welt.seed}"
            )
        )
        zeile.addStretch(1)
        return zeile

    def _wertspalten(self) -> tuple[str, ...]:
        """Die Schluessel aller Einzelwerte, Fahrzeug zuerst."""
        return tuple(f.schluessel for f in self._konfiguration.faehigkeiten) + tuple(
            self._konfiguration.zusatzfaehigkeiten
        )

    def _baue_fahrerliste(self) -> QWidget:
        self._listenkasten = QGroupBox("Fahrer")
        spalte = QVBoxLayout(self._listenkasten)
        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(list(STAMMSPALTEN))
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        self._liste.currentItemChanged.connect(self._zeige_fahrer)
        verbinde_fahrerkarte(self._liste, self.fahrerkarte_gewuenscht.emit)
        spalte.addWidget(self._liste)
        return self._listenkasten

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._steckbrief = QFormLayout()
        kasten = QGroupBox("Fahrer und Team")
        kasten.setLayout(self._steckbrief)
        spalte.addWidget(kasten)

        self._profil = QTreeWidget()
        self._profil.setHeaderLabels(["Eigenschaft", "Wert"])
        self._profil.setAlternatingRowColors(True)
        profilkasten = QGroupBox("Profil und Einzelwerte")
        profil_spalte = QVBoxLayout(profilkasten)
        profil_spalte.addWidget(self._profil)
        spalte.addWidget(profilkasten, stretch=1)
        return seite

    # -- Inhalt ------------------------------------------------------------
    def _fahrerliste(self) -> tuple:
        """Die anzuzeigenden Fahrer, staerkster zuerst."""
        return self._welt.feld

    def _zeige_feld(self, *_) -> None:
        self._liste.clear()
        mit_werten = self._alle_werte.isChecked()
        schluessel = self._wertspalten() if mit_werten else ()

        kopf = list(STAMMSPALTEN) + list(schluessel)
        self._liste.setColumnCount(len(kopf))
        self._liste.setHeaderLabels(kopf)
        self._setze_spaltenhilfe(kopf)

        fahrer_liste = self._fahrerliste()
        saisonstart = self._saisonstart()
        for platz, fahrer in enumerate(fahrer_liste, start=1):
            team = self._welt.team_von(fahrer)
            staerke = sum(fahrer.auto.werte.values()) / len(fahrer.auto.werte)
            felder = [
                str(platz),
                fahrer.kuerzel,
                fahrer.name,
                fahrer.land,
                str(fahrer.alter_am(saisonstart)),
                team.name,
                team.hersteller,
                _zahl(staerke),
            ]
            felder += [_zahl(self._wert_von(fahrer, s)) for s in schluessel]

            zeile = QTreeWidgetItem(self._liste, felder)
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            zeile.setForeground(kopf.index("Kuerzel"), schriftfarbe(team.farbe))
            if fahrer.ist_spieler:
                schrift = zeile.font(2)
                schrift.setBold(True)
                for spalte in range(self._liste.columnCount()):
                    zeile.setFont(spalte, schrift)

        self._listenkasten.setTitle(f"Fahrer ({len(fahrer_liste)})")
        for spalte in range(self._liste.columnCount()):
            self._liste.resizeColumnToContents(spalte)
        if self._liste.topLevelItemCount():
            self._liste.setCurrentItem(self._liste.topLevelItem(0))

    def _wert_von(self, fahrer, schluessel: str) -> int:
        """Einzelwert eines Fahrers, aus der Matrix oder daneben."""
        if schluessel in fahrer.auto.werte:
            return fahrer.auto.werte[schluessel]
        return fahrer.auto.wetterwerte.get(schluessel, 0)

    def _setze_spaltenhilfe(self, kopf: list[str]) -> None:
        """Legt den vollen Namen als Tooltip auf die Wertspalten."""
        namen = {f.schluessel: f.name for f in self._konfiguration.faehigkeiten}
        namen.update(self._zusatznamen())
        for stelle, titel in enumerate(kopf):
            if titel in namen:
                self._liste.headerItem().setToolTip(stelle, namen[titel])

    def _zusatznamen(self) -> dict[str, str]:
        """Namen der Faehigkeiten ausserhalb der Wirkungsmatrix."""
        return {
            e["schluessel"]: e.get("name", e["schluessel"])
            for e in self._konfiguration.zusatzeintraege
        }

    def _saisonstart(self):
        jahr = self._jahr or kern_karriere.startjahr(self._konfiguration)
        return kern_kalender.saisonstart(self._konfiguration, jahr)

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
            ("Team:", f"{team.name} ({team.land})"),
            ("Hersteller:", team.hersteller),
            ("Teamkollege:", kollegen),
            # Punkt 32: ein Satz aus den vorhandenen Werten - 38 Zahlen
            # sagen alles und zeigen nichts.
            ("Charakter:", kern_charakter.profil(self._konfiguration, fahrer.auto)),
        ):
            marke = QLabel(wert)
            marke.setWordWrap(True)
            self._steckbrief.addRow(beschriftung, marke)

        # Erst das Profil ueber die Wirkungsbereiche - daran sieht man, ob
        # jemand Regenspezialist oder Reifenschoner ist (GDD 12) -, dann
        # jeder Einzelwert, aus dem es entsteht.
        bezeichnung = self._konfiguration.wert("wirkungsmatrix", "bezeichnung")
        bereiche = QTreeWidgetItem(self._profil, ["Wirkungsbereiche (GDD 8)", ""])
        for bereich, wert in bereichswerte(self._konfiguration, fahrer.auto).items():
            QTreeWidgetItem(bereiche, [bezeichnung.get(bereich, bereich), _zahl(wert)])

        fahrzeug = QTreeWidgetItem(self._profil, ["Fahrzeug (GDD 5)", ""])
        fahrerwerte = QTreeWidgetItem(self._profil, ["Fahrer (GDD 6)", ""])
        for faehigkeit in self._konfiguration.faehigkeiten:
            ziel = fahrzeug if faehigkeit.ist_fahrzeug else fahrerwerte
            QTreeWidgetItem(
                ziel,
                [
                    f"{faehigkeit.schluessel} {faehigkeit.name}",
                    _zahl(fahrer.auto.werte[faehigkeit.schluessel]),
                ],
            )

        weitere = QTreeWidgetItem(self._profil, ["Neben der Matrix (GDD 7)", ""])
        namen = self._zusatznamen()
        for schluessel, wert in fahrer.auto.wetterwerte.items():
            QTreeWidgetItem(weitere, [namen.get(schluessel, schluessel), _zahl(wert)])

        for gruppe in (bereiche, fahrzeug, fahrerwerte, weitere):
            gruppe.setExpanded(True)
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
    def alle_werte(self) -> QCheckBox:
        """Schalter fuer die Einzelwerte als Spalten."""
        return self._alle_werte
