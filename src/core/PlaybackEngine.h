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
