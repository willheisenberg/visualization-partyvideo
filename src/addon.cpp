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
  if (!m_attached && !m_rendererFailed)
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
  return m_needsDraw || (!m_rendererFailed && m_engine.Mailbox().Sequence() != m_seenSequence);
}

void CPartyVideo::Render()
{
  Logs().Flush();

  if (!m_renderer && !m_rendererFailed)
  {
    auto renderer = std::make_unique<partyvideo::YuvRenderer>();
    if (!renderer->Init())
    {
      m_rendererFailed = true;
      kodi::Log(ADDON_LOG_ERROR, "%sGL-Initialisierung fehlgeschlagen: %s", kPrefix,
                renderer->LastError().c_str());
      if (m_attached)
      {
        m_engine.DetachInstance();
        m_attached = false;
      }
    }
    m_renderer = std::move(renderer);
  }
  if (!m_renderer)
    return;

  const auto read = m_engine.Mailbox().ReadIfChanged(m_seenSequence);
  if (read.changed && !m_rendererFailed)
  {
    if (read.frame)
    {
      const auto previousError = m_renderer->LastError();
      m_renderer->Upload(*read.frame);
      if (!m_renderer->LastError().empty() && m_renderer->LastError() != previousError)
        kodi::Log(ADDON_LOG_ERROR, "%sVideo-Upload fehlgeschlagen: %s", kPrefix,
                  m_renderer->LastError().c_str());
    }
    else
      m_renderer->ClearFrame();
  }
  m_renderer->Draw();
  m_needsDraw = false;
}

ADDONCREATOR(CPartyVideo)
