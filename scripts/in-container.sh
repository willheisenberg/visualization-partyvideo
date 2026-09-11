#!/usr/bin/env bash
# Führt einen Befehl im Build-Container aus.
# Das Projekt liegt dort unter /src/visualization.partyvideo (Arbeitsverzeichnis).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
image="partyvideo-build:21.3-omega"

docker build -q -t "$image" "$root/docker" >/dev/null
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$root":/src/visualization.partyvideo \
  -w /src/visualization.partyvideo \
  "$image" "$@"
