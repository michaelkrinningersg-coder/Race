"""Zeitmodell, Upgrades und Kosten (GDD 2 und 9).

Jede Faehigkeit hat einen festen Waehrungstyp: Geld (G), Erfahrung (E),
Zeit (Z) oder eine Kombination. Daraus folgt, wie sie steigt:

==================  =========================================================
Reine Zeit (Z)      Ein zugewiesener Tag hebt den Wert kostenlos um
                    ``max(+10, +1 %)``.
Zeit + Geld/EP      Der Tag schaltet denselben Zuwachs frei; Geld und EP
                    werden zusaetzlich je +10-Schritt bezahlt.
Nur Geld/EP         Sofort kaufbar, braucht keinen Tag.
==================  =========================================================

Gekauft wird immer in +10-Schritten, nie mehrfach auf einmal (GDD 9). Ein
Schritt ab Wert S kostet

    K(S) = K0 * faktor * (1 + S / 1000) ^ 0,6

Der Faktor je Faehigkeit folgt ihrer Wirkungsbreite: die Summe ihrer
Gewichte aus der Wirkungsmatrix, geteilt durch den Mittelwert ueber alle
Faehigkeiten. Breit wirkende Faehigkeiten kosten mehr, damit Schwerpunkte
noetig werden (GDD 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Faehigkeit, Konfiguration

GELD = "G"
ERFAHRUNG = "E"
ZEIT = "Z"


class EntwicklungsFehler(Exception):
    """Ein Kauf oder eine Tageszuweisung ist so nicht moeglich."""


@dataclass(frozen=True)
class Konto:
    """Der Vorrat des Spielers (GDD 10).

    Es gibt keine laufenden Kosten, keine Schulden und keinen Bankrott -
    ohne Geld kann man nur nichts ausgeben.
    """

    geld: int = 0
    erfahrung: int = 0
    # Eigener Topf je Wetter, nur fuer die passende Wetterfaehigkeit
    # nutzbar (GDD 10).
    wetter_erfahrung: dict[str, int] = field(default_factory=dict)

    def wetter_topf(self, wetter: str) -> int:
        return self.wetter_erfahrung.get(wetter, 0)

    def mit(self, geld: int = 0, erfahrung: int = 0, **wetter: int) -> Konto:
        """Liefert ein Konto mit veraenderten Bestaenden."""
        toepfe = dict(self.wetter_erfahrung)
        for name, betrag in wetter.items():
            toepfe[name] = toepfe.get(name, 0) + betrag
        return Konto(
            geld=self.geld + geld,
            erfahrung=self.erfahrung + erfahrung,
            wetter_erfahrung=toepfe,
        )


@dataclass(frozen=True)
class Entwicklung:
    """Was ein Tagesplatz oder ein Kauf bewirkt."""

    faehigkeit: str
    von: int
    nach: int
    geld: int
    erfahrung: int
    braucht_tag: bool
    # Bei Wetterfaehigkeiten: aus welchem Topf die Erfahrung kommt.
    wettertopf: str | None = None

    @property
    def zuwachs(self) -> int:
        return self.nach - self.von


# ---------------------------------------------------------------------------
# Zeitmodell
# ---------------------------------------------------------------------------
def tageszuwachs(konfiguration: Konfiguration, wert: int) -> int:
    """Wie weit ein zugewiesener Tag einen Wert hebt (GDD 2).

    ``max(+10, +1 % des aktuellen Werts)``, auf ganze Kaufschritte
    abgerundet - gekauft wird nur in +10-Schritten (GDD 9).
    """
    absolut = konfiguration.wert("zeitmodell", "schritt_absolut")
    anteil = konfiguration.wert("zeitmodell", "schritt_anteil")
    schritt = konfiguration.wert("zeitmodell", "kaufschritt")
    roh = max(absolut, int(wert * anteil))
    return max(schritt, (roh // schritt) * schritt)


def braucht_tag(faehigkeit: Faehigkeit) -> bool:
    """Ob die Faehigkeit einen Kalendertag verbraucht (GDD 2)."""
    return ZEIT in faehigkeit.waehrung


def ist_fahrertraining(faehigkeit: Faehigkeit) -> bool:
    """Fahrer-Eigenschaften belegen den Trainingsplatz, Upgrades die Werkstatt.

    GDD 2: "Jeder Tag hat zwei parallele Plaetze: einen fuer den Fahrer
    (Training) und einen fuer die Werkstatt (Entwicklung)."
    """
    return not faehigkeit.ist_fahrzeug


# ---------------------------------------------------------------------------
# Kosten
# ---------------------------------------------------------------------------
@cache
def _gewichtssummen(konfiguration: Konfiguration) -> tuple[dict[str, int], float]:
    summen = {
        f.schluessel: sum(f.gewichte.values()) for f in konfiguration.faehigkeiten
    }
    return summen, sum(summen.values()) / len(summen)


def k0_faktor(konfiguration: Konfiguration, faehigkeit: Faehigkeit) -> float:
    """Kostenfaktor einer Faehigkeit aus ihrer Wirkungsbreite (GDD 9).

    Entscheidung zu Punkt 17: die Summe der Gewichte aus der
    Wirkungsmatrix, geteilt durch den Mittelwert. Faehigkeiten ausserhalb
    der Matrix - die Wetterfaehigkeiten und der Reifenfluesterer - haben
    keine Gewichte und bekommen den Faktor 1.
    """
    if konfiguration.wert("kosten", "k0_faktor", "verfahren") != "wirkungsbreite":
        raise EntwicklungsFehler("Nur das Verfahren 'wirkungsbreite' ist umgesetzt")
    return konfiguration.k0_faktoren.get(faehigkeit.schluessel, 1.0)


def schrittkosten(
    konfiguration: Konfiguration, faehigkeit: Faehigkeit, wert: int
) -> tuple[int, int]:
    """Kosten eines einzelnen +10-Schritts ab ``wert``.

    :return: (Geld in Euro, Erfahrung in EP); nicht geforderte Waehrungen
        sind 0
    """
    einstellung = konfiguration.wert("kosten")
    grundkurve = (1.0 + wert / einstellung["teiler"]) ** einstellung["exponent"]
    faktor = k0_faktor(konfiguration, faehigkeit) * grundkurve

    geld = round(einstellung["k0_geld"] * faktor) if GELD in faehigkeit.waehrung else 0
    if ERFAHRUNG in faehigkeit.waehrung:
        erfahrung = round(einstellung["k0_erfahrung"] * faktor)
    elif ZEIT in faehigkeit.waehrung:
        # Ein belegter Tag kostet zusaetzlich etwas Erfahrung. Die Zeit
        # bleibt ein Tag und skaliert nicht; die Erfahrung waechst ueber
        # dieselbe Kurve mit jedem Kauf.
        erfahrung = round(einstellung["k0_erfahrung_zeit"] * faktor)
    else:
        erfahrung = 0
    return int(geld), int(erfahrung)


def kosten_bis(konfiguration: Konfiguration, faehigkeit: Faehigkeit, ziel: int) -> tuple[int, int]:
    """Summe aller Schritte von 0 bis ``ziel`` - fuer Anzeige und Planung."""
    schritt = konfiguration.wert("zeitmodell", "kaufschritt")
    geld = erfahrung = 0
    for wert in range(0, ziel, schritt):
        einzeln = schrittkosten(konfiguration, faehigkeit, wert)
        geld += einzeln[0]
        erfahrung += einzeln[1]
    return geld, erfahrung


# ---------------------------------------------------------------------------
# Planen und buchen
# ---------------------------------------------------------------------------
def plane_tag(
    konfiguration: Konfiguration, faehigkeit: Faehigkeit, wert: int
) -> Entwicklung:
    """Was ein zugewiesener Tag bei dieser Faehigkeit bringt (GDD 2)."""
    if not braucht_tag(faehigkeit):
        raise EntwicklungsFehler(
            f"{faehigkeit.schluessel} kostet keine Zeit und ist sofort kaufbar"
        )
    zuwachs = tageszuwachs(konfiguration, wert)
    return _entwicklung(konfiguration, faehigkeit, wert, zuwachs, braucht_tag=True)


def plane_kauf(
    konfiguration: Konfiguration, faehigkeit: Faehigkeit, wert: int, schritte: int = 1
) -> Entwicklung:
    """Ein Sofortkauf ohne Tag - nur fuer reine Geld- und EP-Faehigkeiten."""
    if braucht_tag(faehigkeit):
        raise EntwicklungsFehler(
            f"{faehigkeit.schluessel} braucht einen Tag und ist nicht sofort kaufbar"
        )
    if schritte < 1:
        raise EntwicklungsFehler("Mindestens ein Schritt")
    schritt = konfiguration.wert("zeitmodell", "kaufschritt")
    return _entwicklung(
        konfiguration, faehigkeit, wert, schritte * schritt, braucht_tag=False
    )


def _entwicklung(
    konfiguration: Konfiguration,
    faehigkeit: Faehigkeit,
    wert: int,
    zuwachs: int,
    braucht_tag: bool,
) -> Entwicklung:
    groesster = konfiguration.wert("skala", "maximum")
    if wert >= groesster:
        raise EntwicklungsFehler(f"{faehigkeit.schluessel} ist bereits am Maximum")

    schritt = konfiguration.wert("zeitmodell", "kaufschritt")
    ziel = min(wert + zuwachs, groesster)
    geld = erfahrung = 0
    for stelle in range(wert, ziel, schritt):
        einzeln = schrittkosten(konfiguration, faehigkeit, stelle)
        geld += einzeln[0]
        erfahrung += einzeln[1]

    return Entwicklung(
        faehigkeit=faehigkeit.schluessel,
        von=wert,
        nach=ziel,
        geld=geld,
        erfahrung=erfahrung,
        braucht_tag=braucht_tag,
    )


def ist_bezahlbar(konto: Konto, entwicklung: Entwicklung) -> bool:
    """GDD 10: keine Schulden - was nicht da ist, wird nicht ausgegeben."""
    if entwicklung.wettertopf is not None:
        return (
            konto.geld >= entwicklung.geld
            and konto.wetter_topf(entwicklung.wettertopf) >= entwicklung.erfahrung
        )
    return konto.geld >= entwicklung.geld and konto.erfahrung >= entwicklung.erfahrung


def buche(konto: Konto, entwicklung: Entwicklung) -> Konto:
    """Zieht die Kosten ab; wirft, wenn der Vorrat nicht reicht."""
    if not ist_bezahlbar(konto, entwicklung):
        raise EntwicklungsFehler(
            f"{entwicklung.faehigkeit}: {entwicklung.geld} EUR und "
            f"{entwicklung.erfahrung} EP sind nicht gedeckt"
        )
    if entwicklung.wettertopf is not None:
        return konto.mit(
            geld=-entwicklung.geld, **{entwicklung.wettertopf: -entwicklung.erfahrung}
        )
    return konto.mit(geld=-entwicklung.geld, erfahrung=-entwicklung.erfahrung)


def als_wettertopf(entwicklung: Entwicklung, wetter: str) -> Entwicklung:
    """Markiert eine Entwicklung als aus einem Wettertopf bezahlt (GDD 10)."""
    return replace(entwicklung, wettertopf=wetter)
