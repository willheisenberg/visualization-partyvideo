#pragma once

#include <chrono>

namespace partyvideo
{

// Ordnet Medienzeiten (Sekunden, über Schleifen hinweg fortlaufend) Anzeigezeitpunkten zu.
// Nicht thread-sicher: nur der Worker-Thread der PlaybackEngine benutzt ihn.
class FramePacer
{
public:
  using Clock = std::chrono::steady_clock;

  // mediaSeconds wird zum Zeitpunkt now angezeigt; hebt eine Pause auf.
  void Reset(double mediaSeconds, Clock::time_point now);
  // Anker verwerfen, z. B. beim Quellenwechsel.
  void Invalidate();
  bool IsAnchored() const { return m_anchored; }

  // Anzeigezeitpunkt eines Bildes. Nur sinnvoll, wenn IsAnchored() und nicht pausiert.
  Clock::time_point DueTime(double mediaSeconds) const;
  // Verspätung in Sekunden (> 0: zu spät). Während einer Pause 0.
  double Lateness(double mediaSeconds, Clock::time_point now) const;

  // Mehrfaches Pause() behält den ersten Pausenbeginn.
  void Pause(Clock::time_point now);
  // Verschiebt den Anker um die Pausendauer, damit das Video an derselben Stelle weiterläuft.
  void Resume(Clock::time_point now);
  bool IsPaused() const { return m_paused; }

private:
  bool m_anchored = false;
  bool m_paused = false;
  double m_anchorMedia = 0.0;
  Clock::time_point m_anchorTime{};
  Clock::time_point m_pausedAt{};
};

} // namespace partyvideo
