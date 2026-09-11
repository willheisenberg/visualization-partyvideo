#!/usr/bin/env bash
# Läuft im Build-Container. Prüft scripts/check_elf.sh mit kleinen Fixture-Bibliotheken.
set -euo pipefail
cd "$(dirname "$0")/../.."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

printf '#include <stdio.h>\nint f(void) { return puts("x"); }\n' > "$tmp/f.c"
aarch64-linux-gnu-gcc -shared -fPIC "$tmp/f.c" -o "$tmp/good.so"
aarch64-linux-gnu-gcc -shared -fPIC "$tmp/f.c" -Wl,--no-as-needed -lresolv -o "$tmp/badlib.so"
gcc -shared -fPIC "$tmp/f.c" -o "$tmp/x86.so"

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

expect ok   "saubere aarch64-Bibliothek"  scripts/check_elf.sh "$tmp/good.so"
expect fail "unerlaubte Abhängigkeit"      scripts/check_elf.sh "$tmp/badlib.so"
expect fail "falsche Architektur"          scripts/check_elf.sh "$tmp/x86.so"
expect fail "GLIBC-Version über Grenze"    env MAX_GLIBC=2.10 scripts/check_elf.sh "$tmp/good.so"
expect fail "Datei fehlt"                  scripts/check_elf.sh "$tmp/gibt-es-nicht.so"

echo "$passed bestanden, $failed fehlgeschlagen"
[[ "$failed" -eq 0 ]]
