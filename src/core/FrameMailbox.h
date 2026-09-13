#pragma once

#include "core/VideoFrame.h"

#include <cstdint>
#include <memory>
#include <mutex>

namespace partyvideo
{

struct MailboxRead
{
  bool changed = false;                     // seit dem letzten Lesen neues Bild oder geleert
  std::shared_ptr<const VideoFrame> frame;  // nullptr = schwarz anzeigen
};

// Thread-sicheres Fach für das jeweils aktuelle Bild zwischen Worker- und Render-Thread.
// Das letzte Bild bleibt liegen, damit eine neu erzeugte Kodi-Instanz es sofort anzeigen kann.
class FrameMailbox
{
public:
  void Put(std::shared_ptr<const VideoFrame> frame);
  void Clear();
  // Jeder Leser führt seine eigene lastSequence (Start 0); sie wird bei einer Änderung aktualisiert.
  MailboxRead ReadIfChanged(uint64_t& lastSequence) const;
  uint64_t Sequence() const;

private:
  mutable std::mutex m_mutex;
  std::shared_ptr<const VideoFrame> m_frame;
  uint64_t m_sequence = 0;
};

} // namespace partyvideo
