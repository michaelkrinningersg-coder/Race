# Offene Punkte – Vorschläge zur Entscheidung

Das GDD nennt an vielen Stellen eine Mechanik, ohne sie zu beziffern.
Dieses Dokument listet jede solche Lücke, drei Varianten und die getroffene
Entscheidung. **Stand 2026-09-17: alle 41 Punkte entschieden.**
Was danach dazukam, steht als Nachtrag am Ende — zuletzt **Punkt 103**
(keine geschätzten Rückstände mehr), davor **Punkt 102** (Führungsrunden)
und **Punkt 101** (ein Feld aus 50 Autos mit festen Fahrern).

Die entschiedenen Werte stehen in `konfiguration/balancing.toml`; der
Abschnitt `[offen]` dort ist leer. Jede Entscheidung lässt sich ändern,
ohne Code anzufassen — die Nummer unten führt zur Begründung.

---

## Grundsatzfragen zum Projekt

### O1. Herstellerliste

GDD 12 nennt „20 reale Autohersteller, nur Name und Farbe", aber keine
konkreten.

| | Variante |
| --- | --- |
| **A** | Vorgeschlagene Liste übernehmen (Alfa Romeo bis Toyota) |
| **B** | Eigene 20 Hersteller vorgeben |
| **C** | Erfundene Namen statt echter Marken (vermeidet Markenrecht von vornherein) |

**Entscheidung: A** (2026-09-17). `hersteller.toml` trägt jetzt
`bestaetigt = true`. Die Datei bleibt ausgelagert, damit sich die Namen vor
einer Veröffentlichung austauschen lassen — das Markenrecht bleibt also
lösbar, ohne Code anzufassen.

### O2. Referenzstrecke der Kalibrierung

GDD 9 verlangt eine „kurvige Referenzstrecke", nennt aber keine. Ich habe
**Zandvoort** gewählt — mit 46 % den geringsten Geradenanteil aller 20
Strecken, laut GDD 3 „Steilkurven, eng". Ein Wechsel ist ein Aufruf von
`werkzeuge/kalibriere.py --schreiben`.

| | Variante | Geradenanteil |
| --- | --- | --- |
| **A** | Zandvoort | 46 % |
| **B** | Suzuka | 50 % |
| **C** | São Paulo | 48 % |

**Entscheidung: A** (2026-09-17). Zandvoort bleibt Referenzstrecke.

### O3. Dateiname der Arbeitsregeln

Das GDD sagt, die Regeln kommen als `CLAUDE.md` ins Repo; angelegt war sie
als `Claude.md`. Zunächst hatte ich **nicht** umbenannt: Auf Windows und
macOS ist das Dateisystem nicht case-sensitiv, eine reine
Groß-/Kleinschreibungsänderung macht dort beim Auschecken Ärger.

| | Variante |
| --- | --- |
| **A** | So lassen (Claude Code liest die Datei ohnehin) |
| **B** | Auf `CLAUDE.md` umbenennen, wie im GDD beschrieben |

**Entscheidung: B** (2026-09-17). Die Datei heißt jetzt `CLAUDE.md`. Wer
das Repo auf Windows oder macOS ausgecheckt hat, bevor die Umbenennung kam,
löscht die Datei dort einmal und zieht sie neu — sonst hält das
Dateisystem die alte Schreibweise fest.

---

## Übersicht aller entschiedenen Punkte

Gebraucht ab = der Umsetzungsschritt, der den Wert braucht. Die
**fett** markierte Variante ist gesetzt.

### Strecken und Überholen

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 1 | Mindestlänge je Segment | **A keine** · B 15 m · C 25 m | 2 |
| 2 | Überholschwierigkeit je Strecke | A Geradenanteil · **B Überholzonenanteil** · C längste Zone | 4 |
| 3 | Erfolgsformel beim Überholen | A Verhältnis · **B logistisch** · C additiv | 4 |

### Wetter und Zufall

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 4 | Wetterprofil je Strecke | **A drei Klimaprofile** · B Gleichverteilung · C je Strecke einzeln | 5 |
| 5 | Verzögerung der Streckennässe | A keine · **B über 3 Runden** · C über 5 Runden | 5 |
| 21 | Tempobonus der Trockenroutine | A +0,25 % · **B +0,5 %** · C +1,0 % | 5 |
| 22 | D16 dämpft schlechte Tagesform | A 40 % · **B 60 %** · C 80 % | 5 |
| 23 | D12 verkleinert die Rundenform | A 60 % · **B 80 %** · C 95 % | 5 |
| 24 | Q-Spalte als Tempobonus | A +0,5 % · **B +1,0 %** · C +2,0 % | 5 |
| 27 | Qualifying: Dauer und Wetter | **überlappender Start 1,25 Rd. + 15-Min-Fenster + höchstens 1 Wechsel** | 5 |

### Fehler, Unfälle, Defekte, Reifen

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 6 | Basisrate für Fehler | A 1 je 20 Rd. · **B 1 je 10 Rd.** · C 1 je 5 Rd. | 6 |
| 7 | Unfallwahrscheinlichkeit | **A sehr selten** · B mittel · C häufig | 6 |
| 8 | Defektwahrscheinlichkeit | A 2 % · **B 5 %** · C 10 % | 6 |
| 9 | Verlauf des Reifenverschleißes | A linear · **B progressiv** · C mit Abbruchkante | 6 |
| 10 | Verschleiß-Faktor je Strecke | **A Querbeschleunigung** · B Kurvenanteil · C fest 1,0 | 6 |
| 11 | Ermüdungskurve | A linear über alles · **B ab der Hälfte** · C quadratisch | 6 |
| 25 | Einordnung des Reifenflüsterers | A als D17 · **B neben der Wirkungsmatrix** · C D14 aufbohren | 6 |
| 26 | Einheit der Unfallrate | **je Sekunde in Reichweite**, nicht je Zeitschritt | 6 |

### Geld

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 12 | Preisgeld zwischen den Stützstellen | **A logarithmisch** · B linear · C Spline | 8 |
| 13 | Preisgeld-Anteile P4 bis P29 | **A geometrisch** · B linear · C gestaffelt | 8 |
| 14 | Startgeld | **A 5 % der Siegprämie** · B 10 % · C fest 250 € | 8 |
| 15 | Erfahrungsbeträge | A Platzierung dominiert · **B ausgewogen** · C Teilnahme dominiert | 8 |
| 16 | Wetter-Erfahrung je km | A 0,05 % · **B 0,1 %** · C 0,2 % | 8 |
| 17 | K₀-Faktor je Fähigkeit | A alle 1,0 · **B nach Wirkungsbreite** · C drei Klassen | 8 |
| 18 | Liga-Faktor der Reparaturkosten | **A 1 % je Stufe** · B 2,5 % · C linear | 8 |
| 19 | Sponsorbeträge | A zurückhaltend · **B zweite Säule** · C tragende Säule | 8 |

### Welt

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 28 | Bildung der Teamnamen | A 150 von Hand · **B aus zwei Teilen** · C nach Hersteller | 7 |
| 29 | Teamfarbe neben der Herstellerfarbe | **aus der Herstellerfarbe abgeleitet** | 7 |
| 30 | Alter und Regionenanteil der Fahrer | **18 bis 42 Jahre, 10 % Nordamerika** | 7 |
| 31 | Ligastärken zwischen den Stützstellen | **über die Tempotabelle, +6,32 km/h je Liga** | 7 |

### Saison

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 32 | Verkehr im Schnellmodus | A Abstand am Rundenende · **B Reihenfolgewechsel je Runde** · C gar nicht | 9 |
| 33 | Qualifying-Reihenfolge ohne Vorjahresstand | **wie im ersten Rennen: aufsteigend nach Q-Fähigkeit** | 9 |

### Ereignisse

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 20 | Geld- und Erfahrungsbeträge der Ereignisse | A klein · **B spürbar** · C groß | 10 |
| 34 | Bezugsgröße dauerhafter Prozentwirkungen | A vom Wert · **B max(+10, +1 %)** · C von der Skala | 10 |
| 35 | Auswahl des Ereignisses | **gleichverteilt, ohne Zurücklegen je Zyklus** | 10 |
| 36 | Ereignisse für die KI | A alle 600 · B Spielerliga · **C nur der Spieler** | 10 |

### Streuung und Streckenkenntnis

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 37 | Profil über die Wirkungsbereiche | **±30 % je Bereich zusätzlich zu GDD 12** | 10 |
| 38 | Lerntempo je Fahrer | **±60 %, fest über die Karriere** | 10 |
| 39 | Streckenkenntnis der KI | **fest, einmal gesetzt, ±80 %** | 10 |

### Editor

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 40 | Sichtbarkeit des Editors | **eigener Reiter** · Schalter im Menü · Startoption | 10 |
| 41 | Umfang des Editors | Werte und Kenntnis · **zusätzlich Stammdaten** · auch Liga und Team | 10 |

---

## Begründungen im Einzelnen

Was folgt, sind die Vorlagen, aus denen die Entscheidungen entstanden sind —
mit den gemessenen Zahlen, auf denen sie beruhen.

---

## Schritt 2 – Strecken (bereits umgesetzt, Entscheidung nachzuholen)

### 1. Mindestlänge je Segment

**GDD 3** leitet den Segmenttyp allein aus dem Radius ab und nennt keine
Mindestlänge. Dabei entstehen einzelne Segmente von 5 bis 20 m, insgesamt
213 über alle 20 Strecken.

| | Variante | Wirkung |
| --- | --- | --- |
| **A** | Keine Mindestlänge (aktuell umgesetzt) | Segmenttyp rein nach Radius, wie im GDD beschrieben |
| **B** | 15 m, Fragmente gehen im Nachbarsegment auf | Segmentlisten werden übersichtlicher |
| **C** | 25 m | Deutlich weniger Segmente, glättet aber echte kurze Schikanen weg |

**Empfehlung: A.** Gemessen ist der Unterschied folgenlos: Das Verschmelzen
von Fragmenten unter 25 m ändert die Zahl der Überholzonen nur auf 2 von 20
Strecken, weil die 100-m-Regel sie ohnehin filtert. A hält sich exakt an das
GDD und braucht keinen zusätzlichen Wert.

**Entscheidung: A** (2026-09-17)

---

## Schritt 4 – Überholen

### 2. Überholschwierigkeit je Strecke

**GDD 3** nennt „Überholschwierigkeit (aus Geradenanteil)" als Kennwert,
**GDD 4** braucht sie als „Streckenfaktor" in der Erfolgschance. Die Formel
fehlt. Gemessene Spannen:

| Grundlage | Spanne | Schwierigste | Leichteste |
| --- | --- | --- | --- |
| Geradenanteil | 46 % … 81 % | Zandvoort | Norisring |
| Anteil der Überholzonen (Geraden ab 100 m) | 33 % … 81 % | Zandvoort | Norisring |
| Längste Überholzone | 610 m … 1.240 m | Oschersleben | Monza |

| | Variante | Formel |
| --- | --- | --- |
| **A** | Aus dem Geradenanteil | `faktor = geradenanteil / mittelwert_aller_strecken` |
| **B** | Aus dem Überholzonenanteil | wie A, aber nur Geraden ab 100 m zählen |
| **C** | Aus der längsten Überholzone | `faktor = laengste_zone / mittlere_laengste_zone` |

**Empfehlung: B.** Überholt werden darf laut GDD 4 ausschließlich in Zonen
ab 100 m – nur die sollten den Faktor bestimmen. B spreizt außerdem stärker
(33 % bis 81 % statt 46 % bis 81 %) und trifft die Charakterangaben des GDD:
Budapest („kaum Überholen") landet bei 41 %, Monza bei 78 %.

**Entscheidung: B** (2026-09-17)

### 3. Erfolgsformel beim Überholen

**GDD 4:** „Erfolgschance aus Überholen (Angreifer) gegen Verteidigen
(Verteidiger), Streckenfaktor und Tempovorteil". Die Verknüpfung fehlt.
Voraussetzung ist bereits beziffert: Abstand unter 0,05 s und mindestens
2 km/h Vorteil.

| | Variante | Formel |
| --- | --- | --- |
| **A** | Verhältnis | `p = D10 / (D10 + D11) × streckenfaktor × tempobonus`, bei gleichen Werten 50 % |
| **B** | Logistisch | `p = sigmoid(a × (D10 − D11)/100.000 + b × (Δv − 2)/10) × streckenfaktor` |
| **C** | Additiv mit Deckelung | `p = 0,5 + 0,3 × (D10 − D11)/100.000 + 0,2 × (Δv − 2)/10`, begrenzt auf 5 % bis 95 % |

**Empfehlung: B.** Nur die logistische Form bleibt in den Randlagen sinnvoll:
Bei A geht ein Fahrer mit Wert 0 gegen einen mit 100.000 auf 0 % – aber beide
starten laut GDD 1 bei 0, und `0/(0+0)` ist gar nicht definiert. C läuft aus
dem Band, sobald der Tempovorteil groß wird. B braucht zwei Konstanten (`a`,
`b`), die sich an einer Massensimulation kalibrieren lassen.

**Entscheidung: B** (2026-09-17)

---

## Schritt 5 – Wetter

### 4. Wetterprofil je Strecke

**GDD 3** nennt „Wetterprofil" als Streckenkennwert, **GDD 16** entscheidet
„Wetter je Strecke gewichtet, über die Saison schwankend". Die Gewichte
fehlen.

| | Variante | Aufbau |
| --- | --- | --- |
| **A** | Drei Klimaprofile | *heiß-trocken* (Sakhir, Yas Marina, Mexiko-Stadt, Austin, São Paulo, Melbourne, Shanghai), *gemäßigt* (Catalunya, Monza, Budapest, Suzuka, Montreal, Spielberg), *regenreich* (Spa, Zandvoort, Silverstone, Nürburgring, Hockenheim, Norisring, Oschersleben) |
| **B** | Gleichverteilung | Alle fünf Wetterlagen überall gleich wahrscheinlich |
| **C** | Je Strecke einzeln | 20 × 5 Gewichte von Hand |

**Empfehlung: A.** Drei Profile sind schnell entschieden, geben den Strecken
aber Charakter – Spa im Regen, Sakhir in der Hitze – und machen die
Wetterfähigkeiten aus GDD 7 unterschiedlich wertvoll. B verschenkt das, C
sind 100 Werte ohne Mehrwert gegenüber A.

**Entscheidung: A** (2026-09-17)

### 5. Verzögerung der Streckennässe

**GDD 7:** „Streckennässe folgt dem Wetter verzögert (Vorschlag)" – ohne Wert.

| | Variante | Wirkung |
| --- | --- | --- |
| **A** | Keine Verzögerung | Der Grip springt mit dem Wetterwechsel |
| **B** | Über 3 Runden gleitend | Nach einem Wechsel nähert sich der Grip in drei Runden dem neuen Wert |
| **C** | Über 5 Runden gleitend | Träger, in kurzen Rennen spürbar |

**Empfehlung: B.** A macht Wetterwechsel zu harten Sprüngen in der Rundenzeit
und damit unrealistisch. Bei Liga 20 (100 km) sind 3 Runden rund 10 % der
Distanz, bei Liga 1 rund 4 % – in beiden Fällen merklich, aber nicht
dominierend.

**Entscheidung: B** (2026-09-17)

---

## Schritt 6 – Fehler, Unfälle, Defekte, Reifen

### 6. Basisrate für Fehler

**GDD 4:** „Wahrscheinlichkeit aus den Eigenschaften, skaliert mit dem
Wetter; kosten einmalig Zeit". Weder Rate noch Zeitverlust sind genannt. Die
Wetter-Multiplikatoren (× 1,0 bis × 2,5) stehen bereits in GDD 7.

| | Variante | Bei Wert 0 | Bei 100.000 | Zeitverlust |
| --- | --- | --- | --- | --- |
| **A** | Selten | 1 Fehler je 20 Runden | 1 je 200 Runden | 0,3 bis 1,5 s |
| **B** | Mittel | 1 je 10 Runden | 1 je 100 Runden | 0,5 bis 2,0 s |
| **C** | Häufig | 1 je 5 Runden | 1 je 50 Runden | 0,5 bis 3,0 s |

**Empfehlung: B.** Ein Rennen in Liga 20 hat rund 25 Runden. Bei B macht ein
Anfänger etwa 2 bis 3 Fehler je Rennen, bei Starkregen (× 2,5) rund 6 – spürbar,
aber nicht beliebig. Bei A wäre die Eigenschaft D1 Konzentration in den unteren
Ligen kaum wahrnehmbar, bei C wäre Fahren dort reines Glück.

**Entscheidung: B** (2026-09-17)

### 7. Unfallwahrscheinlichkeit

**GDD 4:** „sehr selten und nur bei weniger als 30 m Abstand; mal scheidet ein
Auto aus, mal beide; je Rennen wird eine Obergrenze von 0–5 Ausfällen
gewürfelt". Die Rate und die Aufteilung ein/beide fehlen.

| | Variante | Auslösechance je Annäherung unter 30 m | Ein Auto / beide |
| --- | --- | --- | --- |
| **A** | 0,02 % | rund 0 bis 1 Unfall je Rennen | 75 % / 25 % |
| **B** | 0,05 % | rund 1 bis 2 je Rennen | 70 % / 30 % |
| **C** | 0,10 % | rund 2 bis 4 je Rennen | 65 % / 35 % |

**Empfehlung: A.** Das GDD sagt ausdrücklich „sehr selten", und die
Obergrenze von 0–5 je Rennen ist eine Decke, kein Ziel. Bei 30 Autos und
dichtem Feld gibt es sehr viele Annäherungen unter 30 m; schon A führt zu
Ausfällen in etwa jedem zweiten Rennen. Die genaue Zahl lässt sich nach einer
Massensimulation nachziehen.

**Entscheidung: A** (2026-09-17)

### 8. Defektwahrscheinlichkeit

**GDD 4:** „selten, aber häufiger als Unfälle". Die 20 Defekte und ihre
Wirkungen stehen in GDD 14, die Auslöserate fehlt.

| | Variante | Je Auto und Rennen bei F14 = 0 | Bei F14 = 100.000 |
| --- | --- | --- | --- |
| **A** | 2 % | rund 0,6 Defekte je Rennen im Feld | 0,2 % |
| **B** | 5 % | rund 1,5 je Rennen im Feld | 0,5 % |
| **C** | 10 % | rund 3 je Rennen im Feld | 1,0 % |

**Empfehlung: B.** B erfüllt „häufiger als Unfälle" deutlich (1,5 gegen rund
0,5) und macht F14 Zuverlässigkeit zu einem Upgrade, dessen Wirkung man
bemerkt. Bei A bliebe F14 in den unteren Ligen wirkungslos.

**Entscheidung: B** (2026-09-17)

### 9. Verlauf des Reifenverschleißes

**GDD 4:** „Verschleiß senkt das Tempo und erhöht die Fehlerquote". Der
Verlauf über die Distanz fehlt. Die Wetterfaktoren (× 0,7 bis × 1,4) stehen
in GDD 7.

| | Variante | Verlauf | Tempoverlust am Renn­ende |
| --- | --- | --- | --- |
| **A** | Linear | Gleichmäßig über die Distanz | −2 % |
| **B** | Progressiv | Erst flach, letztes Drittel steil | −1 % nach 2/3, −3 % am Ende |
| **C** | Mit Abbruchkante | Bis 80 % flach, danach stark | −0,5 %, dann −5 % |

**Empfehlung: B.** B bildet den realen „Abbau" ab und macht D14
Reifenmanagement und F10 Reifenhaltbarkeit gegen Rennende wertvoll, ohne dass
das Rennen kippt. C wäre ohne Boxenstopps (die laut GDD 16 erst später kommen)
frustrierend, weil es keine Gegenmaßnahme gibt.

**Entscheidung: B** (2026-09-17)

### 10. Reifenverschleiß-Faktor je Strecke

**GDD 3** nennt ihn als Kennwert, ohne Herleitung. Zwei berechenbare
Grundlagen, hier auf den Mittelwert aller 20 Strecken normiert:

| Strecke | aus Querbeschleunigung | aus Kurvenanteil |
| --- | --- | --- |
| Zandvoort | 1,26 | 1,37 |
| Catalunya (GDD: „Reifenverschleiß") | 1,16 | 1,24 |
| Suzuka | 0,98 | 1,28 |
| Spa | 0,80 | 0,89 |
| Monza | 0,54 | 0,62 |

| | Variante | Grundlage |
| --- | --- | --- |
| **A** | Querbeschleunigung | Summe von 1/Radius über die Runde, auf den Mittelwert normiert |
| **B** | Kurvenanteil | Anteil von enger Kurve und Kurve an der Rundenlänge |
| **C** | Fest 1,0 | Alle Strecken gleich, bis Boxenstopps kommen |

**Empfehlung: A.** Reifen verschleißen durch Querkraft, und die steckt im
Radius, nicht in der bloßen Anzahl der Kurven. A trennt deshalb sauber
zwischen Suzuka (viele, aber schnelle Kurven: 0,98) und Zandvoort (wenige,
aber enge: 1,26), während B beide fast gleich bewertet. Catalunya landet bei
A auf Platz 5 von 20, passend zur Charakterangabe im GDD.

**Entscheidung: A** (2026-09-17)

### 11. Ermüdungskurve

**GDD 8** führt den Wirkungsbereich „Er Ermüdung" mit D2 Ausdauer (Gewicht 3)
und D3 Fitness (Gewicht 2), nennt aber keine Wirkung aufs Tempo. **GDD 6**
beschreibt D2 als „Leistungsabfall über die Distanz".

| | Variante | Verlauf | Verlust am Ende bei Wert 0 |
| --- | --- | --- | --- |
| **A** | Linear über die ganze Distanz | ab Runde 1 | −1,5 % |
| **B** | Ab der Hälfte linear | erste Hälfte ohne Verlust | −2,0 % |
| **C** | Quadratisch | wächst mit dem Quadrat der gefahrenen Distanz | −2,5 % |

**Empfehlung: B.** Ermüdung soll das Renn­ende prägen, nicht den Start; das
passt zu D1 Konzentration, deren Fehler laut GDD 6 „v. a. späte Runden"
betreffen. Bei 100.000 geht der Verlust jeweils auf null zurück.

**Entscheidung: B** (2026-09-17)

---

## Schritt 8 – Geld

### 12. Preisgeld zwischen den Stützstellen

**GDD 10** nennt Siegprämien für die Ligen 20, 15, 10, 5 und 1 und sagt
„Zwischenligen werden interpoliert" – ohne Verfahren. Der Unterschied ist
groß:

| Liga | linear | logarithmisch |
| --- | --- | --- |
| 20 | 4.000 € | 4.000 € (Stützstelle) |
| 19 | 23.200 € | 7.615 € |
| 18 | 42.400 € | 14.496 € |
| 16 | 80.800 € | 52.531 € |
| 15 | 100.000 € | 100.000 € (Stützstelle) |

| | Variante | Eigenschaft |
| --- | --- | --- |
| **A** | Logarithmisch | Gleichmäßiger *Faktor* je Liga (rund 1,9× zwischen Liga 20 und 15) |
| **B** | Linear | Gleichmäßiger *Betrag* je Liga; erzeugt zwischen Liga 20 und 19 einen Sprung von 5,8× |
| **C** | Monotone Spline (PCHIP) | Glatter Übergang an den Stützstellen, Werte zwischen A und B |

**Empfehlung: A.** Das GDD begründet die Preisgelder relativ: „Ein Top-3-Fahrer
soll das Niveau der nächsten Liga in etwa 1,5 Saisons erreichen." Diese
Vorgabe ist ein Verhältnis, kein Betrag – also muss auch die Interpolation
über das Verhältnis laufen. Bei B verdient ein Aufsteiger von Liga 20 nach 19
schlagartig das Sechsfache, danach kaum noch mehr; das widerspricht dem
Satz „durch die Wurzel liegt der größte relative Kostensprung jetzt in den
unteren Ligen" aus GDD 9. C braucht zusätzlich SciPy als Abhängigkeit.

**Entscheidung: A** (2026-09-17)

### 13. Preisgeld-Anteile für die Plätze 4 bis 29

**GDD 10** nennt P1 100 %, P2 80 %, P3 65 % und P30 5 %, dazwischen nur
„danach fallend".

| Platz | A geometrisch | B linear | C gestaffelt |
| --- | --- | --- | --- |
| 4 | 59,1 % | 62,8 % | 52,8 % |
| 6 | 48,9 % | 58,3 % | 34,9 % |
| 10 | 33,4 % | 49,4 % | 15,2 % |
| 15 | 20,8 % | 38,3 % | 5,4 % |
| 20 | 12,9 % | 27,2 % | 5,0 % |
| **Topf je Rennen** | **8,47 ×** Siegprämie | **11,60 ×** | **5,78 ×** |

- **A**: gleichbleibender Faktor von P3 (65 %) bis P30 (5 %)
- **B**: gleichbleibender Abzug je Platz
- **C**: das Verhältnis P2→P3 (0,81) fortgesetzt bis zum Sockel von 5 %

**Empfehlung: A.** Die vorgegebenen Stützstellen fallen oben steil (100 → 80
→ 65) und sollen unten bei 5 % landen – genau das leistet eine geometrische
Kurve. B hält Platz 20 noch bei 27 % und macht das Mittelfeld zu bequem; C
drückt schon Platz 10 auf 15 % und entwertet solide Rennen. Der Topf von
8,47 Siegprämien ist zugleich ein Hebel fürs Balancing, falls das Geld
insgesamt zu knapp oder zu reichlich ist.

**Entscheidung: A** (2026-09-17)

### 14. Startgeld

**GDD 10:** „Startgeld für jeden Teilnehmer" – ohne Höhe. Startkapital ist
1.000 €.

| | Variante | Liga 20 | Liga 1 |
| --- | --- | --- | --- |
| **A** | 5 % der Siegprämie | 200 € | 65.000 € |
| **B** | 10 % der Siegprämie | 400 € | 130.000 € |
| **C** | Fest 250 € in jeder Liga | 250 € | 250 € |

**Empfehlung: A.** Das Startgeld soll ein Sockel sein, kein zweites
Preisgeld; bei A entspricht es genau dem Anteil für Platz 30 (5 % laut GDD)
und bleibt damit unauffällig. C fällt in höheren Ligen komplett aus der
Skala.

*Nachtrag bei der Umsetzung:* Hier stand zunächst, das Startgeld bleibe
**unter** dem Anteil für Platz 30. Das ist falsch — beide sind 5 %, also
gleich. Der Letzte bekommt damit das Doppelte des Sockels, der Sieger
105 % statt 100 %. An der Entscheidung ändert das nichts.

**Entscheidung: A** (2026-09-17)

### 15. Erfahrung: Grundbetrag, Platzierungs- und Überholbonus

**GDD 10** legt fest: „EP-Beträge = Preisgeld ÷ 10". Offen sind die drei
Bestandteile „Grundbetrag je Session, Platzierungsbonus und Bonus je
Überholmanöver".

| | Variante | Grundbetrag je Session | Platzierung | Je Überholmanöver |
| --- | --- | --- | --- | --- |
| **A** | Platzierung dominiert | 5 % der Sieg-EP | voller Anteil nach Tabelle | 0,5 % der Sieg-EP |
| **B** | Ausgewogen | 15 % der Sieg-EP | Anteil nach Tabelle | 1 % der Sieg-EP |
| **C** | Teilnahme dominiert | 30 % der Sieg-EP | halber Anteil | 2 % der Sieg-EP |

**Empfehlung: B.** Der Spieler startet laut GDD 1 mit allen Werten auf 0 und
wird anfangs Letzter. Bei A bekäme er fast nichts und käme nicht in Gang; bei
C lohnt sich Fahren ohne Ehrgeiz. B gibt einen brauchbaren Sockel und belohnt
trotzdem Plätze. Der Überholbonus von 1 % ist bewusst klein, damit sich
absichtliches Zurückfallen nicht lohnt.

**Entscheidung: B** (2026-09-17)

### 16. Wetter-Erfahrung je Kilometer

**GDD 10:** „eigener Topf je Wetter, nur für die passende Wetterfähigkeit
nutzbar; Verdienst je gefahrenem km im jeweiligen Wetter plus
Platzierungsbonus" – ohne Beträge. Ein Rennen ist 100 bis 290 km lang.

| | Variante | Je km | Nach einem Rennen im selben Wetter (Liga 20, 100 km) |
| --- | --- | --- | --- |
| **A** | 0,05 % der Sieg-EP | 0,2 EP | 20 EP |
| **B** | 0,1 % der Sieg-EP | 0,4 EP | 40 EP |
| **C** | 0,2 % der Sieg-EP | 0,8 EP | 80 EP |

**Empfehlung: B.** Die fünf Wetterfähigkeiten kosten laut GDD 7 zum Teil
Erfahrung; ein voller Renntag im Regen soll spürbar auf „Regenfahren"
einzahlen, aber nicht in einer Saison ausreichen. Bei B kommen über eine
Saison mit rund 4 Regenrennen etwa 160 EP zusammen – genug für die ersten
Schritte, weit weg von 100.000.

**Entscheidung: B** (2026-09-17)

### 17. K₀ je Fähigkeit

**GDD 9:** „je Fähigkeit ist ein eigener K₀-Faktor möglich, damit
Schwerpunkte nötig sind" – ohne Faktoren. Grundwerte sind 50 € und 5 EP.

| | Variante | Aufbau |
| --- | --- | --- |
| **A** | Alle 1,0 | Kein Schwerpunktzwang, alle Fähigkeiten gleich teuer |
| **B** | Nach Wirkungsbreite | Faktor = Summe der Gewichte aus der Wirkungsmatrix ÷ Mittelwert; F1 Motorleistung (8 Punkte) wird teurer als F6 Luftwiderstand (3) |
| **C** | Drei Klassen von Hand | 0,7 / 1,0 / 1,5, je Fähigkeit zugeordnet |

**Empfehlung: B.** Es ist der einzige Vorschlag, der die Absicht aus dem GDD
ohne neue Handarbeit erfüllt: Breit wirkende Fähigkeiten kosten mehr, also
zwingt die Skala zu Schwerpunkten. Die Werte stehen bereits in der
Wirkungsmatrix. A erfüllt die Vorgabe gar nicht, C sind 32 Einzelentscheidungen.

**Entscheidung: B** (2026-09-17)

### 18. Liga-Faktor der Reparaturkosten

**GDD 14:** „Reparatur kostet nur Geld (Stufe × Liga-Faktor)". Die
Kostenstufen 1 bis 3 stehen bei jedem der 20 Defekte, der Liga-Faktor fehlt.

| | Variante | Liga 20, Stufe 1 | Liga 1, Stufe 3 |
| --- | --- | --- | --- |
| **A** | 1 % der Siegprämie je Stufe | 40 € | 39.000 € |
| **B** | 2,5 % der Siegprämie je Stufe | 100 € | 97.500 € |
| **C** | Linear: `(21 − liga) × 200 €` je Stufe | 200 € | 12.000 € |

**Empfehlung: A.** Die Reparatur soll ein Ärgernis sein, keine Existenzfrage:
Bei A kostet der teuerste Defekt 3 % der Siegprämie. Die Kopplung an die
Siegprämie hält das über alle 20 Ligen automatisch im Verhältnis, was C nicht
leistet – dort wären 200 € in Liga 20 die Hälfte einer Siegprämie.

**Entscheidung: A** (2026-09-17)

### 19. Sponsorbeträge

**GDD 10** legt Plätze, Zahl und Laufzeit der Angebote fest, nicht aber die
Vergütung: „Grundbetrag je Rennen plus Prämien für Sieg, Top 3 und Top 10".
Sechs Plätze: Anzug, Helm, Mütze, Auto-Hauptsponsor, zwei Nebensponsoren.

| | Variante | Grundbetrag aller 6 Plätze je Rennen | Prämien (Sieg / Top 3 / Top 10) |
| --- | --- | --- | --- |
| **A** | Zurückhaltend | zusammen 30 % einer Siegprämie | 50 % / 25 % / 10 % des Grundbetrags |
| **B** | Zweite Säule | zusammen 60 % | 100 % / 50 % / 20 % |
| **C** | Tragende Säule | zusammen 120 % | 150 % / 75 % / 30 % |

Aufteilung in allen Varianten: Hauptsponsor 40 %, Nebensponsoren je 15 %,
Anzug/Helm/Mütze je 10 %.

**Empfehlung: B.** Sponsoren sind laut GDD 10 neben dem Preisgeld die zweite
Einnahmequelle und sollen „höhere Ligen bringen bessere Sponsoren und damit
schnellere Entwicklung" leisten. Bei A wären sie eine Randnotiz, bei C würde
das Rennergebnis gegenüber der Sponsorenwahl unwichtig.

**Entscheidung: B** (2026-09-17)

---

## Schritt 10 – Ereignisse

### 20. Geld- und Erfahrungsbeträge der Ereignisse

**GDD 14** nennt bei fünf Ereignissen „einmalig Geld" oder „einmalig
Erfahrung", ohne Betrag: E4 Medienrummel, E7 Sponsorbonus, E14
Sponsorenabend (Geld) sowie E9 Mentor-Tipp und E16 Simulatortag (Erfahrung).

| | Variante | E7 Sponsorbonus | E4 / E14 | E9 / E16 |
| --- | --- | --- | --- | --- |
| **A** | Klein | 10 % einer Siegprämie | 5 % | 5 % der Sieg-EP |
| **B** | Spürbar | 25 % | 10 % / 15 % | 15 % der Sieg-EP |
| **C** | Groß | 50 % | 20 % / 30 % | 30 % der Sieg-EP |

**Empfehlung: B.** Ereignisse treten laut GDD 14 nur 0 bis 2 je 14-Tage-Zyklus
auf, über eine Saison also rund 20-mal für alle 35 Ereignisse zusammen – ein
einzelnes darf daher ruhig auffallen. Bei A merkt man sie nicht, bei C
entscheidet Glück über die Entwicklung. Die Kopplung an die Siegprämie hält
sie über alle Ligen im Verhältnis.

**Entscheidung: B** (2026-09-17)

---

## Zusammenfassung der Empfehlungen

| Nr. | Punkt | Empfehlung | Gebraucht ab |
| --- | --- | --- | --- |
| 1 | Mindestsegmentlänge | A – keine | Schritt 2 (umgesetzt) |
| 2 | Überholschwierigkeit | B – aus Überholzonenanteil | Schritt 4 |
| 3 | Erfolgsformel Überholen | B – logistisch | Schritt 4 |
| 4 | Wetterprofil je Strecke | A – drei Klimaprofile | Schritt 5 |
| 5 | Streckennässe | B – über 3 Runden | Schritt 5 |
| 6 | Fehlerrate | B – 1 je 10 Runden bei 0 | Schritt 6 |
| 7 | Unfallrate | A – 0,02 % | Schritt 6 |
| 8 | Defektrate | B – 5 % | Schritt 6 |
| 9 | Verschleißverlauf | B – progressiv | Schritt 6 |
| 10 | Verschleiß je Strecke | A – Querbeschleunigung | Schritt 6 |
| 11 | Ermüdung | B – ab der Hälfte | Schritt 6 |
| 12 | Preisgeld-Interpolation | A – logarithmisch | Schritt 8 |
| 13 | Preisgeld-Anteile | A – geometrisch | Schritt 8 |
| 14 | Startgeld | A – 5 % | Schritt 8 |
| 15 | Erfahrungsbeträge | B – ausgewogen | Schritt 8 |
| 16 | Wetter-EP je km | B – 0,1 % | Schritt 8 |
| 17 | K₀ je Fähigkeit | B – nach Wirkungsbreite | Schritt 8 |
| 18 | Reparatur-Liga-Faktor | A – 1 % je Stufe | Schritt 8 |
| 19 | Sponsorbeträge | B – zweite Säule | Schritt 8 |
| 20 | Ereignisbeträge | B – spürbar | Schritt 10 |

Vor Schritt 3 ist nichts zu entscheiden. Zwingend vor Schritt 4 sind die
Punkte 2 und 3.


---

## Nachtrag: bei Schritt 5 aufgefallen

Diese vier Angaben nennt das GDD, ohne sie zu beziffern. Sie sind nach
demselben Muster entschieden wie die Punkte 1 bis 20.

### 21. Tempobonus der Trockenroutine

**GDD 7:** „bei Trocken gibt sie einen kleinen Tempobonus" – ohne Zahl. Bei
Trocken gibt es keinen Gripverlust zu dämpfen, die Fähigkeit braucht also
eine eigene Wirkung.

| | Variante | Bonus bei 100.000 |
| --- | --- | --- |
| **A** | Sehr klein | +0,25 % |
| **B** | Klein | +0,5 % |
| **C** | Spürbar | +1,0 % |

**Entscheidung: B.** Ein Drittel dessen, was die Streckenkenntnis maximal
bringt (+1,5 %, GDD 6) – das trifft „klein" und bleibt in der vorhandenen
Größenordnung. Bei C wäre Trockenroutine wertvoller als jede andere
Wetterfähigkeit, weil Trocken die häufigste Lage ist.

### 22. Dämpfung der schlechten Tagesform durch D16

**GDD 11:** „D16 Mentale Stärke begrenzt nur die negative Seite der
Tagesform" – ohne Zahl.

| | Variante | Restliche negative Abweichung bei 100.000 |
| --- | --- | --- |
| **A** | 40 % Dämpfung | 60 % bleiben |
| **B** | 60 % Dämpfung | 40 % bleiben |
| **C** | 80 % Dämpfung | 20 % bleiben |

**Entscheidung: B.** Dieselbe Obergrenze wie bei den Wetterfähigkeiten
(GDD 7: „um bis zu 60 %"). Damit hat die Skala eine einheitliche
Dämpfungsstärke, statt für jede Fähigkeit eine eigene zu erfinden.

### 23. Wirkung von D12 Konstanz auf die Rundenform

**GDD 11:** Streuung 0,3 %, „verkleinert durch D12 Konstanz" – ohne Zahl.

| | Variante | Restliche Streuung bei 100.000 |
| --- | --- | --- |
| **A** | 60 % Dämpfung | 0,12 % |
| **B** | 80 % Dämpfung | 0,06 % |
| **C** | 95 % Dämpfung | 0,015 % |

**Entscheidung: B.** Konstanz ist die einzige Eigenschaft, die überhaupt auf
die Rundenform wirkt; bei A wäre der Unterschied kaum messbar. C würde einen
Spitzenfahrer praktisch zur Maschine machen und die Ebene entwerten.

### 24. Umrechnung der Q-Spalte in Zeit

**GDD 8:** „Im Qualifying wirken alle Tempobereiche wie im Rennen; die
Q-Spalte ist ein zusätzliches Gewicht nur für die gezeitete Runde." Wie aus
dem Gewicht eine Zeit wird, steht nicht da.

| | Variante | Tempobonus bei 100.000 | Wirkung auf eine 1:25-Runde |
| --- | --- | --- | --- |
| **A** | +0,5 % | 0,42 s über die ganze Skala | innerhalb einer Liga kaum messbar |
| **B** | +1,0 % | 0,85 s | innerhalb einer Liga wenige Hundertstel |
| **C** | +2,0 % | 1,70 s | Qualifying-Spezialisten dominieren |

**Entscheidung: B.** Dieselbe Form wie die Streckenkenntnis (ein
Tempobonus mit Obergrenze), in vergleichbarer Größe. Wichtig ist der zweite
Effekt: Innerhalb einer Liga ist die Spanne der Q-Werte schmal – in Liga 1
liegen zwischen Erstem und Letztem nur rund 0,05 % – also entscheidet die
Q-Spalte einzelne Hundertstel, nicht ganze Sekunden. Genau das soll eine
Zusatzspalte leisten.


---

## Nachtrag: bei Schritt 6 entschieden

### 25. Reifenflüsterer — eine Eigenschaft neben den 16 aus GDD 6

**Auf Wunsch neu aufgenommen.** Das GDD kennt D14 Reifenmanagement, das
den Verschleiß senkt. Damit allein fächert das Feld in der zweiten
Rennhälfte nur auf: Wer schneller ist, bleibt schneller.

Der Reifenflüsterer greift an anderer Stelle an — er senkt nicht den
Abbau, sondern dessen **Wirkung**. Ein Fahrer mit hohem Wert holt aus
schlechten Reifen noch Zeit heraus. Erst dadurch kreuzen sich Linien:
Ein Auto, das seine Reifen schont, ist früh langsamer und spät schneller
als eines, das sie verheizt.

| | Variante | Einordnung |
| --- | --- | --- |
| **A** | Als 17. Fahrer-Eigenschaft D17 | Ändert GDD 6 (16 Eigenschaften), die Wirkungsmatrix in GDD 8 und die Prüfung „18 Fähigkeiten mit Geldanteil" aus GDD 9 |
| **B** | Wie die Wetterfähigkeiten: neben der Wirkungsmatrix | Lässt GDD 6, 8 und 9 unberührt; Währung E + Z |
| **C** | D14 aufbohren, sodass es beides tut | Keine neue Eigenschaft, aber beide Wirkungen nicht mehr trennbar |

**Entscheidung: B.** Das GDD führt mit den fünf Wetterfähigkeiten aus
Abschnitt 7 bereits Fahrer-Eigenschaften außerhalb der Wirkungsmatrix —
der Reifenflüsterer reiht sich dort ein, ohne eine einzige bestehende
Zusage zu brechen. C wäre der kleinste Eingriff, verliert aber genau die
Trennung, auf die es ankommt: Abbau bremsen und Abbau ertragen sind zwei
verschiedene Fähigkeiten.

Er lässt sich jederzeit zu einem vollen D17 heraufstufen; dann sind GDD 6,
8 und 9 nachzuziehen.

### 26. Einheit der Unfallrate

Die Entscheidung zu Punkt 7 nannte „0,02 % je Annäherung", ohne die
Bezugsgröße zu nennen. Als Wahrscheinlichkeit **je Zeitschritt** gelesen
fielen bei 50 Schritten je Sekunde und dichtem Feld alle fünf erlaubten
Ausfälle bereits in der ersten Runde.

**Entscheidung: je Sekunde in Reichweite**, nicht je Zeitschritt. Sonst
hinge die Unfallhäufigkeit an der Schrittweite der Simulation statt am
Spiel. Gemessen ergibt das rund 0,5 Unfälle je Rennen — passend zu „sehr
selten" aus GDD 4 und zur ursprünglichen Vorhersage „rund 0 bis 1 Unfall
je Rennen".

### 27. Qualifying: Sessiondauer und Wetter

Ohne Gegenmaßnahme dauerte eine Qualifying-Session 30 × 2 Runden — in Spa
drei Stunden. Das Wetter drehte sich darin mehrfach, und die
Startreihenfolge entschied mehr als die Fahrleistung: Die fünf stärksten
Autos landeten im Schnitt auf **Platz 8,0 von 30**.

Drei Maßnahmen, gemessen:

| Maßnahme | Ø Startplatz der 5 Stärksten |
| --- | --- |
| ohne | 8,0 |
| Wetterwechsel nur in einem Fenster am Sessionanfang | 5,9 |
| dazu höchstens ein Wechsel im Qualifying (15-min-Fenster) | **3,9** |
| gar kein Wetterwechsel im Qualifying | 3,3 |

**Entschieden:** überlappender Start mit 1,25 Runden Abstand (Session
3:00 → 1:47) **plus** 15-Minuten-Fenster und höchstens ein Wechsel. Das
Wetter bleibt damit spürbar, entscheidet aber nicht mehr das Ergebnis.
Alle drei Werte stehen in der Konfiguration.


---

## Nachtrag: bei Schritt 7 entschieden

### 28. Bildung der Teamnamen

**GDD 12** nennt für Teams die Felder (Name, Herkunftsland, Hersteller,
Budget, Teamfarbe), nicht aber, wie die 150 Namen entstehen.

| | Variante | |
| --- | --- | --- |
| **A** | 150 Namen von Hand in der Konfiguration | Volle Kontrolle, 150 Einträge zu pflegen |
| **B** | Aus zwei Teilen zusammengesetzt, per Seed | 75 × 10 = 750 mögliche Namen, austauschbar wie die Herstellernamen |
| **C** | Nach dem Hersteller benannt | Nur 20 Stämme für 150 Teams |

**Entscheidung: B.** Dieselbe Bauweise wie bei den Fahrernamen und aus
demselben Grund ausgelagert: austauschbar, ohne Handarbeit, und per Seed
reproduzierbar wie alles andere in GDD 12.

### 29. Teamfarbe neben der Herstellerfarbe

**GDD 12** gibt Hersteller *und* Team je eine Farbe, sagt aber nicht, wie
sie zusammenhängen. 150 Teams treffen auf 20 Hersteller — nähme man die
Herstellerfarbe unverändert, führen in einer Liga mehrere Autos in
derselben Farbe, und GDD 4 verlangt, die Punkte auseinanderhalten zu
können.

**Entschieden:** Die Teamfarbe leitet sich aus der Herstellerfarbe ab,
in der Helligkeit verschoben. Die Marke bleibt erkennbar, und in jeder
Liga kommen mindestens 20 verschiedene Farben auf 30 Autos.

### 30. Altersspanne und Regionenanteil der Fahrer

**GDD 12** nennt ein Geburtsdatum „vorerst ohne Altern" und die Herkunft
„aus Europa und Nordamerika", ohne Spanne oder Gewichtung.

**Entschieden:** 18 bis 42 Jahre zum Saisonstart, und 10 % der Fahrer aus
Nordamerika — das entspricht dem Verhältnis der hinterlegten Länder (3 von
32). Beide Werte stehen in der Konfiguration.

### 31. Ligastärken zwischen den Stützstellen aus GDD 9

Die Kalibriertabelle nennt nur die Ligen 20, 15, 10, 5 und 1. Für die
übrigen 15 Ligen wird die Stärke über die Tempotabelle bestimmt: Das Tempo
wächst je Liga um 6,32 km/h, der Wert S ergibt sich durch Umkehren der
Kalibrierfunktion. Damit liegen alle 20 Ligen auf derselben Kurve, statt
zwischen den Stützstellen zu springen.

---

## Nachtrag: bei Schritt 9 entschieden

### 32. Verkehr und Überholen im Schnellmodus

**GDD 13** verlangt für die übrigen 19 Ligen einen „Schnellmodus auf
Rundenebene: Qualifying und Rennen mit Wetter, Fehlern, Unfällen und
Defekten in vereinfachter Form" — sagt aber nicht, wie dabei Verkehr
entsteht. Auf Rundenebene gibt es keine Positionen auf der Strecke, an
denen zwei Autos nebeneinander wären.

| | Variante | |
| --- | --- | --- |
| **A** | Überholen prüfen, wenn der Abstand am Rundenende unter 0,05 s liegt | Trifft fast nie zu: zwei Autos können eine ganze Runde nebeneinander fahren und trotzdem 20 s auseinander über die Linie kommen — gemessen 5 Manöver je Rennen gegen 359 in der vollen Simulation |
| **B** | Überholen prüfen, wo sich die Reihenfolge gegenüber der Vorrunde geändert hat | Jeder Positionswechsel braucht einen Wurf nach GDD 4; misslingt er, hängt das Auto knapp hinter dem Vordermann fest |
| **C** | Gar nicht überholen, nur Rundenzeiten addieren | Das Ergebnis wäre die Reihenfolge der Rundenzeiten — Überholschwierigkeit je Strecke und D10/D11 blieben wirkungslos |

**Entscheidung: B.** Angefahren wird von hinten nach vorn — zuerst der
nächste Vordermann, dann der davor —, und beim ersten misslungenen Versuch
ist Schluss: Wer nicht vorbeikommt, erreicht die weiter vorne Fahrenden in
dieser Runde gar nicht mehr.

Nachgemessen bei gleichem Wetter in beiden Modellen (dasselbe wird aus
demselben Zweig der Seedquelle gezogen): Die Siegerzeit im Schnellmodus
weicht auf Zandvoort und Monza in den Ligen 5 und 20 um **−1,2 bis +0,5 %**
von der vollen Simulation ab, die schnellste Runde um **−1,4 bis −0,2 %**.
Ein Test hält die 2-%-Schranke fest. Die *Zahl* der Manöver bleibt
naturgemäß kleiner — in der vollen Simulation zählt jeder Positionstausch
innerhalb einer Runde mit, hier nur das Ergebnis am Rundenende.

Zweite Vereinfachung im selben Sinn: Im Qualifying fahren alle Autos ihre
gezeitete Runde in der Wetterlage zu Sessionbeginn. Der überlappende Start
aus GDD 4 bräuchte eine Uhr über die Session — genau das, was der
Schnellmodus einspart.

### 33. Qualifying-Reihenfolge, wenn kein Vorjahresstand passt

**GDD 4** ordnet die Qualifying-Reihenfolge nach dem umgekehrten
Meisterschaftsstand und nennt für das erste Rennen einer Saison die
Ausnahme: aufsteigend nach durchschnittlicher Qualifying-Fähigkeit.

Offen bleibt, was gilt, wenn eine Tabelle nicht zum Feld passt — nach
einem Auf- oder Abstieg fährt ein Fahrer in einer Liga, deren Wertung ihn
nicht kennt.

**Entschieden:** Dann gilt dieselbe Ausnahme wie im ersten Rennen. Jede
Saison beginnt ohnehin mit leeren Tabellen, sodass Rennen 1 automatisch
unter die GDD-Regel fällt; die Prüfung auf ein unvollständiges Feld ist
das Netz darunter, damit eine Aufstellung nie aus einer halben Tabelle
entsteht.

---

## Nachtrag: bei Schritt 10 entschieden

### 34. Bezugsgröße der dauerhaften Prozentwirkungen

**GDD 14** lässt elf Ereignisse „dauerhaft" wirken, meist mit ±1 %
(E11 D8 +1 %, E32 F1 −0,5 %, E22 Regenfahren +2 %). **GDD 1** lässt den
Spieler aber mit allen Werten auf 0 starten — ein Prozentsatz davon ist
null.

| | Variante | |
| --- | --- | --- |
| **A** | Prozent vom aktuellen Wert | Wörtlich nach GDD 14, in den ersten Saisons aber wirkungslos |
| **B** | max(+10, +1 % vom Wert) | Dieselbe Regel wie ein Entwicklungstag in GDD 2 |
| **C** | Prozent der Referenzskala (98.000) | +1 % wären immer +980 — früh fast 100 Entwicklungstage wert |

**Entscheidung: B** (2026-09-17). Bei abweichenden Prozentsätzen skaliert
der Mindestschritt mit, damit die Ereignisse untereinander im Verhältnis
bleiben: +2 % ergibt mindestens +20, −0,5 % höchstens −5. Gemessen: bei
Wert 0 gibt E11 +10, bei Wert 98.000 gibt es +980.

### 35. Auswahl des Ereignisses

GDD 14 nennt keine Gewichte. **Entschieden:** alle 35 gleich
wahrscheinlich, innerhalb eines Zyklus ohne Zurücklegen — sonst träfe
dieselbe Erkältung zweimal in vier Tagen.

Dazu kommt, was GDD 14 offen lässt: Was ist ein „14-Tage-Zyklus" in der
Vor- und Nachsaison? GDD 2 kennt dort keine Zyklen, zusammen sind sie
aber rund ein Viertel des Jahres. **Entschieden:** Über das ganze Jahr
läuft dasselbe 14-Tage-Raster, verankert am Tag nach dem ersten Rennen.
Jeder Zyklus endet damit genau auf einem Renntag, und sein Auslösefenster
fällt immer in die freien Tage danach. Gemessen: 27 Zyklen, 21 bis 33
Ereignisse je Saison.

### 36. Ereignisse für die KI

**GDD 14** schreibt, Ereignisse „betreffen Spieler und KI gleichermaßen".

| | Variante | |
| --- | --- | --- |
| **A** | Alle 600 Fahrer | Wörtlich nach GDD, rund 24.000 Zustandsänderungen je Saison |
| **B** | Nur die Liga des Spielers | 30 statt 600 Fahrer |
| **C** | Nur der Spieler | Am einfachsten, weicht aber vom GDD ab |

**Entscheidung: C** (2026-09-17, vom Auftraggeber gewählt). Das ist die
einzige Stelle in Schritt 10, an der bewusst vom GDD abgewichen wird; sie
steht in der Konfiguration als `[ereignisse.umfang] gilt_fuer_ki = false`
und lässt sich ohne Codeänderung zurückdrehen.

### 37. Profil über die Wirkungsbereiche

**GDD 12** lässt die Einzelwerte „±25 % um den Mittelwert" streuen und
nennt als Ziel Regenspezialisten, Qualifying-Experten und Reifenschoner.
Gemessen kam davon fast nichts an: Die Simulation rechnet mit den
**Bereichsmitteln** aus GDD 8, und über drei bis fünf Einzelwerte hinweg
mittelt sich die Streuung weg — zwischen dem stärksten und dem
schwächsten Bereich eines Fahrers lagen nur **20 %**.

**Entschieden:** eine zweite Ebene. Je Fahrer wird ein Faktor pro
Wirkungsbereich gezogen (±30 %), den jede Fähigkeit nach ihrer Zeile der
Wirkungsmatrix gewichtet erbt. Darauf kommt das Rauschen aus GDD 12.
Gemessen in Liga 10: Profilspanne **41 %** im Schnitt, bis 58 %; ein
Fahrer ist in drei Bereichen Erster seiner Liga und in anderen Sechster.
Die Wetterfähigkeiten stehen neben der Matrix und streuen für sich mit
±45 %, gemessen 65 % Spanne je Fahrer.

Zwei Dinge halten dabei die Kalibriertabelle aus GDD 9 in Ordnung:

* Die Bereichsfaktoren werden **auf den Mittelwert 1 normiert**. Ein
  Spezialist ist damit eine Frage der *Form*, nicht der Stärke — er
  verteilt seine Ligastärke um, statt mehr oder weniger davon zu haben.
  Ohne das rutschte der schwächste Fahrer einer Liga rund 10 % unter
  seinen Sollwert.
* Das **Kappen an der Skala wird ausgeglichen**. In Liga 1 liegt die
  Stärke nahe am Maximum von 100.000; ohne Ausgleich fielen dort die
  hohen Werte eines Spezialisten weg und sein Mittel sänke um 5 %, also
  gut 3 km/h. Jetzt werden die Werte mit Luft nach oben so weit
  angehoben, dass das Mittel wieder stimmt.

Nachgemessen trifft jede Liga ihre beiden Kontrollwerte aus GDD 9 jetzt
**auf den Punkt** — vorher lagen sie bis zu 4.600 daneben.

Was bleibt: In **Liga 1** drückt die Obergrenze die Profilspanne auf 19 %,
weil dort ein großer Teil der Werte am Anschlag liegt. Das folgt direkt
aus GDD 9 (Ligastärke ~95.000, Skala bis 100.000) und lässt sich nicht
beheben, ohne eine Regel zu erfinden, die das GDD nicht nennt. Der Punkt
ist dem Auftraggeber vorgelegt.

### 38. Lerntempo je Fahrer

**GDD 6** lässt den Kenntniszuwachs streuen (±75 % je Start, ±50 % je
Runde). Beides sind Würfe je Session und mitteln sich weg: Nach 20
Saisons auf derselben Strecke blieben gemessen nur **10 %** Streuung
zwischen den Fahrern übrig.

**Entschieden:** zusätzlich ein festes Lerntempo je Fahrer (±60 %), aus
dem Seed abgeleitet und über die ganze Karriere dasselbe. Damit bleiben
nach 20 Saisons **35 %** Streuung, und der Tempobonus reicht von 0,31 %
bis 1,31 %.

### 39. Streckenkenntnis der KI

**GDD 12** sagt: „Die KI verbessert sich vorerst nicht." Eine wachsende
Streckenkenntnis wäre genau das — über die Saisons würden alle 570
KI-Autos der Kalibriertabelle aus GDD 9 davonlaufen.

**Entschieden:** Der Stand der KI wird einmal bei der Welterzeugung je
Fahrer und Strecke gesetzt und bleibt dann fest. Er steht für alles, was
der Fahrer vor Karrierebeginn dort gefahren ist, und streut deshalb breit
(im Mittel 35 % der vollen Kenntnis, ±80 %). Gemessen in Liga 10 auf
Monza: 152 bis 614 Runden, also 0,23 % bis 0,92 % Tempobonus; derselbe
Fahrer kennt eine Strecke mit 620 Runden und eine andere mit 73. Sobald
`[ki] entwicklung` auf `true` steht, lernt die KI wieder mit.

---

## Nachtrag: beim Editor entschieden

### 40. Sichtbarkeit des Editors

**GDD 15** nennt unter den Balancing-Werkzeugen eine „Debug-Ansicht", sagt
aber nicht, wie erreichbar sie sein soll. Ein Editor kann jede Balance
kippen.

| | Variante | |
| --- | --- | --- |
| **A** | Eigener Reiter | Direkt erreichbar, leicht zu testen |
| **B** | Schalter im Menü | Standardmäßig versteckt |
| **C** | Startoption `--editor` | Am weitesten weg vom normalen Spiel |

**Entscheidung: A** (vom Auftraggeber gewählt).

### 41. Umfang des Editors

**Entschieden:** Die 32 Einzelwerte, die sechs Fähigkeiten neben der
Matrix, die Streckenkenntnis je Strecke **und die Stammdaten** (Vorname,
Nachname, Land, Geburtstag).

**Nicht änderbar bleiben Liga und Team.** Ein Wechsel dort spränge die
Ligastärken aus GDD 9 — jede Liga hat feste Kontrollwerte — und die
Teamgrößen aus GDD 12, wo jedes der 150 Teams genau vier Autos hat. Wer
das will, braucht eine eigene Mechanik mit Gegenbuchung, wie sie der Auf-
und Abstieg schon hat.

### Dabei behoben: Die Entwicklung erreichte das Rennen nicht

Beim Bau des Editors kam heraus, dass `Karriere.werte` und
`welt.spieler.auto.werte` nie zusammengeführt wurden. Der Spieler kaufte
Upgrades, fuhr aber weiter mit Nullen; ebenso blieben Ereignisse und
Defekte aus GDD 14 wirkungslos, obwohl `fahrwerte()` sie korrekt
ausrechnete. Der Kernloop aus GDD 1 war damit seit Schritt 8 ohne Wirkung.

**Behoben** über dieselbe Naht, die der Editor braucht:
`starterfeld(..., autos=...)` ersetzt einzelne Autos, ohne die Reihenfolge
des Feldes zu verschieben. Qualifying und Rennen bekommen ein eigenes
Feld, weil E12 nur im Qualifying wirkt.

---

## Nachtrag: beim GDD-Abgleich geschlossen

Der Abgleich gegen das GDD fand vier Stellen, an denen ein fertiges Stueck
Kern nie aufgerufen wurde. Sie sind keine Entscheidungen, sondern fehlende
Nahtstellen — hier steht, wo sie jetzt liegen.

### 42. Das Rennwochenende erreichte die Karriere nicht

`Karriere.verbuche_rennen()` rechnete Preisgeld, Startgeld,
Sponsorenauszahlung und Erfahrung korrekt aus (GDD 10), wurde aber von
keiner Stelle gerufen. Gemessen: Der Spieler wurde in Sakhir 28., sein
Konto stand danach unveraendert auf 1.000 € und 0 EP.

**Behoben** in `Saisonlauf.fahre_rennen()`. Damit die Buchung die noetigen
Zahlen hat, fuehrt jedes `Ligawochenende` jetzt drei Angaben je Fahrer:
gelungene Ueberholmanoever, im Rennen aufgetretene Defekte und gefahrene
Kilometer je Wetterlage. Der Schnellmodus zaehlt sie beim Fahren mit, die
volle Simulation liest sie aus dem `Rennverlauf` — die Kilometer
abschnittweise zwischen zwei Wetterwechseln, also mit derselben Zuordnung
wie im Schnellmodus, wo jede Runde zu der Lage zaehlt, die zu ihrem Beginn
galt.

Dieselbe Naht schliesst **`uebernimm_defekte()`** (GDD 14): Ein Defekt aus
dem Rennen bleibt jetzt offen, bis der Spieler ihn bezahlt.

### 43. E10 Testfahrt geglückt wirkte nicht

`Karriere.verbuche_runden()` hebt den Kenntniszuwachs der nächsten Strecke
um 20 % (GDD 14), wurde aber nie gerufen: Der Saisonlauf buchte die Runden
über `Streckenkenntnis.verbuche_feld()` für das ganze Feld, am Spieler und
seinen Ereignissen vorbei.

**Behoben:** Der Spieler wird aus dem Feldaufruf herausgenommen und über
die Karriere gebucht — mit demselben Seedzweig wie zuvor, damit derselbe
Seed dieselbe Saison ergibt (GDD 15).

Dabei kam eine zweite Trennung heraus: `Karriere.kenntnis` und die
Streckenkenntnis der Welt waren **zwei getrennte Objekte**. Was der Spieler
lernte, hätte das Rennen nie gelesen. Der Spielstand führte beide beim
Laden schon zusammen; der Saisonlauf tut es jetzt auch, für einen neuen
Spielstand ebenso.

### 44. E3 Motivationsschub wirkte nicht

`Lage.tagesformbonus()` lieferte den Zuschlag, aber `form.tagesform()`
kannte keinen.

**Behoben** über einen Mittelwert-Parameter, der von `simuliere()`,
`qualifying.fahre()` und `fahre_wochenende()` je Auto durchgereicht wird —
so wie der Kenntnisfaktor aus GDD 6. Gesetzt wird er nur beim Spieler: Die
KI hat keine Ereignisse (GDD 12).

**Wie E3 wirkt.** GDD 14 nennt das Ziel „Tagesform-Mittelwert", GDD 11 die
Verteilung (σ 3 %, begrenzt auf ±8 %, schlechte Seite durch D16 gedämpft).

| | Variante | |
| --- | --- | --- |
| **A** | Zuschlag nach dem Wurf | Der ganze Wurf verschiebt sich, Streuung bleibt |
| **B** | Zuschlag vor Grenze und Dämpfung | D16 dämpfte auch den Bonus weg |
| **C** | σ oder Grenze anheben | Änderte die Streuung, die GDD 11 festlegt |

**Entschieden: A.** GDD 14 sagt *Mittelwert*, nicht Spanne. Gemessen über
2.000 Würfe: Mittelwert +0,030, Streuung unverändert.

---

## Nachtrag: beim Saisonwechsel entschieden

### 45. Kalender und Rennwochenende liefen nebeneinander her

GDD 2 beschreibt eine Schleife: „Nach jedem Rennen plant der Spieler, wie
er Zeit, Erfahrung und Geld bis zum nächsten Rennwochenende einsetzt."
Gebaut waren beide Hälften, verbunden waren sie nicht — die Saisonseite
fuhr Rennen, der Karrierekalender blieb stehen. Nach drei Rennen stand
als Datum immer noch der 01.01.2026.

| | Variante | |
| --- | --- | --- |
| **A** | `fahre_rennen()` schaltet den Kalender bis zum Renntag vor | Keine neue Fehlermeldung, ungenutzte Tage verfallen wie in GDD 2 |
| **B** | Das Rennen verweigert sich, solange der Kalender nicht auf dem Renntag steht | Sauber, aber der Spieler muss zwei Reiter in der richtigen Reihenfolge bedienen |
| **C** | Der Renntag schaltet automatisch ins Rennen | Nähme dem Spieler die Entscheidung, wann er fährt |

**Entschieden: A.** GDD 2 sagt ohnehin, dass ein ungenutzter Tag verloren
ist. Das Vorschalten passiert **vor** dem Rennen, damit die Ereignisse der
übersprungenen Tage noch auf es wirken; danach geht es einen Tag weiter,
sonst fände das nächste Rennwochenende am selben Tag statt. Die
Saisonseite warnt vorher in Rot, wie viele nutzbare Tage ein Rennen jetzt
kosten würde.

### 46. Was der Saisonwechsel mitnimmt

**GDD 13** nennt Auf- und Abstieg und eine „Historie aller Saisons und
Ligen", sagt aber nicht, was von einer Karriere ins nächste Jahr wandert.

**Entschieden** (vom Auftraggeber gewählt): Sponsorenverträge, offene
Defekte, laufende Ereignisse und Streckenkenntnis wandern mit; die
Statistiken werden komplett je Saison abgelegt. Dieselben 600 Fahrer, keine
Zu- und Abgänge. Die Karriere ist endlos. Nach Rennen 20 zeigt die
Saisonseite eine Abschlussansicht; ein Knopf „Nächste Saison" bestätigt
den Wechsel.

Daraus folgt, was **nicht** mitwandert: die Saisontabellen, der Kalender
und der Ereignisplan — und die verlorenen Tage aus E29, weil sie Daten des
alten Kalenders sind.

**„Statistiken komplett ablegen"** heißt konkret: `Saisonabschluss` trägt
je Fahrer dieselben Zahlen wie die Saisontabelle — Platz, Punkte, Siege,
Podien, Poles, schnellste Runden, Ausfälle und Rennen. Vorher waren es nur
Reihenfolge und Punkte. Die Tabelle wird beim Wechsel geleert; was dann
nicht in der Historie steht, ist fort.

### 47. Startjahr der ersten Saison

Das Jahr 2026 stand an vier Stellen im Code. **Entschieden:** Es steht
jetzt als `[kalender] startjahr` in der Konfiguration, wie jeder andere
Balancing-Wert auch. Jeder Saisonwechsel zählt eines hoch.

---

## Nachtrag: die neun Eigenschaften aus Punkt 48

Aus der Liste mit 20 Vorschlägen hat der Auftraggeber neun gewählt: **2, 5,
7, 9, 11, 12, 13, 15 und 20**. Alles davon steht über GDD v1.0 hinaus; die
Entscheidungen dazu stehen hier.

### 48. Wo die neuen Eigenschaften leben

Fünf der neun brauchen eine neue Eigenschaft: Windschattennutzung,
Kaltreifen, Materialgefühl, Rhythmus und Bremskühlung.

| | Variante | |
| --- | --- | --- |
| **A** | Neben der Wirkungsmatrix, wie die Wetterfähigkeiten aus GDD 7 | GDD 8 und die Kalibriertabelle aus GDD 9 bleiben unberührt |
| **B** | Neue Zeilen D17–D20 und F17 in der Matrix | Änderte Gesamtwert, Bereichswerte und alle Kontrollwerte aus GDD 9 |

**Entscheidung: A** (vom Auftraggeber gewählt). Die Konfiguration hat dafür
einen eigenen Abschnitt `[[zusatzfaehigkeit.liste]]`; jeder Eintrag nennt
seinen `traeger`. Fahrereigenschaften trägt die Tagesform aus GDD 11 und
sie belegen den Fahrerplatz aus GDD 2, Fahrzeugeigenschaften gehören der
Werkstatt. Gemessen: Die Kalibrierung liegt weiter bei ±0.00.

**Alle neuen Wirkungen liegen hinter `ohne_zufall`** — genau wie Reifen,
Fehler und Streckenkenntnis. GDD 9 kalibriert die freie Einzelrunde, und
die kennt weder Ermüdung noch kalte Reifen noch Windschatten.

### 49. Wen die Heimstrecke trifft

Von 600 Fahrern haben nur **212** ein Land, in dem auch eine Strecke liegt:
Die 20 Strecken verteilen sich auf 17 Länder, die Fahrer kommen aus 32.

| | Variante |
| --- | --- |
| **A** | Wer kein Land mit Strecke hat, bekommt eine aus dem Seed zugelost |
| **B** | Nur die 212 mit passendem Land bekommen eine |
| **C** | Ersatzland über Nachbarschaft |

**Entscheidung: B** (vom Auftraggeber gewählt).

**Wie der Bonus wirkt:** 0,5 bis 1,0 Prozent auf **fünf Eigenschaften**,
die **jedes Rennwochenende neu** gezogen werden (Entscheidung des
Auftraggebers gegen eine feste Auswahl je Fahrer) — aus den 32 der Matrix
**und** denen daneben. Er greift über `welt.starterfeld(..., autos=...)`,
dieselbe Naht, über die auch die entwickelten Werte des Spielers ins
Rennen kommen.

### 50. Wann der Windschatten verbraucht ist

Abgestimmt: Er wirkt **von 30 m bis auf gleiche Höhe**, nur auf Geraden,
und **einmal je Gerade**.

| | Variante |
| --- | --- |
| **A** | Einmal auf gleicher Höhe gewesen heißt: auf dieser Geraden vorbei |
| **B** | Der Sog gilt je Gerade nur eine begrenzte Zeit |

**Entscheidung: A** (vom Auftraggeber gewählt). In der Simulation heißt
„auf gleicher Höhe gewesen" konkret: Das Überholmanöver ist gelungen.
Danach ist der Sog auf dieser Geraden dieser Runde aufgebraucht.

Gemessen an der Kurzprobe aus `--pruefe`: Die Überholmanöver stiegen mit
demselben Seed von 435 auf 486.

### 51. Popularität: gestreut, aber nicht nach Ligastärke

**Entschieden** (vom Auftraggeber): Der Anfangswert streut breit, hängt
aber ausdrücklich **nicht** an der Ligastärke — Bekanntheit ist nicht
dasselbe wie Schnelligkeit. Sie wächst aus Siegen, Podien und Poles und
bewegt den Grundbetrag der Sponsorenangebote um bis zu **±25 %**.

**Dabei entschieden:** Bezugspunkt des Faktors ist der *Mittelwert*, nicht
das Skalenende. Sonst läge das ganze Feld unter 1,0 und die
Sponsorenbeträge aus GDD 10 fielen auf einen Schlag um ein Fünftel.

**Sie sinkt nicht wieder.** Wer eine Karriere lang dominiert, erreicht die
Obergrenze — bei 20 Siegen von der Pole je Saison nach gut einer Saison.
Ein Abbau war nicht Teil der Abstimmung und ist deshalb nicht gebaut.

### 52. Ermüdung: zwei Entscheidungen zusammengeführt

Punkt 11 hatte 2026-09-17 schon entschieden, dass die Ermüdung **erst ab
der halben Distanz** wirkt. Die abgestimmte Tabelle zu Punkt 48 nannte
dagegen 2,0 % bei Wert 0 und 0,3 % bei vollem Wert — vorher standen dort
2,0 % und 0,0 %.

**Zusammengeführt:** Der Beginn bei der halben Distanz bleibt (er war
eigens begründet), die Beträge kommen aus der neuen Tabelle. Ohne den Rest
von 0,3 % wäre der Bereich `er` aus GDD 8 für starke Fahrer wirkungslos.

### 53. Punkt 12 war schon richtig

„Beim Überrunden darf der Überrundende nicht aufgehalten werden."

**Gemessen statt gebaut:** Die Folgeregel aus GDD 4 hängt an der
*zurückgelegten Distanz*, nicht an der Position auf der Strecke. Ein
überrundetes Auto liegt damit eine ganze Rundenlänge zurück und kommt dem
Überrundenden nie in das 0,05-Sekunden-Fenster.

Gemessen mit einem 98.000er Auto gegen neun 10.000er über 12 Runden: neun
Autos fünfmal überrundet, und die Rundenzeiten des Schnellen im Verkehr
sind **auf die Millisekunde identisch** mit seiner Alleinfahrt. Zwei Tests
halten das jetzt fest, damit eine spätere Änderung an der Reihenfolge es
nicht still kaputtmacht.

---

## Nachtrag: Überholmanöver zählen in beiden Rennmodellen gleich

### 54. Woran die Erfahrung aus GDD 10 hängt

Seit Punkt 42 verbucht das Rennwochenende die Erfahrung wirklich — und
damit fiel auf, dass die beiden Rennmodelle „gelungene Überholmanöver"
verschieden messen. Gemessen in Zandvoort (Liga 10, 48 Runden, 30 Autos):

| Zählweise | Manöver | je Auto |
| --- | --- | --- |
| volle Simulation, jeder Vorbeigang | 879 | 29,3 |
| … je Gegner und Runde einmal | 482 | 16,1 |
| … Positionsgewinne je Runde | 301 | 10,0 |
| Schnellmodus | 72 | 2,4 |

576 der 879 Vorbeigänge gehören zu Hin-und-Her-Duellen **innerhalb
derselben Runde**. Der Schnellmodus sieht davon am Rundenende nichts.

| | Variante | |
| --- | --- | --- |
| **A** | Beide Modelle zählen Positionsgewinne je Runde | Keine erfundene Zahl; holt 3,2 der 12 Faktoren |
| **B** | Der Schnellmodus skaliert seine Zahl hoch | Erfundene Konstante, beim nächsten Balancing falsch |
| **C** | Die Erfahrung hängt an den Plätzen zwischen Start und Ziel | Widerspricht GDD 10 („je gelungenem Überholmanöver") |

**Entscheidung: A** (vom Auftraggeber gewählt).

`Rennverlauf.positionsgewinne` zählt je Auto und Runde, wie viele
**fahrende** Gegner, die zu Rundenbeginn vorn lagen, am Rundenende hinter
ihm liegen. Ausgefallene und schon im Ziel stehende Autos zählen nicht:
An ihnen ist niemand vorbeigefahren, sie bleiben nur zurück, während die
anderen weiterfahren. Ohne diese Ausnahme zählte ein 2-Runden-Rennen mehr
Manöver als Vorbeigänge — gemessen 604 gegen 486.

Gemessen für Liga 10, Platz 8: Die Erfahrung liegt jetzt bei 29.756 EP
(ausführlich) gegen 26.796 EP (Schnellmodus) statt 36.786 gegen 26.796 —
der Unterschied fällt von **+37 % auf +11 %**.

**Der Rest ist Verkehrsdynamik, nicht Zählweise.** Der Schnellmodus lässt
je Runde *einen* Überholversuch zu („wer nicht vorbeikommt, hängt fest"),
die volle Simulation einen an jeder Überholzone — im Schnitt sechs je
Strecke. Ihn anzugleichen wäre Schritt B; er würde die Ergebnisse aller
19 KI-Ligen verändern und ist deshalb nicht gebaut.

---

## Nachtrag: die Duellstärke wird wirksam

### 55. Woraus die Erfolgschance beim Überholen kommt

GDD 8 gibt dem Wirkungsbereich `du` sechs Eigenschaften: F8 Bremsanlage,
D7 Geraden, D8 Bremsen (je Gewicht 1), D10 Überholen und D11 Verteidigen
(je 3) sowie D15 Nervenstärke (1). Gelesen wurden bisher nur D10 und D11;
die übrigen vier wurden berechnet und von nichts benutzt. `du` war damit
der letzte Bereich der Matrix ohne Wirkung — `er` ist seit Punkt 48 scharf.

**Umgesetzt:** `erfolgschance` rechnet mit
`bereichswert(angreifer, "du") − bereichswert(verteidiger, "du")` statt mit
`D10(angreifer) − D11(verteidiger)`. D10 und D11 wiegen innerhalb des
Bereichs weiter am schwersten, wie GDD 8 es vorgibt.

**Gemessen und noch offen:** Ein Bereichswert ist ein gewichtetes Mittel
und streut deshalb schmaler als ein Einzelwert. Die Streuung des
Könnens-Terms über alle Paarungen einer Liga:

| Liga | alt (D10 − D11) | neu (du − du) | Verhältnis |
| --- | --- | --- | --- |
| 10 | 9.760 | 5.789 | 1,69 |
| 1 | 16.287 | 10.163 | 1,60 |
| 20 | 72 | 68 | 1,05 |

Das Können entscheidet damit **weniger** über ein Überholmanöver als
vorher, das Tempo mehr. `[ueberholen.erfolg] gewicht_koennen` steht bei
4,0 und wurde laut eigenem Kommentar „in Schritt 4 an einer
Massensimulation nachgezogen" — also gegen den alten Term. Um dieselbe
Wirkung zu halten, müsste er auf rund 6,6 steigen.

| | Variante |
| --- | --- |
| **A** | `gewicht_koennen` bleibt bei 4,0 — das Tempo entscheidet mehr |
| **B** | auf 6,6 anheben — die Wirkung des Könnens bleibt wie vorher |

**Entscheidung: A** (vom Auftraggeber gewählt). Der Wert bleibt bei 4,0.

---

## Nachtrag: Entscheidungen zu den Listenpunkten

Der Auftraggeber hat 17 Punkte gewählt und dazu entschieden:

### 56. Oberfläche und Bedienung

| Frage | Entscheidung |
| --- | --- |
| Diagramme mit `QtCharts` oder `QPainter`? | **`QPainter`** — keine zusätzliche Abhängigkeit für die .exe |
| Startliga im Startdialog frei wählbar? | **Nein, immer Liga 20.** Freie Wahl wäre der Schwierigkeitsgrad durch die Hintertür |
| Geführtes Rennwochenende: neuer Reiter oder Ersatz? | **Die drei Reiter Qualifying, Rennen und Saison werden ersetzt** |
| Wetterbilanz: ganzer Verlauf je Rennen oder eine Lage? | **Die vorherrschende Lage** — eine Spalte je Ergebnis |

### 57. KI-Entwicklung, Newgens und Rücktritt (Punkt 35)

| Frage | Entscheidung |
| --- | --- |
| Wächst die KI absolut oder im Korridor? | **Die Ligen dürfen nicht auseinanderlaufen.** Die Ligastärke bleibt der Korridor aus GDD 9; gewachsen wird innerhalb einer Liga |
| Rücktrittsalter | **Gestreut zwischen 34 und 42** |
| Newgens | **Einer je Rücktritt.** Newgens steigen ganz unten ein (Liga 20); die vorhandenen Fahrer füllen nach oben auf — es gibt dadurch mehr Aufsteiger |
| Altert der Spieler? Endet seine Karriere? | **Sein Alter bleibt fest, die Karriere endet nicht** |

### 58. Boxenstopps (Punkt 39)

Grundsatz: **Der Reifenverschleiß wird je Strecke kalibriert, nicht über die
Renndistanz.**

| Frage | Entscheidung |
| --- | --- |
| Stopps Pflicht oder Wahl? | **Wahl** — aber mindestens einer, weil zwei Mischungen verwendet werden müssen |
| Reifenmischungen? | **Ja.** Verschleiß und Zeitgewinn je Mischung müssen kalibriert werden |
| Boxengassenzeit | **Aus den Streckendaten ableitbar.** Limiter 80 km/h von der Einfahrt bis zur Ausfahrt, danach wird beschleunigt |
| Wie stoppt die KI? | **Ein Fenster mit Streuung** — der eine kommt zu früh, der andere zu spät. Fensterbreite 6 Runden |
| Zahl der Stopps | **1 bis 3, je nach Mischungswahl; mindestens 1.** Keine Stopps in den ersten und letzten drei Runden |
| Mischungsregel | **Zwei Mischungen müssen verwendet werden.** Auch zweimal die weichere und dann die härtere ist erlaubt; die Stintlänge folgt der Mischung, die Wahl der KI streut |

#### Nachträge des Auftraggebers zur Umsetzung

| Frage | Entscheidung |
| --- | --- |
| Wo liegt die Boxengasse? | **Auf der Geraden um Start und Ziel**, abgeleitet aus der Streckengeometrie. 500 bis 750 m auf allen 20 Strecken |
| Obergrenze des Verlusts | **50 % der Rundenzeit, und zwar für die Durchfahrt allein.** Die Standzeit ist Sache der Mannschaft, die Boxengasse Sache der Strecke — sonst würde die Gasse kürzer, nur weil das Reifenwechseln länger dauert. Bei 38 % war der Norisring die Ausnahme (490 m, 47,8 %); bei 50 % fällt sie weg (515 m, 49,6 %) |
| Standzeit | **6 bis 12 Sekunden, gewürfelt.** In der Vorausberechnung wird mit der Mitte (9 s) gerechnet |
| Gripkurve am Anfang | Der frische Reifen startet bei **0,880 Grip** statt 0,940 — doppelt so weit unter dem Optimum — und steigt entsprechend steiler auf 0,970 bei 95 %. Tempofaktor 0,952, Fehlerfaktor 1,063 in der ersten Runde |
| Lage des Optimums | Von 80 auf **85 % Restprofil** verschoben. Anstieg 95→85 steiler, Abfall 85→65 langsamer; die Stützstellen bei 95, 65, 50, 30 und 0 % bleiben unverändert |
| Verschleiß je Mischung | Weich 1,27 · Mittel 0,88 · Hart 0,64 · Intermediate 1,10 · Regen 0,90 |
| Streuung je Rennen | **±0,02 auf den Verschleiß, ±0,002 aufs Tempo**, je Fahrer und Mischung, zwei unabhängige Würfe. Beide **nicht** in der Vorausberechnung — Plan und Rennen laufen bewusst auseinander |
| Mischungsfaktor im Rennen | Gilt jetzt auch dort. Vorher stand er nur in der Vorausberechnung, und weich fuhr im Rennen so schnell wie hart |
| Was kostet ein Stopp? | Durchfahrt **plus** Bremsen bis zum Stillstand **plus** Standzeit **plus** Anfahren aus dem Stand. Bremsen und Anfahren aus den Grenzen dieses Autos: Liga 1 zusammen 1,8 s, Liga 20 gut 17 s |
| Tempo in der Boxengasse | **80 km/h, aber nur wo die Strecke schneller wäre.** Wo sie ohnehin langsamer ist — in den unteren Ligen — gilt ihr eigenes Tempo minus 5 %. Sonst wäre ein Stopp in Liga 20 stellenweise umsonst |
| Reifenwahl des Spielers | **Vor dem Rennen**, nach dem Qualifying, je eigenem Fahrer aus den tragfähigen Varianten. Während des Rennens nicht — der Verlauf wird in einem Stück gerechnet und danach nur abgespielt |
| Reifen im Qualifying | **Keine Wahl, sondern eine Regel**: immer weich, bei wechselhaft Intermediates, bei Regen und Starkregen Regenreifen. Das Wetter des Qualifyings steht fest |
| Mischungen | **Fünf**: Weich, Mittel, Hart, Intermediate, Regen. Weich am schnellsten und kürzesten, Regenreifen im Trockenen deutlich langsamer und schneller hin |
| Gripkurve | **Optimum bei 85 % Restprofil**, nicht bei 100. Steiler Anstieg 100→95, weiter steil bis zum Gipfel bei 85, langsamer Abfall 85→65, ab 60 stärker; nie unter ein Viertel des Startgrips. Die Fehlerquote folgt derselben Kurve |
| Verschleiß je Strecke | **Ja**, nicht mehr je Renndistanz — sonst hielte ein Satz per Konstruktion genau ein Rennen |
| Streuung je Rennen | **±0,002 auf den Verschleißfaktor der Mischung**, je Fahrer und Mischung neu gewürfelt. Steht **nicht** in der Vorausberechnung: geplant wird auf den Sollwerten, gefahren mit der Streuung |
| Mindestrestprofil | **30 %**, auch im Ziel. Gilt für die Vorausberechnung **und** für das Zufallsfenster — vorher hebelte das Fenster die Regel wieder aus |
| Boxenstoppfenster | **±5 % der Rundenzahl, aufgerundet, mindestens ±2 Runden**, solange der Mindestabstand von 3 Runden zwischen zwei Stopps und die 30 % halten |
| Welche Varianten sind zulässig? | Alle, die weniger als die Schwelle hinter der besten liegen: 60 s bei 300 km, 45 s bei 200 km, 30 s bei 100 km. Gerechnet **einmal vor dem Rennen** für das Feld; die Autos wählen daraus zufällig |
| Reihenfolge der Stints | In der Vorausberechnung zählt nur die Zusammenstellung (2×M + 1×H), die Reihenfolge wird im Rennen gewürfelt — solange das Wetter gleich bleibt. Wechselt es, ist die Reihenfolge nicht mehr gleichwertig und wird einzeln gerechnet |
| Vierter Stopp | **Nur als Notausgang**, wenn es mit drei rechnerisch nicht aufgeht |
| Wetterwechsel im Rennen | Höchstens **3 Runden auf dem falschen Reifen**, mindestens **3 Runden zwischen zwei Stopps**. Der Notstopp geht dem geplanten vor und schiebt ihn nach hinten |
| Saisonwetter | Je Streckenprofil ein **Band der Wechselneigung**, jede Saison neu gewürfelt; höchstens zwei Wechsel je Rennen und immer nur eine Stufe. Ziel: 75–85 % der Rennen rein trocken — gemessen 77–79 % |

---

## Nachtrag: die Fahrerkarte

### 59. Wie die Fahrerkarte aufgeht und was darin steht

Der Auftraggeber wollte eine persönliche Karte je Fahrer, „mit allen
Details, Charakter und Statistiken, auch gerne über mehrere Tabs
verteilt". Dazu entschieden:

| Frage | Entscheidung |
| --- | --- |
| Öffnen per Einfach- oder Doppelklick? | **Doppelklick** — der Einfachklick ist schon vergeben (Auswahl steuert Steckbrief und Punkteverlauf). Dazu ein Rechtsklick-Menü, weil man einen Doppelklick nicht sieht |
| Eigenes Fenster oder Reiter? | **Eigenes, nicht modales Fenster** — zwei Fahrer nebeneinander, und während eines Rennens offen zu halten |
| Wann gebaut? | **Vor Block 3** |

Fünf Reiter: Steckbrief, Werte, Saison, Laufbahn, Strecken.

**Zwei Annahmen**, vom Auftraggeber nicht widersprochen: Die Karte zeigt
für alle 600 Fahrer dasselbe — Konto, Sponsoren und Werkstatt des Spielers
bleiben auf ihren eigenen Seiten, sonst gäbe es sie zweimal. Und sie ist
rein lesend; Werte ändern geht weiter nur über den Editor.

### Dabei behoben: Zwei Seiten nannten zwei Alter

Die Weltseite maß das Alter am 1. März des **Startjahrs**, fest verdrahtet.
Nach drei Saisonwechseln stand dort noch immer dasselbe Alter, während die
Fahrerkarte am laufenden Jahr gemessen hätte. `kern.kalender.saisonstart`
ist jetzt der eine Stichtag, und die Weltseite bekommt das laufende Jahr
gereicht — beide nennen dieselbe Zahl.

### Dabei behoben: Die Rangliste im Rennen fand ihren Fahrer nicht

`rennen.Teilnehmer` trug Auto, Startplatz, Farbe und die Spielerkennung,
aber nicht die Fahrernummer aus der Welt — eine Rangliste kennt keine
Fahrer, nur Autos. Ein Doppelklick dort hätte nicht sagen können, wessen
Karte zu öffnen ist. Der Teilnehmer trägt die Nummer jetzt als reines
Anzeigefeld mit; die Simulation liest sie nie, und ein Feld aus
`rennen.starterfeld` hat keinen Fahrer dahinter und behält die 0.

---

## Nachtrag: Block 3

### 60. Zuschnitt des gefuehrten Rennwochenendes (Punkt 12)

| Frage | Entscheidung |
| --- | --- |
| Was fährt der Reiter? | **Das echte Saisonrennen.** Strecke, Rundenzahl, Aufstellung und Seed kommen aus Kalender und Saison; das Ergebnis zählt für Tabelle, Preisgeld, Erfahrung und Streckenkenntnis |
| Freie Wahl von Strecke, Liga, Runden, Seed, Aufstellung | **Ganz weg.** Zum Kalibrieren bleiben `--pruefe` und die Werkzeuge unter `werkzeuge/` |
| Knopf „Rennwochenende" auf der Saisonseite | **Verschwindet.** Gefahren wird nur noch geführt; „Restliche Saison" bleibt für den Rest des Jahres |
| Ersetzt der Reiter auch die Saisonseite? | **Nein.** Nur Qualifying und Rennen verschwinden, Saison bleibt eigener Reiter |
| Startdialog (Punkt 11) | **Name, Land, Geburtstag.** Startliga fest 20, kein Seed-Feld — der Seed bleibt im Kopf des Fensters, wo er schon steht |

### Dabei behoben: Schon das Aufschlagen des Reiters kostete Zeit

Der erste Entwurf baute den `Wochenendlauf` samt Kalendersprung im
Konstruktor. Damit schaltete das Öffnen des Fensters den Kalender auf den
Renntag vor — 56 nutzbare Tage weg, nur weil man hingesehen hat, und die
Testreihe lief in ihr Zeitlimit. Der Aufbau ist jetzt eine reine Vorschau;
erst `fahre_qualifying` beginnt das Wochenende.

### 61. Kleinigkeiten in Block 3, selbst entschieden

Vom Auftraggeber nicht widersprochen; hier festgehalten, damit sie nicht
untergehen:

| Sache | Entscheidung |
| --- | --- |
| Zahl der Autosave-Stände | **Einer**, der überschrieben wird. Ein mitwachsender Autosave füllte nach zwanzig Saisons das Verzeichnis |
| Ort der automatischen Stände | **`~/.rennmanager`** — für Stände ohne Dialog braucht es einen Platz, den das Spiel kennt. Von Hand gespeicherte Stände bleiben unberührt |
| Was die Fahrersuche durchsucht | **Die ganze Zeile** (Name, Kürzel, Liga, Team) — so findet „Rosskamp" auch ein ganzes Team. Fahrertreffer stehen aber vorn |
| Wohin die Suche springt | **In die Fahrerkarte** des Treffers |

### 62. Zuschnitt von Block 4

| Frage | Entscheidung |
| --- | --- |
| Wo stehen Strecken- und Wetterbilanz? | **An beiden Stellen** — in der Fahrerkarte je Fahrer, auf der Statistikseite als Vergleich über alle 600 |
| Zählt die Bilanz über Ligen zusammen oder getrennt? | **Zusammen, dazu die beste Liga** — eine Zeile je Strecke, mit der stärksten Liga, in der dort ein Podium gelang |
| Was gehört auf die Rekordseite? | **Strecken-, Karriere- und Saisonrekorde** |

Vom Auftraggeber nicht widersprochen und hier festgehalten:

* Die Bilanz wird für **alle 600 Fahrer** geführt, nicht nur für den
  Spieler. Sie kostet nichts extra, und die Fahrerkarte zeigt schon heute
  für jeden dasselbe.
* Gespeichert werden **Summen**, keine Rennliste — sonst wüchse der
  Spielstand mit jeder Saison weiter (240.000 statt 15.000 Zeilen).
* Die Siegquote unter den Bestmarken zählt erst **ab 20 Rennen**.

**Bekannte Einschränkung:** Spielstände älter als Version 5 haben keine
Bilanzdaten, und sie lassen sich nicht nachbilden — die einzelnen Rennen
von damals sind nirgends aufgehoben. Die Bilanz fängt dort bei null an.

### Dabei behoben: Der Autosave überschrieb sich unter Windows nicht

Der Windows-Lauf meldete nach Punkt 17 einen Fehler: Der zweite Autosave
enthielt noch den Stand vom Vortag. Ursache war nicht der Autosave, sondern
`rennmanager.kern.spielstand`: `with sqlite3.connect(...)` **committet nur,
es schließt nicht**. Die Datei blieb offen, und das `unlink` am Anfang von
`speichere` scheiterte unter Windows an der offenen Verbindung — unter Linux
nicht, dort lässt sich eine offene Datei löschen.

Alle drei Verbindungen schließen jetzt ausdrücklich. Ein Test zählt die
Verbindungen selbst mit, damit der Fehler auf jedem System auffällt und
nicht nur im Windows-Lauf.

### 63. Bestmarken je Liga

Auf Wunsch des Auftraggebers: Die Bestmarken lassen sich zwischen
**insgesamt** und **je Liga** umschalten — als Auswahlliste mit zwei
Pfeilen zum Durchschalten.

In der Ligaansicht kommen die Karrierezahlen aus der Historie statt aus
`statistik.karriere`: Letztere rechnen alles zusammen und wissen nicht, in
welcher Liga ein Sieg fiel. Ein erster Entwurf zählte die *heutigen* Fahrer
einer Liga mit ihrer ganzen Karriere — dabei standen bei „meiste Siege in
Liga 14" und „meiste Siege in einer Saison, Liga 14" zwei verschiedene
Namen. **Bekannte Einschränkung:** Die Ligaansicht zählt nur
abgeschlossene Saisons; die laufende steht noch in den Tabellen.

### 64. Windschatten: Nachlauf und Ueberrunden

Auf Wunsch des Auftraggebers wirkt der Sog nicht mehr nur im Fenster von
30 m bis auf gleiche Höhe:

* Wer vorbei ist, behält den **Überschuss noch 50 m in voller Höhe** und
  danach zur **Hälfte bis zum Anbremsen** derselben Geraden. Ohne das fiel
  ein Auto genau in dem Augenblick, in dem es vorbei war, auf sein freies
  Tempo zurück — und der Überholte klebte wieder dran.
* Der **Überholte** bekommt auf derselben Geraden die Hälfte dessen, was
  der Überholende in der zweiten Stufe hat, und das erst ab dieser Stufe;
  während der ersten 50 m gar nichts.
* Die Nähe wird für den Sog jetzt an der **Position auf der Runde**
  gemessen, nicht an der gesamt gefahrenen Strecke. Vorher konnte ein
  Überrundender nie im Sog eines Überrundeten fahren, weil zwischen beiden
  rechnerisch eine ganze Runde lag. Verkehr, Überholen und Unfälle rechnen
  weiter auf der Gesamtdistanz — so hat es der Auftraggeber entschieden
  („nur der Sog, kein Verkehr").

Gemessen über 10 Rennen mit 20 gleich starken Autos: 16,7 % weniger
Manöver, weil ein Überholmanöver jetzt hält statt sofort zurückgedreht zu
werden. Über 5 Rennen mit einem schnellen und elf langsamen Autos wirkte
der Sog 377.443-mal; davon 2.344-mal für einen Überrundenden und nur
129-mal für einen Überrundeten (0,03 %, Messartefakt der
Positionstausche innerhalb eines Zeitschritts).

### 65. Der Zieleinlauf stand auf dem Kopf

Die Rangliste im Rennen sortierte allein nach zurückgelegter Strecke. Das
geht, solange gefahren wird — danach nicht mehr: Wer im Ziel ist, **steht**,
alle anderen fahren weiter bis zur Linie. Am Ende hatte ausgerechnet der
Letzte die größte Strecke und stand oben.

Gemessen: In **10 von 10** Rennen wich die angezeigte Reihenfolge am Ende
von der Wertung ab, in allen zehn stand der falsche Sieger vorn.

Sortiert wird jetzt wie die Wertung: absolvierte Runden absteigend, dann
Zielzeit aufsteigend, und wer im Ziel ist, steht vor allen, die noch
fahren. Die Abstände stehen fest, sobald beide über der Linie sind —
sie werden nicht mehr aus Strecke und Tempo geschätzt.

### 66. Entwicklung: Zeit kostet Erfahrung, ein Platz hält bis zum Rennen

Zwei Entscheidungen des Auftraggebers:

* **Alles, was Zeit kostet, kostet auch etwas Erfahrung.** Die Zeit bleibt
  ein Tag und skaliert nicht; die Erfahrung wächst über dieselbe Kurve wie
  Geld, also mit jedem Kauf. Wer schon Erfahrung zahlt, zahlt nicht
  doppelt (`k0_erfahrung_zeit = 2.0` gegen `k0_erfahrung = 5.0`).
* **Ein belegter Platz bleibt bis zum nächsten Rennen belegt**, nicht nur
  für einen Tag. Vorher ließ sich an jedem Tag des Abstands ein weiterer
  Schritt belegen; jetzt gibt es je Abstand einen Trainings- und einen
  Werkstattschritt. Das verlangsamt die Entwicklung über Zeit deutlich —
  so gewollt.

### 67. Ereignisse liefen viermal so schnell ab

`verbuche_rennen` zählte am Ende `lage.nach_rennwochenende()`, und die
Saison ruft es **je eigenem Fahrer** auf. Mit vier Autos in derselben Liga
lief damit jedes Ereignis viermal so schnell ab. Die Lage gehört dem Team,
also zählt jetzt nur der erste Aufruf je Rennen.

Die Sponsorenverträge bleiben davon unberührt: Sie sitzen auf dem Auto
**eines** Fahrers (`vertraege_je_fahrer`) und zählen deshalb zu Recht mit
jedem seiner Rennen herunter. Nachgemessen: Ein Vertrag über 16 Rennen
zahlt genau 16-mal.

### 68. Das Kassenbuch und die Finanzseite

Auf Wunsch des Auftraggebers eine Seite mit allen Ein- und Ausgaben,
gruppiert nach Haupt- und Unterkategorien. Das Konto kannte bisher nur
einen Stand; woher er kam, stand nirgends. `kern.kassenbuch` schreibt
deshalb jede Geldbewegung mit — Datum, Betrag, Kategorie, Fahrer.

Entschieden: Das Buch reicht über die **ganze Karriere** (die Seite blendet
auf Wunsch auf eine Saison ein), und das **Teambudget des Spielers** zahlt
sich in zwölf Monatsraten aufs Konto aus, je eine am Monatsersten, auch in
Vor- und Nachsaison. Die Budgets der KI-Teams bleiben reine Anzeige.

Ein Test misst die Vollständigkeit, nicht einzelne Beträge: Der Saldo
aller Buchungen muss den Kontostand ergeben. Fällt eine Buchung aus, fällt
der Test.

**Bekannte Einschränkung:** Spielstände vor Version 8 laden mit leerem
Kassenbuch und ohne Teambudget. Die Buchungen von damals sind nirgends
aufgehoben, und ein nachträglich erfundenes Buch wäre gelogen.

### 69. Der Zeitenmonitor zeigte das Rennende

Der Monitor las `protokoll.letzte_runde_ms` und `beste_runde_ms` — beides
Werte vom **Rennende**, unabhängig davon, wo das Abspielen gerade steht.
Deshalb stand dort immer eine Zeit, die noch gar nicht gefahren war.

Das Rundenprotokoll führt jetzt `rundenende_ms` mit, also den Zeitpunkt
jeder Rundenankunft; `stand_zu(zeit)` liefert daraus letzte Runde, beste
Runde und die Sektorzeiten der letzten Runde. Sortiert wird nach der
besten Runde, und die letzte Runde leuchtet grün auf, wenn sie zugleich
die beste dieses Fahrers war.

### 70. Rangliste: gewonnene und verlorene Plätze

Auf Wunsch des Auftraggebers eine Spalte „+/-" mit grünem Pfeil nach oben
oder rotem nach unten und der Zahl der Plätze daneben — die Farbe ist nie
die einzige Auskunft.

Verglichen wird gegen die Reihenfolge **zu Beginn der laufenden Runde des
Führenden**. Ein fester Bezugspunkt fürs ganze Feld: Nähme jedes Auto seine
eigene letzte Rundenankunft, verglichen dreißig Zeilen dreißig
verschiedene Augenblicke, und die Pfeile widersprächen sich. In der ersten
Runde bleibt die Spalte leer — da gibt es nichts zu vergleichen.

### 71. Die Sponsorenseite bekommt eine Fahrerwahl

Die Sponsoren sitzen auf den Plätzen **eines** Autos, und jedes Auto gehört
seinem Fahrer (`vertraege_je_fahrer`). Die Seite zeigte aber immer nur die
Verträge des gerade eingestellten Fahrers; an die der anderen drei kam man
nur über die Karriereseite. Jetzt steht oben dieselbe Fahrerwahl wie dort.

Vom Auftraggeber bestätigt: Vier Autos, vier Sponsorensätze, vier
Auszahlungen je Rennwochenende — das ist so gewollt.

### 72. Das Rennen läuft erst los, wenn man hinschaut

`zeige_verlauf` startete die Wiedergabe sofort. Im geführten Wochenende
steht der Spieler zu diesem Zeitpunkt aber noch beim Qualifying; bis er
auf den Rennreiter wechselte, war das Rennen im Zeitraffer durchgelaufen
und stand am Ende. Die Wiedergabe wartet jetzt auf `showEvent`.

### 73. Fehler kostet Zeit im Stand, nicht als Abzug

Nachgemessen: Das Modell hielt das schon so — `pause_ms` setzt das Tempo
auf 0, und danach beschleunigt das Auto über seine eigene
Beschleunigungskurve wieder an (gemessen 1,3 → 2,6 → 3,9 km/h). Geändert
wurde nur die Zeit selbst: Sie war zwischen 500 und 2000 ms gewürfelt und
ist jetzt **fest** bei 1250 ms — dem Mittelwert der alten Spanne, damit
der Erwartungswert bleibt, wo er war.

Was ein Fehler wirklich kostet, ist mehr als diese Zahl: Das Anfahren
kommt obendrauf.

### 74. Rückstand und Intervall an festen Messpunkten

Beide Spalten wurden aus Strecke geteilt durch Tempo geschätzt und
schwankten entsprechend — zwei Autos an verschiedenen Streckenpunkten
sind verschieden schnell. Auf Wunsch des Auftraggebers stehen dort jetzt
**echte Zeiten**:

* Je Runde acht **Messpunkte**: die vier Splits (Start/Ziel und die drei
  Sektorgrenzen) und dazwischen je einer in der Mitte, der selbst kein
  Split ist.
* An jedem hält die Simulation die Uhrzeit fest, interpoliert zwischen
  zwei Zeitschritten — dieselbe Rechnung wie bei den Sektorzeiten.
* Der Abstand zweier Autos ist die Differenz ihrer Zeiten am letzten
  Messpunkt, den das **hintere** passiert hat.

Damit summieren sich die Intervalle genau zum Rückstand. Gemessen an
sechs Autos: 0,137 + 1,022 + 0,053 + 0,726 + 0,163 = 2,101 s, und genau
2,101 s steht als Rückstand des Sechsten. Vorher waren es fünf Intervalle
zu 11,6 s gegen 9,0 s Rückstand.

**Ein Minus ist möglich und richtig so.** Zwischen zwei Messpunkten liegt
rund ein Achtel Runde. Wer in dieser Zeit vorbeigeht, war am letzten
gemeinsamen Punkt noch hinten; dann steht dort ein negativer Wert.
Gemessen kam das in 11,6 % der Bilder vor, vor allem in der ersten Runde,
wo der einzige gemeinsame Punkt die Startlinie ist und die Zeiten dort
noch die Startaufstellung tragen. Geglättet wird nichts — so verlangt.

### 75. Ereignisse treffen einzelne Fahrer

Die Karriere führte **eine** Lage fürs ganze Team; jedes Ereignis wirkte
damit auf alle vier Autos zugleich. Jetzt führt jeder Fahrer seine eigene
(`lage_je_fahrer`), und ein ausgelöstes Ereignis trifft **einen**,
gewürfelt aus der Seedquelle der Saison — derselbe Seed ergibt dieselbe
Saison (GDD 15).

Die Meldung nennt den Namen des Getroffenen. Weil die ersten Ereignisse
auf den 1. Januar fallen und damit beim Start der Karriere entstehen —
bevor die Oberfläche die Namen reichen konnte —, benennt
`benenne_fahrer` schon geschriebene Meldungen nachträglich.

**Spielstand:** Die Tabellen `ereignis` und `meldung` tragen jetzt eine
Fahrernummer. Ein Stand vor Version 8 hat `-1`; dessen Ereignisse
gehörten dem ganzen Team und wandern auf den damals gewählten Fahrer.

### 76. Rennseite neu aufgeteilt, Live-Meisterschaft

Rangliste und Zeitenmonitor stehen **nebeneinander**, die Zwischenfälle
als Fußleiste darunter. Vorher lagen alle drei untereinander in einer
schmalen Spalte; die Rangliste hat seit Punkt 60 zwölf Spalten und
braucht Breite.

Unter dem Zeitenmonitor liegt ein zweites Blatt **Meisterschaft**: der
Stand bis zu diesem Rennen plus die Punkte, die jeder Fahrer für seine
derzeitige Position bekäme — samt Qualifying und schnellster Runde
(GDD 13). Grüner Pfeil hoch, roter runter, daneben die Zahl der Plätze;
eine eigene Spalte zeigt mit „+x", wie viel aus diesem Rennen dazukommt.

Eine **vorübergehende** Ansicht zum Abspielzeitpunkt: `livewertung`
rechnet nur und lässt die Tabelle unberührt. Fortgeschrieben wird der
Stand erst am Rennende, und zwar vom Saisonlauf.

### 77. Der Testlauf hing an einem Meldungsfenster

Beim Entschlacken fiel auf, dass der Lauf nicht langsam war, sondern
**stand**: Der Prozess wartete in `poll_schedule_timeout` bei null
Prozent CPU — gemessen 19 Minuten, ohne Ausgabe und ohne Fehler.

`QMessageBox.information` öffnet eine eigene Ereignisschleife und wartet
auf einen Klick. Im Offscreen-Lauf klickt niemand. Ausgelöst hatte es
eine Verkleinerung des Rennkalenders: Mit drei Rennen je Saison war die
Saison im Test zu Ende, und die Karriereseite meldete „Kein Rennen mehr".
In der Oberfläche stehen **22** solcher Dialoge; jeder kann das.

Ein `autouse`-Fixture in `conftest` ersetzt `information`, `warning`,
`critical`, `question` und `about` im Test durch No-Ops. Damit kann kein
Dialog den Lauf mehr anhalten, unabhängig davon, was ihn auslöst. Wer
eine Meldung prüft, hebt die Ersetzung für seinen Test auf.

**Was verkleinert wird und was nicht.** `verkleinert()` nimmt alle vier
Größen als Parameter — Ligen, Autos je Liga, Rennen je Saison,
Renndistanz. Voreingestellt schrumpfen nur die ersten beiden:

| Größe | Voreinstellung | Gemessen | Warum nicht kleiner |
| --- | --- | --- | --- |
| Ligen × Autos | 3 × 4 statt 20 × 30 | 54,27 s → 1,45 s je Wochenende | — |
| Rennen je Saison | 2 statt 20 — erstes und letztes | 18:33 → 11:33 im ganzen Lauf | Zwei zeigen beides: dass Punkte sich summieren und dass eine Saison endet |
| Renndistanz | echt (100 km) | 24,5 s → 8,8 s bei 30 km | Bei sechs Runden trägt kein Boxenstopp; die Reifenstrategie findet keine Variante, fünf Tests fallen aus |

Dass die Saison im Test wirklich zu Ende geht, ist gewollt; die Dialoge,
die das meldeten, fängt das Fixture oben ab. Zwei Dateien brauchen mehr:
`test_bilanz.py` summiert über vier Rennen, und die Fahrerkarte zeigt den
Punkteverlauf der **laufenden** Saison — nach dem letzten Rennen gehört er
der Historie und das Diagramm ist leer. Beide fordern ihren Kalender
selbst an: `verkleinert(rennen=4)`.

Mitgewachsen ist auch der Auf- und Abstieg. Drei von dreißig sind ein
Zehntel; blieben es drei, müsste bei vier Autos derselbe Fahrer zugleich
auf- und absteigen, und der Saisonwechsel bräche mit genau dieser Meldung
ab. `verkleinert()` rechnet denselben Anteil aufs kleine Feld: einer hoch,
einer runter. Dasselbe gilt für `rennen.autos` — dieselbe Zahl wie
`ligen.autos_je_liga`, nur aus dem Blickwinkel des einzelnen Rennens;
blieb sie auf 30, rechneten Preisgeld und Wertung mit einem Feld, das gar
nicht antrat.

Die getesteten Regeln sind größeninvariant: Auf- und Abstieg,
Punktevergabe und Tabellensortierung stimmen mit drei Ligen zu je vier
Autos genauso. Wo die Größe selbst Gegenstand ist — die Ligastruktur über
zwanzig Stufen, oder die Frage, ob sich ein Nachname mit einem Teamnamen
überschneidet —, steht `kf.lade()` daneben.

**Nicht das Feld war teuer, sondern die Wiederholung.** Der zweite Blick
galt den Laufzeiten je Test. `test_rennanzeige.py` rechnete in einem
`function`-Fixture siebzehnmal **denselben** Vierrundenlauf — gemessen
4,85 s je Test, 82 s für nichts. Der Lauf steht jetzt in einem
`module`-Fixture und wird je Test nur noch **gezeigt**; die Seite bleibt
frisch, damit kein Test die Anzeige des nächsten verstellt. Dieselbe
Doppelung steckte in den Stoppläufen (zweimal derselbe Lauf mit
Mischungspflicht), in `test_boxenstopp_rennen.py` (Reifen und Mischung)
und in `test_reifenwahl.py` (zwei Tests, je ein eigenes Wochenende).

| Datei | vorher | nachher |
| --- | --- | --- |
| `test_rennanzeige.py` | 141,6 s | 60,7 s |
| `test_reifenwahl.py` | ~40 s | 25,4 s |
| `test_boxenstopp_rennen.py` | 126,2 s | 117,6 s |

`test_rennanzeige.py` bleibt dabei bewusst auf der **großen** Welt: Vier
Runden mit dreißig Autos bringen 18 Zwischenfälle und zwei Überrundete,
dieselben vier Runden mit vier Autos nur zwei Zwischenfälle und keinen
Überrundeten — der Ticker und die Achse des Rückstandsdiagramms hätten
nichts mehr zu zeigen, und zwei Tests übersprangen sich still. Ein
dritter,
`test_ohne_strategie_bleibt_die_mischungsspalte_leer`, ist ersatzlos
entfallen: Er übersprang sich in **jeder** Größe, weil jeder Verlauf
Mischungen trägt.

**Was das kleine Feld aufgedeckt hat.** Drei Fehler, die in der großen
Welt nur niemandem auffielen:

* **Die Karte des Spielers ging nicht auf.** `verbinde_fahrerkarte`
  prüfte die Fahrernummer mit `if nummer:` — und der Spieler hat die
  Nummer **0**. Doppelklick und Rechtsklick auf seine eigene Zeile taten
  deshalb nichts. In der großen Welt stand er selten in der ersten Zeile,
  im kleinen Feld immer. Jetzt gilt `is not None`. Dieselbe Verwechslung
  saß in der Rangliste des Rennens: Dort heißt 0 „kein Fahrer dahinter",
  weil ein Feld aus `rennen.starterfeld` keine Fahrer hat — das ist jetzt
  daran erkennbar, dass **alle** die 0 tragen, und nicht mehr an der
  einzelnen Null.
* **Die Gripkurve und ihre Tests liefen auseinander.** Das Optimum steht
  seit dem Umbau bei 85 % Restprofil, vier Tests prüften weiter 80 %. Sie
  fielen seitdem durch; niemand hatte sie nachgezogen. Die Tests lesen die
  Stützstellen jetzt aus der Konfiguration, statt die Zahlen zu wiederholen.
* **Ohne Erfahrung ging am 1. Januar gar nichts.** Seit Punkt 66 kostet
  jeder Zeitkauf Erfahrung (2 EP für den ersten). Zu Saisonbeginn hatte
  der Spieler 0 EP, und Erfahrung gibt es nur fürs Fahren — bis zum ersten
  Rennen ließ sich kein einziger Tag belegen. Entscheidung des
  Auftraggebers: **ein Sockel von 20 EP zum Start**, als
  `kosten.startkapital_erfahrung` neben dem Startkapital. Das trägt eine
  Handvoll erster Schritte; ab dem ersten Rennen spielt er keine Rolle
  mehr (Platz 12 bringt 243 EP, ein Sieg 775).

### 78. Wer seine Reifen aufbraucht, muss herein

Der Messlauf über fünf Strecken sollte nur zeigen, wie sich ein Feld der
Liga 1 auf Mischungen und Stintlängen verteilt. Er zeigte etwas anderes:
In jedem Rennen kamen drei bis vier Autos **ohne einen einzigen Stopp**
ins Ziel — obwohl bei Trockenheit ein Pflichtstopp mit Mischungswechsel
gilt.

**Der Plan war nicht das Problem.** Verfolgt man ein solches Auto —
Zandvoort, VE1, das schwächste des Feldes —, dann hatte es sehr wohl drei
Stopps geplant: Runden 16, 33, 50, Folge M‑H‑M‑H. Es erreichte Runde 16
nie. Sein Satz stand ab Runde 9 bei 0,000 Restprofil, und auf blankem
Gummi sank das Tempo auf **16 km/h**. In 57 Minuten legte es 15 Kilometer
zurück; das Rennen war vorbei, bevor die geplante Stopprunde kam.

Die Regel dahinter: `notstopp()` fragte ausschließlich nach dem Wetter.
Ein Reifen, der sich selbst zerstörte, war kein Grund hereinzukommen.

**Entscheidung des Auftraggebers:** unter 30 Prozent Restprofil herein,
aber nicht mehr in den letzten drei Runden. Das steht als
`boxenstopp.strategie.notstopp_ab_restprofil = 0.30` in der
Konfiguration — dieselbe Zahl wie `mindest_restprofil`, und das ist kein
Zufall: Der Planer legt die Stints so, dass am Stintende noch 30 Prozent
übrig sind. Wer darunter fällt, ist aus dem Plan gefallen.

`notstopp_verschleiss()` in `strategie.py` prüft nur zwei Dinge — das
Restprofil und den Mindestabstand von drei Runden zum letzten Stopp. Die
Mischung spielt keine Rolle: Gebraucht wird ein **frischer** Satz, nicht
ein passender. Die Sperre der letzten Runden hält der Aufrufer ein; sie
stand vorher als letzte Bedingung in der Wetterprüfung und steht jetzt
davor, damit sie für beide Gründe gilt.

**Der Schnellmodus musste mit.** `schnellsimulation.py` führt dieselbe
Rechnung getrennt, und nur die Liga des Spielers wird voll gefahren — die
anderen neunzehn laufen schnell. Stünde die Regel nur in `rennen.py`,
führen zwanzig Ligen nach zwei verschiedenen Regelwerken. Drei Tests in
`test_modi.py` fielen genau deshalb durch, und das war der richtige
Alarm: Sie prüfen, dass beide Modelle dasselbe Rennen fahren.

**Gemessen danach**, wieder Liga 1, 30 Autos, Weltseed 1, nur trocken
oder heiß:

| Strecke | Faktor | Runden | Stopps | davon Zwang | je Auto | Restprofil beim Stopp (25/Median/75 %) | Ohne Stopp im Ziel |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Zandvoort | 1,263 | 69 | 107 | 26 | 2–5 | 25,0 / **35,4** / 58,8 | 0 |
| Sao Paulo | 1,132 | 69 | 75 | 6 | 1–3 | 35,8 / **46,8** / 58,1 | 0 |
| Nürburgring | 1,074 | 58 | 90 | 13 | 1–5 | 31,9 / **36,0** / 52,2 | 0 |
| Silverstone | 0,890 | 51 | 78 | 6 | 2–3 | 35,6 / **43,1** / 54,2 | 0 |
| Monza | 0,537 | 51 | 49 | 3 | 1–2 | 47,5 / **55,1** / 69,9 | 0 |

Die letzte Spalte ist der Punkt: vorher drei bis vier je Rennen, jetzt
keiner. Die vier schwächsten Autos in Monza stoppen jetzt in Runde 6 bis
12 statt gar nicht. Und die Zahl der Zwangsstopps folgt sauber dem
Streckenfaktor — 26 auf der härtesten Strecke, 3 auf der mildesten.

**Was dabei auffiel und nicht entschieden ist.** Auf einen Zwangsstopp
folgt sechs bis neun Runden später oft der ohnehin geplante Stopp — und
der wirft dann einen Satz weg, auf dem noch 72 Prozent Profil sind:

| Strecke | Stopps | verworfene Sätze | davon ohne Mischungswechsel |
| --- | --- | --- | --- |
| Zandvoort | 107 | 22 | 14 |
| Nürburgring | 90 | 9 | 5 |
| Silverstone | 78 | 2 | 0 |
| Sao Paulo | 75 | 1 | 1 |
| Monza | 49 | 0 | — |

Gegen genau das gibt es schon eine Regel: `planstopp_ab_restprofil = 0.75`
verschiebt einen geplanten Stopp, solange der Satz besser als 75 Prozent
ist. Ein Satz, der nach sieben Runden bei 72 Prozent steht, rutscht knapp
darunter durch. Auf Zandvoort sind das 22 von 107 Stopps, 14 davon ohne
jeden Mischungswechsel — also rund 25 Sekunden für nichts.

**Entscheidung des Auftraggebers:** Die Schwelle geht auf **0,65** — ein
geplanter Stopp wird also verschoben, bis der Satz unter 65 Prozent
fällt. Gemessen mit demselben Werkzeug, denselben fünf Strecken und
demselben Weltseed:

| Strecke | Stopps | davon Zwang | Planstopp nach Zwang | Rest dabei | davon ohne Mischungswechsel |
| --- | --- | --- | --- | --- | --- |
| Zandvoort | 107 → **104** | 26 → **25** | 25 → **22** | 72,0 → **63,8 %** | 15 → **14** |
| Sao Paulo | 75 → **75** | 6 → **6** | 4 → **4** | 58,0 → **58,0 %** | 2 → **2** |
| Nürburgring | 90 → **88** | 13 → **12** | 12 → **11** | 72,3 → **62,4 %** | 7 → **5** |
| Silverstone | 78 → **78** | 6 → **6** | 6 → **6** | 60,9 → **60,9 %** | 1 → **1** |
| Monza | 49 → **47** | 3 → **3** | — | — | — |

Die Stoppverteilung je Auto rutscht mit: In Zandvoort fahren jetzt sechs
statt acht Autos fünf Stopps, am Nürburgring verschwinden die
Fünf-Stopp-Autos ganz (zwei vorher, keines jetzt), in Monza kommen elf
statt neun mit einem einzigen Stopp aus. Ohne Stopp kommt weiterhin
niemand ins Ziel.

**Was der Wert nicht behebt, und das ist ehrlich zu sagen:** Er macht
jeden verworfenen Satz billiger — acht Prozentpunkte weniger Profil
landen im Müll —, aber er verhindert den Stopp nicht. Über alle fünf
Strecken sinkt die Zahl der Planstopps direkt nach einem Zwangsstopp nur
von 47 auf 43, und die davon ohne jeden Mischungswechsel von 25 auf 22.
Der Grund liegt in der Sache: Das Verschieben rückt den Stopp um zwei bis
drei Runden nach hinten, gefahren wird er trotzdem. Wer diese 22 ganz
loswerden will, braucht die andere Regel — dass ein Zwangsstopp den
nächsten geplanten streicht. Die ist nicht gebaut; sie steht hier nur
als das, was noch offen wäre.

### Dabei behoben: Zwei Tests hingen an einem Balancing-Wert

Die Umstellung auf 0,65 ließ zwei Tests durchfallen —
`test_der_geplante_stopp_wird_gefahren` und
`test_beide_modi_fahren_dieselbe_strategie`. Beide prüften, dass ein für
Runde 16 geplanter Stopp in Runde 16 gefahren wird; jetzt fiel er in
Runde 17.

Am Code war nichts falsch. Falsch war der Test: Ob der Stopp in Runde 16
oder 17 fällt, entscheidet `planstopp_ab_restprofil` — ein Wert, den der
Auftraggeber drehen darf. Ein Test der **Mechanik** darf daran nicht
hängen. Das ist dieselbe Lehre wie bei der Gripkurve in Punkt 77, nur
andersherum: Dort wiederholten Tests eine Zahl aus der Konfiguration,
hier hing eine Rundenzahl indirekt daran.

Beide Tests laufen jetzt über das schon vorhandene Fixture
`ohne_verschiebung`, das die Schwelle auf 1,0 setzt — verschoben wird dann
nie, und die geplante Runde ist die gefahrene, egal wie der Wert steht.

Damit die Verschiebung nicht ungeprüft bleibt — sie hatte bis dahin
keinen eigenen Test —, steht sie jetzt in
`test_ein_zu_guter_satz_verschiebt_den_stopp`. Der prüft nicht gegen eine
ausgerechnete Runde, sondern gegen die Regel: Der Stopp fällt **nicht**
in die geplante Runde, und wenn er fällt, ist das Restprofil höchstens so
hoch wie die Schwelle aus der Konfiguration. Gemessen über acht
Verschleißfaktoren von 0,3 bis 2,5 hält das durchweg — der Stopp landet
immer bei 61 bis 65 Prozent, ganz gleich, in welcher Runde das ist.

### 79. Nach einem Zwangsstopp: härter bleiben, länger warten

Der Messlauf aus Punkt 78 zeigte zwei Dinge, die zusammengehören. Ein
Auto, das sich einen Satz abgefahren hat, bekam beim nächsten Stopp
wieder eine weichere Mischung — und gab den frischen Satz schon bei
72 Prozent ab. Über die fünf Strecken: **69 Stopps** folgten auf einen
Zwangsstopp, davon **37 weicher**, 32 gleich, **0 härter**, und **47**
davon mit mehr als 60 Prozent Restprofil.

**Zwei Entscheidungen des Auftraggebers.**

1. Bei **heiß und trocken** darf nach einem Zwangsstopp keine weichere
   Mischung mehr aufgezogen werden als die, die der Zwangsstopp montiert
   hat — für jeden weiteren Stopp, nicht nur den nächsten. **Ausnahme:**
   Wer bis dahin erst eine Mischung gefahren ist, darf weicher werden;
   sonst wäre die Pflicht zu zwei Mischungen nicht mehr erfüllbar,
   nachdem der Zwangsstopp die härteste aufgelegt hat.
2. Der geplante Stopp **direkt nach** einem Zwangsstopp wartet bis unter
   **60** statt 65 Prozent.

**Der Zwangsstopp selbst brauchte nichts.** Er wählt über
`passende_mischung()`, und die nimmt bei gleicher Eignung die haltbarste
— im Trockenen also immer Hart. Nachgezählt: 52 Zwangsstopps auf
Trockenmischungen, **null** davon weicher oder gleich weich, obwohl es
härter ginge. Die Regel greift beim Stopp danach, nicht bei ihm.

`nicht_weicher_als()` vergleicht nur **innerhalb einer Nässeklasse**. Ein
Regenreifen hat rechnerisch weniger Verschleiß als ein weicher Slick,
ist aber nicht "härter" — er ist etwas anderes. Bei Nässe entscheidet
weiter die Lage.

`verschiebeschwelle()` gibt die tiefere Schwelle zurück, sobald der
letzte gefahrene Stopp ein Notstopp war. Beide Modelle führen dafür
denselben Zustand mit (`letzter_war_notstopp`, `haerte_untergrenze`,
`kuerzel_gefahren`) — sonst führen die Liga des Spielers und die
neunzehn anderen zwei verschiedene Regelwerke.

**Gemessen danach**, Liga 1, 30 Autos, Weltseed 1, nur trocken/heiß:

| Strecke | Stopps | davon Zwang | Verteilung je Auto | Restprofil beim Stopp 25/Median/75 |
| --- | --- | --- | --- | --- |
| Zandvoort | 104 → **98** | 25 → **21** | 5×: 6 → **1**, 4×: 7 → **12** | 26,0 / **35,5** / 57,1 |
| Sao Paulo | 75 → **75** | 6 → **6** | unverändert | 35,8 / **48,3** / 58,6 |
| Nürburgring | 88 → **87** | 12 → **12** | 4×: 6 → **5**, 3×: 19 → **20** | 32,1 / **37,1** / 52,7 |
| Silverstone | 78 → **78** | 6 → **6** | unverändert | 35,6 / **43,5** / 53,7 |
| Monza | 47 → **47** | 3 → **3** | unverändert | 46,9 / **55,1** / 63,9 |

Die Wirkung sitzt dort, wo die Zwangsstopps sitzen: auf Zandvoort. Dort
fällt die Zahl der Fünf-Stopp-Autos von sechs auf **eines**, und sechs
Stopps verschwinden ganz. Wo es kaum Zwangsstopps gibt — Silverstone,
Monza, Sao Paulo — ändert sich nichts, wie es sein soll.

**Beide Regeln nachgezählt**, über alle fünf Rennen:

* Weicher nach einem Zwangsstopp: 37 → **4**, und alle vier sind die
  Ausnahme (Auto hatte erst eine Mischung gefahren, alle vier H→W).
  **Null Verstöße.**
* Planstopp direkt nach einem Zwangsstopp: 38 Stück, davon über 60 Prozent
  Restprofil: **null**. Vorher lagen 47 von 69 darüber.

Was in der Werkzeugausgabe jetzt **steigt**, ist die Zahl der Stopps
"ohne Mischungswechsel" (Zandvoort 14 → 16). Das ist kein Rückschritt,
sondern die Regel bei der Arbeit: Ein Auto auf Hart, das herein muss,
bekommt wieder Hart. Der Stopp holt frisches Gummi, nicht eine andere
Mischung — und das war vorher genau die Wahl, die verboten werden sollte.

### 80. Wo Weich wegfällt

Zwei Entscheidungen des Auftraggebers, beide mit demselben Ziel: die
Vier- und Fünf-Stopp-Rennen zurückdrängen.

1. Eine Variante, die mit **mehr als drei Stopps** plant, darf nicht auf
   der weichsten Trockenmischung stehen. Wer so oft herein muss, hat auf
   dem weichsten Gummi nichts verloren.
2. Auf jeder Strecke mit einem **Streckenfaktor über 1,15** (GDD 3) fällt
   Weich ganz weg — dort bleiben Mittel und Hart.

Beide Werte stehen als `weich_hoechstens_stopps = 3` und
`weich_hoechstens_streckenfaktor = 1.15` in der Konfiguration.

**Welche Strecken das trifft:** fünf der zwanzig. Zandvoort (1,263),
Budapest (1,210), Shanghai und Oschersleben (je 1,168), Catalunya
(1,160). Sao Paulo liegt mit 1,132 knapp darunter und behält Weich.

`weichste_trockene()` sucht die Mischung nicht über ihren Schlüssel,
sondern über die Zahlen: unter allen ohne Nässe die mit dem höchsten
Verschleiß. Käme eine vierte Trockenmischung dazu, stimmte das weiter.
Die Regenreifen rührt die Regel nicht an — sie zielt auf den Verschleiß
der Strecke, nicht auf die Wetterlage.

**Gemessen**, Liga 1, 30 Autos, Weltseed 1, nur trocken/heiß:

| Strecke | Faktor | Stopps | davon Zwang | Verteilung je Auto | Restprofil 25/Median/75 |
| --- | --- | --- | --- | --- | --- |
| **Zandvoort** | **1,263** | 98 → **91** | 21 → **10** | 5×:1→**0**, 4×:12→**7**, 3×:13→**19** | 26,0 → **31,9** / 35,5 / 57,1 → **42,5** |
| Sao Paulo | 1,132 | 75 | 6 | unverändert | 35,8 / 48,3 / 58,6 |
| Nürburgring | 1,074 | 87 | 12 | unverändert | 32,1 / 37,1 / 52,7 |
| Silverstone | 0,890 | 78 | 6 | unverändert | 35,6 / 43,5 / 53,7 |
| Monza | 0,537 | 47 | 3 | unverändert | 46,9 / 55,1 / 63,9 |

Von den fünf Stichprobenstrecken liegt nur Zandvoort über 1,15 — dort
wirkt die Regel, überall sonst ändert sich nichts. **Auf Zandvoort
verschwindet Weich vollständig aus dem Feld**, die Fünf-Stopp-Autos
gehen von einem auf keines zurück, die Vier-Stopp-Autos von zwölf auf
sieben, und die Zwangsstopps halbieren sich von 21 auf 10. Sieben Stopps
weniger im ganzen Rennen.

Bemerkenswert ist die Spanne beim Restprofil: Sie zieht sich von
26–57 auf **32–43** Prozent zusammen. Vorher fiel das Feld auseinander —
einige schlichen auf abgefahrenen weichen Reifen, andere warfen halbvolle
weg. Jetzt stoppt fast jeder in demselben Fenster.

Die anderen vier betroffenen Strecken stehen nicht in der Stichprobe; das
Werkzeug zieht sie nach Perzentilen, und dort liegt nur das Maximum über
der Grenze. Zur Gegenprobe deshalb **Budapest** (1,210) einzeln
gefahren: höchstens drei Stopps im ganzen Feld (2 Autos mit einem,
8 mit zwei, 19 mit drei), nur vier Zwangsstopps, kein Weich. Genau das
Bild, das die Regel erzeugen soll.

### 81. Das Rennen startet in Echtzeit

Bisher suchte die Rennseite beim Aufschlagen die kleinste Zeitrafferstufe,
mit der das Rennen in rund 210 Sekunden durchlief (`wunschdauer_s`). Auf
langen Strecken waren das 20x oder 50x — die ersten Runden waren vorbei,
bevor man richtig hinsah.

**Entscheidung des Auftraggebers:** Jedes Rennen startet mit **1x**. Das
steht als `zeitraffer.start_stufe = 1` in der Konfiguration; `wunschdauer_s`
ist damit gegenstandslos und entfällt. Umstellen geht weiter jederzeit
während des Rennens, die Stufen 1x bis 100x bleiben unverändert.

Die Stufe wird **nicht** fest im Code gesetzt, sondern aus der
Konfiguration gelesen — und wenn dort eine Stufe steht, die es in
`stufen` nicht gibt, nimmt die Oberfläche die langsamste statt zu
stolpern. Ein eigener Test prüft, dass `start_stufe` wirklich in `stufen`
vorkommt; sonst fiele das erst im Spiel auf, und zwar still.

`test_zeitraffer_wird_zur_renndauer_gewaehlt` prüfte die alte Regel und
ist durch `test_das_rennen_startet_mit_der_eingestellten_stufe` ersetzt.
Der liest die Stufe aus der Konfiguration statt die Eins zu wiederholen —
dieselbe Lehre wie bei der Gripkurve in Punkt 77 und der
Verschiebeschwelle in Punkt 78.

**Was das für lange Rennen heißt:** Ein Rennen in Liga 20 dauert real über
eine Stunde. Wer es ganz sehen will, stellt jetzt selbst hoch — oder nimmt
den Knopf **Sofortergebnis**, den es unverändert gibt.

### 82. Vier Blätter rechts, Team überall, lila Sektoren

Vier Wünsche des Auftraggebers an die Rennanzeige, alle in derselben
Ecke.

**Die Meldungen sind ein Blatt geworden.** Der Zwischenfall-Ticker stand
seit Punkt 4 als Fußleiste unter der ganzen Seite, in einem senkrechten
Teiler. Er nahm den Tabellen Höhe weg, obwohl man ihn selten braucht.
Jetzt ist er das vierte Blatt rechts — einen Klick entfernt und keinen
Pixel im Weg. Der senkrechte Teiler entfällt ganz.

**Spalte „Team" in allen Blättern.** Rangliste, Zeitenmonitor,
Bestmögliche Runde und Meisterschaft. `_teamname()` arbeitet wie
`_nachname()`: über die Fahrernummer in die Welt und von dort ins Team.
Ein Feld aus `rennen.starterfeld` hat keinen Fahrer dahinter, dann bleibt
die Spalte leer.

**Der schnellste Sektor des Feldes ist lila.** Wer einen Sektor als
Schnellster aller 30 hält, bekommt ihn in `FARBE_BESTER_SEKTOR` und fett
— wie in der Übertragung. Grün bleibt die persönliche Bestzeit, lila
steht darüber. Gesucht wird über **alle bisher gefahrenen Runden** aller
Autos, nicht nur über die letzte Runde.

**Das Blatt „Bestmögliche Runde".** Aufbau wie der Zeitenmonitor, aber
die Sektoren sind die **persönlich** besten — sie müssen nicht aus
derselben Runde stammen, genau darum geht es. Ihre Summe ist die Zeit,
die der Fahrer hätte fahren können; die Spalte „Lücke" daneben sagt,
wieviel zwischen ihr und seiner wirklich gefahrenen Bestzeit liegt.
Sortiert wird nach der möglichen Zeit: Dort steht, wer das schnellste
Auto hätte, nicht wer es am besten zusammengebracht hat.

Im Kern kommen dafür `Rundenprotokoll.beste_sektoren_bis()` und
`ideale_runde_ms()` dazu. Beide rechnen zum **Abspielzeitpunkt**, wie
alles auf dieser Seite. Ohne vollständige Sektoren gibt es keine ideale
Runde — eine Summe aus halben Runden wäre keine Rundenzeit.

### Dabei behoben: die bestmögliche Runde war eine Millisekunde zu langsam

Der erste Testlauf des neuen Blattes fiel durch:

```
RAD: 5:37.491 > 5:37.490
```

Die aus den besten Sektoren zusammengesetzte Runde war **langsamer** als
eine wirklich gefahrene. Das kann nicht sein — und lag an der Rundung:
Sektorzeiten und Rundenzeiten werden unabhängig voneinander auf ganze
Millisekunden gerundet (GDD: Zeiten sind ganze Millisekunden), also kann
die Summe der Sektoren eine Millisekunde über der Rundenzeit liegen, aus
der sie stammt.

`ideale_runde_ms()` deckelt die Summe jetzt gegen die beste wirklich
gefahrene Runde. Eine „bestmögliche" Runde, die langsamer ist als eine
gefahrene, wäre eine falsche Auskunft — und die Spalte „Lücke" daneben
stünde im Minus.

### 83. Drei Fehler und eine Regel, die es nur auf dem Papier gab

**Das ganze Feld kam in derselben Runde herein.** Gemeldet aus Liga 20 in
Sakhir: Runde 7, alle auf Intermediates, alle unter 40 Prozent. Nachgestellt
und reproduziert — aber die Ursache war nicht der Verschleiß-Zwangsstopp aus
Punkt 78. Die Restprofile lagen bei 36 bis 71 Prozent, weit über den 30.

Es war die **Wetterregel**. Ein Intermediate gilt als falscher Reifen, sobald
die Lage weiter als 0,30 von seinen 0,40 entfernt ist:

| Lage | Abstand | Inter |
| --- | --- | --- |
| wechselhaft (0,35) | 0,05 | ok |
| regen (0,70) | 0,30 | ok |
| **trocken / heiß (0,0)** | **0,40** | **falsch** |
| **starkregen (1,0)** | **0,60** | **falsch** |

Trocknet es ab, werden alle dreißig Intermediates im selben Augenblick
falsch. Und `notstopp()` gab `True` zurück, sobald der Reifen falsch war —
also nahm jedes Auto die früheste erlaubte Runde.

Dabei stand in der Konfiguration seit jeher `falscher_reifen_max_runden = 3`,
und der Docstring versprach „höchstens drei Runden auf dem falschen Reifen".
**Der Wert wurde von nichts gelesen** — `grep` über das ganze Projekt fand
genau eine Fundstelle: die Konfigurationszeile selbst.

Entscheidung des Auftraggebers: Der Wert geht auf **2** und wird je Auto
ausgewürfelt (0 bis 2). `geduld_falscher_reifen()` zieht ihn aus dem Seed des
Autos, beide Rennmodelle zählen mit. Gemessen auf Sakhir: Zwangsstopps von
**29 auf 16**, verteilt auf zwei Runden statt einer.

Was bleibt, ist gewollt: In Runde 11 stoppen weiter 24 Autos — das sind die
**geplanten** Stopps. Alle dreißig planen dort den Wechsel auf Regen, weil
der Wetterumschwung feststeht (GDD 7). So halten es echte Teams auch.

### Dabei behoben: ein Intervall von minus 1 487 467 Stunden

Nach dem Zieldurchlauf stand in der Rangliste:

```
P29 KER Keller  +5:09.430   Intervall -1487467:14:28.515   km/h 105
```

Zwei Fehler griffen ineinander. Sortiert wird nach Runden und dann nach
Zielzeit (Punkt 67), deshalb kann ein Überrundeter, der schon im Ziel ist,
**vor** einem stehen, der noch fährt — auf der Strecke liegt er dann eine
Runde zurück. `_intervall()` fing nur den umgekehrten Fall ab
(`abstand >= laenge`), der negative fiel durch.

Und dort landete er in der Schätzung „Strecke durch Tempo", die mit
`max(tempo, 1e-6)` gegen Division durch null abgesichert war. Ein stehendes
Auto hat aber Tempo null: 5355 Meter geteilt durch 1e-6 m/s sind 5,4
Milliarden Sekunden — **genau die 1 487 467 Stunden aus dem Bild**.

Beides behoben: Ein Rundenrückstand in die andere Richtung steht jetzt als
`-1 Rd.` da, und wer steht, hat keinen Abstand in Sekunden — dann steht dort
nichts. Die Schwelle dafür ist dieselbe `TEMPO_STEHT = 0.1`, die schon die
km/h-Spalte benutzt; vorher stand die 0,1 dort als lose Zahl im Code.

### Dabei behoben: die Fähigkeitenliste ließ sich nicht erreichen

Die Karriereseite trägt Kopf, Kalenderband, Fähigkeitenliste und
Seitenspalte untereinander. Auf einem kleinen Fenster blieb für die Liste
kaum Höhe, und ihr eigener Rollbalken half nichts, weil schon der Kasten
abgeschnitten war. Die ganze Seite liegt jetzt in einer `QScrollArea`, und
die Liste behält eine Mindesthöhe von 320 Pixeln — genug für rund ein
Dutzend Zeilen, darunter sieht man nur noch Kopfzeile und Balken.

### 84. Trainingsprogramme über mehrere Tage

Der Auftraggeber wählte aus drei Vorschlägen diesen — und dabei kam
heraus, dass mein eigener Vorschlag auf einer falschen Annahme stand.

**Es gab kein „Tag für Tag belegen".** `belege_tag()` belegt einen
**Platz** (Fahrer oder Werkstatt) **bis zum nächsten Rennen**, nicht nur
für heute (Punkt 69). Zwischen zwei Rennen liegen 14 Kalendertage mit
**10 nutzbaren** — aber je Fahrer waren nur **zwei Buchungen** möglich,
eine je Platz, jede `max(+10, +1 %)` wert. Die Mechanik war also längst
blockweise; die 10 freien Tage wurden angezeigt und von nichts
verbraucht. Der Satz „bringt mehr als 14 Einzeltage" hatte kein
Gegenstück im Code; ich hatte vom Knopf „Heutigen Tag belegen" auf eine
Tagesbuchung geschlossen.

**Entscheidungen des Auftraggebers**, nachdem das geklärt war:

1. Die Tage werden eine **echte Währung**. Ein Programm zieht sie ab.
2. **5 bis 10 Tage**, nie über ein Rennwochenende hinweg — zehn ist
   zugleich die Zahl der nutzbaren Tage zwischen zwei Rennen, ein
   Programm passt also immer in einen Rennabstand.
3. Ein Abbruch zahlt **anteilig**, was gelaufen ist.
4. **Kein Bonus** fürs Durchhalten.

**Dabei fiel ein Rechenfehler in meinem eigenen Vorschlag auf.** Mit dem
zuerst vorgeschlagenen `tag_anteil = 0,10` und ohne Bonus wäre ein
Programm **strikt schlechter** als die Einzelbuchung gewesen:

| | Ertrag | Risiko | Tage |
| --- | --- | --- | --- |
| Einzelbuchung | 1,0 | keins | 0 |
| Programm, 10 Tage | 10 × 0,10 = **1,0** | Abbruch | alle 10 |

Gleicher Ertrag, gleicher belegter Platz, dazu das Risiko — niemand hätte
je eines gebucht. Der Bonus war genau das, was es trug. Entscheidung des
Auftraggebers: `tag_anteil = 0,15`. Zehn Tage bringen damit anderthalb
Buchungen, und das Programm lohnt sich ohne Bonus.

Neu im Kern: `training.py` mit `Programm`, `zuwachs()`, `plane()` und
`abrechnung()`. Die Karriere führt `programme` je Fahrer, zählt beim
Tageswechsel mit und rechnet ab, sobald ein Programm durch ist oder ein
Ereignis es bricht (E2/E6 sperren die Fähigkeit, E29 frisst Tage).
`entwicklung.mit_zuwachs()` ist die Tür dorthin — vorher hätte `training`
durch die private `_entwicklung` greifen müssen.

**Spielstand auf Version 9.** Die Tabelle `trainingsprogramm` trägt die
laufenden Programme; ältere Stände laden ohne, sie kannten die Mechanik
nicht.

**Die Einzelbuchung bleibt unverändert daneben.** Sie kostet keinen Tag
aus dem Vorrat und ist der sichere Weg; das Programm ist der Einsatz. So
bricht nichts Bestehendes, und es gibt eine echte Wahl.

**Derselbe Fehler noch einmal, eine Ebene tiefer.** Die Tabelle oben
rechnet auf dem rohen Tageszuwachs — aber jeder Zuwachs wird auf ganze
Kaufschritte **abgerundet** (GDD 9, `kaufschritt = 10`), und der
Tageszuwachs ist für jeden Wert unter 2000 genau diese 10. Gemessen:

| Tage | roh bei 0,15 | verbucht | roh bei 0,20 | verbucht |
| --- | --- | --- | --- | --- |
| 5 | 7,5 | **0** | 10,0 | **10** |
| 6 | 9,0 | 0 | 12,0 | 10 |
| 7 | 10,5 | 10 | 14,0 | 10 |
| 8 | 12,0 | 10 | 16,0 | 10 |
| 9 | 13,5 | 10 | 18,0 | 10 |
| 10 | 15,0 | **10** | 20,0 | **20** |

Mit `0,15` bringt ein Fünftageprogramm also **nichts** und ein
Zehntageprogramm **genau eine Einzelbuchung** — bei gleichem belegtem
Platz plus Abbruchrisiko. Die anderthalb Buchungen gibt es nur auf dem
Papier; die Rundung frisst den halben Schritt. Damit ist das Programm
wieder strikt schlechter als die Einzelbuchung, aus demselben Grund wie
bei `0,10`, nur versteckter.

`0,20` ist die nächste Schwelle, an der die Mechanik trägt: Ein Tag ist
ein Fünftel einer Buchung, fünf Tage sind eine, zehn sind zwei. Weil der
Platz nach dem Programm frei wird, passen zwei Fünftageprogramme in einen
Zyklus — die Entwicklung des Spielers verdoppelt sich damit gegenüber
heute, wenn er die Tage voll nutzt.

**Entscheidung des Auftraggebers: „Mach es tragbar" — `tag_anteil =
0,20`.**

**Warum der bestehende Test das nicht gefunden hat.** Es gab einen Test
namens `test_zehn_tage_bringen_anderthalb_buchungen`, und er war grün.
Er maß bei Wert 50.000 — dort ist der Tageszuwachs 500, die Abrundung auf
Kaufschritte fällt nicht ins Gewicht, und 0,15 sah brauchbar aus. Beim
Anfängerwert 0, wo der Spieler tatsächlich startet (GDD 1), ist der
Tageszuwachs genau *ein* Kaufschritt, und dort frisst die Rundung alles.
Ein Test, der nur an der bequemen Stelle misst, ist kein Test.

Er ist jetzt durch drei ersetzt, die nicht die Zahl prüfen, sondern die
**Regel**, und das über eine Reihe von Werten einschließlich der Null:

1. Das längste Programm muss die Einzelbuchung schlagen.
2. Das kürzeste muss überhaupt etwas bringen.
3. `max_tage * tag_anteil` muss zwei Kaufschritte füllen,
   `min_tage * tag_anteil` einen.

Gegengeprobt: Mit `tag_anteil = 0,15` fallen alle drei, mit Meldungen,
die die Ursache benennen („Bei Wert 0 bringt ein Programm über 10 Tage
10, eine Einzelbuchung 10 — niemand würde es buchen"). Damit kann die
Zahl nicht mehr still unter die Schwelle rutschen. Dieselbe Lehre wie bei
Punkt 79 und Punkt 77: Ein Test, der einen Balancing-Wert fest verdrahtet
oder nur an einer bequemen Stelle misst, schützt nichts.

**Eine Treppe bleibt.** Solange der Tageszuwachs genau ein Kaufschritt
ist, zahlt nicht jeder zusätzliche Tag — bei Wert 0 bringen fünf bis neun
Tage alle dasselbe (+10), erst der zehnte hebt auf +20. Am Anfang lohnen
sich also nur die beiden Enden der Spanne. Je höher der Wert, desto
feiner die Treppe; ab etwa 5.000 zahlt jeder einzelne Tag. Das ist keine
eigene Regel, sondern dieselbe +10-Granularität aus GDD 9, die auch den
Kauf bestimmt — und deshalb nichts, was ich ohne Rückfrage glätten
würde.

### 85. Das Qualifying als abspielbarer Zeitenmonitor

Gewünscht: das Qualifying „nur als Zeitenmonitor abspielbar von der
Geschwindigkeit her", nach dem Laden auf Anfang, dieselben
Abspielgeschwindigkeiten wie im Rennen, die Zeit läuft live mit, sobald
ein Fahrer auf seiner schnellen Runde ist, die Fahrer sortieren sich live
ein — Splits **rot** wenn langsamer als der derzeitige Führende, **grün**
wenn schneller, **lila** beim absolut besten Split.

**Der Kern brauchte keine neue Rechnung.** Jede `Fahrt` trug schon
`beginn_ms`, `ziel_ms`, `zeit_ms` und die Sektorzeiten — daraus fallen
`runde_ab_ms` und `sektorenden_ms` einfach ab. Neu sind nur die Abfragen:
`lage_zu()` mit den vier Lagen (Box, Aufwärmrunde, Schnelle Runde, Im
Ziel), `fuehrender_zu()`, `splitvergleich()` und `beste_splits_zu()`.

**Zwei Entscheidungen des Auftraggebers:**

1. Der Vergleich gegen den Führenden ist **wie im Fernsehen** — er friert
   im Moment des Überfahrens ein und dreht sich nicht mehr um.
2. Die **Startaufstellung** füllt sich erst am Ende der Session.

Daraus folgt, dass die beiden Farbgruppen verschiedene Zeitpunkte messen:
Lila ist Live-Stand und wandert weiter, Grün und Rot stehen fest. Das ist
kein Widerspruch, sondern genau das Bild einer Übertragung — nur muss man
es einmal ausschreiben, sonst liest es sich wie ein Fehler.

**Ein Rundungsfall, derselbe wie bei der idealen Runde.** Sektorzeiten
und Rundenzeit runden getrennt auf ganze Millisekunden (GDD 15), ihre
Summe trifft die Rundenzeit also nicht zwingend. Ohne Festlegung wäre ein
Auto für einen Takt im Ziel, ohne seinen letzten Split gesetzt zu haben;
deshalb endet der letzte Sektor per Definition im Ziel.

**Drei Tests hingen am alten Regler.** `test_ui_rennen.py` prüfte die
Live-Einsortierung über `_regler.setValue()` und erwartete die fertige
Aufstellung direkt nach dem Laden — beides gibt es nicht mehr. Sie prüfen
jetzt dasselbe über die Sessionuhr. Dass die Tabelle immer alle dreißig
Autos zeigt (Punkt 64), heißt dabei: gezählt wird, wer schon eine
Position hat, nicht wie viele Zeilen dastehen.

**Ein eigener Testfehler:** Mein erster Beweis, dass der eingefrorene
Vergleich etwas anderes ist als der gegen die Pole, lief über einen Seed
— und der lieferte ihn nicht. In der gemessenen Session fuhr der Erste
zugleich die Pole, weil das Wetter nach seiner Runde umschlug; damit war
der Führende immer die Pole und der Unterschied unsichtbar. Der Fall
steht jetzt als von Hand gebaute Session im Test, die ihn garantiert
enthält.

### 86. Die Rennanzeige und der Rennaufbau, gemessen und beschleunigt

Beauftragt: D1 bis D10 und E1 bis E13 ohne E9, aus `VORSCHLAEGE.md`.
Die Vorschläge standen dort mit Messwerten; hier steht, was dabei
herauskam.

**Die Anzeige: 14,18 → 2,50 ms je Bild** (Zandvoort, Liga 1, 30 Autos,
40 Runden, Seed 4711, `werkzeuge/profil_rennen.py`).

| Schritt | je Bild | Bilder/s |
| --- | ---: | ---: |
| vorher | 14,18 ms | 70 |
| D1, D2, D9 | 3,79 ms | 264 |
| D4–D8, D10 | **2,50 ms** | **401** |

**D3 wurde gemessen und nicht gebaut.** Der Vorschlag lautete, die
dreißig Zeilen wiederzuverwenden statt die Tabelle je Bild zu leeren und
neu aufzubauen. Nach D2 trägt das nichts mehr. Gemessen über 400
Durchläufe mit 30 Zeilen und 13 Spalten:

| Verfahren | je Füllung |
| --- | ---: |
| A — `clear()` und 30 neue Items (heute) | 0,148 ms |
| B — Zeilen wiederverwenden, nur `setText` | 0,133 ms |
| C — wiederverwenden **und** jede Zelle zurücksetzen | **0,214 ms** |
| D — `setText` nur bei Änderung | 0,097 ms |

B spart 0,015 ms je Tabelle und Bild, also rund **ein Prozent** des
Bildes — und handelt sich dafür die Falle ein, dass Farbe, Schrift und
Ausrichtung aus dem vorigen Bild stehen bleiben. Wer das sauber löst,
landet bei C und ist **44 % langsamer als heute**: Eine Zelle
zurückzusetzen kostet genauso viel wie sie zu setzen. Die Rechnung ging
nur auf, solange fünf Tabellen je Bild gefüllt wurden; D2 hat diesen
Boden weggezogen.

Wenn D3 trotzdem gebaut werden soll, ist Variante B die einzige, die
sich lohnt, und dann muss jede Füllfunktion **jedes** Merkmal jeder
Zelle bedingungslos setzen. Das ist eine Entscheidung, keine
Optimierung — deshalb liegt sie hier und nicht im Code.

**Was stattdessen noch da ist:** `_fuelle_rangliste` verbraucht 0,94 ms
je Bild an eigener Zeit, davon nur 0,15 ms fürs Bauen der Zeilen. Der
Rest ist Python-Logik je Zeile — unter anderem wird für jede der dreißig
Zeilen die Liste aller Zwischenfälle dieses Autos neu gefiltert. Das
stand nicht in D1 bis D10 und ist nicht gebaut.

**Die Rennschleife: 13.906 → 10.696 ms je Rennen** (−23 %), bei
unverändertem Fingerabdruck. Gebaut wurden E1, E2, E5, E7, E8 und der
billige Teil von E6:

| | was | Ersparnis |
| --- | --- | ---: |
| E1 | `np.roll` durch einen fertigen Indexvektor ersetzt | 6,42 → 0,21 µs je Aufruf |
| E2 | `np.clip(a, …)` durch `a.clip(…)` ersetzt | 2,12 → 1,05 µs |
| E5 | `np.floor` stand zweimal für denselben Wert | 2,65 → 2,32 µs |
| E6 | `np.argsort(a)` durch `a.argsort()` ersetzt | −2 µs Wrapper |
| E7 | `np.flatnonzero(m)` durch `m.nonzero()[0]` ersetzt | 1,13 → 0,28 µs |
| E8 | Unfallrate beim Wetterwechsel statt bei jedem Paar | 484.220 → wenige Aufrufe |

**Drei Vorschläge haben die Messung nicht überstanden:**

**E3 — die konstanten Tempofaktoren zusammenziehen.** Geht nicht ohne
Verhaltensänderung. Der Ausdruck `x * grip * form * reifen * defekt *
kenntnis * …` wird von links nach rechts ausgewertet; ein vorberechnetes
Teilprodukt ändert die Klammerung, und Gleitkomma-Multiplikation ist
nicht assoziativ. Ein einziges verschobenes Bit kann über 89.439
Schritte ein Überholmanöver kippen. Die bitgenaue Variante — dieselben
Faktoren an Ort und Stelle multiplizieren statt neue Arrays anzulegen —
bringt gemessen 2,09 → 2,02 µs, also drei Prozent. Nicht gebaut.

**E4 — Ermüdung und Kaltreifen als Tabelle.** Dasselbe Problem: Eine
vorberechnete Kurve liefert gerundete Zwischenwerte, keine identischen.
Nicht gebaut.

**E6 — `argsort` nur bei Änderung.** Die Prüfung, ob die Reihenfolge
noch stimmt, kostet gemessen **1,70 µs** — das Sortieren selbst 1,63.
Der Vorschlag war also von vornherein ein Verlust. Gebaut wurde
stattdessen nur, den Wrapper zu umgehen.

Die Lehre ist dieselbe wie bei D3: Ein Vorschlag mit einer plausiblen
Begründung ist noch keine Verbesserung. Gemessen wird vorher.

**E10 bis E12.**

**E10 — das Rennen rechnet im Hintergrund.** `simuliere()` nimmt einen
`fortschritt`-Rückruf, der bei jeder vollen Runde des Führenden gerufen
wird; die Wochenendseite rechnet damit in einem eigenen Faden und zeigt
„Rennen wird gerechnet — Runde 23 von 40". Schneller wird nichts, aber
das Fenster bleibt ansprechbar. Ein Test hält fest, dass der Rückruf am
Rennen nichts ändert.

**E11 — die Welt einmal erzeugen: es gab gar nichts zu tun.** Der
Vorschlag stand unter der Bedingung „wenn das je Rennwochenende erneut
passiert". Tut es nicht: `kern_welt.erzeuge` steht genau einmal im
Programm, im Hauptfenster. Die gemessenen 409 ms fallen beim Start an,
nicht je Rennen.

**E12 — float32 nur für den Reifenzustand.** Der Vorschlag lautete,
alle Bildfelder auf halbe Genauigkeit zu stellen. Für `distanz_m` wäre
das ein Fehler gewesen, und zwar einer, den man erst im fertigen Spiel
sieht:

| | |
| --- | ---: |
| größte Distanz über 40 Runden | 169.778 m |
| Auflösung von `float32` dort | **15,6 mm** |
| engster gemessener Abstand zweier Autos | **5,24 mm** |

An `distanz_m` hängt die Reihenfolge des ganzen Feldes. Bei 15,6 mm
Auflösung bekämen zwei Autos, die 5 mm auseinander sind, denselben Wert
— wer vorn liegt, entschiede dann die Sortierung statt die Strecke. Eine
Stichprobe über 4.000 Zeitpunkte fand zwar keine Abweichung, aber das
beweist nur, dass der Fall selten ist, nicht dass es ihn nicht gibt.
`distanz_m` bleibt deshalb `float64`; die Begründung steht jetzt im
Docstring, damit sie beim nächsten Anlauf gefunden wird.

Der Reifenzustand wird dagegen nur angezeigt — als Balken und als
Prozentzahl — und nie für eine Entscheidung gelesen; die Simulation
rechnet auf `verschleiss`. Dort ist `float32` unbedenklich und halbiert
den Speicher: **10,7 → 8,0 MB** je Rennen.

### 87. Der Fingerabdruck war als CI-Anker ein Fehlentwurf

**Die CI wurde rot, und zwar zu Recht — aber nicht wegen des Codes.**
`test_rennfingerabdruck.py` hielt zwei Hashwerte fest, gebildet über
alle rohen `float64`-Distanzen eines Rennens: 670.000 Zahlen. Auf der
Maschine, auf der sie entstanden, ist das ein scharfes Werkzeug; E1 bis
E8 ließen sich damit als bitgenau verhaltensgleich belegen, und das
stimmt auch weiterhin.

Als CI-Anker war es falsch. Die Tests laufen auf **Linux und Windows**,
NumPy ist nur als `>=1.26` gefordert. Verschiedene Rechner nehmen
verschiedene SIMD-Pfade und liefern in der letzten Stelle andere Bits.
Der Anker **musste** dort rot werden, ohne dass am Rennen irgendetwas
falsch war. Ein Test, der aus einem Grund rot wird, den er nicht meint,
ist schlimmer als kein Test — er kostet Vertrauen in alle anderen mit.

Belegt: derselbe Commit (`e5931d3`, an der Testzahl 1048 erkennbar) ist
hier grün und dort rot, und **beide** Anker wichen ab — ein Codefehler
träfe eher einen.

**Was jetzt gilt:**

* Die Kennzahl bleibt, im Werkzeug, wo sie hingehört:
  `python -m werkzeuge.profil_rennen --fingerabdruck`, vor und nach
  einer Änderung auf **derselben** Maschine. Genau so wurde sie
  gebraucht.
* Der Test prüft, was überall gilt: gleicher Seed → gleiches Rennen
  (auf einer Maschine sogar bitgleich), anderer Seed → anderes Rennen,
  und ein grober Plausibilitätsrahmen. Verglichen wird dabei, was ein
  Spieler sieht — Rundenzeiten, Sektoren, Ergebnisse, Stopps,
  Zwischenfälle —, alles ganze Zahlen.
* Der maschinenunabhängige Anker für die Physik ist die **Kalibrierung**
  (GDD 9): eine einzelne Runde ohne Zufall und ohne Verkehr, Zandvoort
  bei S=98.000 auf 180,00 km/h. Die hängt an keiner Maschine.

**Nebenbefund:** Ein um ein Bit verschobener Eingangswert ließ Rennen,
Rundenzeiten und Ergebnisse gemessen **unverändert**. Die Simulation ist
also nicht so chaotisch, dass jedes Bit durchschlägt — die Abweichung
zwischen den Rechnern entsteht breiter als an einer einzelnen Stelle.

**Windows läuft nur noch auf Ansage** (Entscheidung des Auftraggebers).
`tests.yml` fährt bei einem Push nur Linux und beide Systeme erst bei
„Run workflow"; `build-windows.yml` läuft nur noch bei einem
Versionsschild `v*` oder von Hand.

### 88. Die Strecke gummiert ein

Gewünscht: „Strecke wird schneller, mehr Grip bekommt sie bei trocken
und heiß über die Zeit." Vorgelegt als Konzept, entschieden vom
Auftraggeber:

| | Entscheidung |
| --- | --- |
| Wie viel maximal | **+1,5 %** Grip |
| Wie schnell | Halbwert bei **500** Auto-Runden |
| Was überlebt ins Rennen | **nichts** — jede Session fängt grün an |
| Regen | allmählich **abwaschen**; wird es wieder trocken, baut es sich neu auf. Wechselhaft wäscht ab, aber sehr wenig |
| Sieht der Spieler es | **ja** |
| Kalibrierung | bleibt die **grüne** Strecke |

**Die Zahl, die die Entscheidung erst möglich gemacht hat.** Der Grip
streckt das ganze Geschwindigkeitsprofil um genau seinen Faktor — ein
Prozent Grip ist ein Prozent Rundenzeit. Gemessen bringt +1,0 % Grip
−0,84 s in Zandvoort, −1,13 s in Spa, −0,95 s in Sakhir. **Faustregel:
ein Prozent Grip ist rund eine Sekunde.** Damit ließ sich in Sekunden
entscheiden statt in Prozent — sonst wäre `max_anteil = 0,015` eine Zahl
ohne Bedeutung gewesen.

**Eine einzige Zahl trägt die ganze Mechanik**: der Stand in gefahrenen
Auto-Runden. Aufbauen und Abwaschen sind derselbe Zähler mit
verschiedenem Vorzeichen; damit ist „nach dem Regen baut es sich wieder
auf" nicht als Sonderfall gebaut, sondern fällt von selbst ab.

**Drei Modelle, eine Formel.** Volle Simulation, Qualifying und
Schnellmodus rechnen dasselbe — sonst driften die 19 KI-Ligen weg
(README: Warum es zwei Rennmodelle gibt). Im Qualifying gilt für den
k-ten Starter, was die k Autos vor ihm plus seine eigene Aufwärmrunde
gefahren sind; die Schleife läuft in der Startreihenfolge und damit in
der Zeit.

**Der Aufschlag wirkt nach `grip_fuer`, nicht davor.** Davor dämpfte die
Wetterfähigkeit ihn mit, und ein Regenspezialist bekäme vom Gummi
weniger ab als ein anderer — Gummi ist aber keine Fahrkunst. Außerdem
hat `grip_fuer` bei genau 1,0 einen Sprung (dort schaltet der
Trockenbonus zu), und „heiss" mit Grip 0,97 liefe mit wachsendem Gummi
genau hinein.

**Ein Rennen ohne Wetterverlauf bleibt grün.** Das ist der Laborfall —
Kalibrierung und Tests. Im Spiel hat jedes Rennen ein Wetter, dort
greift die Gummierung immer. Ohne diese Grenze hätte die Mechanik die
Kalibrierung aus GDD 9 verschoben.

**Nachgemessen:** Kalibrierung Zandvoort 180,00 km/h (+0,00),
unverändert. Ein trockenes Rennen baut über 12 Runden 0,50 % auf; setzt
danach wechselhaft ein, friert es fast ein (203 → 197 Auto-Runden); ein
Regenrennen bleibt bei null. Im Qualifying liegen zwischen erstem und
letztem Starter 0,164 % Grip, also 0,14 s.

**Die Reifenart kam eine Runde später dazu.** Gewünscht: „Reifen leichter
Gummi auftragen oder nicht, und mit weichen Reifen ist der Grip-Effekt
stärker als mit harten." Also **zwei** Effekte, nicht einer.

Die Zahl dafür stand schon da: `verschleiss` aus `[reifen.mischungen]`.
Gummi auf der Strecke **ist** abgefahrener Reifen — was 1,44-mal so
schnell abbaut, lässt 1,44-mal so viel liegen. Und dass ein weicher
Reifen sich in den liegenden Gummi besser einarbeitet, kommt aus
derselben Eigenschaft. Keine zweite Tabelle, nur ein Bezug und ein
Exponent:

| | `verschleiss` | Auftrag | Ansprechen |
| --- | ---: | ---: | ---: |
| Weich | 1,05 | 1,44 | 1,20 |
| Mittel | 0,73 | 1,00 | 1,00 |
| Hart | 0,53 | 0,73 | 0,85 |

Der Auftrag ist **linear**, das Ansprechen **gedämpft** (Exponent 0,5) —
der zweite Zusammenhang ist der schwächere. Entscheidungen des
Auftraggebers: Bezug **Mittel**, Exponent **0,5**.

Gemessen in Zandvoort, nach 1.200 Auto-Runden: Weich −1,37 s, Mittel
−1,14 s, Hart −0,98 s. Der Unterschied Weich gegen Hart erreicht 23 %
dessen, was die Mischung an sich ausmacht (1,70 s). Bei Exponent 1,0
wären es 53 % gewesen, und ein später weicher Stint wäre fast erzwungen.

Weil Mittel der Bezug ist, bleibt der gemessene Verlauf aus dem ersten
Teil stehen: Ein trockenes Feld der Liga 1 fährt 46 % Hart, 32 % Mittel
und 22 % Weich, das Feldmittel des Auftrags liegt bei **0,973**.

**Der Auftrag gilt nur beim Aufbau.** Abgewaschen wird vom Regen, nicht
vom Reifen; sonst würde ein Intermediate stärker
abwaschen als ein Regenreifen. Ein Test hält das fest.

**Die Strategie weiß davon nichts** und soll es vorerst auch nicht:
`strategie.py` plant aus Verschleiß und Mischungstempo. Weich wird damit
spät im Rennen relativ besser, ohne dass die Planung es einrechnet — die
KI schöpft es nicht aus, und wer es bemerkt, hat einen echten Vorteil.


---

## Punkt 90 und 91: Die grüne Strecke frisst Reifen, und der Planer
## rechnet neu

**Der Auftrag, in zwei Teilen.** Erstens: „Grüne Strecke frisst Reifen
implementieren, aber Umverteilung, den ganzen Effekt wirklich moderat,
nicht zu extrem. Der erste Stint wäre also rund 20 % kürzer als der
letzte." Zweitens: die Strategien ohne das Delta rechnen, mit dem
Medianfahrer, allein auf der Strecke, die Reihenfolge tatsächlich
verwenden und oben im Rennen anzeigen, wie viele Strategien unterwegs
sind.

### Die grüne Strecke

Derselbe Stand, der den Grip hebt, senkt den Verschleiß — über dieselbe
Kurve, nur von 1,15 (grün) nach 0,928 (voll eingegummiert). Keine
Mischung darin: Wie stark der Asphalt schmirgelt, ist eine Eigenschaft
der Strecke, nicht des Reifens.

Gemessen in Zandvoort, 20 Runden, durchgehend trocken, ohne Strategie:
Der Abrieb je Runde fällt von **3,91 %** auf **3,41 %** — 13 % weniger,
genau das Stück der Kurve, das 546 Auto-Runden hergeben. Über ein volles
Rennen (1.800 Auto-Runden) wären es die vollen 19 %.

Der Planer rechnet den Faktor **mit** (sonst setzt er den ersten Stint
zu lang an), den wachsenden Grip **nicht** — so entschieden.

### Warum die Reihenfolge jetzt zählt

Bisher galt: Ein Stint kostet, was er kostet, egal ob er der erste oder
der letzte ist. Deshalb genügte **eine** Rechnung je Zusammenstellung,
und alle Reihenfolgen erbten das Ergebnis — aus 117 Folgen wurden 31
Rechnungen. Seit die grüne Strecke am Anfang mehr frisst, stimmt das
nicht mehr, und jede Reihenfolge wird einzeln gerechnet. Kosten: 224 ms
statt 60 für ein Feld von 30 Autos über 69 Runden — vertretbar.

### Der Plan gilt dem Medianfahrer

Vorher setzte das **stärkste** Auto den Maßstab, und danach rechnete
*jedes* Auto seine Stopprunden noch einmal mit den eigenen Werten nach.
Aus einer Handvoll Strategien wurden dreißig Abwandlungen. Jetzt steht
ein Satz zugelassener Varianten fest, die Autos ziehen daraus, und was
ein einzelnes Auto vom Median abweicht, fängt im Rennen der Zwangsstopp
bei 30 % Restprofil ab. Das Boxenstoppfenster geht von ±5 % auf ±3 %
der Renndistanz, mindestens eine Runde — es bleiben immer drei mögliche
Stopprunden.

### Was der Messlauf zeigt — und was noch fehlt

Fünf Strecken, Liga 1, trocken, 30 Autos:

| Strecke | Faktor | Rd | Varianten | Verteilung | Notstopps |
| --- | ---: | ---: | ---: | --- | ---: |
| Zandvoort | 1,263 | 69 | 14 / 13 gefahren | 2 Stopps 14 %, 3 Stopps 86 % | 4 |
| Sao Paulo | 1,132 | 69 | 82 / 26 | 1:14 %, 2:31 %, 3:55 % | 5 |
| Nürburgring | 1,074 | 58 | 67 / 26 | 1:3 %, 2:10 %, 3:86 % | 4 |
| Silverstone | 0,890 | 51 | 85 / 24 | 1:10 %, 2:17 %, 3:72 % | 3 |
| Monza | 0,537 | 51 | 21 / 17 | 0:7 %, 1:86 %, 2:7 % | 1 |

**Vier-Stopp-Strategien kommen nirgends mehr vor**, und die Zwangsstopps
sind von 29 auf 17 gefallen. Die gewünschten Verteilungen sind damit
aber **nicht** erreicht: Zandvoort soll 30/70 zwischen zwei und drei
Stopps liegen, Monza 60/40 zwischen einem und zweien.

**Der Grund ist strukturell.** Wie viele Stopps eine Strecke verlangt,
hängt daran, wie viele Runden ein Satz trägt, und das hängt am
Streckenfaktor. Der spannt von 1,263 bis 0,537 — Faktor **2,35**:

| Strecke | Faktor | Rd | W | M | H | mögliche Stopps |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Zandvoort | 1,263 | 69 | 15 | 22 | 30 | 2–4 |
| Sao Paulo | 1,132 | 69 | 17 | 25 | 34 | 2–4 |
| Nürburgring | 1,074 | 58 | 15 | 22 | 30 | 1–3 |
| Silverstone | 0,890 | 51 | 16 | 23 | 32 | 1–3 |
| Monza | 0,537 | 51 | 26 | 38 | 53 | 0–1 |

Monza kommt mit **einem** Stopp aus und braucht keinen zweiten;
Zandvoort schafft **keinen** Zwei-Stopp mehr. Beide Ziele zugleich
verlangen, dass sich die Stintlängen der Strecken höchstens um Faktor
1,5 unterscheiden — ein einzelner Verschleißwert für W, M und H kann
das nicht leisten, weil er beide Strecken in dieselbe Richtung
verschiebt.

**Vorschlag, noch nicht gebaut:** ein Exponent auf den Streckenfaktor,
`streckenfaktor ^ e`, gemessen:

| e | Zandvoort wirkt | Monza wirkt | Spanne | Zandvoort | Monza |
| ---: | ---: | ---: | ---: | --- | --- |
| 1,0 (heute) | 1,263 | 0,537 | 2,35 | 2–4 | 0–1 |
| 0,7 | 1,178 | 0,647 | 1,82 | 2–4 | 1–2 |
| **0,5** | **1,124** | **0,733** | **1,53** | **2–3** | **1–2** |
| 0,4 | 1,098 | 0,780 | 1,41 | 1–4 | 1–2 |

Bei 0,5 und 0,7 stimmen beide Enden; bei 0,4 wird Zandvoort schon zu
weich. Die Aufteilung **innerhalb** einer Strecke (30/70, 60/40) hängt
danach nur noch an der Variantenschwelle.


---

## Punkt 92: Exponent, Schwelle, Gewichtung, Strategieblatt

Vier Entscheidungen des Auftraggebers auf einmal, alle gebaut und
gemessen.

### Der Exponent auf den Streckenfaktor

Der rohe Faktor spannt von 1,263 (Zandvoort) bis 0,537 (Monza) — das
2,35fache. So weit auseinander ließen sich die Stoppzahlen nicht mehr
einfangen. Auf den **Verschleiß** wirkt jetzt `streckenfaktor ^ 0,5`;
der Faktor selbst bleibt roh, sonst fiele
`weich_hoechstens_streckenfaktor` auf allen zwanzig Strecken weg.

**Gibt es Strecken, die bei 1–3 landen?** Ja, acht von zwanzig. Gemessen
über alle Strecken, trocken, mit der neuen Schwelle:

| Spanne | Strecken |
| --- | --- |
| 2–3 Stopps | 12: Zandvoort, Budapest, Shanghai, Oschersleben, Catalunya, Sao Paulo, Austin, Mexiko-Stadt, Yas Marina, Nürburgring, Suzuka, Hockenheim |
| 1–3 Stopps | 8: Norisring, Montreal, Silverstone, Sakhir, Melbourne, Spa, Spielberg, Monza |

Zandvoort landet bei 2–3, Monza bei 1–3 (gefahren 1–2). Keine Strecke
braucht mehr vier Stopps, keine kommt mehr ohne aus.

### Die Variantenschwelle

Sockel und Je-100-km-Anteil je ×1,2: 15 → 18 s. Bei 100 km sind das
36 s, bei 300 km 72 s.

### Die Gewichtung beim Ziehen

Naturgemäß gibt es mehr Varianten mit mehr Stopps: Bei drei
Trockenmischungen hat eine Ein-Stopp-Folge 3² = 9 Reihenfolgen, eine
Zwei-Stopp-Folge 27 und eine Drei-Stopp-Folge 81. Wer gleich verteilt
zieht, lässt das Feld schon deshalb öfter dreimal stoppen — gemessen
planten in Zandvoort 86 und am Nürburgring 97 Prozent der Autos drei
Stopps, ohne dass das jemand entschieden hätte.

Gewichte: **1 Stopp ×10, 2 Stopps ×2,75, 3 Stopps ×1.** Gezogen wird
weiterhin nur aus den zugelassenen Varianten — das Gewicht ändert die
Auswahl nicht, nur ihre Häufigkeit.

### Der Messlauf

Fünf Strecken, Liga 1, trocken, 30 Autos. Drei Spalten, weil sie drei
verschiedene Dinge sagen: **Erwartet** ist, was die Gewichtung aus dem
Variantenvorrat im Mittel macht; **geplant** ist, was dieses eine Feld
gezogen hat; **gefahren** ist, was daraus im Rennen wurde.

| Strecke | Faktor | Erwartet | Geplant | Gefahren | Notstopps |
| --- | ---: | --- | --- | --- | ---: |
| Zandvoort | 1,263 | 2x 36 %, 3x 64 % | 2x 14 %, 3x 86 % | 1x 14 %, 2x 10 %, 3x 76 % | 5 |
| Sao Paulo | 1,132 | 2x 46 %, 3x 54 % | 2x 45 %, 3x 55 % | 1x 14 %, 2x 55 %, 3x 31 % | 5 |
| Nürburgring | 1,074 | 2x 14 %, 3x 86 % | 2x 7 %, 3x 93 % | 2x 21 %, 3x 79 % | 6 |
| Silverstone | 0,890 | 2x 24 %, 3x 76 % | 2x 7 %, 3x 93 % | 1x 14 %, 2x 17 %, 3x 69 % | 4 |
| Monza | 0,537 | 1x 27 %, 2x 41 %, 3x 32 % | 1x 31 %, 2x 31 %, 3x 38 % | 0x 3 %, 1x 59 %, 2x 38 % | 1 |

**Monza liegt bei 59 zu 38 zwischen einem und zwei Stopps** — das Ziel
war 60 zu 40. Getroffen.

**Zandvoort liegt bei 10 zu 76** — aber das ist Würfelglück, kein
Balancing: Erwartet sind 36 %, und ein einzelnes Feld zieht nur
dreißigmal. Über vier Weltseeds gemessen, jeweils geplante
Zwei-Stopp-Rennen: 14 %, 17 %, 0 % und **36 %**. Der dritte Seed hatte
an dem Wochenende gar keine Zwei-Stopp-Variante zugelassen, der vierte
traf die Erwartung genau. Deshalb schreibt das Werkzeug seit diesem
Punkt beide Zeilen nebeneinander — wer nur die gefahrene Verteilung
liest, hält den Wurf für die Einstellung.

### Was noch dazwischensteht

Zwei Dinge erklären den Rest der Abweichung, beide gemessen:

1. **Der Variantenvorrat je Strecke.** Auf trocken/heiß überleben in
   Zandvoort nur 3 von 17 Varianten mit zwei Stopps, am Nürburgring 4
   von 69, in Silverstone 9 von 83. Die Gewichtung kann nur verteilen,
   was der Planer zulässt — sie hebt diese drei Strecken auf 36, 14 und
   24 Prozent, weiter trägt sie nicht.
2. **Das Rennen streicht Stopps.** `planstopp_ab_restprofil = 0,55`
   verschiebt einen geplanten Stopp, solange der Satz noch zu gut dafür
   ist, und wer schon einmal gewechselt hat, fährt den guten Satz dann
   bis ins Ziel. Auf Monza wurden aus 45 % geplanten Drei-Stopp-Rennen
   3 % gefahrene; in Zandvoort entstehen so die 14 % Ein-Stopp-Rennen,
   die der Planer nie vorgesehen hatte.

Wenn die Zielverteilungen genauer getroffen werden sollen, sind das die
beiden Stellschrauben — nicht mehr die Gewichtung.

### Das Strategieblatt

Ein Klick auf die Zahl oben im Rennen öffnet eine Übersicht: je
vertretener Strategie die Mischungsfolge, die geplanten Stopprunden, wie
viele Autos sie fahren, die gerechnete Zeit **ohne Verkehr** und den
mittleren Rückstand **im Rennen** zum gezeigten Zeitpunkt. Der
Unterschied zwischen beiden Spalten ist genau das, was die Rechnung
nicht kennt. Wer welche Strategie fährt, bleibt geheim.


---

## Nachtrag zu Punkt 92: „Es gibt doch einen Pflichtstopp — wie kommt
## Monza auf 0 = 3 Prozent?"

Berechtigte Frage, und die Antwort liegt nicht im Modell, sondern im
**Messwerkzeug**.

`werkzeuge/boxenstopps.py` baute seine Welt mit `spielerliga=1` und maß
dann Liga 1. Ohne Karriere haben die vier Fahrer des Spielers aber alle
Eigenschaften auf **null**. Gemessen:

| | Gesamtwert | Rundenzeit Monza | Runden von 51 |
| --- | ---: | ---: | ---: |
| Sieger | 94.632 | ~85 s | 51 |
| VE1 (Spielerteam) | **0** | ~280 s | **16** |

VE1 hatte den Pflichtstopp sehr wohl eingeplant — sein Plan war **H-W
mit einem Stopp in Runde 34**. Es hat Runde 34 nur nie erreicht: Als der
Sieger ins Ziel kam, stand VE1 auf Runde 16. Die Pflicht war also nie
ausgehebelt, das Auto war nur 3,3-mal zu langsam für die Distanz.

Vier von dreißig Autos, also **13 Prozent des Feldes**, sagten damit
über Strategie gar nichts aus — und genau sie stellten die
Ein-Stopp-Anteile von 13,8 % auf drei der fünf Strecken und die
Null-Stopp-Zeile auf Monza.

Das Werkzeug misst jetzt eine Liga **ohne** Spielerteam (`SPIELERLIGA =
20`): dreißig KI-Autos mit Gesamtwerten von 76.768 bis 94.632. Der
Unterschied ist erheblich:

| Strecke | vorher (mit Nullautos) | nachher |
| --- | --- | --- |
| Zandvoort | 1x 14 %, 2x 10 %, 3x 76 % | 2x 10 %, 3x 90 % |
| Sao Paulo | 1x 14 %, 2x 55 %, 3x 31 % | 2x 62 %, 3x 38 % |
| Nürburgring | 2x 21 %, 3x 79 % | 2x 7 %, 3x 93 % |
| Silverstone | 1x 14 %, 2x 17 %, 3x 69 % | 2x 21 %, 3x 79 % |
| Monza | 0x 3 %, 1x 59 %, 2x 38 % | 1x 48 %, 2x 52 % |

**Keine Null-Stopp-Rennen mehr, keine Ein-Stopp-Ausreißer auf den harten
Strecken, und die Zwangsstopps fallen von 1 bis 6 je Rennen auf 0 bis
1.** Zandvoort liegt damit bei 2 bis 3 Stopps, Monza bei 1 bis 2 — beide
Spannen genau wie gewünscht.


---

## Punkt 93: Die fünfzehn ausgewählten Anzeigepunkte, in sechs Blöcken

Aus `VORSCHLAEGE.md` ausgewählt: A 2, 6, 7, 8, 9, 13, 17, 23 und
B 32, 35, 36, 43, 49, 53, 59. Gebaut in sechs Blöcken.

### Block 1 — die Qualifying-Zeitentafel

**A2 Intervall** als eigene Spalte neben dem Rückstand; die Intervalle
summieren sich genau zum Rückstand. **A6** hebt die Zeile dessen hervor,
der gerade auf seiner gezeiteten Runde ist. **A7** schreibt über die
Tabelle, wer wen gerade um wie viel verdrängt hat. **A8** lässt die neue
Pole golden aufleuchten.

Die Rechnung steht im Kern: `session.letzte_zielankunft(t, fenster)`
liefert Platz, Verdrängten, Abstand und den Polewechsel. Das Fenster
zählt in **Sessionzeit** — bei 50-fachem Zeitraffer wäre eine Sekunde
Bildschirmzeit fast eine Minute Session.

**Drei Testannahmen von mir waren falsch:** Die Mitte zwischen Ausfahrt
und Ziel liegt noch in der Aufwärmrunde. Die dritte Ankunft der
Testsession reiht sich *hinten* ein und verdrängt niemanden. Und in
dieser Session wechselt die Pole **kein einziges Mal** — die
Startreihenfolge des ersten Rennens ist aufsteigend nach
Qualifying-Fähigkeit, das schnellste Auto fährt also zuerst, und seine
132,260 s halten bis zum Schluss.

### Block 2 — Ablauf

**A23** springt zur nächsten Zielankunft, also dorthin, wo sich die
Tafel ändert. **A13** zeigt den Wetterverlauf als Band unter der
Wiedergabeleiste; die Farben sind sequenziell, nicht kategorial.

### Block 3 — Streckengrafik im Qualifying

**A9**: ein Punkt, der die gezeitete Runde abfährt. Den Ort rechnet
`session.ort_auf_der_runde` über die **Sektorgrenzen** — die einzigen
Stellen, an denen Zeit und Ort beide bekannt sind.

### Block 4 — Reifen und Strategie im Rennen

**B35 Alter**, **B36 Reicht**, **B32 Stopp** neben dem Reifenbalken. Die
Restrunden werden **hochgerechnet aus dem, was schon passiert ist**,
nicht aus dem Modell: Ein frischer Satz startet bei 1,0, und was seither
fehlt, verteilt sich auf die gefahrenen Runden.

### Block 5 — Ticker und Wetterband

**B49**: je Art ein Zeichen — Warndreieck, Kreuz, Zahnrad. Wer ausfällt,
bekommt dasselbe Zeichen in Rot; der Ausfall ist keine vierte Art,
sondern das Ende einer der drei. **B43**: dasselbe Wetterband wie im
Qualifying.

### Block 6 — Bilanz, Kompaktmodus, Bestmarke

**B53 Boxenbilanz** als eigenes Blatt. Der Gesamtverlust wird
**gemessen, nicht gerechnet**: die Runde mit Stopp gegen die Medianrunde
desselben Autos. Eine Formel aus Boxengassenlänge und Standzeit kennt
davon nur die Hälfte.

**B59 Kompaktmodus**: nur die Rangliste, große Schrift. Karte, Diagramm
und das rechte Blatt fallen weg — und genau die kosten den Löwenanteil
der Zeit je Bild (D1 bis D10), also ist es nebenbei der schnellste Modus
überhaupt.

**A17 Streckenbestmarke**: die schnellste je hier gefahrene Qualirunde,
mit Fahrer und Jahr. **Getrennt vom Rennrekord geführt** — eine
Qualirunde fährt man auf leerer Strecke mit frischen Reifen; in einem
Topf fiele der Rennrekord nie wieder. Spielstand auf Version 10;
ältere Stände fangen bei null an.

---

## Punkt 101: Eine Liga, 50 Autos, feste Fahrer

Vorgabe des Auftraggebers: „Ich würde gerne auf eine Liga à 50 Autos
reduzieren, 25 Hersteller à zwei Autos, der Spieler hat also auch nur
noch 2 Autos. Das Spreading zwischen bestem Fahrer und schlechtestem soll
ca. 5 Prozent betragen. Lösche die Fahrerentwicklung, den Transfermarkt —
wir spielen mit festen Fahrern, den Editor behalten wir. Geld und
Erfahrungsgewinn auch. Es gibt auch keine Auf- und Abstiege mehr, wir
entschlacken also richtig. Keine Potentiale, da wir feste Stärken haben.
Tempoanker nach wie vor 180 km/h auf Zandvoort, daran die 4 % skalieren."

Vier Nachfragen wurden dabei entschieden:

| Frage | Entscheidung |
| --- | --- |
| Woran hängen die „ca. 5 Prozent"? | **4 % auf die Rundenzeit** |
| Wie viele Plätze bekommen Punkte? | **alle 50**: 100, 90, 80, 76, 72, dann in Zweierschritten bis 20 auf Platz 31, danach 19 bis 1 |
| Was bleibt von der Karriere? | **der Kalender**, der Rest weg |
| Alte Spielstände? | **abweisen**, nichts portieren |

### Die Spanne ergibt `s_letzter` eindeutig

Jede Grenze des Geschwindigkeitsmodells ist linear in
`p = sqrt(S / referenz)`, die Rundenzeit also genau umgekehrt
proportional. 4 % mehr Zeit sind damit 4 % weniger Tempo:

```
v_letzter = 180 / 1,04            = 173,077 km/h
p_letzter = (173,077 - 55) / 125  = 0,944615
s_letzter = 0,944615^2 * 98.000   = 87.445
```

Nachgemessen: 1:28.282 gegen 1:24.887, also +3,9994 %.

### Was bei der Umsetzung selbst entschieden wurde

Diese acht Punkte standen nicht in der Vorgabe. Sie folgen aus ihr, sind
aber Entscheidungen — jede lässt sich zurücknehmen.

1. **Ereignisse (GDD 14) ganz gestrichen.** Alle 30 hingen an Geld,
   Erfahrung, Kaufsperren oder dauerhafter Entwicklung. Ohne diese vier
   bleibt nichts übrig, worauf ein Ereignis wirken könnte.
2. **Defektreparatur gestrichen**, `[defekte] malus_bleibt = false`. Ein
   Defekt gilt nur noch für das Rennen, in dem er fällt. Ohne Geld gäbe
   es sonst keinen Weg, ihn je wieder loszuwerden. Defekte *im* Rennen
   bleiben unverändert.
3. **Streckenkenntnis eingefroren, für alle.** Sie wird einmal bei der
   Welterzeugung je Fahrer und Strecke gewürfelt (im Mittel 35 % der
   vollen Kenntnis, breit gestreut) und bleibt. Auch der Spieler fängt
   nicht mehr bei null an. Wüchse sie weiter, liefe das Feld über die
   Saisons dem Anker aus GDD 9 davon.
4. **`Popularitaet.faktor()` entfernt.** Die Funktion bestimmte allein
   die Höhe der Sponsorenangebote. Der Wert selbst bleibt — er wird
   angezeigt und lässt sich im Editor ändern.
5. **Teamfarbe = Herstellerfarbe.** 25 Teams, 25 Hersteller, eine Farbe
   je Paar; die beiden Autos eines Teams tragen dieselbe. Vorher wurden
   Teamfarben eigens gewürfelt, was bei 25 Teams zu nah beieinander
   liegende Paare ergab.
6. **Die Profilstreuung musste kleiner werden**: `profil_streuung` von
   0,25 auf 0,03 und `bereichs_streuung` von 0,30 auf 0,035. Mit den
   alten Werten lag das Rauschen um ein Vielfaches über der Leiter — die
   4 % wären darin untergegangen und die Reihenfolge wäre reiner Zufall
   gewesen. Gemessen verschiebt sich ein Fahrer von der Stärke zur
   Rundenzeit jetzt um im Mittel 2,1 Plätze, höchstens 8.
7. **Ein Fehler im Ueberholtest behoben** (`kern/rennen.py`): Ein
   *stehendes* Auto konnte überholen. Geprüft wurde `tempo_hinten`, also
   das *erreichbare* Tempo — ein Auto im Stand hat dort einen
   Tempovorteil, den es nicht ausfahren kann. Jetzt muss auch das
   gefahrene Tempo über null liegen.
8. **`werkzeuge/meisterschaftslauf.py` gelöscht.** Es fotografierte die
   Weltmeisterschaft über zehn Ligen, die es nicht mehr gibt.

### Zwei Dinge für die Messphase

* **`[ki] wetter_streuung` steht noch auf 0,45** und wurde nicht
  angefasst. Das ist jetzt zu viel: Gemessen liegen **26 bis 37 von 50**
  Fahrern bei jeder der elf Eigenschaften neben der Matrix exakt auf dem
  Skalenmaximum von 100.000, weil ein Mittelwert um 92.000 plus 45 %
  Streuung oben abgeschnitten wird. Regenfahren, Reifenflüsterer und die
  anderen trennen das Feld dadurch nur noch nach unten. Zum Vergleich:
  Bei den Matrixwerten sind es 2 bis 3 von 50. Ein Wert um 0,03 bis 0,08
  entspräche dem, was oben noch Platz hat — das ist aber ein
  Balancing-Wert und damit eine Entscheidung des Auftraggebers.
* **Die schnellste Rennrunde liegt unter der Polezeit** (gemessen
  Sakhir: 1:32.338 gegen 1:34.020). Das ist kein neuer Effekt — das
  Qualifying fährt auf einer grüneren Strecke als das Rennen —, fällt im
  dichten Feld aber deutlicher auf als vorher.

---

## Punkt 102: Führungsrunden

Vorgabe des Auftraggebers: „Eine Statistik noch als zusätzlicher Tab
Führungsrunden. Zählen wer ist vorne bei Start/Ziel, in den Renn-Screen
bei den verschiedenen Tabs rechts ergänzen, aber auch als Statistik im
Hauptmenü bei den Statistiken ergänzen."

Drei Nachfragen wurden dabei entschieden:

| Frage | Entscheidung |
| --- | --- |
| Was zeigt das Blatt im Rennen? | **Live mitzählen** bis zum Abspielzeitpunkt, wie Zeitenmonitor und Meisterschaft |
| Alte Spielstände (Version 12)? | **Abweisen**, wie bei Punkt 101 |
| Wo in den Statistiken? | **Nur eine Spalte** in der Bestenliste der Karriere, keine eigene Ansicht |

### Die Zählregel

Gezählt wird an der **Start/Ziel-Linie**: Wer eine Runde als Erster
abschließt, hat sie geführt. Die Daten lagen schon vor —
`Rundenprotokoll.rundenende_ms` hält je Auto fest, wann es jede Runde
beendet hat, und das kleinste Rundenende gehört dem Führenden.

Drei Dinge folgen daraus von selbst:

* **Die Startaufstellung zählt nicht.** Vor dem Start steht überall
  null. Gemessen an einem umgedrehten Feld ist das kein Haarspalten:
  Dort fährt ein Auto 170 m hinter der Pole los und ist trotzdem 4,5 s
  früher an der Linie.
* **Ein Boxenstopp fällt richtig aus.** Wer in Runde 30 an die Box geht,
  schließt Runde 30 nicht als Erster ab.
* **Die Summe ist die Renndistanz.** Jede Runde hat genau einen
  Führenden — daraus wird auch der Nenner des Anteils, ohne dass ihn
  jemand mitreichen müsste.

### Gemessen

Zwei Wochenenden in trocken, Hauptseed 0:

```
Sakhir     55 Runden   FID 15, VER 13, MEL 12, FOI 12, SCH 3    10 Wechsel
Melbourne  56 Runden   VER 29, MEL 14, SCH 6, OBE 4, RAU 3       7 Wechsel
```

Fünf verschiedene Führende je Rennen und sieben bis zehn Wechsel an der
Linie — das ist die Vier-Prozent-Spanne aus Punkt 101, von der anderen
Seite betrachtet.

**Beide Rennmodelle liefern die Zahl**, aber nicht dieselbe: Gemessen an
einem Achtrundenrennen in Monza hatte die volle Simulation vier
Führungswechsel, der Schnellmodus keinen. Das ist derselbe Unterschied
in der Verkehrsdynamik, der schon bei den Überholmanövern steht — der
Schnellmodus lässt je Runde nur einen Überholversuch zu.

### Was bei der Umsetzung auffiel

* **Sechs Reiter passen nicht mehr nebeneinander.** Die Blattleiste
  rechts braucht 688 px, verfügbar sind rund 570; Qt blendet Rollpfeile
  ein, und „Zeitenmonitor" rutscht aus dem Bild. Ein kürzeres Etikett
  löst es nicht — mit „Führung" wären es immer noch 639 px. Offen: Wer
  das behoben haben will, muss entweder die rechte Spalte breiter
  machen oder mehrere Etiketten kürzen. Das ist eine Layoutfrage und
  wurde nicht eigenmächtig entschieden.

---

## Punkt 103: Vor der ersten Überfahrt gibt es keinen Rückstand

Aufgefallen beim Fotografieren der Standbilder zu Punkt 101: Vor dem
Start standen in der Rangliste absurde Abstände — P2 lag +14.473
zurück, P50 volle +11:49, und zwar bevor die Ampel aus war.

Gemessene Ursache: Die Anzeige schätzte den Abstand aus Strecke geteilt
durch Tempo, wenn noch kein gemeinsamer Messpunkt vorlag. Im ersten
50-ms-Bild kriechen die Autos mit **0,345 m/s** los; 5 m Startabstand
geteilt durch dieses Tempo sind 14,47 s **je Startplatz**. Die Schwelle
aus Punkt 83 („wer steht, hat keinen Abstand", `TEMPO_STEHT = 0,1 m/s`)
griff nicht, weil die Autos eben nicht ganz standen.

Drei Wege standen zur Wahl: die Schwelle hochsetzen, gar nicht schätzen,
oder im Stand den Startplatzabstand in Metern zeigen.

**Entscheidung des Auftraggebers: gar nicht schätzen.** „Bis zum ersten
Mal Start/Ziel hat ein Fahrer keinen Rückstand."

Das fiel mit dem Modell zusammen, ohne dass etwas erfunden werden
musste: Der erste der acht Messpunkte je Runde liegt auf der
Start/Ziel-Linie. `Rennverlauf.abstand_ms` liefert `None`, solange die
beiden keinen gemeinsamen Punkt passiert haben — also genau bis zur
ersten Überfahrt. Die Anzeige gibt diesen Fall jetzt als Strich weiter,
statt ihn mit einer Schätzung zu füllen.

Gemessen in Sakhir: Bei t = 0 und t = 1 s steht überall ein Strich, ab
rund zwei Sekunden stehen echte Zeiten da (+1.010 s für P2 — die
Differenz der beiden Linienüberfahrten, nicht geschätzt).

Betroffen sind beide Spalten, „Zeit / Rückstand" und „Intervall": Sie
gehen durch dieselbe Funktion. Die km/h-Spalte bleibt, wie sie war; sie
braucht das Momentantempo weiterhin und hat ihre eigene Schwelle.

---

## Vorschläge 2, 15 und 16: die drei ausgewählten

Aus den dreißig Vorschlägen (`VORSCHLAEGE.md`, Stand 2026-09-22) hat der
Auftraggeber drei gewählt: **2** (Führungswechsel im Ticker), **15**
(Führungsrunden in der Fahrerkarte) und **16** (Führungsrunden je
Strecke und Wetterlage). Alle drei bauen auf Punkt 102 auf.

### Vorschlag 15: Fahrerkarte

Zwei Zeilen, keine neue Mechanik. Im Reiter **Saison** steht die Zahl
der laufenden Saison (aus `Statistik.saisonfuehrung`), im Reiter
**Laufbahn** die der ganzen Karriere, dort mit Nenner und Anteil:
„387 von 1.276 (30,3 %)". Wer nie geführt hat, steht auf „0" — der
Nenner steht trotzdem daneben, sonst wäre die Null nichtssagend.

### Vorschlag 2: Führungswechsel im Ticker

Das Blatt Meldungen zeigte nur Zwischenfälle. Ein Führungswechsel ist
keiner, gehört aber in dieselbe Liste: Beide Quellen stehen jetzt nach
Zeit gemischt, neueste zuerst, unter einem fünften Zeichen (⚑, blau)
neben ⚠ ✖ ⚙.

Die Kastenüberschrift zählt sie **getrennt** — „Meldungen — 24
Zwischenfälle, 15 Führungswechsel". Eine gemeinsame Zahl wäre gelogen.

Gemessen an einem vollen Rennen in Sakhir (55 Runden, gewürfeltes
Wetter): 24 Zwischenfälle, 15 Führungswechsel, fünf verschiedene
Führende (MEL 30, VER 12, FID 8, OBE 4, FOI 1).

#### Was bei der Umsetzung auffiel

Der Standardlauf der Anzeige-Tests (Seed 4711, vier Runden in Sakhir)
hat **keinen einzigen Führungswechsel** — einer fährt vorn durch. Zwei
neue Tests standen damit auf Sand: Ohne Wechsel ist die leere Liste
richtig, und der Test bliebe grün, auch wenn die Anzeige kaputt wäre.

Gemessen über die Seeds 1 bis 24 auf derselben Strecke: neun Seeds
liefern null Wechsel, Seed 4 liefert drei (VER, FOI, MEL, FOI) und dazu
sieben Zwischenfälle — also beide Quellen in einem Rennen. Dafür gibt
es jetzt ein eigenes Fixture; `tests/oberflaeche.rennverlauf` nimmt den
Seed als Parameter.

### Vorschlag 16: je Strecke und je Wetterlage

`Bilanz` bekommt dieselben zwei Zähler wie `Karrierezahlen`, und
`Statistik.verbuche_fuehrungsrunden` nimmt Strecke und Lage entgegen.
Bleiben sie leer, bleiben die Bilanzen unberührt — es wird keine Zeile
angelegt, die nie ein Rennen gesehen hat.

Gemessen über eine ganze Saison (20 Rennen, 1.276 Runden, Seed 0):
15 von 50 Fahrern haben mindestens eine Runde geführt, der Beste 387
Runden oder 30,3 Prozent.

```
Streckenbilanz des Besten          Wetterbilanz
  Oschersleben   80 von  80 100,0 %  trocken      178 von 519  34,3 %  (9 Rennen)
  Zandvoort      69 von  69 100,0 %  wechselhaft  160 von 367  43,6 %  (6 Rennen)
  Nürburgring    57 von  58  98,3 %  heiss         35 von 261  13,4 %  (4 Rennen)
  Catalunya      35 von  64  54,7 %  regen         14 von 129  10,9 %  (1 Rennen)
  Norisring      14 von 129  10,9 %
```

Vier Strecken flag to flag, auf dem Norisring dagegen 129 Runden und
nur 14 davon vorn. Erst der Anteil macht das vergleichbar — die bloße
Zahl hängt an der Renndistanz.

Probe über die fünf Bestgeführten: Die Summe über die Strecken und die
Summe über die Lagen ergeben beide genau die Karrierezahl, und dasselbe
gilt für den Nenner. Zwei Tests halten das fest.

#### Was bei der Umsetzung auffiel

**Die Bilanzspalten standen zweimal im Code** — als Liste in
`statistikseite.py` und als Literale in `fahrerkarte.py`, dazu die
Felder selbst einmal als Helfer und einmal von Hand geschrieben. Zwei
neue Spalten hätten an vier Stellen nachgetragen werden müssen. Sie
liegen jetzt einmal in `rennmanager/ui/tabellen.py`
(`BILANZSPALTEN`, `bilanzfelder`, `setze_bilanzsortierung`); beide
Seiten lesen von dort.

**Der Spielstand geht auf Version 14**, Mindestversion ebenfalls 14.
Entscheidung des Auftraggebers: abweisen wie bei Punkt 101 und 102,
nichts umrechnen. Die Führungsrunden je Strecke stehen in keinem
älteren Stand, und nachträglich lassen sie sich nicht ermitteln — die
Rennen von damals sind nicht aufgehoben.

---

## Vorschlag 23: Die Blattleiste rollte — und was dabei auffiel

Steht seit Punkt 102 offen. Die alte Notiz sagte „688 px gebraucht,
rund 570 da" — die 570 waren geschätzt. Nachgemessen am wirklich
ausgelegten Fenster mit laufendem Rennen:

| Fenster | Blatt breit | Leiste braucht | fehlt |
|---|---|---|---|
| 1366 px | 358 px | 688 px | **330 px** |
| 1600 px | 450 px | 688 px | 238 px |
| 1920 px | 579 px | 688 px | 109 px |
| 2560 px | 837 px | 688 px | passt |

Erst ab rund 2560 px Fensterbreite passt es.

### Zwei der drei vorgeschlagenen Wege tragen nicht

Vorschlag 23 nannte drei: rechte Spalte breiter, Etiketten kürzer, zwei
Reihen. Gemessen:

* **Rechte Spalte breiter** geht nicht. Das Streckenbild hat eine harte
  Mindestbreite von 424 px (`Streckenansicht.setMinimumSize(420, 320)`)
  und gibt nichts ab. Die Breite käme also nur von der Rangliste — und
  die ist selbst 393 px zu schmal. Erster Versuch mit
  `setStretchFactor` änderte übrigens gar nichts: Der Faktor wirkt nur
  auf noch nicht gesetzte Größen, für schon ausgelegte Teiler braucht
  es `setSizes`.
* **Zwei Reihen** kann `QTabWidget` nicht. Das wäre ein eigenes Widget.
* **Kürzere Etiketten** („Zeiten | Ideal | Meister | Meldungen | Box |
  Führung") bringen 688 px auf 405 px. Reicht ab 1600 px Fenster, bei
  1366 fehlen noch 47 px.

### Gewählt: die Leiste senkrecht an die linke Kante

`setTabPosition(QTabWidget.West)`. Dieselbe Leiste braucht dann 26 px
Breite und 688 px Höhe — und Höhe ist da: 963 px bei einem 1080er
Fenster, 1206 px bei einem 1440er. Gemessen passt es bei **jeder**
Fenstergröße. Nebenbei bekommen die Tabellen die Zeile Höhe zurück, die
die waagerechte Leiste fraß.

Der Platz ist nicht in der Breite, sondern in der Höhe — das war der
Punkt, den die drei alten Wege übersahen.

Ein Test hält den Deckel fest: Die Leiste muss senkrecht stehen und darf
nicht mehr als 963 px Höhe brauchen. Ein siebtes Blatt wirft ihn um,
statt stillschweigend wieder Rollpfeile zu erzeugen.

### Dabei aufgefallen: die Rangliste ist schlimmer dran

Sie braucht 1195 px für ihre 16 Spalten und bekommt 802 — **393 px
fehlen**, sie rollt waagerecht. Im Rennen fallen damit sechs Spalten aus
dem Bild, und zwar genau der Reifen- und Strategieblock:

```
sichtbar:  Pos  Auto  Fahrer  Team  +/-  Rd  Zeit/Rückstand  Intervall  km/h  Ø km/h
aus dem Bild:  Mischung  Reifen  Alter  Reicht  Stopp  Status
```

Die teuersten Spalten: Team 172 px, Status 130 px, Zeit/Rückstand
121 px, Fahrer 105 px, Reifen 96 px. Drei davon wegzulassen würde
reichen (423 px).

**Der Kompaktmodus löst das aber schon.** Gemessen: Mit ausgeblendeter
Karte und ausgeblendeten Blättern hat die Rangliste 1844 px und braucht
1828 — es passt, wenn auch knapp. Wer die volle Tabelle sehen will,
drückt „Kompakt"; die Dreispaltenansicht ist zum Zusehen auf Karte und
Blätter gedacht. Ob das so bleiben soll oder ob die Normalansicht
weniger Spalten zeigen sollte, ist eine Entscheidung über Inhalt und
steht offen.

### Und noch etwas: das Fenster lässt sich nicht kleiner als 1197 px hoch machen

Gemessen: `resize(1920, 1080)` liefert ein Fenster von 1920x1197,
`resize(1366, 768)` eines von 1371x1197. `minimumSizeHint().height()`
des Hauptfensters ist 1197. Auf einem 1080er Bildschirm — der
verbreitetsten Auflösung — ist das Fenster also 117 px höher als der
Schirm.

Die Rennseite ist nicht die Ursache; ihre eigene Mindesthöhe liegt bei
350 px. Die 1197 kommen aus einem anderen Reiter des Hauptfensters
(`QStackedWidget` nimmt das Maximum über alle Seiten). Nicht weiter
verfolgt — das ist ein eigener Punkt und keine Layoutfrage der
Blattleiste.
