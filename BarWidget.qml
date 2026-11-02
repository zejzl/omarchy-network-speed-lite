import QtQuick
import Quickshell.Io
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "zejzl.network-speed-lite"
    property var sample: null
    implicitWidth: vertical ? barSize : button.implicitWidth
    implicitHeight: vertical ? button.implicitHeight : barSize

    function rate(value) {
        if (value >= 1048576) return (value / 1048576).toFixed(1) + " MiB/s"
        return (value / 1024).toFixed(1) + " KiB/s"
    }

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

    Ui.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        pressable: false
        text: !root.sample ? "↓ —  ↑ —"
            : root.sample.interfaces.length === 0 ? "↓ offline  ↑ offline"
            : "↓ " + root.rate(root.sample.download)
              + (root.vertical ? "\n↑ " : "  ↑ ") + root.rate(root.sample.upload)
        tooltipText: "Download / Upload · 2-second average\n"
            + (root.sample && root.sample.interfaces.length
               ? "Interfaces: " + root.sample.interfaces.join(", ")
               : "Waiting for an active physical network interface")
    }
}
