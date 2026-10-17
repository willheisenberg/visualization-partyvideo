# Party Video bedienen und per JSON-RPC steuern

## Fernbedienung

- Party Video öffnen: Quellenmenü. Der erste Punkt heißt je nach Zustand
  „Visual einschalten“ oder „Visual ausschalten“.
- Addon-Informationen → Konfigurieren → **Videoquelle wählen / Menü öffnen**:
  YouTube-URL, lokale Videodatei, Visual aus, Status und Werkzeug-Update.
- **Maximale YouTube-Auflösung**: 1080 (Standard) oder 720.
- Erster YouTube-Download aus dem Menü: Bestätigung für yt-dlp/Deno (ca. 100 MB).
  Downloadfortschritt erscheint als Hintergrunddialog; die Bedienung bleibt möglich.
- Ausschalten löscht heruntergeladene YouTube-Videos, merkt sich aber den Link.
  Beim Wiedereinschalten wird er erneut geladen. Lokale Dateien werden nie gelöscht.
- Neustart des Service/Kodi: temporäre Downloads entfernen, Visual aus. Der zuletzt
  gewählte Link/lokale Pfad bleibt für den nächsten Klick gespeichert.

## Befehle

Kodis vorhandener JSON-RPC-Zugang und dessen Zugangsdaten werden benutzt.
`params` ist stets ein Array von `key=value`-Strings.

```json
{"jsonrpc":"2.0","id":1,"method":"Addons.ExecuteAddon","params":{"addonid":"visualization.partyvideo","params":["action=play","url=https://youtu.be/zbo6jUGrwdk"]}}
```

Weitere Argumente für dasselbe `params`-Array:

| Aktion | Argumente |
|---|---|
| Datei spielen | `["action=play", "path=/storage/videos/visual.mp4"]` |
| Ausschalten/Download abbrechen | `["action=stop"]` |
| Status senden | `["action=status"]` |
| Werkzeuge aktualisieren | `["action=update_tools"]` |
| Quellenmenü öffnen | `["action=menu"]` (oder ohne Argumente) |
| An-/ausschalten | `["action=toggle"]` |

Bot-Befehle installieren fehlende Werkzeuge ohne Dialog. Erfolg/Fehler kommen
asynchron als `Other.partyvideo_status` über Kodis WebSocket. `ExecuteAddon` bestätigt
nur die Übergabe. Das interne `Other.partyvideo_cmd` kann der Bot ignorieren.

Statusfelder: `state`, `title`, `kind`, `source`, `progress`, `error`, `warning`,
`revision`. Zustände: `idle`, `installing_tools`, `downloading`, `playing`, `error`.
`progress` ist außerhalb Installation/Download `null`; Fortschritt höchstens alle
zwei Sekunden. Ein laufendes Video bleibt während eines neuen Downloads sichtbar.
`playing` bedeutet ausgewählt/aktiv; ohne Musik ist noch keine Videoanzeige möglich.
Renderer-Fehler werden nur bei zur aktuellen Quelle passender Revision übernommen.

```json
{"jsonrpc":"2.0","id":2,"method":"XBMC.GetInfoLabels","params":{"labels":["Window(Home).Property(partyvideo.service)","Window(Home).Property(partyvideo.state)","Window(Home).Property(partyvideo.progress)","Window(Home).Property(partyvideo.error)"]}}
```

`partyvideo.service=ready` bestätigt den laufenden Service. Die übrigen Statusfelder
sind analog als `Window(Home).Property(partyvideo.<feld>)` abfragbar.

## Automatisches Umschalten unterdrücken

Der Service schaltet bei jedem Wiedergabestart mit Ton auf die Visualisierung. Spielt
ein anderes Addon Ton ab, der keine Musik ist, setzt es solange die Eigenschaft
`partyvideo.suppress` am Home-Fenster (beliebiger nicht leerer Wert) und löscht sie
danach wieder:

```python
xbmcgui.Window(10000).setProperty("partyvideo.suppress", "script.telegram.calls")
xbmcgui.Window(10000).clearProperty("partyvideo.suppress")
```

Genutzt von `script.telegram.calls` während Klingeln und Gespräch.

## Downloadtechnik

H.264 bis 1080p/720p, bevorzugt höchstens 30 fps, danach die Format-Fallbacks aus
§7.3 der Design-Spezifikation. Nur eine Datei, kein Zusammenführen mit Audio und
kein zusätzliches ffmpeg-Programm. Eine eventuell enthaltene Tonspur ignoriert der
Renderer. Playlisten und Live-Streams werden nicht heruntergeladen.

yt-dlp läuft bei jedem Anlauf als eigener Prozess über das System-Python
(`python3 <tools>/yt-dlp`), nie in Kodis eingebettetem Python: `yt_dlp/YoutubeDL.py`
enthält ein `\N{…}`-Escape, für das Python 3.11 prozessweit einen Zeiger in das
`unicodedata`-Modul des ersten Interpreters behält. Nach einem Neustart dieses Service
war er ungültig, und der nächste Download brachte Kodi zum Absturz (SIGSEGV).

Das yt-dlp-Zip enthält EJS; Deno ist die JavaScript-Runtime. Beide kommen von den
offiziellen GitHub-Releases, mit SHA-256-Prüfung aus demselben fest aufgelösten
Release. Ein fehlgeschlagenes Update behält das vorherige Werkzeugpaar.

Schlägt der erste Anlauf fehl, holt der zweite einen PO-Token: Das Addon startet den
Container `partyvideo-pot` (bgutil-ytdlp-pot-provider, nur an `127.0.0.1:4416`), lädt
mit dem Client `mweb` und entfernt den Container wieder. Dieser Anlauf wird bei einem
Fehlschlag einmal wiederholt. Das zugehörige yt-dlp-Plugin liegt mit fester Version
und SHA-256 neben den Werkzeugen und wird nur diesem Prozess mitgegeben: In Kodis
eingebettetem Python hat es Kodi zum Absturz gebracht. Eine Installation ohne das
Plugin wird beim nächsten YouTube-Download einmal erneuert. Ohne das Docker-Addon
entfällt der Token, und der zweite Anlauf ist wie bisher eine frische Auflösung.
