#!/usr/bin/env bash
# Erzeugt kleine Testvideos für die C++-Tests (im Build-Container, Debian-ffmpeg mit libx264).
# Vorhandene Dateien bleiben stehen. Aufruf: tests/cpp/make_fixtures.sh <zielverzeichnis>
set -euo pipefail

dir="${1:?Aufruf: make_fixtures.sh <zielverzeichnis>}"
mkdir -p "$dir"

fixture() { # fixture <datei> <ffmpeg-argumente …>
  local file="$dir/$1"
  shift
  [[ -s "$file" ]] && return 0
  ffmpeg -hide_banner -loglevel error -y "$@" "$file"
}

fixture h264_320x240_25fps_2s.mp4 \
  -f lavfi -i testsrc2=size=320x240:rate=25 -t 2 -c:v libx264 -pix_fmt yuv420p -g 25 -bf 2
fixture h264_yuv422p_160x120_1s.mkv \
  -f lavfi -i testsrc2=size=160x120:rate=25 -t 1 -c:v libx264 -pix_fmt yuv422p
fixture h264_with_audio_320x240_1s.mp4 \
  -f lavfi -i testsrc2=size=320x240:rate=25 -f lavfi -i sine=frequency=440 -t 1 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac
fixture audio_only_1s.m4a \
  -f lavfi -i sine=frequency=440 -t 1 -c:a aac
fixture mpeg4_320x240_1s.avi \
  -f lavfi -i testsrc2=size=320x240:rate=25 -t 1 -c:v mpeg4
fixture h264_2048x1152_0p4s.mp4 \
  -f lavfi -i testsrc2=size=2048x1152:rate=25 -t 0.4 -c:v libx264 -pix_fmt yuv420p -preset ultrafast

if [[ ! -s "$dir/not_a_video.mp4" ]]; then
  for _ in $(seq 1 200); do echo "Das ist kein Video."; done > "$dir/not_a_video.mp4"
fi
