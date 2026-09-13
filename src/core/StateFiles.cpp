#include "core/StateFiles.h"

#include <filesystem>
#include <fstream>
#include <system_error>

#include <nlohmann/json.hpp>

namespace partyvideo
{

namespace
{

std::string StringField(const nlohmann::json& object, const char* key)
{
  const auto it = object.find(key);
  if (it == object.end() || !it->is_string())
    return {};
  return it->get<std::string>();
}

} // namespace

std::optional<PlaybackState> ReadPlaybackState(const std::string& path)
{
  std::ifstream in(path);
  if (!in)
    return std::nullopt;

  const auto json = nlohmann::json::parse(in, nullptr, false);
  if (json.is_discarded() || !json.is_object())
    return std::nullopt;

  const auto revision = json.find("revision");
  if (revision == json.end() || !revision->is_number_integer())
    return std::nullopt;

  PlaybackState state;
  state.revision = revision->get<int64_t>();
  state.source = StringField(json, "source");
  state.kind = StringField(json, "kind");
  state.title = StringField(json, "title");
  return state;
}

bool WriteRendererStatus(const std::string& path, const RendererStatus& status)
{
  const nlohmann::json json = {
      {"revision", status.revision}, {"state", status.state},   {"error", status.error},
      {"warning", status.warning},   {"width", status.width},   {"height", status.height},
      {"codec", status.codec},
  };

  std::error_code ec;
  const std::filesystem::path target(path);
  if (target.has_parent_path())
  {
    std::filesystem::create_directories(target.parent_path(), ec);
    if (ec)
      return false;
  }

  const std::string temp = path + ".tmp";
  {
    std::ofstream out(temp, std::ios::trunc);
    if (!out)
    {
      std::filesystem::remove(temp, ec);
      return false;
    }
    out << json.dump(2) << '\n';
    // Explizit schließen und prüfen: Kleine Schreibvorgänge landen nur im Puffer und erreichen
    // die Datei erst beim Schließen, ein Fehler dort (z. B. voller Datenträger) bliebe sonst unbemerkt.
    out.close();
    if (!out)
    {
      std::filesystem::remove(temp, ec);
      return false;
    }
  }

  std::filesystem::rename(temp, target, ec);
  if (ec)
  {
    std::filesystem::remove(temp, ec);
    return false;
  }
  return true;
}

} // namespace partyvideo
