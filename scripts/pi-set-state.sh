#!/usr/bin/env bash
# Schreibt state.json für visualization.partyvideo atomar auf den Pi.
# SCHREIBENDER ZUGRIFF: nur nach ausdrücklicher Freigabe des Maintainers benutzen.
# Aufruf: scripts/pi-set-state.sh <revision> <quelle|""> [titel]
set -euo pipefail

revision="${1:?Aufruf: pi-set-state.sh <revision> <quelle|\"\"> [titel]}"
source_path="${2?Aufruf: pi-set-state.sh <revision> <quelle|\"\"> [titel]}"
title="${3:-Stufe-1-Test}"
host="${PI_HOST:-root@192.168.178.10}"
dir=/storage/.kodi/userdata/addon_data/visualization.partyvideo

kind=file
[[ -z "$source_path" ]] && kind=""

json="$(python3 -c 'import json, sys; print(json.dumps({"revision": int(sys.argv[1]), "source": sys.argv[2], "kind": sys.argv[3], "title": sys.argv[4]}))' \
  "$revision" "$source_path" "$kind" "$title")"

printf '%s\n' "$json" | ssh -o BatchMode=yes "$host" \
  "mkdir -p '$dir' && cat > '$dir/state.json.tmp' && mv '$dir/state.json.tmp' '$dir/state.json' && cat '$dir/state.json'"
