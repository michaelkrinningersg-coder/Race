# Offene Punkte – Vorschläge zur Entscheidung

Das GDD nennt an vielen Stellen eine Mechanik, ohne sie zu beziffern.
Dieses Dokument listet jede solche Lücke, drei Varianten und die getroffene
Entscheidung. **Stand 2026-09-17: alle 41 Punkte entschieden.**

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
