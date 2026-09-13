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
