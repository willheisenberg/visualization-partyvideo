#pragma once

#include <array>

namespace partyvideo
{

// Farbraum-Hinweis aus den Metadaten des Videos.
enum class ColorSpaceHint
{
  Unknown,
  Bt601,
  Bt709
};

enum class ColorMatrix
{
  Bt601,
  Bt709
};

// Umrechnung für den Shader: rgb = matrix * (yuv - offset).
// matrix ist spaltenweise wie GLSL mat3 (Spalten Y, U, V); Y/U/V sind auf 0 … 1 normiert.
struct YuvToRgb
{
  std::array<float, 9> matrix;
  std::array<float, 3> offset;
};

YuvToRgb MakeYuvToRgb(ColorMatrix matrix, bool fullRange);

// Der Hinweis gewinnt; ohne Hinweis BT.709 ab 720 Pixel Höhe, sonst BT.601.
ColorMatrix ChooseMatrix(ColorSpaceHint hint, int height);

} // namespace partyvideo
