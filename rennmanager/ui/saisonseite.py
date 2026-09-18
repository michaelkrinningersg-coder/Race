"""Seite fuer die Saison: Wertung, Schnellsimulation, Auf- und Abstieg (GDD 13).

Links die Tabelle der gewaehlten Liga, rechts das Ergebnis des zuletzt
gefahrenen Rennwochenendes. Ueber die Knoepfe laeuft ein einzelnes
Wochenende oder gleich die ganze Saison; die Liga des Spielers kann dabei
wahlweise ausfuehrlich gefahren werden - dann dauert sie laenger, liefert
aber einen abspielbaren Rennverlauf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import saison as kern_saison
from rennmanager.kern import strecke as kern_strecke
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern.saison import Saisonlauf, Wochenende
from rennmanager.kern.welt import Welt
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.punkteansicht import Punkteansicht
from rennmanager.ui.tabellen import verbinde_fahrerkarte

FARBE_AUFSTIEG = QColor("#2e7d32")
FARBE_ABSTIEG = QColor("#c62828")


class Saisonseite(QWidget):
    """Faehrt die Saison und zeigt Wertung sowie Auf- und Abstieg."""

    # Nach dem Saisonwechsel: Die Welt ist eine neue, das Fenster muss sie
    # uebernehmen. Als Signal, weil die Seite sich sonst waehrend ihres
    # eigenen Klicks selbst abbauen wuerde.
    saison_gewechselt = Signal()
    # Doppelklick auf einen Namen: Das Fenster oeffnet die Fahrerkarte.
    fahrerkarte_gewuenscht = Signal(int)

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt: Welt,
        seed: int = 0,
        statistik=None,
        kenntnis=None,
        tabellen=None,
        gefahrene_rennen: int = 0,
        karriere=None,
        jahr: int | None = None,
        popularitaet=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        # Statistik und Streckenkenntnis ueberdauern die Saison (GDD 6 und
        # 13); das Fenster haelt sie und reicht sie herein.
        self._lauf = Saisonlauf(
            konfiguration,
            welt,
            Seedquelle(seed),
            jahr=jahr,
            strecken=kern_strecke.lade_alle(konfiguration),
            statistik=statistik,
            kenntnis=kenntnis,
            tabellen=tabellen,
            vorgefahren=gefahrene_rennen,
            # Damit die entwickelten Werte des Spielers im Rennen ankommen
            # (GDD 1) und Ereignisse wie Defekte daran ziehen (GDD 14).
            karriere=karriere,
            popularitaet=popularitaet,
        )
        self._letztes: Wochenende | None = None
        # Welcher Fahrer in welcher Linie des Punktediagramms steckt.
        self._fahrernummern: list[int] = []

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())
        spalte.addWidget(self._baue_kalenderzeile())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_tabelle())
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._aktualisiere()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()

        self._liga = QComboBox()
        for nummer in range(1, self._konfiguration.wert("ligen", "anzahl") + 1):
            self._liga.addItem(
                f"Liga {nummer} - {self._konfiguration.ligenname(nummer)}", nummer
            )
        spieler = self._welt.spieler
        if spieler is not None:
            self._liga.setCurrentIndex(spieler.liga - 1)
        self._liga.currentIndexChanged.connect(self._aktualisiere)

        # Punkt 12: Ein einzelnes Wochenende faehrt der Spieler gefuehrt
        # im eigenen Reiter. Hier bleibt nur der Weg, den Rest des Jahres
        # im Schnellmodus durchlaufen zu lassen.
        self._ganze_saison = QPushButton("Restliche Saison")
        self._ganze_saison.setToolTip(
            "Alle verbleibenden Wochenenden im Schnellmodus fahren - auch die "
            "des Spielers. Wer sie selbst fahren will, nimmt den Reiter "
            "Rennwochenende (GDD 15)."
        )
        self._ganze_saison.clicked.connect(self._fahre_rest)
        self._naechste_saison = QPushButton("Naechste Saison")
        self._naechste_saison.setToolTip(
            "Auf- und Abstieg vollziehen und ins naechste Jahr wechseln. "
            "Statistik, Streckenkenntnis und die Karriere wandern mit (GDD 13)."
        )
        self._naechste_saison.clicked.connect(self._wechsle_saison)
        self._naechste_saison.setEnabled(False)

        self._stand = QLabel()

        zeile.addWidget(QLabel("Liga:"))
        zeile.addWidget(self._liga)
        zeile.addWidget(self._ganze_saison)
        zeile.addWidget(self._naechste_saison)
        zeile.addWidget(self._stand, stretch=1)
        return zeile

    def _baue_kalenderzeile(self) -> QWidget:
        """Zeigt, wo der Kalender steht und was ein Rennen jetzt kostet.

        Bewusst kein modaler Dialog: Der Hinweis muss vor dem Klick zu
        sehen sein, nicht danach - und ein Fenster, das jedes Mal
        weggeklickt werden will, steht nur im Weg.
        """
        self._kalender = QLabel()
        self._kalender.setWordWrap(True)
        return self._kalender

    def _baue_tabelle(self) -> QWidget:
        """Links die Tabelle, darunter der Punkteverlauf derselben Liga.

        Die Tabelle sagt, wie es steht; das Diagramm darunter sagt, wie es
        dazu kam - und beides gehoert zusammen, deshalb eine Spalte.
        """
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._tabellenkasten = QGroupBox("Saisonwertung")
        kasten = QVBoxLayout(self._tabellenkasten)
        self._tabelle = QTreeWidget()
        self._tabelle.setHeaderLabels(
            ["#", "Fahrer", "Team", "Punkte", "Siege", "Podien", "Poles", "SR", "DNF"]
        )
        self._tabelle.setRootIsDecorated(False)
        self._tabelle.setAlternatingRowColors(True)
        self._tabelle.currentItemChanged.connect(self._auswahl_geaendert)
        verbinde_fahrerkarte(self._tabelle, self.fahrerkarte_gewuenscht.emit)
        kasten.addWidget(self._tabelle)
        spalte.addWidget(self._tabellenkasten, stretch=3)

        self._verlaufkasten = QGroupBox("Punkteverlauf")
        verlaufspalte = QVBoxLayout(self._verlaufkasten)
        self._punkteansicht = Punkteansicht()
        verlaufspalte.addWidget(self._punkteansicht)
        spalte.addWidget(self._verlaufkasten, stretch=2)
        return seite

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._rennkasten = QGroupBox("Letztes Rennwochenende")
        rennspalte = QVBoxLayout(self._rennkasten)
        self._rennkopf = QLabel("Noch kein Rennen gefahren.")
        self._rennkopf.setWordWrap(True)
        rennspalte.addWidget(self._rennkopf)
        self._rennliste = QTreeWidget()
        self._rennliste.setHeaderLabels(["#", "Fahrer", "Quali", "Punkte"])
        self._rennliste.setRootIsDecorated(False)
        self._rennliste.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._rennliste, self.fahrerkarte_gewuenscht.emit)
        rennspalte.addWidget(self._rennliste)
        spalte.addWidget(self._rennkasten, stretch=1)

        self._wechselkasten = QGroupBox("Auf- und Abstieg")
        wechselspalte = QVBoxLayout(self._wechselkasten)
        self._wechselliste = QTreeWidget()
        self._wechselliste.setHeaderLabels(["Fahrer", "Von", "Nach"])
        self._wechselliste.setRootIsDecorated(False)
        self._wechselliste.setAlternatingRowColors(True)
        wechselspalte.addWidget(self._wechselliste)
        self._wechselkasten.setVisible(False)
        spalte.addWidget(self._wechselkasten, stretch=1)

        self._abschlusskasten = QGroupBox("Saisonabschluss")
        abschlussspalte = QVBoxLayout(self._abschlusskasten)
        self._abschluss = QLabel()
        self._abschluss.setWordWrap(True)
        abschlussspalte.addWidget(self._abschluss)
        self._abschlusskasten.setVisible(False)
        spalte.addWidget(self._abschlusskasten)
        return seite

    # -- Fahren ------------------------------------------------------------
    def _fahre_rest(self) -> None:
        """Laesst die restliche Saison im Schnellmodus durchlaufen (GDD 15)."""
        if self._lauf.ist_fertig:
            return
        self._ganze_saison.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            while not self._lauf.ist_fertig:
                nummer = self._lauf.naechstes_rennen
                self._stand.setText(
                    f"Rennen {nummer} von {self._lauf.rennen_je_saison} laeuft ..."
                )
                QApplication.processEvents()
                self._letztes = self._lauf.fahre_rennen()
        finally:
            QApplication.restoreOverrideCursor()
            self._ganze_saison.setEnabled(not self._lauf.ist_fertig)
        self._aktualisiere()

    def _wechsle_saison(self) -> None:
        """Vollzieht Auf- und Abstieg und beginnt das naechste Jahr (GDD 13)."""
        if not self._lauf.ist_fertig:
            return
        try:
            self._lauf = self._lauf.naechste_saison()
        except (kern_saison.SaisonFehler, kern_wertung.WertungsFehler) as fehler:
            QMessageBox.warning(self, "Saisonwechsel", str(fehler))
            return
        self._welt = self._lauf.welt
        self._letztes = None
        # Nach einem Auf- oder Abstieg faehrt der Spieler woanders.
        spieler = self._welt.spieler
        if spieler is not None:
            self._liga.blockSignals(True)
            self._liga.setCurrentIndex(spieler.liga - 1)
            self._liga.blockSignals(False)
        self._aktualisiere()
        self.saison_gewechselt.emit()

    # -- Anzeige -----------------------------------------------------------
    def _aktualisiere(self, *_) -> None:
        # Das gefuehrte Wochenende faehrt denselben Saisonlauf; sein
        # Ergebnis steht dann in ``wochenenden`` und nicht in ``_letztes``.
        if self._lauf.wochenenden:
            self._letztes = self._lauf.wochenenden[-1]
        liga = self._liga.currentData()
        self._zeige_tabelle(liga)
        self._zeige_verlauf(liga)
        self._zeige_rennen(liga)
        self._zeige_wechsel()
        self._zeige_kalender()
        self._zeige_abschluss()
        self._naechste_saison.setEnabled(self._lauf.ist_fertig)
        self._ganze_saison.setEnabled(not self._lauf.ist_fertig)
        if self._lauf.ist_fertig:
            self._stand.setText(
                f"Saison {self._lauf.jahr} beendet - {self._lauf.gefahren} Rennen gefahren."
            )
        else:
            self._stand.setText(
                f"Rennen {self._lauf.gefahren} von {self._lauf.rennen_je_saison} gefahren; "
                f"als naechstes {self._lauf.strecke_zu(self._lauf.naechstes_rennen).name}."
            )

    def _zeige_abschluss(self) -> None:
        """Die Bilanz der beendeten Saison (GDD 13).

        Sichtbar erst nach Rennen 20; der Knopf daneben bestaetigt den
        Wechsel ins naechste Jahr.
        """
        if not self._lauf.ist_fertig:
            self._abschlusskasten.setVisible(False)
            return
        self._abschlusskasten.setVisible(True)
        self._abschlusskasten.setTitle(f"Saisonabschluss {self._lauf.jahr}")

        zeilen = []
        for liga in sorted(self._lauf.tabellen):
            stand = self._lauf.tabelle(liga).stand()
            if not stand:
                continue
            meister = self._welt.fahrer[stand[0].fahrer]
            zeilen.append(
                f"Liga {liga} ({self._konfiguration.ligenname(liga)}): "
                f"<b>{meister.name}</b>, {stand[0].punkte} Punkte"
            )

        spieler = self._welt.spieler
        eigen = ""
        if spieler is not None:
            tabelle = self._lauf.tabelle(spieler.liga)
            eintrag = tabelle.eintraege.get(spieler.nummer)
            if eintrag is not None:
                eigen = (
                    f"<br><br><b>{spieler.name}</b> - Liga {spieler.liga}, "
                    f"Platz {tabelle.platz_von(spieler.nummer)} von "
                    f"{len(tabelle.eintraege)}<br>"
                    f"{eintrag.punkte} Punkte · {eintrag.siege} Siege · "
                    f"{eintrag.podien} Podien · {eintrag.poles} Poles · "
                    f"{eintrag.schnellste_runden} schnellste Runden · "
                    f"{eintrag.ausfaelle} Ausfaelle"
                )
        self._abschluss.setText("Meister:<br>" + "<br>".join(zeilen) + eigen)

    def _zeige_kalender(self) -> None:
        """Kalenderstand und die Tage, die ein Rennen jetzt kosten wuerde.

        GDD 2: Das Rennen findet an seinem Renntag statt; wer vorher
        faehrt, laesst die nutzbaren Tage bis dahin verfallen.
        """
        karriere = self._lauf.karriere
        if karriere is None:
            self._kalender.setText("")
            return
        stand = (
            f"Kalender: {kern_kalender.wochentag(karriere.heute)} "
            f"{karriere.heute:%d.%m.%Y}"
        )
        nummer = self._lauf.naechstes_rennen
        if nummer is None:
            self._kalender.setStyleSheet("")
            self._kalender.setText(f"{stand} · Saison gefahren.")
            return

        renntag = self._lauf.renntag(nummer)
        stand += (
            f" · Rennen {nummer} am {kern_kalender.wochentag(renntag)} "
            f"{renntag:%d.%m.%Y}"
        )
        offen = self._lauf.offene_tage_vor_dem_rennen
        if offen:
            self._kalender.setStyleSheet(f"color: {FARBE_ABSTIEG.name()};")
            self._kalender.setText(
                f"{stand} · Noch {offen} nutzbare Tage - wer jetzt faehrt, "
                "laesst sie verfallen (GDD 2)."
            )
        else:
            self._kalender.setStyleSheet("")
            self._kalender.setText(f"{stand} · Heute ist Renntag.")

    def _zeige_tabelle(self, liga: int) -> None:
        self._tabelle.clear()
        self._tabellenkasten.setTitle(
            f"Saisonwertung {self._lauf.jahr} - Liga {liga} "
            f"({self._konfiguration.ligenname(liga)})"
        )
        aufsteiger = self._konfiguration.wert("auf_abstieg", "aufsteiger")
        absteiger = self._konfiguration.wert("auf_abstieg", "absteiger")
        stand = self._lauf.tabelle(liga).stand()
        for platz, eintrag in enumerate(stand, start=1):
            fahrer = self._welt.fahrer[eintrag.fahrer]
            team = self._welt.team_von(fahrer)
            zeile = QTreeWidgetItem(
                self._tabelle,
                [
                    str(platz),
                    fahrer.name,
                    team.name,
                    str(eintrag.punkte),
                    str(eintrag.siege),
                    str(eintrag.podien),
                    str(eintrag.poles),
                    str(eintrag.schnellste_runden),
                    str(eintrag.ausfaelle),
                ],
            )
            zeile.setForeground(0, QColor(team.farbe))
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            # Wer am Saisonende auf- oder absteigt, ist farbig markiert.
            if platz <= aufsteiger and liga > 1:
                zeile.setForeground(1, FARBE_AUFSTIEG)
            elif platz > len(stand) - absteiger and liga < len(self._lauf.tabellen):
                zeile.setForeground(1, FARBE_ABSTIEG)
            if fahrer.ist_spieler:
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(self._tabelle.columnCount()):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._tabelle.columnCount()):
            self._tabelle.resizeColumnToContents(spalte)

    def _zeige_verlauf(self, liga: int) -> None:
        """Fuellt das Punktediagramm mit dem Stand jedes Fahrers (Punkt 9).

        Gezeichnet wird die Reihenfolge der Tabelle, damit die
        hervorgehobene Linie zu der Zeile passt, die daneben gewaehlt ist.
        """
        stand = self._lauf.tabelle(liga).stand()
        statistik = self._lauf.statistik
        reihen = []
        self._fahrernummern = []
        for eintrag in stand:
            fahrer = self._welt.fahrer[eintrag.fahrer]
            team = self._welt.team_von(fahrer)
            reihen.append(
                (fahrer.kuerzel, team.farbe, statistik.punktestand(liga, fahrer.nummer))
            )
            self._fahrernummern.append(fahrer.nummer)
        self._punkteansicht.zeige(reihen)
        self._verlaufkasten.setTitle(
            f"Punkteverlauf - Liga {liga}, {self._punkteansicht.rennen} Rennen"
        )
        self._auswahl_geaendert(self._tabelle.currentItem())

    def _auswahl_geaendert(self, jetzt, _davor=None) -> None:
        """Hebt Spieler und gewaehlte Zeile im Diagramm hervor (Punkt 9)."""
        if not self._fahrernummern:
            return
        # Alle eigenen Fahrer dieser Liga treten hervor, nicht nur einer:
        # Seit der Spieler Teamchef ist, hat er bis zu vier.
        hervor = [
            self._fahrernummern.index(f.nummer)
            for f in self._welt.spielerfahrer
            if f.nummer in self._fahrernummern
        ]
        gewaehlt = jetzt.data(0, Qt.UserRole) if jetzt is not None else None
        if gewaehlt in self._fahrernummern:
            stelle = self._fahrernummern.index(gewaehlt)
            if stelle not in hervor:
                hervor.append(stelle)
        self._punkteansicht.hebe_hervor(hervor)

    def _zeige_rennen(self, liga: int) -> None:
        self._rennliste.clear()
        if self._letztes is None:
            self._rennkopf.setText("Noch kein Rennen gefahren.")
            return

        ergebnis = self._letztes.liga(liga)
        art = "ausfuehrlich" if ergebnis.ausfuehrlich else "Schnellmodus"
        self._rennkopf.setText(
            f"Rennen {self._letztes.nummer} - {self._letztes.strecke} ({art})<br>"
            f"Wetter: {', '.join(ergebnis.wetter)}<br>"
            f"Siegerzeit {formatiere_dauer(ergebnis.siegerzeit_ms)} · "
            f"schnellste Runde {formatiere_dauer(ergebnis.schnellste_runde_ms)} · "
            f"{ergebnis.ueberholmanoever} Ueberholmanoever · "
            f"{ergebnis.ausfaelle} Ausfaelle"
        )
        for e in ergebnis.ergebnisse:
            fahrer = self._welt.fahrer[e.fahrer]
            punkte = kern_wertung.punkte_fuer(self._konfiguration, e)
            zeile = QTreeWidgetItem(
                self._rennliste,
                [
                    "DNF" if e.ausgefallen else str(e.rennplatz),
                    fahrer.name + (" (SR)" if e.schnellste_runde else ""),
                    str(e.qualifyingplatz),
                    str(punkte),
                ],
            )
            zeile.setForeground(0, QColor(self._welt.team_von(fahrer).farbe))
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            if fahrer.ist_spieler:
                schrift = zeile.font(1)
                schrift.setBold(True)
                for spalte in range(self._rennliste.columnCount()):
                    zeile.setFont(spalte, schrift)
        for spalte in range(self._rennliste.columnCount()):
            self._rennliste.resizeColumnToContents(spalte)

    def _zeige_wechsel(self) -> None:
        self._wechselliste.clear()
        if not self._lauf.ist_fertig:
            self._wechselkasten.setVisible(False)
            return
        self._wechselkasten.setVisible(True)
        try:
            wechsel = self._lauf.schliesse_ab()
        except kern_saison.SaisonFehler as fehler:  # pragma: no cover - Notfall
            QMessageBox.warning(self, "Auf- und Abstieg", str(fehler))
            return
        self._wechselkasten.setTitle(f"Auf- und Abstieg ({len(wechsel)} Wechsel)")
        for w in sorted(wechsel, key=lambda w: (w.von_liga, not w.ist_aufstieg)):
            fahrer = self._welt.fahrer[w.fahrer]
            zeile = QTreeWidgetItem(
                self._wechselliste,
                [fahrer.name, f"Liga {w.von_liga}", f"Liga {w.nach_liga}"],
            )
            zeile.setForeground(2, FARBE_AUFSTIEG if w.ist_aufstieg else FARBE_ABSTIEG)
        for spalte in range(self._wechselliste.columnCount()):
            self._wechselliste.resizeColumnToContents(spalte)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def lauf(self) -> Saisonlauf:
        return self._lauf

    @property
    def tabelle(self) -> QTreeWidget:
        return self._tabelle

    @property
    def rennliste(self) -> QTreeWidget:
        return self._rennliste

    @property
    def wechselliste(self) -> QTreeWidget:
        return self._wechselliste

    @property
    def liga_auswahl(self) -> QComboBox:
        return self._liga

    @property
    def knopf_restliche_saison(self) -> QPushButton:
        return self._ganze_saison

    @property
    def kalenderzeile(self) -> QLabel:
        return self._kalender

    @property
    def knopf_naechste_saison(self) -> QPushButton:
        return self._naechste_saison

    @property
    def abschlusstext(self) -> QLabel:
        return self._abschluss

    @property
    def punkteansicht(self) -> Punkteansicht:
        return self._punkteansicht
