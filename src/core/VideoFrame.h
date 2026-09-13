#pragma once

#include "core/ColorConversion.h"

#include <array>
#include <cstdint>
#include <vector>

namespace partyvideo
{

// Ein dekodiertes Bild im Format YUV 4:2:0 mit 8 Bit, unabhängig von FFmpeg-Puffern.
struct VideoFrame
{
  int width = 0;  // sichtbare Breite in Pixeln
  int height = 0; // sichtbare Höhe in Pixeln
  // Ebene 0 = Y (width × height), 1 = U und 2 = V (je ChromaWidth × ChromaHeight).
  std::array<std::vector<uint8_t>, 3> planes;
  // Bytes pro Zeile je Ebene (>= sichtbare Ebenenbreite, wegen Speicherausrichtung).
  std::array<int, 3> strides{0, 0, 0};
  double mediaSeconds = 0.0; // über Schleifen hinweg fortlaufend
  ColorMatrix matrix = ColorMatrix::Bt709;
  bool fullRange = false;
  int sarNum = 1;
  int sarDen = 1;
};

inline int ChromaWidth(int width)
{
  return (width + 1) / 2;
}

inline int ChromaHeight(int height)
{
  return (height + 1) / 2;
}

} // namespace partyvideo
