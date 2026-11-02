import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui as Ui
import qs.Commons

Ui.BarWidget {
    id: root
    moduleName: "zejzl.network-speed-lite"
    property var sample: null
    property bool popupOpen: false
    property bool compact: false
    property bool blink: false
    readonly property real activityThreshold: 1024
    readonly property bool downActive: !!sample && sample.download > activityThreshold
    readonly property bool upActive: !!sample && sample.upload > activityThreshold
    readonly property string stateDir: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/omarchy-network-speed-lite"

    implicitWidth: vertical ? barSize : button.implicitWidth
    implicitHeight: vertical ? button.implicitHeight : barSize

    function close() { popupOpen = false }

    function rate(value) {
        if (value >= 1048576) return (value / 1048576).toFixed(1) + " MiB/s"
        return (value / 1024).toFixed(1) + " KiB/s"
    }

    function amount(value) {
        if (value >= 1073741824) return (value / 1073741824).toFixed(2) + " GiB"
        if (value >= 1048576) return (value / 1048576).toFixed(1) + " MiB"
        return (value / 1024).toFixed(1) + " KiB"
    }

    function setCompact(value) {
        compact = value
        saver.command = ["/bin/sh", "-c", "mkdir -p \"$1\" && printf '%s\\n' \"$2\" > \"$1/mode\"", "sh", stateDir, value ? "compact" : "normal"]
        saver.running = true
    }

    FileView {
        id: modeFile
        path: root.stateDir + "/mode"
        printErrors: false
        onLoaded: root.compact = text().trim() === "compact"
    }

    Process { id: saver }

    Process {
        id: collector
        command: ["/usr/bin/python3", "-u", decodeURIComponent(Qt.resolvedUrl("traffic.py").toString().replace(/^file:\/\//, ""))]
        running: true
        stdout: SplitParser {
            onRead: data => {
                try { root.sample = JSON.parse(data) }
                catch (error) { root.sample = null }
            }
        }
        onExited: { root.sample = null; retry.restart() }
    }

    Timer {
        id: retry
        interval: 5000
        onTriggered: collector.running = true
    }

    Timer {
        interval: 350
        repeat: true
        running: root.compact && (root.downActive || root.upActive)
        onTriggered: root.blink = !root.blink
        onRunningChanged: if (!running) root.blink = false
    }

    Ui.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        pressable: true
        labelVisible: !root.compact
        text: root.compact ? (root.vertical ? "↓\n↑" : "↓ ↑")
            : !root.sample ? "↓ —  ↑ —"
            : root.sample.interfaces.length === 0 ? "↓ offline  ↑ offline"
            : "↓ " + root.rate(root.sample.download)
              + (root.vertical ? "\n↑ " : "  ↑ ") + root.rate(root.sample.upload)
        tooltipText: root.popupOpen ? "" : "Left click: details · Right click: "
            + (root.compact ? "normal view" : "compact view")
        onPressed: button => {
            if (button === Qt.RightButton) root.setCompact(!root.compact)
            else if (button === Qt.LeftButton) root.popupOpen = !root.popupOpen
        }
    }

    Flow {
        anchors.centerIn: parent
        visible: root.compact
        flow: root.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: Style.space(4)
        Repeater {
            model: [{glyph: "↓", down: true}, {glyph: "↑", down: false}]
            Text {
                required property var modelData
                readonly property bool active: modelData.down ? root.downActive : root.upActive
                text: modelData.glyph
                textFormat: Text.PlainText
                color: root.bar ? root.bar.barForeground : "white"
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                font.bold: active
                opacity: !active ? 0.3 : (root.blink ? 0.55 : 1.0)
                Behavior on opacity { NumberAnimation { duration: 120 } }
            }
        }
    }

    Ui.PopupCard {
        id: popup
        anchorItem: root
        bar: root.bar
        owner: root
        open: root.popupOpen
        contentWidth: popup.fittedContentWidth(Style.space(300))
        contentHeight: popup.fittedContentHeight(details.implicitHeight)

        Text {
            id: details
            width: parent.width
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: root.bar ? root.bar.foreground : "white"
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.body
            text: {
                var s = root.sample
                if (!s) return "Network Speed Lite\nWaiting for data…"
                var lines = ["Network Speed Lite · 2-second average", "",
                    "Now      ↓ " + root.rate(s.download) + "   ↑ " + root.rate(s.upload),
                    "Peak     ↓ " + root.rate(s.peakDown || 0) + "   ↑ " + root.rate(s.peakUp || 0),
                    "Session  ↓ " + root.amount(s.totalDown || 0) + "   ↑ " + root.amount(s.totalUp || 0),
                    "", "Interfaces (physical only):"]
                var per = s.perInterface || []
                if (per.length === 0) lines.push("  none active")
                for (var i = 0; i < per.length; i++)
                    lines.push("  " + per[i].name + "  ↓ " + root.rate(per[i].download) + "   ↑ " + root.rate(per[i].upload))
                return lines.join("\n")
            }
        }
    }
}
