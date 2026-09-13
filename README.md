# visualization.partyvideo

Kodi-Addon für LibreELEC 12 / Kodi 21 auf dem Raspberry Pi 5: zeigt lokale Videos
oder heruntergeladene YouTube-Videos stumm in Endlosschleife während der Musik.

## Bedienung

**Party Video öffnen** zeigt das Quellenmenü. Der erste Punkt schaltet das Visual
ein oder aus; darunter folgen YouTube-URL, Videodatei, Status und Werkzeug-Update.
Die Musikwiedergabe läuft unverändert weiter.

**Addon-Informationen → Konfigurieren → Videoquelle wählen / Menü öffnen** führt zu:
YouTube-URL eingeben, Videodatei wählen, Visual aus, Status und Werkzeug-Update.
In den Einstellungen lässt sich die maximale YouTube-Auflösung auf 720 oder 1080 setzen.

Der erste YouTube-Download installiert nach Bestätigung yt-dlp und Deno mit
Prüfsummenprüfung. Das Video wird vollständig geladen und dann angezeigt.
Während eines neuen Downloads läuft das bisherige Video weiter. Ausschalten oder
Ersetzen löscht den alten YouTube-Download; der Link bleibt für das nächste
Einschalten gespeichert. Lokale Videodateien werden nicht gelöscht.

Beim Titelwechsel öffnet sich die Visualisierung automatisch. Nach „Zurück“ kehrt
sie aus Hauptmenü/Musikansicht nach drei Sekunden Bedienpause zurück; Einstellungen
und fremde Dialoge bleiben bedienbar. Ausschalten beendet auch diese Rückkehr.
Nach einem Kodi-Neustart ist das Visual aus; die letzte Quelle bleibt auswählbar.

[Bedienung und Bot-API](docs/bot-api.md) ·
[Design](docs/superpowers/specs/2026-09-11-partyvideo-design.md) ·
[Implementierungsplan](docs/superpowers/plans/2026-09-12-plan-3-service-youtube.md)

## Entwicklung

```sh
./build.sh    # Addon-Zip im Docker-Container bauen → dist/
./test.sh     # Python-, Kern- und Pakettests plus vollständiger Addon-Build
```

Voraussetzungen: Docker, Python ≥ 3.11 und `.venv` mit ruff.
Zielgerät: RPi5/aarch64, LibreELEC 12.2.1, Kodi 21.3, System-FFmpeg 6.0.
Auf dem Pi werden keine Compiler, kein Docker und kein zusätzliches ffmpeg benötigt.
