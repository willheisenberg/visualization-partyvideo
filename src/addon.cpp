#include "addon.h"

#include <atomic>

#include <GLES3/gl3.h>

extern "C"
{
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libswscale/swscale.h>
}

namespace
{

// Prozessweite Zähler für Risiko R6: entlädt Kodi die Instanz oder die .so zwischen Songs?
// Beginnt die laufende Nummer wieder bei 1, wurde die .so neu geladen.
static std::atomic<int> g_instancesCreated{0};
static std::atomic<int> g_instancesAlive{0};

void LogLibVersion(const char* name, unsigned version)
{
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] %s %u.%u.%u", name, AV_VERSION_MAJOR(version),
            AV_VERSION_MINOR(version), AV_VERSION_MICRO(version));
}

} // namespace

CPartyVideo::CPartyVideo()
{
  const int number = ++g_instancesCreated;
  const int alive = ++g_instancesAlive;
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Instanz erzeugt (#%d, aktiv %d)", number, alive);
}

CPartyVideo::~CPartyVideo()
{
  const int alive = --g_instancesAlive;
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Instanz zerstört (aktiv %d)", alive);
}

bool CPartyVideo::Start(int channels, int samplesPerSec, int bitsPerSample, const std::string& songName)
{
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Start: '%s' (%d Kanäle, %d Hz, %d Bit)",
            songName.c_str(), channels, samplesPerSec, bitsPerSample);
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] FFmpeg %s", av_version_info());
  LogLibVersion("libavcodec", avcodec_version());
  LogLibVersion("libavformat", avformat_version());
  LogLibVersion("libavutil", avutil_version());
  LogLibVersion("libswscale", swscale_version());
  return true;
}

void CPartyVideo::Stop()
{
  kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Stop");
}

void CPartyVideo::Render()
{
  if (!m_glInfoLogged)
  {
    const GLubyte* glVersion = glGetString(GL_VERSION);
    kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] GL_VERSION %s",
              glVersion ? reinterpret_cast<const char*>(glVersion) : "(kein GL-Kontext)");
    kodi::Log(ADDON_LOG_INFO, "[visualization.partyvideo] Viewport x=%d y=%d w=%d h=%d", X(), Y(),
              Width(), Height());
    m_glInfoLogged = true;
  }

  // Kodi hat die Scissor-Box schon auf die Visualisierungsfläche gesetzt; X()/Y() sind keine GL-Koordinaten.
  glEnable(GL_SCISSOR_TEST);
  glClearColor(0.85f, 0.10f, 0.55f, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT);
  glDisable(GL_SCISSOR_TEST);
}

ADDONCREATOR(CPartyVideo)
