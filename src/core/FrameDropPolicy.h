#pragma once

namespace partyvideo
{

// A clock reset is not recovery. Leave overload mode only after two seconds
// of decoded frames demonstrate headroom at the original frame rate.
class FrameDropPolicy
{
public:
  struct Decision
  {
    bool resync;
    bool drop;
    bool skipping;
  };

  void Reset() { m_recoverySeconds = 0.0; m_skipping = false; }

  void ObserveDecode(double decodeSeconds, double frameSeconds)
  {
    if (m_skipping && decodeSeconds <= 0.75 * frameSeconds)
      m_recoverySeconds += frameSeconds;
    else
      m_recoverySeconds = 0.0;
  }

  Decision Evaluate(double lateness, double frameSeconds)
  {
    if (lateness > 2.0 * frameSeconds)
    {
      if (!m_skipping)
        m_recoverySeconds = 0.0;
      m_skipping = true;
    }
    else if (lateness <= 0.5 * frameSeconds && m_recoverySeconds >= 2.0)
      Reset();
    const bool resync = lateness > 1.0;
    return {resync, !resync && lateness > 2.0 * frameSeconds, m_skipping};
  }

private:
  double m_recoverySeconds = 0.0;
  bool m_skipping = false;
};

} // namespace partyvideo
