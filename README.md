# Rennmanager

Motorsport-Manager mit sichtbarer Rennsimulation. Grundlage ist das
[Game Design Dokument v1.0](Rennmanager%20%E2%80%93%20Game%20Design%20Dokument%20%28v1.0%29.md);
die Arbeitsregeln stehen in [CLAUDE.md](CLAUDE.md).

**Stand: alle zehn Schritte der Umsetzungsreihenfolge sind durch.** Eine
Karriere laeuft vom 1. Januar bis zum Auf- und Abstieg, mit Ereignissen,
Rundenrekorden, Historie und Spielstand auf der Platte. Dazu der Editor aus
GDD 15 (Debug-Ansicht), mit dem sich jeder der 600 Fahrer aendern laesst.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `rennmanager/kern/` | Simulationskern, reines Python, kennt die Oberflaeche nicht |
| `daten/strecken/` | Die 20 Strecken als CSV (TUMFTM, LGPL-3.0), mitgeliefert |
| `rennmanager/konfiguration.py` | Laden und Pruefen der Balancing-Dateien |
| `rennmanager/ui/` | PySide6-Oberflaeche, ein Modul je Reiter |
| `rennmanager/ui/editorseite.py` | Debug-Ansicht aus GDD 15: Fahrer und Autos aendern |
| `konfiguration/balancing.toml` | **Alle** Balancing-Werte, zentral an einer Stelle |
| `konfiguration/hersteller.toml` | Herstellernamen, ausgelagert und austauschbar |
| `konfiguration/namen.toml` | Fahrer- und Teamnamen, ebenfalls austauschbar |
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

Der Lauf verteilt sich ueber `pytest-xdist` auf **alle Kerne** der
Maschine - eingestellt in `pyproject.toml`, `pytest` allein genuegt also.
Verteilt wird **je Datei** (`--dist loadfile`) und nicht je Test: Mehrere
Dateien rechnen ein Rennen einmal in einem Fixture mit Modulgueltigkeit
und zeigen es dann in jedem Test; auf mehrere Prozesse verstreut,
rechnete jeder Prozess dasselbe Rennen noch einmal.

Weil je Datei verteilt wird, bestimmt die **laengste Datei**, wie lange
der ganze Lauf dauert. Deshalb sind die beiden laengsten aufgeteilt: Die
Oberflaechen-Tests stehen in vier Dateien (`test_ui`, `test_ui_rennen`,
`test_ui_welt`, `test_ui_karriere`), die Boxenstopp-Tests in vier
Dateien im Ordner `tests/boxenstopp/`. Was sie sich teilen, steht in
`tests/oberflaeche.py` und in `tests/boxenstopp/conftest.py`. Gemessen
auf vier Kernen: **2:39 statt 9:10**.

Wer einen einzelnen Fehler sucht, haengt `-n0` an. Dann laeuft alles
wieder in einem Prozess - mit lesbarer Ausgabe, brauchbarem `--pdb` und
einem `-x`, das wirklich sofort anhaelt.

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

### Was die Rennanzeige zeigt

Vier Dinge stehen neben der Streckenansicht, alle aus dem fertigen
`Rennverlauf` gelesen (GDD 15: die Anzeige rechnet nicht mit):

* **Rangliste** mit Rueckstand zur Spitze *und* Intervall zum Vordermann.
  Das Intervall rechnet mit dem Tempo des Vordermanns, der Rueckstand mit
  dem des Fuehrenden - beide Bezuege sind der jeweils richtige, aber weil
  zwei Autos an verschiedenen Streckenpunkten verschieden schnell sind,
  summieren sich die Intervalle **nicht** genau zum Rueckstand. Gemessen:
  fuenf Intervalle 11,6 s, Rueckstand des sechsten Autos 9,0 s. Nur beim
  Zweiten stimmen beide Zahlen ueberein, weil dort Vordermann und
  Fuehrender dasselbe Auto sind.
* **Reifenzustand als Balken** statt als Prozentzahl - im Zeitraffer
  schneller zu lesen. Die Farbe kommt aus der Statuspalette (gut, Warnung,
  kritisch), nicht aus einer Serienpalette: Der Balken sagt "kritisch",
  nicht "Auto Nummer drei".
* **Zwischenfall-Ticker**: Fehler, Unfaelle und Defekte bis zur laufenden
  Rennzeit, neueste zuerst. Er steht als Blatt **Meldungen** rechts bei
  den Tabellen; bis Punkt 82 war er eine Fussleiste unter der ganzen
  Seite und nahm ihnen Hoehe weg.
* **Zeitenmonitor** mit letzter Runde, bester Runde und den vier
  Sektorzeiten - alles **zum Abspielzeitpunkt**, sortiert nach der besten
  Runde. Die letzte Runde leuchtet gruen auf, wenn sie zugleich die beste
  dieses Fahrers war. Dafuer fuehrt das Rundenprotokoll ``rundenende_ms``
  mit; ohne diese Zeitpunkte zeigte der Monitor die Werte vom Rennende,
  also Runden, die in der Uebertragung noch gar nicht gefahren waren.
  Wer einen Sektor als **Schnellster des ganzen Feldes** gefahren ist,
  bekommt ihn lila - gesucht ueber alle bisher gefahrenen Runden aller
  Autos, nicht nur ueber die letzte.
* **Bestmoegliche Runde** als eigenes Blatt: dieselben Sektoren, aber die
  **persoenlich** besten je Fahrer - sie muessen nicht aus derselben
  Runde stammen. Ihre Summe ist die Zeit, die er haette fahren koennen,
  und die Spalte "Luecke" sagt, wieviel zwischen ihr und seiner
  wirklichen Bestzeit liegt. Sortiert nach der moeglichen Zeit: Dort
  steht, wer das schnellste Auto haette, nicht wer es am besten
  zusammengebracht hat.
* **Spalte Team** in Rangliste, Zeitenmonitor, Bestmoeglicher Runde und
  Meisterschaft - wer fuer wen faehrt, stand im Rennen bis Punkt 82
  nirgends.
* **Rundenstand** "Runde X/Y" des Fuehrenden im Kopf der Seite.
* **Rueckstandsdiagramm** als zweiter Reiter neben der Strecke; es zeigt
  nur, was schon gefahren ist - sonst stuende dem Zuschauer der ganze
  Rennausgang vor Augen, waehrend die Uebertragung in Runde drei laeuft.
* **Live-Meisterschaft** als zweites Blatt unter dem Zeitenmonitor: der
  Stand bis zu diesem Rennen plus die Punkte, die jeder fuer seine
  derzeitige Position bekaeme, samt Qualifying und schnellster Runde.
  Gruener Pfeil hoch, roter runter, dazu "+x" fuer den Zuwachs. Eine
  Vorschau, die nichts fortschreibt - das tut am Rennende der Saisonlauf.

Rangliste und Zeitenmonitor stehen **nebeneinander**, die Zwischenfaelle
als Fussleiste darunter. Wie oft die Listen nachgezogen werden, ist
einstellbar (200 ms voreingestellt, 10 ms bis 5 s); die Karte laeuft
unabhaengig davon fluessig weiter.

Ausgefallene Autos bleiben noch eine Minute auf der Streckengrafik stehen
- lang genug, um zu sehen, wo es passiert ist - und werden danach
abgeraeumt, statt regungslos liegen zu bleiben.

#### Warum Rueckstand und Intervall an Messpunkten haengen

Beide Zahlen wurden anfangs aus Strecke geteilt durch Tempo geschaetzt.
Das schwankte stark, weil zwei Autos an verschiedenen Streckenpunkten
verschieden schnell sind, und die Intervalle summierten sich **nicht**
zum Rueckstand - gemessen fuenf Intervalle zu 11,6 s gegen 9,0 s
Rueckstand.

Stattdessen haelt die Simulation an **acht Messpunkten je Runde** die
Uhrzeit fest: den vier Splits (Start/Ziel und die drei Sektorgrenzen) und
dazwischen je einem in der Mitte, der selbst kein Split ist. Der Abstand
zweier Autos ist die Differenz ihrer Zeiten am letzten Punkt, den das
hintere passiert hat - zwei echte Zeiten an derselben Stelle der Strecke.
Gemessen an sechs Autos summieren sich die Intervalle jetzt genau zum
Rueckstand: 0,137 + 1,022 + 0,053 + 0,726 + 0,163 = 2,101 s.

Ein **Minus** ist moeglich und richtig so: Wer zwischen zwei Messpunkten
vorbeigeht, war am letzten gemeinsamen Punkt noch hinten. Gemessen kam
das in 11,6 % der Bilder vor, vor allem in der ersten Runde, wo der
einzige gemeinsame Punkt die Startlinie ist.

#### Warum die Reihenfolge im Ziel nicht aus der Strecke kommt

Die Rangliste sortierte anfangs allein nach zurueckgelegter Strecke. Das
geht, solange gefahren wird; danach nicht mehr: Wer im Ziel ist, **steht**,
alle anderen fahren weiter bis zur Linie. Gemessen stand am Ende in 10 von
10 Rennen der falsche Sieger oben - naemlich der, der als Letzter ankam
und deshalb die groesste Strecke hatte.

Sortiert wird jetzt wie die Wertung: Runden absteigend, dann Zielzeit
aufsteigend, und wer im Ziel ist, steht vor allen, die noch fahren.

#### Warum das Diagramm nur zwei farbige Linien hat

Bei 30 Linien traegt Farbe keine Identitaet mehr - benachbarte Toene sind
nicht auseinanderzuhalten, fuer Farbenblinde erst gar nicht. Das Feld
liegt deshalb als duenne graue Linien im Hintergrund; hervorgehoben und
am Linienende direkt beschriftet sind nur zwei: das Auto des Spielers und
das in der Rangliste gewaehlte. Gezeichnet wird mit `QPainter` - PySide6
bringt `QtCharts` nicht mit, und eine zusaetzliche Abhaengigkeit muesste
in die .exe.

Die Achse skaliert nicht nach Ausgefallenen und Ueberrundeten: GDD 4 kennt
fuer sie keinen Zeitrueckstand, sondern "+n Rd.", und ihre Kurve bleibt
beim letzten gueltigen Wert stehen. Dass ein Feld weit auseinanderliegt,
bleibt dagegen sichtbar - in Liga 20 reicht die Ligastaerke von 0 bis 157,
und das letzte Auto liegt dort gemessen 328 s hinter dem Sieger.

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

### Neue Karriere

Beim Start fragt das Spiel, wer der Spieler ist: **Vorname, Nachname,
Land und Geburtstag** - mehr nicht. `Datei -> Neue Karriere` (Strg+N)
fragt spaeter noch einmal und setzt alles auf Anfang: Welt, Karriere,
Statistik, Streckenkenntnis und Popularitaet.

Die Startliga steht **nicht** zur Wahl; sie ist immer die aus der
Konfiguration (Liga 20). Freie Wahl waere der Schwierigkeitsgrad durch
die Hintertuer - wer in Liga 5 anfinge, liesse die halbe Karriere aus
GDD 13 einfach aus. Die Laender kommen aus derselben Liste wie die der
599 KI-Fahrer, damit der Spieler kein Land traegt, das es in dieser Welt
sonst nicht gibt; an zweien haengt mehr als Farbe, denn wer im Land einer
der 20 Strecken wohnt, hat dort seine Heimstrecke (Punkt 49).

### Das gefuehrte Rennwochenende

In der Oberflaeche laeuft ein Rennwochenende in vier Schritten ab, in
einem Reiter:

1. **Vorschau** - Renntag, Strecke, Charakter, Laenge, Rundenzahl und der
   Tabellenstand vor dem Rennen. Vor Rennen 1 gibt es noch keine Tabelle;
   dann steht dort das Feld nach Staerke.
2. **Qualifying** - die Session der eigenen Liga als Zeitenmonitor,
   abspielbar wie das Rennen (GDD 4)
3. **Rennen** - auf die gefahrene Aufstellung, abspielbar im Zeitraffer.
   Es startet in **Echtzeit** (1x) und laeuft von selbst los, sobald man
   den Reiter aufschlaegt; die Stufen 1x bis 100x lassen sich waehrend
   des Rennens umstellen (``zeitraffer.start_stufe``)
4. **Ergebnis** - die eigene Wertung, das Rennergebnis und die Tabelle
   danach mit dem Sprung gegen vorher

Gefahren wird, was der Kalender vorgibt (GDD 2): Strecke, Rundenzahl,
Aufstellung und Seed kommen aus der Saison. Frueher liessen sich hier
Strecke, Liga, Rundenzahl, Seed und Startaufstellung frei einstellen -
das war ein Werkzeug, kein Spiel. Zum Kalibrieren dienen
`python -m rennmanager --pruefe` und die Werkzeuge unter `werkzeuge/`,
die ohne Oberflaeche laufen.

```python
from rennmanager.kern.saison import Wochenendlauf

wochenende = Wochenendlauf(lauf, liga=20)
wochenende.nummer, wochenende.strecke.name, wochenende.runden   # Vorschau
wochenende.fahre_qualifying()   # ab hier springt der Kalender auf den Renntag
wochenende.fahre_rennen()       # auf die Aufstellung des Qualifyings
wochenende.schliesse_ab()       # die 19 anderen Ligen, dann verbuchen
```

#### Das Qualifying als Uebertragung

Bis Punkt 85 stand ueber der Qualifyingseite ein Regler "Gefahrene
Laeufe": Man konnte die Session laufweise durchblaettern, aber nicht
zusehen. Jetzt traegt sie dieselbe Wiedergabeleiste wie das Rennen -
Start, Anfang, Zeitraffer 1x bis 100x, Sofortergebnis, laufende Uhr -
und steht nach dem Laden auf Anfang.

Der Kern rechnet dafuer nichts Neues. Jede `Fahrt` trug schon
`beginn_ms`, `ziel_ms`, `zeit_ms` und die Sektorzeiten; daraus ergibt
sich alles Weitere:

```python
fahrt.runde_ab_ms       # ziel_ms - zeit_ms, also nach der Aufwaermrunde
fahrt.sektorenden_ms    # wann die einzelnen Splits fallen
session.lage_zu(t)      # was jedes Auto gerade macht, live sortiert
```

`lage_zu()` kennt vier Lagen - Box, Aufwaermrunde, Schnelle Runde, Im
Ziel - und sortiert die beendeten Runden nach Zeit nach oben; darunter
stehen die, die gerade unterwegs sind, dann die Aufwaermrunden, zuletzt
die Box. Es stehen immer alle dreissig Autos da, damit die Tabelle beim
Abspielen nicht springt (Punkt 64). Wer faehrt, hat noch keine Position -
seine Rundenzeit laeuft kursiv mit, bis sie im Ziel steht.

Der letzte Sektor endet dabei per Definition im Ziel: Sektorzeiten und
Rundenzeit runden getrennt auf ganze Millisekunden (GDD 15), ihre Summe
trifft die Rundenzeit also nicht zwingend. Ohne diese Festlegung waere
ein Auto fuer einen Takt im Ziel, ohne seinen letzten Split gesetzt zu
haben - derselbe Rundungsfall wie bei der idealen Runde im Rennen.

##### Warum Lila mitlaeuft und Gruen und Rot einfrieren

Die Splits sind dreifarbig, und die beiden Farbgruppen messen bewusst
verschieden:

| Farbe | Vergleich | Zeitpunkt |
| --- | --- | --- |
| Lila | schnellster Split des Feldes | **jetzt** - wandert weiter |
| Gruen / Rot | gegen den Fuehrenden | **damals** - friert ein |

Entscheidung des Auftraggebers: wie im Fernsehen. Gruen und Rot sagen,
wie der Split stand, **als er fiel** - gemessen gegen den, der in dem
Moment die schnellste stehende Runde hatte. Die Farbe dreht sich nicht
mehr um, wenn spaeter jemand schneller ist; sonst waere die Tabelle am
Ende nur noch eine Tabelle gegen die Pole, und die frueh gefahrenen
Runden haetten ihre Geschichte verloren. Lila dagegen ist Live-Stand: Es
haelt immer genau einer je Sektor, und es wandert in dem Moment weiter,
in dem es jemand unterbietet.

Wer als Erster faehrt, bekommt kein Gruen und kein Rot - es gibt noch
niemanden, gegen den zu messen waere. Eine laufende Runde fuehrt
ausserdem nie: Solange sie nicht steht, ist sie mit nichts vergleichbar.

Die **Startaufstellung fuers Rennen** rechts fuellt sich erst, wenn der
Letzte durch ist (ebenfalls Entscheidung des Auftraggebers). Vorher
stuende dort das Ergebnis, auf das die Uebertragung gerade zulaeuft.

#### Warum der Aufbau nichts bewegt

Der `Wochenendlauf` ist beim Aufbau eine reine Vorschau: Strecke,
Rundenzahl und Renntag stehen fest, ohne dass der Kalender vorschaltet
oder ein Wuerfel faellt. Sonst kostete schon das Aufschlagen des Reiters
die nutzbaren Tage bis zum Rennen (GDD 2) - man haette Zeit verloren, nur
weil man hingesehen hat.

Gebucht wird erst im letzten Schritt. Ein abgebrochenes Wochenende bewegt
die Saison nicht.

#### Warum gefuehrt und am Stueck dasselbe ergibt

`fahre_rennen` geht von Liga 1 bis 20 durch, das gefuehrte Wochenende
faengt mit der Liga des Spielers an. Dass beides dasselbe ergibt, haengt
an zwei Dingen: Die Seedzweige heissen nach ihrer Sache (`qualifying`,
`rennwetter`, `rennen`, `liga 7`) und nicht nach der Reihenfolge, und jede
Liga bucht fuer sich. Ein Test haelt es fest - gemessen stimmen alle 600
Ergebniszeilen ueberein, dazu Tabellen, Streckenkenntnis und Popularitaet
aller 600 Fahrer. Gegenprobe mit einem anderen Seed: Dann weichen alle 20
Ligen ab.

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

### Was ein Fehler kostet

Kein Zeitabzug, sondern **Stillstand**: Das Auto geht auf 0 km/h, steht
eine **feste** Zeit (``fehler.zeitverlust_ms``, 1250 ms) und faehrt
danach mit seiner eigenen Beschleunigungskurve wieder an. Gemessen laeuft
es nach der Pause ueber 1,3 → 2,6 → 3,9 km/h an, nicht sprunghaft zurueck
aufs alte Tempo. Der wirkliche Verlust ist deshalb groesser als die
1250 ms - das Anfahren kommt obendrauf.

### Ereignisse treffen einzelne Fahrer

GDD 14 laesst Ereignisse auf den Spieler wirken. Seit der Spieler ein
Team mit vier Autos fuehrt, ist das nicht mehr eindeutig: Eine
Erkaeltung hat **einer**, nicht alle vier. Jeder Fahrer fuehrt deshalb
seine eigene Lage (``karriere.lage_je_fahrer``), und ein ausgeloestes
Ereignis trifft einen, gewuerfelt aus der Seedquelle der Saison. Die
Meldung nennt seinen Namen.

## Boxenstopps und Reifenstrategie (Punkt 39)

Vier Module tragen das: `boxenstopp` rechnet, was ein Stopp kostet,
`reifen` haelt die fuenf Mischungen und die Gripkurve, `strategie` sucht
die beste Stoppverteilung, `wettersaison` gibt jeder Saison ihr eigenes
Wetter.

**Die Boxengasse steht in keiner Streckendatei.** Sie wird aus der
Geometrie abgeleitet: die Gerade um Start und Ziel, 500 bis 750 Meter
lang, und ihre Durchfahrt darf hoechstens 50 Prozent der Rundenzeit
kosten. Diese Grenze trifft nur den Norisring (2260 m Runde, 515 m Gasse,
49,6 Prozent); die uebrigen 19 Strecken bleiben unberuehrt.

**Der 80er-Deckel gilt nur, wo die Strecke schneller waere.** Wo sie
ohnehin langsamer ist, gilt ihr eigenes Tempo minus 5 Prozent. In Liga 1
kommt das nie vor - die Gasse liegt auf der Geraden, dort werden 89 bis
385 km/h gefahren. In Liga 20 schon: Das schwaechste Auto kommt dort
stellenweise nur auf 29 km/h, und ohne den Abzug waere die Boxengasse
fuer es kostenlos.

Ein Stopp kostet vier Dinge: die langsame **Durchfahrt**, das **Bremsen**
bis zum Stillstand, die **Standzeit** (6 bis 12 Sekunden, gewuerfelt) und
das **Anfahren** aus dem Stand. Bremsen und Anfahren kommen aus den
Grenzen dieses Autos: In Liga 1 zusammen 1,8 Sekunden, in Liga 20 gut 17 -
ein schwaches Auto kommt aus der Box eben nicht heraus. Im Zeitraffer
faehrt das Auto die Gasse wirklich langsam ab und steht wirklich, der
Schnellmodus bucht dieselbe Summe.

**Die Strategie steht vor dem Start fest.** Einmal je Rennen werden alle
zulaessigen Mischungsfolgen durchgerechnet - als Minimum-Plus-Faltung
ueber die Stints, exakt und nicht geraten. Was mehr als die Schwelle
hinter der besten liegt, faellt heraus (60 s bei 300 km, 30 s bei 100 km);
unter den ueberlebenden waehlt jedes Auto zufaellig. Deshalb faehrt nicht
das ganze Feld dasselbe, und trotzdem faehrt niemand offensichtlichen
Unsinn.

**Zwei Grenzen fuer die weichste Trockenmischung.** Sie faellt weg, wo
sie ohnehin nicht traegt: bei einer Strategie mit **mehr als drei
Stopps** - wer so oft herein muss, hat auf dem weichsten Gummi nichts
verloren -, und auf jeder Strecke mit einem **Streckenfaktor ueber
1,15**. Das sind fuenf der zwanzig: Zandvoort (1,263), Budapest (1,210),
Shanghai und Oschersleben (je 1,168) und Catalunya (1,160). Dort bleiben
Mittel und Hart. Die Regenreifen ruehrt das nicht an - die Regel zielt
auf den Verschleiss der Strecke, nicht auf die Wetterlage.

Die Vorausberechnung rechnet mit **9 Sekunden** Standzeit, der Mitte der
Spanne: Sie kennt die einzelnen Wuerfe noch nicht, und die Mitte
bevorzugt keine Strategie.

Der teurere Stopp - im Mittel 31,5 statt 23,3 Sekunden - und die
haerteren Mischungen haben die Stoppzahl sichtbar gesenkt: Zwei-Stopp-
Strategien sind von 10 auf 23 von 100 Strecke-Liga-Kombinationen
gestiegen. Ohne die Drei-Stopp-Grenze waeren frueher 4 bis 6 Stopps in
76 Faellen optimal gewesen, jetzt 2 bis 3 in 79; fuenf oder mehr kommen
gar nicht mehr vor. Die Grenze bindet damit nur noch in 19 statt in 76
Faellen - die Reifenwahl steuert die Stoppzahl endlich selbst.

### Die Gripkurve

Tempo und Fehlerquote sind **keine eigenen Kurven**: Beide sind der
Grip, auf sein Optimum normiert::

    grip(zustand)  = lineare Interpolation ueber die Stuetzstellen
    tempofaktor    = 1 - (1 - grip/bestgrip) * (1 - daempfung)
    fehlerfaktor   = dieselbe Kurve, nur als Aufschlag statt Abzug

``daempfung`` ist der Reifenfluesterer: Er aendert die Kurve nicht, nur
ihre Wirkung, um bis zu 60 Prozent. Fuer ein Auto mit dem
Referenzwert heisst das:

```
Restprofil   100 %   95 %   90 %   85 %   80 %   65 %   50 %   30 %    0 %
Grip         0.880  0.970  0.992  1.000  0.998  0.978  0.925  0.790  0.235
Tempofaktor  0.952  0.988  0.997  1.000  0.999  0.991  0.970  0.916  0.694
Fehlerfaktor 1.063  1.016  1.004  1.000  1.001  1.012  1.039  1.110  1.400
```

Der frische Reifen steht also bei 95,2 Prozent Tempo und 6,3 Prozent
erhoehter Fehlerquote - in der Runde nach dem Start wie in der Runde
nach jedem Stopp.

**Der Gipfel wird frueh passiert.** In Zandvoort steht ein weicher Satz
nach zwei Runden bei 80 Prozent, ein harter nach neun; der Reifen ist
also in der ersten Runde auf dem Punkt und verbringt den Rest des Stints
im Abstieg. Runden bis 80 / 50 / 30 / 0 Prozent, bestes Auto der Liga 1,
trocken:

```
                      Monza (0,54)   Nuerburgring (1,07)   Zandvoort (1,26)
  Weich              8/ 20/ 29/ 41       4/ 11/ 16/ 23       4/ 12/ 16/ 24
  Mittel            12/ 30/ 42/ 60       6/ 17/ 24/ 34       6/ 17/ 24/ 34
  Hart              16/ 41/ 58/ 83       9/ 23/ 33/ 47       9/ 24/ 33/ 48
  Intermediate       5/ 14/ 20/ 29       3/  8/ 11/ 16       3/  8/ 11/ 17
  Regen              5/ 12/ 17/ 25       2/  7/  9/ 14       2/  7/ 10/ 14
```

**Kein Stint faellt unter 30 Prozent Restprofil**, auch der letzte nicht -
und auch nicht, nachdem das Zufallsfenster die Stopprunden verschoben hat.
Das war lange anders: Die Vorausberechnung hielt die Regel ein, das
Fenster hebelte sie wieder aus. In Zandvoort kamen so 23 von 30 Autos
darunter, eines mit 9 Prozent ins Ziel.

### Warum die Strategie das ganze Wetter kennt

Das Rennwetter steht vor dem Start fest (GDD 7) - also darf die Strategie
es kennen. Frueher plante sie nur gegen die **Startlage**: Ein Rennen, das
trocken beginnt und nass endet, wurde als Trockenrennen geplant, und das
ganze Feld kam auf abgefahrenen Reifen ins Ziel.

Jetzt geht die Naesse **je Runde** in die Rechnung. Solange sie gleich
bleibt, kostet ein Stint ueberall dasselbe, und aus einer Rechnung werden
alle Reihenfolgen. Sobald sie wechselt, ist das nicht mehr wahr - ein
weicher Satz vor dem Regen ist etwas anderes als derselbe Satz danach -,
und jede Reihenfolge wird einzeln gerechnet. Das kostet Zeit, betrifft
aber nur die 21 bis 23 Prozent der Rennen, in denen sich das Wetter
ueberhaupt dreht.

### Was im Rennen davon abweicht

Drei Dinge halten sich nicht an den Plan:

* **Die Verschleissstreuung.** Je Fahrer und Mischung wird ein Betrag von
  hoechstens 0,002 auf den Verschleissfaktor gewuerfelt, jedes Rennen neu.
  Die Vorausberechnung kennt ihn nicht - geplant wird auf den Sollwerten.
* **Der Notstopp.** Zwei Lagen zwingen ausserplanmaessig herein, beide
  gehen dem geplanten Stopp vor und schieben ihn nach hinten. Dreht sich
  das **Wetter**, faehrt ein Auto noch **null bis zwei Runden** auf dem
  falschen Reifen weiter - je Auto ausgewuerfelt - und wechselt dann auf
  den, der zur Lage passt. Der Wurf ist noetig, weil bei einem
  Wetterwechsel alle dreissig Reifen im selben Augenblick falsch werden:
  Ohne ihn kam das ganze Feld in derselben Runde herein. Faellt das **Restprofil
  unter 30 Prozent**, kommt es in der naechsten Runde herein und holt
  sich einen frischen Satz - egal welcher Mischung. Fuer beide gilt der
  Mindestabstand von drei Runden zum letzten Stopp und dieselbe Sperre
  der letzten drei Runden wie fuer jeden anderen Stopp.
* **Der Planstopp selbst.** Passt der geplante Reifen nicht mehr zur Lage,
  kommt der auf, der passt. Ohne das zoege ein Auto im Regen Slicks auf
  und muesste zwei Runden spaeter wieder herein. Und er wartet: Solange
  der Satz noch besser als **65 Prozent** ist, faehrt das Auto Runde um
  Runde weiter, bis er darunter faellt. Sonst gaebe es nach einem
  Notstopp wenige Runden spaeter einen fast neuen Satz ab, nur weil der
  Plan das so vorsah.
* **Was ein Notstopp danach aendert.** Er wirkt ueber den Stopp hinaus,
  gleich zweifach. Der naechste geplante Stopp wartet noch laenger -
  bis **60 statt 65 Prozent**, denn der Satz ist eben erst aufgezogen
  worden. Und bei **heiss und trocken** geht es von da an nicht wieder
  auf weicheren Gummi zurueck: Wer sich einen Satz abgefahren hat, hat
  gezeigt, dass die Strecke ihm zu viel abverlangt. Das gilt fuer jeden
  weiteren Stopp im Rennen, nicht nur fuer den naechsten. Eine Ausnahme
  gibt es: Wer bis dahin erst **eine** Mischung gefahren hat, darf
  weicher werden - sonst liesse sich die Pflicht zu zwei Mischungen nicht
  mehr erfuellen, wenn der Notstopp schon die haerteste aufgelegt hat.

**Nachsehen, was dabei herauskommt.** `python -m werkzeuge.boxenstopps`
faehrt fuenf Rennen der Liga 1 und schreibt je Fahrer auf, auf welcher
Mischung er startet, in welcher Runde er stoppt und wieviel Profil dann
noch drauf war. Die fuenf Strecken sind nicht ausgesucht, sondern nach
dem Streckenfaktor gezogen - Maximum, 75er Perzentil, Median, 25er
Perzentil, Minimum -, und das Wetter wird so lange neu gewuerfelt, bis
kein Abschnitt nass ist. Das ist ein Balancing-Werkzeug, kein Test: Es
sagt nichts richtig oder falsch, es zeigt nur, was die Strategie tut.

### Die Reifenwahl des Spielers

Nach dem Qualifying und **vor** dem Start zeigt das gefuehrte
Rennwochenende, was zur Wahl steht: das Wetter des Rennens, ob zwei
Mischungen Pflicht sind, und die zwoelf besten der tragfaehigen
Strategien mit Folge, Stoppzahl und Rueckstand auf die schnellste. Fuer
jeden der vier eigenen Fahrer laesst sich eine davon waehlen; wer nichts
waehlt, faehrt das, was das Team ihm zuteilt.

``Wochenendlauf.strategiewahl()`` rechnet Wetter und Varianten vor, ohne
das Rennen zu fahren - beides haengt allein am Seed, der Blick darauf
aendert also nichts. ``waehle_reifen()`` prueft die Wahl gegen die Regeln
und weist sie sonst ab.

**Waehrend des Rennens geht es nicht mehr.** Der Verlauf wird in einem
Stueck gerechnet und danach nur noch abgespielt (GDD 15); ein Eingriff
mitten im Rennen muesste ihn ab dieser Stelle neu rechnen.

Im **Qualifying** gibt es nichts zu waehlen: Dort gilt eine feste Regel -
immer die weichste Trockenmischung, bei wechselhaftem Wetter
Intermediates, bei Regen und Starkregen Regenreifen. Ueber eine einzige
gezeitete Runde nimmt jeder den schnellsten Satz.

### Was die Rangliste dazu zeigt

Eine Spalte **Mischung** mit dem Kuerzel und der Zahl der bisherigen
Stopps, etwa `M (1)`. Solange die Pflicht zu zwei Mischungen offen ist,
steht sie in Warnfarbe; sobald sie erfuellt ist, gruen mit Haken. Bei
Regen, Starkregen und wechselhaftem Wetter gilt die Pflicht nicht - dann
steht die Spalte von Anfang an auf gruen, weil nichts zu erfuellen ist.

### Warum die Unfallrate je Sekunde gilt

Als Wahrscheinlichkeit je Zeitschritt gelesen fielen bei 50 Schritten je
Sekunde alle fuenf erlaubten Ausfaelle in der ersten Runde. Die Rate gilt
deshalb je Sekunde in Reichweite - sonst haengt die Unfallhaeufigkeit an
der Schrittweite der Simulation statt am Spiel.

## Der Spieler ist Teamchef

Das GDD kannte einen Spielerfahrer. Der Auftraggeber hat daraus etwas
anderes gemacht: **Der Spieler fuehrt ein Team mit vier Fahrern**, alle
beginnen bei null, alle vier in Liga 20. Live angesehen werden die Rennen
der Ligen, in denen seine Fahrer stehen; alle uebrigen laufen im
Schnellmodus, aber vollstaendig - Erfahrung, Streckenkenntnis und
Statistik entstehen auch dort.

Daraus folgen drei Dinge, die vorher nicht im Modell standen:

* **Jedes Auto wird einzeln entwickelt.** Es gibt keine
  Teameigenschaft mehr; wer einen neuen Fahrer holt, bekommt ein
  **leeres, nicht aufgeruestetes Auto** dazu. Die Karriere fuehrt
  deshalb vier Autos statt einem (`karriere.autos`).
* **Die Einnahmen gehoeren dem Team**: vier Preisgelder, vier
  Sponsorensaetze, ein Konto.
* **Der Spieler altert wie alle anderen.** Seine vier Fahrer haben ein
  gewuerfeltes Ruecktrittsalter wie jeder Gegner.

### Der Transfermarkt

`rennmanager.kern.transfer` - nicht im GDD, komplett aus der Abstimmung.
Das Fenster liegt im **Winter**. Ein Vertrag laeuft ein bis vier Saisons
und wird nicht gespeichert, sondern aus dem Seed abgeleitet: So ist in
jedem Winter ein Teil des Feldes frei, ohne dass irgendwo eine Liste
gefuehrt wuerde.

Ein Wechsel kostet **Gehalt plus Abloese** - die Abloese nur, solange der
Vertrag laeuft. Und der Fahrer **waegt ab**: Liga gegen Auto gegen Geld,
gewichtet, gegen eine Schwelle, die mit seiner Bekanntheit steigt
(Punkt 5). Weil ein neuer Fahrer sein leeres Auto mitbringt, ist der
Autoteil beim Spieler fast immer ein Minus - Geld muss es ausgleichen.
Sagt er ab, nennt die Antwort den schwaechsten der drei Punkte.

### Geld: Kassenbuch und Finanzseite

`rennmanager.kern.kassenbuch` schreibt **jede** Geldbewegung mit - Datum,
Betrag, Haupt- und Unterkategorie, Fahrer. Das Konto kannte bisher nur
einen Stand; woher er kam, stand nirgends, und eine Finanzseite haette
nichts zu gruppieren gehabt.

| Hauptkategorie | Unterkategorien |
|---|---|
| Rennen | Preisgeld, Startgeld |
| Sponsoren | Sponsorenzahlung |
| Team | Monatsbudget, Startkapital |
| Ereignisse | Zuschuss, Strafe |
| Entwicklung | Fahrzeug-Upgrade, Fahrertraining |
| Werkstatt | Reparatur |
| Personal | Gehalt |
| Transfer | Abloese |

Das **Teambudget** des Spielers stand in der Welt und war reine Anzeige.
Jetzt zahlt es sich in zwoelf Monatsraten aufs Konto aus, je eine am
Monatsersten - auch in Vor- und Nachsaison. Die Budgets der KI-Teams
bleiben Anzeige (`finanzen.ki_budget_wirksam = false`).

Der Reiter **Finanzen** zeigt das Buch als Baum: Hauptkategorie,
Unterkategorie, darunter die Einzelbuchungen; wahlweise die ganze
Karriere oder eine Saison. Ein Test misst die Vollstaendigkeit statt
einzelner Betraege - der Saldo aller Buchungen muss den Kontostand
ergeben.

### Was ein Tag kostet

Zwei Entscheidungen des Auftraggebers weichen vom GDD ab:

* **Alles, was Zeit kostet, kostet auch etwas Erfahrung.** Die Zeit bleibt
  ein Tag und skaliert nicht; die Erfahrung waechst ueber dieselbe Kurve
  wie das Geld, also mit jedem Kauf. Wer schon Erfahrung zahlt, zahlt
  nicht doppelt.
* **Ein belegter Platz bleibt bis zum naechsten Rennen belegt.** GDD 2
  gibt jedem Tag zwei Plaetze; gemeint ist jetzt der Abstand zwischen zwei
  Rennen. Je Abstand gibt es also einen Trainings- und einen
  Werkstattschritt, nicht einen je Tag.
* **Ein Erfahrungssockel von 20 EP zum Start**
  (`kosten.startkapital_erfahrung`). Er folgt aus der ersten
  Entscheidung: Ohne ihn stuende der Spieler am 1. Januar mit null
  Erfahrung da, der erste Zeitkauf kostet aber 2 EP, und Erfahrung gibt es
  erst fuers Fahren - die Tage bis zum ersten Rennen waeren tot. Danach
  faellt der Sockel nicht mehr ins Gewicht: Platz 12 bringt 243 EP, ein
  Sieg 775.

## Talente und Generationen

`rennmanager.kern.talent` und `rennmanager.kern.generationen` (Punkt 35).

**Jeder Fahrer hat sein eigenes Potential**, gewuerfelt auf jede einzelne
Eigenschaft - auch auf die Wetterfaehigkeiten und die Streckenkenntnis.
Dazu ein eigenes Entwicklungstempo, ein eigenes Gipfelalter und ein
eigenes Alter, ab dem es wieder abwaerts geht. Das gilt fuer die KI wie
fuer die Fahrer des Spielers; es gibt keinen Sonderweg mehr.

Entwickelt wird ueber **Lueckenschluss**: Jedes Jahr holt ein Wert einen
Anteil des Abstands zu seinem Potential auf. Das ist skalenfrei - ein
Fahrer bei 5000 und einer bei 90000 machen denselben *relativen* Schritt.

Das Talent haengt an **(Fahrernummer, Geburtstag)**, nicht an der Nummer
allein. Sonst erbte ein Newgen das Talent seines Vorgaengers, denn er
uebernimmt dessen Nummer und Teamplatz - so bleiben die Teams bei vier
Autos.

### Was das die Ligatabelle gekostet hat

Der Ligakorridor aus GDD 9 gilt seither **nur noch beim Weltstart**.
Danach sortieren sich die Ligen ueber Auf- und Abstieg. Gemessen ueber
dreissig Saisons mit echtem Rennbetrieb, Ist gegen Soll:

```
Liga      1     5    10    15      20
         84%   59%   88%  149%   5182%
```

Der Grund ist strukturell: Ein Newgen-Jahrgang traegt im Schnitt ein
Potential von rund 33000 - Liga-10-Niveau -, steigt aber geschlossen in
Liga 20 ein, deren Soll bei 82 liegt. Liga 20 ist damit kein schwaches
Feld mehr, sondern der Talentpool der ganzen Welt.

**Der Auftraggeber hat das so entschieden**, nachdem ihm die Zahlen und
drei Gegenmassnahmen vorlagen. Die Ligen sind ab jetzt Leistungsklassen,
nicht mehr Altersklassen.

## Die Welt

`rennmanager.kern.welt` erzeugt aus einem Seed alles, was eine Karriere
braucht (GDD 12):

```python
from rennmanager.kern import welt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
w = welt.erzeuge(k, Seedquelle(4711), spielerliga=20)
len(w.fahrer)                 # 600 in 20 Ligen zu je 30
len(w.teams)                  # 150 mit je 4 Autos eines Herstellers
w.spieler.name                # der Spieler, alle Werte auf 0 (GDD 1)
w.teamkollegen(w.spieler)     # seine 3 KI-Teamkollegen
feld = welt.starterfeld(w, liga=10)
```

Die 4 Autos eines Teams fahren meist in verschiedenen Ligen, wie GDD 12
es erlaubt. Jedes Auto bekommt ein eigenes Profil.

### Warum es zwei Streuungsebenen gibt

GDD 12 laesst die Einzelwerte "+/- 25 % um den Mittelwert" streuen und
nennt als Ziel Regenspezialisten, Qualifying-Experten und Reifenschoner.
Davon kam fast nichts an: Gefahren wird mit den **Bereichsmitteln** aus
GDD 8, und ueber drei bis fuenf Einzelwerte mittelt sich die Streuung
weg - zwischen dem staerksten und dem schwaechsten Bereich eines Fahrers
lagen gemessen nur 20 %.

Deshalb wird zusaetzlich je Fahrer ein Faktor pro Wirkungsbereich gezogen
(+/- 30 %), den jede Faehigkeit nach ihrer Zeile der Wirkungsmatrix
gewichtet erbt. Damit steigt die Profilspanne auf 41 % im Schnitt: Ein
Fahrer ist in drei Bereichen Erster seiner Liga und in anderen Sechster.
Die Wetterfaehigkeiten stehen neben der Matrix und streuen fuer sich.

Die Faktoren sind auf den Mittelwert 1 normiert, und was das Kappen an der
Skala wegnimmt, wird zurueckgeholt. Ein Spezialist verteilt seine
Ligastaerke also um, statt mehr oder weniger davon zu haben: Jede Liga
trifft ihre beiden Kontrollwerte aus GDD 9 auf den Punkt.

Ligen ohne Kontrollwert in GDD 9 werden ueber die Tempotabelle bestimmt -
das Tempo waechst je Liga um 6,32 km/h, der Wert S ergibt sich durch
Umkehren der Kalibrierfunktion. So liegen alle 20 Ligen auf derselben
Kurve.

### Die Fahrerkarte

Ein **Doppelklick** auf einen Fahrernamen - in der Welt, der Saisonwertung,
dem letzten Rennwochenende, der Renn-Rangliste, dem Zwischenfall-Ticker,
dem Qualifying oder der Statistik - oeffnet die Karte dieses Fahrers. Ein
Rechtsklick tut dasselbe ueber ein Menue, weil man einen Doppelklick nicht
sieht. Der **Einfachklick** bleibt, was er war: Er waehlt die Zeile aus
und steuert damit den Steckbrief der Weltseite und die hervorgehobene
Linie im Punkteverlauf.

Die Karte ist ein eigenes, nicht modales Fenster - zwei Fahrer lassen sich
nebeneinanderlegen, und waehrend ein Rennen laeuft kann sie offen bleiben.
Fuenf Reiter:

| Reiter | Was darin steht |
| --- | --- |
| Steckbrief | Person, Team, Teamkollegen, Staerke und Platz in der Liga, Popularitaet, der Charaktersatz mit Staerken und Schwaechen einzeln |
| Werte | die 11 Wirkungsbereiche aus GDD 8 als Balken, dann alle 32 Einzelwerte und die 11 Eigenschaften neben der Matrix |
| Saison | die Zeile der laufenden Saison und der Punkteverlauf der Liga, in dem nur dieser Fahrer farbig ist |
| Laufbahn | Karrierezahlen ueber alle Saisons, Meisterschaften, Liga je Jahr als Linie, gehaltene Rundenrekorde |
| Strecken | Streckenkenntnis je Strecke mit Tempogewinn; Heimstrecken hervorgehoben (Punkt 49) |

Sie **rechnet nichts**: Gelesen wird nur, was Welt, Auto, Statistik,
Streckenkenntnis und Popularitaet ohnehin fuehren, und sie ist rein
lesend - Werte aendern geht weiter nur ueber den Editor. Fuer alle 600
Fahrer zeigt sie dasselbe; Konto, Sponsoren und Werkstatt des Spielers
bleiben auf ihren eigenen Seiten.

#### Die Fahrersuche

Ueber allen Reitern steht ein Suchfeld (Punkt 18, **Strg+F**). Name
tippen, Eingabetaste, die Fahrerkarte geht auf. Gesucht wird ueber die
ganze Zeile - Name, Kuerzel, Liga und Team -, deshalb findet "Rosskamp"
auch die vier Fahrer dieses Teams. **Fahrertreffer stehen vorn:** Auf
"kamp" passen 18 Zeilen, aber nur 2 ueber den Fahrernamen, und wer einen
Namen tippt, meint den Fahrer und nicht dessen Teamkollegen.

#### Warum die Balken gegen den eigenen Hoechstwert messen

Die Skala reicht von 0 bis 100.000, ein Fahrer aus Liga 20 steht bei 150.
Gegen die Skala waere jeder seiner Balken unsichtbar. Zu sehen ist hier
ohnehin die **Form** seines Profils, nicht sein Platz auf der Skala -
deshalb misst jeder Ast gegen seinen eigenen groessten Wert, und die Zahl
steht daneben. Es ist dieselbe Ueberlegung wie beim Charaktersatz, der
gegen den eigenen Durchschnitt misst.

Ein Neuaufbau des Fensters - Saisonwechsel, Editor, geladener Spielstand -
schliesst offene Karten: Die Welt ist danach eine andere.

### Der Charakter in einem Satz

38 Zahlen sagen alles und zeigen nichts. `rennmanager.kern.charakter`
macht daraus einen Satz fuer den Steckbrief:

```python
from rennmanager.kern import charakter

charakter.profil(k, w.fahrer[401].auto)
# "Stark in Gerade und Beschleunigen, schwach in Verschleiss/Defekte und
#  Ermuedung, dazu Anpassungsfaehigkeit und Windschattennutzung."
```

Gelesen wird nur, was schon da ist - die elf Wirkungsbereiche aus GDD 8
und die Eigenschaften daneben; es entsteht kein Wert, der irgendwo wirkt.
Gemessen wird gegen den **eigenen** Durchschnitt, nicht gegen die Skala:
Ein Fahrer aus Liga 20 hat lauter niedrige Werte und trotzdem ein Profil.
Genannt werden hoechstens zwei Staerken und zwei Schwaechen, und nur ab
6 % Abweichung. Gemessen bekommen in Liga 1 27 von 30 Fahrern ein Profil,
in den Ligen 5, 10 und 20 alle 30; der Spieler steht am ersten Tag auf
lauter Nullen (GDD 1) und liest "Noch kein Profil".

## Kalender und Zeitmodell

`rennmanager.kern.kalender` baut die Saison (GDD 2): Das erste Rennen ist
der erste Sonntag ab dem 1. Maerz, danach alle 14 Tage, das zwanzigste
266 Tage spaeter. Jeder Zyklus hat genau 10 nutzbare Tage; die uebrigen
vier sind zwei Reisetage, der Qualifying-Samstag und der Renn-Sonntag.

Zeit ist eine Kapazitaet: Jeder nutzbare Tag hat zwei Plaetze, einen fuer
den Fahrer und einen fuer die Werkstatt. Ein zugewiesener Tag hebt einen
Wert um `max(+10, +1 %)`.

```python
from rennmanager.kern import karriere
from rennmanager.konfiguration import lade

k = lade()
c = karriere.beginne(k, 2026, liga=20)
c.belege_tag("D1")     # Konzentration, reine Zeit - kostenlos
c.belege_tag("F10")    # Reifenhaltbarkeit, Geld und Zeit
c.kaufe("F1")          # Motorleistung, nur Geld - ohne Tag
c.bis_zum_rennen()
c.verbuche_rennen(platz=12, ueberholmanoever=4)
```

### Das Jahr als Band

Zeit ist eine Kapazitaet - in einer Liste von 365 Zeilen sieht man das
nicht. Die Karriereseite zeigt das Jahr deshalb als Band aus
Tagesstreifen, eine Spalte je Woche: Renntag, Qualifying, Reise,
verlorene Tage aus E29 Reisechaos, voll belegt, halb belegt, frei. Die
Legende zaehlt mit, und ein Mouseover nennt Datum und Zustand. Wo Luecken
im Band bleiben, ist Zeit liegen geblieben - das ist die ganze Aussage.

### Trainingsprogramme ueber mehrere Tage

Bis Punkt 84 standen die zehn nutzbaren Tage eines Zyklus nur in der
Anzeige: `belege_tag()` belegt den Platz bis zum naechsten Rennen (Punkt
69), egal ob noch neun Tage kommen oder einer. Zwei Buchungen je Fahrer
und Rennabstand, mehr gab der Kalender nicht her - die Tage selbst waren
keine Waehrung.

Ein Programm macht sie dazu. Es laeuft ueber fuenf bis zehn nutzbare
Tage, belegt solange denselben Platz und zahlt je Tag einen Anteil
dessen, was eine Einzelbuchung braechte:

    Zuwachs(n) = n * tag_anteil * Tageszuwachs

```python
c.freie_trainingstage()            # die noch offenen Tage bis zum Renntag
c.programm_vorschau("D1", 10)      # was es braechte, ohne zu buchen
c.starte_programm("D1", 10)        # Platz belegt, Tage vergeben
c.tag_weiter()                     # zaehlt mit, rechnet am Ende ab
```

Bezahlt und gutgeschrieben wird erst am Ende. **Ein Abbruch zahlt
anteilig**, was gelaufen ist: Sperrt ein Ereignis die Faehigkeit (GDD 14:
E2, E6) oder frisst es einen der vergebenen Tage (E29 Reisechaos), endet
das Programm vorzeitig, der Platz wird frei und die geleisteten Tage
werden abgerechnet. Einen Bonus fuers Durchhalten gibt es nicht - das
waere ein zweiter Anreiz neben dem Tagesanteil, und der Auftraggeber
wollte nur einen.

**Nie ueber ein Rennwochenende hinweg**: `freie_trainingstage()` schoepft
nur aus den nutzbaren Tagen bis zum naechsten Renntag, und `max_tage`
ist genau die zehn eines Zyklus. Ein Programm passt damit immer in einen
Rennabstand; am Renntag ist ohnehin jedes beendet.

#### Warum der Tagesanteil an der Rundung haengt

`tag_anteil` allein sagt noch nichts. Jeder Zuwachs wird auf ganze
Kaufschritte abgerundet (GDD 9, `kaufschritt = 10`), und der
Tageszuwachs ist fuer jeden Wert unter 2000 genau diese 10. Der Anteil
muss also erst einen vollen Schritt fuellen, bevor er ueberhaupt
sichtbar wird:

| Tage | bei 0,15 | bei 0,20 |
| --- | --- | --- |
| 5 | 7,5 -> **0** | 10,0 -> **10** |
| 7 | 10,5 -> 10 | 14,0 -> 10 |
| 10 | 15,0 -> **10** | 20,0 -> **20** |

Eine Einzelbuchung bringt 10 und belegt den Platz ebenfalls bis zum
Rennen. Unter 0,20 ist ein Programm damit nie besser als sie - bei 0,15
braechten fuenf Tage gar nichts und zehn Tage genau dasselbe. Der Wert
steht deshalb auf **0,20**: Ein Tag traegt ein Fuenftel einer Buchung,
fuenf Tage sind eine, zehn sind zwei. Weil der Platz nach dem Programm
frei wird, passen zwei Fuenftageprogramme in einen Zyklus.

Drei Tests in `test_training.py` halten das fest - nicht die Zahl,
sondern die Regel: Das laengste Programm muss die Einzelbuchung
schlagen, das kuerzeste muss ueberhaupt etwas bringen, und
`max_tage * tag_anteil` muss zwei Kaufschritte fuellen. Gemessen wird
dabei **auch bei Wert 0**, wo der Spieler startet (GDD 1) und die
Rundung am haertesten zuschlaegt. Ein frueherer Test mass nur bei
50.000; dort betraegt der Tageszuwachs 500, die Rundung faellt nicht ins
Gewicht, und 0,15 sah brauchbar aus.

##### Die Treppe am Anfang

Solange der Tageszuwachs genau ein Kaufschritt ist, zahlt nicht jeder
zusaetzliche Tag:

| Tage | bei Wert 0 | bei Wert 2.000 | bei Wert 50.000 |
| --- | --- | --- | --- |
| 5 | +10 | +20 | +500 |
| 7 | +10 | +20 | +700 |
| 9 | +10 | +30 | +900 |
| 10 | +20 | +40 | +1.000 |

Am Anfang lohnen sich deshalb nur die beiden Enden der Spanne - fuenf
Tage oder zehn, alles dazwischen verschenkt Vorrat. Je hoeher der Wert,
desto feiner wird die Treppe; ab etwa 5.000 zahlt jeder einzelne Tag.
Das ist keine eigene Regel, sondern dieselbe +10-Granularitaet aus
GDD 9, die auch den Kauf bestimmt.

### Was ein Upgrade kostet

`K(S) = K0 * faktor * (1 + S/1000)^0,6` je +10-Schritt. Der Faktor folgt
der Wirkungsbreite einer Faehigkeit - der Summe ihrer Gewichte aus der
Wirkungsmatrix, geteilt durch den Mittelwert. F9 Reifen-Grip wirkt auf
fuenf Bereiche und kostet den Faktor 2,10; F16 Kuehlung wirkt auf einen
und kostet 0,47. Im Mittel ueber alle Faehigkeiten ist der Faktor genau
1,0, sodass die Kontrolltabelle aus GDD 9 weiterhin stimmt.

## Die Saison

`rennmanager.kern.saison` faehrt die 20 Rennwochenenden aus GDD 2 in allen
20 Ligen und fuehrt je Liga eine Tabelle (GDD 13):

```python
from rennmanager.kern import saison, strecke, welt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
haupt = Seedquelle(4711)
w = welt.erzeuge(k, haupt.zweig("welt"), spielerliga=20)
lauf = saison.Saisonlauf(k, w, haupt, jahr=2026, strecken=strecke.lade_alle(k))

wochenende = lauf.fahre_rennen(ausfuehrliche_liga=20)
wochenende.verlauf               # abspielbares Rennen der Spielerliga
wochenende.liga(7).ergebnisse    # Wertung einer der 19 Schnellmodus-Ligen
lauf.tabelle(20).stand()[0]      # Tabellenfuehrer

lauf.fahre_saison()              # die restlichen 19 Wochenenden
lauf.auf_und_abstieg()           # 114 Wechsel: 57 Auf-, 57 Abstiege
neue_welt = lauf.naechste_welt() # Welt der Folgesaison
```

Bekommt der Saisonlauf eine Karriere, verbucht er nach jedem
Rennwochenende, was GDD 10 und 14 dem Spieler zusprechen: Preisgeld,
Startgeld, Sponsorenauszahlung und Erfahrung - Letztere auch aus den
gelungenen Ueberholmanoevern und, je Wetterlage getrennt, aus den
gefahrenen Kilometern. Defekte aus dem Rennen bleiben offen, bis er sie
bezahlt, und die gefahrenen Runden wachsen seiner Streckenkenntnis zu.
Dafuer fuehrt jedes `Ligawochenende` drei Angaben je Fahrer mit:

```python
liga = wochenende.liga(20)
liga.manoever_je_fahrer[401]     # gelungene Ueberholmanoever
liga.defekte_je_fahrer[401]      # ("X20",) - offen bis zur Reparatur
liga.kilometer_je_fahrer[401]    # {"trocken": 92.8, "heiss": 3.8}
```

Sie stehen fuer alle 600 Fahrer bereit, gebucht wird davon nur der
Spieler: Die KI hat weder Konto noch Werkstatt (GDD 12).

### Woraus die Erfolgschance beim Ueberholen kommt

Der Wirkungsbereich ``du`` aus GDD 8 traegt sechs Eigenschaften: F8
Bremsanlage, D7 Geraden, D8 Bremsen (je Gewicht 1), D10 Ueberholen und D11
Verteidigen (je 3) und D15 Nervenstaerke (1). ``erfolgschance`` rechnet
mit dem ganzen Bereich - vorher standen dort allein D10 und D11, die
uebrigen vier wurden berechnet und von nichts gelesen. Damit hat jeder der
elf Bereiche der Matrix eine Wirkung.

### Warum Ueberholmanoever nicht gleich Vorbeigaenge sind

``ueberholmanoever`` zaehlt **Positionsgewinne je Runde**: Wer lag zu
Rundenbeginn vor mir, und wen davon habe ich bis zum Rundenende hinter mir
gelassen? Ein Duell, das innerhalb einer Runde mehrfach hin und her geht,
ist damit *ein* Manoever - oder gar keins, wenn es am Ende steht wie am
Anfang. Ausgefallene und schon im Ziel stehende Autos zaehlen nicht mit:
An ihnen ist niemand vorbeigefahren, sie bleiben nur zurueck.

Das ist noetig, weil die Erfahrung aus GDD 10 an dieser Zahl haengt und
die beiden Rennmodelle sie sonst verschieden messen. Gemessen ueber ein
Rennen in Zandvoort (Liga 10, 48 Runden, 30 Autos):

| Zaehlweise | Manoever | je Auto |
| --- | --- | --- |
| jeder Vorbeigang (``Rennverlauf.manoever``) | 879 | 29,3 |
| Positionsgewinne je Runde | 301 | 10,0 |
| Schnellmodus | 72 | 2,4 |

Fuer Liga 10, Platz 8 schrumpft der Unterschied in der Erfahrung damit von
+37 % auf +11 %. Der Rest kommt daher, dass der Schnellmodus je Runde nur
*einen* Ueberholversuch zulaesst, die volle Simulation dagegen an jeder
Ueberholzone einen - das ist ein Unterschied in der Verkehrsdynamik, nicht
in der Zaehlweise.

Jeder einzelne Vorbeigang steht weiter in ``Rennverlauf.manoever`` und ist
fuer die Anzeige des Rennens da, nicht fuer die Wertung.

Kalender und Rennwochenende haengen dabei zusammen (GDD 2): Ein Rennen
findet an seinem Renntag statt. `fahre_rennen()` schaltet den Kalender der
Karriere bis dorthin vor - vor dem Rennen, damit die Ereignisse dieser
Tage noch auf es wirken - und danach einen Tag darueber hinaus. Wer
faehrt, ohne vorher geplant zu haben, laesst die nutzbaren Tage bis zum
Renntag verfallen; die Saisonseite sagt vorher, wie viele das waeren.

Punkte gibt es nach GDD 13: 40-35-30-...-1 fuers Rennen, 3 fuer die
schnellste Runde (auch ohne Zielankunft) und 5-3-1 fuers Qualifying. Bei
Punktgleichheit liegt vorn, wer mehr Siege hat, dann mehr zweite Plaetze.
Am Saisonende steigen je Liga die ersten drei auf und die letzten drei ab;
Liga 1 kennt keinen Auf-, Liga 20 keinen Abstieg. Der Wechsel gilt fuer
Fahrer, nicht fuer Teams - ein Team hat danach seine vier Autos
gegebenenfalls in anderen Ligen.

### Der Saisonwechsel

`naechste_saison()` macht aus dem Saisonende den Anfang des naechsten
Jahres. Die Karriere ist endlos; dieselben 600 Fahrer bleiben, es gibt
keine Zu- und Abgaenge.

```python
neu = lauf.naechste_saison()   # schliesst ab, wechselt die Ligen, zaehlt das Jahr hoch
neu.jahr                       # 2027
neu.welt.spieler.liga          # nach Auf- oder Abstieg eine andere
neu.statistik.abschluss(2026, 20).zeilen[0]
# Saisonzeile(fahrer=51, platz=1, punkte=809, siege=12, podien=19,
#             poles=8, schnellste_runden=10, ausfaelle=0, rennen=20)
```

| Wandert mit | Beginnt neu |
| --- | --- |
| Statistik: Rundenrekorde, Karrierezahlen, Historie | Saisontabellen aller 20 Ligen |
| Streckenkenntnis aller 600 Fahrer (GDD 6) | Kalender und Ereignisplan (GDD 2 und 14) |
| Konto, Werte, Sponsorenvertraege, offene Defekte, laufende Ereignisse (GDD 10 und 14) | Liga des Spielers nach Auf- oder Abstieg |

Die Historie traegt dabei jede Saison **vollstaendig**: Platz, Punkte,
Siege, Podien, Poles, schnellste Runden, Ausfaelle und Rennen je Fahrer.
Die Tabelle der Saison wird geleert - was dann nicht in der Historie
steht, ist fort.

Gemessen ueber drei voll gefahrene Saisons in Liga 20 (je rund 90
Sekunden fuer 20 Rennen mal 20 Ligen): Konto 12.180 EUR nach der ersten,
21.420 nach der zweiten, 34.000 nach der dritten; Streckenkenntnis in
Sakhir 19,6 / 36,4 / 52,2 Runden; nach jedem Wechsel stehen in jeder der
20 Ligen wieder genau 30 Fahrer.

### Der Punkteverlauf der laufenden Saison

Die Statistik fuehrt neben dem Endstand den Weg dorthin: `punktestand`
liefert den aufsummierten Stand eines Fahrers Rennen fuer Rennen.

```python
lauf.statistik.gefahrene_rennen(20)     # (1, 2, 3)
lauf.statistik.punktestand(20, 401)     # (0, 12, 27) - aufsummiert
```

Die Saisonseite zeichnet daraus ein Liniendiagramm unter der Tabelle: Man
sieht, wann eine Meisterschaft entschieden war und wann sie kippte. Es
gilt dieselbe Regel wie beim Rueckstandsdiagramm - das Feld liegt grau im
Hintergrund, hervorgehoben und am Linienende beschriftet sind nur der
Spieler und der in der Tabelle gewaehlte Fahrer.

Beim Saisonwechsel wird der Verlauf geleert; der Endstand steht dann in
der Historie. Er liegt im Spielstand (Version 4) in der Tabelle
`saisonverlauf`.

### Warum es zwei Rennmodelle gibt

Ein volles Rennwochenende in allen 20 Ligen wuerde mit
`rennmanager.kern.rennen` Minuten dauern. `rennmanager.kern.schnellsimulation`
bildet je Runde eine Rundenzeit statt 50-Millisekunden-Schritte: Ein
Wochenende ueber alle 20 Ligen braucht rund 4 Sekunden, eine ganze Saison
86. Wetter, Fehler, Unfaelle, Defekte und Reifenverschleiss sind dabei
dieselben Bausteine wie in der vollen Simulation.

Verkehr entsteht ueber die Reihenfolge: Wo sich die Reihenfolge gegenueber
der Vorrunde geaendert hat, ist ueberholt worden - und das gelingt nur mit
einem Wurf nach GDD 4. Bei gleichem Wetter in beiden Modellen weicht die
Siegerzeit um weniger als 1,3 % ab, die schnellste Runde um weniger als
1,4 %; ein Test haelt eine 2-%-Schranke fest. Ohne diesen Abgleich waeren
die Rundenrekorde der ausfuehrlich gefahrenen Spielerliga nicht mit denen
der uebrigen 19 vergleichbar.

Welche Liga ausfuehrlich faehrt, veraendert die uebrigen 19 nicht: Jede
Liga wuerfelt aus ihrem eigenen Zweig
`saison/<jahr>/rennen/<nummer>/liga/<liga>`.

## Ereignisse, Defekte und Reparatur

`rennmanager.kern.ereignis` setzt GDD 14 um: 0 bis 2 Ereignisse je
14-Tage-Zyklus, ausgeloest beim Tageswechsel in den ersten vier Tagen.

```python
from rennmanager.kern import karriere
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
c = karriere.beginne(k, 2026, liga=20, seedquelle=Seedquelle(4711))
c.tag_weiter()
c.meldungen[-1].zeile        # "E1 Erkaeltung - D2 -15 %, D1 -10 %"
c.faktoren()                 # {"D2": 0.85, "D1": 0.90}
c.fahrwerte()                # die Werte, mit denen gefahren wird
c.gesperrt()                 # was gerade nicht entwickelt werden darf
c.offene_reparaturen         # Defekte und Schaeden mit ihren Kosten
```

Die 35 Ereignisse kennen sechs Dauerarten und fuenf Wirkungsarten; ein
einzelnes kann beides mischen - E23 Hitzetraining hebt die Hitzeresistenz
dauerhaft und senkt D2 fuer ein Rennwochenende. Defekte bleiben nach dem
Rennen offen, bis der Spieler die Reparatur zahlt (Kostenstufe mal
Liga-Faktor).

Drei Ereignisse wirken nicht auf eine Faehigkeit, sondern auf die
Simulation selbst; der Saisonlauf reicht sie deshalb als eigene Groessen
durch, jeweils nur fuer den Spieler:

* **E3 Motivationsschub** hebt den *Mittelwert* der Tagesform um 3 %.
  Streuung, Grenze und die Daempfung durch D16 bleiben, wie GDD 11 sie
  nennt - der ganze Wurf verschiebt sich nach oben.
* **E10 Testfahrt geglueckt** hebt den Kenntniszuwachs der naechsten
  Strecke um 20 %. Deshalb bucht der Spieler seine Runden ueber die
  Karriere, nicht ueber das Feld.
* **E29 Reisechaos** nimmt nutzbare Kalendertage weg (GDD 2).

### Warum das Jahr ein durchgehendes 14-Tage-Raster hat

GDD 14 zaehlt Ereignisse je 14-Tage-Zyklus, GDD 2 kennt Zyklen aber nur
zwischen zwei Rennen. Vor- und Nachsaison sind zusammen rund ein Viertel
des Jahres und blieben sonst ereignislos - gerade die Vorsaison, in der
der Spieler 56 nutzbare Tage entwickelt. Deshalb laeuft ueber das ganze
Jahr dasselbe Raster, verankert am Tag nach dem ersten Rennen: Jeder
Zyklus endet genau auf einem Renntag, das Ausloesefenster faellt in die
freien Tage danach. Macht 27 Zyklen und 21 bis 33 Ereignisse je Saison.

## Neun Eigenschaften ueber das GDD hinaus

Aus einer Liste von 20 Vorschlaegen hat der Auftraggeber neun gewaehlt.
Alle Entscheidungen dazu stehen in OFFENE_PUNKTE.md (Punkte 48 bis 53).

| Was | Wirkung | Wo |
| --- | --- | --- |
| **Ermuedung** (GDD 8, Bereich `er`) | bis -2,0 % Tempo am Rennende, ab halber Distanz | `kern.tempoverlauf` |
| **Kaltreifen** | bis -3,0 % Tempo, abgebaut ueber die erste Runde | `kern.tempoverlauf` |
| **Bremskuehlung** | bis -4,0 % Bremsgrenze am Rennende | `kern.tempoverlauf` |
| **Windschatten** | bis +2,5 % Tempo, 30 m bis auf gleiche Hoehe, einmal je Gerade, danach Nachlauf | `kern.windschatten` |
| **Rhythmus** | +/- 1,5 % Querbeschleunigung, je nach Kurvenanteil der Strecke | `kern.rhythmus` |
| **Materialgefuehl** | Defektrate mal 1,0 bis 0,6 | `kern.zwischenfall` |
| **Heimstrecke** | +0,5 bis +1,0 % auf fuenf je Wochenende gezogene Eigenschaften | `kern.heimstrecke` |
| **Popularitaet** | +/- 25 % auf den Grundbetrag der Sponsorenangebote | `kern.popularitaet` |
| **Ueberrunden** | war schon richtig - siehe unten | `kern.rennen` |

Fuenf davon brauchen eine neue Eigenschaft. Sie stehen **neben der
Wirkungsmatrix** aus GDD 8, wie die Wetterfaehigkeiten aus GDD 7 und der
Reifenfluesterer:

```toml
[[zusatzfaehigkeit.liste]]
schluessel = "bremskuehlung"
name = "Bremskuehlung"
traeger = "fahrzeug"     # Fahrerwerte traegt die Tagesform, Fahrzeugwerte nicht
waehrung = ["G", "E"]
```

So bleiben Gesamtwert, Bereichswerte und damit die Kalibriertabelle aus
GDD 9 unberuehrt - gemessen liegt Zandvoort weiter bei +0.00. Dafuer
sorgt auch, dass **alle neuen Wirkungen hinter `ohne_zufall` liegen**:
GDD 9 kalibriert die freie Einzelrunde, und die kennt weder Ermuedung noch
kalte Reifen noch Windschatten.

### Der Nachlauf des Windschattens

Der Sog endete anfangs in dem Augenblick, in dem ein Auto vorbei war -
und der gerade Ueberholte klebte sofort wieder dran. Auf Wunsch des
Auftraggebers laeuft er jetzt nach:

* Der **Ueberholende** behaelt den Ueberschuss **50 m in voller Hoehe**
  und danach **zur Haelfte bis zum Anbremsen** derselben Geraden. Das
  Anbremsen erkennt das Modell daran, dass das Profil faellt - dort ist
  Schluss, sonst traege das Auto zu viel Tempo in die Kurve.
* Der **Ueberholte** bekommt waehrend der ersten 50 m gar nichts und
  danach die **Haelfte dessen**, was der Ueberholende in der zweiten Stufe
  hat. Er haengt sich also an, statt im vollen Sog zurueckzuschlagen.

Gemessen ueber 10 Rennen mit 20 gleich starken Autos: **16,7 % weniger
Manoever**, weil ein Ueberholmanoever jetzt haelt.

Die Naehe wird fuer den Sog an der **Position auf der Runde** gemessen,
nicht an der gesamt gefahrenen Strecke. Vorher konnte ein Ueberrundender
nie im Sog eines Ueberrundeten fahren, weil zwischen beiden rechnerisch
eine ganze Runde lag; ein Ueberrundeter bekam umgekehrt nie den Sog des
Ueberrundenden. Der erste Fall ist jetzt moeglich, der zweite bleibt
ausgeschlossen (`wird_ueberrundet`). **Verkehr, Ueberholen und Unfaelle
rechnen weiter auf der Gesamtdistanz** - so hat es der Auftraggeber
entschieden.

### Warum die Bremskuehlung ein zweites Profil bekommt

Die anderen Verlaeufe sind Faktoren aufs Tempo. Die Bremskuehlung senkt
dagegen die *Bremsgrenze* - und was das kostet, haengt davon ab, wie viel
auf einer Strecke gebremst wird. Deshalb wird das Geschwindigkeitsprofil
zweimal gebildet, einmal mit voller Bremse und einmal mit der Bremse des
Rennendes; dazwischen wird nach gefahrener Distanz gemischt. Das kostet
einmal je Rennen doppelte Rechenzeit fuers Profil und trifft dafuer
Monza anders als Zandvoort.

### Warum Punkt 12 nichts zu tun gab

"Beim Ueberrunden darf der Ueberrundende nicht aufgehalten werden" - das
war schon so. Die Folgeregel aus GDD 4 haengt an der *zurueckgelegten
Distanz*, nicht an der Position auf der Strecke; ein ueberrundetes Auto
liegt damit eine ganze Rundenlaenge zurueck und kommt nie ins
0,05-Sekunden-Fenster. Gemessen mit einem 98.000er Auto gegen neun
10.000er ueber 12 Runden: neun Autos fuenfmal ueberrundet, und die
Rundenzeiten des Schnellen im Verkehr sind auf die Millisekunde identisch
mit seiner Alleinfahrt. Zwei Tests halten das jetzt fest.

## Streckenkenntnis

`rennmanager.kern.streckenkenntnis` setzt GDD 6 um: Der Kenntniswert
steigt mit jeder gefahrenen Runde und gibt bis zu 1,5 % Tempo, voll nach
etwa 1.000 Runden. Er haengt am Paar aus Fahrer und Strecke; die
Simulation bekommt ihn als fertigen Tempofaktor.

Zwei Entscheidungen stehen daneben, beide gemessen begruendet in
OFFENE_PUNKTE.md:

* **Lerntempo je Fahrer** (Punkt 38). Die beiden Streuungen aus GDD 6
  sind Wuerfe je Session und mitteln sich weg - nach 20 Saisons blieben
  nur 10 % Unterschied zwischen den Fahrern. Ein fester Faktor je Fahrer
  haelt dagegen 35 %.
* **Die KI lernt nicht** (Punkt 39). GDD 12 sagt "die KI verbessert sich
  vorerst nicht"; ihr Stand wird einmal gesetzt und bleibt. Sonst liefen
  alle 570 KI-Autos ueber die Saisons der Kalibriertabelle aus GDD 9
  davon.

## Statistik und Spielstand

`rennmanager.kern.statistik` fuehrt, was die Saison ueberdauert (GDD 13):

```python
statistik.rekord("Monza", liga=10)      # schnellste Runde in Tausendsteln
statistik.bestenliste("siege")          # Karrierezahlen aller Fahrer
statistik.laufbahn(fahrer)              # je Saison Liga und Platz
statistik.punkte_in(2026, 10, fahrer)   # Gesamtpunkte je Liga und Saison
```

`rennmanager.kern.spielstand` schreibt alles in eine SQLite-Datei, wie
GDD 15 es vorgibt - eine Datei je Spielstand, im Menue unter Datei. Jede
Verbindung wird dabei ausdruecklich geschlossen: `with sqlite3.connect(...)`
committet nur, es schliesst *nicht*. Unter Linux faellt das nicht auf -
eine offene Datei laesst sich dort loeschen. Unter Windows nicht, und dann
ueberschreibt der naechste Autosave den alten Stand nicht mehr. Ein Test
zaehlt die Verbindungen selbst mit, statt sich aufs Betriebssystem zu
verlassen. Die Welt wird dabei vollstaendig abgelegt statt aus dem Seed neu
gewuerfelt: Nach dem ersten Auf- und Abstieg stimmt die gewuerfelte Welt
nicht mehr mit der gespielten ueberein. Ein Test haelt genau das fest.

Der Stand traegt seine **Version**. Version 5 legt Strecken- und
Wetterbilanz ab (Punkte 21 und 23). Version 2 legt die Historie je Saison
und Liga vollstaendig ab (Tabelle `historiezeile`) statt nur Reihenfolge
und Punkte; Staende der Version 1 bleiben lesbar, die Zahlen, die es dort
nicht gab, stehen auf 0. Auch das haelt ein Test fest - er baut einen
gespeicherten Stand auf das alte Schema zurueck und laedt ihn.

### Streckenbilanz, Wetterbilanz und Bestmarken

Was ein Fahrer **wo** und **bei welchem Wetter** erreicht hat, fuehrt die
Statistik als Summe je Paar (Punkte 21 und 23):

```python
statistik.strecken_von(fahrer)["Monza"].siege     # Bilanz eines Fahrers
statistik.wetterlagen_von(fahrer)["regen"].punkte
statistik.bilanzen_auf("Monza")                   # alle Fahrer dort
statistik.bilanzen_bei("regen")
```

Je Zeile stehen Starts, Siege, Podien, Poles, schnellste Runden,
Ausfaelle, Punkte, das beste Ergebnis und die **beste Liga** - die
staerkste Liga, in der dort ein Podium gelang. Zehn Siege in Liga 20 und
einer in Liga 3 stuenden sonst gleichwertig nebeneinander.

Zu sehen ist beides an zwei Stellen: in der Fahrerkarte (die
Streckenbilanz im Reiter *Strecken* neben der Streckenkenntnis, die
Wetterbilanz als eigener Reiter neben der Faehigkeit zu jeder Lage) und
auf der Statistikseite als Vergleich ueber alle 600 Fahrer.

#### Warum Summen und keine Rennliste

600 Fahrer mal 20 Rennen mal zwanzig Saisons waeren 240.000 Zeilen, und
der Spielstand wuechse endlos weiter. Als Summe bleiben es 12.000 Zeilen
je Strecke und 3.000 je Wetterlage - gleich viele nach der ersten Saison
wie nach der zwanzigsten. Ein Test haelt genau das fest: Vier Rennen auf
vier Strecken ergeben vier Zeilen je Fahrer, nicht acht.

Der Preis: Ein geladener Spielstand aelter als Version 5 hat keine
Bilanzdaten, und sie lassen sich nicht nachbilden - die einzelnen Rennen
von damals sind nirgends aufgehoben. Die Bilanz faengt dort bei null an.

#### Die vorherrschende Wetterlage

Eine Session wechselt 0- bis 3-mal (GDD 7). Die Wetterbilanz braucht aber
**eine** Lage je Rennen, und die richtige ist die, unter der am meisten
gefahren wurde - nicht die erste und nicht die haeufigste. Ein Rennen, das
zwei Runden im Regen beginnt und danach trocken bleibt, war ein
trockenes. Bei Gleichstand gewinnt die fruehere Lage, damit das Ergebnis
nicht an der Reihenfolge eines Woerterbuchs haengt.

#### Bestmarken

Die Statistikseite kennt eine Ansicht *Bestmarken* (Punkt 25) mit drei
Gruppen: die schnellste Runde je Strecke, die Bestmarken der Karriere
(meiste Siege, Punkte, Podien, Poles, schnellste Runden und die beste
Siegquote ab 20 Rennen) und aus der Historie die beste einzelne Saison.
Die Quote braucht die 20 Rennen, sonst gewaenne, wer einmal gefahren und
einmal gewonnen hat.

Wahlweise **insgesamt oder je Liga** - mit einer Auswahlliste und zwei
Pfeilen zum Durchschalten. Insgesamt gewinnt fast immer Liga 1, dort
faehrt das staerkste Feld; wer wissen will, wer in Liga 14 am meisten
gewonnen hat, muss die Liga einzeln sehen koennen.

In der Ligaansicht kommen die Karrierezahlen aus der **Historie**, nicht
aus ``statistik.karriere``: Die Karrierezahlen rechnen alles zusammen und
wissen nicht, in welcher Liga ein Sieg fiel. ``karriere_in_liga`` summiert
stattdessen die Abschlusstabellen dieser Liga. Der Preis: Nur
abgeschlossene Saisons zaehlen, die laufende steht noch in den Tabellen.
Dafuer stimmen Karriere- und Saisonmarke einer Liga zusammen, statt zwei
verschiedene Namen zu nennen.

### Autosave und Schnellspeicher

Zwei Staende schreibt das Spiel ohne Dialog, an einem festen Ort unter
`~/.rennmanager`:

| Datei | Wann |
| --- | --- |
| `autosave.sqlite` | nach jedem Tageswechsel und jedem Rennwochenende |
| `schnellspeicher.sqlite` | auf **F5**; **F9** laedt ihn zurueck |

Beide werden **ueberschrieben**, nicht fortgeschrieben: Ein Autosave, der
mitwaechst, fuellte nach zwanzig Saisons das Verzeichnis. Von Hand
gespeicherte Staende bleiben davon unberuehrt - fuer die fragt der
Dateidialog weiter nach Ort und Namen.

Ein misslungener Autosave haelt das Spiel nicht an, verschwindet aber auch
nicht stillschweigend: Er meldet sich in der Statuszeile.

## Der Editor

GDD 15 nennt unter den Balancing-Werkzeugen eine Debug-Ansicht. Der Reiter
**Editor** ist sie: Er aendert je Fahrer alle 32 Einzelwerte aus GDD 5 und
6, die sechs Faehigkeiten neben der Wirkungsmatrix, die Streckenkenntnis
je Strecke und die Stammdaten. Unten steht, was die Eingabe bewirkt -
Bereichsmittel, staerkster und schwaechster Bereich, freie Rundenzeit auf
der gewaehlten Strecke -, damit man nicht blind schiebt.

Oben waehlt man die Strecke; die Liste zeigt dann je Fahrer seine
**Rundenzeit** und den Rueckstand zur Bestzeit. Die Zeit ist trocken und
ohne jeden Wurf gerechnet - keine Tagesform, keine Rundenform, kein
Eigenschafts-Zufall (GDD 11), kein Reifenverschleiss, kein
Qualifying-Bonus -, also genau das Modell, mit dem GDD 9 kalibriert. Die
Streckenkenntnis aus GDD 6 ist drin: Sie ist kein Zufall, sondern eine
Eigenschaft des Fahrers auf dieser Strecke.

Daran sieht man, was die Streuung anrichtet: In Liga 10 weichen auf Monza
27 von 30 Plaetzen von der reinen Staerkereihenfolge ab, und zwischen
Monza und Zandvoort aendern sich 23 von 30 Plaetzen.

Liga und Team bleiben aussen vor: Ein Wechsel dort spraenge die
Ligastaerken aus GDD 9 und die Teamgroessen aus GDD 12.

```python
from rennmanager.kern import welt

neu = welt.mit_fahrerwerten(w, {17: (werte, wetterwerte)})
neu = welt.mit_fahrerdaten(neu, {17: {"vorname": "Ada", "nachname": "Lovelace"}})
```

### Wo die Werte des Spielers stehen

Nicht in der Welt, sondern in der Karriere: GDD 1 laesst den Spieler bei 0
anfangen und sich entwickeln, GDD 14 laesst Ereignisse und Defekte an den
Werten ziehen. Beides fuehrt ``rennmanager.kern.karriere``. Ins Rennen
kommen sie ueber ``starterfeld(..., autos=...)``, das einzelne Autos
ersetzt, ohne die Reihenfolge des Feldes zu verschieben - die richtet sich
weiter nach der Welt, sonst passten die Indizes aus dem Qualifying nicht
mehr aufs Rennen.

Qualifying und Rennen bekommen dabei ein eigenes Feld, weil E12 aus GDD 14
nur im Qualifying wirkt.

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

Das GDD nennt an vielen Stellen eine Mechanik, ohne sie zu beziffern. Zu
jeder liegen in [OFFENE_PUNKTE.md](OFFENE_PUNKTE.md) Vorschlaege mit
Begruendung; alle 39 sind am 2026-09-17 entschieden, der Abschnitt `[offen]`
in der Konfiguration ist leer. Kommt spaeter eine Luecke hinzu, wird sie dort
vermerkt und im Hauptfenster angezeigt, statt still gefuellt zu werden.

## Datenquellen

Streckendaten: [TUMFTM/racetrack-database](https://github.com/TUMFTM/racetrack-database),
Lizenz LGPL-3.0. Die 20 Strecken der Saison liegen unveraendert unter
`daten/strecken/` und werden in die .exe gepackt; Herkunft, Format und
Datenqualitaet beschreibt `daten/strecken/HERKUNFT.md`.
