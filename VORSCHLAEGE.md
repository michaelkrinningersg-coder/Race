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

---

# Vorschläge, Stand 2026-09-22

Nach Punkt 101 (ein Feld aus 50 Autos, feste Fahrer), Punkt 102
(Führungsrunden) und Punkt 103 (keine geschätzten Rückstände). **Nichts
davon ist gebaut.** Sag die Nummern, dann zeige ich für die gewählten
einen Plan, bevor ich anfange (CLAUDE.md).

Die Liste oben von 2026-09-20 gilt weiter, aber **mit Lücken**: Alles,
was an Ligen, Geld, Erfahrung oder den vier Spielerautos hing, ist
gegenstandslos geworden — A15 (Teamduell der vier Fahrer), A19 (was die
Pole an Entwicklungspunkten gekostet hätte), B47 bis B52 (Team und
Strategie mit Konto). Gebaut sind unter anderem A9, A17, A23, B53 und
B59.

Sechs Punkte unten sind **gemessen**, nicht geraten: 6, 12, 19, 25, 29
und 30. Sie beschreiben etwas, das heute nachweislich schief steht.

## Rennen

1. **Rundenzeitenband unter der Rangliste.** Je Auto eine Zeile aus 55
   kleinen Kästchen, eines je Runde, eingefärbt nach Mischung. Ein Blick
   sagt, wer wann gestoppt hat und wo eine Runde ausriss. Die Daten
   stehen komplett in `Rundenprotokoll`.
2. **Der Führungswechsel als Meldung.** Der Ticker meldet Fehler,
   Unfälle und Defekte — nicht aber „VER übernimmt die Führung". Nach
   Punkt 102 liegt die Information vor; gemessen fallen 7 bis 10 Wechsel
   je Rennen, das wären 7 bis 10 zusätzliche Zeilen.
3. **Rennbericht in fünf Sätzen** am Ende, statt nur einer Tabelle: wer
   führte, wo es kippte, wer am meisten aufholte, die schnellste Runde,
   der teuerste Zwischenfall. Alles aus dem Verlauf ablesbar.
4. **Undercut sichtbar machen.** Wenn zwei Autos in benachbarten Runden
   stoppen, die Positionen davor und danach gegenüberstellen. Die
   Boxenbilanz sagt heute, was ein Stopp *gekostet* hat, nicht was er
   *gebracht* hat.
5. **Die eigenen zwei Autos anheften**: eine schmale Leiste über der
   Rangliste, die sie immer zeigt — auch wenn sie auf P27 und P34
   stehen und man gerade oben scrollt.
6. **Der Zieleinlauf braucht eine eigene Ansicht.** *(gemessen)* Heute
   steht am Ende dieselbe Rangliste wie in Runde 30, nur eingefroren.
   Im letzten Screenshot standen 22 von 50 Autos auf „+1 Rd." — bei
   vier Prozent Feldspanne über 55 Runden ist Überrunden die Regel, und
   die Tabelle sagt nicht, wer auf der Führungsrunde blieb.
7. **Positionsdiagramm über die Runden**, eine Linie je Auto wie beim
   Rückstandsdiagramm, aber mit Platz statt Sekunden. Zeigt Verläufe,
   die in Momentaufnahmen untergehen.
8. **Reifenwahl auch während des Rennens** für die eigenen Autos: beim
   nächsten Stopp eine andere Mischung. Heute steht die Strategie vor
   dem Start fest — das ist eine Mechanikfrage, keine Anzeigefrage.

## Qualifying

9. **Die theoretische Pole** als Zeile über dem Feld: die vier besten
   Sektoren des Feldes zusammengezählt. Steht schon als A4 auf der alten
   Liste und ist nach wie vor der billigste Mehrwert dort.
10. **Sektorbalken je Fahrer** statt vier Zahlenspalten — vier Balken,
    Länge gleich Abstand zum besten Sektor.
11. **Das Feld als Histogramm** der Rundenzeiten, die eigenen zwei Autos
    markiert. Bei 4 % Spanne und 50 Autos ist die spannende Frage, wie
    dicht der Pulk an der Stelle ist, wo man selbst steht.
12. **Warum ist die Pole langsamer als die schnellste Rennrunde?**
    *(gemessen)* Sakhir: Pole 1:34.020, schnellste Rennrunde 1:32.338.
    Ursache ist die Gummierung — das Qualifying fährt auf grünerer
    Strecke. Kein Fehler, aber es sieht nach einem aus. Entweder
    erklären (ein Satz in der Session-Box) oder das Modell ändern.
13. **Q1/Q2/Q3 statt einer Session.** 50 Autos, ein Lauf, eine Runde
    jeder — das ist viel Feld für wenig Spannung. Ein Ausscheidungsmodus
    wäre eine echte Mechanikerweiterung; steht nicht im GDD.
14. **Sektorenvergleich zweier Fahrer** auf Knopfdruck, nebeneinander —
    der Griff, den man nach jeder Session macht.

## Statistiken

15. **Führungsrunden in die Fahrerkarte.** Punkt 102 hat sie in die
    Bestenliste gebracht, aber der Reiter *Saison* und der Reiter
    *Laufbahn* kennen sie noch nicht. Dort gehören sie hin.
16. **Führungsrunden je Strecke** in der Streckenbilanz — wer Monza
    beherrscht, sieht man daran besser als an Siegen.
17. **Kopf-an-Kopf zweier Fahrer** über die ganze Karriere: Qualifying,
    Rennen, Punkte, Führungsrunden, wer wen wie oft geschlagen hat.
18. **Saisonvergleich im Diagramm**: mehrere Saisons als Linien
    übereinander, um zu sehen, ob eine Saison eng oder früh entschieden
    war.
19. **Der 30-Saisons-Lauf steht seit Block 5 offen.** *(gemessen: 10
    von 30)* Seit Punkt 101 altert niemand mehr und entwickelt sich
    niemand — der Lauf sollte jetzt ein völlig anderes Ergebnis liefern
    als damals und wäre die Probe darauf, ob die Welt über Jahrzehnte
    stabil bleibt. Aufgabe #37.
20. **Rekorde mit Kontext**: Neben der schnellsten Runde stehen Jahr,
    Wetter und Reifenmischung. Heute steht nur die Zeit da.
21. **Eine Ansicht „Diese Saison in Zahlen"**: verschiedene Sieger,
    Führungswechsel, engster Zieleinlauf, meiste Ausfälle. Die Saison
    als Ganzes, nicht Fahrer für Fahrer.
22. **Statistik ausgeben** als CSV — wer eigene Auswertungen fahren
    will, kommt heute nur über den Spielstand heran.

## Oberfläche und Bedienung

23. **Die Reiterleiste rechts rollt.** Sechs Blätter brauchen 688 px,
    verfügbar sind rund 570. Drei Wege: rechte Spalte breiter, Etiketten
    kürzer, oder die Blätter in zwei Reihen. Steht seit Punkt 102 offen.
24. **Tastatur im Rennen und im Qualifying**: Leertaste Start/Pause,
    Pfeiltasten für den Zeitraffer, Pos1 an den Anfang. Heute ist alles
    Maus.
25. **Der Fortschrittsbalken ist nicht klickbar.** *(gemessen)* Wer in
    Runde 40 sehen will, was in Runde 12 passiert ist, muss zurück auf
    Anfang und vorspulen. `_springe` kann es längst — es fehlt nur der
    Klick.
26. **Spaltenwahl merken.** Die Rangliste hat 14 Spalten; wer Alter,
    Reichweite und Planstopp nicht braucht, sollte sie dauerhaft
    ausblenden können.
27. **Dunkle Darstellung.** Elf Sekunden Rennen mit weißem Hintergrund
    sind abends anstrengend, und die Teamfarben sind auf Dunkel ohnehin
    besser zu unterscheiden.
28. **Fenstergröße und Reiter merken** über den Programmstart hinweg.
29. **Das Standbild sagt zu wenig.** *(gemessen)* Seit Punkt 103 steht
    vor dem Start überall ein Strich — richtig, aber karg. Der
    Startplatzabstand in Metern wäre dort eine echte Information.
30. **`kern/wettersaison.py` ist tot.** *(gemessen)* Kein Modul
    importiert es; nur sein eigener Test hält es am Leben. Entweder
    anschließen — es würde eine Saison mit zusammenhängendem Wetter
    ermöglichen statt 20 unabhängiger Würfe — oder löschen.
