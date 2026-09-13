#include "core/Letterbox.h"

namespace partyvideo
{

NdcRect FitVideo(int viewportWidth, int viewportHeight, int videoWidth, int videoHeight, int sarNum, int sarDen)
{
  if (viewportWidth <= 0 || viewportHeight <= 0 || videoWidth <= 0 || videoHeight <= 0)
    return {0.0f, 0.0f, 0.0f, 0.0f};

  const double sar = (sarNum > 0 && sarDen > 0) ? static_cast<double>(sarNum) / sarDen : 1.0;
  const double videoAspect = static_cast<double>(videoWidth) * sar / videoHeight;
  const double viewportAspect = static_cast<double>(viewportWidth) / viewportHeight;

  double scaleX = 1.0;
  double scaleY = 1.0;
  if (videoAspect > viewportAspect)
    scaleY = viewportAspect / videoAspect;
  else
    scaleX = videoAspect / viewportAspect;

  return {static_cast<float>(-scaleX), static_cast<float>(-scaleY), static_cast<float>(scaleX),
          static_cast<float>(scaleY)};
}

} // namespace partyvideo
