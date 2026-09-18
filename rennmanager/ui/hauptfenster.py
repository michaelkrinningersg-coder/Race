"""Hauptfenster der Anwendung.

Stand des Geruests (Schritt 1): Das Fenster zeigt, welche Konfiguration
geladen wurde, erlaubt die Eingabe eines Seeds fuer spaetere Simulationen
(GDD 15: Seed-Eingabe als Balancing-Werkzeug) und listet die im GDD noch
offenen Angaben auf.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager import __version__
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern import popularitaet as kern_popularitaet
from rennmanager.kern import spielstand as kern_spielstand
from rennmanager.kern import statistik as kern_statistik
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import welt as kern_welt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.editorseite import Editorseite
from rennmanager.ui.fahrerkarte import Fahrerkarte
from rennmanager.ui.fahrersuche import Fahrersuche
from rennmanager.ui.karriereseite import Karriereseite
from rennmanager.ui.karriereseite import beginne as beginne_karriere
from rennmanager.ui.rennwochenendeseite import Rennwochenendeseite
from rennmanager.ui.rundenseite import Rundenseite
from rennmanager.ui.saisonseite import Saisonseite
from rennmanager.ui.sponsorenseite import Sponsorenseite
from rennmanager.ui.startdialog import Startdialog
from rennmanager.ui.statistikseite import Statistikseite
from rennmanager.ui.streckenseite import Streckenseite
from rennmanager.ui.weltseite import Weltseite

# Qt-Spinboxen rechnen mit 32-Bit-Ganzzahlen; der Hauptseed wird in der
# Oberflaeche deshalb auf diesen Bereich begrenzt.
SEED_MAX = 2**31 - 1

# GDD 15: Spielstand in SQLite, eine Datei je Stand.
DATEIFILTER = "Rennmanager-Spielstand (*.sqlite);;Alle Dateien (*)"


class Hauptfenster(QMainWindow):
    """Fenster mit Konfigurationsuebersicht und Seed-Eingabe."""

    def __init__(self, konfiguration: Konfiguration) -> None:
        super().__init__()
        self._konfiguration = konfiguration
        self._seedquelle = Seedquelle(0)
        # Offene Fahrerkarten je Fahrernummer - ein Doppelklick auf
        # denselben Namen holt die vorhandene nach vorn, ein Neuaufbau des
        # Fensters schliesst sie.
        self._karten: dict[int, Fahrerkarte] = {}
        # Eine Welt je Fenster: 600 Autos, 150 Teams, 20 Ligen (GDD 12).
        self._welt = kern_welt.erzeuge(
            konfiguration,
            self._seedquelle.zweig("welt"),
            spielerliga=konfiguration.wert("ligen", "startliga"),
        )
        # Statistik und Streckenkenntnis ueberdauern die Saison (GDD 6 und
        # 13) und gehoeren deshalb dem Fenster, nicht dem Saisonlauf.
        self._karriere = None
        # Das Jahr der laufenden Saison; jeder Saisonwechsel zaehlt es
        # eines hoch (GDD 13).
        self._jahr = kern_karriere.startjahr(konfiguration)
        self._statistik = kern_statistik.Statistik(konfiguration)
        self._kenntnis = kern_streckenkenntnis.Streckenkenntnis(
            konfiguration, seedquelle=self._seedquelle.zweig("lerntempo")
        )
        # Punkt 5: Bekanntheit, gestreut aber nicht nach Ligastaerke.
        self._popularitaet = kern_popularitaet.Popularitaet(konfiguration)
        self._popularitaet.anfang(
            tuple(f.nummer for f in self._welt.fahrer),
            self._seedquelle.zweig("popularitaet"),
        )
        # Die KI bekommt ihre Streckenkenntnis einmal fest (GDD 12).
        kern_streckenkenntnis.setze_ki_anfang(
            konfiguration,
            self._welt,
            self._kenntnis,
            tuple(e["name"] for e in konfiguration.strecken),
            self._seedquelle.zweig("kikenntnis"),
        )

        self.setWindowTitle(f"Rennmanager {__version__}")
        self.resize(900, 640)

        self._baue_menue()
        self.setCentralWidget(self._baue_inhalt())
        self.statusBar().showMessage(
            f"Konfiguration geladen aus {konfiguration.quelle}"
        )

    # -- Aufbau ------------------------------------------------------------
    def _baue_menue(self) -> None:
        datei = self.menuBar().addMenu("&Datei")

        speichern = QAction("&Speichern ...", self)
        speichern.setShortcut("Ctrl+S")
        speichern.triggered.connect(self._speichere)
        datei.addAction(speichern)

        laden = QAction("&Laden ...", self)
        laden.setShortcut("Ctrl+O")
        laden.triggered.connect(self._lade)
        datei.addAction(laden)
        datei.addSeparator()

        # Punkt 18: Strg+F springt ins Suchfeld ueber den Reitern.
        suchen = QAction("Fahrer &suchen", self)
        suchen.setShortcut("Ctrl+F")
        suchen.triggered.connect(lambda: self._suche.fokussiere())
        datei.addAction(suchen)
        datei.addSeparator()

        neu = QAction("&Neue Karriere ...", self)
        neu.setShortcut("Ctrl+N")
        neu.triggered.connect(self.neue_karriere)
        datei.addAction(neu)
        datei.addSeparator()

        # Punkt 17: Schnellspeichern und -laden ohne Dialog. Wer ein
        # Wochenende neu fahren will, soll nicht jedes Mal durch einen
        # Dateibrowser muessen.
        schnell_speichern = QAction("&Schnellspeichern", self)
        schnell_speichern.setShortcut("F5")
        schnell_speichern.triggered.connect(self.schnellspeichern)
        datei.addAction(schnell_speichern)

        schnell_laden = QAction("Schnell&laden", self)
        schnell_laden.setShortcut("F9")
        schnell_laden.triggered.connect(self.schnellladen)
        datei.addAction(schnell_laden)
        datei.addSeparator()

        beenden = QAction("&Beenden", self)
        beenden.setShortcut("Ctrl+Q")
        beenden.triggered.connect(self.close)
        datei.addAction(beenden)

        hilfe = self.menuBar().addMenu("&Hilfe")
        ueber = QAction("&Ueber Rennmanager", self)
        ueber.triggered.connect(self._zeige_ueber)
        hilfe.addAction(ueber)

    def _baue_inhalt(self) -> QWidget:
        # Ein Neuaufbau ersetzt die Welt - offene Karten zeigten sonst
        # Fahrer, die es so nicht mehr gibt (Saisonwechsel, Editor,
        # geladener Spielstand).
        self._schliesse_fahrerkarten()
        self._reiter = QTabWidget()
        self._reiter.addTab(self._baue_uebersichtsseite(), "Uebersicht")
        self._streckenseite = Streckenseite(self._konfiguration)
        self._reiter.addTab(self._streckenseite, "Strecke")
        self._rundenseite = Rundenseite(self._konfiguration)
        self._reiter.addTab(self._rundenseite, "Runde")
        self._weltseite = Weltseite(self._konfiguration, self._welt, jahr=self._jahr)
        self._reiter.addTab(self._weltseite, "Welt")
        if getattr(self, "_karriere", None) is None:
            self._karriere = beginne_karriere(
                self._konfiguration,
                self._welt,
                self._seedquelle.zweig("karriere", self._jahr),
                self._jahr,
            )
        self._karriereseite = Karriereseite(self._konfiguration, self._karriere)
        # Punkt 17: Jeder Tageswechsel schreibt den Autosave.
        self._karriereseite.tag_gewechselt.connect(self.autosave)
        self._reiter.addTab(self._karriereseite, "Karriere")
        self._sponsorenseite = Sponsorenseite(
            self._konfiguration,
            self._karriere,
            self._seedquelle.zweig("sponsoren"),
            self._popularitaet,
        )
        self._reiter.addTab(self._sponsorenseite, "Sponsoren")
        self._saisonseite = Saisonseite(
            self._konfiguration,
            self._welt,
            seed=self._seedquelle.seed,
            statistik=self._statistik,
            kenntnis=self._kenntnis,
            tabellen=getattr(self, "_geladene_tabellen", None),
            gefahrene_rennen=getattr(self, "_gefahrene_rennen", 0),
            karriere=self._karriere,
            jahr=self._jahr,
            popularitaet=self._popularitaet,
        )
        self._saisonseite.saison_gewechselt.connect(self._saison_gewechselt)
        # Punkt 12: Das gefuehrte Wochenende ersetzt die Reiter Qualifying
        # und Rennen. Es steht vor der Saison, weil es der Weg ist, den
        # der Spieler jede zweite Woche geht.
        self._wochenendeseite = Rennwochenendeseite(
            self._konfiguration, self._saisonseite.lauf
        )
        self._wochenendeseite.wochenende_gefahren.connect(self._wochenende_gefahren)
        self._reiter.addTab(self._wochenendeseite, "Rennwochenende")
        self._reiter.addTab(self._saisonseite, "Saison")
        self._statistikseite = Statistikseite(
            self._konfiguration, self._welt, self._statistik
        )
        self._reiter.addTab(self._statistikseite, "Statistik")
        # GDD 15 nennt eine Debug-Ansicht unter den Balancing-Werkzeugen.
        self._editorseite = Editorseite(
            self._konfiguration,
            self._welt,
            self._kenntnis,
            popularitaet=self._popularitaet,
            karriere=self._karriere,
        )
        self._reiter.addTab(self._editorseite, "Editor")
        # Die Statistik waechst mit jedem Rennwochenende; beim Aufschlagen
        # der Seite wird sie deshalb neu gelesen.
        self._reiter.currentChanged.connect(self._reiter_gewechselt)
        self._verbinde_fahrerkarten()

        # Punkt 18: Die Suche steht ueber den Reitern, damit sie von
        # ueberall aus erreichbar ist.
        rahmen = QWidget()
        spalte = QVBoxLayout(rahmen)
        spalte.setContentsMargins(6, 4, 6, 0)
        self._suche = Fahrersuche(self._konfiguration, self._welt)
        self._suche.fahrer_gewaehlt.connect(self.oeffne_fahrerkarte)
        spalte.addWidget(self._suche)
        spalte.addWidget(self._reiter, stretch=1)
        return rahmen

    def _schliesse_fahrerkarten(self) -> None:
        for karte in getattr(self, "_karten", {}).values():
            karte.close()
        self._karten = {}

    def _verbinde_fahrerkarten(self) -> None:
        """Jede Liste mit Fahrernamen oeffnet dieselbe Karte.

        Die Seiten kennen die Karte nicht - sie melden nur eine
        Fahrernummer. Das Fenster oeffnet sie, weil nur es Statistik,
        Streckenkenntnis, Tabelle und Popularitaet zusammen hat.
        """
        for seite in (
            self._weltseite,
            self._wochenendeseite,
            self._saisonseite,
            self._statistikseite,
        ):
            seite.fahrerkarte_gewuenscht.connect(self.oeffne_fahrerkarte)

    def oeffne_fahrerkarte(self, nummer: int) -> Fahrerkarte:
        """Oeffnet die Karte eines Fahrers - nicht modal, mehrere zugleich.

        Eine schon offene Karte desselben Fahrers wird nach vorn geholt,
        statt sie ein zweites Mal zu bauen.
        """
        offen = self._karten.get(nummer)
        if offen is not None and offen.isVisible():
            offen.raise_()
            offen.activateWindow()
            return offen

        lauf = self._saisonseite.lauf
        karte = Fahrerkarte(
            self._konfiguration,
            self._welt,
            nummer,
            statistik=self._statistik,
            kenntnis=self._kenntnis,
            tabelle=lauf.tabelle(self._welt.fahrer[nummer].liga),
            strecken=lauf.strecken,
            popularitaet=self._popularitaet,
            jahr=lauf.jahr,
            parent=self,
        )
        self._karten[nummer] = karte
        karte.show()
        return karte

    def _wochenende_gefahren(self) -> None:
        """Nach einem gefuehrten Wochenende steht die Saison woanders.

        Die Saisonseite haelt denselben ``Saisonlauf``, muss ihre Anzeige
        aber neu lesen; Karriere und Statistik ebenso.
        """
        self._saisonseite._aktualisiere()
        self.statusBar().showMessage(
            f"Rennwochenende gefahren - {self._saisonseite.lauf.gefahren} von "
            f"{self._saisonseite.lauf.rennen_je_saison} Rennen",
            8000,
        )
        self.autosave()

    def _reiter_gewechselt(self, stelle: int) -> None:
        seite = self._reiter.widget(stelle)
        # Der Editor baut die Welt neu auf. Die uebrigen Seiten halten noch
        # die alte, deshalb wird beim Verlassen des Editors alles neu
        # aufgebaut - waehrenddessen wuerde sich das Fenster selbst unter
        # den Fuessen wegziehen.
        if seite is not self._editorseite and self._editorseite.geaendert:
            self.uebernimm_welt(self._editorseite.welt)
            return
        if seite is self._statistikseite:
            self._statistikseite.aktualisiere()
        elif seite is self._sponsorenseite:
            # Die Angebote haengen an der Kalenderwoche (GDD 10).
            self._sponsorenseite.wuerfle_angebote()
        elif seite is self._karriereseite:
            self._karriereseite._zeichne()

    def _baue_uebersichtsseite(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.addWidget(self._baue_uebersicht())
        spalte.addWidget(self._baue_seedbereich())
        spalte.addWidget(self._baue_offene_punkte(), stretch=1)
        return seite

    def _baue_uebersicht(self) -> QGroupBox:
        k = self._konfiguration
        kasten = QGroupBox("Geladene Konfiguration")
        formular = QFormLayout(kasten)
        formular.addRow("GDD-Version:", QLabel(str(k.wert("gdd_version"))))
        formular.addRow(
            "Ligen:",
            QLabel(
                f"{k.wert('ligen', 'anzahl')} "
                f"({k.ligenname(1)} bis {k.ligenname(k.wert('ligen', 'anzahl'))}), "
                f"je {k.wert('ligen', 'autos_je_liga')} Autos"
            ),
        )
        formular.addRow(
            "Strecken:",
            QLabel(f"{len(k.strecken)} (TUMFTM, LGPL-3.0, mitgeliefert)"),
        )
        formular.addRow(
            "Fahrzeug-Upgrades:", QLabel(f"{len(k.fahrzeug)} (F1 bis F16)")
        )
        formular.addRow(
            "Fahrer-Eigenschaften:", QLabel(f"{len(k.fahrer)} (D1 bis D16)")
        )
        formular.addRow(
            "Ereignisse / Defekte:",
            QLabel(
                f"{len(k.wert('ereignisse', 'liste'))} / "
                f"{len(k.wert('defekte', 'liste'))}"
            ),
        )

        hersteller_text = f"{len(k.hersteller)}"
        if not k.hersteller_bestaetigt:
            hersteller_text += "  (Platzhalterliste, noch nicht bestaetigt)"
        formular.addRow("Hersteller:", QLabel(hersteller_text))
        return kasten

    def _baue_seedbereich(self) -> QGroupBox:
        kasten = QGroupBox("Seed")
        zeile = QHBoxLayout(kasten)

        self._seed_eingabe = QSpinBox()
        self._seed_eingabe.setRange(0, SEED_MAX)
        self._seed_eingabe.setValue(0)
        self._seed_eingabe.setGroupSeparatorShown(True)
        self._seed_eingabe.valueChanged.connect(self._seed_geaendert)

        neuer_seed = QPushButton("Neuer Seed")
        neuer_seed.clicked.connect(self._wuerfle_seed)

        self._seed_hinweis = QLabel()
        self._seed_hinweis.setTextInteractionFlags(Qt.TextSelectableByMouse)

        zeile.addWidget(QLabel("Hauptseed:"))
        zeile.addWidget(self._seed_eingabe)
        zeile.addWidget(neuer_seed)
        zeile.addWidget(self._seed_hinweis, stretch=1)

        self._seed_geaendert(0)
        return kasten

    def _baue_offene_punkte(self) -> QGroupBox:
        offen = self._konfiguration.offene_punkte
        kasten = QGroupBox(f"Im GDD noch nicht festgelegt ({len(offen)})")
        spalte = QVBoxLayout(kasten)

        baum = QTreeWidget()
        baum.setHeaderLabels(["Thema", "Fehlende Angabe"])
        baum.setRootIsDecorated(False)
        baum.setAlternatingRowColors(True)
        for thema, beschreibung in sorted(offen.items()):
            QTreeWidgetItem(baum, [thema, beschreibung])
        baum.resizeColumnToContents(0)
        spalte.addWidget(baum)
        return kasten

    # -- Reaktionen --------------------------------------------------------
    def _seed_geaendert(self, wert: int) -> None:
        self._seedquelle = Seedquelle(wert)
        beispiel = self._seedquelle.zweig("saison", 1).zweig("rennen", 1).zweig("wetter")
        self._seed_hinweis.setText(
            f"Beispielzweig {beispiel.bezeichnung} "
            f"-> {beispiel.abgeleiteter_seed}"
        )

    def _wuerfle_seed(self) -> None:
        self._seed_eingabe.setValue(Seedquelle.zufaellig().seed % (SEED_MAX + 1))

    @property
    def streckenseite(self) -> Streckenseite:
        """Die Seite mit der Streckendarstellung."""
        return self._streckenseite

    @property
    def rundenseite(self) -> Rundenseite:
        """Die Seite mit Geschwindigkeitsprofil und Rundenzeit."""
        return self._rundenseite

    @property
    def welt(self) -> kern_welt.Welt:
        """Die erzeugte Welt dieses Fensters."""
        return self._welt

    @property
    def weltseite(self) -> Weltseite:
        return self._weltseite

    @property
    def karriereseite(self) -> Karriereseite:
        """Die Seite mit Kalender, Entwicklung und Sponsoren."""
        return self._karriereseite

    @property
    def fahrersuche(self) -> Fahrersuche:
        """Das Suchfeld ueber den Reitern (Punkt 18)."""
        return self._suche

    @property
    def wochenendeseite(self) -> Rennwochenendeseite:
        """Der gefuehrte Reiter: Vorschau, Qualifying, Rennen, Ergebnis."""
        return self._wochenendeseite

    @property
    def qualifyingseite(self):
        """Die Qualifying-Anzeige im gefuehrten Wochenende."""
        return self._wochenendeseite.qualifyingseite

    @property
    def rennseite(self):
        """Die Rennanzeige im gefuehrten Wochenende."""
        return self._wochenendeseite.rennseite

    @property
    def saisonseite(self) -> Saisonseite:
        """Die Seite mit Saisonwertung und Auf-/Abstieg."""
        return self._saisonseite

    @property
    def editorseite(self) -> Editorseite:
        """Die Debug-Ansicht aus GDD 15."""
        return self._editorseite

    @property
    def sponsorenseite(self) -> Sponsorenseite:
        """Die Seite mit den sechs Sponsorenplaetzen."""
        return self._sponsorenseite

    @property
    def statistikseite(self) -> Statistikseite:
        """Die Seite mit Rundenrekorden, Bestenliste und Historie."""
        return self._statistikseite

    @property
    def statistik(self) -> kern_statistik.Statistik:
        return self._statistik

    @property
    def karriere(self):
        """Der Karrierestand des Spielers - er ueberdauert den Saisonwechsel."""
        return self._karriere

    @property
    def popularitaet(self):
        """Der Bekanntheitsgrad aller Fahrer (Punkt 5)."""
        return self._popularitaet

    @property
    def jahr(self) -> int:
        """Das Jahr der laufenden Saison (GDD 13)."""
        return self._jahr

    @property
    def seedquelle(self) -> Seedquelle:
        """Der aktuell eingestellte Hauptseed."""
        return self._seedquelle

    # -- Spielstand (GDD 15) -----------------------------------------------
    def spielstand(self) -> kern_spielstand.Spielstand:
        """Alles, was zum Speichern gehoert, in einem Stueck."""
        return kern_spielstand.aus_teilen(
            seed=self._seedquelle.seed,
            saisonjahr=self._karriere.saison.jahr,
            welt=self._welt,
            karriere=self._karriere,
            tabellen=self._saisonseite.lauf.tabellen,
            statistik=self._statistik,
            kenntnis=self._kenntnis,
            gefahrene_rennen=self._saisonseite.lauf.gefahren,
            popularitaet=self._popularitaet,
        )

    def neue_karriere(self) -> bool:
        """Fragt Name, Land und Geburtstag und beginnt von vorn (Punkt 11).

        Alles andere wuerfelt der Seed: Welt, Teams, Gegner. Die Startliga
        ist fest die aus der Konfiguration - freie Wahl waere der
        Schwierigkeitsgrad durch die Hintertuer.
        """
        dialog = Startdialog(
            self._konfiguration, self._jahr, vorgabe=self._welt.spieler, parent=self
        )
        if dialog.exec() != Startdialog.Accepted:
            return False
        self.beginne_neue_karriere(dialog.stammdaten())
        return True

    def beginne_neue_karriere(self, stammdaten: dict) -> None:
        """Setzt Welt, Karriere und Statistik auf Anfang (GDD 1)."""
        spieler = self._welt.spieler
        if spieler is not None:
            self._welt = kern_welt.mit_fahrerdaten(
                self._welt, {spieler.nummer: stammdaten}
            )
        self._jahr = kern_karriere.startjahr(self._konfiguration)
        self._karriere = None
        self._statistik = kern_statistik.Statistik(self._konfiguration)
        self._kenntnis = kern_streckenkenntnis.Streckenkenntnis(
            self._konfiguration, seedquelle=self._seedquelle.zweig("lerntempo")
        )
        self._popularitaet = kern_popularitaet.Popularitaet(self._konfiguration)
        self._geladene_tabellen = None
        self._gefahrene_rennen = 0
        self.setCentralWidget(self._baue_inhalt())
        name = self._welt.spieler.name if self._welt.spieler else "Der Spieler"
        self.statusBar().showMessage(
            f"Neue Karriere: {name}, Liga "
            f"{self._konfiguration.wert('ligen', 'startliga')}, Saison {self._jahr}",
            8000,
        )

    # -- Speichern ohne Dialog (Punkt 17) ----------------------------------
    def schnellspeichern(self) -> Path | None:
        """Schreibt den Schnellspeicherstand (F5)."""
        return self._schreibe(kern_spielstand.schnellspeicher(), "Schnellspeicher")

    def schnellladen(self) -> bool:
        """Liest den Schnellspeicherstand zurueck (F9)."""
        return self._lies(kern_spielstand.schnellspeicher(), "Schnellspeicher")

    def autosave(self) -> Path | None:
        """Schreibt den Autosave-Stand.

        Laeuft nach jedem Tageswechsel und jedem Rennwochenende. Eine
        einzige Datei, die ueberschrieben wird: Ein Autosave, der mitwaechst,
        fuellte nach zwanzig Saisons das Verzeichnis.
        """
        return self._schreibe(kern_spielstand.autosave(), "Autosave", leise=True)

    def _schreibe(self, pfad: Path, was: str, leise: bool = False) -> Path | None:
        if self._karriere is None:  # pragma: no cover - ohne Karriere kein Stand
            return None
        try:
            ziel = kern_spielstand.speichere(self.spielstand(), pfad)
        except (kern_spielstand.SpielstandFehler, OSError) as fehler:
            # Ein misslungener Autosave darf das Spiel nicht anhalten, aber
            # stillschweigend verschwinden darf er auch nicht.
            self.statusBar().showMessage(f"{was} fehlgeschlagen: {fehler}", 12000)
            return None
        self.statusBar().showMessage(f"{was}: {ziel}", 5000)
        return ziel

    def _lies(self, pfad: Path, was: str) -> bool:
        try:
            stand = kern_spielstand.lade(self._konfiguration, pfad)
        except kern_spielstand.SpielstandFehler as fehler:
            QMessageBox.warning(self, was, str(fehler))
            return False
        self.uebernimm(stand)
        self.statusBar().showMessage(f"{was} geladen: {pfad}", 8000)
        return True

    def _speichere(self) -> None:
        pfad, _ = QFileDialog.getSaveFileName(
            self, "Spielstand speichern", str(Path.home() / "rennmanager.sqlite"), DATEIFILTER
        )
        if not pfad:
            return
        try:
            ziel = kern_spielstand.speichere(self.spielstand(), pfad)
        except (OSError, kern_spielstand.SpielstandFehler) as fehler:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(fehler))
            return
        self.statusBar().showMessage(f"Spielstand gespeichert: {ziel}", 8000)

    def _lade(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(
            self, "Spielstand laden", str(Path.home()), DATEIFILTER
        )
        if not pfad:
            return
        try:
            stand = kern_spielstand.lade(self._konfiguration, pfad)
        except (OSError, kern_spielstand.SpielstandFehler) as fehler:
            QMessageBox.critical(self, "Laden fehlgeschlagen", str(fehler))
            return
        self.uebernimm(stand)
        self.statusBar().showMessage(
            f"Spielstand geladen: {kern_spielstand.beschreibe(pfad)}", 8000
        )

    def _saison_gewechselt(self) -> None:
        """Uebernimmt die Welt der neuen Saison (GDD 13).

        Auf- und Abstieg haben die Ligen umgestellt; alle Seiten halten
        noch die alte Welt.
        """
        lauf = self._saisonseite.lauf
        self._welt = lauf.welt
        self._jahr = lauf.jahr
        self._geladene_tabellen = lauf.tabellen
        self._gefahrene_rennen = lauf.gefahren
        # Der Neuaufbau ersetzt die Seite, die dieses Signal gerade
        # gesendet hat - deshalb erst nach der Rueckkehr in die
        # Ereignisschleife.
        QTimer.singleShot(0, self._baue_neu_auf)

    def _baue_neu_auf(self) -> None:
        stelle = self._reiter.currentIndex()
        self.setCentralWidget(self._baue_inhalt())
        self._reiter.setCurrentIndex(min(stelle, self._reiter.count() - 1))
        self.statusBar().showMessage(f"Saison {self._jahr} begonnen", 8000)

    def uebernimm_welt(self, welt: kern_welt.Welt) -> None:
        """Uebernimmt eine im Editor geaenderte Welt (GDD 15)."""
        self._welt = welt
        # Die Tabellen der laufenden Saison bleiben; nur die Werte aendern
        # sich, nicht wer in welcher Liga faehrt.
        self._geladene_tabellen = self._saisonseite.lauf.tabellen
        self._gefahrene_rennen = self._saisonseite.lauf.gefahren
        stelle = self._reiter.currentIndex()
        self.setCentralWidget(self._baue_inhalt())
        self._reiter.setCurrentIndex(min(stelle, self._reiter.count() - 1))
        self.statusBar().showMessage("Welt aus dem Editor uebernommen", 8000)

    def uebernimm(self, stand: kern_spielstand.Spielstand) -> None:
        """Baut das Fenster auf einen geladenen Spielstand um (GDD 15).

        Die Seiten halten Welt und Karriere fest, deshalb werden sie neu
        aufgebaut statt einzeln nachgezogen.
        """
        self._seedquelle = Seedquelle(stand.seed)
        self._seed_eingabe.blockSignals(True)
        self._seed_eingabe.setValue(min(stand.seed, SEED_MAX))
        self._seed_eingabe.blockSignals(False)

        self._welt = stand.welt
        self._karriere = stand.karriere
        self._jahr = stand.saisonjahr
        self._statistik = stand.statistik
        self._kenntnis = stand.kenntnis
        if stand.popularitaet is not None and stand.popularitaet.werte:
            self._popularitaet = stand.popularitaet
        else:
            # Ein Stand vor Version 3 kennt sie noch nicht.
            self._popularitaet = kern_popularitaet.Popularitaet(self._konfiguration)
            self._popularitaet.anfang(
                tuple(f.nummer for f in stand.welt.fahrer),
                Seedquelle(stand.seed).zweig("popularitaet"),
            )
        self._geladene_tabellen = stand.tabellen
        self._gefahrene_rennen = stand.gefahrene_rennen

        stelle = self._reiter.currentIndex()
        self.setCentralWidget(self._baue_inhalt())
        self._reiter.setCurrentIndex(min(stelle, self._reiter.count() - 1))

    def _zeige_ueber(self) -> None:
        QMessageBox.about(
            self,
            "Ueber Rennmanager",
            f"<b>Rennmanager {__version__}</b><br><br>"
            "Motorsport-Manager mit sichtbarer Rennsimulation.<br>"
            f"Grundlage: Game Design Dokument v{self._konfiguration.wert('gdd_version')}.<br><br>"
            "Streckendaten: TUMFTM/racetrack-database (LGPL-3.0).",
        )
