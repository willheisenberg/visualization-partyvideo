# Stufe-0-Test auf dem Raspberry Pi

Zip: `dist/visualization.partyvideo-0.1.0.zip`. Installation und alle Eingriffe auf dem
Pi macht der Maintainer.

## Installation

1. Zip auf den Pi bringen (z. B. über die Samba-Freigabe nach `/storage/downloads`).
2. Kodi → Einstellungen → System → Addons → „Unbekannte Quellen“ erlauben (falls noch aus).
3. Kodi → Addons → Aus ZIP-Datei installieren → Zip wählen.
   - [ ] Installation ohne Fehlermeldung
   - [ ] Unter „Meine Addons → Musikvisualisierungen“ erscheint „Party Video“
   - [ ] Unter „Meine Addons → Programme“ erscheint „Party Video“
   - War schon eine ältere Stufe-0-Version installiert: Kodi nach der (Neu-)Installation
     einmal neu starten. Eine bereits geladene `.so` wird nicht zuverlässig ersetzt.

## Diagnose-Script

4. Programme → Party Video starten, Deno-Frage mit „Ja“ beantworten.
   Der Pi braucht dafür Internet. Der Deno-Download (rund 45 MB) kann etwas dauern;
   Kodi hängt in der Zeit nicht, das Ergebnisfenster erscheint danach von selbst.
   - [ ] Umgebung zeigt Python 3.11 (aarch64)
   - [ ] Visualisierungs-Einstellung: „Wert vorher“ notieren (wird in Schritt 7 gebraucht): ________
   - [ ] Visualisierungs-Einstellung: „Wert danach“ ist `'visualization.partyvideo'`
   - [ ] „SetSettingValue(vorher)“ ist `True` (Einstellung wiederhergestellt)
   - [ ] Deno: `Exit-Code 0` und eine Zeile, die mit `deno ` beginnt (z. B. `deno 2.x.y`)
   - [ ] Deno-Datei wurde danach automatisch gelöscht (Zeile `deno: …, … MB`, keine Zeile
     „Löschen fehlgeschlagen“ oder „Verzeichnis nicht entfernt“)

## Visualisierung

5. Einstellungen → Player → Musik → Visualisierung → „Party Video“.
6. Warteschlange oder Playlist mit mindestens zwei Titeln starten (jede Musikquelle genügt),
   Vollbild-Wiedergabe öffnen.
   - [ ] Pinke Fläche im Vollbild, Musik läuft ohne Aussetzer
   - [ ] Nach Songwechsel weiterhin pinke Fläche
7. Visualisierung wieder auf den notierten „Wert vorher“ (z. B. „Keine“) stellen.

## Rückmeldung

8. Kodi vor der Rückmeldung **nicht** neu starten – sonst rotiert `kodi.log` und die
   Testzeilen landen in `kodi.old.log`.
9. Claude Bescheid geben und dabei den Checklistenstand nennen (welche Punkte abgehakt
   sind, welche nicht); Claude liest `kodi.log` per ssh (nur lesend) aus.
