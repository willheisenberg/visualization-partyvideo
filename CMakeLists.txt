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
