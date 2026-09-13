#include "TempDir.h"
#include "core/PlaybackEngine.h"
#include "core/FrameDropPolicy.h"

#include <chrono>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

using partyvideo::EngineConfig;
using partyvideo::LogLevel;
using partyvideo::PlaybackEngine;
using namespace std::chrono_literals;

namespace
{

std::string Fixture(const char* name)
{
  return std::string(PARTYVIDEO_FIXTURE_DIR) + "/" + name;
}

void WriteState(const TempDir& dir, int revision, const std::string& source)
{
  const auto path = dir.Path() / "state.json";
  {
    std::ofstream out(path.string() + ".tmp");
    out << nlohmann::json{{"revision", revision}, {"source", source}, {"kind", "file"}, {"title", "Test"}}.dump();
  }
  std::filesystem::rename(path.string() + ".tmp", path);
}

nlohmann::json ReadStatus(const TempDir& dir)
{
  std::ifstream in(dir.Path() / "renderer.json");
  if (!in)
    return nlohmann::json::object();
  auto json = nlohmann::json::parse(in, nullptr, false);
  return json.is_discarded() ? nlohmann::json::object() : json;
}

template<typename Predicate>
bool WaitFor(Predicate predicate, std::chrono::milliseconds timeout = 5000ms)
{
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (std::chrono::steady_clock::now() < deadline)
  {
    if (predicate())
      return true;
    std::this_thread::sleep_for(10ms);
  }
  return predicate();
}

bool StatusIs(const TempDir& dir, int revision, const std::string& state)
{
  const auto status = ReadStatus(dir);
  return status.value("revision", -1) == revision && status.value("state", "") == state;
}

EngineConfig Config(const TempDir& dir)
{
  EngineConfig config;
  config.stateDirectory = dir.Path().string();
  config.pollInterval = 50ms;
  return config;
}

double LatestMediaSeconds(PlaybackEngine& engine)
{
  uint64_t seen = 0;
  const auto read = engine.Mailbox().ReadIfChanged(seen);
  return read.frame ? read.frame->mediaSeconds : -1.0;
}

} // namespace

TEST(PlaybackEngine, WritesIdleWithoutStateFile)
{
  TempDir dir;
  PlaybackEngine engine(Config(dir));
  EXPECT_TRUE(WaitFor([&] { return StatusIs(dir, 0, "idle"); }));
}

TEST(PlaybackEngine, PlaysVideoWhileInstanceAttached)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();

  const auto start = engine.Mailbox().Sequence();
  ASSERT_TRUE(WaitFor([&] { return engine.Mailbox().Sequence() >= start + 10; }));

  const auto status = ReadStatus(dir);
  EXPECT_EQ(status.value("state", ""), "playing");
  EXPECT_EQ(status.value("revision", -1), 1);
  EXPECT_EQ(status.value("width", 0), 320);
  EXPECT_EQ(status.value("height", 0), 240);
  EXPECT_EQ(status.value("codec", ""), "h264");
  EXPECT_EQ(status.value("error", "x"), "");
  EXPECT_EQ(status.value("warning", "x"), "");

  const double first = LatestMediaSeconds(engine);
  std::this_thread::sleep_for(200ms);
  EXPECT_GT(LatestMediaSeconds(engine), first);
}

TEST(PlaybackEngine, DoesNotDecodeWithoutInstance)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));

  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));
  std::this_thread::sleep_for(100ms);
  const auto sequence = engine.Mailbox().Sequence();
  std::this_thread::sleep_for(300ms);
  EXPECT_EQ(engine.Mailbox().Sequence(), sequence);
}

TEST(PlaybackEngine, PausesOnDetachAndContinuesWhereItStopped)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return LatestMediaSeconds(engine) > 0.3; }));

  engine.DetachInstance();
  std::this_thread::sleep_for(100ms);
  const double pausedAt = LatestMediaSeconds(engine);
  const auto sequence = engine.Mailbox().Sequence();
  std::this_thread::sleep_for(500ms);
  EXPECT_EQ(engine.Mailbox().Sequence(), sequence);

  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return engine.Mailbox().Sequence() > sequence; }));
  const double resumedAt = LatestMediaSeconds(engine);
  EXPECT_GE(resumedAt, pausedAt);
  EXPECT_LT(resumedAt, pausedAt + 0.25) << "Das Video darf die Pausendauer nicht überspringen";
}

TEST(PlaybackEngine, EmptySourceClearsMailboxAndGoesIdle)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return LatestMediaSeconds(engine) >= 0.0; }));

  WriteState(dir, 2, "");
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 2, "idle"); }));
  std::this_thread::sleep_for(100ms);
  EXPECT_LT(LatestMediaSeconds(engine), 0.0);
}

TEST(PlaybackEngine, MissingFileReportsErrorAndLogs)
{
  TempDir dir;
  std::mutex logMutex;
  std::vector<std::string> messages;
  WriteState(dir, 1, Fixture("gibt_es_nicht.mp4"));

  auto config = Config(dir);
  config.log = [&](LogLevel, const std::string& message) {
    std::lock_guard<std::mutex> lock(logMutex);
    messages.push_back(message);
  };
  PlaybackEngine engine(config);
  engine.AttachInstance();

  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "error"); }));
  EXPECT_EQ(ReadStatus(dir).value("error", ""), "file_not_found");

  std::lock_guard<std::mutex> lock(logMutex);
  bool logged = false;
  for (const auto& message : messages)
    logged = logged || message.find("file_not_found") != std::string::npos;
  EXPECT_TRUE(logged);
}

TEST(PlaybackEngine, NewRevisionReplacesSource)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  engine.AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));

  WriteState(dir, 2, Fixture("h264_yuv422p_160x120_1s.mkv"));
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 2, "playing"); }));
  EXPECT_EQ(ReadStatus(dir).value("width", 0), 160);
  ASSERT_TRUE(WaitFor([&] {
    uint64_t seen = 0;
    const auto read = engine.Mailbox().ReadIfChanged(seen);
    return read.frame && read.frame->width == 160;
  }));
}

TEST(PlaybackEngine, SameRevisionIsNotReloaded)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  PlaybackEngine engine(Config(dir));
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));

  WriteState(dir, 1, Fixture("gibt_es_nicht.mp4"));
  std::this_thread::sleep_for(300ms);
  EXPECT_TRUE(StatusIs(dir, 1, "playing"));
}

TEST(PlaybackEngine, LargeVideoWarns)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_2048x1152_0p4s.mp4"));
  PlaybackEngine engine(Config(dir));
  ASSERT_TRUE(WaitFor([&] { return StatusIs(dir, 1, "playing"); }));
  EXPECT_EQ(ReadStatus(dir).value("warning", ""), "too_large");
}

TEST(PlaybackEngine, DestructorStopsPromptly)
{
  TempDir dir;
  WriteState(dir, 1, Fixture("h264_320x240_25fps_2s.mp4"));
  auto engine = std::make_unique<PlaybackEngine>(Config(dir));
  engine->AttachInstance();
  ASSERT_TRUE(WaitFor([&] { return LatestMediaSeconds(*engine) > 0.1; }));

  const auto start = std::chrono::steady_clock::now();
  engine.reset();
  EXPECT_LT(std::chrono::steady_clock::now() - start, 1s);
}

// Deterministic overload regression: clock resets must not look like recovery.
TEST(FrameDropPolicy, ResyncDoesNotDisableSkipping)
{
  partyvideo::FrameDropPolicy policy;
  EXPECT_TRUE(policy.Evaluate(0.1, 0.04).drop);
  auto decision = policy.Evaluate(1.1, 0.04);
  EXPECT_TRUE(decision.resync);
  EXPECT_FALSE(decision.drop);
  EXPECT_TRUE(decision.skipping);
  EXPECT_TRUE(policy.Evaluate(0.0, 0.04).skipping);
  EXPECT_TRUE(policy.Evaluate(0.01, 0.04).skipping);
  // Scheduling the same pending frame repeatedly must not count as recovery.
  for (int i = 0; i < 100; ++i)
    EXPECT_TRUE(policy.Evaluate(0.0, 0.04).skipping);
  for (int i = 0; i < 51; ++i)
    policy.ObserveDecode(0.01, 0.04);
  EXPECT_FALSE(policy.Evaluate(0.0, 0.04).skipping);
}

TEST(FrameDropPolicy, RecoversWithoutResyncAndResetsForNewSource)
{
  partyvideo::FrameDropPolicy policy;
  EXPECT_TRUE(policy.Evaluate(0.1, 0.04).skipping);
  for (int i = 0; i < 51; ++i)
    policy.ObserveDecode(0.035, 0.04);
  EXPECT_TRUE(policy.Evaluate(0.01, 0.04).skipping);
  for (int i = 0; i < 51; ++i)
    policy.ObserveDecode(0.01, 0.04);
  EXPECT_FALSE(policy.Evaluate(0.01, 0.04).skipping);
  EXPECT_TRUE(policy.Evaluate(1.1, 0.04).skipping);
  policy.Reset();
  EXPECT_FALSE(policy.Evaluate(0.0, 0.04).skipping);
}
