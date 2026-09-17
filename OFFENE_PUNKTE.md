# Offene Punkte – Vorschläge zur Entscheidung

Das GDD nennt an vielen Stellen eine Mechanik, ohne sie zu beziffern.
Dieses Dokument listet jede solche Lücke, drei Varianten und die getroffene
Entscheidung. **Stand 2026-09-17: 31 Punkte entschieden, 3 noch offen.**

Die entschiedenen Werte stehen in `konfiguration/balancing.toml`; der
Abschnitt `[offen]` dort ist leer. Jede Entscheidung lässt sich ändern,
ohne Code anzufassen — die Nummer unten führt zur Begründung.

---

## Noch offen — hier fehlt Ihre Entscheidung

### O1. Herstellerliste

`konfiguration/hersteller.toml` trägt `bestaetigt = false`. GDD 12 nennt
„20 reale Autohersteller, nur Name und Farbe", aber keine konkreten. Meine
Platzhalterliste (Alfa Romeo bis Toyota) ist nie bestätigt worden.

| | Variante |
| --- | --- |
| **A** | Platzhalterliste übernehmen und `bestaetigt = true` setzen |
| **B** | Eigene 20 Hersteller vorgeben |
| **C** | Erfundene Namen statt echter Marken (vermeidet Markenrecht von vornherein) |

### O2. Referenzstrecke der Kalibrierung

GDD 9 verlangt eine „kurvige Referenzstrecke", nennt aber keine. Ich habe
**Zandvoort** gewählt — mit 46 % den geringsten Geradenanteil aller 20
Strecken, laut GDD 3 „Steilkurven, eng". Ein Wechsel ist ein Aufruf von
`werkzeuge/kalibriere.py --schreiben`.

| | Variante | Geradenanteil |
| --- | --- | --- |
| **A** | Zandvoort (gesetzt) | 46 % |
| **B** | Suzuka | 50 % |
| **C** | São Paulo | 48 % |

### O3. Dateiname der Arbeitsregeln

Das GDD sagt, die Regeln kommen als `CLAUDE.md` ins Repo; die Datei heißt
`Claude.md`. Ich habe **nicht** umbenannt: Auf Windows und macOS ist das
Dateisystem nicht case-sensitiv, eine reine Groß-/Kleinschreibungsänderung
macht dort beim Auschecken Ärger.

| | Variante |
| --- | --- |
| **A** | So lassen (Claude Code liest die Datei ohnehin) |
| **B** | Auf `CLAUDE.md` umbenennen, wie im GDD beschrieben |

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

### Ereignisse

| Nr. | Punkt | Varianten | Ab |
| --- | --- | --- | --- |
| 20 | Geld- und Erfahrungsbeträge der Ereignisse | A klein · **B spürbar** · C groß | 10 |

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
