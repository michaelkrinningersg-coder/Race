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


# --- Kleine Welt fuer teure Laeufe (Punkt 77) -----------------------------
# Ein Rennwochenende in voller Groesse rechnet 20 Ligen zu je 30 Autos -
# gemessen 54 Sekunden. Dieselbe Logik mit 3 Ligen zu je 4 Autos braucht
# 1,45 Sekunden, also den 37. Teil. Wer prueft, *ob* Punkte gebucht und
# Tabellen fortgeschrieben werden, braucht die 600 Fahrer nicht; wer die
# Ligastruktur selbst prueft, schon. Deshalb steht beides bereit.
KLEINE_LIGEN = 3
KLEINE_AUTOS_JE_LIGA = 4


@pytest.fixture(scope="session")
def kleine_konfiguration():
    """Dieselbe Konfiguration, nur mit 3 Ligen zu je 4 Autos.

    Alle Balancing-Werte bleiben, wie sie sind - nur die Groesse der Welt
    schrumpft. Die Ligastaerken rechnen sich aus ``bester_liga20_kmh`` und
    ``zuwachs_je_liga_kmh``, laufen also weiter, nur ueber drei statt
    zwanzig Stufen.
    """
    import copy
    from dataclasses import replace

    from rennmanager import konfiguration as kf

    gross = kf.lade()
    roh = copy.deepcopy(gross.roh)
    roh["ligen"]["anzahl"] = KLEINE_LIGEN
    roh["ligen"]["autos_je_liga"] = KLEINE_AUTOS_JE_LIGA
    # Der Spieler faengt in der untersten Liga an - in der kleinen Welt
    # ist das die dritte, nicht die zwanzigste. Ohne das verteilt
    # ``_sortiere_in_ligen`` die Fahrer auf eine Liga, die es nicht gibt.
    roh["ligen"]["startliga"] = KLEINE_LIGEN
    je_team = roh["teams"]["autos_je_team"]
    roh["teams"]["anzahl"] = (KLEINE_LIGEN * KLEINE_AUTOS_JE_LIGA) // je_team
    return replace(gross, roh=roh)


@pytest.fixture(scope="session")
def kleine_welt(kleine_konfiguration):
    """Eine Welt aus ``kleine_konfiguration``, Spieler in der letzten Liga.

    **Nicht veraendern.** Das Fixture gilt fuer die ganze Sitzung; wer die
    Welt umbaut, zieht alle anderen Tests mit. ``Welt`` ist eingefroren,
    ein ``replace`` liefert eine eigene Kopie.
    """
    from rennmanager.kern import welt as kw
    from rennmanager.kern.zufall import Seedquelle

    return kw.erzeuge(
        kleine_konfiguration,
        Seedquelle(12).zweig("welt"),
        spielerliga=KLEINE_LIGEN,
    )
