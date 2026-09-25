"""Tests fuer die Mini-Flaggen in den Fahrertabellen (Punkt 105).

Zwei Sorten Zusicherung: Das Modul zeichnet jede Nation, die in der
Konfiguration vorkommt - und die Tabellen setzen die Flagge wirklich.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from rennmanager import konfiguration as kf

pytest.importorskip("PySide6")

from rennmanager.ui import flaggen  # noqa: E402


@pytest.fixture(scope="module")
def konfig() -> kf.Konfiguration:
    return kf.lade()


def nationen_der_konfiguration() -> set[str]:
    """Alle Herkunftslaender aus ``namen.toml`` (GDD 12).

    Gelesen wird die Datei direkt: ``Konfiguration.wert`` kennt nur die
    Balancingwerte, die Namen stehen woanders.
    """
    roh = tomllib.loads(
        Path("konfiguration/namen.toml").read_text(encoding="utf-8")
    )
    laender = roh["fahrer"]["laender"]
    return set(laender["europa"]) | set(laender["nordamerika"])


def test_jede_nation_der_konfiguration_hat_eine_flagge(qtbot) -> None:
    """Sonst stuende bei einem Fahrer nichts, und niemand merkte es.

    Beim ersten Bau fehlten Tschechien und Lettland - die 24 Nationen
    einer gewuerfelten Welt deckten nicht die 32 der Konfiguration ab.
    """
    ohne = sorted(
        land for land in nationen_der_konfiguration()
        if flaggen.flagge(land).isNull()
    )
    assert not ohne, f"ohne Flagge: {ohne}"


def test_eine_unbekannte_nation_liefert_ein_leeres_symbol(qtbot) -> None:
    """Kein Absturz, nur nichts - ein leeres QIcon ist gueltig."""
    assert flaggen.flagge("Atlantis").isNull()
    assert flaggen.flagge("").isNull()


def test_die_flagge_hat_die_vorgesehene_groesse(qtbot) -> None:
    """Groesser sprengt die Zeilenhoehe, kleiner wird matschig."""
    symbol = flaggen.flagge("Deutschland")
    groessen = symbol.availableSizes()
    assert groessen
    assert groessen[0].width() == flaggen.BREITE_PX
    assert groessen[0].height() == flaggen.HOEHE_PX


def abdruck(land: str) -> bytes:
    """Die Bildpunkte einer Flagge, zum Vergleichen.

    Direkt aus dem Bild gelesen und nicht ueber ``QBuffer``: Ein
    ``QBuffer(QByteArray())`` haelt eine Referenz auf ein temporaeres
    Objekt, das Python sofort wieder einsammelt - der Testlauf stuerzte
    damit ab, statt eine Zusicherung zu melden.
    """
    bild = flaggen.flagge(land).pixmap(
        flaggen.BREITE_PX, flaggen.HOEHE_PX
    ).toImage()
    return bytes(bild.constBits())


def test_verschiedene_nationen_sehen_verschieden_aus(qtbot) -> None:
    """Eine Flagge, die wie jede andere aussieht, traegt keine Aussage.

    Geprueft wird ueber die Bildpunkte, nicht ueber die Farbtabelle:
    Nur so faellt auf, wenn zwei Muster zufaellig dasselbe Bild ergeben.
    """
    proben = [
        "Deutschland", "Frankreich", "Schweden", "Schweiz",
        "Grossbritannien", "USA", "Griechenland", "Tschechien", "Polen",
    ]
    abdruecke = {land: abdruck(land) for land in proben}
    assert len(set(abdruecke.values())) == len(proben)


def test_gleiche_muster_trennt_nur_der_farbton(qtbot) -> None:
    """Der Preis des Selbstzeichnens, gemessen statt behauptet.

    Italien und Mexiko sind beide gruen-weiss-rot senkrecht; was sie
    wirklich unterscheidet, ist das Wappen, und das ist bei elf Pixeln
    Hoehe nicht darstellbar. Erwartet hatte ich zwei identische Bilder -
    gemessen sind sie es **nicht**, weil die Farbtoene auseinandergehen
    (Italien #008c45/#cd212a, Mexiko #006847/#ce1126).

    Unterscheidbar heisst aber nicht erkennbar: Auf einen Blick sieht
    man den Unterschied nicht. Deshalb traegt jede Flagge den
    Landesnamen als Tooltip.
    """
    paare = [("Italien", "Mexiko"), ("Slowenien", "Slowakei")]
    for eins, zwei in paare:
        assert abdruck(eins) != abdruck(zwei), f"{eins} und {zwei} gleich"


def test_setze_flagge_haengt_symbol_und_tooltip_an(qtbot) -> None:
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

    baum = QTreeWidget()
    baum.setColumnCount(2)
    qtbot.addWidget(baum)
    zeile = QTreeWidgetItem(baum, ["A", "B"])

    flaggen.setze_flagge(zeile, 1, "Deutschland")
    assert not zeile.icon(1).isNull()
    # Der Tooltip traegt den Namen: Die Flagge allein gibt ihn bei
    # dieser Groesse nicht immer her.
    assert zeile.toolTip(1) == "Deutschland"
    # Spalte 0 bleibt unberuehrt.
    assert zeile.icon(0).isNull()


def test_ohne_nation_bleibt_die_zelle_leer(qtbot) -> None:
    """Ein Feld aus ``rennen.starterfeld`` hat keinen Fahrer dahinter."""
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

    baum = QTreeWidget()
    baum.setColumnCount(2)
    qtbot.addWidget(baum)
    zeile = QTreeWidgetItem(baum, ["A", "B"])

    flaggen.setze_flagge(zeile, 1, "")
    flaggen.setze_flagge(zeile, 1, "Atlantis")
    assert zeile.icon(1).isNull()
    assert zeile.toolTip(1) == ""


# -- Die Nation muss durch die ganze Kette kommen ---------------------------
def test_die_nation_kommt_vom_fahrer_bis_ins_rennfeld(konfig) -> None:
    """Sie wird zweimal umgepackt, und beim zweiten Mal ging sie verloren.

    ``welt.starterfeld`` baut Teilnehmer aus Fahrern, und
    ``saison.startfeld`` baut sie **noch einmal** neu, nur mit der
    Startaufstellung des Qualifyings als Reihenfolge. Was dort nicht
    abgeschrieben wird, ist im Rennen weg: Die Flaggen der Rangliste
    fehlten genau deshalb, waehrend die Zeitentafel des Qualifyings sie
    schon hatte.
    """
    from rennmanager.kern import qualifying as ql
    from rennmanager.kern import saison as sa
    from rennmanager.kern import strecke as st
    from rennmanager.kern import welt as kw
    from rennmanager.kern.zufall import Seedquelle

    welt = kw.erzeuge(konfig, Seedquelle(3).zweig("welt"))
    feld = kw.starterfeld(welt)
    assert all(t.land for t in feld), "welt.starterfeld"

    strecke = st.lade(konfig, konfig.strecken[0]["name"])
    quali = ql.fahre(konfig, strecke, feld, Seedquelle(3).zweig("quali"))
    assert all(t.land for t in quali.teilnehmer), "durchs Qualifying"

    rennfeld = sa.startfeld(konfig, welt, {}, quali)
    assert all(t.land for t in rennfeld), "saison.startfeld"
    # Und es ist wirklich die Nation des richtigen Fahrers.
    nach_nummer = {f.nummer: f.land for f in welt.fahrer}
    for teilnehmer in rennfeld:
        assert teilnehmer.land == nach_nummer[teilnehmer.nummer]
