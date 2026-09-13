# Stufe-1-Test auf dem Raspberry Pi

Zip: `dist/visualization.partyvideo-0.2.0.zip`, Testvideos: `dist/testvideos/`.
Schreibende Schritte auf dem Pi macht Agent nur nach ausdrücklicher Freigabe im Chat.

## Vorbereitung (Agent, nach Freigabe)

1. Addon-Ordner aus dem Zip nach `/storage/.kodi/addons/visualization.partyvideo/` kopieren
   (ohne die Symlink-Einträge) und Kodi neu starten (`systemctl restart kodi`), weil eine
   bereits geladene `.so` nicht ersetzt wird.
2. Testvideos nach `/storage/videos/partyvideo-test/` kopieren.
3. `scripts/pi-set-state.sh 1 /storage/videos/partyvideo-test/partyvideo-1080p30.mp4`

## Prüfungen (Maintainer am Fernseher)

4. Musik mit mindestens zwei Titeln starten, Visualisierung „Party Video“, Vollbild.
   - [ ] Testbild (bewegte Farbflächen, Zähler) läuft flüssig, Musik ohne Aussetzer
   - [ ] Nach etwa 20 Sekunden beginnt das Video ohne sichtbaren Sprung von vorn
   - [ ] Nach einem Songwechsel läuft das Video an etwa derselben Stelle weiter (kurzer Stillstand ist in Ordnung)
5. Agent setzt Revision 2 (720p).
   - [ ] Wechsel auf das 720p-Testbild innerhalb einer Sekunde, flüssig, bildschirmfüllend
6. Agent setzt Revision 3 (Farbbalken).
   - [ ] Balken von links: Grau/Weiß, Gelb, Cyan, Grün, Magenta, Rot, Blau – keine vertauschten oder blassen Farben
7. Agent setzt Revision 4 (leere Quelle).
   - [ ] Schwarzes Bild, Musik läuft weiter
8. Agent setzt Revision 5 (nicht vorhandene Datei).
   - [ ] Schwarzes Bild, kein Absturz
9. Agent setzt Revision 6 (wieder 1080p).
   - [ ] Video läuft wieder

## Seitenverhältnis

Nach Revision 6: `scripts/pi-set-state.sh 7 /storage/videos/partyvideo-test/partyvideo-4x3.mp4`.
- [ ] Auf einem 16:9-Bildschirm seitlich schwarze Balken, Bild mittig und unverzerrt.
- [ ] Wechsel zurück mit Revision 8 und `partyvideo-1080p30.mp4`: bildschirmfüllend.

## Rückmeldung

10. Kodi vor der Rückmeldung nicht neu starten; Checklistenstand im Chat nennen.
    Agent liest `renderer.json`, `kodi.log` und die CPU-Last (`top`) nur lesend aus.

## Aufräumen (Agent, nach dem Test)

Der Maintainer hat die schreibenden Schritte auf dem Pi unter der Bedingung freigegeben,
dass die Testvideos danach wieder entfernt werden. Nach der Auswertung daher:

11. `scripts/pi-set-state.sh 9 ""` – leere Quelle setzen, damit die Visualisierung
    abgeschaltet ist und das Addon keine Videodatei mehr geöffnet hält.
12. `/storage/videos/partyvideo-test/` auf dem Pi löschen.
13. Löschung nur lesend bestätigen (`ls` auf `/storage/videos/`), Ergebnis im Bericht nennen.
