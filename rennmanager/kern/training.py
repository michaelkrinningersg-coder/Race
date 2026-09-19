"""Trainingsprogramme ueber mehrere Tage (Punkt 84).

Bis hierher kannte die Karriere zwei Wege, einen Wert zu heben: einen
Platz mit einer Faehigkeit **belegen** - das gilt bis zum naechsten
Rennen und bringt ``max(+10, +1 %)`` - oder eine reine Geld- oder
EP-Faehigkeit sofort **kaufen**. Die zehn nutzbaren Tage zwischen zwei
Rennen standen dabei in der Anzeige, wurden aber von nichts verbraucht.

Ein Programm macht sie zur Waehrung. Es laeuft ueber fuenf bis zehn
nutzbare Tage, belegt solange den Platz und zahlt je Tag einen Anteil
dessen, was eine Einzelbuchung braechte:

    Zuwachs(n) = n * tag_anteil * Tageszuwachs

Bei ``tag_anteil = 0,20`` sind fuenf Tage eine Buchung und zehn Tage
zwei. Das ist der Anreiz - ohne ihn waere das Programm strikt schlechter
als die sichere Einzelbuchung, denn es belegt denselben Platz, bringt
dasselbe und kann abbrechen.

Die Zahl haengt dabei an der Rundung, nicht am Bauchgefuehl: Jeder
Zuwachs faellt auf ganze Kaufschritte (GDD 9), und der Tageszuwachs ist
fuer jeden Wert unter 2000 genau ein solcher Schritt. Der Anteil muss
also erst einen vollen Schritt fuellen, bevor er sichtbar wird - unter
``2 / max_tage`` ist die Mechanik tot. ``test_training.py`` haelt das
als Regel fest, damit die Zahl nicht still darunter rutscht.

**Nie ueber ein Rennwochenende hinweg** (Entscheidung des
Auftraggebers). Zwischen zwei Rennen liegen genau zehn nutzbare Tage,
und ``max_tage`` ist ebenfalls zehn - ein Programm passt also immer in
einen Rennabstand und endet spaetestens am Renntag.

**Ein Abbruch zahlt anteilig.** Sperrt ein Ereignis die Faehigkeit
(GDD 14: E2, E6) oder frisst es Tage (E29), endet das Programm vorzeitig
und rechnet die geleisteten Tage ab. Die Zeit war dann nicht umsonst,
der Rest ist verloren. Einen Bonus fuers Durchhalten gibt es nicht.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from rennmanager.kern import entwicklung as kern_entwicklung

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration


class TrainingsFehler(Exception):
    """Dieses Programm laesst sich so nicht buchen."""


@dataclass(frozen=True)
class Programm:
    """Ein laufendes Trainingsprogramm eines Fahrers.

    :param tage: die nutzbaren Tage, an denen trainiert wird - die
        Kalendertage dazwischen (Rennen, Qualifying, Reise) zaehlen nicht
        mit und stehen deshalb gar nicht erst in der Liste
    :param geleistet: wie viele davon schon vorbei sind
    """

    faehigkeit: str
    platz: str
    tage: tuple[dt.date, ...]
    geleistet: int = 0

    @property
    def dauer(self) -> int:
        return len(self.tage)

    @property
    def laeuft(self) -> bool:
        return self.geleistet < self.dauer

    @property
    def letzter_tag(self) -> dt.date:
        return self.tage[-1]

    def mit_tag(self) -> Programm:
        """Einen geleisteten Tag weiter."""
        return replace(self, geleistet=min(self.geleistet + 1, self.dauer))


def spanne(konfiguration: Konfiguration) -> tuple[int, int]:
    """Kuerzeste und laengste erlaubte Dauer in nutzbaren Tagen."""
    einstellung = konfiguration.wert("zeitmodell", "training")
    return int(einstellung["min_tage"]), int(einstellung["max_tage"])


def zuwachs(konfiguration: Konfiguration, wert: int, tage: int) -> int:
    """Was ``tage`` Trainingstage bei diesem Wert heben.

    Gerechnet wird auf dem Tageszuwachs der Einzelbuchung: Ein
    Trainingstag bringt ``tag_anteil`` davon. Das Ergebnis wird wie jeder
    Zuwachs auf ganze Kaufschritte abgerundet (GDD 9) - Bruchteile eines
    Schritts gibt es nicht.

    Null Tage bringen null; ein einzelner Tag kann bei kleinem
    ``tag_anteil`` ebenfalls auf null abrunden, und das ist richtig so:
    Wer einen Tag trainiert, hat noch nichts erreicht.
    """
    if tage <= 0:
        return 0
    einstellung = konfiguration.wert("zeitmodell", "training")
    schritt = konfiguration.wert("zeitmodell", "kaufschritt")
    je_tag = kern_entwicklung.tageszuwachs(konfiguration, wert) * einstellung["tag_anteil"]
    roh = int(tage * je_tag)
    return (roh // schritt) * schritt


def plane(
    konfiguration: Konfiguration,
    faehigkeit,
    wert: int,
    tage: int,
) -> kern_entwicklung.Entwicklung:
    """Was ein Programm ueber ``tage`` Tage braechte, ohne es zu buchen.

    Die Waehrungskosten sind dieselben wie bei der Einzelbuchung, nur auf
    den groesseren Zuwachs gerechnet: Wer mit Geld oder EP zahlt, zahlt
    je +10-Schritt, und ein Programm bringt eben mehrere Schritte.
    """
    if not kern_entwicklung.braucht_tag(faehigkeit):
        raise TrainingsFehler(
            f"{faehigkeit.schluessel} kostet keine Zeit - dafuer gibt es kein Programm"
        )
    kuerzeste, laengste = spanne(konfiguration)
    if not kuerzeste <= tage <= laengste:
        raise TrainingsFehler(
            f"Ein Programm dauert {kuerzeste} bis {laengste} Tage, nicht {tage}"
        )
    return _entwicklung(konfiguration, faehigkeit, wert, zuwachs(konfiguration, wert, tage))


def abrechnung(
    konfiguration: Konfiguration,
    faehigkeit,
    wert: int,
    geleistet: int,
) -> kern_entwicklung.Entwicklung:
    """Was ein abgebrochenes Programm nach ``geleistet`` Tagen auszahlt.

    Entscheidung des Auftraggebers: anteilig, was gelaufen ist. Einen
    Bonus fuers Durchhalten gibt es nicht, also ist die Abrechnung eines
    vollstaendig gelaufenen Programms dieselbe Rechnung wie ``plane`` -
    nur ohne die Pruefung der Spanne, denn ein Abbruch kann jederzeit
    kommen.
    """
    return _entwicklung(
        konfiguration, faehigkeit, wert, zuwachs(konfiguration, wert, geleistet)
    )


def _entwicklung(
    konfiguration: Konfiguration, faehigkeit, wert: int, gewinn: int
) -> kern_entwicklung.Entwicklung:
    """Dieselbe Rechnung wie in ``entwicklung``, nur mit fertigem Zuwachs.

    ``braucht_tag`` bleibt wahr: Ein Programm ist Zeit, auch wenn es die
    Tage anders verbraucht als die Einzelbuchung.
    """
    return kern_entwicklung.mit_zuwachs(konfiguration, faehigkeit, wert, gewinn)
