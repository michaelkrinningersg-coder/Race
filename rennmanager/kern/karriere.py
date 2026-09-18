"""Karrierestand: Kalender, Konto, Werte und Vertraege (GDD 2, 9 und 10).

Fasst zusammen, was der Spieler zwischen zwei Rennen tut: Tage
weiterschalten, Trainings- und Werkstattplaetze belegen, Upgrades kaufen
und Sponsorenvertraege abschliessen.

Zeit ist dabei eine Kapazitaet (GDD 2): Jeder nutzbare Tag hat zwei
Plaetze, einen fuer den Fahrer und einen fuer die Werkstatt. Ein Tag, der
vorbei ist, ohne belegt zu sein, ist verloren.

Seit Schritt 10 haengen drei weitere Zustaende an der Karriere:

* die **Ereignisse** aus GDD 14, die beim Tageswechsel ausgeloest werden
  und Werte zeitweise oder dauerhaft veraendern,
* die **offenen Defekte** aus GDD 14, die nach dem Rennen bestehen
  bleiben, bis der Spieler sie bezahlt,
* die **Streckenkenntnis** aus GDD 6, die mit jeder gefahrenen Runde
  waechst.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from rennmanager.kern import einnahmen as kern_einnahmen
from rennmanager.kern import entwicklung as kern_entwicklung
from rennmanager.kern import ereignis as kern_ereignis
from rennmanager.kern import kalender as kern_kalender
from rennmanager.kern import kassenbuch as kern_kassenbuch
from rennmanager.kern import sponsoren as kern_sponsoren
from rennmanager.kern import streckenkenntnis as kern_streckenkenntnis
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.entwicklung import Konto
from rennmanager.kern.kalender import Saison, Tagesart
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

FAHRERPLATZ = "fahrer"
WERKSTATTPLATZ = "werkstatt"


class KarriereFehler(Exception):
    """Die Aktion ist an diesem Tag oder mit diesem Vorrat nicht moeglich."""


@dataclass(frozen=True)
class Meldung:
    """Was an einem Tag passiert ist - fuer die Anzeige (GDD 14)."""

    datum: dt.date
    schluessel: str
    name: str
    text: str
    geld: int = 0
    erfahrung: int = 0
    # Punkt 56: Wen es getroffen hat. 0 heisst: das ganze Team - das gibt
    # es seit Punkt 56 nicht mehr, alte Staende koennen es aber noch
    # tragen.
    fahrer: int = 0
    fahrername: str = ""

    @property
    def zeile(self) -> str:
        wen = self.fahrername or (f"Fahrer {self.fahrer}" if self.fahrer else "")
        teile = [f"{self.schluessel} {self.name}"]
        if wen:
            teile.append(wen)
        teile.append(self.text)
        if self.geld:
            teile.append(f"{self.geld:+,} EUR".replace(",", "."))
        if self.erfahrung:
            teile.append(f"{self.erfahrung:+,} EP".replace(",", "."))
        return " - ".join(teil for teil in teile if teil)


@dataclass(frozen=True)
class Tagesbuchung:
    """Was an einem Tag auf welchem Platz gearbeitet wurde."""

    datum: dt.date
    platz: str
    faehigkeit: str
    von: int
    nach: int
    geld: int
    erfahrung: int


@dataclass
class Karriere:
    """Der Stand einer Karriere - jetzt die eines ganzen Teams.

    **Jedes Auto gehoert seinem Fahrer**, nicht dem Team (Entscheidung
    des Auftraggebers). Die Karriere fuehrt deshalb je Fahrernummer einen
    eigenen Satz Werte; entwickelt wird jedes Auto einzeln. Geht ein
    Fahrer, geht sein Auto mit: Der Nachfolger bringt ein leeres,
    nicht upgegradetes Auto mit (siehe ``fahrer_geht``).

    Was dem **Team** gehoert und nicht dem einzelnen Auto: Konto,
    Sponsorenvertraege, Kalender und die Ereignisse der Saison.

    :param autos: je Fahrernummer die Werte seines Autos - die 32 aus der
        Wirkungsmatrix und die Zusatzfaehigkeiten aus GDD 7 und dem
        Reifenfluesterer
    """

    konfiguration: Konfiguration
    saison: Saison
    heute: dt.date
    liga: int
    konto: Konto
    autos: dict[int, dict[str, int]]
    # Sponsoren sitzen auf den Plaetzen **eines** Autos (GDD 10). Jedes
    # Auto gehoert seinem Fahrer, also traegt jeder seine eigenen.
    vertraege_je_fahrer: dict[int, dict[str, kern_sponsoren.Vertrag]] = field(
        default_factory=dict
    )
    buchungen: list[Tagesbuchung] = field(default_factory=list)
    # Belegte Plaetze des laufenden Tages, je Fahrer: An einem Tag wird
    # an **einem** Auto gearbeitet, und jedes hat seine eigenen Plaetze.
    belegte_plaetze: dict[int, set[str]] = field(default_factory=dict)
    # Punkt 72: Jede Geldbewegung wird mitgeschrieben, damit die
    # Finanzseite nach Kategorien gruppieren kann. Das Konto kennt nur
    # den Stand, nicht die Herkunft.
    kassenbuch: kern_kassenbuch.Kassenbuch = field(
        default_factory=kern_kassenbuch.Kassenbuch
    )
    # Das Teambudget des Spielers; es zahlt sich in Monatsraten aus.
    # 0 heisst: kein Budget, also keine Raten (so laufen alte Staende und
    # Tests, die nur die Entwicklung pruefen).
    teambudget: int = 0
    # Der Monat, fuer den zuletzt eine Rate gebucht wurde - damit ein
    # Tageswechsel ueber mehrere Monate keine Rate verschluckt und ein
    # zweiter Blick auf denselben Tag keine doppelt bucht.
    letzte_rate: tuple[int, int] | None = None

    # -- Schritt 10 --------------------------------------------------------
    # Die Ereignisse der Saison, einmal beim Start gewuerfelt (GDD 14).
    ereignisplan: dict[dt.date, tuple[str, ...]] = field(default_factory=dict)
    # Punkt 56: Ereignisse treffen **einzelne Fahrer**, nicht das ganze
    # Team. Eine Erkaeltung hat einer, nicht alle vier; ein
    # Motivationsschub genauso. Jeder fuehrt deshalb seine eigene Lage.
    lage_je_fahrer: dict[int, kern_ereignis.Lage] = field(default_factory=dict)
    # Die Seedquelle der Saison. Sie wuerfelt, wen ein Ereignis trifft -
    # aus derselben Quelle wie der Ereignisplan, damit derselbe Seed
    # dieselbe Saison ergibt (GDD 15). Ohne sie laeuft die Karriere ohne
    # Ereignisse, und dann gibt es auch nichts zu wuerfeln.
    seedquelle: Seedquelle | None = None
    # Die Namen der eigenen Fahrer, nur fuer die Anzeige der Meldungen.
    # Der Kern kennt sonst nur Nummern; die Namen stehen in der Welt.
    fahrernamen: dict[int, str] = field(default_factory=dict)
    # Defekte, die aus einem Rennen offen geblieben sind (GDD 14).
    defekte: list[dict] = field(default_factory=list)
    # Tage, die E29 Reisechaos gekostet hat.
    verlorene_tage: set[dt.date] = field(default_factory=set)
    meldungen: list[Meldung] = field(default_factory=list)
    kenntnis: kern_streckenkenntnis.Streckenkenntnis | None = None
    # Nummer des Fahrers in der Welt - fuer die Streckenkenntnis.
    fahrernummer: int = 0
    # Punkt 7: Was der Chef seinen Fahrern zahlt, je Fahrer Gehalt je
    # Saison und Restlaufzeit in Saisons. Wer hier fehlt, faehrt zum
    # Nulltarif - das sind die vier, mit denen das Spiel beginnt.
    fahrervertraege: dict[int, tuple[int, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kenntnis is None:
            self.kenntnis = kern_streckenkenntnis.Streckenkenntnis(self.konfiguration)
        if self.fahrernummer not in self.autos:
            self.autos[self.fahrernummer] = leere_werte(self.konfiguration)

    # -- Der gewaehlte Fahrer ----------------------------------------------
    # Entwickelt, trainiert und gebucht wird immer an **einem** Auto. Wer
    # gerade dran ist, steht in ``fahrernummer``; ``werte`` und ``belegt``
    # sind die Sicht darauf. So bleibt alles, was mit einem Auto arbeitet,
    # unveraendert - es sieht nur den gewaehlten.
    @property
    def werte(self) -> dict[str, int]:
        """Die Werte des gewaehlten Fahrers - aenderbar, kein Abbild."""
        return self.autos.setdefault(
            self.fahrernummer, leere_werte(self.konfiguration)
        )

    @property
    def lage(self) -> kern_ereignis.Lage:
        """Die Ereignislage des gewaehlten Fahrers (Punkt 56).

        Wie ``werte`` und ``vertraege`` eine Sicht auf den einen Fahrer,
        an dem gerade gearbeitet oder gerechnet wird. Wer einen Fahrer
        aufs Rennen schickt, bekommt damit auch nur dessen Ereignisse.
        """
        return self.lage_je_fahrer.setdefault(
            self.fahrernummer, kern_ereignis.Lage(self.konfiguration)
        )

    @property
    def alle_lagen(self) -> tuple[kern_ereignis.Lage, ...]:
        """Die Lagen aller eigenen Fahrer - fuers Weiterzaehlen."""
        for nummer in self.autos:
            self.lage_je_fahrer.setdefault(nummer, kern_ereignis.Lage(self.konfiguration))
        return tuple(self.lage_je_fahrer[nummer] for nummer in sorted(self.autos))

    @property
    def belegt(self) -> set[str]:
        """Die belegten Plaetze des gewaehlten Fahrers (Punkt 69).

        Wer einen Platz mit Zeit belegt, hat ihn **bis zum naechsten
        Rennen** belegt, nicht nur fuer heute: Ein Umbau am Auto oder ein
        Trainingsblock laeuft ueber den ganzen Abstand zwischen zwei
        Rennen. Erst der Renntag gibt die Plaetze wieder frei.
        """
        return self.belegte_plaetze.setdefault(self.fahrernummer, set())

    @property
    def vertraege(self) -> dict[str, kern_sponsoren.Vertrag]:
        """Die Sponsorenvertraege auf dem Auto des gewaehlten Fahrers."""
        return self.vertraege_je_fahrer.setdefault(self.fahrernummer, {})

    @vertraege.setter
    def vertraege(self, neue: dict[str, kern_sponsoren.Vertrag]) -> None:
        self.vertraege_je_fahrer[self.fahrernummer] = neue

    @property
    def fahrer(self) -> tuple[int, ...]:
        """Die Fahrernummern, fuer die das Team ein Auto fuehrt."""
        return tuple(sorted(self.autos))

    def waehle_fahrer(self, nummer: int) -> None:
        """Stellt auf einen anderen eigenen Fahrer um."""
        if nummer not in self.autos:
            raise KarriereFehler(f"Fahrer {nummer} gehoert nicht zum Team")
        self.fahrernummer = nummer

    def werte_von(self, nummer: int) -> dict[str, int]:
        """Die Werte eines bestimmten eigenen Fahrers."""
        if nummer not in self.autos:
            raise KarriereFehler(f"Fahrer {nummer} gehoert nicht zum Team")
        return self.autos[nummer]

    def fahrer_geht(self, nummer: int, nachfolger: int | None = None) -> None:
        """Ein Fahrer hoert auf; sein Auto geht mit.

        Der Auftraggeber hat entschieden: Ein neuer Fahrer bringt ein
        **leeres, nicht upgegradetes** Auto mit. Alles, was der Chef in
        das alte Auto investiert hat, ist damit weg - Fahrer zu halten
        hat einen Preis, und ein Wechsel kostet mehr als das Gehalt.
        """
        self.autos.pop(nummer, None)
        self.belegte_plaetze.pop(nummer, None)
        # Die Sponsoren sassen auf seinem Auto - auch sie gehen mit.
        self.vertraege_je_fahrer.pop(nummer, None)
        self.fahrervertraege.pop(nummer, None)
        self.defekte = [d for d in self.defekte if d.get("fahrer", nummer) != nummer]
        if nachfolger is not None:
            self.autos[nachfolger] = leere_werte(self.konfiguration)
            self.belegte_plaetze[nachfolger] = set()
        if self.fahrernummer == nummer:
            self.fahrernummer = nachfolger if nachfolger is not None else (
                self.fahrer[0] if self.fahrer else 0
            )

    # -- Kalender ----------------------------------------------------------
    @property
    def tag(self) -> kern_kalender.Kalendertag:
        return self.saison.tag(self.heute)

    @property
    def naechstes_rennen(self) -> dt.date | None:
        return self.saison.naechster_renntag(self.heute)

    @property
    def tage_bis_zum_rennen(self) -> int | None:
        ziel = self.naechstes_rennen
        return (ziel - self.heute).days if ziel else None

    @property
    def offene_tage(self) -> int:
        """Nutzbare Tage bis zum naechsten Rennen, heute eingeschlossen.

        Tage, die E29 Reisechaos gekostet hat, zaehlen nicht mit (GDD 14).
        """
        ziel = self.naechstes_rennen
        if ziel is None:
            ziel = self.saison.tage[-1].datum
        return len(
            [
                tag
                for tag in self.saison.nutzbare_tage(self.heute, ziel)
                if tag.datum not in self.verlorene_tage
            ]
        )

    @property
    def heute_nutzbar(self) -> bool:
        """Ob heute gearbeitet werden kann (GDD 2 und 14)."""
        return self.tag.ist_nutzbar and self.heute not in self.verlorene_tage

    def tag_weiter(self) -> kern_kalender.Kalendertag:
        """Schaltet einen Tag weiter und loest Ereignisse aus (GDD 2 und 14)."""
        naechster = self.heute + dt.timedelta(days=1)
        if naechster > self.saison.tage[-1].datum:
            raise KarriereFehler("Die Saison ist zu Ende")

        vorher = kern_ereignis.zyklusnummer(self.konfiguration, self.saison, self.heute)
        war_renntag = self.tag.art is Tagesart.RENNEN
        self.heute = naechster
        self.zahle_monatsrate()
        # Die belegten Plaetze bleiben bis zum naechsten Rennen belegt
        # (Punkt 69) - erst danach steht wieder ein Platz zur Verfuegung.
        if war_renntag:
            self.belegte_plaetze.clear()
        if kern_ereignis.zyklusnummer(self.konfiguration, self.saison, naechster) != vorher:
            # Punkt 56: Jeder Fahrer fuehrt seine eigene Lage - der Zyklus
            # zaehlt bei allen weiter.
            for lage in self.alle_lagen:
                lage.nach_zyklus()

        for schluessel in self.ereignisplan.get(naechster, ()):
            self._loese_ereignis_aus(schluessel)
        return self.tag

    # -- Ereignisse (GDD 14) -----------------------------------------------
    def benenne_fahrer(self, namen: dict[int, str]) -> None:
        """Gibt der Karriere die Namen ihrer Fahrer (Punkt 56).

        Der Kern kennt nur Nummern; die Namen stehen in der Welt. Sie
        werden gebraucht, damit eine Meldung sagen kann, **wen** ein
        Ereignis getroffen hat.

        Schon geschriebene Meldungen werden nachtraeglich benannt: Die
        ersten Ereignisse fallen auf den 1. Januar und entstehen damit
        beim Start der Karriere - also bevor die Oberflaeche die Namen
        reichen konnte.
        """
        self.fahrernamen = dict(namen)
        self.meldungen = [
            replace(m, fahrername=namen.get(m.fahrer, m.fahrername))
            if m.fahrer and not m.fahrername
            else m
            for m in self.meldungen
        ]

    def _waehle_betroffenen(self, schluessel: str) -> int:
        """Wen ein Ereignis trifft (Punkt 56).

        Nicht das ganze Team, sondern **einen** Fahrer. Gewuerfelt wird
        aus der Seedquelle, damit derselbe Seed dieselbe Saison ergibt
        (GDD 15); ohne Seedquelle - etwa in Tests, die nur die Entwicklung
        pruefen - trifft es den gerade gewaehlten Fahrer.
        """
        fahrer = sorted(self.autos)
        if len(fahrer) <= 1 or self.seedquelle is None:
            return self.fahrernummer
        wuerfel = self.seedquelle.zweig(
            "ereignistreffer", schluessel, self.heute.toordinal()
        ).generator()
        return fahrer[int(wuerfel.integers(0, len(fahrer)))]

    def _loese_ereignis_aus(self, schluessel: str) -> Meldung:
        """Startet ein Ereignis und verbucht, was sofort wirkt.

        Es trifft **einen** Fahrer (Punkt 56). Fuer die Dauer dieser
        Methode ist er der gewaehlte, damit ``lage`` und ``werte`` auf
        sein Auto zeigen.
        """
        e = kern_ereignis.eintrag(self.konfiguration, schluessel)
        vorher = self.fahrernummer
        betroffen = self._waehle_betroffenen(schluessel)
        self.fahrernummer = betroffen
        try:
            return self._loese_ereignis_aus_fuer(schluessel, e)
        finally:
            self.fahrernummer = vorher

    def _loese_ereignis_aus_fuer(self, schluessel: str, e: dict) -> Meldung:
        """Der eigentliche Ablauf, auf dem gewaehlten Fahrer."""
        aktiv = self.lage.loese_aus(schluessel, self.heute)

        geld = 0
        erfahrung = 0
        for wirkung in e["wirkung"]:
            ziel = wirkung["ziel"]
            if wirkung.get("einmalig"):
                anteil = kern_ereignis.betrag(self.konfiguration, schluessel)
                if ziel == kern_ereignis.GELD:
                    geld += int(
                        round(anteil * kern_einnahmen.siegpraemie(self.konfiguration, self.liga))
                    )
                else:
                    erfahrung += int(
                        round(
                            anteil * kern_einnahmen.sieg_erfahrung(self.konfiguration, self.liga)
                        )
                    )
            elif ziel == kern_ereignis.KALENDERTAGE:
                self._verliere_tage(-int(wirkung["absolut"]))
            elif kern_ereignis.ist_dauerhaft(e, wirkung) and ziel in self.werte:
                kleinster = self.konfiguration.wert("skala", "minimum")
                groesster = self.konfiguration.wert("skala", "maximum")
                neu_wert = self.werte[ziel] + kern_ereignis.dauerhafter_zuwachs(
                    self.konfiguration, self.werte[ziel], wirkung["faktor"]
                )
                self.werte[ziel] = min(max(neu_wert, kleinster), groesster)

        if geld or erfahrung:
            self.konto = self.konto.mit(geld=geld, erfahrung=erfahrung)
        if geld:
            self.kassenbuch.buche(
                self.heute, geld, kern_kassenbuch.EREIGNISSE,
                kern_kassenbuch.ZUSCHUSS if geld > 0 else kern_kassenbuch.STRAFE,
                text=aktiv.name,
            )

        meldung = Meldung(
            datum=self.heute,
            schluessel=schluessel,
            name=aktiv.name,
            text=aktiv.beschreibung(self.konfiguration),
            geld=geld,
            erfahrung=erfahrung,
            fahrer=self.fahrernummer,
            fahrername=self.fahrernamen.get(self.fahrernummer, ""),
        )
        self.meldungen.append(meldung)
        return meldung

    def _verliere_tage(self, anzahl: int) -> None:
        """Nimmt die naechsten nutzbaren Tage weg (E29 Reisechaos).

        Entschieden: Es trifft die naechsten nutzbaren Tage, nicht die vor
        dem Rennen - gemeint ist die Kapazitaet aus GDD 2.
        """
        offen = [
            tag.datum
            for tag in self.saison.tage
            if tag.datum >= self.heute
            and tag.ist_nutzbar
            and tag.datum not in self.verlorene_tage
        ]
        self.verlorene_tage.update(offen[:anzahl])

    def faktoren(self, session: str = kern_ereignis.RENNEN) -> dict[str, float]:
        """Alle Faktoren, die gerade auf Werte wirken (GDD 14).

        Ereignisse und offene Defekte zusammen; beide sind Faktoren auf
        einzelne Faehigkeiten.
        """
        faktoren = dict(self.lage.faktoren(session))
        for ziel, faktor in kern_zwischenfall.wertfaktoren(
            self.konfiguration, self.defekte
        ).items():
            faktoren[ziel] = faktoren.get(ziel, 1.0) * faktor
        return faktoren

    def rennauto(self, vorlage, session: str = kern_ereignis.RENNEN):
        """Das Auto des Spielers, wie es in dieser Session faehrt.

        GDD 1 laesst den Spieler bei 0 anfangen und sich entwickeln; GDD 14
        laesst Ereignisse und Defekte an den Werten ziehen. Beides steht in
        der Karriere, nicht in der Welt - dieses Auto bringt es ins Rennen.

        :param vorlage: das Auto aus der Welt. Kuerzel und Name kommen von
            dort: Die Seitenleiste im Rennen zeigt sie (GDD 4), die
            Karriere kennt sie nicht.
        """
        from rennmanager.kern.auto import Auto

        werte = self.fahrwerte(session)
        matrix = {f.schluessel for f in self.konfiguration.faehigkeiten}
        return Auto(
            kuerzel=vorlage.kuerzel,
            name=vorlage.name,
            werte={s: w for s, w in werte.items() if s in matrix},
            wetterwerte={s: w for s, w in werte.items() if s not in matrix},
        )

    def entwickelte_autos(self, welt) -> dict[int, object]:
        """Die entwickelten Autos aller eigenen Fahrer, fuer die Anzeige.

        **Ohne** Ereignisse und Defekte: Die gehoeren ins Rennen, nicht in
        den Steckbrief. Wer auf die Werte seines Fahrers schaut, will
        sehen, was er sich erarbeitet hat.
        """
        from rennmanager.kern.auto import Auto

        matrix = {f.schluessel for f in self.konfiguration.faehigkeiten}
        vorlagen = {f.nummer: f.auto for f in welt.fahrer}
        gebaut = {}
        for nummer, werte in self.autos.items():
            vorlage = vorlagen.get(nummer)
            if vorlage is None:
                continue
            gebaut[nummer] = Auto(
                kuerzel=vorlage.kuerzel,
                name=vorlage.name,
                werte={s: w for s, w in werte.items() if s in matrix},
                wetterwerte={s: w for s, w in werte.items() if s not in matrix},
            )
        return gebaut

    def rennauto_von(self, nummer: int, vorlage, session: str = kern_ereignis.RENNEN):
        """Das Auto eines bestimmten eigenen Fahrers in dieser Session.

        Jedes Auto gehoert seinem Fahrer und ist einzeln entwickelt - hier
        wird das richtige genommen, ohne die Auswahl zu verstellen.
        """
        vorher = self.fahrernummer
        try:
            self.fahrernummer = nummer
            return self.rennauto(vorlage, session)
        finally:
            self.fahrernummer = vorher

    def fahrwerte(self, session: str = kern_ereignis.RENNEN) -> dict[str, int]:
        """Die Werte, mit denen gefahren wird - Ereignisse und Defekte drin."""
        faktoren = self.faktoren(session)
        kleinster = self.konfiguration.wert("skala", "minimum")
        groesster = self.konfiguration.wert("skala", "maximum")
        return {
            schluessel: int(
                round(min(max(wert * faktoren.get(schluessel, 1.0), kleinster), groesster))
            )
            for schluessel, wert in self.werte.items()
        }

    # -- Defekte und Reparatur (GDD 14) ------------------------------------
    def uebernimm_defekte(self, schluessel: tuple[str, ...]) -> None:
        """Traegt die Defekte eines Rennens ein; sie bleiben bis zur Reparatur."""
        for eintrag_ in schluessel:
            self.defekte.append(kern_zwischenfall.defekt_von(self.konfiguration, eintrag_))

    @property
    def offene_reparaturen(self) -> tuple[tuple[str, str, int], ...]:
        """Alles, was repariert werden kann: Schluessel, Name, Kosten.

        Das sind die offenen Defekte aus GDD 14 und die beiden Ereignisse,
        die bis zur Reparatur laufen (E8 Motorschaden, E25 Getriebeproblem).
        """
        posten = [
            (d["schluessel"], d["name"], self.reparaturkosten(d["schluessel"]))
            for d in self.defekte
        ]
        posten += [
            (a.schluessel, a.name, self.reparaturkosten(a.schluessel))
            for a in self.lage.offene_reparaturen
        ]
        return tuple(posten)

    def reparaturkosten(self, schluessel: str) -> int:
        """Was eine Reparatur kostet (GDD 14: Stufe mal Liga-Faktor)."""
        defekt = next((d for d in self.defekte if d["schluessel"] == schluessel), None)
        if defekt is not None:
            return kern_zwischenfall.reparaturkosten(self.konfiguration, defekt, self.liga)
        if any(a.schluessel == schluessel for a in self.lage.offene_reparaturen):
            # Ereignisse nennen keine Kostenstufe; angesetzt wird die
            # mittlere Stufe der 20 Defekte aus GDD 14.
            stufen = [d["kostenstufe"] for d in self.konfiguration.wert("defekte", "liste")]
            mittel = {"kostenstufe": sum(stufen) / len(stufen)}
            return kern_zwischenfall.reparaturkosten(self.konfiguration, mittel, self.liga)
        raise KarriereFehler(f"{schluessel} ist nicht offen und nicht reparierbar")

    def repariere(self, schluessel: str) -> int:
        """Repariert einen Defekt oder ein Ereignis; wirkt sofort (GDD 14).

        :return: die bezahlten Kosten
        """
        kosten = self.reparaturkosten(schluessel)
        if self.konto.geld < kosten:
            raise KarriereFehler(
                f"Die Reparatur kostet {kosten} EUR, auf dem Konto liegen {self.konto.geld}"
            )
        defekt = next((d for d in self.defekte if d["schluessel"] == schluessel), None)
        if defekt is not None:
            self.defekte.remove(defekt)
        else:
            self.lage.repariere(schluessel)
        self.konto = self.konto.mit(geld=-kosten)
        self.kassenbuch.buche(
            self.heute, -kosten, kern_kassenbuch.WERKSTATT,
            kern_kassenbuch.REPARATUR, fahrer=self.fahrernummer,
            text=schluessel,
        )
        return kosten

    # -- Kassenbuch (Punkt 72) ---------------------------------------------
    def _buche_entwicklung(self, entwicklung, platz: str) -> None:
        """Schreibt einen Kauf oder belegten Tag ins Kassenbuch.

        Fahrzeug und Fahrer bekommen eigene Unterkategorien: Wer wissen
        will, ob sein Geld ins Auto oder in die Fahrer geht, sieht es
        sonst nirgends.
        """
        if not entwicklung.geld:
            return
        fahrzeug = self._faehigkeit(entwicklung.faehigkeit)
        ins_auto = fahrzeug is not None and fahrzeug.ist_fahrzeug
        self.kassenbuch.buche(
            self.heute,
            -entwicklung.geld,
            kern_kassenbuch.ENTWICKLUNG,
            kern_kassenbuch.FAHRZEUG if ins_auto else kern_kassenbuch.TRAINING,
            fahrer=self.fahrernummer,
            text=f"{entwicklung.faehigkeit} {entwicklung.von} auf {entwicklung.nach}"
            + (f" ({platz})" if platz else ""),
        )

    def zahle_monatsrate(self) -> int:
        """Bucht die faellige Monatsrate aus dem Teambudget (Punkt 72).

        Am Ersten jedes Monats fuellt eine Rate das Konto. Gezaehlt wird
        ueber den zuletzt gezahlten Monat, nicht ueber das Datum allein:
        Wer mit ``bis_zum_rennen`` ueber einen Monatsersten hinwegspringt,
        soll seine Rate trotzdem bekommen, und zweimal derselbe Tag darf
        nicht zweimal zahlen.

        :return: die gebuchte Summe
        """
        rate = kern_kassenbuch.monatsrate(self.konfiguration, self.teambudget)
        if rate <= 0:
            return 0
        jetzt = (self.heute.year, self.heute.month)
        if self.letzte_rate is not None and self.letzte_rate >= jetzt:
            return 0
        self.letzte_rate = jetzt
        self.konto = self.konto.mit(geld=rate)
        self.kassenbuch.buche(
            self.heute, rate, kern_kassenbuch.TEAM, kern_kassenbuch.MONATSBUDGET,
            text=f"{self.heute.month:02d}/{self.heute.year}",
        )
        return rate

    def bis_zum_rennen(self) -> int:
        """Springt direkt zum naechsten Renntag (GDD 2).

        :return: Zahl der uebersprungenen Tage
        """
        ziel = self.naechstes_rennen
        if ziel is None:
            raise KarriereFehler("Es steht kein Rennen mehr an")
        uebersprungen = 0
        while self.heute < ziel:
            self.tag_weiter()
            uebersprungen += 1
        return uebersprungen

    # -- Entwicklung -------------------------------------------------------
    def wert(self, schluessel: str) -> int:
        try:
            return self.werte[schluessel]
        except KeyError:
            raise KarriereFehler(f"Unbekannte Faehigkeit: {schluessel}") from None

    def platz_fuer(self, schluessel: str) -> str:
        """Ob eine Faehigkeit den Fahrer- oder den Werkstattplatz belegt."""
        faehigkeit = self._faehigkeit(schluessel)
        if faehigkeit is None:
            # Neben der Matrix entscheidet der Traeger: Wetterfaehigkeiten,
            # Reifenfluesterer und die vier neuen Fahrereigenschaften
            # gehoeren dem Fahrer, die Bremskuehlung der Werkstatt.
            return (
                WERKSTATTPLATZ
                if schluessel in self.konfiguration.fahrzeugzusatz
                else FAHRERPLATZ
            )
        return (
            FAHRERPLATZ
            if kern_entwicklung.ist_fahrertraining(faehigkeit)
            else WERKSTATTPLATZ
        )

    def vorschau(self, schluessel: str) -> kern_entwicklung.Entwicklung:
        """Was eine Tageszuweisung oder ein Kauf braechte, ohne zu buchen."""
        faehigkeit = self._faehigkeit(schluessel)
        wert = self.wert(schluessel)
        if faehigkeit is None:
            return self._zusatz_vorschau(schluessel, wert)
        if kern_entwicklung.braucht_tag(faehigkeit):
            return kern_entwicklung.plane_tag(self.konfiguration, faehigkeit, wert)
        return kern_entwicklung.plane_kauf(self.konfiguration, faehigkeit, wert)

    def belege_tag(self, schluessel: str) -> kern_entwicklung.Entwicklung:
        """Belegt den heutigen Platz mit einer Faehigkeit (GDD 2)."""
        if self.tag.art is not Tagesart.NUTZBAR:
            raise KarriereFehler(
                f"{self.heute} ist ein {self.tag.art.bezeichnung}-Tag und nicht nutzbar"
            )
        if self.heute in self.verlorene_tage:
            raise KarriereFehler(f"{self.heute} ist durch ein Ereignis ausgefallen")
        self._pruefe_sperre(schluessel)
        entwicklung = self.vorschau(schluessel)
        if not entwicklung.braucht_tag:
            raise KarriereFehler(
                f"{schluessel} kostet keine Zeit - direkt kaufen statt einen Tag belegen"
            )

        platz = self.platz_fuer(schluessel)
        if platz in self.belegt:
            raise KarriereFehler(
                f"Der Platz {platz} ist bis zum naechsten Rennen belegt"
            )
        self.konto = kern_entwicklung.buche(self.konto, entwicklung)
        self._buche_entwicklung(entwicklung, platz)
        self.belegt.add(platz)
        self._uebernimm(entwicklung, platz)
        return entwicklung

    def kaufe(self, schluessel: str) -> kern_entwicklung.Entwicklung:
        """Kauft einen +10-Schritt sofort - nur ohne Zeitanteil (GDD 2)."""
        self._pruefe_sperre(schluessel)
        entwicklung = self.vorschau(schluessel)
        if entwicklung.braucht_tag:
            raise KarriereFehler(
                f"{schluessel} braucht einen Tag - ueber belege_tag statt kaufen"
            )
        self.konto = kern_entwicklung.buche(self.konto, entwicklung)
        self._buche_entwicklung(entwicklung, platz="")
        self._uebernimm(entwicklung, platz="")
        return entwicklung

    def gesperrt(self) -> frozenset[str]:
        """Was gerade nicht entwickelt werden darf (GDD 14: E2, E6)."""
        sperren = set(self.lage.gesperrt())
        # E2 sperrt "fahrertraining" als Ganzes, also jede Faehigkeit, die
        # den Fahrerplatz belegt.
        if kern_ereignis.FAHRERTRAINING in sperren:
            sperren.discard(kern_ereignis.FAHRERTRAINING)
            sperren.update(
                f.schluessel
                for f in self.konfiguration.faehigkeiten
                if kern_entwicklung.ist_fahrertraining(f)
            )
            # Nur was dem Fahrer gehoert - die Werkstatt arbeitet weiter.
            sperren.update(
                schluessel
                for schluessel in self.konfiguration.zusatzfaehigkeiten
                if schluessel not in self.konfiguration.fahrzeugzusatz
            )
        return frozenset(sperren)

    def _pruefe_sperre(self, schluessel: str) -> None:
        if schluessel in self.gesperrt():
            raise KarriereFehler(
                f"{schluessel} ist durch ein Ereignis gesperrt (GDD 14)"
            )

    def _uebernimm(self, entwicklung: kern_entwicklung.Entwicklung, platz: str) -> None:
        self.werte[entwicklung.faehigkeit] = entwicklung.nach
        self.buchungen.append(
            Tagesbuchung(
                datum=self.heute,
                platz=platz,
                faehigkeit=entwicklung.faehigkeit,
                von=entwicklung.von,
                nach=entwicklung.nach,
                geld=entwicklung.geld,
                erfahrung=entwicklung.erfahrung,
            )
        )

    def _faehigkeit(self, schluessel: str):
        try:
            return self.konfiguration.faehigkeit(schluessel)
        except KeyError:
            return None

    def _zusatz_vorschau(self, schluessel: str, wert: int) -> kern_entwicklung.Entwicklung:
        """Wetterfaehigkeiten und Reifenfluesterer stehen ausserhalb der Matrix.

        Ihre Waehrung steht bei ihnen selbst; die Wetter-Erfahrung kommt
        aus dem eigenen Topf des jeweiligen Wetters (GDD 10).
        """
        from rennmanager.konfiguration import Faehigkeit

        eintrag = self.zusatz_eintrag(schluessel)
        faehigkeit = Faehigkeit(
            schluessel=schluessel,
            name=eintrag.get("name", schluessel),
            waehrung=tuple(eintrag.get("waehrung", ("E",))),
            gewichte={},
        )
        entwicklung = (
            kern_entwicklung.plane_tag(self.konfiguration, faehigkeit, wert)
            if kern_entwicklung.braucht_tag(faehigkeit)
            else kern_entwicklung.plane_kauf(self.konfiguration, faehigkeit, wert)
        )
        wetter = eintrag.get("wetter")
        if wetter:
            return kern_entwicklung.als_wettertopf(entwicklung, wetter)
        return entwicklung

    def zusatz_eintrag(self, schluessel: str) -> dict:
        """Der Konfigurationseintrag einer Faehigkeit ausserhalb der Matrix.

        Die Wetterfaehigkeiten aus GDD 7, der Reifenfluesterer und die
        fuenf Eigenschaften aus Punkt 48 stehen nicht in der
        Wirkungsmatrix; Name und Waehrung kommen deshalb aus ihrem eigenen
        Abschnitt der Konfiguration.
        """
        try:
            return self.konfiguration.zusatzeintrag(schluessel)
        except KeyError:
            raise KarriereFehler(f"Unbekannte Faehigkeit: {schluessel}") from None

    # -- Rennwochenende ----------------------------------------------------
    def verbuche_rennen(
        self,
        platz: int,
        ueberholmanoever: int = 0,
        kilometer_je_wetter: dict[str, float] | None = None,
        fahrer: int | None = None,
        liga: int | None = None,
        zaehle_rennwochenende: bool = True,
    ) -> Konto:
        """Schreibt Preisgeld, Startgeld, Erfahrung und Sponsoren gut (GDD 10).

        Alles laeuft in **ein** Konto: Der Teamchef verdient an allen
        seinen Autos. Preisgeld und Erfahrung haengen aber an der Liga des
        einzelnen Fahrers, und die Sponsoren sitzen auf seinem Auto.

        :param fahrer: wessen Rennen gebucht wird. Ohne Angabe der
            gewaehlte - so bleiben Aufrufe mit einem Auto unveraendert.
        :param liga: seine Liga. Ohne Angabe die des Teams.
        :param zaehle_rennwochenende: ob dieser Aufruf die Ereignisse ein
            Wochenende weiterzaehlt. Die Lage gehoert dem **Team**, nicht
            dem einzelnen Fahrer: Stehen vier eigene Autos im selben
            Rennen, wird viermal gebucht, aber es ist ein Rennen. Wer das
            viermal zaehlt, laesst jedes Ereignis viermal so schnell
            ablaufen. Die Sponsorenvertraege sitzen dagegen auf dem
            einzelnen Auto und zaehlen deshalb bei jedem Aufruf mit.
        """
        vorher = self.fahrernummer
        if fahrer is not None:
            self.fahrernummer = fahrer
        seine_liga = liga if liga is not None else self.liga
        try:
            preisgeld = kern_einnahmen.preisgeld(self.konfiguration, seine_liga, platz)
            startgeld = kern_einnahmen.startgeld(self.konfiguration, seine_liga)
            sponsoren = kern_sponsoren.auszahlung(self.vertraege, platz)
            geld = preisgeld + startgeld + sponsoren
            for betrag, haupt, unter in (
                (preisgeld, kern_kassenbuch.RENNEN, kern_kassenbuch.PREISGELD),
                (startgeld, kern_kassenbuch.RENNEN, kern_kassenbuch.STARTGELD),
                (sponsoren, kern_kassenbuch.SPONSOREN, kern_kassenbuch.SPONSORENGELD),
            ):
                self.kassenbuch.buche(
                    self.heute, betrag, haupt, unter,
                    fahrer=self.fahrernummer, text=f"Platz {platz}",
                )
            erfahrung = kern_einnahmen.erfahrung_fuer(
                self.konfiguration, seine_liga, platz, ueberholmanoever
            )

            toepfe = {}
            for wetter, kilometer in (kilometer_je_wetter or {}).items():
                toepfe[wetter] = kern_einnahmen.wetter_erfahrung(
                    self.konfiguration, seine_liga, kilometer, platz
                )

            self.konto = self.konto.mit(geld=geld, erfahrung=erfahrung, **toepfe)
            # Die Sponsorenvertraege sitzen auf dem Auto dieses Fahrers -
            # sie zaehlen mit jedem seiner Rennen herunter, nicht mit
            # denen seiner Kollegen.
            self.vertraege = kern_sponsoren.nach_rennen(self.vertraege)
        finally:
            self.fahrernummer = vorher
        # Ereignisse, die in Rennwochenenden laufen, sind eines weiter
        # (GDD 14).
        if zaehle_rennwochenende:
            for lage in self.alle_lagen:
                lage.nach_rennwochenende()
        return self.konto

    def verbuche_runden(
        self,
        strecke: str,
        runden: int,
        seedquelle: Seedquelle,
        fahrer: int | None = None,
    ) -> float:
        """Schreibt gefahrene Runden der Streckenkenntnis gut (GDD 6).

        E10 Testfahrt geglueckt hebt den Zuwachs der naechsten Strecke -
        das Ereignis gehoert dem Team, gilt also fuer alle vier.

        :param fahrer: wessen Runden gebucht werden. Ohne Angabe die des
            gewaehlten.
        """
        nummer = self.fahrernummer if fahrer is None else fahrer
        zuschlag = 1.0 + self.lage.streckenkenntnisbonus()
        gewachsen = self.kenntnis.verbuche(nummer, strecke, runden, seedquelle)
        if zuschlag != 1.0:
            zusatz = gewachsen * (zuschlag - 1.0)
            self.kenntnis.setze(
                nummer, strecke, self.kenntnis.stand(nummer, strecke) + zusatz
            )
            gewachsen += zusatz
        return gewachsen

    def kenntnisfaktor(self, strecke: str) -> float:
        """Tempofaktor des Spielers auf dieser Strecke (GDD 6)."""
        return self.kenntnis.tempofaktor(self.fahrernummer, strecke)

    def tagesformbonus(self) -> float:
        """Zuschlag auf den Tagesform-Mittelwert (E3 aus GDD 14).

        0,0, solange kein Ereignis darauf wirkt. Der Wert geht als
        Mittelwertverschiebung in ``rennmanager.kern.form.tagesform``.
        """
        return self.lage.tagesformbonus()

    # -- Saisonwechsel (GDD 13) --------------------------------------------
    def naechste_saison(
        self, jahr: int, liga: int, seedquelle: Seedquelle | None = None
    ) -> None:
        """Traegt die Karriere in die naechste Saison (GDD 2 und 13).

        Der Saisonwechsel liegt laut GDD 2 am 31.12./01.01.; die Karriere
        laeuft endlos weiter.

        Es bleiben: Konto, Werte, Sponsorenvertraege, offene Defekte,
        laufende Ereignisse, Streckenkenntnis und das Karrierelog aus
        Buchungen und Meldungen.

        Neu sind Kalender und Ereignisplan - und nach Auf- oder Abstieg
        die Liga. Die verlorenen Tage bleiben nicht: Sie sind Daten des
        alten Kalenders und haetten im neuen keine Bedeutung.
        """
        if jahr <= self.saison.jahr:
            raise KarriereFehler(
                f"Die Saison {jahr} liegt nicht nach {self.saison.jahr}"
            )
        self.saison = kern_kalender.erzeuge(self.konfiguration, jahr)
        self.heute = self.saison.tage[0].datum
        self.liga = liga
        self.belegte_plaetze.clear()
        self.verlorene_tage.clear()
        self.ereignisplan = (
            kern_ereignis.plane_saison(
                self.konfiguration, self.saison, seedquelle.zweig("ereignisse")
            )
            if seedquelle is not None
            else {}
        )
        # Wie beim Karrierestart: Der 1. Januar wird nie "weitergeschaltet",
        # was auf ihn faellt, muesste sonst ausfallen.
        for schluessel in self.ereignisplan.get(self.heute, ()):
            self._loese_ereignis_aus(schluessel)

    # -- Fahrervertraege (Punkt 7) -----------------------------------------
    @property
    def gehaltssumme(self) -> int:
        """Was alle Fahrervertraege zusammen je Saison kosten."""
        return sum(gehalt for gehalt, _ in self.fahrervertraege.values())

    def verpflichte(
        self, nummer: int, gehalt: int, laufzeit: int, abloese: int = 0
    ) -> None:
        """Nimmt einen Fahrer unter Vertrag und zahlt die Abloese.

        Er bringt ein leeres, nicht upgegradetes Auto mit - so hat es der
        Auftraggeber entschieden. Wer verdraengt wird, entscheidet der
        Chef selbst, indem er vorher ``fahrer_geht`` ruft.
        """
        if abloese > self.konto.geld:
            raise KarriereFehler(
                f"Die Abloese von {abloese} EUR ist nicht gedeckt "
                f"({self.konto.geld} EUR auf dem Konto)"
            )
        if abloese:
            self.konto = self.konto.mit(geld=-abloese)
            self.kassenbuch.buche(
                self.heute, -abloese, kern_kassenbuch.TRANSFER,
                kern_kassenbuch.ABLOESE, fahrer=nummer,
            )
        self.autos.setdefault(nummer, leere_werte(self.konfiguration))
        self.belegte_plaetze.setdefault(nummer, set())
        self.vertraege_je_fahrer.setdefault(nummer, {})
        self.fahrervertraege[nummer] = (int(gehalt), int(laufzeit))

    def zahle_gehaelter(self) -> int:
        """Bucht die Jahresgehaelter ab und zaehlt die Vertraege herunter.

        Einmal je Saisonwechsel. Ohne Geld wird trotzdem gezahlt - GDD 10
        kennt keine Schulden und keinen Bankrott, das Konto geht nur auf
        null. Ein ausgelaufener Vertrag verschwindet; der Fahrer bleibt,
        bis der Chef ihn gehen laesst oder verlaengert.

        :return: die gezahlte Summe
        """
        summe = min(self.gehaltssumme, max(self.konto.geld, 0))
        if summe:
            self.konto = self.konto.mit(geld=-summe)
            self.kassenbuch.buche(
                self.heute, -summe, kern_kassenbuch.PERSONAL,
                kern_kassenbuch.GEHALT,
                text=f"{len(self.fahrervertraege)} Vertraege",
            )
        weiter = {}
        for nummer, (gehalt, laufzeit) in self.fahrervertraege.items():
            if nummer not in self.autos:
                continue  # Er ist gegangen, sein Vertrag mit ihm.
            if laufzeit > 1:
                weiter[nummer] = (gehalt, laufzeit - 1)
        self.fahrervertraege = weiter
        return summe

    def unterschreibe(self, angebot: kern_sponsoren.Angebot) -> None:
        """Nimmt ein Sponsorenangebot an; ein Platz traegt einen Vertrag."""
        self.vertraege[angebot.platz] = kern_sponsoren.unterschreibe(angebot)


def leere_werte(konfiguration: Konfiguration) -> dict[str, int]:
    """Ein frisches Auto: alle Werte auf 0.

    So faengt jeder eigene Fahrer an - beim Start des Spiels und wenn er
    einen abgetretenen ersetzt. Ein neuer Fahrer bringt ein leeres, nicht
    upgegradetes Auto mit (Entscheidung des Auftraggebers).
    """
    werte = {f.schluessel: 0 for f in konfiguration.faehigkeiten}
    werte.update(dict.fromkeys(konfiguration.zusatzfaehigkeiten, 0))
    return werte


def startjahr(konfiguration: Konfiguration) -> int:
    """Das Jahr der ersten Saison (GDD 2)."""
    return int(konfiguration.wert("kalender", "startjahr"))


def beginne(
    konfiguration: Konfiguration,
    jahr: int,
    liga: int,
    werte: dict[str, int] | None = None,
    seedquelle: Seedquelle | None = None,
    fahrernummer: int = 0,
    fahrer: tuple[int, ...] | None = None,
    teambudget: int = 0,
) -> Karriere:
    """Startet eine Karriere am 1. Januar (GDD 10).

    :param fahrer: die Fahrernummern des Teams. Jeder bekommt sein
        **eigenes** Auto; ``werte`` gilt fuer alle als Anfangsstand.
        Ohne Angabe fuehrt die Karriere nur ``fahrernummer``.
    :param seedquelle: bestimmt die Ereignisse der Saison (GDD 14). Ohne
        Angabe laeuft das Jahr ohne Ereignisse - so bleiben Tests, die
        allein die Entwicklung pruefen, von ihnen unberuehrt.
    :param teambudget: das Budget des eigenen Teams aus der Welt. Es zahlt
        sich in Monatsraten aufs Konto aus (Punkt 72); 0 heisst keine
        Raten.
    """
    saison = kern_kalender.erzeuge(konfiguration, jahr)
    if werte is None:
        # Jeder eigene Fahrer startet mit allen Werten auf 0.
        werte = leere_werte(konfiguration)
    nummern = tuple(fahrer) if fahrer else (fahrernummer,)
    if fahrernummer not in nummern:
        fahrernummer = nummern[0]
    plan = (
        kern_ereignis.plane_saison(konfiguration, saison, seedquelle.zweig("ereignisse"))
        if seedquelle is not None
        else {}
    )
    karriere = Karriere(
        konfiguration=konfiguration,
        saison=saison,
        heute=saison.tage[0].datum,
        liga=liga,
        konto=Konto(geld=kern_einnahmen.startkapital(konfiguration)),
        autos={nummer: dict(werte) for nummer in nummern},
        ereignisplan=plan,
        fahrernummer=fahrernummer,
        teambudget=teambudget,
        seedquelle=seedquelle,
    )
    karriere.kassenbuch.buche(
        karriere.heute,
        karriere.konto.geld,
        kern_kassenbuch.TEAM,
        kern_kassenbuch.STARTKAPITAL,
    )
    # Die Rate des Startmonats gibt es sofort - sonst faengt das erste
    # Jahr mit elf Raten an.
    karriere.zahle_monatsrate()
    # Der erste Januar ist selbst schon ein Tag des ersten Zyklus; was auf
    # ihn faellt, wird nie "weitergeschaltet" und muesste sonst ausfallen.
    for schluessel in plan.get(karriere.heute, ()):
        karriere._loese_ereignis_aus(schluessel)
    return karriere


def kopiere(karriere: Karriere) -> Karriere:
    """Eine unabhaengige Kopie - fuer Vorschauen, die nichts veraendern."""
    kopie = replace(
        karriere,
        konto=karriere.konto,
        autos={n: dict(w) for n, w in karriere.autos.items()},
        vertraege_je_fahrer={
            n: dict(v) for n, v in karriere.vertraege_je_fahrer.items()
        },
        fahrervertraege=dict(karriere.fahrervertraege),
        buchungen=list(karriere.buchungen),
        belegte_plaetze={n: set(p) for n, p in karriere.belegte_plaetze.items()},
        defekte=list(karriere.defekte),
        verlorene_tage=set(karriere.verlorene_tage),
        meldungen=list(karriere.meldungen),
        # Die laufenden Ereignisse werden einzeln kopiert: Ihr Restzaehler
        # wird an Ort und Stelle heruntergezaehlt, eine flache Kopie der
        # Liste teilte ihn also mit dem Original. Seit Punkt 56 fuehrt
        # jeder Fahrer seine eigene Lage - kopiert werden alle.
        lage_je_fahrer={
            nummer: kern_ereignis.Lage(
                karriere.konfiguration, [replace(a) for a in lage.aktive]
            )
            for nummer, lage in karriere.lage_je_fahrer.items()
        },
        fahrernamen=dict(karriere.fahrernamen),
        kenntnis=kern_streckenkenntnis.Streckenkenntnis(
            karriere.konfiguration, dict(karriere.kenntnis.runden)
        ),
    )
    return kopie
