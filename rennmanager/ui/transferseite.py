"""Der Transfermarkt (Punkt 7).

Hier holt der Teamchef Fahrer. Die Liste zeigt jeden, der im kommenden
Winter zu haben ist, mit allem, was fuer die Entscheidung zaehlt:

* **Potential** - voll sichtbar, so hat es der Auftraggeber entschieden.
  Wer wen holt, ist keine Frage der Information, sondern des Geldes.
* **Koennen und Alter** - zusammen mit dem Potential sieht man, ob einer
  schon oben ist oder erst hinkommt.
* **Gehalt und Abloese** - was er je Saison kostet und was der Wechsel
  einmalig kostet, wenn er noch unter Vertrag steht.

Die Spalte **Luecke** ist die eigentliche Hilfe: Potential geteilt durch
Koennen. Ein Wert um 1 heisst, der Fahrer ist fertig; alles darueber
heisst, da kommt noch was. So findet man den Achtzehnjaehrigen in Liga 12,
dessen Potential fuer Liga 1 reicht.

**Ein neuer Fahrer bringt ein leeres, nicht upgegradetes Auto mit.** Der
Hinweis steht ueber der Liste, weil er die ganze Rechnung dreht: Wer
einen Star holt, setzt ihn in ein Auto mit lauter Nullen und muss ihn
dafuer ueberzahlen. Wen man schon hat, bleibt oft die bessere Wahl.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import talent as kern_talent
from rennmanager.kern import transfer as kern_transfer
from rennmanager.kern.auto import gesamtwert
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import verbinde_fahrerkarte

SPALTEN = (
    "Fahrer",
    "Liga",
    "Alter",
    "Koennen",
    "Potential",
    "Luecke",
    "Gehalt",
    "Abloese",
    "Vertrag",
)


def _euro(betrag: int) -> str:
    return f"{betrag:,} EUR".replace(",", ".")


class Angebotsdialog(QDialog):
    """Fragt Gehalt und Laufzeit fuer ein Angebot ab."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        name: str,
        vorschlag: kern_transfer.Angebot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Angebot an {name}")
        self.setModal(True)
        einstellung = konfiguration.wert("transfer")

        spalte = QVBoxLayout(self)
        hinweis = QLabel(
            f"{name} verlangt {_euro(vorschlag.gehalt)} je Saison. "
            "Mehr zu bieten erhoeht die Chance, dass er unterschreibt - "
            "er waegt Ligahoehe, Auto und Geld gegeneinander ab."
        )
        hinweis.setWordWrap(True)
        spalte.addWidget(hinweis)

        formular = QFormLayout()
        self._gehalt = QSpinBox()
        self._gehalt.setRange(0, 2_000_000_000)
        self._gehalt.setSingleStep(max(vorschlag.gehalt // 10, 1000))
        self._gehalt.setValue(vorschlag.gehalt)
        self._gehalt.setSuffix(" EUR je Saison")
        self._gehalt.setGroupSeparatorShown(True)

        self._laufzeit = QSpinBox()
        self._laufzeit.setRange(einstellung["laufzeit_min"], einstellung["laufzeit_max"])
        self._laufzeit.setValue(vorschlag.laufzeit)
        self._laufzeit.setSuffix(" Saisons")

        formular.addRow("Gehalt:", self._gehalt)
        formular.addRow("Laufzeit:", self._laufzeit)
        if vorschlag.abloese:
            formular.addRow("Abloese:", QLabel(_euro(vorschlag.abloese)))
        spalte.addLayout(formular)

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.button(QDialogButtonBox.Ok).setText("Angebot machen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        spalte.addWidget(knoepfe)

    @property
    def gehalt(self) -> int:
        return self._gehalt.value()

    @property
    def laufzeit(self) -> int:
        return self._laufzeit.value()


class Transferseite(QWidget):
    """Liste der verfuegbaren Fahrer mit Angebot (Punkt 7)."""

    fahrerkarte_gewuenscht = Signal(int)
    verpflichtet = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        lauf,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._lauf = lauf

        spalte = QVBoxLayout(self)
        self._hinweis = QLabel()
        self._hinweis.setWordWrap(True)
        spalte.addWidget(self._hinweis)

        kasten = QGroupBox("Verfuegbare Fahrer")
        kastenspalte = QVBoxLayout(kasten)
        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(list(SPALTEN))
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        self._liste.setSortingEnabled(True)
        verbinde_fahrerkarte(self._liste, self.fahrerkarte_gewuenscht.emit)
        kastenspalte.addWidget(self._liste)

        zeile = QHBoxLayout()
        self._konto = QLabel()
        self._angebot = QPushButton("Angebot machen")
        self._angebot.clicked.connect(self._mache_angebot)
        zeile.addWidget(self._konto)
        zeile.addStretch(1)
        zeile.addWidget(self._angebot)
        kastenspalte.addLayout(zeile)
        spalte.addWidget(kasten, stretch=1)

        self.aktualisiere()

    # -- Daten -------------------------------------------------------------
    def setze_lauf(self, lauf) -> None:
        self._lauf = lauf
        self.aktualisiere()

    def aktualisiere(self) -> None:
        """Fuellt die Liste mit dem Markt des kommenden Winters."""
        self._liste.setSortingEnabled(False)
        self._liste.clear()
        welt = self._lauf.welt
        jahr = self._lauf.jahr + 1
        stichtag = kern_kalender.saisonstart(self._konfiguration, jahr)
        quelle = self._lauf.seedquelle

        for nummer in self._lauf.transfermarkt():
            fahrer = welt.fahrer[nummer]
            talent = kern_talent.talent(
                self._konfiguration, nummer, fahrer.geburtstag, quelle
            )
            koennen = gesamtwert(self._konfiguration, fahrer.auto)
            angebot = kern_transfer.angebot(
                self._konfiguration, welt, nummer, jahr, quelle
            )
            rest = kern_transfer.restlaufzeit(self._konfiguration, nummer, quelle, jahr)
            luecke = talent.gipfelstaerke / koennen if koennen > 0 else 0.0

            zeile = QTreeWidgetItem(
                self._liste,
                [
                    fahrer.name,
                    str(fahrer.liga),
                    str(fahrer.alter_am(stichtag)),
                    f"{koennen:.0f}",
                    f"{talent.gipfelstaerke:.0f}",
                    f"{luecke:.1f}x" if koennen > 0 else "-",
                    _euro(angebot.gehalt),
                    _euro(angebot.abloese) if angebot.abloese else "frei",
                    f"{rest} Saisons" if rest else "laeuft aus",
                ],
            )
            zeile.setData(0, Qt.UserRole, nummer)
            for spalte in (1, 2, 3, 4, 5, 6, 7):
                zeile.setTextAlignment(spalte, Qt.AlignRight | Qt.AlignVCenter)

        self._liste.setSortingEnabled(True)
        for spalte in range(self._liste.columnCount()):
            self._liste.resizeColumnToContents(spalte)
        self._zeichne_kopf()

    def _zeichne_kopf(self) -> None:
        karriere = self._lauf.karriere
        anzahl = self._liste.topLevelItemCount()
        self._hinweis.setText(
            f"<b>{anzahl} Fahrer</b> sind im Winter {self._lauf.jahr + 1} zu haben. "
            "Wessen Vertrag auslaeuft, kostet keine Abloese; wer noch laeuft, schon.<br>"
            "<b>Ein neuer Fahrer bringt ein leeres, nicht upgegradetes Auto mit</b> - "
            "alles, was Sie in das Auto seines Vorgaengers gesteckt haben, ist damit weg. "
            "Die Spalte <i>Luecke</i> zeigt Potential geteilt durch Koennen: alles ueber "
            "1 heisst, da kommt noch etwas."
        )
        if karriere is None:
            self._konto.setText("")
            self._angebot.setEnabled(False)
            return
        self._konto.setText(
            f"Konto: <b>{_euro(karriere.konto.geld)}</b> - "
            f"Gehaelter bisher {_euro(karriere.gehaltssumme)} je Saison"
        )
        self._angebot.setEnabled(True)

    # -- Angebot -----------------------------------------------------------
    def _mache_angebot(self) -> None:
        zeile = self._liste.currentItem()
        karriere = self._lauf.karriere
        if zeile is None or karriere is None:
            QMessageBox.information(
                self, "Kein Fahrer gewaehlt", "Waehlen Sie einen Fahrer aus der Liste."
            )
            return
        nummer = int(zeile.data(0, Qt.UserRole))
        welt = self._lauf.welt
        fahrer = welt.fahrer[nummer]
        jahr = self._lauf.jahr + 1
        quelle = self._lauf.seedquelle

        vorschlag = kern_transfer.angebot(self._konfiguration, welt, nummer, jahr, quelle)
        dialog = Angebotsdialog(self._konfiguration, fahrer.name, vorschlag, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return

        meins = kern_transfer.angebot(
            self._konfiguration,
            welt,
            nummer,
            jahr,
            quelle,
            gehalt=dialog.gehalt,
            laufzeit=dialog.laufzeit,
        )
        eigene = welt.spielerfahrer
        antwort = kern_transfer.pruefe(
            self._konfiguration,
            welt,
            nummer,
            meins,
            # Er kaeme in die Liga des Autos, das frei wird - und in ein
            # leeres Auto, deshalb steht da eine Null.
            ziel_liga=eigene[0].liga if eigene else fahrer.liga,
            ziel_auto_wert=0.0,
            jahr=jahr,
            seedquelle=quelle,
            # Bekanntheit als Anteil der Skala (Punkt 5).
            bekanntheit=self._lauf.popularitaet.stand(nummer)
            / max(self._konfiguration.wert("skala", "maximum"), 1),
        )
        if not antwort.angenommen:
            QMessageBox.information(self, f"{fahrer.name} lehnt ab", antwort.grund)
            return
        if meins.abloese > karriere.konto.geld:
            QMessageBox.warning(
                self,
                "Abloese nicht gedeckt",
                f"{fahrer.name} wuerde unterschreiben, aber die Abloese von "
                f"{_euro(meins.abloese)} uebersteigt Ihr Konto "
                f"({_euro(karriere.konto.geld)}).",
            )
            return

        karriere.verpflichte(
            nummer, gehalt=meins.gehalt, laufzeit=meins.laufzeit, abloese=meins.abloese
        )
        QMessageBox.information(
            self,
            f"{fahrer.name} unterschreibt",
            f"{fahrer.name} faehrt ab {jahr} fuer Sie - "
            f"{_euro(meins.gehalt)} je Saison ueber {meins.laufzeit} Saisons."
            + (f"\n\nAbloese gezahlt: {_euro(meins.abloese)}" if meins.abloese else "")
            + "\n\nEr bringt ein leeres Auto mit.",
        )
        self.verpflichtet.emit(nummer)
        self.aktualisiere()

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def liste(self) -> QTreeWidget:
        return self._liste

    @property
    def knopf_angebot(self) -> QPushButton:
        return self._angebot
