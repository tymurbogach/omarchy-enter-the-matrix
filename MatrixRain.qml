import QtQuick

// Digital rain, on the GPU.
//
// It is a single full-screen ShaderEffect: matrix.frag.qsb does the work and
// all that happens here is handing it the clock, the size and the colours.
// An earlier version drew into a QML Canvas and never convinced: repainting
// cell by cell forces a choice between too few characters and burning CPU, and
// the trail never looked right.
//
// The shader comes from bjarneo/quickshell (MIT), with its procedural glyphs
// swapped for an atlas of the real katakana ttfx uses. See rain/matrix.frag.
//
// running=false stops the clock: with no property changing, the ShaderEffect
// does not render again, so the GPU drops to zero and the last frame stays
// frozen on screen.

Item {
  id: root

  property bool running: true
  // Frames per second at which the shader's clock advances.
  property int fps: 30
  // Cell height in logical px. 32 is the row pitch of the real screensaver
  // (64 native px on a panel at scale 2); the shader derives the width from it.
  property real cellHeight: 32

  // Straight from `ttfx matrix`: --highlight-color and --rain-color-gradient.
  property color bgColor: "#000000"
  property color headColor: "#dbffdb"
  property color rainA: "#92be92"
  property color rainB: "#185318"

  property real elapsed: 0

  Image {
    id: atlasImage
    source: Qt.resolvedUrl("glyphs.png")
    visible: false
    smooth: true
  }

  ShaderEffect {
    anchors.fill: parent
    fragmentShader: Qt.resolvedUrl("matrix.frag.qsb")

    // The names have to match those in the shader's uniform block.
    property real iTime: root.elapsed
    // `size` and not `vector2d`: that is the type Qt maps a vec2 to inside a
    // ShaderEffect without surprises.
    property size iResolution: Qt.size(width, height)
    property color colBg: root.bgColor
    property color colHead: root.headColor
    property color colRainA: root.rainA
    property color colRainB: root.rainB
    property real cellH: root.cellHeight
    property variant atlas: atlasImage
  }

  // FrameAnimation and not Timer. With a Timer the clock did advance (proved
  // with logs: elapsed kept rising) but the ShaderEffect never repainted, so
  // the rain came out drawn and frozen. FrameAnimation is wired into the render
  // loop, which is exactly what it takes for a new frame to appear.
  //
  // Since it runs at the monitor's refresh rate (144 Hz on the external screen)
  // and this is a background, time is accumulated but only published to
  // `elapsed` at `fps`: the shader sees 30 steps per second, not 144.
  FrameAnimation {
    id: clock
    running: root.running
    property real accumulated: 0
    onTriggered: {
      accumulated += frameTime
      var step = 1 / Math.max(1, root.fps)
      if (accumulated >= step) {
        root.elapsed += accumulated
        accumulated = 0
      }
    }
  }
}
