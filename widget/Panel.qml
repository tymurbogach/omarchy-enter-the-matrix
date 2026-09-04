import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// The pack's switchboard, on the bar.
//
// It used to be a block spliced into ~/.config/omarchy/extensions/omarchy-menu.jsonc
// -- three clicks deep under Style, and the single most invasive thing the pack
// did to a file that is not its own. A bar widget is the extension point
// Omarchy's own built-ins use, so the splice is gone.
//
// It owns no state. Every question goes to `omarchy-matrix status --json` and
// every answer comes back from it, so the ✓ here and the ✓ in the terminal are
// the same ✓ -- and "on" keeps meaning "happening now" rather than
// "configured" (see is_active in the CLI).
//
// A plugin of its own, deliberately. For kind `bar-widget`, "enabled" means
// "present in bar.layout": PluginRegistry.setEnabled inserts the entry there
// and removes it again (PluginRegistry.qml:498-520). Folding this into the rain
// plugin would mean turning both rain layers off took the icon off the bar with
// them, leaving nothing to turn them back on with.
Panel {
  id: root

  moduleName: "matrix.control"
  // No IpcHandler: the shell routes `summon` to a live bar widget through the
  // bar itself (shell.qml:isBarWidgetPanelPlugin), and registering a target
  // here would only compete with the rain service's own.
  manageIpc: false

  // The provider owns this file, the way it owns manifest.json -- the machinery
  // is the CLI, the derivers and the scripts. This is the one name in it.
  readonly property string cli: "omarchy-matrix"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // --- what the CLI last told us ---------------------------------------------

  property var state: ({})
  property bool asked: false

  readonly property string packName: state.name || "Matrix"
  readonly property string currentTheme: String(state.theme || "")
  readonly property bool inEffect: state.active === true

  function on(key) {
    return !!(state.pieces && state.pieces[key])
  }

  function wanted(key) {
    return !!(state.settings && state.settings[key])
  }

  readonly property var rows: [
    { key: "wallpaper", label: "Background", description: "Rain on the desktop" },
    { key: "screensaver", label: "Screensaver", description: "Rain when idle, instead of Omarchy's" },
    { key: "lock", label: "Lock", description: "Rain behind the password field" },
    { key: "boot", label: "Boot splash", description: "The screen before login. Asks for your password." }
  ]

  readonly property int activeCount: {
    var n = 0
    for (var i = 0; i < rows.length; i++) if (on(rows[i].key)) n++
    return n
  }

  readonly property string summary: {
    if (!asked) return "…"
    if (!inEffect) return currentTheme === "" ? "stood down" : "stood down — theme is " + currentTheme
    if (activeCount === 0) return "nothing on"
    return activeCount + " of " + rows.length + " on"
  }

  // --- the cursor -------------------------------------------------------------
  // Four switches then two actions, in one list: Up/Down walks it, Enter
  // activates. Mouse hover moves the cursor to whatever it is over, so the
  // keyboard never lands somewhere the eye is not.

  property bool cursorActive: false
  property int cursorIndex: 0
  readonly property int itemCount: rows.length + 2

  function moveCursor(dx, dy) {
    var step = dy !== 0 ? dy : dx
    cursorIndex = (cursorIndex + step + itemCount) % itemCount
  }

  function activateCursor() {
    if (cursorIndex < rows.length) togglePiece(rows[cursorIndex].key)
    else if (cursorIndex === rows.length) repair()
    else uninstall()
  }

  // --- doing things -----------------------------------------------------------

  function run(command) {
    if (bar) bar.run(command)
  }

  // In a terminal, not detached: these want a password, print as they go, or
  // ask a question. The menu rows they replace did the same.
  function runVisibly(command) {
    run("omarchy-launch-floating-terminal-with-presentation '" + command + "'")
  }

  function togglePiece(key) {
    if (key === "boot") {
      // sudo, and it rebuilds the initramfs.
      runVisibly(cli + " boot toggle")
      root.close()
      return
    }
    run(cli + " " + key + " toggle")
    // The lock swap restarts the shell, which takes this widget with it; the
    // others land in a second or so. Ask again shortly either way rather than
    // drawing an optimistic tick that may not come true.
    settle.restart()
  }

  function repair() {
    runVisibly(cli + " doctor")
    root.close()
  }

  function uninstall() {
    runVisibly(cli + "-uninstall")
    root.close()
  }

  function refresh() {
    if (!status.running) status.running = true
  }

  onOpenedChanged: {
    if (opened) {
      cursorActive = false
      cursorIndex = 0
      refresh()
    }
  }

  // The bar icon has to be right before anyone opens the panel: the pack can be
  // stood down by a theme change nobody told us about.
  Component.onCompleted: refresh()

  Process {
    id: status
    command: [root.cli, "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.state = JSON.parse(text || "{}")
        } catch (e) {
          root.state = ({})
        }
        root.asked = true
      }
    }
    // Not installed, or half installed: say nothing and dim the icon rather
    // than drawing four switches that would answer nothing.
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.state = ({})
        root.asked = true
      }
    }
  }

  // One late re-read after a toggle. A piece can take a moment: `lock` waits for
  // the handler to answer steadily, `wallpaper` waits for the background to be
  // selected.
  Timer {
    id: settle
    interval: 1200
    repeat: false
    onTriggered: root.refresh()
  }

  // While the panel is open, keep it honest: `omarchy theme set` from anywhere
  // else stands the pack down, and a stale ✓ is the bug this pack has already
  // paid for once.
  Timer {
    running: root.opened
    interval: 3000
    repeat: true
    onTriggered: root.refresh()
  }

  // The bar sizes each slot from the widget item's implicit size
  // (Bar.qml:1565), and a plain Item has none: without these two lines the
  // widget loads, answers, opens its panel -- and paints nothing on the bar.
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰘨"
    tooltipText: root.packName + " — " + root.summary
    foreground: root.activeCount > 0 && root.inEffect
      ? (root.bar ? root.bar.barForeground : Color.foreground)
      : Qt.darker(root.bar ? root.bar.barForeground : Color.foreground, 1.55)
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(560))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) {
        if (!root.cursorActive) { root.cursorActive = true; return }
        root.moveCursor(dx, dy)
      }
      onActivateRequested: if (root.cursorActive) root.activateCursor()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.repair()
      }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(12)

        PanelHero {
          width: parent.width
          title: root.packName
          meta: root.summary
          foreground: root.foreground
          fontFamily: root.fontFamily
          iconOpacity: root.inEffect ? 1.0 : 0.5
          iconComponent: Component {
            Text {
              text: "󰘨"
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.display
            }
          }
        }

        // Said once, at the top, instead of four times over four dead switches:
        // with another theme current the pack has stood down on purpose, and
        // the switches below are what will come back when it returns.
        Text {
          visible: root.asked && !root.inEffect
          width: parent.width
          text: "Picking another theme stands the pack down. Your settings are kept — "
            + "come back with: omarchy theme set " + (root.state.slug || "")
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        Repeater {
          model: root.rows

          Toggle {
            required property var modelData
            required property int index

            width: column.width
            label: modelData.label
            description: modelData.description
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.fontFamily
            // The switch follows what is happening, not what is configured. A
            // piece that is on but stood down reads as off, which is the truth
            // on screen -- the line above says why.
            checked: root.on(modelData.key)
            hasCursor: root.cursorActive && root.cursorIndex === index
            onHovered: function(isHovered) {
              if (isHovered) { root.cursorActive = true; root.cursorIndex = index }
            }
            onClicked: {
              root.cursorActive = true
              root.cursorIndex = index
              root.togglePiece(modelData.key)
            }
          }
        }

        PanelSeparator { width: parent.width }

        Row {
          width: parent.width
          spacing: Style.space(8)

          Button {
            text: "Repair"
            iconText: "󰗠"
            tooltipText: "Re-apply everything. Run this after `omarchy refresh shell`."
            bordered: true
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.fontFamily
            hasCursor: root.cursorActive && root.cursorIndex === root.rows.length
            onHovered: function(isHovered) {
              if (isHovered) { root.cursorActive = true; root.cursorIndex = root.rows.length }
            }
            onClicked: root.repair()
          }

          Button {
            text: "Uninstall"
            iconText: "󰩹"
            // Omarchy's own Remove -> Theme only deletes the theme folder: it
            // would leave the plugin, the lock clone, the CLI and the hooks
            // behind, pointing at a theme that is gone.
            tooltipText: "Remove the pack and the theme, and hand Omarchy's lock, screensaver and boot splash back"
            bordered: true
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.fontFamily
            hasCursor: root.cursorActive && root.cursorIndex === root.rows.length + 1
            onHovered: function(isHovered) {
              if (isHovered) { root.cursorActive = true; root.cursorIndex = root.rows.length + 1 }
            }
            onClicked: root.uninstall()
          }
        }
      }
    }
  }
}
