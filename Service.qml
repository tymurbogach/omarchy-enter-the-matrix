import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.UPower
import QtQuick

// El plugin del pack Matrix: la misma lluvia en el escritorio y en el
// salvapantallas.
//
// Es aditivo a proposito. No clona ni desactiva omarchy.background: pinta en su
// propia superficie layer-shell por encima del fondo (WlrLayer.Bottom) y deja
// pasar los clics con `mask: Region {}`, igual que hace el propio Omarchy en
// plugins/osd/Osd.qml y plugins/bar/Bar.qml. El fondo de Omarchy sigue vivo
// debajo, con sus transiciones de tema intactas.
//
// El salvapantallas es la MISMA MatrixRain en WlrLayer.Overlay. Antes esto era
// `ttfx` dentro de una terminal, o sea otro programa dibujando otra lluvia; de
// ahi que no cuadrase con el fondo ni con el lock. Con `omarchy toggle
// screensaver-off` puesto, omarchy-launch-screensaver se rinde solo y aqui
// dibujamos nosotros.

Item {
  id: root

  // omarchy-shell inyecta esto en cualquier plugin de servicio, tambien los de
  // terceros (shell.qml:306). De aqui salen los tiempos de idle configurados.
  property var shell: null

  readonly property string home: Quickshell.env("HOME")
  readonly property string configPath: home + "/.config/omarchy/matrix.json"
  readonly property string backgroundLink: home + "/.local/state/omarchy/current/background"

  // --- ajustes propios --------------------------------------------------
  // Viven en matrix.json y no en shell.json a proposito: `omarchy refresh
  // shell` reescribe shell.json entero y se llevaria por delante estas dos.
  property bool wantWallpaper: true
  property bool wantScreensaver: true

  // --- que fondo esta puesto --------------------------------------------
  // La lluvia se elige como un fondo mas del carrusel. 0-lluvia-viva.png es un
  // fotograma fijo de este mismo shader: sirve de miniatura, de marcador y de
  // respaldo si el plugin no esta activo.
  readonly property string liveMarker: "0-lluvia-viva.png"
  property string currentBackground: ""
  readonly property bool rainIsBackground: String(currentBackground).indexOf(liveMarker) >= 0

  // --- lo que sabe el resto de la shell ---------------------------------
  // Buscar por sufijo y no por id exacto: un clon de omarchy.lock se llama
  // <usuario>.lock, y el pack instala justo ese clon.
  function serviceLike(suffix, property, fallback) {
    try {
      var services = shell ? shell._services : null
      if (!services) return fallback
      for (var id in services) {
        if (String(id).indexOf(suffix) !== String(id).length - suffix.length) continue
        var instance = services[id]
        if (instance && (property in instance)) return instance[property]
      }
    } catch (e) {}
    return fallback
  }

  // Con la sesion bloqueada manda la WlSessionLock del lock, que por protocolo
  // tapa cualquier capa. Seguir dibujando debajo solo gastaria GPU.
  readonly property bool sessionLocked: serviceLike(".lock", "locked", false)
  // Respetar "stay awake" es lo mismo que hace el idle de Omarchy: si el
  // usuario ha pedido no dormir, tampoco queremos salvapantallas.
  readonly property bool idleAllowed: serviceLike(".idle", "idleEnabled", true)

  readonly property int screensaverSeconds: {
    var idle = shell && shell.shellConfig && shell.shellConfig.idle ? shell.shellConfig.idle : ({})
    var seconds = Number(idle.screensaver)
    return (isFinite(seconds) && seconds > 0) ? Math.round(seconds) : 150
  }

  // El salvapantallas se rinde en cuanto entra el bloqueo: si idle.lock es igual
  // o menor que idle.screensaver, no llegamos a asomar.
  property bool screensaverActive: false

  function applyConfig(raw) {
    var parsed = ({})
    try { parsed = JSON.parse(raw || "{}") || ({}) } catch (e) { parsed = ({}) }
    root.wantWallpaper = parsed.wallpaper !== false
    root.wantScreensaver = parsed.screensaver !== false
  }

  function dismissScreensaver() {
    if (!root.screensaverActive) return
    root.screensaverActive = false
  }

  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    printErrors: false
    onLoaded: root.applyConfig(text())
    // Sin archivo, el pack esta entero: es lo que deja instalar.sh y es lo que
    // alguien espera despues de `omarchy plugin add`.
    onLoadFailed: root.applyConfig("{}")
    onFileChanged: reload()
  }

  // El enlace del fondo actual es un symlink que cambia bajo nuestros pies, asi
  // que no vale un FileView. Se relee al arrancar, por IPC (lo llama
  // omarchy-matrix) y en un sondeo lento como red de seguridad, porque la IPC
  // `background refresh` de Omarchy no es nuestra y no podemos engancharnos.
  Process {
    id: readLink
    command: ["readlink", "-f", root.backgroundLink]
    stdout: StdioCollector {
      onStreamFinished: root.currentBackground = String(text || "").trim()
    }
  }

  function refreshBackground() {
    if (!readLink.running) readLink.running = true
  }

  Timer {
    interval: 3000
    repeat: true
    running: true
    onTriggered: root.refreshBackground()
  }

  IpcHandler {
    target: "matrix"

    function refresh(): void {
      root.refreshBackground()
      configFile.reload()
    }

    function status(): string {
      return JSON.stringify({
        wallpaper: root.wantWallpaper,
        screensaver: root.wantScreensaver,
        rainIsBackground: root.rainIsBackground,
        background: root.currentBackground,
        screensaverActive: root.screensaverActive,
        screensaverSeconds: root.screensaverSeconds,
        locked: root.sessionLocked
      })
    }

    // Para probar el salvapantallas sin esperar los minutos de idle.
    function screensaver(action: string): string {
      if (action === "stop") { root.dismissScreensaver(); return "stopped" }
      root.screensaverActive = root.wantScreensaver
      return root.screensaverActive ? "started" : "disabled"
    }
  }

  IdleMonitor {
    id: idleMonitor
    enabled: root.wantScreensaver && root.idleAllowed && !root.sessionLocked
    timeout: root.screensaverSeconds
    respectInhibitors: true
    onIsIdleChanged: {
      if (isIdle) root.screensaverActive = true
      else root.dismissScreensaver()
    }
  }

  Component.onCompleted: root.refreshBackground()

  // --- capa 1: el fondo vivo -------------------------------------------
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: wallpaperPanel
      required property var modelData

      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      visible: root.wantWallpaper && root.rainIsBackground && !root.sessionLocked

      // Bottom y no Background: el orden dentro de una misma capa depende del
      // orden de creacion, y ahi no queremos jugarnosla contra
      // omarchy.background. Bottom esta por encima del fondo y por debajo de
      // toda ventana, que es exactamente el sitio.
      WlrLayershell.namespace: "matrix-rain-wallpaper"
      WlrLayershell.layer: WlrLayer.Bottom
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      // Region vacia: el compositor nos saca del reparto de entrada y los clics
      // llegan al escritorio de Omarchy, que es quien abre su menu.
      mask: Region {}

      // Cuantas ventanas hay en el espacio activo DE ESTA pantalla. El panel ya
      // es por pantalla, asi que el freno tambien lo es.
      readonly property int windowsHere: {
        try {
          var monitors = Hyprland.monitors.values
          for (var i = 0; i < monitors.length; i++) {
            if (monitors[i].name !== wallpaperPanel.modelData.name) continue
            var workspace = monitors[i].activeWorkspace
            if (!workspace || !workspace.lastIpcObject) return 0
            return workspace.lastIpcObject.windows || 0
          }
        } catch (e) {
          // Si la forma del objeto IPC cambia, mejor pasarse de conservador y
          // dar por hecho que hay algo tapando.
          try { return ToplevelManager.toplevels.values.length } catch (e2) { return 1 }
        }
        return 0
      }

      MatrixRain {
        anchors.fill: parent
        // Con cargador llueve siempre; con bateria, solo mientras se vea el
        // escritorio. Abrir cualquier ventana lo congela y la GPU baja a cero.
        running: wallpaperPanel.visible && (!UPower.onBattery || wallpaperPanel.windowsHere === 0)
      }
    }
  }

  // --- capa 2: el salvapantallas ---------------------------------------
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: screensaverPanel
      required property var modelData

      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      color: "black"
      visible: root.screensaverActive && root.wantScreensaver && !root.sessionLocked

      WlrLayershell.namespace: "matrix-rain-screensaver"
      WlrLayershell.layer: WlrLayer.Overlay
      // Exclusivo mientras se ve: hace falta el teclado para poder salir con
      // cualquier tecla, como hacia la terminal del salvapantallas de Omarchy.
      WlrLayershell.keyboardFocus: screensaverPanel.visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore

      MatrixRain {
        anchors.fill: parent
        running: screensaverPanel.visible
      }

      // Cualquier senal de vida lo cierra. El IdleMonitor tambien lo haria solo,
      // pero esto responde al primer movimiento en vez de al siguiente tick.
      //
      // Con la gracia: la superficie aparece justo debajo del cursor, asi que el
      // compositor le manda un evento de posicion nada mas mapearla. Sin esto el
      // salvapantallas se cerraba solo en el mismo fotograma en que salia.
      Timer {
        id: gracia
        interval: 400
        repeat: false
        running: screensaverPanel.visible
      }

      MouseArea {
        id: despertador
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.AllButtons
        // Punto de referencia: el raton tiene que moverse de verdad, no solo
        // entrar en la superficie recien creada.
        property real desdeX: -1
        property real desdeY: -1

        function despertar() {
          if (gracia.running) return
          root.dismissScreensaver()
        }

        onVisibleChanged: { desdeX = -1; desdeY = -1 }
        onClicked: despertar()
        onWheel: despertar()
        onPositionChanged: function (mouse) {
          if (desdeX < 0) { desdeX = mouse.x; desdeY = mouse.y; return }
          if (Math.abs(mouse.x - desdeX) + Math.abs(mouse.y - desdeY) < 8) return
          despertar()
        }
      }

      Item {
        anchors.fill: parent
        focus: screensaverPanel.visible
        Keys.onPressed: function (event) {
          event.accepted = true
          despertador.despertar()
        }
      }
    }
  }
}
