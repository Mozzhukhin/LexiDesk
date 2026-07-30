import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: root

    signal completed(string command, int exitCode, string stdout, string stderr)

    function run(command) {
        commandSource.connectSource(command)
    }

    P5Support.DataSource {
        id: commandSource
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            root.completed(
                source,
                data["exit code"],
                data["stdout"] || "",
                data["stderr"] || ""
            )
            disconnectSource(source)
        }
    }
}
