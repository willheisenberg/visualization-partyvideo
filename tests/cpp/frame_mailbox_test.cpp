#include "core/FrameMailbox.h"

#include <atomic>
#include <memory>
#include <thread>

#include <gtest/gtest.h>

using partyvideo::FrameMailbox;
using partyvideo::VideoFrame;

namespace
{

std::shared_ptr<const VideoFrame> MakeFrame(double mediaSeconds)
{
  auto frame = std::make_shared<VideoFrame>();
  frame->mediaSeconds = mediaSeconds;
  return frame;
}

} // namespace

TEST(FrameMailbox, EmptyMailboxReportsNoChange)
{
  FrameMailbox mailbox;
  uint64_t seen = 0;
  const auto read = mailbox.ReadIfChanged(seen);
  EXPECT_FALSE(read.changed);
  EXPECT_EQ(read.frame, nullptr);
  EXPECT_EQ(mailbox.Sequence(), 0u);
}

TEST(FrameMailbox, PutIsReportedOncePerReader)
{
  FrameMailbox mailbox;
  const auto frame = MakeFrame(1.5);
  mailbox.Put(frame);

  uint64_t seen = 0;
  auto read = mailbox.ReadIfChanged(seen);
  EXPECT_TRUE(read.changed);
  EXPECT_EQ(read.frame, frame);
  EXPECT_EQ(seen, mailbox.Sequence());

  read = mailbox.ReadIfChanged(seen);
  EXPECT_FALSE(read.changed);
}

TEST(FrameMailbox, NewReaderGetsCurrentFrame)
{
  FrameMailbox mailbox;
  mailbox.Put(MakeFrame(1.0));
  mailbox.Put(MakeFrame(2.0));

  uint64_t firstReader = 0;
  uint64_t secondReader = 0;
  EXPECT_DOUBLE_EQ(mailbox.ReadIfChanged(firstReader).frame->mediaSeconds, 2.0);
  EXPECT_DOUBLE_EQ(mailbox.ReadIfChanged(secondReader).frame->mediaSeconds, 2.0);
}

TEST(FrameMailbox, ClearIsReportedAsChangeWithoutFrame)
{
  FrameMailbox mailbox;
  mailbox.Put(MakeFrame(1.0));
  uint64_t seen = 0;
  mailbox.ReadIfChanged(seen);

  mailbox.Clear();
  const auto read = mailbox.ReadIfChanged(seen);
  EXPECT_TRUE(read.changed);
  EXPECT_EQ(read.frame, nullptr);
}

TEST(FrameMailbox, ConcurrentWriterAndReaderSeeMonotonicFrames)
{
  FrameMailbox mailbox;
  constexpr int kFrames = 2000;
  std::atomic<bool> done{false};

  std::thread writer([&] {
    for (int i = 1; i <= kFrames; ++i)
      mailbox.Put(MakeFrame(i));
    done = true;
  });

  uint64_t seen = 0;
  double last = 0.0;
  bool finished = false;
  while (!finished)
  {
    finished = done.load();
    const auto read = mailbox.ReadIfChanged(seen);
    if (read.changed && read.frame)
    {
      EXPECT_GE(read.frame->mediaSeconds, last);
      last = read.frame->mediaSeconds;
    }
  }
  writer.join();

  const auto read = mailbox.ReadIfChanged(seen);
  if (read.changed)
    last = read.frame->mediaSeconds;
  EXPECT_DOUBLE_EQ(last, kFrames);
}

TEST(VideoFrame, ChromaSizeRoundsUp)
{
  EXPECT_EQ(partyvideo::ChromaWidth(1920), 960);
  EXPECT_EQ(partyvideo::ChromaWidth(1281), 641);
  EXPECT_EQ(partyvideo::ChromaHeight(1081), 541);
}
