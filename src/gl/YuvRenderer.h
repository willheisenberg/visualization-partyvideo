#pragma once

#include "core/VideoFrame.h"

#include <array>
#include <string>

#include <GLES3/gl3.h>

namespace partyvideo
{

// Zeichnet YUV-4:2:0-Bilder mit OpenGL ES 3.0 in den aktuellen Viewport (mit Letterbox).
// Alle Methoden und der Destruktor nur im GL-Thread mit aktivem Kontext aufrufen.
// Stellt den vorgefundenen GL-Zustand nach Upload() und Draw() wieder her.
class YuvRenderer
{
public:
  YuvRenderer() = default;
  ~YuvRenderer();
  YuvRenderer(const YuvRenderer&) = delete;
  YuvRenderer& operator=(const YuvRenderer&) = delete;

  bool Init();
  void Upload(const VideoFrame& frame);
  void ClearFrame() { m_hasFrame = false; }
  void Draw();
  const std::string& LastError() const { return m_lastError; }

private:
  GLuint CompileShader(GLenum type, const char* source);

  GLuint m_program = 0;
  GLuint m_vertexArray = 0;
  GLuint m_vertexBuffer = 0;
  std::array<GLuint, 3> m_textures{0, 0, 0};
  std::array<std::array<int, 2>, 3> m_textureSizes{}; // Breite (= stride), Höhe je Ebene

  GLint m_uniformMatrix = -1;
  GLint m_uniformOffset = -1;
  GLint m_uniformLumaScale = -1;
  GLint m_uniformChromaScale = -1;

  bool m_hasFrame = false;
  int m_width = 0;
  int m_height = 0;
  std::array<int, 3> m_strides{0, 0, 0};
  ColorMatrix m_matrix = ColorMatrix::Bt709;
  bool m_fullRange = false;
  int m_sarNum = 1;
  int m_sarDen = 1;

  std::string m_lastError;
};

} // namespace partyvideo
