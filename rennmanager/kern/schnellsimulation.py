"""Schnellsimulation der uebrigen Ligen (GDD 13).

"Nach jedem Rennwochenende des Spielers im Schnellmodus auf Rundenebene:
Qualifying und Rennen mit Wetter, Fehlern, Unfaellen und Defekten in
vereinfachter Form."

Der Unterschied zur vollen Simulation aus ``rennmanager.kern.rennen``: Dort
laeuft die Uhr in 50-Millisekunden-Schritten und die Autos stehen einzeln
auf der Strecke. Hier wird je Runde eine Rundenzeit gebildet und
aufsummiert; Verkehr und Ueberholen werden ueber die Reihenfolge geregelt,
nicht ueber Positionen.

Das genuegt fuer 19 Ligen zu je 30 Autos nach jedem Rennwochenende - die
volle Simulation braeuchte dafuer Minuten, diese Sekunden.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from rennmanager.kern import boxenstopp as kern_boxenstopp
from rennmanager.kern import form as kern_form
from rennmanager.kern import gummierung as kern_gummierung
from rennmanager.kern import reifen as kern_reifen
from rennmanager.kern import strategie as kern_strategie
from rennmanager.kern import tempoverlauf as kern_tempoverlauf
from rennmanager.kern import wetter as kern_wetter
from rennmanager.kern import windschatten as kern_windschatten
from rennmanager.kern import zwischenfall as kern_zwischenfall
from rennmanager.kern.auto import gesamtwert
from rennmanager.kern.qualifying import qualifyingbonus
from rennmanager.kern.rennen import Teilnehmer, erfolgschance, streckenfaktor
from rennmanager.kern.strecke import Strecke
from rennmanager.kern.tempo import fahre_runde, grenzen_aus
from rennmanager.kern.wertung import Rennergebnis
from rennmanager.kern.zufall import Seedquelle

if TYPE_CHECKING:  # pragma: no cover
    from rennmanager.konfiguration import Konfiguration

# Mindestabstand, den ein aufgehaltenes Auto zum Vordermann behaelt. Er
# entspricht der Schwelle aus GDD 4, ab der ueberholt werden darf.
STAU_ABSTAND_S = 0.05


@dataclass(frozen=True)
class Schnellergebnis:
    """Ergebnis eines Rennwochenendes im Schnellmodus."""

    liga: int
    strecke: str
    ergebnisse: tuple[Rennergebnis, ...]
    wetter: tuple[str, ...]
    siegerzeit_ms: int
    schnellste_runde_ms: int
    ueberholmanoever: int
    ausfaelle: int
    # Punkt 23: die Lage, unter der am meisten gefahren wurde. Fuer die
    # Wetterbilanz braucht es eine Lage je Rennen, nicht den Verlauf.
    vorherrschendes_wetter: str = ""
    # Je Auto: gelungene Ueberholmanoever, offen gebliebene Defekte und
    # gefahrene Kilometer je Wetterlage. Die Karriere braucht das fuer
    # Erfahrung, Reparaturen und die Wetter-Erfahrung (GDD 10 und 14).
    manoever_je_auto: tuple[int, ...] = ()
    defekte_je_auto: tuple[tuple[str, ...], ...] = ()
    kilometer_je_wetter: tuple[dict[str, float], ...] = ()


def _grenzen(konfiguration, auto, rhythmus: float):
    """Die Grenzen eines Autos, mit dem Rhythmusvorteil aus Punkt 15."""
    grenzen = grenzen_aus(konfiguration, auto)
    return replace(grenzen, quer=grenzen.quer * rhythmus) if rhythmus != 1.0 else grenzen


def _grundrunden(
    konfiguration: Konfiguration, strecke: Strecke, autos, rhythmusfaktor=None
) -> np.ndarray:
    """Rundenzeit jedes Autos ohne Wetter, Zufall und Verschleiss."""
    faktoren = rhythmusfaktor if rhythmusfaktor is not None else (1.0,) * len(autos)
    return np.array(
        [
            fahre_runde(
                konfiguration, strecke, auto, grenzen=_grenzen(konfiguration, auto, faktor)
            ).zeit_ms
            for auto, faktor in zip(autos, faktoren, strict=True)
        ],
        dtype=float,
    )


def fahre_wochenende(
    konfiguration: Konfiguration,
    liga: int,
    strecke: Strecke,
    teilnehmer: tuple[Teilnehmer, ...],
    runden: int,
    seedquelle: Seedquelle,
    streckenmittel: float,
    streckenverschleiss: float = 1.0,
    kenntnisfaktor: tuple[float, ...] | None = None,
    tagesformbonus: tuple[float, ...] | None = None,
    rhythmusfaktor: tuple[float, ...] | None = None,
    mischungen: tuple[kern_reifen.Mischung, ...] | None = None,
    strategien: tuple[kern_strategie.Strategie, ...] | None = None,
) -> Schnellergebnis:
    """Faehrt Qualifying und Rennen einer Liga im Schnellmodus (GDD 13).

    :param kenntnisfaktor: Tempofaktor aus der Streckenkenntnis je Auto
        (GDD 6). Ohne Angabe faehrt jedes Auto ohne Kenntnisbonus.
    :param tagesformbonus: Zuschlag auf den Tagesform-Mittelwert je Auto
        (E3 Motivationsschub aus GDD 14). Ohne Angabe faehrt jedes Auto
        ohne Zuschlag.
    :param rhythmusfaktor: Faktor auf die Querbeschleunigung in Kurven je
        Auto (Punkt 15). Ohne Angabe faehrt jedes Auto ohne Vorteil.
    :param mischungen: Reifenmischung je Auto (Punkt 39). Ohne Angabe
        faehrt jedes Auto die mittlere Trockenmischung.
    :param strategien: Mischungsfolge und Stopprunden je Auto (Punkt 39).
        Mit Angabe werden dieselben Stopps gefahren wie im Zeitraffer und
        mit demselben Zeitverlust gebucht - die volle Simulation faehrt
        die Boxengasse wirklich langsam, hier wird die Differenz
        abgezogen.
    """
    if not teilnehmer:
        raise ValueError("Ohne Teilnehmer gibt es kein Rennwochenende")
    if kenntnisfaktor is None:
        kenntnisfaktor = (1.0,) * len(teilnehmer)
    elif len(kenntnisfaktor) != len(teilnehmer):
        raise ValueError(
            f"Kenntnisfaktor fuer {len(kenntnisfaktor)} Autos, "
            f"im Feld stehen {len(teilnehmer)}"
        )
    if tagesformbonus is None:
        tagesformbonus = (0.0,) * len(teilnehmer)
    elif len(tagesformbonus) != len(teilnehmer):
        raise ValueError(
            f"Tagesformbonus fuer {len(tagesformbonus)} Autos, "
            f"im Feld stehen {len(teilnehmer)}"
        )
    if rhythmusfaktor is None:
        rhythmusfaktor = (1.0,) * len(teilnehmer)
    elif len(rhythmusfaktor) != len(teilnehmer):
        raise ValueError(
            f"Rhythmusfaktor fuer {len(rhythmusfaktor)} Autos, "
            f"im Feld stehen {len(teilnehmer)}"
        )

    anzahl = len(teilnehmer)
    nummern = np.arange(anzahl)

    # --- Qualifying ------------------------------------------------------
    quali_formen = [
        kern_form.wuerfle(
            konfiguration, t.auto, seedquelle.zweig("qualiform", i), tagesformbonus[i]
        )
        for i, t in enumerate(teilnehmer)
    ]
    quali_autos = [f.auto for f in quali_formen]
    quali_runden = _grundrunden(konfiguration, strecke, quali_autos, rhythmusfaktor)
    quali_wetter = kern_wetter.wuerfle(
        konfiguration,
        strecke.name,
        int(quali_runden.mean() * 2 * anzahl),
        int(quali_runden.mean()),
        seedquelle.zweig("qualiwetter"),
        wechselfenster_ms=int(
            konfiguration.wert("qualifying", "wetter", "fenster_minuten") * 60_000
        ),
        wechsel_max=konfiguration.wert("qualifying", "wetter", "wechsel_max"),
    )
    # Vereinfachung des Schnellmodus (GDD 13): Alle Autos fahren ihre
    # gezeitete Runde in der Lage zu Sessionbeginn. Im vollen Qualifying
    # rueckt jedes Auto einzeln los und trifft deshalb je nach Startzeit
    # anderes Wetter an - dafuer braeuchte es hier eine Uhr, die der
    # Schnellmodus gerade nicht fuehrt.
    quali_zustand = quali_wetter.startzustand
    # Punkt 88: Wer spaeter faehrt, findet mehr Gummi vor - wie in der
    # vollen Session. Vor dem i-ten Auto lagen i Autos mit je einer
    # Aufwaerm- und einer gezeiteten Runde draussen, dazu die eigene
    # Aufwaermrunde.
    quali_aufwaerm = konfiguration.wert("qualifying", "aufwaermrunden")
    # Punkt 39: Im Qualifying wird immer weich gefahren, im Nassen der
    # passende Satz. Die Mischung steht damit vor der Runde fest und wird
    # schon fuer Auftrag und Ansprechen des Gummis gebraucht.
    quali_misch = kern_strategie.qualifyingmischung(konfiguration, quali_zustand)
    for i, auto in enumerate(quali_autos):
        gummistand = kern_gummierung.naechster_stand(
            konfiguration,
            0.0,
            quali_zustand,
            i * (quali_aufwaerm + 1) + quali_aufwaerm,
            mischung=quali_misch,
        )
        grip = kern_wetter.grip_fuer(
            konfiguration, auto, quali_zustand, quali_wetter.grip_zu(0)
        ) * kern_gummierung.faktor(konfiguration, gummistand, quali_misch)
        streuung = kern_form.rundenform(
            konfiguration, auto, seedquelle.zweig("qualirunde", i), 1
        )
        quali_mischfaktor = kern_reifen.mischungsfaktor(
            konfiguration, quali_misch, kern_reifen.naesse_von(konfiguration, quali_zustand)
        )
        quali_runden[i] *= streuung / (
            grip
            * (1.0 + qualifyingbonus(konfiguration, auto))
            * kenntnisfaktor[i]
            * quali_mischfaktor
        )

    aufstellung = list(np.argsort(quali_runden))
    qualifyingplatz = {int(i): platz for platz, i in enumerate(aufstellung, start=1)}

    # --- Rennen ----------------------------------------------------------
    formen = [
        kern_form.wuerfle(
            konfiguration, t.auto, seedquelle.zweig("rennform", i), tagesformbonus[i]
        )
        for i, t in enumerate(teilnehmer)
    ]
    autos = [f.auto for f in formen]
    grundrunde = _grundrunden(konfiguration, strecke, autos, rhythmusfaktor)
    # Dieselbe Runde mit der Bremse des Rennendes (Punkt 20). Zwischen
    # beiden wird nach gefahrener Distanz gemischt - so wie die volle
    # Simulation zwischen zwei Geschwindigkeitsprofilen mischt.
    grundrunde_ende = np.array(
        [
            fahre_runde(
                konfiguration,
                strecke,
                auto,
                grenzen=replace(
                    _grenzen(konfiguration, auto, faktor),
                    brems=kern_tempoverlauf.bremsgrenze_am_ende(
                        konfiguration, auto, _grenzen(konfiguration, auto, faktor).brems
                    ),
                ),
            ).zeit_ms
            for auto, faktor in zip(autos, rhythmusfaktor, strict=True)
        ],
        dtype=float,
    )
    sog_gewinn = np.array(
        [kern_windschatten.gewinn(konfiguration, auto) for auto in autos]
    )

    wetter = kern_wetter.wuerfle(
        konfiguration,
        strecke.name,
        int(grundrunde.mean() * runden),
        int(grundrunde.mean()),
        seedquelle.zweig("rennwetter"),
    )
    faktor = streckenfaktor(konfiguration, strecke, streckenmittel)
    wuerfel = seedquelle.zweig("schnellrennen").generator()

    # Punkt 39: je Strecke und Mischung, nicht je Renndistanz.
    streuungen: list[dict[str, kern_reifen.Mischung]] = [{} for _ in range(anzahl)]

    def gestreut(i: int, misch: kern_reifen.Mischung) -> kern_reifen.Mischung:
        """Der Verschleisswurf dieses Fahrers - wie in der vollen Simulation."""
        bekannt = streuungen[i].get(misch.schluessel)
        if bekannt is None:
            bekannt = kern_reifen.mit_streuung(
                konfiguration, misch, seedquelle.zweig("reifenstreuung", i)
            )
            streuungen[i][misch.schluessel] = bekannt
        return bekannt

    if strategien is not None:
        if len(strategien) != anzahl:
            raise ValueError(
                f"Strategien fuer {len(strategien)} Autos, im Feld stehen {anzahl}"
            )
        gewaehlt = [s.mischungen[0] for s in strategien]
    else:
        gewaehlt = list(
            mischungen
            if mischungen is not None
            else [kern_reifen.standardmischung(konfiguration)] * anzahl
        )
    gefahrene = [gestreut(i, m) for i, m in enumerate(gewaehlt)]
    # Wie in der vollen Simulation: welche Mischungen schon gefahren
    # sind, und was ein Zwangsstopp im Trockenen als weichste erlaubte
    # Mischung festgelegt hat.
    kuerzel_gefahren: list[set[str]] = [{m.kuerzel} for m in gefahrene]
    haerte_untergrenze: list[kern_reifen.Mischung | None] = [None] * anzahl
    # Punkt 83: wie lange ein Auto schon auf dem falschen Reifen faehrt
    # und wie lange es das aushaelt - wie in der vollen Simulation.
    runden_falscher_reifen = np.zeros(anzahl, dtype=int)
    geduld_falsch = np.array(
        [
            kern_strategie.geduld_falscher_reifen(
                konfiguration, seedquelle.zweig("reifengeduld", i)
            )
            for i in range(anzahl)
        ],
        dtype=int,
    )

    def je_runde(i: int, naesse: float) -> float:
        """Profilverlust je Runde - die Naesse geht hier ein, nicht obendrauf.

        Ohne sie rechnet die Funktion mit trockener Strecke und haelt
        einen Intermediate schon fuer einen Fehlgriff; der Aufschlag kaeme
        dann zweimal.
        """
        return (
            kern_reifen.verschleiss_je_meter(
                konfiguration, autos[i], gefahrene[i], streckenverschleiss, 1.0, naesse
            )
            * strecke.laenge_m
        )

    naesse_start = kern_reifen.naesse_von(konfiguration, wetter.startzustand)
    verschleiss_je_runde = np.array([je_runde(i, naesse_start) for i in range(anzahl)])
    # Was ein Stopp kostet - ohne die Standzeit, die je Stopp gewuerfelt
    # wird. Durchfahrt, Bremsen und Anfahren haengen nur am Auto.
    stoppgrundlast = np.array(
        [
            kern_boxenstopp.durchfahrtsverlust_ms(
                konfiguration, strecke, _grenzen(konfiguration, auto, faktor_r), liga=liga
            )
            + kern_boxenstopp.haltverlust_ms(
                konfiguration, _grenzen(konfiguration, auto, faktor_r), liga
            )
            for auto, faktor_r in zip(autos, rhythmusfaktor, strict=True)
        ],
        dtype=float,
    )
    strategie_stand = list(strategien) if strategien is not None else None
    pflicht_zwei = kern_strategie.pflicht_zwei_mischungen(konfiguration, wetter.zustaende)
    stint_stand = np.zeros(anzahl, dtype=int)
    stopp_nummer = np.zeros(anzahl, dtype=int)
    runde_letzter_stopp = np.zeros(anzahl, dtype=int)
    # Ob der letzte gefahrene Stopp ein Notstopp war - danach darf der
    # naechste geplante Stopp laenger warten, wie in der vollen Simulation.
    letzter_war_notstopp = np.zeros(anzahl, dtype=bool)
    notstopp_faellig = np.zeros(anzahl, dtype=bool)
    stopps_je_auto = np.zeros(anzahl, dtype=int)

    gesamtzeit = np.zeros(anzahl)
    # Die Startaufstellung kostet Zeit: 5 m Abstand je Platz.
    abstand_m = konfiguration.wert("start", "abstand_m")
    tempo_ms = strecke.laenge_m / grundrunde  # m pro ms
    for platz, i in enumerate(aufstellung):
        gesamtzeit[i] = abstand_m * platz / tempo_ms[i]

    verschleiss = np.zeros(anzahl)
    defekt_tempo = np.ones(anzahl)
    manoever_je_auto = np.zeros(anzahl, dtype=int)
    kilometer = [dict.fromkeys(konfiguration.wert("wetter", "kette"), 0.0)
                 for _ in range(anzahl)]
    # GDD 14 deckelt die Wirkung aller aktiven Defekte zusammen; deshalb
    # werden sie gesammelt und der Faktor jedes Mal neu aus der ganzen
    # Liste gebildet - nicht Defekt fuer Defekt multipliziert.
    defekte_je_auto: list[list[dict]] = [[] for _ in range(anzahl)]
    aktiv = np.ones(anzahl, dtype=bool)
    gefahrene_runden = np.zeros(anzahl, dtype=int)
    beste_runde = np.full(anzahl, np.inf)
    manoever = 0
    ausfaelle = 0
    grenze = kern_zwischenfall.ausfallgrenze(konfiguration, wuerfel)
    # Die Startaufstellung ist die Reihenfolge vor der ersten Runde.
    vorige_reihenfolge = list(aufstellung)
    naesse_lage = naesse_start
    # Punkt 88: Gefahrene Auto-Runden Gummi, wie in der vollen Simulation.
    gummistand = 0.0

    for runde in range(1, runden + 1):
        zustand = wetter.zustand_zu(gesamtzeit[aktiv].min() if aktiv.any() else 0.0)
        wetter_fehler = float(konfiguration.wert("wetter", "zustand", zustand)["fehlerquote"])
        wetter_verschleiss = kern_wetter.verschleissfaktor(konfiguration, zustand)
        # Punkt 90: Die gruene Strecke frisst Reifen, die eingegummierte
        # schont sie - wie in der vollen Simulation. Der Stand gilt zum
        # Beginn der Runde; was diese Runde dazulegt, wirkt erst in der
        # naechsten.
        gummi_verschleiss = kern_gummierung.verschleissfaktor(konfiguration, gummistand)
        naesse_jetzt = kern_reifen.naesse_von(konfiguration, zustand)
        if naesse_jetzt != naesse_lage:
            naesse_lage = naesse_jetzt
            for i in range(anzahl):
                verschleiss_je_runde[i] = je_runde(i, naesse_lage)

        for i in range(anzahl):
            if not aktiv[i]:
                continue
            auto = autos[i]
            grip = kern_wetter.grip_fuer(
                konfiguration, auto, zustand, wetter.grip_zu(gesamtzeit[i])
            ) * kern_gummierung.faktor(konfiguration, gummistand, gefahrene[i])
            streuung = kern_form.rundenform(
                konfiguration, auto, seedquelle.zweig("rundenform", i), runde
            )
            # Punkt 39: Der Tempofaktor der Mischung gehoert dazu - sonst
            # faehrt weich im Rennen so schnell wie hart, und die
            # Strategie waere eine Rechnung ohne Wirkung.
            reifen = kern_reifen.mischungsfaktor(
                konfiguration, gefahrene[i], naesse_lage
            ) * kern_reifen.tempofaktor(konfiguration, auto, float(verschleiss[i]))
            # Ueber die Distanz (Punkte 9, 11 und 20): Die Bremse laesst
            # nach, die Ermuedung waechst, die kalten Reifen kosten die
            # erste Runde. Der Anteil gilt zu Rundenbeginn.
            anteil = (runde - 1) / runden
            basis = grundrunde[i] + anteil * (grundrunde_ende[i] - grundrunde[i])
            ermuedung = kern_tempoverlauf.ermuedungsfaktor(konfiguration, auto, anteil)
            kalt = kern_tempoverlauf.kaltreifenfaktor_runde(
                konfiguration, auto, runde, strecke.laenge_m
            )
            zeit = basis * streuung / (
                grip * reifen * defekt_tempo[i] * kenntnisfaktor[i] * ermuedung * kalt
            )

            # Fehler kosten einmalig Zeit (GDD 4).
            reifenfehler = kern_reifen.fehlerfaktor(konfiguration, auto, float(verschleiss[i]))
            if wuerfel.random() < kern_zwischenfall.fehlerrate_je_runde(
                konfiguration, auto, wetter_fehler, reifenfehler
            ):
                zeit += kern_zwischenfall.zeitverlust_ms(konfiguration, wuerfel)

            # Defekte senken das Tempo bis zur Reparatur (GDD 4 und 14).
            if wuerfel.random() < kern_zwischenfall.defektrate_je_runde(
                konfiguration, auto, runden
            ):
                defekte_je_auto[i].append(kern_zwischenfall.waehle_defekt(konfiguration, wuerfel))
                defekt_tempo[i] = kern_zwischenfall.tempofaktor_defekte(
                    konfiguration, defekte_je_auto[i]
                )

            gesamtzeit[i] += zeit
            beste_runde[i] = min(beste_runde[i], zeit)
            # Fuer die Wetter-Erfahrung aus GDD 10: Die Runde zaehlt zu der
            # Lage, die zu ihrem Beginn galt.
            kilometer[i][zustand] += strecke.laenge_m / 1000.0
            verschleiss[i] += verschleiss_je_runde[i] * wetter_verschleiss * gummi_verschleiss
            gefahrene_runden[i] += 1

            # --- Boxenstopp (Punkt 39) --------------------------------
            # Dieselben Regeln wie im Zeitraffer, nur ohne Geometrie: Was
            # dort als langsame Durchfahrt entsteht, wird hier gebucht.
            if strategie_stand is None or gefahrene_runden[i] >= runden:
                continue
            strat = strategie_stand[i]
            stelle = int(stopp_nummer[i])
            geplant = stelle < len(strat.stopps) and strat.stopps[stelle] == runde
            # Punkt 39: Ein geplanter Stopp wird verschoben, solange der
            # Satz besser ist als die Schwelle. Entschieden wird eine
            # Runde im Voraus - genau wie im Zeitraffer, wo das Auto sonst
            # schon langsam in die Boxengasse einfuehre und dann doch
            # daran vorbei.
            if (
                not notstopp_faellig[i]
                and stelle < len(strat.stopps)
                and strat.stopps[stelle] == runde + 1
            ):
                einstellung = konfiguration.wert("boxenstopp", "strategie")
                kuenftig = 1.0 - float(
                    verschleiss[i]
                    + verschleiss_je_runde[i] * wetter_verschleiss * gummi_verschleiss
                )
                if kuenftig > kern_strategie.verschiebeschwelle(
                    konfiguration, nach_notstopp=bool(letzter_war_notstopp[i])
                ):
                    spaeteste = runden - einstellung["sperre_runden"]
                    stopps = list(strat.stopps)
                    if runde + 2 <= spaeteste:
                        stopps[stelle] = runde + 2
                    elif stopps_je_auto[i] or not pflicht_zwei:
                        stopps = stopps[:stelle]
                    else:
                        # Zwei Mischungen sind Pflicht - der Stopp bleibt,
                        # so spaet wie erlaubt.
                        stopps[stelle] = spaeteste
                    strategie_stand[i] = kern_strategie.Strategie(
                        mischungen=strat.mischungen, stopps=tuple(stopps)
                    )
                    continue
            if not (geplant or notstopp_faellig[i]):
                # Zwei Gruende zwingen ausserplanmaessig herein - dieselben
                # wie in der vollen Simulation, sonst faehrt die Liga des
                # Spielers ein anderes Rennen als die neunzehn anderen.
                # Der Fahrer merkt es auf der Strecke und kommt eine Runde
                # spaeter herein.
                naesse = kern_reifen.naesse_von(konfiguration, zustand)
                seit = runde - int(runde_letzter_stopp[i])
                sperre = konfiguration.wert("boxenstopp", "strategie", "sperre_runden")
                if runde + 1 > runden - sperre:
                    continue
                # Der Reifen ist durch: Hier zaehlt allein das Restprofil.
                if kern_strategie.notstopp_verschleiss(
                    konfiguration, 1.0 - float(verschleiss[i]), seit
                ):
                    notstopp_faellig[i] = True
                    continue
                grenze = konfiguration.wert("boxenstopp", "strategie", "eignungsgrenze")
                if abs(gefahrene[i].naesse - naesse) > grenze:
                    runden_falscher_reifen[i] += 1
                else:
                    runden_falscher_reifen[i] = 0
                if (
                    kern_strategie.notstopp(
                        konfiguration,
                        gefahrene[i],
                        naesse,
                        seit,
                        int(runden_falscher_reifen[i]) - 1,
                        int(geduld_falsch[i]),
                    )
                    and kern_strategie.passende_mischung(konfiguration, naesse).kuerzel
                    != gefahrene[i].kuerzel
                ):
                    notstopp_faellig[i] = True
                continue

            if notstopp_faellig[i]:
                naesse = kern_reifen.naesse_von(konfiguration, zustand)
                neu = kern_strategie.passende_mischung(konfiguration, naesse)
                notstopp_faellig[i] = False
                letzter_war_notstopp[i] = True
                if neu.naesse == 0.0:
                    haerte_untergrenze[i] = neu
                strategie_stand[i] = kern_strategie.nach_notstopp(
                    konfiguration, strat, stelle, runde, runden
                )
            else:
                neu_stelle = min(int(stint_stand[i]) + 1, len(strat.mischungen) - 1)
                stint_stand[i] = neu_stelle
                stopp_nummer[i] += 1
                # Der Plan steht vor dem Rennen, das Wetter kann sich
                # seither gedreht haben. Passt der geplante Reifen nicht
                # mehr zur Lage, kommt der auf, der passt - wie in der
                # vollen Simulation. Ohne das zieht ein Auto im Regen
                # Slicks auf und kommt zwei Runden spaeter zum Notstopp.
                neu = strat.mischungen[neu_stelle]
                naesse = kern_reifen.naesse_von(konfiguration, zustand)
                grenze = konfiguration.wert("boxenstopp", "strategie", "eignungsgrenze")
                if abs(neu.naesse - naesse) > grenze:
                    neu = kern_strategie.passende_mischung(konfiguration, naesse)
                # Nach einem Zwangsstopp im Trockenen nicht wieder weicher
                # werden - ausser die Mischungspflicht steht noch aus.
                if (
                    haerte_untergrenze[i] is not None
                    and naesse == 0.0
                    and len(kuerzel_gefahren[i]) >= 2
                ):
                    neu = kern_strategie.nicht_weicher_als(neu, haerte_untergrenze[i])
                letzter_war_notstopp[i] = False

            standzeit = kern_boxenstopp.standzeit_ms(
                konfiguration,
                seedquelle.zweig("standzeit", i, int(stopps_je_auto[i])),
            )
            gesamtzeit[i] += stoppgrundlast[i] + standzeit
            gefahrene[i] = gestreut(i, neu)
            kuerzel_gefahren[i].add(neu.kuerzel)
            runden_falscher_reifen[i] = 0
            verschleiss[i] = 0.0
            verschleiss_je_runde[i] = je_runde(i, naesse_lage)
            runde_letzter_stopp[i] = runde
            stopps_je_auto[i] += 1

        # Verkehr und Ueberholen: Wo sich die Reihenfolge gegenueber der
        # Vorrunde geaendert hat, ist auf der Strecke ueberholt worden -
        # und das gelingt nur mit einem Wurf (GDD 4). Der blosse Abstand
        # am Rundenende taugt dafuer nicht: Zwei Autos koennen eine ganze
        # Runde nebeneinander fahren und trotzdem 20 Sekunden auseinander
        # ins Ziel kommen.
        #
        # Angefahren wird von hinten nach vorne: zuerst der naechste
        # Vordermann, dann der davor. Beim ersten misslungenen Versuch ist
        # Schluss - wer nicht vorbeikommt, haengt fest und erreicht die
        # weiter vorne Fahrenden in dieser Runde gar nicht mehr.
        neu = sorted(nummern[aktiv], key=lambda i: gesamtzeit[i])
        stelle_vorher = {i: platz for platz, i in enumerate(vorige_reihenfolge)}
        # Wer in der neuen Reihenfolge weiter hinten steht - daraus
        # ergibt sich, wen ein Auto in dieser Runde ueberholt hat.
        jetzt_hinter = set(neu)
        for hinten in neu:
            jetzt_hinter.discard(hinten)
            if hinten not in stelle_vorher:
                continue
            # Alle, die vorher vorne lagen und jetzt dahinter sind, vom
            # naechsten Vordermann aus aufwaerts.
            ueberholt = sorted(
                (i for i in jetzt_hinter if stelle_vorher.get(i, -1) < stelle_vorher[hinten]),
                key=lambda i: -stelle_vorher[i],
            )
            for vorne in ueberholt:
                # Windschatten (Punkt 7): Wer angreift, sitzt im
                # entscheidenden Moment dicht dahinter auf einer Geraden -
                # also mit dem vollen Sog. Der Schnellmodus fuehrt keine
                # Positionen, mehr laesst sich hier nicht abbilden.
                vorteil_kmh = (
                    strecke.laenge_m / grundrunde[hinten] * (1.0 + sog_gewinn[hinten])
                    - strecke.laenge_m / grundrunde[vorne]
                ) * 3600.0
                chance = erfolgschance(
                    konfiguration,
                    autos[hinten],
                    autos[vorne],
                    max(vorteil_kmh, 0.0),
                    faktor,
                )
                if wuerfel.random() < chance:
                    manoever += 1
                    manoever_je_auto[hinten] += 1
                    continue
                # Nicht vorbeigekommen: bleibt knapp dahinter haengen.
                gesamtzeit[hinten] = max(
                    gesamtzeit[hinten], gesamtzeit[vorne] + STAU_ABSTAND_S * 1000
                )
                break

        reihenfolge = sorted(nummern[aktiv], key=lambda i: gesamtzeit[i])
        vorige_reihenfolge = list(reihenfolge)

        # Unfaelle: sehr selten, nur zwischen nahen Autos (GDD 4).
        if ausfaelle < grenze:
            for stelle in range(1, len(reihenfolge)):
                vorne, hinten = reihenfolge[stelle - 1], reihenfolge[stelle]
                # In Reichweite ist, wer weniger als eine Rundenlaenge
                # Abstand hat, gemessen an der 30-m-Regel aus GDD 4.
                abstand_zeit = gesamtzeit[hinten] - gesamtzeit[vorne]
                reichweite = (
                    konfiguration.wert("unfaelle", "max_abstand_m")
                    / strecke.laenge_m
                    * grundrunde[hinten]
                )
                if abstand_zeit >= reichweite:
                    continue
                dauer_s = grundrunde[hinten] / 1000.0
                if wuerfel.random() < kern_zwischenfall.unfallrate(
                    konfiguration, dauer_s, wetter_fehler
                ):
                    betroffen = (
                        [hinten, vorne]
                        if kern_zwischenfall.beide_betroffen(konfiguration, wuerfel)
                        else [hinten]
                    )
                    for i in betroffen:
                        if ausfaelle < grenze and aktiv[i]:
                            aktiv[i] = False
                            ausfaelle += 1
                    break

        # Punkt 88: Was in dieser Runde gefahren wurde, zaehlt fuer die
        # naechste - bei trocken als Gummi, bei Regen als Abwaschen. Wer
        # auf Weich unterwegs war, hat mehr liegen lassen, also wird je
        # Auto einzeln gezaehlt.
        for i in range(anzahl):
            if aktiv[i]:
                gummistand = kern_gummierung.naechster_stand(
                    konfiguration, gummistand, zustand, mischung=gefahrene[i]
                )

        if not aktiv.any():
            break

    # --- Wertung ---------------------------------------------------------
    def schluessel(i: int) -> tuple:
        # Mehr Runden zuerst, dann die kuerzere Gesamtzeit; bei Gleichstand
        # der hoehere Durchschnitt der Basiseigenschaften (GDD 4).
        return (
            0 if aktiv[i] else 1,
            -int(gefahrene_runden[i]),
            float(gesamtzeit[i]),
            -gesamtwert(konfiguration, teilnehmer[i].auto),
        )

    schlussstand = sorted(range(anzahl), key=schluessel)
    schnellste = int(np.argmin(beste_runde))

    ergebnisse = tuple(
        Rennergebnis(
            fahrer=i,
            rennplatz=platz,
            qualifyingplatz=qualifyingplatz[i],
            schnellste_runde=(i == schnellste),
            ausgefallen=not bool(aktiv[i]),
        )
        for platz, i in enumerate(schlussstand, start=1)
    )

    return Schnellergebnis(
        liga=liga,
        strecke=strecke.name,
        ergebnisse=ergebnisse,
        wetter=wetter.zustaende,
        vorherrschendes_wetter=wetter.vorherrschend(
            int(round(gesamtzeit[schlussstand[0]]))
        ),
        siegerzeit_ms=int(round(gesamtzeit[schlussstand[0]])),
        schnellste_runde_ms=int(round(beste_runde[schnellste])),
        ueberholmanoever=manoever,
        ausfaelle=ausfaelle,
        manoever_je_auto=tuple(int(n) for n in manoever_je_auto),
        defekte_je_auto=tuple(
            tuple(d["schluessel"] for d in defekte) for defekte in defekte_je_auto
        ),
        kilometer_je_wetter=tuple(
            {lage: km for lage, km in eintrag.items() if km} for eintrag in kilometer
        ),
    )
