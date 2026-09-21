"""Streckenkenntnis (GDD 6, Punkt 101).

"Je Strecke steigt ein Kenntniswert mit jedem Start und jeder gefahrenen
Runde. Der Wert gibt einen kleinen Tempobonus mit Obergrenze (bis +1,5 %,
voll nach etwa 1.000 Runden)."

Seit Punkt 101 **waechst** er nicht mehr: Wir fahren mit festen Fahrern
und festen Staerken, niemand entwickelt sich. Der Stand wird einmal bei
der Welterzeugung je Fahrer und Strecke gewuerfelt und bleibt dann, wie
er ist. Was bleibt, ist der Gedanke dahinter - auf derselben Strecke
kennt sich der eine bestens aus, der andere kaum, und das ist auf jeder
Strecke anders.

Gemessen wird der Kenntnisstand in Runden - das ist die Einheit, in der
GDD 6 die Obergrenze nennt.

Der Kenntnisstand gehoert nicht ins Auto, sondern neben es: Er haengt am
Paar aus Fahrer und Strecke. Die Simulation bekommt ihn deshalb als
fertigen Tempofaktor uebergeben und muss nicht wissen, wem er gehoert.
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


@dataclass
class Streckenkenntnis:
    """Was ein Fahrer auf welcher Strecke schon gefahren ist.

    Der Stand wird je Fahrer und Strecke in Runden gehalten; ``stand`` und
    ``tempofaktor`` liefern daraus Kenntnis und Bonus.
    """

    konfiguration: Konfiguration
    runden: dict[tuple[int, str], float] = field(default_factory=dict)

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

    def setze(self, fahrer: int, strecke: str, runden: float) -> None:
        """Setzt einen Stand - fuers Laden eines Spielstands und den Editor."""
        self.runden[(fahrer, strecke)] = float(runden)

    def setze_anfang(
        self,
        fahrer: tuple[int, ...],
        strecken: tuple[str, ...],
        seedquelle: Seedquelle,
    ) -> None:
        """Gibt jedem Fahrer seinen Stand je Strecke (Punkt 101).

        Er steht fuer alles, was ein Fahrer vor Spielbeginn hier gefahren
        ist, und aendert sich danach nicht mehr. Die Streuung ist breit:
        Auf derselben Strecke kennt sich der eine bestens aus, der andere
        kaum.
        """
        einstellung = self.konfiguration.wert("streckenkenntnis", "anfang")
        voll = self.konfiguration.wert("streckenkenntnis", "volle_kenntnis_runden")
        mittel = einstellung["anteil"] * voll
        breite = einstellung["streuung"]

        for nummer in fahrer:
            wuerfel = seedquelle.zweig("fahrer", nummer).generator()
            for strecke in strecken:
                faktor = 1.0 + float(wuerfel.uniform(-breite, breite))
                self.runden[(nummer, strecke)] = max(mittel * faktor, 0.0)


def setze_feldanfang(
    konfiguration: Konfiguration,
    welt,
    kenntnis: Streckenkenntnis,
    strecken: tuple[str, ...],
    seedquelle: Seedquelle,
) -> None:
    """Gibt allen Fahrern einer Welt ihren Stand (Punkt 101).

    Seit Punkt 101 gilt das auch fuer den Spieler: Er entwickelt sich
    nicht mehr, also faengt er auch nicht mehr bei null an und faehrt
    sich ein.
    """
    del konfiguration  # die Regel steht fest, sie braucht keinen Wert
    kenntnis.setze_anfang(
        tuple(f.nummer for f in welt.fahrer), strecken, seedquelle
    )
