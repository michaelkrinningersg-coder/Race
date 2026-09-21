"""Fahrersuche im Fensterkopf (Punkt 18).

400 Fahrer stehen in 10 Ligen. Wer einen bestimmten sucht, musste bisher
wissen, in welcher Liga er faehrt, dort hinblaettern und die Liste
durchsehen. Ein Suchfeld nimmt das ab: Name tippen, Eingabetaste, seine
Fahrerkarte geht auf.

Der Vorschlag nennt Name, Kuerzel, Liga und Team - Nachnamen gibt es
zweimal. Gesucht wird ueber die ganze Zeile, also auch ueber Team und
Liga: "Rosskamp" findet die vier Fahrer dieses Teams. Teiltreffer zaehlen
an beliebiger Stelle, wer nur "kamp" tippt, findet "Holtkamp".

**Fahrertreffer stehen vorn.** Wer einen Namen tippt und die
Eingabetaste drueckt, meint den Fahrer und nicht dessen Teamkollegen -
gemessen passten auf "kamp" 18 Zeilen, aber nur 2 ueber den Fahrernamen.

Das Feld sucht nur; geoeffnet wird die Karte vom Fenster, denn nur dort
kommen Statistik, Streckenkenntnis, Tabelle und Popularitaet zusammen.
"""

from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from rennmanager.konfiguration import Konfiguration

# So viele Vorschlaege zeigt die Klappliste hoechstens.
HOECHSTENS = 12


def eintrag(konfiguration: Konfiguration, fahrer, team) -> str:
    """Wie ein Fahrer in der Vorschlagsliste steht."""
    return (
        f"{fahrer.name} · {fahrer.kuerzel} · Liga {fahrer.liga} "
        f"({konfiguration.ligenname(fahrer.liga)}) · {team.name}"
    )


class Fahrersuche(QWidget):
    """Ein Suchfeld ueber alle Fahrer der Welt."""

    # Ein Fahrer wurde gewaehlt - das Fenster oeffnet seine Karte.
    fahrer_gewaehlt = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._nummer_zu: dict[str, int] = {}
        # Je Zeile nur der Teil, der den Fahrer nennt - fuer die Reihung.
        self._name_zu: dict[str, str] = {}

        zeile = QHBoxLayout(self)
        zeile.setContentsMargins(0, 0, 0, 0)
        self._feld = QLineEdit()
        self._feld.setPlaceholderText("Fahrer suchen - Name, Kuerzel (Strg+F)")
        self._feld.setClearButtonEnabled(True)
        self._feld.returnPressed.connect(self._uebernimm_erste)

        self._treffer = QCompleter(self)
        self._treffer.setCaseSensitivity(Qt.CaseInsensitive)
        # Teiltreffer an beliebiger Stelle: Wer "kamp" tippt, sucht
        # "Holtkamp" und nicht einen Fahrer, der mit "kamp" anfaengt.
        self._treffer.setFilterMode(Qt.MatchContains)
        self._treffer.setMaxVisibleItems(HOECHSTENS)
        self._treffer.activated[str].connect(self._waehle)
        self._feld.setCompleter(self._treffer)

        zeile.addWidget(QLabel("Suche:"))
        zeile.addWidget(self._feld, stretch=1)
        self.setze_welt(welt)

    # -- Daten -------------------------------------------------------------
    def setze_welt(self, welt) -> None:
        """Baut die Vorschlagsliste neu - nach Saisonwechsel und Editor."""
        self._nummer_zu = {}
        self._name_zu = {}
        for fahrer in welt.fahrer:
            text = eintrag(self._konfiguration, fahrer, welt.team_von(fahrer))
            self._nummer_zu[text] = fahrer.nummer
            self._name_zu[text] = f"{fahrer.name} {fahrer.kuerzel}".casefold()
        self._treffer.setModel(QStringListModel(sorted(self._nummer_zu), self))

    def treffer(self, text: str) -> tuple[int, ...]:
        """Die Fahrernummern, auf die eine Eingabe passt.

        Zuerst die, deren **Name oder Kuerzel** passt, dann die uebrigen -
        die ueber Team oder Liga. Sonst oeffnete die Eingabetaste bei
        "Fahrenkamp" einen Fahrer von Rosskamp Engineering.
        """
        gesucht = text.strip().casefold()
        if not gesucht:
            return ()
        ueber_namen = []
        daneben = []
        for zeile, nummer in sorted(self._nummer_zu.items()):
            if gesucht in self._name_zu[zeile]:
                ueber_namen.append(nummer)
            elif gesucht in zeile.casefold():
                daneben.append(nummer)
        return tuple(ueber_namen + daneben)

    # -- Bedienung ---------------------------------------------------------
    def _waehle(self, text: str) -> None:
        nummer = self._nummer_zu.get(text)
        if nummer is not None:
            self._feld.clear()
            self.fahrer_gewaehlt.emit(nummer)

    def _uebernimm_erste(self) -> None:
        """Eingabetaste ohne Auswahl: der erste Treffer.

        Wer den vollen Namen tippt und Enter drueckt, will nicht erst noch
        aus einer Liste waehlen.
        """
        gefunden = self.treffer(self._feld.text())
        if not gefunden:
            return
        self._feld.clear()
        self.fahrer_gewaehlt.emit(gefunden[0])

    def fokussiere(self) -> None:
        """Setzt den Schreibzeiger ins Feld (Strg+F)."""
        self._feld.setFocus()
        self._feld.selectAll()

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def feld(self) -> QLineEdit:
        return self._feld

    @property
    def vervollstaendigung(self) -> QCompleter:
        return self._treffer
