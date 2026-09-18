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
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import strecke as kern_strecke
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
SPALTE_INTERVALL = 4
SPALTE_REIFEN = 5
SPALTE_STATUS = 6
# So viele Zwischenfaelle stehen im Ticker; aeltere rollen heraus.
TICKER_ZEILEN = 12
# Platz fuer den Reifenbalken samt Prozentzahl daneben.
BREITE_REIFEN = 96


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
        self._zeit_ms = 0.0
        self._laeuft = False

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

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._blaetter)
        teiler.addWidget(self._baue_seitenleiste())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
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
        self._fortschritt = QProgressBar()
        self._fortschritt.setTextVisible(False)

        zeile.addWidget(self._abspielen)
        zeile.addWidget(self._zurueck)
        zeile.addWidget(QLabel("Zeitraffer:"))
        zeile.addWidget(self._raffer)
        zeile.addWidget(self._sofort)
        self._wetteranzeige = QLabel("-")
        zeile.addWidget(self._uhrzeit)
        zeile.addWidget(self._fortschritt, stretch=1)
        zeile.addWidget(QLabel("Wetter:"))
        zeile.addWidget(self._wetteranzeige)
        return zeile

    def _baue_seitenleiste(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        # GDD 4: Positionen, Gesamtzeit des Fuehrenden, Rueckstand der uebrigen
        self._rangliste = QTreeWidget()
        self._rangliste.setHeaderLabels(
            ["Pos", "Auto", "Rd", "Zeit / Rueckstand", "Intervall", "Reifen", "Status"]
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
        spalte.addWidget(kasten, stretch=3)

        # GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten
        self._monitor = QTreeWidget()
        self._monitor.setHeaderLabels(
            ["Auto", "Letzte Rd", "Beste Rd", "S1", "S2", "S3", "S4"]
        )
        self._monitor.setRootIsDecorated(False)
        self._monitor.setAlternatingRowColors(True)
        monitorkasten = QGroupBox("Zeitenmonitor")
        monitor_spalte = QVBoxLayout(monitorkasten)
        monitor_spalte.addWidget(self._monitor)
        spalte.addWidget(monitorkasten, stretch=2)

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
        ticker_spalte.addWidget(self._ticker)
        spalte.addWidget(self._tickerkasten, stretch=2)
        return seite

    # -- Rennen uebernehmen ------------------------------------------------
    def zeige_verlauf(
        self,
        verlauf: Rennverlauf,
        strecke: kern_strecke.Strecke,
        qualifying=None,
    ) -> None:
        """Uebernimmt ein fertig gerechnetes Rennen und spielt es ab.

        Gerechnet hat es der Kern - beim gefuehrten Wochenende der
        ``Wochenendlauf`` (Punkt 12). Die Seite ist reine Uebertragung.
        """
        self._halte_an()
        self._verlauf = verlauf
        self._qualifying = qualifying
        self._ansicht.zeige(strecke)
        self._rueckstand.zeige(verlauf)
        self._auswahl_geaendert(None)
        self._fortschritt.setRange(0, max(verlauf.dauer_ms, 1))
        for knopf in (self._abspielen, self._zurueck, self._sofort):
            knopf.setEnabled(True)
        self._waehle_zeitraffer()
        self._springe(0)

        # Das Rennen laeuft von selbst los, damit es sich wie eine
        # Uebertragung anfuehlt und nicht wie eine Auswertung.
        if self._konfiguration.wert("zeitraffer", "automatisch_starten"):
            self._umschalten()

    def _waehle_zeitraffer(self) -> None:
        """Waehlt die kleinste Stufe, mit der das Rennen zuegig durchlaeuft.

        Ein Rennen dauert real bis zu anderthalb Stunden; bei einfacher
        Geschwindigkeit saehe man nichts als Warten.
        """
        if self._verlauf is None:
            return
        wunsch_ms = self._konfiguration.wert("zeitraffer", "wunschdauer_s") * 1000
        stufen = self._konfiguration.wert("zeitraffer", "stufen")
        passend = next(
            (stufe for stufe in stufen if self._verlauf.dauer_ms / stufe <= wunsch_ms),
            stufen[-1],
        )
        self._raffer.setCurrentIndex(stufen.index(passend))

    # -- Wiedergabe --------------------------------------------------------
    def _umschalten(self) -> None:
        if self._laeuft:
            self._halte_an()
        else:
            self._laeuft = True
            self._abspielen.setText("Pause")
            self._uhr.start()

    def _halte_an(self) -> None:
        self._laeuft = False
        self._uhr.stop()
        self._abspielen.setText("Start")

    def _springe(self, zeit_ms: float) -> None:
        self._zeit_ms = zeit_ms
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

        self._ansicht.zeige_autos(
            [
                (
                    float(distanzen[i]),
                    verlauf.teilnehmer[i].kuerzel,
                    verlauf.teilnehmer[i].farbe,
                    verlauf.teilnehmer[i].ist_spieler,
                )
                for i in reihenfolge
            ]
        )
        self._fuelle_rangliste(verlauf, reihenfolge, distanzen, zeit)
        self._fuelle_monitor(verlauf, reihenfolge)
        self._fuelle_ticker(verlauf, zeit)
        self._rueckstand.setze_marke(zeit)

    def _fuelle_rangliste(
        self, verlauf: Rennverlauf, reihenfolge: list[int], distanzen, zeit: float
    ) -> None:
        """GDD 4: Gesamtzeit des Fuehrenden, Rueckstand der uebrigen."""
        self._rangliste.clear()
        laenge = verlauf.strecke.laenge_m
        fuehrender = reihenfolge[0]
        vorne = float(distanzen[fuehrender])
        reifen = verlauf.reifen_zu(zeit)
        bild = verlauf.bild_zu(zeit)
        raus = verlauf.ausgefallen[bild]

        for platz, i in enumerate(reihenfolge, start=1):
            teilnehmer = verlauf.teilnehmer[i]
            distanz = float(distanzen[i])
            runde = min(int(max(distanz, 0.0) // laenge) + 1, verlauf.runden)

            if i == fuehrender:
                text = formatiere_dauer(int(zeit))
            else:
                rueckstandsrunden = int((vorne - distanz) // laenge)
                if rueckstandsrunden >= 1:
                    text = formatiere_runden_rueckstand(rueckstandsrunden)
                else:
                    # Rueckstand in Zeit: Strecke geteilt durch das Tempo des
                    # Fuehrenden an dieser Stelle.
                    tempo = self._tempo_naeherung(verlauf, fuehrender, zeit)
                    text = formatiere_rueckstand(int((vorne - distanz) / max(tempo, 1e-6) * 1000))

            # GDD 4: Zwischenfaelle sind im Ranking markiert, die
            # Einzelheiten stehen im Mouseover.
            bisher = [z for z in verlauf.zwischenfaelle_von(i) if z.zeit_ms <= zeit]
            status = self._status(bisher, bool(raus[i]))

            zeile = QTreeWidgetItem(
                self._rangliste,
                [
                    str(platz),
                    teilnehmer.kuerzel,
                    str(runde),
                    text,
                    self._intervall(verlauf, reihenfolge, distanzen, zeit, platz),
                    f"{reifen[i]:.0%}",
                    status,
                ],
            )
            zeile.setForeground(1, QColor(teilnehmer.farbe))
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
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(4):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._rangliste.columnCount()):
            if spalte != SPALTE_REIFEN:
                self._rangliste.resizeColumnToContents(spalte)

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

        Gerechnet wird mit dem Tempo des *Vordermanns*: Das Intervall ist
        die Zeit, die es braucht, um dort zu sein, wo er gerade ist. Der
        Rueckstand zur Spitze rechnet entsprechend mit dem Tempo des
        Fuehrenden. Beide Bezuege sind der jeweils richtige - aber weil
        zwei Autos an verschiedenen Streckenpunkten verschieden schnell
        sind, summieren sich die Intervalle **nicht** genau zum
        Rueckstand. Gemessen lagen fuenf Intervalle bei 11,6 s, der
        Rueckstand des sechsten Autos bei 9,0 s. Dasselbe gilt fuer echte
        Zeitmonitore; nur beim Zweiten stimmen beide Zahlen ueberein, weil
        dort Vordermann und Fuehrender dasselbe Auto sind.
        """
        if platz <= 1:
            return "-"
        vorne = reihenfolge[platz - 2]
        hinten = reihenfolge[platz - 1]
        abstand = float(distanzen[vorne]) - float(distanzen[hinten])
        laenge = verlauf.strecke.laenge_m
        if abstand >= laenge:
            return formatiere_runden_rueckstand(int(abstand // laenge))
        tempo = self._tempo_naeherung(verlauf, vorne, zeit)
        return formatiere_rueckstand(int(abstand / max(tempo, 1e-6) * 1000))

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

    def _fuelle_monitor(self, verlauf: Rennverlauf, reihenfolge: list[int]) -> None:
        """GDD 4: letzte Runde, beste Runde, 4 Sektorzeiten."""
        self._monitor.clear()
        for i in reihenfolge[:10]:
            protokoll = verlauf.protokolle[i]
            sektoren = protokoll.sektorzeiten_ms[-1] if protokoll.sektorzeiten_ms else ()
            spalten = [
                verlauf.teilnehmer[i].kuerzel,
                formatiere_dauer(protokoll.letzte_runde_ms) if protokoll.letzte_runde_ms else "-",
                formatiere_dauer(protokoll.beste_runde_ms) if protokoll.beste_runde_ms else "-",
            ]
            spalten += [formatiere_dauer(zeit) for zeit in sektoren]
            spalten += ["-"] * (7 - len(spalten))
            zeile = QTreeWidgetItem(self._monitor, spalten)
            zeile.setForeground(0, QColor(verlauf.teilnehmer[i].farbe))
        for spalte in range(7):
            self._monitor.resizeColumnToContents(spalte)

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
            return self._verlauf.teilnehmer[int(stelle)].nummer or None

        return nummer_von

    def _auswahl_geaendert(self, jetzt, _davor=None) -> None:
        """Hebt Spieler und gewaehltes Auto im Diagramm hervor (Punkt 2)."""
        if self._verlauf is None:
            return
        hervor = [
            i
            for i, teilnehmer in enumerate(self._verlauf.teilnehmer)
            if teilnehmer.ist_spieler
        ]
        gewaehlt = jetzt.data(0, Qt.UserRole) if jetzt is not None else None
        if gewaehlt is not None and gewaehlt not in hervor:
            hervor.append(int(gewaehlt))
        self._rueckstand.hebe_hervor(hervor)

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
    def verlauf(self) -> Rennverlauf | None:
        return self._verlauf

    @property
    def qualifying(self):
        """Das Qualifying, falls die Aufstellung daraus stammt."""
        return self._qualifying

    @property
    def zeit_ms(self) -> float:
        return self._zeit_ms
