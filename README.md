# Rennmanager

Motorsport-Manager mit sichtbarer Rennsimulation. Grundlage ist das
[Game Design Dokument v1.0](Rennmanager%20%E2%80%93%20Game%20Design%20Dokument%20%28v1.0%29.md);
die Arbeitsregeln stehen in [Claude.md](Claude.md).

**Stand: Schritt 1 von 10 – Projektgeruest, Konfigurationsdatei, Build-Workflow.**
Es wird noch nichts simuliert.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `rennmanager/kern/` | Simulationskern, reines Python, kennt die Oberflaeche nicht |
| `rennmanager/konfiguration.py` | Laden und Pruefen der Balancing-Dateien |
| `rennmanager/ui/` | PySide6-Oberflaeche |
| `konfiguration/balancing.toml` | **Alle** Balancing-Werte, zentral an einer Stelle |
| `konfiguration/hersteller.toml` | Herstellernamen, ausgelagert und austauschbar |
| `tests/` | Tests fuer Kern, Konfiguration, Oberflaeche und Architektur |

Die Trennung zwischen Kern und Oberflaeche wird von `tests/test_aufbau.py`
geprueft: Kein Modul unter `rennmanager/kern/` darf Qt importieren.

## Starten

```bash
python -m pip install -e ".[entwicklung]"
python -m rennmanager
```

Ohne Bildschirm laesst sich nur die Konfiguration pruefen:

```bash
python -m rennmanager --pruefe
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen pytest
ruff check .
```

Unter Linux brauchen die Oberflaechen-Tests einige Qt-Systembibliotheken
(`libegl1`, `libgl1`, `libdbus-1-3`, `libxkbcommon-x11-0` und die
`libxcb-*`-Pakete); der Workflow `tests.yml` installiert sie.

## Die .exe bauen

Der Workflow `.github/workflows/build-windows.yml` baut auf `windows-latest`
mit PyInstaller eine einzelne `Rennmanager.exe` ohne Konsolenfenster. Sie
laeuft ohne Installation und ohne Adminrechte; die Konfigurationsdateien sind
mitgepackt. Der Build laedt die fertige Datei als Artefakt hoch.

Lokal:

```bash
pyinstaller --clean --noconfirm rennmanager.spec
```

## Zwei Regeln, die den Code praegen

**Zeiten sind ganze Millisekunden.** Im Kern gibt es keine Sekunden als
Gleitkommazahl. Die Anzeige uebernimmt `rennmanager.kern.zeit`:
`m:ss.mmm`, ab einer Stunde `h:mm:ss.mmm`, Rueckstaende unter 60 Sekunden
als `s.mmm`.

**Jede Simulation laeuft mit Seed.** `rennmanager.kern.zufall.Seedquelle`
leitet aus einem Hauptseed benannte Teilstroeme ab:

```python
haupt = Seedquelle(4711)
wetter = haupt.zweig("saison", 1).zweig("rennen", 3).zweig("wetter")
werte = wetter.generator().normal(0, 0.03, size=30)
```

Derselbe Pfad liefert immer dieselbe Folge, und ein zusaetzlicher Zweig
verschiebt keinen bestehenden. Das ist noetig, weil das GDD an vielen
Stellen getrennt wuerfelt – Wetter, Tagesform und Eigenschafts-Zufall je
einmal fuer Qualifying und einmal fuer das Rennen.

## Offene Punkte

`konfiguration/balancing.toml` enthaelt einen Abschnitt `[offen]`. Dort steht,
welche Angaben das GDD nennt, aber nicht beziffert – etwa die Interpolation
der Preisgelder zwischen den Ligen oder die Basisrate fuer Fehler und
Defekte. Diese Werte werden **nicht** erfunden; die Anwendung zeigt die Liste
im Hauptfenster an, damit sie vor dem jeweiligen Umsetzungsschritt geklaert
werden kann.

## Datenquellen

Streckendaten: [TUMFTM/racetrack-database](https://github.com/TUMFTM/racetrack-database),
Lizenz LGPL-3.0. Der Import folgt in Schritt 2.
