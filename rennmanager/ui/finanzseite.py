"""Die Finanzseite: woher das Geld kam und wohin es ging (Punkt 72).

Das Konto zeigt einen Stand. Was diesen Stand ausmacht - Preisgeld,
Sponsoren, das Monatsbudget des Teams auf der einen, Upgrades,
Reparaturen, Gehaelter und Abloesen auf der anderen Seite -, steht im
Kassenbuch der Karriere. Diese Seite liest es und gruppiert es nach
Haupt- und Unterkategorien.

Sie rechnet nichts aus: Alle Summen kommen aus
``rennmanager.kern.kassenbuch``. Die Seite entscheidet nur, was sie
zeigt - die ganze Karriere oder eine einzelne Saison.
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

from rennmanager.kern import kalender as kern_kalender
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import SortierbareZeile

# Spalten des Baums.
SPALTE_NAME = 0
SPALTE_EINNAHMEN = 1
SPALTE_AUSGABEN = 2
SPALTE_SALDO = 3
SPALTE_ANZAHL = 4

# Statusfarben aus der Referenzpalette: Gruen fuer das, was hereinkommt,
# Rot fuer das, was hinausgeht. Sie stehen neben der Zahl, nicht als
# einzige Auskunft - das Vorzeichen sagt dasselbe.
FARBE_EIN = "#2e7d32"
FARBE_AUS = "#c62828"
FARBE_STILL = "#8b93a1"

# Der Eintrag, der das ganze Kassenbuch zeigt.
ALLE = -1
# So viele Einzelbuchungen stehen unter einer Unterkategorie; darueber
# waere der Baum nicht mehr zu lesen. Die neuesten zuerst.
EINZELN_HOECHSTENS = 50


def euro(betrag: int) -> str:
    """Ein Geldbetrag mit Tausenderpunkten, wie ihn das Spiel sonst zeigt."""
    return f"{betrag:,} €".replace(",", ".")


class Finanzseite(QWidget):
    """Einnahmen und Ausgaben, nach Kategorien gegliedert."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        karriere=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._karriere = karriere

        spalte = QVBoxLayout(self)

        kopf = QHBoxLayout()
        kopf.addWidget(QLabel("Zeitraum:"))
        self._zeitraum = QComboBox()
        self._zeitraum.currentIndexChanged.connect(self.zeichne)
        kopf.addWidget(self._zeitraum)
        kopf.addSpacing(16)
        self._bilanz = QLabel()
        kopf.addWidget(self._bilanz)
        kopf.addStretch(1)
        self._stand = QLabel()
        kopf.addWidget(self._stand)
        spalte.addLayout(kopf)

        self._baum = QTreeWidget()
        self._baum.setHeaderLabels(
            ["Kategorie", "Einnahmen", "Ausgaben", "Saldo", "Buchungen"]
        )
        self._baum.setAlternatingRowColors(True)
        for stelle in (SPALTE_EINNAHMEN, SPALTE_AUSGABEN, SPALTE_SALDO, SPALTE_ANZAHL):
            self._baum.headerItem().setTextAlignment(
                stelle, Qt.AlignRight | Qt.AlignVCenter
            )
        kasten = QGroupBox("Ein- und Ausgaben")
        kasten_spalte = QVBoxLayout(kasten)
        kasten_spalte.addWidget(self._baum)
        spalte.addWidget(kasten, stretch=1)

        self._fuelle_zeitraum()
        self.zeichne()

    # -- Uebernehmen -------------------------------------------------------
    def setze_karriere(self, karriere) -> None:
        """Nimmt eine andere Karriere an - etwa aus einem geladenen Stand."""
        self._karriere = karriere
        self._fuelle_zeitraum()
        self.zeichne()

    def _fuelle_zeitraum(self) -> None:
        """Alle Jahre, in denen etwas gebucht wurde, plus 'ganze Karriere'."""
        self._zeitraum.blockSignals(True)
        vorher = self._zeitraum.currentData()
        self._zeitraum.clear()
        self._zeitraum.addItem("Ganze Karriere", ALLE)
        for jahr in self._jahre():
            self._zeitraum.addItem(f"Saison {jahr}", jahr)
        stelle = self._zeitraum.findData(vorher)
        self._zeitraum.setCurrentIndex(max(stelle, 0))
        self._zeitraum.blockSignals(False)

    def _jahre(self) -> tuple[int, ...]:
        if self._karriere is None:
            return ()
        return tuple(
            sorted({b.datum.year for b in self._karriere.kassenbuch.buchungen})
        )

    # -- Zeichnen ----------------------------------------------------------
    def _buchungen(self):
        """Die Buchungen des gewaehlten Zeitraums."""
        if self._karriere is None:
            return ()
        buch = self._karriere.kassenbuch
        jahr = self._zeitraum.currentData()
        if jahr is None or jahr == ALLE:
            return tuple(buch.buchungen)
        # Eine Saison laeuft ueber ein Kalenderjahr (GDD 2); der
        # Kalenderstreifen zeigt denselben Rahmen.
        saison = kern_kalender.erzeuge(self._konfiguration, jahr)
        return buch.im_zeitraum(saison.tage[0].datum, saison.tage[-1].datum)

    def zeichne(self, *_) -> None:
        """Baut den Baum aus dem Kassenbuch neu auf."""
        self._baum.clear()
        if self._karriere is None:
            self._bilanz.setText("Noch keine Karriere")
            self._stand.setText("")
            return

        buch = self._karriere.kassenbuch
        buchungen = self._buchungen()
        einnahmen = buch.einnahmen(buchungen)
        ausgaben = buch.ausgaben(buchungen)
        saldo = einnahmen - ausgaben

        self._bilanz.setText(
            f"Einnahmen <b style='color:{FARBE_EIN}'>{euro(einnahmen)}</b> · "
            f"Ausgaben <b style='color:{FARBE_AUS}'>{euro(ausgaben)}</b> · "
            f"Saldo <b>{euro(saldo)}</b>"
        )
        self._stand.setText(f"Kontostand: <b>{euro(self._karriere.konto.geld)}</b>")

        for haupt, unterkategorien in buch.nach_kategorien(buchungen).items():
            summe = buch.summe_von(haupt, buchungen)
            ast = self._zeile(self._baum, haupt, summe.einnahmen, summe.ausgaben,
                              summe.anzahl, fett=True)
            for name, teil in sorted(
                unterkategorien.items(), key=lambda paar: -abs(paar[1].saldo)
            ):
                zweig = self._zeile(ast, name, teil.einnahmen, teil.ausgaben,
                                    teil.anzahl)
                self._haenge_buchungen_an(zweig, buchungen, haupt, name)
            ast.setExpanded(True)

        for stelle in range(self._baum.columnCount()):
            self._baum.resizeColumnToContents(stelle)

    def _haenge_buchungen_an(self, zweig, buchungen, haupt: str, unter: str) -> None:
        """Die Einzelbuchungen einer Unterkategorie, die neuesten zuerst."""
        passende = [
            b
            for b in buchungen
            if b.hauptkategorie == haupt and b.unterkategorie == unter
        ]
        passende.sort(key=lambda b: b.datum, reverse=True)
        for buchung in passende[:EINZELN_HOECHSTENS]:
            beschriftung = buchung.datum.strftime("%d.%m.%Y")
            if buchung.text:
                beschriftung += f" · {buchung.text}"
            zeile = self._zeile(
                zweig,
                beschriftung,
                buchung.betrag if buchung.betrag > 0 else 0,
                -buchung.betrag if buchung.betrag < 0 else 0,
                0,
            )
            zeile.setForeground(SPALTE_NAME, QColor(FARBE_STILL))
        if len(passende) > EINZELN_HOECHSTENS:
            rest = QTreeWidgetItem(
                zweig, [f"… und {len(passende) - EINZELN_HOECHSTENS} aeltere", "", "", "", ""]
            )
            rest.setForeground(SPALTE_NAME, QColor(FARBE_STILL))

    @staticmethod
    def _zeile(eltern, name: str, einnahmen: int, ausgaben: int, anzahl: int,
               fett: bool = False) -> SortierbareZeile:
        """Eine Zeile des Baums; Summen rechtsbuendig und farbig."""
        saldo = einnahmen - ausgaben
        zeile = SortierbareZeile(
            eltern,
            [
                name,
                euro(einnahmen) if einnahmen else "",
                euro(ausgaben) if ausgaben else "",
                euro(saldo),
                str(anzahl) if anzahl else "",
            ],
        )
        for stelle, wert in (
            (SPALTE_EINNAHMEN, einnahmen),
            (SPALTE_AUSGABEN, ausgaben),
            (SPALTE_SALDO, saldo),
            (SPALTE_ANZAHL, anzahl),
        ):
            zeile.setze_sortierwert(stelle, wert)
            zeile.setTextAlignment(stelle, Qt.AlignRight | Qt.AlignVCenter)
        if einnahmen:
            zeile.setForeground(SPALTE_EINNAHMEN, QColor(FARBE_EIN))
        if ausgaben:
            zeile.setForeground(SPALTE_AUSGABEN, QColor(FARBE_AUS))
        zeile.setForeground(
            SPALTE_SALDO, QColor(FARBE_EIN if saldo >= 0 else FARBE_AUS)
        )
        if fett:
            schrift = zeile.font(SPALTE_NAME)
            schrift.setBold(True)
            for stelle in range(5):
                zeile.setFont(stelle, schrift)
        return zeile

    # -- Fuer Tests --------------------------------------------------------
    @property
    def baum(self) -> QTreeWidget:
        return self._baum

    @property
    def zeitraum(self) -> QComboBox:
        return self._zeitraum

    def hauptkategorien(self) -> tuple[str, ...]:
        """Die Hauptkategorien, die gerade im Baum stehen."""
        return tuple(
            self._baum.topLevelItem(stelle).text(SPALTE_NAME)
            for stelle in range(self._baum.topLevelItemCount())
        )
