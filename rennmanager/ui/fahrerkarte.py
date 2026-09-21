"""Die persoenliche Karte eines Fahrers.

Ein Doppelklick auf einen Namen - in jeder Liste des Spiels - oeffnet
dieses Fenster. Es sammelt an einer Stelle, was ueber einen Fahrer sonst
auf fuenf Seiten verstreut steht.

**Die Karte rechnet nichts.** Sie liest nur, was Welt, Auto, Statistik,
Streckenkenntnis und Popularitaet ohnehin fuehren, und ist rein lesend:
Werte aendern geht weiter nur ueber den Editor. Fuer alle 600 Fahrer
zeigt sie dasselbe; Konto, Sponsoren und Werkstatt des Spielers bleiben
auf ihren eigenen Seiten, sonst gaebe es sie zweimal.

Fuenf Reiter:

===========  =============================================================
Steckbrief   Person, Team, Charakter, Stand in der Liga, Popularitaet
Werte        die 11 Wirkungsbereiche als Balken, dann alle Einzelwerte
Saison       die Zeile der laufenden Saison und der Punkteverlauf
Laufbahn     Karrierezahlen, Titel, Liga je Jahr, gehaltene Rundenrekorde
Strecken     Streckenkenntnis je Strecke, Heimstrecken hervorgehoben
===========  =============================================================

Die Balken messen gegen den **eigenen** Hoechstwert, nicht gegen die
Skala: Ein Fahrer aus Liga 20 steht bei 150 von 100.000 - gegen die Skala
waere jeder seiner Balken unsichtbar, und zu sehen ist hier ohnehin die
Form seines Profils, nicht sein Platz auf der Skala. Die Zahl steht
daneben.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rennmanager.kern import charakter as kern_charakter
from rennmanager.kern import heimstrecke as kern_heimstrecke
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import karriere as kern_karriere
from rennmanager.kern.auto import bereichswerte, gesamtwert
from rennmanager.kern.zeit import formatiere_dauer
from rennmanager.konfiguration import Konfiguration
from rennmanager.ui.laufbahnansicht import Laufbahnansicht
from rennmanager.ui.punkteansicht import Punkteansicht
from rennmanager.ui.tabellen import Balkenzeichner, SortierbareZeile, schriftfarbe

# Der Balken der Wirkungsbereiche soll die Form zeigen, nicht warnen -
# deshalb liegen beide Schwellen unter jedem vorkommenden Anteil.
NIE_WARNEN = {"warnung": -1.0, "kritisch": -2.0}


def _zahl(wert: float) -> str:
    """Ganze Zahl mit Punkt als Tausendertrennung, wie im ganzen Spiel."""
    return f"{round(wert):,}".replace(",", ".")


def _prozent(anteil: float) -> str:
    return f"{anteil * 100:.2f} %".replace(".", ",")


def _bilanzfelder(bilanz) -> list[str]:
    """Die neun Spalten einer Bilanz als Text (Punkte 21 und 23).

    Ohne Bilanz - also vor dem ersten Rennen dort - bleiben sie leer statt
    auf 0 zu stehen: "noch nie gefahren" ist etwas anderes als "null Siege".
    """
    if bilanz is None or not bilanz.rennen:
        return [""] * 9
    return [
        str(bilanz.rennen),
        str(bilanz.siege),
        str(bilanz.podien),
        str(bilanz.poles),
        str(bilanz.schnellste_runden),
        str(bilanz.ausfaelle),
        _zahl(bilanz.punkte),
        str(bilanz.bester_platz) if bilanz.bester_platz else "-",
        str(bilanz.beste_liga) if bilanz.beste_liga else "-",
    ]


def _setze_bilanzsortierung(zeile, bilanz, ab: int) -> None:
    """Sortiert die Bilanzspalten nach Zahlen, nicht nach Text."""
    if bilanz is None:
        werte = [0] * 9
    else:
        werte = [
            bilanz.rennen,
            bilanz.siege,
            bilanz.podien,
            bilanz.poles,
            bilanz.schnellste_runden,
            bilanz.ausfaelle,
            bilanz.punkte,
            # Platz 1 ist der beste: ohne Vorzeichenwechsel stuende der
            # Sieger beim Sortieren ganz unten. Wer nie ankam, auch.
            -bilanz.bester_platz if bilanz.bester_platz else -99,
            -bilanz.beste_liga if bilanz.beste_liga else -99,
        ]
    for versatz, wert in enumerate(werte):
        zeile.setze_sortierwert(ab + versatz, wert)


class Fahrerkarte(QDialog):
    """Alles ueber einen Fahrer in einem Fenster."""

    def __init__(
        self,
        konfiguration: Konfiguration,
        welt,
        nummer: int,
        statistik=None,
        kenntnis=None,
        tabelle=None,
        strecken=(),
        popularitaet=None,
        jahr: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._konfiguration = konfiguration
        self._welt = welt
        self._fahrer = welt.fahrer[nummer]
        self._team = welt.team_von(self._fahrer)
        self._statistik = statistik
        self._kenntnis = kenntnis
        self._tabelle = tabelle
        self._strecken = tuple(strecken)
        self._popularitaet = popularitaet
        self._jahr = jahr

        self.setWindowTitle(f"{self._fahrer.name} - Fahrerkarte")
        # Nicht modal: Man soll zwei Fahrer nebeneinanderlegen koennen und
        # die Karte auch waehrend eines laufenden Rennens offen halten.
        self.setModal(False)
        self.resize(760, 640)

        spalte = QVBoxLayout(self)
        spalte.addWidget(self._baue_kopf())
        self._blaetter = QTabWidget()
        self._blaetter.addTab(self._baue_steckbrief(), "Steckbrief")
        self._blaetter.addTab(self._baue_werte(), "Werte")
        self._blaetter.addTab(self._baue_saison(), "Saison")
        self._blaetter.addTab(self._baue_laufbahn(), "Laufbahn")
        self._blaetter.addTab(self._baue_strecken(), "Strecken")
        self._blaetter.addTab(self._baue_wetter(), "Wetter")
        spalte.addWidget(self._blaetter, stretch=1)

    # -- Kopf --------------------------------------------------------------
    def _baue_kopf(self) -> QWidget:
        zeile = QWidget()
        kasten = QHBoxLayout(zeile)
        kasten.setContentsMargins(0, 0, 0, 0)

        name = QLabel(f"<b>{self._fahrer.name}</b>")
        schrift = name.font()
        schrift.setPointSize(schrift.pointSize() + 4)
        name.setFont(schrift)

        # Der Farbfleck traegt die Teamfarbe (GDD 12) - dieselbe, die im
        # Rennen an seinem Punkt haengt.
        fleck = QLabel(" ")
        fleck.setFixedWidth(14)
        fleck.setStyleSheet(f"background-color: {self._team.farbe};")

        kasten.addWidget(fleck)
        kasten.addWidget(name)
        kasten.addWidget(
            QLabel(
                f"#{self._fahrer.nummer} · {self._fahrer.kuerzel} · "
                f"Liga {self._fahrer.liga} "
                f"({self._konfiguration.ligenname(self._fahrer.liga)}) · "
                f"{self._team.name}"
            )
        )
        kasten.addStretch(1)
        return zeile

    # -- Steckbrief --------------------------------------------------------
    def _baue_steckbrief(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        person = QFormLayout()
        kasten = QGroupBox("Person")
        kasten.setLayout(person)
        kollegen = ", ".join(f.name for f in self._welt.teamkollegen(self._fahrer))
        for beschriftung, wert in (
            ("Land:", self._fahrer.land),
            ("Geboren:", self._fahrer.geburtstag.strftime("%d.%m.%Y")),
            ("Alter:", f"{self._alter()} Jahre"),
            ("Team:", f"{self._team.name} ({self._team.land})"),
            ("Hersteller:", self._team.hersteller),
            ("Teamkollegen:", kollegen),
        ):
            marke = QLabel(wert)
            marke.setWordWrap(True)
            person.addRow(beschriftung, marke)
        spalte.addWidget(kasten)

        stand = QFormLayout()
        standkasten = QGroupBox("Stand")
        standkasten.setLayout(stand)
        platz, feld = self._platz_in_der_liga()
        stand.addRow("Staerke:", QLabel(_zahl(gesamtwert(self._konfiguration, self._fahrer.auto))))
        stand.addRow("Platz nach Staerke:", QLabel(f"{platz} von {feld} in seiner Liga"))
        if self._popularitaet is not None:
            beliebt = self._popularitaet.stand(self._fahrer.nummer)
            faktor = f"{self._popularitaet.faktor(self._fahrer.nummer):.2f}".replace(
                ".", ","
            )
            stand.addRow(
                "Popularitaet:",
                QLabel(f"{_zahl(beliebt)} · Sponsorenfaktor {faktor}"),
            )
        spalte.addWidget(standkasten)

        charakterkasten = QGroupBox("Charakter")
        charakterspalte = QVBoxLayout(charakterkasten)
        satz = QLabel(kern_charakter.profil(self._konfiguration, self._fahrer.auto))
        satz.setWordWrap(True)
        charakterspalte.addWidget(satz)

        einzeln = QFormLayout()
        for beschriftung, teile in (
            ("Stark in:", kern_charakter.staerken(self._konfiguration, self._fahrer.auto)),
            ("Schwach in:", kern_charakter.schwaechen(self._konfiguration, self._fahrer.auto)),
            ("Daneben:", kern_charakter.besondere(self._konfiguration, self._fahrer.auto)),
        ):
            einzeln.addRow(beschriftung, QLabel(", ".join(teile) if teile else "-"))
        charakterspalte.addLayout(einzeln)
        spalte.addWidget(charakterkasten)

        spalte.addStretch(1)
        return seite

    def _alter(self) -> int:
        """Alter am Stichtag der Saison - dieselbe Rechnung wie die Weltseite."""
        jahr = (
            self._jahr
            if self._jahr is not None
            else kern_karriere.startjahr(self._konfiguration)
        )
        return self._fahrer.alter_am(
            kern_kalender.saisonstart(self._konfiguration, jahr)
        )

    def _platz_in_der_liga(self) -> tuple[int, int]:
        feld = self._welt.liga(self._fahrer.liga)
        nummern = [f.nummer for f in feld]
        return nummern.index(self._fahrer.nummer) + 1, len(feld)

    # -- Werte -------------------------------------------------------------
    def _baue_werte(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        self._werte = QTreeWidget()
        self._werte.setHeaderLabels(["Eigenschaft", "Wert", "Anteil"])
        self._werte.setRootIsDecorated(True)
        self._werte.setAlternatingRowColors(True)
        self._werte.setItemDelegateForColumn(
            2, Balkenzeichner(self._werte, **NIE_WARNEN)
        )

        auto = self._fahrer.auto
        bezeichnung = self._konfiguration.wert("wirkungsmatrix", "bezeichnung")
        bereiche = bereichswerte(self._konfiguration, auto)
        self._fuelle_zweig(
            "Wirkungsbereiche (GDD 8)",
            [(bezeichnung.get(b, b), wert) for b, wert in bereiche.items()],
        )

        fahrzeug = []
        fahrer = []
        for faehigkeit in self._konfiguration.faehigkeiten:
            ziel = fahrzeug if faehigkeit.ist_fahrzeug else fahrer
            ziel.append(
                (f"{faehigkeit.schluessel} {faehigkeit.name}", auto.wert(faehigkeit.schluessel))
            )
        self._fuelle_zweig("Fahrzeug (GDD 5)", fahrzeug)
        self._fuelle_zweig("Fahrer (GDD 6)", fahrer)

        daneben = [
            (eintrag.get("name", eintrag["schluessel"]), auto.wetterwert(eintrag["schluessel"]))
            for eintrag in self._konfiguration.zusatzeintraege
        ]
        self._fuelle_zweig("Neben der Matrix (GDD 7)", daneben)

        self._werte.expandAll()
        for stelle in range(2):
            self._werte.resizeColumnToContents(stelle)
        self._werte.setColumnWidth(2, 140)
        spalte.addWidget(self._werte)
        return seite

    def _fuelle_zweig(self, name: str, eintraege) -> None:
        """Ein Ast mit Balken, die gegen den groessten Wert des Astes messen.

        Gegen die Skala (0 bis 100.000) waere jeder Balken eines
        Liga-20-Fahrers unsichtbar. Zu sehen ist hier die Form des
        Profils, nicht der Platz auf der Skala.
        """
        ast = QTreeWidgetItem(self._werte, [name, "", ""])
        schrift = ast.font(0)
        schrift.setBold(True)
        ast.setFont(0, schrift)
        groesster = max((wert for _, wert in eintraege), default=0)
        for beschriftung, wert in eintraege:
            zeile = SortierbareZeile(ast, [beschriftung, _zahl(wert), ""])
            zeile.setze_sortierwert(1, wert)
            anteil = wert / groesster if groesster else 0.0
            zeile.setData(2, Balkenzeichner.ANTEILSROLLE, anteil)
            zeile.setze_sortierwert(2, anteil)

    # -- Saison ------------------------------------------------------------
    def _baue_saison(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        jahr = f" {self._jahr}" if self._jahr is not None else ""
        kasten = QGroupBox(f"Laufende Saison{jahr}")
        felder = QFormLayout(kasten)
        eintrag = (
            self._tabelle.eintraege.get(self._fahrer.nummer)
            if self._tabelle is not None
            else None
        )
        if eintrag is None or not eintrag.rennen:
            felder.addRow(QLabel("In dieser Saison noch kein Rennen gefahren."))
        else:
            felder.addRow(
                "Platz:",
                QLabel(
                    f"{self._tabelle.platz_von(self._fahrer.nummer)} von "
                    f"{len(self._tabelle.eintraege)}"
                ),
            )
            for beschriftung, wert in (
                ("Punkte:", eintrag.punkte),
                ("Rennen:", eintrag.rennen),
                ("Siege:", eintrag.siege),
                ("Podien:", eintrag.podien),
                ("Poles:", eintrag.poles),
                ("Schnellste Runden:", eintrag.schnellste_runden),
                ("Ausfaelle:", eintrag.ausfaelle),
            ):
                felder.addRow(beschriftung, QLabel(str(wert)))
        spalte.addWidget(kasten)

        verlaufkasten = QGroupBox("Punkteverlauf der Liga")
        verlaufspalte = QVBoxLayout(verlaufkasten)
        self._verlauf = Punkteansicht(
            "Punktestand je Rennwochenende - grau die Liga, farbig dieser Fahrer"
        )
        verlaufspalte.addWidget(self._verlauf)
        spalte.addWidget(verlaufkasten, stretch=1)
        self._fuelle_verlauf()
        return seite

    def _fuelle_verlauf(self) -> None:
        """Die Liga als graues Feld, dieser Fahrer als einzige Linie."""
        if self._statistik is None:
            return
        liga = self._fahrer.liga
        reihen = []
        eigene = 0
        for stelle, mitfahrer in enumerate(self._welt.liga(liga)):
            reihen.append(
                (
                    mitfahrer.kuerzel,
                    self._welt.team_von(mitfahrer).farbe,
                    self._statistik.punktestand(mitfahrer.nummer),
                )
            )
            if mitfahrer.nummer == self._fahrer.nummer:
                eigene = stelle
        self._verlauf.zeige(reihen)
        self._verlauf.hebe_hervor([eigene])

    # -- Laufbahn ----------------------------------------------------------
    def _baue_laufbahn(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        zahlen = (
            self._statistik.zahlen(self._fahrer.nummer)
            if self._statistik is not None
            else None
        )
        kasten = QGroupBox("Ueber alle Saisons")
        felder = QFormLayout(kasten)
        if zahlen is None or not zahlen.rennen:
            felder.addRow(QLabel("Noch kein Rennen gefahren."))
        else:
            for beschriftung, wert in (
                ("Rennen:", str(zahlen.rennen)),
                ("Siege:", f"{zahlen.siege} ({zahlen.siegquote:.1%})".replace(".", ",")),
                ("Podien:", str(zahlen.podien)),
                ("Poles:", str(zahlen.poles)),
                ("Schnellste Runden:", str(zahlen.schnellste_runden)),
                ("Ausfaelle:", str(zahlen.ausfaelle)),
                ("Punkte:", _zahl(zahlen.punkte)),
            ):
                felder.addRow(beschriftung, QLabel(wert))
            titel = self._statistik.titel_von(self._fahrer.nummer)
            felder.addRow(
                "Meisterschaften:",
                QLabel(
                    ", ".join(f"{a.saison} (Liga {a.liga})" for a in titel)
                    if titel
                    else "-"
                ),
            )
        spalte.addWidget(kasten)

        bahnkasten = QGroupBox("Liga je Saison")
        bahnspalte = QVBoxLayout(bahnkasten)
        self._bahn = Laufbahnansicht(self._konfiguration.wert("ligen", "anzahl"))
        if self._statistik is not None:
            self._bahn.zeige(
                self._statistik.laufbahn(self._fahrer.nummer), self._team.farbe
            )
        bahnspalte.addWidget(self._bahn)
        spalte.addWidget(bahnkasten, stretch=1)

        rekordkasten = QGroupBox("Gehaltene Rundenrekorde")
        rekordspalte = QVBoxLayout(rekordkasten)
        self._rekorde = QTreeWidget()
        self._rekorde.setHeaderLabels(["Strecke", "Liga", "Zeit", "Saison", "Rennen"])
        self._rekorde.setRootIsDecorated(False)
        self._rekorde.setAlternatingRowColors(True)
        self._fuelle_rekorde()
        rekordspalte.addWidget(self._rekorde)
        spalte.addWidget(rekordkasten, stretch=1)
        return seite

    def _fuelle_rekorde(self) -> None:
        if self._statistik is None:
            return
        eigene = [
            rekord
            for rekord in self._statistik.rekorde.values()
            if rekord.fahrer == self._fahrer.nummer
        ]
        for rekord in sorted(eigene, key=lambda r: (r.strecke, r.liga)):
            zeile = SortierbareZeile(
                self._rekorde,
                [
                    rekord.strecke,
                    str(rekord.liga),
                    formatiere_dauer(rekord.zeit_ms),
                    str(rekord.saison),
                    str(rekord.rennen),
                ],
            )
            zeile.setze_sortierwert(2, rekord.zeit_ms)
        for stelle in range(self._rekorde.columnCount()):
            self._rekorde.resizeColumnToContents(stelle)

    # -- Strecken ----------------------------------------------------------
    def _baue_strecken(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        heim = [
            strecke
            for strecke in self._strecken
            if kern_heimstrecke.ist_heimstrecke(self._fahrer.land, strecke)
        ]
        # Nur 20 Strecken in 15 Laendern: Die meisten Fahrer haben gar
        # keine Heimstrecke, und dann waere der Hinweis eine Luege.
        nachsatz = (
            "Heimstrecken sind hervorgehoben (Punkt 49): "
            + ", ".join(s.name for s in heim)
            + "."
            if heim
            # Nicht "In Schweiz": Manche Laender brauchen einen Artikel,
            # manche nicht. So stimmt der Satz fuer alle 32.
            else f"Keine der {len(self._strecken)} Strecken liegt in seinem "
            f"Land ({self._fahrer.land}) - keine Heimstrecke (Punkt 49)."
        )
        hinweis = QLabel(
            "Streckenkenntnis nach GDD 6: Wer eine Strecke kennt, faehrt sie "
            f"schneller. {nachsatz}"
        )
        hinweis.setWordWrap(True)
        spalte.addWidget(hinweis)

        self._streckenliste = QTreeWidget()
        # Punkt 21: Was er dort erreicht hat, steht neben dem, was er dort
        # kann - Kenntnis und Bilanz gehoeren zur selben Strecke.
        self._streckenliste.setHeaderLabels(
            [
                "Strecke",
                "Land",
                "Runden",
                "Tempogewinn",
                "Kenntnis",
                "Starts",
                "Siege",
                "Podien",
                "Poles",
                "SR",
                "DNF",
                "Punkte",
                "Bester",
                "Beste Liga",
            ]
        )
        self._streckenliste.setRootIsDecorated(False)
        self._streckenliste.setAlternatingRowColors(True)
        self._streckenliste.setItemDelegateForColumn(
            4, Balkenzeichner(self._streckenliste, **NIE_WARNEN)
        )
        self._fuelle_strecken()
        spalte.addWidget(self._streckenliste)
        return seite

    def _fuelle_strecken(self) -> None:
        if self._kenntnis is None or not self._strecken:
            return
        bilanzen = (
            self._statistik.strecken_von(self._fahrer.nummer)
            if self._statistik is not None
            else {}
        )
        voll = self._konfiguration.wert("streckenkenntnis", "volle_kenntnis_runden")
        for strecke in self._strecken:
            runden = self._kenntnis.stand(self._fahrer.nummer, strecke.name)
            bonus = self._kenntnis.bonus(self._fahrer.nummer, strecke.name)
            bilanz = bilanzen.get(strecke.name)
            zeile = SortierbareZeile(
                self._streckenliste,
                [
                    strecke.name,
                    strecke.land,
                    f"{runden:.1f}".replace(".", ","),
                    _prozent(bonus),
                    "",
                    *_bilanzfelder(bilanz),
                ],
            )
            zeile.setze_sortierwert(2, runden)
            zeile.setze_sortierwert(3, bonus)
            _setze_bilanzsortierung(zeile, bilanz, ab=5)
            anteil = min(runden / voll, 1.0) if voll else 0.0
            zeile.setData(4, Balkenzeichner.ANTEILSROLLE, anteil)
            zeile.setze_sortierwert(4, anteil)
            if kern_heimstrecke.ist_heimstrecke(self._fahrer.land, strecke):
                schrift = zeile.font(0)
                schrift.setBold(True)
                zeile.setFont(0, schrift)
                zeile.setForeground(0, schriftfarbe(self._team.farbe))
        for stelle in range(self._streckenliste.columnCount()):
            if stelle != 4:
                self._streckenliste.resizeColumnToContents(stelle)
        self._streckenliste.setColumnWidth(4, 120)

    # -- Wetter ------------------------------------------------------------
    def _baue_wetter(self) -> QWidget:
        seite = QWidget()
        spalte = QVBoxLayout(seite)

        hinweis = QLabel(
            "Wetterbilanz nach Punkt 23: Gezaehlt wird je Rennen die Lage, "
            "unter der am meisten gefahren wurde - nicht jeder Wechsel. Ein "
            "Rennen, das zwei Runden im Regen beginnt und danach trocken "
            "bleibt, war ein trockenes."
        )
        hinweis.setWordWrap(True)
        spalte.addWidget(hinweis)

        self._wetterliste = QTreeWidget()
        self._wetterliste.setHeaderLabels(
            [
                "Wetterlage",
                "Koennen",
                "Starts",
                "Siege",
                "Podien",
                "Poles",
                "SR",
                "DNF",
                "Punkte",
                "Bester",
                "Beste Liga",
            ]
        )
        self._wetterliste.setRootIsDecorated(False)
        self._wetterliste.setAlternatingRowColors(True)
        self._fuelle_wetter()
        spalte.addWidget(self._wetterliste)
        return seite

    def _fuelle_wetter(self) -> None:
        """Je Lage der Wirkungswert daneben - Koennen und Bilanz zusammen."""
        bilanzen = (
            self._statistik.wetterlagen_von(self._fahrer.nummer)
            if self._statistik is not None
            else {}
        )
        # Zu jeder Lage aus GDD 7 gehoert eine Faehigkeit daneben
        # (Trockenroutine, Regenfahren, ...). Beide nebeneinander zeigen,
        # ob das Koennen zum Ergebnis passt.
        koennen = {
            eintrag["wetter"]: eintrag
            for eintrag in self._konfiguration.zusatzeintraege
            if eintrag.get("wetter")
        }
        for lage in self._konfiguration.wert("wetter", "kette"):
            bilanz = bilanzen.get(lage)
            eintrag = koennen.get(lage)
            wert = (
                f"{eintrag['name']} {_zahl(self._fahrer.auto.wetterwert(eintrag['schluessel']))}"
                if eintrag
                else "-"
            )
            zeile = SortierbareZeile(
                self._wetterliste, [lage, wert, *_bilanzfelder(bilanz)]
            )
            if eintrag:
                zeile.setze_sortierwert(
                    1, self._fahrer.auto.wetterwert(eintrag["schluessel"])
                )
            _setze_bilanzsortierung(zeile, bilanz, ab=2)
        for stelle in range(self._wetterliste.columnCount()):
            self._wetterliste.resizeColumnToContents(stelle)

    # -- Zugriff fuer Tests -------------------------------------------------
    @property
    def fahrer(self):
        return self._fahrer

    @property
    def blaetter(self) -> QTabWidget:
        return self._blaetter

    @property
    def werteliste(self) -> QTreeWidget:
        return self._werte

    @property
    def streckenliste(self) -> QTreeWidget:
        return self._streckenliste

    @property
    def wetterliste(self) -> QTreeWidget:
        return self._wetterliste

    @property
    def rekordliste(self) -> QTreeWidget:
        return self._rekorde

    @property
    def punkteverlauf(self) -> Punkteansicht:
        return self._verlauf

    @property
    def laufbahn(self) -> Laufbahnansicht:
        return self._bahn
