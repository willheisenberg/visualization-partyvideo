#include "TempDir.h"
#include "core/StateFiles.h"

#include <fstream>
#include <string>

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

using partyvideo::ReadPlaybackState;
using partyvideo::RendererStatus;
using partyvideo::WriteRendererStatus;

namespace
{

void WriteText(const std::filesystem::path& path, const std::string& text)
{
  std::ofstream out(path);
  out << text;
}

} // namespace

TEST(StateFiles, ReadsCompleteState)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"revision": 7, "source": "/storage/v.mp4", "kind": "file", "title": "Loop"})");

  const auto state = ReadPlaybackState(path.string());
  ASSERT_TRUE(state.has_value());
  EXPECT_EQ(state->revision, 7);
  EXPECT_EQ(state->source, "/storage/v.mp4");
  EXPECT_EQ(state->kind, "file");
  EXPECT_EQ(state->title, "Loop");
}

TEST(StateFiles, MissingFileGivesNullopt)
{
  TempDir dir;
  EXPECT_FALSE(ReadPlaybackState((dir.Path() / "state.json").string()).has_value());
}

TEST(StateFiles, InvalidJsonGivesNullopt)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"revision": 7, "source": )");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
}

TEST(StateFiles, RevisionMustBeAnInteger)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"source": "/storage/v.mp4"})");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
  WriteText(path, R"({"revision": "7", "source": "/storage/v.mp4"})");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
  WriteText(path, R"([1, 2, 3])");
  EXPECT_FALSE(ReadPlaybackState(path.string()).has_value());
}

TEST(StateFiles, MissingOrWrongOptionalFieldsBecomeEmpty)
{
  TempDir dir;
  const auto path = dir.Path() / "state.json";
  WriteText(path, R"({"revision": 3, "source": 42})");

  const auto state = ReadPlaybackState(path.string());
  ASSERT_TRUE(state.has_value());
  EXPECT_EQ(state->revision, 3);
  EXPECT_EQ(state->source, "");
  EXPECT_EQ(state->kind, "");
  EXPECT_EQ(state->title, "");
}

TEST(StateFiles, WriteCreatesDirectoryAndAllFields)
{
  TempDir dir;
  const auto path = dir.Path() / "neu" / "renderer.json";
  RendererStatus status;
  status.revision = 9;
  status.state = "error";
  status.error = "file_not_found";
  status.warning = "too_large";
  status.width = 2048;
  status.height = 1152;
  status.codec = "h264";

  ASSERT_TRUE(WriteRendererStatus(path.string(), status));

  std::ifstream in(path);
  const auto json = nlohmann::json::parse(in);
  EXPECT_EQ(json.at("revision"), 9);
  EXPECT_EQ(json.at("state"), "error");
  EXPECT_EQ(json.at("error"), "file_not_found");
  EXPECT_EQ(json.at("warning"), "too_large");
  EXPECT_EQ(json.at("width"), 2048);
  EXPECT_EQ(json.at("height"), 1152);
  EXPECT_EQ(json.at("codec"), "h264");
  EXPECT_EQ(json.size(), 7u);
}

TEST(StateFiles, WriteOverwritesAndLeavesNoTempFile)
{
  TempDir dir;
  const auto path = dir.Path() / "renderer.json";
  RendererStatus status;
  status.state = "loading";
  ASSERT_TRUE(WriteRendererStatus(path.string(), status));
  status.state = "playing";
  ASSERT_TRUE(WriteRendererStatus(path.string(), status));

  std::ifstream in(path);
  EXPECT_EQ(nlohmann::json::parse(in).at("state"), "playing");
  EXPECT_FALSE(std::filesystem::exists(path.string() + ".tmp"));
}

TEST(StateFiles, WriteFailsForUnwritableLocation)
{
  TempDir dir;
  const auto blocker = dir.Path() / "datei";
  WriteText(blocker, "kein Verzeichnis");
  RendererStatus status;
  EXPECT_FALSE(WriteRendererStatus((blocker / "renderer.json").string(), status));
}
