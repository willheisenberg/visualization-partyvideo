# CLAUDE.md

## Befehle

    ./build.sh    # Addon-Zip bauen (Docker) → dist/
    ./test.sh     # ruff + Tests

## Regeln

- Nie committen oder pushen ohne ausdrückliche Anweisung.
- Pi `root@192.168.178.10`: nur lesender Zugriff (Logs, addon_data). Kein scp, keine
  Installation, kein Neustart – das macht der Maintainer.
- Python-Code läuft in Kodis Python 3.11; ruff prüft mit `target-version = "py311"`.
- Die Addon-Version steht nur in `visualization.partyvideo/addon.xml.in`.
- Nur `kodi.py`, `ui.py`, `default.py` und `service.py` dürfen `xbmc*` importieren
  (ab Plan 3).
