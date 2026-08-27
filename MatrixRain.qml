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
  // Fotogramas por segundo a los que avanza el reloj del shader.
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
    // `size` y no `vector2d`: es el tipo con el que Qt mapea un vec2 en un
    // ShaderEffect sin sorpresas.
    property size iResolution: Qt.size(width, height)
    property color colBg: root.bgColor
    property color colHead: root.headColor
    property color colRainA: root.rainA
    property color colRainB: root.rainB
    property real cellH: root.cellHeight
    property variant atlas: atlasImage
  }

  // FrameAnimation y no Timer. Con un Timer el reloj avanzaba (comprobado con
  // logs: elapsed subia) pero el ShaderEffect no volvia a repintar, asi que la
  // lluvia salia dibujada y congelada. FrameAnimation va enganchado al bucle de
  // render, que es justo lo que hace falta para que el fotograma nuevo salga.
  //
  // Como corre al refresco del monitor (144 Hz en el externo) y esto es un
  // fondo, se acumula el tiempo pero solo se publica en `elapsed` a `fps`: el
  // shader ve 30 pasos por segundo y no 144.
  FrameAnimation {
    id: reloj
    running: root.running
    property real acumulado: 0
    onTriggered: {
      acumulado += frameTime
      var paso = 1 / Math.max(1, root.fps)
      if (acumulado >= paso) {
        root.elapsed += acumulado
        acumulado = 0
      }
    }
  }
}
