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

COPY aarch64-toolchain.cmake /opt/toolchains/aarch64.cmake
