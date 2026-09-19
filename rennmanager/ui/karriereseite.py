"""Seite fuer die Karriere: Kalender, Entwicklung und Sponsoren (GDD 2, 9, 10).

Links der Tageskalender mit den beiden Plaetzen des Tages, rechts das
Konto und die Sponsorenangebote. Zeit ist eine Kapazitaet: Jeder nutzbare
Tag hat einen Platz fuer den Fahrer und einen fuer die Werkstatt; ein Tag,
der vergeht, ohne belegt zu sein, ist verloren.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern.entwicklung import EntwicklungsFehler, ist_bezahlbar
from rennmanager.kern.kalender import Tagesart
from rennmanager.kern.karriere import FAHRERPLATZ, WERKSTATTPLATZ, Karriere, KarriereFehler
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.kalenderstreifen import Kalenderstreifen

# Punkt 83: So hoch bleibt die Faehigkeitenliste mindestens - genug fuer
# rund ein Dutzend Zeilen. Darunter lohnt sich das Rollen in ihr nicht
# mehr, man sieht dann nur noch Kopfzeile und Balken.
HOEHE_FAEHIGKEITEN = 320

FARBE_RENNEN = QColor("#c62828")
FARBE_QUALIFYING = QColor("#eda100")
FARBE_REISE = QColor("#8b93a1")
FARBE_BELEGT = QColor("#2e7d32")

# Dauerarten, bei denen ein Restzaehler nichts aussagt (GDD 14).
OHNE_RESTZAEHLER = (
    kern_ereignis.Dauer.BIS_REPARATUR,
    kern_ereignis.Dauer.SOFORT,
    kern_ereignis.Dauer.DAUERHAFT,
)


def euro(betrag: float) -> str:
    return f"{betrag:,.0f} €".replace(",", ".")


class Karriereseite(QWidget):
    """Tageskalender, Entwicklung und Sponsoren."""

    # Punkt 17: Ein Tageswechsel ist ein Spielstand wert - das Fenster
    # schreibt darauf den Autosave.
    tag_gewechselt = Signal()
    # Die Werte eines eigenen Autos haben sich geaendert - belegter Tag,
    # Sofortkauf oder Tageswechsel. Die Welt kennt diese Werte nicht, sie
    # stehen in der Karriere; wer sie anzeigt, muss sie neu holen.
    werte_geaendert = Signal()

    def __init__(
        self,
        konfiguration: Konfiguration,
        karriere: Karriere,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._karriere = karriere

        # Punkt 83: Die Seite traegt Kopf, Kalenderband, die
        # Faehigkeitenliste und die Seitenspalte untereinander. Auf einem
        # kleinen Fenster blieb fuer die Liste kaum Hoehe, und ihr eigener
        # Rollbalken half nichts, weil schon der Kasten abgeschnitten war.
        # Jetzt rollt die ganze Seite.
        rollflaeche = QScrollArea(self)
        rollflaeche.setWidgetResizable(True)
        rollflaeche.setFrameShape(QScrollArea.NoFrame)
        inhalt = QWidget()
        rollflaeche.setWidget(inhalt)
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(0, 0, 0, 0)
        aussen.addWidget(rollflaeche)

        spalte = QVBoxLayout(inhalt)
        spalte.addLayout(self._baue_kopf())
        # Punkt 7: Das Jahr als Band - wo Luecken bleiben, ist Zeit
        # liegen geblieben (GDD 2).
        self._streifen = Kalenderstreifen()
        streifenkasten = QGroupBox("Kalender")
        streifen_spalte = QVBoxLayout(streifenkasten)
        streifen_spalte.addWidget(self._streifen)
        spalte.addWidget(streifenkasten)

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_entwicklung())
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._fuelle_fahrerwahl()
        self._zeichne()

    # -- Die vier eigenen Autos --------------------------------------------
    def _fuelle_fahrerwahl(self, namen: dict[int, str] | None = None) -> None:
        """Traegt die eigenen Fahrer ein; der gewaehlte bleibt gewaehlt."""
        self._fahrerwahl.blockSignals(True)
        self._fahrerwahl.clear()
        for nummer in self._karriere.fahrer:
            beschriftung = (namen or {}).get(nummer, f"Fahrer {nummer}")
            self._fahrerwahl.addItem(beschriftung, nummer)
        stelle = self._fahrerwahl.findData(self._karriere.fahrernummer)
        self._fahrerwahl.setCurrentIndex(stelle if stelle >= 0 else 0)
        self._fahrerwahl.blockSignals(False)
        # Bei einem einzigen Auto waere die Auswahl eine Zeile ohne Wahl.
        self._fahrerwahl.setVisible(len(self._karriere.fahrer) > 1)

    def _fahrer_gewechselt(self) -> None:
        nummer = self._fahrerwahl.currentData()
        if nummer is None or nummer == self._karriere.fahrernummer:
            return
        self._karriere.waehle_fahrer(int(nummer))
        self._zeichne()

    def zeige_namen(self, namen: dict[int, str]) -> None:
        """Ersetzt 'Fahrer 401' durch den wirklichen Namen."""
        self._fuelle_fahrerwahl(namen)
        # Punkt 56: Ereignisse treffen einzelne Fahrer; die Meldung nennt
        # den Namen. Der Kern kennt nur Nummern.
        self._karriere.benenne_fahrer(namen)
        self._zeichne()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._datum = QLabel()
        schrift = self._datum.font()
        schrift.setBold(True)
        schrift.setPointSize(schrift.pointSize() + 2)
        self._datum.setFont(schrift)

        # Jedes Auto gehoert seinem Fahrer und wird einzeln entwickelt -
        # hier steht, an welchem der vier heute gearbeitet wird.
        self._fahrerwahl = QComboBox()
        self._fahrerwahl.setToolTip(
            "Jedes Auto gehoert seinem Fahrer und wird fuer sich "
            "entwickelt. Hier waehlen Sie, an welchem Sie arbeiten."
        )
        self._fahrerwahl.currentIndexChanged.connect(self._fahrer_gewechselt)

        self._weiter = QPushButton("Tag weiter")
        self._weiter.clicked.connect(self._tag_weiter)
        self._springen = QPushButton("Zum naechsten Rennen")
        self._springen.clicked.connect(self._zum_rennen)

        self._hinweis = QLabel()
        # Was der letzte Tageswechsel gebracht hat (GDD 14).
        self._meldung = QLabel()
        self._meldung.setWordWrap(True)
        self._meldung.setStyleSheet(f"color: {FARBE_RENNEN.name()};")
        zeile.addWidget(self._datum)
        zeile.addSpacing(12)
        zeile.addWidget(QLabel("Auto:"))
        zeile.addWidget(self._fahrerwahl)
        zeile.addSpacing(12)
        zeile.addWidget(self._weiter)
        zeile.addWidget(self._springen)
        zeile.addSpacing(12)
        zeile.addWidget(self._hinweis)
        zeile.addSpacing(12)
        zeile.addWidget(self._meldung, stretch=1)
        return zeile

    def _baue_entwicklung(self) -> QWidget:
        kasten = QGroupBox("Faehigkeiten")
        spalte = QVBoxLayout(kasten)

        self._plaetze = QLabel()
        spalte.addWidget(self._plaetze)

        # Die Knoepfe stehen ueber der Liste: Die Liste ist lang, und wer
        # unten in ihr eine Faehigkeit waehlt, soll nicht erst wieder
        # nach unten schauen muessen.
        knoepfe = QHBoxLayout()
        self._belegen = QPushButton("Heutigen Tag belegen")
        self._belegen.clicked.connect(self._belege_tag)
        self._kaufen = QPushButton("Sofort kaufen (+10)")
        self._kaufen.clicked.connect(self._kaufe)
        knoepfe.addWidget(self._belegen)
        knoepfe.addWidget(self._kaufen)
        knoepfe.addStretch(1)
        spalte.addLayout(knoepfe)

        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(
            ["", "Faehigkeit", "Wert", "Waehrung", "Ein Tag bringt", "Kosten", "Platz"]
        )
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        # Punkt 83: Die Liste traegt alle Faehigkeiten der Matrix plus die
        # Zusatzfaehigkeiten. Ohne Mindesthoehe schrumpfte sie auf dem
        # Teiler auf zwei Zeilen zusammen; mit ihr bleibt sie lesbar und
        # rollt im Zweifel selbst.
        self._liste.setMinimumHeight(HOEHE_FAEHIGKEITEN)
        spalte.addWidget(self._liste)
        return kasten

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._konto = QFormLayout()
        kontokasten = QGroupBox("Konto")
        kontokasten.setLayout(self._konto)
        spalte.addWidget(kontokasten)

        # Ereignisse und Reparaturen (GDD 14).
        self._ereignisse = QTreeWidget()
        self._ereignisse.setHeaderLabels(["Ereignis", "Wirkung", "Dauer", "Rest"])
        self._ereignisse.setRootIsDecorated(False)
        self._ereignisse.setAlternatingRowColors(True)
        self._ereigniskasten = QGroupBox("Ereignisse")
        ereignis_spalte = QVBoxLayout(self._ereigniskasten)
        ereignis_spalte.addWidget(self._ereignisse)
        self._reparieren = QPushButton("Reparieren")
        self._reparieren.clicked.connect(self._repariere)
        ereignis_spalte.addWidget(self._reparieren)
        spalte.addWidget(self._ereigniskasten, stretch=1)

        # Die Sponsoren haben seit Schritt 10 einen eigenen Reiter; hier
        # steht nur noch, was sie einbringen.
        self._sponsorenstand = QLabel()
        self._sponsorenstand.setWordWrap(True)
        kasten = QGroupBox("Sponsoren")
        kasten_spalte = QVBoxLayout(kasten)
        kasten_spalte.addWidget(self._sponsorenstand)
        spalte.addWidget(kasten)
        return seite

    # -- Aktionen ----------------------------------------------------------
    def _tag_weiter(self) -> None:
        offen = len(self._karriere.meldungen)
        try:
            self._karriere.tag_weiter()
        except KarriereFehler as fehler:
            QMessageBox.information(self, "Saisonende", str(fehler))
            return
        self._zeichne()
        self._melde_neues(offen)
        self.werte_geaendert.emit()
        self.tag_gewechselt.emit()

    def _zum_rennen(self) -> None:
        offen = len(self._karriere.meldungen)
        try:
            self._karriere.bis_zum_rennen()
        except KarriereFehler as fehler:
            QMessageBox.information(self, "Kein Rennen mehr", str(fehler))
            return
        self._zeichne()
        self._melde_neues(offen)
        self.werte_geaendert.emit()
        self.tag_gewechselt.emit()

    def _melde_neues(self, vorher: int) -> None:
        """Zeigt, was seit dem letzten Tageswechsel passiert ist (GDD 14).

        Bewusst kein modaler Dialog: Der Spieler schaltet viele Tage
        hintereinander weiter, und ein Fenster, das jedes Mal wegklickt
        werden will, macht daraus eine Qual.
        """
        neue = self._karriere.meldungen[vorher:]
        if not neue:
            self._meldung.setText("")
            return
        self._meldung.setText(
            " · ".join(f"{m.datum:%d.%m.} {m.zeile}" for m in neue)
        )

    def _repariere(self) -> None:
        """Repariert den gewaehlten Defekt oder Schaden (GDD 14)."""
        zeile = self._ereignisse.currentItem()
        schluessel = zeile.data(0, Qt.UserRole) if zeile is not None else None
        if schluessel is None:
            QMessageBox.information(
                self, "Reparatur", "Kein reparierbarer Eintrag gewaehlt."
            )
            return
        try:
            kosten = self._karriere.repariere(schluessel)
        except KarriereFehler as fehler:
            QMessageBox.warning(self, "Reparatur", str(fehler))
            return
        self._zeichne()
        self._meldung.setText(f"{schluessel} repariert fuer {euro(kosten)}.")

    def _gewaehlt(self) -> str | None:
        eintrag = self._liste.currentItem()
        return eintrag.data(0, Qt.UserRole) if eintrag else None

    def _belege_tag(self) -> None:
        schluessel = self._gewaehlt()
        if schluessel is None:
            return
        try:
            self._karriere.belege_tag(schluessel)
        except (KarriereFehler, EntwicklungsFehler) as fehler:
            QMessageBox.information(self, "Nicht moeglich", str(fehler))
            return
        self._zeichne()
        self.werte_geaendert.emit()

    def _kaufe(self) -> None:
        schluessel = self._gewaehlt()
        if schluessel is None:
            return
        try:
            self._karriere.kaufe(schluessel)
        except (KarriereFehler, EntwicklungsFehler) as fehler:
            QMessageBox.information(self, "Nicht moeglich", str(fehler))
            return
        self._zeichne()
        self.werte_geaendert.emit()

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self) -> None:
        self._streifen.zeige(self._karriere)
        tag = self._karriere.tag
        self._datum.setText(
            f"{kern_kalender.wochentag(tag.datum)} {tag.datum:%d.%m.%Y} — {tag.art.bezeichnung}"
        )
        rennen = self._karriere.naechstes_rennen
        if rennen is None:
            self._hinweis.setText("Saisonende erreicht")
        else:
            self._hinweis.setText(
                f"Naechstes Rennen am {rennen.strftime('%d.%m.')} "
                f"(Rennen {self._karriere.saison.rennnummer_nach(self._karriere.heute)} "
                f"von {len(self._karriere.saison.renntage)}), "
                f"noch {self._karriere.offene_tage} nutzbare Tage"
            )

        belegt = self._karriere.belegt
        self._plaetze.setText(
            "Plaetze heute: "
            f"Fahrer {'belegt' if FAHRERPLATZ in belegt else 'frei'} · "
            f"Werkstatt {'belegt' if WERKSTATTPLATZ in belegt else 'frei'}"
            + ("" if tag.art is Tagesart.NUTZBAR else "  (heute nicht nutzbar)")
        )
        self._belegen.setEnabled(tag.art is Tagesart.NUTZBAR)

        self._fuelle_faehigkeiten()
        self._fuelle_konto()
        self._fuelle_ereignisse()
        self._fuelle_sponsoren()

    def _fuelle_faehigkeiten(self) -> None:
        gewaehlt = self._gewaehlt()
        self._liste.clear()
        belegt = self._karriere.belegt
        # Was ein Ereignis gerade sperrt (GDD 14: E2, E6).
        gesperrt = self._karriere.gesperrt()

        matrix = {f.schluessel: f for f in self._konfiguration.faehigkeiten}
        schluessel = list(matrix)
        schluessel += list(self._konfiguration.zusatzfaehigkeiten)
        for name in schluessel:
            try:
                vorschau = self._karriere.vorschau(name)
            except EntwicklungsFehler:
                continue

            if name in matrix:
                anzeigename = matrix[name].name
                waehrung = "".join(matrix[name].waehrung)
            else:
                # Wetterfaehigkeiten und Reifenfluesterer stehen ausserhalb
                # der Wirkungsmatrix und bringen ihren Namen selbst mit.
                eintrag = self._karriere.zusatz_eintrag(name)
                anzeigename = eintrag.get("name", name)
                waehrung = "".join(eintrag.get("waehrung", ("E",)))
            platz = self._karriere.platz_fuer(name) if vorschau.braucht_tag else "sofort"
            if name in gesperrt:
                platz = "gesperrt"

            kosten = []
            if vorschau.geld:
                kosten.append(euro(vorschau.geld))
            if vorschau.erfahrung:
                topf = f" ({vorschau.wettertopf})" if vorschau.wettertopf else ""
                kosten.append(f"{vorschau.erfahrung} EP{topf}")

            zeile = QTreeWidgetItem(
                self._liste,
                [
                    name,
                    anzeigename,
                    f"{self._karriere.wert(name):,}".replace(",", "."),
                    waehrung,
                    f"+{vorschau.zuwachs}",
                    " + ".join(kosten) if kosten else "kostenlos",
                    platz,
                ],
            )
            zeile.setData(0, Qt.UserRole, name)
            if name in gesperrt:
                # Ein gesperrter Eintrag ist durchgestrichen und rot - sonst
                # merkt man die Sperre erst am Fehler beim Klicken.
                schrift = zeile.font(1)
                schrift.setStrikeOut(True)
                for spalte in range(self._liste.columnCount()):
                    zeile.setFont(spalte, schrift)
                    zeile.setForeground(spalte, FARBE_RENNEN)
            elif not ist_bezahlbar(self._karriere.konto, vorschau):
                for spalte in range(self._liste.columnCount()):
                    zeile.setForeground(spalte, FARBE_REISE)
            elif vorschau.braucht_tag and platz in belegt:
                zeile.setForeground(6, FARBE_BELEGT)
            if name == gewaehlt:
                self._liste.setCurrentItem(zeile)

        for spalte in range(self._liste.columnCount()):
            self._liste.resizeColumnToContents(spalte)

    def _fuelle_konto(self) -> None:
        while self._konto.rowCount():
            self._konto.removeRow(0)
        konto = self._karriere.konto
        self._konto.addRow("Geld:", QLabel(euro(konto.geld)))
        self._konto.addRow("Erfahrung:", QLabel(f"{konto.erfahrung:,} EP".replace(",", ".")))
        for wetter in self._konfiguration.wert("wetter", "kette"):
            self._konto.addRow(
                f"EP {wetter}:", QLabel(f"{konto.wetter_topf(wetter):,} EP".replace(",", "."))
            )
        self._konto.addRow(
            "Liga:",
            QLabel(
                f"{self._karriere.liga} - "
                f"{self._konfiguration.ligenname(self._karriere.liga)}"
            ),
        )

    def _fuelle_ereignisse(self) -> None:
        """Laufende Ereignisse und offene Defekte (GDD 14)."""
        self._ereignisse.clear()
        laufend = self._karriere.lage.laufende
        reparierbar = {s: kosten for s, _, kosten in self._karriere.offene_reparaturen}

        for aktiv in laufend:
            rest = "" if aktiv.dauer in OHNE_RESTZAEHLER else str(aktiv.rest)
            if aktiv.schluessel in reparierbar:
                rest = euro(reparierbar[aktiv.schluessel])
            zeile = QTreeWidgetItem(
                self._ereignisse,
                [
                    f"{aktiv.schluessel} {aktiv.name}",
                    aktiv.beschreibung(self._konfiguration),
                    aktiv.dauer.bezeichnung,
                    rest,
                ],
            )
            if aktiv.reparierbar:
                zeile.setData(0, Qt.UserRole, aktiv.schluessel)
                zeile.setForeground(0, FARBE_RENNEN)

        for defekt in self._karriere.defekte:
            schluessel = defekt["schluessel"]
            wirkung = ", ".join(
                f"{w['ziel']} {w['faktor'] * 100:+.1f} %" for w in defekt["wirkung"]
            )
            zeile = QTreeWidgetItem(
                self._ereignisse,
                [
                    f"{schluessel} {defekt['name']}",
                    wirkung,
                    "bis zur Reparatur",
                    euro(reparierbar.get(schluessel, 0)),
                ],
            )
            zeile.setData(0, Qt.UserRole, schluessel)
            zeile.setForeground(0, FARBE_RENNEN)

        anzahl = len(laufend) + len(self._karriere.defekte)
        offen = len(reparierbar)
        titel = f"Ereignisse ({anzahl})"
        if offen:
            titel += f" - {offen} zu reparieren"
        self._ereigniskasten.setTitle(titel)
        self._reparieren.setEnabled(offen > 0)
        for spalte in range(self._ereignisse.columnCount()):
            self._ereignisse.resizeColumnToContents(spalte)
        if self._ereignisse.topLevelItemCount():
            self._ereignisse.setCurrentItem(self._ereignisse.topLevelItem(0))

    def _fuelle_sponsoren(self) -> None:
        """Nur noch der Stand; die Auswahl steht im Reiter Sponsoren."""
        bezeichnungen = self._konfiguration.wert("sponsoren", "bezeichnung")
        laufend = [
            f"{bezeichnungen.get(platz, platz)}: {vertrag.angebot.name} "
            f"({euro(vertrag.angebot.grundbetrag)} je Rennen, noch "
            f"{vertrag.verbleibende_rennen} Rennen)"
            for platz, vertrag in sorted(self._karriere.vertraege.items())
            if vertrag.laeuft
        ]
        plaetze = len(self._konfiguration.wert("sponsoren", "plaetze"))
        if laufend:
            self._sponsorenstand.setText(
                f"{len(laufend)} von {plaetze} Plaetzen belegt:\n" + "\n".join(laufend)
            )
        else:
            self._sponsorenstand.setText(
                f"Kein Platz von {plaetze} belegt - Angebote stehen im Reiter Sponsoren."
            )

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def karriere(self) -> Karriere:
        return self._karriere

    @property
    def liste(self) -> QTreeWidget:
        return self._liste

    def waehle(self, schluessel: str) -> None:
        for nummer in range(self._liste.topLevelItemCount()):
            eintrag = self._liste.topLevelItem(nummer)
            if eintrag.data(0, Qt.UserRole) == schluessel:
                self._liste.setCurrentItem(eintrag)
                return
        raise KeyError(schluessel)


    @property
    def kalenderstreifen(self) -> Kalenderstreifen:
        return self._streifen


def beginne(
    konfiguration: Konfiguration,
    welt,
    seedquelle: Seedquelle | None = None,
    jahr: int | None = None,
) -> Karriere:
    """Startet die Karriere des Spielers in seiner Liga.

    :param seedquelle: bestimmt die Ereignisse der Saison (GDD 14)
    :param jahr: Jahr der ersten Saison; ohne Angabe das Startjahr aus der
        Konfiguration (GDD 2)
    """
    eigene = welt.spielerfahrer
    spieler = eigene[0] if eigene else None
    liga = spieler.liga if spieler else konfiguration.wert("ligen", "startliga")
    # Jedes Auto gehoert seinem Fahrer; alle vier fangen bei null an, also
    # traegt der Anfangsstand fuer alle dasselbe.
    werte = dict(spieler.auto.werte) if spieler else None
    if werte is not None:
        werte.update(spieler.auto.wetterwerte)
    # Punkt 72: Das Budget des eigenen Teams zahlt sich in Monatsraten
    # aufs Konto aus. Es steht in der Welt, nicht in der Karriere.
    mannschaft = welt.spielerteam
    return kern_karriere.beginne(
        konfiguration,
        jahr if jahr is not None else kern_karriere.startjahr(konfiguration),
        liga,
        werte,
        seedquelle=seedquelle,
        fahrernummer=spieler.nummer if spieler else 0,
        fahrer=tuple(f.nummer for f in eigene) if eigene else None,
        teambudget=mannschaft.budget if mannschaft is not None else 0,
    )
