"""Zeitrechnung und Zeitanzeige.

Arbeitsregel: Zeiten werden intern ausschliesslich als ganze Millisekunden
(``int``) gefuehrt. Gleitkommazahlen kommen nur an den Raendern vor, wo aus
einer Interpolation eine Zeit entsteht; dort wird sofort gerundet.

Anzeigeformate laut GDD 4:
    unter einer Stunde      ``m:ss.mmm``
    ab einer Stunde         ``h:mm:ss.mmm``
    Rueckstand unter 60 s   ``s.mmm``
    Rueckstand ab 60 s      ``m:ss.mmm``
"""

from __future__ import annotations

import re
from functools import lru_cache

MS_JE_SEKUNDE = 1_000
MS_JE_MINUTE = 60 * MS_JE_SEKUNDE
MS_JE_STUNDE = 60 * MS_JE_MINUTE

_MUSTER_DAUER = re.compile(
    r"^(?:(?P<stunden>\d+):(?=\d{2}:))?"
    r"(?:(?P<minuten>\d{1,2}):)?"
    r"(?P<sekunden>\d{1,2})"
    r"(?:\.(?P<millisekunden>\d{1,3}))?$"
)


def zu_ms(sekunden: float) -> int:
    """Rechnet Sekunden in ganze Millisekunden um (kaufmaennisch gerundet)."""
    return int(round(sekunden * MS_JE_SEKUNDE))


def zerlege(ms: int) -> tuple[int, int, int, int]:
    """Zerlegt Millisekunden in (Stunden, Minuten, Sekunden, Millisekunden).

    Erwartet einen nicht negativen Wert; das Vorzeichen behandeln die
    aufrufenden Formatierer.
    """
    if ms < 0:
        raise ValueError("zerlege erwartet einen nicht negativen Wert")
    stunden, rest = divmod(int(ms), MS_JE_STUNDE)
    minuten, rest = divmod(rest, MS_JE_MINUTE)
    sekunden, millisekunden = divmod(rest, MS_JE_SEKUNDE)
    return stunden, minuten, sekunden, millisekunden


@lru_cache(maxsize=4096)
def formatiere_dauer(ms: int) -> str:
    """Formatiert eine Dauer als ``m:ss.mmm`` bzw. ab einer Stunde ``h:mm:ss.mmm``.

    Gepuffert (D5): Die Rennanzeige ruft das in jedem Bild rund
    hundertsiebzig Mal auf, und die meisten Werte sind dieselben wie im
    Bild davor - die beste Runde eines Fahrers aendert sich alle
    hundertzehn Sekunden, die Anzeige fuenfmal je Sekunde. Die Funktion
    haengt nur von ihrem Argument ab, also ist der Puffer immer richtig.

    >>> formatiere_dauer(83_456)
    '1:23.456'
    >>> formatiere_dauer(3_723_004)
    '1:02:03.004'
    """
    vorzeichen = "-" if ms < 0 else ""
    stunden, minuten, sekunden, millis = zerlege(abs(int(ms)))
    if stunden:
        return f"{vorzeichen}{stunden}:{minuten:02d}:{sekunden:02d}.{millis:03d}"
    return f"{vorzeichen}{minuten}:{sekunden:02d}.{millis:03d}"


def formatiere_rueckstand(ms: int, *, mit_vorzeichen: bool = True) -> str:
    """Formatiert einen Rueckstand oder eine Differenz fuer die Seitenleiste.

    Unter 60 Sekunden als ``s.mmm``, ab 60 Sekunden als ``m:ss.mmm``, ab einer
    Stunde als ``h:mm:ss.mmm``. Mit ``mit_vorzeichen`` wird ein ``+`` bzw. ``-``
    vorangestellt, wie es Seitenleiste und Sektorvergleich zeigen.

    >>> formatiere_rueckstand(512)
    '+0.512'
    >>> formatiere_rueckstand(61_004)
    '+1:01.004'
    >>> formatiere_rueckstand(-312)
    '-0.312'
    """
    betrag = abs(int(ms))
    if ms < 0:
        zeichen = "-"
    elif mit_vorzeichen:
        zeichen = "+"
    else:
        zeichen = ""

    if betrag < MS_JE_MINUTE:
        sekunden, millis = divmod(betrag, MS_JE_SEKUNDE)
        return f"{zeichen}{sekunden}.{millis:03d}"
    return f"{zeichen}{formatiere_dauer(betrag)}"


def formatiere_runden_rueckstand(runden: int) -> str:
    """Formatiert den Rueckstand Ueberrundeter als ``+n Rd.`` (GDD 4).

    >>> formatiere_runden_rueckstand(1)
    '+1 Rd.'
    """
    if runden < 1:
        raise ValueError("Ein Rundenrueckstand ist mindestens eine Runde")
    return f"+{runden} Rd."


def lies_dauer(text: str) -> int:
    """Liest ``m:ss.mmm`` oder ``h:mm:ss.mmm`` zurueck in Millisekunden.

    Gegenstueck zu :func:`formatiere_dauer`, vor allem fuer Tests und die
    Eingabe von Vergleichszeiten in der Debug-Ansicht.

    >>> lies_dauer('1:23.456')
    83456
    >>> lies_dauer('1:02:03.004')
    3723004
    """
    roh = text.strip()
    negativ = roh.startswith("-")
    if negativ or roh.startswith("+"):
        roh = roh[1:]

    treffer = _MUSTER_DAUER.match(roh)
    if treffer is None:
        raise ValueError(f"Unlesbare Zeitangabe: {text!r}")

    stunden = int(treffer.group("stunden") or 0)
    minuten = int(treffer.group("minuten") or 0)
    sekunden = int(treffer.group("sekunden"))
    millis_text = treffer.group("millisekunden") or "0"
    millis = int(millis_text.ljust(3, "0"))

    if minuten > 59 and stunden:
        raise ValueError(f"Minutenanteil ausserhalb 0-59: {text!r}")
    if sekunden > 59 and (minuten or stunden):
        raise ValueError(f"Sekundenanteil ausserhalb 0-59: {text!r}")

    gesamt = stunden * MS_JE_STUNDE + minuten * MS_JE_MINUTE
    gesamt += sekunden * MS_JE_SEKUNDE + millis
    return -gesamt if negativ else gesamt
