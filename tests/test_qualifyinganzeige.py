"""Tests fuer das abspielbare Qualifying (Punkt 85).

Die Seite rechnet nichts - getestet wird, dass sie zum richtigen
Zeitpunkt das Richtige zeigt: Anfangsstellung, mitlaufende Zeit,
Live-Einsortierung, die drei Splitfarben und die Aufstellung, die erst am
Ende steht.
"""

from __future__ import annotations

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from rennmanager.kern import qualifying as ql  # noqa: E402
from rennmanager.kern import rennen as rn  # noqa: E402
from rennmanager.kern import strecke as st  # noqa: E402
from rennmanager.kern.zufall import Seedquelle  # noqa: E402
from rennmanager.ui import qualifyingseite as qs  # noqa: E402
from rennmanager.ui.hauptfenster import Hauptfenster  # noqa: E402
from rennmanager.ui.tabellen import kurzname  # noqa: E402
from tests.oberflaeche import gefahrenes_qualifying  # noqa: E402

LIGA = 10


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    return kf.lade()


@pytest.fixture(scope="module")
def session(konfig) -> ql.Qualifying:
    strecke = st.lade(konfig, "Catalunya")
    feld = rn.starterfeld(konfig)
    return ql.fahre(konfig, strecke, feld, Seedquelle(4711))


@pytest.fixture
def seite(qtbot, konfig, session) -> qs.Qualifyingseite:
    """Jeder Test bekommt eine frische Seite mit derselben Session."""
    widget = qs.Qualifyingseite(konfig)
    qtbot.addWidget(widget)
    widget.zeige_session(session)
    return widget


def _zeilen(seite) -> list[list[str]]:
    liste = seite._rangliste
    return [
        [zeile.text(spalte) for spalte in range(liste.columnCount())]
        for zeile in (liste.topLevelItem(i) for i in range(liste.topLevelItemCount()))
    ]



def _spalte_lage(session) -> int:
    """Die Lage steht hinter den Sektoren - deren Zahl kommt aus der Strecke."""
    return qs.SPALTE_SEKTOR_AB + len(session.fahrten[0].sektoren_ms)


def _zeile_von(seite, session, fahrt) -> list[str]:
    kuerzel = session.teilnehmer[fahrt.teilnehmer].kuerzel
    return next(z for z in _zeilen(seite) if z[qs.SPALTE_AUTO] == kuerzel)


def _farben(seite, session, fahrt) -> list[str]:
    """Die Farbe je Sektorspalte als Hex - leer, wo keine gesetzt ist."""
    liste = seite._rangliste
    kuerzel = session.teilnehmer[fahrt.teilnehmer].kuerzel
    zeile = next(
        liste.topLevelItem(i)
        for i in range(liste.topLevelItemCount())
        if liste.topLevelItem(i).text(qs.SPALTE_AUTO) == kuerzel
    )
    werte = []
    for nummer in range(len(fahrt.sektoren_ms)):
        spalte = qs.SPALTE_SEKTOR_AB + nummer
        pinsel = zeile.foreground(spalte)
        # Eine Zelle ohne gesetzte Farbe traegt Qt.NoBrush - deren
        # color() ist Schwarz und waere sonst nicht von einer echten
        # Farbe zu unterscheiden.
        if not zeile.text(spalte) or pinsel.style() == Qt.NoBrush:
            werte.append("")
            continue
        werte.append(pinsel.color().name())
    return werte


# -- Anfangsstellung --------------------------------------------------------
def test_nach_dem_laden_steht_die_session_auf_anfang(seite, session) -> None:
    """Wunsch des Auftraggebers: nach dem Laden auf Anfang, pausiert."""
    assert seite.zeit_ms == 0
    assert not seite.laeuft
    assert seite._abspielen.text() == "Start"


def test_am_anfang_steht_noch_keine_zeit_da(seite, session) -> None:
    zeilen = _zeilen(seite)
    assert len(zeilen) == len(session.fahrten)
    assert all(zeile[qs.SPALTE_ZEIT] == "" for zeile in zeilen)
    assert all(zeile[qs.SPALTE_POS] == "" for zeile in zeilen)


def test_die_zeitrafferstufen_sind_dieselben_wie_im_rennen(seite, konfig) -> None:
    stufen = [seite._raffer.itemData(i) for i in range(seite._raffer.count())]
    assert stufen == list(konfig.wert("zeitraffer", "stufen"))
    assert seite._raffer.currentData() == konfig.wert("zeitraffer", "start_stufe")


# -- Wiedergabe -------------------------------------------------------------
def test_start_und_pause_schalten_die_uhr(seite) -> None:
    seite._abspielen.click()
    assert seite.laeuft and seite._abspielen.text() == "Pause"
    seite._abspielen.click()
    assert not seite.laeuft and seite._abspielen.text() == "Start"


def test_ein_takt_bringt_die_sessionzeit_voran(seite, konfig) -> None:
    seite._takt()
    assert seite.zeit_ms == konfig.wert("zeitraffer", "takt_ms") * seite._raffer.currentData()


def test_sofortergebnis_springt_ans_ende_und_haelt_an(seite, session) -> None:
    seite._abspielen.click()
    seite._sofort.click()
    assert seite.zeit_ms == session.dauer_ms
    assert not seite.laeuft


def test_anfang_setzt_zurueck(seite, session) -> None:
    seite._sofort.click()
    seite._zurueck.click()
    assert seite.zeit_ms == 0
    assert all(zeile[qs.SPALTE_ZEIT] == "" for zeile in _zeilen(seite))


# -- Live-Einsortierung -----------------------------------------------------
def test_die_zeit_laeuft_auf_der_schnellen_runde_mit(seite, session) -> None:
    """Sobald einer auf seiner Runde ist, sieht man die Zeit laufen.

    Zwei Zeitpunkte auf derselben Runde muessen verschiedene Zeiten
    zeigen - sonst stuende dort eine Zahl, die sich nicht bewegt.
    """
    fahrt = session.fahrten[0]
    spalte = _spalte_lage(session)

    seite._springe(fahrt.runde_ab_ms + 30_000)
    frueh = _zeile_von(seite, session, fahrt)
    seite._springe(fahrt.runde_ab_ms + 60_000)
    spaet = _zeile_von(seite, session, fahrt)

    assert frueh[spalte] == ql.Lage.SCHNELLE_RUNDE.bezeichnung
    assert frueh[qs.SPALTE_ZEIT] and spaet[qs.SPALTE_ZEIT]
    assert frueh[qs.SPALTE_ZEIT] != spaet[qs.SPALTE_ZEIT]


def test_vor_der_ausfahrt_steht_das_auto_in_der_box(seite, session) -> None:
    letzter = session.fahrten[-1]
    seite._springe(0)
    zeile = _zeile_von(seite, session, letzter)
    assert zeile[_spalte_lage(session)] == ql.Lage.WARTET.bezeichnung
    assert zeile[qs.SPALTE_ZEIT] == ""


def test_wer_faehrt_hat_noch_keine_position(seite, session) -> None:
    fahrt = session.fahrten[0]
    seite._springe(fahrt.runde_ab_ms + 30_000)
    laufend = [z for z in _zeilen(seite) if z[qs.SPALTE_ZEIT] and z[qs.SPALTE_POS] == ""]
    assert laufend, "Einer muss unterwegs sein"
    assert all(z[qs.SPALTE_RUECKSTAND] == "" for z in laufend)


def test_wer_durch_ist_bekommt_seine_position(seite, session) -> None:
    dritter = session.fahrten[2]
    seite._springe(dritter.ziel_ms)
    zeilen = _zeilen(seite)
    mit_position = [z for z in zeilen if z[qs.SPALTE_POS]]
    assert [z[qs.SPALTE_POS] for z in mit_position] == ["1", "2", "3"]


def test_am_ende_steht_das_ganze_feld_mit_position(seite, session) -> None:
    seite._sofort.click()
    zeilen = _zeilen(seite)
    assert [z[qs.SPALTE_POS] for z in zeilen] == [
        str(platz) for platz in range(1, len(session.fahrten) + 1)
    ]
    assert zeilen[0][qs.SPALTE_RUECKSTAND] == ""


# -- Aufstellung ------------------------------------------------------------
def test_die_aufstellung_bleibt_bis_zum_ende_leer(seite, session) -> None:
    """Entscheidung des Auftraggebers: erst am Ende fuellen."""
    assert seite._aufstellung.topLevelItemCount() == 0
    seite._springe(session.fahrten[-2].ziel_ms)
    assert seite._aufstellung.topLevelItemCount() == 0


def test_die_aufstellung_steht_nach_der_letzten_runde(seite, session) -> None:
    seite._sofort.click()
    assert seite._aufstellung.topLevelItemCount() == len(session.fahrten)
    assert seite._aufstellungskasten.title() == "Startaufstellung fuers Rennen"


def test_ein_sprung_zurueck_leert_die_aufstellung_wieder(seite) -> None:
    seite._sofort.click()
    seite._zurueck.click()
    assert seite._aufstellung.topLevelItemCount() == 0


# -- Die drei Splitfarben ---------------------------------------------------
def test_ungefahrene_sektoren_bleiben_leer(seite, session) -> None:
    fahrt = session.fahrten[0]
    seite._springe(fahrt.sektorenden_ms[0])
    werte = _farben(seite, session, fahrt)
    assert werte[0] != "" and werte[1] == "" and werte[-1] == ""


def test_der_beste_split_ist_lila(seite, session) -> None:
    seite._sofort.click()
    lila = session.beste_splits_zu(session.dauer_ms)
    for nummer, halter in enumerate(lila):
        fahrt = next(f for f in session.fahrten if f.teilnehmer == halter)
        assert _farben(seite, session, fahrt)[nummer] == qs.FARBE_BESTER.name()


def test_lila_haelt_je_sektor_genau_einer(seite, session) -> None:
    seite._sofort.click()
    for nummer in range(len(session.fahrten[0].sektoren_ms)):
        traeger = [
            f
            for f in session.fahrten
            if _farben(seite, session, f)[nummer] == qs.FARBE_BESTER.name()
        ]
        assert len(traeger) == 1


def test_langsamer_als_der_fuehrende_ist_rot_schneller_gruen(seite, session) -> None:
    seite._sofort.click()
    lila = session.beste_splits_zu(session.dauer_ms)
    geprueft = 0
    for fahrt in session.fahrten:
        werte = _farben(seite, session, fahrt)
        for nummer, farbe in enumerate(werte):
            if lila[nummer] == fahrt.teilnehmer:
                continue
            abstand = session.splitvergleich(fahrt, nummer)
            if abstand is None:
                assert farbe == ""
                continue
            erwartet = qs.FARBE_LANGSAMER if abstand > 0 else qs.FARBE_SCHNELLER
            assert farbe == erwartet.name()
            geprueft += 1
    assert geprueft > 0


def test_neben_dem_split_steht_der_abstand(seite, session) -> None:
    """Die Farbe allein traegt die Aussage nicht - die Zahl steht daneben."""
    seite._sofort.click()
    zweiter = session.fahrten[1]
    zeile = _zeile_von(seite, session, zweiter)
    abstand = session.splitvergleich(zweiter, 0)
    assert abstand is not None
    assert zeile[qs.SPALTE_SEKTOR_AB].count(":") >= 1
    assert zeile[qs.SPALTE_SEKTOR_AB].endswith(
        ("+" if abstand > 0 else "-") + f"{abs(abstand) / 1000:.3f}"
    )


def test_der_erste_fahrer_hat_keine_splitfarbe(seite, session) -> None:
    """Wer als Erster faehrt, misst sich gegen niemanden - ausser lila."""
    seite._springe(session.fahrten[0].ziel_ms)
    erster = session.fahrten[0]
    lila = session.beste_splits_zu(session.fahrten[0].ziel_ms)
    werte = _farben(seite, session, erster)
    for nummer, farbe in enumerate(werte):
        assert lila[nummer] == erster.teilnehmer
        assert farbe == qs.FARBE_BESTER.name()


# -- Punkt 93, Block 1 ------------------------------------------------------
def _nach_der_nten_ankunft(session, n: int) -> float:
    """Der Zeitpunkt kurz nach der n-ten Zielankunft der Session."""
    ziele = sorted(f.ziel_ms for f in session.fahrten)
    return ziele[n - 1] + 1


def test_die_tafel_hat_eine_spalte_fuers_intervall(seite, session) -> None:
    """A2: Rueckstand auf die Spitze und Abstand zum Vordermann.

    Zwei verschiedene Fragen - die Tafel beantwortete bisher nur die
    erste.
    """
    liste = seite._rangliste
    kopf = [liste.headerItem().text(s) for s in range(liste.columnCount())]
    assert kopf[qs.SPALTE_RUECKSTAND] == "Rueckstand"
    assert kopf[qs.SPALTE_INTERVALL] == "Intervall"


def test_die_intervalle_summieren_sich_zum_rueckstand(seite, session) -> None:
    """Sonst stuenden zwei Zahlen da, die einander widersprechen."""
    seite._springe(session.dauer_ms)
    zeilen = [z for z in _zeilen(seite) if z[qs.SPALTE_POS]]
    assert len(zeilen) == len(session.fahrten)
    # Der Fuehrende hat weder Rueckstand noch Intervall.
    assert zeilen[0][qs.SPALTE_RUECKSTAND] == ""
    assert zeilen[0][qs.SPALTE_INTERVALL] == ""

    def sekunden(text: str) -> float:
        return float(text.replace("+", "").replace(",", "."))

    gesamt = 0.0
    for zeile in zeilen[1:]:
        gesamt += sekunden(zeile[qs.SPALTE_INTERVALL])
        assert sekunden(zeile[qs.SPALTE_RUECKSTAND]) == pytest.approx(gesamt, abs=0.002)


def test_wer_auf_der_schnellen_runde_ist_wird_hervorgehoben(seite, session) -> None:
    """A6: Unter dreissig Zeilen findet man ihn sonst nicht.

    Der Zeitpunkt wird **gesucht**, nicht geraten: Die Mitte zwischen
    Ausfahrt und Ziel liegt noch in der Aufwaermrunde, dort ist niemand
    auf der gezeiteten.
    """
    fahrt = session.fahrten[0]
    mitte = (fahrt.runde_ab_ms + fahrt.ziel_ms) / 2
    seite._springe(mitte)
    liste = seite._rangliste
    unterwegs = [
        liste.topLevelItem(i)
        for i in range(liste.topLevelItemCount())
        if liste.topLevelItem(i).text(_spalte_lage(session))
        == ql.Lage.SCHNELLE_RUNDE.bezeichnung
    ]
    assert unterwegs, "Zu diesem Zeitpunkt muss jemand auf der Runde sein"
    for zeile in unterwegs:
        assert zeile.background(qs.SPALTE_AUTO).color() == qs.FARBE_UNTERWEGS
    # Und wer noch in der Box steht, bleibt unbehelligt.
    wartend = [
        liste.topLevelItem(i)
        for i in range(liste.topLevelItemCount())
        if liste.topLevelItem(i).text(_spalte_lage(session)) == ql.Lage.WARTET.bezeichnung
    ]
    for zeile in wartend:
        assert zeile.background(qs.SPALTE_AUTO).color() != qs.FARBE_UNTERWEGS


def test_nach_einer_ankunft_steht_da_wer_verdraengt_wurde(seite, session) -> None:
    """A7: Kommt einer ins Ziel, steht kurz da, wen er um wie viel schob.

    Gesucht wird eine Ankunft, die wirklich jemanden verdraengt hat -
    wer sich hinten einreiht, schiebt niemanden, und die dritte Ankunft
    dieser Session tut genau das.
    """
    fenster = seite._konfiguration.wert("qualifying", "hervorhebung_ms")
    mit_wirkung = [
        f
        for f in session.fahrten
        if (a := session.letzte_zielankunft(f.ziel_ms, fenster)) is not None
        and a.fahrt is f
        and a.verdraengt is not None
    ]
    assert mit_wirkung, "Diese Session muss Verdraengungen haben"
    seite._springe(mit_wirkung[0].ziel_ms)

    text = seite._verdraengung.text()
    assert "verdraengt" in text, text
    ankunft = session.letzte_zielankunft(seite.zeit_ms, fenster)
    assert ankunft is not None and ankunft.verdraengt is not None
    assert session.teilnehmer[ankunft.fahrt.teilnehmer].kuerzel in text
    assert session.teilnehmer[ankunft.verdraengt.teilnehmer].kuerzel in text


def test_der_hinweis_verschwindet_wieder(seite, session) -> None:
    """Sonst stuende am Ende der Session der letzte Wechsel fuer immer da."""
    fenster = seite._konfiguration.wert("qualifying", "hervorhebung_ms")
    seite._springe(_nach_der_nten_ankunft(session, 3))
    assert seite._verdraengung.text().strip()
    seite._springe(_nach_der_nten_ankunft(session, 3) + fenster + 1)
    assert seite._verdraengung.text() == " "


def _kunst_session(konfig, session) -> ql.Qualifying:
    """Drei Autos, jedes schneller als das vorige - also zwei Polewechsel.

    Die echte Session taugt dafuer nicht: Dort faehrt das schnellste
    Auto zuerst (die Reihenfolge des ersten Rennens ist aufsteigend nach
    Qualifying-Faehigkeit), seine 132,260 s haelt bis zum Schluss, und
    die Pole wechselt kein einziges Mal. Hier steht die Reihenfolge fest,
    statt sie aus einem Seed zu hoffen.
    """
    vorlage = session.fahrten[0]
    fahrten = tuple(
        ql.Fahrt(
            teilnehmer=n,
            reihenfolge=n,
            beginn_ms=n * 60_000,
            ziel_ms=n * 60_000 + 200_000,
            zeit_ms=100_000 - n * 1_000,
            sektoren_ms=vorlage.sektoren_ms,
            tagesform=1.0,
            zustand="trocken",
            grip=1.0,
        )
        for n in range(3)
    )
    return ql.Qualifying(
        strecke=session.strecke,
        teilnehmer=session.teilnehmer[:3],
        fahrten=fahrten,
        wetter=session.wetter,
        aufstellung=(2, 1, 0),
        dauer_ms=fahrten[-1].ziel_ms + 10_000,
    )


def test_der_erste_im_ziel_uebernimmt_keine_pole(konfig, session) -> None:
    """Er eroeffnet sie - verdraengt hat er niemanden."""
    kunst = _kunst_session(konfig, session)
    fenster = konfig.wert("qualifying", "hervorhebung_ms")
    erste = kunst.letzte_zielankunft(kunst.fahrten[0].ziel_ms, fenster)
    assert erste is not None
    assert erste.platz == 1
    assert erste.verdraengt is None
    assert not erste.neue_pole


def test_die_neue_pole_leuchtet_auf(qtbot, konfig, session) -> None:
    """A8: Und nur sie - nicht jede Ankunft."""
    kunst = _kunst_session(konfig, session)
    seite = qs.Qualifyingseite(konfig)
    qtbot.addWidget(seite)
    seite.zeige_session(kunst)

    # Die zweite Ankunft ist schneller als die erste: Pole wechselt.
    seite._springe(kunst.fahrten[1].ziel_ms)
    liste = seite._rangliste
    erste = liste.topLevelItem(0)
    assert erste.text(qs.SPALTE_POS) == "1"
    assert erste.background(qs.SPALTE_AUTO).color() == qs.FARBE_NEUE_POLE
    assert "neue Pole" in seite._verdraengung.text()
    # Die uebrigen Zeilen leuchten nicht mit.
    for i in range(1, liste.topLevelItemCount()):
        assert liste.topLevelItem(i).background(qs.SPALTE_AUTO).color() != (
            qs.FARBE_NEUE_POLE
        )


def test_nach_dem_fenster_leuchtet_die_pole_nicht_mehr(qtbot, konfig, session) -> None:
    kunst = _kunst_session(konfig, session)
    seite = qs.Qualifyingseite(konfig)
    qtbot.addWidget(seite)
    seite.zeige_session(kunst)
    seite._springe(kunst.dauer_ms)
    erste = seite._rangliste.topLevelItem(0)
    assert erste.background(qs.SPALTE_AUTO).color() != qs.FARBE_NEUE_POLE


# -- Punkt 93, Block 2 ------------------------------------------------------
def test_der_knopf_springt_zur_naechsten_zielankunft(seite, session) -> None:
    """A23: Bei 75 Minuten Session der meistgebrauchte Knopf."""
    ziele = sorted(f.ziel_ms for f in session.fahrten)
    seite._springe(0)
    seite._zur_naechsten_ankunft()
    assert seite.zeit_ms == ziele[0]
    seite._zur_naechsten_ankunft()
    assert seite.zeit_ms == ziele[1]


def test_der_sprung_landet_auf_der_ankunft_nicht_davor(seite, session) -> None:
    """Sonst stuende die neue Zeit noch nicht in der Tafel."""
    ziele = sorted(f.ziel_ms for f in session.fahrten)
    seite._springe(0)
    seite._zur_naechsten_ankunft()
    fertig = [z for z in _zeilen(seite) if z[qs.SPALTE_POS]]
    assert len(fertig) == 1, "Genau der eben Angekommene steht mit Position da"
    assert seite.zeit_ms == ziele[0]


def test_nach_der_letzten_ankunft_geht_es_ans_ende(seite, session) -> None:
    seite._springe(max(f.ziel_ms for f in session.fahrten))
    seite._zur_naechsten_ankunft()
    assert seite.zeit_ms == session.dauer_ms


def test_das_wetterband_zeigt_den_ganzen_verlauf(seite, session) -> None:
    """A13: Wo war es trocken, wo nass."""
    band = seite._wetterband
    abschnitte = band.abschnitte
    assert len(abschnitte) == len(session.wetter.abschnitte)
    assert [zustand for zustand, _von, _bis in abschnitte] == list(
        session.wetter.zustaende
    )
    # Lueckenlos von null bis zum Sessionende.
    assert abschnitte[0][1] == 0
    assert abschnitte[-1][2] == session.dauer_ms
    for vorher, nachher in zip(abschnitte, abschnitte[1:], strict=False):
        assert vorher[2] == nachher[1]


def test_die_marke_des_wetterbands_laeuft_mit(seite, session) -> None:
    seite._springe(0)
    assert seite._wetterband._marke_ms == 0
    seite._springe(session.dauer_ms // 2)
    assert seite._wetterband._marke_ms == session.dauer_ms // 2


def test_nasser_ist_dunkler(konfig) -> None:
    """Die Farben sind sequenziell, nicht kategorial.

    "Wie nass" ist eine Groesse mit Richtung. Waeren die Toene bunt
    durcheinander, muesste man die Legende lesen, statt das Band zu
    sehen.
    """
    from rennmanager.ui.wetterband import Wetterband

    reihe = ["trocken", "heiss", "wechselhaft", "regen", "starkregen"]
    helligkeit = [Wetterband.farbe_fuer(z).lightness() for z in reihe]
    # Heiss ist der eine Ausreisser - es ist ein Sonnenton, kein Nasston.
    assert helligkeit[2] > helligkeit[3] > helligkeit[4]
    assert helligkeit[0] > helligkeit[2]


# -- Punkt 93, Block 3 ------------------------------------------------------
def test_die_streckengrafik_zeigt_die_strecke_der_session(seite, session) -> None:
    """A9: Die Ansicht gibt es fuers Rennen schon."""
    assert seite._ansicht.strecke is session.strecke


def test_auf_der_strecke_stehen_nur_die_auf_der_schnellen_runde(seite, session):
    """Ein Feld aus Aufwaermpunkten wuerde die zwei zudecken, auf die es ankommt."""
    fahrt = session.fahrten[0]
    mitte = (fahrt.runde_ab_ms + fahrt.ziel_ms) / 2
    seite._springe(mitte)

    auf_der_runde = {
        session.teilnehmer[s.fahrt.teilnehmer].kuerzel
        for s in session.lage_zu(mitte)
        if s.lage is ql.Lage.SCHNELLE_RUNDE
    }
    assert auf_der_runde, "Zu diesem Zeitpunkt muss jemand auf der Runde sein"
    gezeichnet = {kuerzel for _ort, kuerzel, _farbe, _spieler in seite._ansicht._autos}
    assert gezeichnet == auf_der_runde


def test_am_anfang_und_am_ende_ist_die_strecke_leer(seite, session) -> None:
    seite._springe(0)
    assert seite._ansicht._autos == []
    seite._springe(session.dauer_ms)
    assert seite._ansicht._autos == []


def test_der_punkt_wandert_die_runde_entlang(seite, session) -> None:
    """Sonst waere es kein abfahrender Punkt, sondern ein stehender."""
    fahrt = session.fahrten[0]
    kuerzel = session.teilnehmer[fahrt.teilnehmer].kuerzel
    orte = []
    for anteil in (0.1, 0.4, 0.7, 0.95):
        seite._springe(fahrt.runde_ab_ms + anteil * fahrt.zeit_ms)
        orte += [
            ort for ort, kz, _farbe, _spieler in seite._ansicht._autos if kz == kuerzel
        ]
    assert len(orte) == 4
    assert orte == sorted(orte)
    assert orte[0] < session.strecke.laenge_m * 0.2
    assert orte[-1] > session.strecke.laenge_m * 0.9


# -- Punkt 93, Block 6: die Streckenbestmarke (A17) -------------------------
def test_ohne_rekord_sagt_die_bestmarke_das_auch(seite) -> None:
    """Ein leeres Feld saehe aus wie ein Fehler."""
    seite.zeige_bestmarke(None)
    assert "Noch keine" in seite._bestmarke.text()


def test_die_bestmarke_nennt_zeit_fahrer_und_jahr(seite, konfig) -> None:
    """A17: die schnellste je gefahrene Qualirunde hier."""
    from rennmanager.kern.statistik import Rekord

    rekord = Rekord(strecke="Catalunya", zeit_ms=78_432, fahrer=7, saison=2029, rennen=4)
    seite.zeige_bestmarke(rekord, "Lena Moser")
    text = seite._bestmarke.text()
    assert "Lena Moser" in text
    assert "2029" in text
    assert "1:18.432" in text


def test_der_qualirekord_wird_getrennt_vom_rennrekord_gefuehrt(konfig) -> None:
    """Eine Qualirunde faehrt man auf leerer Strecke mit frischen Reifen.

    In einem Topf mit den Rennrunden fiele der Rennrekord nie wieder.
    """
    from rennmanager.kern import statistik as st

    zahlen = st.Statistik(konfig)
    assert zahlen.melde_qualirunde("Monza", 80_000, fahrer=3, saison=2026, rennen=1)
    assert zahlen.qualirekord("Monza").zeit_ms == 80_000
    assert zahlen.rekord("Monza") is None, "Der Rennrekord bleibt unberuehrt"

    # Langsamer faellt durch, schneller setzt neu.
    assert not zahlen.melde_qualirunde("Monza", 80_001, 4, 2026, 2)
    assert zahlen.melde_qualirunde("Monza", 79_500, 4, 2026, 2)
    assert zahlen.qualirekord("Monza").fahrer == 4
    # Und eine Zeit von null ist keine Zeit.
    assert not zahlen.melde_qualirunde("Monza", 0, 5, 2026, 3)


# --- Punkt 98: Name in der Zeitentafel, Unterlegung am Sessionende --------
def test_die_zeitentafel_nennt_den_fahrernamen(qtbot, konfig) -> None:
    """Punkt 98: "JOR" sagt niemandem etwas - der Name steht daneben."""
    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)
    seite._sofort.click()

    assert seite._rangliste.headerItem().text(qs.SPALTE_NAME) == "Fahrer"
    namen = {f.nummer: f.name for f in fenster.welt.fahrer}
    zeile = seite._rangliste.topLevelItem(0)
    nummer = zeile.data(qs.SPALTE_POS, Qt.UserRole)
    assert zeile.text(qs.SPALTE_NAME) == kurzname(namen[nummer])
    # Und der Nachname steht wirklich voll da.
    assert fenster.welt.fahrer[nummer].nachname in zeile.text(qs.SPALTE_NAME)


def test_am_sessionende_bleibt_keine_zeile_unterlegt(qtbot, konfig) -> None:
    """Punkt 98: Am Ende ist nichts mehr "gerade passiert".

    Die Wiedergabe haelt beim letzten Zielankunft an - ohne diese Regel
    laege sie fuer immer im Hervorhebungsfenster, und die Zeile des
    Letzten blieb dauerhaft unterlegt.
    """
    from PySide6.QtGui import QBrush

    fenster = Hauptfenster(konfig)
    qtbot.addWidget(fenster)
    seite = gefahrenes_qualifying(fenster)
    seite._sofort.click()

    liste = seite._rangliste
    leer = QBrush()
    for stelle in range(liste.topLevelItemCount()):
        zeile = liste.topLevelItem(stelle)
        assert zeile.background(qs.SPALTE_POS) == leer, (
            f"Zeile {stelle} ist am Sessionende noch unterlegt"
        )
