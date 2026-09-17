"""Tests fuer die Zeitanzeige (GDD 4: m:ss.mmm bzw. h:mm:ss.mmm)."""

import pytest

from rennmanager.kern import zeit


@pytest.mark.parametrize(
    ("ms", "erwartet"),
    [
        (0, "0:00.000"),
        (1, "0:00.001"),
        (999, "0:00.999"),
        (1_000, "0:01.000"),
        (83_456, "1:23.456"),
        (59_999, "0:59.999"),
        (3_599_999, "59:59.999"),
        (3_600_000, "1:00:00.000"),
        (3_723_004, "1:02:03.004"),
        (7_384_500, "2:03:04.500"),
    ],
)
def test_formatiere_dauer(ms: int, erwartet: str) -> None:
    assert zeit.formatiere_dauer(ms) == erwartet


@pytest.mark.parametrize(
    ("ms", "erwartet"),
    [
        (0, "+0.000"),
        (512, "+0.512"),
        (12_043, "+12.043"),
        (59_999, "+59.999"),
        (60_000, "+1:00.000"),
        (61_004, "+1:01.004"),
        (3_600_000, "+1:00:00.000"),
        (-312, "-0.312"),
        (-61_004, "-1:01.004"),
    ],
)
def test_formatiere_rueckstand(ms: int, erwartet: str) -> None:
    assert zeit.formatiere_rueckstand(ms) == erwartet


def test_rueckstand_ohne_vorzeichen() -> None:
    assert zeit.formatiere_rueckstand(512, mit_vorzeichen=False) == "0.512"
    # Ein negativer Wert behaelt sein Minus, sonst waere er nicht lesbar.
    assert zeit.formatiere_rueckstand(-512, mit_vorzeichen=False) == "-0.512"


def test_runden_rueckstand() -> None:
    assert zeit.formatiere_runden_rueckstand(1) == "+1 Rd."
    assert zeit.formatiere_runden_rueckstand(3) == "+3 Rd."
    with pytest.raises(ValueError):
        zeit.formatiere_runden_rueckstand(0)


@pytest.mark.parametrize(
    "ms",
    [0, 1, 999, 1_000, 83_456, 3_599_999, 3_600_000, 3_723_004, 35_999_999],
)
def test_lies_dauer_ist_umkehrung(ms: int) -> None:
    assert zeit.lies_dauer(zeit.formatiere_dauer(ms)) == ms


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        ("1:23.456", 83_456),
        ("1:02:03.004", 3_723_004),
        ("12.5", 12_500),
        ("12.05", 12_050),
        ("7", 7_000),
        ("-1:23.456", -83_456),
    ],
)
def test_lies_dauer(text: str, erwartet: int) -> None:
    assert zeit.lies_dauer(text) == erwartet


@pytest.mark.parametrize("text", ["", "abc", "1:2:3:4.000", "1:99:00.000", "1:23.4567"])
def test_lies_dauer_meldet_fehler(text: str) -> None:
    with pytest.raises(ValueError):
        zeit.lies_dauer(text)


def test_zu_ms_rundet_auf_ganze_millisekunden() -> None:
    assert zeit.zu_ms(1.0) == 1_000
    assert zeit.zu_ms(1.2345) == 1_234
    assert zeit.zu_ms(1.2346) == 1_235
    assert isinstance(zeit.zu_ms(1.2346), int)


def test_zerlege_weist_negative_werte_zurueck() -> None:
    with pytest.raises(ValueError):
        zeit.zerlege(-1)
