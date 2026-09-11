# Plan 1: Fundament und Stufe 0 – Umsetzungsplan

> **Für ausführende Agenten:** ERFORDERLICHER SUB-SKILL: superpowers:subagent-driven-development (empfohlen) oder superpowers:executing-plans, um diesen Plan Task für Task umzusetzen. Schritte nutzen Checkboxen (`- [ ]`).

**Ziel:** Ein reproduzierbarer Docker-Build erzeugt ein installierbares Stufe-0-Zip von `visualization.partyvideo`, mit dem sich auf dem Pi die Grundannahmen der Spec prüfen lassen (gemischtes Addon, Laden der `.so` mit System-FFmpeg, GL-Kontext, Deno aus `addon_data`, Setzen der Visualisierung per JSON-RPC).

**Architektur:** Build über Kodis offiziellen `cmake/addons`-Mechanismus (Tag `21.3-Omega`) in einem Debian-Bookworm-Container mit aarch64-Cross-Compiler; FFmpeg n6.0 wird im Image nur zum Linken gebaut. Das Addon besteht in Stufe 0 aus einer Visualisierung, die eine Farbfläche zeichnet, einem Diagnose-Script und einem leeren Service.

**Tech-Stack:** Docker, CMake, aarch64-linux-gnu-GCC 12, kodi-dev-kit 21.3, FFmpeg n6.0, OpenGL ES 3, Python 3.11 (Kodi), ruff.

**Spec:** `docs/superpowers/specs/2026-09-11-partyvideo-design.md`

**Planfolge:** Dieser Plan deckt Spec §9 (Build/Tests, Grundgerüst) und §10 Stufe 0 ab. Die Folgepläne werden erst nach dem Stufe-0-Test auf dem Pi geschrieben, weil dessen Ergebnis (R1, R3, R5) sie beeinflusst:
- Plan 2: Renderer (Spec §6) + Stufe 1; ergänzt das Build-Image um FFmpeg n6.0 für amd64 (C++-Tests) und ein `ffmpeg`-Programm zum Erzeugen von Testvideos (Spec §9.2/§9.3)
- Plan 3: Service, Script, Bot-API (Spec §5, §7.1–7.4, §7.6–7.7) + Stufe 2
- Plan 4: Werkzeuge und YouTube (Spec §7.3, §7.5) + Stufe 3

## Globale Vorgaben

- Projektwurzel: `/home/tesla/githubprojects/visualization.partyvideo` (im Container: `/src/visualization.partyvideo`).
- Addon-ID: `visualization.partyvideo`; `provider-name="tesla"`; Lizenz `GPL-2.0-or-later`.
- **Kein `git commit`, kein `git push`** – nur auf ausdrückliche Anweisung des Maintainers. Wo der Skill einen Commit-Schritt vorsieht, steht hier „Stand prüfen, nicht committen“.
- **Kein schreibender Zugriff auf den Pi** (`root@192.168.178.10`): kein scp, keine Installation, kein Neustart. Lesender ssh-Zugriff (z. B. `kodi.log`) ist erlaubt.
- Zielsystem: LibreELEC 12.2.1, Kodi 21.3 Omega, aarch64, glibc 2.38, libstdc++ `GLIBCXX_3.4.32`, FFmpeg 6.0 (`libavcodec.so.60`, `libavformat.so.60`, `libavutil.so.58`, `libswscale.so.7`), OpenGL ES 3.1.
- Python-Code muss unter **Python 3.11** laufen (ruff `target-version = "py311"`); das lokale venv ist 3.14.
- `xbmc.python`-Import: `version="3.0.1"`.
- Einzige Versionsquelle: `version`-Attribut in `visualization.partyvideo/addon.xml.in`. Stufe 0 = `0.1.0`.
- Kommentare, Log-Texte für Menschen und Doku auf Deutsch; Bezeichner auf Englisch.

## Dateiübersicht

| Datei | Verantwortung |
|---|---|
| `.gitignore` | Build-Artefakte, venv, Caches ausschließen |
| `LICENSE` | GPL-2.0-Text |
| `README.md` | Kurzbeschreibung, Befehle |
| `CLAUDE.md` | Arbeitsregeln für Agenten in diesem Repo |
| `pyproject.toml` | ruff-Konfiguration |
| `docker/Dockerfile` | Build-Image: Cross-Toolchain, Kodi-Quellen, FFmpeg n6.0 aarch64 |
| `docker/aarch64-toolchain.cmake` | CMake-Toolchain für aarch64 |
| `scripts/in-container.sh` | Image bauen (gecacht) und Befehl im Container ausführen |
| `scripts/check_elf.sh` | Prüft `.so`: Architektur, `NEEDED`, glibc-/libstdc++-Symbolversionen |
| `scripts/build-in-container.sh` | Kodi-Addon-Build, ELF-Prüfung, Zip nach `dist/` |
| `build.sh` | Einstieg Build (Host) |
| `test.sh` | Einstieg Tests (Host) |
| `tests/build/test_check_elf.sh` | Tests für `check_elf.sh` mit Fixture-Bibliotheken |
| `CMakeLists.txt` | Addon-Build via `build_addon` |
| `src/addon.h`, `src/addon.cpp` | Stufe-0-Visualisierung |
| `visualization.partyvideo/addon.xml.in` | Addon-Manifest mit drei Erweiterungspunkten |
| `visualization.partyvideo/default.py` | Stufe-0-Diagnose-Script |
| `visualization.partyvideo/service.py` | Stufe-0-Service |
| `docs/stufe-0-test.md` | Checkliste für den Test auf dem Pi |

---

### Task 1: Projektgerüst und lokale Python-Werkzeuge

**Files:**
- Create: `.gitignore`, `LICENSE`, `README.md`, `CLAUDE.md`, `pyproject.toml`

**Interfaces:**
- Consumes: –
- Produces: `.venv/bin/ruff`, `.venv/bin/pytest` (von späteren Tasks und Plänen genutzt); ruff-Konfiguration mit `target-version = "py311"`.

- [ ] **Step 1: `.gitignore` anlegen**

```gitignore
/build/
/dist/
/.venv/
__pycache__/
.ruff_cache/
.pytest_cache/
```

- [ ] **Step 2: GPL-2.0-Lizenztext herunterladen**

Run: `curl -fsSL -o /home/tesla/githubprojects/visualization.partyvideo/LICENSE https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt && head -3 /home/tesla/githubprojects/visualization.partyvideo/LICENSE`
Expected: Ausgabe beginnt mit `GNU GENERAL PUBLIC LICENSE` / `Version 2, June 1991`.

- [ ] **Step 3: `pyproject.toml` anlegen**

```toml
[tool.ruff]
target-version = "py311"
line-length = 110

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B"]
```

- [ ] **Step 4: `README.md` anlegen**

````markdown
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
````

- [ ] **Step 5: `CLAUDE.md` anlegen**

```markdown
# CLAUDE.md

## Befehle

    ./build.sh    # Addon-Zip bauen (Docker) → dist/
    ./test.sh     # ruff + Tests

## Regeln

- Nie committen oder pushen ohne ausdrückliche Anweisung.
- Pi `root@192.168.178.10`: nur lesender Zugriff (Logs, addon_data). Kein scp, keine
  Installation, kein Neustart – das macht der Maintainer.
- Python-Code läuft in Kodis Python 3.11; ruff prüft mit `target-version = "py311"`.
- Die Addon-Version steht nur in `visualization.partyvideo/addon.xml.in`.
- Nur `kodi.py`, `ui.py`, `default.py` und `service.py` dürfen `xbmc*` importieren
  (ab Plan 3).
```

- [ ] **Step 6: venv mit ruff und pytest anlegen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && python3 -m venv .venv && .venv/bin/pip install -q ruff pytest && .venv/bin/ruff --version`
Expected: `ruff 0.x.y`

- [ ] **Step 7: ruff auf leerem Projekt laufen lassen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && .venv/bin/ruff check .`
Expected: `All checks passed!`

- [ ] **Step 8: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`
Expected: die neuen Dateien als untracked (`??`); `build/`, `dist/`, `.venv/` erscheinen nicht.

---

### Task 2: Docker-Build-Image mit aarch64-Toolchain und FFmpeg n6.0

**Files:**
- Create: `docker/Dockerfile`, `docker/aarch64-toolchain.cmake`, `scripts/in-container.sh`

**Interfaces:**
- Consumes: –
- Produces:
  - Image `partyvideo-build:21.3-omega`
  - im Image: `/opt/kodi` (Kodi-Quellen, Tag `21.3-Omega`), `/opt/ffmpeg-aarch64` (FFmpeg n6.0 shared, mit `lib/pkgconfig`), `/opt/toolchains/aarch64.cmake`
  - `scripts/in-container.sh <befehl> [argumente…]`: führt den Befehl im Container mit Projekt unter `/src/visualization.partyvideo` als Arbeitsverzeichnis und mit der UID/GID des Aufrufers aus.

- [ ] **Step 1: Toolchain-Datei anlegen – `docker/aarch64-toolchain.cmake`**

```cmake
# Cross-Build für Raspberry Pi 5 (LibreELEC 12, aarch64) auf Debian Bookworm.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

# Multiarch-Pakete (libgles-dev:arm64) liegen unter /usr/lib/aarch64-linux-gnu.
set(CMAKE_LIBRARY_ARCHITECTURE aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu /opt/ffmpeg-aarch64)

# Programme vom Host, Bibliotheken/Header/Pakete aus Root-Pfad und Host-Präfixen:
# Kodis cmake/addons legt KodiConfig.cmake in einem Host-Pfad des Build-Verzeichnisses ab.
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)

# pkg-config darf nur die aarch64-FFmpeg-Dateien sehen.
set(ENV{PKG_CONFIG_LIBDIR} /opt/ffmpeg-aarch64/lib/pkgconfig)
set(ENV{PKG_CONFIG_PATH} "")
```

- [ ] **Step 2: `docker/Dockerfile` anlegen**

```dockerfile
FROM debian:bookworm

ARG KODI_TAG=21.3-Omega
ARG FFMPEG_TAG=n6.0

RUN dpkg --add-architecture arm64 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential crossbuild-essential-arm64 cmake git ca-certificates \
      pkg-config nasm zip unzip file \
      libgles-dev:arm64 \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${KODI_TAG}" https://github.com/xbmc/xbmc.git /opt/kodi

# FFmpeg n6.0 nur zum Linken: gleiche Sonames wie LibreELEC 12 (libavcodec.so.60 …).
# --disable-autodetect verhindert, dass Host-Bibliotheken (x86) eingebunden werden.
RUN git clone --depth 1 --branch "${FFMPEG_TAG}" https://github.com/FFmpeg/FFmpeg.git /opt/src/ffmpeg \
 && mkdir -p /opt/src/ffmpeg-build-aarch64 \
 && cd /opt/src/ffmpeg-build-aarch64 \
 && /opt/src/ffmpeg/configure \
      --prefix=/opt/ffmpeg-aarch64 \
      --enable-cross-compile --cross-prefix=aarch64-linux-gnu- \
      --arch=aarch64 --target-os=linux \
      --enable-shared --disable-static \
      --disable-programs --disable-doc --disable-autodetect \
      --disable-avdevice --disable-avfilter --disable-postproc --disable-swresample \
 && make -j"$(nproc)" \
 && make install \
 && rm -rf /opt/src/ffmpeg-build-aarch64

COPY aarch64-toolchain.cmake /opt/toolchains/aarch64.cmake
```

- [ ] **Step 3: `scripts/in-container.sh` anlegen**

```bash
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
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/in-container.sh`

- [ ] **Step 4: Image bauen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && docker build -t partyvideo-build:21.3-omega docker`
Expected: Build endet mit `naming to docker.io/library/partyvideo-build:21.3-omega`. Dauer beim ersten Mal mehrere Minuten (Kodi-Klon, FFmpeg-Build).

- [ ] **Step 5: Toolchain und FFmpeg im Container prüfen**

Run:
```bash
cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh bash -c '
  PKG_CONFIG_LIBDIR=/opt/ffmpeg-aarch64/lib/pkgconfig pkg-config --modversion libavcodec libavformat libavutil libswscale
  file -L /opt/ffmpeg-aarch64/lib/libavcodec.so.60
  ls /usr/lib/aarch64-linux-gnu/libGLESv2.so /usr/include/GLES3/gl3.h
  cat /opt/kodi/version.txt | grep -E "^(VERSION_MAJOR|VERSION_TAG)"'
```
Expected:
- Versionen `60.3.100`, `60.3.100`, `58.2.100`, `7.1.100`
- `ELF 64-bit LSB shared object, ARM aarch64`
- beide GLES-Pfade vorhanden
- `VERSION_MAJOR 21`

- [ ] **Step 6: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`
Expected: `docker/` und `scripts/` untracked.

---

### Task 3: ELF-Prüfskript mit Tests

**Files:**
- Create: `scripts/check_elf.sh`, `tests/build/test_check_elf.sh`, `test.sh`

**Interfaces:**
- Consumes: `scripts/in-container.sh` (Task 2)
- Produces:
  - `scripts/check_elf.sh <datei.so>` → Exit 0, wenn die Datei aarch64 ist, nur erlaubte `NEEDED`-Einträge hat und keine Symbolversion über `MAX_GLIBC` (Standard `2.38`) bzw. `MAX_GLIBCXX` (Standard `3.4.32`) verlangt; sonst Exit 1 mit einer Meldung pro Verstoß auf stdout.
  - `./test.sh` (Host): ruff + alle Tests; spätere Tasks/Pläne hängen ihre Tests dort an.

- [ ] **Step 1: Failing Test schreiben – `tests/build/test_check_elf.sh`**

```bash
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
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/tests/build/test_check_elf.sh`

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh tests/build/test_check_elf.sh`
Expected: `FAIL saubere aarch64-Bibliothek (erwartet ok, erhalten fail)` (Skript existiert noch nicht), Exit-Code ≠ 0.

- [ ] **Step 3: `scripts/check_elf.sh` implementieren**

```bash
#!/usr/bin/env bash
# Prüft, ob eine gebaute Addon-Bibliothek auf LibreELEC 12 (RPi5, aarch64) laden kann.
# Grenzen per Umgebung überschreibbar: MAX_GLIBC (2.38), MAX_GLIBCXX (3.4.32).
set -euo pipefail

so="${1:?Aufruf: check_elf.sh <datei.so>}"
readelf="${READELF:-aarch64-linux-gnu-readelf}"
max_glibc="${MAX_GLIBC:-2.38}"
max_glibcxx="${MAX_GLIBCXX:-3.4.32}"
allowed=" libavformat.so.60 libavcodec.so.60 libavutil.so.58 libswscale.so.7 libGLESv2.so.2 libstdc++.so.6 libm.so.6 libgcc_s.so.1 libc.so.6 libdl.so.2 libpthread.so.0 ld-linux-aarch64.so.1 "

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
  "$readelf" -V "$so" | grep -o "${1}_[0-9][0-9.]*" | sed "s/^${1}_//" | sort -V | tail -1
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
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/check_elf.sh`

- [ ] **Step 4: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh tests/build/test_check_elf.sh`
Expected: fünf `PASS`-Zeilen, `5 bestanden, 0 fehlgeschlagen`, Exit 0.

- [ ] **Step 5: `test.sh` anlegen**

```bash
#!/usr/bin/env bash
# Alle Prüfungen: ruff (Python 3.11-Syntax) und Tests im Build-Container.
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/ruff check .
scripts/in-container.sh tests/build/test_check_elf.sh
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/test.sh && cd /home/tesla/githubprojects/visualization.partyvideo && ./test.sh`
Expected: `All checks passed!`, danach `5 bestanden, 0 fehlgeschlagen`, Exit 0.

- [ ] **Step 6: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 4: Stufe-0-Visualisierung und Build-Pipeline bis zum Zip

**Files:**
- Create: `CMakeLists.txt`, `src/addon.h`, `src/addon.cpp`, `visualization.partyvideo/addon.xml.in`, `visualization.partyvideo/service.py`, `visualization.partyvideo/default.py` (vorläufig, wird in Task 5 ersetzt), `scripts/build-in-container.sh`, `build.sh`

**Interfaces:**
- Consumes: Image und `scripts/in-container.sh` (Task 2), `scripts/check_elf.sh` (Task 3)
- Produces:
  - `./build.sh` → `dist/visualization.partyvideo-0.1.0.zip` mit Wurzelordner `visualization.partyvideo/`
  - Klasse `CPartyVideo` (Datei `src/addon.h`), Einstieg `ADDONCREATOR(CPartyVideo)` – Plan 2 ersetzt die Stufe-0-Methodenrümpfe
  - Log-Präfix `[visualization.partyvideo]` in allen Kodi-Logzeilen des Addons

- [ ] **Step 1: `visualization.partyvideo/addon.xml.in` anlegen**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<addon id="visualization.partyvideo" version="0.1.0" name="Party Video" provider-name="tesla">
  <requires>@ADDON_DEPENDS@
    <import addon="xbmc.python" version="3.0.1"/>
  </requires>
  <extension point="xbmc.player.musicviz" library_@PLATFORM@="@LIBRARY_FILENAME@"/>
  <extension point="xbmc.python.script" library="default.py">
    <provides>executable</provides>
  </extension>
  <extension point="xbmc.service" library="service.py"/>
  <extension point="xbmc.addon.metadata">
    <platform>@PLATFORM@</platform>
    <license>GPL-2.0-or-later</license>
    <summary lang="de_DE">Stummes Video in Endlosschleife als Musikvisualisierung</summary>
    <summary lang="en_GB">Muted looping video as music visualization</summary>
    <description lang="de_DE">Stufe 0: Diagnoseversion. Zeichnet eine Farbfläche und prüft die Umgebung.</description>
    <description lang="en_GB">Stage 0: diagnostic build. Draws a solid colour and probes the environment.</description>
  </extension>
</addon>
```

- [ ] **Step 2: `visualization.partyvideo/service.py` anlegen**

```python
"""Stufe 0: belegt nur, dass der Service-Erweiterungspunkt neben Visualisierung und Script startet."""

import xbmc

ADDON_ID = "visualization.partyvideo"


def main():
    xbmc.log(f"[{ADDON_ID}] service: gestartet", xbmc.LOGINFO)
    xbmc.Monitor().waitForAbort()
    xbmc.log(f"[{ADDON_ID}] service: beendet", xbmc.LOGINFO)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: vorläufiges `visualization.partyvideo/default.py` anlegen**

```python
"""Vorläufig: wird in Task 5 durch die Stufe-0-Diagnose ersetzt."""

import xbmcgui

xbmcgui.Dialog().notification("Party Video", "Script-Erweiterung geladen")
```

- [ ] **Step 4: `src/addon.h` anlegen**

```cpp
#pragma once

#include <kodi/addon-instance/Visualization.h>

#include <string>

// Stufe 0: zeichnet eine Farbfläche und protokolliert die geladenen FFmpeg-Versionen.
class ATTR_DLL_LOCAL CPartyVideo : public kodi::addon::CAddonBase,
                                   public kodi::addon::CInstanceVisualization
{
public:
  CPartyVideo() = default;

  bool Start(int channels, int samplesPerSec, int bitsPerSample, const std::string& songName) override;
  void Stop() override;
  void Render() override;

private:
  // GL-Infos erst im ersten Render() protokollieren: nur dort ist der GL-Kontext sicher aktiv.
  bool m_glInfoLogged = false;
};
```

- [ ] **Step 5: `src/addon.cpp` anlegen**

```cpp
#include "addon.h"

#include <GLES3/gl3.h>

extern "C"
{
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libswscale/swscale.h>
}

namespace
{

void LogLibVersion(const char* name, unsigned version)
{
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] %s %u.%u.%u", name, AV_VERSION_MAJOR(version),
            AV_VERSION_MINOR(version), AV_VERSION_MICRO(version));
}

} // namespace

bool CPartyVideo::Start(int channels, int samplesPerSec, int bitsPerSample, const std::string& songName)
{
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Start: '%s' (%d Kanäle, %d Hz, %d Bit)",
            songName.c_str(), channels, samplesPerSec, bitsPerSample);
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] FFmpeg %s", av_version_info());
  LogLibVersion("libavcodec", avcodec_version());
  LogLibVersion("libavformat", avformat_version());
  LogLibVersion("libavutil", avutil_version());
  LogLibVersion("libswscale", swscale_version());
  return true;
}

void CPartyVideo::Stop()
{
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Stop");
}

void CPartyVideo::Render()
{
  if (!m_glInfoLogged)
  {
    const GLubyte* glVersion = glGetString(GL_VERSION);
    kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] GL_VERSION %s",
              glVersion ? reinterpret_cast<const char*>(glVersion) : "(kein GL-Kontext)");
    kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Viewport x=%d y=%d w=%d h=%d", X(), Y(),
              Width(), Height());
    m_glInfoLogged = true;
  }

  glEnable(GL_SCISSOR_TEST);
  glScissor(X(), Y(), Width(), Height());
  glClearColor(0.85f, 0.10f, 0.55f, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT);
  glDisable(GL_SCISSOR_TEST);
}

ADDONCREATOR(CPartyVideo)
```

- [ ] **Step 6: `CMakeLists.txt` anlegen**

```cmake
cmake_minimum_required(VERSION 3.18)
project(visualization.partyvideo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Kodi REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(FFMPEG REQUIRED libavformat>=60 libavcodec>=60 libavutil>=58 libswscale>=7)

find_path(GLES3_INCLUDE_DIR GLES3/gl3.h REQUIRED)
find_library(GLESV2_LIBRARY GLESv2 REQUIRED)

include_directories(${KODI_INCLUDE_DIR}/..
                    ${FFMPEG_INCLUDE_DIRS}
                    ${GLES3_INCLUDE_DIR}
                    ${PROJECT_SOURCE_DIR}/src)

set(PARTYVIDEO_SOURCES src/addon.cpp)
set(PARTYVIDEO_HEADERS src/addon.h)

set(DEPLIBS ${FFMPEG_LINK_LIBRARIES} ${GLESV2_LIBRARY})

build_addon(visualization.partyvideo PARTYVIDEO DEPLIBS)

include(CPack)
```

- [ ] **Step 7: `scripts/build-in-container.sh` anlegen**

```bash
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

so="$(find "$out/install/$id" -maxdepth 1 -type f -name "$id.so*" | head -1)"
if [[ -z "$so" ]]; then
  echo "Keine Bibliothek unter $out/install/$id gefunden" >&2
  exit 1
fi
"$src/scripts/check_elf.sh" "$so"

zip="$(find "$out/zips" -type f -name "$id-*.zip" | head -1)"
if [[ -z "$zip" ]]; then
  echo "Kein Zip unter $out/zips gefunden" >&2
  exit 1
fi
rm -f "$src/dist/$id-"*.zip
cp "$zip" "$src/dist/"
unzip -l "$src/dist/$(basename "$zip")"
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/build-in-container.sh`

- [ ] **Step 8: `build.sh` anlegen**

```bash
#!/usr/bin/env bash
# Baut das Addon-Zip für Raspberry Pi 5 / LibreELEC 12 / Kodi 21 im Docker-Container.
set -euo pipefail
cd "$(dirname "$0")"

scripts/in-container.sh scripts/build-in-container.sh
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/build.sh`

- [ ] **Step 9: Build ausführen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./build.sh`
Expected:
- CMake-Ausgabe enthält `Exact match visualization.partyvideo, building addon`
- keine Ausgabe von `check_elf.sh` (keine Verstöße)
- `unzip -l` listet mindestens: `visualization.partyvideo/addon.xml`, `visualization.partyvideo/default.py`, `visualization.partyvideo/service.py`, `visualization.partyvideo/visualization.partyvideo.so.0.1.0`
- Exit 0, Datei `dist/visualization.partyvideo-0.1.0.zip` existiert

Falls der Build an einer anderen Stelle scheitert, als hier erwartet: Fehlermeldung vollständig lesen, Ursache beheben und die Abweichung vom Plan im Task-Bericht nennen (z. B. geänderter Pfad oder CMake-Variable).

- [ ] **Step 10: Generiertes Manifest prüfen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && unzip -p dist/visualization.partyvideo-0.1.0.zip visualization.partyvideo/addon.xml`
Expected:
- `<import addon="kodi.binary.global.main" …/>` und `<import addon="kodi.binary.instance.visualization" …/>` sind eingesetzt
- `<import addon="xbmc.python" version="3.0.1"/>` vorhanden
- `library_linux="visualization.partyvideo.so.0.1.0"`
- `<platform>linux</platform>`
- alle drei Erweiterungspunkte vorhanden, `xbmc.player.musicviz` als erster

- [ ] **Step 11: ELF-Details dokumentieren**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh bash -c 'so=$(find build/aarch64/install -name "visualization.partyvideo.so*" -type f | head -1); aarch64-linux-gnu-readelf -d "$so" | grep NEEDED; aarch64-linux-gnu-readelf -V "$so" | grep -oE "GLIBC(XX)?_[0-9.]+" | sort -Vu | tail -4'`
Expected: `NEEDED` enthält `libavformat.so.60`, `libavcodec.so.60`, `libavutil.so.58`, `libswscale.so.7`, `libGLESv2.so.2`; höchste Versionen ≤ `GLIBC_2.38` und ≤ `GLIBCXX_3.4.32`. Ausgabe in den Task-Bericht übernehmen.

- [ ] **Step 12: Tests laufen lassen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./test.sh`
Expected: `All checks passed!`, `5 bestanden, 0 fehlgeschlagen`.

- [ ] **Step 13: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 5: Stufe-0-Diagnose-Script

**Files:**
- Modify: `visualization.partyvideo/default.py` (vorläufige Fassung aus Task 4 vollständig ersetzen)

**Interfaces:**
- Consumes: Addon-Gerüst (Task 4)
- Produces: Diagnose-Dialog auf dem Pi und Logzeilen `[visualization.partyvideo] probe: …` in `kodi.log` für folgende Prüfpunkte:
  - Python-, OpenSSL- und Kodi-Version
  - `musicplayer.visualisation` lesen, auf `visualization.partyvideo` setzen, zurücklesen, wiederherstellen (Risiko R3)
  - Deno herunterladen, entpacken, ausführbar machen, `deno --version` (Risiko R5)

Dieser Code ist Diagnose-Code für einen einmaligen Test auf dem Gerät und wird in Plan 3 ersetzt. Er bekommt keine Unit-Tests; geprüft wird er durch ruff und den Stufe-0-Test auf dem Pi.

- [ ] **Step 1: `visualization.partyvideo/default.py` ersetzen**

```python
"""Stufe-0-Diagnose für visualization.partyvideo.

Prüft auf dem Zielgerät die Python-Umgebung, ob sich die Musikvisualisierung per
JSON-RPC setzen lässt und ob ein heruntergeladenes Deno aus dem Addon-Datenordner
startet. Wird in Plan 3 durch das echte Menü ersetzt.
"""

import json
import os
import platform
import ssl
import stat
import subprocess
import urllib.request
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "visualization.partyvideo"
VISUALISATION_SETTING = "musicplayer.visualisation"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-unknown-linux-gnu.zip"


def log(message):
    xbmc.log(f"[{ADDON_ID}] probe: {message}", xbmc.LOGINFO)


def jsonrpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return json.loads(xbmc.executeJSONRPC(json.dumps(request)))


def probe_environment():
    return [
        f"Python {platform.python_version()} ({platform.machine()})",
        ssl.OPENSSL_VERSION,
        f"Kodi {xbmc.getInfoLabel('System.BuildVersion')}",
    ]


def probe_visualisation_setting():
    before = jsonrpc("Settings.GetSettingValue", {"setting": VISUALISATION_SETTING})
    if "result" not in before:
        return [f"GetSettingValue fehlgeschlagen: {before}"]
    old_value = before["result"].get("value")
    changed = jsonrpc("Settings.SetSettingValue", {"setting": VISUALISATION_SETTING, "value": ADDON_ID})
    after = jsonrpc("Settings.GetSettingValue", {"setting": VISUALISATION_SETTING})
    restored = jsonrpc("Settings.SetSettingValue", {"setting": VISUALISATION_SETTING, "value": old_value})
    return [
        f"Wert vorher: {old_value!r}",
        f"SetSettingValue(Addon): {changed.get('result', changed.get('error'))}",
        f"Wert danach: {after.get('result', {}).get('value')!r}",
        f"SetSettingValue(vorher): {restored.get('result', restored.get('error'))}",
    ]


def probe_deno(tools_dir):
    os.makedirs(tools_dir, exist_ok=True)
    archive = os.path.join(tools_dir, "deno.zip")
    deno = os.path.join(tools_dir, "deno")
    try:
        urllib.request.urlretrieve(DENO_URL, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extract("deno", tools_dir)
    except Exception as exc:  # Diagnose: jeden Fehler anzeigen
        return [f"Download/Entpacken fehlgeschlagen: {exc!r}"]
    finally:
        if os.path.exists(archive):
            os.remove(archive)

    os.chmod(deno, os.stat(deno).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    try:
        result = subprocess.run([deno, "--version"], capture_output=True, text=True, timeout=120)
    except Exception as exc:  # Diagnose: jeden Fehler anzeigen
        return [f"Start fehlgeschlagen: {exc!r}"]
    output = (result.stdout or result.stderr).strip().splitlines()
    return [f"Exit-Code {result.returncode}", *output[:3]]


def main():
    addon = xbmcaddon.Addon()
    tools_dir = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo("profile")), "tools")
    dialog = xbmcgui.Dialog()

    lines = ["[B]Umgebung[/B]", *probe_environment()]
    lines += ["", "[B]Visualisierungs-Einstellung[/B]", *probe_visualisation_setting()]
    if dialog.yesno("Party Video", "Deno testweise herunterladen (rund 45 MB) und starten?"):
        dialog.notification("Party Video", "Deno wird geladen …", xbmcgui.NOTIFICATION_INFO, 5000)
        lines += ["", "[B]Deno[/B]", *probe_deno(tools_dir)]

    for line in lines:
        if line:
            log(line.replace("[B]", "").replace("[/B]", ""))
    dialog.textviewer("Party Video – Stufe 0", "\n".join(lines))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: ruff laufen lassen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && .venv/bin/ruff check .`
Expected: `All checks passed!` Meldet ruff Importsortierung (`I001`) oder Modernisierungen (`UP`), mit `.venv/bin/ruff check --fix .` beheben und erneut prüfen.

- [ ] **Step 3: Python-3.11-Syntax zusätzlich prüfen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && docker run --rm -v "$PWD":/w -w /w python:3.11-alpine python -m py_compile visualization.partyvideo/default.py visualization.partyvideo/service.py && echo OK`
Expected: `OK`

- [ ] **Step 4: Zip neu bauen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./build.sh && unzip -p dist/visualization.partyvideo-0.1.0.zip visualization.partyvideo/default.py | head -5`
Expected: Build Exit 0; die ersten Zeilen zeigen den Docstring `Stufe-0-Diagnose für visualization.partyvideo.`

- [ ] **Step 5: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 6: Checkliste für den Stufe-0-Test und Übergabe

**Files:**
- Create: `docs/stufe-0-test.md`

**Interfaces:**
- Consumes: `dist/visualization.partyvideo-0.1.0.zip` (Task 4/5)
- Produces: Checkliste für den Maintainer; nach dessen Test eine Ergebnisdatei `docs/superpowers/results/stufe-0.md` (Step 4), die Plan 2 als Grundlage nimmt.

- [ ] **Step 1: `docs/stufe-0-test.md` anlegen**

```markdown
# Stufe-0-Test auf dem Raspberry Pi

Zip: `dist/visualization.partyvideo-0.1.0.zip`. Installation und alle Eingriffe auf dem
Pi macht der Maintainer.

## Installation

1. Zip auf den Pi bringen (z. B. über die Samba-Freigabe nach `/storage/downloads`).
2. Kodi → Einstellungen → System → Addons → „Unbekannte Quellen“ erlauben (falls noch aus).
3. Kodi → Addons → Aus ZIP-Datei installieren → Zip wählen.
   - [ ] Installation ohne Fehlermeldung
   - [ ] Unter „Meine Addons → Musikvisualisierungen“ erscheint „Party Video“
   - [ ] Unter „Meine Addons → Programme“ erscheint „Party Video“

## Diagnose-Script

4. Programme → Party Video starten, Deno-Frage mit „Ja“ beantworten.
   - [ ] Umgebung zeigt Python 3.11 (aarch64)
   - [ ] Visualisierungs-Einstellung: „Wert danach“ ist `'visualization.partyvideo'`
   - [ ] „SetSettingValue(vorher)“ ist `True` (Einstellung wiederhergestellt)
   - [ ] Deno: `Exit-Code 0` und eine Zeile `deno 2.x.y`

## Visualisierung

5. Einstellungen → Player → Musik → Visualisierung → „Party Video“.
6. SoundCloud-Track starten, Vollbild-Wiedergabe öffnen.
   - [ ] Pinke Fläche im Vollbild, Musik läuft ohne Aussetzer
   - [ ] Nach Songwechsel weiterhin pinke Fläche
7. Visualisierung wieder auf den vorherigen Wert (z. B. „Keine“) stellen.

## Rückmeldung

8. Claude Bescheid geben; Claude liest `kodi.log` per ssh (nur lesend) aus.
```

- [ ] **Step 2: Abschlussprüfung**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./test.sh && ./build.sh && ls -l dist/`
Expected: beide Exit 0; `dist/visualization.partyvideo-0.1.0.zip` vorhanden.

- [ ] **Step 3: Übergabe an den Maintainer**

Dem Maintainer melden: Pfad des Zips, Verweis auf `docs/stufe-0-test.md`, ELF-Details aus Task 4 Step 11. Nicht committen. Auf die Rückmeldung zum Test warten.

- [ ] **Step 4: Nach der Rückmeldung `kodi.log` lesend auswerten und Ergebnis festhalten**

Run: `ssh -o BatchMode=yes root@192.168.178.10 'grep -E "visualization\.partyvideo|partyvideo" /storage/.kodi/temp/kodi.log | tail -80'`
Expected (bei Erfolg):
- `service: gestartet`
- `probe: Python 3.11…`, `probe: Wert danach: 'visualization.partyvideo'`, `probe: Exit-Code 0`
- `Start: '…'`, `FFmpeg 6.0…`, `libavcodec 60.3.100`, `GL_VERSION OpenGL ES 3.1 …`
- keine Zeilen mit `ERROR` zum Addon

`docs/superpowers/results/stufe-0.md` anlegen mit: Datum, Checklistenstand aus `docs/stufe-0-test.md`, relevanten Logzeilen, Bewertung von R1, R3 und R5 (bestätigt / widerlegt, mit Beleg) und daraus folgenden Änderungen für Plan 2–4. Nicht committen.
