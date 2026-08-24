import QtQuick

// Lluvia digital, en la GPU.
//
// Es un unico ShaderEffect a pantalla completa: el trabajo lo hace
// matrix.frag.qsb y aqui solo se le pasan el reloj, el tamano y los colores.
// La version anterior de esto dibujaba en un Canvas desde QML y no daba el
// pego: repintar celda a celda obliga a elegir entre pocos caracteres o
// quemar CPU, y la estela nunca quedaba bien.
//
// El shader viene de bjarneo/quickshell (MIT), con los glifos cambiados por el
// atlas de katakana reales de ttfx. Ver matrix.frag.
//
// running=false para el Timer: sin cambios de propiedad el ShaderEffect no
// vuelve a renderizar, asi que la GPU queda a cero y la ultima imagen se
// congela en pantalla.

Item {
  id: root

  property bool running: true
  // Fotogramas por segundo. No se usa FrameAnimation a proposito: iria al
  // refresco del monitor (144 Hz en el externo) y esto es un fondo.
  property int fps: 30
  // Alto de celda en px logicos. 32 es el paso de fila del screensaver real
  // (64 px nativos en un panel a escala 2); el shader saca el ancho de aqui.
  property real cellHeight: 32

  // Los de `ttfx matrix`: --highlight-color y --rain-color-gradient.
  property color bgColor: "#000000"
  property color headColor: "#dbffdb"
  property color rainA: "#92be92"
  property color rainB: "#185318"

  property real elapsed: 0

  Image {
    id: atlasImage
    source: Qt.resolvedUrl("glifos.png")
    visible: false
    smooth: true
  }

  ShaderEffect {
    anchors.fill: parent
    fragmentShader: Qt.resolvedUrl("matrix.frag.qsb")

    // Los nombres tienen que coincidir con los del bloque uniform del shader.
    property real iTime: root.elapsed
    property vector2d iResolution: Qt.vector2d(width, height)
    property color colBg: root.bgColor
    property color colHead: root.headColor
    property color colRainA: root.rainA
    property color colRainB: root.rainB
    property real cellH: root.cellHeight
    property variant atlas: atlasImage
  }

  Timer {
    running: root.running
    interval: Math.max(8, Math.round(1000 / root.fps))
    repeat: true
    onTriggered: root.elapsed += interval / 1000
  }
}
