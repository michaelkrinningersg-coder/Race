"""Charakterprofil eines Fahrers in einem Satz (Punkt 32).

38 Zahlen sagen alles und zeigen nichts. Dieses Modul macht daraus einen
Satz: *woran* ein Fahrer stark ist, woran er schwach ist, und was ihn
ausserhalb der Wirkungsmatrix auszeichnet.

**Keine neue Mechanik.** Hier entsteht kein Wert, der irgendwo wirkt -
gelesen wird nur, was schon da ist: die elf Wirkungsbereiche aus GDD 8 und
die Eigenschaften daneben. Das Profil ist eine Beschreibung, kein
Spielelement.

Gemessen wird gegen den eigenen Durchschnitt, nicht gegen die Skala: Ein
Fahrer aus Liga 20 hat lauter niedrige Werte und trotzdem ein Profil.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rennmanager.kern.auto import Auto, bereichswerte, gesamtwert

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Ab welcher Abweichung vom eigenen Mittel ein Bereich genannt wird.
SCHWELLE = 0.06
# So viele Staerken und Schwaechen nennt der Satz hoechstens.
HOECHSTENS = 2


def _abweichungen(konfiguration: Konfiguration, auto: Auto) -> dict[str, float]:
    """Jeder Wirkungsbereich als Abweichung vom eigenen Mittel."""
    bereiche = bereichswerte(konfiguration, auto)
    mittel = sum(bereiche.values()) / len(bereiche) if bereiche else 0.0
    if mittel <= 0.0:
        return dict.fromkeys(bereiche, 0.0)
    return {bereich: wert / mittel - 1.0 for bereich, wert in bereiche.items()}


def staerken(konfiguration: Konfiguration, auto: Auto) -> tuple[str, ...]:
    """Die Bereiche, in denen dieser Fahrer ueber seinem Mittel liegt."""
    bezeichnung = konfiguration.wert("wirkungsmatrix", "bezeichnung")
    geordnet = sorted(
        _abweichungen(konfiguration, auto).items(), key=lambda paar: -paar[1]
    )
    return tuple(
        bezeichnung.get(bereich, bereich)
        for bereich, abweichung in geordnet[:HOECHSTENS]
        if abweichung >= SCHWELLE
    )


def schwaechen(konfiguration: Konfiguration, auto: Auto) -> tuple[str, ...]:
    """Die Bereiche, in denen dieser Fahrer unter seinem Mittel liegt."""
    bezeichnung = konfiguration.wert("wirkungsmatrix", "bezeichnung")
    geordnet = sorted(
        _abweichungen(konfiguration, auto).items(), key=lambda paar: paar[1]
    )
    return tuple(
        bezeichnung.get(bereich, bereich)
        for bereich, abweichung in geordnet[:HOECHSTENS]
        if abweichung <= -SCHWELLE
    )


def besondere(konfiguration: Konfiguration, auto: Auto) -> tuple[str, ...]:
    """Eigenschaften neben der Matrix, die deutlich ueber dem Mittel liegen.

    Wetterkoennen, Reifenfluesterer und die fuenf aus Punkt 48 - das, was
    einen Fahrer jenseits der reinen Rundenzeit auszeichnet.
    """
    if not auto.wetterwerte:
        return ()
    mittel = sum(auto.wetterwerte.values()) / len(auto.wetterwerte)
    if mittel <= 0.0:
        return ()
    namen = {
        eintrag["schluessel"]: eintrag.get("name", eintrag["schluessel"])
        for eintrag in konfiguration.zusatzeintraege
    }
    geordnet = sorted(auto.wetterwerte.items(), key=lambda paar: -paar[1])
    return tuple(
        namen.get(schluessel, schluessel)
        for schluessel, wert in geordnet[:HOECHSTENS]
        if wert / mittel - 1.0 >= SCHWELLE
    )


def profil(konfiguration: Konfiguration, auto: Auto) -> str:
    """Ein Satz, der diesen Fahrer beschreibt.

    Leer bleibt er nur bei einem Fahrer, der ueberall gleich ist - beim
    Spieler am ersten Tag zum Beispiel, der laut GDD 1 auf lauter Nullen
    steht.
    """
    teile = []
    stark = staerken(konfiguration, auto)
    schwach = schwaechen(konfiguration, auto)
    extra = besondere(konfiguration, auto)

    if stark:
        teile.append("stark in " + " und ".join(stark))
    if schwach:
        teile.append("schwach in " + " und ".join(schwach))
    if extra:
        teile.append("dazu " + " und ".join(extra))

    if not teile:
        if gesamtwert(konfiguration, auto) <= 0:
            return "Noch kein Profil - alle Werte stehen auf 0 (GDD 1)."
        return "Ausgeglichen, ohne ausgepraegte Staerken oder Schwaechen."
    satz = ", ".join(teile)
    # Nur der erste Buchstabe gross: ``capitalize`` machte aus
    # "Bremsanlage" ein "bremsanlage".
    return satz[0].upper() + satz[1:] + "."
