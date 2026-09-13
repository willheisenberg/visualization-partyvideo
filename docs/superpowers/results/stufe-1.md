# Stufe 1 – Fortsetzung am 12. September 2026

## Übernommener Stand

Claude hatte Plan 2 bis zum Abschlussreview umgesetzt und Version 0.2.0 auf dem
Pi installiert. Der Maintainer hatte Videoausgabe und Fortsetzung nach einem
Titelwechsel bestätigt. Die sechs technischen Nachbesserungen des Abschlussreviews
waren beim Kontingentabbruch noch offen.

## Nachbesserungen

- Aufholen: Ein Uhr-Reset beendet das Überspringen von Nichtreferenzbildern nicht
  mehr. Erst zwei Sekunden dekodierter Bilder mit mindestens 25 Prozent zeitlicher
  Reserve und aufgeholter Anzeige erlauben normale Dekodierung. Die Messung zählt
  tatsächliche Dekodiervorgänge, keine wiederholten Warteaufrufe für dasselbe Bild.
- Grafik-Upload: Pixel-Unpack-Buffer, Zeilenlänge und Zeilen-/Pixel-Offsets werden
  neutralisiert und danach ebenso wie das Alignment wiederhergestellt.
- Texturgrenzen: Alle Ebenen einschließlich Stride werden gegen
  GL_MAX_TEXTURE_SIZE geprüft. Zu große Bilder ergeben Schwarzbild und eine
  deduplizierte Fehlermeldung im Kodi-Log.
- Fehler beim Initialisieren der Grafik: Schwarze Fläche, kein permanentes
  IsDirty und keine aktive Decoder-Anmeldung dieser Instanz.
- test.sh baut jetzt auch die ausgelieferte Kodi-/GLES-Bibliothek und prüft ihr Zip.
- Zusätzliches 4:3-Testvideo und Prüfung der seitlichen schwarzen Balken.

## Verifikation

`./test.sh`: ruff erfolgreich, 5 ELF-Fälle, 7 Zip-Fälle, 59 C++-Tests erfolgreich;
anschließend aarch64-Addon einschließlich Paketprüfung erfolgreich gebaut.
Zwei deterministische Regressionstests prüfen Resync, echte Erholung, weiterhin
zu langsames Dekodieren und Rücksetzen beim Quellenwechsel.

Installiertes Zip: `dist/visualization.partyvideo-0.2.0.zip`.
SHA-256: `be2b19c308458e537dd1b68f692f4be4b762c7a0bdece4247ebebf5f2e91a3c4`.
Bibliothek lokal und auf dem Pi:
`b115a3eae06fd065fa544a36f7a581771cfd5c9f990071c77a942b9466736eb6`.

Deployment mit der bestehenden Freigabe ausgeführt; Kodi einmal neu gestartet.
Vorherige Addon-Dateien gesichert unter
`/storage/.cache/partyvideo-backups/20260912-162013`.
Kodi hat Version 0.2.0 erkannt und den Service gestartet. Um 16:21:42 hat die neue
Instanz Revision 1 geöffnet; renderer.json meldet 1920×1080/h264/playing ohne
Fehler oder Warnung. JSON-RPC bestätigt Audiovisualisierung und laufenden
SoundCloud-Titel. Das zusätzliche 4:3-Video
liegt unter `/storage/videos/partyvideo-test/partyvideo-4x3.mp4`.

## Noch offen

- Maintainer bestätigt: korrigiertes Video läuft flüssig, auch nach Titelwechsel.
  Noch offen: Farben, Seitenverhältnis, Quellenwechsel und Fehlerfall. GL-Laufzeitverhalten ist nicht durch die
  automatisierten Kerntests abgedeckt.
- Testvideos nach dem Gerätetest entfernen; vorher mit neuer Revision die Quelle
  leeren. Sie sind derzeit noch vorhanden, weil der Sichttest läuft.
- Plan 3 muss fehlende und nach einem Kodi-Neustart veraltete renderer.json-Dateien
  berücksichtigen. `playing` allein beweist keine aktuell aktive Visualisierung.
- Auf ausdrücklichen Wunsch vorgezogener Service-Ausbau: bei Player.OnAVStart
  Visualisierung öffnen und Musik-OSD/Titelinfo schließen, sofern Party Video
  ausgewählt ist und eine Quelle gesetzt ist. Gerätetest dieser Ergänzung läuft.
- YouTube-Auswahl, Downloads und Bot-Steuerung gehören zum anschließenden Plan 3.

## Automatische Ansicht beim Titelwechsel

Auf Nutzerwunsch am 12.09.2026 ergänzt und um 16:30 nur den Python-Service auf dem
Pi neu gestartet (alter Service laut Kodi-Log beendet, neuer erfolgreich gestartet).
Kodi und Audiowiedergabe blieben aktiv. Sechs neue Python-Tests prüfen die
Aktivierungsbedingungen, das gezielte Schließen und den Info-Toggle sowie das
OnAVStart-Ereignis. Vollständiger Testlauf einschließlich 59 C++-Tests und
Addon-Zip erfolgreich. Das Paket-Gate erkannte zunächst einen durch Testimporte
erzeugten Python-Cache; Tests schreiben diesen Cache jetzt nicht mehr ins Addon.

Der Kodi-21.3-Quelltext in GUIWindowVisualisation.cpp bestätigt SetShowInfo(true)
beim Fensterstart und beim Wechsel der Track-Metadaten. Der Service reagiert auf
Player.OnAVStart mit begrenzten Nachläufen nach 0,25/0,75/1,5 Sekunden; später manuell
geöffnete Menüs bleiben bedienbar. Ein laufender Service erhält dieselbe Behandlung
beim Neustart während Musik läuft. Die Sichtbestätigung des automatischen
Ausblendens beim nächsten echten Titelwechsel steht noch aus.

Vorherige Service-Datei:
`/storage/.cache/partyvideo-backups/service-before-autoshow.py`.
Aktuelles Zip (ersetzt den oben dokumentierten Renderer-Build), SHA-256:
`dbeb61e538ecc2f1f220912f039189a27bf02c8a0d8f0856bc549d4c2358a903`.

## Rückkehr nach manueller Bedienung (abschließender Stand)

Der Nutzer testete auch den manuellen Wechsel mit „Zurück“. Dieser Fall war durch
den bisherigen Titelstart-Auslöser nicht erfasst. Der Service prüft nun zusätzlich
alle 0,5 Sekunden, ob drei Sekunden keine Bedienung stattfand. Aus Hauptmenü,
Musikansicht, Musikplaylist und Visualisierung kehrt er dann zum Video zurück;
Einstellungen und fremde modale Dialoge werden nicht geschlossen. Voraussetzung
bleibt aktive Audiowiedergabe, gesetzte Quelle und ausgewähltes Party Video.
Titelstarts werden direkt über xbmc.Player.onAVStarted verarbeitet.
GUI-Befehle werden asynchron und einzeln ausgeführt; erst beim nächsten Durchlauf
wird der veränderte GUI-Zustand bewertet.

Live-Test um 16:55 auf dem Pi:
1. Vorher: Audio aktiv, Visualisierung aktiv, Titelinfo aus.
2. Input.Back: Hauptmenü aktiv, Visualisierung inaktiv.
3. Nach sechs Sekunden: Visualisierung wieder aktiv, Hauptmenü inaktiv,
   Titelinfo aus, Audio weiterhin aktiv.

Verifikation: neun Python-Tests, 59 C++-Tests, 5 ELF- und 7 Zip-Prüffälle,
ruff und vollständiger aarch64-Paketbuild erfolgreich. Nur der Python-Service
wurde auf dem Pi aktualisiert; Kodi und die Musik wurden nicht neu gestartet.
Der nächste echte Titelwechsel bleibt als Nutzer-Sichtprüfung offen.

Aktuelles Zip SHA-256:
`e0fe1ada1ea3e032826da3ca52e5c5fd4c2664153e25dc9b6982cc755cf3eb66`.

## Ein-Klick-Schalter

Nutzer bestätigt automatische Rückkehr und Titelwechsel als funktionierend.
Auf Wunsch ersetzt default.py nun das alte Stufe-0-Diagnoseprogramm:
Addon öffnen schaltet Party Video aus/an. Die zuvor gewählte Visualisierung wird
in prev_visualisation.json gesichert und beim Ausschalten wiederhergestellt.
Ohne gespeicherten Vorgänger (bestehende Testinstallation) wird keine Visualisierung
gewählt. Die Videoquelle bleibt gespeichert. Beim Einschalten ohne vorhandene
Videodatei öffnet sich der lokale Dateibrowser; Abbrechen verändert die Auswahl
nicht. Einstellungen werden auf erfolgreiche Kodi-Antwort geprüft; atomare
JSON-Schreibvorgänge und eine nichtblockierende Dateisperre schützen den Zustand.

16 Python-Tests, 59 C++-Tests, 5 ELF-/7 Zip-Fälle, ruff und Paketbuild erfolgreich.
Installation nur von default.py, kein Neustart. SHA-256 lokal/auf Pi identisch:
836b95d235b2f7fbb6e5455a03fb4aaf99ef22d7e2d6876c005efecc3df5be96.
Zweimal Addons.ExecuteAddon auf dem Pi geprüft:
- Klick 1: Visualisierung leer, Hauptmenü aktiv, Audio weiter aktiv.
- Klick 2: Party Video gewählt, Visualisierung aktiv, Titelinfo aus, Audio aktiv.
Endzustand ist eingeschaltet. Backup des Diagnoseprogramms:
/storage/.cache/partyvideo-backups/default-before-toggle.py.
Aktuelles Zip SHA-256:
c0a66828acfb64af97be03d7d9491e8e8f310a72e7f9054bc998a879eef86b35.
