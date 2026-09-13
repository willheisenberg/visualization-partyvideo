#pragma once

namespace partyvideo
{

// Rechteck in normalisierten Gerätekoordinaten (-1 … 1) des aktuellen Viewports.
struct NdcRect
{
  float left;
  float bottom;
  float right;
  float top;
};

// Passt ein Video mit erhaltenem Seitenverhältnis (inklusive Pixel-Seitenverhältnis sarNum:sarDen)
// mittig in den Viewport ein. sarNum/sarDen <= 0 gilt als 1:1. Ungültige Größen (<= 0) ergeben
// ein leeres Rechteck (alle Werte 0).
NdcRect FitVideo(int viewportWidth, int viewportHeight, int videoWidth, int videoHeight, int sarNum, int sarDen);

} // namespace partyvideo
