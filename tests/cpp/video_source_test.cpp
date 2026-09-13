#include "core/VideoSource.h"

#include <string>

#include <gtest/gtest.h>

using partyvideo::ColorMatrix;
using partyvideo::ErrorCode;
using partyvideo::SourceError;
using partyvideo::VideoFrame;
using partyvideo::VideoSource;

namespace
{

std::string Fixture(const char* name)
{
  return std::string(PARTYVIDEO_FIXTURE_DIR) + "/" + name;
}

// Bilder bis zum ersten Schleifenwechsel zählen (das letzte gehört schon zur zweiten Runde).
// -1 bei einem Fehler, -2 wenn die Datei unerwartet lang ist.
int FramesInFirstLoop(VideoSource& source)
{
  VideoFrame frame;
  int count = 0;
  while (source.LoopCount() == 0)
  {
    if (!source.NextFrame(frame))
      return -1;
    if (++count > 500)
      return -2;
  }
  return count;
}

} // namespace

TEST(VideoSource, OpensH264AndReportsInfo)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  EXPECT_TRUE(source.IsOpen());
  EXPECT_EQ(source.Info().width, 320);
  EXPECT_EQ(source.Info().height, 240);
  EXPECT_EQ(source.Info().codec, "h264");
  EXPECT_NEAR(source.Info().frameSeconds, 0.04, 1e-6);
}

TEST(VideoSource, DecodesYuv420FramesWithIncreasingMediaTime)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);

  VideoFrame frame;
  ASSERT_TRUE(source.NextFrame(frame));
  EXPECT_NEAR(frame.mediaSeconds, 0.0, 1e-6);
  EXPECT_EQ(frame.width, 320);
  EXPECT_EQ(frame.height, 240);
  EXPECT_GE(frame.strides[0], 320);
  EXPECT_GE(frame.strides[1], 160);
  EXPECT_GE(frame.strides[2], 160);
  EXPECT_GE(frame.planes[0].size(), static_cast<size_t>(frame.strides[0]) * 240);
  EXPECT_GE(frame.planes[1].size(), static_cast<size_t>(frame.strides[1]) * 120);
  EXPECT_EQ(frame.matrix, ColorMatrix::Bt601);
  EXPECT_FALSE(frame.fullRange);

  double previous = frame.mediaSeconds;
  for (int i = 1; i < 10; ++i)
  {
    ASSERT_TRUE(source.NextFrame(frame));
    EXPECT_NEAR(frame.mediaSeconds - previous, 0.04, 1e-3);
    previous = frame.mediaSeconds;
  }
}

TEST(VideoSource, LoopsSeamlesslyAtEnd)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);

  VideoFrame frame;
  double previous = -1.0;
  for (int i = 0; i < 120; ++i)
  {
    ASSERT_TRUE(source.NextFrame(frame)) << "Bild " << i;
    EXPECT_GT(frame.mediaSeconds, previous) << "Bild " << i;
    if (i == 50)
    {
      EXPECT_NEAR(frame.mediaSeconds, 2.0, 1e-3);
    }
    previous = frame.mediaSeconds;
  }
  EXPECT_GE(source.LoopCount(), 2);
  EXPECT_NEAR(previous, 119 * 0.04, 1e-2);
}

TEST(VideoSource, ConvertsOtherPixelFormatsTo420)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_yuv422p_160x120_1s.mkv")), SourceError::None);

  VideoFrame frame;
  ASSERT_TRUE(source.NextFrame(frame));
  EXPECT_EQ(frame.width, 160);
  EXPECT_EQ(frame.height, 120);
  EXPECT_GE(frame.strides[1], 80);
  EXPECT_GE(frame.planes[1].size(), static_cast<size_t>(frame.strides[1]) * 60);
  EXPECT_GE(frame.planes[2].size(), static_cast<size_t>(frame.strides[2]) * 60);
}

TEST(VideoSource, IgnoresAudioStream)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_with_audio_320x240_1s.mp4")), SourceError::None);
  VideoFrame frame;
  for (int i = 0; i < 30; ++i)
    ASSERT_TRUE(source.NextFrame(frame));
}

TEST(VideoSource, SkippingNonReferenceFramesStillDelivers)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  source.SetSkipNonReference(true);

  VideoFrame frame;
  double previous = -1.0;
  for (int i = 0; i < 20; ++i)
  {
    ASSERT_TRUE(source.NextFrame(frame));
    EXPECT_GT(frame.mediaSeconds, previous);
    previous = frame.mediaSeconds;
  }
}

TEST(VideoSource, SkippingSurvivesReopen)
{
  // Das Video hat B-Bilder ohne Referenz: mit AVDISCARD_NONREF kommen weniger Bilder je Runde.
  VideoSource complete;
  ASSERT_EQ(complete.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  const int allFrames = FramesInFirstLoop(complete);
  ASSERT_GT(allFrames, 0);

  VideoSource skipping;
  ASSERT_EQ(skipping.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  skipping.SetSkipNonReference(true);
  // Neu öffnen wie im Notfallpfad von RestartFromBeginning: der Wunsch muss erhalten bleiben.
  ASSERT_EQ(skipping.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  const int skippedFrames = FramesInFirstLoop(skipping);
  ASSERT_GT(skippedFrames, 0);
  EXPECT_LT(skippedFrames, allFrames);

  // Nach Close() beginnt eine Quelle wieder ohne Überspringen.
  skipping.Close();
  ASSERT_EQ(skipping.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  EXPECT_EQ(FramesInFirstLoop(skipping), allFrames);
}

TEST(VideoSource, LargeVideoReportsItsSize)
{
  VideoSource source;
  ASSERT_EQ(source.Open(Fixture("h264_2048x1152_0p4s.mp4")), SourceError::None);
  EXPECT_EQ(source.Info().width, 2048);
  EXPECT_EQ(source.Info().height, 1152);
}

TEST(VideoSource, MissingFile)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("gibt_es_nicht.mp4")), SourceError::FileNotFound);
  EXPECT_FALSE(source.IsOpen());
  EXPECT_EQ(source.LastError(), SourceError::FileNotFound);
  VideoFrame frame;
  EXPECT_FALSE(source.NextFrame(frame));
}

TEST(VideoSource, AudioOnlyFileHasNoVideoStream)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("audio_only_1s.m4a")), SourceError::NoVideoStream);
  EXPECT_FALSE(source.IsOpen());
}

TEST(VideoSource, TextFileCannotBeOpened)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("not_a_video.mp4")), SourceError::OpenFailed);
  EXPECT_FALSE(source.IsOpen());
}

TEST(VideoSource, MissingDecoderIsUnsupportedCodec)
{
  // Der amd64-Testbuild von FFmpeg hat absichtlich keinen mpeg4-Decoder.
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("mpeg4_320x240_1s.avi")), SourceError::UnsupportedCodec);
  EXPECT_FALSE(source.IsOpen());
}

TEST(VideoSource, CanBeReopenedAfterError)
{
  VideoSource source;
  EXPECT_EQ(source.Open(Fixture("gibt_es_nicht.mp4")), SourceError::FileNotFound);
  ASSERT_EQ(source.Open(Fixture("h264_320x240_25fps_2s.mp4")), SourceError::None);
  EXPECT_EQ(source.LastError(), SourceError::None);
  VideoFrame frame;
  EXPECT_TRUE(source.NextFrame(frame));
}

TEST(VideoSource, ErrorCodesMatchSpec)
{
  EXPECT_STREQ(ErrorCode(SourceError::None), "");
  EXPECT_STREQ(ErrorCode(SourceError::FileNotFound), "file_not_found");
  EXPECT_STREQ(ErrorCode(SourceError::OpenFailed), "open_failed");
  EXPECT_STREQ(ErrorCode(SourceError::NoVideoStream), "no_video_stream");
  EXPECT_STREQ(ErrorCode(SourceError::UnsupportedCodec), "unsupported_codec");
  EXPECT_STREQ(ErrorCode(SourceError::DecodeFailed), "decode_failed");
}
