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
