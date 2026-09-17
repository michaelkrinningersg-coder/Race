"""Tests fuer die Seed-Verwaltung (Arbeitsregel: jede Simulation mit Seed)."""

import pytest

from rennmanager.kern.zufall import Seedquelle


def test_gleicher_pfad_liefert_gleiche_folge() -> None:
    a = Seedquelle(4711).zweig("rennen", 3).zweig("wetter")
    b = Seedquelle(4711).zweig("rennen", 3).zweig("wetter")
    assert a.abgeleiteter_seed == b.abgeleiteter_seed
    assert list(a.generator().random(5)) == list(b.generator().random(5))


def test_generator_beginnt_jedes_mal_von_vorn() -> None:
    quelle = Seedquelle(4711).zweig("qualifying")
    assert list(quelle.generator().random(5)) == list(quelle.generator().random(5))


def test_verschiedene_pfade_liefern_verschiedene_folgen() -> None:
    haupt = Seedquelle(4711)
    quali = haupt.zweig("qualifying")
    rennen = haupt.zweig("rennen")
    assert quali.abgeleiteter_seed != rennen.abgeleiteter_seed
    assert list(quali.generator().random(5)) != list(rennen.generator().random(5))


def test_verschiedene_hauptseeds_liefern_verschiedene_folgen() -> None:
    pfad = ("rennen", 3)
    a = Seedquelle(1).zweig(*pfad)
    b = Seedquelle(2).zweig(*pfad)
    assert a.abgeleiteter_seed != b.abgeleiteter_seed


def test_nummern_trennen_zweige() -> None:
    haupt = Seedquelle(99)
    assert haupt.zweig("rennen", 1).abgeleiteter_seed != haupt.zweig("rennen", 2).abgeleiteter_seed


def test_pfadteile_sind_eindeutig_getrennt() -> None:
    """('ab', 'c') und ('a', 'bc') duerfen nicht denselben Seed ergeben."""
    haupt = Seedquelle(99)
    assert (
        haupt.zweig("ab").zweig("c").abgeleiteter_seed
        != haupt.zweig("a").zweig("bc").abgeleiteter_seed
    )


def test_neuer_zweig_veraendert_bestehende_nicht() -> None:
    """Ein zusaetzlicher Wurf darf keine anderen Ergebnisse verschieben."""
    haupt = Seedquelle(2024)
    vorher = list(haupt.zweig("rennen", 1).generator().random(3))
    haupt.zweig("neuer_zweck").generator().random(100)
    nachher = list(haupt.zweig("rennen", 1).generator().random(3))
    assert vorher == nachher


def test_bezeichnung_zeigt_den_pfad() -> None:
    quelle = Seedquelle(7).zweig("saison", 2).zweig("rennen", 5)
    assert quelle.bezeichnung == "seed:7/saison:2/rennen:5"


def test_zufaelliger_seed_ist_gueltig() -> None:
    quelle = Seedquelle.zufaellig()
    assert 0 <= quelle.seed < 2**64
    quelle.generator().random()


@pytest.mark.parametrize("seed", [-1, 2**64, "7", 1.0, True])
def test_ungueltiger_seed_wird_abgelehnt(seed) -> None:
    with pytest.raises((TypeError, ValueError)):
        Seedquelle(seed)


def test_zweig_ohne_namen_wird_abgelehnt() -> None:
    with pytest.raises(ValueError):
        Seedquelle(1).zweig("")
