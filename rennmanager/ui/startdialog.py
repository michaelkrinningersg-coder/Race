"""Der Dialog "Neue Karriere" (Punkt 11).

GDD 1 sagt, wer der Spieler ist: ein Fahrer, der bei null anfaengt. Wie
er heisst, woher er kommt und wann er geboren ist, soll er selbst
bestimmen duerfen - das ist alles, was hier gefragt wird.

**Die Startliga steht nicht zur Wahl.** Sie ist immer Liga 20. Freie Wahl
waere der Schwierigkeitsgrad durch die Hintertuer: Wer in Liga 5 anfinge,
liesse die halbe Karriere aus GDD 13 einfach aus.

Die Laender kommen aus derselben Liste, aus der die 599 KI-Fahrer ihre
bekommen (``konfiguration/namen.toml``) - der Spieler soll kein Land
tragen, das es in dieser Welt sonst nicht gibt. An zwei von ihnen haengt
mehr als Farbe: Wer in einem Land wohnt, in dem eine der 20 Strecken
liegt, hat dort seine Heimstrecke (Punkt 49).
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import welt as kern_welt
from rennmanager.konfiguration import Konfiguration

# Das Alter zum Saisonstart. GDD 12 laesst die KI zwischen diesen Werten
# altern; der Spieler soll nicht ausserhalb davon anfangen.
JUENGSTES_ALTER = 18
AELTESTES_ALTER = 40
STANDARDALTER = 21


class Startdialog(QDialog):
    """Fragt Name, Land und Geburtstag des Spielers ab (GDD 1)."""

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
        self.setWindowTitle("Neue Karriere")
        self.setModal(True)

        spalte = QVBoxLayout(self)
        hinweis = QLabel(
            "Ein neuer Fahrer faengt bei null an (GDD 1) und startet in "
            f"Liga {konfiguration.wert('ligen', 'startliga')} - "
            f"{konfiguration.ligenname(konfiguration.wert('ligen', 'startliga'))}."
        )
        hinweis.setWordWrap(True)
        spalte.addWidget(hinweis)

        formular = QFormLayout()
        self._vorname = QLineEdit()
        self._nachname = QLineEdit()
        self._land = QComboBox()
        for land in self.laender(konfiguration):
            self._land.addItem(land)

        self._geburtstag = QDateEdit()
        self._geburtstag.setCalendarPopup(True)
        self._geburtstag.setDisplayFormat("dd.MM.yyyy")
        self._geburtstag.setDateRange(
            QDate(jahr - AELTESTES_ALTER, 1, 1),
            QDate(jahr - JUENGSTES_ALTER, 12, 31),
        )

        if vorgabe is not None:
            self._vorname.setText(vorgabe.vorname)
            self._nachname.setText(vorgabe.nachname)
            stelle = self._land.findText(vorgabe.land)
            if stelle >= 0:
                self._land.setCurrentIndex(stelle)
            self._geburtstag.setDate(
                QDate(
                    vorgabe.geburtstag.year,
                    vorgabe.geburtstag.month,
                    vorgabe.geburtstag.day,
                )
            )
        else:
            self._geburtstag.setDate(QDate(jahr - STANDARDALTER, 1, 1))

        formular.addRow("Vorname:", self._vorname)
        formular.addRow("Nachname:", self._nachname)
        formular.addRow("Land:", self._land)
        formular.addRow("Geburtstag:", self._geburtstag)
        spalte.addLayout(formular)

        self._knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._knoepfe.button(QDialogButtonBox.Ok).setText("Karriere beginnen")
        self._knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self._knoepfe.accepted.connect(self.accept)
        self._knoepfe.rejected.connect(self.reject)
        spalte.addWidget(self._knoepfe)

        for feld in (self._vorname, self._nachname):
            feld.textChanged.connect(self._pruefe)
        self._pruefe()

    @staticmethod
    def laender(konfiguration: Konfiguration) -> tuple[str, ...]:
        """Alle Laender der Namensliste, alphabetisch."""
        gruppen = kern_welt.lade_namen(konfiguration)["fahrer"]["laender"]
        return tuple(sorted({land for liste in gruppen.values() for land in liste}))

    def _pruefe(self) -> None:
        """Ohne Vor- und Nachnamen geht es nicht weiter."""
        vollstaendig = bool(
            self._vorname.text().strip() and self._nachname.text().strip()
        )
        self._knoepfe.button(QDialogButtonBox.Ok).setEnabled(vollstaendig)

    def stammdaten(self) -> dict:
        """Die eingegebenen Stammdaten, wie ``welt.mit_fahrerdaten`` sie will."""
        datum = self._geburtstag.date()
        return {
            "vorname": self._vorname.text().strip(),
            "nachname": self._nachname.text().strip(),
            "land": self._land.currentText(),
            "geburtstag": dt.date(datum.year(), datum.month(), datum.day()),
        }

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def vornamefeld(self) -> QLineEdit:
        return self._vorname

    @property
    def nachnamefeld(self) -> QLineEdit:
        return self._nachname

    @property
    def landauswahl(self) -> QComboBox:
        return self._land

    @property
    def geburtstagsfeld(self) -> QDateEdit:
        return self._geburtstag

    @property
    def knopf_beginnen(self):
        return self._knoepfe.button(QDialogButtonBox.Ok)
