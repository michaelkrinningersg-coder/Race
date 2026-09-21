# Rennmanager

Motorsport-Manager mit sichtbarer Rennsimulation. Grundlage ist das
[Game Design Dokument v1.0](Rennmanager%20%E2%80%93%20Game%20Design%20Dokument%20%28v1.0%29.md);
die Arbeitsregeln stehen in [CLAUDE.md](CLAUDE.md).

**Stand: alle zehn Schritte der Umsetzungsreihenfolge sind durch, dazu
der Umbau aus Punkt 101.** Eine Saison laeuft vom 1. Januar bis zum
Saisonabschluss, mit Rundenrekorden, Historie und Spielstand auf der
Platte. Dazu der Editor aus GDD 15 (Debug-Ansicht), mit dem sich jeder
Fahrer aendern laesst.

Die Welt besteht seit Punkt 101 aus **einem Feld von 50 Autos** - 25
Hersteller mit je zwei Autos, der Spieler hat also selbst zwei. Es gibt
keine Ligen mehr, keinen Auf- und Abstieg, keinen Transfermarkt, kein
Geld und keine Fahrerentwicklung: Die Staerken stehen fest, und wer wie
schnell ist, entscheidet sich auf der Strecke.

Das ganze Feld liegt **vier Prozent Rundenzeit** auseinander: Der Beste
faehrt auf Zandvoort 180 km/h Schnitt (S = 98.000, 1:24.887), der Letzte
1:28.282. Alle 50 Staerken liegen gleichmaessig dazwischen; das Rauschen
der Einzelwerte macht daraus gemessene 4,5 bis 4,7 Prozent. Jedes Rennen
geht ueber die volle Distanz von 290 km, und **jeder Platz bekommt
Punkte** - von 100 fuer den Sieg bis 1 fuer Platz 50.

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

Das Hauptfenster hat seit Punkt 101 **acht** Reiter: Uebersicht, Strecke,
Runde, Welt, Rennwochenende, Saison, Statistik, Editor. Karriere,
Finanzen, Sponsoren und Transfermarkt sind mit dem Umbau weggefallen.

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

Mit dieser Form trifft das Modell den Anker aus GDD 9 - 180 km/h bei
S = 98.000 auf Zandvoort - auf 0,01 km/h genau und ebenso Werte, die bei
der Anpassung gar nicht vorkamen. Angepasst wird gegen ein Raster ueber
die ganze Skala plus die beiden Enden des Feldes (`werkzeuge/kalibriere.py`).

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
feld = rennen.starterfeld(k, spielerplatz=30)
verlauf = rennen.simuliere(
    k, monza, feld, rennen.rundenzahl(k, monza), Seedquelle(4711),
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
  Rennzeit, neueste zuerst, **fuenfzig Zeilen tief** (Punkt 97). Zwoelf
  waren es bis dahin - bei 50 Autos ueber die volle Distanz fallen
  mehrere hundert Zwischenfaelle, und wer zwei Bilder wegsah, hatte den
  Ausfall verpasst. Passen die Zeilen nicht ins Blatt, rollt es; den
  Rollbalken setzt Qt von selbst (gemessen: 47 Zeilen in einem 460 px
  hohen Blatt ergeben einen Rollbereich von 17). Der Ticker steht als
  Blatt **Meldungen** rechts bei den Tabellen; bis Punkt 82 war er eine
  Fussleiste unter der ganzen Seite und nahm ihnen Hoehe weg.
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

Bei 40 Linien traegt Farbe keine Identitaet mehr - benachbarte Toene sind
nicht auseinanderzuhalten, fuer Farbenblinde erst gar nicht. Das Feld
liegt deshalb als duenne graue Linien im Hintergrund; hervorgehoben und
am Linienende direkt beschriftet sind nur zwei: das Auto des Spielers und
das in der Rangliste gewaehlte. Gezeichnet wird mit `QPainter` - PySide6
bringt `QtCharts` nicht mit, und eine zusaetzliche Abhaengigkeit muesste
in die .exe.

Die Achse skaliert nicht nach Ausgefallenen und Ueberrundeten: GDD 4 kennt
fuer sie keinen Zeitrueckstand, sondern "+n Rd.", und ihre Kurve bleibt
beim letzten gueltigen Wert stehen. Dass ein Feld auseinanderliegt,
bleibt dagegen sichtbar - seit Punkt 101 sind das die vier Prozent
Rundenzeit zwischen dem Besten und dem Letzten, ueber 69 Runden also rund
eine Minute.

## Wetter und Zufall

`rennmanager.kern.wetter` wuerfelt je Session eine Lage, die 0- bis 3-mal
um je eine Stufe wechselt. `rennmanager.kern.form` liefert die drei
Zufallsebenen aus GDD 11: Tagesform, Eigenschafts-Zufall und Rundenform.

### Die Form wechselt je Sektor, nicht je Runde

Die Rundenform wird **an jeder Sektorgrenze** neu gezogen, im Qualifying
wie im Rennen - eine Runde besteht damit aus vier Wuerfen statt einem.
Gestreut wird mit sigma = 0,5 % (`[zufall.rundenform] sigma`), gedaempft
ueber D12 Konstanz.

Die Wuerfe sind **nicht unabhaengig**: Wer im Sektor davor Plaetze
gutgemacht hat, faehrt mit 3/4 Wahrscheinlichkeit auch den naechsten in
der oberen Haelfte seiner Streuung, und je mehr Plaetze es waren, desto
naeher liegt die Wahrscheinlichkeit an eins; bei verlorenen Plaetzen
kehrt sich das um (`[zufall.rundenform.kopplung] bei_einem_platz`). So
haelt ein Lauf ueber mehrere Sektoren an, statt sich von selbst
wegzumitteln - und trotzdem bleibt jeder Sektor ein eigener Wurf.

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
feld = rennen.starterfeld(k, spielerplatz=30)
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

Wo der Spieler im Feld steht, ist **nicht** zur Wahl: Sein Team wird
wie jedes andere auf die Leiter gewuerfelt (Punkt 101). Die Laender
kommen aus derselben Liste wie die der KI-Fahrer, damit der Spieler kein
Land traegt, das es in dieser Welt sonst nicht gibt; an zweien haengt
mehr als Farbe, denn wer im Land einer der 20 Strecken wohnt, hat dort
seine Heimstrecke (Punkt 49).

### Das gefuehrte Rennwochenende

In der Oberflaeche laeuft ein Rennwochenende in vier Schritten ab, in
einem Reiter:

1. **Vorschau** - Renntag, Strecke, Charakter, Laenge, Rundenzahl und der
   Tabellenstand vor dem Rennen. Vor Rennen 1 gibt es noch keine Tabelle;
   dann steht dort das Feld nach Staerke.
2. **Qualifying** - die Session des ganzen Feldes als Zeitenmonitor,
   abspielbar wie das Rennen (GDD 4)
3. **Rennen** - auf die gefahrene Aufstellung, abspielbar im Zeitraffer.
   Es startet in **Echtzeit** (1x) und laeuft von selbst los, sobald man
   den Reiter aufschlaegt; die Stufen 1x bis 100x lassen sich waehrend
   des Rennens umstellen (``zeitraffer.start_stufe``)
4. **Ergebnis** - die eigene Wertung, das Rennergebnis und die Tabelle
   danach mit dem Sprung gegen vorher

Gefahren wird, was der Kalender vorgibt (GDD 2): Strecke, Rundenzahl,
Aufstellung und Seed kommen aus der Saison. Frueher liessen sich hier
Strecke, Rundenzahl, Seed und Startaufstellung frei einstellen -
das war ein Werkzeug, kein Spiel. Zum Kalibrieren dienen
`python -m rennmanager --pruefe` und die Werkzeuge unter `werkzeuge/`,
die ohne Oberflaeche laufen.

```python
from rennmanager.kern.saison import Wochenendlauf

wochenende = Wochenendlauf(lauf)
wochenende.nummer, wochenende.strecke.name, wochenende.runden   # Vorschau
wochenende.fahre_qualifying()   # ab hier springt der Kalender auf den Renntag
wochenende.fahre_rennen()       # auf die Aufstellung des Qualifyings
wochenende.schliesse_ab()       # verbuchen: Tabelle, Statistik, Kenntnis
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
die Box. Es stehen immer alle vierzig Autos da, damit die Tabelle beim
Abspielen nicht springt (Punkt 64). Wer faehrt, hat noch keine Position -
seine Rundenzeit laeuft kursiv mit, bis sie im Ziel steht.

Der letzte Sektor endet dabei per Definition im Ziel: Sektorzeiten und
Rundenzeit runden getrennt auf ganze Millisekunden (GDD 15), ihre Summe
trifft die Rundenzeit also nicht zwingend. Ohne diese Festlegung waere
ein Auto fuer einen Takt im Ziel, ohne seinen letzten Split gesetzt zu
haben - derselbe Rundungsfall wie bei der idealen Runde im Rennen.

##### Was die Tafel sonst noch zeigt (Punkt 93)

Vier Dinge, die die Uebertragung lesbar machen:

* **Intervall** als eigene Spalte neben dem Rueckstand. Zwei
  verschiedene Fragen - "wie weit bin ich hinten" und "wen habe ich
  direkt vor mir" -, und die Tafel beantwortete bisher nur die erste.
  Die Intervalle summieren sich genau zum Rueckstand; ein Test haelt das
  fest.
* **Wer gerade auf seiner gezeiteten Runde ist**, bekommt einen kuehlen
  Schimmer hinter der Zeile. Unter dreissig Zeilen findet man ihn sonst
  nicht.
* **Wer sich gerade eingereiht hat**, steht ueber der Tabelle: *"P4: GUN
  verdraengt ME4 um +0,132 s"*. Eine eigene Zeile und keine Spalte - es
  betrifft immer nur ein Auto.
* **Die neue Pole leuchtet golden auf.** Der Erste der Session
  uebernimmt dabei keine Pole, er eroeffnet sie.

Die Rechnung dazu steht im Kern und nicht in der Anzeige:
`session.letzte_zielankunft(t, fenster)` liefert die juengste Ankunft
mit Platz, Verdraengtem, Abstand und der Frage, ob die Pole gewechselt
hat. Das Fenster zaehlt in **Sessionzeit**, nicht in Bildschirmzeit: Bei
50-fachem Zeitraffer waere eine Sekunde Bildschirmzeit fast eine Minute
Session, und der Hinweis stuende dauernd da.

Dazu drei Dinge um die Tafel herum:

* **"Naechste Ankunft"** springt zu dem Augenblick, in dem der naechste
  Fahrer ueber die Linie kommt - dorthin also, wo sich die Tafel
  aendert. Bei 75 Minuten Session ist das der meistgebrauchte Knopf;
  dafuer den Zeitraffer hochzudrehen und wieder herunter ist Arbeit.
  Gesprungen wird **auf** die Ankunft, nicht eine Millisekunde davor:
  Dort steht die neue Zeit schon da.
* **Das Wetterband** unter der Wiedergabeleiste zeigt den ganzen
  Verlauf: hell ist trocken, dunkel ist nass, ein Strich sagt, wo die
  Wiedergabe steht. Die Farben sind **sequenziell**, nicht kategorial -
  "wie nass" ist eine Groesse mit Richtung. Ein Regenabschnitt in
  Minute 40 ist der Grund, warum eine Strategie aufgeht oder nicht, und
  bisher sah man ihn erst, wenn man hineinfuhr. Dasselbe Band steht
  spaeter im Rennen.
* **Die Streckengrafik** faehrt die gezeiteten Runden ab. Wer in der Box
  steht oder sich aufwaermt, ist nicht darauf - ein Feld aus
  Aufwaermpunkten wuerde die zwei zudecken, auf die es ankommt. Gerechnet
  wird der Ort ueber die **Sektorgrenzen**: Sie sind die einzigen
  Stellen, an denen Zeit und Ort beide bekannt sind, innerhalb eines
  Sektors wird linear interpoliert.

##### Die Streckenbestmarke (Punkt 93, A17)

Neben dem Wetter steht die **schnellste je hier gefahrene Qualirunde**,
mit Fahrer und Jahr. Sie wird **getrennt vom Rennrekord** gefuehrt: Eine
Qualirunde faehrt man auf leerer Strecke mit frischen Reifen, eine
Rennrunde mit Verkehr und abbauenden Reifen - in einem Topf fiele der
Rennrekord nie wieder. Gemeldet wird beim Verbuchen des Wochenendes,
gespeichert ab Spielstandversion 10; aeltere Staende fangen bei null an,
und die naechste Pole setzt die Marke.

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

#### Warum das Rennen im Hintergrund rechnet

Ein Rennen zu rechnen kostet gemessen rund eine Minute (Zandvoort,
50 Autos, 69 Runden ueber die volle Distanz). Bis Punkt 86 lief das im
Oberflaechen-Thread: Der Knopf ging aus, der Mauszeiger wurde zur Sanduhr,
und das Fenster reagierte eine Dreiviertelminute lang auf nichts. Ein Fenster, das nicht reagiert, sieht
abgestuerzt aus - auch wenn es fleissig rechnet.

Jetzt laeuft dieselbe Rechnung in einem eigenen Faden
(`rennmanager.ui.hintergrund.Rechenlauf`) und meldet unterwegs, wie weit
sie ist: "Rennen wird gerechnet - Runde 23 von 69". Schneller wird sie
davon nicht, sie fuehlt sich nur nicht mehr wie ein Haenger an.

`simuliere()` nimmt dafuer einen `fortschritt`-Rueckruf, der bei jeder
vollen Runde des Fuehrenden gerufen wird. Er liest nur mit - am Rennen
aendert er nichts, und das haelt ein Test fest. Je Rechenschritt zu
melden waere bei 313.599 Schritten selbst eine Bremse.

Der Arbeitsfaden fasst keine Widgets an; er meldet ueber Signale, die Qt
in die Schlange des Hauptthreads stellt. Alles andere waere ein Absturz,
der erst beim Kunden auftritt.

#### Warum der Aufbau nichts bewegt

Der `Wochenendlauf` ist beim Aufbau eine reine Vorschau: Strecke,
Rundenzahl und Renntag stehen fest, ohne dass der Kalender vorschaltet
oder ein Wuerfel faellt. Sonst kostete schon das Aufschlagen des Reiters
die nutzbaren Tage bis zum Rennen (GDD 2) - man haette Zeit verloren, nur
weil man hingesehen hat.

Gebucht wird erst im letzten Schritt. Ein abgebrochenes Wochenende bewegt
die Saison nicht.

#### Warum gefuehrt und am Stueck dasselbe ergibt

`Saisonlauf.fahre_rennen` rechnet das Wochenende in einem Zug, das
gefuehrte Wochenende in vier Schritten. Dass beides dasselbe ergibt,
haengt daran, dass die Seedzweige nach ihrer **Sache** heissen
(`qualifying`, `rennwetter`, `rennen`) und nicht nach der Reihenfolge, in
der jemand sie zieht. Ein Test haelt es fest - gemessen stimmen alle 50
Ergebniszeilen ueberein, dazu Tabelle, Streckenkenntnis und Popularitaet.
Gegenprobe mit einem anderen Seed: Dann weicht alles ab.

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

Die Streckenwirkung kommt aus der Querbeschleunigung der Runde:
Zandvoort nimmt die Reifen deutlich mehr her als Monza.

### Was ein Fehler kostet

Kein Zeitabzug, sondern **Stillstand**: Das Auto geht auf 0 km/h, steht
eine gewuerfelte Zeit und faehrt danach mit seiner eigenen
Beschleunigungskurve wieder an. Gemessen laeuft es nach der Pause ueber
1,3 → 2,6 → 3,9 km/h an, nicht sprunghaft zurueck aufs alte Tempo. Der
wirkliche Verlust ist deshalb groesser als die Standzeit - das Anfahren
kommt obendrauf.

**Die Standzeit ist eine Verteilung, keine Zahl** (Punkt 96). Frueher
kostete jeder Fehler dieselben 1250 ms; ein Verbremser und ein Dreher
waren damit dasselbe. Der Auftraggeber hat die Verteilung ueber ihre
Streuungsbaender beschrieben - Gipfel bei 1,2 s, und um ihn herum:

| Band | | |
| --- | ---: | ---: |
| 1 Sigma (68,3 %) | 0,80 s | 1,80 s |
| 2 Sigma (95,4 %) | 0,60 s | 3,00 s |
| 4 Sigma (99,99 %) | 0,32 s | 4,60 s |
| harte Grenzen | 0,30 s | 5,00 s |

Genau das steht in ``[fehler.zeitverlust]``: je Stuetzstelle der Anteil
der Fehler darunter und die Sekunden dazu, dazwischen linear. Gezogen
wird daraus mit dem Zufallsstrom des Rennens; ohne ihn - fuer alles, was
nach GDD 9 ohne Zufall rechnen soll - kommt der Erwartungswert zurueck.

**Der Erwartungswert bleibt, wo er war.** ``mittelwert_ms = 1250`` haelt
ihn fest: Die Tabelle kommt von sich aus auf 1,3716 s und wird beim Laden
mit **0,9113** gestaucht. Damit verliert ein Rennen insgesamt so viel
Zeit an Fehler wie vorher, nur ungleich verteilt - die Streuung ist eine
Frage der Dramaturgie, nicht des Balancings. Nach der Stauchung liegt der
Gipfel bei 1,09 s, die Grenzen bei 0,27 und 4,56 s, und 11 % der Fehler
kosten mehr als zwei Sekunden. Wer die Eckwerte unveraendert sehen will,
setzt ``mittelwert_ms = 1372``.

``python -m rennmanager --pruefe`` zeigt die Zahlen, mit denen wirklich
gefahren wird:

```
Fehler:        Standzeit 0.27 bis 4.56 s, Gipfel 1.09 s, im Mittel 1.25 s
```

Gemessen an einem ganzen Rennen (Zandvoort, 69 Runden, 40 Autos, vor
Punkt 101) fallen 371 Fehler: Standzeiten von 0,34 bis 4,05 s, 44 davon ueber zwei
und 9 ueber drei Sekunden. Zusammen 464 Sekunden Stillstand - auf die
Sekunde dasselbe, was die frueheren 1250 ms ergeben haetten.

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
ohnehin langsamer ist, gilt ihr eigenes Tempo minus 5 Prozent. Beim Feld
von heute kommt das nicht mehr vor - die Gasse liegt auf der Geraden,
dort werden 200 bis 400 km/h gefahren. Die Regel steht trotzdem: Sie ist
gebaut fuer den Fall, dass die Gasse schneller waere als die Strecke, und
ohne sie kostete die Boxengasse dort gar nichts. Seit Punkt 101 gibt es
nur noch **ein** Limit (`[boxenstopp] limit_kmh = 80`) statt einer
Staffelung je Liga.

Ein Stopp kostet vier Dinge: die langsame **Durchfahrt**, das **Bremsen**
bis zum Stillstand, die **Standzeit** (6 bis 12 Sekunden, gewuerfelt) und
das **Anfahren** aus dem Stand. Bremsen und Anfahren kommen aus den
Grenzen dieses Autos: zusammen rund 1,7 Sekunden - ein schwaecheres Auto
kommt aus der Box etwas langsamer heraus. Im Zeitraffer
faehrt das Auto die Gasse wirklich langsam ab und steht wirklich, der
Schnellmodus bucht dieselbe Summe.

**Die Strategie steht vor dem Start fest.** Einmal je Rennen werden alle
zulaessigen Mischungsfolgen durchgerechnet - als Minimum-Plus-Faltung
ueber die Stints, exakt und nicht geraten. Was mehr als die Schwelle
hinter der besten liegt, faellt heraus (60 s bei 300 km, 30 s bei 100 km);
unter den ueberlebenden waehlt jedes Auto zufaellig. Deshalb faehrt nicht
das ganze Feld dasselbe, und trotzdem faehrt niemand offensichtlichen
Unsinn.

**Gerechnet wird mit dem Medianfahrer, allein auf der Strecke.** Frueher
setzte das staerkste Auto den Massstab, und danach rechnete *jedes* Auto
seine Stopprunden noch einmal mit den eigenen Werten nach - wer die
Reifen schlechter schont, kam frueher herein. Das gab dreissig
Abwandlungen statt einer Handvoll Strategien. Jetzt steht ein Satz
zugelassener Varianten fest, die Autos ziehen daraus, und was ein
einzelnes Auto vom Median abweicht, faengt im Rennen der Zwangsstopp bei
30 Prozent Restprofil ab. Oben im Rennen steht, wie viele verschiedene
Strategien unterwegs sind.

Danach - und **nur** danach - kommt das Boxenstoppfenster: ein
zufaelliges Delta von +/- 3 Prozent der Renndistanz auf jede Stopprunde,
mindestens aber eine Runde, so dass immer drei Runden moeglich bleiben.
Es entzerrt die Boxengasse, ohne den Plan zu veraendern.

**Gezogen wird gewichtet, nicht gleich verteilt.** Naturgemaess gibt es
mehr Varianten mit mehr Stopps: Bei drei Trockenmischungen hat eine
Ein-Stopp-Folge 3^2 = 9 Reihenfolgen, eine Zwei-Stopp-Folge 27 und eine
Drei-Stopp-Folge 81. Wer gleich verteilt zieht, laesst das Feld schon
deshalb oefter dreimal stoppen - gemessen planten in Zandvoort 86 und am
Nuerburgring 97 Prozent der Autos drei Stopps, ohne dass das jemand
entschieden haette. Die Gewichte gleichen das aus: Ein-Stopp-Varianten
**zehnmal**, Zwei-Stopp-Varianten **2,75-mal** so wahrscheinlich wie
Drei-Stopp-Varianten. Gezogen wird weiterhin nur aus dem, was die
Vorausberechnung zugelassen hat - das Gewicht aendert die Auswahl nicht,
nur ihre Haeufigkeit.

**Das Strategieblatt.** Ein Klick auf die Zahl oben im Rennen oeffnet
eine Uebersicht: je vertretener Strategie die Mischungsfolge, die
geplanten Stopprunden, wie viele Autos sie fahren - und zwei Zeiten
nebeneinander. *Ohne Verkehr* ist die Rennzeit, die der Planer vor dem
Start gerechnet hat (Medianfahrer, allein auf der Strecke); *im Rennen*
ist der mittlere Rueckstand der Autos, die sie fahren, zum gerade
gezeigten Zeitpunkt. Der Unterschied zwischen beiden Spalten ist genau
das, was die Rechnung nicht kennt: Verkehr, Fahrer, Fehler, Zwangsstopps.
**Wer welche Strategie faehrt, bleibt geheim** - die Autonummern stecken
in den Daten, damit sich der Mittelwert bilden laesst, auf den
Bildschirm kommen sie nicht.

**Der Exponent auf den Streckenfaktor.** Der rohe Faktor aus GDD 3
spannt ueber die zwanzig Strecken von 1,263 (Zandvoort) bis 0,537
(Monza) - das 2,35fache. So weit auseinander lassen sich die Stoppzahlen
nicht mehr einfangen: Monza kaeme mit einem Stopp aus und braeuchte nie
einen zweiten, Zandvoort schaffte keinen Zwei-Stopp mehr. Auf den
**Verschleiss** wirkt deshalb `streckenfaktor ^ 0,5`:

| Exponent | Zandvoort | Monza | Spanne | Zandvoort | Monza |
| ---: | ---: | ---: | ---: | --- | --- |
| 1,0 | 1,263 | 0,537 | 2,35 | 2-4 Stopps | 0-1 |
| 0,7 | 1,178 | 0,647 | 1,82 | 2-4 | 1-2 |
| **0,5** | **1,124** | **0,733** | **1,53** | **2-3** | **1-2** |
| 0,4 | 1,098 | 0,780 | 1,41 | 1-4 | 1-2 |

Der Exponent wirkt **nur auf den Verschleiss**, nicht auf den Faktor
selbst: Die Anzeige und `weich_hoechstens_streckenfaktor` vergleichen
weiter gegen den rohen Wert - sonst faellt die Weich-Regel auf allen
zwanzig Strecken weg, weil keine mehr ueber 1,15 kaeme.

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
haerteren Mischungen haben die Stoppzahl sichtbar gesenkt. Gemessen
wurde das damals ueber 100 Strecke-Liga-Kombinationen: Zwei-Stopp-
Strategien stiegen von 10 auf 23, und ohne die Drei-Stopp-Grenze waeren
vorher 4 bis 6 Stopps in 76 Faellen optimal gewesen, danach 2 bis 3 in
79. Fuenf oder mehr kommen gar nicht mehr vor.

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
im Abstieg. Runden bis 80 / 50 / 30 / 0 Prozent, bestes Auto des Feldes,
trocken:

```
                      Monza (0,54)   Nuerburgring (1,07)   Zandvoort (1,26)
  Weich               7/ 18/ 25/ 36       5/ 14/ 20/ 29       6/ 15/ 22/ 31
  Mittel             10/ 25/ 36/ 51       8/ 20/ 29/ 41       9/ 22/ 32/ 45
  Hart               14/ 35/ 50/ 71      11/ 28/ 40/ 57      12/ 31/ 44/ 63
  Intermediate        9/ 23/ 33/ 47       7/ 18/ 26/ 37       8/ 20/ 29/ 41
  Regen              11/ 27/ 38/ 54       8/ 21/ 29/ 42       9/ 23/ 33/ 47
```

**Die Nassreifen halten seit Punkt 100 wie ein Mittel** (Intermediate
0,73, Regen 0,64). Davor standen sie bei 1,10 und 0,90 - der
Intermediate war damit der **kurzlebigste Reifen im ganzen Satz**,
kurzlebiger noch als Weich. Das fiel bei den schwachen Autos auf: Aus
einem Satz Mittel kamen 20 Runden, aus einem Intermediate nur 12 - bei
derselben vollen Distanz. Im Nassen brauchten sie dadurch bis zu
**fuenf** Stopps, wo der Planer nur drei vergeben darf; der Rest kam als
Zwangsstopp. Gemessen ueber alle 20 Strecken sind es jetzt hoechstens
drei. Der Preis steht daneben und war eine Entscheidung des
Auftraggebers: Die Spitze faehrt ein nasses Rennen jetzt mit einem Stopp
statt mit zweien.

**Kein Stint faellt unter 30 Prozent Restprofil**, auch der letzte nicht -
und auch nicht, nachdem das Zufallsfenster die Stopprunden verschoben hat.
Das war lange anders: Die Vorausberechnung hielt die Regel ein, das
Fenster hebelte sie wieder aus. In Zandvoort kamen so 23 von damals 30
Autos darunter, eines mit 9 Prozent ins Ziel.

### Die Strecke gummiert ein

Je mehr auf einer trockenen Strecke gefahren wird, desto mehr Gummi
liegt auf der Ideallinie und desto mehr Grip gibt sie her. Regen waescht
das wieder ab; sobald es trocknet, baut es sich von neuem auf.

Eine einzige Zahl traegt das: der **Stand** zaehlt gefahrene
**Auto-Runden**. Jede Runde, die ein Auto auf dieser Strecke in dieser
Session dreht, aendert ihn um den Beitrag der herrschenden Lage:

| Lage | je Auto-Runde |
| --- | ---: |
| trocken, heiss | +1,0 |
| wechselhaft | −0,05 |
| regen | −1,5 |
| starkregen | −3,0 |

Unter null faellt er nie. Aus dem Stand wird der Grip-Aufschlag:

    faktor(n) = 1 + max_anteil * (1 - e^(-n / halbwert_runden))

Viel am Anfang, immer weniger, je mehr schon liegt. Mit `max_anteil =
0,015` und `halbwert_runden = 500`:

| | Auto-Runden | Aufschlag | Zandvoort |
| --- | ---: | ---: | ---: |
| Qualifying, erster Starter | 0 | 0,00 % | — |
| Qualifying, letzter Starter | 58 | 0,16 % | −0,14 s |
| Rennen, nach 10 Runden | 300 | 0,68 % | −0,57 s |
| Rennen, nach 40 Runden | 1.200 | 1,36 % | −1,15 s |

#### Was die Reifenart damit zu tun hat

Weiche Reifen tragen **mehr Gummi auf** und holen auch **mehr daraus
heraus**. Beides kommt aus derselben Eigenschaft - wie weich der Reifen
ist -, und die steht schon als `verschleiss` in `[reifen.mischungen]`.
Es braucht deshalb keine zweite Tabelle, nur einen Bezug und einen
Exponenten:

    Auftrag    =  verschleiss / verschleiss(Mittel)
    Ansprechen = (verschleiss / verschleiss(Mittel)) ^ 0,5

| | `verschleiss` | Auftrag | Ansprechen |
| --- | ---: | ---: | ---: |
| Weich | 1,05 | 1,44 | 1,20 |
| Mittel | 0,73 | 1,00 | 1,00 |
| Hart | 0,53 | 0,73 | 0,85 |

Der **Auftrag** ist linear: Gummi auf der Strecke *ist* abgefahrener
Reifen, was 1,44-mal so schnell abbaut, laesst 1,44-mal so viel liegen.
Das **Ansprechen** ist gedaempft - dass sich ein weicher Reifen besser
in den liegenden Gummi einarbeitet, ist der schwaechere Zusammenhang.
Ein Exponent statt fuenf erfundener Zahlen, und genau eine Stellschraube.

Der Auftrag gilt **nur beim Aufbau**. Abgewaschen wird vom Regen, nicht
vom Reifen; ein Intermediate darf nicht staerker
abwaschen als ein Regenreifen.

Gemessen in Zandvoort, reine Physik:

| Stand | Gummi | Weich | Mittel | Hart | W−H |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 300 | 0,68 % | −0,68 s | −0,57 s | −0,49 s | 0,20 s |
| 600 | 1,05 % | −1,05 s | −0,88 s | −0,75 s | 0,30 s |
| 1.200 | 1,36 % | −1,37 s | −1,14 s | −0,98 s | 0,39 s |

Zum Vergleich: Weich ist an sich **1,70 s** schneller als Hart
(Zandvoort, frischer Satz). Der Gummi-Unterschied erreicht damit rund
**23 %** davon - spuerbar, aber er stellt die Mischungswahl nicht auf
den Kopf. Bei Exponent 1,0 waeren es 53 %, und ein spaeter weicher
Stint waere fast erzwungen.

**Den Grip kennt die Strategie nicht.** `strategie.py` plant Stints aus
Verschleiss und Mischungstempo; den Gummi-Aufschlag kennt sie nicht.
Weich wird damit spaet im Rennen relativ besser, ohne dass die Planung
es einrechnet - die KI schoepft es nicht aus, und wer es bemerkt, hat
einen Vorteil. So gewollt (Entscheidung des Auftraggebers).

#### Die gruene Strecke frisst Reifen

Rauer Asphalt schmirgelt, eingegummierter Asphalt traegt. Derselbe
Stand, der den Grip hebt, senkt also auch den Verschleiss - ueber
dieselbe Kurve, nur von `verschleiss_gruen` nach `verschleiss_voll`:

    Verschleissfaktor(n) = 1,15 + (0,928 - 1,15) * (1 - e^(-n / 500))

| Auto-Runden | Faktor | Ein 20-Runden-Stint waere |
| ---: | ---: | ---: |
| 0 (gruen) | 1,150 | 17 Runden |
| 200 | 1,077 | 19 Runden |
| 500 | 1,010 | 20 Runden |
| 900 | 0,965 | 21 Runden |
| 1.800 (Rennende) | 0,934 | 21 Runden |

**Umverteilung, nicht mehr Verschleiss.** Die beiden Zahlen sind so
gewaehlt, dass ein volles Rennen ueber alles gerechnet ungefaehr dort
herauskommt, wo es vorher lag; der Verschleiss wandert nur vom Ende an
den Anfang. Das Verhaeltnis 1,15 zu 0,928 ist 1,24 - der erste Stint
faellt rund ein Fuenftel kuerzer aus als der letzte.

**Ohne Mischung.** Wie stark der Asphalt schmirgelt, ist eine
Eigenschaft der Strecke, nicht des Reifens; anders als beim Auftrag und
beim Ansprechen steht hier kein Mischungsfaktor.

**Das** kennt die Strategie sehr wohl (Entscheidung des Auftraggebers):
Der Planer rechnet mit dem Verschleissfaktor je Runde, weil er sonst
den ersten Stint zu lang ansetzt. Den wachsenden Grip rechnet er
weiterhin nicht mit.

Damit ist auch die **Reihenfolge der Mischungen** keine freie Wahl mehr.
Frueher galt: Ein Stint kostet, was er kostet, egal ob er der erste oder
der letzte ist - dann genuegte eine Rechnung je Zusammenstellung, und
die Reihenfolgen erbten sie. Jetzt ist ein weicher Satz auf gruenem
Asphalt etwas anderes als derselbe Satz auf eingegummiertem, und jede
Reihenfolge wird einzeln gerechnet.

#### Was das Rennen sonst noch zeigt (Punkt 93)

* **Alter, Reicht, Stopp** neben dem Reifenbalken. Der Balken sagt
  "wieviel", nicht "wie lange" (B35) und nicht "wie lange noch" (B36):
  *Alter* zaehlt die Runden auf dem Satz, *Reicht* rechnet hoch, wie
  viele noch bis zur Zwangsstopp-Grenze bleiben - aus dem, was schon
  passiert ist, also mit dem Verschleiss, den dieses Auto an diesem Tag
  wirklich hat. *Stopp* nennt die Runde, in der der Plan hereinkommen
  will (B32); was das Rennen daraus macht, ist die Geschichte des
  Rennens.
* **Der Ticker traegt je Art ein Zeichen** (B49) - Warndreieck, Kreuz,
  Zahnrad. Zwoelf Zeilen Fliesstext sehen alle gleich aus; ein Zeichen
  am Zeilenanfang laesst sich im Vorbeischauen zaehlen. Wer ausfaellt,
  bekommt dasselbe Zeichen in Rot: Der Ausfall ist keine vierte Art,
  sondern das Ende einer der drei.
* **Das Wetterband** unter der Wiedergabeleiste (B43), dasselbe Widget
  wie im Qualifying.
* **Die Boxenbilanz** als eigenes Blatt (B53): Stopps, Standzeit,
  Gesamtverlust und der Abstand zum Feld. Der Verlust wird **gemessen,
  nicht gerechnet** - die Runde mit Stopp gegen die Medianrunde
  desselben Autos. Eine Formel aus Boxengassenlaenge und Standzeit
  kennt davon nur die Haelfte.
* **Der Kompaktmodus** (B59): nur die Rangliste, grosse Schrift, fuers
  reine Zusehen. Karte, Diagramm und das rechte Blatt fallen weg - und
  genau die kosten den Loewenanteil der Zeit je Bild (siehe D1 bis D10),
  also ist es nebenbei der schnellste Modus ueberhaupt.

#### Warum ein Prozent Grip eine Sekunde ist

Der Grip streckt das **ganze Geschwindigkeitsprofil** um genau seinen
Faktor (siehe "Warum der Grip quadratisch angesetzt wird" - das Quadrat
auf den Beschleunigungen ist gerade das, was die Geschwindigkeit linear
macht). Ein Prozent Grip ist damit ein Prozent Tempo und
`1 - 1/1,01 = 0,99 %` Rundenzeit.

In Sekunden haengt das an der Rundenlaenge. Gemessen mit dem besten Auto
des Feldes sind +1,0 % Grip:

| | Rundenzeit | −1 % |
| --- | ---: | ---: |
| Zandvoort | 1:24,8 | −0,84 s |
| Sakhir | 1:36,0 | −0,95 s |
| Spa | 1:54,3 | −1,13 s |

Weil eine Runde rund anderthalb Minuten dauert, ist **ein Prozent Grip
ungefaehr eine Sekunde** - eine brauchbare Faustregel, um die Mechanik
in Sekunden einzustellen statt in Prozent.

#### Warum Auto-Runden und nicht Zeit

Dreissig Autos gummieren schneller ein als eines. Im Rennen geht es
damit von selbst schneller als im Qualifying, ohne dass irgendwo eine
zweite Zahl noetig waere - und es bleibt ueber den Seed reproduzierbar,
weil kein Wurf mitspielt.

#### Warum der Aufschlag nach `grip_fuer` wirkt

Vor `wetter.grip_fuer` waere er falsch: Dort daempft die
Wetterfaehigkeit die Abweichung von 1,0, und ein Regenspezialist
bekaeme vom Gummi weniger ab als ein anderer. Gummi auf der Strecke ist
aber keine Fahrkunst. Ausserdem hat `grip_fuer` bei genau 1,0 einen
Sprung - dort schaltet der Trockenbonus zu -, und "heiss" (Grip 0,97)
liefe mit wachsendem Gummi genau hinein.

#### Was das fuer das Qualifying bedeutet

Die Startreihenfolge ist der umgekehrte Meisterschaftsstand (GDD 4) -
wer vorn liegt, faehrt zuletzt und findet die gummiertere Strecke vor.
Bei den Werten oben sind das **0,14 s** zwischen erstem und letztem
Starter: spuerbar, aber nicht entscheidend. Zwischen Qualifying und
Rennen ueberlebt **nichts**; jede Session faengt gruen an (Entscheidung
des Auftraggebers).

Der Anker aus GDD 9 bleibt gruen: Die Kalibrierung rechnet eine
einzelne Runde ohne Wetter und ohne Verkehr, dort ist der Stand null und
der Faktor genau 1,0. Zandvoort bei S=98.000 steht weiter auf
180,00 km/h. Auch ein Rennen ohne Wetterverlauf bleibt gruen - das ist
der Laborfall fuer Kalibrierung und Tests; im Spiel hat jedes Rennen ein
Wetter.

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
faehrt fuenf Rennen und schreibt je Fahrer auf, auf welcher
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

## Der Spieler fuehrt zwei Autos

Das GDD kannte einen Spielerfahrer, die Abstimmung machte daraus einen
Teamchef mit vier Autos in zehn Ligen. **Punkt 101 hat das wieder
eingedampft:** Der Spieler fuehrt ein Team wie jedes andere, also
**zwei Autos** im einen Feld. Sie stehen dort, wo die Leiter sie hinstellt
- kein Startplatz ganz unten, kein Aufstieg nach oben.

Damit ist auch alles weg, was am Aufstieg hing:

* **Kein Geld.** Kein Konto, kein Kassenbuch, keine Sponsoren, kein
  Preisgeld, keine Werkstattkosten, keine Gehaelter.
* **Keine Erfahrung und keine Entwicklung.** Die Werte eines Fahrers
  stehen bei der Welterzeugung fest und bleiben. Es gibt keine
  Potentiale mehr, weil es nichts gibt, worauf sie hinwachsen koennten.
* **Kein Transfermarkt und keine Generationen.** Niemand wechselt das
  Team, niemand altert, niemand tritt zurueck, niemand kommt nach.
* **Kein Auf- und Abstieg.** Es gibt nur ein Feld.

Was bleibt, ist die Saison: Kalender, Rennwochenende, Qualifying,
Rennen, Tabelle, Statistik, Spielstand - und der Editor, mit dem sich
jeder Fahrer aendern laesst.

### Was von der Karriere uebrig ist

`rennmanager.kern.karriere` fuehrt seit Punkt 101 nur noch den
**Kalender**: welcher Tag heute ist, wann das naechste Rennen ist, wie
viele Tage dazwischen liegen. Die Tage lassen sich weiterschalten, aber
sie kosten nichts und bringen nichts - es gibt keine Trainingsprogramme,
keine Upgrades und keine belegten Plaetze mehr.

## Die Welt

`rennmanager.kern.welt` erzeugt aus einem Seed alles, was eine Saison
braucht (GDD 12):

```python
from rennmanager.kern import welt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
w = welt.erzeuge(k, Seedquelle(4711))
len(w.fahrer)                 # 50 in einem Feld
len(w.teams)                  # 25 mit je 2 Autos eines Herstellers
w.feld                        # dasselbe Feld, staerkster zuerst
w.spielerfahrer               # die 2 Autos des Spielers
w.teamkollegen(w.spieler)     # sein zweiter Fahrer
feld = welt.starterfeld(w)
```

**Die Leiter.** `welt.feldstaerken(k)` legt die 50 Staerken gleichmaessig
zwischen `feld.s_bester` (98.000) und `feld.s_letzter` (87.445). Die
Teams werden dann **paarweise** auf die Leiter gewuerfelt: Die zwei Autos
eines Teams stehen nebeneinander, das Team selbst irgendwo. Jedes Auto
bekommt trotzdem sein eigenes Profil, zwei Teamkollegen sind also nicht
gleich schnell - nur gleich gut ausgestattet.

**Die Teamfarbe ist die Herstellerfarbe** (Punkt 101): 25 Teams, 25
Hersteller, eine Farbe je Paar. Beide Autos eines Teams tragen dieselbe.

### Warum der Letzte bei 87.445 steht

Der Auftraggeber hat **vier Prozent Rundenzeit** als Spanne des ganzen
Feldes vorgegeben, und den Tempoanker bei 180 km/h auf Zandvoort
gelassen. Beides zusammen bestimmt `s_letzter` eindeutig.

Jede Grenze des Geschwindigkeitsmodells ist linear in
`p = sqrt(S / referenz)`, die Rundenzeit also genau umgekehrt
proportional dazu. Vier Prozent mehr Zeit heissen damit vier Prozent
weniger Tempo:

```
v_letzter  = 180 / 1,04            = 173,077 km/h
p_letzter  = (173,077 - 55) / 125  = 0,944615
s_letzter  = 0,944615^2 * 98.000   = 87.445
```

Nachgemessen: S = 87.445 faehrt auf Zandvoort 1:28.282 gegen 1:24.887,
also +3,9994 Prozent. `--pruefe` rechnet das bei jedem Start nach und
meldet `Rundenzeitspanne +4.00%`.

### Warum es zwei Streuungsebenen gibt

GDD 12 laesst die Einzelwerte "+/- 25 % um den Mittelwert" streuen und
nennt als Ziel Regenspezialisten, Qualifying-Experten und Reifenschoner.
Davon kam fast nichts an: Gefahren wird mit den **Bereichsmitteln** aus
GDD 8, und ueber drei bis fuenf Einzelwerte mittelt sich die Streuung
weg - zwischen dem staerksten und dem schwaechsten Bereich eines Fahrers
lagen gemessen nur 20 %.

Deshalb wird zusaetzlich je Fahrer ein Faktor pro Wirkungsbereich
gezogen, den jede Faehigkeit nach ihrer Zeile der Wirkungsmatrix
gewichtet erbt. Die Wetterfaehigkeiten stehen neben der Matrix und
streuen fuer sich.

Die Faktoren sind auf den Mittelwert 1 normiert, und was das Kappen an
der Skala wegnimmt, wird zurueckgeholt. Ein Spezialist verteilt seine
Staerke also um, statt mehr oder weniger davon zu haben.

**Punkt 101 hat beide Ebenen klein gemacht.** Mit +/- 25 % auf die
Einzelwerte und +/- 30 % auf die Bereiche lag das Rauschen um ein
Vielfaches ueber der Leiter selbst - die vier Prozent Feldspanne waeren
darin untergegangen und die Reihenfolge waere reiner Zufall gewesen.
Jetzt sind es 3 % und 3,5 % (`[ki] profil_streuung`,
`bereichs_streuung`).

Gemessen ueber ein volles Feld (Seed 2026):

```
reine Leiter, ohne Rauschen   Zandvoort 1:24.887 .. 1:28.282   Spanne 4,00 %
mit Rauschen  Zandvoort       1:24.562 .. 1:28.509   Spanne 4,67 %
              Monza           1:24.065 .. 1:28.030   Spanne 4,72 %
              Norisring         0:41.527 .. 0:43.403   Spanne 4,52 %
```

Und die Leiter bleibt erkennbar: Von der Staerke zur trockenen
Rundenzeit verschiebt sich ein Fahrer im Mittel um **2,1 Plaetze**,
hoechstens um 8. Ueber eine ganze Saison (20 Rennen, Seed 2026) sind es
im Mittel 2,5 Plaetze und hoechstens 6 - genug, dass das Rennen
entscheidet, und wenig genug, dass Staerke sich auszahlt.

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
Sechs Reiter:

| Reiter | Was darin steht |
| --- | --- |
| Steckbrief | Person, Team, Teamkollege, Staerke und Platz im Feld, Popularitaet, der Charaktersatz mit Staerken und Schwaechen einzeln |
| Werte | die 11 Wirkungsbereiche aus GDD 8 als Balken, dann alle 32 Einzelwerte und die 11 Eigenschaften neben der Matrix |
| Saison | die Zeile der laufenden Saison und der Punkteverlauf des Feldes, in dem nur dieser Fahrer farbig ist |
| Laufbahn | Karrierezahlen ueber alle Saisons, Meisterschaften, Platz je Jahr als Linie, gehaltene Rundenrekorde |
| Strecken | Streckenkenntnis je Strecke mit Tempogewinn; Heimstrecken hervorgehoben (Punkt 49) |
| Wetter | die Wetterbilanz und die Faehigkeit zu jeder Lage (Punkt 23) |

Sie **rechnet nichts**: Gelesen wird nur, was Welt, Auto, Statistik,
Streckenkenntnis und Popularitaet ohnehin fuehren, und sie ist rein
lesend - Werte aendern geht weiter nur ueber den Editor. Fuer alle 50
Fahrer zeigt sie dasselbe, den Spieler eingeschlossen.

#### Die Fahrersuche

Ueber allen Reitern steht ein Suchfeld (Punkt 18, **Strg+F**). Name
tippen, Eingabetaste, die Fahrerkarte geht auf. Gesucht wird ueber die
ganze Zeile - Name, Kuerzel und Team -, deshalb findet "Rosskamp" auch
die beiden Fahrer dieses Teams. **Fahrertreffer stehen vorn:** Wer einen
Namen tippt, meint den Fahrer und nicht dessen Teamkollegen.

#### Warum die Balken gegen den eigenen Hoechstwert messen

Die Skala reicht von 0 bis 100.000, das Feld steht seit Punkt 101 dicht
gedraengt zwischen 87.445 und 98.000. Gegen die Skala waeren die Balken
kaum zu unterscheiden. Zu sehen ist hier
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
Auch ein Fahrer am unteren Ende des Feldes hat ein Profil. Genannt werden
hoechstens zwei Staerken und zwei Schwaechen, und nur ab 6 % Abweichung.
Seit Punkt 101 streuen die Einzelwerte nur noch um drei Prozent - wer
kein ausgepraegtes Profil hat, liest "Ausgeglichen, ohne ausgepraegte
Staerken oder Schwaechen".

## Kalender und Zeitmodell

`rennmanager.kern.kalender` baut die Saison (GDD 2): Das erste Rennen ist
der erste Sonntag ab dem 1. Maerz, danach alle 14 Tage, das zwanzigste
266 Tage spaeter. Jeder Zyklus hat genau 10 nutzbare Tage; die uebrigen
vier sind zwei Reisetage, der Qualifying-Samstag und der Renn-Sonntag.

Seit Punkt 101 ist der Kalender **nur noch Kalender**: Er sagt, welcher
Tag heute ist und wann das naechste Rennen faellt. Belegte Tage,
Trainingsprogramme, Upgrades und Kosten gibt es nicht mehr - die Werte
eines Fahrers stehen fest.

```python
from rennmanager.kern import karriere
from rennmanager.konfiguration import lade

k = lade()
c = karriere.beginne(k, 2026)
c.tag                       # heute
c.naechstes_rennen          # Nummer des naechsten Rennens
c.tage_bis_zum_rennen       # wie viele Tage noch
c.tag_weiter()              # einen Tag vor
c.bis_zum_rennen()          # bis zum naechsten Renntag
```

### Das Jahr als Band

Die Saisonseite zeigt das Jahr als Band aus Tagesstreifen, eine Spalte je
Woche: Renntag, Qualifying, Reise, freier Tag. Ein Mouseover nennt Datum
und Zustand.

## Die Saison

`rennmanager.kern.saison` faehrt die 20 Rennwochenenden aus GDD 2 und
fuehrt **eine** Tabelle (GDD 13):

```python
from rennmanager.kern import saison, strecke, welt
from rennmanager.kern.zufall import Seedquelle
from rennmanager.konfiguration import lade

k = lade()
haupt = Seedquelle(4711)
w = welt.erzeuge(k, haupt.zweig("welt"))
lauf = saison.Saisonlauf(k, w, haupt, jahr=2026, strecken=strecke.lade_alle(k))

wochenende = lauf.fahre_rennen(ausfuehrlich=True)
wochenende.verlauf               # abspielbares Rennen
wochenende.ergebnisse            # die Wertung aller 50
lauf.tabelle.stand()[0]          # Tabellenfuehrer

lauf.fahre_saison()              # die restlichen 19 Wochenenden
naechste = lauf.naechste_saison()  # schliesst ab und beginnt das Folgejahr
```

### Die Punkteleiter

Seit Punkt 101 steht die Tabelle fest in `[wertung] punkte_je_platz`,
eine Zahl je Platz, vom Auftraggeber so vorgegeben:

```
Platz     1   2   3   4   5   6   7  ...  30  31 | 32  33  ...  49  50
Punkte  100  90  80  76  72  70  68  ...  22  20 | 19  18  ...   2   1
```

Also 100, 90, 80, dann 76 und 72, ab Platz 5 in Zweierschritten bis 20
auf Platz 31, danach in Einerschritten bis 1 auf Platz 50.

**Jeder Platz bekommt Punkte**, auch der Fuenfzigste und auch wer
ausgefallen ist: Er wird nach absolvierten Runden und dann nach der Zeit
einsortiert und bekommt die Punkte fuer diesen Platz. Bei Gleichstand
entscheiden die besseren Platzierungen - mehr Siege, dann mehr zweite
Plaetze und so weiter.

**Zusatzpunkte gehen als Anteil auf die Siegerpunkte:**

| | Anteil | Punkte |
| --- | ---: | ---: |
| schnellste Runde | 1,0 % | 1 |
| Pole | 1,5 % | 2 |
| Qualifying P2 | 0,5 % | 1 |
| Qualifying P3 | 0,25 % | 1 |

Gerundet wird **auf**, und es ist immer mindestens ein Punkt. Ein
perfektes Wochenende - Pole und Sieg mit schnellster Runde - bringt
damit 103 Punkte.

Gemessen ueber eine volle Saison (20 Rennen, Seed 2026): Der Meister kam
auf 1709 Punkte mit 8 Siegen, der Letzte auf 133. In den 20 Rennen gab
es **5 verschiedene Sieger**.

### Was am Saisonende passiert

Nichts ausser dem Abschluss: Die Tabelle wandert in die Historie, die
Statistik behaelt Rekorde und Karrierezahlen, das Feld bleibt, wie es
ist. Es gibt keinen Auf- und Abstieg mehr, keine Transferzeit und keinen
Winterschritt - die Fahrer sind fest (Punkt 101).

Was die Saison ueberdauert, wandert unveraendert mit: Statistik,
Streckenkenntnis und Popularitaet. Neu sind nur Tabelle und Kalender.

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

Die Zaehlweise war noetig, weil die beiden Rennmodelle die Zahl sonst
verschieden messen. Gemessen ueber ein Rennen in Zandvoort (69 Runden
ueber die volle Distanz, 40 Autos, vor Punkt 101):

| Zaehlweise | Manoever | je Auto |
| --- | --- | --- |
| jeder Vorbeigang (``Rennverlauf.manoever``) | 655 | 16,4 |
| Positionsgewinne je Runde | 397 | 9,9 |
| Schnellmodus | 122 | 3,0 |

Der Rest des Unterschieds kommt daher, dass der Schnellmodus je Runde nur
*einen* Ueberholversuch zulaesst, die volle Simulation dagegen an jeder
Ueberholzone einen - das ist ein Unterschied in der Verkehrsdynamik, nicht
in der Zaehlweise.

Jeder einzelne Vorbeigang steht weiter in ``Rennverlauf.manoever`` und ist
fuer die Anzeige des Rennens da, nicht fuer die Wertung.

Kalender und Rennwochenende haengen dabei zusammen (GDD 2): Ein Rennen
findet an seinem Renntag statt. `fahre_rennen()` schaltet den Kalender der
Karriere bis dorthin vor und danach einen Tag darueber hinaus.

Wie die Punkte fallen, steht oben unter *Die Punkteleiter*.

### Der Saisonwechsel

`naechste_saison()` macht aus dem Saisonende den Anfang des naechsten
Jahres. Die Karriere ist endlos; dieselben 50 Fahrer bleiben, es gibt
keine Zu- und Abgaenge.

```python
neu = lauf.naechste_saison()   # schliesst ab und zaehlt das Jahr hoch
neu.jahr                       # 2027
neu.statistik.abschluss(2026).zeilen[0]
# Saisonzeile(fahrer=7, platz=1, punkte=1709, siege=8, podien=15,
#             poles=6, schnellste_runden=5, ausfaelle=1, rennen=20)
```

| Wandert mit | Beginnt neu |
| --- | --- |
| Statistik: Rundenrekorde, Karrierezahlen, Historie | die Saisontabelle |
| Streckenkenntnis aller 50 Fahrer (GDD 6) | der Kalender (GDD 2) |
| Popularitaet aller 50 Fahrer (Punkt 5) | |

Die Historie traegt dabei jede Saison **vollstaendig**: Platz, Punkte,
Siege, Podien, Poles, schnellste Runden, Ausfaelle und Rennen je Fahrer.
Die Tabelle der Saison wird geleert - was dann nicht in der Historie
steht, ist fort.

**Das Feld bleibt dasselbe.** Seit Punkt 101 altert niemand, entwickelt
sich niemand und wechselt niemand das Team; die Reihenfolge der Leiter
steht in Saison 30 wie in Saison 1.

### Der Punkteverlauf der laufenden Saison

Die Statistik fuehrt neben dem Endstand den Weg dorthin: `punktestand`
liefert den aufsummierten Stand eines Fahrers Rennen fuer Rennen.

```python
lauf.statistik.gefahrene_rennen()       # (1, 2, 3)
lauf.statistik.punktestand(401)         # (0, 262, 516) - aufsummiert
```

Der Verlauf gehoert dem Fahrer.

Die Saisonseite zeichnet daraus ein Liniendiagramm unter der Tabelle: Man
sieht, wann eine Meisterschaft entschieden war und wann sie kippte. Es
gilt dieselbe Regel wie beim Rueckstandsdiagramm - das Feld liegt grau im
Hintergrund, hervorgehoben und am Linienende beschriftet sind nur der
Spieler und der in der Tabelle gewaehlte Fahrer.

Beim Saisonwechsel wird der Verlauf geleert; der Endstand steht dann in
der Historie. Er liegt im Spielstand in der Tabelle `saisonverlauf`.

### Warum es zwei Rennmodelle gibt

Ein Rennen ueber die volle Distanz kostet mit `rennmanager.kern.rennen`
37 bis 47 Sekunden - fuer eine Saison im Schnelldurchlauf zu viel.
`rennmanager.kern.schnellsimulation` bildet je Runde eine Rundenzeit statt
50-Millisekunden-Schritte: Gemessen braucht ein Rennen damit 1,4 Sekunden
und eine ganze Saison aus 20 Rennen 29. Im gefuehrten Wochenende faehrt
der Spieler sein Rennen voll und sieht zu; wer die Saison durchlaufen
lassen will, nimmt den Schnellmodus. Wetter, Fehler, Unfaelle, Defekte und
Reifenverschleiss sind dabei dieselben Bausteine wie in der vollen
Simulation.

Verkehr entsteht ueber die Reihenfolge: Wo sich die Reihenfolge gegenueber
der Vorrunde geaendert hat, ist ueberholt worden - und das gelingt nur mit
einem Wurf nach GDD 4. Bei gleichem Wetter in beiden Modellen weicht die
Siegerzeit um weniger als 1,3 % ab, die schnellste Runde um weniger als
1,4 %; ein Test haelt eine 2-%-Schranke fest. Ohne diesen Abgleich waeren
die Rundenrekorde eines voll gefahrenen Rennens nicht mit denen eines
schnell gefahrenen vergleichbar.

Ob ein Rennen ausfuehrlich oder schnell faehrt, aendert an den uebrigen
nichts: Jedes wuerfelt aus seinem eigenen Zweig
`saison/<jahr>/rennen/<nummer>`.

## Defekte

`rennmanager.kern.zwischenfall` wuerfelt Fehler, Unfaelle und Defekte
(GDD 6). Ein Defekt trifft eine einzelne Faehigkeit und kostet sie einen
Anteil ihres Wertes - fuer **dieses eine Rennen**.

Punkt 101 hat die Reparatur abgeschafft: Es gibt kein Geld mehr, mit dem
sich ein Defekt bezahlen liesse, und ein dauerhafter Malus ohne Ausweg
waere eine Einbahnstrasse. `[defekte] malus_bleibt = false` haelt das
fest - nach dem Zielstrich ist der Wagen wieder heil.

**Ereignisse (GDD 14) gibt es nicht mehr.** Jedes der 30 hing an Geld,
Erfahrung, Kaufsperren oder dauerhafter Entwicklung; ohne diese vier
bleibt nichts uebrig, worauf ein Ereignis wirken koennte.

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
| **Popularitaet** | Bekanntheit eines Fahrers, waechst mit Siegen und Podien | `kern.popularitaet` |
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

`rennmanager.kern.streckenkenntnis` setzt GDD 6 um: Ein Kenntniswert je
Paar aus Fahrer und Strecke gibt bis zu 1,5 % Tempo, voll nach etwa 1.000
Runden. Die Simulation bekommt ihn als fertigen Tempofaktor.

**Seit Punkt 101 waechst er nicht mehr.** Er wird einmal bei der
Welterzeugung gewuerfelt - im Mittel 35 % der vollen Kenntnis, breit
gestreut (`[streckenkenntnis.anfang]`) - und bleibt dann stehen. Das gilt
fuer alle 50 Fahrer, den Spieler eingeschlossen: Er faengt nicht mehr bei
null an und holt auch niemanden mehr ein. Liefe die Kenntnis weiter,
liefe das Feld ueber die Saisons dem Anker aus GDD 9 davon.

Jeder Fahrer kennt sich dabei nicht ueberall gleich gut aus - gewuerfelt
wird je Paar, nicht je Fahrer. Zwei Strecken derselben Saison trennen
damit das Feld verschieden.

## Statistik und Spielstand

`rennmanager.kern.statistik` fuehrt, was die Saison ueberdauert (GDD 13):

```python
statistik.rekord("Monza")               # schnellste Runde in Tausendsteln
statistik.qualirekord("Monza")          # und die schnellste Qualirunde
statistik.bestenliste("siege")          # Karrierezahlen aller Fahrer
statistik.laufbahn(fahrer)              # je Saison das Jahr und der Platz
statistik.punkte_in(2026, fahrer)       # Gesamtpunkte einer Saison
```

`rennmanager.kern.spielstand` schreibt alles in eine SQLite-Datei, wie
GDD 15 es vorgibt - eine Datei je Spielstand, im Menue unter Datei. Jede
Verbindung wird dabei ausdruecklich geschlossen: `with sqlite3.connect(...)`
committet nur, es schliesst *nicht*. Unter Linux faellt das nicht auf -
eine offene Datei laesst sich dort loeschen. Unter Windows nicht, und dann
ueberschreibt der naechste Autosave den alten Stand nicht mehr. Ein Test
zaehlt die Verbindungen selbst mit, statt sich aufs Betriebssystem zu
verlassen. Die Welt wird dabei vollstaendig abgelegt statt aus dem Seed neu
gewuerfelt: Sobald jemand den Editor benutzt hat, stimmt die gewuerfelte
Welt nicht mehr mit der gespielten ueberein. Ein Test haelt genau das
fest.

Der Stand traegt seine **Version**; die aktuelle ist **12** mit 18
Tabellen. Sie ist zugleich die **aelteste lesbare**: Punkt 101 hat
Weltgroesse, Punktesystem, Karriere und Wertung so veraendert, dass ein
alter Stand nicht mehr zu retten war. Ein Stand vor Version 12 wird
deshalb abgewiesen, mit einer Meldung, die den Grund nennt, statt still
falsche Zahlen zu zeigen; ein Test haelt beides fest. Umgerechnet wird
nichts - so hat es der Auftraggeber entschieden.

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
Ausfaelle, Punkte und das beste Ergebnis.

Zu sehen ist beides an zwei Stellen: in der Fahrerkarte (die
Streckenbilanz im Reiter *Strecken* neben der Streckenkenntnis, die
Wetterbilanz als eigener Reiter neben der Faehigkeit zu jeder Lage) und
auf der Statistikseite als Vergleich ueber alle 50 Fahrer.

#### Warum Summen und keine Rennliste

50 Fahrer mal 20 Rennen mal zwanzig Saisons waeren 20.000 Zeilen, und der
Spielstand wuechse endlos weiter. Als Summe bleiben es 1.000 Zeilen je
Strecke und 250 je Wetterlage - gleich viele nach der ersten Saison wie
nach der zwanzigsten. Ein Test haelt genau das fest: Vier Rennen auf vier
Strecken ergeben vier Zeilen je Fahrer, nicht acht.

Aufgehoben werden nur die Summen: Die einzelnen Rennen von damals stehen
nirgends, eine Bilanz laesst sich also nicht nachtraeglich bilden.

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

Seit Punkt 101 gibt es nur noch **eine** Ansicht: Es gibt nur ein Feld,
also auch nur eine Bestenliste. Je Strecke stehen Renn- und Qualirekord
nebeneinander, darunter die vollstaendige Liste aller Saisons.

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

Daran sieht man, was die Streuung anrichtet: Von der reinen
Staerkereihenfolge zur Rundenzeit verschiebt sich ein Fahrer im Mittel um
2,1 Plaetze, hoechstens um 8 - und zwischen zwei Strecken sieht die
Reihenfolge wieder anders aus.

Das Team bleibt aussen vor: Ein Wechsel dort spraenge die Teamgroessen
aus GDD 12.

```python
from rennmanager.kern import welt

neu = welt.mit_fahrerwerten(w, {17: (werte, wetterwerte)})
neu = welt.mit_fahrerdaten(neu, {17: {"vorname": "Ada", "nachname": "Lovelace"}})
```

### Wo die Werte des Spielers stehen

In der Welt, wie bei jedem anderen. Bis Punkt 101 fuehrte die Karriere
eigene Werte fuer die Autos des Spielers, weil er sich entwickelte und
Ereignisse an den Werten zogen. Beides gibt es nicht mehr, und damit auch
keinen zweiten Ort fuer dieselbe Zahl: Der Editor aendert den Spieler
genauso wie jeden KI-Fahrer.

``starterfeld(..., autos=...)`` gibt es weiter - es ersetzt einzelne
Autos, ohne die Reihenfolge des Feldes zu verschieben.

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
werte = wetter.generator().normal(0, 0.03, size=40)
```

Derselbe Pfad liefert immer dieselbe Folge, und ein zusaetzlicher Zweig
verschiebt keinen bestehenden. Das ist noetig, weil das GDD an vielen
Stellen getrennt wuerfelt – Wetter, Tagesform und Eigenschafts-Zufall je
einmal fuer Qualifying und einmal fuer das Rennen.

## Offene Punkte

Das GDD nennt an vielen Stellen eine Mechanik, ohne sie zu beziffern. Zu
jeder liegen in [OFFENE_PUNKTE.md](OFFENE_PUNKTE.md) Vorschlaege mit
Begruendung; alle sind entschieden, der Abschnitt `[offen]`
in der Konfiguration ist leer. Kommt spaeter eine Luecke hinzu, wird sie dort
vermerkt und im Hauptfenster angezeigt, statt still gefuellt zu werden.

## Datenquellen

Streckendaten: [TUMFTM/racetrack-database](https://github.com/TUMFTM/racetrack-database),
Lizenz LGPL-3.0. Die 20 Strecken der Saison liegen unveraendert unter
`daten/strecken/` und werden in die .exe gepackt; Herkunft, Format und
Datenqualitaet beschreibt `daten/strecken/HERKUNFT.md`.
