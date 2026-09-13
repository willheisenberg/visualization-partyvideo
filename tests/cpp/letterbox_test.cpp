#include "core/Letterbox.h"

#include <gtest/gtest.h>

namespace
{

constexpr float kTolerance = 1e-4f;

void ExpectRect(const partyvideo::NdcRect& rect, float left, float bottom, float right, float top)
{
  EXPECT_NEAR(rect.left, left, kTolerance);
  EXPECT_NEAR(rect.bottom, bottom, kTolerance);
  EXPECT_NEAR(rect.right, right, kTolerance);
  EXPECT_NEAR(rect.top, top, kTolerance);
}

} // namespace

TEST(Letterbox, SameAspectFillsViewport)
{
  ExpectRect(partyvideo::FitVideo(1920, 1080, 1280, 720, 1, 1), -1.0f, -1.0f, 1.0f, 1.0f);
}

TEST(Letterbox, NarrowVideoGetsPillarbox)
{
  // 4:3 in 16:9 → Breite 0.75 des Viewports
  ExpectRect(partyvideo::FitVideo(1920, 1080, 640, 480, 1, 1), -0.75f, -1.0f, 0.75f, 1.0f);
}

TEST(Letterbox, WideVideoGetsLetterbox)
{
  // 21:9 in 16:9 → Höhe 16/21 des Viewports
  const float h = 16.0f / 21.0f;
  ExpectRect(partyvideo::FitVideo(1920, 1080, 2520, 1080, 1, 1), -1.0f, -h, 1.0f, h);
}

TEST(Letterbox, SampleAspectRatioIsApplied)
{
  // 720x576 mit SAR 4:3 → Anzeige 960x576 (1.6667) in 16:9 → Breite 0.9375
  ExpectRect(partyvideo::FitVideo(1920, 1080, 720, 576, 4, 3), -0.9375f, -1.0f, 0.9375f, 1.0f);
}

TEST(Letterbox, InvalidSampleAspectRatioCountsAsSquare)
{
  ExpectRect(partyvideo::FitVideo(1920, 1080, 640, 480, 0, 0), -0.75f, -1.0f, 0.75f, 1.0f);
}

TEST(Letterbox, InvalidSizesGiveEmptyRect)
{
  ExpectRect(partyvideo::FitVideo(0, 1080, 640, 480, 1, 1), 0.0f, 0.0f, 0.0f, 0.0f);
  ExpectRect(partyvideo::FitVideo(1920, 1080, 640, 0, 1, 1), 0.0f, 0.0f, 0.0f, 0.0f);
}
