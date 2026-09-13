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
