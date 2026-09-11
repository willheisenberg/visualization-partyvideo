#!/usr/bin/env bash
# Prüft, ob eine gebaute Addon-Bibliothek auf LibreELEC 12 (RPi5, aarch64) laden kann.
# Grenzen per Umgebung überschreibbar: MAX_GLIBC (2.38), MAX_GLIBCXX (3.4.32).
set -euo pipefail

so="${1:?Aufruf: check_elf.sh <datei.so>}"
readelf="${READELF:-aarch64-linux-gnu-readelf}"
max_glibc="${MAX_GLIBC:-2.38}"
max_glibcxx="${MAX_GLIBCXX:-3.4.32}"
allowed=" libavformat.so.60 libavcodec.so.60 libavutil.so.58 libswscale.so.7 libGLESv2.so.2 libstdc++.so.6 libm.so.6 libgcc_s.so.1 libc.so.6 "

if [[ ! -f "$so" ]]; then
  echo "Datei nicht gefunden: $so"
  exit 1
fi

fail=0

machine="$("$readelf" -h "$so" | sed -n 's/^ *Machine: *//p')"
if [[ "$machine" != "AArch64" ]]; then
  echo "falsche Architektur: $machine"
  fail=1
fi

while read -r lib; do
  [[ -z "$lib" ]] && continue
  if [[ "$allowed" != *" $lib "* ]]; then
    echo "unerlaubte Abhängigkeit: $lib"
    fail=1
  fi
done < <("$readelf" -d "$so" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p')

version_le() { # version_le a b → wahr, wenn a <= b
  [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" == "$1" ]]
}

highest() { # highest PRÄFIX → höchste referenzierte Version oder leer
  "$readelf" -V "$so" | { grep -o "${1}_[0-9][0-9.]*" || true; } | sed "s/^${1}_//" | sort -V | tail -1
}

glibc="$(highest GLIBC)"
if [[ -n "$glibc" ]] && ! version_le "$glibc" "$max_glibc"; then
  echo "GLIBC_$glibc verlangt, erlaubt bis $max_glibc"
  fail=1
fi

glibcxx="$(highest GLIBCXX)"
if [[ -n "$glibcxx" ]] && ! version_le "$glibcxx" "$max_glibcxx"; then
  echo "GLIBCXX_$glibcxx verlangt, erlaubt bis $max_glibcxx"
  fail=1
fi

exit "$fail"
