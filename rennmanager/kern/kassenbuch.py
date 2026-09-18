"""Das Kassenbuch: jede Geldbewegung mit Kategorie (Punkt 72).

Bisher kannte die Karriere nur einen Kontostand. Wo das Geld herkam und
wohin es ging, stand nirgends - eine Finanzseite haette nichts zu
gruppieren gehabt. Dieses Modul fuehrt deshalb Buch: Jede Buchung traegt
Datum, Betrag, Haupt- und Unterkategorie und, wo es passt, den Fahrer.

**Vorzeichen statt zweier Listen.** Ein positiver Betrag ist eine
Einnahme, ein negativer eine Ausgabe. So lassen sich Summen ohne
Fallunterscheidung bilden, und eine Rueckerstattung ist einfach eine
Ausgabe mit umgekehrtem Vorzeichen.

Das Buch reicht ueber die **ganze Karriere**; die Finanzseite blendet auf
Wunsch auf eine Saison ein. Es rechnet nichts aus und aendert nichts -
es schreibt mit. Wer Geld bewegt, bucht hier zusaetzlich mit.
"""

from __future__ import annotations

import datetime as dt
from collections import OrderedDict
from dataclasses import dataclass, field

# --- Hauptkategorien ------------------------------------------------------
# Sie stehen hier und nicht in der Konfiguration: Es sind keine
# Balancing-Werte, sondern die Struktur des Buchs. Wer eine Kategorie
# aendert, aendert den Code, der sie bucht, ohnehin mit.
RENNEN = "Rennen"
SPONSOREN = "Sponsoren"
TEAM = "Team"
EREIGNISSE = "Ereignisse"
ENTWICKLUNG = "Entwicklung"
WERKSTATT = "Werkstatt"
PERSONAL = "Personal"
TRANSFER = "Transfer"

# --- Unterkategorien ------------------------------------------------------
PREISGELD = "Preisgeld"
STARTGELD = "Startgeld"
SPONSORENGELD = "Sponsorenzahlung"
MONATSBUDGET = "Monatsbudget"
ZUSCHUSS = "Zuschuss"
STRAFE = "Strafe"
FAHRZEUG = "Fahrzeug-Upgrade"
TRAINING = "Fahrertraining"
REPARATUR = "Reparatur"
GEHALT = "Gehalt"
ABLOESE = "Abloese"
STARTKAPITAL = "Startkapital"

# In dieser Reihenfolge stehen die Hauptkategorien in der Anzeige:
# erst, womit Geld hereinkommt, dann, wofuer es hinausgeht.
REIHENFOLGE = (
    RENNEN,
    SPONSOREN,
    TEAM,
    EREIGNISSE,
    ENTWICKLUNG,
    WERKSTATT,
    PERSONAL,
    TRANSFER,
)


@dataclass(frozen=True)
class Buchung:
    """Eine einzelne Geldbewegung.

    :param betrag: positiv ist eine Einnahme, negativ eine Ausgabe
    :param fahrer: wessen Auto es betrifft; ``None`` fuer das ganze Team
    """

    datum: dt.date
    betrag: int
    hauptkategorie: str
    unterkategorie: str
    fahrer: int | None = None
    text: str = ""

    @property
    def ist_einnahme(self) -> bool:
        return self.betrag > 0


@dataclass
class Zusammenfassung:
    """Was eine Kategorie ueber den betrachteten Zeitraum bewegt hat."""

    einnahmen: int = 0
    ausgaben: int = 0
    anzahl: int = 0

    @property
    def saldo(self) -> int:
        return self.einnahmen - self.ausgaben


@dataclass
class Kassenbuch:
    """Alle Buchungen einer Karriere, in der Reihenfolge ihres Entstehens."""

    buchungen: list[Buchung] = field(default_factory=list)

    # -- Schreiben ---------------------------------------------------------
    def buche(
        self,
        datum: dt.date,
        betrag: int,
        hauptkategorie: str,
        unterkategorie: str,
        fahrer: int | None = None,
        text: str = "",
    ) -> Buchung | None:
        """Schreibt eine Buchung; ein Betrag von 0 wird nicht gebucht.

        Nullbuchungen entstehen an vielen Stellen - ein Rennen ohne
        Sponsoren, ein Ereignis ohne Geldwirkung. Sie wuerden das Buch
        fuellen, ohne etwas auszusagen.
        """
        if not betrag:
            return None
        eintrag = Buchung(
            datum=datum,
            betrag=int(betrag),
            hauptkategorie=hauptkategorie,
            unterkategorie=unterkategorie,
            fahrer=fahrer,
            text=text,
        )
        self.buchungen.append(eintrag)
        return eintrag

    # -- Lesen -------------------------------------------------------------
    def im_zeitraum(
        self, von: dt.date | None = None, bis: dt.date | None = None
    ) -> tuple[Buchung, ...]:
        """Alle Buchungen zwischen zwei Tagen, beide eingeschlossen."""
        return tuple(
            b
            for b in self.buchungen
            if (von is None or b.datum >= von) and (bis is None or b.datum <= bis)
        )

    def einnahmen(self, buchungen=None) -> int:
        return sum(b.betrag for b in self._auswahl(buchungen) if b.betrag > 0)

    def ausgaben(self, buchungen=None) -> int:
        """Die Ausgaben als positive Zahl - so liest sich eine Bilanz."""
        return -sum(b.betrag for b in self._auswahl(buchungen) if b.betrag < 0)

    def saldo(self, buchungen=None) -> int:
        return sum(b.betrag for b in self._auswahl(buchungen))

    def nach_kategorien(self, buchungen=None) -> dict[str, dict[str, Zusammenfassung]]:
        """Summen je Haupt- und Unterkategorie, in fester Reihenfolge.

        Genau die Form, die die Finanzseite als Baum zeichnet: aussen die
        Hauptkategorie, innen ihre Unterkategorien.
        """
        gruppen: dict[str, dict[str, Zusammenfassung]] = OrderedDict()
        for buchung in self._auswahl(buchungen):
            innen = gruppen.setdefault(buchung.hauptkategorie, OrderedDict())
            summe = innen.setdefault(buchung.unterkategorie, Zusammenfassung())
            if buchung.betrag > 0:
                summe.einnahmen += buchung.betrag
            else:
                summe.ausgaben += -buchung.betrag
            summe.anzahl += 1
        # Bekannte Hauptkategorien zuerst, in der festgelegten Reihenfolge;
        # alles Unbekannte haengt hinten an, statt zu verschwinden.
        geordnet: dict[str, dict[str, Zusammenfassung]] = OrderedDict()
        for name in REIHENFOLGE:
            if name in gruppen:
                geordnet[name] = gruppen.pop(name)
        geordnet.update(gruppen)
        return geordnet

    def summe_von(self, hauptkategorie: str, buchungen=None) -> Zusammenfassung:
        """Was eine Hauptkategorie insgesamt bewegt hat."""
        gesamt = Zusammenfassung()
        for buchung in self._auswahl(buchungen):
            if buchung.hauptkategorie != hauptkategorie:
                continue
            if buchung.betrag > 0:
                gesamt.einnahmen += buchung.betrag
            else:
                gesamt.ausgaben += -buchung.betrag
            gesamt.anzahl += 1
        return gesamt

    def _auswahl(self, buchungen):
        return self.buchungen if buchungen is None else buchungen

    def __len__(self) -> int:
        return len(self.buchungen)


def monatsrate(konfiguration, teambudget: int) -> int:
    """Die Monatsrate aus dem Teambudget (Punkt 72).

    GDD 10 kennt fuer den Spieler bisher nur Preis- und Startgeld. Das
    Teambudget stand in der Welt und war reine Anzeige; jetzt zahlt es
    sich in Raten aus und fuellt das Konto.
    """
    raten = konfiguration.wert("finanzen", "budget_raten_je_jahr")
    if raten <= 0:
        return 0
    return int(max(teambudget, 0) // raten)
