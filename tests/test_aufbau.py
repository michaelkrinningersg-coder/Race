"""Test der Architektur.

Arbeitsregel: Der Simulationskern ist von der Oberflaeche getrennt. Konkret
darf kein Modul unter ``rennmanager.kern`` Qt importieren, sonst waere der
Kern ohne Oberflaeche nicht mehr lauffaehig und nicht mehr frei testbar.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

KERN = Path(__file__).resolve().parent.parent / "rennmanager" / "kern"


def _importierte_module(pfad: Path) -> set[str]:
    baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
    module: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            module.update(alias.name for alias in knoten.names)
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            module.add(knoten.module)
    return module


@pytest.mark.parametrize("pfad", sorted(KERN.glob("*.py")), ids=lambda p: p.name)
def test_kern_kennt_keine_oberflaeche(pfad: Path) -> None:
    verboten = [
        name
        for name in _importierte_module(pfad)
        if name.split(".")[0] in {"PySide6", "PyQt5", "PyQt6", "shiboken6"}
    ]
    assert not verboten, f"{pfad.name} importiert die Oberflaeche: {verboten}"


def test_konfiguration_kennt_keine_oberflaeche() -> None:
    pfad = KERN.parent / "konfiguration.py"
    verboten = [
        name
        for name in _importierte_module(pfad)
        if name.split(".")[0].startswith(("PySide", "PyQt"))
    ]
    assert not verboten, f"konfiguration.py importiert die Oberflaeche: {verboten}"
