#include "core/VideoSource.h"

#include "core/ColorConversion.h"

#include <array>
#include <cstring>

#include <sys/stat.h>

extern "C"
{
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/imgutils.h>
#include <libavutil/pixdesc.h>
#include <libswscale/swscale.h>
}

namespace partyvideo
{

namespace
{

constexpr int kSwsAlignment = 32; // swscale darf mit SIMD über die sichtbare Zeilenbreite hinaus schreiben

ColorSpaceHint HintFromFfmpeg(int colorspace)
{
  switch (colorspace)
  {
    case AVCOL_SPC_BT709:
      return ColorSpaceHint::Bt709;
    case AVCOL_SPC_BT470BG:
    case AVCOL_SPC_SMPTE170M:
    case AVCOL_SPC_FCC:
      return ColorSpaceHint::Bt601;
    default:
      return ColorSpaceHint::Unknown;
  }
}

bool IsFullRangeFormat(int format)
{
  return format == AV_PIX_FMT_YUVJ420P || format == AV_PIX_FMT_YUVJ422P || format == AV_PIX_FMT_YUVJ444P ||
         format == AV_PIX_FMT_YUVJ440P || format == AV_PIX_FMT_YUVJ411P;
}

} // namespace

const char* ErrorCode(SourceError error)
{
  switch (error)
  {
    case SourceError::None:
      return "";
    case SourceError::FileNotFound:
      return "file_not_found";
    case SourceError::OpenFailed:
      return "open_failed";
    case SourceError::NoVideoStream:
      return "no_video_stream";
    case SourceError::UnsupportedCodec:
      return "unsupported_codec";
    case SourceError::DecodeFailed:
      return "decode_failed";
  }
  return "decode_failed";
}

VideoSource::~VideoSource()
{
  Close();
}

void VideoSource::Close()
{
  sws_freeContext(m_sws);
  m_sws = nullptr;
  m_swsFormat = AV_PIX_FMT_NONE;
  m_swsWidth = 0;
  m_swsHeight = 0;
  av_frame_free(&m_decoded);
  av_packet_free(&m_packet);
  avcodec_free_context(&m_codec);
  avformat_close_input(&m_format);

  m_info = SourceInfo{};
  m_error = SourceError::None;
  m_streamIndex = -1;
  m_timeBase = 0.0;
  m_firstPts = 0;
  m_haveFirstPts = false;
  m_loopOffset = 0.0;
  m_lastMediaSeconds = 0.0;
  m_haveFrame = false;
  m_frameInThisLoop = false;
  m_draining = false;
  m_skipNonReference = false;
  m_loopCount = 0;
  m_consecutiveErrors = 0;
}

SourceError VideoSource::Fail(SourceError error)
{
  Close();
  m_error = error;
  return error;
}

SourceError VideoSource::Open(const std::string& path)
{
  // skip_frame steckt nur im AVCodecContext. Close() setzt den Wunsch zurück, also
  // merken wir ihn hier und übertragen ihn am Ende auf den neuen Kontext – sonst
  // verliert ihn der Notfallpfad von RestartFromBeginning.
  const bool skipNonReference = m_skipNonReference;
  Close();
  m_path = path;

  struct stat info
  {
  };
  if (::stat(path.c_str(), &info) != 0 || !S_ISREG(info.st_mode))
    return Fail(SourceError::FileNotFound);

  if (avformat_open_input(&m_format, path.c_str(), nullptr, nullptr) < 0)
    return Fail(SourceError::OpenFailed);
  if (avformat_find_stream_info(m_format, nullptr) < 0)
    return Fail(SourceError::OpenFailed);

  const AVCodec* decoder = nullptr;
  const int index = av_find_best_stream(m_format, AVMEDIA_TYPE_VIDEO, -1, -1, &decoder, 0);
  if (index == AVERROR_STREAM_NOT_FOUND)
    return Fail(SourceError::NoVideoStream);
  if (index == AVERROR_DECODER_NOT_FOUND || (index >= 0 && decoder == nullptr))
    return Fail(SourceError::UnsupportedCodec);
  if (index < 0)
    return Fail(SourceError::OpenFailed);

  AVStream* stream = m_format->streams[index];
  if (stream->disposition & AV_DISPOSITION_ATTACHED_PIC)
    return Fail(SourceError::NoVideoStream); // nur ein Coverbild, kein Video

  m_codec = avcodec_alloc_context3(decoder);
  if (m_codec == nullptr || avcodec_parameters_to_context(m_codec, stream->codecpar) < 0)
    return Fail(SourceError::OpenFailed);
  m_codec->thread_count = kDecoderThreads;
  m_codec->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;
  m_codec->pkt_timebase = stream->time_base;
  if (avcodec_open2(m_codec, decoder, nullptr) < 0)
    return Fail(SourceError::UnsupportedCodec);

  m_packet = av_packet_alloc();
  m_decoded = av_frame_alloc();
  if (m_packet == nullptr || m_decoded == nullptr)
    return Fail(SourceError::OpenFailed);

  m_streamIndex = index;
  m_timeBase = av_q2d(stream->time_base);

  const AVRational rate = av_guess_frame_rate(m_format, stream, nullptr);
  m_info.width = m_codec->width;
  m_info.height = m_codec->height;
  m_info.codec = avcodec_get_name(decoder->id);
  m_info.frameSeconds = (rate.num > 0 && rate.den > 0) ? av_q2d(av_inv_q(rate)) : 0.04;
  SetSkipNonReference(skipNonReference);
  return SourceError::None;
}

void VideoSource::SetSkipNonReference(bool skip)
{
  m_skipNonReference = skip;
  if (m_codec != nullptr)
    m_codec->skip_frame = skip ? AVDISCARD_NONREF : AVDISCARD_DEFAULT;
}

bool VideoSource::CountDecodeError()
{
  if (++m_consecutiveErrors >= kMaxConsecutiveErrors)
  {
    Fail(SourceError::DecodeFailed);
    return false;
  }
  return true;
}

bool VideoSource::RestartFromBeginning()
{
  if (!m_frameInThisLoop)
  {
    // Ein ganzer Durchlauf ohne ein einziges Bild: die Datei ist nicht abspielbar.
    Fail(SourceError::DecodeFailed);
    return false;
  }

  // Die nächste Runde beginnt ein Bild nach dem zuletzt gelieferten.
  m_loopOffset = m_lastMediaSeconds + m_info.frameSeconds;
  m_haveFirstPts = false;
  m_frameInThisLoop = false;
  m_draining = false;
  ++m_loopCount;

  const AVStream* stream = m_format->streams[m_streamIndex];
  const int64_t start = stream->start_time != AV_NOPTS_VALUE ? stream->start_time : 0;
  if (av_seek_frame(m_format, m_streamIndex, start, AVSEEK_FLAG_BACKWARD) >= 0)
  {
    avcodec_flush_buffers(m_codec);
    return true;
  }

  // Seek nicht möglich: neu öffnen und den Schleifenzustand übernehmen.
  const std::string path = m_path;
  const double loopOffset = m_loopOffset;
  const double lastMediaSeconds = m_lastMediaSeconds;
  const int loopCount = m_loopCount;
  if (Open(path) != SourceError::None)
    return false;
  m_loopOffset = loopOffset;
  m_lastMediaSeconds = lastMediaSeconds;
  m_haveFrame = true;
  m_loopCount = loopCount;
  return true;
}

double VideoSource::NextMediaSeconds()
{
  const int64_t pts = m_decoded->best_effort_timestamp;
  double media = m_haveFrame ? m_lastMediaSeconds + m_info.frameSeconds : 0.0;
  if (pts != AV_NOPTS_VALUE)
  {
    if (!m_haveFirstPts)
    {
      m_firstPts = pts;
      m_haveFirstPts = true;
    }
    media = m_loopOffset + static_cast<double>(pts - m_firstPts) * m_timeBase;
  }
  if (m_haveFrame && media <= m_lastMediaSeconds)
    media = m_lastMediaSeconds + m_info.frameSeconds; // streng monoton halten
  return media;
}

bool VideoSource::NextFrame(VideoFrame& frame)
{
  if (m_codec == nullptr)
    return false;

  while (true)
  {
    int ret = avcodec_receive_frame(m_codec, m_decoded);
    if (ret == 0)
    {
      m_consecutiveErrors = 0;
      frame.mediaSeconds = NextMediaSeconds();
      const bool converted = ConvertFrame(frame);
      av_frame_unref(m_decoded);
      if (!converted)
      {
        Fail(SourceError::DecodeFailed);
        return false;
      }
      m_lastMediaSeconds = frame.mediaSeconds;
      m_haveFrame = true;
      m_frameInThisLoop = true;
      return true;
    }
    if (ret == AVERROR_EOF)
    {
      if (!RestartFromBeginning())
        return false;
      continue;
    }
    if (ret != AVERROR(EAGAIN))
    {
      if (!CountDecodeError())
        return false;
      continue;
    }

    // Der Decoder braucht weitere Daten.
    if (m_draining)
    {
      // Beim Leeren darf kein EAGAIN mehr kommen; wie Dateiende behandeln statt endlos zu warten.
      if (!RestartFromBeginning())
        return false;
      continue;
    }
    ret = av_read_frame(m_format, m_packet);
    if (ret < 0)
    {
      // Dateiende oder unlesbarer Rest: Decoder leeren, danach beginnt die nächste Runde.
      avcodec_send_packet(m_codec, nullptr);
      m_draining = true;
      continue;
    }
    if (m_packet->stream_index != m_streamIndex)
    {
      av_packet_unref(m_packet);
      continue;
    }
    ret = avcodec_send_packet(m_codec, m_packet);
    av_packet_unref(m_packet);
    if (ret < 0 && ret != AVERROR(EAGAIN) && !CountDecodeError())
      return false;
  }
}

bool VideoSource::ConvertFrame(VideoFrame& out)
{
  const AVFrame* src = m_decoded;
  const int width = src->width;
  const int height = src->height;
  if (width <= 0 || height <= 0)
    return false;

  const std::array<int, 3> planeWidth{width, ChromaWidth(width), ChromaWidth(width)};
  const std::array<int, 3> planeHeight{height, ChromaHeight(height), ChromaHeight(height)};
  const bool direct = src->format == AV_PIX_FMT_YUV420P || src->format == AV_PIX_FMT_YUVJ420P;

  out.width = width;
  out.height = height;

  if (direct)
  {
    for (int p = 0; p < 3; ++p)
    {
      const int stride = src->linesize[p];
      if (stride < planeWidth[p])
        return false; // negative bzw. zu kurze Zeilen werden nicht unterstützt
      out.strides[p] = stride;
      out.planes[p].resize(static_cast<size_t>(stride) * planeHeight[p]);
      for (int y = 0; y < planeHeight[p]; ++y)
        std::memcpy(out.planes[p].data() + static_cast<size_t>(y) * stride,
                    src->data[p] + static_cast<ptrdiff_t>(y) * stride, static_cast<size_t>(stride));
    }
    out.fullRange = src->format == AV_PIX_FMT_YUVJ420P || src->color_range == AVCOL_RANGE_JPEG;
  }
  else
  {
    // Eigener Cache statt sich auf sws_getCachedContext zu verlassen: sws_init_context
    // schreibt YUVJ-Formate intern auf ihre Nicht-J-Variante um, der Vergleich in
    // sws_getCachedContext prüft aber gegen das ursprüngliche Format. Der Cache träfe
    // deshalb bei YUVJ nie, und FFmpeg baute den Kontext samt Warnung pro Bild neu.
    if (m_sws == nullptr || src->format != m_swsFormat || width != m_swsWidth || height != m_swsHeight)
    {
      m_sws = sws_getCachedContext(m_sws, width, height, static_cast<AVPixelFormat>(src->format), width, height,
                                   AV_PIX_FMT_YUV420P, SWS_BILINEAR, nullptr, nullptr, nullptr);
      if (m_sws == nullptr)
      {
        m_swsFormat = AV_PIX_FMT_NONE;
        return false;
      }
      m_swsFormat = src->format;
      m_swsWidth = width;
      m_swsHeight = height;
    }

    std::array<uint8_t*, 4> dst{};
    std::array<int, 4> dstStride{};
    for (int p = 0; p < 3; ++p)
    {
      const int stride = FFALIGN(planeWidth[p], kSwsAlignment);
      out.strides[p] = stride;
      // Eine Zusatzzeile als Reserve für SIMD-Schreibzugriffe über das Ende hinaus.
      out.planes[p].assign(static_cast<size_t>(stride) * (planeHeight[p] + 1), 0);
      dst[p] = out.planes[p].data();
      dstStride[p] = stride;
    }
    if (sws_scale(m_sws, src->data, src->linesize, 0, height, dst.data(), dstStride.data()) != height)
      return false;
    // swscale wandelt YUVJ-Formate nach Limited Range; nur eine reine Range-Markierung bleibt Full Range.
    out.fullRange = !IsFullRangeFormat(src->format) && src->color_range == AVCOL_RANGE_JPEG;
  }

  out.matrix = ChooseMatrix(HintFromFfmpeg(src->colorspace), height);
  // av_guess_sample_aspect_ratio erwartet einen nicht-konstanten Frame.
  const AVRational sar = av_guess_sample_aspect_ratio(m_format, m_format->streams[m_streamIndex], m_decoded);
  out.sarNum = sar.num > 0 ? sar.num : 1;
  out.sarDen = sar.den > 0 ? sar.den : 1;
  return true;
}

} // namespace partyvideo
