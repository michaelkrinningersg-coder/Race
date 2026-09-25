"""Seite fuer ein Rennen: Strecke, Seitenleiste, Zeitenmonitor, Zeitraffer.

Der Verlauf wird vorab berechnet (GDD 15); diese Seite spielt ihn nur ab.
Deshalb kostet auch 100-facher Zeitraffer nichts - es wird lediglich in
groesseren Schritten aus dem fertigen Verlauf gelesen.
"""

from __future__ import annotations

import statistics
import time

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

from rennmanager.kern import gummierung as kern_gummierung
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.rennen import KEIN_FAHRER, Rennverlauf
from rennmanager.kern.welt import Welt
from rennmanager.kern.zeit import (
    formatiere_dauer,
    formatiere_rueckstand,
    formatiere_runden_rueckstand,
)
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.flaggen import BREITE_PX as FLAGGE_BREITE_PX
from rennmanager.ui.flaggen import setze_flagge
from rennmanager.ui.rueckstandsansicht import Rueckstandsansicht
from rennmanager.ui.streckenansicht import Streckenansicht
from rennmanager.ui.tabellen import (
    Balkenzeichner,
    kurzname,
    schriftfarbe,
    setze_breiten,
    verbinde_fahrerkarte,
)
from rennmanager.ui.wetterband import Wetterband

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
# Punkt 93: Der Balken sagt "wieviel", nicht "wie lange" (B35) und nicht
# "wie lange noch" (B36). Und B32: in welcher Runde der Plan den
# naechsten Stopp vorsieht - der Kern wusste es, die Anzeige zeigte es
# nicht.
SPALTE_ALTER = 12
SPALTE_REICHT = 13
SPALTE_PLANSTOPP = 14
SPALTE_STATUS = 15
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
# Punkt 82: die vier Blaetter des rechten Reiters, in der Reihenfolge,
# in der sie dort stehen. D2 fuellt nur das, welches man gerade sieht.
BLATT_MONITOR = 0
BLATT_IDEAL = 1
BLATT_MEISTERSCHAFT = 2
BLATT_TICKER = 3
# Punkt 93 (B53): Was die Stopps gekostet haben, je Fahrer.
BLATT_BOXENBILANZ = 4
BLATT_FUEHRUNG = 5
# Gruener Pfeil hoch, roter Pfeil runter - die Zahl daneben sagt, um wie
# viele Plaetze. Die Farbe ist nie die einzige Auskunft.
PFEIL_HOCH = "\u25b2"
PFEIL_RUNTER = "\u25bc"
FARBE_GEWONNEN = "#2e7d32"
FARBE_VERLOREN = "#c62828"
# So viele Zwischenfaelle stehen im Ticker; aeltere rollen heraus. Bei
# 40 Autos ueber die volle Distanz fallen mehrere hundert - zwoelf Zeilen
# waren davon das letzte Prozent, und wer zwei Bilder wegsah, hatte den
# Ausfall verpasst. Fuenfzig passen nicht ins Blatt; den Rollbalken setzt
# Qt dann von selbst, und gemessen bleibt der Rollstand ueber die
# Neuaufbauten hinweg stehen - anders als bei den Tabellen mit Auswahl
# braucht es dafuer hier nichts.
TICKER_ZEILEN = 50
# Punkt 93 (B59): Schriftgroesse der Rangliste im Kompaktmodus.
SCHRIFT_KOMPAKT = 14
# Punkt 93 (B49): Je Art ein eigenes Zeichen. Zwoelf Zeilen Fliesstext
# sehen alle gleich aus; ein Zeichen am Zeilenanfang laesst sich im
# Vorbeischauen zaehlen - "drei Defekte, ein Unfall".
TICKER_ZEICHEN = {
    kern_zwischenfall.Art.FEHLER: "⚠",   # Warndreieck
    kern_zwischenfall.Art.UNFALL: "✖",   # Kreuz
    kern_zwischenfall.Art.DEFEKT: "⚙",   # Zahnrad
}
# Vorschlag 2: Der Fuehrungswechsel ist **kein** Zwischenfall - er steht
# nicht in ``verlauf.zwischenfaelle`` und zaehlt nirgends als einer. Er
# bekommt trotzdem eine Zeile im Ticker, weil er dorthin gehoert: Was im
# Rennen passiert, steht hier. Deshalb ein eigenes Zeichen und eine
# eigene Farbe.
TICKER_FUEHRUNG = "⚑"
FARBE_FUEHRUNG = "#1565c0"
# Wer ausfaellt, bekommt dasselbe Zeichen in Rot - der Ausfall ist keine
# vierte Art, sondern das Ende einer der drei.
FARBE_AUSFALL = "#c62828"
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
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
        # D9: Derselbe Wert deckelt zusaetzlich in **Echtzeit**. Ohne das
        # war der Takt oben ab Stufe 50x wirkungslos, weil zwischen zwei
        # Bildern mehr Rennzeit liegt als die Schwelle.
        self._letzte_fuellung_s: float | None = None
        # D6: Nachnamen und Teams stehen beim Rennstart fest. Sie wurden
        # bisher in jedem Bild fuer jede Zeile neu aus der Welt geholt
        # und zerlegt - je 9000 Mal auf 150 Bilder.
        self._namen: list[str] = []
        self._teams: list[str] = []
        # Punkt 95: Dasselbe fuer die Fahrer, die **nicht** mitfahren -
        # in der Weltsicht der Meisterschaft stehen alle 400. Je Fahrer
        # einmal aus der Welt geholt, danach gemerkt.
        self._weltnamen: dict[int, tuple[str, str, str, str]] = {}
        # D7 und D10: je ein Puffer fuer das laufende Bild. Beide Werte
        # gelten fuer das ganze Feld, wurden aber je Zeile neu gerechnet.
        self._plaetze_puffer: tuple[object, dict[int, int]] = (None, {})
        self._tempo_puffer: tuple[object, object] = (None, None)

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
        # Punkt 93 (B43): Dasselbe Band wie im Qualifying (A13). Ein
        # Regenabschnitt in Runde 40 ist der Grund, warum eine Strategie
        # aufgeht oder nicht - und man sah ihn erst, wenn man hineinfuhr.
        self._wetterband = Wetterband()
        spalte.addWidget(self._wetterband)

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

        # Punkt 93 (B59): Nur die Rangliste, grosse Schrift - fuers reine
        # Zusehen. Und nebenbei der schnellste Modus ueberhaupt: Karte,
        # Rueckstandsdiagramm und das rechte Blatt fallen weg, und genau
        # die kosten den Loewenanteil der Zeit je Bild (siehe D1 bis D10).
        self._kompakt = QPushButton("Kompakt")
        self._kompakt.setCheckable(True)
        self._kompakt.setEnabled(False)
        self._kompakt.setToolTip(
            "Blendet Karte, Diagramm und die rechten Blaetter aus und "
            "vergroessert die Rangliste - fuers reine Zusehen."
        )
        self._kompakt.toggled.connect(self._setze_kompakt)

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
        zeile.addWidget(self._kompakt)
        self._wetteranzeige = QLabel("-")
        # Punkt 91: Wie viele verschiedene Strategien das Feld faehrt.
        # Der Planer laesst eine Handvoll Varianten zu und verteilt sie
        # zufaellig; hier steht, wie viele davon wirklich unterwegs sind.
        # Punkt 92: Ein Klick darauf oeffnet das Strategieblatt. Deshalb
        # ein Knopf und kein Etikett - ein Etikett sieht nicht aus, als
        # koennte man es anklicken.
        self._strategiezahl = QPushButton("-")
        self._strategiezahl.setFlat(True)
        self._strategiezahl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._strategiezahl.setToolTip(
            "Wie viele verschiedene Reifenstrategien im Feld gefahren werden. "
            "Zwei Autos auf derselben Variante zaehlen einmal, auch wenn "
            "ihre Stopprunden um eine Runde auseinanderliegen.\n"
            "Anklicken zeigt, welche Strategien vertreten sind."
        )
        self._strategiezahl.clicked.connect(self._zeige_strategien)
        zeile.addWidget(self._uhrzeit)
        zeile.addWidget(self._rundenstand)
        zeile.addWidget(self._fortschritt, stretch=1)
        zeile.addWidget(QLabel("Strategien:"))
        zeile.addWidget(self._strategiezahl)
        zeile.addSpacing(12)
        zeile.addWidget(QLabel("Wetter:"))
        zeile.addWidget(self._wetteranzeige)
        zeile.addSpacing(12)
        zeile.addWidget(QLabel("Takt:"))
        zeile.addWidget(self._takteingabe)
        return zeile

    def _zeige_strategien(self) -> None:
        """Punkt 92: Welche Strategien im Feld vertreten sind.

        Gezeigt wird der Stand zum gerade gespielten Zeitpunkt - der
        mittlere Rueckstand je Strategie wandert mit dem Rennen. Wer
        welche faehrt, bleibt geheim.
        """
        if self._verlauf is None or not self._verlauf.strategieblaetter:
            return
        from rennmanager.ui.strategieblatt import Strategieblattfenster

        fenster = Strategieblattfenster(self._verlauf, self._zeit_ms, self)
        fenster.exec()

    def _tabellen_faellig(self, zeit: float) -> bool:
        """Ob Rangliste und das sichtbare Blatt jetzt nachgezogen werden.

        Zwei Deckel, beide mit demselben Wert aus ``anzeige_takt_ms``:

        * In **Rennzeit**, damit die Listen bei jedem Tempo genauso oft
          stehenbleiben wie bei einfachem.
        * In **Echtzeit** (D9), damit sie es auch wirklich tun. Der erste
          Deckel allein war ab Stufe 50x wirkungslos: Dort liegen
          zwischen zwei Bildern mehr Rennsekunden als die Schwelle, also
          wurde in **jedem** Takt neu gefuellt - gemessen 14 ms Arbeit
          alle 33 ms.

        Ein Sprung umgeht beide, siehe ``_erzwinge_fuellung``.
        """
        davor = self._letzte_tabellen_ms
        if davor is not None and abs(zeit - davor) < self._anzeige_takt_ms:
            return False
        jetzt = time.perf_counter()
        zuletzt = self._letzte_fuellung_s
        if zuletzt is not None and (jetzt - zuletzt) * 1000.0 < self._anzeige_takt_ms:
            return False
        self._letzte_tabellen_ms = zeit
        self._letzte_fuellung_s = jetzt
        return True

    def _erzwinge_fuellung(self) -> None:
        """Der naechste Zeichenvorgang fuellt die Tabellen auf jeden Fall.

        Fuer Spruenge, den Taktwechsel und den Reiterwechsel: Was der
        Spieler gerade angestossen hat, soll sofort zu sehen sein und
        nicht erst, wenn der Takt es erlaubt.
        """
        self._letzte_tabellen_ms = None
        self._letzte_fuellung_s = None

    def _blatt_gewechselt(self, _index: int) -> None:
        """Ein frisch aufgeschlagenes Blatt sofort fuellen (D2)."""
        self._erzwinge_fuellung()
        self._zeichne()

    def _takt_geaendert(self, wert: int) -> None:
        """Uebernimmt einen neuen Anzeigetakt und zeichnet sofort neu."""
        self._anzeige_takt_ms = int(wert)
        self._erzwinge_fuellung()
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
                "Intervall", "km/h", "Ø km/h", "Mischung", "Reifen",
                "Alter", "Reicht", "Stopp", "Status",
            ]
        )
        self._rangliste.setRootIsDecorated(False)
        self._rangliste.setAlternatingRowColors(True)
        # Punkt 93 (B59): Wohin der Kompaktmodus zurueckschaltet. Die
        # Groesse kommt vom System, nicht von uns - sie darf deshalb
        # nicht fest eingetippt werden.
        self._schriftgroesse = self._rangliste.font().pointSize()
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
        # Vorschlag 23: Die Leiste steht senkrecht an der linken Kante,
        # und die Etiketten sind kurz. Beides zusammen, weil keines
        # allein reicht.
        #
        # Waagerecht brauchen die sechs Etiketten unter Linux 688 px und
        # bekommen 579 bei einem 1920er Fenster, 358 bei einem 1366er -
        # erst ab rund 2560 px passte es. Qt blendete Rollpfeile ein, und
        # das letzte Blatt war nur ueber den Pfeil erreichbar.
        #
        # Senkrecht ist Platz: Auf einem 1080er Schirm bleiben dem Blatt
        # 846 px Hoehe (1080 abzueglich 234 px fuer Menue, Suche,
        # Reiterleiste, Seitenkopf und Statuszeile).
        #
        # Das genuegte aber nur unter Linux. Gemessen auf dem
        # Windows-Runner brauchen **dieselben** Etiketten dort 1104 px
        # statt 688 - Segoe UI ist breiter als die Linux-Schrift, Faktor
        # 1,6. Senkrecht haette die Leiste damit auch auf Windows
        # gerollt, und Windows ist die Zielplattform (GDD 15). Deshalb
        # sind die Etiketten gekuerzt: gemessen 451 px unter Linux,
        # hochgerechnet 724 px auf Windows, also 122 px Luft.
        self._monitorblaetter.setTabPosition(QTabWidget.West)
        self._monitorblaetter.addTab(self._monitor, "Zeiten")
        self._monitorblaetter.addTab(self._ideal, "Idealrunde")
        self._monitorblaetter.addTab(self._meisterschaft, "Tabelle")
        # Punkt 82: Die Meldungen standen fest unter der Seite und nahmen
        # den Tabellen Hoehe weg. Als viertes Blatt stoeren sie nicht mehr
        # und sind trotzdem einen Klick entfernt.
        self._monitorblaetter.addTab(self._baue_ticker(), "Meldungen")
        self._monitorblaetter.addTab(self._baue_boxenbilanz(), "Boxen")
        # Punkt 102: Wer wie viele Runden vorn lag. Das Blatt zaehlt mit,
        # statt den Endstand vorwegzunehmen - man sieht die Fuehrung im
        # Rennen wandern.
        self._monitorblaetter.addTab(self._baue_fuehrung(), "Fuehrung")
        # D2: Ein frisch aufgeschlagenes Blatt steht sonst so lange leer
        # oder veraltet da, bis der naechste Takt faellig ist.
        self._monitorblaetter.currentChanged.connect(self._blatt_gewechselt)
        return self._monitorblaetter

    def _baue_ticker(self) -> QWidget:
        # Punkt 4: Fehler, Unfaelle und Defekte laufen mit, neueste zuerst.
        self._ticker = QTreeWidget()
        self._ticker.setHeaderLabels(["", "Zeit", "Rd", "Auto", "Was"])
        self._ticker.setRootIsDecorated(False)
        self._ticker.setAlternatingRowColors(True)
        verbinde_fahrerkarte(
            self._ticker, self.fahrerkarte_gewuenscht.emit, self._fahrernummer_in(3)
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
        self._wetterband.zeige(verlauf.wetter, verlauf.dauer_ms)
        self._kompakt.setEnabled(True)
        # Punkt 91: Steht einmal je Rennen fest und aendert sich nicht.
        self._strategiezahl.setText(
            str(verlauf.strategiezahl) if verlauf.strategiezahl else "-"
        )
        self._strategiezahl.setEnabled(bool(verlauf.strategieblaetter))
        for knopf in (self._abspielen, self._zurueck, self._sofort):
            knopf.setEnabled(True)
        self._waehle_zeitraffer()
        # D6: Namen und Teams einmal aufloesen, nicht je Zeile je Bild.
        self._namen = [self._nachname(t) for t in verlauf.teilnehmer]
        self._teams = [self._teamname(t) for t in verlauf.teilnehmer]
        # Nach einem Auf- oder Abstieg steht derselbe Fahrer in einem
        # anderen Team; das Gedaechtnis der Weltsicht faengt deshalb mit
        # jedem Rennen neu an.
        self._weltnamen.clear()
        # D1: Die Spalten werden **einmal** je Rennen ausgemessen. Bisher
        # rief jede Fuellung ``resizeColumnToContents`` fuer jede Spalte
        # jeder Tabelle auf - 37 Aufrufe je Bild.
        self._setze_spaltenbreiten(verlauf)
        self._springe(0)

        # Das Rennen laeuft von selbst los, damit es sich wie eine
        # Uebertragung anfuehlt und nicht wie eine Auswertung - aber erst,
        # wenn man auch hinschaut.
        if self._konfiguration.wert("zeitraffer", "automatisch_starten"):
            if self.isVisible():
                self._umschalten()
            else:
                self._startet_beim_zeigen = True

    def _setze_spaltenbreiten(self, verlauf: Rennverlauf) -> None:
        """Alle Spalten einmal je Rennen ausmessen (D1).

        Die Probetexte sind der breiteste Fall, den die Spalte je zeigt.
        Fuer Namen, Teams und Kuerzel muss nichts geraten werden - das
        Feld steht beim Rennstart fest, also wird der laengste genommen.
        Fuer Zeiten und Zahlen steht der Extremfall da: eine Rundenzeit
        ist nie laenger als ``1:23:45.678``.

        Die Spalte mit dem Reifenbalken bleibt ausgespart; sie hat ihre
        eigene Breite aus ``BREITE_REIFEN``.
        """
        def laengster(werte, ersatz: str) -> str:
            gefunden = max(werte, key=len, default="")
            return gefunden if gefunden else ersatz

        teilnehmer = verlauf.teilnehmer
        name = laengster(self._namen, "Mustermann")
        # Punkt 105: Neben dem Namen steht die Flagge - sie braucht ihre
        # Breite plus einen Abstand, sonst schneidet Qt den Namen ab.
        mit_flagge = (name, FLAGGE_BREITE_PX + 6)
        team = laengster(self._teams, "Rennstall")
        kuerzel = laengster([t.kuerzel for t in teilnehmer], "A30")
        dauer = "1:23:45.678"
        abstand = "+1:23.456"
        sektor = "0:59.999"

        setze_breiten(self._rangliste, [
            "30", kuerzel, mit_flagge, team, f"{PFEIL_RUNTER} 12", "48",
            dauer, abstand, "320", "288,8", f"WW (4){HAKEN}", None,
            "88 Rd", "88 Rd", "R88",
            "Defekt x2, 3 Fehler",
        ])
        setze_breiten(self._monitor, [
            kuerzel, mit_flagge, team, dauer, dauer, "48", "288,8",
            sektor, sektor, sektor, sektor,
        ])
        setze_breiten(self._ideal, [
            kuerzel, mit_flagge, team, dauer, dauer, abstand,
            sektor, sektor, sektor, sektor,
        ])
        setze_breiten(self._meisterschaft, [
            "30", kuerzel, mit_flagge, team, f"{PFEIL_RUNTER} 12", "888", "+40",
        ])
        setze_breiten(self._ticker, ["⚙", dauer, "48", kuerzel,
                                     "Dreher in der Schikane, 8,4 s verloren"])

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
        self._erzwinge_fuellung()
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
        self._wetterband.setze_marke(zeit)

        if verlauf.wetter is not None:
            zustand = verlauf.wetter.zustand_zu(zeit)
            grip = verlauf.wetter.grip_zu(zeit)
            # Punkt 88: Was die Strecke inzwischen an Gummi liegen hat.
            # Ein Prozent davon ist rund eine Sekunde Rundenzeit.
            gummi = kern_gummierung.anteil(
                self._konfiguration, verlauf.gummierung_zu(zeit)
            )
            self._wetteranzeige.setText(
                f"{zustand}  (Grip {grip:.2f})   Strecke +{gummi * 100:.2f} %"
            )

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
            self._fuelle_sichtbares_blatt(verlauf, reihenfolge, zeit)
        self._rueckstand.setze_marke(zeit)

    def _fuelle_sichtbares_blatt(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> None:
        """Nur das Blatt fuellen, das man gerade sieht (D2).

        Zeitenmonitor, Bestmoegliche Runde, Meisterschaft und Meldungen
        liegen in **einem** Reiter; sichtbar ist immer genau eines.
        Gefuellt wurden bisher alle vier, in jedem Bild - gemessen ein
        Drittel der Zeit, die ein Bild kostet, fuer Tabellen, die niemand
        sieht. Beim Reiterwechsel zieht ``_blatt_gewechselt`` sofort nach.
        """
        blatt = self._monitorblaetter.currentIndex()
        if blatt == BLATT_MONITOR:
            self._fuelle_monitor(verlauf, reihenfolge, zeit)
        elif blatt == BLATT_IDEAL:
            self._fuelle_ideal(verlauf, reihenfolge, zeit)
        elif blatt == BLATT_MEISTERSCHAFT:
            self._fuelle_meisterschaft(verlauf, reihenfolge, zeit)
        elif blatt == BLATT_TICKER:
            self._fuelle_ticker(verlauf, zeit)
        elif blatt == BLATT_BOXENBILANZ:
            self._fuelle_boxenbilanz(verlauf, reihenfolge, zeit)
        elif blatt == BLATT_FUEHRUNG:
            self._fuelle_fuehrung(verlauf, zeit)

    def _teamname(self, teilnehmer) -> str:
        """Das Team hinter einem Auto (Punkt 82).

        Wie ``_nachname``: Ein Feld aus ``rennen.starterfeld`` hat keinen
        Fahrer dahinter, dann bleibt die Spalte leer.
        """
        nummer = getattr(teilnehmer, "nummer", KEIN_FAHRER)
        if self._welt is None or not 0 <= nummer < len(self._welt.fahrer):
            return ""
        return self._welt.team_von(self._welt.fahrer[nummer]).name

    def _nachname(self, teilnehmer) -> str:
        """Der Name des Fahrers hinter einem Auto (Punkte 60 und 98).

        Ein Kuerzel wie "MKR" sagt niemandem etwas; der Name schon.
        Nachname voll, Vorname als Anfangsbuchstabe - "M. Krinninger":
        In vierzig Zeilen kostet ein ausgeschriebener Vorname eine halbe
        Spaltenbreite und trennt nichts, was der erste Buchstabe nicht
        auch trennt. Ein Feld aus ``rennen.starterfeld`` hat keinen
        Fahrer dahinter - dann bleibt die Spalte leer.
        """
        nummer = getattr(teilnehmer, "nummer", KEIN_FAHRER)
        if self._welt is None or not 0 <= nummer < len(self._welt.fahrer):
            return ""
        return kurzname(self._welt.fahrer[nummer].name)

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

    def _plaetze_vorige_runde(
        self, verlauf: Rennverlauf, fuehrender: int, zeit: float
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
        # D7: Das kostet ein zweites ``reihenfolge_zu`` samt Interpolation
        # und Sortierung - fuer einen Zeitpunkt, der sich nur beim
        # Rundenwechsel des Fuehrenden aendert, nicht je Bild.
        schluessel = (id(verlauf), fuehrender, rundenbeginn)
        if self._plaetze_puffer[0] == schluessel:
            return self._plaetze_puffer[1]
        plaetze = {
            auto: platz
            for platz, auto in enumerate(verlauf.reihenfolge_zu(rundenbeginn), start=1)
        }
        self._plaetze_puffer = (schluessel, plaetze)
        return plaetze

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

    def _reichttext(self, verlauf: Rennverlauf, i: int, runde: int, zeit: float) -> str:
        """Punkt 93 (B36): Wie viele Runden der Satz noch traegt.

        Gerechnet gegen die Zwangsstopp-Grenze: Darunter kommt das Auto
        herein, ob es will oder nicht. Die Zahl macht die Grenze
        sichtbar, bevor sie zuschlaegt.
        """
        schwelle = self._konfiguration.wert(
            "boxenstopp", "strategie", "notstopp_ab_restprofil"
        )
        rest = verlauf.restrunden(i, runde, zeit, schwelle)
        return "-" if rest is None else f"{rest} Rd"

    def _planstopptext(self, verlauf: Rennverlauf, i: int, runde: int) -> str:
        """Punkt 93 (B32): In welcher Runde der Plan den naechsten Stopp vorsieht."""
        naechster = verlauf.naechster_planstopp(i, runde)
        return "-" if naechster is None else f"R{naechster}"

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
                    self._namen[i],
                    self._teams[i],
                    self._wechseltext(gewinn),
                    str(runde),
                    text,
                    self._intervall(verlauf, reihenfolge, distanzen, zeit, platz),
                    self._tempotext(verlauf, i, zeit),
                    self._schnitttext(distanz, zeit),
                    self._mischungstext(verlauf, i, mischungen[i], zeit),
                    f"{reifen[i]:.0%}",
                    f"{verlauf.reifenalter(i, runde, zeit)} Rd",
                    self._reichttext(verlauf, i, runde, zeit),
                    self._planstopptext(verlauf, i, runde),
                    status,
                ],
            )
            zeile.setForeground(SPALTE_KUERZEL, schriftfarbe(teilnehmer.farbe))
            # Punkt 105: Die Flagge steht im Namensfeld, nicht in einer
            # eigenen Spalte - die Rangliste ist ohnehin zu schmal.
            setze_flagge(zeile, SPALTE_NAME, teilnehmer.land)
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

        **Geschaetzt wird gar nichts** (Punkt 103). Solange die beiden
        keinen gemeinsamen Messpunkt passiert haben, steht hier ein
        Strich. Der erste Messpunkt einer Runde liegt auf der
        Start/Ziel-Linie - vor seiner ersten Ueberfahrt hat ein Fahrer
        also keinen Rueckstand, und die Anzeige behauptet auch keinen.

        Davor stand hier eine Schaetzung aus Strecke geteilt durch Tempo.
        Auf dem Standbild vor dem Start kam dabei Unsinn heraus: Die
        Autos kriechen im ersten Bild mit 0,345 m/s los, und 5 m
        Startabstand geteilt durch dieses Tempo ergaben 14,47 s **je
        Startplatz** - der Fuenfzigste lag 11:49 zurueck, bevor das
        Rennen begonnen hatte. Die Schwelle ``TEMPO_STEHT`` fing das
        nicht ab, weil die Autos eben nicht ganz standen.

        **Ein Minus ist moeglich und richtig so.** Zwischen zwei
        Messpunkten liegt rund ein Achtel Runde. Wer in dieser Zeit
        vorbeigeht, liegt jetzt vorn, war am letzten gemeinsamen Punkt
        aber noch hinten - dann steht dort ein negativer Wert, und der
        sagt genau das: seit dem letzten Split hat sich etwas geaendert.
        Gemessen kam das in 11,6 % der Bilder vor, vor allem in der
        ersten Runde.
        """
        echt = verlauf.abstand_ms(hinten, vorne, zeit)
        return formatiere_rueckstand(echt) if echt is not None else "-"

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

    def _tempi(self, verlauf: Rennverlauf, zeit: float):
        """Das Momentantempo **aller** Autos zu diesem Zeitpunkt, in m/s.

        D10: Gerechnet wurde das je Zeile - dreissigmal je Bild dieselbe
        Suche nach dem Bild, dieselbe Zeitdifferenz, und dann eine
        einzelne Subtraktion. Als Vektor ist es ein Zugriff.
        """
        schluessel = (id(verlauf), zeit)
        if self._tempo_puffer[0] == schluessel:
            return self._tempo_puffer[1]
        bild = verlauf.bild_zu(zeit)
        if bild >= len(verlauf.zeitpunkte_ms) - 1:
            bild = max(0, len(verlauf.zeitpunkte_ms) - 2)
        dt = (verlauf.zeitpunkte_ms[bild + 1] - verlauf.zeitpunkte_ms[bild]) / 1000.0
        tempi = (verlauf.distanz_m[bild + 1] - verlauf.distanz_m[bild]) / max(dt, 1e-6)
        self._tempo_puffer = (schluessel, tempi)
        return tempi

    def _tempo_naeherung(self, verlauf: Rennverlauf, i: int, zeit: float) -> float:
        """Tempo eines Autos aus zwei benachbarten Bildern, in m/s."""
        return float(self._tempi(verlauf, zeit)[i])

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
                self._namen[i],
                self._teams[i],
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
            zeile.setForeground(0, schriftfarbe(verlauf.teilnehmer[i].farbe))
            zeile.setData(0, Qt.UserRole, i)
            setze_flagge(zeile, 1, verlauf.teilnehmer[i].land)
            # Die letzte Runde leuchtet auf, wenn sie zugleich die beste
            # dieses Fahrers war - eine persoenliche Bestzeit sieht man
            # so im Vorbeilaufen.
            if letzte is not None and letzte == beste:
                zeile.setForeground(MONITOR_LETZTE, QColor(FARBE_PERSOENLICHE_BEST))
                schrift = zeile.font(MONITOR_LETZTE)
                schrift.setBold(True)
                zeile.setFont(MONITOR_LETZTE, schrift)
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
                self._namen[i],
                self._teams[i],
                formatiere_dauer(beste) if beste else "-",
                formatiere_dauer(kann) if kann else "-",
                f"-{formatiere_dauer(luecke)}" if luecke else "-",
            ]
            spalten += [formatiere_dauer(s) if s else "-" for s in sektoren]
            spalten += ["-"] * (IDEAL_SPALTEN - len(spalten))
            zeile = QTreeWidgetItem(self._ideal, spalten)
            zeile.setForeground(0, schriftfarbe(verlauf.teilnehmer[i].farbe))
            zeile.setData(0, Qt.UserRole, i)
            setze_flagge(zeile, 1, verlauf.teilnehmer[i].land)
            for nummer, sektor in enumerate(sektoren):
                if sektor is not None and bestzeiten.get(nummer) == sektor:
                    self._faerbe_lila(zeile, IDEAL_SEKTOR + nummer)
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

        lage = self._rennlage(verlauf, reihenfolge, zeit)
        zeilen = kern_wertung.livewertung(self._konfiguration, self._tabelle, lage)
        nummern = {t.nummer: i for i, t in enumerate(verlauf.teilnehmer)}
        for zeile in zeilen:
            stelle = nummern.get(zeile.fahrer)
            if stelle is not None:
                teilnehmer = verlauf.teilnehmer[stelle]
                kuerzel, name, team = (
                    teilnehmer.kuerzel, self._namen[stelle], self._teams[stelle]
                )
                farbe = teilnehmer.farbe
                land = teilnehmer.land
            else:
                # Ein Testrennen kann ein Feld fahren, das nicht der Welt
                # entspricht; dann steht in der Tabelle jemand, der hier
                # nicht mitfaehrt.
                kuerzel, name, team, farbe = self._aus_der_welt(zeile.fahrer)
                land = self._land_aus_der_welt(zeile.fahrer)
            eintrag = QTreeWidgetItem(
                self._meisterschaft,
                [
                    str(zeile.platz),
                    kuerzel,
                    name,
                    team,
                    self._wechseltext(zeile.veraenderung),
                    str(zeile.punkte),
                    f"+{zeile.zuwachs}" if zeile.zuwachs else "",
                ],
            )
            if farbe:
                eintrag.setForeground(1, schriftfarbe(farbe))
            setze_flagge(eintrag, 2, land)
            if stelle is not None:
                eintrag.setData(0, Qt.UserRole, stelle)
            if zeile.veraenderung:
                eintrag.setForeground(
                    4,
                    QColor(
                        FARBE_GEWONNEN if zeile.veraenderung > 0 else FARBE_VERLOREN
                    ),
                )
        self._stelle_auswahl_wieder_her(self._meisterschaft)

    def _land_aus_der_welt(self, nummer: int) -> str:
        """Die Nation eines Fahrers, der nicht im Feld steht (Punkt 105)."""
        if self._welt is None or not 0 <= nummer < len(self._welt.fahrer):
            return ""
        return self._welt.fahrer[nummer].land

    def _aus_der_welt(self, nummer: int) -> tuple[str, str, str, str]:
        """Kuerzel, Nachname, Team und Farbe eines Fahrers ausserhalb des Rennens.

        Gemerkt wird das Ergebnis: Die Weltsicht wird in jedem Anzeigetakt
        neu gefuellt, die Namen aendern sich dabei nicht (wie ``_namen``
        und ``_teams`` fuer das Feld, D6).
        """
        bekannt = self._weltnamen.get(nummer)
        if bekannt is not None:
            return bekannt
        if self._welt is None or not 0 <= nummer < len(self._welt.fahrer):
            return ("", "", "", "")
        fahrer = self._welt.fahrer[nummer]
        team = self._welt.team_von(fahrer)
        # Die Farbe gehoert dem Team, nicht dem Auto (GDD 4 und 12).
        bekannt = (fahrer.kuerzel, kurzname(fahrer.name), team.name, team.farbe)
        self._weltnamen[nummer] = bekannt
        return bekannt

    def _rennlage(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> list:
        """Die derzeitige Lage im Rennen als Rennergebnisse (Punkt 73).

        Der Qualifyingplatz ist der **Startplatz**: ``saison.startfeld``
        stellt das Rennfeld in der Reihenfolge des Qualifyings auf, Platz
        1 ist die Pole. Frueher stand hier eine Umrechnung ueber
        ``qualifying.aufstellung`` - deren Zahlen zaehlen aber im Feld der
        Session (nach Weltreihenfolge) und nicht im Starterfeld. Die
        Qualifyingpunkte des Livestands landeten dadurch bei den falschen
        Fahrern: Auf dem Standbild vor dem Start bekam der Pilot auf der
        Pole keinen Polepunkt, dafuer irgendwer im Mittelfeld.
        """
        schnellster = self._schnellste_runde_bis(verlauf, zeit)
        bild = verlauf.bild_zu(zeit)
        raus = verlauf.ausgefallen[bild]
        return [
            kern_wertung.Rennergebnis(
                fahrer=verlauf.teilnehmer[i].nummer,
                rennplatz=platz,
                qualifyingplatz=verlauf.teilnehmer[i].startplatz,
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

    def _setze_kompakt(self, an: bool) -> None:
        """Punkt 93 (B59): Nur die Rangliste, grosse Schrift.

        Die ausgeblendeten Teile werden nicht nur versteckt, sondern
        auch **nicht mehr gefuellt**: Karte, Rueckstandsdiagramm und das
        rechte Blatt kosten den Loewenanteil der Zeit je Bild (siehe D1
        bis D10). Der Modus ist damit nebenbei der schnellste ueberhaupt.
        """
        self._blaetter.setVisible(not an)
        self._monitorblaetter.setVisible(not an)
        schrift = self._rangliste.font()
        schrift.setPointSize(SCHRIFT_KOMPAKT if an else self._schriftgroesse)
        self._rangliste.setFont(schrift)
        self._rangliste.header().setFont(schrift)
        if self._verlauf is not None:
            self._setze_spaltenbreiten(self._verlauf)
            self._erzwinge_fuellung()
            self._zeichne()

    @property
    def kompakt(self) -> bool:
        return self._kompakt.isChecked()

    def _baue_boxenbilanz(self) -> QWidget:
        """Punkt 93 (B53): Standzeit, Gesamtverlust, Vergleich zum Feld."""
        self._boxenbilanz = QTreeWidget()
        self._boxenbilanz.setHeaderLabels(
            ["Auto", "Fahrer", "Team", "Stopps", "Standzeit", "Verlust", "zum Feld"]
        )
        self._boxenbilanz.setRootIsDecorated(False)
        self._boxenbilanz.setAlternatingRowColors(True)
        verbinde_fahrerkarte(
            self._boxenbilanz, self.fahrerkarte_gewuenscht.emit, self._fahrernummer_in(0)
        )
        return self._boxenbilanz

    def _fuelle_boxenbilanz(
        self, verlauf: Rennverlauf, reihenfolge: list[int], zeit: float
    ) -> None:
        """Punkt 93 (B53): Was die Stopps bis hierher gekostet haben.

        "Zum Feld" misst gegen den **Median derer, die schon gestoppt
        haben** - gegen das Feldmittel waere es unfair: Wer noch nicht
        drin war, hat null Verlust, und mit dem im Nenner saehe jeder
        Stopper schlecht aus.
        """
        self._boxenbilanz.clear()
        bilanzen = {i: verlauf.stoppbilanz(i, zeit) for i in reihenfolge}
        verluste = [v for _n, _s, v in bilanzen.values() if v > 0]
        mittel = statistics.median(verluste) if verluste else 0

        for i in reihenfolge:
            anzahl, standzeit, verlust = bilanzen[i]
            teilnehmer = verlauf.teilnehmer[i]
            zeile = QTreeWidgetItem(
                self._boxenbilanz,
                [
                    teilnehmer.kuerzel,
                    self._namen[i],
                    self._teams[i],
                    str(anzahl),
                    formatiere_rueckstand(standzeit) if anzahl else "-",
                    formatiere_rueckstand(verlust) if anzahl else "-",
                    (
                        formatiere_rueckstand(verlust - int(mittel))
                        if anzahl and mittel
                        else "-"
                    ),
                ],
            )
            zeile.setForeground(0, schriftfarbe(teilnehmer.farbe))
            zeile.setData(0, Qt.UserRole, i)
            setze_flagge(zeile, 1, verlauf.teilnehmer[i].land)
            if anzahl and mittel:
                zeile.setForeground(
                    6,
                    QColor(FARBE_GEWONNEN if verlust <= mittel else FARBE_VERLOREN),
                )
            if teilnehmer.ist_spieler:
                schrift = zeile.font(0)
                schrift.setBold(True)
                for spalte in range(self._boxenbilanz.columnCount()):
                    zeile.setFont(spalte, schrift)

    def _baue_fuehrung(self) -> QWidget:
        """Punkt 102: Runden in Fuehrung, an der Start/Ziel-Linie gezaehlt."""
        self._fuehrung = QTreeWidget()
        self._fuehrung.setHeaderLabels(
            ["Auto", "Fahrer", "Team", "Runden", "Anteil", "von"]
        )
        self._fuehrung.headerItem().setToolTip(
            3,
            "Runden, die dieses Auto als Erster an der Start/Ziel-Linie "
            "abgeschlossen hat. Die Startaufstellung zaehlt nicht mit - "
            "gefuehrt wird eine Runde erst, wenn sie gefahren ist.",
        )
        self._fuehrung.setRootIsDecorated(False)
        self._fuehrung.setAlternatingRowColors(True)
        verbinde_fahrerkarte(
            self._fuehrung, self.fahrerkarte_gewuenscht.emit, self._fahrernummer_in(0)
        )
        self._fuehrungskasten = QGroupBox("Fuehrungsrunden")
        spalte = QVBoxLayout(self._fuehrungskasten)
        spalte.addWidget(self._fuehrung)
        return self._fuehrungskasten

    def _fuelle_fuehrung(self, verlauf: Rennverlauf, zeit: float) -> None:
        """Wer bis hierher wie viele Runden vorn lag (Punkt 102).

        Sortiert nach Runden, nicht nach der Rennposition: Die Frage ist,
        wer das Rennen bestimmt hat, und die beantwortet keine Rangliste.
        Wer nie vorn lag, steht nicht in der Liste - bei 50 Autos waeren
        das sonst 45 leere Zeilen.
        """
        self._fuehrung.clear()
        gezaehlt = verlauf.fuehrungsrunden(zeit)
        gesamt = sum(gezaehlt)
        wechsel = verlauf.fuehrungswechsel(zeit)
        self._fuehrungskasten.setTitle(
            f"Fuehrungsrunden - {gesamt} von {verlauf.runden} Runden gefahren, "
            f"{wechsel} Wechsel an der Linie"
        )
        if not gesamt:
            return

        for i, runden in sorted(
            enumerate(gezaehlt), key=lambda paar: (-paar[1], paar[0])
        ):
            if not runden:
                continue
            teilnehmer = verlauf.teilnehmer[i]
            zeile = QTreeWidgetItem(
                self._fuehrung,
                [
                    teilnehmer.kuerzel,
                    self._namen[i],
                    self._teams[i],
                    str(runden),
                    f"{runden / gesamt:.0%}",
                    str(gesamt),
                ],
            )
            zeile.setForeground(0, schriftfarbe(teilnehmer.farbe))
            zeile.setData(0, Qt.UserRole, i)
            setze_flagge(zeile, 1, verlauf.teilnehmer[i].land)
            if teilnehmer.ist_spieler:
                schrift = zeile.font(0)
                schrift.setBold(True)
                for spalte in range(self._fuehrung.columnCount()):
                    zeile.setFont(spalte, schrift)

    def _fuehrungsmeldungen(
        self, verlauf: Rennverlauf, zeit: float
    ) -> list[tuple[int, int, int, str]]:
        """Die Fuehrungswechsel bis hierher (Vorschlag 2).

        ``(Zeit, Runde, Auto, Text)`` je Wechsel. Der Zeitpunkt ist die
        Ueberfahrt an der Start/Ziel-Linie - der Moment, in dem der
        Wechsel wirklich stattfindet (Punkt 102).

        Der erste Fuehrende ist kein Wechsel: Dass der Erste der ersten
        Runde fuehrt, ist keine Meldung wert.
        """
        meldungen: list[tuple[int, int, int, str]] = []
        davor: int | None = None
        for runde, (wer, ende) in enumerate(verlauf.fuehrender_je_runde, start=1):
            if ende > zeit:
                break
            if davor is not None and wer != davor:
                meldungen.append(
                    (
                        int(ende),
                        runde,
                        wer,
                        f"uebernimmt die Fuehrung von "
                        f"{verlauf.teilnehmer[davor].kuerzel}",
                    )
                )
            davor = wer
        return meldungen

    def _fuelle_ticker(self, verlauf: Rennverlauf, zeit: float) -> None:
        """Was bis zur laufenden Rennzeit passiert ist, neueste zuerst.

        Zwei Quellen in einer Liste: die Zwischenfaelle aus Punkt 4 und
        die Fuehrungswechsel aus Punkt 102 (Vorschlag 2). Gezaehlt werden
        sie **getrennt** - ein Fuehrungswechsel ist kein Zwischenfall,
        und eine Ueberschrift, die beides zusammenwirft, luegt.
        """
        bisher = [z for z in verlauf.zwischenfaelle if z.zeit_ms <= zeit]
        wechsel = self._fuehrungsmeldungen(verlauf, zeit)
        self._tickerkasten.setTitle(
            f"Meldungen - {len(bisher)} Zwischenfaelle, "
            f"{len(wechsel)} Fuehrungswechsel"
        )
        self._ticker.clear()

        # Beide Quellen auf dieselbe Form bringen, dann gemeinsam sortieren.
        eintraege: list[tuple[int, object]] = [(int(z.zeit_ms), z) for z in bisher]
        eintraege += [(m[0], m) for m in wechsel]
        for _zeitpunkt, was in sorted(
            eintraege, key=lambda paar: -paar[0]
        )[:TICKER_ZEILEN]:
            if isinstance(was, tuple):
                zeitpunkt, runde, stelle, text = was
                teilnehmer = verlauf.teilnehmer[stelle]
                zeile = QTreeWidgetItem(
                    self._ticker,
                    [
                        TICKER_FUEHRUNG,
                        formatiere_dauer(zeitpunkt),
                        str(runde),
                        teilnehmer.kuerzel,
                        text,
                    ],
                )
                zeile.setForeground(0, QColor(FARBE_FUEHRUNG))
                zeile.setForeground(4, QColor(FARBE_FUEHRUNG))
                zeile.setForeground(3, schriftfarbe(teilnehmer.farbe))
                zeile.setData(0, Qt.UserRole, zeitpunkt)
                zeile.setData(3, Qt.UserRole, stelle)
                continue

            z = was
            teilnehmer = verlauf.teilnehmer[z.teilnehmer]
            zeile = QTreeWidgetItem(
                self._ticker,
                [
                    TICKER_ZEICHEN.get(z.art, "?"),
                    formatiere_dauer(z.zeit_ms),
                    str(z.runde),
                    teilnehmer.kuerzel,
                    z.beschreibung + (" - Ausfall" if z.ausgefallen else ""),
                ],
            )
            zeile.setForeground(3, schriftfarbe(teilnehmer.farbe))
            if z.ausgefallen:
                # Der Ausfall ist keine vierte Art, sondern das Ende
                # einer der drei - also dasselbe Zeichen, nur in Rot.
                zeile.setForeground(0, QColor(FARBE_AUSFALL))
                zeile.setForeground(4, QColor(FARBE_AUSFALL))
            # Spalte 0 traegt weiterhin die Zeit als Sortierschluessel -
            # das Zeichen steht zwar darin, aber die Rolle daneben ist
            # frei, und ein Test liest von dort, ob das Neueste oben
            # steht. Spalte 3 traegt das Auto, damit der Doppelklick die
            # Fahrerkarte findet.
            zeile.setData(0, Qt.UserRole, int(z.zeit_ms))
            zeile.setData(3, Qt.UserRole, z.teilnehmer)

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
    def fuehrung(self) -> QTreeWidget:
        return self._fuehrung

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
