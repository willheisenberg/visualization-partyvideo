# Stufen 2 und 3 – Service und YouTube, 2026-09-12

## Umsetzung

Design §§4–5, 7–10 umgesetzt: alleiniger Zustandsbesitzer Controller im Service,
Script → JSONRPC.NotifyAll → Service, Statusereignisse und Home-Properties,
atomares state.json, Wiederherstellung vorheriger Visualisierung, lokale Quellen,
YouTube-URL-Prüfung, H.264-Formatkette 720/1080, geprüfte yt-dlp-/Deno-Werkzeuge,
ein abbrechbarer Download-Worker, Quellenwechsel und Temp-Verwaltung.

Die nachträglich ausdrücklich gewünschte Ein-Klick-Bedienung bleibt erhalten.
Das geplante Quellenmenü ist über `action=menu` oder Addon-Konfigurieren erreichbar.
Ohne gespeicherte Auswahl öffnet der normale Klick ebenfalls das Menü. Aus merkt
sich eine YouTube-URL, löscht aber ihre Videodatei; erneutes An lädt sie neu.
Die automatische Rückkehr zur Videoansicht bleibt erhalten.

Werkzeuge liegen wie geplant unter addon_data/tools/{yt-dlp,deno}. Prüfsummen
stammen aus dem jeweils fest aufgelösten offiziellen Release; beide Werkzeuge
werden vor dem Austausch geprüft, Deno zusätzlich mit --version. Jeder Download
hat einen eigenen Temp-Unterordner, damit auch erneutes Laden derselben URL die
bisherige Quelle bis zur vollständigen Ablösung erhält.

Die EJS-Frage aus R4 ist geklärt: Das offizielle Zipimport-Paket enthält EJS.
Kein `remote_components`-Download erforderlich.
Quelle: https://github.com/yt-dlp/yt-dlp/wiki/EJS

## Tests

`./test.sh` grün: 37 Python-Tests, 59 C++-Tests, 5 ELF-/7 Zip-Prüffälle,
ruff und vollständiger aarch64-Build. Netzwerkfreie Python-Tests für URL-/Argumentvalidierung, Formatkette, Kodi-UI,
Werkzeug-Prüfsummen, fehlgeschlagene Updates, atomares Schreiben, Controller-
Abbruch und Ersetzen, parallele Befehle, lokale Dateien, Wiederherstellung,
veraltete Renderer-Zustände, Rückkehr und Toggle. Zielsyntax Python 3.11 geprüft.
Der Zusatzversuch im Build-Container fand kein python3; dort laufen ausschließlich
C++-Tests. Die tatsächliche Python-3.11-Laufzeit wurde auf LibreELEC geprüft.

## Live-Prüfung

- Addon 0.3.0 installiert, Kodi einmal neu gestartet. Vorheriger Stand gesichert
  unter /storage/.cache/partyvideo-backups/20260912-171257.
- Kodi erkennt v0.3.0, Service meldet ready und startet entsprechend dem Plan idle.
- Addons.ExecuteAddon mit Array-Parametern und Nutzerlink
  https://youtu.be/zbo6jUGrwdk funktioniert über den vorgesehenen Befehlskanal.
- Werkzeuge automatisch installiert: yt-dlp 2026.08.19, Deno v2.9.6.
- YouTube-Titel: „Lava Lamp 4k Yellow Orange Liquid 3 Hours of Relaxing Long Video“.
  Rund 1,8 GB, als MP4/H.264 in 1920×1080 geladen.
- renderer.json Revision 3: playing, h264, 1920×1080, error/warning leer.
- Maintainer bestätigt im Chat: „ja es funktioniert“.
- Quellenmenü live geprüft: Kodi meldet Auswahldialog „Party Video“, Eintrag
  „YouTube-URL eingeben“. Deutscher Text wird korrekt geladen.
- Ein zweiter Aufruf derselben URL lädt in einem eigenen Verzeichnis, während
  das erste Video weiterläuft. Abschluss: Revision 4, state=playing. Das erste
  Downloadverzeichnis download-g_9tqlrq wurde automatisch entfernt.
- Die vier Testvideos aus Stufe 1 wurden entsprechend der damaligen
  Aufräumbedingung entfernt, /storage/videos/partyvideo-test existiert nicht mehr.
  state.json und last_selection.json zeigen inzwischen auf YouTube.

## Grenzen

Der Bot wird hier nicht geändert; seine Anbindung erfolgt über die dokumentierte
API. Netzwerkpfade, Playlisten und Livestreams gehören nicht zum Umfang.
Heruntergeladen wird die vollständige Datei. Ohne Musik ist die Auswahl aktiv,
aber es gibt noch keine sichtbare Musikvisualisierung.

Aktuelles geprüftes Paket: `dist/visualization.partyvideo-0.3.0.zip`.
SHA-256: `6f7a5adba6490e9df82c7777562ed676cc09a8a5f6b1bb6217fdb72134d5dfef`.
