# Plan 3 – Service, Quellenmenü und YouTube

Grundlage: Design vom 2026-09-11, §§4–5 und 7–10. Fortsetzung nach Stufe 1.

1. Kodi-freie Module für Befehle, JSON-Dateien, URL-Prüfung, geprüfte Werkzeuge
   und abbrechbare yt-dlp-Downloads implementieren.
2. Controller als einzigen Schreiber des Zustands einführen: maximal ein Worker,
   alte Quelle während des Downloads weiterspielen, Abbruch/Ersetzen serialisieren,
   temporäre Dateien ausschließlich innerhalb des eigenen Temp-Ordners entfernen.
3. Kodi-Adapter, Service-Queue, Status-Properties/NotifyAll und Script-Menü anbinden.
4. Geprüften Ein-Klick-Schalter und automatische Rückkehr erhalten, als ausdrücklich
   nachträglich gewünschte Ergänzungen zum ursprünglichen Menü-Entwurf.
   Ohne Argumente toggle, action=menu öffnet das vollständige Quellenmenü;
   zusätzlich über eine Aktion in den Addon-Einstellungen erreichbar.
5. DE-/EN-Texte, Einstellung 720/1080, Update-Aktion und Bot-API dokumentieren.
6. Netzwerkfreie Tests, vollständiger Build, Installation und Live-Download auf Pi.

Präzisierungen gegenüber dem Entwurf:
- yt-dlp und Deno aus jeweils einem fest aufgelösten Release beziehen, Prüfsummen
  aus demselben Release; beide Werkzeuge erst nach vollständiger Prüfung ersetzen.
- EJS ist laut offizieller yt-dlp-Wiki im Zipimport-Paket enthalten; kein zusätzliches
  remote_components nötig.
- Eigener Unterordner je Download verhindert, dass erneutes Laden derselben URL
  das noch laufende Video überschreibt. Stop/Ersetzen löscht den gesamten Jobordner.
- Beim Service-Start Quelle leeren und Revision über alte state-/renderer-Revision
  hinaus erhöhen. Veraltete Renderer-Meldungen dadurch nicht übernehmen.
- Ausschalten merkt Auswahl als lokale Datei oder YouTube-URL, löscht aber das
  heruntergeladene Video. Wieder einschalten lädt YouTube erneut (F4).
- Bestehende Deployment-Freigaben gelten weiter; keine Commits/Pushes.
