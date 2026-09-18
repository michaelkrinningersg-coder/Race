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


@pytest.fixture(autouse=True)
def keine_modalen_dialoge(monkeypatch):
    """Laesst Meldungsfenster im Test nicht warten (Punkt 77).

    ``QMessageBox.information`` und Geschwister oeffnen eine eigene
    Ereignisschleife und warten auf einen Klick. Im Offscreen-Lauf klickt
    niemand - der ganze Testlauf bleibt dann stehen, ohne Ausgabe und
    ohne Fehler, bis ein Zeitlimit ihn abraeumt. Gemessen: ein einziger
    solcher Dialog hielt den Lauf 19 Minuten bei null Prozent CPU.

    Die Meldungen selbst sind hier nicht Gegenstand; wer eine prueft,
    hebt die Ersetzung fuer seinen Test wieder auf.
    """
    try:
        from PySide6.QtWidgets import QMessageBox
    except ImportError:  # pragma: no cover - ohne Qt gibt es nichts zu tun
        return

    for name in ("information", "warning", "critical", "question", "about"):
        monkeypatch.setattr(
            QMessageBox, name, staticmethod(lambda *_a, **_k: QMessageBox.Ok)
        )


# --- Kleine Welt fuer teure Laeufe (Punkt 77) -----------------------------
# Die getesteten Regeln sind **groesseninvariant**: Auf- und Abstieg,
# Punktevergabe und Tabellensortierung stimmen mit 3 Ligen zu je 4 Autos
# genauso wie mit 20 zu je 30. Gemessen kostet ein Rennwochenende dabei
# 1,45 statt 54,27 Sekunden - Faktor 37. Wer die Groesse selbst prueft,
# nimmt ``kf.lade()``; alle anderen nehmen das hier.
#
# Die drei Groessen sind **Parameter**, keine Konstanten: ``verkleinert``
# nimmt sie entgegen, die Fixtures reichen nur die Voreinstellung durch.
KLEINE_LIGEN = 3
KLEINE_AUTOS_JE_LIGA = 4
# Rennkalender und Renndistanz bleiben voreingestellt so, wie sie im Spiel
# sind. Beide **koennen** verkleinert werden - gemessen faellt ein
# ausfuehrliches Wochenende von 24,5 auf 8,8 Sekunden, wenn die Distanz
# von 100 auf 30 km sinkt -, aber beide haben Nebenwirkungen:
#
# * Ein kurzer Kalender laesst die Saison im Test enden, und die
#   Oberflaeche meldet das per Dialog.
# * Eine kurze Distanz laesst keine Reifenstrategie mehr zu: Bei sechs
#   Runden traegt kein Stopp, und die Variantenliste bleibt leer.
#
# Wer sie braucht, fordert sie an: ``verkleinert(rennen=3, distanz_km=30)``.
KLEINE_RENNEN = None
KLEINE_DISTANZ_KM = None


def verkleinert(
    konfiguration=None,
    ligen: int = KLEINE_LIGEN,
    autos_je_liga: int = KLEINE_AUTOS_JE_LIGA,
    rennen: int | None = KLEINE_RENNEN,
    distanz_km: int | None = KLEINE_DISTANZ_KM,
):
    """Dieselbe Konfiguration in klein - Groessen als Parameter.

    Alle Balancing-Werte bleiben, wie sie sind; nur die **Groesse** der
    Welt schrumpft. Die Ligastaerken rechnen sich aus
    ``bester_liga20_kmh`` und ``zuwachs_je_liga_kmh``, laufen also weiter,
    nur ueber weniger Stufen.

    :param ligen: Zahl der Ligen
    :param autos_je_liga: Fahrer je Liga
    :param rennen: Rennen je Saison; ``None`` laesst den echten Kalender
        stehen. Vorsicht: Ein kurzer Kalender laesst die Saison im Test
        enden, und die Oberflaeche meldet das per Dialog.
    :param distanz_km: Renndistanz der untersten Liga; ``None`` laesst die
        echte Distanz stehen. Vorsicht: Unter etwa 60 km traegt kein
        Boxenstopp mehr, und die Reifenstrategie findet keine Variante.
    """
    import copy
    from dataclasses import replace

    from rennmanager import konfiguration as kf

    gross = konfiguration if konfiguration is not None else kf.lade()
    roh = copy.deepcopy(gross.roh)
    roh["ligen"]["anzahl"] = ligen
    roh["ligen"]["autos_je_liga"] = autos_je_liga
    # Der Spieler faengt in der untersten Liga an - in der kleinen Welt
    # ist das die dritte, nicht die zwanzigste. Ohne das verteilt
    # ``_sortiere_in_ligen`` die Fahrer auf eine Liga, die es nicht gibt.
    roh["ligen"]["startliga"] = ligen
    je_team = roh["teams"]["autos_je_team"]
    roh["teams"]["anzahl"] = (ligen * autos_je_liga) // je_team
    if rennen is not None:
        roh["kalender"]["rennen_je_saison"] = rennen
    if distanz_km is not None:
        roh["rennen"]["distanz_liga20_km"] = distanz_km
        roh["rennen"]["distanz_zuwachs_je_liga_km"] = 0
    return replace(gross, roh=roh)


@pytest.fixture(scope="session")
def kleine_konfiguration():
    """Die voreingestellte kleine Welt: 3 Ligen, 4 Autos, 3 Rennen."""
    return verkleinert()


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
