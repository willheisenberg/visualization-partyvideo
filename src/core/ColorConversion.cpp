#include "core/ColorConversion.h"

namespace partyvideo
{

YuvToRgb MakeYuvToRgb(ColorMatrix matrix, bool fullRange)
{
  const double kr = matrix == ColorMatrix::Bt709 ? 0.2126 : 0.299;
  const double kb = matrix == ColorMatrix::Bt709 ? 0.0722 : 0.114;
  const double kg = 1.0 - kr - kb;

  // Limited Range: Luma 16 … 235, Chroma 16 … 240 (8 Bit) auf volle Aussteuerung strecken.
  const double lumaScale = fullRange ? 1.0 : 255.0 / 219.0;
  const double chromaScale = fullRange ? 1.0 : 255.0 / 224.0;

  const double rFromV = 2.0 * (1.0 - kr) * chromaScale;
  const double gFromU = -2.0 * kb * (1.0 - kb) / kg * chromaScale;
  const double gFromV = -2.0 * kr * (1.0 - kr) / kg * chromaScale;
  const double bFromU = 2.0 * (1.0 - kb) * chromaScale;

  YuvToRgb result{};
  // Spalte Y
  result.matrix[0] = static_cast<float>(lumaScale);
  result.matrix[1] = static_cast<float>(lumaScale);
  result.matrix[2] = static_cast<float>(lumaScale);
  // Spalte U
  result.matrix[3] = 0.0f;
  result.matrix[4] = static_cast<float>(gFromU);
  result.matrix[5] = static_cast<float>(bFromU);
  // Spalte V
  result.matrix[6] = static_cast<float>(rFromV);
  result.matrix[7] = static_cast<float>(gFromV);
  result.matrix[8] = 0.0f;

  result.offset = {fullRange ? 0.0f : 16.0f / 255.0f, 128.0f / 255.0f, 128.0f / 255.0f};
  return result;
}

ColorMatrix ChooseMatrix(ColorSpaceHint hint, int height)
{
  switch (hint)
  {
    case ColorSpaceHint::Bt601:
      return ColorMatrix::Bt601;
    case ColorSpaceHint::Bt709:
      return ColorMatrix::Bt709;
    case ColorSpaceHint::Unknown:
      break;
  }
  return height >= 720 ? ColorMatrix::Bt709 : ColorMatrix::Bt601;
}

} // namespace partyvideo
