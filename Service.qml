import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.UPower
import QtQuick

// The Matrix pack's plugin: the same rain on the desktop and as the
// screensaver.
//
// Additive on purpose. It neither clones nor disables omarchy.background: it
// draws on a layer-shell surface of its own above the wallpaper
// (WlrLayer.Bottom) and lets clicks through with `mask: Region {}`, the same
// idiom Omarchy itself uses in plugins/osd/Osd.qml and plugins/bar/Bar.qml.
// Omarchy's background stays alive underneath, theme transitions intact.
//
// The screensaver is the SAME MatrixRain on WlrLayer.Overlay. It used to be
// `ttfx` inside a terminal -- a different program drawing a different rain,
// which is why it never matched the wallpaper or the lock. With
// `omarchy toggle screensaver-off` set, omarchy-launch-screensaver bows out and
// we draw instead.

Item {
  id: root

  // omarchy-shell injects this into any service plugin, third-party ones
  // included (shell.qml:306). The configured idle timings come from here.
  property var shell: null

  readonly property string home: Quickshell.env("HOME")
  readonly property string configPath: home + "/.config/omarchy/matrix.json"
  readonly property string backgroundLink: home + "/.local/state/omarchy/current/background"

  // --- our own settings -------------------------------------------------
  // They live in matrix.json rather than shell.json on purpose: `omarchy
  // refresh shell` rewrites shell.json wholesale and would take these with it.
  property bool wantWallpaper: true
  property bool wantScreensaver: true

  // --- which background is selected --------------------------------------
  // The rain is picked like any other background in the carousel.
  // The live background is a real still from the film, and it doubles as the
  // thumbnail, as the marker, and as the fallback if the plugin is not running.
  // Matched by suffix, never by number: the carousel gets reordered (the default
  // is now a still from the film, so the rain no longer has to sort first) and
  // anything pinning "0-" silently stops raining when it does. That is exactly
  // how it broke once -- the background got selected, and nothing drew.
  readonly property string liveMarker: "-live-"
  property string currentBackground: ""
  readonly property bool rainIsBackground: String(currentBackground).indexOf(liveMarker) >= 0

  // --- what the rest of the shell knows ----------------------------------
  // Match by suffix rather than exact id: a clone of omarchy.lock is called
  // <username>.lock, and that clone is exactly what the pack installs.
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

  // While the session is locked the lock's WlSessionLock is in charge, and by
  // protocol it covers every layer. Drawing underneath would only burn GPU.
  readonly property bool sessionLocked: serviceLike(".lock", "locked", false)
  // The screensaver is finished the moment the lock comes up. Otherwise it
  // reappeared over the desktop after unlocking without anyone asking for it,
  // since moving the mouse no longer dismisses it.
  onSessionLockedChanged: if (sessionLocked) dismissScreensaver()
  // Respecting "stay awake" is what Omarchy's own idle service does: if the
  // user asked not to sleep, we do not want a screensaver either.
  readonly property bool idleAllowed: serviceLike(".idle", "idleEnabled", true)

  readonly property int screensaverSeconds: {
    var idle = shell && shell.shellConfig && shell.shellConfig.idle ? shell.shellConfig.idle : ({})
    var seconds = Number(idle.screensaver)
    return (isFinite(seconds) && seconds > 0) ? Math.round(seconds) : 150
  }

  // The screensaver gives way as soon as the lock arrives: if idle.lock is at
  // or below idle.screensaver, we never get to show at all.
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

  // Omarchy's screensaver hides the pointer while it runs and gives it back on
  // exit (bin/omarchy-screensaver), using this same command and this same
  // fallback. Doing it identically keeps the feel identical: a clean screen,
  // with no pointer floating over the rain.
  function hidePointer(hidden) {
    var value = hidden ? "true" : "false"
    Quickshell.execDetached(["bash", "-lc",
      "hyprctl eval 'hl.config({ cursor = { invisible = " + value + " } })' &>/dev/null" +
      " || hyprctl keyword cursor:invisible " + value + " &>/dev/null || true"])
  }

  // One place decides: hidden on the way in, given back on the way out, whatever
  // happens to the screensaver. Should the shell die with the pointer hidden,
  // `hyprctl keyword cursor:invisible false` brings it back.
  onScreensaverActiveChanged: hidePointer(root.screensaverActive)
  Component.onDestruction: if (root.screensaverActive) hidePointer(false)

  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    printErrors: false
    onLoaded: root.applyConfig(text())
    // With no file the pack is complete: that is what install.sh leaves behind
    // and what anyone expects after `omarchy plugin add`.
    onLoadFailed: root.applyConfig("{}")
    onFileChanged: reload()
  }

  // The current background is a symlink that moves under our feet, so a
  // FileView will not do. It is re-read at startup, over IPC (omarchy-matrix
  // calls it) and on a slow poll as a safety net, because Omarchy's own
  // `background refresh` IPC is not ours to hook into.
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

    // For testing the screensaver without waiting out the idle timer.
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
    // It only switches on. Dismissing when idle ends is what made it vanish on
    // mouse movement, and Omarchy's does not do that: its loop only watches the
    // keyboard (`read -n1`) and whether it still has focus. The mouse never
    // closes it.
    onIsIdleChanged: if (isIdle) root.screensaverActive = true
  }

  Component.onCompleted: root.refreshBackground()

  // --- layer 1: the live wallpaper ---------------------------------------
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: wallpaperPanel
      required property var modelData

      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      visible: root.wantWallpaper && root.rainIsBackground && !root.sessionLocked

      // Bottom and not Background: within one layer the order depends on
      // creation order, and that is not a race we want to run against
      // omarchy.background. Bottom sits above the wallpaper and below every
      // window, which is exactly the right place.
      WlrLayershell.namespace: "matrix-rain-wallpaper"
      WlrLayershell.layer: WlrLayer.Bottom
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      // An empty region takes us out of input routing altogether, so clicks
      // reach Omarchy's desktop, which is what opens its menu.
      mask: Region {}

      // How many windows are on the active workspace OF THIS screen. The panel
      // is already per-screen, so the brake is per-screen too.
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
          // If the shape of the IPC object ever changes, err on the cautious
          // side and assume something is covering the desktop.
          try { return ToplevelManager.toplevels.values.length } catch (e2) { return 1 }
        }
        return 0
      }

      MatrixRain {
        anchors.fill: parent
        // On mains it always rains; on battery, only while the desktop is
        // visible. Opening any window freezes it and the GPU drops to zero.
        running: wallpaperPanel.visible && (!UPower.onBattery || wallpaperPanel.windowsHere === 0)
      }
    }
  }

  // --- layer 2: the screensaver ------------------------------------------
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
      // Exclusive while visible: the keyboard is needed so any key dismisses
      // it, the way Omarchy's terminal screensaver behaves.
      WlrLayershell.keyboardFocus: screensaverPanel.visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore

      MatrixRain {
        anchors.fill: parent
        running: screensaverPanel.visible
      }

      // Swallows the mouse and ignores it. It neither dismisses nor lets the
      // event through to whatever is underneath, which is how Omarchy's
      // screensaver window behaves: a click inside does not close it, because
      // its loop only ever reads keys.
      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
      }

      // A short grace period before keys count: the surface takes focus as
      // soon as it maps, and a keystroke already in flight should not dismiss
      // it in the very frame it appears.
      Timer {
        id: grace
        interval: 400
        repeat: false
        running: screensaverPanel.visible
      }

      Item {
        anchors.fill: parent
        focus: screensaverPanel.visible
        Keys.onPressed: function (event) {
          event.accepted = true
          if (!grace.running) root.dismissScreensaver()
        }
      }
    }
  }
}
