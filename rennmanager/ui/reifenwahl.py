"""Die Reifenwahl vor dem Rennen (Punkt 39).

Der Spieler fuehrt ein Team mit vier Fahrern; welche Mischungsfolge jeder
von ihnen faehrt, darf er selbst bestimmen. Zur Wahl steht, was die
Vorausberechnung vor dem Start als zulaessig ermittelt hat - nichts
anderes, damit niemand eine Strategie faehrt, die rechnerisch gar nicht
aufgeht.

**Vor dem Start, nicht waehrend des Rennens.** Der Rennverlauf wird in
einem Stueck gerechnet und danach nur noch abgespielt (GDD 15); ein
Eingriff mitten im Rennen muesste ihn ab dieser Stelle neu rechnen. Wer
nichts waehlt, faehrt das, was das Team ihm zuteilt.

Die Reifen des **Qualifyings** stehen hier nicht zur Wahl: Dort gilt eine
feste Regel - immer weich, im Nassen der passende Satz.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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

from rennmanager.kern import strategie as kern_strategie
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import schriftfarbe

# Der Eintrag, der die Wahl wieder ans Team abgibt.
TEAM = "Team entscheidet"
# Spalten der Liste.
SPALTE_FAHRER = 0
SPALTE_START = 1
SPALTE_WAHL = 2
# So viele Varianten stehen zur Wahl. Es sind oft ueber hundert; eine
# Liste mit hundert Eintraegen waehlt niemand durch, und was weit hinten
# steht, ist ohnehin die schlechtere Wahl.
HOECHSTENS = 12
FARBE_HINWEIS = "#8b93a1"


def beschriftung(variante, bestzeit_ms: float) -> str:
    """Wie eine Variante in der Auswahlliste heisst.

    Folge, Zahl der Stopps und Rueckstand auf die beste - das sind die
    drei Zahlen, nach denen man waehlt.
    """
    rueckstand = (variante.zeit_ms - bestzeit_ms) / 1000.0
    stopps = variante.anzahl_stopps
    wort = "Stopp" if stopps == 1 else "Stopps"
    if rueckstand < 0.05:
        return f"{variante.folge}  ·  {stopps} {wort}  ·  schnellste"
    return f"{variante.folge}  ·  {stopps} {wort}  ·  +{rueckstand:.1f} s"


class Reifenwahl(QGroupBox):
    """Laesst den Spieler die Strategie seiner Fahrer festlegen."""

    # Fahrernummer und gewaehlte Strategie; ``None`` gibt sie ans Team ab.
    gewaehlt = Signal(int, object)

    def __init__(
        self, konfiguration: Konfiguration, parent: QWidget | None = None
    ) -> None:
        super().__init__("Reifenwahl fuers Rennen", parent)
        self._konfiguration = konfiguration
        self._varianten: list = []
        self._runden = 0

        spalte = QVBoxLayout(self)

        kopf = QHBoxLayout()
        self._lage = QLabel()
        kopf.addWidget(self._lage)
        kopf.addStretch(1)
        self._hinweis = QLabel()
        self._hinweis.setStyleSheet(f"color: {FARBE_HINWEIS};")
        kopf.addWidget(self._hinweis)
        spalte.addLayout(kopf)

        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(["Fahrer", "Start", "Strategie"])
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        self._liste.setColumnWidth(SPALTE_WAHL, 320)
        spalte.addWidget(self._liste)

    # -- Fuellen -----------------------------------------------------------
    def zeige(self, vorbereitung, welt, runden: int) -> None:
        """Baut die Liste aus einer fertigen Rennvorbereitung.

        :param vorbereitung: aus ``kern.saison.vor_dem_rennen``
        :param welt: fuer die Namen der eigenen Fahrer
        """
        self._liste.clear()
        self._runden = runden
        strategien = vorbereitung.strategien
        self._varianten = list(strategien.varianten[:HOECHSTENS])

        lagen = " → ".join(strategien.lagen)
        pflicht = (
            "zwei Mischungen Pflicht"
            if strategien.pflicht_zwei
            else "keine Mischungspflicht"
        )
        self._lage.setText(f"<b>{lagen}</b> · {pflicht}")
        self._hinweis.setText(
            f"{len(strategien.varianten)} Strategien sind rechnerisch tragfaehig; "
            f"die {len(self._varianten)} besten stehen zur Wahl."
        )

        namen = {f.nummer: f.name for f in welt.fahrer}
        eigene = {f.nummer for f in welt.spielerfahrer}
        bestzeit = self._varianten[0].zeit_ms if self._varianten else 0.0

        for stelle, teilnehmer in enumerate(vorbereitung.teilnehmer):
            if teilnehmer.nummer not in eigene:
                continue
            zeile = QTreeWidgetItem(
                self._liste,
                [
                    namen.get(teilnehmer.nummer, teilnehmer.kuerzel),
                    f"P{teilnehmer.startplatz}",
                    "",
                ],
            )
            zeile.setForeground(SPALTE_FAHRER, schriftfarbe(teilnehmer.farbe))
            zeile.setData(SPALTE_FAHRER, Qt.UserRole, teilnehmer.nummer)
            self._liste.setItemWidget(
                zeile,
                SPALTE_WAHL,
                self._auswahlfeld(
                    teilnehmer.nummer, strategien.je_auto[stelle], bestzeit
                ),
            )
        for spalte in (SPALTE_FAHRER, SPALTE_START):
            self._liste.resizeColumnToContents(spalte)

    def _auswahlfeld(self, nummer: int, vorgabe, bestzeit_ms: float) -> QComboBox:
        """Das Auswahlfeld eines Fahrers, mit dem Teamvorschlag obenan."""
        feld = QComboBox()
        folge = "-".join(m.kuerzel for m in vorgabe.mischungen)
        feld.addItem(f"{TEAM} ({folge})", None)
        for variante in self._varianten:
            feld.addItem(beschriftung(variante, bestzeit_ms), variante)
        feld.currentIndexChanged.connect(
            lambda _stelle, feld=feld, nummer=nummer: self._gewaehlt(nummer, feld)
        )
        return feld

    def _gewaehlt(self, nummer: int, feld: QComboBox) -> None:
        variante = feld.currentData()
        if variante is None:
            self.gewaehlt.emit(nummer, None)
            return
        self.gewaehlt.emit(
            nummer,
            kern_strategie.Strategie(
                mischungen=variante.mischungen, stopps=variante.stopps
            ),
        )

    # -- Fuer Tests --------------------------------------------------------
    @property
    def liste(self) -> QTreeWidget:
        return self._liste

    def feld_von(self, nummer: int) -> QComboBox | None:
        """Das Auswahlfeld dieses Fahrers, oder ``None``."""
        for stelle in range(self._liste.topLevelItemCount()):
            zeile = self._liste.topLevelItem(stelle)
            if zeile.data(SPALTE_FAHRER, Qt.UserRole) == nummer:
                return self._liste.itemWidget(zeile, SPALTE_WAHL)
        return None
