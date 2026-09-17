# Herkunft der Streckendaten

Die Dateien in `ideallinie/` und `mittellinie/` stammen unveraendert aus der
[TUMFTM racetrack-database](https://github.com/TUMFTM/racetrack-database) des
Lehrstuhls fuer Fahrzeugtechnik der Technischen Universitaet Muenchen.

**Lizenz: LGPL-3.0** (Volltext in `LICENSE`). Die Dateien sind unveraendert
uebernommen; ausgewaehlt wurden die 20 Strecken der Saison laut GDD 3.

## Inhalt

| Ordner | Spalten | Bedeutung |
| --- | --- | --- |
| `ideallinie/` | `x_m, y_m` | Fertige Ideallinie in Metern. Darauf fahren die Autos (GDD 3). |
| `mittellinie/` | `x_m, y_m, w_tr_right_m, w_tr_left_m` | Geglaettete Mittellinie mit Streckenbreite rechts und links. |

Beide Linien sind geschlossene Runden; der letzte Punkt schliesst mit rund 5 m
Abstand an den ersten an. Der erste Punkt ist die Start/Ziel-Linie.

Die Ideallinien liegen bereits bei rund 5 m Punktabstand, aber nicht exakt.
`rennmanager.kern.strecke` tastet sie deshalb neu ab (GDD 3).

## Datenqualitaet

Die README der Quelle weist darauf hin, dass die Qualitaet der Ausgangsdaten
(GPS-Punkte und Satellitenbilder) je nach Ort stark schwankt. Ein Abgleich der
laengsten Geraden mit den realen Strecken ist bei der Uebernahme erfolgt:
Shanghai 1.160 m (real rund 1.170 m), Mexiko-Stadt 1.210 m, Monza 1.240 m,
Sakhir 1.055 m (real rund 1.090 m), Spa 1.060 m (Kemmel-Gerade rund 1.000 m).

## Nicht enthalten

Monaco, Imola und Mugello fehlen im Datensatz (GDD 3 und 16). Sie liessen sich
ueber [bacinger/f1-circuits](https://github.com/bacinger/f1-circuits) nachruesten,
dort allerdings nur als Linie ohne Breite.
