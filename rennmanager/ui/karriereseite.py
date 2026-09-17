"""Seite fuer die Karriere: Kalender, Entwicklung und Sponsoren (GDD 2, 9, 10).

Links der Tageskalender mit den beiden Plaetzen des Tages, rechts das
Konto und die Sponsorenangebote. Zeit ist eine Kapazitaet: Jeder nutzbare
Tag hat einen Platz fuer den Fahrer und einen fuer die Werkstatt; ein Tag,
der vergeht, ohne belegt zu sein, ist verloren.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFormLayout,
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

from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern import sponsoren as kern_sponsoren
from rennmanager.kern.entwicklung import EntwicklungsFehler, ist_bezahlbar
from rennmanager.kern.kalender import Tagesart
from rennmanager.kern.karriere import FAHRERPLATZ, WERKSTATTPLATZ, Karriere, KarriereFehler
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import Konfiguration

FARBE_RENNEN = QColor("#c62828")
FARBE_QUALIFYING = QColor("#eda100")
FARBE_REISE = QColor("#8b93a1")
FARBE_BELEGT = QColor("#2e7d32")


def euro(betrag: float) -> str:
    return f"{betrag:,.0f} €".replace(",", ".")


class Karriereseite(QWidget):
    """Tageskalender, Entwicklung und Sponsoren."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        karriere: Karriere,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._karriere = karriere
        self._angebote: dict[str, tuple[kern_sponsoren.Angebot, ...]] = {}

        spalte = QVBoxLayout(self)
        spalte.addLayout(self._baue_kopf())

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self._baue_entwicklung())
        teiler.addWidget(self._baue_seitenspalte())
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        spalte.addWidget(teiler, stretch=1)

        self._wuerfle_angebote()
        self._zeichne()

    # -- Aufbau ------------------------------------------------------------
    def _baue_kopf(self) -> QHBoxLayout:
        zeile = QHBoxLayout()
        self._datum = QLabel()
        schrift = self._datum.font()
        schrift.setBold(True)
        schrift.setPointSize(schrift.pointSize() + 2)
        self._datum.setFont(schrift)

        self._weiter = QPushButton("Tag weiter")
        self._weiter.clicked.connect(self._tag_weiter)
        self._springen = QPushButton("Zum naechsten Rennen")
        self._springen.clicked.connect(self._zum_rennen)

        self._hinweis = QLabel()
        zeile.addWidget(self._datum)
        zeile.addSpacing(12)
        zeile.addWidget(self._weiter)
        zeile.addWidget(self._springen)
        zeile.addSpacing(12)
        zeile.addWidget(self._hinweis)
        zeile.addStretch(1)
        return zeile

    def _baue_entwicklung(self) -> QWidget:
        kasten = QGroupBox("Faehigkeiten")
        spalte = QVBoxLayout(kasten)

        self._plaetze = QLabel()
        spalte.addWidget(self._plaetze)

        self._liste = QTreeWidget()
        self._liste.setHeaderLabels(
            ["", "Faehigkeit", "Wert", "Waehrung", "Ein Tag bringt", "Kosten", "Platz"]
        )
        self._liste.setRootIsDecorated(False)
        self._liste.setAlternatingRowColors(True)
        spalte.addWidget(self._liste)

        knoepfe = QHBoxLayout()
        self._belegen = QPushButton("Heutigen Tag belegen")
        self._belegen.clicked.connect(self._belege_tag)
        self._kaufen = QPushButton("Sofort kaufen (+10)")
        self._kaufen.clicked.connect(self._kaufe)
        knoepfe.addWidget(self._belegen)
        knoepfe.addWidget(self._kaufen)
        knoepfe.addStretch(1)
        spalte.addLayout(knoepfe)
        return kasten

    def _baue_seitenspalte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)
        spalte.setContentsMargins(0, 0, 0, 0)

        self._konto = QFormLayout()
        kontokasten = QGroupBox("Konto")
        kontokasten.setLayout(self._konto)
        spalte.addWidget(kontokasten)

        self._sponsoren = QTreeWidget()
        self._sponsoren.setHeaderLabels(
            ["Platz", "Sponsor", "Je Rennen", "Sieg", "Laufzeit", "Stand"]
        )
        self._sponsoren.setRootIsDecorated(False)
        self._sponsoren.setAlternatingRowColors(True)
        kasten = QGroupBox("Sponsoren")
        kasten_spalte = QVBoxLayout(kasten)
        kasten_spalte.addWidget(self._sponsoren)
        self._unterschreiben = QPushButton("Angebot annehmen")
        self._unterschreiben.clicked.connect(self._unterschreibe)
        kasten_spalte.addWidget(self._unterschreiben)
        spalte.addWidget(kasten, stretch=1)
        return seite

    # -- Aktionen ----------------------------------------------------------
    def _tag_weiter(self) -> None:
        try:
            self._karriere.tag_weiter()
        except KarriereFehler as fehler:
            QMessageBox.information(self, "Saisonende", str(fehler))
            return
        self._zeichne()

    def _zum_rennen(self) -> None:
        try:
            self._karriere.bis_zum_rennen()
        except KarriereFehler as fehler:
            QMessageBox.information(self, "Kein Rennen mehr", str(fehler))
            return
        self._zeichne()

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

    def _wuerfle_angebote(self) -> None:
        woche = self._karriere.heute.isocalendar().week
        self._angebote = kern_sponsoren.wuerfle_angebote(
            self._konfiguration,
            self._karriere.liga,
            woche,
            Seedquelle(self._karriere.saison.jahr),
        )

    def _unterschreibe(self) -> None:
        eintrag = self._sponsoren.currentItem()
        if eintrag is None:
            return
        angebot = eintrag.data(0, Qt.UserRole)
        if angebot is None:
            return
        self._karriere.unterschreibe(angebot)
        self._zeichne()

    # -- Anzeige -----------------------------------------------------------
    def _zeichne(self) -> None:
        tag = self._karriere.tag
        self._datum.setText(
            f"{tag.datum.strftime('%a %d.%m.%Y')} — {tag.art.bezeichnung}"
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
        self._fuelle_sponsoren()

    def _fuelle_faehigkeiten(self) -> None:
        gewaehlt = self._gewaehlt()
        self._liste.clear()
        belegt = self._karriere.belegt

        schluessel = [f.schluessel for f in self._konfiguration.faehigkeiten]
        schluessel += list(self._konfiguration.zusatzfaehigkeiten)
        for name in schluessel:
            try:
                vorschau = self._karriere.vorschau(name)
            except EntwicklungsFehler:
                continue

            faehigkeit = self._konfiguration.faehigkeit(name) if name in [
                f.schluessel for f in self._konfiguration.faehigkeiten
            ] else None
            anzeigename = faehigkeit.name if faehigkeit else name
            waehrung = (
                "".join(faehigkeit.waehrung)
                if faehigkeit
                else "".join(self._karriere._zusatz_eintrag(name).get("waehrung", ("E",)))
            )
            platz = self._karriere.platz_fuer(name) if vorschau.braucht_tag else "sofort"

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
            if not ist_bezahlbar(self._karriere.konto, vorschau):
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

    def _fuelle_sponsoren(self) -> None:
        self._sponsoren.clear()
        for platz, liste in self._angebote.items():
            vertrag = self._karriere.vertraege.get(platz)
            for angebot in liste:
                stand = ""
                if vertrag is not None and vertrag.angebot.name == angebot.name:
                    stand = f"laeuft, {vertrag.verbleibende_rennen} Rennen"
                elif vertrag is not None:
                    stand = "Platz belegt"
                zeile = QTreeWidgetItem(
                    self._sponsoren,
                    [
                        platz,
                        angebot.name,
                        euro(angebot.grundbetrag),
                        euro(angebot.praemie_sieg),
                        f"{angebot.laufzeit_rennen} Rennen",
                        stand,
                    ],
                )
                zeile.setData(0, Qt.UserRole, angebot)
                if stand.startswith("laeuft"):
                    zeile.setForeground(5, FARBE_BELEGT)
        for spalte in range(self._sponsoren.columnCount()):
            self._sponsoren.resizeColumnToContents(spalte)

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


def beginne(konfiguration: Konfiguration, welt) -> Karriere:
    """Startet die Karriere des Spielers in seiner Liga."""
    spieler = welt.spieler
    liga = spieler.liga if spieler else konfiguration.wert("ligen", "startliga")
    werte = dict(spieler.auto.werte) if spieler else None
    if werte is not None:
        werte.update(spieler.auto.wetterwerte)
    return kern_karriere.beginne(konfiguration, 2026, liga, werte)
