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
