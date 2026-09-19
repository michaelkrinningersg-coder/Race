"""Seite fuer ein Rennen: Strecke, Seitenleiste, Zeitenmonitor, Zeitraffer.

Der Verlauf wird vorab berechnet (GDD 15); diese Seite spielt ihn nur ab.
Deshalb kostet auch 100-facher Zeitraffer nichts - es wird lediglich in
groesseren Schritten aus dem fertigen Verlauf gelesen.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
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
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern.rennen import Rennverlauf
from rennmanager.kern.welt import Welt
from rennmanager.kern.zeit import (
    formatiere_dauer,
    formatiere_rueckstand,
    formatiere_runden_rueckstand,
)
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.rueckstandsansicht import Rueckstandsansicht
from rennmanager.ui.streckenansicht import Streckenansicht
from rennmanager.ui.tabellen import Balkenzeichner, verbinde_fahrerkarte

# Der Zeitraffer vervielfacht die Rennzeit je Takt, nicht die Zahl der
# Takte - die Anzeige bleibt damit gleich fluessig, egal wie schnell
# gerafft wird.

# Spalten der Rangliste.
SPALTE_PLATZ = 0
SPALTE_KUERZEL = 1
# Punkt 60: Der Nachname - ein Kuerzel wie "MKR" sagt niemandem etwas.
SPALTE_NAME = 2
# Punkt 82: Das Team dazu - wer fuer wen faehrt, sieht man sonst nirgends.
SPALTE_TEAM = 3
# Punkt 76: Gewonnene oder verlorene Plaetze seit Beginn dieser Runde.
SPALTE_WECHSEL = 4
SPALTE_RUNDE = 5
SPALTE_ZEIT = 6
SPALTE_INTERVALL = 7
# Punkt 60: Momentantempo und Schnitt ueber das bisherige Rennen.
SPALTE_TEMPO = 8
SPALTE_SCHNITT = 9
SPALTE_MISCHUNG = 10
SPALTE_REIFEN = 11
SPALTE_STATUS = 12
# Spalten des Zeitenmonitors.
MONITOR_KUERZEL = 0
MONITOR_NAME = 1
MONITOR_TEAM = 2
MONITOR_LETZTE = 3
MONITOR_BESTE = 4
MONITOR_BESTRUNDE = 5
MONITOR_SCHNITT = 6
MONITOR_SEKTOR = 7
MONITOR_SPALTEN = 11
# Spalten des Blattes "Bestmoegliche Runde" (Punkt 82): dieselben
# Sektoren, aber die persoenlich besten - und was sie zusammen ergaeben.
IDEAL_KUERZEL = 0
IDEAL_NAME = 1
IDEAL_TEAM = 2
IDEAL_BESTE = 3
IDEAL_MOEGLICH = 4
IDEAL_GEWINN = 5
IDEAL_SEKTOR = 6
IDEAL_SPALTEN = 10
# Gruener Pfeil hoch, roter Pfeil runter - die Zahl daneben sagt, um wie
# viele Plaetze. Die Farbe ist nie die einzige Auskunft.
PFEIL_HOCH = "\u25b2"
PFEIL_RUNTER = "\u25bc"
FARBE_GEWONNEN = "#2e7d32"
FARBE_VERLOREN = "#c62828"
# So viele Zwischenfaelle stehen im Ticker; aeltere rollen heraus.
TICKER_ZEILEN = 12
# Punkt 63: So lange bleibt ein ausgefallenes Auto noch auf der
# Streckengrafik stehen - lang genug, um zu sehen, wo es passiert ist,
# und kurz genug, dass die Karte nicht mit Standbildern zuwaechst.
AUSFALL_SICHTBAR_MS = 60_000
# Die letzte Runde leuchtet auf, wenn sie die beste dieses Fahrers war.
FARBE_PERSOENLICHE_BEST = "#2e7d32"
# Ab welchem Tempo ein Auto als fahrend gilt, in m/s. Darunter steht es -
# im Ziel, in der Box oder ausgefallen -, und dann gibt es weder ein
# Momentantempo noch einen Abstand, der sich aus Strecke durch Tempo
# rechnen liesse (Punkt 83).
TEMPO_STEHT = 0.1
# Punkt 82: Wer einen Sektor als Schnellster des ganzen Feldes gefahren
# ist, bekommt ihn lila - wie in der Uebertragung. Gruen bleibt die
# persoenliche Bestzeit, lila steht ueber allem.
FARBE_BESTER_SEKTOR = "#8e24aa"
# Platz fuer den Reifenbalken samt Prozentzahl daneben.
BREITE_REIFEN = 96
# Punkt 39: Zwei Mischungen sind im Trockenen Pflicht. Solange ein Auto
# sie nicht erfuellt hat, steht die Mischungsspalte in Warnfarbe; danach
# traegt sie einen Haken. Bei Regen, Starkregen und wechselhaftem Wetter
# ist die Pflicht aufgehoben - dann steht der Haken von Anfang an, weil
# nichts mehr zu erfuellen ist.
HAKEN = " \u2713"
FARBE_PFLICHT_OFFEN = "#eda100"
FARBE_PFLICHT_ERFUELLT = "#2e7d32"


class Rennseite(QWidget):
    """Spielt ein fertig gerechnetes Rennen ab (GDD 4).

    Die Seite rechnet nichts: Sie bekommt einen ``Rennverlauf`` von aussen
    - vom gefuehrten Rennwochenende (Punkt 12) - und macht daraus eine
    Uebertragung. Frei einstellbare Testrennen gab es hier frueher; sie
    sind mit dem gefuehrten Wochenende entfallen, weil gefahren wird, was
    der Kalender vorgibt (GDD 2). Zum Kalibrieren dienen
    ``python -m rennmanager --pruefe`` und die Werkzeuge unter
    ``werkzeuge/``, die ohne Oberflaeche laufen.
    """

    # Doppelklick auf eine Zeile: Das Fenster oeffnet die Fahrerkarte. Die
    # Listen hier fuehren die Startnummer im Feld, nicht die des Fahrers -
    # ``_fahrernummer`` uebersetzt.
    fahrerkarte_gewuenscht = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        karriere=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        # Die entwickelten Werte des Spielers stehen in der Karriere, nicht
        # in der Welt (GDD 1 und 14); ohne sie faehrt er hier mit Nullen.
        self._karriere = karriere
        self._strecken: dict[str, kern_strecke.Strecke] = {}
        self._verlauf: Rennverlauf | None = None
        self._qualifying = None
        # Punkt 73: Der Meisterschaftsstand vor diesem Rennen.
        self._tabelle = None
        self._zeit_ms = 0.0
        self._laeuft = False
        # Das Rennen laeuft erst los, wenn diese Seite auch zu sehen ist.
        # Sonst rauscht es im Hintergrund durch, waehrend der Spieler noch
        # beim Qualifying steht - und er findet es am Ende vor.
        self._startet_beim_zeigen = False
        # Punkt 58: Welcher Fahrer gerade gewaehlt ist. Rangliste und
        # Monitor werden bei jedem Bild neu gefuellt; ohne diese Marke
        # waere die Auswahl nach 200 ms wieder weg.
        self._gewaehlt: int | None = None
        # Punkt 62: Rangliste und Zeitenmonitor werden seltener neu
        # gefuellt als die Karte - sonst springen die Zeiten schneller
        # um, als sie zu lesen sind.
        self._anzeige_takt_ms = konfiguration.wert("zeitraffer", "anzeige_takt_ms")
        self._letzte_tabellen_ms: float | None = None

        self._ansicht = Streckenansicht()
        # Punkt 2: Das Rueckstandsdiagramm liegt als zweiter Reiter neben
        # der Streckenansicht - beide zeigen denselben Verlauf, einmal
        # raeumlich und einmal ueber die Zeit.
        self._rueckstand = Rueckstandsansicht()
        self._takt_ms = konfiguration.wert("zeitraffer", "takt_ms")
        self._uhr = QTimer(self)
        self._uhr.setInterval(self._takt_ms)
        self._uhr.timeout.connect(self._takt)

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_wiedergabe())

        self._blaetter = QTabWidget()
        self._blaetter.addTab(self._ansicht, "Strecke")
        self._blaetter.addTab(self._rueckstand, "Rueckstand")

        # Punkt 59: Rangliste und Zeitenmonitor stehen **nebeneinander**.
        # Vorher lagen alle Listen untereinander in einer schmalen Spalte;
        # die Rangliste hat seit Punkt 60 zwoelf Spalten und braucht
        # Breite. Punkt 82: Die Zwischenfaelle standen bis dahin als
        # Fussleiste darunter und nahmen den Tabellen Hoehe weg - sie
        # sind jetzt ein Blatt neben den anderen.
        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._blaetter)
        teiler.addWidget(self._baue_listen())
        teiler.setStretchFactor(0, 2)
        teiler.setStretchFactor(1, 3)
        spalte.addWidget(teiler, stretch=1)

    # -- Aufbau ------------------------------------------------------------
    def _baue_wiedergabe(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._abspielen = QPushButton("Start")
        self._abspielen.setEnabled(False)
        self._abspielen.clicked.connect(self._umschalten)

        self._zurueck = QPushButton("Anfang")
        self._zurueck.setEnabled(False)
        self._zurueck.clicked.connect(lambda: self._springe(0))

        self._raffer = QComboBox()
        for stufe in self._konfiguration.wert("zeitraffer", "stufen"):
            self._raffer.addItem(f"{stufe}x", stufe)

        self._sofort = QPushButton("Sofortergebnis")
        self._sofort.setEnabled(False)
        self._sofort.clicked.connect(self._zum_ende)

        self._uhrzeit = QLabel("0:00.000")
        # Punkt 65: Je Fahrer steht in der Rangliste, in welcher Runde er
        # ist - aber nirgends, wie weit das Rennen insgesamt ist. Hier
        # steht die Runde des Fuehrenden und die Gesamtzahl.
        self._rundenstand = QLabel("Runde -/-")
        # Punkt 62: Wie oft die Zeiten in den Listen nachgezogen werden.
        self._takteingabe = QSpinBox()
        self._takteingabe.setRange(
            self._konfiguration.wert("zeitraffer", "anzeige_takt_min_ms"),
            self._konfiguration.wert("zeitraffer", "anzeige_takt_max_ms"),
        )
        self._takteingabe.setSingleStep(10)
        self._takteingabe.setSuffix(" ms")
        self._takteingabe.setValue(self._anzeige_takt_ms)
        self._takteingabe.setToolTip(
            "Wie oft Rangliste und Zeitenmonitor nachgezogen werden. "
            "Die Karte laeuft unabhaengig davon fluessig weiter."
        )
        self._takteingabe.valueChanged.connect(self._takt_geaendert)
        self._fortschritt = QProgressBar()
        self._fortschritt.setTextVisible(False)

        zeile.addWidget(self._abspielen)
        zeile.addWidget(self._zurueck)
        zeile.addWidget(QLabel("Zeitraffer:"))
        zeile.addWidget(self._raffer)
        zeile.addWidget(self._sofort)
        self._wetteranzeige = QLabel("-")
        zeile.addWidget(self._uhrzeit)
        zeile.addWidget(self._rundenstand)
        zeile.addWidget(self._fortschritt, stretch=1)
        zeile.addWidget(QLabel("Wetter:"))
        zeile.addWidget(self._wetteranzeige)
        zeile.addSpacing(12)
        zeile.addWidget(QLabel("Takt:"))
        zeile.addWidget(self._takteingabe)
        return zeile

    def _tabellen_faellig(self, zeit: float) -> bool:
        """Ob Rangliste, Monitor und Ticker jetzt nachgezogen werden.

        Gemessen wird in **Rennzeit**, nicht in Echtzeit: Im Zeitraffer
        laufen zwischen zwei Bildern viele Rennsekunden, und die Listen
        sollen genauso oft stehenbleiben wie bei einfachem Tempo.
        """
        davor = self._letzte_tabellen_ms
        if davor is None or abs(zeit - davor) >= self._anzeige_takt_ms:
            self._letzte_tabellen_ms = zeit
            return True
        return False

    def _takt_geaendert(self, wert: int) -> None:
        """Uebernimmt einen neuen Anzeigetakt und zeichnet sofort neu."""
        self._anzeige_takt_ms = int(wert)
        self._letzte_tabellen_ms = None
        self._zeichne()

    def _baue_listen(self) -> QWidget:
        """Rangliste links, Zeitenmonitor und Meisterschaft rechts."""
        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_rangliste())
        teiler.addWidget(self._baue_monitor())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        return teiler

    def _baue_rangliste(self) -> QWidget:
        # GDD 4: Positionen, Gesamtzeit des Fuehrenden, Rueckstand der uebrigen
        self._rangliste = QTreeWidget()
        self._rangliste.setHeaderLabels(
            [
                "Pos", "Auto", "Fahrer", "Team", "+/-", "Rd", "Zeit / Rueckstand",
                "Intervall", "km/h", "Ø km/h", "Mischung", "Reifen", "Status",
            ]
        )
        self._rangliste.setRootIsDecorated(False)
        self._rangliste.setAlternatingRowColors(True)
        # Punkt 3: Der Reifenzustand als Balken - im Zeitraffer schneller
        # zu lesen als eine Prozentzahl.
        self._rangliste.setItemDelegateForColumn(
            SPALTE_REIFEN, Balkenzeichner(self._rangliste)
        )
        # Der Balken braucht Platz; auf Inhaltsbreite blieben ihm die
        # sechs Pixel, die "42 %" uebrig laesst.
        self._rangliste.setColumnWidth(SPALTE_REIFEN, BREITE_REIFEN)
        # Wer in der Rangliste gewaehlt ist, tritt im Diagramm hervor.
        self._rangliste.currentItemChanged.connect(self._auswahl_geaendert)
        verbinde_fahrerkarte(
            self._rangliste, self.fahrerkarte_gewuenscht.emit, self._fahrernummer_in(0)
        )
        kasten = QGroupBox("Rangliste")
        kasten_spalte = QVBoxLayout(kasten)
        kasten_spalte.addWidget(self._rangliste)
        return kasten

    def _baue_monitor(self) -> QWidget:
        """Zeitenmonitor und darunter der Live-Meisterschaftsstand."""
        # GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten
        self._monitor = QTreeWidget()
        self._monitor.setHeaderLabels(
            [
                "Auto", "Fahrer", "Team", "Letzte Rd", "Beste Rd", "in Rd",
                "Ø km/h", "S1", "S2", "S3", "S4",
            ]
        )
        self._monitor.setRootIsDecorated(False)
        self._monitor.setAlternatingRowColors(True)
        # Punkt 58: Auch aus dem Monitor heraus laesst sich ein Fahrer
        # waehlen; die Karte markiert ihn genauso.
        self._monitor.currentItemChanged.connect(self._auswahl_geaendert)
        # Punkt 73: Der Meisterschaftsstand, als waere das Rennen jetzt
        # zu Ende - als zweites Blatt unter dem Zeitenmonitor.
        self._meisterschaft = QTreeWidget()
        self._meisterschaft.setHeaderLabels(
            ["Pos", "Auto", "Fahrer", "Team", "+/-", "Punkte", "davon jetzt"]
        )
        self._meisterschaft.setRootIsDecorated(False)
        self._meisterschaft.setAlternatingRowColors(True)
        self._meisterschaft.currentItemChanged.connect(self._auswahl_geaendert)

        # Punkt 82: Dieselben Sektoren, aber die persoenlich besten -
        # und was sie zusammen ergaeben.
        self._ideal = QTreeWidget()
        self._ideal.setHeaderLabels(
            [
                "Auto", "Fahrer", "Team", "Beste Rd", "Moeglich", "Luecke",
                "S1", "S2", "S3", "S4",
            ]
        )
        self._ideal.setRootIsDecorated(False)
        self._ideal.setAlternatingRowColors(True)
        self._ideal.currentItemChanged.connect(self._auswahl_geaendert)

        self._monitorblaetter = QTabWidget()
        self._monitorblaetter.addTab(self._monitor, "Zeitenmonitor")
        self._monitorblaetter.addTab(self._ideal, "Bestmoegliche Runde")
        self._monitorblaetter.addTab(self._meisterschaft, "Meisterschaft")
        # Punkt 82: Die Meldungen standen fest unter der Seite und nahmen
        # den Tabellen Hoehe weg. Als viertes Blatt stoeren sie nicht mehr
        # und sind trotzdem einen Klick entfernt.
        self._monitorblaetter.addTab(self._baue_ticker(), "Meldungen")
        return self._monitorblaetter

    def _baue_ticker(self) -> QWidget:
        # Punkt 4: Fehler, Unfaelle und Defekte laufen mit, neueste zuerst.
        self._ticker = QTreeWidget()
        self._ticker.setHeaderLabels(["Zeit", "Rd", "Auto", "Was"])
        self._ticker.setRootIsDecorated(False)
        self._ticker.setAlternatingRowColors(True)
        verbinde_fahrerkarte(
            self._ticker, self.fahrerkarte_gewuenscht.emit, self._fahrernummer_in(2)
        )
        self._tickerkasten = QGroupBox("Zwischenfaelle")
        ticker_spalte = QVBoxLayout(self._tickerkasten)
        ticker_spalte.setContentsMargins(6, 4, 6, 4)
        ticker_spalte.addWidget(self._ticker)
        return self._tickerkasten

    # -- Rennen uebernehmen ------------------------------------------------
    def zeige_verlauf(
        self,
        verlauf: Rennverlauf,
        strecke: kern_strecke.Strecke,
        qualifying=None,
        tabelle=None,
    ) -> None:
        """Uebernimmt ein fertig gerechnetes Rennen und spielt es ab.

        Gerechnet hat es der Kern - beim gefuehrten Wochenende der
        ``Wochenendlauf`` (Punkt 12). Die Seite ist reine Uebertragung.

        :param tabelle: der Meisterschaftsstand **vor** diesem Rennen
            (Punkt 73). Ohne ihn bleibt das Blatt "Meisterschaft" leer -
            ein Testrennen ohne Saison hat keinen Stand.
        """
        self._halte_an()
        self._verlauf = verlauf
        self._qualifying = qualifying
        self._tabelle = tabelle
        self._ansicht.zeige(strecke)
        self._rueckstand.zeige(verlauf)
        # Ein neues Rennen faengt ohne Auswahl an.
        self._gewaehlt = None
        self._zeige_auswahl()
        self._fortschritt.setRange(0, max(verlauf.dauer_ms, 1))
        for knopf in (self._abspielen, self._zurueck, self._sofort):
            knopf.setEnabled(True)
        self._waehle_zeitraffer()
        self._springe(0)

        # Das Rennen laeuft von selbst los, damit es sich wie eine
        # Uebertragung anfuehlt und nicht wie eine Auswertung - aber erst,
        # wenn man auch hinschaut.
        if self._konfiguration.wert("zeitraffer", "automatisch_starten"):
            if self.isVisible():
                self._umschalten()
            else:
                self._startet_beim_zeigen = True

    def showEvent(self, ereignis) -> None:  # noqa: D102 - Qt-Name
        super().showEvent(ereignis)
        if self._startet_beim_zeigen and self._verlauf is not None:
            self._startet_beim_zeigen = False
            self._umschalten()

    def _waehle_zeitraffer(self) -> None:
        """Stellt die Stufe ein, mit der jedes Rennen startet.

        Entscheidung des Auftraggebers: ``start_stufe``, also Echtzeit.
        Vorher suchte die Oberflaeche die kleinste Stufe, mit der das
        Rennen in rund 210 Sekunden durchlief - auf langen Strecken also
        20x oder 50x, und die ersten Runden waren vorbei, bevor man
        hinsah. Wer es schneller will, stellt waehrend des Rennens um.
        """
        if self._verlauf is None:
            return
        stufen = self._konfiguration.wert("zeitraffer", "stufen")
        start = self._konfiguration.wert("zeitraffer", "start_stufe")
        # Steht in der Konfiguration eine Stufe, die es nicht gibt, wird
        # daraus die langsamste - lieber zu langsam als gar kein Rennen.
        index = stufen.index(start) if start in stufen else 0
        self._raffer.setCurrentIndex(index)

    # -- Wiedergabe --------------------------------------------------------
    def _umschalten(self) -> None:
        if self._laeuft:
            self._halte_an()
        else:
            self._laeuft = True
            self._abspielen.setText("Pause")
            self._uhr.start()

    def _halte_an(self) -> None:
        self._startet_beim_zeigen = False
        self._laeuft = False
        self._uhr.stop()
        self._abspielen.setText("Start")

    def _springe(self, zeit_ms: float) -> None:
        self._zeit_ms = zeit_ms
        # Ein Sprung soll sofort zu sehen sein, nicht erst im naechsten Takt.
        self._letzte_tabellen_ms = None
        self._zeichne()

    def _zum_ende(self) -> None:
        """GDD 4: Sofortergebnis."""
        if self._verlauf is not None:
            self._halte_an()
            self._springe(self._verlauf.dauer_ms)

    def _takt(self) -> None:
        if self._verlauf is None:
            return
        self._zeit_ms += self._takt_ms * self._raffer.currentData()
        if self._zeit_ms >= self._verlauf.dauer_ms:
            self._zeit_ms = self._verlauf.dauer_ms
            self._halte_an()
        self._zeichne()

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self) -> None:
        if self._verlauf is None:
            return
        verlauf = self._verlauf
        zeit = self._zeit_ms
        self._uhrzeit.setText(formatiere_dauer(int(zeit)))
        self._fortschritt.setValue(int(zeit))

        if verlauf.wetter is not None:
            zustand = verlauf.wetter.zustand_zu(zeit)
            grip = verlauf.wetter.grip_zu(zeit)
            self._wetteranzeige.setText(f"{zustand}  (Grip {grip:.2f})")

        distanzen = verlauf.distanzen_zu(zeit)
        reihenfolge = verlauf.reihenfolge_zu(zeit)
        self._rundenstand.setText(
            f"Runde {self._runde_des_ersten(verlauf, reihenfolge, distanzen)}"
            f"/{verlauf.runden}"
        )

        self._ansicht.zeige_autos(
            [
                (
                    float(distanzen[i]),
                    verlauf.teilnehmer[i].kuerzel,
                    verlauf.teilnehmer[i].farbe,
                    verlauf.teilnehmer[i].ist_spieler,
                )
                for i in reihenfolge
                if self._noch_auf_der_karte(verlauf, i, zeit)
            ]
        )
        if self._tabellen_faellig(zeit):
            self._fuelle_rangliste(verlauf, reihenfolge, distanzen, zeit)
            self._fuelle_monitor(verlauf, reihenfolge, zeit)
            self._fuelle_ideal(verlauf, reihenfolge, zeit)
            self._fuelle_meisterschaft(verlauf, reihenfolge, zeit)
            self._fuelle_ticker(verlauf, zeit)
        self._rueckstand.setze_marke(zeit)

    def _teamname(self, teilnehmer) -> str:
        """Das Team hinter einem Auto (Punkt 82).

        Wie ``_nachname``: Ein Feld aus ``rennen.starterfeld`` hat keinen
        Fahrer dahinter, dann bleibt die Spalte leer.
        """
        nummer = getattr(teilnehmer, "nummer", 0)
        if not nummer or self._welt is None or nummer >= len(self._welt.fahrer):
            return ""
        return self._welt.team_von(self._welt.fahrer[nummer]).name

    def _nachname(self, teilnehmer) -> str:
        """Der Nachname des Fahrers hinter einem Auto (Punkt 60).

        Ein Kuerzel wie "MKR" sagt niemandem etwas; der Nachname schon.
        Ein Feld aus ``rennen.starterfeld`` hat keinen Fahrer dahinter -
        dann bleibt die Spalte leer.
        """
        nummer = getattr(teilnehmer, "nummer", 0)
        if not nummer or self._welt is None or nummer >= len(self._welt.fahrer):
            return ""
        name = self._welt.fahrer[nummer].name
        return name.rsplit(" ", 1)[-1] if name else ""

    def _tempotext(self, verlauf: Rennverlauf, i: int, zeit: float) -> str:
        """Das Momentantempo in km/h (Punkt 60)."""
        tempo = self._tempo_naeherung(verlauf, i, zeit)
        return f"{tempo * 3.6:.0f}" if tempo > TEMPO_STEHT else "-"

    @staticmethod
    def _schnitttext(distanz: float, zeit: float) -> str:
        """Der Schnitt ueber das bisherige Rennen in km/h (Punkt 60)."""
        if zeit <= 0.0 or distanz <= 0.0:
            return "-"
        return f"{distanz / (zeit / 1000.0) * 3.6:.1f}"

    @staticmethod
    def _beste_rundennummer(
        verlauf: Rennverlauf, i: int, zeit: float, beste: int | None
    ) -> int:
        """In welcher Runde die beste Zeit gefahren wurde (Punkt 60)."""
        if beste is None:
            return 0
        protokoll = verlauf.protokolle[i]
        bis = protokoll.gefahren_bis(zeit)
        zeiten = protokoll.rundenzeiten_ms[:bis]
        return zeiten.index(beste) + 1 if beste in zeiten else 0

    @staticmethod
    def _wechseltext(gewinn: int) -> str:
        """Pfeil und Zahl der Plaetze, oder leer bei keiner Aenderung."""
        if gewinn > 0:
            return f"{PFEIL_HOCH} {gewinn}"
        if gewinn < 0:
            return f"{PFEIL_RUNTER} {-gewinn}"
        return ""

    @staticmethod
    def _plaetze_vorige_runde(
        verlauf: Rennverlauf, fuehrender: int, zeit: float
    ) -> dict[int, int]:
        """Die Plaetze zu Beginn der laufenden Runde des Fuehrenden.

        Ein fester Bezugspunkt fuers ganze Feld: Nimmt jedes Auto seine
        eigene letzte Rundenankunft, vergleichen dreissig Zeilen dreissig
        verschiedene Augenblicke, und die Pfeile widersprechen sich.
        Leer, solange die erste Runde laeuft - da gibt es nichts zu
        vergleichen.
        """
        protokoll = verlauf.protokolle[fuehrender]
        gefahren = protokoll.gefahren_bis(zeit)
        if gefahren < 1 or not protokoll.rundenende_ms:
            return {}
        rundenbeginn = protokoll.rundenende_ms[gefahren - 1]
        return {
            auto: platz
            for platz, auto in enumerate(verlauf.reihenfolge_zu(rundenbeginn), start=1)
        }

    @staticmethod
    def _noch_auf_der_karte(verlauf: Rennverlauf, teilnehmer: int, zeit: float) -> bool:
        """Ob ein Auto noch auf der Streckengrafik steht (Punkt 63).

        Wer ausfaellt, bleibt eine Minute stehen - so sieht man, wo es
        passiert ist - und wird danach abgeraeumt. Sonst klebt am Ende
        ein halbes Feld regungslos auf der Karte.
        """
        ausfall = verlauf.ausfallzeit(teilnehmer)
        return ausfall is None or zeit - ausfall <= AUSFALL_SICHTBAR_MS

    @staticmethod
    def _runde_des_ersten(verlauf: Rennverlauf, reihenfolge: list[int], distanzen) -> int:
        """In welcher Runde der Fuehrende gerade ist (Punkt 65)."""
        if not reihenfolge:
            return 0
        erster = reihenfolge[0]
        strecke = max(verlauf.strecke.laenge_m, 1e-9)
        runde = int(max(float(distanzen[erster]), 0.0) // strecke) + 1
        return min(runde, verlauf.runden)

    @staticmethod
    def _zeit_des_ersten(verlauf: Rennverlauf, fuehrender: int, zeit: float) -> str:
        """Die Gesamtzeit oben in der Liste (GDD 4).

        Solange gefahren wird, laeuft die Rennuhr mit. Ist der Erste im
        Ziel, bleibt seine Zielzeit stehen - sonst tickte die Anzeige
        weiter, obwohl das Rennen fuer ihn gelaufen ist.
        """
        ergebnis = verlauf._ergebnis_je_auto.get(fuehrender)
        if ergebnis is not None and ergebnis.zeit_ms is not None and ergebnis.zeit_ms <= zeit:
            return formatiere_dauer(int(ergebnis.zeit_ms))
        return formatiere_dauer(int(zeit))

    @staticmethod
    def _abstand_im_ziel(verlauf: Rennverlauf, teilnehmer: int) -> str:
        """Der feststehende Rueckstand eines Autos im Ziel."""
        ergebnis = verlauf._ergebnis_je_auto.get(teilnehmer)
        if ergebnis is None:
            return ""
        if ergebnis.rundenrueckstand >= 1:
            return formatiere_runden_rueckstand(ergebnis.rundenrueckstand)
        if ergebnis.rueckstand_ms is None:
            return ""
        return formatiere_rueckstand(int(ergebnis.rueckstand_ms))

    def _fuelle_rangliste(
        self, verlauf: Rennverlauf, reihenfolge: list[int], distanzen, zeit: float
    ) -> None:
        """GDD 4: Gesamtzeit des Fuehrenden, Rueckstand der uebrigen."""
        self._merke_stand(self._rangliste)
        self._rangliste.blockSignals(True)
        self._rangliste.clear()
        self._rangliste.blockSignals(False)
        laenge = verlauf.strecke.laenge_m
        fuehrender = reihenfolge[0]
        vorne = float(distanzen[fuehrender])
        reifen = verlauf.reifen_zu(zeit)
        bild = verlauf.bild_zu(zeit)
        raus = verlauf.ausgefallen[bild]
        mischungen = verlauf.mischung_zu(zeit)
        vorher = self._plaetze_vorige_runde(verlauf, fuehrender, zeit)

        for platz, i in enumerate(reihenfolge, start=1):
            teilnehmer = verlauf.teilnehmer[i]
            distanz = float(distanzen[i])
            runde = min(int(max(distanz, 0.0) // laenge) + 1, verlauf.runden)

            if i == fuehrender:
                text = self._zeit_des_ersten(verlauf, fuehrender, zeit)
            elif verlauf.im_ziel_zu(i, zeit) and verlauf.im_ziel_zu(fuehrender, zeit):
                # Beide sind ueber der Linie - dann steht der Abstand fest
                # und wird nicht mehr aus Strecke und Tempo geschaetzt.
                text = self._abstand_im_ziel(verlauf, i)
            else:
                rueckstandsrunden = int((vorne - distanz) // laenge)
                if rueckstandsrunden >= 1:
                    text = formatiere_runden_rueckstand(rueckstandsrunden)
                else:
                    text = self._zeitabstand(verlauf, i, fuehrender, zeit)

            # GDD 4: Zwischenfaelle sind im Ranking markiert, die
            # Einzelheiten stehen im Mouseover.
            bisher = [z for z in verlauf.zwischenfaelle_von(i) if z.zeit_ms <= zeit]
            status = self._status(bisher, bool(raus[i]))

            # Punkt 76: Wie viele Plaetze seit Beginn dieser Runde gewonnen
            # oder verloren wurden.
            gewinn = vorher.get(i, platz) - platz

            zeile = QTreeWidgetItem(
                self._rangliste,
                [
                    str(platz),
                    teilnehmer.kuerzel,
                    self._nachname(teilnehmer),
                    self._teamname(teilnehmer),
                    self._wechseltext(gewinn),
                    str(runde),
                    text,
                    self._intervall(verlauf, reihenfolge, distanzen, zeit, platz),
                    self._tempotext(verlauf, i, zeit),
                    self._schnitttext(distanz, zeit),
                    self._mischungstext(verlauf, i, mischungen[i], zeit),
                    f"{reifen[i]:.0%}",
                    status,
                ],
            )
            zeile.setForeground(SPALTE_KUERZEL, QColor(teilnehmer.farbe))
            if gewinn:
                zeile.setForeground(
                    SPALTE_WECHSEL,
                    QColor(FARBE_GEWONNEN if gewinn > 0 else FARBE_VERLOREN),
                )
            self._faerbe_mischung(zeile, verlauf, i, zeit)
            zeile.setData(0, Qt.UserRole, i)
            zeile.setData(SPALTE_REIFEN, Balkenzeichner.ANTEILSROLLE, float(reifen[i]))
            # Die Zahl rechts, der Balken links - sonst liegen sie
            # uebereinander.
            zeile.setTextAlignment(SPALTE_REIFEN, Qt.AlignRight | Qt.AlignVCenter)
            if bisher:
                zeile.setToolTip(
                    SPALTE_STATUS,
                    "\n".join(f"Runde {z.runde}: {z.beschreibung}" for z in bisher),
                )
            if raus[i]:
                for spalte in range(self._rangliste.columnCount()):
                    zeile.setForeground(spalte, QColor("#8b93a1"))
            if teilnehmer.ist_spieler:
                schrift = zeile.font(SPALTE_KUERZEL)
                schrift.setBold(True)
                for spalte in range(SPALTE_ZEIT + 1):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._rangliste.columnCount()):
            if spalte != SPALTE_REIFEN:
                self._rangliste.resizeColumnToContents(spalte)
        self._stelle_auswahl_wieder_her(self._rangliste)

    @staticmethod
    def _pflicht_erfuellt(verlauf: Rennverlauf, i: int, zeit: float) -> bool:
        """Ob dieses Auto die Mischungspflicht schon erfuellt hat (Punkt 39).

        Gilt sie gar nicht - bei Regen, Starkregen oder wechselhaftem
        Wetter -, ist nichts zu erfuellen und die Spalte steht von Anfang
        an auf gruen.
        """
        if not verlauf.mischungspflicht:
            return True
        return len(verlauf.gefahrene_mischungen(i, zeit)) >= 2

    def _mischungstext(
        self, verlauf: Rennverlauf, i: int, kuerzel: str, zeit: float
    ) -> str:
        """Gefahrene Mischung, Zahl der Stopps und der Haken der Pflicht."""
        if not kuerzel:
            return "-"
        stopps = sum(1 for b in verlauf.boxenstopps if b.teilnehmer == i and b.zeit_ms <= zeit)
        text = f"{kuerzel} ({stopps})"
        return text + HAKEN if self._pflicht_erfuellt(verlauf, i, zeit) else text

    def _faerbe_mischung(
        self, zeile: QTreeWidgetItem, verlauf: Rennverlauf, i: int, zeit: float
    ) -> None:
        """Warnfarbe, solange die Pflicht offen ist; gruen, sobald sie steht."""
        if not verlauf.mischungen:
            return
        erfuellt = self._pflicht_erfuellt(verlauf, i, zeit)
        zeile.setForeground(
            SPALTE_MISCHUNG,
            QColor(FARBE_PFLICHT_ERFUELLT if erfuellt else FARBE_PFLICHT_OFFEN),
        )
        zeile.setToolTip(
            SPALTE_MISCHUNG,
            "Mischungspflicht erfuellt"
            if erfuellt
            else "Zweite Mischung steht noch aus",
        )

    def _intervall(
        self,
        verlauf: Rennverlauf,
        reihenfolge: list[int],
        distanzen,
        zeit: float,
        platz: int,
    ) -> str:
        """Abstand zum Auto direkt davor, in Sekunden (Punkt 1).

        Der Rueckstand daneben zaehlt zur Spitze; das Intervall sagt, wie
        weit der naechste Gegner entfernt ist - die Zahl, an der im Rennen
        haengt, ob ein Ueberholmanoever ueberhaupt in Reichweite ist.

        Gemessen wird am letzten **Messpunkt**, den das hintere Auto
        passiert hat (Punkt 75): Dort stand die Uhr fuer beide an
        derselben Stelle der Strecke. Damit summieren sich die Intervalle
        genau zum Rueckstand - gemessen an sechs Autos: 0,137 + 1,022 +
        0,053 + 0,726 + 0,163 = 2,101 s, und genau 2,101 s steht als
        Rueckstand des Sechsten.

        Frueher wurde aus Strecke geteilt durch Tempo geschaetzt. Das
        schwankte stark, weil zwei Autos an verschiedenen Streckenpunkten
        verschieden schnell sind, und die Intervalle summierten sich
        **nicht** zum Rueckstand - gemessen fuenf Intervalle zu 11,6 s
        gegen 9,0 s Rueckstand.
        """
        if platz <= 1:
            return "-"
        vorne = reihenfolge[platz - 2]
        hinten = reihenfolge[platz - 1]
        abstand = float(distanzen[vorne]) - float(distanzen[hinten])
        laenge = verlauf.strecke.laenge_m
        if abstand >= laenge:
            return formatiere_runden_rueckstand(int(abstand // laenge))
        # Punkt 83: Auch andersherum. Sortiert wird nach Runden und dann
        # nach Zielzeit (Punkt 67), deshalb kann ein Ueberrundeter, der
        # schon im Ziel ist, vor einem stehen, der noch faehrt - auf der
        # Strecke liegt er dann eine Runde **zurueck**. Ohne diesen Fall
        # landete ein Abstand von minus einer Runde in der Schaetzung
        # unten und kam als -1487467:14:28.515 heraus.
        if abstand <= -laenge:
            return f"-{int(-abstand // laenge)} Rd."
        return self._zeitabstand(verlauf, hinten, vorne, zeit)

    def _zeitabstand(
        self, verlauf: Rennverlauf, hinten: int, vorne: int, zeit: float
    ) -> str:
        """Der Zeitabstand zweier Autos am letzten gemeinsamen Messpunkt.

        Auf den ersten Metern eines Rennens hat noch keiner einen Punkt
        passiert; dann bleibt nur die alte Schaetzung aus Strecke und
        Tempo. Sobald der erste Messpunkt faellt, stehen echte Zeiten da.

        **Ein Minus ist moeglich und richtig so.** Zwischen zwei
        Messpunkten liegt rund ein Achtel Runde. Wer in dieser Zeit
        vorbeigeht, liegt jetzt vorn, war am letzten gemeinsamen Punkt
        aber noch hinten - dann steht dort ein negativer Wert, und der
        sagt genau das: seit dem letzten Split hat sich etwas geaendert.
        Gemessen kam das in 11,6 % der Bilder vor, vor allem in der ersten
        Runde, wo der einzige gemeinsame Punkt die Startlinie ist und die
        Zeiten dort noch die Startaufstellung tragen. Geschaetzt wird
        nichts - so hat es der Auftraggeber verlangt.
        """
        echt = verlauf.abstand_ms(hinten, vorne, zeit)
        if echt is not None:
            return formatiere_rueckstand(echt)
        distanzen = verlauf.distanzen_zu(zeit)
        abstand = float(distanzen[vorne]) - float(distanzen[hinten])
        tempo = self._tempo_naeherung(verlauf, vorne, zeit)
        # Punkt 83: Ein stehendes Auto hat kein Tempo, durch das sich
        # teilen liesse. Frueher fing ``max(tempo, 1e-6)`` das ab - und
        # machte aus einer Rundenlaenge rund anderthalb Millionen Stunden.
        # Wer steht, hat keinen Abstand in Sekunden; dann steht da nichts.
        if tempo <= TEMPO_STEHT:
            return "-"
        return formatiere_rueckstand(int(abstand / tempo * 1000))

    @staticmethod
    def _status(zwischenfaelle, ausgefallen: bool) -> str:
        """Kurzzeichen fuer die Rangliste (GDD 4)."""
        if ausgefallen:
            return "ausgefallen"
        zeichen = []
        fehler = sum(1 for z in zwischenfaelle if z.art == "fehler")
        defekte = sum(1 for z in zwischenfaelle if z.art == "defekt")
        if defekte:
            zeichen.append(f"Defekt x{defekte}" if defekte > 1 else "Defekt")
        if fehler:
            zeichen.append(f"{fehler} Fehler")
        return ", ".join(zeichen)

    @staticmethod
    def _tempo_naeherung(verlauf: Rennverlauf, i: int, zeit: float) -> float:
        """Tempo eines Autos aus zwei benachbarten Bildern, in m/s."""
        bild = verlauf.bild_zu(zeit)
        if bild >= len(verlauf.zeitpunkte_ms) - 1:
            bild = max(0, len(verlauf.zeitpunkte_ms) - 2)
        dt = (verlauf.zeitpunkte_ms[bild + 1] - verlauf.zeitpunkte_ms[bild]) / 1000.0
        return float(verlauf.distanz_m[bild + 1, i] - verlauf.distanz_m[bild, i]) / max(dt, 1e-6)

    @staticmethod
    def _beste_sektoren_im_feld(
        verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> dict[int, int]:
        """Je Sektor die schnellste Zeit, die **irgendwer** gefahren ist.

        Ueber alle Autos und alle bis dahin gefahrenen Runden - nicht nur
        ueber die letzte Runde. Wer einen davon haelt, bekommt ihn im
        Monitor lila.
        """
        bestzeiten: dict[int, int] = {}
        for i in reihenfolge:
            for nummer, sektor in enumerate(verlauf.protokolle[i].beste_sektoren_bis(zeit)):
                if sektor is None:
                    continue
                if nummer not in bestzeiten or sektor < bestzeiten[nummer]:
                    bestzeiten[nummer] = sektor
        return bestzeiten

    @staticmethod
    def _faerbe_lila(zeile: QTreeWidgetItem, spalte: int) -> None:
        """Ein Sektor in Lila und fett - die Bestzeit des ganzen Feldes."""
        zeile.setForeground(spalte, QColor(FARBE_BESTER_SEKTOR))
        schrift = zeile.font(spalte)
        schrift.setBold(True)
        zeile.setFont(spalte, schrift)

    def _fuelle_monitor(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> None:
        """GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten.

        Alles zum **Abspielzeitpunkt**: Der Monitor zeigte bisher die
        Zeiten vom Rennende, also Runden, die in der Uebertragung noch
        gar nicht gefahren waren.

        Sortiert wird nach der besten Runde - das ist die Frage, die
        dieser Monitor beantwortet. Wer noch keine Runde beendet hat,
        steht hinten.
        """
        self._merke_stand(self._monitor)
        self._monitor.blockSignals(True)
        self._monitor.clear()
        self._monitor.blockSignals(False)
        staende = {i: verlauf.protokolle[i].stand_zu(zeit) for i in reihenfolge}
        # Alle Fahrer, nicht nur die ersten zehn: Wer sein eigenes Auto
        # auf Platz 18 sucht, will dessen Sektorzeiten genauso sehen.
        nach_bestzeit = sorted(
            reihenfolge,
            key=lambda i: (staende[i][1] is None, staende[i][1] or 0, i),
        )
        laenge = verlauf.strecke.laenge_m
        bestzeiten = self._beste_sektoren_im_feld(verlauf, reihenfolge, zeit)
        for i in nach_bestzeit:
            letzte, beste, sektoren = staende[i]
            runde = self._beste_rundennummer(verlauf, i, zeit, beste)
            spalten = [
                verlauf.teilnehmer[i].kuerzel,
                self._nachname(verlauf.teilnehmer[i]),
                self._teamname(verlauf.teilnehmer[i]),
                formatiere_dauer(letzte) if letzte else "-",
                formatiere_dauer(beste) if beste else "-",
                str(runde) if runde else "-",
                f"{laenge / (beste / 1000.0) * 3.6:.1f}" if beste else "-",
            ]
            spalten += [formatiere_dauer(sektor) for sektor in sektoren]
            spalten += ["-"] * (MONITOR_SPALTEN - len(spalten))
            zeile = QTreeWidgetItem(self._monitor, spalten)
            # Punkt 82: Wer einen Sektor als Schnellster des ganzen Feldes
            # gefahren ist, bekommt ihn lila.
            for nummer, sektor in enumerate(sektoren):
                if bestzeiten.get(nummer) == sektor:
                    self._faerbe_lila(zeile, MONITOR_SEKTOR + nummer)
            zeile.setForeground(0, QColor(verlauf.teilnehmer[i].farbe))
            zeile.setData(0, Qt.UserRole, i)
            # Die letzte Runde leuchtet auf, wenn sie zugleich die beste
            # dieses Fahrers war - eine persoenliche Bestzeit sieht man
            # so im Vorbeilaufen.
            if letzte is not None and letzte == beste:
                zeile.setForeground(MONITOR_LETZTE, QColor(FARBE_PERSOENLICHE_BEST))
                schrift = zeile.font(MONITOR_LETZTE)
                schrift.setBold(True)
                zeile.setFont(MONITOR_LETZTE, schrift)
        for spalte in range(MONITOR_SPALTEN):
            self._monitor.resizeColumnToContents(spalte)
        self._stelle_auswahl_wieder_her(self._monitor)

    def _fuelle_ideal(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> None:
        """Was jeder haette fahren koennen (Punkt 82).

        Aufbau wie der Zeitenmonitor, aber die Sektoren sind die
        **persoenlich** besten - sie muessen nicht aus derselben Runde
        stammen. Ihre Summe ist die bestmoegliche Runde, und die Luecke
        daneben sagt, wieviel zwischen ihr und der wirklich gefahrenen
        Bestzeit liegt.

        Sortiert wird nach der moeglichen Zeit: Hier steht, wer das
        schnellste Auto haette, nicht wer es am besten zusammengebracht
        hat.
        """
        self._merke_stand(self._ideal)
        self._ideal.blockSignals(True)
        self._ideal.clear()
        self._ideal.blockSignals(False)
        moeglich = {i: verlauf.protokolle[i].ideale_runde_ms(zeit) for i in reihenfolge}
        bestzeiten = self._beste_sektoren_im_feld(verlauf, reihenfolge, zeit)
        gereiht = sorted(
            reihenfolge,
            key=lambda i: (moeglich[i] is None, moeglich[i] or 0, i),
        )
        for i in gereiht:
            protokoll = verlauf.protokolle[i]
            sektoren = protokoll.beste_sektoren_bis(zeit)
            _letzte, beste, _ = protokoll.stand_zu(zeit)
            kann = moeglich[i]
            luecke = beste - kann if beste is not None and kann is not None else None
            spalten = [
                verlauf.teilnehmer[i].kuerzel,
                self._nachname(verlauf.teilnehmer[i]),
                self._teamname(verlauf.teilnehmer[i]),
                formatiere_dauer(beste) if beste else "-",
                formatiere_dauer(kann) if kann else "-",
                f"-{formatiere_dauer(luecke)}" if luecke else "-",
            ]
            spalten += [formatiere_dauer(s) if s else "-" for s in sektoren]
            spalten += ["-"] * (IDEAL_SPALTEN - len(spalten))
            zeile = QTreeWidgetItem(self._ideal, spalten)
            zeile.setForeground(0, QColor(verlauf.teilnehmer[i].farbe))
            zeile.setData(0, Qt.UserRole, i)
            for nummer, sektor in enumerate(sektoren):
                if sektor is not None and bestzeiten.get(nummer) == sektor:
                    self._faerbe_lila(zeile, IDEAL_SEKTOR + nummer)
        for spalte in range(IDEAL_SPALTEN):
            self._ideal.resizeColumnToContents(spalte)
        self._stelle_auswahl_wieder_her(self._ideal)

    def _fuelle_meisterschaft(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> None:
        """Der Meisterschaftsstand, als waere das Rennen jetzt zu Ende.

        Eine **voruebergehende** Ansicht zum Abspielzeitpunkt: Zu den
        Punkten bis zu diesem Rennen kommen die, die jeder Fahrer fuer
        seine derzeitige Position bekaeme - samt schnellster Runde und
        Qualifying (GDD 13). Fortgeschrieben wird der Stand erst am
        Rennende, und zwar vom Saisonlauf, nicht von hier.
        """
        self._merke_stand(self._meisterschaft)
        self._meisterschaft.blockSignals(True)
        self._meisterschaft.clear()
        self._meisterschaft.blockSignals(False)
        if self._tabelle is None:
            return

        zeilen = kern_wertung.livewertung(
            self._konfiguration, self._tabelle, self._rennlage(verlauf, reihenfolge, zeit)
        )
        nummern = {t.nummer: i for i, t in enumerate(verlauf.teilnehmer)}
        for zeile in zeilen:
            stelle = nummern.get(zeile.fahrer)
            teilnehmer = verlauf.teilnehmer[stelle] if stelle is not None else None
            eintrag = QTreeWidgetItem(
                self._meisterschaft,
                [
                    str(zeile.platz),
                    teilnehmer.kuerzel if teilnehmer else "",
                    self._nachname(teilnehmer) if teilnehmer else "",
                    self._teamname(teilnehmer) if teilnehmer else "",
                    self._wechseltext(zeile.veraenderung),
                    str(zeile.punkte),
                    f"+{zeile.zuwachs}" if zeile.zuwachs else "",
                ],
            )
            if teilnehmer is not None:
                eintrag.setForeground(1, QColor(teilnehmer.farbe))
                eintrag.setData(0, Qt.UserRole, stelle)
            if zeile.veraenderung:
                eintrag.setForeground(
                    4,
                    QColor(
                        FARBE_GEWONNEN if zeile.veraenderung > 0 else FARBE_VERLOREN
                    ),
                )
        for spalte in range(self._meisterschaft.columnCount()):
            self._meisterschaft.resizeColumnToContents(spalte)
        self._stelle_auswahl_wieder_her(self._meisterschaft)

    def _rennlage(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> list:
        """Die derzeitige Lage im Rennen als Rennergebnisse (Punkt 73)."""
        quali = {}
        if self._qualifying is not None:
            for platz, stelle in enumerate(self._qualifying.aufstellung, start=1):
                quali[stelle] = platz
        schnellster = self._schnellste_runde_bis(verlauf, zeit)
        bild = verlauf.bild_zu(zeit)
        raus = verlauf.ausgefallen[bild]
        return [
            kern_wertung.Rennergebnis(
                fahrer=verlauf.teilnehmer[i].nummer,
                rennplatz=platz,
                qualifyingplatz=quali.get(i, verlauf.teilnehmer[i].startplatz),
                schnellste_runde=i == schnellster,
                ausgefallen=bool(raus[i]),
            )
            for platz, i in enumerate(reihenfolge, start=1)
        ]

    @staticmethod
    def _schnellste_runde_bis(verlauf: Rennverlauf, zeit: float) -> int | None:
        """Wer bis hierher die schnellste Runde gefahren ist."""
        bester = None
        beste = None
        for i in range(verlauf.anzahl):
            _, runde, _ = verlauf.protokolle[i].stand_zu(zeit)
            if runde is not None and (beste is None or runde < beste):
                bester, beste = i, runde
        return bester

    def _fuelle_ticker(self, verlauf: Rennverlauf, zeit: float) -> None:
        """Zwischenfaelle bis zur laufenden Rennzeit, neueste zuerst (Punkt 4)."""
        bisher = [z for z in verlauf.zwischenfaelle if z.zeit_ms <= zeit]
        self._tickerkasten.setTitle(f"Zwischenfaelle ({len(bisher)})")
        self._ticker.clear()
        for z in sorted(bisher, key=lambda z: -z.zeit_ms)[:TICKER_ZEILEN]:
            teilnehmer = verlauf.teilnehmer[z.teilnehmer]
            zeile = QTreeWidgetItem(
                self._ticker,
                [
                    formatiere_dauer(z.zeit_ms),
                    str(z.runde),
                    teilnehmer.kuerzel,
                    z.beschreibung,
                ],
            )
            zeile.setForeground(2, QColor(teilnehmer.farbe))
            # Spalte 0 sortiert nach Zeit, Spalte 2 traegt das Auto - dort
            # steht die Startnummer, damit der Doppelklick sie findet.
            zeile.setData(0, Qt.UserRole, int(z.zeit_ms))
            zeile.setData(2, Qt.UserRole, z.teilnehmer)
        for spalte in range(self._ticker.columnCount()):
            self._ticker.resizeColumnToContents(spalte)

    def _fahrernummer_in(self, spalte: int):
        """Liefert den Uebersetzer von einer Zeile zum Fahrer der Welt.

        Die Listen im Rennen fuehren die Startnummer im Feld, nicht die
        des Fahrers - eine Rangliste kennt keine Welt, nur Autos. Der
        Teilnehmer traegt die Fahrernummer mit; ein Feld aus
        ``rennen.starterfeld`` hat keinen Fahrer dahinter und liefert 0.
        In welcher Spalte die Startnummer steht, ist je Liste verschieden:
        Der Ticker braucht Spalte 0 zum Sortieren nach Zeit.
        """

        def nummer_von(zeile) -> int | None:
            stelle = zeile.data(spalte, Qt.UserRole)
            if stelle is None or self._verlauf is None:
                return None
            if not 0 <= int(stelle) < len(self._verlauf.teilnehmer):
                return None
            nummer = self._verlauf.teilnehmer[int(stelle)].nummer
            # Ein Feld aus ``rennen.starterfeld`` hat keine Fahrer
            # dahinter - dort traegt **jeder** die 0. Die Null eines
            # echten Feldes gehoert dagegen dem Spieler, und seine Karte
            # ging deshalb frueher nicht auf.
            if nummer == 0 and all(t.nummer == 0 for t in self._verlauf.teilnehmer):
                return None
            return nummer

        return nummer_von

    def _auswahl_geaendert(self, jetzt, _davor=None) -> None:
        """Merkt sich den gewaehlten Fahrer und hebt ihn hervor.

        Die Auswahl gilt fuer beide Listen und die Karte: Wer in der
        Rangliste ein Auto anklickt, sieht es auch im Zeitenmonitor und
        auf der Strecke markiert.
        """
        if jetzt is not None:
            nummer = jetzt.data(0, Qt.UserRole)
            if nummer is not None:
                self._gewaehlt = int(nummer)
        self._zeige_auswahl()

    def _zeige_auswahl(self) -> None:
        """Traegt die gemerkte Auswahl in Diagramm und Karte ein."""
        if self._verlauf is None:
            return
        hervor = [
            i
            for i, teilnehmer in enumerate(self._verlauf.teilnehmer)
            if teilnehmer.ist_spieler
        ]
        gewaehlt = self._gewaehlt
        if gewaehlt is not None and gewaehlt not in hervor:
            hervor.append(gewaehlt)
        self._rueckstand.hebe_hervor(hervor)
        # Punkt 58: Auf der Karte bekommt der gewaehlte Fahrer einen
        # goldenen Kreis - das Diagramm zeigt Linien, die Karte Punkte.
        self._ansicht.hebe_hervor(
            self._verlauf.teilnehmer[gewaehlt].kuerzel
            if gewaehlt is not None and gewaehlt < len(self._verlauf.teilnehmer)
            else ""
        )

    def _stelle_auswahl_wieder_her(self, liste) -> None:
        """Waehlt nach dem Neuaufbau dieselbe Zeile und denselben Stand.

        Beide Listen werden bei jedem Bild geleert und neu gefuellt. Ohne
        das hier waere die Auswahl nach 200 ms weg, und die Liste spraenge
        bei jedem Bild an den Anfang zurueck - wer weiter unten sucht,
        kaeme nie an.
        """
        balken = liste.verticalScrollBar()
        stand = getattr(liste, "_stand", balken.value())
        liste.blockSignals(True)
        if self._gewaehlt is not None:
            for stelle in range(liste.topLevelItemCount()):
                zeile = liste.topLevelItem(stelle)
                if zeile.data(0, Qt.UserRole) == self._gewaehlt:
                    liste.setCurrentItem(zeile)
                    break
        balken.setValue(min(stand, balken.maximum()))
        liste.blockSignals(False)

    @staticmethod
    def _merke_stand(liste) -> None:
        """Haelt den Rollstand fest, bevor die Liste geleert wird."""
        liste._stand = liste.verticalScrollBar().value()

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def rueckstandsansicht(self) -> Rueckstandsansicht:
        return self._rueckstand

    @property
    def ticker(self) -> QTreeWidget:
        return self._ticker

    @property
    def rangliste(self) -> QTreeWidget:
        return self._rangliste

    @property
    def monitor(self) -> QTreeWidget:
        return self._monitor

    @property
    def ideal(self) -> QTreeWidget:
        """Das Blatt "Bestmoegliche Runde" (Punkt 82)."""
        return self._ideal

    @property
    def meisterschaft(self) -> QTreeWidget:
        return self._meisterschaft

    @property
    def blaetter_rechts(self) -> QTabWidget:
        """Zeitenmonitor, Bestmoegliche Runde, Meisterschaft, Meldungen."""
        return self._monitorblaetter

    @property
    def verlauf(self) -> Rennverlauf | None:
        return self._verlauf

    @property
    def qualifying(self):
        """Das Qualifying, falls die Aufstellung daraus stammt."""
        return self._qualifying

    @property
    def zeit_ms(self) -> float:
        return self._zeit_ms
