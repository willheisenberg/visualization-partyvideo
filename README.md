# visualization.partyvideo

Kodi-Addon für LibreELEC 12 / Kodi 21 auf dem Raspberry Pi 5: spielt während der
Musikwiedergabe ein stummes Video in Endlosschleife als Musikvisualisierung.

Design: `docs/superpowers/specs/2026-09-11-partyvideo-design.md`

## Befehle

```
./build.sh    # Addon-Zip im Docker-Container bauen → dist/
./test.sh     # ruff + Tests
```

Voraussetzungen auf dem Entwicklungsrechner: Docker, Python ≥ 3.11 mit venv in `.venv`
(`python3 -m venv .venv && .venv/bin/pip install ruff pytest`).
Auf dem Pi wird nur das Zip installiert.
