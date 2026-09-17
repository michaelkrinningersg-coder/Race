"""Editor fuer Fahrer und Autos (GDD 15: Balancing-Werkzeuge).

GDD 15 nennt unter den Werkzeugen eine Debug-Ansicht. Diese Seite ist sie:
Sie laesst jeden der 600 Fahrer aendern - alle 32 Einzelwerte aus GDD 5
und 6, die sechs Faehigkeiten neben der Wirkungsmatrix (GDD 7 und der
Reifenfluesterer), die Streckenkenntnis je Strecke (GDD 6) und die
Stammdaten.

Links der Fahrer, rechts drei Blaetter: Fahrzeug, Fahrer, Strecken. Unten
steht, was die Aenderung bewirkt - Bereichsmittel und freie Rundenzeit -,
damit man nicht blind schiebt.

Liga und Team bleiben aussen vor: Ein Wechsel dort spraenge die
Ligastaerken aus GDD 9 und die Teamgroessen aus GDD 12.

Die Aenderungen sind dauerhaft. Sie bauen die Welt neu auf und wandern mit
dem Spielstand auf die Platte; beim Spieler gehen sie zusaetzlich in die
Karriere, weil dort seine entwickelten Werte stehen.
"""

from __future__ import annotations

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import streckenkenntnis as kern_kenntnis
from rennmanager.kern import tempo as kern_tempo
from rennmanager.kern import welt as kern_welt
from rennmanager.kern.auto import Auto, bereichswerte
from rennmanager.kern.welt import Welt, WeltFehler
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.konfiguration import Konfiguration

ALLE_LIGEN = 0

# Die Oberflaeche ist deutsch (CLAUDE.md); QSpinBox richtet sich sonst
# nach der Locale des Rechners und schreibt 23,504 statt 23.504.
DEUTSCH = QLocale(QLocale.German, QLocale.Germany)


def _zahl(wert: float) -> str:
    return f"{wert:,.0f}".replace(",", ".")


class Editorseite(QWidget):
    """Aendert Werte, Zusatzfaehigkeiten, Streckenkenntnis und Stammdaten."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        kenntnis: kern_kenntnis.Streckenkenntnis,
        karriere=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        self._kenntnis = kenntnis
        self._karriere = karriere
        self._strecken = tuple(e["name"] for e in konfiguration.strecken)
        self._geladen: int | None = None
        self._felder: dict[str, QSpinBox] = {}
        self._kenntnisfelder: dict[str, QSpinBox] = {}
        self._probestrecke: kern_strecke.Strecke | None = None
        # Solange nichts uebernommen wurde, muss das Fenster nichts neu
        # aufbauen.
        self._geaendert = False

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_fahrerliste())
        teiler.addWidget(self._baue_blaetter())
        teiler.setStretchFactor(0, 2)
        teiler.setStretchFactor(1, 3)
        spalte.addWidget(teiler, stretch=1)
        spalte.addLayout(self._baue_fuss())

        self._fuelle_liste()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._liga = QComboBox()
        self._liga.addItem("Alle Ligen", ALLE_LIGEN)
        for nummer in range(1, self._konfiguration.wert("ligen", "anzahl") + 1):
            self._liga.addItem(
                f"Liga {nummer} - {self._konfiguration.ligenname(nummer)}", nummer
            )
        spieler = self._welt.spieler
        if spieler is not None:
            self._liga.setCurrentIndex(spieler.liga)
        self._liga.currentIndexChanged.connect(self._fuelle_liste)

        self._suche = QLineEdit()
        self._suche.setPlaceholderText("Name oder Kuerzel ...")
        self._suche.setClearButtonEnabled(True)
        self._suche.textChanged.connect(self._fuelle_liste)

        self._zumSpieler = QPushButton("Zum Spieler")
        self._zumSpieler.setEnabled(spieler is not None)
        self._zumSpieler.clicked.connect(self._springe_zum_spieler)

        zeile.addWidget(QLabel("Liga:"))
        zeile.addWidget(self._liga)
        zeile.addWidget(QLabel("Suche:"))
        zeile.addWidget(self._suche, stretch=1)
        zeile.addWidget(self._zumSpieler)
        return zeile

    def _baue_fahrerliste(self) -> QWidget:
        self._listenkasten = QGroupBox("Fahrer")
        spalte = QVBoxLayout(self._listenkasten)
        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(["Liga", "Kuerzel", "Fahrer", "Team", "Staerke"])
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        self._liste.currentItemChanged.connect(self._lade_fahrer)
        spalte.addWidget(self._liste)
        return self._listenkasten

    def _baue_blaetter(self) -> QWidget:
        self._blaetter = QTabWidget()
        self._blaetter.addTab(self._baue_werteblatt(fahrzeug=True), "Fahrzeug (GDD 5)")
        self._blaetter.addTab(self._baue_werteblatt(fahrzeug=False), "Fahrer (GDD 6)")
        self._blaetter.addTab(self._baue_kenntnisblatt(), "Strecken (GDD 6)")
        self._blaetter.addTab(self._baue_stammblatt(), "Stammdaten")
        return self._blaetter

    @staticmethod
    def _zahlenfeld(kleinster: int, groesster: int, schritt: int) -> QSpinBox:
        feld = QSpinBox()
        feld.setLocale(DEUTSCH)
        feld.setRange(kleinster, groesster)
        feld.setGroupSeparatorShown(True)
        feld.setSingleStep(schritt)
        return feld

    def _baue_werteblatt(self, fahrzeug: bool) -> QWidget:
        seite = QWidget()
        formular = QFormLayout(seite)
        kleinster = self._konfiguration.wert("skala", "minimum")
        groesster = self._konfiguration.wert("skala", "maximum")

        for faehigkeit in self._konfiguration.faehigkeiten:
            if faehigkeit.ist_fahrzeug != fahrzeug:
                continue
            feld = self._zahlenfeld(kleinster, groesster, schritt=100)
            feld.valueChanged.connect(self._zeige_wirkung)
            self._felder[faehigkeit.schluessel] = feld
            formular.addRow(f"{faehigkeit.schluessel} {faehigkeit.name}:", feld)

        if not fahrzeug:
            # Die Faehigkeiten neben der Wirkungsmatrix gehoeren dem Fahrer.
            for schluessel, name in self._zusatznamen().items():
                feld = self._zahlenfeld(kleinster, groesster, schritt=100)
                feld.valueChanged.connect(self._zeige_wirkung)
                self._felder[schluessel] = feld
                formular.addRow(f"{name}:", feld)
        return seite

    def _baue_kenntnisblatt(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        hinweis = QLabel(
            "Kenntnisstand in gefahrenen Runden. "
            f"Voll nach {self._konfiguration.wert('streckenkenntnis', 'volle_kenntnis_runden')} "
            f"Runden, dann {self._konfiguration.wert('streckenkenntnis', 'max_bonus') * 100:.1f} %"
            " Tempo (GDD 6)."
        )
        hinweis.setWordWrap(True)
        spalte.addWidget(hinweis)

        formular = QFormLayout()
        voll = self._konfiguration.wert("streckenkenntnis", "volle_kenntnis_runden")
        for name in self._strecken:
            zeile = QHBoxLayout()
            feld = self._zahlenfeld(0, voll * 10, schritt=10)
            feld.setSuffix(" Rd.")
            bonus = QLabel()
            feld.valueChanged.connect(
                lambda wert, marke=bonus: marke.setText(
                    f"+{kern_kenntnis.bonus(self._konfiguration, wert) * 100:.3f} %"
                )
            )
            self._kenntnisfelder[name] = feld
            zeile.addWidget(feld)
            zeile.addWidget(bonus)
            zeile.addStretch(1)
            behaelter = QWidget()
            behaelter.setLayout(zeile)
            formular.addRow(f"{name}:", behaelter)
        rahmen = QWidget()
        rahmen.setLayout(formular)
        spalte.addWidget(rahmen)
        spalte.addStretch(1)
        return seite

    def _baue_stammblatt(self) -> QWidget:
        seite = QWidget()
        formular = QFormLayout(seite)
        self._vorname = QLineEdit()
        self._nachname = QLineEdit()
        self._land = QLineEdit()
        self._geburtstag = QDateEdit()
        self._geburtstag.setDisplayFormat("dd.MM.yyyy")
        self._geburtstag.setCalendarPopup(True)
        formular.addRow("Vorname:", self._vorname)
        formular.addRow("Nachname:", self._nachname)
        formular.addRow("Land:", self._land)
        formular.addRow("Geburtstag:", self._geburtstag)

        self._unveraenderlich = QLabel()
        self._unveraenderlich.setWordWrap(True)
        formular.addRow("Fest:", self._unveraenderlich)
        return seite

    def _baue_fuss(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._wirkung = QLabel()
        self._wirkung.setWordWrap(True)

        self._probe = QComboBox()
        for eintrag in self._konfiguration.strecken:
            self._probe.addItem(f"{eintrag['nummer']:>2}  {eintrag['name']}", eintrag["name"])
        self._probe.currentIndexChanged.connect(self._zeige_wirkung)

        self._uebernehmen = QPushButton("Uebernehmen")
        self._uebernehmen.clicked.connect(self._uebernimm)
        self._verwerfen = QPushButton("Verwerfen")
        self._verwerfen.clicked.connect(lambda: self._lade_fahrer(self._liste.currentItem()))
        self._zuruecksetzen = QPushButton("Auf Ligastaerke setzen")
        self._zuruecksetzen.clicked.connect(self._setze_auf_ligastaerke)

        zeile.addWidget(QLabel("Probe auf:"))
        zeile.addWidget(self._probe)
        zeile.addWidget(self._wirkung, stretch=1)
        zeile.addWidget(self._zuruecksetzen)
        zeile.addWidget(self._verwerfen)
        zeile.addWidget(self._uebernehmen)
        return zeile

    def _zusatznamen(self) -> dict[str, str]:
        namen = {
            e["schluessel"]: e.get("name", e["schluessel"])
            for e in self._konfiguration.wert("wetter", "faehigkeit", "liste")
        }
        fluesterer = self._konfiguration.wert("reifen", "fluesterer")
        namen[fluesterer["schluessel"]] = fluesterer.get("name", fluesterer["schluessel"])
        return namen

    # -- Liste -------------------------------------------------------------
    def _fahrerauswahl(self) -> tuple:
        liga = self._liga.currentData()
        wenn = self._suche.text().strip().lower()
        if liga == ALLE_LIGEN:
            fahrer = tuple(
                f
                for nummer in range(1, self._konfiguration.wert("ligen", "anzahl") + 1)
                for f in self._welt.liga(nummer)
            )
        else:
            fahrer = self._welt.liga(liga)
        if wenn:
            fahrer = tuple(
                f for f in fahrer if wenn in f.name.lower() or wenn in f.kuerzel.lower()
            )
        return fahrer

    def _fuelle_liste(self, *_) -> None:
        vorher = self._geladen
        self._liste.clear()
        for fahrer in self._fahrerauswahl():
            team = self._welt.team_von(fahrer)
            staerke = sum(fahrer.auto.werte.values()) / len(fahrer.auto.werte)
            zeile = QTreeWidgetItem(
                self._liste,
                [str(fahrer.liga), fahrer.kuerzel, fahrer.name, team.name, _zahl(staerke)],
            )
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            if fahrer.ist_spieler:
                schrift = zeile.font(2)
                schrift.setBold(True)
                for spalte in range(self._liste.columnCount()):
                    zeile.setFont(spalte, schrift)
            if fahrer.nummer == vorher:
                self._liste.setCurrentItem(zeile)

        self._listenkasten.setTitle(f"Fahrer ({self._liste.topLevelItemCount()})")
        for spalte in range(self._liste.columnCount()):
            self._liste.resizeColumnToContents(spalte)
        if self._liste.currentItem() is None and self._liste.topLevelItemCount():
            self._liste.setCurrentItem(self._liste.topLevelItem(0))

    def _springe_zum_spieler(self) -> None:
        spieler = self._welt.spieler
        if spieler is None:
            return
        self._suche.clear()
        self._liga.setCurrentIndex(spieler.liga)
        for stelle in range(self._liste.topLevelItemCount()):
            zeile = self._liste.topLevelItem(stelle)
            if zeile.data(0, Qt.UserRole) == spieler.nummer:
                self._liste.setCurrentItem(zeile)
                return

    # -- Laden und Uebernehmen ---------------------------------------------
    def _lade_fahrer(self, jetzt, _davor=None) -> None:
        if jetzt is None:
            return
        nummer = jetzt.data(0, Qt.UserRole)
        self._geladen = nummer
        fahrer = self._welt.fahrer[nummer]
        quelle = self._werte_von(fahrer)

        for schluessel, feld in self._felder.items():
            feld.blockSignals(True)
            feld.setValue(int(quelle.get(schluessel, 0)))
            feld.blockSignals(False)
        for name, feld in self._kenntnisfelder.items():
            feld.setValue(int(round(self._kenntnis.stand(nummer, name))))

        self._vorname.setText(fahrer.vorname)
        self._nachname.setText(fahrer.nachname)
        self._land.setText(fahrer.land)
        self._geburtstag.setDate(fahrer.geburtstag)
        team = self._welt.team_von(fahrer)
        self._unveraenderlich.setText(
            f"Liga {fahrer.liga} · Team {team.name} · Hersteller {team.hersteller} · "
            f"Kuerzel {fahrer.kuerzel}"
        )
        self._zeige_wirkung()

    def _werte_von(self, fahrer) -> dict[str, int]:
        """Woher die Werte kommen - beim Spieler aus der Karriere.

        Der Spieler entwickelt sich (GDD 1); seine Werte stehen deshalb in
        der Karriere und nicht in der Welt.
        """
        if self._karriere is not None and fahrer.nummer == self._karriere.fahrernummer:
            return dict(self._karriere.werte)
        werte = dict(fahrer.auto.werte)
        werte.update(fahrer.auto.wetterwerte)
        return werte

    def _eingegeben(self) -> dict[str, int]:
        return {schluessel: feld.value() for schluessel, feld in self._felder.items()}

    def _uebernimm(self) -> None:
        if self._geladen is None:
            return
        nummer = self._geladen
        werte = self._eingegeben()
        matrix = {f.schluessel for f in self._konfiguration.faehigkeiten}

        try:
            self._welt = kern_welt.mit_fahrerwerten(
                self._welt,
                {
                    nummer: (
                        {s: w for s, w in werte.items() if s in matrix},
                        {s: w for s, w in werte.items() if s not in matrix},
                    )
                },
            )
            self._welt = kern_welt.mit_fahrerdaten(
                self._welt,
                {
                    nummer: {
                        "vorname": self._vorname.text().strip() or "Ohne",
                        "nachname": self._nachname.text().strip() or "Namen",
                        "land": self._land.text().strip(),
                        "geburtstag": self._geburtstag.date().toPython(),
                    }
                },
            )
        except WeltFehler as fehler:  # pragma: no cover - Eingaben sind begrenzt
            QMessageBox.warning(self, "Editor", str(fehler))
            return

        for name, feld in self._kenntnisfelder.items():
            self._kenntnis.setze(nummer, name, feld.value())
        # Ein editierter Fahrer behaelt seinen Stand; sonst schriebe die
        # naechste Session ihn sofort wieder hoch (GDD 12 fuer die KI).
        if self._karriere is not None and nummer == self._karriere.fahrernummer:
            self._karriere.werte.update(werte)

        self._geaendert = True
        self._fuelle_liste()
        self._zeige_wirkung()

    def _setze_auf_ligastaerke(self) -> None:
        """Setzt alle Werte auf den Mittelwert des geladenen Fahrers."""
        if self._geladen is None:
            return
        fahrer = self._welt.fahrer[self._geladen]
        mittel = int(round(sum(fahrer.auto.werte.values()) / len(fahrer.auto.werte)))
        for feld in self._felder.values():
            feld.blockSignals(True)
            feld.setValue(mittel)
            feld.blockSignals(False)
        self._zeige_wirkung()

    # -- Wirkung -----------------------------------------------------------
    def _zeige_wirkung(self, *_) -> None:
        """Zeigt Bereichsmittel und freie Rundenzeit der Eingaben."""
        if self._geladen is None:
            return
        werte = self._eingegeben()
        matrix = {f.schluessel for f in self._konfiguration.faehigkeiten}
        auto = Auto(
            kuerzel="",
            name="",
            werte={s: w for s, w in werte.items() if s in matrix},
            wetterwerte={s: w for s, w in werte.items() if s not in matrix},
        )
        bereiche = bereichswerte(self._konfiguration, auto)
        gesamt = sum(auto.werte.values()) / len(auto.werte)

        name = self._probe.currentData()
        if self._probestrecke is None or self._probestrecke.name != name:
            self._probestrecke = kern_strecke.lade(self._konfiguration, name)
        runde = kern_tempo.fahre_runde(self._konfiguration, self._probestrecke, auto)
        bezeichnung = self._konfiguration.wert("wirkungsmatrix", "bezeichnung")
        bester = max(bereiche, key=lambda b: bereiche[b])
        schwaechster = min(bereiche, key=lambda b: bereiche[b])
        self._wirkung.setText(
            f"Mittel {_zahl(gesamt)} · stark in {bezeichnung.get(bester, bester)} "
            f"({_zahl(bereiche[bester])}), schwach in "
            f"{bezeichnung.get(schwaechster, schwaechster)} ({_zahl(bereiche[schwaechster])}) · "
            f"{name}: {formatiere_dauer(runde.zeit_ms)}, {runde.schnitt_kmh:.1f} km/h"
        )

    # -- Anschluss ans Fenster ---------------------------------------------
    @property
    def geaendert(self) -> bool:
        """Ob seit dem Aufbau etwas uebernommen wurde."""
        return self._geaendert

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def welt(self) -> Welt:
        return self._welt

    @property
    def liste(self) -> QTreeWidget:
        return self._liste

    @property
    def liga_auswahl(self) -> QComboBox:
        return self._liga

    @property
    def suche(self) -> QLineEdit:
        return self._suche

    @property
    def felder(self) -> dict[str, QSpinBox]:
        return self._felder

    @property
    def kenntnisfelder(self) -> dict[str, QSpinBox]:
        return self._kenntnisfelder

    @property
    def knopf_uebernehmen(self) -> QPushButton:
        return self._uebernehmen

    @property
    def stammdaten(self) -> tuple[QLineEdit, QLineEdit, QLineEdit, QDateEdit]:
        return self._vorname, self._nachname, self._land, self._geburtstag
