import QtQuick
import QtQuick.Layouts
import QtCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    property int cardId: 0
    property string sourceText: ""
    property string translationText: ""
    property string directionText: "OFFLINE"
    property string metadataText: ""
    property string exampleText: ""
    property string exampleTranslationText: ""
    property real retrievability: -1
    property bool empty: true
    property bool loaded: false
    property bool revealed: plasmoid.configuration.revealMode === "both"
    property bool busy: false
    property string errorText: ""
    property int failureCount: 0
    property int secondsLeft: plasmoid.configuration.rotationSeconds
    property int dueCount: 0
    property int reviewsToday: 0
    property bool answerChecked: false
    property string answerFeedback: ""
    property string suggestedRating: ""
    property string typedAnswer: ""
    property var choiceOptions: []
    property bool choiceMode: false
    property bool choiceAnswered: false
    property string selectedChoice: ""
    property string quizRating: ""
    property int cardsSeen: 0
    property int cardRevision: 0
    property string pendingKind: ""
    property string bridgePath: findExecutable(
        "lexidesk-bridge", "lexidesk-cli")
    property string guiPath: findExecutable("lexidesk-gui", "lexidesk")

    Plasmoid.icon: "accessories-dictionary"
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    function localFilePath(location) {
        var value = location.toString()
        if (value.indexOf("file://") === 0)
            return decodeURIComponent(value.substring(7))
        return value
    }

    function findExecutable(localName, systemName) {
        var localPath = localFilePath(
            StandardPaths.writableLocation(StandardPaths.HomeLocation))
            + "/.local/bin/" + localName
        var found = StandardPaths.findExecutable(localName)
        if (found && found.toString().length > 0)
            return localFilePath(found)
        found = StandardPaths.findExecutable(systemName)
        if (found && found.toString().length > 0)
            return localFilePath(found)
        return localPath
    }

    function shellQuote(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'"
    }

    function runBridge(arguments, kind) {
        if (busy)
            return
        busy = true
        errorText = ""
        pendingKind = kind
        runner.run(shellQuote(bridgePath) + " " + arguments)
    }

    function loadNext() {
        var exclusion = cardId > 0 ? " --exclude " + cardId : ""
        runBridge("card" + exclusion, "card")
    }

    function review(result) {
        if (cardId > 0)
            runBridge("review " + cardId + " " + result, "card")
    }

    function checkAnswer() {
        var answer = typedAnswer.trim()
        if (cardId > 0 && answer.length > 0)
            runBridge(
                "check " + cardId + " " + shellQuote(answer),
                "check")
    }

    function chooseAnswer(answer) {
        if (!choiceMode || choiceAnswered || busy)
            return
        selectedChoice = answer
        choiceAnswered = true
        answerChecked = true
        revealed = true
        if (answer === translationText) {
            suggestedRating = "good"
            quizRating = "know"
            answerFeedback = i18n("Correct — next word…")
        } else {
            suggestedRating = "again"
            quizRating = "dont-know"
            answerFeedback = i18n(
                "Incorrect — correct answer: %1",
                translationText)
        }
        choiceAdvanceTimer.restart()
    }

    function undoReview() {
        runBridge("undo", "undo")
    }

    function launchGui(arguments, kind) {
        if (busy)
            return
        busy = true
        pendingKind = kind
        runner.run(shellQuote(guiPath) + " " + arguments)
    }

    function applyCard(card) {
        loaded = true
        empty = Boolean(card.empty)
        cardId = Number(card.id || 0)
        sourceText = card.source || ""
        translationText = card.translation || ""
        directionText = card.direction || "OFFLINE"
        var metadata = []
        if (card.part_of_speech)
            metadata.push(card.part_of_speech)
        if (card.transcription)
            metadata.unshift(card.transcription)
        if (card.frequency)
            metadata.push(card.frequency)
        if (card.alternatives)
            metadata = metadata.concat(card.alternatives)
        if (card.forms)
            metadata = metadata.concat(card.forms)
        metadataText = metadata.join("  •  ")
        exampleText = card.example || ""
        exampleTranslationText = card.example_translation || ""
        retrievability = card.retrievability === null
            || card.retrievability === undefined
            ? -1 : Number(card.retrievability)
        choiceOptions = card.choices || []
        cardsSeen++
        choiceMode = !empty && choiceOptions.length === 4
            && cardsSeen % 3 === 0
        revealed = !choiceMode
            && plasmoid.configuration.revealMode === "both"
        choiceAnswered = false
        selectedChoice = ""
        quizRating = ""
        choiceAdvanceTimer.stop()
        answerChecked = false
        answerFeedback = ""
        suggestedRating = ""
        typedAnswer = ""
        secondsLeft = plasmoid.configuration.rotationSeconds
        failureCount = 0
        errorText = ""
        cardRevision++
    }

    function requestStats() {
        if (!busy)
            runBridge("stats", "stats")
    }

    RunCommand {
        id: runner
        onCompleted: function(command, exitCode, stdout, stderr) {
            busy = false
            if (exitCode !== 0) {
                if (pendingKind === "stats")
                    return
                failureCount++
                errorText = i18n("LexiDesk could not reach its local Python bridge.")
                secondsLeft = 0
                retryTimer.interval = Math.min(30000, 3000 * Math.pow(2, failureCount - 1))
                retryTimer.restart()
                return
            }
            if (pendingKind === "add" || pendingKind === "library") {
                loadNext()
                return
            }
            var payload
            try {
                payload = JSON.parse(stdout.trim())
            } catch (error) {
                errorText = i18n("LexiDesk returned an invalid local response.")
                retryTimer.restart()
                console.error("Could not parse LexiDesk response:", error, stdout)
                return
            }
            try {
                if (payload.error) {
                    errorText = payload.error
                } else if (pendingKind === "stats") {
                    dueCount = Number(payload.due || 0)
                    reviewsToday = Number(payload.reviews_today || 0)
                } else if (pendingKind === "check") {
                    answerChecked = true
                    revealed = true
                    if (payload.grade === "correct") {
                        suggestedRating = "good"
                        answerFeedback = i18n("Correct")
                    } else if (payload.grade === "close") {
                        suggestedRating = "again"
                        answerFeedback = i18n(
                            "Almost correct: %1",
                            payload.matched)
                    } else {
                        suggestedRating = "again"
                        answerFeedback = i18n(
                            "Expected: %1",
                            payload.expected)
                    }
                } else if (pendingKind === "undo") {
                    if (payload.undone)
                        applyCard(payload)
                    else
                        errorText = i18n("There is no recent review to undo.")
                } else {
                    applyCard(payload)
                    Qt.callLater(requestStats)
                }
            } catch (error) {
                errorText = i18n("LexiDesk could not display the local response.")
                retryTimer.restart()
                console.error("Could not apply LexiDesk response:", error, stdout)
            }
        }
    }

    Timer {
        id: retryTimer
        interval: 3000
        repeat: false
        onTriggered: loadNext()
    }

    Timer {
        id: choiceAdvanceTimer
        interval: 1000
        repeat: false
        onTriggered: {
            if (cardId > 0 && quizRating.length > 0)
                review(quizRating)
        }
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            if (secondsLeft > 0)
                secondsLeft--
            if (secondsLeft <= 0 && !busy && errorText.length === 0)
                loadNext()
        }
    }

    Component.onCompleted: loadNext()

    compactRepresentation: PlasmaComponents.ToolButton {
        icon.name: "accessories-dictionary"
        text: dueCount > 0 ? String(dueCount) : ""
        display: PlasmaComponents.AbstractButton.IconOnly
        onClicked: root.expanded = !root.expanded
        PlasmaComponents.ToolTip.text: dueCount > 0
            ? i18np("%1 card due", "%1 cards due", dueCount)
            : i18n("LexiDesk")
        PlasmaComponents.ToolTip.visible: hovered
    }

    fullRepresentation: Rectangle {
        id: card
        implicitWidth: 390
        implicitHeight: 320
        Layout.minimumWidth: 330
        Layout.minimumHeight: 312
        radius: 16
        color: {
            switch (plasmoid.configuration.colorTheme) {
            case "oled": return "#080808"
            case "forest": return "#17251d"
            case "purple": return "#221b2e"
            default: return Kirigami.Theme.backgroundColor
            }
        }
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.18)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 6

            RowLayout {
                Layout.fillWidth: true

                PlasmaComponents.Label {
                    text: "LEXIDESK"
                    opacity: 0.65
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                }

                Item { Layout.fillWidth: true }

                PlasmaComponents.Label {
                    text: Math.min(reviewsToday, plasmoid.configuration.dailyGoal)
                        + "/" + plasmoid.configuration.dailyGoal
                    opacity: 0.55
                    font.pixelSize: 10
                }

                PlasmaComponents.Label {
                    text: directionText
                    opacity: 0.55
                    font.pixelSize: 10
                }

                PlasmaComponents.ToolButton {
                    icon.name: "list-add"
                    text: i18n("Add card")
                    display: PlasmaComponents.AbstractButton.IconOnly
                    onClicked: launchGui("--add-clipboard", "add")
                }

                PlasmaComponents.ToolButton {
                    icon.name: "view-list-details"
                    text: i18n("Open library")
                    display: PlasmaComponents.AbstractButton.IconOnly
                    onClicked: launchGui("--library", "library")
                }
            }

            Rectangle {
                id: contentFrame
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 165
                radius: 13
                color: Qt.alpha(Kirigami.Theme.textColor, 0.035)
                border.width: 1
                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.1)

                Connections {
                    target: root
                    function onCardRevisionChanged() {
                        contentFrame.opacity = 0
                        contentFrame.scale = 0.985
                        cardEnterAnimation.restart()
                    }
                }

                ParallelAnimation {
                    id: cardEnterAnimation
                    NumberAnimation {
                        target: contentFrame
                        property: "opacity"
                        to: 1
                        duration: 220
                        easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: contentFrame
                        property: "scale"
                        to: 1
                        duration: 260
                        easing.type: Easing.OutCubic
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4
                    Item { Layout.fillHeight: true }

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: !loaded
                            ? i18n("Loading vocabulary…")
                            : (empty ? i18n("Your vocabulary is empty") : sourceText)
                        wrapMode: Text.Wrap
                        font.pixelSize: empty ? 18 : 26
                        font.bold: true
                    }

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: !loaded
                            ? ""
                            : (empty
                            ? i18n("Press + to add a word or phrase")
                            : translationText)
                        visible: loaded && (empty || revealed)
                        wrapMode: Text.Wrap
                        color: Kirigami.Theme.highlightColor
                        font.pixelSize: 19
                        font.bold: !empty
                        opacity: visible ? 1 : 0
                        Behavior on opacity {
                            NumberAnimation { duration: 180 }
                        }
                    }

                    PlasmaComponents.Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: i18n("Reveal translation")
                        visible: loaded && !empty && !revealed
                            && plasmoid.configuration.revealMode === "quiz"
                        onClicked: revealed = true
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 6
                        rowSpacing: 5
                        visible: loaded && choiceMode

                        Repeater {
                            model: root.choiceOptions

                            delegate: PlasmaComponents.Button {
                                required property string modelData
                                readonly property bool correctOption:
                                    text === root.translationText
                                readonly property bool selectedOption:
                                    text === root.selectedChoice

                                Layout.fillWidth: true
                                implicitHeight: 32
                                text: modelData
                                enabled: !busy
                                background: Rectangle {
                                    radius: 7
                                    color: {
                                        if (root.choiceAnswered
                                                && parent.correctOption)
                                            return Qt.alpha(
                                                Kirigami.Theme.positiveTextColor,
                                                0.28)
                                        if (root.choiceAnswered
                                                && parent.selectedOption)
                                            return Qt.alpha(
                                                Kirigami.Theme.negativeTextColor,
                                                0.28)
                                        return Qt.alpha(
                                            Kirigami.Theme.textColor, 0.055)
                                    }
                                    border.width: root.choiceAnswered
                                        && (parent.correctOption
                                            || parent.selectedOption) ? 2 : 1
                                    border.color: {
                                        if (root.choiceAnswered
                                                && parent.correctOption)
                                            return Kirigami.Theme.positiveTextColor
                                        if (root.choiceAnswered
                                                && parent.selectedOption)
                                            return Kirigami.Theme.negativeTextColor
                                        return Qt.alpha(
                                            Kirigami.Theme.textColor, 0.18)
                                    }
                                }
                                onClicked: root.chooseAnswer(text)
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: loaded && !empty
                            && !choiceMode
                            && plasmoid.configuration.revealMode === "typing"
                            && !answerChecked

                        PlasmaComponents.TextField {
                            Layout.fillWidth: true
                            text: root.typedAnswer
                            placeholderText: i18n("Type the translation…")
                            enabled: !busy
                            onTextChanged: {
                                if (root.typedAnswer !== text)
                                    root.typedAnswer = text
                            }
                            onAccepted: checkAnswer()
                        }

                        PlasmaComponents.Button {
                            text: i18n("Check")
                            enabled: !busy && root.typedAnswer.trim().length > 0
                            onClicked: checkAnswer()
                        }
                    }

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        Layout.minimumHeight: visible ? 20 : 0
                        horizontalAlignment: Text.AlignHCenter
                        text: answerFeedback
                        visible: answerChecked
                        wrapMode: Text.Wrap
                        font.bold: choiceMode
                        font.pixelSize: choiceMode ? 13 : 12
                        color: suggestedRating === "again"
                            ? Kirigami.Theme.negativeTextColor
                            : Kirigami.Theme.positiveTextColor
                    }

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: metadataText
                        visible: revealed && !choiceMode
                            && metadataText.length > 0
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        font.pixelSize: 12
                        maximumLineCount: 1
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        id: examplePanel
                        Layout.fillWidth: true
                        visible: revealed && !choiceMode
                            && exampleText.length > 0
                        implicitHeight: exampleColumn.implicitHeight + 12
                        radius: 8
                        color: Qt.alpha(Kirigami.Theme.highlightColor, 0.08)

                        ColumnLayout {
                            id: exampleColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 8
                            spacing: 2

                            PlasmaComponents.Label {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                                text: exampleText
                                wrapMode: Text.Wrap
                                font.italic: true
                                font.pixelSize: 12
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }

                            PlasmaComponents.Label {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                                text: exampleTranslationText
                                visible: text.length > 0
                                wrapMode: Text.Wrap
                                opacity: 0.7
                                font.pixelSize: 11
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                visible: errorText.length > 0

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    text: errorText
                    color: Kirigami.Theme.negativeTextColor
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    font.pixelSize: 11
                }

                PlasmaComponents.Button {
                    text: i18n("Retry")
                    enabled: !busy
                    onClicked: {
                        retryTimer.stop()
                        loadNext()
                    }
                }
            }

            PlasmaComponents.Button {
                Layout.fillWidth: true
                visible: !choiceMode
                implicitHeight: 36
                text: i18n("Next")
                icon.name: "go-next"
                enabled: loaded && !empty && !busy
                onClicked: loadNext()
            }

            RowLayout {
                Layout.fillWidth: true

                PlasmaComponents.ToolButton {
                    icon.name: "edit-undo"
                    text: i18n("Undo last review")
                    display: PlasmaComponents.AbstractButton.IconOnly
                    enabled: !busy
                    onClicked: undoReview()
                    PlasmaComponents.ToolTip.text: text
                    PlasmaComponents.ToolTip.visible: hovered
                }

                Item { Layout.fillWidth: true }

                PlasmaComponents.BusyIndicator {
                    running: busy
                    visible: busy
                    implicitWidth: 18
                    implicitHeight: 18
                }

                PlasmaComponents.Label {
                    text: retrievability >= 0
                        ? i18n("%1% recall", retrievability.toFixed(0))
                        : ""
                    opacity: 0.6
                    font.pixelSize: 10
                }

                PlasmaComponents.Label {
                    text: Math.floor(secondsLeft / 60) + ":"
                        + String(secondsLeft % 60).padStart(2, "0")
                    opacity: 0.6
                    font.family: "monospace"
                }
            }
        }
    }
}
