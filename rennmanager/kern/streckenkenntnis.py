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

Die KI bekam ihren Stand lange **einmal fest** gesetzt: GDD 12 sagte
"die KI verbessert sich vorerst nicht". Mit Punkt 35 entwickelt sie sich,
also lernt sie auch Strecken dazu - ``[ki] entwicklung`` schaltet beides
gemeinsam. Der Anfangsstand bleibt: Die Startwelt wuerfelt Alter von 18
bis 42, diese Fahrer haben eine Laufbahn hinter sich. **Newgens starten
dagegen bei null** und muessen sich einfahren.

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

    def vergiss_fahrer(self, fahrer: int) -> None:
        """Setzt einen Fahrer auf null zurueck (Punkt 35).

        Ein Newgen erbt die Nummer des Zurueckgetretenen; dessen
        Streckenkenntnis waere ein Startvorteil, den er nie gefahren hat.
        """
        for schluessel in [s for s in self.runden if s[0] == fahrer]:
            del self.runden[schluessel]
        self._lerntempo.pop(fahrer, None)
        self.fest.discard(fahrer)

    def setze(self, fahrer: int, strecke: str, runden: float) -> None:
        """Setzt einen Stand - fuer das Laden eines Spielstands (GDD 15)."""
        self.runden[(fahrer, strecke)] = float(runden)

    def setze_anfang(
        self,
        fahrer: tuple[int, ...],
        strecken: tuple[str, ...],
        seedquelle: Seedquelle,
        fest: bool = True,
    ) -> None:
        """Gibt der KI ihren Anfangsstand je Strecke.

        Die Startwelt wuerfelt Alter von 18 bis 42 - diese Fahrer haben
        eine Laufbahn hinter sich, und der Stand steht fuer alles, was sie
        vor Spielbeginn hier gefahren sind. Die Streuung ist breit: Auf
        derselben Strecke kennt sich der eine bestens aus, der andere kaum.

        :param fest: friert den Stand ein. Solange die KI sich nicht
            entwickelt (GDD 12), darf auch ihre Streckenkenntnis nicht
            wachsen - sonst liefen alle 570 KI-Autos ueber die Saisons der
            Kalibriertabelle aus GDD 9 davon. Mit Punkt 35 entwickelt sie
            sich, also lernt sie auch mit.
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
            if fest:
                self.fest.add(nummer)


def setze_ki_anfang(
    konfiguration: Konfiguration,
    welt,
    kenntnis: Streckenkenntnis,
    strecken: tuple[str, ...],
    seedquelle: Seedquelle,
) -> None:
    """Gibt allen KI-Fahrern einer Welt ihren Anfangsstand.

    Der Spieler bleibt aussen vor: Er faengt bei null an und faehrt sich
    ein.

    Ob der Stand danach fest bleibt, entscheidet ``[ki] entwicklung``.
    Seit Punkt 35 lernt die KI mit - **Newgens starten dann bei null**
    (Entscheidung des Auftraggebers). ``vergiss_fahrer`` sorgt dafuer: Ein
    Newgen erbt die Nummer eines Zurueckgetretenen, nicht dessen Kenntnis.
    Am Anfang seiner Laufbahn fehlen ihm damit bis zu 1,5 % Tempo, rund
    1,3 Sekunden je Runde - er muss sich einfahren wie ein echter Rookie.
    """
    ki = tuple(f.nummer for f in welt.fahrer if not f.ist_spieler)
    kenntnis.setze_anfang(
        ki, strecken, seedquelle, fest=not konfiguration.wert("ki", "entwicklung")
    )
