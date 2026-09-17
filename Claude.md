## 17. Arbeitsregeln für Claude Code

Diese Regeln kommen als `CLAUDE.md` ins Repo; alle Punkte in Abschnitt 16 sind entschieden, die Umsetzung kann starten.

```markdown
# Arbeitsregeln
- Das GDD ist die verbindliche Vorgabe. Nichts hinzufügen, was dort nicht steht.
- Bei jeder Unklarheit oder fehlenden Angabe: nachfragen, nicht selbst entscheiden.
- Vor jedem neuen Modul: kurzen Plan zeigen und auf Freigabe warten.
- Keine eigenen Features, Mechaniken, Balancing-Werte oder Designänderungen ohne Rückfrage.
- Alle Balancing-Werte zentral in einer Konfigurationsdatei, nie im Code verstreut.
- Zeiten intern als ganze Millisekunden; Anzeige m:ss.mmm bzw. h:mm:ss.mmm.
- Jede Simulation mit Seed, damit Ergebnisse reproduzierbar sind.
- Simulationskern getrennt von der Oberfläche und mit Tests.
- Kleine Schritte, jeder Schritt lauffähig und getestet.
- Kommunikation und Oberfläche auf Deutsch.
```

**Reihenfolge der Umsetzung (Vorschlag)**

1. Projektgerüst (Python, PySide6), Konfigurationsdatei, Build-Workflow für die .exe
2. Streckenimport (TUMFTM), Segmenttypen, Sektoren, Darstellung einer Strecke
3. Geschwindigkeitsprofil für ein Auto, Rundenzeit in Tausendsteln, Kalibrierung gegen Abschnitt 9
4. 30 Autos, Start, Überholen, Seitenleiste und Zeitenmonitor, Zeitraffer
5. Qualifying, Zufallssystem, Wetter
6. Fehler, Unfälle, Defekte, Reifenverschleiß
7. Fahrer, Teams, 600 KI-Autos, Ligen
8. Kalender, Zeitmodell, Upgrades, Kosten, Einnahmen, Sponsoren
9. Saisonwertung, Schnellsimulation, Auf-/Abstieg
10. Ereignisse, Statistiken, Speichern und Laden
