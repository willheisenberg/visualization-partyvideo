#pragma once

#include "core/VideoFrame.h"

#include <cstdint>
#include <string>

struct AVCodecContext;
struct AVFormatContext;
struct AVFrame;
struct AVPacket;
struct SwsContext;

namespace partyvideo
{

enum class SourceError
{
  None,
  FileNotFound,
  OpenFailed,
  NoVideoStream,
  UnsupportedCodec,
  DecodeFailed
};

// Fehlercode für renderer.json (Spec §5.2); "" für None.
const char* ErrorCode(SourceError error);

struct SourceInfo
{
  int width = 0;
  int height = 0;
  std::string codec;
  double frameSeconds = 0.04; // Bilddauer aus der Bildrate, ersatzweise 25 fps
};

// Liest den besten Videostream einer lokalen Datei mit FFmpeg und liefert Bilder als YUV 4:2:0.
// Am Dateiende geht es nahtlos von vorn weiter; mediaSeconds steigt dabei weiter an.
// Nicht thread-sicher: nur der Worker-Thread benutzt eine Instanz.
class VideoSource
{
public:
  static constexpr int kMaxConsecutiveErrors = 50;
  static constexpr int kDecoderThreads = 3;

  VideoSource() = default;
  ~VideoSource();
  VideoSource(const VideoSource&) = delete;
  VideoSource& operator=(const VideoSource&) = delete;

  // Schließt eine offene Quelle und öffnet path. Bei Fehler bleibt die Quelle geschlossen.
  SourceError Open(const std::string& path);
  void Close();
  bool IsOpen() const { return m_codec != nullptr; }
  const SourceInfo& Info() const { return m_info; }

  // Nächstes Bild. false ohne offene Quelle oder bei dauerhaftem Fehler (dann LastError()).
  bool NextFrame(VideoFrame& frame);
  // Aufholen bei Verspätung: Bilder ohne Referenz überspringen, solange aktiv.
  void SetSkipNonReference(bool skip);

  SourceError LastError() const { return m_error; }
  int LoopCount() const { return m_loopCount; }

private:
  SourceError Fail(SourceError error);
  bool CountDecodeError();
  bool RestartFromBeginning();
  double NextMediaSeconds();
  bool ConvertFrame(VideoFrame& out);

  std::string m_path;
  SourceInfo m_info;
  SourceError m_error = SourceError::None;

  AVFormatContext* m_format = nullptr;
  AVCodecContext* m_codec = nullptr;
  AVPacket* m_packet = nullptr;
  AVFrame* m_decoded = nullptr;
  SwsContext* m_sws = nullptr;
  // Parameter, für die m_sws gebaut wurde (siehe ConvertFrame).
  int m_swsFormat = -1; // AV_PIX_FMT_NONE
  int m_swsWidth = 0;
  int m_swsHeight = 0;
  int m_streamIndex = -1;
  double m_timeBase = 0.0;

  int64_t m_firstPts = 0;
  bool m_haveFirstPts = false;
  double m_loopOffset = 0.0;
  double m_lastMediaSeconds = 0.0;
  bool m_haveFrame = false;
  bool m_frameInThisLoop = false;
  bool m_draining = false;
  bool m_skipNonReference = false; // überlebt das Neuöffnen in RestartFromBeginning
  int m_loopCount = 0;
  int m_consecutiveErrors = 0;
};

} // namespace partyvideo
