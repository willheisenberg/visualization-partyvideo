# visualization.partyvideo – Design

Stand: 2026-09-11 · Status: Entwurf zur Durchsicht

## 1. Ziel

Ein Kodi-Addon, das während der Musikwiedergabe (z. B. ein SoundCloud-Track über
`plugin.audio.soundcloud`) ein **stummes Video in Endlosschleife** als
Musikvisualisierung zeigt. Die Musik läuft unverändert über Kodis normalen Player;
das Video wird vom Addon selbst dekodiert und gezeichnet und belegt deshalb keinen
Player.

Das Addon wird als **ein einziges Zip** installiert.

## 2. Anforderungen

### Funktional

| # | Anforderung |
|---|---|
| F1 | Video läuft stumm in Schleife als Kodi-Musikvisualisierung, solange das Visual aktiv ist. |
| F2 | Quelle YouTube: URL-Eingabe in Kodi. Download in einen Temp-Ordner. |
| F3 | Quelle Dateisystem: Auswahl einer lokalen Videodatei über Kodis Dateibrowser. |
| F4 | Heruntergeladene YouTube-Videos werden gelöscht, wenn das Visual ausgeschaltet oder durch ein anderes Video ersetzt wird. |
| F5 | Das aktive Video bleibt über Songwechsel und Musikpausen hinweg aktiv. |
| F6 | Bedienung mit der Fernbedienung in Kodi (Script-Menü). |
| F7 | API für den Telegram-Bot (KodiMediaBot) über Kodis JSON-RPC: Befehle, Status-Ereignisse, Statusabfrage. |
| F8 | Ist das Visual aus, wird die vorher eingestellte Musikvisualisierung wiederhergestellt. |

### Nicht-funktional

- Zielplattform: Raspberry Pi 5, LibreELEC 12.2.1, Kodi 21.3 Omega (siehe §3).
- Auf dem Pi sind außer dem Addon-Zip keine Installationen nötig (kein Docker, kein Compiler).
- Python-Code muss mit **Python 3.11** (Kodis Interpreter) laufen.
- Musikwiedergabe darf durch den Renderer nicht gestört werden (ein CPU-Kern bleibt frei).

## 3. Zielsystem (per ssh ermittelt, 2026-09-11)

| | |
|---|---|
| Hardware | Raspberry Pi 5 Model B, 8 GB RAM, aarch64 |
| System | LibreELEC 12.2.1 (`RPi5.aarch64`), Kernel 6.12 |
| Kodi | 21.3 Omega |
| GPU | Broadcom V3D 7.1, OpenGL ES 3.1 (Mesa 25.1), EGL 1.5 |
| glibc / libstdc++ | 2.38 / 6.0.32 (GCC 13) |
| FFmpeg (System) | 6.0 – `libavcodec.so.60`, `libavformat.so.60`, `libavutil.so.58`, `libswscale.so.7` |
| Hardware-Decoder | nur HEVC (`/dev/video19`); **kein H.264-Hardwaredecoder** |
| Python | 3.11 (`libpython3.11.so`) |
| Audio | HDMI (`vc4hdmi0`), Passthrough aktiv, `guisoundmode=1` |
| Visualisierungen | keine installiert, `musicplayer.visualisation` leer |
| Speicher `/storage` | 57,7 GB, 49 GB frei |

Folgerungen: Software-Dekodierung, bevorzugt H.264 ≤ 1080p; das Addon linkt gegen das
System-FFmpeg 6.0 und liefert keins mit.

## 4. Architektur

### 4.1 Ein Addon, drei Erweiterungspunkte

Kodi erlaubt mehrere Extension-Points pro Addon und lädt je Typ die zugehörige
Bibliothek (`CAddon::LibPath()` verwendet die Library des angefragten Typs;
`CAddonInfoBuilder` setzt den ersten Extension-Point als Haupttyp).

```xml
<addon id="visualization.partyvideo" name="Party Video" version="@VERSION@" provider-name="tesla">
  <requires>@ADDON_DEPENDS@
    <import addon="xbmc.python" version="3.0.1"/>
  </requires>
  <extension point="xbmc.player.musicviz" library_@PLATFORM@="@LIBRARY_FILENAME@"/>
  <extension point="xbmc.python.script" library="default.py">
    <provides>executable</provides>
  </extension>
  <extension point="xbmc.service" library="service.py"/>
  <extension point="xbmc.addon.metadata">
    <platform>@PLATFORM@</platform>
    <license>GPL-2.0-or-later</license>
    <summary lang="de_DE">Stummes Video in Endlosschleife als Musikvisualisierung</summary>
    <summary lang="en_GB">Muted looping video as music visualization</summary>
  </extension>
</addon>
```

Die Visualisierung muss der **erste** Extension-Point sein (Haupttyp, Library-Pflicht
für Binärtypen). Validierung in Rollout-Stufe 0 (§10).

### 4.2 Komponenten

| Teil | Datei | Aufgabe |
|---|---|---|
| Renderer | `visualization.partyvideo.so` | Liest `state.json`, dekodiert das Video, zeichnet es; schreibt `renderer.json`. |
| Service | `service.py` | Einziger Zustandsbesitzer: Befehle ausführen, Downloads, Temp-Verwaltung, Status publizieren. |
| Script | `default.py` | Menü für die Fernbedienung und Einstieg für die Bot-API; leitet Befehle an den Service weiter. |

### 4.3 Datenfluss

```
Bot ── Addons.ExecuteAddon ──► default.py ─┐
Fernbedienung ── Menü ───────► default.py ─┤ JSONRPC.NotifyAll(message="partyvideo_cmd")
                                           ▼
                           service.py (xbmc.Monitor.onNotification)
                             │  Zustandsautomat
                             ├──► state.json            (atomar) ──► Renderer (Polling 500 ms)
                             ├──◄ renderer.json         (atomar) ◄── Renderer
                             ├──► Window(Home).Property(partyvideo.*)
                             └──► JSONRPC.NotifyAll(message="partyvideo_status") ──► Bot (WebSocket)
```

### 4.4 Pfade

| Zweck | Pfad |
|---|---|
| Addon-Daten | `special://profile/addon_data/visualization.partyvideo/` (= `/storage/.kodi/userdata/addon_data/visualization.partyvideo/`) |
| `state.json`, `renderer.json`, `prev_visualisation.json` | im Addon-Datenordner |
| Werkzeuge | `<addon_data>/tools/yt-dlp`, `<addon_data>/tools/deno` |
| Temp-Downloads | `special://temp/partyvideo/` (= `/storage/.kodi/temp/partyvideo/`) |

Der Renderer ermittelt den Datenordner über `kodi::addon::GetUserPath()`.

## 5. Schnittstellen

### 5.1 `state.json` (Service → Renderer)

```json
{
  "revision": 7,
  "source": "/storage/.kodi/temp/partyvideo/dQw4w9WgXcQ.mp4",
  "kind": "youtube",
  "title": "Video-Titel"
}
```

- `revision`: monoton steigende Ganzzahl; der Renderer lädt die Quelle neu, sobald sie sich ändert.
- `source`: absoluter lokaler Pfad oder `""` (= Visual aus, Renderer zeigt Schwarz).
- `kind`: `"youtube"`, `"file"` oder `""`.
- Schreiben immer atomar: in `state.json.tmp` schreiben, dann `rename`.

### 5.2 `renderer.json` (Renderer → Service)

```json
{
  "revision": 7,
  "state": "playing",
  "error": "",
  "warning": "",
  "width": 1920,
  "height": 1080,
  "codec": "h264"
}
```

- `revision`: die `state.json`-Revision, auf die sich der Status bezieht.
- `state`: `idle` | `loading` | `playing` | `error`.
- `error`: `""` | `file_not_found` | `open_failed` | `no_video_stream` | `unsupported_codec` | `decode_failed`.
- `warning`: `""` | `too_large` (Auflösung > 1920×1080).
- Atomar geschrieben wie `state.json`. Der Service prüft die Datei jede Sekunde.

### 5.3 Bot-API

**Befehle** über `Addons.ExecuteAddon`. `params` **muss ein Array** sein: Kodi
maskiert nur Array-Elemente (`StringUtils::Paramify`); bei einem Objekt werden die
Werte ungeschützt mit Kommas verkettet (`AddonsOperations.cpp`).

```json
{"jsonrpc": "2.0", "id": 1, "method": "Addons.ExecuteAddon",
 "params": {"addonid": "visualization.partyvideo",
            "params": ["action=play", "url=https://youtu.be/dQw4w9WgXcQ"]}}
```

| Aktion | Parameter | Wirkung |
|---|---|---|
| `play` | `url=<YouTube-URL>` | Download, danach als Visual aktivieren |
| `play` | `path=<absoluter lokaler Pfad>` | Datei als Visual aktivieren |
| `stop` | – | Visual aus, Temp-Download löschen, vorherige Visualisierung wiederherstellen |
| `status` | – | Service sendet sofort ein `partyvideo_status`-Ereignis |
| `update_tools` | – | yt-dlp und Deno neu herunterladen |

`ExecuteAddon` liefert keine Ergebnisdaten; Erfolg und Fehler kommen über das Ereignis.

**Ereignis** (Service → alle JSON-RPC-Clients): `Other.partyvideo_status`, gesendet bei
jeder Zustandsänderung, Fortschritt höchstens alle 2 s.

```json
{
  "state": "downloading",
  "title": "Video-Titel",
  "kind": "youtube",
  "source": "",
  "progress": 42,
  "error": "",
  "warning": "",
  "revision": 7
}
```

- `state`: `idle` | `installing_tools` | `downloading` | `playing` | `error`.
- `progress`: 0–100 während `installing_tools`/`downloading`, sonst `null`.
- `playing` bedeutet: Video ist ausgewählt und aktiv; sichtbar ist es, sobald Kodis
  Visualisierungsfenster offen ist.
- Meldet der Renderer für die aktuelle Revision `error`, wechselt der Service auf
  `state=error` mit dem Renderer-Fehlercode.

**Statusabfrage** per `XBMC.GetInfoLabels` auf dieselben Felder:
`Window(Home).Property(partyvideo.state)`, `…(partyvideo.title)`, `…(partyvideo.kind)`,
`…(partyvideo.progress)`, `…(partyvideo.error)`, `…(partyvideo.warning)`,
`…(partyvideo.revision)`. Zusätzlich `partyvideo.service` = `ready`, solange der
Service läuft.

### 5.4 Interner Befehlskanal (Script → Service)

`JSONRPC.NotifyAll` mit `sender="visualization.partyvideo"`, `message="partyvideo_cmd"`,
`data={"action": …, "url": …, "path": …}`. Der Service empfängt es über
`xbmc.Monitor.onNotification` als `Other.partyvideo_cmd`. Das Ereignis erreicht auch
den Bot; der ignoriert es. Ist `partyvideo.service` nicht `ready`, zeigt das Script
eine Fehlermeldung statt den Befehl zu senden.

## 6. Renderer (C++)

### 6.1 Einheiten

| Einheit | Aufgabe | Testbar ohne GL |
|---|---|---|
| `StateFiles` | `state.json` lesen, `renderer.json` atomar schreiben (vendored `nlohmann/json`, MIT) | ja |
| `VideoSource` | libavformat/libavcodec kapseln: öffnen, Videostream wählen, nächstes Bild, Schleife | ja |
| `FramePacer` | Anzeigezeitpunkt aus PTS, Loop-Offset, Pause/Resume, Verspätung | ja |
| `FrameMailbox` | thread-sicheres Ein-Bild-Übergabefach | ja |
| `PlaybackEngine` | Worker-Thread: Polling, Quelle, Pacer, Mailbox, Pause, Statusdatei | ja (ohne Kodi) |
| `Letterbox` | Zielrechteck aus Viewport, Videogröße und Pixel-Seitenverhältnis | ja |
| `YuvRenderer` | drei `GL_R8`-Texturen, Shader, Zeichnen | nein |
| `CVisualizationPartyVideo` | Kodi-Instanz (`kodi::addon::CInstanceVisualization`) | nein |

### 6.2 Ablauf

- `PlaybackEngine` existiert **einmal pro Prozess**, unabhängig von Kodi-Instanzen.
- `Start()` meldet eine aktive Instanz an → Worker läuft; `Stop()` meldet ab → Worker
  pausiert (keine Dekodierung, Position bleibt). Beim Resume wird die Uhr neu
  ausgerichtet, nicht vorgespult.
- Worker prüft alle 500 ms `state.json` (mtime, dann `revision`). Bei neuer Revision:
  alte Quelle schließen, neue öffnen, `renderer.json` = `loading`, danach `playing` oder `error`.
- Dekodierung: libavcodec mit `thread_count=3`, `thread_type=FRAME|SLICE`.
- Taktung: Bild wird ins Übergabefach gelegt, wenn seine PTS fällig ist (`steady_clock`).
  Liegt der Decoder mehr als zwei Bilder zurück, `skip_frame=AVDISCARD_NONREF`, bis er
  aufgeholt hat; verspätete Bilder werden verworfen statt nachgeholt.
- Schleife: bei EOF `av_seek_frame(…, 0, AVSEEK_FLAG_BACKWARD)` + `avcodec_flush_buffers`;
  schlägt der Seek fehl, Quelle neu öffnen. Loop-Offset im `FramePacer` um die Dauer erhöhen.
- Audio-Streams der Quelle werden ignoriert. `AudioData()` bleibt leer.

### 6.3 Bildformate und Zeichnen

- `yuv420p`/`yuvj420p` direkt; alle anderen Formate per `swscale` nach `yuv420p`.
- Upload in `Render()`: nur wenn ein neues Bild im Übergabefach liegt; `GL_UNPACK_ALIGNMENT=1`;
  Texturbreite = `linesize`, Crop über Texturkoordinaten.
- Fragment-Shader (`#version 300 es`): YUV→RGB mit BT.709 oder BT.601 nach
  `frame->colorspace`; unbekannt → BT.709 ab 720 px Höhe, sonst BT.601. Range nach
  `color_range` (limited/full).
- Seitenverhältnis erhalten (inkl. SAR), Rest schwarz.
- `IsDirty()` liefert `true`, wenn ein neues Bild vorliegt oder der Viewport sich geändert hat.

### 6.4 Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| `source` leer | Schwarz, `renderer.json: idle` |
| Datei fehlt | Schwarz, `error=file_not_found` |
| Öffnen scheitert | Schwarz, `error=open_failed` |
| kein Videostream | Schwarz, `error=no_video_stream` |
| kein Decoder für Codec | Schwarz, `error=unsupported_codec` |
| einzelne defekte Pakete | überspringen |
| 50 Decodierfehler in Folge | Schwarz, `error=decode_failed` |
| Auflösung > 1920×1080 | abspielen, `warning=too_large` |

## 7. Python-Teil

### 7.1 Module

| Modul | Aufgabe |
|---|---|
| `default.py` | Einstieg: ohne Argumente Menü, sonst `sys.argv` parsen und Befehl weiterleiten |
| `service.py` | Einstieg: `Controller` + `Monitor`-Schleife |
| `resources/lib/partyvideo/commands.py` | `key=value`-Argumente → `Command`; Validierung |
| `resources/lib/partyvideo/controller.py` | Zustandsautomat; alle Abhängigkeiten injiziert |
| `resources/lib/partyvideo/kodi.py` | Adapter: Properties, NotifyAll, Settings, Fenster, Player, Log, Pfade |
| `resources/lib/partyvideo/statefile.py` | atomares Lesen/Schreiben der JSON-Dateien |
| `resources/lib/partyvideo/youtube.py` | URL-Prüfung, Video-ID, Formatkette, yt-dlp-Aufruf mit Abbruch |
| `resources/lib/partyvideo/tools.py` | yt-dlp/Deno herunterladen, prüfen, entpacken, Version |
| `resources/lib/partyvideo/ui.py` | Menü und Dialoge |

Nur `kodi.py`, `ui.py` und die beiden Einstiegsdateien importieren `xbmc*`.

### 7.2 Zustandsautomat (`controller.py`)

```
            play(url)                    Download ok
  idle ─────────────────► downloading ─────────────────► playing
   ▲  ▲  (Werkzeuge fehlen: installing_tools davor)        │  │
   │  │                         │ Fehler                   │  │ play(…): neues Video ersetzt altes
   │  │                         ▼                          │  │
   │  └──────── stop ──────── error ◄──── Renderer-Fehler ─┘  │
   └───────────────────────── stop ───────────────────────────┘
  play(path): aus jedem Zustand ──► playing (ohne Download; ein laufender Download wird abgebrochen)
```

- **`play(url)`**: URL prüfen (`youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`);
  laufenden Download abbrechen; fehlen Werkzeuge → `installing_tools`; dann `downloading`.
  Nach Erfolg:
  1. `state.json` mit neuer Revision, `source` = Download, `kind=youtube`.
  2. Vorherigen YouTube-Download löschen.
  3. Visualisierung aktivieren (§7.4).
  Das bisherige Video läuft während des Downloads weiter.
- **`play(path)`**: Pfad muss absolut und lokal sein (beginnt mit `/`), sonst
  `network_path_unsupported`; muss existieren, sonst `file_not_found`. Dann wie oben
  ohne Download.
- **`stop`**: laufenden Download abbrechen, `state.json` mit `source=""`, Temp-Download
  löschen, vorherige Visualisierung wiederherstellen, `idle`.
- **Service-Start**: Temp-Ordner leeren, `state.json` auf `source=""` setzen, `idle`,
  `partyvideo.service=ready`.
- Jede Zustandsänderung aktualisiert Properties und sendet `partyvideo_status`.

### 7.3 YouTube-Download (`youtube.py`)

- yt-dlp-Optionen: `format` (siehe unten), `outtmpl=<temp>/%(id)s.%(ext)s`,
  `noplaylist=True`, `fixup="never"`, `progress_hooks=[…]`, `js_runtimes={"deno": {"path": <tools>/deno}}`,
  Logger auf `xbmc.log` umgeleitet.
- Formatkette (nur Videospur bevorzugt, kein Zusammenführen, daher kein `ffmpeg`-Programm nötig):
  1. `bestvideo[vcodec^=avc1][height<=H][fps<=30]`
  2. `bestvideo[vcodec^=avc1][height<=H]`
  3. `best[vcodec^=avc1][height<=H]` (Tonspur wird vom Renderer ignoriert)
  `H` = Addon-Einstellung *Maximale YouTube-Auflösung* (720 oder 1080, Standard 1080).
  Ohne Treffer: `no_suitable_format`.
- Abbruch: Progress-Hook wirft eine eigene Exception, wenn das Abbruch-Flag gesetzt ist;
  `.part`-Dateien werden entfernt.
- Download läuft in einem eigenen Thread; es gibt höchstens einen gleichzeitig.

### 7.4 Visualisierung ein-/ausschalten

- Aktivieren: aktuellen Wert von `musicplayer.visualisation` per `Settings.GetSettingValue`
  lesen und in `prev_visualisation.json` sichern (nur wenn noch nicht gesichert und nicht
  bereits unser Addon), dann `Settings.SetSettingValue` auf `visualization.partyvideo`.
  Läuft Audio (`xbmc.Player().isPlayingAudio()`), `ActivateWindow(visualisation)`.
- Wiederherstellen: gesicherten Wert zurückschreiben, `prev_visualisation.json` löschen.

### 7.5 Werkzeuge (`tools.py`)

| Werkzeug | Quelle | Prüfung |
|---|---|---|
| yt-dlp | `https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp` (Zipimport) | SHA-256 aus `SHA2-256SUMS` desselben Releases |
| Deno | `https://github.com/denoland/deno/releases/latest/download/deno-aarch64-unknown-linux-gnu.zip` | SHA-256 aus der zugehörigen `.sha256sum`-Datei; nach dem Entpacken `deno --version` |

- yt-dlp wird per `sys.path.insert(0, <tools>/yt-dlp)` importiert (Zipimport).
- Download erst in `*.tmp`, Prüfung, dann `rename`; bei Fehler bleibt die alte Version.
- Menü: vor dem ersten Download Bestätigungsdialog (~100 MB). Bot-API: ohne Nachfrage,
  Status `installing_tools`.
- Offener Punkt: ob das Zipimport-Release die EJS-Skripte enthält; andernfalls
  `remote_components=["ejs:github"]` setzen (Klärung in Stufe 3).

### 7.6 Menü (`ui.py`)

1. **YouTube-URL eingeben** – `xbmcgui.Dialog().input`
2. **Videodatei wählen** – `xbmcgui.Dialog().browse(1, …, "video", ".mp4|.mkv|.webm|.mov")`
3. **Visual aus**
4. **Status** – Zustand, Titel, Fehler
5. **yt-dlp und Deno aktualisieren**

Fehler werden als Kodi-Benachrichtigung angezeigt. Texte in
`resources/language/resource.language.de_de/strings.po` und `…en_gb/strings.po`.

### 7.7 Addon-Einstellungen

| ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `max_height` | Auswahl 720/1080 | 1080 | Obergrenze für YouTube-Downloads |

## 8. Fehlercodes (gesamt)

| Code | Herkunft | Bedeutung |
|---|---|---|
| `invalid_url` | Service | keine gültige YouTube-URL |
| `network_path_unsupported` | Service | Pfad ist nicht lokal (z. B. `smb://`) |
| `file_not_found` | Service/Renderer | Datei existiert nicht |
| `tools_install_failed` | Service | yt-dlp/Deno-Download oder Prüfung gescheitert |
| `download_failed` | Service | yt-dlp-Fehler |
| `no_suitable_format` | Service | kein H.264-Format ≤ `max_height` |
| `open_failed` | Renderer | libavformat kann Datei nicht öffnen |
| `no_video_stream` | Renderer | Datei enthält keinen Videostream |
| `unsupported_codec` | Renderer | kein Decoder im System-FFmpeg |
| `decode_failed` | Renderer | dauerhafte Decodierfehler |

## 9. Build, Paketierung, Tests

### 9.1 Projektstruktur

```
visualization.partyvideo/
├─ CMakeLists.txt                 Kodi-Binäraddon-Build (build_addon)
├─ src/                           C++-Renderer
├─ third_party/nlohmann/json.hpp  vendored, MIT
├─ visualization.partyvideo/      Addon-Inhalt: addon.xml.in, default.py, service.py, resources/…
├─ docker/Dockerfile              Build-/Test-Image
├─ tests/python/                  pytest mit Stub-Modulen xbmc, xbmcgui, xbmcvfs, xbmcaddon
├─ tests/cpp/                     Unit- und Integrationstests
├─ build.sh                       → dist/visualization.partyvideo-<version>.zip
├─ test.sh                        ruff + pytest + C++-Tests
├─ pyproject.toml                 ruff: target-version = "py311"
└─ LICENSE                        GPL-2.0-or-later
```

### 9.2 Build (Docker auf dem Entwicklungsrechner)

- Basis `debian:bookworm` (glibc 2.36, GCC 12 – beide älter als auf dem Pi).
- `crossbuild-essential-arm64`, CMake, Ninja, `libgles-dev:arm64` (Multiarch).
- FFmpeg **n6.0** aus den Quellen: einmal aarch64-shared (nur zum Linken, Soname wie auf
  dem Pi), einmal amd64 für die Tests. `--disable-programs --disable-doc`.
- kodi-dev-kit und `cmake/addons` aus dem Kodi-Repo, Tag `21.3-Omega`;
  `APP_RENDER_SYSTEM=gles`, `CORE_SYSTEM_NAME=linux`. Dieser Mechanismus füllt
  `@ADDON_DEPENDS@` mit den API-Versionen.
- Prüfschritt nach dem Linken (Build schlägt sonst fehl):
  - höchste verlangte Symbolversionen `GLIBC_2.38`, `GLIBCXX_3.4.32`;
  - `NEEDED` nur aus: `libavformat.so.60`, `libavcodec.so.60`, `libavutil.so.58`,
    `libswscale.so.7`, `libGLESv2.so.2`, `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`.
- Zip enthält den Ordner `visualization.partyvideo/` mit `.so`, `addon.xml`, Python-Dateien und `resources/`.
- Einzige Versionsquelle ist das `version`-Attribut in `visualization.partyvideo/addon.xml.in`;
  Kodis `AddonHelpers.cmake` liest sie dort aus.
- `<platform>` wird zu `linux` (`PrepareEnv.cmake` hängt unter Linux keine Architektur an;
  Kodi 21 akzeptiert `linux` auf aarch64, `AddonInfoBuilder::PlatformSupportsAddon`).

### 9.3 Tests

| Bereich | Werkzeug | Inhalt |
|---|---|---|
| Python | pytest (lokal) | Zustandsautomat inkl. Abbruch/Ersetzen, Argument-Parsing, URL-Prüfung, Pfadprüfung, Temp-Aufräumen, Formatkette, Prüfsummen, atomares Schreiben, Wiederherstellen der Visualisierung – ohne Netzwerk |
| Python | ruff (`py311`) | Lint + Syntax-Kompatibilität |
| C++ Unit | im Docker-Image, amd64 | `FramePacer`, `FrameMailbox`, `Letterbox`, `StateFiles` |
| C++ Integration | im Docker-Image, amd64 | kurzes H.264-Testvideo (im Build erzeugt) dekodieren, Schleife und Seek, Fehlerfälle (fehlende Datei, Datei ohne Videostream) |
| GL-Ausgabe | manuell auf dem Pi | Stufen 0–1 |

„Fertig“ heißt: `./test.sh` grün und `./build.sh` erzeugt ein geprüftes Zip.

## 10. Rollout auf dem Pi

Installation erfolgt durch den Maintainer („Aus ZIP-Datei installieren“). Kein
automatisches Deployment.

| Stufe | Zip-Inhalt | Prüft |
|---|---|---|
| 0 | Visualisierung zeichnet Farbfläche; Script zeigt Benachrichtigung; `deno --version`-Probe aus `/storage` | gemischtes Addon (Binär + Python), Laden der `.so`, GL-Kontext, Ausführbarkeit von Binaries aus `addon_data` |
| 1 | Renderer mit festem lokalem Testvideo (1080p30 und 720p30 H.264) | Decode-Leistung, Farben, Letterbox, Schleife, Verhalten bei Songwechsel/Pause |
| 2 | + Service, Script, Dateibrowser, Bot-API | Menü, `state.json`/`renderer.json`, Ereignisse, `Settings.SetSettingValue` für `musicplayer.visualisation`, Wiederherstellen |
| 3 | + yt-dlp/Deno, YouTube | Werkzeug-Installation, EJS, Download nur Videospur, Löschen bei Stop/Ersetzen |

Lesender ssh-Zugriff auf den Pi (`root@192.168.178.10`, z. B. `kodi.log`, Addon-Datenordner)
ist freigegeben. Schreibende Zugriffe (Dateien kopieren/ändern/löschen, Dienste neu starten,
Addons installieren) sind ausgeschlossen und bleiben beim Maintainer.

## 11. Risiken und offene Punkte

| # | Risiko | Klärung | Ausweichweg |
|---|---|---|---|
| R1 | Kodi akzeptiert Binär- und Python-Extension nicht in einem Addon (gering: Team Kodis `visualization.shadertoy` kombiniert `xbmc.player.musicviz` und `xbmc.python.script` ebenfalls) | Stufe 0 | eigenes Repository-Addon, das zwei Addons als Abhängigkeit installiert |
| R2 | 1080p30-H.264 per Software ruckelt neben Kodi | Stufe 1 | `max_height=720` als Standard |
| R3 | `musicplayer.visualisation` per JSON-RPC nicht setzbar | Stufe 2 | Hinweisdialog mit Anleitung, einmalig manuell setzen |
| R4 | EJS nicht im yt-dlp-Zipimport enthalten | Stufe 3 | `remote_components=["ejs:github"]` |
| R5 | Deno läuft nicht aus `/storage` (Rechte, Bibliotheken) | Stufe 0 | Deno-Build gegen ältere glibc bzw. anderer Runtime-Pfad |
| R6 | Kodi entlädt die `.so` zwischen Songs | Stufe 1 | akzeptiert: Video beginnt dann von vorn |
| R7 | YouTube ändert Schnittstellen | laufend | Menüpunkt/Aktion `update_tools` |
| R8 | LibreELEC-Update ändert FFmpeg- oder Kodi-ABI | bei Updates | neu bauen gegen neue Versionen |

## 12. Nicht enthalten

- Hardware-Dekodierung (HEVC über `/dev/video19`)
- Netzwerkquellen (`smb://`, `nfs://`)
- Playlisten mehrerer Videos, Überblendungen, audioreaktive Effekte
- Andere Plattformen als RPi5/aarch64 mit LibreELEC 12
- Anbindung im KodiMediaBot (eigenes Folgeprojekt; nutzt die API aus §5.3)
