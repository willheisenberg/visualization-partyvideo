#include "core/FrameMailbox.h"

#include <utility>

namespace partyvideo
{

void FrameMailbox::Put(std::shared_ptr<const VideoFrame> frame)
{
  std::lock_guard<std::mutex> lock(m_mutex);
  m_frame = std::move(frame);
  ++m_sequence;
}

void FrameMailbox::Clear()
{
  std::lock_guard<std::mutex> lock(m_mutex);
  m_frame.reset();
  ++m_sequence;
}

MailboxRead FrameMailbox::ReadIfChanged(uint64_t& lastSequence) const
{
  std::lock_guard<std::mutex> lock(m_mutex);
  MailboxRead result;
  if (m_sequence == lastSequence)
    return result;
  lastSequence = m_sequence;
  result.changed = true;
  result.frame = m_frame;
  return result;
}

uint64_t FrameMailbox::Sequence() const
{
  std::lock_guard<std::mutex> lock(m_mutex);
  return m_sequence;
}

} // namespace partyvideo
