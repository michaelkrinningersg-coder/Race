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
# Die getesteten Regeln sind **groesseninvariant**: Punktevergabe und
# Tabellensortierung stimmen mit 8 Autos genauso wie mit 50. Gemessen
# kostet ein Rennwochenende dabei einen Bruchteil. Wer die Groesse selbst
# prueft, nimmt ``kf.lade()``; alle anderen nehmen das hier.
#
# Die Groessen sind **Parameter**, keine Konstanten: ``verkleinert``
# nimmt sie entgegen, die Fixtures reichen nur die Voreinstellung durch.
KLEINE_AUTOS = 8
# Der Rennkalender wird auf **zwei** Rennen gekuerzt - erstes und letztes.
# Mehr braucht keine Regel, die hier geprueft wird: Dass sich Punkte
# summieren, zeigt das zweite Rennen; dass eine Saison endet, ebenfalls.
# Dass die Saison dabei im Test wirklich zu Ende geht, ist gewollt - die
# Oberflaeche meldet es per Dialog, und den faengt
# ``keine_modalen_dialoge`` ab.
KLEINE_RENNEN = 2
# Die Renndistanz: Das Feld faehrt 290 km. Fuer die kleine Welt sind das
# zu viele Runden. 100 km sind kurz genug fuer den Testlauf und lang
# genug fuer eine Reifenstrategie. Unter etwa 60 km traegt kein
# Boxenstopp mehr.
KLEINE_DISTANZ_KM = 100


def verkleinert(
    konfiguration=None,
    autos: int = KLEINE_AUTOS,
    rennen: int | None = KLEINE_RENNEN,
    distanz_km: int | None = KLEINE_DISTANZ_KM,
):
    """Dieselbe Konfiguration in klein - Groessen als Parameter.

    Alle Balancing-Werte bleiben, wie sie sind; nur die **Groesse** des
    Feldes schrumpft. Die Spanne aus ``[feld]`` bleibt dieselbe, nur
    ueber weniger Stufen.

    :param autos: Zahl der Autos im Feld. Muss durch ``autos_je_team``
        teilbar sein, sonst geht die Welt nicht auf.
    :param rennen: Rennen je Saison; ``None`` laesst den echten Kalender
        stehen. Ein kurzer Kalender laesst die Saison im Test enden - die
        Oberflaeche meldet das per Dialog, den ``keine_modalen_dialoge``
        abfaengt.
    :param distanz_km: Renndistanz; ``None`` laesst die echte Distanz
        stehen. Vorsicht: Unter etwa 60 km traegt kein Boxenstopp mehr,
        und die Reifenstrategie findet keine Variante.
    """
    import copy
    from dataclasses import replace

    from rennmanager import konfiguration as kf

    gross = konfiguration if konfiguration is not None else kf.lade()
    roh = copy.deepcopy(gross.roh)
    je_team = roh["teams"]["autos_je_team"]
    if autos % je_team:
        raise ValueError(
            f"{autos} Autos lassen sich nicht auf Teams zu je {je_team} verteilen"
        )
    roh["rennen"]["autos"] = autos
    roh["teams"]["anzahl"] = autos // je_team
    # Die Punktetabelle nennt je Platz einen Wert; ein kleineres Feld
    # braucht die vorderen davon. Die Pruefung in konfiguration.py
    # vergleicht beide Laengen.
    roh["wertung"]["punkte_je_platz"] = list(
        roh["wertung"]["punkte_je_platz"][:autos]
    )
    if rennen is not None:
        roh["kalender"]["rennen_je_saison"] = rennen
    if distanz_km is not None:
        roh["rennen"]["distanz_km"] = distanz_km
    return replace(gross, roh=roh)


@pytest.fixture(scope="module")
def konfig(kleine_konfiguration):
    """Die kleine Welt fuer alle Oberflaechen-Tests (Punkt 77).

    Jeder dieser Tests baut ein ganzes ``Hauptfenster`` - und damit eine
    Welt, eine Karriere und alle Seiten. Geprueft wird dort, ob die
    Oberflaeche das Richtige liest und zeichnet; dafuer genuegen acht
    Autos. Wo die Groesse selbst Gegenstand ist, steht
    ``grosse_konfiguration`` daneben - und wer etwas anderes braucht,
    ueberschreibt ``konfig`` in seiner Datei (so machen es
    ``test_rennanzeige`` und ``test_fahrerkarte``).
    """
    return kleine_konfiguration


@pytest.fixture(scope="module")
def grosse_konfiguration():
    """Die echte Konfiguration mit einem Feld aus 50 Autos."""
    from rennmanager import konfiguration as kf

    return kf.lade()


@pytest.fixture(scope="session")
def kleine_konfiguration():
    """Die voreingestellte kleine Welt: 8 Autos, 2 Rennen."""
    return verkleinert()


@pytest.fixture(scope="session")
def kleine_welt(kleine_konfiguration):
    """Eine Welt aus ``kleine_konfiguration``, mit Spielerteam.

    **Nicht veraendern.** Das Fixture gilt fuer die ganze Sitzung; wer die
    Welt umbaut, zieht alle anderen Tests mit. ``Welt`` ist eingefroren,
    ein ``replace`` liefert eine eigene Kopie.
    """
    from rennmanager.kern import welt as kw
    from rennmanager.kern.zufall import Seedquelle

    return kw.erzeuge(kleine_konfiguration, Seedquelle(12).zweig("welt"))
