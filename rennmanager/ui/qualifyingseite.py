"""Seite fuer das Qualifying (GDD 4).

Seit Punkt 85 ist das Qualifying eine **Uebertragung** wie das Rennen:
dieselbe Wiedergabeleiste, dieselben Zeitrafferstufen, nach dem Laden auf
Anfang. Die Uhr laeuft ueber die ganze Session, die Autos fahren
ueberlappend, und wer seine gezeitete Runde beendet, sortiert sich in dem
Moment ein, in dem er ueber die Linie kommt.

Vorher stand hier ein Regler "Gefahrene Laeufe": Man konnte die Session
laufweise durchblaettern, aber nicht zusehen. Der Unterschied ist, dass
man jetzt die Zeit mitlaufen sieht, waehrend einer auf der Runde ist.

Die Splits sind dreifarbig (Entscheidung des Auftraggebers):

* **Lila** haelt, wer den Sektor bis zu diesem Augenblick am schnellsten
  gefahren ist. Das ist Live-Stand und wandert weiter, sobald ihn jemand
  unterbietet.
* **Gruen** und **Rot** messen gegen den Fuehrenden - und zwar gegen
  den, der fuehrte, **als der Split fiel**. Wie im Fernsehen: Die Farbe
  friert im Moment des Ueberfahrens ein und dreht sich nicht mehr um,
  wenn spaeter jemand schneller ist.

Die Seite rechnet nichts: Sie bekommt eine gefahrene Session von aussen -
vom gefuehrten Rennwochenende (Punkt 12) - und macht daraus ein Bild.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern.qualifying import Lage, Qualifying
from rennmanager.kern.zeit import formatiere_dauer, formatiere_rueckstand
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.streckenansicht import Streckenansicht
from rennmanager.ui.tabellen import kurzname, schriftfarbe, verbinde_fahrerkarte
from rennmanager.ui.wetterband import Wetterband

FARBE_SCHNELLER = QColor("#2e7d32")
FARBE_LANGSAMER = QColor("#c62828")
# Punkt 82: dasselbe Lila wie fuer den schnellsten Sektor im Rennen.
FARBE_BESTER = QColor("#8e24aa")
# Punkt 93 (A6): Wer gerade auf seiner gezeiteten Runde ist, bekommt
# einen kuehlen Schimmer - dezent genug, dass er die Wechselfarben der
# Zeilen nicht erschlaegt, deutlich genug, dass man ihn unter dreissig
# Zeilen findet.
FARBE_UNTERWEGS = QColor("#eaf1f8")
# Punkt 93 (A8): Und wer sich gerade die Pole geholt hat, leuchtet kurz
# golden auf. Beides sind Hintergruende, keine Schrift: Die Schrift
# traegt schon die Teamfarbe.
FARBE_NEUE_POLE = QColor("#fff2c9")

SPALTE_POS = 0
SPALTE_AUTO = 1
# Punkt 98: Der Name neben dem Kuerzel. "JOR" sagt niemandem etwas -
# dieselbe Ueberlegung wie in der Rangliste des Rennens (Punkt 60).
SPALTE_NAME = 2
SPALTE_ZEIT = 3
SPALTE_RUECKSTAND = 4
# Punkt 93 (A2): Der Abstand zum Vordermann steht neben dem Rueckstand
# auf die Spitze. Zwei verschiedene Fragen - "wie weit bin ich hinten"
# und "wen habe ich direkt vor mir" -, und die Tafel beantwortete bisher
# nur die erste.
SPALTE_INTERVALL = 5
SPALTE_SEKTOR_AB = 6


class Qualifyingseite(QWidget):
    """Spielt ein gefahrenes Qualifying als Zeitenmonitor ab."""

    # Doppelklick auf eine Zeile: Das Fenster oeffnet die Fahrerkarte.
    fahrerkarte_gewuenscht = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._session: Qualifying | None = None
        # Punkt 98: Nachname je Fahrernummer. Der Kern kennt nur Nummern,
        # die Namen stehen in der Welt - das gefuehrte Wochenende reicht
        # sie herein. Ohne sie bleibt die Spalte leer, und ein Testlauf
        # ohne Welt laeuft trotzdem durch.
        self._namen: dict[int, str] = {}
        self._zeit_ms = 0.0
        self._laeuft = False
        # Punkt 62: Die Tabelle wird seltener nachgezogen als die Uhr -
        # sonst springen dreissig Zeilen schneller um, als sie zu lesen
        # sind. Die Uhr oben laeuft trotzdem in jedem Takt weiter.
        self._anzeige_takt_ms = konfiguration.wert("zeitraffer", "anzeige_takt_ms")
        self._letzte_tabelle_ms: float | None = None

        self._takt_ms = konfiguration.wert("zeitraffer", "takt_ms")
        self._uhr = QTimer(self)
        self._uhr.setInterval(self._takt_ms)
        self._uhr.timeout.connect(self._takt)

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_wiedergabe())
        # Punkt 93 (A13): Wo war es trocken, wo nass. Direkt unter der
        # Leiste, damit Zeitachse und Band dieselbe Breite haben und
        # uebereinanderliegen.
        self._wetterband = Wetterband()
        spalte.addWidget(self._wetterband)

        inhalt = QHBoxLayout()
        inhalt.addWidget(self._baue_rangliste(), stretch=3)
        inhalt.addWidget(self._baue_seitenspalte(), stretch=2)
        spalte.addLayout(inhalt, stretch=1)

    # -- Aufbau ------------------------------------------------------------
    def _baue_wiedergabe(self) -> QHBoxLayout:
        """Dieselbe Leiste wie im Rennen - Wunsch des Auftraggebers."""
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

        # Punkt 93 (A23): Bei 75 Minuten Session ist das der
        # meistgebrauchte Knopf. Zwischen zwei Zielankuenften passiert
        # nichts, was in der Tafel steht - dafuer den Zeitraffer
        # hochzudrehen und wieder herunter ist Arbeit.
        self._naechste = QPushButton("Naechste Ankunft")
        self._naechste.setEnabled(False)
        self._naechste.setToolTip(
            "Springt zu dem Augenblick, in dem der naechste Fahrer ueber die "
            "Linie kommt - dorthin, wo sich die Tafel aendert."
        )
        self._naechste.clicked.connect(self._zur_naechsten_ankunft)

        self._uhrzeit = QLabel("0:00.000")
        self._stand = QLabel("Noch kein Qualifying gefahren")
        self._fortschritt = QProgressBar()
        self._fortschritt.setTextVisible(False)

        zeile.addWidget(self._abspielen)
        zeile.addWidget(self._zurueck)
        zeile.addWidget(QLabel("Zeitraffer:"))
        zeile.addWidget(self._raffer)
        zeile.addWidget(self._naechste)
        zeile.addWidget(self._sofort)
        zeile.addWidget(self._uhrzeit)
        zeile.addWidget(self._stand)
        zeile.addWidget(self._fortschritt, stretch=1)
        return zeile

    def _baue_rangliste(self) -> QWidget:
        kasten = QGroupBox("Zeitenmonitor")
        spalte = QVBoxLayout(kasten)
        # Punkt 93 (A7): Kommt einer ins Ziel, steht hier kurz, wen er um
        # wie viel verdraengt hat. Eine eigene Zeile und keine Spalte:
        # Es betrifft immer nur ein Auto, und in einer Spalte muesste man
        # es unter dreissig Zeilen suchen.
        self._verdraengung = QLabel(" ")
        self._verdraengung.setStyleSheet("font-weight: bold;")
        spalte.addWidget(self._verdraengung)
        self._rangliste = QTreeWidget()
        self._rangliste.setHeaderLabels(self._kopfzeilen(4))
        self._rangliste.setRootIsDecorated(False)
        self._rangliste.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._rangliste, self.fahrerkarte_gewuenscht.emit)
        spalte.addWidget(self._rangliste)
        return kasten

    @staticmethod
    def _kopfzeilen(sektoren: int) -> list[str]:
        kopf = ["Pos", "Auto", "Fahrer", "Zeit", "Rueckstand", "Intervall"]
        kopf += [f"S{nummer + 1}" for nummer in range(sektoren)]
        return kopf + ["Lage", "Wetter", "Form"]

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        # Punkt 93 (A9): Die Ansicht gibt es fuers Rennen schon - hier
        # faehrt sie die Runden ab.
        #
        # Die Aufwaermrunde war urspruenglich nicht darauf: Der Vorschlag
        # hiess "ein Punkt, der die schnelle Runde abfaehrt", und ein
        # Feld aus Aufwaermpunkten haette die zugedeckt, auf die es
        # ankommt. Gemessen war die Karte damit aber ueber ein Fuenftel
        # der Session leer, unter anderem gleich am Anfang - und ein Auto
        # ist laenger ungezeitet auf der Strecke (101 s) als gezeitet
        # (98 s). Entscheidung des Auftraggebers: mitzeichnen, aber
        # blasser.
        self._ansicht = Streckenansicht()
        streckenkasten = QGroupBox("Strecke")
        streckenspalte = QVBoxLayout(streckenkasten)
        streckenspalte.addWidget(self._ansicht)
        spalte.addWidget(streckenkasten, stretch=2)

        self._wetterfeld = QFormLayout()
        wetterkasten = QGroupBox("Wetter der Session")
        wetterkasten.setLayout(self._wetterfeld)
        spalte.addWidget(wetterkasten)

        # Punkt 93 (A17): Die schnellste je hier gefahrene Qualirunde,
        # mit Fahrer und Jahr. Getrennt vom Rennrekord gefuehrt: Eine
        # Qualirunde faehrt man auf leerer Strecke mit frischen Reifen.
        self._bestmarke = QLabel("-")
        markenkasten = QGroupBox("Streckenbestmarke im Qualifying")
        marken_spalte = QVBoxLayout(markenkasten)
        marken_spalte.addWidget(self._bestmarke)
        spalte.addWidget(markenkasten)

        self._aufstellung = QTreeWidget()
        self._aufstellung.setHeaderLabels(["Startplatz", "Auto", "Zeit"])
        self._aufstellung.setRootIsDecorated(False)
        self._aufstellung.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._aufstellung, self.fahrerkarte_gewuenscht.emit)
        # Entscheidung des Auftraggebers: Die Aufstellung fuellt sich erst
        # am Ende. Vorher stuende dort das Ergebnis, auf das die
        # Uebertragung gerade zulaeuft.
        self._aufstellungskasten = QGroupBox("Startaufstellung fuers Rennen")
        kasten_spalte = QVBoxLayout(self._aufstellungskasten)
        kasten_spalte.addWidget(self._aufstellung)
        spalte.addWidget(self._aufstellungskasten, stretch=1)
        return seite

    # -- Session uebernehmen -----------------------------------------------
    def zeige_bestmarke(self, rekord, name: str = "") -> None:
        """Punkt 93 (A17): Die schnellste je hier gefahrene Qualirunde.

        ``rekord`` ist ein ``statistik.Rekord`` oder ``None``. Steht
        noch keiner, sagt die Zeile das auch - ein leeres Feld saehe aus
        wie ein Fehler.
        """
        if rekord is None:
            self._bestmarke.setText("Noch keine - die heutige Pole setzt sie.")
            return
        wer = name or f"Fahrer {rekord.fahrer}"
        self._bestmarke.setText(
            f"{formatiere_dauer(rekord.zeit_ms)}   {wer}   {rekord.saison}"
        )

    def zeige_namen(self, namen: dict[int, str]) -> None:
        """Gibt der Seite die Fahrernamen je Nummer (Punkt 98).

        Wie in der Karriereseite: Der Kern kennt nur Nummern, die Namen
        stehen in der Welt. Abgekuerzt wird hier, nicht beim Aufrufer -
        so steht die Regel an einer Stelle.
        """
        self._namen = {nummer: kurzname(name) for nummer, name in namen.items()}
        if self._session is not None:
            self._letzte_tabelle_ms = None
            self._zeichne()

    def zeige_session(self, session: Qualifying) -> None:
        """Uebernimmt ein gefahrenes Qualifying und stellt es auf Anfang."""
        self._session = session
        self._halte_an()
        sektoren = len(session.fahrten[0].sektoren_ms) if session.fahrten else 4
        self._rangliste.setHeaderLabels(self._kopfzeilen(sektoren))
        self._fortschritt.setRange(0, max(session.dauer_ms, 1))
        self._wetterband.zeige(session.wetter, session.dauer_ms)
        self._ansicht.zeige(session.strecke)
        for knopf in (self._abspielen, self._zurueck, self._sofort, self._naechste):
            knopf.setEnabled(True)
        self._waehle_zeitraffer()
        self._fuelle_wetter()
        self._leere_aufstellung()
        self._springe(0)

    def _waehle_zeitraffer(self) -> None:
        """Dieselbe Startstufe wie im Rennen (Punkt 81): Echtzeit."""
        stufen = self._konfiguration.wert("zeitraffer", "stufen")
        start = self._konfiguration.wert("zeitraffer", "start_stufe")
        self._raffer.setCurrentIndex(stufen.index(start) if start in stufen else 0)

    # -- Wiedergabe ---------------------------------------------------------
    def _umschalten(self) -> None:
        if self._laeuft:
            self._halte_an()
            return
        self._laeuft = True
        self._abspielen.setText("Pause")
        self._uhr.start()

    def _halte_an(self) -> None:
        self._laeuft = False
        self._uhr.stop()
        self._abspielen.setText("Start")

    def _springe(self, zeit_ms: float) -> None:
        self._zeit_ms = zeit_ms
        # Ein Sprung soll sofort zu sehen sein, nicht erst im naechsten Takt.
        self._letzte_tabelle_ms = None
        self._zeichne()

    def _zum_ende(self) -> None:
        """GDD 4: Sofortergebnis."""
        if self._session is not None:
            self._halte_an()
            self._springe(self._session.dauer_ms)

    def _zur_naechsten_ankunft(self) -> None:
        """Punkt 93 (A23): Vor zu dem Moment, in dem sich die Tafel aendert.

        Gesprungen wird **auf** die Ankunft, nicht eine Millisekunde
        davor: Dort steht die neue Zeit schon in der Tafel und der
        Verdraengungshinweis darueber. Ist keine mehr uebrig, geht es
        ans Ende - dann ist die Session durch, und das ist die ehrliche
        Antwort auf "was kommt noch".

        Die Wiedergabe laeuft dabei weiter, wenn sie lief: Der Knopf ist
        ein Vorspulen, kein Anhalten.
        """
        if self._session is None:
            return
        jetzt = self._zeit_ms
        kommende = [f.ziel_ms for f in self._session.fahrten if f.ziel_ms > jetzt]
        self._springe(min(kommende) if kommende else self._session.dauer_ms)

    def _takt(self) -> None:
        if self._session is None:
            return
        self._zeit_ms += self._takt_ms * self._raffer.currentData()
        if self._zeit_ms >= self._session.dauer_ms:
            self._zeit_ms = self._session.dauer_ms
            self._halte_an()
            self._letzte_tabelle_ms = None
        self._zeichne()

    def _tabelle_faellig(self, zeit: float) -> bool:
        """Gemessen in Sessionzeit, nicht in Echtzeit (wie im Rennen)."""
        davor = self._letzte_tabelle_ms
        if davor is None or abs(zeit - davor) >= self._anzeige_takt_ms:
            self._letzte_tabelle_ms = zeit
            return True
        return False

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self) -> None:
        if self._session is None:
            return
        zeit = self._zeit_ms
        self._uhrzeit.setText(formatiere_dauer(int(zeit)))
        self._fortschritt.setValue(int(zeit))
        self._wetterband.setze_marke(zeit)
        self._zeichne_strecke(zeit)
        if not self._tabelle_faellig(zeit):
            return

        session = self._session
        stand = session.lage_zu(zeit)
        self._zeige_gummi(stand)
        fertig = [s for s in stand if s.ist_fertig]
        self._stand.setText(f"{len(fertig)} von {len(session.fahrten)} Runden gefahren")
        bestzeit = fertig[0].zeit_ms if fertig else None
        lila = session.beste_splits_zu(zeit)

        # Punkt 93 (A7 und A8): Was gerade passiert ist - wer sich
        # eingereiht hat und ob dabei die Pole gewechselt ist.
        ankunft = session.letzte_zielankunft(
            zeit, self._konfiguration.wert("qualifying", "hervorhebung_ms")
        )
        # Punkt 98: Am Ende der Session haelt die Wiedergabe an. Die
        # letzte Ankunft laege damit **fuer immer** im Hervorhebungs-
        # fenster, und die Zeile des Letzten blieb dauerhaft unterlegt -
        # so lange, bis der Spieler zurueckspulte. Ist jeder durch, ist
        # auch nichts mehr "gerade passiert". Die Regel steht hier und
        # nicht im Kern: ``letzte_zielankunft`` beantwortet weiter genau
        # die Frage, die sie verspricht.
        if len(fertig) == len(session.fahrten) and zeit >= session.dauer_ms:
            ankunft = None
        self._zeige_verdraengung(ankunft)
        frische_pole = (
            ankunft.fahrt.teilnehmer if ankunft is not None and ankunft.neue_pole else None
        )

        self._rangliste.clear()
        # Die Position gilt nur fuer stehende Runden - wer noch faehrt,
        # hat noch keine. lage_zu() liefert die Fertigen zuerst, der
        # Zaehler laeuft also einfach mit.
        platz = 0
        vorherige_zeit: int | None = None
        for zeile in stand:
            if zeile.ist_fertig:
                platz += 1
            # A2: Der Abstand zum Vordermann - also zur zuletzt
            # eingetragenen stehenden Zeit. Der Erste hat keinen.
            intervall = (
                zeile.zeit_ms - vorherige_zeit
                if zeile.ist_fertig and vorherige_zeit is not None
                else None
            )
            self._fuelle_zeile(
                zeile,
                platz if zeile.ist_fertig else None,
                bestzeit,
                lila,
                intervall=intervall,
                frische_pole=frische_pole,
            )
            if zeile.ist_fertig:
                vorherige_zeit = zeile.zeit_ms
        for spalte in range(self._rangliste.columnCount()):
            self._rangliste.resizeColumnToContents(spalte)

        # Die Aufstellung steht erst, wenn der Letzte durch ist.
        if len(fertig) == len(session.fahrten):
            self._fuelle_aufstellung()
        else:
            self._leere_aufstellung()

    def _zeichne_strecke(self, zeit: float) -> None:
        """Punkt 93 (A9): Die Punkte derer, die gerade auf der Strecke sind.

        Gezeichnet wird **beides**, die gezeitete Runde und die
        Aufwaermrunde davor - letztere blasser, weil sie nicht gezaehlt
        wird. Vorher stand nur da, wer gezeitet fuhr; gemessen war die
        Karte damit ueber ein Fuenftel der Session leer, unter anderem
        gleich am Anfang, und ein Auto ist laenger ungezeitet auf der
        Strecke (101 s) als gezeitet (98 s).

        Laeuft **ausserhalb** des Takt-Deckels der Tabelle (D9): Die
        Karte soll fluessig laufen, auch wenn die Zeiten nur alle 200 ms
        nachgezogen werden.
        """
        session = self._session
        if session is None:
            return
        punkte = []
        for stand in session.lage_zu(zeit):
            ort = session.ort_auf_der_runde(stand, zeit)
            if ort is None:
                continue
            teilnehmer = session.teilnehmer[stand.fahrt.teilnehmer]
            punkte.append(
                (
                    float(ort),
                    teilnehmer.kuerzel,
                    teilnehmer.farbe,
                    teilnehmer.ist_spieler,
                    stand.lage is Lage.AUFWAERMUNG,
                )
            )
        self._ansicht.zeige_autos(punkte)

    def _zeige_verdraengung(self, ankunft) -> None:
        """Punkt 93 (A7): Wer wen gerade um wie viel verdraengt hat.

        Ausserhalb des Fensters bleibt die Zeile leer - aber nicht
        wirklich leer, sondern mit einem Leerzeichen: Sonst springt die
        Tabelle bei jeder Ankunft um die Zeilenhoehe nach unten.
        """
        if ankunft is None or self._session is None:
            self._verdraengung.setText(" ")
            return
        teilnehmer = self._session.teilnehmer
        wer = teilnehmer[ankunft.fahrt.teilnehmer].kuerzel
        if ankunft.verdraengt is None:
            self._verdraengung.setText(f"{wer} reiht sich auf P{ankunft.platz} ein")
            return
        wen = teilnehmer[ankunft.verdraengt.teilnehmer].kuerzel
        abstand = formatiere_rueckstand(ankunft.abstand_ms)
        pole = "  -  neue Pole!" if ankunft.neue_pole else ""
        self._verdraengung.setText(
            f"P{ankunft.platz}: {wer} verdraengt {wen} um {abstand}{pole}"
        )

    def _zeige_gummi(self, stand) -> None:
        """Wie viel Gummi die Strecke gerade hergibt (Punkt 88).

        Genommen wird der Wert des zuletzt gestarteten Autos - das ist
        der Stand, den die Strecke in diesem Augenblick bietet. Wer noch
        in der Box steht, hat seinen Wert noch nicht.
        """
        gefahren = [s.fahrt.gummi for s in stand if s.lage is not Lage.WARTET]
        jetzt = max(gefahren) if gefahren else 0.0
        self._gummianzeige.setText(f"+{jetzt * 100:.2f} %")

    def _fuelle_zeile(
        self,
        stand,
        platz: int | None,
        bestzeit: int | None,
        lila,
        intervall: int | None = None,
        frische_pole: int | None = None,
    ) -> None:
        session = self._session
        fahrt = stand.fahrt
        teilnehmer = session.teilnehmer[fahrt.teilnehmer]
        unterwegs = stand.lage is not Lage.WARTET

        spalten = [
            str(platz) if platz is not None else "",
            teilnehmer.kuerzel,
            self._namen.get(teilnehmer.nummer, ""),
            formatiere_dauer(stand.zeit_ms) if stand.zeit_ms is not None else "",
            (
                formatiere_rueckstand(stand.zeit_ms - bestzeit)
                if stand.ist_fertig and bestzeit is not None and stand.zeit_ms > bestzeit
                else ""
            ),
            formatiere_rueckstand(intervall) if intervall is not None else "",
        ]
        spalten += ["" for _ in fahrt.sektoren_ms]
        spalten += [
            stand.lage.bezeichnung,
            fahrt.zustand if unterwegs else "",
            f"{(fahrt.tagesform - 1) * 100:+.1f}%" if unterwegs else "",
        ]

        zeile = QTreeWidgetItem(self._rangliste, spalten)
        zeile.setForeground(SPALTE_AUTO, schriftfarbe(teilnehmer.farbe))
        zeile.setData(SPALTE_POS, Qt.UserRole, teilnehmer.nummer)
        self._faerbe_splits(zeile, stand, lila)

        # Eine laufende Runde ist keine Zeit, sondern eine Behauptung -
        # deshalb steht sie kursiv da, bis sie im Ziel steht.
        if stand.lage is Lage.SCHNELLE_RUNDE:
            schrift = zeile.font(SPALTE_ZEIT)
            schrift.setItalic(True)
            zeile.setFont(SPALTE_ZEIT, schrift)
        if teilnehmer.ist_spieler:
            schrift = zeile.font(SPALTE_AUTO)
            schrift.setBold(True)
            for spalte in range(self._rangliste.columnCount()):
                zeile.setFont(spalte, schrift)

        # A8 geht A6 vor: Wer sich gerade die Pole geholt hat, ist nicht
        # mehr auf der Runde - und selbst wenn, waere das die groessere
        # Nachricht.
        if frische_pole is not None and fahrt.teilnehmer == frische_pole:
            self._hinterlege(zeile, FARBE_NEUE_POLE)
        elif stand.lage is Lage.SCHNELLE_RUNDE:
            self._hinterlege(zeile, FARBE_UNTERWEGS)

    def _hinterlege(self, zeile: QTreeWidgetItem, farbe: QColor) -> None:
        """Faerbt die ganze Zeile - eine halbe saehe nach Fehler aus."""
        for spalte in range(self._rangliste.columnCount()):
            zeile.setBackground(spalte, farbe)

    def _faerbe_splits(self, zeile: QTreeWidgetItem, stand, lila) -> None:
        """Traegt die gesetzten Splits ein und faerbt sie."""
        fahrt = stand.fahrt
        for nummer in range(stand.sektoren):
            spalte = SPALTE_SEKTOR_AB + nummer
            wert = fahrt.sektoren_ms[nummer]
            zeile.setText(spalte, formatiere_dauer(wert))

            if nummer < len(lila) and lila[nummer] == fahrt.teilnehmer:
                zeile.setForeground(spalte, FARBE_BESTER)
                continue
            abstand = self._session.splitvergleich(fahrt, nummer)
            if abstand is None:
                continue
            zeile.setForeground(
                spalte, FARBE_LANGSAMER if abstand > 0 else FARBE_SCHNELLER
            )
            zeile.setText(
                spalte, f"{formatiere_dauer(wert)} {formatiere_rueckstand(abstand)}"
            )

    def _fuelle_wetter(self) -> None:
        self._leere(self._wetterfeld)
        verlauf = self._session.wetter
        self._wetterfeld.addRow("Start:", QLabel(verlauf.startzustand))
        self._wetterfeld.addRow("Wechsel:", QLabel(str(verlauf.wechsel)))
        self._wetterfeld.addRow("Verlauf:", QLabel(" → ".join(verlauf.zustaende)))
        self._wetterfeld.addRow(
            "Dauer der Session:", QLabel(formatiere_dauer(self._session.dauer_ms))
        )
        # Punkt 88: Die Strecke gummiert ueber die Session ein. Wer
        # spaeter faehrt, findet mehr vor - und die Startreihenfolge ist
        # der umgekehrte Meisterschaftsstand (GDD 4).
        self._gummianzeige = QLabel("+0,00 %")
        self._wetterfeld.addRow("Strecke:", self._gummianzeige)

    def _leere_aufstellung(self) -> None:
        if self._aufstellung.topLevelItemCount():
            self._aufstellung.clear()
        self._aufstellungskasten.setTitle(
            "Startaufstellung fuers Rennen (steht nach der letzten Runde)"
        )

    def _fuelle_aufstellung(self) -> None:
        self._aufstellungskasten.setTitle("Startaufstellung fuers Rennen")
        if self._aufstellung.topLevelItemCount():
            return
        for platz, i in enumerate(self._session.aufstellung, start=1):
            fahrt = next(f for f in self._session.fahrten if f.teilnehmer == i)
            teilnehmer = self._session.teilnehmer[i]
            zeile = QTreeWidgetItem(
                self._aufstellung,
                [str(platz), teilnehmer.kuerzel, formatiere_dauer(fahrt.zeit_ms)],
            )
            zeile.setForeground(1, schriftfarbe(teilnehmer.farbe))
            zeile.setData(0, Qt.UserRole, teilnehmer.nummer)
        for spalte in range(3):
            self._aufstellung.resizeColumnToContents(spalte)

    @staticmethod
    def _leere(formular: QFormLayout) -> None:
        while formular.rowCount():
            formular.removeRow(0)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def session(self) -> Qualifying | None:
        return self._session

    @property
    def zeit_ms(self) -> float:
        return self._zeit_ms

    @property
    def laeuft(self) -> bool:
        return self._laeuft
