#!/usr/bin/env bash
# Läuft im Build-Container: Testvideos erzeugen, Kerneinheiten für amd64 bauen und testen.
set -euo pipefail

src=/src/visualization.partyvideo
out=$src/build/amd64-tests
fixtures=$src/build/fixtures

"$src/tests/cpp/make_fixtures.sh" "$fixtures"

PKG_CONFIG_LIBDIR=/opt/ffmpeg-amd64/lib/pkgconfig \
  cmake -S "$src/tests/cpp" -B "$out" -DCMAKE_BUILD_TYPE=Debug -DFIXTURE_DIR="$fixtures"
cmake --build "$out" -j"$(nproc)"
ctest --test-dir "$out" --output-on-failure -j"$(nproc)"
