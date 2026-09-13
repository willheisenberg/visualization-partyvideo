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

if(NOT FIXTURE_DIR)
  message(FATAL_ERROR "FIXTURE_DIR fehlt (scripts/test-cpp-in-container.sh setzt ihn)")
endif()

set(CORE_SOURCES
  ${REPO_ROOT}/src/core/Letterbox.cpp
  ${REPO_ROOT}/src/core/ColorConversion.cpp
  ${REPO_ROOT}/src/core/FramePacer.cpp
  ${REPO_ROOT}/src/core/FrameMailbox.cpp
  ${REPO_ROOT}/src/core/StateFiles.cpp
  ${REPO_ROOT}/src/core/VideoSource.cpp
  ${REPO_ROOT}/src/core/PlaybackEngine.cpp
)

add_library(partyvideo_core STATIC ${CORE_SOURCES})
target_include_directories(partyvideo_core PUBLIC ${REPO_ROOT}/src)
target_include_directories(partyvideo_core SYSTEM PUBLIC ${REPO_ROOT}/third_party)
target_link_libraries(partyvideo_core PUBLIC PkgConfig::FFMPEG Threads::Threads)

set(TEST_SOURCES
  letterbox_test.cpp
  color_conversion_test.cpp
  frame_pacer_test.cpp
  frame_mailbox_test.cpp
  state_files_test.cpp
  video_source_test.cpp
  playback_engine_test.cpp
)

add_executable(core_tests ${TEST_SOURCES})
target_link_libraries(core_tests PRIVATE partyvideo_core GTest::gtest_main)
target_compile_definitions(core_tests PRIVATE PARTYVIDEO_FIXTURE_DIR="${FIXTURE_DIR}")

enable_testing()
include(GoogleTest)
gtest_discover_tests(core_tests DISCOVERY_TIMEOUT 30)
