# Stufe-0-Ergebnis

Datum: 2026-09-11 · Gerät: Raspberry Pi 5, LibreELEC 12.2.1, Kodi 21.3, Skin Arctic Zephyr Mod
Zip: `dist/visualization.partyvideo-0.1.0.zip`

## Ablauf

- Installation durch Claude auf Anweisung des Maintainers: Addon-Ordner nach
  `/storage/.kodi/addons/visualization.partyvideo/` kopiert (ohne die zwei Symlink-Einträge),
  `UpdateLocalAddons`, Aktivierung per `Addons.SetAddonEnabled` (Kodi hatte das Addon nach dem
  Kopieren deaktiviert gefunden).
- Diagnose-Script, Visualisierung und Songwechsel durch den Maintainer am Gerät.
- Skin-Einstellung `HideMusicScrollingText` auf Anweisung des Maintainers per `kodi-send` gesetzt.

## Checkliste

- [x] Installation ohne Fehler; Addon unter Musikvisualisierungen und Programm-Addons
- [x] Umgebung: Python 3.11.13 (aarch64), Userland 64 Bit, OpenSSL 3.5.4, CA-Datei `/etc/ssl/cert.pem`
- [x] „Wert vorher“: `''` (keine Visualisierung)
- [x] Visualisierungs-Einstellung: „Wert danach“ `'visualization.partyvideo'`, Wiederherstellen `True`
- [x] Deno: `Exit-Code 0`, `deno 2.9.6 (stable, release, aarch64-unknown-linux-gnu)`, 81,0 MB, danach gelöscht
- [x] Pinke Fläche im Vollbild, Musik läuft
- [x] Nach Songwechsel weiterhin pinke Fläche

## Relevante Logzeilen (`kodi.log`)

```
19:22:56 CAddonMgr::FindAddons: visualization.partyvideo v0.1.0 installed
19:23:50 [visualization.partyvideo] service: gestartet
19:34:50 probe: Wert danach: 'visualization.partyvideo'
19:35:22 probe: Exit-Code 0 / deno 2.9.6 (stable, release, aarch64-unknown-linux-gnu)
19:41:00 Instanz erzeugt (#1, aktiv 1)
19:41:00 Start: 'HEIMLICH KNÜLLER @ LOCO PARAÍSO / GARBICZ 2026' (2 Kanäle, 44100 Hz, 32 Bit)
19:41:00 FFmpeg 6.0.1 · libavcodec 60.3.100 · libavformat 60.3.100 · libavutil 58.2.100 · libswscale 7.1.100
19:41:00 GL_VERSION OpenGL ES 3.1 Mesa 25.1.9 · Viewport x=0 y=0 w=1920 h=1080
19:46:48 Stop · Instanz zerstört (aktiv 0)
19:46:49 VideoPlayer::OpenFile: plugin://plugin.video.youtube/play/?video_id=…
19:47:52 Instanz erzeugt (#2, aktiv 1) · Start: 'HEIMLICH KNÜLLER …'
19:47:54 Stop · Instanz zerstört (aktiv 0)
19:48:33 VideoPlayer::OpenFile: plugin://plugin.audio.soundcloud/play/?url=…amelie-lens-radio-show-024
19:48:39 Instanz erzeugt (#3, aktiv 1) · Start: 'Amelie Lens Radio Show 024'
19:48:42 Stop · Instanz zerstört (aktiv 0)
```

Keine Fehler zum Addon.

## Bewertung der Risiken

| Risiko | Ergebnis | Beleg |
|---|---|---|
| R1 – Binär- und Python-Extension in einem Addon | **widerlegt (funktioniert)** | `Addons.GetAddons` listet das Addon unter `xbmc.player.musicviz`, `xbmc.python.script` und `xbmc.service`; Service startet, Script läuft, Visualisierung rendert |
| R3 – `musicplayer.visualisation` per JSON-RPC nicht setzbar | **widerlegt (setzbar)** | `SetSettingValue` → `True`, Wert danach `'visualization.partyvideo'`, Wiederherstellen `True` |
| R5 – Deno läuft nicht aus `/storage` | **widerlegt (läuft)** | `deno --version` Exit-Code 0 aus `addon_data/…/tools-stage0/` |
| R6 – Kodi entlädt die `.so` zwischen Songs | **widerlegt; Instanz wird aber pro Song neu erzeugt** | Instanzzähler steigt über Songwechsel (#1 → #2 → #3): die `.so` bleibt geladen, prozessweiter Zustand überlebt. Kodi ruft bei jedem Wechsel `Stop` + Destruktor und erzeugt für den nächsten Titel eine neue Instanz |
| Stufe-0-Ziele `.so` + System-FFmpeg + GL | **bestätigt** | FFmpeg 6.0.1 / `libavcodec 60.3.100` geladen, OpenGL ES 3.1, Vollbild-Viewport 1920×1080 |

## Folgerungen für Plan 2–4

1. **Plan 2 (Renderer):** Spec §6.2 bestätigt: `PlaybackEngine` einmal pro Prozess, `Start()` meldet an, `Stop()`/Destruktor meldet ab und pausiert. Die Instanz kommt und geht pro Titel (Lücken von wenigen Sekunden beim Wechsel); das Video soll dabei pausieren und an derselben Stelle weiterlaufen, nicht neu starten. GL-Ressourcen (Texturen, Shader) gehören zur Instanz bzw. zum GL-Kontext und müssen pro Instanz neu angelegt werden, Decoder-Zustand nicht.
2. **Plan 2:** Kein `glScissor` setzen (Kodi setzt die Scissor-Box); eigenen GL-Zustand nach `Render()` wiederherstellen.
3. **Plan 3 (Script):** Skins legen eigene Ebenen über die Visualisierung (Arctic Zephyr Mod: Laufschrift `HideMusicScrollingText`, Fanart-Overlays abhängig von `musicvisualisation.hide.background`). Das Script sollte beim Einschalten des Visuals bekannte Skin-Overlays abschalten oder darauf hinweisen und beim Ausschalten den vorherigen Zustand wiederherstellen.
4. **Plan 3:** Nach dem Kopieren ins Addon-Verzeichnis ist ein Addon deaktiviert; Updates über Zip-Installation in Kodi oder per `Addons.SetAddonEnabled`.
5. **Plan 4:** Deno 2.9.6 läuft auf dem Gerät; der YouTube-Weg mit yt-dlp + Deno ist gangbar. Download (~45 MB) in wenigen Sekunden.
