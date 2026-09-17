"""Streckenkenntnis (GDD 6).

"Je Strecke steigt ein Kenntniswert mit jedem Start und jeder gefahrenen
Runde. Der Zuwachs streut zufaellig: +/-75 % je Start und zusaetzlich
+/-50 % je Runde. Der Wert gibt einen kleinen Tempobonus mit Obergrenze
(bis +1,5 %, voll nach etwa 1.000 Runden)."

Gemessen wird der Kenntnisstand in Runden - das ist die Einheit, in der
GDD 6 die Obergrenze nennt. Die beiden Streuungen stapeln sich, wie das
Wort "zusaetzlich" es sagt: Je Session faellt ein Wurf fuer den Start, je
Runde ein weiterer. Dadurch bringt dieselbe Zahl Runden mal mehr und mal
weniger Kenntnis, und zwei Fahrer mit gleicher Historie stehen trotzdem
verschieden da.

Der Kenntnisstand gehoert nicht ins Auto, sondern neben es: Er haengt am
Paar aus Fahrer und Strecke und ueberdauert die Session. Die Simulation
bekommt ihn deshalb als fertigen Tempofaktor uebergeben und muss nicht
wissen, wem er gehoert.

Die KI bekommt ihren Stand dagegen **einmal fest** gesetzt (Entscheidung
zu Punkt 39): GDD 12 sagt "die KI verbessert sich vorerst nicht", und
eine wachsende Streckenkenntnis waere genau das - ueber die Saisons
wuerden alle 570 KI-Autos der Kalibriertabelle aus GDD 9 davonlaufen.

Dazu kommt ein **Lerntempo je Fahrer** (Entscheidung zu Punkt 38). Die
beiden Streuungen aus GDD 6 mitteln sich ueber eine Saison weg - nach 20
Starts stuenden alle Fahrer nahezu gleich da. Ein fester Faktor je Fahrer
bleibt dagegen bestehen: Manche lernen eine Strecke schnell, andere nie
ganz. Er wird aus der Seedquelle abgeleitet und muss deshalb nicht
gespeichert werden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


def bonus(konfiguration: Konfiguration, runden: float) -> float:
    """Tempobonus bei diesem Kenntnisstand, 0 bis ``max_bonus`` (GDD 6).

    Linear bis zur Obergrenze: "voll nach etwa 1.000 Runden".
    """
    einstellung = konfiguration.wert("streckenkenntnis")
    voll = max(einstellung["volle_kenntnis_runden"], 1)
    return einstellung["max_bonus"] * min(max(runden, 0.0) / voll, 1.0)


def zuwachs(
    konfiguration: Konfiguration, runden: int, seedquelle: Seedquelle
) -> float:
    """Kenntniszuwachs einer Session in Runden (GDD 6).

    Ein Wurf gilt fuer den Start, je Runde faellt ein weiterer. Beide
    streuen gleichverteilt um ihre Spanne aus der Konfiguration.
    """
    if runden <= 0:
        return 0.0
    einstellung = konfiguration.wert("streckenkenntnis")
    wuerfel = seedquelle.generator()
    start = 1.0 + float(
        wuerfel.uniform(-einstellung["streuung_je_start"], einstellung["streuung_je_start"])
    )
    je_runde = 1.0 + wuerfel.uniform(
        -einstellung["streuung_je_runde"], einstellung["streuung_je_runde"], size=runden
    )
    return float(start * je_runde.sum())


@dataclass
class Streckenkenntnis:
    """Was ein Fahrer auf welcher Strecke schon gefahren ist.

    Der Stand wird je Fahrer und Strecke in Runden gehalten; ``stand`` und
    ``tempofaktor`` liefern daraus Kenntnis und Bonus.

    :param seedquelle: bestimmt das Lerntempo je Fahrer. Ohne Angabe lernt
        jeder gleich schnell - das brauchen Tests, die allein die Formel
        pruefen.
    """

    konfiguration: Konfiguration
    runden: dict[tuple[int, str], float] = field(default_factory=dict)
    seedquelle: Seedquelle | None = None
    # Fahrer, deren Stand fest ist: Solange die KI sich nicht entwickelt
    # (GDD 12), waechst auch ihre Streckenkenntnis nicht.
    fest: set[int] = field(default_factory=set)
    _lerntempo: dict[int, float] = field(default_factory=dict, repr=False)

    def lerntempo(self, fahrer: int) -> float:
        """Wie schnell dieser Fahrer eine Strecke lernt (Punkt 38).

        Ein fester Faktor je Fahrer, aus dem Seed abgeleitet und deshalb
        ueber die ganze Karriere derselbe.
        """
        if self.seedquelle is None:
            return 1.0
        if fahrer not in self._lerntempo:
            breite = self.konfiguration.wert("streckenkenntnis", "lerntempo_streuung")
            wuerfel = self.seedquelle.zweig("lerntempo", fahrer).generator()
            self._lerntempo[fahrer] = 1.0 + float(wuerfel.uniform(-breite, breite))
        return self._lerntempo[fahrer]

    def stand(self, fahrer: int, strecke: str) -> float:
        return self.runden.get((fahrer, strecke), 0.0)

    def bonus(self, fahrer: int, strecke: str) -> float:
        """Tempobonus dieses Fahrers auf dieser Strecke."""
        return bonus(self.konfiguration, self.stand(fahrer, strecke))

    def tempofaktor(self, fahrer: int, strecke: str) -> float:
        """Faktor aufs Tempo: 1,0 ohne Kenntnis, bis 1,015 bei voller."""
        return 1.0 + self.bonus(fahrer, strecke)

    def tempofaktoren(self, fahrer: tuple[int, ...], strecke: str) -> tuple[float, ...]:
        """Die Faktoren eines ganzen Feldes, in der Reihenfolge der Fahrer."""
        return tuple(self.tempofaktor(nummer, strecke) for nummer in fahrer)

    def verbuche(
        self, fahrer: int, strecke: str, runden: int, seedquelle: Seedquelle
    ) -> float:
        """Schreibt die Runden einer Session gut (GDD 6).

        Fahrer mit festem Stand lernen nicht dazu; ihr Wert wurde einmal
        gesetzt und bleibt (GDD 12).

        :return: der gewuerfelte Zuwachs in Runden
        """
        if fahrer in self.fest:
            return 0.0
        gewachsen = zuwachs(self.konfiguration, runden, seedquelle) * self.lerntempo(fahrer)
        self.runden[(fahrer, strecke)] = self.stand(fahrer, strecke) + gewachsen
        return gewachsen

    def verbuche_feld(
        self,
        fahrer: tuple[int, ...],
        strecke: str,
        runden: int,
        seedquelle: Seedquelle,
    ) -> None:
        """Schreibt dieselbe Rundenzahl fuer ein ganzes Feld gut."""
        for nummer in fahrer:
            self.verbuche(nummer, strecke, runden, seedquelle.zweig("fahrer", nummer))

    def setze(self, fahrer: int, strecke: str, runden: float) -> None:
        """Setzt einen Stand - fuer das Laden eines Spielstands (GDD 15)."""
        self.runden[(fahrer, strecke)] = float(runden)

    def setze_festen_anfang(
        self,
        fahrer: tuple[int, ...],
        strecken: tuple[str, ...],
        seedquelle: Seedquelle,
    ) -> None:
        """Gibt der KI einen festen Anfangsstand je Strecke (GDD 12).

        "Die KI verbessert sich vorerst nicht" - dann darf auch ihre
        Streckenkenntnis nicht wachsen, sonst liefen ueber die Saisons alle
        570 KI-Autos der Kalibriertabelle aus GDD 9 davon. Der Stand wird
        deshalb einmal gewuerfelt und dann festgehalten; er steht fuer
        alles, was der Fahrer vor Karrierebeginn hier gefahren ist.

        Die Streuung ist breit: Auf derselben Strecke kennt sich der eine
        bestens aus, der andere kaum.
        """
        einstellung = self.konfiguration.wert("streckenkenntnis", "ki")
        voll = self.konfiguration.wert("streckenkenntnis", "volle_kenntnis_runden")
        mittel = einstellung["anfang_anteil"] * voll
        breite = einstellung["anfang_streuung"]

        for nummer in fahrer:
            wuerfel = seedquelle.zweig("fahrer", nummer).generator()
            for strecke in strecken:
                faktor = 1.0 + float(wuerfel.uniform(-breite, breite))
                self.runden[(nummer, strecke)] = max(mittel * faktor, 0.0)
            self.fest.add(nummer)


def setze_ki_anfang(
    konfiguration: Konfiguration,
    welt,
    kenntnis: Streckenkenntnis,
    strecken: tuple[str, ...],
    seedquelle: Seedquelle,
) -> None:
    """Gibt allen KI-Fahrern einer Welt ihren festen Stand (GDD 12).

    Der Spieler bleibt aussen vor: Er entwickelt sich, also waechst seine
    Streckenkenntnis mit jeder gefahrenen Runde.
    """
    if konfiguration.wert("ki", "entwicklung"):
        # Sobald sich die KI entwickelt, lernt sie auch Strecken dazu.
        return
    ki = tuple(f.nummer for f in welt.fahrer if not f.ist_spieler)
    kenntnis.setze_festen_anfang(ki, strecken, seedquelle)
