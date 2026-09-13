#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace partyvideo
{

// Inhalt von state.json (Spec §5.1), geschrieben vom Service.
struct PlaybackState
{
  int64_t revision = 0;
  std::string source; // absoluter Pfad oder "" (Visual aus)
  std::string kind;   // "youtube" | "file" | ""
  std::string title;
};

// Inhalt von renderer.json (Spec §5.2), geschrieben vom Renderer.
struct RendererStatus
{
  int64_t revision = 0;
  std::string state = "idle"; // idle | loading | playing | error
  std::string error;          // "" | file_not_found | open_failed | no_video_stream | unsupported_codec | decode_failed
  std::string warning;        // "" | too_large
  int width = 0;
  int height = 0;
  std::string codec;
};

// std::nullopt, wenn die Datei fehlt, kein JSON-Objekt ist oder keine ganzzahlige "revision" hat.
// Fehlende oder nicht-textuelle Felder source/kind/title werden zu "".
std::optional<PlaybackState> ReadPlaybackState(const std::string& path);

// Schreibt atomar (erst path + ".tmp", dann rename) und legt das Verzeichnis bei Bedarf an.
bool WriteRendererStatus(const std::string& path, const RendererStatus& status);

} // namespace partyvideo
