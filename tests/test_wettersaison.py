"""Das Wetter einer Saison (Punkt 39, Erweiterung zu GDD 7).

Drei Regeln des Auftraggebers stehen hier auf dem Pruefstand: das Band
der Wechselneigung je Streckenprofil, hoechstens zwei Wechsel je Rennen
mit je einer Stufe, und ueber eine Saison 75 bis 85 Prozent der Rennen
rein trocken oder heiss.
"""

import pytest

from rennmanager.kern import wettersaison as ws
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

# Der Zielkorridor des Auftraggebers fuer rein trockene Rennen.
TROCKEN_MIN = 0.75
TROCKEN_MAX = 0.85


@pytest.fixture(scope="module")
def k():
    return lade()


@pytest.fixture(scope="module")
def profile(k):
    return tuple(k.wert("wetter", "profil"))


def test_jedes_profil_hat_ein_band(k, profile):
    for profil in profile:
        band = ws.baender(k, profil)
        assert "wechselneigung" in band
        unten, oben = band["wechselneigung"]
        assert 0.0 <= unten <= oben <= 1.0


def test_ein_unbekanntes_profil_wirft(k):
    with pytest.raises(ws.WettersaisonFehler):
        ws.baender(k, "Mondbasis")


def test_die_verteilung_ist_normiert(k, profile):
    for profil in profile:
        saison = ws.wuerfle_saison(k, profil, 2030, Seedquelle(1))
        assert sum(saison.verteilung.values()) == pytest.approx(1.0)


def test_dieselbe_saison_hat_dasselbe_wetter(k):
    """Der Zweig haengt an Profil und Jahr, nicht an der Aufrufreihenfolge."""
    quelle = Seedquelle(9)
    erst = ws.wuerfle_saison(k, "gemaessigt", 2031, quelle)
    # Dazwischen andere Fragen stellen - das darf nichts aendern.
    ws.wuerfle_saison(k, "regenreich", 2031, quelle)
    ws.wuerfle_saison(k, "gemaessigt", 2032, quelle)
    nochmal = ws.wuerfle_saison(k, "gemaessigt", 2031, quelle)
    assert erst == nochmal


def test_verschiedene_jahre_bringen_verschiedenes_wetter(k):
    quelle = Seedquelle(9)
    jahre = {
        ws.wuerfle_saison(k, "gemaessigt", jahr, quelle).wechselneigung
        for jahr in range(2030, 2040)
    }
    assert len(jahre) > 1


def test_in_der_wueste_wechselt_es_praktisch_nie(k):
    """Der Auftraggeber: bei Wuestenrennen quasi nie, sonst bis 40 Prozent."""
    wueste = ws.baender(k, "heiss_trocken")["wechselneigung"]
    assert wueste[1] <= 0.05
    for profil in k.wert("wetter", "profil"):
        assert ws.baender(k, profil)["wechselneigung"][1] <= 0.40


def test_hoechstens_zwei_wechsel_und_immer_nur_eine_stufe(k):
    """Beide Regeln kommen vom Auftraggeber."""
    kette = list(k.wert("wetter", "kette"))
    hoechstens = k.wert("wetter", "saison", "wechsel_max")
    quelle = Seedquelle(4)
    saison = ws.wuerfle_saison(k, "regenreich", 2030, quelle)
    for n in range(400):
        lagen = ws.rennwetter(saison, k, quelle.zweig("rennen", n))
        assert 1 <= len(lagen) <= hoechstens + 1
        for davor, danach in zip(lagen, lagen[1:], strict=False):
            assert abs(kette.index(davor) - kette.index(danach)) == 1


def test_drei_viertel_bis_sechs_siebtel_bleiben_trocken(k):
    """75 bis 85 Prozent der Rennen ohne Wechsel und ohne Nass.

    Gemessen ueber 30 Saisons zu 20 Rennen, wie der Auftraggeber es
    verlangt hat. Der Wert schwankt je Saison; ueber alle zusammen muss
    er im Korridor liegen.
    """
    quelle = Seedquelle(2024)
    trocken = 0
    gesamt = 0
    for jahr in range(2030, 2060):
        wetterjahr = ws.saisonwetter(k, jahr, quelle)
        for nummer, profil in enumerate(sorted(wetterjahr)):
            for rennen in range(20 // len(wetterjahr) + 1):
                lagen = ws.rennwetter(
                    wetterjahr[profil], k, quelle.zweig("lauf", jahr, nummer, rennen)
                )
                gesamt += 1
                if len(lagen) == 1 and lagen[0] in ("trocken", "heiss"):
                    trocken += 1
    anteil = trocken / gesamt
    assert TROCKEN_MIN <= anteil <= TROCKEN_MAX, f"{anteil:.1%} rein trocken"
