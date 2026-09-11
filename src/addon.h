#pragma once

#include <kodi/addon-instance/Visualization.h>

#include <string>

// Stufe 0: zeichnet eine Farbfläche und protokolliert die geladenen FFmpeg-Versionen.
class ATTR_DLL_LOCAL CPartyVideo : public kodi::addon::CAddonBase,
                                   public kodi::addon::CInstanceVisualization
{
public:
  CPartyVideo();
  ~CPartyVideo() override;

  bool Start(int channels, int samplesPerSec, int bitsPerSample, const std::string& songName) override;
  void Stop() override;
  void Render() override;

private:
  // GL-Infos erst im ersten Render() protokollieren: nur dort ist der GL-Kontext sicher aktiv.
  bool m_glInfoLogged = false;
};
