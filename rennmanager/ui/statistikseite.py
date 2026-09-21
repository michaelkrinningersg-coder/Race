"""Seite fuer die Statistiken (GDD 13).

"Rundenrekorde je Strecke und Liga in Tausendsteln. Karriere: Siege,
Podien, Pole-Positions, schnellste Runden, Gesamtpunkte je Liga und
Saison. Historie aller Saisons und Ligen."

Drei Ansichten in einer Seite, umschaltbar:

* **Rundenrekorde** - je Strecke die schnellste Runde jeder Liga
* **Bestenliste** - die Karrierezahlen aller Fahrer, nach einem Merkmal
  geordnet
* **Historie** - der Endstand einer Saison in einer Liga
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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

# Die Bestmarken ueber alle Ligen hinweg.
ALLE_LIGEN = 0

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
    "Beste Liga",
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
        self._ansicht.addItem("Rundenrekorde je Strecke und Liga", REKORDE)
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

        # Bestmarken: erst insgesamt, dann Liga fuer Liga. Mit Pfeilen zum
        # Durchschalten - 20 Ligen einzeln aus einer Liste zu klicken ist
        # umstaendlich, wenn man sie vergleichen will.
        self._bestliga = QComboBox()
        self._bestliga.addItem("Insgesamt", ALLE_LIGEN)
        for nummer in range(1, self._konfiguration.wert("ligen", "anzahl") + 1):
            self._bestliga.addItem(
                f"Liga {nummer} - {self._konfiguration.ligenname(nummer)}", nummer
            )
        self._bestliga.currentIndexChanged.connect(self.aktualisiere)

        self._zurueck = QPushButton("\u2190")
        self._zurueck.setFixedWidth(28)
        self._zurueck.setToolTip("Eine Liga zurueck")
        self._zurueck.clicked.connect(lambda: self._blaettere(-1))
        self._vor = QPushButton("\u2192")
        self._vor.setFixedWidth(28)
        self._vor.setToolTip("Eine Liga weiter")
        self._vor.clicked.connect(lambda: self._blaettere(1))

        self._hinweis = QLabel()

        zeile.addWidget(QLabel("Ansicht:"))
        zeile.addWidget(self._ansicht)
        zeile.addWidget(self._strecke)
        zeile.addWidget(self._merkmal)
        zeile.addWidget(self._saison)
        zeile.addWidget(self._lage)
        zeile.addWidget(self._zurueck)
        zeile.addWidget(self._bestliga)
        zeile.addWidget(self._vor)
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
        for knopf in (self._zurueck, self._bestliga, self._vor):
            knopf.setVisible(art == BESTMARKEN)
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
        strecke = self._strecke.currentData()
        self._kasten.setTitle(f"Rundenrekorde - {strecke}")
        self._tabelle.setColumnCount(6)
        self._tabelle.setHeaderLabels(
            ["Liga", "Zeit", "Rueckstand", "Fahrer", "Saison", "Rennen"]
        )

        rekorde = self._statistik.rekorde_je_strecke(strecke)
        if not rekorde:
            self._hinweis.setText("Noch keine Runde gefahren.")
            return
        self._hinweis.setText(f"{len(self._statistik.rekorde)} Rekorde insgesamt")

        bestzeit = rekorde[0].zeit_ms
        for rekord in rekorde:
            fahrer = self._welt.fahrer[rekord.fahrer]
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    f"{rekord.liga} - {self._konfiguration.ligenname(rekord.liga)}",
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
        self._tabelle.setColumnCount(10)
        self._tabelle.setHeaderLabels(
            [
                "#",
                "Fahrer",
                "Liga",
                "Rennen",
                "Siege",
                "Podien",
                "Poles",
                "SR",
                "DNF",
                "Punkte",
            ]
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
                    str(fahrer.liga),
                    str(zahlen.rennen),
                    str(zahlen.siege),
                    str(zahlen.podien),
                    str(zahlen.poles),
                    str(zahlen.schnellste_runden),
                    str(zahlen.ausfaelle),
                    str(zahlen.punkte),
                ],
            )
            self._faerbe(zeile, fahrer)

    def _zeige_historie(self) -> None:
        jahr = self._saison.currentData()
        self._tabelle.setColumnCount(4)
        self._tabelle.setHeaderLabels(["Liga", "Meister", "Punkte", "Zweiter"])
        if jahr is None:
            self._kasten.setTitle("Historie")
            self._hinweis.setText("Noch keine Saison abgeschlossen.")
            return

        self._kasten.setTitle(f"Historie - Saison {jahr}")
        self._hinweis.setText(f"{len(self._statistik.saisons)} abgeschlossene Saisons")
        for liga in range(1, self._konfiguration.wert("ligen", "anzahl") + 1):
            abschluss = self._statistik.abschluss(jahr, liga)
            if abschluss is None:
                continue
            meister = self._welt.fahrer[abschluss.meister]
            zweiter = (
                self._welt.fahrer[abschluss.reihenfolge[1]].name
                if len(abschluss.reihenfolge) > 1
                else ""
            )
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    f"{liga} - {self._konfiguration.ligenname(liga)}",
                    meister.name,
                    str(abschluss.punkte[0]),
                    zweiter,
                ],
            )
            self._faerbe(zeile, meister)

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
        self._tabelle.setColumnCount(3 + len(BILANZSPALTEN))
        self._tabelle.setHeaderLabels(["#", "Fahrer", "Liga", *BILANZSPALTEN])
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
                    str(fahrer.liga),
                    str(bilanz.rennen),
                    str(bilanz.siege),
                    str(bilanz.podien),
                    str(bilanz.poles),
                    str(bilanz.schnellste_runden),
                    str(bilanz.ausfaelle),
                    _zahl(bilanz.punkte),
                    str(bilanz.bester_platz) if bilanz.bester_platz else "-",
                    str(bilanz.beste_liga) if bilanz.beste_liga else "-",
                ],
            )
            self._faerbe(zeile, fahrer)

    # -- Bestmarken (Punkt 25) ---------------------------------------------
    def _blaettere(self, richtung: int) -> None:
        """Eine Liga vor oder zurueck, ohne die Liste aufzuklappen."""
        stelle = self._bestliga.currentIndex() + richtung
        if 0 <= stelle < self._bestliga.count():
            self._bestliga.setCurrentIndex(stelle)

    def _zeige_bestmarken(self) -> None:
        """Was in dieser Welt bisher am weitesten ging.

        Drei Gruppen: die Rundenrekorde je Strecke, die Bestmarken der
        Karriere ueber alle Fahrer und die besten Saisons aus der Historie.

        Waehlbar ist, ob das ueber alle Ligen gilt oder in einer einzelnen.
        Insgesamt gewinnt fast immer Liga 1 - dort faehrt das staerkste
        Feld. Wer wissen will, wer in Liga 14 am meisten gewonnen hat, muss
        die Liga einzeln sehen koennen.
        """
        liga = self._bestliga.currentData()
        wo = "insgesamt" if liga == ALLE_LIGEN else f"Liga {liga}"
        self._kasten.setTitle(f"Bestmarken - {wo}")
        self._tabelle.setColumnCount(4)
        self._tabelle.setHeaderLabels(["Marke", "Wert", "Fahrer", "Wo und wann"])
        self._tabelle.setRootIsDecorated(True)
        self._zurueck.setEnabled(self._bestliga.currentIndex() > 0)
        self._vor.setEnabled(
            self._bestliga.currentIndex() < self._bestliga.count() - 1
        )

        zeilen = (
            self._marken_der_strecken(liga)
            + self._marken_der_karriere(liga)
            + self._marken_der_saisons(liga)
        )
        if not zeilen:
            self._hinweis.setText(
                "Noch kein Rennen gefahren."
                if liga == ALLE_LIGEN
                else f"In Liga {liga} ist noch kein Rennen gefahren."
            )
            return
        self._hinweis.setText(f"{len(zeilen)} Bestmarken")
        for marke, wert, fahrer, wo in zeilen:
            zeile = QTreeWidgetItem(self._tabelle, [marke, wert, "", wo])
            if fahrer is not None:
                zeile.setText(2, fahrer.name)
                self._faerbe(zeile, fahrer, spalte=2)

    def _marken_der_strecken(self, liga: int = ALLE_LIGEN) -> list[tuple]:
        """Die schnellste Runde je Strecke, in einer Liga oder ueber alle."""
        marken = []
        for eintrag in self._konfiguration.strecken:
            rekorde = self._statistik.rekorde_je_strecke(eintrag["name"])
            if liga != ALLE_LIGEN:
                rekorde = tuple(r for r in rekorde if r.liga == liga)
            if not rekorde:
                continue
            beste = min(rekorde, key=lambda r: r.zeit_ms)
            marken.append(
                (
                    f"Schnellste Runde in {eintrag['name']}",
                    formatiere_dauer(beste.zeit_ms),
                    self._welt.fahrer[beste.fahrer],
                    f"Liga {beste.liga}, Saison {beste.saison}, Rennen {beste.rennen}",
                )
            )
        return marken

    def _marken_der_karriere(self, liga: int = ALLE_LIGEN) -> list[tuple]:
        """Die Bestmarken ueber alle Fahrer.

        Insgesamt zaehlen die Karrierezahlen, die alles zusammenrechnen.
        Fuer eine einzelne Liga taugen die nicht: Sie wissen nicht, in
        welcher Liga ein Sieg fiel. Dort kommen die Zahlen deshalb aus der
        Historie, die je Saison und Liga eine Abschlusstabelle fuehrt -
        also aus den **abgeschlossenen** Saisons dieser Liga.
        """
        if liga == ALLE_LIGEN:
            quelle = self._statistik.karriere.values()
            zusatz = ""
        else:
            quelle = self._statistik.karriere_in_liga(liga).values()
            zusatz = f" in Liga {liga}"
        zahlen = [z for z in quelle if z.rennen]
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
                    f"Meiste {name} (Karriere{zusatz})",
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
                        f"Beste Siegquote (ab {MINDESTRENNEN} Rennen{zusatz})",
                        f"{beste.siegquote:.1%}".replace(".", ","),
                        self._welt.fahrer[beste.fahrer],
                        f"{beste.siege} Siege in {beste.rennen} Rennen",
                    )
                )
        return marken

    def _marken_der_saisons(self, liga: int = ALLE_LIGEN) -> list[tuple]:
        """Die besten einzelnen Saisons aus der Historie.

        Hier steht die Liga wirklich dabei: Die Historie fuehrt je Saison
        und Liga eine eigene Abschlusstabelle.
        """
        zeilen = [
            (abschluss, zeile)
            for abschluss in self._statistik.historie
            if liga == ALLE_LIGEN or abschluss.liga == liga
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
                    f"Liga {abschluss.liga}, Saison {abschluss.saison}",
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
    def bestmarkenliga(self) -> QComboBox:
        return self._bestliga

    @property
    def knopf_liga_zurueck(self) -> QPushButton:
        return self._zurueck

    @property
    def knopf_liga_vor(self) -> QPushButton:
        return self._vor

    @property
    def merkmalauswahl(self) -> QComboBox:
        return self._merkmal
