"""Gemeinsame Test-Einstellungen."""

import os

# Die Oberflaechen-Tests brauchen keinen Bildschirm.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def spielstandordner(tmp_path, monkeypatch):
    """Haelt Autosave und Schnellspeicher aus dem echten Benutzerordner.

    Seit Punkt 17 schreibt jeder Tageswechsel und jedes Rennwochenende
    einen Autosave nach ``~/.rennmanager``. In Tests darf das nicht
    passieren - sonst haette eine Testreihe den Spielstand ueberschrieben,
    an dem gerade jemand sitzt.

    Umgebogen wird ``HOME``, nicht die Funktion: So laeuft im Test
    dieselbe ``spielstandordner``, die auch im Spiel laeuft.
    """
    from rennmanager.kern import spielstand as kern_spielstand

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return kern_spielstand.spielstandordner()
