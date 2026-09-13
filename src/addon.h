#pragma once

#include <kodi/addon-instance/Visualization.h>

#include <cstdint>
#include <memory>
#include <string>

namespace partyvideo
{
class PlaybackEngine;
class YuvRenderer;
} // namespace partyvideo

// Kodi-Visualisierung: zeigt das Video der prozessweiten PlaybackEngine.
// Kodi erzeugt diese Instanz bei jedem Songwechsel neu; Decoder und Wiedergabeposition bleiben in der Engine.
class ATTR_DLL_LOCAL CPartyVideo : public kodi::addon::CAddonBase,
                                   public kodi::addon::CInstanceVisualization
{
public:
  CPartyVideo();
  ~CPartyVideo() override;

  bool Start(int channels, int samplesPerSec, int bitsPerSample, const std::string& songName) override;
  void Stop() override;
  bool IsDirty() override;
  void Render() override;

private:
  partyvideo::PlaybackEngine& m_engine;
  std::unique_ptr<partyvideo::YuvRenderer> m_renderer; // GL-Objekte gehören zur Instanz
  bool m_rendererFailed = false;
  bool m_attached = false;
  bool m_needsDraw = true;
  uint64_t m_seenSequence = 0;
};
