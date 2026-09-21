"""Popularitaet: wie bekannt ein Fahrer ist (Punkt 5).

GDD 10 laesst die Hoehe der Sponsorenangebote allein an der Liga haengen.
Das ist grob: Zwei Fahrer derselben Liga bekommen dieselben Angebote, egal
ob der eine Titel gesammelt hat und der andere nie vorn war. Die
Popularitaet ist die Groesse, die das trennt.

Sie ist aufgebaut wie die Streckenkenntnis aus GDD 6: ein Wert je Fahrer
neben der Welt, der die Saison ueberdauert und im Spielstand liegt. Zwei
Regeln, beide mit dem Auftraggeber abgestimmt:

* Der **Anfangswert** ist gestreut, aber ausdruecklich *nicht* nach
  Ligastaerke. Bekanntheit ist nicht dasselbe wie Schnelligkeit - ein
  Fahrer aus Liga 10 kann bekannter sein als einer aus Liga 1.
* Sie **waechst aus Siegen, Podien und Poles**, also aus dem, was die
  Karrierezahlen aus GDD 13 ohnehin fuehren.

Sie sinkt nicht wieder: Was ein Fahrer erreicht hat, bleibt. Wer eine
Karriere lang dominiert, erreicht deshalb irgendwann die Obergrenze der
Skala - bei durchgehend 20 Siegen je Saison nach gut vier Jahren.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.kern.wertung import Rennergebnis
    from rennmanager.konfiguration import Konfiguration


@dataclass
class Popularitaet:
    """Der Bekanntheitsgrad aller Fahrer, auf der Skala aus GDD 1."""

    konfiguration: Konfiguration
    werte: dict[int, float] = field(default_factory=dict)

    # -- Stand -------------------------------------------------------------
    def stand(self, fahrer: int) -> float:
        return self.werte.get(fahrer, 0.0)

    def vergiss_fahrer(self, fahrer: int) -> None:
        """Nimmt einen Fahrer aus der Bekanntheit (Punkt 35).

        Ein Newgen erbt die Nummer des Zurueckgetretenen - dessen
        Bekanntheit waere ein Sponsorenvorteil, den er nie verdient hat.
        Sein eigener Anfangswert wird beim naechsten ``anfang`` gezogen.
        """
        self.werte.pop(fahrer, None)

    def setze(self, fahrer: int, wert: float) -> None:
        kleinster = self.konfiguration.wert("skala", "minimum")
        groesster = self.konfiguration.wert("skala", "maximum")
        self.werte[fahrer] = float(min(max(wert, kleinster), groesster))

    def anfang(self, fahrer: tuple[int, ...], seedquelle: Seedquelle) -> None:
        """Wuerfelt den Anfangswert aller Fahrer.

        Gestreut, aber nicht nach Ligastaerke: Jeder Fahrer zieht aus
        derselben Verteilung.
        """
        einstellung = self.konfiguration.wert("popularitaet")
        mittel = einstellung["mittelwert"]
        breite = einstellung["anfang_streuung"]
        for nummer in fahrer:
            wuerfel = seedquelle.zweig("fahrer", nummer).generator()
            self.setze(nummer, mittel * (1.0 + float(wuerfel.uniform(-breite, breite))))

    # -- Wachstum ----------------------------------------------------------
    def zuwachs(self, ergebnis: Rennergebnis) -> int:
        """Was ein Rennwochenende einbringt (GDD 13: Siege, Podien, Poles)."""
        einstellung = self.konfiguration.wert("popularitaet")
        gewonnen = 0
        if ergebnis.rennplatz == 1:
            gewonnen += einstellung["je_sieg"]
        if ergebnis.rennplatz <= 3:
            gewonnen += einstellung["je_podium"]
        if ergebnis.qualifyingplatz == 1:
            gewonnen += einstellung["je_pole"]
        return int(gewonnen)

    def verbuche_wochenende(self, ergebnisse) -> None:
        """Schreibt einem ganzen Feld gut, was es erreicht hat."""
        for ergebnis in ergebnisse:
            zuwachs = self.zuwachs(ergebnis)
            if zuwachs:
                self.setze(ergebnis.fahrer, self.stand(ergebnis.fahrer) + zuwachs)

    # -- Wirkung -----------------------------------------------------------
    def faktor(self, fahrer: int) -> float:
        """Faktor auf den Grundbetrag der Sponsorenangebote (GDD 10).

        Bezugspunkt ist der Mittelwert, nicht das Skalenende: Wer genau
        durchschnittlich bekannt ist, bekommt die Betraege, die GDD 10 fuer
        seine Liga vorsieht. Von dort geht es linear bis +/- 25 Prozent.

        Anders als sonst wird hier *nicht* ueber den Leistungsanteil
        gerechnet - Bekanntheit ist keine Fahrleistung, sondern eine Zahl
        fuer sich.
        """
        einstellung = self.konfiguration.wert("popularitaet")
        max_anteil = einstellung["max_anteil_sponsor"]
        mittel = einstellung["mittelwert"]
        if mittel <= 0:
            return 1.0
        abstand = min(max((self.stand(fahrer) - mittel) / mittel, -1.0), 1.0)
        return 1.0 + max_anteil * abstand
