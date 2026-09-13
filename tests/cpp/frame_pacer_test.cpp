#include "core/FramePacer.h"

#include <chrono>

#include <gtest/gtest.h>

using partyvideo::FramePacer;
using namespace std::chrono_literals;

namespace
{

const FramePacer::Clock::time_point kT0 = FramePacer::Clock::time_point{} + 100s;

void ExpectTime(FramePacer::Clock::time_point actual, FramePacer::Clock::time_point expected)
{
  const auto diff = std::chrono::duration_cast<std::chrono::microseconds>(actual - expected).count();
  EXPECT_LE(diff < 0 ? -diff : diff, 10) << "Abweichung in Mikrosekunden: " << diff;
}

} // namespace

TEST(FramePacer, NotAnchoredInitially)
{
  FramePacer pacer;
  EXPECT_FALSE(pacer.IsAnchored());
  EXPECT_FALSE(pacer.IsPaused());
}

TEST(FramePacer, DueTimeFollowsMediaTime)
{
  FramePacer pacer;
  pacer.Reset(10.0, kT0);
  EXPECT_TRUE(pacer.IsAnchored());
  ExpectTime(pacer.DueTime(10.0), kT0);
  ExpectTime(pacer.DueTime(10.5), kT0 + 500ms);
}

TEST(FramePacer, LatenessIsPositiveWhenLate)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  EXPECT_NEAR(pacer.Lateness(0.04, kT0 + 100ms), 0.06, 1e-6);
  EXPECT_NEAR(pacer.Lateness(0.2, kT0 + 100ms), -0.1, 1e-6);
}

TEST(FramePacer, PauseShiftsScheduleByPauseDuration)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0 + 1s);
  EXPECT_TRUE(pacer.IsPaused());
  pacer.Resume(kT0 + 3s);
  EXPECT_FALSE(pacer.IsPaused());
  ExpectTime(pacer.DueTime(1.5), kT0 + 3500ms);
}

TEST(FramePacer, RepeatedPauseKeepsFirstPauseStart)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0 + 1s);
  pacer.Pause(kT0 + 2s);
  pacer.Resume(kT0 + 3s);
  ExpectTime(pacer.DueTime(1.0), kT0 + 3s);
}

TEST(FramePacer, LatenessIsZeroWhilePaused)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0);
  EXPECT_DOUBLE_EQ(pacer.Lateness(0.0, kT0 + 10s), 0.0);
}

TEST(FramePacer, ResetClearsPauseAndInvalidateDropsAnchor)
{
  FramePacer pacer;
  pacer.Reset(0.0, kT0);
  pacer.Pause(kT0 + 1s);
  pacer.Reset(5.0, kT0 + 2s);
  EXPECT_FALSE(pacer.IsPaused());
  ExpectTime(pacer.DueTime(5.0), kT0 + 2s);
  pacer.Invalidate();
  EXPECT_FALSE(pacer.IsAnchored());
}
