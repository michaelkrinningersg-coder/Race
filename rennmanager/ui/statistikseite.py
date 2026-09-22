"""Seite fuer die Statistiken (GDD 13).

"Rundenrekorde je Strecke in Tausendsteln. Karriere: Siege, Podien,
Pole-Positions, schnellste Runden, Gesamtpunkte je Saison. Historie aller
Saisons."

Sechs Ansichten in einer Seite, umschaltbar:

* **Rundenrekorde** - je Strecke die schnellste Runde, Renn- und Qualirunde
* **Bestenliste** - die Karrierezahlen aller Fahrer, nach einem Merkmal
  geordnet
* **Historie** - der Endstand einer Saison
* **Strecken- und Wetterbilanz** sowie **Bestmarken**
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

from rennmanager.kern.statistik import Statistik
from rennmanager.kern.welt import Welt
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.tabellen import schriftfarbe, verbinde_fahrerkarte

REKORDE = "rekorde"
BESTENLISTE = "bestenliste"
HISTORIE = "historie"
# Punkt 21, 23 und 25.
STRECKENBILANZ = "streckenbilanz"
WETTERBILANZ = "wetterbilanz"
BESTMARKEN = "bestmarken"

# Die Spalten einer Bilanz, ueberall gleich (Punkte 21 und 23).
BILANZSPALTEN = (
    "Starts",
    "Siege",
    "Podien",
    "Poles",
    "SR",
    "DNF",
    "Punkte",
    "Bester",
)

# Merkmale der Bestenliste - Schluessel in Karrierezahlen, Anzeigename.
# Ab so vielen Rennen zaehlt eine Quote als Bestmarke - sonst gewinnt,
# wer einmal gefahren und einmal gewonnen hat.
MINDESTRENNEN = 20

def _zahl(wert: float) -> str:
    """Ganze Zahl mit Punkt als Tausendertrennung."""
    return f"{round(wert):,}".replace(",", ".")


MERKMALE = (
    ("siege", "Siege"),
    ("punkte", "Punkte"),
    ("podien", "Podien"),
    ("poles", "Pole-Positions"),
    ("schnellste_runden", "Schnellste Runden"),
    # Punkt 102: Wer das Rennen bestimmt hat, statt nur wer es gewonnen hat.
    ("fuehrungsrunden", "Fuehrungsrunden"),
    ("rennen", "Rennen"),
    ("ausfaelle", "Ausfaelle"),
)


class Statistikseite(QWidget):
    """Rundenrekorde, Karrierezahlen und Historie."""

    # Doppelklick auf einen Namen: Das Fenster oeffnet die Fahrerkarte.
    fahrerkarte_gewuenscht = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        statistik: Statistik,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        self._statistik = statistik

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())
        spalte.addWidget(self._baue_tabelle(), stretch=1)
        # Blendet die Filter aus, die zur Startansicht nicht gehoeren, und
        # fuellt die Tabelle.
        self._ansicht_gewechselt()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._ansicht = QComboBox()
        self._ansicht.addItem("Rundenrekorde je Strecke", REKORDE)
        self._ansicht.addItem("Bestenliste der Karriere", BESTENLISTE)
        self._ansicht.addItem("Historie aller Saisons", HISTORIE)
        self._ansicht.addItem("Streckenbilanz aller Fahrer", STRECKENBILANZ)
        self._ansicht.addItem("Wetterbilanz aller Fahrer", WETTERBILANZ)
        self._ansicht.addItem("Bestmarken", BESTMARKEN)
        self._ansicht.currentIndexChanged.connect(self._ansicht_gewechselt)

        # Je Ansicht ein eigener zweiter Filter.
        self._strecke = QComboBox()
        for eintrag in self._konfiguration.strecken:
            self._strecke.addItem(f"{eintrag['nummer']:>2}  {eintrag['name']}", eintrag["name"])
        self._strecke.currentIndexChanged.connect(self.aktualisiere)

        self._merkmal = QComboBox()
        for schluessel, name in MERKMALE:
            self._merkmal.addItem(name, schluessel)
        self._merkmal.currentIndexChanged.connect(self.aktualisiere)

        self._saison = QComboBox()
        self._saison.currentIndexChanged.connect(self.aktualisiere)

        self._lage = QComboBox()
        for lage in self._konfiguration.wert("wetter", "kette"):
            self._lage.addItem(lage, lage)
        self._lage.currentIndexChanged.connect(self.aktualisiere)

        self._hinweis = QLabel()

        zeile.addWidget(QLabel("Ansicht:"))
        zeile.addWidget(self._ansicht)
        zeile.addWidget(self._strecke)
        zeile.addWidget(self._merkmal)
        zeile.addWidget(self._saison)
        zeile.addWidget(self._lage)
        zeile.addWidget(self._hinweis, stretch=1)
        return zeile

    def _baue_tabelle(self) -> QWidget:
        self._kasten = QGroupBox("Statistik")
        spalte = QVBoxLayout(self._kasten)
        self._tabelle = QTreeWidget()
        self._tabelle.setRootIsDecorated(False)
        self._tabelle.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._tabelle, self.fahrerkarte_gewuenscht.emit)
        spalte.addWidget(self._tabelle)
        return self._kasten

    # -- Anzeige -----------------------------------------------------------
    def _ansicht_gewechselt(self, *_) -> None:
        art = self._ansicht.currentData()
        self._strecke.setVisible(art in (REKORDE, STRECKENBILANZ))
        self._merkmal.setVisible(art == BESTENLISTE)
        self._saison.setVisible(art == HISTORIE)
        self._lage.setVisible(art == WETTERBILANZ)
        self.aktualisiere()

    def aktualisiere(self, *_) -> None:
        """Liest die Statistik neu ein - nach jedem Rennwochenende noetig."""
        self._fuelle_saisons()
        art = self._ansicht.currentData()
        self._tabelle.clear()
        if art == REKORDE:
            self._zeige_rekorde()
        elif art == BESTENLISTE:
            self._zeige_bestenliste()
        elif art == STRECKENBILANZ:
            self._zeige_streckenbilanz()
        elif art == WETTERBILANZ:
            self._zeige_wetterbilanz()
        elif art == BESTMARKEN:
            self._zeige_bestmarken()
        else:
            self._zeige_historie()
        for spalte in range(self._tabelle.columnCount()):
            self._tabelle.resizeColumnToContents(spalte)

    def _fuelle_saisons(self) -> None:
        saisons = list(self._statistik.saisons)
        vorhanden = [self._saison.itemData(i) for i in range(self._saison.count())]
        if vorhanden == saisons:
            return
        gewaehlt = self._saison.currentData()
        self._saison.blockSignals(True)
        self._saison.clear()
        for jahr in saisons:
            self._saison.addItem(f"Saison {jahr}", jahr)
        if gewaehlt in saisons:
            self._saison.setCurrentIndex(saisons.index(gewaehlt))
        self._saison.blockSignals(False)

    def _zeige_rekorde(self) -> None:
        """Renn- und Qualifyingrekord der gewaehlten Strecke (Punkt 93)."""
        strecke = self._strecke.currentData()
        self._kasten.setTitle(f"Rundenrekorde - {strecke}")
        self._tabelle.setColumnCount(6)
        self._tabelle.setHeaderLabels(
            ["Session", "Zeit", "Rueckstand", "Fahrer", "Saison", "Rennen"]
        )

        rekorde = [
            (name, rekord)
            for name, rekord in (
                ("Rennrunde", self._statistik.rekord(strecke)),
                ("Qualirunde", self._statistik.qualirekord(strecke)),
            )
            if rekord is not None
        ]
        if not rekorde:
            self._hinweis.setText("Noch keine Runde gefahren.")
            return
        self._hinweis.setText(f"{len(self._statistik.rekorde)} Streckenrekorde")

        bestzeit = min(rekord.zeit_ms for _, rekord in rekorde)
        for name, rekord in rekorde:
            fahrer = self._welt.fahrer[rekord.fahrer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    name,
                    formatiere_dauer(rekord.zeit_ms),
                    "" if rekord.zeit_ms == bestzeit
                    else formatiere_rueckstand(rekord.zeit_ms - bestzeit),
                    fahrer.name,
                    str(rekord.saison),
                    str(rekord.rennen),
                ],
            )
            self._faerbe(zeile, fahrer)

    def _zeige_bestenliste(self) -> None:
        merkmal = self._merkmal.currentData()
        name = dict(MERKMALE)[merkmal]
        self._kasten.setTitle(f"Bestenliste nach {name}")
        self._tabelle.setColumnCount(11)
        self._tabelle.setHeaderLabels(
            [
                "#",
                "Fahrer",
                "Rennen",
                "Siege",
                "Podien",
                "Poles",
                "SR",
                "DNF",
                "Punkte",
                "Fuehrung",
                "Anteil",
            ]
        )
        # Punkt 102: Die Spalte zaehlt Runden, keine Rennen - der Tooltip
        # sagt, woran sie haengt.
        self._tabelle.headerItem().setToolTip(
            9,
            "Runden, die dieser Fahrer als Erster an der Start/Ziel-Linie "
            "abgeschlossen hat, ueber die ganze Karriere.",
        )
        self._tabelle.headerItem().setToolTip(
            10, "Anteil an allen Runden, die er gefahren ist."
        )

        beste = self._statistik.bestenliste(merkmal, anzahl=50)
        if not beste:
            self._hinweis.setText("Noch kein Rennen gefahren.")
            return
        self._hinweis.setText(f"{len(self._statistik.karriere)} Fahrer gewertet")

        for platz, zahlen in enumerate(beste, start=1):
            fahrer = self._welt.fahrer[zahlen.fahrer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    str(platz),
                    fahrer.name,
                    str(zahlen.rennen),
                    str(zahlen.siege),
                    str(zahlen.podien),
                    str(zahlen.poles),
                    str(zahlen.schnellste_runden),
                    str(zahlen.ausfaelle),
                    str(zahlen.punkte),
                    str(zahlen.fuehrungsrunden),
                    (
                        f"{zahlen.fuehrungsanteil:.1%}"
                        if zahlen.gefahrene_runden
                        else "-"
                    ),
                ],
            )
            self._faerbe(zeile, fahrer)

    def _zeige_historie(self) -> None:
        """Die Abschlusstabelle einer beendeten Saison (GDD 13)."""
        jahr = self._saison.currentData()
        self._tabelle.setColumnCount(9)
        self._tabelle.setHeaderLabels(
            ["#", "Fahrer", "Punkte", "Siege", "Podien", "Poles", "SR", "DNF", "Rennen"]
        )
        if jahr is None:
            self._kasten.setTitle("Historie")
            self._hinweis.setText("Noch keine Saison abgeschlossen.")
            return

        abschluss = self._statistik.abschluss(jahr)
        self._kasten.setTitle(f"Historie - Saison {jahr}")
        self._hinweis.setText(f"{len(self._statistik.saisons)} abgeschlossene Saisons")
        if abschluss is None:  # pragma: no cover - die Auswahl kennt nur Saisons
            return
        for zeile_der_saison in abschluss.zeilen:
            fahrer = self._welt.fahrer[zeile_der_saison.fahrer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    str(zeile_der_saison.platz),
                    fahrer.name,
                    _zahl(zeile_der_saison.punkte),
                    str(zeile_der_saison.siege),
                    str(zeile_der_saison.podien),
                    str(zeile_der_saison.poles),
                    str(zeile_der_saison.schnellste_runden),
                    str(zeile_der_saison.ausfaelle),
                    str(zeile_der_saison.rennen),
                ],
            )
            self._faerbe(zeile, fahrer)

    # -- Bilanzen (Punkte 21 und 23) ---------------------------------------
    def _zeige_streckenbilanz(self) -> None:
        strecke = self._strecke.currentData()
        self._kasten.setTitle(f"Streckenbilanz - {strecke}")
        self._zeige_bilanzen(
            self._statistik.bilanzen_auf(strecke),
            f"Auf {strecke} hat noch niemand ein Rennen gefahren.",
        )

    def _zeige_wetterbilanz(self) -> None:
        lage = self._lage.currentData()
        self._kasten.setTitle(f"Wetterbilanz - {lage}")
        self._zeige_bilanzen(
            self._statistik.bilanzen_bei(lage),
            f"Bei {lage} ist noch kein Rennen gefahren worden.",
        )

    def _zeige_bilanzen(self, bilanzen: dict, leer: str) -> None:
        """Eine Bilanztabelle ueber alle Fahrer, bester zuerst."""
        self._tabelle.setColumnCount(2 + len(BILANZSPALTEN))
        self._tabelle.setHeaderLabels(["#", "Fahrer", *BILANZSPALTEN])
        if not bilanzen:
            self._hinweis.setText(leer)
            return
        self._hinweis.setText(f"{len(bilanzen)} Fahrer gewertet")

        # Sortiert nach Siegen, dann Podien, dann Punkten - wie man eine
        # Bilanz liest.
        geordnet = sorted(
            bilanzen.items(),
            key=lambda paar: (-paar[1].siege, -paar[1].podien, -paar[1].punkte),
        )
        for platz, (nummer, bilanz) in enumerate(geordnet, start=1):
            fahrer = self._welt.fahrer[nummer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    str(platz),
                    fahrer.name,
                    str(bilanz.rennen),
                    str(bilanz.siege),
                    str(bilanz.podien),
                    str(bilanz.poles),
                    str(bilanz.schnellste_runden),
                    str(bilanz.ausfaelle),
                    _zahl(bilanz.punkte),
                    str(bilanz.bester_platz) if bilanz.bester_platz else "-",
                ],
            )
            self._faerbe(zeile, fahrer)

    # -- Bestmarken (Punkt 25) ---------------------------------------------
    def _zeige_bestmarken(self) -> None:
        """Was in dieser Welt bisher am weitesten ging.

        Drei Gruppen: die Rundenrekorde je Strecke, die Bestmarken der
        Karriere ueber alle Fahrer und die besten Saisons aus der
        Historie.
        """
        self._kasten.setTitle("Bestmarken")
        self._tabelle.setColumnCount(4)
        self._tabelle.setHeaderLabels(["Marke", "Wert", "Fahrer", "Wo und wann"])
        self._tabelle.setRootIsDecorated(True)

        zeilen = (
            self._marken_der_strecken()
            + self._marken_der_karriere()
            + self._marken_der_saisons()
        )
        if not zeilen:
            self._hinweis.setText("Noch kein Rennen gefahren.")
            return
        self._hinweis.setText(f"{len(zeilen)} Bestmarken")
        for marke, wert, fahrer, wo in zeilen:
            zeile = QTreeWidgetItem(self._tabelle, [marke, wert, "", wo])
            if fahrer is not None:
                zeile.setText(2, fahrer.name)
                self._faerbe(zeile, fahrer, spalte=2)

    def _marken_der_strecken(self) -> list[tuple]:
        """Die schnellste Rennrunde je Strecke."""
        marken = []
        for eintrag in self._konfiguration.strecken:
            beste = self._statistik.rekord(eintrag["name"])
            if beste is None:
                continue
            marken.append(
                (
                    f"Schnellste Runde in {eintrag['name']}",
                    formatiere_dauer(beste.zeit_ms),
                    self._welt.fahrer[beste.fahrer],
                    f"Saison {beste.saison}, Rennen {beste.rennen}",
                )
            )
        return marken

    def _marken_der_karriere(self) -> list[tuple]:
        """Die Bestmarken ueber alle Fahrer."""
        zahlen = [z for z in self._statistik.karriere.values() if z.rennen]
        if not zahlen:
            return []
        marken = []
        for schluessel, name in MERKMALE:
            if schluessel in ("rennen", "ausfaelle"):
                continue
            beste = max(zahlen, key=lambda z: getattr(z, schluessel))
            wert = getattr(beste, schluessel)
            if not wert:
                continue
            marken.append(
                (
                    f"Meiste {name} (Karriere)",
                    _zahl(wert),
                    self._welt.fahrer[beste.fahrer],
                    f"in {beste.rennen} Rennen",
                )
            )
        # Die Siegquote nur bei genug Rennen - sonst gewinnt, wer einmal
        # gefahren und einmal gewonnen hat.
        genug = [z for z in zahlen if z.rennen >= MINDESTRENNEN]
        if genug:
            beste = max(genug, key=lambda z: z.siegquote)
            if beste.siege:
                marken.append(
                    (
                        f"Beste Siegquote (ab {MINDESTRENNEN} Rennen)",
                        f"{beste.siegquote:.1%}".replace(".", ","),
                        self._welt.fahrer[beste.fahrer],
                        f"{beste.siege} Siege in {beste.rennen} Rennen",
                    )
                )
        return marken

    def _marken_der_saisons(self) -> list[tuple]:
        """Die besten einzelnen Saisons aus der Historie."""
        zeilen = [
            (abschluss, zeile)
            for abschluss in self._statistik.historie
            for zeile in abschluss.zeilen
        ]
        if not zeilen:
            return []
        marken = []
        for merkmal, name in (("punkte", "Punkte"), ("siege", "Siege")):
            abschluss, beste = max(zeilen, key=lambda paar: getattr(paar[1], merkmal))
            wert = getattr(beste, merkmal)
            if not wert:
                continue
            marken.append(
                (
                    f"Meiste {name} in einer Saison",
                    _zahl(wert),
                    self._welt.fahrer[beste.fahrer],
                    f"Saison {abschluss.saison}",
                )
            )
        return marken

    def _faerbe(self, zeile: QTreeWidgetItem, fahrer, spalte: int = 0) -> None:
        """Faerbt eine Zeile in der Teamfarbe und haengt die Fahrernummer an.

        :param spalte: wo die Farbe hin soll. Sonst steht sie auf Spalte 0,
            und die traegt in den meisten Ansichten nur eine Platzziffer.
            In den Bestmarken steht dort ein ganzer Satz - eine helle
            Teamfarbe machte ihn unlesbar.
        """
        zeile.setForeground(spalte, schriftfarbe(self._welt.team_von(fahrer).farbe))
        zeile.setData(0, Qt.UserRole, fahrer.nummer)
        if fahrer.ist_spieler:
            schrift = zeile.font(1)
            schrift.setBold(True)
            for spalte in range(self._tabelle.columnCount()):
                zeile.setFont(spalte, schrift)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def tabelle(self) -> QTreeWidget:
        return self._tabelle

    @property
    def ansicht(self) -> QComboBox:
        return self._ansicht

    @property
    def streckenauswahl(self) -> QComboBox:
        return self._strecke

    @property
    def merkmalauswahl(self) -> QComboBox:
        return self._merkmal
