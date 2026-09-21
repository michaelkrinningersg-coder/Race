"""Der Dialog "Neue Karriere" (Punkt 11).

Der Spieler ist Teamchef: Ihm gehoert ein Team mit **vier** Autos, und
alle vier fangen bei null an. Wie das Team heisst und wer darin faehrt -
Name, Land und Geburtstag jedes der vier -, bestimmt er hier selbst.

Vier Fahrer zu je vier Feldern waeren untereinander eine Wand aus
Eingabezeilen. Sie liegen deshalb auf Reitern, einer je Auto; der
Teamname steht darueber, weil er fuer alle vier gilt.

**Die Startliga steht nicht zur Wahl.** Sie ist immer Liga 10, und alle
vier starten dort. Freie Wahl waere der Schwierigkeitsgrad durch die
Hintertuer: Wer in Liga 5 anfinge, liesse die halbe Karriere aus GDD 13
einfach aus.

Die Laender kommen aus derselben Liste, aus der die KI-Fahrer ihre
bekommen (``konfiguration/namen.toml``) - die eigenen Fahrer sollen kein
Land tragen, das es in dieser Welt sonst nicht gibt. An zwei von ihnen
haengt mehr als Farbe: Wer in einem Land wohnt, in dem eine der 20
Strecken liegt, hat dort seine Heimstrecke (Punkt 49).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import welt as kern_welt
from rennmanager.konfiguration import Konfiguration

# Das Alter zum Saisonstart. GDD 12 laesst die KI zwischen diesen Werten
# altern; die eigenen Fahrer sollen nicht ausserhalb davon anfangen.
JUENGSTES_ALTER = 18
AELTESTES_ALTER = 40
STANDARDALTER = 21


@dataclass
class _Fahrerfelder:
    """Die vier Eingabefelder eines Fahrers."""

    vorname: QLineEdit
    nachname: QLineEdit
    land: QComboBox
    geburtstag: QDateEdit


class Startdialog(QDialog):
    """Fragt Teamname und die vier eigenen Fahrer ab (Punkt 11)."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        jahr: int,
        vorgabe=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._jahr = jahr
        self._anzahl = konfiguration.wert("teams", "autos_je_team")
        self.setWindowTitle("Neue Karriere")
        self.setModal(True)

        startliga = konfiguration.wert("ligen", "startliga")
        spalte = QVBoxLayout(self)
        hinweis = QLabel(
            f"Ihnen gehoert ein Team mit {self._anzahl} Autos. Alle "
            f"{self._anzahl} Fahrer fangen bei null an und starten in "
            f"Liga {startliga} - {konfiguration.ligenname(startliga)}."
        )
        hinweis.setWordWrap(True)
        spalte.addWidget(hinweis)

        kopf = QFormLayout()
        self._teamname = QLineEdit()
        self._teamname.setPlaceholderText("z. B. Krinninger Racing")
        kopf.addRow("Teamname:", self._teamname)
        spalte.addLayout(kopf)

        laender = self.laender(konfiguration)
        self._reiter = QTabWidget()
        self._felder: list[_Fahrerfelder] = []
        for stelle in range(self._anzahl):
            seite, felder = self._baue_fahrerseite(laender, jahr)
            self._felder.append(felder)
            self._reiter.addTab(seite, f"Fahrer {stelle + 1}")
        spalte.addWidget(self._reiter)

        self._uebernimm_vorgabe(vorgabe)

        self._knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._knoepfe.button(QDialogButtonBox.Ok).setText("Karriere beginnen")
        self._knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self._knoepfe.accepted.connect(self.accept)
        self._knoepfe.rejected.connect(self.reject)
        spalte.addWidget(self._knoepfe)

        self._teamname.textChanged.connect(self._pruefe)
        for felder in self._felder:
            felder.vorname.textChanged.connect(self._pruefe)
            felder.nachname.textChanged.connect(self._pruefe)
        self._pruefe()

    # -- Aufbau ------------------------------------------------------------
    def _baue_fahrerseite(
        self, laender: tuple[str, ...], jahr: int
    ) -> tuple[QWidget, _Fahrerfelder]:
        seite = QWidget()
        formular = QFormLayout(seite)
        felder = _Fahrerfelder(
            vorname=QLineEdit(),
            nachname=QLineEdit(),
            land=QComboBox(),
            geburtstag=QDateEdit(),
        )
        for land in laender:
            felder.land.addItem(land)
        felder.geburtstag.setCalendarPopup(True)
        felder.geburtstag.setDisplayFormat("dd.MM.yyyy")
        felder.geburtstag.setDateRange(
            QDate(jahr - AELTESTES_ALTER, 1, 1),
            QDate(jahr - JUENGSTES_ALTER, 12, 31),
        )
        felder.geburtstag.setDate(QDate(jahr - STANDARDALTER, 1, 1))

        formular.addRow("Vorname:", felder.vorname)
        formular.addRow("Nachname:", felder.nachname)
        formular.addRow("Land:", felder.land)
        formular.addRow("Geburtstag:", felder.geburtstag)
        return seite, felder

    def _uebernimm_vorgabe(self, vorgabe) -> None:
        """Fuellt die Felder aus der laufenden Welt vor.

        ``vorgabe`` sind die vier eigenen Fahrer; ein einzelner wird
        ebenfalls angenommen, damit alte Aufrufer nicht brechen. Der
        Teamname kommt aus dem Team des ersten.
        """
        if vorgabe is None:
            return
        fahrer = list(vorgabe) if isinstance(vorgabe, (list, tuple)) else [vorgabe]
        for felder, einer in zip(self._felder, fahrer, strict=False):
            felder.vorname.setText(einer.vorname)
            felder.nachname.setText(einer.nachname)
            stelle = felder.land.findText(einer.land)
            if stelle >= 0:
                felder.land.setCurrentIndex(stelle)
            felder.geburtstag.setDate(
                QDate(
                    einer.geburtstag.year,
                    einer.geburtstag.month,
                    einer.geburtstag.day,
                )
            )

    @staticmethod
    def laender(konfiguration: Konfiguration) -> tuple[str, ...]:
        """Alle Laender der Namensliste, alphabetisch."""
        gruppen = kern_welt.lade_namen(konfiguration)["fahrer"]["laender"]
        return tuple(sorted({land for liste in gruppen.values() for land in liste}))

    # -- Pruefen und Ausgeben ----------------------------------------------
    def _pruefe(self) -> None:
        """Ohne Teamnamen und ohne vollstaendige Namen geht es nicht weiter."""
        vollstaendig = bool(self._teamname.text().strip()) and all(
            felder.vorname.text().strip() and felder.nachname.text().strip()
            for felder in self._felder
        )
        self._knoepfe.button(QDialogButtonBox.Ok).setEnabled(vollstaendig)

    def stammdaten(self) -> dict:
        """Teamname und die Stammdaten der vier Fahrer.

        Die Fahrerteile passen so, wie sie sind, in
        ``welt.mit_fahrerdaten``.
        """
        return {
            "team": self._teamname.text().strip(),
            "fahrer": [self._fahrerdaten(stelle) for stelle in range(self._anzahl)],
        }

    def _fahrerdaten(self, stelle: int) -> dict:
        felder = self._felder[stelle]
        datum = felder.geburtstag.date()
        return {
            "vorname": felder.vorname.text().strip(),
            "nachname": felder.nachname.text().strip(),
            "land": felder.land.currentText(),
            "geburtstag": dt.date(datum.year(), datum.month(), datum.day()),
        }

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def teamnamefeld(self) -> QLineEdit:
        return self._teamname

    @property
    def fahrerreiter(self) -> QTabWidget:
        return self._reiter

    def vornamefeld(self, stelle: int = 0) -> QLineEdit:
        return self._felder[stelle].vorname

    def nachnamefeld(self, stelle: int = 0) -> QLineEdit:
        return self._felder[stelle].nachname

    def landauswahl(self, stelle: int = 0) -> QComboBox:
        return self._felder[stelle].land

    def geburtstagsfeld(self, stelle: int = 0) -> QDateEdit:
        return self._felder[stelle].geburtstag

    @property
    def knopf_beginnen(self):
        return self._knoepfe.button(QDialogButtonBox.Ok)
