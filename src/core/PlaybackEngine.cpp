#include "core/PlaybackEngine.h"

#include "core/StateFiles.h"
#include "core/FrameDropPolicy.h"

#include <algorithm>
#include <utility>

namespace partyvideo
{

namespace
{

constexpr int kMaxPixels = 1920 * 1080;


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
  FrameDropPolicy dropPolicy;
  int64_t policyRevision = m_revision;

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
      if (policyRevision != m_revision)
      {
        dropPolicy.Reset();
        policyRevision = m_revision;
      }
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
      const auto decodeStarted = Clock::now();
      if (!m_source.NextFrame(*frame))
      {
        ReportSourceError();
        continue;
      }
      dropPolicy.ObserveDecode(
          std::chrono::duration<double>(Clock::now() - decodeStarted).count(),
          m_source.Info().frameSeconds);
      m_pending = std::move(frame);
      if (!m_pacer.IsAnchored())
        m_pacer.Reset(m_pending->mediaSeconds, Clock::now());
    }

    now = Clock::now();
    const double frameSeconds = m_source.Info().frameSeconds;
    const auto decision = dropPolicy.Evaluate(
        m_pacer.Lateness(m_pending->mediaSeconds, now), frameSeconds);
    if (decision.resync)
      m_pacer.Reset(m_pending->mediaSeconds, now);
    if (decision.skipping != m_skipping)
    {
      m_source.SetSkipNonReference(decision.skipping);
      m_skipping = decision.skipping;
    }
    if (decision.drop)
    {
      m_pending.reset();
      continue;
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
