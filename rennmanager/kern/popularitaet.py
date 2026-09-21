"""Popularitaet: wie bekannt ein Fahrer ist (Punkt 5).

Sie ist aufgebaut wie die Streckenkenntnis aus GDD 6: ein Wert je Fahrer
neben der Welt, der die Saison ueberdauert und im Spielstand liegt. Zwei
Regeln, beide mit dem Auftraggeber abgestimmt:

* Der **Anfangswert** ist gestreut, aber ausdruecklich *nicht* nach
  Staerke. Bekanntheit ist nicht dasselbe wie Schnelligkeit - der
  Letzte des Feldes kann bekannter sein als der Erste.
* Sie **waechst aus Siegen, Podien und Poles**, also aus dem, was die
  Karrierezahlen aus GDD 13 ohnehin fuehren.

Sie sinkt nicht wieder: Was ein Fahrer erreicht hat, bleibt. Wer eine
Karriere lang dominiert, erreicht deshalb irgendwann die Obergrenze der
Skala - bei durchgehend 20 Siegen je Saison nach gut vier Jahren.

Seit Punkt 101 bewegt sie nichts mehr: Die Sponsoren aus GDD 10, deren
Grundbetrag sie hob und senkte, sind mit dem Geld weggefallen. Sie
bleibt als Angabe im Steckbrief und im Editor.
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
