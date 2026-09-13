#!/usr/bin/env bash
# Läuft im Build-Container. Prüft scripts/check_zip.sh mit kleinen Addon-Zips.
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$PWD"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

printf '#include <stdio.h>\nint f(void) { return puts("x"); }\n' > "$tmp/f.c"
aarch64-linux-gnu-gcc -shared -fPIC "$tmp/f.c" -o "$tmp/arm.so"
gcc -shared -fPIC "$tmp/f.c" -o "$tmp/x86.so"

make_zip() { # make_zip <name> <bibliothek|-> <library_linux-name> [extra: symlink|pycache|noxml]
  local name="$1" lib="$2" libname="$3" extra="${4:-}"
  local dir="$tmp/$name/visualization.partyvideo"
  mkdir -p "$dir"
  if [[ "$extra" != noxml ]]; then
    printf '<addon id="visualization.partyvideo"><extension point="xbmc.player.musicviz" library_linux="%s"/></addon>\n' \
      "$libname" > "$dir/addon.xml"
  fi
  if [[ "$lib" != - ]]; then
    if [[ "$extra" == symlink ]]; then
      cp "$lib" "$dir/real.so"
      ln -s real.so "$dir/$libname"
    else
      cp "$lib" "$dir/$libname"
    fi
  fi
  if [[ "$extra" == pycache ]]; then
    mkdir -p "$dir/__pycache__"
    echo x > "$dir/__pycache__/default.cpython-311.pyc"
  fi
  (cd "$tmp/$name" && zip -qry "$tmp/$name.zip" visualization.partyvideo)
  echo "$tmp/$name.zip"
}

passed=0
failed=0
expect() { # expect <ok|fail> <beschreibung> <befehl …>
  local want="$1" desc="$2" got
  shift 2
  if "$@" >/dev/null 2>&1; then got=ok; else got=fail; fi
  if [[ "$got" == "$want" ]]; then
    echo "PASS $desc"
    passed=$((passed + 1))
  else
    echo "FAIL $desc (erwartet $want, erhalten $got)"
    failed=$((failed + 1))
  fi
}

expect ok   "gültiges Zip"                "$root/scripts/check_zip.sh" "$(make_zip good "$tmp/arm.so" lib.so.0.2.0)"
expect fail "Bibliothek fehlt"            "$root/scripts/check_zip.sh" "$(make_zip missing - lib.so.0.2.0)"
expect fail "Bibliothek ist Symlink"      "$root/scripts/check_zip.sh" "$(make_zip link "$tmp/arm.so" lib.so.0.2.0 symlink)"
expect fail "falsche Architektur"         "$root/scripts/check_zip.sh" "$(make_zip x86 "$tmp/x86.so" lib.so.0.2.0)"
expect fail "Python-Cache im Zip"         "$root/scripts/check_zip.sh" "$(make_zip cache "$tmp/arm.so" lib.so.0.2.0 pycache)"
expect fail "addon.xml fehlt"             "$root/scripts/check_zip.sh" "$(make_zip noxml "$tmp/arm.so" lib.so.0.2.0 noxml)"
expect fail "Zip fehlt"                   "$root/scripts/check_zip.sh" "$tmp/gibt-es-nicht.zip"

echo "$passed bestanden, $failed fehlgeschlagen"
[[ "$failed" -eq 0 ]]
