"""Karrierestand: Kalender, Konto, Werte und Vertraege (GDD 2, 9 und 10).

Fasst zusammen, was der Spieler zwischen zwei Rennen tut: Tage
weiterschalten, Trainings- und Werkstattplaetze belegen, Upgrades kaufen
und Sponsorenvertraege abschliessen.

Zeit ist dabei eine Kapazitaet (GDD 2): Jeder nutzbare Tag hat zwei
Plaetze, einen fuer den Fahrer und einen fuer die Werkstatt. Ein Tag, der
vorbei ist, ohne belegt zu sein, ist verloren.

Seit Schritt 10 haengen drei weitere Zustaende an der Karriere:

* die **Ereignisse** aus GDD 14, die beim Tageswechsel ausgeloest werden
  und Werte zeitweise oder dauerhaft veraendern,
* die **offenen Defekte** aus GDD 14, die nach dem Rennen bestehen
  bleiben, bis der Spieler sie bezahlt,
* die **Streckenkenntnis** aus GDD 6, die mit jeder gefahrenen Runde
  waechst.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from rennmanager.kern import einnahmen as kern_einnahmen
from rennmanager.kern import entwicklung as kern_entwicklung
from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import sponsoren as kern_sponsoren
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.entwicklung import Konto
from rennmanager.kern.kalender import Saison, Tagesart
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

FAHRERPLATZ = "fahrer"
WERKSTATTPLATZ = "werkstatt"


class KarriereFehler(Exception):
    """Die Aktion ist an diesem Tag oder mit diesem Vorrat nicht moeglich."""


@dataclass(frozen=True)
class Meldung:
    """Was an einem Tag passiert ist - fuer die Anzeige (GDD 14)."""

    datum: dt.date
    schluessel: str
    name: str
    text: str
    geld: int = 0
    erfahrung: int = 0

    @property
    def zeile(self) -> str:
        teile = [f"{self.schluessel} {self.name}", self.text]
        if self.geld:
            teile.append(f"{self.geld:+,} EUR".replace(",", "."))
        if self.erfahrung:
            teile.append(f"{self.erfahrung:+,} EP".replace(",", "."))
        return " - ".join(teil for teil in teile if teil)


@dataclass(frozen=True)
class Tagesbuchung:
    """Was an einem Tag auf welchem Platz gearbeitet wurde."""

    datum: dt.date
    platz: str
    faehigkeit: str
    von: int
    nach: int
    geld: int
    erfahrung: int


@dataclass
class Karriere:
    """Der Stand einer Karriere.

    :param werte: Wert je Faehigkeit; enthaelt die 32 aus der
        Wirkungsmatrix und die Zusatzfaehigkeiten aus GDD 7 und dem
        Reifenfluesterer
    """

    konfiguration: Konfiguration
    saison: Saison
    heute: dt.date
    liga: int
    konto: Konto
    werte: dict[str, int]
    vertraege: dict[str, kern_sponsoren.Vertrag] = field(default_factory=dict)
    buchungen: list[Tagesbuchung] = field(default_factory=list)
    # Belegte Plaetze des laufenden Tages.
    belegt: set[str] = field(default_factory=set)

    # -- Schritt 10 --------------------------------------------------------
    # Die Ereignisse der Saison, einmal beim Start gewuerfelt (GDD 14).
    ereignisplan: dict[dt.date, tuple[str, ...]] = field(default_factory=dict)
    lage: kern_ereignis.Lage | None = None
    # Defekte, die aus einem Rennen offen geblieben sind (GDD 14).
    defekte: list[dict] = field(default_factory=list)
    # Tage, die E29 Reisechaos gekostet hat.
    verlorene_tage: set[dt.date] = field(default_factory=set)
    meldungen: list[Meldung] = field(default_factory=list)
    kenntnis: kern_streckenkenntnis.Streckenkenntnis | None = None
    # Nummer des Fahrers in der Welt - fuer die Streckenkenntnis.
    fahrernummer: int = 0

    def __post_init__(self) -> None:
        if self.lage is None:
            self.lage = kern_ereignis.Lage(self.konfiguration)
        if self.kenntnis is None:
            self.kenntnis = kern_streckenkenntnis.Streckenkenntnis(self.konfiguration)

    # -- Kalender ----------------------------------------------------------
    @property
    def tag(self) -> kern_kalender.Kalendertag:
        return self.saison.tag(self.heute)

    @property
    def naechstes_rennen(self) -> dt.date | None:
        return self.saison.naechster_renntag(self.heute)

    @property
    def tage_bis_zum_rennen(self) -> int | None:
        ziel = self.naechstes_rennen
        return (ziel - self.heute).days if ziel else None

    @property
    def offene_tage(self) -> int:
        """Nutzbare Tage bis zum naechsten Rennen, heute eingeschlossen.

        Tage, die E29 Reisechaos gekostet hat, zaehlen nicht mit (GDD 14).
        """
        ziel = self.naechstes_rennen
        if ziel is None:
            ziel = self.saison.tage[-1].datum
        return len(
            [
                tag
                for tag in self.saison.nutzbare_tage(self.heute, ziel)
                if tag.datum not in self.verlorene_tage
            ]
        )

    @property
    def heute_nutzbar(self) -> bool:
        """Ob heute gearbeitet werden kann (GDD 2 und 14)."""
        return self.tag.ist_nutzbar and self.heute not in self.verlorene_tage

    def tag_weiter(self) -> kern_kalender.Kalendertag:
        """Schaltet einen Tag weiter und loest Ereignisse aus (GDD 2 und 14)."""
        naechster = self.heute + dt.timedelta(days=1)
        if naechster > self.saison.tage[-1].datum:
            raise KarriereFehler("Die Saison ist zu Ende")

        vorher = kern_ereignis.zyklusnummer(self.konfiguration, self.saison, self.heute)
        self.heute = naechster
        self.belegt.clear()
        if kern_ereignis.zyklusnummer(self.konfiguration, self.saison, naechster) != vorher:
            self.lage.nach_zyklus()

        for schluessel in self.ereignisplan.get(naechster, ()):
            self._loese_ereignis_aus(schluessel)
        return self.tag

    # -- Ereignisse (GDD 14) -----------------------------------------------
    def _loese_ereignis_aus(self, schluessel: str) -> Meldung:
        """Startet ein Ereignis und verbucht, was sofort wirkt."""
        e = kern_ereignis.eintrag(self.konfiguration, schluessel)
        aktiv = self.lage.loese_aus(schluessel, self.heute)

        geld = 0
        erfahrung = 0
        for wirkung in e["wirkung"]:
            ziel = wirkung["ziel"]
            if wirkung.get("einmalig"):
                anteil = kern_ereignis.betrag(self.konfiguration, schluessel)
                if ziel == kern_ereignis.GELD:
                    geld += int(
                        round(anteil * kern_einnahmen.siegpraemie(self.konfiguration, self.liga))
                    )
                else:
                    erfahrung += int(
                        round(
                            anteil * kern_einnahmen.sieg_erfahrung(self.konfiguration, self.liga)
                        )
                    )
            elif ziel == kern_ereignis.KALENDERTAGE:
                self._verliere_tage(-int(wirkung["absolut"]))
            elif kern_ereignis.ist_dauerhaft(e, wirkung) and ziel in self.werte:
                kleinster = self.konfiguration.wert("skala", "minimum")
                groesster = self.konfiguration.wert("skala", "maximum")
                neu_wert = self.werte[ziel] + kern_ereignis.dauerhafter_zuwachs(
                    self.konfiguration, self.werte[ziel], wirkung["faktor"]
                )
                self.werte[ziel] = min(max(neu_wert, kleinster), groesster)

        if geld or erfahrung:
            self.konto = self.konto.mit(geld=geld, erfahrung=erfahrung)

        meldung = Meldung(
            datum=self.heute,
            schluessel=schluessel,
            name=aktiv.name,
            text=aktiv.beschreibung(self.konfiguration),
            geld=geld,
            erfahrung=erfahrung,
        )
        self.meldungen.append(meldung)
        return meldung

    def _verliere_tage(self, anzahl: int) -> None:
        """Nimmt die naechsten nutzbaren Tage weg (E29 Reisechaos).

        Entschieden: Es trifft die naechsten nutzbaren Tage, nicht die vor
        dem Rennen - gemeint ist die Kapazitaet aus GDD 2.
        """
        offen = [
            tag.datum
            for tag in self.saison.tage
            if tag.datum >= self.heute
            and tag.ist_nutzbar
            and tag.datum not in self.verlorene_tage
        ]
        self.verlorene_tage.update(offen[:anzahl])

    def faktoren(self, session: str = kern_ereignis.RENNEN) -> dict[str, float]:
        """Alle Faktoren, die gerade auf Werte wirken (GDD 14).

        Ereignisse und offene Defekte zusammen; beide sind Faktoren auf
        einzelne Faehigkeiten.
        """
        faktoren = dict(self.lage.faktoren(session))
        for ziel, faktor in kern_zwischenfall.wertfaktoren(
            self.konfiguration, self.defekte
        ).items():
            faktoren[ziel] = faktoren.get(ziel, 1.0) * faktor
        return faktoren

    def rennauto(self, vorlage, session: str = kern_ereignis.RENNEN):
        """Das Auto des Spielers, wie es in dieser Session faehrt.

        GDD 1 laesst den Spieler bei 0 anfangen und sich entwickeln; GDD 14
        laesst Ereignisse und Defekte an den Werten ziehen. Beides steht in
        der Karriere, nicht in der Welt - dieses Auto bringt es ins Rennen.

        :param vorlage: das Auto aus der Welt. Kuerzel und Name kommen von
            dort: Die Seitenleiste im Rennen zeigt sie (GDD 4), die
            Karriere kennt sie nicht.
        """
        from rennmanager.kern.auto import Auto

        werte = self.fahrwerte(session)
        matrix = {f.schluessel for f in self.konfiguration.faehigkeiten}
        return Auto(
            kuerzel=vorlage.kuerzel,
            name=vorlage.name,
            werte={s: w for s, w in werte.items() if s in matrix},
            wetterwerte={s: w for s, w in werte.items() if s not in matrix},
        )

    def fahrwerte(self, session: str = kern_ereignis.RENNEN) -> dict[str, int]:
        """Die Werte, mit denen gefahren wird - Ereignisse und Defekte drin."""
        faktoren = self.faktoren(session)
        kleinster = self.konfiguration.wert("skala", "minimum")
        groesster = self.konfiguration.wert("skala", "maximum")
        return {
            schluessel: int(
                round(min(max(wert * faktoren.get(schluessel, 1.0), kleinster), groesster))
            )
            for schluessel, wert in self.werte.items()
        }

    # -- Defekte und Reparatur (GDD 14) ------------------------------------
    def uebernimm_defekte(self, schluessel: tuple[str, ...]) -> None:
        """Traegt die Defekte eines Rennens ein; sie bleiben bis zur Reparatur."""
        for eintrag_ in schluessel:
            self.defekte.append(kern_zwischenfall.defekt_von(self.konfiguration, eintrag_))

    @property
    def offene_reparaturen(self) -> tuple[tuple[str, str, int], ...]:
        """Alles, was repariert werden kann: Schluessel, Name, Kosten.

        Das sind die offenen Defekte aus GDD 14 und die beiden Ereignisse,
        die bis zur Reparatur laufen (E8 Motorschaden, E25 Getriebeproblem).
        """
        posten = [
            (d["schluessel"], d["name"], self.reparaturkosten(d["schluessel"]))
            for d in self.defekte
        ]
        posten += [
            (a.schluessel, a.name, self.reparaturkosten(a.schluessel))
            for a in self.lage.offene_reparaturen
        ]
        return tuple(posten)

    def reparaturkosten(self, schluessel: str) -> int:
        """Was eine Reparatur kostet (GDD 14: Stufe mal Liga-Faktor)."""
        defekt = next((d for d in self.defekte if d["schluessel"] == schluessel), None)
        if defekt is not None:
            return kern_zwischenfall.reparaturkosten(self.konfiguration, defekt, self.liga)
        if any(a.schluessel == schluessel for a in self.lage.offene_reparaturen):
            # Ereignisse nennen keine Kostenstufe; angesetzt wird die
            # mittlere Stufe der 20 Defekte aus GDD 14.
            stufen = [d["kostenstufe"] for d in self.konfiguration.wert("defekte", "liste")]
            mittel = {"kostenstufe": sum(stufen) / len(stufen)}
            return kern_zwischenfall.reparaturkosten(self.konfiguration, mittel, self.liga)
        raise KarriereFehler(f"{schluessel} ist nicht offen und nicht reparierbar")

    def repariere(self, schluessel: str) -> int:
        """Repariert einen Defekt oder ein Ereignis; wirkt sofort (GDD 14).

        :return: die bezahlten Kosten
        """
        kosten = self.reparaturkosten(schluessel)
        if self.konto.geld < kosten:
            raise KarriereFehler(
                f"Die Reparatur kostet {kosten} EUR, auf dem Konto liegen {self.konto.geld}"
            )
        defekt = next((d for d in self.defekte if d["schluessel"] == schluessel), None)
        if defekt is not None:
            self.defekte.remove(defekt)
        else:
            self.lage.repariere(schluessel)
        self.konto = self.konto.mit(geld=-kosten)
        return kosten

    def bis_zum_rennen(self) -> int:
        """Springt direkt zum naechsten Renntag (GDD 2).

        :return: Zahl der uebersprungenen Tage
        """
        ziel = self.naechstes_rennen
        if ziel is None:
            raise KarriereFehler("Es steht kein Rennen mehr an")
        uebersprungen = 0
        while self.heute < ziel:
            self.tag_weiter()
            uebersprungen += 1
        return uebersprungen

    # -- Entwicklung -------------------------------------------------------
    def wert(self, schluessel: str) -> int:
        try:
            return self.werte[schluessel]
        except KeyError:
            raise KarriereFehler(f"Unbekannte Faehigkeit: {schluessel}") from None

    def platz_fuer(self, schluessel: str) -> str:
        """Ob eine Faehigkeit den Fahrer- oder den Werkstattplatz belegt."""
        faehigkeit = self._faehigkeit(schluessel)
        if faehigkeit is None:
            # Wetterfaehigkeiten und Reifenfluesterer gehoeren dem Fahrer.
            return FAHRERPLATZ
        return (
            FAHRERPLATZ
            if kern_entwicklung.ist_fahrertraining(faehigkeit)
            else WERKSTATTPLATZ
        )

    def vorschau(self, schluessel: str) -> kern_entwicklung.Entwicklung:
        """Was eine Tageszuweisung oder ein Kauf braechte, ohne zu buchen."""
        faehigkeit = self._faehigkeit(schluessel)
        wert = self.wert(schluessel)
        if faehigkeit is None:
            return self._zusatz_vorschau(schluessel, wert)
        if kern_entwicklung.braucht_tag(faehigkeit):
            return kern_entwicklung.plane_tag(self.konfiguration, faehigkeit, wert)
        return kern_entwicklung.plane_kauf(self.konfiguration, faehigkeit, wert)

    def belege_tag(self, schluessel: str) -> kern_entwicklung.Entwicklung:
        """Belegt den heutigen Platz mit einer Faehigkeit (GDD 2)."""
        if self.tag.art is not Tagesart.NUTZBAR:
            raise KarriereFehler(
                f"{self.heute} ist ein {self.tag.art.bezeichnung}-Tag und nicht nutzbar"
            )
        if self.heute in self.verlorene_tage:
            raise KarriereFehler(f"{self.heute} ist durch ein Ereignis ausgefallen")
        self._pruefe_sperre(schluessel)
        entwicklung = self.vorschau(schluessel)
        if not entwicklung.braucht_tag:
            raise KarriereFehler(
                f"{schluessel} kostet keine Zeit - direkt kaufen statt einen Tag belegen"
            )

        platz = self.platz_fuer(schluessel)
        if platz in self.belegt:
            raise KarriereFehler(f"Der Platz {platz} ist heute schon belegt")
        self.konto = kern_entwicklung.buche(self.konto, entwicklung)
        self.belegt.add(platz)
        self._uebernimm(entwicklung, platz)
        return entwicklung

    def kaufe(self, schluessel: str) -> kern_entwicklung.Entwicklung:
        """Kauft einen +10-Schritt sofort - nur ohne Zeitanteil (GDD 2)."""
        self._pruefe_sperre(schluessel)
        entwicklung = self.vorschau(schluessel)
        if entwicklung.braucht_tag:
            raise KarriereFehler(
                f"{schluessel} braucht einen Tag - ueber belege_tag statt kaufen"
            )
        self.konto = kern_entwicklung.buche(self.konto, entwicklung)
        self._uebernimm(entwicklung, platz="")
        return entwicklung

    def gesperrt(self) -> frozenset[str]:
        """Was gerade nicht entwickelt werden darf (GDD 14: E2, E6)."""
        sperren = set(self.lage.gesperrt())
        # E2 sperrt "fahrertraining" als Ganzes, also jede Faehigkeit, die
        # den Fahrerplatz belegt.
        if kern_ereignis.FAHRERTRAINING in sperren:
            sperren.discard(kern_ereignis.FAHRERTRAINING)
            sperren.update(
                f.schluessel
                for f in self.konfiguration.faehigkeiten
                if kern_entwicklung.ist_fahrertraining(f)
            )
            sperren.update(self.konfiguration.zusatzfaehigkeiten)
        return frozenset(sperren)

    def _pruefe_sperre(self, schluessel: str) -> None:
        if schluessel in self.gesperrt():
            raise KarriereFehler(
                f"{schluessel} ist durch ein Ereignis gesperrt (GDD 14)"
            )

    def _uebernimm(self, entwicklung: kern_entwicklung.Entwicklung, platz: str) -> None:
        self.werte[entwicklung.faehigkeit] = entwicklung.nach
        self.buchungen.append(
            Tagesbuchung(
                datum=self.heute,
                platz=platz,
                faehigkeit=entwicklung.faehigkeit,
                von=entwicklung.von,
                nach=entwicklung.nach,
                geld=entwicklung.geld,
                erfahrung=entwicklung.erfahrung,
            )
        )

    def _faehigkeit(self, schluessel: str):
        try:
            return self.konfiguration.faehigkeit(schluessel)
        except KeyError:
            return None

    def _zusatz_vorschau(self, schluessel: str, wert: int) -> kern_entwicklung.Entwicklung:
        """Wetterfaehigkeiten und Reifenfluesterer stehen ausserhalb der Matrix.

        Ihre Waehrung steht bei ihnen selbst; die Wetter-Erfahrung kommt
        aus dem eigenen Topf des jeweiligen Wetters (GDD 10).
        """
        from rennmanager.konfiguration import Faehigkeit

        eintrag = self.zusatz_eintrag(schluessel)
        faehigkeit = Faehigkeit(
            schluessel=schluessel,
            name=eintrag.get("name", schluessel),
            waehrung=tuple(eintrag.get("waehrung", ("E",))),
            gewichte={},
        )
        entwicklung = (
            kern_entwicklung.plane_tag(self.konfiguration, faehigkeit, wert)
            if kern_entwicklung.braucht_tag(faehigkeit)
            else kern_entwicklung.plane_kauf(self.konfiguration, faehigkeit, wert)
        )
        wetter = eintrag.get("wetter")
        if wetter:
            return kern_entwicklung.als_wettertopf(entwicklung, wetter)
        return entwicklung

    def zusatz_eintrag(self, schluessel: str) -> dict:
        """Der Konfigurationseintrag einer Faehigkeit ausserhalb der Matrix.

        Die Wetterfaehigkeiten aus GDD 7 und der Reifenfluesterer stehen
        nicht in der Wirkungsmatrix; Name und Waehrung kommen deshalb aus
        ihrem eigenen Abschnitt der Konfiguration.
        """
        for eintrag in self.konfiguration.wert("wetter", "faehigkeit", "liste"):
            if eintrag["schluessel"] == schluessel:
                return eintrag
        fluesterer = self.konfiguration.wert("reifen", "fluesterer")
        if fluesterer.get("schluessel") == schluessel:
            return fluesterer
        raise KarriereFehler(f"Unbekannte Faehigkeit: {schluessel}")

    # -- Rennwochenende ----------------------------------------------------
    def verbuche_rennen(
        self,
        platz: int,
        ueberholmanoever: int = 0,
        kilometer_je_wetter: dict[str, float] | None = None,
    ) -> Konto:
        """Schreibt Preisgeld, Startgeld, Erfahrung und Sponsoren gut (GDD 10)."""
        geld = kern_einnahmen.preisgeld(self.konfiguration, self.liga, platz)
        geld += kern_einnahmen.startgeld(self.konfiguration, self.liga)
        geld += kern_sponsoren.auszahlung(self.vertraege, platz)
        erfahrung = kern_einnahmen.erfahrung_fuer(
            self.konfiguration, self.liga, platz, ueberholmanoever
        )

        toepfe = {}
        for wetter, kilometer in (kilometer_je_wetter or {}).items():
            toepfe[wetter] = kern_einnahmen.wetter_erfahrung(
                self.konfiguration, self.liga, kilometer, platz
            )

        self.konto = self.konto.mit(geld=geld, erfahrung=erfahrung, **toepfe)
        self.vertraege = kern_sponsoren.nach_rennen(self.vertraege)
        # Ereignisse, die in Rennwochenenden laufen, sind eines weiter
        # (GDD 14).
        self.lage.nach_rennwochenende()
        return self.konto

    def verbuche_runden(self, strecke: str, runden: int, seedquelle: Seedquelle) -> float:
        """Schreibt gefahrene Runden der Streckenkenntnis gut (GDD 6).

        E10 Testfahrt geglueckt hebt den Zuwachs der naechsten Strecke.
        """
        zuschlag = 1.0 + self.lage.streckenkenntnisbonus()
        gewachsen = self.kenntnis.verbuche(self.fahrernummer, strecke, runden, seedquelle)
        if zuschlag != 1.0:
            zusatz = gewachsen * (zuschlag - 1.0)
            self.kenntnis.setze(
                self.fahrernummer,
                strecke,
                self.kenntnis.stand(self.fahrernummer, strecke) + zusatz,
            )
            gewachsen += zusatz
        return gewachsen

    def kenntnisfaktor(self, strecke: str) -> float:
        """Tempofaktor des Spielers auf dieser Strecke (GDD 6)."""
        return self.kenntnis.tempofaktor(self.fahrernummer, strecke)

    def tagesformbonus(self) -> float:
        """Zuschlag auf den Tagesform-Mittelwert (E3 aus GDD 14).

        0,0, solange kein Ereignis darauf wirkt. Der Wert geht als
        Mittelwertverschiebung in ``rennmanager.kern.form.tagesform``.
        """
        return self.lage.tagesformbonus()

    # -- Saisonwechsel (GDD 13) --------------------------------------------
    def naechste_saison(
        self, jahr: int, liga: int, seedquelle: Seedquelle | None = None
    ) -> None:
        """Traegt die Karriere in die naechste Saison (GDD 2 und 13).

        Der Saisonwechsel liegt laut GDD 2 am 31.12./01.01.; die Karriere
        laeuft endlos weiter.

        Es bleiben: Konto, Werte, Sponsorenvertraege, offene Defekte,
        laufende Ereignisse, Streckenkenntnis und das Karrierelog aus
        Buchungen und Meldungen.

        Neu sind Kalender und Ereignisplan - und nach Auf- oder Abstieg
        die Liga. Die verlorenen Tage bleiben nicht: Sie sind Daten des
        alten Kalenders und haetten im neuen keine Bedeutung.
        """
        if jahr <= self.saison.jahr:
            raise KarriereFehler(
                f"Die Saison {jahr} liegt nicht nach {self.saison.jahr}"
            )
        self.saison = kern_kalender.erzeuge(self.konfiguration, jahr)
        self.heute = self.saison.tage[0].datum
        self.liga = liga
        self.belegt.clear()
        self.verlorene_tage.clear()
        self.ereignisplan = (
            kern_ereignis.plane_saison(
                self.konfiguration, self.saison, seedquelle.zweig("ereignisse")
            )
            if seedquelle is not None
            else {}
        )
        # Wie beim Karrierestart: Der 1. Januar wird nie "weitergeschaltet",
        # was auf ihn faellt, muesste sonst ausfallen.
        for schluessel in self.ereignisplan.get(self.heute, ()):
            self._loese_ereignis_aus(schluessel)

    def unterschreibe(self, angebot: kern_sponsoren.Angebot) -> None:
        """Nimmt ein Sponsorenangebot an; ein Platz traegt einen Vertrag."""
        self.vertraege[angebot.platz] = kern_sponsoren.unterschreibe(angebot)


def startjahr(konfiguration: Konfiguration) -> int:
    """Das Jahr der ersten Saison (GDD 2)."""
    return int(konfiguration.wert("kalender", "startjahr"))


def beginne(
    konfiguration: Konfiguration,
    jahr: int,
    liga: int,
    werte: dict[str, int] | None = None,
    seedquelle: Seedquelle | None = None,
    fahrernummer: int = 0,
) -> Karriere:
    """Startet eine Karriere am 1. Januar (GDD 1 und 10).

    :param seedquelle: bestimmt die Ereignisse der Saison (GDD 14). Ohne
        Angabe laeuft das Jahr ohne Ereignisse - so bleiben Tests, die
        allein die Entwicklung pruefen, von ihnen unberuehrt.
    """
    saison = kern_kalender.erzeuge(konfiguration, jahr)
    if werte is None:
        # GDD 1: Der Spieler startet mit allen Werten auf 0.
        werte = {f.schluessel: 0 for f in konfiguration.faehigkeiten}
        werte.update(dict.fromkeys(konfiguration.zusatzfaehigkeiten, 0))
    plan = (
        kern_ereignis.plane_saison(konfiguration, saison, seedquelle.zweig("ereignisse"))
        if seedquelle is not None
        else {}
    )
    karriere = Karriere(
        konfiguration=konfiguration,
        saison=saison,
        heute=saison.tage[0].datum,
        liga=liga,
        konto=Konto(geld=kern_einnahmen.startkapital(konfiguration)),
        werte=dict(werte),
        ereignisplan=plan,
        fahrernummer=fahrernummer,
    )
    # Der erste Januar ist selbst schon ein Tag des ersten Zyklus; was auf
    # ihn faellt, wird nie "weitergeschaltet" und muesste sonst ausfallen.
    for schluessel in plan.get(karriere.heute, ()):
        karriere._loese_ereignis_aus(schluessel)
    return karriere


def kopiere(karriere: Karriere) -> Karriere:
    """Eine unabhaengige Kopie - fuer Vorschauen, die nichts veraendern."""
    kopie = replace(
        karriere,
        konto=karriere.konto,
        werte=dict(karriere.werte),
        vertraege=dict(karriere.vertraege),
        buchungen=list(karriere.buchungen),
        belegt=set(karriere.belegt),
        defekte=list(karriere.defekte),
        verlorene_tage=set(karriere.verlorene_tage),
        meldungen=list(karriere.meldungen),
        # Die laufenden Ereignisse werden einzeln kopiert: Ihr Restzaehler
        # wird an Ort und Stelle heruntergezaehlt, eine flache Kopie der
        # Liste teilte ihn also mit dem Original.
        lage=kern_ereignis.Lage(
            karriere.konfiguration, [replace(a) for a in karriere.lage.aktive]
        ),
        kenntnis=kern_streckenkenntnis.Streckenkenntnis(
            karriere.konfiguration, dict(karriere.kenntnis.runden)
        ),
    )
    return kopie
