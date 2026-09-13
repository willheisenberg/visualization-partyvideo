# Plan 2: Video-Renderer und Stufe 1 – Umsetzungsplan

> **Für ausführende Agenten:** ERFORDERLICHER SUB-SKILL: superpowers:subagent-driven-development (empfohlen) oder superpowers:executing-plans, um diesen Plan Task für Task umzusetzen. Schritte nutzen Checkboxen (`- [ ]`).

**Ziel:** Die Visualisierung spielt das in `state.json` eingetragene lokale Video stumm in Endlosschleife ab, pausiert bei Songwechseln und läuft an derselben Stelle weiter.

**Architektur:** Kodi-freie Kerneinheiten (`src/core/`) dekodieren mit dem System-FFmpeg 6.0 in einem prozessweiten Worker-Thread und legen Bilder in ein Übergabefach; eine GLES-3-Einheit (`src/gl/`) lädt sie pro Kodi-Instanz als drei Texturen hoch und zeichnet sie per YUV→RGB-Shader mit Letterbox. Die Kerneinheiten werden auf amd64 im Build-Container mit GoogleTest und echten Testvideos geprüft; GL und Kodi-Anbindung prüft Stufe 1 auf dem Pi.

**Tech-Stack:** C++17, FFmpeg 6.0 (libavformat/libavcodec/libavutil/libswscale), OpenGL ES 3.0, kodi-dev-kit 21.3, nlohmann/json 3.11.3 (vendored), GoogleTest 1.12 (Debian bookworm), Docker.

**Spec:** `docs/superpowers/specs/2026-09-11-partyvideo-design.md` (§5.1, §5.2, §6, §9, §10 Stufe 1)
**Grundlagen:** `docs/superpowers/plans/2026-09-11-plan-1-fundament-stufe-0.md`, `docs/superpowers/results/stufe-0.md`

## Globale Vorgaben

- Projektwurzel: `/home/tesla/githubprojects/visualization.partyvideo` (im Container: `/src/visualization.partyvideo`).
- Addon-ID `visualization.partyvideo`; Version nach diesem Plan `0.2.0` (einzige Quelle: `version`-Attribut in `visualization.partyvideo/addon.xml.in`).
- **Kein `git commit`/`git push`** ohne ausdrückliche Anweisung des Maintainers.
- **Pi `root@192.168.178.10`:** lesend frei; jeder schreibende Zugriff (Dateien kopieren, Addon aktivieren, Einstellungen) nur nach ausdrücklicher Freigabe des Maintainers im Chat.
- Zielsystem: aarch64, glibc ≤ 2.38, `GLIBCXX` ≤ 3.4.32, FFmpeg 6.0 (`libavformat.so.60`, `libavcodec.so.60`, `libavutil.so.58`, `libswscale.so.7`), OpenGL ES 3.1, Kodi 21.3.
- `NEEDED` der Addon-Bibliothek nur: `libavformat.so.60 libavcodec.so.60 libavutil.so.58 libswscale.so.7 libGLESv2.so.2 libstdc++.so.6 libm.so.6 libgcc_s.so.1 libc.so.6` (Spec §9.2).
- `state.json` / `renderer.json` liegen im Addon-Datenordner (`kodi::addon::GetUserPath()`, auf dem Pi `/storage/.kodi/userdata/addon_data/visualization.partyvideo/`). Formate exakt nach Spec §5.1/§5.2.
- Renderer-Fehlercodes: `file_not_found`, `open_failed`, `no_video_stream`, `unsupported_codec`, `decode_failed`; Warnung `too_large` bei mehr als 1920×1080 Pixeln. Zustände: `idle`, `loading`, `playing`, `error`.
- Worker prüft `state.json` alle 500 ms; `thread_count=3`; `skip_frame=AVDISCARD_NONREF`, solange mehr als zwei Bilder Verspätung; 50 Decodierfehler in Folge → `decode_failed`.
- GL: kein `glScissor` setzen (Kodi setzt die Scissor-Box); eigenen GL-Zustand nach dem Zeichnen wiederherstellen; Viewport-Größe per `glGetIntegerv(GL_VIEWPORT)`, nicht `X()/Y()/Width()/Height()`.
- Stufe-0-Befund: Kodi zerstört die Instanz bei jedem Songwechsel und erzeugt sie neu, die `.so` bleibt geladen. Decoder-Zustand ist prozessweit, GL-Objekte gehören zur Instanz.
- Kommentare, Log-Texte und Doku auf Deutsch; Bezeichner auf Englisch; Log-Präfix `[visualization.partyvideo]`.
- Kerneinheiten unter `src/core/` inkludieren weder Kodi- noch GL-Header.

## Dateiübersicht

| Datei | Verantwortung |
|---|---|
| `docker/Dockerfile` | + FFmpeg n6.0 amd64 (`/opt/ffmpeg-amd64`), `libgtest-dev`, `ffmpeg`-Programm (Testvideos) |
| `scripts/in-container.sh` | + `--init`, Usage-Prüfung |
| `tests/cpp/CMakeLists.txt` | eigenständiger amd64-Testbuild der Kerneinheiten |
| `tests/cpp/make_fixtures.sh` | erzeugt Testvideos in `build/fixtures/` |
| `scripts/test-cpp-in-container.sh` | Fixtures erzeugen, Tests bauen, `ctest` |
| `test.sh` | + C++-Tests |
| `src/core/Letterbox.{h,cpp}` | Zielrechteck in NDC |
| `src/core/ColorConversion.{h,cpp}` | YUV→RGB-Matrix und Offsets |
| `src/core/FramePacer.{h,cpp}` | Anzeigezeitpunkte, Pause/Resume |
| `src/core/VideoFrame.h`, `src/core/FrameMailbox.{h,cpp}` | Bilddaten, thread-sicheres Übergabefach |
| `third_party/nlohmann/json.hpp`, `src/core/StateFiles.{h,cpp}` | `state.json` lesen, `renderer.json` atomar schreiben |
| `src/core/VideoSource.{h,cpp}` | FFmpeg: öffnen, dekodieren, Endlosschleife |
| `src/core/PlaybackEngine.{h,cpp}` | Worker-Thread, Polling, Taktung, Status |
| `src/gl/YuvRenderer.{h,cpp}` | Texturen, Shader, Zeichnen, GL-Zustand |
| `src/addon.{h,cpp}` | Kodi-Instanz, prozessweite Engine |
| `CMakeLists.txt` | neue Quellen, `third_party` |
| `scripts/build-in-container.sh`, `scripts/check_zip.sh`, `tests/build/test_check_zip.sh` | Gate auf die `.so` im Zip + `library_linux` |
| `scripts/make-testvideos.sh` | 1080p30/720p30-Testvideos für Stufe 1 |
| `docs/stufe-1-test.md` | Checkliste Stufe 1 |

---

### Task 1: C++-Testumgebung und Letterbox

**Files:**
- Modify: `docker/Dockerfile` (neue Schichten vor `COPY aarch64-toolchain.cmake …`)
- Modify: `scripts/in-container.sh`
- Create: `tests/cpp/CMakeLists.txt`, `scripts/test-cpp-in-container.sh`, `src/core/Letterbox.h`, `src/core/Letterbox.cpp`, `tests/cpp/letterbox_test.cpp`
- Modify: `test.sh`

**Interfaces:**
- Consumes: Image `partyvideo-build:21.3-omega` (Plan 1), `/opt/src/ffmpeg` (FFmpeg-Quellen n6.0 im Image)
- Produces:
  - Image enthält `/opt/ffmpeg-amd64` (FFmpeg n6.0 shared, amd64, **ohne** `mpeg4`-Decoder), `libgtest-dev`, `/usr/bin/ffmpeg` (Debian, mit libx264)
  - `tests/cpp/CMakeLists.txt` mit Listen `CORE_SOURCES` und `TEST_SOURCES` (eine Datei pro Zeile), Bibliothek `partyvideo_core`, Testprogramm `core_tests`; Include-Wurzeln `src/` und `third_party/`
  - `scripts/test-cpp-in-container.sh` (im Container): baut nach `build/amd64-tests` und führt `ctest` aus
  - `namespace partyvideo { struct NdcRect { float left; float bottom; float right; float top; }; NdcRect FitVideo(int viewportWidth, int viewportHeight, int videoWidth, int videoHeight, int sarNum, int sarDen); }` in `src/core/Letterbox.h`

- [ ] **Step 1: Dockerfile erweitern**

In `docker/Dockerfile` direkt **vor** der Zeile `COPY aarch64-toolchain.cmake /opt/toolchains/aarch64.cmake` einfügen:

```dockerfile
# Tests der Kerneinheiten (amd64): GoogleTest und das Debian-ffmpeg-Programm (mit libx264) für Testvideos.
# Nur Laufzeitpakete, keine FFmpeg-Header: das Addon linkt weiter ausschließlich gegen /opt/ffmpeg-aarch64.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgtest-dev ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# FFmpeg n6.0 für amd64: gleiche API-Version wie auf dem Pi.
# Der mpeg4-Decoder fehlt absichtlich, damit sich „unsupported_codec“ mit einem echten Video testen lässt.
RUN mkdir -p /opt/src/ffmpeg-build-amd64 \
 && cd /opt/src/ffmpeg-build-amd64 \
 && /opt/src/ffmpeg/configure \
      --prefix=/opt/ffmpeg-amd64 \
      --enable-shared --disable-static \
      --disable-programs --disable-doc --disable-autodetect \
      --disable-avdevice --disable-avfilter --disable-postproc --disable-swresample \
      --disable-decoder=mpeg4 \
 && make -j"$(nproc)" \
 && make install \
 && rm -rf /opt/src/ffmpeg-build-amd64
```

- [ ] **Step 2: `scripts/in-container.sh` ersetzen**

```bash
#!/usr/bin/env bash
# Führt einen Befehl im Build-Container aus.
# Das Projekt liegt dort unter /src/visualization.partyvideo (Arbeitsverzeichnis).
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Aufruf: scripts/in-container.sh <befehl> [argumente…]" >&2
  exit 2
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
image="partyvideo-build:21.3-omega"

docker build -q -t "$image" "$root/docker" >/dev/null
# --init: Ctrl-C erreicht make/cmake/ctest, statt vom PID-1-Prozess ignoriert zu werden.
docker run --rm --init \
  -u "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$root":/src/visualization.partyvideo \
  -w /src/visualization.partyvideo \
  "$image" "$@"
```

- [ ] **Step 3: Image bauen und prüfen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && docker build -t partyvideo-build:21.3-omega docker && scripts/in-container.sh bash -c 'PKG_CONFIG_LIBDIR=/opt/ffmpeg-amd64/lib/pkgconfig pkg-config --modversion libavcodec; file -L /opt/ffmpeg-amd64/lib/libavcodec.so.60; ls /usr/lib/x86_64-linux-gnu/libgtest.a; ffmpeg -hide_banner -encoders | grep -c libx264'`
Expected: `60.3.100`, `ELF 64-bit LSB shared object, x86-64`, Pfad zu `libgtest.a`, `1`.

- [ ] **Step 4: `tests/cpp/CMakeLists.txt` anlegen**

```cmake
cmake_minimum_required(VERSION 3.18)
project(partyvideo_core_tests CXX)

# Eigenständiger amd64-Testbuild der Kodi- und GL-freien Kerneinheiten aus src/core.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../..)

find_package(PkgConfig REQUIRED)
pkg_check_modules(FFMPEG REQUIRED IMPORTED_TARGET libavformat>=60 libavcodec>=60 libavutil>=58 libswscale>=7)
find_package(GTest REQUIRED)
find_package(Threads REQUIRED)

add_compile_options(-Wall -Wextra -Werror)

set(CORE_SOURCES
  ${REPO_ROOT}/src/core/Letterbox.cpp
)

add_library(partyvideo_core STATIC ${CORE_SOURCES})
target_include_directories(partyvideo_core PUBLIC ${REPO_ROOT}/src)
target_include_directories(partyvideo_core SYSTEM PUBLIC ${REPO_ROOT}/third_party)
target_link_libraries(partyvideo_core PUBLIC PkgConfig::FFMPEG Threads::Threads)

set(TEST_SOURCES
  letterbox_test.cpp
)

add_executable(core_tests ${TEST_SOURCES})
target_link_libraries(core_tests PRIVATE partyvideo_core GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(core_tests DISCOVERY_TIMEOUT 30)
```

- [ ] **Step 5: `scripts/test-cpp-in-container.sh` anlegen**

```bash
#!/usr/bin/env bash
# Läuft im Build-Container: baut die Kerneinheiten für amd64 und führt die GoogleTest-Suite aus.
set -euo pipefail

src=/src/visualization.partyvideo
out=$src/build/amd64-tests

PKG_CONFIG_LIBDIR=/opt/ffmpeg-amd64/lib/pkgconfig \
  cmake -S "$src/tests/cpp" -B "$out" -DCMAKE_BUILD_TYPE=Debug
cmake --build "$out" -j"$(nproc)"
ctest --test-dir "$out" --output-on-failure -j"$(nproc)"
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/test-cpp-in-container.sh`

- [ ] **Step 6: Failing Test schreiben – `tests/cpp/letterbox_test.cpp`**

```cpp
#include "core/Letterbox.h"

#include <gtest/gtest.h>

namespace
{

constexpr float kTolerance = 1e-4f;

void ExpectRect(const partyvideo::NdcRect& rect, float left, float bottom, float right, float top)
{
  EXPECT_NEAR(rect.left, left, kTolerance);
  EXPECT_NEAR(rect.bottom, bottom, kTolerance);
  EXPECT_NEAR(rect.right, right, kTolerance);
  EXPECT_NEAR(rect.top, top, kTolerance);
}

} // namespace

TEST(Letterbox, SameAspectFillsViewport)
{
  ExpectRect(partyvideo::FitVideo(1920, 1080, 1280, 720, 1, 1), -1.0f, -1.0f, 1.0f, 1.0f);
}

TEST(Letterbox, NarrowVideoGetsPillarbox)
{
  // 4:3 in 16:9 → Breite 0.75 des Viewports
  ExpectRect(partyvideo::FitVideo(1920, 1080, 640, 480, 1, 1), -0.75f, -1.0f, 0.75f, 1.0f);
}

TEST(Letterbox, WideVideoGetsLetterbox)
{
  // 21:9 in 16:9 → Höhe 16/21 des Viewports
  const float h = 16.0f / 21.0f;
  ExpectRect(partyvideo::FitVideo(1920, 1080, 2520, 1080, 1, 1), -1.0f, -h, 1.0f, h);
}

TEST(Letterbox, SampleAspectRatioIsApplied)
{
  // 720x576 mit SAR 4:3 → Anzeige 960x576 (1.6667) in 16:9 → Breite 0.9375
  ExpectRect(partyvideo::FitVideo(1920, 1080, 720, 576, 4, 3), -0.9375f, -1.0f, 0.9375f, 1.0f);
}

TEST(Letterbox, InvalidSampleAspectRatioCountsAsSquare)
{
  ExpectRect(partyvideo::FitVideo(1920, 1080, 640, 480, 0, 0), -0.75f, -1.0f, 0.75f, 1.0f);
}

TEST(Letterbox, InvalidSizesGiveEmptyRect)
{
  ExpectRect(partyvideo::FitVideo(0, 1080, 640, 480, 1, 1), 0.0f, 0.0f, 0.0f, 0.0f);
  ExpectRect(partyvideo::FitVideo(1920, 1080, 640, 0, 1, 1), 0.0f, 0.0f, 0.0f, 0.0f);
}
```

- [ ] **Step 7: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Abbruch beim Konfigurieren oder Kompilieren, weil `src/core/Letterbox.cpp` bzw. `core/Letterbox.h` fehlt.

- [ ] **Step 8: `src/core/Letterbox.h` anlegen**

```cpp
#pragma once

namespace partyvideo
{

// Rechteck in normalisierten Gerätekoordinaten (-1 … 1) des aktuellen Viewports.
struct NdcRect
{
  float left;
  float bottom;
  float right;
  float top;
};

// Passt ein Video mit erhaltenem Seitenverhältnis (inklusive Pixel-Seitenverhältnis sarNum:sarDen)
// mittig in den Viewport ein. sarNum/sarDen <= 0 gilt als 1:1. Ungültige Größen (<= 0) ergeben
// ein leeres Rechteck (alle Werte 0).
NdcRect FitVideo(int viewportWidth, int viewportHeight, int videoWidth, int videoHeight, int sarNum, int sarDen);

} // namespace partyvideo
```

- [ ] **Step 9: `src/core/Letterbox.cpp` anlegen**

```cpp
#include "core/Letterbox.h"

namespace partyvideo
{

NdcRect FitVideo(int viewportWidth, int viewportHeight, int videoWidth, int videoHeight, int sarNum, int sarDen)
{
  if (viewportWidth <= 0 || viewportHeight <= 0 || videoWidth <= 0 || videoHeight <= 0)
    return {0.0f, 0.0f, 0.0f, 0.0f};

  const double sar = (sarNum > 0 && sarDen > 0) ? static_cast<double>(sarNum) / sarDen : 1.0;
  const double videoAspect = static_cast<double>(videoWidth) * sar / videoHeight;
  const double viewportAspect = static_cast<double>(viewportWidth) / viewportHeight;

  double scaleX = 1.0;
  double scaleY = 1.0;
  if (videoAspect > viewportAspect)
    scaleY = viewportAspect / videoAspect;
  else
    scaleX = videoAspect / viewportAspect;

  return {static_cast<float>(-scaleX), static_cast<float>(-scaleY), static_cast<float>(scaleX),
          static_cast<float>(scaleY)};
}

} // namespace partyvideo
```

- [ ] **Step 10: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 6`, keine Compiler-Warnungen.

- [ ] **Step 11: `test.sh` erweitern**

```bash
#!/usr/bin/env bash
# Alle Prüfungen: ruff (Python 3.11-Syntax), Build-Skript-Tests und C++-Tests im Build-Container.
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/ruff check .
scripts/in-container.sh tests/build/test_check_elf.sh
scripts/in-container.sh scripts/test-cpp-in-container.sh
```

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./test.sh`
Expected: `All checks passed!`, `5 bestanden, 0 fehlgeschlagen`, `100% tests passed … out of 6`.

- [ ] **Step 12: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 2: Farbumrechnung YUV→RGB

**Files:**
- Create: `src/core/ColorConversion.h`, `src/core/ColorConversion.cpp`, `tests/cpp/color_conversion_test.cpp`
- Modify: `tests/cpp/CMakeLists.txt` (Listen `CORE_SOURCES`, `TEST_SOURCES`)

**Interfaces:**
- Consumes: Testumgebung aus Task 1
- Produces (in `src/core/ColorConversion.h`, `namespace partyvideo`):
  - `enum class ColorSpaceHint { Unknown, Bt601, Bt709 };`
  - `enum class ColorMatrix { Bt601, Bt709 };`
  - `struct YuvToRgb { std::array<float, 9> matrix; std::array<float, 3> offset; };` – `matrix` spaltenweise wie GLSL `mat3`: `rgb = matrix * (yuv - offset)`, Spalten Y, U, V; Werte Y/U/V normiert 0 … 1
  - `YuvToRgb MakeYuvToRgb(ColorMatrix matrix, bool fullRange);`
  - `ColorMatrix ChooseMatrix(ColorSpaceHint hint, int height);` – Hinweis gewinnt; `Unknown` → `Bt709` ab 720 Pixel Höhe, sonst `Bt601`

- [ ] **Step 1: Failing Test schreiben – `tests/cpp/color_conversion_test.cpp`**

```cpp
#include "core/ColorConversion.h"

#include <array>

#include <gtest/gtest.h>

using partyvideo::ChooseMatrix;
using partyvideo::ColorMatrix;
using partyvideo::ColorSpaceHint;
using partyvideo::MakeYuvToRgb;

namespace
{

constexpr float kTolerance = 1e-3f;

std::array<float, 3> Apply(const partyvideo::YuvToRgb& conv, float y, float u, float v)
{
  const float yy = y - conv.offset[0];
  const float uu = u - conv.offset[1];
  const float vv = v - conv.offset[2];
  const auto& m = conv.matrix;
  return {m[0] * yy + m[3] * uu + m[6] * vv, m[1] * yy + m[4] * uu + m[7] * vv,
          m[2] * yy + m[5] * uu + m[8] * vv};
}

void ExpectRgb(const std::array<float, 3>& rgb, float r, float g, float b)
{
  EXPECT_NEAR(rgb[0], r, kTolerance);
  EXPECT_NEAR(rgb[1], g, kTolerance);
  EXPECT_NEAR(rgb[2], b, kTolerance);
}

} // namespace

TEST(ColorConversion, LimitedRangeBlackAndWhite)
{
  for (const auto matrix : {ColorMatrix::Bt601, ColorMatrix::Bt709})
  {
    const auto conv = MakeYuvToRgb(matrix, false);
    ExpectRgb(Apply(conv, 16.0f / 255, 128.0f / 255, 128.0f / 255), 0.0f, 0.0f, 0.0f);
    ExpectRgb(Apply(conv, 235.0f / 255, 128.0f / 255, 128.0f / 255), 1.0f, 1.0f, 1.0f);
  }
}

TEST(ColorConversion, FullRangeBlackAndWhite)
{
  for (const auto matrix : {ColorMatrix::Bt601, ColorMatrix::Bt709})
  {
    const auto conv = MakeYuvToRgb(matrix, true);
    ExpectRgb(Apply(conv, 0.0f, 128.0f / 255, 128.0f / 255), 0.0f, 0.0f, 0.0f);
    ExpectRgb(Apply(conv, 1.0f, 128.0f / 255, 128.0f / 255), 1.0f, 1.0f, 1.0f);
  }
}

TEST(ColorConversion, Bt709FullRangeCoefficients)
{
  const auto conv = MakeYuvToRgb(ColorMatrix::Bt709, true);
  EXPECT_NEAR(conv.matrix[6], 1.5748f, kTolerance);  // R aus V
  EXPECT_NEAR(conv.matrix[4], -0.1873f, kTolerance); // G aus U
  EXPECT_NEAR(conv.matrix[7], -0.4681f, kTolerance); // G aus V
  EXPECT_NEAR(conv.matrix[5], 1.8556f, kTolerance);  // B aus U
}

TEST(ColorConversion, Bt601LimitedRangeCoefficients)
{
  const auto conv = MakeYuvToRgb(ColorMatrix::Bt601, false);
  EXPECT_NEAR(conv.matrix[0], 1.1644f, kTolerance); // Y-Skalierung
  EXPECT_NEAR(conv.matrix[6], 1.5960f, kTolerance); // R aus V
  EXPECT_NEAR(conv.matrix[4], -0.3918f, kTolerance); // G aus U
  EXPECT_NEAR(conv.matrix[7], -0.8130f, kTolerance); // G aus V
  EXPECT_NEAR(conv.matrix[5], 2.0172f, kTolerance); // B aus U
}

TEST(ColorConversion, ChooseMatrixPrefersHint)
{
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Bt709, 480), ColorMatrix::Bt709);
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Bt601, 1080), ColorMatrix::Bt601);
}

TEST(ColorConversion, ChooseMatrixFallsBackToHeight)
{
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Unknown, 720), ColorMatrix::Bt709);
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Unknown, 719), ColorMatrix::Bt601);
}
```

- [ ] **Step 2: Test in `tests/cpp/CMakeLists.txt` eintragen**

In der Liste `TEST_SOURCES` nach `letterbox_test.cpp` die Zeile `color_conversion_test.cpp` ergänzen; in der Liste `CORE_SOURCES` nach `${REPO_ROOT}/src/core/Letterbox.cpp` die Zeile `${REPO_ROOT}/src/core/ColorConversion.cpp` ergänzen.

- [ ] **Step 3: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Abbruch, weil `src/core/ColorConversion.cpp` / `core/ColorConversion.h` fehlt.

- [ ] **Step 4: `src/core/ColorConversion.h` anlegen**

```cpp
#pragma once

#include <array>

namespace partyvideo
{

// Farbraum-Hinweis aus den Metadaten des Videos.
enum class ColorSpaceHint
{
  Unknown,
  Bt601,
  Bt709
};

enum class ColorMatrix
{
  Bt601,
  Bt709
};

// Umrechnung für den Shader: rgb = matrix * (yuv - offset).
// matrix ist spaltenweise wie GLSL mat3 (Spalten Y, U, V); Y/U/V sind auf 0 … 1 normiert.
struct YuvToRgb
{
  std::array<float, 9> matrix;
  std::array<float, 3> offset;
};

YuvToRgb MakeYuvToRgb(ColorMatrix matrix, bool fullRange);

// Der Hinweis gewinnt; ohne Hinweis BT.709 ab 720 Pixel Höhe, sonst BT.601.
ColorMatrix ChooseMatrix(ColorSpaceHint hint, int height);

} // namespace partyvideo
```

- [ ] **Step 5: `src/core/ColorConversion.cpp` anlegen**

```cpp
#include "core/ColorConversion.h"

namespace partyvideo
{

YuvToRgb MakeYuvToRgb(ColorMatrix matrix, bool fullRange)
{
  const double kr = matrix == ColorMatrix::Bt709 ? 0.2126 : 0.299;
  const double kb = matrix == ColorMatrix::Bt709 ? 0.0722 : 0.114;
  const double kg = 1.0 - kr - kb;

  // Limited Range: Luma 16 … 235, Chroma 16 … 240 (8 Bit) auf volle Aussteuerung strecken.
  const double lumaScale = fullRange ? 1.0 : 255.0 / 219.0;
  const double chromaScale = fullRange ? 1.0 : 255.0 / 224.0;

  const double rFromV = 2.0 * (1.0 - kr) * chromaScale;
  const double gFromU = -2.0 * kb * (1.0 - kb) / kg * chromaScale;
  const double gFromV = -2.0 * kr * (1.0 - kr) / kg * chromaScale;
  const double bFromU = 2.0 * (1.0 - kb) * chromaScale;

  YuvToRgb result{};
  // Spalte Y
  result.matrix[0] = static_cast<float>(lumaScale);
  result.matrix[1] = static_cast<float>(lumaScale);
  result.matrix[2] = static_cast<float>(lumaScale);
  // Spalte U
  result.matrix[3] = 0.0f;
  result.matrix[4] = static_cast<float>(gFromU);
  result.matrix[5] = static_cast<float>(bFromU);
  // Spalte V
  result.matrix[6] = static_cast<float>(rFromV);
  result.matrix[7] = static_cast<float>(gFromV);
  result.matrix[8] = 0.0f;

  result.offset = {fullRange ? 0.0f : 16.0f / 255.0f, 128.0f / 255.0f, 128.0f / 255.0f};
  return result;
}

ColorMatrix ChooseMatrix(ColorSpaceHint hint, int height)
{
  switch (hint)
  {
    case ColorSpaceHint::Bt601:
      return ColorMatrix::Bt601;
    case ColorSpaceHint::Bt709:
      return ColorMatrix::Bt709;
    case ColorSpaceHint::Unknown:
      break;
  }
  return height >= 720 ? ColorMatrix::Bt709 : ColorMatrix::Bt601;
}

} // namespace partyvideo
```

- [ ] **Step 6: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 12`, keine Warnungen.

- [ ] **Step 7: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 3: Taktung (FramePacer)

**Files:**
- Create: `src/core/FramePacer.h`, `src/core/FramePacer.cpp`, `tests/cpp/frame_pacer_test.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: Testumgebung aus Task 1
- Produces (in `src/core/FramePacer.h`, `namespace partyvideo`):
  ```cpp
  class FramePacer
  {
  public:
    using Clock = std::chrono::steady_clock;
    void Reset(double mediaSeconds, Clock::time_point now);
    void Invalidate();
    bool IsAnchored() const;
    Clock::time_point DueTime(double mediaSeconds) const;
    double Lateness(double mediaSeconds, Clock::time_point now) const;
    void Pause(Clock::time_point now);
    void Resume(Clock::time_point now);
    bool IsPaused() const;
  };
  ```
  Medienzeit in Sekunden, über Schleifen hinweg fortlaufend (liefert `VideoSource`, Task 6). Nicht thread-sicher; nur der Worker-Thread benutzt ihn.

- [ ] **Step 1: Failing Test schreiben – `tests/cpp/frame_pacer_test.cpp`**

```cpp
#include "core/FramePacer.h"

#include <chrono>

#include <gtest/gtest.h>

using partyvideo::FramePacer;
using namespace std::chrono_literals;

namespace
{

const FramePacer::Clock::time_point kT0 = FramePacer::Clock::time_point{} + 100s;

void ExpectTime(FramePacer::Clock::time_point actual, FramePacer::Clock::time_point expected)
{
  const auto diff = std::chrono::duration_cast<std::chrono::microseconds>(actual - expected).count();
  EXPECT_LE(diff < 0 ? -diff : diff, 10) << "Abweichung in Mikrosekunden: " << diff;
}

} // namespace

TEST(FramePacer, NotAnchoredInitially)
{
  FramePacer pacer;
  EXPECT_FALSE(pacer.IsAnchored());
  EXPECT_FALSE(pacer.IsPaused());
}

TEST(FramePacer, DueTimeFollowsMediaTime)
{
  FramePacer pacer;
  pacer.Reset(10.0, kT0);
  EXPECT_TRUE(pacer.IsAnchored());
  ExpectTime(pacer.DueTime(10.0), kT0);
  ExpectTime(pacer.DueTime(10.5), kT0 + 500ms);
}

TEST(FramePacer, LatenessIsPositiveWhenLate)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  EXPECT_NEAR(pacer.Lateness(0.04, kT0 + 100ms), 0.06, 1e-6);
  EXPECT_NEAR(pacer.Lateness(0.2, kT0 + 100ms), -0.1, 1e-6);
}

TEST(FramePacer, PauseShiftsScheduleByPauseDuration)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0 + 1s);
  EXPECT_TRUE(pacer.IsPaused());
  pacer.Resume(kT0 + 3s);
  EXPECT_FALSE(pacer.IsPaused());
  ExpectTime(pacer.DueTime(1.5), kT0 + 3500ms);
}

TEST(FramePacer, RepeatedPauseKeepsFirstPauseStart)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0 + 1s);
  pacer.Pause(kT0 + 2s);
  pacer.Resume(kT0 + 3s);
  ExpectTime(pacer.DueTime(1.0), kT0 + 3s);
}

TEST(FramePacer, LatenessIsZeroWhilePaused)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0);
  EXPECT_DOUBLE_EQ(pacer.Lateness(0.0, kT0 + 10s), 0.0);
}

TEST(FramePacer, ResetClearsPauseAndInvalidateDropsAnchor)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0 + 1s);
  pacer.Reset(5.0, kT0 + 2s);
  EXPECT_FALSE(pacer.IsPaused());
  ExpectTime(pacer.DueTime(5.0), kT0 + 2s);
  pacer.Invalidate();
  EXPECT_FALSE(pacer.IsAnchored());
}
```

- [ ] **Step 2: In `tests/cpp/CMakeLists.txt` eintragen**

`TEST_SOURCES`: Zeile `frame_pacer_test.cpp` ergänzen. `CORE_SOURCES`: Zeile `${REPO_ROOT}/src/core/FramePacer.cpp` ergänzen.

- [ ] **Step 3: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Abbruch, weil `src/core/FramePacer.cpp` / `core/FramePacer.h` fehlt.

- [ ] **Step 4: `src/core/FramePacer.h` anlegen**

```cpp
#pragma once

#include <chrono>

namespace partyvideo
{

// Ordnet Medienzeiten (Sekunden, über Schleifen hinweg fortlaufend) Anzeigezeitpunkten zu.
// Nicht thread-sicher: nur der Worker-Thread der PlaybackEngine benutzt ihn.
class FramePacer
{
public:
  using Clock = std::chrono::steady_clock;

  // mediaSeconds wird zum Zeitpunkt now angezeigt; hebt eine Pause auf.
  void Reset(double mediaSeconds, Clock::time_point now);
  // Anker verwerfen, z. B. beim Quellenwechsel.
  void Invalidate();
  bool IsAnchored() const { return m_anchored; }

  // Anzeigezeitpunkt eines Bildes. Nur sinnvoll, wenn IsAnchored() und nicht pausiert.
  Clock::time_point DueTime(double mediaSeconds) const;
  // Verspätung in Sekunden (> 0: zu spät). Während einer Pause 0.
  double Lateness(double mediaSeconds, Clock::time_point now) const;

  // Mehrfaches Pause() behält den ersten Pausenbeginn.
  void Pause(Clock::time_point now);
  // Verschiebt den Anker um die Pausendauer, damit das Video an derselben Stelle weiterläuft.
  void Resume(Clock::time_point now);
  bool IsPaused() const { return m_paused; }

private:
  bool m_anchored = false;
  bool m_paused = false;
  double m_anchorMedia = 0.0;
  Clock::time_point m_anchorTime{};
  Clock::time_point m_pausedAt{};
};

} // namespace partyvideo
```

- [ ] **Step 5: `src/core/FramePacer.cpp` anlegen**

```cpp
#include "core/FramePacer.h"

namespace partyvideo
{

void FramePacer::Reset(double mediaSeconds, Clock::time_point now)
{
  m_anchored = true;
  m_paused = false;
  m_anchorMedia = mediaSeconds;
  m_anchorTime = now;
}

void FramePacer::Invalidate()
{
  m_anchored = false;
  m_paused = false;
}

FramePacer::Clock::time_point FramePacer::DueTime(double mediaSeconds) const
{
  const std::chrono::duration<double> offset(mediaSeconds - m_anchorMedia);
  return m_anchorTime + std::chrono::duration_cast<Clock::duration>(offset);
}

double FramePacer::Lateness(double mediaSeconds, Clock::time_point now) const
{
  if (m_paused)
    return 0.0;
  return std::chrono::duration<double>(now - DueTime(mediaSeconds)).count();
}

void FramePacer::Pause(Clock::time_point now)
{
  if (m_paused)
    return;
  m_paused = true;
  m_pausedAt = now;
}

void FramePacer::Resume(Clock::time_point now)
{
  if (!m_paused)
    return;
  m_anchorTime += now - m_pausedAt;
  m_paused = false;
}

} // namespace partyvideo
```

- [ ] **Step 6: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 19`, keine Warnungen.

- [ ] **Step 7: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 4: Bilddaten und Übergabefach (VideoFrame, FrameMailbox)

**Files:**
- Create: `src/core/VideoFrame.h`, `src/core/FrameMailbox.h`, `src/core/FrameMailbox.cpp`, `tests/cpp/frame_mailbox_test.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: `ColorMatrix` aus `src/core/ColorConversion.h` (Task 2)
- Produces (`namespace partyvideo`):
  - `src/core/VideoFrame.h`:
    ```cpp
    struct VideoFrame
    {
      int width = 0;
      int height = 0;
      std::array<std::vector<uint8_t>, 3> planes; // 0 = Y, 1 = U, 2 = V, YUV 4:2:0, 8 Bit
      std::array<int, 3> strides{0, 0, 0};        // Bytes pro Zeile je Ebene
      double mediaSeconds = 0.0;
      ColorMatrix matrix = ColorMatrix::Bt709;
      bool fullRange = false;
      int sarNum = 1;
      int sarDen = 1;
    };
    inline int ChromaWidth(int width);   // (width + 1) / 2
    inline int ChromaHeight(int height); // (height + 1) / 2
    ```
  - `src/core/FrameMailbox.h`:
    ```cpp
    struct MailboxRead { bool changed = false; std::shared_ptr<const VideoFrame> frame; };
    class FrameMailbox
    {
    public:
      void Put(std::shared_ptr<const VideoFrame> frame);
      void Clear();
      MailboxRead ReadIfChanged(uint64_t& lastSequence) const;
      uint64_t Sequence() const;
    };
    ```
    Das Fach behält das letzte Bild; jeder Leser führt seine eigene `lastSequence` (Start `0`), so bekommt eine neu erzeugte Kodi-Instanz sofort das aktuelle Bild.

- [ ] **Step 1: Failing Test schreiben – `tests/cpp/frame_mailbox_test.cpp`**

```cpp
#include "core/FrameMailbox.h"

#include <atomic>
#include <memory>
#include <thread>

#include <gtest/gtest.h>

using partyvideo::FrameMailbox;
using partyvideo::VideoFrame;

namespace
{

std::shared_ptr<const VideoFrame> MakeFrame(double mediaSeconds)
{
  auto frame = std::make_shared<VideoFrame>();
  frame->mediaSeconds = mediaSeconds;
  return frame;
}

} // namespace

TEST(FrameMailbox, EmptyMailboxReportsNoChange)
{
  FrameMailbox mailbox;
  uint64_t seen = 0;
  const auto read = mailbox.ReadIfChanged(seen);
  EXPECT_FALSE(read.changed);
  EXPECT_EQ(read.frame, nullptr);
  EXPECT_EQ(mailbox.Sequence(), 0u);
}

TEST(FrameMailbox, PutIsReportedOncePerReader)
{
  FrameMailbox mailbox;
  const auto frame = MakeFrame(1.5);
  mailbox.Put(frame);

  uint64_t seen = 0;
  auto read = mailbox.ReadIfChanged(seen);
  EXPECT_TRUE(read.changed);
  EXPECT_EQ(read.frame, frame);
  EXPECT_EQ(seen, mailbox.Sequence());

  read = mailbox.ReadIfChanged(seen);
  EXPECT_FALSE(read.changed);
}

TEST(FrameMailbox, NewReaderGetsCurrentFrame)
{
  FrameMailbox mailbox;
  mailbox.Put(MakeFrame(1.0));
  mailbox.Put(MakeFrame(2.0));

  uint64_t firstReader = 0;
  uint64_t secondReader = 0;
  EXPECT_DOUBLE_EQ(mailbox.ReadIfChanged(firstReader).frame->mediaSeconds, 2.0);
  EXPECT_DOUBLE_EQ(mailbox.ReadIfChanged(secondReader).frame->mediaSeconds, 2.0);
}

TEST(FrameMailbox, ClearIsReportedAsChangeWithoutFrame)
{
  FrameMailbox mailbox;
  mailbox.Put(MakeFrame(1.0));
  uint64_t seen = 0;
  mailbox.ReadIfChanged(seen);

  mailbox.Clear();
  const auto read = mailbox.ReadIfChanged(seen);
  EXPECT_TRUE(read.changed);
  EXPECT_EQ(read.frame, nullptr);
}

TEST(FrameMailbox, ConcurrentWriterAndReaderSeeMonotonicFrames)
{
  FrameMailbox mailbox;
  constexpr int kFrames = 2000;
  std::atomic<bool> done{false};

  std::thread writer([&] {
    for (int i = 1; i <= kFrames; ++i)
      mailbox.Put(MakeFrame(i));
    done = true;
  });

  uint64_t seen = 0;
  double last = 0.0;
  bool finished = false;
  while (!finished)
  {
    finished = done.load();
    const auto read = mailbox.ReadIfChanged(seen);
    if (read.changed && read.frame)
    {
      EXPECT_GE(read.frame->mediaSeconds, last);
      last = read.frame->mediaSeconds;
    }
  }
  writer.join();

  const auto read = mailbox.ReadIfChanged(seen);
  if (read.changed)
    last = read.frame->mediaSeconds;
  EXPECT_DOUBLE_EQ(last, kFrames);
}

TEST(VideoFrame, ChromaSizeRoundsUp)
{
  EXPECT_EQ(partyvideo::ChromaWidth(1920), 960);
  EXPECT_EQ(partyvideo::ChromaWidth(1281), 641);
  EXPECT_EQ(partyvideo::ChromaHeight(1081), 541);
}
```

- [ ] **Step 2: In `tests/cpp/CMakeLists.txt` eintragen**

`TEST_SOURCES`: Zeile `frame_mailbox_test.cpp` ergänzen. `CORE_SOURCES`: Zeile `${REPO_ROOT}/src/core/FrameMailbox.cpp` ergänzen.

- [ ] **Step 3: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Abbruch, weil `src/core/FrameMailbox.cpp` / `core/FrameMailbox.h` fehlt.

- [ ] **Step 4: `src/core/VideoFrame.h` anlegen**

```cpp
#pragma once

#include "core/ColorConversion.h"

#include <array>
#include <cstdint>
#include <vector>

namespace partyvideo
{

// Ein dekodiertes Bild im Format YUV 4:2:0 mit 8 Bit, unabhängig von FFmpeg-Puffern.
struct VideoFrame
{
  int width = 0;  // sichtbare Breite in Pixeln
  int height = 0; // sichtbare Höhe in Pixeln
  // Ebene 0 = Y (width × height), 1 = U und 2 = V (je ChromaWidth × ChromaHeight).
  std::array<std::vector<uint8_t>, 3> planes;
  // Bytes pro Zeile je Ebene (>= sichtbare Ebenenbreite, wegen Speicherausrichtung).
  std::array<int, 3> strides{0, 0, 0};
  double mediaSeconds = 0.0; // über Schleifen hinweg fortlaufend
  ColorMatrix matrix = ColorMatrix::Bt709;
  bool fullRange = false;
  int sarNum = 1;
  int sarDen = 1;
};

inline int ChromaWidth(int width)
{
  return (width + 1) / 2;
}

inline int ChromaHeight(int height)
{
  return (height + 1) / 2;
}

} // namespace partyvideo
```

- [ ] **Step 5: `src/core/FrameMailbox.h` anlegen**

```cpp
#pragma once

#include "core/VideoFrame.h"

#include <cstdint>
#include <memory>
#include <mutex>

namespace partyvideo
{

struct MailboxRead
{
  bool changed = false;                     // seit dem letzten Lesen neues Bild oder geleert
  std::shared_ptr<const VideoFrame> frame;  // nullptr = schwarz anzeigen
};

// Thread-sicheres Fach für das jeweils aktuelle Bild zwischen Worker- und Render-Thread.
// Das letzte Bild bleibt liegen, damit eine neu erzeugte Kodi-Instanz es sofort anzeigen kann.
class FrameMailbox
{
public:
  void Put(std::shared_ptr<const VideoFrame> frame);
  void Clear();
  // Jeder Leser führt seine eigene lastSequence (Start 0); sie wird bei einer Änderung aktualisiert.
  MailboxRead ReadIfChanged(uint64_t& lastSequence) const;
  uint64_t Sequence() const;

private:
  mutable std::mutex m_mutex;
  std::shared_ptr<const VideoFrame> m_frame;
  uint64_t m_sequence = 0;
};

} // namespace partyvideo
```

- [ ] **Step 6: `src/core/FrameMailbox.cpp` anlegen**

```cpp
#include "core/FrameMailbox.h"

#include <utility>

namespace partyvideo
{

void FrameMailbox::Put(std::shared_ptr<const VideoFrame> frame)
{
  std::lock_guard<std::mutex> lock(m_mutex);
  m_frame = std::move(frame);
  ++m_sequence;
}

void FrameMailbox::Clear()
{
  std::lock_guard<std::mutex> lock(m_mutex);
  m_frame.reset();
  ++m_sequence;
}

MailboxRead FrameMailbox::ReadIfChanged(uint64_t& lastSequence) const
{
  std::lock_guard<std::mutex> lock(m_mutex);
  MailboxRead result;
  if (m_sequence == lastSequence)
    return result;
  lastSequence = m_sequence;
  result.changed = true;
  result.frame = m_frame;
  return result;
}

uint64_t FrameMailbox::Sequence() const
{
  std::lock_guard<std::mutex> lock(m_mutex);
  return m_sequence;
}

} // namespace partyvideo
```

- [ ] **Step 7: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 25`, keine Warnungen.

- [ ] **Step 8: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 5: Statusdateien (StateFiles)

**Files:**
- Create: `third_party/nlohmann/json.hpp`, `third_party/nlohmann/LICENSE.MIT`, `src/core/StateFiles.h`, `src/core/StateFiles.cpp`, `tests/cpp/state_files_test.cpp`, `tests/cpp/TempDir.h`
- Modify: `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: Testumgebung aus Task 1 (Include-Wurzel `third_party/`)
- Produces (in `src/core/StateFiles.h`, `namespace partyvideo`):
  ```cpp
  struct PlaybackState { int64_t revision = 0; std::string source; std::string kind; std::string title; };
  struct RendererStatus
  {
    int64_t revision = 0;
    std::string state = "idle"; // idle | loading | playing | error
    std::string error;          // "" | file_not_found | open_failed | no_video_stream | unsupported_codec | decode_failed
    std::string warning;        // "" | too_large
    int width = 0;
    int height = 0;
    std::string codec;
  };
  std::optional<PlaybackState> ReadPlaybackState(const std::string& path);
  bool WriteRendererStatus(const std::string& path, const RendererStatus& status);
  ```
  - `tests/cpp/TempDir.h`: `class TempDir { public: TempDir(); ~TempDir(); const std::filesystem::path& Path() const; };` – eindeutiges, beim Zerstören gelöschtes Verzeichnis (auch von Task 6 und 7 benutzt)

- [ ] **Step 1: nlohmann/json 3.11.3 einbinden und prüfen**

Run:
```bash
cd /home/tesla/githubprojects/visualization.partyvideo \
 && mkdir -p third_party/nlohmann \
 && curl -fsSL -o third_party/nlohmann/json.hpp https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp \
 && curl -fsSL -o third_party/nlohmann/LICENSE.MIT https://raw.githubusercontent.com/nlohmann/json/v3.11.3/LICENSE.MIT \
 && echo "9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6  third_party/nlohmann/json.hpp" | sha256sum -c
```
Expected: `third_party/nlohmann/json.hpp: OK`

- [ ] **Step 2: `tests/cpp/TempDir.h` anlegen**

```cpp
#pragma once

#include <atomic>
#include <filesystem>
#include <string>

#include <unistd.h>

// Eindeutiges temporäres Verzeichnis für einen Test; wird beim Zerstören samt Inhalt gelöscht.
class TempDir
{
public:
  TempDir()
  {
    static std::atomic<int> counter{0};
    m_path = std::filesystem::temp_directory_path() /
             ("partyvideo-test-" + std::to_string(::getpid()) + "-" + std::to_string(++counter));
    std::filesystem::remove_all(m_path);
    std::filesystem::create_directories(m_path);
  }

  ~TempDir()
  {
    std::error_code ignored;
    std::filesystem::remove_all(m_path, ignored);
  }

  TempDir(const TempDir&) = delete;
  TempDir& operator=(const TempDir&) = delete;

  const std::filesystem::path& Path() const { return m_path; }

private:
  std::filesystem::path m_path;
};
```

- [ ] **Step 3: Failing Test schreiben – `tests/cpp/state_files_test.cpp`**

```cpp
#include "TempDir.h"
#include "core/StateFiles.h"

#include <fstream>
#include <string>

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

using partyvideo::ReadPlaybackState;
using partyvideo::RendererStatus;
using partyvideo::WriteRendererStatus;

namespace
{

void WriteText(const std::filesystem::path& path, const std::string& text)
{
  std::ofstream out(path);
  out << text;
}

} // namespace

TEST(StateFiles, ReadsCompleteState)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"revision": 7, "source": "/storage/v.mp4", "kind": "file", "title": "Loop"})");

  const auto state = ReadPlaybackState(path.string());
  ASSERT_TRUE(state.has_value());
  EXPECT_EQ(state->revision, 7);
  EXPECT_EQ(state->source, "/storage/v.mp4");
  EXPECT_EQ(state->kind, "file");
  EXPECT_EQ(state->title, "Loop");
}

TEST(StateFiles, MissingFileGivesNullopt)
{
  TempDir dir;
  EXPECT_FALSE(ReadPlaybackState((dir.Path() / "state.json").string()).has_value());
}

TEST(StateFiles, InvalidJsonGivesNullopt)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"revision": 7, "source": )");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
}

TEST(StateFiles, RevisionMustBeAnInteger)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"source": "/storage/v.mp4"})");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
  WriteText(path, R"({"revision": "7", "source": "/storage/v.mp4"})");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
  WriteText(path, R"([1, 2, 3])");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
}

TEST(StateFiles, MissingOrWrongOptionalFieldsBecomeEmpty)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"revision": 3, "source": 42})");

  const auto state = ReadPlaybackState(path.string());
  ASSERT_TRUE(state.has_value());
  EXPECT_EQ(state->revision, 3);
  EXPECT_EQ(state->source, "");
  EXPECT_EQ(state->kind, "");
  EXPECT_EQ(state->title, "");
}

TEST(StateFiles, WriteCreatesDirectoryAndAllFields)
{
  TempDir dir;
  const auto path = dir.Path() / "neu" / "renderer.json";
  RendererStatus status;
  status.revision = 9;
  status.state = "error";
  status.error = "file_not_found";
  status.warning = "too_large";
  status.width = 2048;
  status.height = 1152;
  status.codec = "h264";

  ASSERT_TRUE(WriteRendererStatus(path.string(), status));

  std::ifstream in(path);
  const auto json = nlohmann::json::parse(in);
  EXPECT_EQ(json.at("revision"), 9);
  EXPECT_EQ(json.at("state"), "error");
  EXPECT_EQ(json.at("error"), "file_not_found");
  EXPECT_EQ(json.at("warning"), "too_large");
  EXPECT_EQ(json.at("width"), 2048);
  EXPECT_EQ(json.at("height"), 1152);
  EXPECT_EQ(json.at("codec"), "h264");
  EXPECT_EQ(json.size(), 7u);
}

TEST(StateFiles, WriteOverwritesAndLeavesNoTempFile)
{
  TempDir dir;
  const auto path = dir.Path() / "renderer.json";
  RendererStatus status;
  status.state = "loading";
  ASSERT_TRUE(WriteRendererStatus(path.string(), status));
  status.state = "playing";
  ASSERT_TRUE(WriteRendererStatus(path.string(), status));

  std::ifstream in(path);
  EXPECT_EQ(nlohmann::json::parse(in).at("state"), "playing");
  EXPECT_FALSE(std::filesystem::exists(path.string() + ".tmp"));
}

TEST(StateFiles, WriteFailsForUnwritableLocation)
{
  TempDir dir;
  const auto blocker = dir.Path() / "datei";
  WriteText(blocker, "kein Verzeichnis");
  RendererStatus status;
  EXPECT_FALSE(WriteRendererStatus((blocker / "renderer.json").string(), status));
}
```

- [ ] **Step 4: In `tests/cpp/CMakeLists.txt` eintragen**

`TEST_SOURCES`: Zeile `state_files_test.cpp` ergänzen. `CORE_SOURCES`: Zeile `${REPO_ROOT}/src/core/StateFiles.cpp` ergänzen.

- [ ] **Step 5: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Abbruch, weil `src/core/StateFiles.cpp` / `core/StateFiles.h` fehlt.

- [ ] **Step 6: `src/core/StateFiles.h` anlegen**

```cpp
#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace partyvideo
{

// Inhalt von state.json (Spec §5.1), geschrieben vom Service.
struct PlaybackState
{
  int64_t revision = 0;
  std::string source; // absoluter Pfad oder "" (Visual aus)
  std::string kind;   // "youtube" | "file" | ""
  std::string title;
};

// Inhalt von renderer.json (Spec §5.2), geschrieben vom Renderer.
struct RendererStatus
{
  int64_t revision = 0;
  std::string state = "idle"; // idle | loading | playing | error
  std::string error;          // "" | file_not_found | open_failed | no_video_stream | unsupported_codec | decode_failed
  std::string warning;        // "" | too_large
  int width = 0;
  int height = 0;
  std::string codec;
};

// std::nullopt, wenn die Datei fehlt, kein JSON-Objekt ist oder keine ganzzahlige "revision" hat.
// Fehlende oder nicht-textuelle Felder source/kind/title werden zu "".
std::optional<PlaybackState> ReadPlaybackState(const std::string& path);

// Schreibt atomar (erst path + ".tmp", dann rename) und legt das Verzeichnis bei Bedarf an.
bool WriteRendererStatus(const std::string& path, const RendererStatus& status);

} // namespace partyvideo
```

- [ ] **Step 7: `src/core/StateFiles.cpp` anlegen**

```cpp
#include "core/StateFiles.h"

#include <filesystem>
#include <fstream>
#include <system_error>

#include <nlohmann/json.hpp>

namespace partyvideo
{

namespace
{

std::string StringField(const nlohmann::json& object, const char* key)
{
  const auto it = object.find(key);
  if (it == object.end() || !it->is_string())
    return {};
  return it->get<std::string>();
}

} // namespace

std::optional<PlaybackState> ReadPlaybackState(const std::string& path)
{
  std::ifstream in(path);
  if (!in)
    return std::nullopt;

  const auto json = nlohmann::json::parse(in, nullptr, false);
  if (json.is_discarded() || !json.is_object())
    return std::nullopt;

  const auto revision = json.find("revision");
  if (revision == json.end() || !revision->is_number_integer())
    return std::nullopt;

  PlaybackState state;
  state.revision = revision->get<int64_t>();
  state.source = StringField(json, "source");
  state.kind = StringField(json, "kind");
  state.title = StringField(json, "title");
  return state;
}

bool WriteRendererStatus(const std::string& path, const RendererStatus& status)
{
  const nlohmann::json json = {
      {"revision", status.revision}, {"state", status.state},   {"error", status.error},
      {"warning", status.warning},   {"width", status.width},   {"height", status.height},
      {"codec", status.codec},
  };

  std::error_code ec;
  const std::filesystem::path target(path);
  if (target.has_parent_path())
  {
    std::filesystem::create_directories(target.parent_path(), ec);
    if (ec)
      return false;
  }

  const std::string temp = path + ".tmp";
  {
    std::ofstream out(temp, std::ios::trunc);
    if (!out)
      return false;
    out << json.dump(2) << '\n';
    if (!out)
      return false;
  }

  std::filesystem::rename(temp, target, ec);
  if (ec)
  {
    std::filesystem::remove(temp, ec);
    return false;
  }
  return true;
}

} // namespace partyvideo
```

- [ ] **Step 8: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 33`, keine Warnungen.

- [ ] **Step 9: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 6: Videoquelle (VideoSource) mit Testvideos

**Files:**
- Create: `tests/cpp/make_fixtures.sh`, `src/core/VideoSource.h`, `src/core/VideoSource.cpp`, `tests/cpp/video_source_test.cpp`
- Modify: `scripts/test-cpp-in-container.sh`, `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: `VideoFrame`, `ChromaWidth`, `ChromaHeight` (Task 4); `ColorSpaceHint`, `ChooseMatrix` (Task 2); Image mit `/usr/bin/ffmpeg` und `/opt/ffmpeg-amd64` ohne `mpeg4`-Decoder (Task 1)
- Produces:
  - Testvideos in `build/fixtures/` (Namen siehe Step 1); Makro `PARTYVIDEO_FIXTURE_DIR` (String) im Testprogramm
  - In `src/core/VideoSource.h`, `namespace partyvideo`:
    ```cpp
    enum class SourceError { None, FileNotFound, OpenFailed, NoVideoStream, UnsupportedCodec, DecodeFailed };
    const char* ErrorCode(SourceError error); // "" | "file_not_found" | "open_failed" | "no_video_stream" | "unsupported_codec" | "decode_failed"
    struct SourceInfo { int width = 0; int height = 0; std::string codec; double frameSeconds = 0.04; };
    class VideoSource
    {
    public:
      static constexpr int kMaxConsecutiveErrors = 50;
      static constexpr int kDecoderThreads = 3;
      SourceError Open(const std::string& path); // schließt eine offene Quelle vorher
      void Close();
      bool IsOpen() const;
      const SourceInfo& Info() const;
      bool NextFrame(VideoFrame& frame);         // endlos; false bei dauerhaftem Fehler
      void SetSkipNonReference(bool skip);
      SourceError LastError() const;
      int LoopCount() const;
    };
    ```
    `mediaSeconds` beginnt bei 0 und steigt über Schleifen hinweg streng monoton. Nach einem Fehler ist die Quelle geschlossen (`IsOpen() == false`), `LastError()` nennt den Grund.

Hinweis: `decode_failed` (50 Decodierfehler in Folge oder ein Durchlauf ohne ein einziges Bild) lässt sich nicht zuverlässig mit einer erzeugten Datei auslösen und wird im Review anhand des Codes geprüft.

- [ ] **Step 1: `tests/cpp/make_fixtures.sh` anlegen**

```bash
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
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/tests/cpp/make_fixtures.sh`

- [ ] **Step 2: `scripts/test-cpp-in-container.sh` ersetzen**

```bash
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
```

- [ ] **Step 3: `tests/cpp/CMakeLists.txt` ergänzen**

Direkt nach `add_compile_options(-Wall -Wextra -Werror)` einfügen:

```cmake
if(NOT FIXTURE_DIR)
  message(FATAL_ERROR "FIXTURE_DIR fehlt (scripts/test-cpp-in-container.sh setzt ihn)")
endif()
```

Nach `target_link_libraries(core_tests PRIVATE partyvideo_core GTest::gtest_main)` einfügen:

```cmake
target_compile_definitions(core_tests PRIVATE PARTYVIDEO_FIXTURE_DIR="${FIXTURE_DIR}")
```

`TEST_SOURCES`: Zeile `video_source_test.cpp` ergänzen. `CORE_SOURCES`: Zeile `${REPO_ROOT}/src/core/VideoSource.cpp` ergänzen.

- [ ] **Step 4: Failing Test schreiben – `tests/cpp/video_source_test.cpp`**

```cpp
#include "core/VideoSource.h"

#include <string>

#include <gtest/gtest.h>

using partyvideo::ColorMatrix;
using partyvideo::ErrorCode;
using partyvideo::SourceError;
using partyvideo::VideoFrame;
using partyvideo::VideoSource;

namespace
{

std::string Fixture(const char* name)
{
  return std::string(PARTYVIDEO_FIXTURE_DIR) + "/" + name;
}

} // namespace

TEST(VideoSource, OpensH264AndReportsInfo)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  EXPECT_TRUE(source.IsOpen());
  EXPECT_EQ(source.Info().width, 320);
  EXPECT_EQ(source.Info().height, 240);
  EXPECT_EQ(source.Info().codec, "h264");
  EXPECT_NEAR(source.Info().frameSeconds, 0.04, 1e-6);
}

TEST(VideoSource, DecodesYuv420FramesWithIncreasingMediaTime)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);

  VideoFrame frame;
  ASSERT_TRUE(source.NextFrame(frame));
  EXPECT_NEAR(frame.mediaSeconds, 0.0, 1e-6);
  EXPECT_EQ(frame.width, 320);
  EXPECT_EQ(frame.height, 240);
  EXPECT_GE(frame.strides[0], 320);
  EXPECT_GE(frame.strides[1], 160);
  EXPECT_GE(frame.strides[2], 160);
  EXPECT_GE(frame.planes[0].size(), static_cast<size_t>(frame.strides[0]) * 240);
  EXPECT_GE(frame.planes[1].size(), static_cast<size_t>(frame.strides[1]) * 120);
  EXPECT_EQ(frame.matrix, ColorMatrix::Bt601);
  EXPECT_FALSE(frame.fullRange);

  double previous = frame.mediaSeconds;
  for (int i = 1; i < 10; ++i)
  {
    ASSERT_TRUE(source.NextFrame(frame));
    EXPECT_NEAR(frame.mediaSeconds - previous, 0.04, 1e-3);
    previous = frame.mediaSeconds;
  }
}

TEST(VideoSource, LoopsSeamlesslyAtEnd)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);

  VideoFrame frame;
  double previous = -1.0;
  for (int i = 0; i < 120; ++i)
  {
    ASSERT_TRUE(source.NextFrame(frame)) << "Bild " << i;
    EXPECT_GT(frame.mediaSeconds, previous) << "Bild " << i;
    if (i == 50)
      EXPECT_NEAR(frame.mediaSeconds, 2.0, 1e-3);
    previous = frame.mediaSeconds;
  }
  EXPECT_GE(source.LoopCount(), 2);
  EXPECT_NEAR(previous, 119 * 0.04, 1e-2);
}

TEST(VideoSource, ConvertsOtherPixelFormatsTo420)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_yuv422p_160x120_1s.mkv")), SourceError::None);

  VideoFrame frame;
  ASSERT_TRUE(source.NextFrame(frame));
  EXPECT_EQ(frame.width, 160);
  EXPECT_EQ(frame.height, 120);
  EXPECT_GE(frame.strides[1], 80);
  EXPECT_GE(frame.planes[1].size(), static_cast<size_t>(frame.strides[1]) * 60);
  EXPECT_GE(frame.planes[2].size(), static_cast<size_t>(frame.strides[2]) * 60);
}

TEST(VideoSource, IgnoresAudioStream)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_with_audio_320x240_1s.mp4")), SourceError::None);
  VideoFrame frame;
  for (int i = 0; i < 30; ++i)
    ASSERT_TRUE(source.NextFrame(frame));
}

TEST(VideoSource, SkippingNonReferenceFramesStillDelivers)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  source.SetSkipNonReference(true);

  VideoFrame frame;
  double previous = -1.0;
  for (int i = 0; i < 20; ++i)
  {
    ASSERT_TRUE(source.NextFrame(frame));
    EXPECT_GT(frame.mediaSeconds, previous);
    previous = frame.mediaSeconds;
  }
}

TEST(VideoSource, LargeVideoReportsItsSize)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_2048x1152_0p4s.mp4")), SourceError::None);
  EXPECT_EQ(source.Info().width, 2048);
  EXPECT_EQ(source.Info().height, 1152);
}

TEST(VideoSource, MissingFile)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("gibt_es_nicht.mp4")), SourceError::FileNotFound);
  EXPECT_FALSE(source.IsOpen());
  EXPECT_EQ(source.LastError(), SourceError::FileNotFound);
  VideoFrame frame;
  EXPECT_FALSE(source.NextFrame(frame));
}

TEST(VideoSource, AudioOnlyFileHasNoVideoStream)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("audio_only_1s.m4a")), SourceError::NoVideoStream);
  EXPECT_FALSE(source.IsOpen());
}

TEST(VideoSource, TextFileCannotBeOpened)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("not_a_video.mp4")), SourceError::OpenFailed);
  EXPECT_FALSE(source.IsOpen());
}

TEST(VideoSource, MissingDecoderIsUnsupportedCodec)
{
  // Der amd64-Testbuild von FFmpeg hat absichtlich keinen mpeg4-Decoder.
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("mpeg4_320x240_1s.avi")), SourceError::UnsupportedCodec);
  EXPECT_FALSE(source.IsOpen());
}

TEST(VideoSource, CanBeReopenedAfterError)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("gibt_es_nicht.mp4")), SourceError::FileNotFound);
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  EXPECT_EQ(source.LastError(), SourceError::None);
  VideoFrame frame;
  EXPECT_TRUE(source.NextFrame(frame));
}

TEST(VideoSource, ErrorCodesMatchSpec)
{
  EXPECT_STREQ(ErrorCode(SourceError::None), "");
  EXPECT_STREQ(ErrorCode(SourceError::FileNotFound), "file_not_found");
  EXPECT_STREQ(ErrorCode(SourceError::OpenFailed), "open_failed");
  EXPECT_STREQ(ErrorCode(SourceError::NoVideoStream), "no_video_stream");
  EXPECT_STREQ(ErrorCode(SourceError::UnsupportedCodec), "unsupported_codec");
  EXPECT_STREQ(ErrorCode(SourceError::DecodeFailed), "decode_failed");
}
```

- [ ] **Step 5: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Testvideos werden erzeugt (`ls build/fixtures` zeigt 7 Dateien), dann Abbruch, weil `src/core/VideoSource.cpp` / `core/VideoSource.h` fehlt.

- [ ] **Step 6: `src/core/VideoSource.h` anlegen**

```cpp
#pragma once

#include "core/VideoFrame.h"

#include <cstdint>
#include <string>

struct AVCodecContext;
struct AVFormatContext;
struct AVFrame;
struct AVPacket;
struct SwsContext;

namespace partyvideo
{

enum class SourceError
{
  None,
  FileNotFound,
  OpenFailed,
  NoVideoStream,
  UnsupportedCodec,
  DecodeFailed
};

// Fehlercode für renderer.json (Spec §5.2); "" für None.
const char* ErrorCode(SourceError error);

struct SourceInfo
{
  int width = 0;
  int height = 0;
  std::string codec;
  double frameSeconds = 0.04; // Bilddauer aus der Bildrate, ersatzweise 25 fps
};

// Liest den besten Videostream einer lokalen Datei mit FFmpeg und liefert Bilder als YUV 4:2:0.
// Am Dateiende geht es nahtlos von vorn weiter; mediaSeconds steigt dabei weiter an.
// Nicht thread-sicher: nur der Worker-Thread benutzt eine Instanz.
class VideoSource
{
public:
  static constexpr int kMaxConsecutiveErrors = 50;
  static constexpr int kDecoderThreads = 3;

  VideoSource() = default;
  ~VideoSource();
  VideoSource(const VideoSource&) = delete;
  VideoSource& operator=(const VideoSource&) = delete;

  // Schließt eine offene Quelle und öffnet path. Bei Fehler bleibt die Quelle geschlossen.
  SourceError Open(const std::string& path);
  void Close();
  bool IsOpen() const { return m_codec != nullptr; }
  const SourceInfo& Info() const { return m_info; }

  // Nächstes Bild. false ohne offene Quelle oder bei dauerhaftem Fehler (dann LastError()).
  bool NextFrame(VideoFrame& frame);
  // Aufholen bei Verspätung: Bilder ohne Referenz überspringen, solange aktiv.
  void SetSkipNonReference(bool skip);

  SourceError LastError() const { return m_error; }
  int LoopCount() const { return m_loopCount; }

private:
  SourceError Fail(SourceError error);
  bool CountDecodeError();
  bool RestartFromBeginning();
  double NextMediaSeconds();
  bool ConvertFrame(VideoFrame& out);

  std::string m_path;
  SourceInfo m_info;
  SourceError m_error = SourceError::None;

  AVFormatContext* m_format = nullptr;
  AVCodecContext* m_codec = nullptr;
  AVPacket* m_packet = nullptr;
  AVFrame* m_decoded = nullptr;
  SwsContext* m_sws = nullptr;
  int m_streamIndex = -1;
  double m_timeBase = 0.0;

  int64_t m_firstPts = 0;
  bool m_haveFirstPts = false;
  double m_loopOffset = 0.0;
  double m_lastMediaSeconds = 0.0;
  bool m_haveFrame = false;
  bool m_frameInThisLoop = false;
  bool m_draining = false;
  int m_loopCount = 0;
  int m_consecutiveErrors = 0;
};

} // namespace partyvideo
```

- [ ] **Step 7: `src/core/VideoSource.cpp` anlegen**

```cpp
#include "core/VideoSource.h"

#include "core/ColorConversion.h"

#include <array>
#include <cstring>

#include <sys/stat.h>

extern "C"
{
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/imgutils.h>
#include <libavutil/pixdesc.h>
#include <libswscale/swscale.h>
}

namespace partyvideo
{

namespace
{

constexpr int kSwsAlignment = 32; // swscale darf mit SIMD über die sichtbare Zeilenbreite hinaus schreiben

ColorSpaceHint HintFromFfmpeg(int colorspace)
{
  switch (colorspace)
  {
    case AVCOL_SPC_BT709:
      return ColorSpaceHint::Bt709;
    case AVCOL_SPC_BT470BG:
    case AVCOL_SPC_SMPTE170M:
    case AVCOL_SPC_FCC:
      return ColorSpaceHint::Bt601;
    default:
      return ColorSpaceHint::Unknown;
  }
}

bool IsFullRangeFormat(int format)
{
  return format == AV_PIX_FMT_YUVJ420P || format == AV_PIX_FMT_YUVJ422P || format == AV_PIX_FMT_YUVJ444P ||
         format == AV_PIX_FMT_YUVJ440P || format == AV_PIX_FMT_YUVJ411P;
}

} // namespace

const char* ErrorCode(SourceError error)
{
  switch (error)
  {
    case SourceError::None:
      return "";
    case SourceError::FileNotFound:
      return "file_not_found";
    case SourceError::OpenFailed:
      return "open_failed";
    case SourceError::NoVideoStream:
      return "no_video_stream";
    case SourceError::UnsupportedCodec:
      return "unsupported_codec";
    case SourceError::DecodeFailed:
      return "decode_failed";
  }
  return "decode_failed";
}

VideoSource::~VideoSource()
{
  Close();
}

void VideoSource::Close()
{
  sws_freeContext(m_sws);
  m_sws = nullptr;
  av_frame_free(&m_decoded);
  av_packet_free(&m_packet);
  avcodec_free_context(&m_codec);
  avformat_close_input(&m_format);

  m_info = SourceInfo{};
  m_error = SourceError::None;
  m_streamIndex = -1;
  m_timeBase = 0.0;
  m_firstPts = 0;
  m_haveFirstPts = false;
  m_loopOffset = 0.0;
  m_lastMediaSeconds = 0.0;
  m_haveFrame = false;
  m_frameInThisLoop = false;
  m_draining = false;
  m_loopCount = 0;
  m_consecutiveErrors = 0;
}

SourceError VideoSource::Fail(SourceError error)
{
  Close();
  m_error = error;
  return error;
}

SourceError VideoSource::Open(const std::string& path)
{
  Close();
  m_path = path;

  struct stat info
  {
  };
  if (::stat(path.c_str(), &info) != 0 || !S_ISREG(info.st_mode))
    return Fail(SourceError::FileNotFound);

  if (avformat_open_input(&m_format, path.c_str(), nullptr, nullptr) < 0)
    return Fail(SourceError::OpenFailed);
  if (avformat_find_stream_info(m_format, nullptr) < 0)
    return Fail(SourceError::OpenFailed);

  const AVCodec* decoder = nullptr;
  const int index = av_find_best_stream(m_format, AVMEDIA_TYPE_VIDEO, -1, -1, &decoder, 0);
  if (index == AVERROR_STREAM_NOT_FOUND)
    return Fail(SourceError::NoVideoStream);
  if (index == AVERROR_DECODER_NOT_FOUND || (index >= 0 && decoder == nullptr))
    return Fail(SourceError::UnsupportedCodec);
  if (index < 0)
    return Fail(SourceError::OpenFailed);

  AVStream* stream = m_format->streams[index];
  if (stream->disposition & AV_DISPOSITION_ATTACHED_PIC)
    return Fail(SourceError::NoVideoStream); // nur ein Coverbild, kein Video

  m_codec = avcodec_alloc_context3(decoder);
  if (m_codec == nullptr || avcodec_parameters_to_context(m_codec, stream->codecpar) < 0)
    return Fail(SourceError::OpenFailed);
  m_codec->thread_count = kDecoderThreads;
  m_codec->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;
  m_codec->pkt_timebase = stream->time_base;
  if (avcodec_open2(m_codec, decoder, nullptr) < 0)
    return Fail(SourceError::UnsupportedCodec);

  m_packet = av_packet_alloc();
  m_decoded = av_frame_alloc();
  if (m_packet == nullptr || m_decoded == nullptr)
    return Fail(SourceError::OpenFailed);

  m_streamIndex = index;
  m_timeBase = av_q2d(stream->time_base);

  const AVRational rate = av_guess_frame_rate(m_format, stream, nullptr);
  m_info.width = m_codec->width;
  m_info.height = m_codec->height;
  m_info.codec = avcodec_get_name(decoder->id);
  m_info.frameSeconds = (rate.num > 0 && rate.den > 0) ? av_q2d(av_inv_q(rate)) : 0.04;
  return SourceError::None;
}

void VideoSource::SetSkipNonReference(bool skip)
{
  if (m_codec != nullptr)
    m_codec->skip_frame = skip ? AVDISCARD_NONREF : AVDISCARD_DEFAULT;
}

bool VideoSource::CountDecodeError()
{
  if (++m_consecutiveErrors >= kMaxConsecutiveErrors)
  {
    Fail(SourceError::DecodeFailed);
    return false;
  }
  return true;
}

bool VideoSource::RestartFromBeginning()
{
  if (!m_frameInThisLoop)
  {
    // Ein ganzer Durchlauf ohne ein einziges Bild: die Datei ist nicht abspielbar.
    Fail(SourceError::DecodeFailed);
    return false;
  }

  // Die nächste Runde beginnt ein Bild nach dem zuletzt gelieferten.
  m_loopOffset = m_lastMediaSeconds + m_info.frameSeconds;
  m_haveFirstPts = false;
  m_frameInThisLoop = false;
  m_draining = false;
  ++m_loopCount;

  const AVStream* stream = m_format->streams[m_streamIndex];
  const int64_t start = stream->start_time != AV_NOPTS_VALUE ? stream->start_time : 0;
  if (av_seek_frame(m_format, m_streamIndex, start, AVSEEK_FLAG_BACKWARD) >= 0)
  {
    avcodec_flush_buffers(m_codec);
    return true;
  }

  // Seek nicht möglich: neu öffnen und den Schleifenzustand übernehmen.
  const std::string path = m_path;
  const double loopOffset = m_loopOffset;
  const double lastMediaSeconds = m_lastMediaSeconds;
  const int loopCount = m_loopCount;
  if (Open(path) != SourceError::None)
    return false;
  m_loopOffset = loopOffset;
  m_lastMediaSeconds = lastMediaSeconds;
  m_haveFrame = true;
  m_loopCount = loopCount;
  return true;
}

double VideoSource::NextMediaSeconds()
{
  const int64_t pts = m_decoded->best_effort_timestamp;
  double media = m_haveFrame ? m_lastMediaSeconds + m_info.frameSeconds : 0.0;
  if (pts != AV_NOPTS_VALUE)
  {
    if (!m_haveFirstPts)
    {
      m_firstPts = pts;
      m_haveFirstPts = true;
    }
    media = m_loopOffset + static_cast<double>(pts - m_firstPts) * m_timeBase;
  }
  if (m_haveFrame && media <= m_lastMediaSeconds)
    media = m_lastMediaSeconds + m_info.frameSeconds; // streng monoton halten
  return media;
}

bool VideoSource::NextFrame(VideoFrame& frame)
{
  if (m_codec == nullptr)
    return false;

  while (true)
  {
    int ret = avcodec_receive_frame(m_codec, m_decoded);
    if (ret == 0)
    {
      m_consecutiveErrors = 0;
      frame.mediaSeconds = NextMediaSeconds();
      const bool converted = ConvertFrame(frame);
      av_frame_unref(m_decoded);
      if (!converted)
      {
        Fail(SourceError::DecodeFailed);
        return false;
      }
      m_lastMediaSeconds = frame.mediaSeconds;
      m_haveFrame = true;
      m_frameInThisLoop = true;
      return true;
    }
    if (ret == AVERROR_EOF)
    {
      if (!RestartFromBeginning())
        return false;
      continue;
    }
    if (ret != AVERROR(EAGAIN))
    {
      if (!CountDecodeError())
        return false;
      continue;
    }

    // Der Decoder braucht weitere Daten.
    if (m_draining)
    {
      // Beim Leeren darf kein EAGAIN mehr kommen; wie Dateiende behandeln statt endlos zu warten.
      if (!RestartFromBeginning())
        return false;
      continue;
    }
    ret = av_read_frame(m_format, m_packet);
    if (ret < 0)
    {
      // Dateiende oder unlesbarer Rest: Decoder leeren, danach beginnt die nächste Runde.
      avcodec_send_packet(m_codec, nullptr);
      m_draining = true;
      continue;
    }
    if (m_packet->stream_index != m_streamIndex)
    {
      av_packet_unref(m_packet);
      continue;
    }
    ret = avcodec_send_packet(m_codec, m_packet);
    av_packet_unref(m_packet);
    if (ret < 0 && ret != AVERROR(EAGAIN) && !CountDecodeError())
      return false;
  }
}

bool VideoSource::ConvertFrame(VideoFrame& out)
{
  const AVFrame* src = m_decoded;
  const int width = src->width;
  const int height = src->height;
  if (width <= 0 || height <= 0)
    return false;

  const std::array<int, 3> planeWidth{width, ChromaWidth(width), ChromaWidth(width)};
  const std::array<int, 3> planeHeight{height, ChromaHeight(height), ChromaHeight(height)};
  const bool direct = src->format == AV_PIX_FMT_YUV420P || src->format == AV_PIX_FMT_YUVJ420P;

  out.width = width;
  out.height = height;

  if (direct)
  {
    for (int p = 0; p < 3; ++p)
    {
      const int stride = src->linesize[p];
      if (stride < planeWidth[p])
        return false; // negative bzw. zu kurze Zeilen werden nicht unterstützt
      out.strides[p] = stride;
      out.planes[p].resize(static_cast<size_t>(stride) * planeHeight[p]);
      for (int y = 0; y < planeHeight[p]; ++y)
        std::memcpy(out.planes[p].data() + static_cast<size_t>(y) * stride,
                    src->data[p] + static_cast<ptrdiff_t>(y) * stride, static_cast<size_t>(stride));
    }
    out.fullRange = src->format == AV_PIX_FMT_YUVJ420P || src->color_range == AVCOL_RANGE_JPEG;
  }
  else
  {
    m_sws = sws_getCachedContext(m_sws, width, height, static_cast<AVPixelFormat>(src->format), width, height,
                                 AV_PIX_FMT_YUV420P, SWS_BILINEAR, nullptr, nullptr, nullptr);
    if (m_sws == nullptr)
      return false;

    std::array<uint8_t*, 4> dst{};
    std::array<int, 4> dstStride{};
    for (int p = 0; p < 3; ++p)
    {
      const int stride = FFALIGN(planeWidth[p], kSwsAlignment);
      out.strides[p] = stride;
      // Eine Zusatzzeile als Reserve für SIMD-Schreibzugriffe über das Ende hinaus.
      out.planes[p].assign(static_cast<size_t>(stride) * (planeHeight[p] + 1), 0);
      dst[p] = out.planes[p].data();
      dstStride[p] = stride;
    }
    if (sws_scale(m_sws, src->data, src->linesize, 0, height, dst.data(), dstStride.data()) != height)
      return false;
    // swscale wandelt YUVJ-Formate nach Limited Range; nur eine reine Range-Markierung bleibt Full Range.
    out.fullRange = !IsFullRangeFormat(src->format) && src->color_range == AVCOL_RANGE_JPEG;
  }

  out.matrix = ChooseMatrix(HintFromFfmpeg(src->colorspace), height);
  // av_guess_sample_aspect_ratio erwartet einen nicht-konstanten Frame.
  const AVRational sar = av_guess_sample_aspect_ratio(m_format, m_format->streams[m_streamIndex], m_decoded);
  out.sarNum = sar.num > 0 ? sar.num : 1;
  out.sarDen = sar.den > 0 ? sar.den : 1;
  return true;
}

} // namespace partyvideo
```

- [ ] **Step 8: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 46`, keine Compiler-Warnungen. Falls FFmpeg bei den Fehlerfällen Meldungen auf stderr ausgibt, im Bericht nennen (keine Testfehler).

- [ ] **Step 9: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 7: Wiedergabe-Engine (PlaybackEngine)

**Files:**
- Create: `src/core/PlaybackEngine.h`, `src/core/PlaybackEngine.cpp`, `tests/cpp/playback_engine_test.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: `FramePacer` (Task 3), `FrameMailbox`/`VideoFrame` (Task 4), `ReadPlaybackState`/`WriteRendererStatus`/`RendererStatus` (Task 5), `VideoSource`/`SourceError`/`ErrorCode` (Task 6), `TempDir` und Fixtures (Task 5/6)
- Produces (in `src/core/PlaybackEngine.h`, `namespace partyvideo`):
  ```cpp
  enum class LogLevel { Debug, Info, Warning, Error };
  using LogFunction = std::function<void(LogLevel, const std::string&)>;
  struct EngineConfig
  {
    std::string stateDirectory;                    // enthält state.json und renderer.json
    LogFunction log;                               // darf leer sein
    std::chrono::milliseconds pollInterval{500};
  };
  class PlaybackEngine
  {
  public:
    explicit PlaybackEngine(EngineConfig config);  // startet den Worker; dekodiert erst nach AttachInstance()
    ~PlaybackEngine();                             // beendet und joint den Worker
    void AttachInstance();                         // Kodi Start()
    void DetachInstance();                         // Kodi Stop() / Destruktor; bei 0 Instanzen Pause
    FrameMailbox& Mailbox();
  };
  ```
  Verhalten:
  - Liest `state.json` im Takt `pollInterval`, auch ohne Instanz. Die Datei ist klein; statt der in Spec §6.2 genannten mtime-Vorprüfung wird sie jedes Mal gelesen und nur über `revision` verglichen (einfacher, gleiches Ergebnis). Neue `revision` → Quelle wechseln: `renderer.json` = `loading`, danach `playing` (mit `width`, `height`, `codec`, ggf. `warning: too_large`) oder `error` (Fehlercode). `source == ""` → Quelle schließen, Fach leeren, `idle`. Gleiche `revision` → nichts tun. Ohne `state.json` beim Start: einmal `idle` mit `revision 0`.
  - Dekodiert und taktet nur, solange mindestens eine Instanz angemeldet ist; ohne Instanz pausiert die Uhr, beim nächsten Attach geht es an derselben Stelle weiter.
  - Verspätung > 2 Bilddauern: Bild verwerfen und `SetSkipNonReference(true)`; ≤ 0,5 Bilddauern: wieder `false`. Verspätung > 1 s: Uhr neu ausrichten.
  - Dauerhafter Dekodierfehler: `error` mit Code, Fach leeren; erst eine neue `revision` versucht es erneut.

- [ ] **Step 1: Failing Test schreiben – `tests/cpp/playback_engine_test.cpp`**

```cpp
#include "TempDir.h"
#include "core/PlaybackEngine.h"

#include <chrono>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

using partyvideo::EngineConfig;
using partyvideo::LogLevel;
using partyvideo::PlaybackEngine;
using namespace std::chrono_literals;

namespace
{

std::string Fixture(const char* name)
{
  return std::string(PARTYVIDEO_FIXTURE_DIR) + "/" + name;
}

void WriteState(const TempDir& dir, int revision, const std::string& source)
{
  const auto path = dir.Path() / "state.json";
  {
    std::ofstream out(path.string() + ".tmp");
    out << nlohmann::json{{"revision", revision}, {"source", source}, {"kind", "file"}, {"title", "Test"}}.dump();
  }
  std::filesystem::rename(path.string() + ".tmp", path);
}

nlohmann::json ReadStatus(const TempDir& dir)
{
  std::ifstream in(dir.Path() / "renderer.json");
  if (!in)
    return nlohmann::json::object();
  auto json = nlohmann::json::parse(in, nullptr, false);
  return json.is_discarded() ? nlohmann::json::object() : json;
}

template<typename Predicate>
bool WaitFor(Predicate predicate, std::chrono::milliseconds timeout = 5000ms)
{
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (std::chrono::steady_clock::now() < deadline)
  {
    if (predicate())
      return true;
    std::this_thread::sleep_for(10ms);
  }
  return predicate();
}

bool StatusIs(const TempDir& dir, int revision, const std::string& state)
{
  const auto status = ReadStatus(dir);
  return status.value("revision", -1) == revision && status.value("state", "") == state;
}

EngineConfig Config(const TempDir& dir)
{
  EngineConfig config;
  config.stateDirectory = dir.Path().string();
  config.pollInterval = 50ms;
  return config;
}

double LatestMediaSeconds(PlaybackEngine& engine)
{
  uint64_t seen = 0;
  const auto read = engine.Mailbox().ReadIfChanged(seen);
  return read.frame ? read.frame->mediaSeconds : -1.0;
}

} // namespace

TEST(PlaybackEngine, WritesIdleWithoutStateFile)
{
  TempDir dir;
  PlaybackEngine engine(Config(dir));
  EXPECT_TRUE(WaitFor([&] { return StatusIs(dir, 0, "idle"); }));
}

TEST(PlaybackEngine, PlaysVideoWhileInstanceAttached)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();

  const auto start = engine.Mailbox().Sequence();
  ASSERT_TRUE(WaitFor([&] { return engine.Mailbox().Sequence() >= start + 10; }));

  const auto status = ReadStatus(dir);
  EXPECT_EQ(status.value("state", ""), "playing");
  EXPECT_EQ(status.value("revision", -1), 1);
  EXPECT_EQ(status.value("width", 0), 320);
  EXPECT_EQ(status.value("height", 0), 240);
  EXPECT_EQ(status.value("codec", ""), "h264");
  EXPECT_EQ(status.value("error", "x"), "");
  EXPECT_EQ(status.value("warning", "x"), "");

  const double first = LatestMediaSeconds(engine);
  std::this_thread::sleep_for(200ms);
  EXPECT_GT(LatestMediaSeconds(engine), first);
}

TEST(PlaybackEngine, DoesNotDecodeWithoutInstance)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));

  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));
  std::this_thread::sleep_for(100ms);
  const auto sequence = engine.Mailbox().Sequence();
  std::this_thread::sleep_for(300ms);
  EXPECT_EQ(engine.Mailbox().Sequence(), sequence);
}

TEST(PlaybackEngine, PausesOnDetachAndContinuesWhereItStopped)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return LatestMediaSeconds(engine) > 0.3; }));

  engine.DetachInstance();
  std::this_thread::sleep_for(100ms);
  const double pausedAt = LatestMediaSeconds(engine);
  const auto sequence = engine.Mailbox().Sequence();
  std::this_thread::sleep_for(500ms);
  EXPECT_EQ(engine.Mailbox().Sequence(), sequence);

  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return engine.Mailbox().Sequence() > sequence; }));
  const double resumedAt = LatestMediaSeconds(engine);
  EXPECT_GE(resumedAt, pausedAt);
  EXPECT_LT(resumedAt, pausedAt + 0.25) << "Das Video darf die Pausendauer nicht überspringen";
}

TEST(PlaybackEngine, EmptySourceClearsMailboxAndGoesIdle)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return LatestMediaSeconds(engine) >= 0.0; }));

  WriteState(dir, 2, "");
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 2, "idle"); }));
  std::this_thread::sleep_for(100ms);
  EXPECT_LT(LatestMediaSeconds(engine), 0.0);
}

TEST(PlaybackEngine, MissingFileReportsErrorAndLogs)
{
  TempDir dir;
  std::mutex logMutex;
  std::vector<std::string> messages;
  WriteState(dir, 1, Fixture("gibt_es_nicht.mp4"));

  auto config = Config(dir);
  config.log = [&](LogLevel, const std::string& message) {
    std::lock_guard<std::mutex> lock(logMutex);
    messages.push_back(message);
  };
  PlaybackEngine engine(config);
  engine.AttachInstance();

  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "error"); }));
  EXPECT_EQ(ReadStatus(dir).value("error", ""), "file_not_found");

  std::lock_guard<std::mutex> lock(logMutex);
  bool logged = false;
  for (const auto& message : messages)
    logged = logged || message.find("file_not_found") != std::string::npos;
  EXPECT_TRUE(logged);
}

TEST(PlaybackEngine, NewRevisionReplacesSource)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));

  WriteState(dir, 2, Fixture("h264_yuv422p_160x120_1s.mkv"));
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 2, "playing"); }));
  EXPECT_EQ(ReadStatus(dir).value("width", 0), 160);
  ASSERT_TRUE(WaitFor([&] {
    uint64_t seen = 0;
    const auto read = engine.Mailbox().ReadIfChanged(seen);
    return read.frame && read.frame->width == 160;
  }));
}

TEST(PlaybackEngine, SameRevisionIsNotReloaded)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));

  WriteState(dir, 1, Fixture("gibt_es_nicht.mp4"));
  std::this_thread::sleep_for(300ms);
  EXPECT_TRUE(StatusIs(dir, 1, "playing"));
}

TEST(PlaybackEngine, LargeVideoWarns)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_2048x1152_0p4s.mp4"));
  PlaybackEngine engine(Config(dir));
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));
  EXPECT_EQ(ReadStatus(dir).value("warning", ""), "too_large");
}

TEST(PlaybackEngine, DestructorStopsPromptly)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  auto engine = std::make_unique<PlaybackEngine>(Config(dir));
  engine->AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return LatestMediaSeconds(*engine) > 0.1; }));

  const auto start = std::chrono::steady_clock::now();
  engine.reset();
  EXPECT_LT(std::chrono::steady_clock::now() - start, 1s);
}
```

- [ ] **Step 2: In `tests/cpp/CMakeLists.txt` eintragen**

`TEST_SOURCES`: Zeile `playback_engine_test.cpp` ergänzen. `CORE_SOURCES`: Zeile `${REPO_ROOT}/src/core/PlaybackEngine.cpp` ergänzen.

- [ ] **Step 3: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: Abbruch, weil `src/core/PlaybackEngine.cpp` / `core/PlaybackEngine.h` fehlt.

- [ ] **Step 4: `src/core/PlaybackEngine.h` anlegen**

```cpp
#pragma once

#include "core/FrameMailbox.h"
#include "core/FramePacer.h"
#include "core/VideoSource.h"

#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

namespace partyvideo
{

enum class LogLevel
{
  Debug,
  Info,
  Warning,
  Error
};

using LogFunction = std::function<void(LogLevel, const std::string&)>;

struct EngineConfig
{
  std::string stateDirectory; // enthält state.json (lesen) und renderer.json (schreiben)
  LogFunction log;            // darf leer sein
  std::chrono::milliseconds pollInterval{500};
};

// Prozessweite Wiedergabe: ein Worker-Thread liest state.json, dekodiert das Video und legt
// Bilder zum richtigen Zeitpunkt ins Übergabefach. Kodi-Instanzen melden sich an und ab;
// ohne angemeldete Instanz pausiert die Wiedergabe an der aktuellen Stelle.
class PlaybackEngine
{
public:
  explicit PlaybackEngine(EngineConfig config);
  ~PlaybackEngine();
  PlaybackEngine(const PlaybackEngine&) = delete;
  PlaybackEngine& operator=(const PlaybackEngine&) = delete;

  void AttachInstance();
  void DetachInstance();
  FrameMailbox& Mailbox() { return m_mailbox; }

private:
  using Clock = FramePacer::Clock;

  void Run();
  void PollState();
  void ReportSourceError();
  void WriteStatus(const char* state, SourceError error);
  void WaitUntil(Clock::time_point deadline);
  void Log(LogLevel level, const std::string& message) const;

  const EngineConfig m_config;
  FrameMailbox m_mailbox;

  // Nur vom Worker-Thread benutzt.
  VideoSource m_source;
  FramePacer m_pacer;
  std::shared_ptr<VideoFrame> m_pending; // dekodiert, wartet auf seinen Anzeigezeitpunkt
  bool m_skipping = false;
  bool m_haveRevision = false;
  bool m_wroteInitialStatus = false;
  int64_t m_revision = 0;

  // Geteilt zwischen Kodi-Threads und Worker, geschützt durch m_mutex.
  std::mutex m_mutex;
  std::condition_variable m_wake;
  int m_instances = 0;
  bool m_stop = false;
  bool m_wakeRequested = false;

  std::thread m_worker; // zuletzt, damit alles andere vor dem Thread-Start initialisiert ist
};

} // namespace partyvideo
```

- [ ] **Step 5: `src/core/PlaybackEngine.cpp` anlegen**

```cpp
#include "core/PlaybackEngine.h"

#include "core/StateFiles.h"

#include <algorithm>
#include <utility>

namespace partyvideo
{

namespace
{

constexpr int kMaxPixels = 1920 * 1080;
constexpr double kDropAfterFrames = 2.0;   // mehr als zwei Bilddauern zu spät → verwerfen
constexpr double kCatchUpFrames = 0.5;     // höchstens eine halbe Bilddauer zu spät → normal
constexpr double kResyncSeconds = 1.0;     // weit zurück → Uhr neu ausrichten statt alles zu verwerfen

} // namespace

PlaybackEngine::PlaybackEngine(EngineConfig config)
  : m_config(std::move(config)), m_worker([this] { Run(); })
{
}

PlaybackEngine::~PlaybackEngine()
{
  {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_stop = true;
  }
  m_wake.notify_all();
  if (m_worker.joinable())
    m_worker.join();
}

void PlaybackEngine::AttachInstance()
{
  {
    std::lock_guard<std::mutex> lock(m_mutex);
    ++m_instances;
    m_wakeRequested = true;
  }
  m_wake.notify_all();
}

void PlaybackEngine::DetachInstance()
{
  {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (m_instances > 0)
      --m_instances;
    m_wakeRequested = true;
  }
  m_wake.notify_all();
}

void PlaybackEngine::Log(LogLevel level, const std::string& message) const
{
  if (m_config.log)
    m_config.log(level, message);
}

void PlaybackEngine::WaitUntil(Clock::time_point deadline)
{
  std::unique_lock<std::mutex> lock(m_mutex);
  m_wake.wait_until(lock, deadline, [this] { return m_stop || m_wakeRequested; });
  m_wakeRequested = false;
}

void PlaybackEngine::WriteStatus(const char* state, SourceError error)
{
  RendererStatus status;
  status.revision = m_revision;
  status.state = state;
  status.error = ErrorCode(error);
  if (m_source.IsOpen())
  {
    const auto& info = m_source.Info();
    status.width = info.width;
    status.height = info.height;
    status.codec = info.codec;
    if (info.width * info.height > kMaxPixels)
      status.warning = "too_large";
  }
  if (!WriteRendererStatus(m_config.stateDirectory + "/renderer.json", status))
    Log(LogLevel::Warning, "renderer.json konnte nicht geschrieben werden");
}

void PlaybackEngine::PollState()
{
  const auto state = ReadPlaybackState(m_config.stateDirectory + "/state.json");
  if (!state)
  {
    if (!m_wroteInitialStatus && !m_haveRevision)
    {
      WriteStatus("idle", SourceError::None);
      m_wroteInitialStatus = true;
    }
    return;
  }
  if (m_haveRevision && state->revision == m_revision)
    return;

  m_haveRevision = true;
  m_revision = state->revision;
  m_pending.reset();
  m_pacer.Invalidate();
  m_skipping = false;

  if (state->source.empty())
  {
    m_source.Close();
    m_mailbox.Clear();
    WriteStatus("idle", SourceError::None);
    Log(LogLevel::Info, "Revision " + std::to_string(m_revision) + ": kein Video");
    return;
  }

  m_source.Close();
  WriteStatus("loading", SourceError::None);
  const SourceError error = m_source.Open(state->source);
  m_mailbox.Clear();
  if (error != SourceError::None)
  {
    WriteStatus("error", error);
    Log(LogLevel::Warning, "Revision " + std::to_string(m_revision) + ": " + state->source + " → " +
                               ErrorCode(error));
    return;
  }

  WriteStatus("playing", SourceError::None);
  const auto& info = m_source.Info();
  Log(LogLevel::Info, "Revision " + std::to_string(m_revision) + ": " + state->source + " (" +
                          std::to_string(info.width) + "x" + std::to_string(info.height) + ", " + info.codec +
                          ")");
}

void PlaybackEngine::ReportSourceError()
{
  const SourceError error = m_source.LastError();
  m_pending.reset();
  m_pacer.Invalidate();
  m_mailbox.Clear();
  WriteStatus("error", error);
  Log(LogLevel::Error, "Revision " + std::to_string(m_revision) + ": Wiedergabe abgebrochen → " +
                           ErrorCode(error));
}

void PlaybackEngine::Run()
{
  Clock::time_point nextPoll = Clock::now();

  while (true)
  {
    bool active = false;
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      if (m_stop)
        break;
      active = m_instances > 0;
    }

    Clock::time_point now = Clock::now();
    if (now >= nextPoll)
    {
      PollState();
      nextPoll = Clock::now() + m_config.pollInterval;
      continue;
    }

    if (!active)
    {
      if (m_pacer.IsAnchored())
        m_pacer.Pause(now);
      WaitUntil(nextPoll);
      continue;
    }
    if (m_pacer.IsPaused())
      m_pacer.Resume(now);

    if (!m_source.IsOpen())
    {
      WaitUntil(nextPoll);
      continue;
    }

    if (!m_pending)
    {
      auto frame = std::make_shared<VideoFrame>();
      if (!m_source.NextFrame(*frame))
      {
        ReportSourceError();
        continue;
      }
      m_pending = std::move(frame);
      if (!m_pacer.IsAnchored())
        m_pacer.Reset(m_pending->mediaSeconds, Clock::now());
    }

    now = Clock::now();
    const double frameSeconds = m_source.Info().frameSeconds;
    double lateness = m_pacer.Lateness(m_pending->mediaSeconds, now);
    if (lateness > kResyncSeconds)
    {
      m_pacer.Reset(m_pending->mediaSeconds, now);
      lateness = 0.0;
    }
    if (lateness > kDropAfterFrames * frameSeconds)
    {
      if (!m_skipping)
      {
        m_source.SetSkipNonReference(true);
        m_skipping = true;
      }
      m_pending.reset();
      continue;
    }
    if (m_skipping && lateness <= kCatchUpFrames * frameSeconds)
    {
      m_source.SetSkipNonReference(false);
      m_skipping = false;
    }

    const Clock::time_point due = m_pacer.DueTime(m_pending->mediaSeconds);
    if (due > now)
    {
      WaitUntil(std::min(due, nextPoll));
      continue;
    }

    m_mailbox.Put(std::move(m_pending));
    m_pending.reset();
  }
}

} // namespace partyvideo
```

- [ ] **Step 6: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/test-cpp-in-container.sh`
Expected: `100% tests passed, 0 tests failed out of 56`, keine Warnungen.

- [ ] **Step 7: Stabilität prüfen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh bash -c 'ctest --test-dir build/amd64-tests -R PlaybackEngine --repeat until-fail:5 -j4 --output-on-failure'`
Expected: alle Wiederholungen bestanden. Scheitert ein Test sporadisch, Ursache (Zeitannahme im Test oder Fehler in der Engine) klären und im Bericht nennen, nicht Zeitgrenzen blind erhöhen.

- [ ] **Step 8: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 8: Build-Gate auf das ausgelieferte Zip

**Files:**
- Create: `scripts/check_zip.sh`, `tests/build/test_check_zip.sh`
- Modify: `scripts/build-in-container.sh`, `test.sh`

**Interfaces:**
- Consumes: `scripts/check_elf.sh` (Plan 1)
- Produces: `scripts/check_zip.sh <addon.zip>` → Exit 0 nur, wenn im Zip `visualization.partyvideo/addon.xml` existiert, die in `library_linux` genannte Datei als echte Datei (kein Symlink) im Zip liegt und `check_elf.sh` besteht, und kein `__pycache__`/`*.pyc` enthalten ist; sonst Exit 1 mit Meldung auf stdout. `build-in-container.sh` prüft damit das Zip in `dist/`.

- [ ] **Step 1: Failing Test schreiben – `tests/build/test_check_zip.sh`**

```bash
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
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/tests/build/test_check_zip.sh`

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh tests/build/test_check_zip.sh`
Expected: `FAIL gültiges Zip (erwartet ok, erhalten fail)`, Exit ≠ 0.

- [ ] **Step 3: `scripts/check_zip.sh` anlegen**

```bash
#!/usr/bin/env bash
# Prüft das ausgelieferte Addon-Zip: addon.xml vorhanden, library_linux zeigt auf eine echte Datei
# im Zip, diese besteht check_elf.sh, und es ist kein Python-Cache enthalten.
set -euo pipefail

zip="${1:?Aufruf: check_zip.sh <addon.zip>}"
id=visualization.partyvideo

if [[ ! -f "$zip" ]]; then
  echo "Zip nicht gefunden: $zip"
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
unzip -q "$zip" -d "$tmp"

xml="$tmp/$id/addon.xml"
if [[ ! -f "$xml" ]]; then
  echo "addon.xml fehlt im Zip"
  exit 1
fi

lib="$(grep -o -m1 'library_linux="[^"]*"' "$xml" | sed 's/^library_linux="//; s/"$//' || true)"
if [[ -z "$lib" ]]; then
  echo "library_linux fehlt in addon.xml"
  exit 1
fi

so="$tmp/$id/$lib"
if [[ -L "$so" || ! -f "$so" ]]; then
  echo "Bibliothek $lib fehlt im Zip oder ist ein Symlink"
  exit 1
fi

if [[ -n "$(find "$tmp" \( -name __pycache__ -o -name '*.pyc' \) -print -quit)" ]]; then
  echo "Python-Cache im Zip"
  exit 1
fi

"$(dirname "$0")/check_elf.sh" "$so"
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/check_zip.sh`

- [ ] **Step 4: Test laufen lassen, er muss bestehen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh tests/build/test_check_zip.sh`
Expected: sieben `PASS`-Zeilen, `7 bestanden, 0 fehlgeschlagen`.

- [ ] **Step 5: `scripts/build-in-container.sh` anpassen**

Den Block ab `so="$(find …` bis zum Dateiende ersetzen durch:

```bash
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
```

- [ ] **Step 6: `test.sh` erweitern**

Nach der Zeile `scripts/in-container.sh tests/build/test_check_elf.sh` einfügen:

```bash
scripts/in-container.sh tests/build/test_check_zip.sh
```

- [ ] **Step 7: Build und Tests laufen lassen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./build.sh && ./test.sh`
Expected: Build Exit 0 ohne Ausgabe von `check_zip.sh`/`check_elf.sh`; `test.sh` mit `5 bestanden`, `7 bestanden` und allen C++-Tests grün. (Das Zip ist noch die Stufe-0-Fassung.)

- [ ] **Step 8: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 9: GL-Renderer und Kodi-Anbindung

**Files:**
- Create: `src/gl/YuvRenderer.h`, `src/gl/YuvRenderer.cpp`
- Modify (vollständig ersetzen): `src/addon.h`, `src/addon.cpp`, `CMakeLists.txt`
- Modify: `visualization.partyvideo/addon.xml.in` (Version, Beschreibung)

**Interfaces:**
- Consumes: `PlaybackEngine`, `EngineConfig`, `LogLevel` (Task 7); `FrameMailbox`, `MailboxRead`, `VideoFrame` (Task 4); `MakeYuvToRgb` (Task 2); `FitVideo` (Task 1); `scripts/check_zip.sh` im Build (Task 8)
- Produces:
  - `src/gl/YuvRenderer.h`, `namespace partyvideo`:
    ```cpp
    class YuvRenderer
    {
    public:
      ~YuvRenderer();
      bool Init();                         // idempotent; false bei Shader-/Link-Fehler, Grund in LastError()
      void Upload(const VideoFrame& frame);
      void ClearFrame();                   // nächstes Draw() zeigt nur Schwarz
      void Draw();                         // Schwarz löschen, Video mit Letterbox zeichnen
      const std::string& LastError() const;
    };
    ```
    Alle Methoden und der Destruktor nur im Kodi-GUI-Thread mit aktivem GL-Kontext (dort ruft Kodi `Render()` und zerstört die Instanz, geprüft im Kodi-21.3-Quellcode).
  - `src/addon.cpp`: prozessweite `PlaybackEngine` (erste Instanz erzeugt sie mit `kodi::addon::GetUserPath()`), Logmeldungen des Workers über eine Warteschlange, die nur Kodi-Threads mit gültiger Addon-Schnittstelle leeren
  - `dist/visualization.partyvideo-0.2.0.zip`

Hinweis zur Log-Warteschlange: `ADDON_Create` setzt `CPrivateBase::m_interface` bei jeder Instanz neu auf eine von Kodi verwaltete Struktur. Zwischen zwei Songs gibt es keine gültige Schnittstelle; ein direkter `kodi::Log`-Aufruf aus dem Worker-Thread wäre dann ein Zugriff auf freigegebenen Speicher.

GL- und Kodi-Code hat keine automatischen Tests; geprüft wird er durch Build, Review und Stufe 1 (Task 10).

- [ ] **Step 1: `src/gl/YuvRenderer.h` anlegen**

```cpp
#pragma once

#include "core/VideoFrame.h"

#include <array>
#include <string>

#include <GLES3/gl3.h>

namespace partyvideo
{

// Zeichnet YUV-4:2:0-Bilder mit OpenGL ES 3.0 in den aktuellen Viewport (mit Letterbox).
// Alle Methoden und der Destruktor nur im GL-Thread mit aktivem Kontext aufrufen.
// Stellt den vorgefundenen GL-Zustand nach Upload() und Draw() wieder her.
class YuvRenderer
{
public:
  YuvRenderer() = default;
  ~YuvRenderer();
  YuvRenderer(const YuvRenderer&) = delete;
  YuvRenderer& operator=(const YuvRenderer&) = delete;

  bool Init();
  void Upload(const VideoFrame& frame);
  void ClearFrame() { m_hasFrame = false; }
  void Draw();
  const std::string& LastError() const { return m_lastError; }

private:
  GLuint CompileShader(GLenum type, const char* source);

  GLuint m_program = 0;
  GLuint m_vertexArray = 0;
  GLuint m_vertexBuffer = 0;
  std::array<GLuint, 3> m_textures{0, 0, 0};
  std::array<std::array<int, 2>, 3> m_textureSizes{}; // Breite (= stride), Höhe je Ebene

  GLint m_uniformMatrix = -1;
  GLint m_uniformOffset = -1;
  GLint m_uniformLumaScale = -1;
  GLint m_uniformChromaScale = -1;

  bool m_hasFrame = false;
  int m_width = 0;
  int m_height = 0;
  std::array<int, 3> m_strides{0, 0, 0};
  ColorMatrix m_matrix = ColorMatrix::Bt709;
  bool m_fullRange = false;
  int m_sarNum = 1;
  int m_sarDen = 1;

  std::string m_lastError;
};

} // namespace partyvideo
```

- [ ] **Step 2: `src/gl/YuvRenderer.cpp` anlegen**

```cpp
#include "gl/YuvRenderer.h"

#include "core/ColorConversion.h"
#include "core/Letterbox.h"

namespace partyvideo
{

namespace
{

const char* const kVertexShader = R"(#version 300 es
layout(location = 0) in vec2 aPosition;
layout(location = 1) in vec2 aTexCoord;
out vec2 vTexCoord;
void main()
{
  vTexCoord = aTexCoord;
  gl_Position = vec4(aPosition, 0.0, 1.0);
}
)";

const char* const kFragmentShader = R"(#version 300 es
precision highp float;
in vec2 vTexCoord;
out vec4 fragColor;
uniform sampler2D uTextureY;
uniform sampler2D uTextureU;
uniform sampler2D uTextureV;
uniform mat3 uYuvToRgb;
uniform vec3 uOffset;
uniform vec2 uLumaScale;
uniform vec2 uChromaScale;
void main()
{
  vec3 yuv = vec3(texture(uTextureY, vTexCoord * uLumaScale).r,
                  texture(uTextureU, vTexCoord * uChromaScale).r,
                  texture(uTextureV, vTexCoord * uChromaScale).r);
  fragColor = vec4(clamp(uYuvToRgb * (yuv - uOffset), 0.0, 1.0), 1.0);
}
)";

// Sichert den GL-Zustand, den Kodi um Render() herum nicht selbst wiederherstellt, und setzt ihn zurück.
class GlStateGuard
{
public:
  GlStateGuard()
  {
    glGetIntegerv(GL_CURRENT_PROGRAM, &m_program);
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &m_vertexArray);
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &m_arrayBuffer);
    glGetIntegerv(GL_ACTIVE_TEXTURE, &m_activeTexture);
    glGetIntegerv(GL_UNPACK_ALIGNMENT, &m_unpackAlignment);
    glGetFloatv(GL_COLOR_CLEAR_VALUE, m_clearColor.data());
    m_blend = glIsEnabled(GL_BLEND);
    m_depthTest = glIsEnabled(GL_DEPTH_TEST);
    m_cullFace = glIsEnabled(GL_CULL_FACE);
    m_scissorTest = glIsEnabled(GL_SCISSOR_TEST);
    for (int unit = 0; unit < 3; ++unit)
    {
      glActiveTexture(GL_TEXTURE0 + unit);
      glGetIntegerv(GL_TEXTURE_BINDING_2D, &m_textures[unit]);
    }
    glDisable(GL_BLEND);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
  }

  ~GlStateGuard()
  {
    for (int unit = 2; unit >= 0; --unit)
    {
      glActiveTexture(GL_TEXTURE0 + unit);
      glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(m_textures[unit]));
    }
    glActiveTexture(static_cast<GLenum>(m_activeTexture));
    glPixelStorei(GL_UNPACK_ALIGNMENT, m_unpackAlignment);
    glBindBuffer(GL_ARRAY_BUFFER, static_cast<GLuint>(m_arrayBuffer));
    glBindVertexArray(static_cast<GLuint>(m_vertexArray));
    glUseProgram(static_cast<GLuint>(m_program));
    glClearColor(m_clearColor[0], m_clearColor[1], m_clearColor[2], m_clearColor[3]);
    SetEnabled(GL_BLEND, m_blend);
    SetEnabled(GL_DEPTH_TEST, m_depthTest);
    SetEnabled(GL_CULL_FACE, m_cullFace);
    SetEnabled(GL_SCISSOR_TEST, m_scissorTest);
  }

  GlStateGuard(const GlStateGuard&) = delete;
  GlStateGuard& operator=(const GlStateGuard&) = delete;

private:
  static void SetEnabled(GLenum capability, GLboolean enabled)
  {
    if (enabled)
      glEnable(capability);
    else
      glDisable(capability);
  }

  GLint m_program = 0;
  GLint m_vertexArray = 0;
  GLint m_arrayBuffer = 0;
  GLint m_activeTexture = GL_TEXTURE0;
  GLint m_unpackAlignment = 4;
  std::array<GLfloat, 4> m_clearColor{};
  GLboolean m_blend = GL_FALSE;
  GLboolean m_depthTest = GL_FALSE;
  GLboolean m_cullFace = GL_FALSE;
  GLboolean m_scissorTest = GL_FALSE;
  std::array<GLint, 3> m_textures{};
};

} // namespace

YuvRenderer::~YuvRenderer()
{
  if (m_textures[0] != 0)
    glDeleteTextures(3, m_textures.data());
  if (m_vertexBuffer != 0)
    glDeleteBuffers(1, &m_vertexBuffer);
  if (m_vertexArray != 0)
    glDeleteVertexArrays(1, &m_vertexArray);
  if (m_program != 0)
    glDeleteProgram(m_program);
}

GLuint YuvRenderer::CompileShader(GLenum type, const char* source)
{
  GLuint shader = glCreateShader(type);
  glShaderSource(shader, 1, &source, nullptr);
  glCompileShader(shader);
  GLint ok = GL_FALSE;
  glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
  if (ok != GL_TRUE)
  {
    std::array<char, 1024> log{};
    glGetShaderInfoLog(shader, static_cast<GLsizei>(log.size()), nullptr, log.data());
    m_lastError = std::string("Shader-Fehler: ") + log.data();
    glDeleteShader(shader);
    return 0;
  }
  return shader;
}

bool YuvRenderer::Init()
{
  if (m_program != 0)
    return true;

  const GLuint vertex = CompileShader(GL_VERTEX_SHADER, kVertexShader);
  if (vertex == 0)
    return false;
  const GLuint fragment = CompileShader(GL_FRAGMENT_SHADER, kFragmentShader);
  if (fragment == 0)
  {
    glDeleteShader(vertex);
    return false;
  }

  GLuint program = glCreateProgram();
  glAttachShader(program, vertex);
  glAttachShader(program, fragment);
  glLinkProgram(program);
  glDeleteShader(vertex);
  glDeleteShader(fragment);

  GLint ok = GL_FALSE;
  glGetProgramiv(program, GL_LINK_STATUS, &ok);
  if (ok != GL_TRUE)
  {
    std::array<char, 1024> log{};
    glGetProgramInfoLog(program, static_cast<GLsizei>(log.size()), nullptr, log.data());
    m_lastError = std::string("Link-Fehler: ") + log.data();
    glDeleteProgram(program);
    return false;
  }

  GlStateGuard guard;
  m_program = program;
  glUseProgram(m_program);
  glUniform1i(glGetUniformLocation(m_program, "uTextureY"), 0);
  glUniform1i(glGetUniformLocation(m_program, "uTextureU"), 1);
  glUniform1i(glGetUniformLocation(m_program, "uTextureV"), 2);
  m_uniformMatrix = glGetUniformLocation(m_program, "uYuvToRgb");
  m_uniformOffset = glGetUniformLocation(m_program, "uOffset");
  m_uniformLumaScale = glGetUniformLocation(m_program, "uLumaScale");
  m_uniformChromaScale = glGetUniformLocation(m_program, "uChromaScale");

  glGenVertexArrays(1, &m_vertexArray);
  glGenBuffers(1, &m_vertexBuffer);
  glBindVertexArray(m_vertexArray);
  glBindBuffer(GL_ARRAY_BUFFER, m_vertexBuffer);
  glBufferData(GL_ARRAY_BUFFER, 16 * sizeof(GLfloat), nullptr, GL_DYNAMIC_DRAW);
  glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), nullptr);
  glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat),
                        reinterpret_cast<const void*>(2 * sizeof(GLfloat)));
  glEnableVertexAttribArray(0);
  glEnableVertexAttribArray(1);

  glGenTextures(3, m_textures.data());
  for (int plane = 0; plane < 3; ++plane)
  {
    glActiveTexture(GL_TEXTURE0 + plane);
    glBindTexture(GL_TEXTURE_2D, m_textures[plane]);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  }
  return true;
}

void YuvRenderer::Upload(const VideoFrame& frame)
{
  if (m_program == 0 || frame.width <= 0 || frame.height <= 0)
    return;

  const std::array<int, 3> heights{frame.height, ChromaHeight(frame.height), ChromaHeight(frame.height)};
  const std::array<int, 3> widths{frame.width, ChromaWidth(frame.width), ChromaWidth(frame.width)};
  for (int plane = 0; plane < 3; ++plane)
  {
    const size_t needed = static_cast<size_t>(frame.strides[plane]) * heights[plane];
    if (frame.strides[plane] < widths[plane] || frame.planes[plane].size() < needed)
      return; // unvollständiges Bild nicht hochladen
  }

  GlStateGuard guard;
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
  for (int plane = 0; plane < 3; ++plane)
  {
    glActiveTexture(GL_TEXTURE0 + plane);
    glBindTexture(GL_TEXTURE_2D, m_textures[plane]);
    const std::array<int, 2> size{frame.strides[plane], heights[plane]};
    if (m_textureSizes[plane] != size)
    {
      glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, size[0], size[1], 0, GL_RED, GL_UNSIGNED_BYTE,
                   frame.planes[plane].data());
      m_textureSizes[plane] = size;
    }
    else
    {
      glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, size[0], size[1], GL_RED, GL_UNSIGNED_BYTE,
                      frame.planes[plane].data());
    }
  }

  m_hasFrame = true;
  m_width = frame.width;
  m_height = frame.height;
  m_strides = frame.strides;
  m_matrix = frame.matrix;
  m_fullRange = frame.fullRange;
  m_sarNum = frame.sarNum;
  m_sarDen = frame.sarDen;
}

void YuvRenderer::Draw()
{
  GlStateGuard guard;

  // Kodi hat Viewport und Scissor-Box auf die Visualisierungsfläche gesetzt.
  glEnable(GL_SCISSOR_TEST);
  glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT);

  if (m_program == 0 || !m_hasFrame)
    return;

  std::array<GLint, 4> viewport{};
  glGetIntegerv(GL_VIEWPORT, viewport.data());
  const NdcRect rect = FitVideo(viewport[2], viewport[3], m_width, m_height, m_sarNum, m_sarDen);

  // x, y, u, v – Texturzeile 0 ist die oberste Bildzeile.
  const std::array<GLfloat, 16> vertices{
      rect.left,  rect.bottom, 0.0f, 1.0f, //
      rect.right, rect.bottom, 1.0f, 1.0f, //
      rect.left,  rect.top,    0.0f, 0.0f, //
      rect.right, rect.top,    1.0f, 0.0f, //
  };

  const YuvToRgb conversion = MakeYuvToRgb(m_matrix, m_fullRange);

  glUseProgram(m_program);
  glUniformMatrix3fv(m_uniformMatrix, 1, GL_FALSE, conversion.matrix.data());
  glUniform3fv(m_uniformOffset, 1, conversion.offset.data());
  glUniform2f(m_uniformLumaScale, static_cast<GLfloat>(m_width) / m_strides[0], 1.0f);
  glUniform2f(m_uniformChromaScale, static_cast<GLfloat>(ChromaWidth(m_width)) / m_strides[1], 1.0f);

  glBindVertexArray(m_vertexArray);
  glBindBuffer(GL_ARRAY_BUFFER, m_vertexBuffer);
  glBufferSubData(GL_ARRAY_BUFFER, 0, static_cast<GLsizeiptr>(sizeof(vertices)), vertices.data());

  for (int plane = 0; plane < 3; ++plane)
  {
    glActiveTexture(GL_TEXTURE0 + plane);
    glBindTexture(GL_TEXTURE_2D, m_textures[plane]);
  }
  glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
}

} // namespace partyvideo
```

- [ ] **Step 3: `src/addon.h` ersetzen**

```cpp
#pragma once

#include <kodi/addon-instance/Visualization.h>

#include <cstdint>
#include <memory>
#include <string>

namespace partyvideo
{
class PlaybackEngine;
class YuvRenderer;
} // namespace partyvideo

// Kodi-Visualisierung: zeigt das Video der prozessweiten PlaybackEngine.
// Kodi erzeugt diese Instanz bei jedem Songwechsel neu; Decoder und Wiedergabeposition bleiben in der Engine.
class ATTR_DLL_LOCAL CPartyVideo : public kodi::addon::CAddonBase,
                                   public kodi::addon::CInstanceVisualization
{
public:
  CPartyVideo();
  ~CPartyVideo() override;

  bool Start(int channels, int samplesPerSec, int bitsPerSample, const std::string& songName) override;
  void Stop() override;
  bool IsDirty() override;
  void Render() override;

private:
  partyvideo::PlaybackEngine& m_engine;
  std::unique_ptr<partyvideo::YuvRenderer> m_renderer; // GL-Objekte gehören zur Instanz
  bool m_rendererFailed = false;
  bool m_attached = false;
  bool m_needsDraw = true;
  uint64_t m_seenSequence = 0;
};
```

- [ ] **Step 4: `src/addon.cpp` ersetzen**

```cpp
#include "addon.h"

#include "core/PlaybackEngine.h"
#include "gl/YuvRenderer.h"

#include <deque>
#include <mutex>
#include <utility>

namespace
{

constexpr const char* kPrefix = "[visualization.partyvideo] ";
constexpr size_t kMaxQueuedMessages = 200;

ADDON_LOG ToKodiLevel(partyvideo::LogLevel level)
{
  switch (level)
  {
    case partyvideo::LogLevel::Debug:
      return ADDON_LOG_DEBUG;
    case partyvideo::LogLevel::Info:
      return ADDON_LOG_INFO;
    case partyvideo::LogLevel::Warning:
      return ADDON_LOG_WARNING;
    case partyvideo::LogLevel::Error:
      return ADDON_LOG_ERROR;
  }
  return ADDON_LOG_INFO;
}

// Meldungen des Worker-Threads warten hier, bis ein Kodi-Thread sie ausgibt. Zwischen zwei Songs
// gibt es keine gültige Addon-Schnittstelle, deshalb darf der Worker kodi::Log nicht selbst aufrufen.
class LogQueue
{
public:
  void Push(partyvideo::LogLevel level, std::string text)
  {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (m_messages.size() >= kMaxQueuedMessages)
      m_messages.pop_front();
    m_messages.push_back({level, std::move(text)});
  }

  // Nur aus Kodi-Aufrufen (Konstruktor, Start, Stop, Render, Destruktor) heraus aufrufen.
  void Flush()
  {
    std::deque<Message> messages;
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      messages.swap(m_messages);
    }
    for (const auto& message : messages)
      kodi::Log(ToKodiLevel(message.level), "%s%s", kPrefix, message.text.c_str());
  }

private:
  struct Message
  {
    partyvideo::LogLevel level;
    std::string text;
  };

  std::mutex m_mutex;
  std::deque<Message> m_messages;
};

LogQueue& Logs()
{
  static LogQueue queue;
  return queue;
}

std::string StateDirectory()
{
  std::string path = kodi::addon::GetUserPath();
  while (path.size() > 1 && path.back() == '/')
    path.pop_back();
  return path;
}

// Prozessweit: überlebt die Kodi-Instanzen (Stufe-0-Befund: neue Instanz pro Song, .so bleibt geladen).
partyvideo::PlaybackEngine& SharedEngine()
{
  Logs(); // vor der Engine anlegen, damit die Warteschlange erst nach ihr zerstört wird
  static partyvideo::PlaybackEngine engine([] {
    partyvideo::EngineConfig config;
    config.stateDirectory = StateDirectory();
    config.log = [](partyvideo::LogLevel level, const std::string& text) { Logs().Push(level, text); };
    return config;
  }());
  return engine;
}

} // namespace

CPartyVideo::CPartyVideo() : m_engine(SharedEngine())
{
  Logs().Flush();
}

CPartyVideo::~CPartyVideo()
{
  if (m_attached)
    m_engine.DetachInstance();
  Logs().Flush();
}

bool CPartyVideo::Start(int, int, int, const std::string&)
{
  if (!m_attached)
  {
    m_engine.AttachInstance();
    m_attached = true;
  }
  m_needsDraw = true;
  Logs().Flush();
  return true;
}

void CPartyVideo::Stop()
{
  if (m_attached)
  {
    m_engine.DetachInstance();
    m_attached = false;
  }
  Logs().Flush();
}

bool CPartyVideo::IsDirty()
{
  return m_needsDraw || m_engine.Mailbox().Sequence() != m_seenSequence;
}

void CPartyVideo::Render()
{
  Logs().Flush();

  if (!m_renderer && !m_rendererFailed)
  {
    auto renderer = std::make_unique<partyvideo::YuvRenderer>();
    if (renderer->Init())
    {
      m_renderer = std::move(renderer);
    }
    else
    {
      m_rendererFailed = true;
      kodi::Log(ADDON_LOG_ERROR, "%sGL-Initialisierung fehlgeschlagen: %s", kPrefix,
                renderer->LastError().c_str());
    }
  }
  if (!m_renderer)
    return;

  const auto read = m_engine.Mailbox().ReadIfChanged(m_seenSequence);
  if (read.changed)
  {
    if (read.frame)
      m_renderer->Upload(*read.frame);
    else
      m_renderer->ClearFrame();
  }
  m_renderer->Draw();
  m_needsDraw = false;
}

ADDONCREATOR(CPartyVideo)
```

- [ ] **Step 5: `CMakeLists.txt` ersetzen**

```cmake
cmake_minimum_required(VERSION 3.18)
project(visualization.partyvideo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Kodi REQUIRED)
find_package(PkgConfig REQUIRED)
find_package(Threads REQUIRED)
pkg_check_modules(FFMPEG REQUIRED libavformat>=60 libavcodec>=60 libavutil>=58 libswscale>=7)

find_path(GLES3_INCLUDE_DIR GLES3/gl3.h REQUIRED)
find_library(GLESV2_LIBRARY GLESv2 REQUIRED)

include_directories(${KODI_INCLUDE_DIR}/..
                    ${FFMPEG_INCLUDE_DIRS}
                    ${GLES3_INCLUDE_DIR}
                    ${PROJECT_SOURCE_DIR}/src)
include_directories(SYSTEM ${PROJECT_SOURCE_DIR}/third_party)

set(PARTYVIDEO_SOURCES src/addon.cpp
                       src/core/ColorConversion.cpp
                       src/core/FrameMailbox.cpp
                       src/core/FramePacer.cpp
                       src/core/Letterbox.cpp
                       src/core/PlaybackEngine.cpp
                       src/core/StateFiles.cpp
                       src/core/VideoSource.cpp
                       src/gl/YuvRenderer.cpp)

set(PARTYVIDEO_HEADERS src/addon.h
                       src/core/ColorConversion.h
                       src/core/FrameMailbox.h
                       src/core/FramePacer.h
                       src/core/Letterbox.h
                       src/core/PlaybackEngine.h
                       src/core/StateFiles.h
                       src/core/VideoFrame.h
                       src/core/VideoSource.h
                       src/gl/YuvRenderer.h)

set(DEPLIBS ${FFMPEG_LINK_LIBRARIES} ${GLESV2_LIBRARY} Threads::Threads)

build_addon(visualization.partyvideo PARTYVIDEO DEPLIBS)

include(CPack)
```

- [ ] **Step 6: `visualization.partyvideo/addon.xml.in` anpassen**

`version="0.1.0"` → `version="0.2.0"`. Die beiden `<description>`-Zeilen ersetzen durch:

```xml
    <description lang="de_DE">Stufe 1: spielt das in state.json eingetragene Video stumm in Endlosschleife als Musikvisualisierung.</description>
    <description lang="en_GB">Stage 1: plays the video named in state.json muted and looped as music visualization.</description>
```

- [ ] **Step 7: Addon bauen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./build.sh`
Expected: Exit 0, keine Ausgabe von `check_zip.sh`, `unzip -l` listet `visualization.partyvideo/visualization.partyvideo.so.0.2.0`; `dist/` enthält nur `visualization.partyvideo-0.2.0.zip`. Compiler-Warnungen aus eigenen Dateien (`src/…`) im Bericht aufführen.

- [ ] **Step 8: Symbolversionen und Abhängigkeiten dokumentieren**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh bash -c 't=$(mktemp -d); unzip -q dist/visualization.partyvideo-0.2.0.zip -d "$t"; so="$t/visualization.partyvideo/visualization.partyvideo.so.0.2.0"; aarch64-linux-gnu-readelf -d "$so" | grep NEEDED; aarch64-linux-gnu-readelf -V "$so" | grep -oE "(GLIBC|GLIBCXX|CXXABI)_[0-9.]+" | sort -Vu | tail -6'`
Expected: `NEEDED` nur aus der erlaubten Liste; höchste Versionen ≤ `GLIBC_2.38`, ≤ `GLIBCXX_3.4.32`. Ausgabe in den Bericht übernehmen.

- [ ] **Step 9: Alle Tests laufen lassen**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./test.sh`
Expected: ruff grün, `5 bestanden`, `7 bestanden`, `100% tests passed … out of 56`.

- [ ] **Step 10: Stand prüfen, nicht committen**

Run: `git -C /home/tesla/githubprojects/visualization.partyvideo status --short`

---

### Task 10: Stufe 1 – Testvideos, Checkliste, Test auf dem Pi

**Files:**
- Create: `scripts/make-testvideos.sh`, `scripts/pi-set-state.sh`, `docs/stufe-1-test.md`
- Create (nach dem Pi-Test): `docs/superpowers/results/stufe-1.md`

**Interfaces:**
- Consumes: `dist/visualization.partyvideo-0.2.0.zip` (Task 9); Formate `state.json`/`renderer.json` (Spec §5.1/§5.2)
- Produces:
  - `scripts/in-container.sh scripts/make-testvideos.sh` → `dist/testvideos/partyvideo-1080p30.mp4`, `partyvideo-720p30.mp4`, `partyvideo-farbbalken-1080p.mp4`
  - `scripts/pi-set-state.sh <revision> <quelle>` (Host) → schreibt `state.json` atomar auf den Pi (**schreibender Zugriff, nur nach Freigabe**)
  - Checkliste `docs/stufe-1-test.md`; Ergebnis `docs/superpowers/results/stufe-1.md`

Steps 1–5 führt ein Implementer aus. Steps 6–9 greifen schreibend auf den Pi zu bzw. brauchen den Maintainer am Fernseher; sie macht der Controller erst nach ausdrücklicher Freigabe im Chat.

- [ ] **Step 1: `scripts/make-testvideos.sh` anlegen**

```bash
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

ls -l "$out"
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/make-testvideos.sh && cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh scripts/make-testvideos.sh`
Expected: drei Dateien in `dist/testvideos/`, jeweils einige MB.

- [ ] **Step 2: Testvideos lokal mit der Engine prüfen**

Run:
```bash
cd /home/tesla/githubprojects/visualization.partyvideo && scripts/in-container.sh bash -c '
  for f in dist/testvideos/*.mp4; do
    ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,color_space -of csv=p=0 "$f"
  done'
```
Expected: `h264,1920,1080,yuv420p,bt709,30/1`, `h264,1280,720,yuv420p,bt709,30/1`, `h264,1920,1080,yuv420p,bt709,30/1` (Reihenfolge der Felder wie von ffprobe ausgegeben).

- [ ] **Step 3: `scripts/pi-set-state.sh` anlegen**

```bash
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
```

Run: `chmod +x /home/tesla/githubprojects/visualization.partyvideo/scripts/pi-set-state.sh && bash -n /home/tesla/githubprojects/visualization.partyvideo/scripts/pi-set-state.sh && echo OK`
Expected: `OK` (nur Syntaxprüfung, **nicht** ausführen).

- [ ] **Step 4: `docs/stufe-1-test.md` anlegen**

```markdown
# Stufe-1-Test auf dem Raspberry Pi

Zip: `dist/visualization.partyvideo-0.2.0.zip`, Testvideos: `dist/testvideos/`.
Schreibende Schritte auf dem Pi macht Claude nur nach ausdrücklicher Freigabe im Chat.

## Vorbereitung (Claude, nach Freigabe)

1. Addon-Ordner aus dem Zip nach `/storage/.kodi/addons/visualization.partyvideo/` kopieren
   (ohne die Symlink-Einträge) und Kodi neu starten (`systemctl restart kodi`), weil eine
   bereits geladene `.so` nicht ersetzt wird.
2. Testvideos nach `/storage/videos/partyvideo-test/` kopieren.
3. `scripts/pi-set-state.sh 1 /storage/videos/partyvideo-test/partyvideo-1080p30.mp4`

## Prüfungen (Maintainer am Fernseher)

4. Musik mit mindestens zwei Titeln starten, Visualisierung „Party Video“, Vollbild.
   - [ ] Testbild (bewegte Farbflächen, Zähler) läuft flüssig, Musik ohne Aussetzer
   - [ ] Nach etwa 20 Sekunden beginnt das Video ohne sichtbaren Sprung von vorn
   - [ ] Nach einem Songwechsel läuft das Video an etwa derselben Stelle weiter (kurzer Stillstand ist in Ordnung)
5. Claude setzt Revision 2 (720p).
   - [ ] Wechsel auf das 720p-Testbild innerhalb einer Sekunde, flüssig, bildschirmfüllend
6. Claude setzt Revision 3 (Farbbalken).
   - [ ] Balken von links: Grau/Weiß, Gelb, Cyan, Grün, Magenta, Rot, Blau – keine vertauschten oder blassen Farben
7. Claude setzt Revision 4 (leere Quelle).
   - [ ] Schwarzes Bild, Musik läuft weiter
8. Claude setzt Revision 5 (nicht vorhandene Datei).
   - [ ] Schwarzes Bild, kein Absturz
9. Claude setzt Revision 6 (wieder 1080p).
   - [ ] Video läuft wieder

## Rückmeldung

10. Kodi vor der Rückmeldung nicht neu starten; Checklistenstand im Chat nennen.
    Claude liest `renderer.json`, `kodi.log` und die CPU-Last (`top`) nur lesend aus.
```

- [ ] **Step 5: Abschlussprüfung und Übergabe**

Run: `cd /home/tesla/githubprojects/visualization.partyvideo && ./test.sh && ./build.sh && ls -l dist/ dist/testvideos/`
Expected: alles grün; `dist/visualization.partyvideo-0.2.0.zip` und drei Testvideos vorhanden. Übergabe an den Controller; nicht committen.

- [ ] **Step 6 (Controller, nach Freigabe): Addon und Testvideos auf den Pi bringen**

Run:
```bash
cd /home/tesla/githubprojects/visualization.partyvideo \
 && t="$(mktemp -d)" && unzip -q dist/visualization.partyvideo-0.2.0.zip -d "$t" \
 && tar -C "$t" -cf - --exclude='visualization.partyvideo.so' --exclude='visualization.partyvideo.so.21.3' visualization.partyvideo \
  | ssh -o BatchMode=yes root@192.168.178.10 'rm -rf /storage/.kodi/addons/visualization.partyvideo && tar -C /storage/.kodi/addons -xf - && chown -R root:root /storage/.kodi/addons/visualization.partyvideo' \
 && ssh -o BatchMode=yes root@192.168.178.10 'mkdir -p /storage/videos/partyvideo-test' \
 && scp -q dist/testvideos/*.mp4 root@192.168.178.10:/storage/videos/partyvideo-test/ \
 && ssh -o BatchMode=yes root@192.168.178.10 'systemctl restart kodi'
```
Expected: kein Fehler. Nach etwa 20 Sekunden (Kodi-Neustart) lesend prüfen:
```bash
ssh -o BatchMode=yes root@192.168.178.10 python3 - <<'PY'
import base64, json, re, urllib.request
xml = open("/storage/.kodi/userdata/guisettings.xml", encoding="utf-8").read()
user = re.search(r'id="services\.webserverusername"[^>]*>([^<]*)', xml).group(1)
pw = re.search(r'id="services\.webserverpassword"[^>]*>([^<]*)', xml).group(1)
body = {"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddonDetails",
        "params": {"addonid": "visualization.partyvideo", "properties": ["version", "enabled"]}}
req = urllib.request.Request("http://127.0.0.1:8080/jsonrpc", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()})
print(json.load(urllib.request.urlopen(req, timeout=10))["result"])
PY
```
Erwartet: `version` `0.2.0`, `enabled` `True`. Ist das Addon deaktiviert, nach Freigabe mit `Addons.SetAddonEnabled` aktivieren (wie bei der Stufe-0-Installation).

- [ ] **Step 7 (Controller, nach Freigabe): Revisionen während des Tests setzen**

Nach jeweiliger Rückmeldung des Maintainers:
```bash
scripts/pi-set-state.sh 1 /storage/videos/partyvideo-test/partyvideo-1080p30.mp4
scripts/pi-set-state.sh 2 /storage/videos/partyvideo-test/partyvideo-720p30.mp4
scripts/pi-set-state.sh 3 /storage/videos/partyvideo-test/partyvideo-farbbalken-1080p.mp4
scripts/pi-set-state.sh 4 ""
scripts/pi-set-state.sh 5 /storage/videos/partyvideo-test/gibt-es-nicht.mp4
scripts/pi-set-state.sh 6 /storage/videos/partyvideo-test/partyvideo-1080p30.mp4
```
Nach jeder Revision lesend prüfen: `ssh root@192.168.178.10 'cat /storage/.kodi/userdata/addon_data/visualization.partyvideo/renderer.json'` – erwartet `playing` (1, 2, 3, 6), `idle` (4), `error`/`file_not_found` (5).

- [ ] **Step 8 (Controller, lesend): Last und Log auswerten**

Während Revision 1 läuft:
```bash
ssh -o BatchMode=yes root@192.168.178.10 'top -b -n 2 -d 3 | grep -E "^ *PID|kodi" | tail -3; grep -nE "partyvideo" /storage/.kodi/temp/kodi.log | tail -40'
```
Erwartet: `kodi.bin` deutlich unter 400 % (vier Kerne); Logzeilen `Revision N: …` passend zu den gesetzten Revisionen, keine `GL-Initialisierung fehlgeschlagen`.

- [ ] **Step 9 (Controller): Ergebnis festhalten**

`docs/superpowers/results/stufe-1.md` anlegen mit: Datum, Checklistenstand, `renderer.json` je Revision, CPU-Last bei 1080p und 720p, relevante Logzeilen, Bewertung von R2 (1080p-Leistung) und R6 (Fortsetzen nach Songwechsel), Folgerungen für Plan 3 (z. B. Standard für `max_height`). Nicht committen.
