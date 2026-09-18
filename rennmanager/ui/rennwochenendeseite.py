"""Das gefuehrte Rennwochenende (Punkt 12).

Frueher lagen Qualifying und Rennen als zwei Reiter nebeneinander, jeder
mit eigenen Reglern fuer Strecke, Liga, Rundenzahl und Seed. Das war ein
Werkzeug, kein Spiel: Der Spieler stellte sein eigenes Rennen zusammen.

Hier laeuft stattdessen **sein** Wochenende ab, in vier Schritten:

1. **Vorschau** - wo, wann, wie viele Runden, wie steht er in der Tabelle
2. **Qualifying** - die Session seiner Liga, Fahrt fuer Fahrt (GDD 4)
3. **Rennen** - auf die gefahrene Aufstellung, abspielbar im Zeitraffer
4. **Ergebnis** - seine Wertung, die der Liga, und was das Wochenende
   eingebracht hat

Gefahren wird, was der Kalender vorgibt (GDD 2): Strecke, Rundenzahl,
Aufstellung und Seed kommen aus der Saison, nicht aus einem Regler. Die
Arbeit macht ``kern.saison.Wochenendlauf``; diese Seite ist die Fuehrung
drumherum. Erst der letzte Schritt bucht - ein abgebrochenes Wochenende
bewegt die Saison nicht.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import saison as kern_saison
from rennmanager.kern import wertung as kern_wertung
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.qualifyingseite import Qualifyingseite
from rennmanager.ui.rennseite import Rennseite
from rennmanager.ui.tabellen import verbinde_fahrerkarte

# Die vier Schritte. Der Text auf dem Knopf sagt, was als Naechstes
# passiert - nicht, wo man gerade ist.
SCHRITTE = ("Vorschau", "Qualifying", "Rennen", "Ergebnis")
WEITER = (
    "Qualifying fahren",
    "Ins Rennen",
    "Wochenende abschliessen",
    "Naechstes Rennwochenende",
)

FARBE_AKTIV = QColor("#0b0b0b")
FARBE_RUHE = QColor("#8b93a1")
FARBE_GUT = QColor("#2e7d32")
FARBE_SCHLECHT = QColor("#c62828")


class Rennwochenendeseite(QWidget):
    """Fuehrt den Spieler durch sein Rennwochenende."""

    # Doppelklick auf einen Namen: Das Fenster oeffnet die Fahrerkarte.
    fahrerkarte_gewuenscht = Signal(int)
    # Ein Wochenende ist gebucht - Saison, Karriere und Statistik haben
    # sich bewegt, die anderen Seiten muessen nachziehen.
    wochenende_gefahren = Signal()

    def __init__(
        self,
        konfiguration: Konfiguration,
        lauf: kern_saison.Saisonlauf,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._lauf = lauf
        self._wochenende: kern_saison.Wochenendlauf | None = None
        self._schritt = 0

        spalte = QVBoxLayout(self)
        spalte.addWidget(self._baue_kopf())
        spalte.addWidget(self._baue_schrittleiste())

        self._blaetter = QStackedWidget()
        self._blaetter.addWidget(self._baue_vorschau())
        self._quali = Qualifyingseite(konfiguration)
        self._quali.fahrerkarte_gewuenscht.connect(self.fahrerkarte_gewuenscht.emit)
        self._blaetter.addWidget(self._quali)
        self._rennen = Rennseite(konfiguration, lauf.welt, lauf.karriere)
        self._rennen.fahrerkarte_gewuenscht.connect(self.fahrerkarte_gewuenscht.emit)
        self._blaetter.addWidget(self._rennen)
        self._blaetter.addWidget(self._baue_ergebnis())
        spalte.addWidget(self._blaetter, stretch=1)

        self._rueste_zu()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QWidget:
        zeile = QWidget()
        kasten = QHBoxLayout(zeile)
        kasten.setContentsMargins(0, 0, 0, 0)

        self._ueberschrift = QLabel()
        schrift = self._ueberschrift.font()
        schrift.setPointSize(schrift.pointSize() + 3)
        schrift.setBold(True)
        self._ueberschrift.setFont(schrift)

        self._weiter = QPushButton()
        self._weiter.clicked.connect(self._naechster_schritt)

        kasten.addWidget(self._ueberschrift)
        kasten.addStretch(1)
        kasten.addWidget(self._weiter)
        return zeile

    def _baue_schrittleiste(self) -> QWidget:
        """Vier Marken, die zeigen, wo im Wochenende man steht."""
        zeile = QWidget()
        kasten = QHBoxLayout(zeile)
        kasten.setContentsMargins(0, 0, 0, 0)
        self._marken = []
        for nummer, name in enumerate(SCHRITTE, start=1):
            marke = QLabel(f"{nummer}. {name}")
            self._marken.append(marke)
            kasten.addWidget(marke)
            if nummer < len(SCHRITTE):
                pfeil = QLabel("→")
                pfeil.setStyleSheet(f"color: {FARBE_RUHE.name()};")
                kasten.addWidget(pfeil)
        kasten.addStretch(1)
        return zeile

    def _baue_vorschau(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        self._vorschaukasten = QGroupBox("Das naechste Rennwochenende")
        self._vorschau = QFormLayout(self._vorschaukasten)
        spalte.addWidget(self._vorschaukasten)

        self._standkasten = QGroupBox("So steht es vor dem Rennen")
        standspalte = QVBoxLayout(self._standkasten)
        self._vorher = QTreeWidget()
        self._vorher.setHeaderLabels(["#", "Fahrer", "Team", "Punkte"])
        self._vorher.setRootIsDecorated(False)
        self._vorher.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._vorher, self.fahrerkarte_gewuenscht.emit)
        standspalte.addWidget(self._vorher)
        spalte.addWidget(self._standkasten, stretch=1)
        return seite

    def _baue_ergebnis(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        self._bilanzkasten = QGroupBox("Das Wochenende")
        self._bilanz = QFormLayout(self._bilanzkasten)
        spalte.addWidget(self._bilanzkasten)

        zeile = QHBoxLayout()
        rennkasten = QGroupBox("Rennergebnis")
        rennspalte = QVBoxLayout(rennkasten)
        self._ergebnisliste = QTreeWidget()
        self._ergebnisliste.setHeaderLabels(["#", "Fahrer", "Quali", "Punkte"])
        self._ergebnisliste.setRootIsDecorated(False)
        self._ergebnisliste.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._ergebnisliste, self.fahrerkarte_gewuenscht.emit)
        rennspalte.addWidget(self._ergebnisliste)
        zeile.addWidget(rennkasten)

        tabellenkasten = QGroupBox("Tabelle danach")
        tabellenspalte = QVBoxLayout(tabellenkasten)
        self._nachher = QTreeWidget()
        self._nachher.setHeaderLabels(["#", "Fahrer", "Punkte", "±"])
        self._nachher.setRootIsDecorated(False)
        self._nachher.setAlternatingRowColors(True)
        verbinde_fahrerkarte(self._nachher, self.fahrerkarte_gewuenscht.emit)
        tabellenspalte.addWidget(self._nachher)
        zeile.addWidget(tabellenkasten)
        spalte.addLayout(zeile, stretch=1)
        return seite

    # -- Ablauf ------------------------------------------------------------
    def _rueste_zu(self) -> None:
        """Bereitet das naechste Wochenende vor, ohne es zu fahren."""
        self._schritt = 0
        self._wochenende = None
        if self._lauf.ist_fertig:
            self._zeige_saisonende()
            return
        self._wochenende = kern_saison.Wochenendlauf(self._lauf, self._spielerliga())
        self._plaetze_vorher = self._plaetze()
        self._fuelle_vorschau()
        self._zeige_schritt()

    def _spielerliga(self) -> int:
        spieler = self._lauf.welt.spieler
        return spieler.liga if spieler else 1

    def _plaetze(self) -> dict[int, int]:
        """Platz je Fahrer in der Tabelle der Spielerliga."""
        tabelle = self._lauf.tabelle(self._spielerliga())
        return {e.fahrer: platz for platz, e in enumerate(tabelle.stand(), start=1)}

    def _naechster_schritt(self) -> None:
        if self._lauf.ist_fertig and self._wochenende is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._weiter.setEnabled(False)
        try:
            if self._schritt == 0:
                self._quali.zeige_session(self._wochenende.fahre_qualifying())
                self._schritt = 1
            elif self._schritt == 1:
                verlauf = self._wochenende.fahre_rennen()
                self._rennen.zeige_verlauf(
                    verlauf, self._wochenende.strecke, self._wochenende.qualifying
                )
                self._schritt = 2
            elif self._schritt == 2:
                self._wochenende.schliesse_ab()
                self._fuelle_ergebnis()
                self._schritt = 3
                self.wochenende_gefahren.emit()
            else:
                self._rueste_zu()
                return
        except kern_saison.SaisonFehler as fehler:  # pragma: no cover - Notfall
            QMessageBox.warning(self, "Rennwochenende", str(fehler))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._weiter.setEnabled(True)
        self._zeige_schritt()

    def _zeige_schritt(self) -> None:
        self._blaetter.setCurrentIndex(self._schritt)
        for nummer, marke in enumerate(self._marken):
            schrift = marke.font()
            schrift.setBold(nummer == self._schritt)
            marke.setFont(schrift)
            farbe = FARBE_AKTIV if nummer <= self._schritt else FARBE_RUHE
            marke.setStyleSheet(f"color: {farbe.name()};")
        self._weiter.setText(WEITER[self._schritt])
        self._weiter.setEnabled(True)
        if self._wochenende is not None:
            self._ueberschrift.setText(
                f"Rennen {self._wochenende.nummer} von "
                f"{self._lauf.rennen_je_saison} · {self._wochenende.strecke.name}"
            )

    def _zeige_saisonende(self) -> None:
        self._blaetter.setCurrentIndex(0)
        self._ueberschrift.setText(f"Saison {self._lauf.jahr} gefahren")
        self._weiter.setText("Saison beendet")
        self._weiter.setEnabled(False)
        self._leere(self._vorschau)
        self._vorschau.addRow(
            QLabel(
                "Alle Rennen sind gefahren. Auf- und Abstieg und der Wechsel "
                "ins naechste Jahr stehen im Reiter Saison (GDD 13)."
            )
        )
        self._vorher.clear()
        for marke in self._marken:
            marke.setStyleSheet(f"color: {FARBE_RUHE.name()};")
            schrift = marke.font()
            schrift.setBold(False)
            marke.setFont(schrift)

    # -- Anzeige -----------------------------------------------------------
    def _fuelle_vorschau(self) -> None:
        lauf = self._wochenende
        liga = self._spielerliga()
        self._leere(self._vorschau)
        self._vorschaukasten.setTitle(
            f"Rennen {lauf.nummer} von {self._lauf.rennen_je_saison}"
        )

        strecke = lauf.strecke
        zeilen = [
            ("Strecke:", f"{strecke.name} ({strecke.land})"),
            ("Charakter:", strecke.charakter),
            ("Laenge:", f"{strecke.laenge_m / 1000:.3f} km".replace(".", ",")),
            ("Runden:", str(lauf.runden)),
            ("Liga:", f"{liga} - {self._konfiguration.ligenname(liga)}"),
        ]
        renntag = lauf.renntag
        if renntag is not None:
            zeilen.insert(
                0,
                (
                    "Renntag:",
                    f"{kern_kalender.wochentag(renntag)} {renntag:%d.%m.%Y}",
                ),
            )
        for beschriftung, wert in zeilen:
            self._vorschau.addRow(beschriftung, QLabel(wert))

        self._vorher.clear()
        stand = self._lauf.tabelle(liga).stand()
        # Vor dem ersten Rennen gibt es keine Tabelle. Dann steht hier das
        # Feld nach Staerke - dieselbe Reihenfolge, nach der das
        # Qualifying faehrt, solange es keinen Meisterschaftsstand gibt
        # (GDD 4).
        self._standkasten.setTitle(
            "So steht es vor dem Rennen"
            if stand
            else "Das Feld nach Staerke - die Tabelle beginnt mit Rennen 1"
        )
        if stand:
            zeilen = [
                (self._lauf.welt.fahrer[e.fahrer], str(e.punkte)) for e in stand
            ]
        else:
            zeilen = [(fahrer, "-") for fahrer in self._lauf.welt.liga(liga)]
        for platz, (fahrer, punkte) in enumerate(zeilen, start=1):
            team = self._lauf.welt.team_von(fahrer)
            zeile = QTreeWidgetItem(
                self._vorher, [str(platz), fahrer.name, team.name, punkte]
            )
            zeile.setForeground(0, QColor(team.farbe))
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            self._hebe_spieler_hervor(zeile, fahrer, self._vorher.columnCount())
        for spalte in range(self._vorher.columnCount()):
            self._vorher.resizeColumnToContents(spalte)

    def _fuelle_ergebnis(self) -> None:
        liga = self._spielerliga()
        wochenende = self._wochenende.wochenende
        ergebnis = wochenende.liga(liga)
        spieler = self._lauf.welt.spieler

        self._leere(self._bilanz)
        self._bilanzkasten.setTitle(
            f"Rennen {wochenende.nummer} - {wochenende.strecke}"
        )
        zeilen = [
            ("Wetter:", ", ".join(ergebnis.wetter)),
            ("Siegerzeit:", formatiere_dauer(ergebnis.siegerzeit_ms)),
            ("Schnellste Runde:", formatiere_dauer(ergebnis.schnellste_runde_ms)),
            ("Ueberholmanoever:", str(ergebnis.ueberholmanoever)),
            ("Ausfaelle:", str(ergebnis.ausfaelle)),
        ]
        if spieler is not None:
            eigen = next(
                (e for e in ergebnis.ergebnisse if e.fahrer == spieler.nummer), None
            )
            if eigen is not None:
                punkte = kern_wertung.punkte_fuer(self._konfiguration, eigen)
                platz = "DNF" if eigen.ausgefallen else str(eigen.rennplatz)
                zeilen.insert(
                    0,
                    (
                        f"{spieler.name}:",
                        f"Platz {platz} von {eigen.qualifyingplatz} gestartet · "
                        f"{punkte} Punkte",
                    ),
                )
        for beschriftung, wert in zeilen:
            self._bilanz.addRow(beschriftung, QLabel(wert))

        self._ergebnisliste.clear()
        for e in ergebnis.ergebnisse:
            fahrer = self._lauf.welt.fahrer[e.fahrer]
            zeile = QTreeWidgetItem(
                self._ergebnisliste,
                [
                    "DNF" if e.ausgefallen else str(e.rennplatz),
                    fahrer.name + (" (SR)" if e.schnellste_runde else ""),
                    str(e.qualifyingplatz),
                    str(kern_wertung.punkte_fuer(self._konfiguration, e)),
                ],
            )
            zeile.setForeground(0, QColor(self._lauf.welt.team_von(fahrer).farbe))
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            self._hebe_spieler_hervor(zeile, fahrer, self._ergebnisliste.columnCount())
        for spalte in range(self._ergebnisliste.columnCount()):
            self._ergebnisliste.resizeColumnToContents(spalte)

        # Die Tabelle danach, mit dem Sprung gegen vorher. Ohne den sieht
        # man nicht, was das Wochenende in der Meisterschaft bewegt hat.
        self._nachher.clear()
        for platz, eintrag in enumerate(self._lauf.tabelle(liga).stand(), start=1):
            fahrer = self._lauf.welt.fahrer[eintrag.fahrer]
            davor = self._plaetze_vorher.get(eintrag.fahrer)
            sprung = "" if davor is None else f"{davor - platz:+d}"
            if sprung == "+0":
                sprung = "="
            zeile = QTreeWidgetItem(
                self._nachher,
                [str(platz), fahrer.name, str(eintrag.punkte), sprung],
            )
            zeile.setForeground(0, QColor(self._lauf.welt.team_von(fahrer).farbe))
            zeile.setData(0, Qt.UserRole, fahrer.nummer)
            if davor is not None and davor != platz:
                zeile.setForeground(
                    3, FARBE_GUT if davor > platz else FARBE_SCHLECHT
                )
            self._hebe_spieler_hervor(zeile, fahrer, self._nachher.columnCount())
        for spalte in range(self._nachher.columnCount()):
            self._nachher.resizeColumnToContents(spalte)

    @staticmethod
    def _hebe_spieler_hervor(zeile, fahrer, spalten: int) -> None:
        if not fahrer.ist_spieler:
            return
        schrift = zeile.font(1)
        schrift.setBold(True)
        for spalte in range(spalten):
            zeile.setFont(spalte, schrift)

    @staticmethod
    def _leere(formular: QFormLayout) -> None:
        while formular.rowCount():
            formular.removeRow(0)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def schritt(self) -> int:
        return self._schritt

    @property
    def knopf_weiter(self) -> QPushButton:
        return self._weiter

    @property
    def wochenende(self) -> kern_saison.Wochenendlauf | None:
        return self._wochenende

    @property
    def qualifyingseite(self) -> Qualifyingseite:
        return self._quali

    @property
    def rennseite(self) -> Rennseite:
        return self._rennen

    @property
    def vorschauliste(self) -> QTreeWidget:
        return self._vorher

    @property
    def ergebnisliste(self) -> QTreeWidget:
        return self._ergebnisliste

    @property
    def tabellenliste(self) -> QTreeWidget:
        return self._nachher
