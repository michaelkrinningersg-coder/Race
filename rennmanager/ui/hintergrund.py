"""Rechnen, ohne dass die Oberflaeche stehenbleibt (E10).

Ein Rennen zu rechnen kostet gemessen 47 Sekunden (Zandvoort, 40 Autos,
40 Runden). Bisher lief das im Oberflaechen-Thread: Der Knopf ging aus,
der Mauszeiger wurde zur Sanduhr, und das Fenster reagierte elf Sekunden
lang auf nichts. Ein Fenster, das nicht reagiert, sieht abgestuerzt aus -
auch wenn es fleissig rechnet.

Hier laeuft dieselbe Rechnung in einem eigenen Thread und meldet
unterwegs, wie weit sie ist. Schneller wird sie davon nicht; sie fuehlt
sich nur nicht mehr wie ein Haenger an.

**Der Kern bleibt, wo er ist.** Der Thread ruft nur eine Funktion auf, die
er uebergeben bekommt, und reicht ihr einen Melder durch. Nichts hier
weiss, was ein Rennen ist.

**Der Arbeitsfaden fasst keine Widgets an.** Er meldet ueber Signale;
Qt stellt sie in die Schlange des Hauptthreads. Alles andere waere ein
Absturz, der erst beim Kunden auftritt.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class Rechenlauf(QThread):
    """Fuehrt eine Rechnung im Hintergrund aus.

    :param arbeit: bekommt einen Melder ``(getan, gesamt) -> None`` und
        gibt zurueck, was am Ende gebraucht wird
    """

    #: (getan, gesamt) - was die Rechnung gerade meldet
    fortschritt = Signal(int, int)
    #: das Ergebnis von ``arbeit``
    fertig = Signal(object)
    #: die Meldung eines Fehlers samt Rueckverfolgung
    fehlgeschlagen = Signal(str, str)

    def __init__(self, arbeit: Callable[[Callable[[int, int], None]], object], parent=None):
        super().__init__(parent)
        self._arbeit = arbeit
        self._ergebnis: object = None

    @property
    def ergebnis(self) -> object:
        """Was die Rechnung geliefert hat, oder ``None``."""
        return self._ergebnis

    def run(self) -> None:  # noqa: D102 - Qt-Name
        try:
            self._ergebnis = self._arbeit(self._melde)
        except Exception as fehler:  # noqa: BLE001 - alles muss ankommen
            # Ein Fehler im Arbeitsfaden darf nicht still verschwinden.
            # Ohne das stuende die Oberflaeche ewig auf "rechnet".
            self.fehlgeschlagen.emit(str(fehler), traceback.format_exc())
            return
        self.fertig.emit(self._ergebnis)

    def _melde(self, getan: int, gesamt: int) -> None:
        self.fortschritt.emit(int(getan), int(gesamt))
