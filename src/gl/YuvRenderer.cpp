#include "gl/YuvRenderer.h"

#include "core/ColorConversion.h"
#include "core/Letterbox.h"

namespace partyvideo
{

namespace
{

const char* const kVertexShader = R"(#version 300 es
layout(location = 0) in vec2 aPosition;
layout(location = 1) in vec2 aTexCoord;
out vec2 vTexCoord;
void main()
{
  vTexCoord = aTexCoord;
  gl_Position = vec4(aPosition, 0.0, 1.0);
}
)";

const char* const kFragmentShader = R"(#version 300 es
precision highp float;
in vec2 vTexCoord;
out vec4 fragColor;
uniform sampler2D uTextureY;
uniform sampler2D uTextureU;
uniform sampler2D uTextureV;
uniform mat3 uYuvToRgb;
uniform vec3 uOffset;
uniform vec2 uLumaScale;
uniform vec2 uChromaScale;
void main()
{
  vec3 yuv = vec3(texture(uTextureY, vTexCoord * uLumaScale).r,
                  texture(uTextureU, vTexCoord * uChromaScale).r,
                  texture(uTextureV, vTexCoord * uChromaScale).r);
  fragColor = vec4(clamp(uYuvToRgb * (yuv - uOffset), 0.0, 1.0), 1.0);
}
)";

// Sichert den GL-Zustand, den Kodi um Render() herum nicht selbst wiederherstellt, und setzt ihn zurück.
class GlStateGuard
{
public:
  GlStateGuard()
  {
    glGetIntegerv(GL_CURRENT_PROGRAM, &m_program);
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &m_vertexArray);
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &m_arrayBuffer);
    glGetIntegerv(GL_ACTIVE_TEXTURE, &m_activeTexture);
    glGetIntegerv(GL_UNPACK_ALIGNMENT, &m_unpackAlignment);
    glGetIntegerv(GL_UNPACK_ROW_LENGTH, &m_unpackRowLength);
    glGetIntegerv(GL_UNPACK_SKIP_ROWS, &m_unpackSkipRows);
    glGetIntegerv(GL_UNPACK_SKIP_PIXELS, &m_unpackSkipPixels);
    glGetIntegerv(GL_PIXEL_UNPACK_BUFFER_BINDING, &m_unpackBuffer);
    glGetFloatv(GL_COLOR_CLEAR_VALUE, m_clearColor.data());
    m_blend = glIsEnabled(GL_BLEND);
    m_depthTest = glIsEnabled(GL_DEPTH_TEST);
    m_cullFace = glIsEnabled(GL_CULL_FACE);
    m_scissorTest = glIsEnabled(GL_SCISSOR_TEST);
    for (int unit = 0; unit < 3; ++unit)
    {
      glActiveTexture(GL_TEXTURE0 + unit);
      glGetIntegerv(GL_TEXTURE_BINDING_2D, &m_textures[unit]);
    }
    glDisable(GL_BLEND);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
  }

  ~GlStateGuard()
  {
    for (int unit = 2; unit >= 0; --unit)
    {
      glActiveTexture(GL_TEXTURE0 + unit);
      glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(m_textures[unit]));
    }
    glActiveTexture(static_cast<GLenum>(m_activeTexture));
    glPixelStorei(GL_UNPACK_ALIGNMENT, m_unpackAlignment);
    glPixelStorei(GL_UNPACK_ROW_LENGTH, m_unpackRowLength);
    glPixelStorei(GL_UNPACK_SKIP_ROWS, m_unpackSkipRows);
    glPixelStorei(GL_UNPACK_SKIP_PIXELS, m_unpackSkipPixels);
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, static_cast<GLuint>(m_unpackBuffer));
    glBindBuffer(GL_ARRAY_BUFFER, static_cast<GLuint>(m_arrayBuffer));
    glBindVertexArray(static_cast<GLuint>(m_vertexArray));
    glUseProgram(static_cast<GLuint>(m_program));
    glClearColor(m_clearColor[0], m_clearColor[1], m_clearColor[2], m_clearColor[3]);
    SetEnabled(GL_BLEND, m_blend);
    SetEnabled(GL_DEPTH_TEST, m_depthTest);
    SetEnabled(GL_CULL_FACE, m_cullFace);
    SetEnabled(GL_SCISSOR_TEST, m_scissorTest);
  }

  GlStateGuard(const GlStateGuard&) = delete;
  GlStateGuard& operator=(const GlStateGuard&) = delete;

private:
  static void SetEnabled(GLenum capability, GLboolean enabled)
  {
    if (enabled)
      glEnable(capability);
    else
      glDisable(capability);
  }

  GLint m_program = 0;
  GLint m_vertexArray = 0;
  GLint m_arrayBuffer = 0;
  GLint m_activeTexture = GL_TEXTURE0;
  GLint m_unpackAlignment = 4;
  GLint m_unpackRowLength = 0;
  GLint m_unpackSkipRows = 0;
  GLint m_unpackSkipPixels = 0;
  GLint m_unpackBuffer = 0;
  std::array<GLfloat, 4> m_clearColor{};
  GLboolean m_blend = GL_FALSE;
  GLboolean m_depthTest = GL_FALSE;
  GLboolean m_cullFace = GL_FALSE;
  GLboolean m_scissorTest = GL_FALSE;
  std::array<GLint, 3> m_textures{};
};

} // namespace

YuvRenderer::~YuvRenderer()
{
  if (m_textures[0] != 0)
    glDeleteTextures(3, m_textures.data());
  if (m_vertexBuffer != 0)
    glDeleteBuffers(1, &m_vertexBuffer);
  if (m_vertexArray != 0)
    glDeleteVertexArrays(1, &m_vertexArray);
  if (m_program != 0)
    glDeleteProgram(m_program);
}

GLuint YuvRenderer::CompileShader(GLenum type, const char* source)
{
  GLuint shader = glCreateShader(type);
  glShaderSource(shader, 1, &source, nullptr);
  glCompileShader(shader);
  GLint ok = GL_FALSE;
  glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
  if (ok != GL_TRUE)
  {
    std::array<char, 1024> log{};
    glGetShaderInfoLog(shader, static_cast<GLsizei>(log.size()), nullptr, log.data());
    m_lastError = std::string("Shader-Fehler: ") + log.data();
    glDeleteShader(shader);
    return 0;
  }
  return shader;
}

bool YuvRenderer::Init()
{
  if (m_program != 0)
    return true;

  const GLuint vertex = CompileShader(GL_VERTEX_SHADER, kVertexShader);
  if (vertex == 0)
    return false;
  const GLuint fragment = CompileShader(GL_FRAGMENT_SHADER, kFragmentShader);
  if (fragment == 0)
  {
    glDeleteShader(vertex);
    return false;
  }

  GLuint program = glCreateProgram();
  glAttachShader(program, vertex);
  glAttachShader(program, fragment);
  glLinkProgram(program);
  glDeleteShader(vertex);
  glDeleteShader(fragment);

  GLint ok = GL_FALSE;
  glGetProgramiv(program, GL_LINK_STATUS, &ok);
  if (ok != GL_TRUE)
  {
    std::array<char, 1024> log{};
    glGetProgramInfoLog(program, static_cast<GLsizei>(log.size()), nullptr, log.data());
    m_lastError = std::string("Link-Fehler: ") + log.data();
    glDeleteProgram(program);
    return false;
  }

  GlStateGuard guard;
  m_program = program;
  glUseProgram(m_program);
  glUniform1i(glGetUniformLocation(m_program, "uTextureY"), 0);
  glUniform1i(glGetUniformLocation(m_program, "uTextureU"), 1);
  glUniform1i(glGetUniformLocation(m_program, "uTextureV"), 2);
  m_uniformMatrix = glGetUniformLocation(m_program, "uYuvToRgb");
  m_uniformOffset = glGetUniformLocation(m_program, "uOffset");
  m_uniformLumaScale = glGetUniformLocation(m_program, "uLumaScale");
  m_uniformChromaScale = glGetUniformLocation(m_program, "uChromaScale");

  glGenVertexArrays(1, &m_vertexArray);
  glGenBuffers(1, &m_vertexBuffer);
  glBindVertexArray(m_vertexArray);
  glBindBuffer(GL_ARRAY_BUFFER, m_vertexBuffer);
  glBufferData(GL_ARRAY_BUFFER, 16 * sizeof(GLfloat), nullptr, GL_DYNAMIC_DRAW);
  glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), nullptr);
  glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat),
                        reinterpret_cast<const void*>(2 * sizeof(GLfloat)));
  glEnableVertexAttribArray(0);
  glEnableVertexAttribArray(1);

  glGenTextures(3, m_textures.data());
  for (int plane = 0; plane < 3; ++plane)
  {
    glActiveTexture(GL_TEXTURE0 + plane);
    glBindTexture(GL_TEXTURE_2D, m_textures[plane]);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  }
  return true;
}

void YuvRenderer::Upload(const VideoFrame& frame)
{
  if (m_program == 0 || frame.width <= 0 || frame.height <= 0)
    return;

  m_hasFrame = false;
  m_lastError.clear();
  GLint maxTextureSize = 0;
  glGetIntegerv(GL_MAX_TEXTURE_SIZE, &maxTextureSize);
  const std::array<int, 3> heights{frame.height, ChromaHeight(frame.height), ChromaHeight(frame.height)};
  const std::array<int, 3> widths{frame.width, ChromaWidth(frame.width), ChromaWidth(frame.width)};
  for (int plane = 0; plane < 3; ++plane)
  {
    if (frame.strides[plane] > maxTextureSize || heights[plane] > maxTextureSize)
    {
      m_lastError = "Videobild überschreitet GL_MAX_TEXTURE_SIZE";
      return;
    }
    const size_t needed = static_cast<size_t>(frame.strides[plane]) * heights[plane];
    if (frame.strides[plane] < widths[plane] || frame.planes[plane].size() < needed)
      return; // unvollständiges Bild nicht hochladen
  }

  GlStateGuard guard;
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
  glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
  glPixelStorei(GL_UNPACK_SKIP_ROWS, 0);
  glPixelStorei(GL_UNPACK_SKIP_PIXELS, 0);
  glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0);
  for (int plane = 0; plane < 3; ++plane)
  {
    glActiveTexture(GL_TEXTURE0 + plane);
    glBindTexture(GL_TEXTURE_2D, m_textures[plane]);
    const std::array<int, 2> size{frame.strides[plane], heights[plane]};
    if (m_textureSizes[plane] != size)
    {
      glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, size[0], size[1], 0, GL_RED, GL_UNSIGNED_BYTE,
                   frame.planes[plane].data());
      m_textureSizes[plane] = size;
    }
    else
    {
      glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, size[0], size[1], GL_RED, GL_UNSIGNED_BYTE,
                      frame.planes[plane].data());
    }
  }

  m_hasFrame = true;
  m_width = frame.width;
  m_height = frame.height;
  m_strides = frame.strides;
  m_matrix = frame.matrix;
  m_fullRange = frame.fullRange;
  m_sarNum = frame.sarNum;
  m_sarDen = frame.sarDen;
}

void YuvRenderer::Draw()
{
  GlStateGuard guard;

  // Kodi hat Viewport und Scissor-Box auf die Visualisierungsfläche gesetzt.
  glEnable(GL_SCISSOR_TEST);
  glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT);

  if (m_program == 0 || !m_hasFrame)
    return;

  std::array<GLint, 4> viewport{};
  glGetIntegerv(GL_VIEWPORT, viewport.data());
  const NdcRect rect = FitVideo(viewport[2], viewport[3], m_width, m_height, m_sarNum, m_sarDen);

  // x, y, u, v – Texturzeile 0 ist die oberste Bildzeile.
  const std::array<GLfloat, 16> vertices{
      rect.left,  rect.bottom, 0.0f, 1.0f, //
      rect.right, rect.bottom, 1.0f, 1.0f, //
      rect.left,  rect.top,    0.0f, 0.0f, //
      rect.right, rect.top,    1.0f, 0.0f, //
  };

  const YuvToRgb conversion = MakeYuvToRgb(m_matrix, m_fullRange);

  glUseProgram(m_program);
  glUniformMatrix3fv(m_uniformMatrix, 1, GL_FALSE, conversion.matrix.data());
  glUniform3fv(m_uniformOffset, 1, conversion.offset.data());
  glUniform2f(m_uniformLumaScale, static_cast<GLfloat>(m_width) / m_strides[0], 1.0f);
  glUniform2f(m_uniformChromaScale, static_cast<GLfloat>(ChromaWidth(m_width)) / m_strides[1], 1.0f);

  glBindVertexArray(m_vertexArray);
  glBindBuffer(GL_ARRAY_BUFFER, m_vertexBuffer);
  glBufferSubData(GL_ARRAY_BUFFER, 0, static_cast<GLsizeiptr>(sizeof(vertices)), vertices.data());

  for (int plane = 0; plane < 3; ++plane)
  {
    glActiveTexture(GL_TEXTURE0 + plane);
    glBindTexture(GL_TEXTURE_2D, m_textures[plane]);
  }
  glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
}

} // namespace partyvideo
