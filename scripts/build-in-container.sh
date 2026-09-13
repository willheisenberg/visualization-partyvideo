#!/usr/bin/env bash
# Läuft im Build-Container (scripts/in-container.sh). Baut das Addon über Kodis
# cmake/addons, prüft die Bibliothek und legt das Zip in dist/ ab.
set -euo pipefail

id=visualization.partyvideo
src=/src/$id
out=$src/build/aarch64

rm -rf "$out"
mkdir -p "$out/defs/$id" "$src/dist"

# Addon-Definition für cmake/addons; die URL wird wegen ADDON_SRC_PREFIX nicht benutzt.
echo "$id file://$src main" > "$out/defs/$id/$id.txt"
echo "linux" > "$out/defs/$id/platforms.txt"

cmake -S /opt/kodi/cmake/addons -B "$out/cmake" \
  -DCORE_SOURCE_DIR=/opt/kodi \
  -DCORE_SYSTEM_NAME=linux \
  -DAPP_RENDER_SYSTEM=gles \
  -DADDONS_TO_BUILD="$id" \
  -DADDONS_DEFINITION_DIR="$out/defs" \
  -DADDON_SRC_PREFIX=/src \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$out/install" \
  -DPACKAGE_ZIP=ON \
  -DPACKAGE_DIR="$out/zips" \
  -DCMAKE_TOOLCHAIN_FILE=/opt/toolchains/aarch64.cmake

cmake --build "$out/cmake" -j"$(nproc)"
cmake --build "$out/cmake" --target package-addons

zip="$(find "$out/zips" -type f -name "$id-*.zip" -print -quit)"
if [[ -z "$zip" ]]; then
  echo "Kein Zip unter $out/zips gefunden" >&2
  exit 1
fi

# Geprüft wird die Bibliothek, die tatsächlich ausgeliefert wird (gestrippt, im Zip).
"$src/scripts/check_zip.sh" "$zip"

rm -f "$src/dist/$id-"*.zip
cp "$zip" "$src/dist/"
unzip -l "$src/dist/$(basename "$zip")"
