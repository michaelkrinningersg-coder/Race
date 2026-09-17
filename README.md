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
GDD 15 es vorgibt - 21 Tabellen, eine Datei je Spielstand, im Menue unter
Datei. Die Welt wird dabei vollstaendig abgelegt statt aus dem Seed neu
gewuerfelt: Nach dem ersten Auf- und Abstieg stimmt die gewuerfelte Welt
nicht mehr mit der gespielten ueberein. Ein Test haelt genau das fest.

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
