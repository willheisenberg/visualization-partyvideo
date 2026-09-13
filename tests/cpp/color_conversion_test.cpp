#include "core/ColorConversion.h"

#include <array>

#include <gtest/gtest.h>

using partyvideo::ChooseMatrix;
using partyvideo::ColorMatrix;
using partyvideo::ColorSpaceHint;
using partyvideo::MakeYuvToRgb;

namespace
{

constexpr float kTolerance = 1e-3f;

std::array<float, 3> Apply(const partyvideo::YuvToRgb& conv, float y, float u, float v)
{
  const float yy = y - conv.offset[0];
  const float uu = u - conv.offset[1];
  const float vv = v - conv.offset[2];
  const auto& m = conv.matrix;
  return {m[0] * yy + m[3] * uu + m[6] * vv, m[1] * yy + m[4] * uu + m[7] * vv,
          m[2] * yy + m[5] * uu + m[8] * vv};
}

void ExpectRgb(const std::array<float, 3>& rgb, float r, float g, float b)
{
  EXPECT_NEAR(rgb[0], r, kTolerance);
  EXPECT_NEAR(rgb[1], g, kTolerance);
  EXPECT_NEAR(rgb[2], b, kTolerance);
}

} // namespace

TEST(ColorConversion, LimitedRangeBlackAndWhite)
{
  for (const auto matrix : {ColorMatrix::Bt601, ColorMatrix::Bt709})
  {
    const auto conv = MakeYuvToRgb(matrix, false);
    ExpectRgb(Apply(conv, 16.0f / 255, 128.0f / 255, 128.0f / 255), 0.0f, 0.0f, 0.0f);
    ExpectRgb(Apply(conv, 235.0f / 255, 128.0f / 255, 128.0f / 255), 1.0f, 1.0f, 1.0f);
  }
}

TEST(ColorConversion, FullRangeBlackAndWhite)
{
  for (const auto matrix : {ColorMatrix::Bt601, ColorMatrix::Bt709})
  {
    const auto conv = MakeYuvToRgb(matrix, true);
    ExpectRgb(Apply(conv, 0.0f, 128.0f / 255, 128.0f / 255), 0.0f, 0.0f, 0.0f);
    ExpectRgb(Apply(conv, 1.0f, 128.0f / 255, 128.0f / 255), 1.0f, 1.0f, 1.0f);
  }
}

TEST(ColorConversion, Bt709FullRangeCoefficients)
{
  const auto conv = MakeYuvToRgb(ColorMatrix::Bt709, true);
  EXPECT_NEAR(conv.matrix[6], 1.5748f, kTolerance);  // R aus V
  EXPECT_NEAR(conv.matrix[4], -0.1873f, kTolerance); // G aus U
  EXPECT_NEAR(conv.matrix[7], -0.4681f, kTolerance); // G aus V
  EXPECT_NEAR(conv.matrix[5], 1.8556f, kTolerance);  // B aus U
}

TEST(ColorConversion, Bt601LimitedRangeCoefficients)
{
  const auto conv = MakeYuvToRgb(ColorMatrix::Bt601, false);
  EXPECT_NEAR(conv.matrix[0], 1.1644f, kTolerance); // Y-Skalierung
  EXPECT_NEAR(conv.matrix[6], 1.5960f, kTolerance); // R aus V
  EXPECT_NEAR(conv.matrix[4], -0.3918f, kTolerance); // G aus U
  EXPECT_NEAR(conv.matrix[7], -0.8130f, kTolerance); // G aus V
  EXPECT_NEAR(conv.matrix[5], 2.0172f, kTolerance); // B aus U
}

TEST(ColorConversion, ChooseMatrixPrefersHint)
{
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Bt709, 480), ColorMatrix::Bt709);
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Bt601, 1080), ColorMatrix::Bt601);
}

TEST(ColorConversion, ChooseMatrixFallsBackToHeight)
{
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Unknown, 720), ColorMatrix::Bt709);
  EXPECT_EQ(ChooseMatrix(ColorSpaceHint::Unknown, 719), ColorMatrix::Bt601);
}
