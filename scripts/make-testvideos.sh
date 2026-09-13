#!/usr/bin/env bash
# Läuft im Build-Container: erzeugt H.264-Testvideos für Stufe 1 in dist/testvideos/.
# Aufruf: scripts/in-container.sh scripts/make-testvideos.sh
set -euo pipefail

out=/src/visualization.partyvideo/dist/testvideos
mkdir -p "$out"

encode() { # encode <datei> <lavfi-quelle> <sekunden>
  ffmpeg -hide_banner -loglevel error -y \
    -f lavfi -i "$2" -t "$3" \
    -c:v libx264 -preset medium -profile:v high -pix_fmt yuv420p -g 60 \
    -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
    -movflags +faststart "$out/$1"
}

encode partyvideo-1080p30.mp4 "testsrc2=size=1920x1080:rate=30" 20
encode partyvideo-720p30.mp4 "testsrc2=size=1280x720:rate=30" 20
encode partyvideo-farbbalken-1080p.mp4 "smptehdbars=size=1920x1080:rate=30" 10

encode partyvideo-4x3.mp4 "testsrc2=size=960x720:rate=30" 10

ls -l "$out"
