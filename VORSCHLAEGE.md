# Vorschläge: Qualifying, Live-Rennen, Performance

Stand 2026-09-20. **Nichts davon ist gebaut.** Die Liste ist zum
Auswählen da — sag die Nummern, dann zeige ich für die gewählten einen
Plan, bevor ich anfange (CLAUDE.md).

Abschnitt C und D stehen auf einer **Messung**, nicht auf Vermutungen.
Die Messwerte stammen aus Zandvoort, Liga 1, 30 Autos, 40 Runden,
Seed 4711, auf dem Entwicklungsrechner (4 Kerne). Die Skripte liegen
unter `werkzeuge/` noch nicht — sie standen im Scratchpad; wenn die
Messung wiederholbar sein soll, ist das ein eigener Punkt (E13).

---

## A. Qualifying — 30 Vorschläge

### Zeitentafel und Live-Ablauf

1. **Rückstand läuft mit.** Während ein Fahrer auf der Runde ist, aus
   seinen fertigen Sektoren hochrechnen, wo er landen wird, und die
   Zeile schon dort einsortieren — heute steht er unten, bis er
   ankommt.
2. **Gap zum Vordermann** als eigene Spalte neben dem Rückstand auf die
   Spitze. Zwei verschiedene Fragen, heute beantwortet die Tafel nur
   eine.
3. **Bestzeitenleiste** über der Tabelle: je Sektor Kürzel und Zeit des
   Halters, in Lila. Wer S1 hält, sieht man heute nur, indem man 30
   Zeilen absucht.
4. **Die theoretische Pole**: S1+S2+S3+S4 der jeweils Schnellsten
   zusammengezählt, als eigene Zeile über dem Feld. Sagt, wie viel im
   Feld noch drin wäre.
5. **Streckenfortschritt je Fahrer** auf seiner schnellen Runde: ein
   dünner Balken, wie weit er ist. Heute sieht man nur, dass die Zeit
   läuft, nicht wo er steht.
6. **Der gerade Fahrende** bekommt eine dezent hervorgehobene Zeile —
   bei 30 Zeilen verliert man ihn sonst.
7. **Verdrängungspfeil**: Kommt einer ins Ziel, kurz anzeigen, wen er um
   wie viel verdrängt hat.
8. **Neue Pole leuchtet auf**: Die Zeile blinkt einmal, wenn P1 wechselt.

### Strecke und Grafik

9. **Streckengrafik auch im Qualifying**: ein Punkt, der die schnelle
   Runde abfährt. Die Ansicht existiert für das Rennen bereits.
10. **Sektoren auf der Streckengrafik einfärben** — wo gewinnt der
    aktuelle Fahrer gegen den Führenden, wo verliert er.
11. **Sektorbalken je Fahrer**: vier Balken, Länge gleich Abstand zum
    besten Sektor. Zeigt auf einen Blick, wo die Zeit liegen blieb.
12. **Startreihenfolge gegen Rundenzeit** als Streudiagramm. Macht
    sichtbar, ob die Strecke aufging oder das Wetter kippte — heute
    steht das nur als Wetterverlauf daneben.
13. **Wetterband unter der Zeitleiste**: wo war es trocken, wo nass.

### Statistik nach der Session

14. **Rückstand nach Sektoren aufgeschlüsselt**: von den 0,8 s auf die
    Pole liegen 0,5 s in Sektor 2. Im Qualifying fährt jeder nur eine
    Runde, eine ideale Runde wie im Rennen gibt es also nicht — das hier
    ist die sinnvolle Entsprechung.
15. **Teamduell**: die vier eigenen Fahrer gegeneinander, Delta in
    Tausendsteln, mit Sektorvergleich.
16. **Qualifying-Bilanz über die Saison** je Fahrer: Schnitt-Startplatz,
    Poles, Delta zum Teamkollegen. Die Statistik führt Poles schon.
17. **Streckenbestmarke**: die schnellste je gefahrene Qualirunde hier,
    mit Jahr und Fahrer. Die Rekordseite (Punkt 25) hat die Struktur.
18. **Vergleich zum Vorjahr** auf derselben Strecke — ist das Feld
    schneller geworden oder nur du?
19. **Was die Pole gekostet hätte**: wie viele Punkte im Bereich `q`
    gefehlt haben. Rechnet gegen die Wirkungsmatrix, macht die
    Entwicklung greifbar.
20. **Tagesform als Balken** statt Prozentzahl, mit Farbe.
21. **Wetterprobe**: dieselbe Session mit festem Wetter nachrechnen und
    die Reihenfolge danebenstellen. Zeigt, wen das Wetter getragen und
    wen es erwischt hat. Kostet eine zweite Session — nur auf Knopfdruck.
22. **Histogramm der Rundenzeiten** des Feldes, die eigenen vier Fahrer
    markiert. Zeigt, ob man im Pulk steckt oder abgehängt ist.

### Bedienung

23. **Zur nächsten Zielankunft springen** statt nur Start/Pause — bei
    75 Minuten Session ist das der meistgebrauchte Knopf.
24. **Auf eigene Fahrer filtern** (nur Team / alle).
25. **Zeitleiste zum Scrubben**: der Fortschrittsbalken wird klickbar.
26. **Tastatur**: Leertaste Start/Pause, Pfeiltasten Zeitraffer hoch und
    runter.
27. **Eigene Zeile anheften**, damit sie sichtbar bleibt, auch wenn sie
    auf P24 steht.
28. **Spaltenwahl merken** — wer Wetter und Form nicht braucht, blendet
    sie dauerhaft aus.
29. **Ein Satz zum Schluss**: „A03 holt die Pole mit 0,072 s Vorsprung;
    dein Bester ist P7, 1,4 s zurück."
30. **Session ausgeben** als Textblock oder CSV zum Mitschreiben.

---

## B. Live-Rennen — 30 Vorschläge

### Zeitentafel

31. **Intervall und Rückstand umschaltbar** in einer Spalte, statt
    beide dauerhaft nebeneinander.
32. **Stoppfenster je Fahrer**: in welcher Runde die Strategie den
    nächsten Stopp vorsieht. Der Kern weiß es, die Anzeige zeigt es
    nicht.
33. **Undercut-Warnung**: wer hinter deinem Fahrer gerade an die Box
    geht und damit gefährlich wird.
34. **Positionsverlauf als Mini-Kurve** je Zeile, die letzten zehn
    Runden.
35. **Reifenalter in Runden** neben dem Balken — der Balken sagt
    „wieviel", nicht „wie lange".
36. **Erwartete Restrunden auf dem Satz**, aus dem Verschleiß
    hochgerechnet. Macht die Zwangsstopp-Grenze aus Punkt 78 sichtbar,
    bevor sie zuschlägt.
37. **Delta zur eigenen besten Runde** live — sagt, ob ein Fahrer
    abbaut.

### Grafik

38. **Rückstandsdiagramm auf alle 30 Linien umschaltbar**, in
    Teamfarben. Die zwei Linien sind als Voreinstellung richtig (siehe
    README), aber ein „alle zeigen"-Schalter fehlt.
39. **Boxenstopps als Marker** im Rückstandsdiagramm — ohne sie erklärt
    das Diagramm die Sprünge nicht.
40. **Stintbalken je Fahrer** über die Renndistanz: welcher Satz von
    wann bis wann, in den Mischungsfarben.
41. **Windschattenbereich auf der Streckengrafik** andeuten, wenn zwei
    Autos nah genug sind.
42. **Rundenzeitendiagramm**: jede Runde, je Fahrer, mit den Stopps als
    Ausreißern.
43. **Wetterband unter der Zeitleiste**, wie A13.
44. **Überholheatmap**: wo auf der Strecke wird tatsächlich überholt.
    Die Überholzonen stehen im Streckenmodell, die Manöver im Verlauf.

### Ereignisse

45. **Ticker filtern** — nur eigene Fahrer, nur Unfälle, nur Defekte.
46. **Zum nächsten Ereignis springen**: nächstes Überholmanöver, nächster
    Stopp, nächster Zwischenfall.
47. **Zehn Sekunden zurück** als Knopf — man verpasst sonst genau das,
    worauf man gewartet hat.
48. **Ereignisdichte als Leiste** über der Zeitleiste: wo im Rennen ist
    etwas passiert.
49. **Ausfallgrund im Ticker** mit eigenem Symbol je Art.
50. **Höhepunkte nach dem Rennen** automatisch gesammelt: Führungswechsel,
    Ausfälle, der engste Zweikampf.

### Team und Strategie

51. **Team-Panel**: die vier eigenen Fahrer dauerhaft oben angeheftet,
    egal auf welcher Position sie liegen.
52. **Was-wäre-wenn nach dem nächsten Stopp**: wo käme dein Fahrer
    heraus, wenn er jetzt stoppt.
53. **Boxenstoppbilanz** je Fahrer: Standzeit, Gesamtverlust, Vergleich
    zum Feld.
54. **Stintvergleich**: wer war auf welcher Mischung wie schnell.
55. **Mischungspflicht-Ampel** je Fahrer, statt sie aus zwei Spalten
    zusammenzusuchen.

### Bedienung

56. **Zeitleiste zum Scrubben** (wie A25).
57. **Tastatursteuerung** (wie A26).
58. **Fahrerfokus**: Zeile anklicken → Karte zentriert auf ihn, alle
    Diagramme filtern auf ihn.
59. **Kompaktmodus**: nur die Rangliste, große Schrift, für's reine
    Zusehen — und nebenbei der schnellste Modus überhaupt (siehe D).
60. **Rennen ausgeben** als CSV: Zeitentafel, Stopps, Ereignisse.

---

## C. Die Messung

Zandvoort, Liga 1, 30 Autos, 40 Runden, Seed 4711.

### Aufbau

| Schritt | Zeit |
| --- | ---: |
| Strecke laden | 143 ms |
| Welt erzeugen (600 Fahrer) | 925 ms |
| **Rennen simulieren** | **13.906 ms** |
| `zeige_verlauf()` (Anzeige aufbauen) | 50 ms |

Das Rennen umfasst 22.361 Bilder über 4.472 s Renndauer;
`zeitschritt_ms = 50` bedeutet 89.439 Rechenschritte, `bildschritt_ms =
200` bedeutet ein gespeichertes Bild je vierten Schritt. `distanz_m`
allein ist 5,4 MB (22.361 × 30 float64).

### Wiedergabe

| | je Bild | Bilder/s |
| --- | ---: | ---: |
| wie gebaut | **14,18 ms** | 70 |
| nur die Streckenkarte, ohne Tabellen | 0,10 ms | 10.142 |

**Die Tabellen kosten 99 % der Zeit, die Karte 1 %.** Das ist die
ganze Diagnose. Und es wird schlimmer, je schneller man spielt: Der
Anzeigetakt (`anzeige_takt_ms = 200`) misst in **Rennzeit**. Bei 1x
werden die Tabellen etwa jeden sechsten Takt neu gefüllt, bei 50x und
100x **in jedem einzelnen Takt** — 14,18 ms Arbeit alle 33 ms.

### Zwei Eingriffe, gemessen

| | je Bild | Bilder/s |
| --- | ---: | ---: |
| wie gebaut | 14,18 ms | 70 |
| nur sichtbares Blatt füllen | 9,45 ms | 106 |
| + kein `resizeColumnToContents` | 3,74 ms | 267 |
| + Sektoren gepuffert | **3,64 ms** | **275** |

**3,9x schneller mit zwei Änderungen**, ohne dass sich an der Anzeige
etwas ändert, was man sehen könnte.

---

## D. Die zehn stärksten Bremsen

Gemessen über 200 Bilder mit `cProfile`, sortiert nach Eigenzeit.

### D1 — `resizeColumnToContents` (40–62 % eines Bildes)

7.400 Aufrufe auf 200 Bilder, also **37 je Bild**: fünf Tabellen mal
ihre Spalten, jedes Mal neu. Qt misst dafür jede Zelle der Spalte.
Allein 1,727 s von 3,789 s Profilzeit.

*Abhilfe:* Die Breiten einmal beim Aufbau setzen, danach
`QHeaderView.Fixed` oder `Interactive`. Wer will, darf dann selbst
ziehen — was heute ohnehin bei jedem Bild wieder überschrieben wird.

### D2 — Alle fünf Tabellen füllen, vier davon unsichtbar (33 %)

Zeitenmonitor, Bestmögliche Runde, Meisterschaft und Meldungen liegen
in **einem Reiter**; sichtbar ist immer genau einer. Gefüllt werden
alle vier plus die Rangliste, in jedem Bild.

*Abhilfe:* Nur die Rangliste und das aktive Blatt füllen, beim
Reiterwechsel einmal nachziehen. −4,73 ms je Bild.

### D3 — `clear()` und 30 neue Zeilen je Tabelle je Bild

Gemessen auf 200 Bilder: 1.000 `clear()`, 28.148 `setData`, 38.944
`setForeground`. Jede Zeile wird als neues `QTreeWidgetItem` gebaut,
obwohl sich meist nur zwei Zellen geändert haben.

*Abhilfe:* Die 30 Zeilen einmal anlegen und nur die Texte setzen, die
sich geändert haben. Die Sortierung ändert dann die Reihenfolge, nicht
die Objekte.

### D4 — `beste_sektoren_bis` läuft über alle bisherigen Runden (5 %)

24.000 Aufrufe auf 200 Bilder; die innere Schleife 439.932-mal. Die
Funktion sucht bei jedem Aufruf aus allen bisher gefahrenen Runden die
besten Sektoren neu zusammen — in Runde 40 also über 40 Runden.

*Abhilfe:* Je Fahrer inkrementell mitführen, einmal je Rundenende.
Nach D2 bleiben davon nur noch 1 % übrig, weil der Hauptverbraucher
(„Bestmögliche Runde") dann meist nicht gefüllt wird — aber es ist
derselbe Aufruf, der bei offenem Reiter wieder zuschlägt.

### D5 — `formatiere_dauer` 381-mal je Bild

76.177 Aufrufe auf 200 Bilder. Jede Zeitzelle wird in jedem Bild neu
formatiert, auch wenn sich der Wert seit dem letzten Bild nicht geändert
hat — die beste Runde eines Fahrers etwa ändert sich alle 110 Sekunden.

*Abhilfe:* Fällt mit D3 weitgehend weg. Zusätzlich lohnt ein kleiner
Puffer für unveränderte Werte.

### D6 — `_nachname` und `_teamname` je Zeile je Bild

Je 18.000 Aufrufe. Beide greifen über `self._welt.fahrer[nummer]` und
zerlegen bei jedem Bild denselben String.

*Abhilfe:* Einmal beim `zeige_verlauf()` in zwei Listen auflösen.
Klein, aber kostenlos.

### D7 — Die Reihenfolge wird mehrfach je Bild sortiert

`reihenfolge_zu()` baut eine Python-Schlüsselfunktion über 30 Elemente.
`_plaetze_vorige_runde()` ruft sie ein zweites Mal für einen anderen
Zeitpunkt auf, und `distanzen_zu()` interpoliert dabei erneut.

*Abhilfe:* Ergebnis je Bild einmal rechnen und durchreichen; die Plätze
der Vorrunde ändern sich nur beim Rundenwechsel des Führenden.

### D8 — `_beste_sektoren_im_feld` geht über alle 30 Protokolle

400 Aufrufe, 0,224 s kumuliert — es ruft D4 dreißigmal je Bild.

*Abhilfe:* Fällt mit D4 zusammen; zusätzlich reicht eine Neuberechnung
je Rundenwechsel statt je Bild.

### D9 — Der Anzeigetakt schützt nicht im Zeitraffer

`anzeige_takt_ms` misst in Rennzeit. Bei 1x bremst er wie gedacht, bei
50x und höher ist er wirkungslos, weil zwischen zwei Takten mehr
Rennzeit liegt als die Schwelle.

*Abhilfe:* Zusätzlich in **Echtzeit** deckeln — höchstens N Füllungen
je Sekunde, unabhängig von der Stufe. Das allein macht den Zeitraffer
flüssig, ohne dass eine Zeile Anzeigecode sich ändert.

### D10 — `_tempo_naeherung` interpoliert je Zeile neu

6.059 Aufrufe, 0,215 s kumuliert. Für die Tempospalte wird je Fahrer
zweimal `distanzen_zu()` ausgewertet.

*Abhilfe:* Das Tempo aller 30 Autos einmal je Bild als Vektor rechnen —
es steht im Verlauf ohnehin schon als Feld.

### Zusammen

Gemessen ergeben **D1 + D2** allein 14,18 → 3,74 ms (3,8x). Mit D3, D9
und dem Rest ist ein Bild realistisch unter 1,5 ms, also über 600
Bilder/s — der Zeitraffer läuft dann bei jeder Stufe flüssig.

---

## E. Die Ladezeit

13,9 s für ein Rennen. Das Profil zeigt eine einzige Ursache:
`_ziel_tempo` kostet **13,28 s von 19,17 s** (69 %, mit Profiler
gemessen), aufgerufen 89.439-mal — einmal je Rechenschritt.

Der Grund ist nicht die Mathematik, sondern die **Aufrufkosten von
NumPy auf 30 Werten**. Gemessen auf diesem Rechner:

| Operation auf 30 Werten | Zeit |
| --- | ---: |
| `a * b` | 0,41 µs |
| `np.maximum(a, 0)` | 0,73 µs |
| `a.any()` | 1,07 µs |
| `np.mod(np.floor(a).astype(int), n)` | 1,37 µs |
| `np.argsort(-a)` | 1,65 µs |
| `np.where(a > 0.5, a, b)` | 1,69 µs |
| `np.flatnonzero(a > 0.9)` | 1,79 µs |
| `np.clip(a, 0, 1)` | 2,23 µs |
| **`np.roll(a, -1)`** | **6,73 µs** |

Bei 30 Autos ist fast alles davon Verwaltung. `_ziel_tempo` macht rund
30 solcher Aufrufe je Schritt — das sind die 80 µs.

**E1 — `np.roll` ersetzen.** 178.878 Aufrufe, 1,25 s Eigenzeit. Zwei
Aufrufe je Schritt in `_sogpaare`. Ein vorbereiteter Indexvektor kostet
0,4 µs statt 6,7. Erwartet: **−1,1 s**, ohne jede Verhaltensänderung.

**E2 — `np.clip` durch `np.minimum`/`np.maximum` ersetzen.** 385.922
Aufrufe, 1,50 s kumuliert. `clip` geht über `_wrapfunc` und ist
dreimal so teuer wie die beiden Einzeloperationen. Erwartet: **−0,7 s**.

**E3 — Die konstanten Tempofaktoren zusammenfassen.** `grip *
tempoform * reifen_tempo * defekt_tempo * kenntnis_tempo` sind fünf
Multiplikationen je Schritt, aber vier der fünf ändern sich nur beim
Rundenwechsel oder bei einem Ereignis. Einmal zu einem Faktor
zusammenziehen und nur bei Änderung neu bilden. Erwartet: **−0,5 s**.

**E4 — Ermüdung und Kaltreifen als Tabelle.** Beide hängen nur von der
zurückgelegten Distanz ab und werden je Schritt aus `clip` und
Multiplikationen neu gebaut. Als vorberechnete Kurve über die
Renndistanz sind sie ein Index-Zugriff. Erwartet: **−0,6 s**.

**E5 — Die Profilinterpolation billiger.** `np.mod(np.floor(stelle)
.astype(int), punkte)` dreimal je Schritt. Da `distanz` monoton wächst,
lässt sich der Index fortschreiben statt neu zu rechnen. Erwartet:
**−0,4 s**.

**E6 — `argsort` nur bei Änderung.** 178.878 Aufrufe. Bei 30 Autos
ändert sich die Reihenfolge zwischen zwei 50-ms-Schritten fast nie; ein
Vergleich mit dem Vorschritt ist billiger als ein Sortieren. Erwartet:
**−0,2 s**.

**E7 — `flatnonzero` und `any` durch Zähler ersetzen.** 157.136 und
447.195 Aufrufe. Wer ausgefallen ist, ändert sich selten; ein
mitgeführter Zähler ersetzt die Suche.

**E8 — Konfigurationszugriffe aus der Schleife ziehen.**
`konfiguration.wert()` 214.049-mal. Klein (0,2 s), aber trivial.

**E9 — Der Zeitschritt.** `zeitschritt_ms = 50` ergibt 89.439 Schritte.
100 ms halbierte die Ladezeit sofort. **Aber**: Das ändert die
Simulationsergebnisse und damit die Kalibrierung aus Abschnitt 9 des
GDD. Das ist ein Balancing-Eingriff, keine Optimierung — nur auf deine
Ansage, und dann mit Nachmessung.

**E10 — Im Hintergrund rechnen.** Das Rennen läuft heute im
Oberflächen-Thread; 14 Sekunden lang steht alles. In einem Thread mit
Fortschrittsbalken („Runde 23 von 40") fühlt es sich nicht mehr wie ein
Hänger an, auch wenn es gleich lang dauert. Der Kern ist von der
Oberfläche getrennt, das geht sauber.

**E11 — Die Welt einmal erzeugen.** 925 ms je Aufruf. Wenn das je
Rennwochenende erneut passiert, ist es reine Wiederholung.

**E12 — `float32` statt `float64`** für `distanz_m`, `reifenzustand`
und die anderen Bildfelder. Halbiert 5,4 MB auf 2,7 MB und macht jede
Abfrage der Anzeige billiger. Die Distanzen brauchen keine 15 Stellen.

**E13 — Die Messung ins Repo.** Die Profile oben entstanden in
Wegwerf-Skripten. Als `werkzeuge/profil_rennen.py` wären sie
wiederholbar, und jede der Änderungen hier ließe sich vorher/nachher
belegen — so wie es `werkzeuge/boxenstopps.py` für das Balancing tut.

**Reihenfolge, wenn du willst, dass es schnell wird:** E10 zuerst (die
gefühlte Ladezeit), dann E1–E5 (zusammen rund **−3,3 s**, gemessen
erwartbar, ohne jede Verhaltensänderung), E12 nebenbei. E9 bleibt
deine Entscheidung.
