"""Karrierestand: Kalender, Konto, Werte und Vertraege (GDD 2, 9 und 10).

Fasst zusammen, was der Spieler zwischen zwei Rennen tut: Tage
weiterschalten, Trainings- und Werkstattplaetze belegen, Upgrades kaufen
und Sponsorenvertraege abschliessen.

Zeit ist dabei eine Kapazitaet (GDD 2): Jeder nutzbare Tag hat zwei
Plaetze, einen fuer den Fahrer und einen fuer die Werkstatt. Ein Tag, der
vorbei ist, ohne belegt zu sein, ist verloren.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from rennmanager.kern import einnahmen as kern_einnahmen
from rennmanager.kern import entwicklung as kern_entwicklung
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import sponsoren as kern_sponsoren
from rennmanager.kern.entwicklung import Konto
from rennmanager.kern.kalender import Saison, Tagesart

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

FAHRERPLATZ = "fahrer"
WERKSTATTPLATZ = "werkstatt"


class KarriereFehler(Exception):
    """Die Aktion ist an diesem Tag oder mit diesem Vorrat nicht moeglich."""


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
        """Nutzbare Tage bis zum naechsten Rennen, heute eingeschlossen."""
        ziel = self.naechstes_rennen
        if ziel is None:
            ziel = self.saison.tage[-1].datum
        return len(self.saison.nutzbare_tage(self.heute, ziel))

    def tag_weiter(self) -> kern_kalender.Kalendertag:
        """Schaltet einen Tag weiter (GDD 2).

        Ereignisse werden beim Tageswechsel ausgeloest; sie kommen in
        Schritt 10 dazu.
        """
        naechster = self.heute + dt.timedelta(days=1)
        if naechster > self.saison.tage[-1].datum:
            raise KarriereFehler("Die Saison ist zu Ende")
        self.heute = naechster
        self.belegt.clear()
        return self.tag

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
        entwicklung = self.vorschau(schluessel)
        if entwicklung.braucht_tag:
            raise KarriereFehler(
                f"{schluessel} braucht einen Tag - ueber belege_tag statt kaufen"
            )
        self.konto = kern_entwicklung.buche(self.konto, entwicklung)
        self._uebernimm(entwicklung, platz="")
        return entwicklung

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

        eintrag = self._zusatz_eintrag(schluessel)
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

    def _zusatz_eintrag(self, schluessel: str) -> dict:
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
        return self.konto

    def unterschreibe(self, angebot: kern_sponsoren.Angebot) -> None:
        """Nimmt ein Sponsorenangebot an; ein Platz traegt einen Vertrag."""
        self.vertraege[angebot.platz] = kern_sponsoren.unterschreibe(angebot)


def beginne(
    konfiguration: Konfiguration, jahr: int, liga: int, werte: dict[str, int] | None = None
) -> Karriere:
    """Startet eine Karriere am 1. Januar (GDD 1 und 10)."""
    saison = kern_kalender.erzeuge(konfiguration, jahr)
    if werte is None:
        # GDD 1: Der Spieler startet mit allen Werten auf 0.
        werte = {f.schluessel: 0 for f in konfiguration.faehigkeiten}
        werte.update(dict.fromkeys(konfiguration.zusatzfaehigkeiten, 0))
    return Karriere(
        konfiguration=konfiguration,
        saison=saison,
        heute=saison.tage[0].datum,
        liga=liga,
        konto=Konto(geld=kern_einnahmen.startkapital(konfiguration)),
        werte=dict(werte),
    )


def kopiere(karriere: Karriere) -> Karriere:
    """Eine unabhaengige Kopie - fuer Vorschauen, die nichts veraendern."""
    return replace(
        karriere,
        konto=karriere.konto,
        werte=dict(karriere.werte),
        vertraege=dict(karriere.vertraege),
        buchungen=list(karriere.buchungen),
        belegt=set(karriere.belegt),
    )
