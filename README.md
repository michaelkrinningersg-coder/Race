# Rennmanager

Motorsport-Manager mit sichtbarer Rennsimulation. Grundlage ist das
[Game Design Dokument v1.0](Rennmanager%20%E2%80%93%20Game%20Design%20Dokument%20%28v1.0%29.md);
die Arbeitsregeln stehen in [Claude.md](Claude.md).

**Stand: Schritt 6 von 10 – Fehler, Unfaelle, Defekte, Reifenverschleiss.**
Ein Rennwochenende laeuft durch; Fahrer, Teams und Ligen folgen in Schritt 7.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `rennmanager/kern/` | Simulationskern, reines Python, kennt die Oberflaeche nicht |
| `daten/strecken/` | Die 20 Strecken als CSV (TUMFTM, LGPL-3.0), mitgeliefert |
| `rennmanager/konfiguration.py` | Laden und Pruefen der Balancing-Dateien |
| `rennmanager/ui/` | PySide6-Oberflaeche |
| `konfiguration/balancing.toml` | **Alle** Balancing-Werte, zentral an einer Stelle |
| `konfiguration/hersteller.toml` | Herstellernamen, ausgelagert und austauschbar |
| `werkzeuge/` | Balancing-Werkzeuge, nicht Teil der Auslieferung |
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

## Das Streckenmodell

`rennmanager.kern.strecke` macht aus einer Ideallinie eine fahrbare Strecke
(GDD 3): neu abtasten auf rund 5 m, Kruemmungsradius je Punkt, daraus der
Segmenttyp (enge Kurve unter 60 m, Gerade ab 300 m), Geraden ab 100 m als
Ueberholzonen, vier Sektoren gleicher Laenge.

```python
from rennmanager.kern import strecke
from rennmanager.konfiguration import lade

monza = strecke.lade(lade(), "Monza")
monza.laenge_m            # 5758.0
len(monza.ueberholzonen)  # 7, laengste 1240 m
monza.geradenanteil       # 0.79
```

Die Rechnung ist gegen erzeugte Formen geprueft: Ein Kreis mit Radius R
liefert ueberall R zurueck, ein Oval aus zwei Geraden und zwei Halbkreisen
genau vier Segmente. Der Abgleich mit der Wirklichkeit stimmt ebenfalls -
die laengste Gerade in Shanghai misst 1.155 m, real sind es rund 1.170 m.

Die Segmentgrenzen laufen rein ueber den Radius, ohne Mindestlaenge, weil
das GDD keine nennt. Dabei entstehen einzelne Segmente von 5 bis 20 m. Das
ist gemessen und unkritisch: Sie zu verschmelzen aendert die Zahl der
Ueberholzonen nur auf 2 von 20 Strecken, weil die 100-m-Regel sie ohnehin
filtert. Die Frage steht unter den offenen Punkten.

## Geschwindigkeit und Rundenzeit

`rennmanager.kern.tempo` setzt das Modell aus GDD 4 um: Kurvenlimit
`v = sqrt(a * r)`, Hoechstgeschwindigkeit auf Geraden, dann ein
Vorwaertsdurchlauf mit der Beschleunigungs- und ein Rueckwaertsdurchlauf mit
der Bremsgrenze.

```python
from rennmanager.kern import auto, strecke, tempo
from rennmanager.konfiguration import lade

k = lade()
runde = tempo.fahre_runde(k, strecke.lade(k, "Monza"), auto.gleichverteilt(k, 98_130))
runde.zeit_ms        # 84276, ganze Millisekunden
runde.sektoren_ms    # vier Sektorzeiten
runde.schnitt_kmh    # 245.96
```

### Warum die Haftung quadratisch waechst

GDD 9 kalibriert linear in `p = sqrt(S / 98.000)`: `v(S) = 55 + 125 * p`.
Das Kurvenlimit folgt aber `v = sqrt(a * r)`. Damit die *Geschwindigkeit*
linear in `p` herauskommt, muss die *Haftung* quadratisch in `p` wachsen:

    a(S) = haftung_referenz * (anteil_bei_null + (1 - anteil_bei_null) * p)^2

Mit dieser Form trifft das Modell alle zehn Kontrollwerte der Ligatabelle
aus GDD 9 auf 0,01 km/h genau - und ebenso Werte, die bei der Anpassung
gar nicht vorkamen.

### Warum nur zwei freie Konstanten

Mit einer dritten waere das Modell durch GDD 9 nicht eindeutig bestimmt:
Man kann mehr Endgeschwindigkeit gegen weniger Haftung tauschen und trifft
denselben Rundenschnitt auf der Referenzstrecke. Die Wahl verschiebt aber
das Verhaeltnis zwischen schnellen und kurvigen Strecken. Deshalb ist die
Endgeschwindigkeit bei `S = 0` an dasselbe `anteil_bei_null` gekoppelt: Bei
Wert 0 kann das Auto in jeder Hinsicht denselben Bruchteil dessen, was es
bei `S = referenz` kann.

Kalibriert wird mit `python -m werkzeuge.kalibriere --schreiben`. Als
Referenzstrecke dient Zandvoort - mit 46 % der geringste Geradenanteil
aller 20 Strecken, laut GDD 3 "Steilkurven, eng". GDD 9 verlangt eine
"kurvige Referenzstrecke", ohne sie zu nennen.

## Das Rennen

`rennmanager.kern.rennen` faehrt ein ganzes Rennen vorab durch und legt die
Positionen in festen Abstaenden ab; die Oberflaeche spielt diesen Verlauf
nur noch ab (GDD 15). Deshalb kostet 100-facher Zeitraffer nichts.

```python
from rennmanager.kern import rennen, strecke
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
alle = strecke.lade_alle(k)
monza = next(s for s in alle if s.name == "Monza")
feld = rennen.starterfeld(k, liga=10, spielerplatz=30)
verlauf = rennen.simuliere(
    k, monza, feld, rennen.rundenzahl(k, monza, 10), Seedquelle(4711),
    rennen.mittlerer_ueberholzonenanteil(k, alle),
)
verlauf.reihenfolge_zu(90_000)   # Positionen nach anderthalb Minuten
verlauf.ergebnisse[0].zeit_ms    # Siegerzeit in Millisekunden
```

Das freie Profil aus Schritt 3 ist dabei die Obergrenze. Interaktion
entsteht durch die zwei Regeln aus GDD 4: Wer naeher als 0,05 s auffaehrt,
faehrt das Tempo des Vordermanns; ueberholen darf er nur in einer
Ueberholzone und nur mit mindestens 2 km/h Vorteil.

### Warum zwischen den Profilpunkten interpoliert wird

Das Profil ist alle 5 m definiert. Zielt ein Auto auf das Tempo des zuletzt
passierten Punktes, dann hinkt es durch die Beschleunigungsgrenze dauerhaft
einen Punkt hinterher - auf einer Runde in Zandvoort kostet das rund 1,5 s.
Mit linearer Interpolation zwischen den Punkten stimmt die Rennrunde wieder
mit der Einzelrunde aus Schritt 3 ueberein, auf 30 Millisekunden genau. Ein
Test haelt das fest: Ein Auto allein auf der Strecke muss im Rennen so
schnell sein wie in der Einzelrunde.

## Wetter und Zufall

`rennmanager.kern.wetter` wuerfelt je Session eine Lage, die 0- bis 3-mal
um je eine Stufe wechselt. `rennmanager.kern.form` liefert die drei
Zufallsebenen aus GDD 11: Tagesform, Eigenschafts-Zufall und Rundenform.

### Warum der Grip quadratisch angesetzt wird

GDD 4 sagt: "Der Grip-Faktor senkt das Tempo jedes Autos." Das Kurvenlimit
folgt aber `v = sqrt(a * r)`. Legt man den Grip quadratisch auf alle
Beschleunigungen, kommt genau das heraus:

    sqrt(g^2 * a * r) = g * sqrt(a * r)

Auch der Vorwaerts- und der Rueckwaertsdurchlauf skalieren dann exakt mit.
Ein Test haelt fest, dass Grip 0,72 die Rundengeschwindigkeit auf genau
72,000 % senkt - nicht auf 71,8 oder 72,3 %.

## Das Rennwochenende

```python
from rennmanager.kern import qualifying, rennen, strecke, wetter
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
spa = strecke.lade(k, "Spa")
feld = rennen.starterfeld(k, liga=10, spielerplatz=30)
haupt = Seedquelle(4711)

# Samstag: jedes Auto allein, Aufwaermrunde plus gezeitete Runde
session = qualifying.fahre(k, spa, feld, haupt.zweig("qualifying"))
session.aufstellung          # Startaufstellung fuers Rennen
session.wetter.zustaende     # ("starkregen", "regen", ...)
```

Qualifying und Rennen wuerfeln getrennt - Wetter, Tagesform und
Eigenschafts-Zufall je einmal pro Session (GDD 7 und 11). Fuer die
Kalibrierung und die Massensimulation laesst sich der Zufall abschalten:
`rennen.simuliere(..., ohne_zufall=True)`, wie GDD 9 es verlangt.

## Reifen, Fehler, Unfaelle, Defekte

`rennmanager.kern.reifen` und `rennmanager.kern.zwischenfall` setzen um,
was GDD 4 und 14 verlangen. Wichtig ist dabei eine Trennung, die es im
GDD so noch nicht gab:

* **D14 Reifenmanagement** senkt, wie schnell die Reifen abbauen.
* Der **Reifenfluesterer** senkt, wie sehr abgebaute Reifen wehtun.

Ohne diese Trennung faechert das Feld in der zweiten Rennhaelfte nur auf:
Wer schneller ist, bleibt schneller. Mit ihr ist ein Auto, das seine
Reifen schont, frueh langsamer und spaet schneller als eines, das sie
verheizt - die Linien im Rennverlauf kreuzen sich. Der Reifenfluesterer
steht wie die Wetterfaehigkeiten aus GDD 7 neben der Wirkungsmatrix;
die Begruendung dazu in OFFENE_PUNKTE.md.

Die Streckenwirkung kommt aus der Querbeschleunigung der Runde: In
Zandvoort enden die Reifen einer Liga-10-Session bei 11 bis 19 %, in
Monza bei 62 bis 66 %.

### Warum die Unfallrate je Sekunde gilt

Als Wahrscheinlichkeit je Zeitschritt gelesen fielen bei 50 Schritten je
Sekunde alle fuenf erlaubten Ausfaelle in der ersten Runde. Die Rate gilt
deshalb je Sekunde in Reichweite - sonst haengt die Unfallhaeufigkeit an
der Schrittweite der Simulation statt am Spiel.

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

Das GDD nennt an 20 Stellen eine Mechanik, ohne sie zu beziffern. Zu jeder
liegen in [OFFENE_PUNKTE.md](OFFENE_PUNKTE.md) drei Vorschlaege mit
Begruendung; alle 20 sind am 2026-09-17 entschieden, der Abschnitt `[offen]`
in der Konfiguration ist leer. Kommt spaeter eine Luecke hinzu, wird sie dort
vermerkt und im Hauptfenster angezeigt, statt still gefuellt zu werden.

## Datenquellen

Streckendaten: [TUMFTM/racetrack-database](https://github.com/TUMFTM/racetrack-database),
Lizenz LGPL-3.0. Die 20 Strecken der Saison liegen unveraendert unter
`daten/strecken/` und werden in die .exe gepackt; Herkunft, Format und
Datenqualitaet beschreibt `daten/strecken/HERKUNFT.md`.
