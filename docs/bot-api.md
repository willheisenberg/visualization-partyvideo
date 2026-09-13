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

## Downloadtechnik

H.264 bis 1080p/720p, bevorzugt höchstens 30 fps, danach die Format-Fallbacks aus
§7.3 der Design-Spezifikation. Nur eine Datei, kein Zusammenführen mit Audio und
kein zusätzliches ffmpeg-Programm. Eine eventuell enthaltene Tonspur ignoriert der
Renderer. Playlisten und Live-Streams werden nicht heruntergeladen.

yt-dlp-Zipimport enthält EJS; Deno ist die JavaScript-Runtime. Beide kommen von den
offiziellen GitHub-Releases, mit SHA-256-Prüfung aus demselben fest aufgelösten
Release. Ein fehlgeschlagenes Update behält das vorherige Werkzeugpaar.
