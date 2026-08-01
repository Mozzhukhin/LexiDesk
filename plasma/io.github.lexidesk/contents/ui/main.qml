import QtQuick
import QtQuick.Layouts
import QtCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    property int cardId: 0
    property string sourceText: ""
    property string translationText: ""
    property string sourceLanguage: ""
    property string targetLanguage: ""
    readonly property bool targetFirst: targetLanguage === "en"
    readonly property string primaryText: targetFirst
        ? translationText : sourceText
    readonly property string secondaryText: targetFirst
        ? sourceText : translationText
    readonly property string primaryExampleText: targetFirst
        ? exampleTranslationText : exampleText
    readonly property string secondaryExampleText: targetFirst
        ? exampleText : exampleTranslationText
    property string directionText: "OFFLINE"
    property bool presentationReversed: false
    property string metadataText: ""
    property string exampleText: ""
    property string exampleTranslationText: ""
    property bool empty: true
    property bool loaded: false
    property bool revealed: plasmoid.configuration.revealMode === "both"
    property bool busy: false
    property string errorText: ""
    property int failureCount: 0
    property int secondsLeft: plasmoid.configuration.rotationSeconds
    property int dueCount: 0
    property int totalCount: 0
    property int reviewsToday: 0
    property bool answerChecked: false
    property string answerFeedback: ""
    property string suggestedRating: ""
    property string typedAnswer: ""
    property var choiceOptions: []
    property bool choiceMode: false
    property bool quizUnavailable: false
    property bool choiceAnswered: false
    property string selectedChoice: ""
    property string quizRating: ""
    property string quizType: ""
    property string quizPrompt: ""
    property string quizAnswer: ""
    property string quizInstruction: ""
    property var quizVariants: ({})
    property string quizMode: plasmoid.configuration.quizMode || "off"
    property bool quizEligible: false
    property int mixedDryStreak: 0
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

    function htmlEscape(value) {
        return String(value).replace(/&/g, "&amp;")
            .replace(/</g, "&lt;").replace(/>/g, "&gt;")
    }

    function highlightTerm(sentence, term) {
        var position = sentence.toLowerCase().indexOf(term.toLowerCase())
        if (position < 0)
            return htmlEscape(sentence)
        return htmlEscape(sentence.substring(0, position))
            + "<b>" + htmlEscape(sentence.substring(
                position, position + term.length)) + "</b>"
            + htmlEscape(sentence.substring(position + term.length))
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
        var adaptive = quizMode === "mixed" ? " --adaptive" : ""
        runBridge("card" + exclusion + adaptive, "card")
    }

    function review(result) {
        if (cardId > 0) {
            var metadata = " --quiz-type " + shellQuote(quizType)
                + " --selected " + shellQuote(
                    selectedChoice || typedAnswer.trim())
                + " --correct " + shellQuote(quizAnswer)
            if (quizMode === "mixed")
                metadata += " --adaptive"
            if (presentationReversed)
                metadata += " --reversed"
            runBridge("review " + cardId + " " + result + metadata, "card")
        }
    }

    function checkAnswer() {
        var answer = typedAnswer.trim()
        if (cardId > 0 && answer.length > 0)
            runBridge(
                "check " + cardId + " " + shellQuote(answer)
                    + (presentationReversed ? " --reversed" : ""),
                "check")
    }

    function chooseAnswer(answer) {
        if (!choiceMode || choiceAnswered || busy)
            return
        selectedChoice = answer
        choiceAnswered = true
        answerChecked = true
        revealed = true
        if (answer === quizAnswer) {
            suggestedRating = "good"
            quizRating = "know"
        } else {
            suggestedRating = "again"
            quizRating = "dont-know"
        }
        answerFeedback = ""
        choiceAdvanceTimer.restart()
    }

    function startQuiz(kind, animate) {
        var quiz = quizVariants[kind]
        if (busy || empty)
            return
        if (!quiz) {
            quizType = kind
            quizPrompt = i18n("No suitable card for this quiz yet")
            quizAnswer = ""
            quizInstruction = i18n(
                "This mode remains selected. Press Next or wait for another card.")
            choiceOptions = []
            choiceMode = true
            quizUnavailable = true
            revealed = false
            answerChecked = false
            suggestedRating = ""
            answerFeedback = ""
            return
        }
        quizType = quiz.type || kind
        quizPrompt = quiz.prompt || sourceText
        quizAnswer = quiz.answer || translationText
        quizInstruction = quiz.instruction || ""
        choiceOptions = quiz.choices || []
        choiceMode = true
        quizUnavailable = false
        choiceAnswered = false
        selectedChoice = ""
        quizRating = ""
        answerChecked = false
        answerFeedback = ""
        suggestedRating = ""
        typedAnswer = ""
        revealed = false
        choiceAdvanceTimer.stop()
        if (quizMode === "mixed")
            mixedDryStreak = 0
        if (animate !== false)
            cardRevision++
    }

    function selectQuizMode(kind) {
        plasmoid.configuration.quizMode = kind
        mixedDryStreak = 0
        if (kind === "off" || kind === "mixed") {
            choiceMode = false
            quizUnavailable = false
            revealed = plasmoid.configuration.revealMode === "both"
            answerChecked = false
            answerFeedback = ""
            choiceAdvanceTimer.stop()
        } else {
            startQuiz(kind)
        }
    }

    function quizModeLabel() {
        switch (quizMode) {
        case "mixed": return i18n("Mixed")
        case "translation": return i18n("Translation")
        case "reverse": return i18n("Reverse")
        case "cloze": return i18n("Sentence")
        case "context": return i18n("Context")
        case "typing": return i18n("Typing")
        default: return ""
        }
    }

    function applyQuizMode() {
        if (quizMode === "off")
            return
        if (quizMode !== "mixed") {
            startQuiz(quizMode, false)
            return
        }
        mixedDryStreak++
        if (mixedDryStreak < 5 || !quizEligible)
            return
        var mixedKinds = ["translation", "reverse", "cloze", "context"]
        var available = []
        for (var index = 0; index < mixedKinds.length; index++) {
            var kind = mixedKinds[index]
            if (quizVariants[kind])
                available.push(kind)
        }
        if (available.length > 0) {
            var selected = available[Math.floor(Math.random() * available.length)]
            startQuiz(selected, false)
        }
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
        sourceLanguage = card.source_language || "en"
        targetLanguage = card.target_language || (sourceLanguage === "en" ? "ru" : "en")
        directionText = card.deck_direction || card.direction || "OFFLINE"
        presentationReversed = Boolean(card.presentation_reversed)
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
        quizVariants = card.quizzes || {}
        quizEligible = Boolean(card.quiz_eligible)
        var quiz = card.quiz || {}
        quizType = quiz.type || ""
        quizPrompt = quiz.prompt || sourceText
        quizAnswer = quiz.answer || translationText
        quizInstruction = quiz.instruction || ""
        choiceOptions = quiz.choices || card.choices || []
        choiceMode = false
        quizUnavailable = false
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
        applyQuizMode()
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
                errorText = i18n(
                    "LexiDesk backend is unavailable. Run scripts/setup.sh, "
                    + "then remove and add the widget again.")
                secondsLeft = 0
                retryTimer.interval = Math.min(30000, 3000 * Math.pow(2, failureCount - 1))
                retryTimer.restart()
                return
            }
            if (pendingKind === "add" || pendingKind === "edit"
                    || pendingKind === "delete" || pendingKind === "library"
                    || pendingKind === "settings" || pendingKind === "support"
                    || pendingKind === "deck") {
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
                    totalCount = Number(payload.total || 0)
                    dueCount = Number(payload.due || 0)
                    reviewsToday = Number(payload.reviews_today || 0)
                } else if (pendingKind === "check") {
                    answerChecked = true
                    revealed = true
                    if (payload.grade === "correct") {
                        suggestedRating = "good"
                        answerFeedback = i18n("Correct")
                        quizRating = "know"
                    } else if (payload.grade === "close") {
                        suggestedRating = "again"
                        answerFeedback = i18n(
                            "Almost correct: %1",
                            payload.matched)
                        quizRating = "dont-know"
                    } else {
                        suggestedRating = "again"
                        answerFeedback = i18n(
                            "Expected: %1",
                            payload.expected)
                        quizRating = "dont-know"
                    }
                    if (choiceMode)
                        choiceAdvanceTimer.restart()
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
        implicitHeight: 280
        Layout.minimumWidth: 330
        Layout.minimumHeight: 270
        Layout.preferredHeight: implicitHeight
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

        PlasmaExtras.Menu {
            id: appMenu
            visualParent: appMenuButton
            placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup

            PlasmaExtras.MenuItem {
                text: i18n("Vocabulary library")
                icon: "view-list-details"
                onClicked: root.launchGui("--library", "library")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Choose language deck")
                icon: "view-filter"
                onClicked: root.launchGui("--decks", "deck")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Learning analytics")
                icon: "office-chart-line"
                onClicked: root.launchGui("--analytics", "library")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Batch add from text")
                icon: "document-import"
                onClicked: root.launchGui("--batch", "library")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Settings")
                icon: "configure"
                onClicked: Plasmoid.internalAction("configure").trigger()
            }

            PlasmaExtras.MenuItem {
                text: i18n("Support developer")
                icon: "help-donate"
                onClicked: root.launchGui("--support", "support")
            }

            PlasmaExtras.MenuItem {
                separator: true
            }

            PlasmaExtras.MenuItem {
                text: i18n("Practice mode")
                enabled: false
            }

            PlasmaExtras.MenuItem {
                text: i18n("Off — normal cards")
                checkable: true
                checked: root.quizMode === "off"
                onClicked: root.selectQuizMode("off")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Mixed — adaptive + regular checks")
                checkable: true
                checked: root.quizMode === "mixed"
                onClicked: root.selectQuizMode("mixed")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Choose translation")
                checkable: true
                checked: root.quizMode === "translation"
                onClicked: root.selectQuizMode("translation")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Reverse translation")
                checkable: true
                checked: root.quizMode === "reverse"
                onClicked: root.selectQuizMode("reverse")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Complete the sentence")
                checkable: true
                checked: root.quizMode === "cloze"
                onClicked: root.selectQuizMode("cloze")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Choose the context")
                checkable: true
                checked: root.quizMode === "context"
                onClicked: root.selectQuizMode("context")
            }
            PlasmaExtras.MenuItem {
                text: i18n("Type the translation")
                checkable: true
                checked: root.quizMode === "typing"
                onClicked: root.selectQuizMode("typing")
            }
        }

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
                    text: i18np("%1 word", "%1 words", totalCount)
                    opacity: 0.55
                    font.pixelSize: 10
                }

                PlasmaComponents.ToolButton {
                    text: directionText + "  ▾"
                    display: PlasmaComponents.AbstractButton.TextOnly
                    font.pixelSize: 10
                    onClicked: root.launchGui("--decks", "deck")
                    PlasmaComponents.ToolTip.text: i18n("Choose language deck")
                    PlasmaComponents.ToolTip.visible: hovered
                }

                PlasmaComponents.Label {
                    text: root.quizModeLabel()
                    visible: text.length > 0
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.85
                    font.pixelSize: 10
                }

                PlasmaComponents.ToolButton {
                    icon.name: "list-add"
                    text: i18n("Add card")
                    display: PlasmaComponents.AbstractButton.IconOnly
                    onClicked: launchGui("--add-clipboard", "add")
                }

                PlasmaComponents.ToolButton {
                    id: appMenuButton
                    icon.name: "application-menu"
                    text: i18n("LexiDesk menu")
                    display: PlasmaComponents.AbstractButton.IconOnly
                    checked: appMenu.status === PlasmaExtras.Menu.Open
                    onPressed: appMenu.openRelative()
                    PlasmaComponents.ToolTip.text: text
                    PlasmaComponents.ToolTip.visible: hovered
                }

                PlasmaComponents.BusyIndicator {
                    running: busy
                    visible: busy
                    implicitWidth: 16
                    implicitHeight: 16
                }
            }

            Rectangle {
                id: contentFrame
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 145
                radius: 13
                color: Qt.alpha(Kirigami.Theme.textColor, 0.035)
                border.width: 1
                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.1)

                HoverHandler {
                    id: contentHover
                    acceptedDevices: PointerDevice.Mouse
                }

                Row {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 7
                    spacing: 2
                    z: 3
                    visible: loaded && !empty
                    opacity: contentHover.hovered ? 1 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 120 }
                    }

                    PlasmaComponents.ToolButton {
                        icon.name: "document-edit"
                        text: i18n("Edit card")
                        display: PlasmaComponents.AbstractButton.IconOnly
                        enabled: !busy
                        onClicked: root.launchGui(
                            "--edit " + root.cardId, "edit")
                        PlasmaComponents.ToolTip.text: text
                        PlasmaComponents.ToolTip.visible: hovered
                    }

                    PlasmaComponents.ToolButton {
                        icon.name: "go-next-skip"
                        text: i18n("Hide for now")
                        display: PlasmaComponents.AbstractButton.IconOnly
                        enabled: !busy
                        onClicked: root.loadNext()
                        PlasmaComponents.ToolTip.text: text
                        PlasmaComponents.ToolTip.visible: hovered
                    }

                    PlasmaComponents.ToolButton {
                        icon.name: "edit-delete"
                        text: i18n("Delete card…")
                        display: PlasmaComponents.AbstractButton.IconOnly
                        enabled: !busy
                        onClicked: root.launchGui(
                            "--delete " + root.cardId, "delete")
                        PlasmaComponents.ToolTip.text: text
                        PlasmaComponents.ToolTip.visible: hovered
                    }

                    PlasmaComponents.ToolButton {
                        icon.name: "view-list-details"
                        text: i18n("Open library")
                        display: PlasmaComponents.AbstractButton.IconOnly
                        enabled: !busy
                        onClicked: root.launchGui("--library", "library")
                        PlasmaComponents.ToolTip.text: text
                        PlasmaComponents.ToolTip.visible: hovered
                    }
                }

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
                            : (empty ? i18n("Your vocabulary is empty")
                            : (choiceMode ? quizPrompt : primaryText))
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        font.pixelSize: empty ? 18
                            : (choiceMode
                            && (quizType === "context"
                            || quizType === "cloze") ? 16 : 26)
                        font.bold: true
                    }

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: !loaded
                            ? ""
                            : (empty
                            ? i18n("Press + to add a word or phrase")
                            : (choiceMode ? quizAnswer : secondaryText))
                        visible: loaded && (empty || revealed)
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
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
                            && !choiceMode
                            && plasmoid.configuration.revealMode === "quiz"
                        onClicked: revealed = true
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: quizType === "context" ? 1 : 2
                        columnSpacing: 6
                        rowSpacing: 5
                        visible: loaded && choiceMode
                            && quizType !== "typing"

                        Repeater {
                            model: root.choiceOptions

                            delegate: PlasmaComponents.Button {
                                required property string modelData
                                readonly property bool correctOption:
                                    text === root.quizAnswer
                                readonly property bool selectedOption:
                                    text === root.selectedChoice

                                Layout.fillWidth: true
                                implicitHeight: root.quizType === "context" ? 38 : 32
                                text: modelData
                                font.pixelSize: root.quizType === "context" ? 10 : 12
                                enabled: !busy
                                opacity: root.choiceAnswered
                                    && !correctOption && !selectedOption ? 0.42 : 1
                                Behavior on opacity {
                                    NumberAnimation { duration: 120 }
                                }
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
                                    Behavior on color {
                                        ColorAnimation { duration: 120 }
                                    }
                                }
                                onClicked: root.chooseAnswer(text)
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: loaded && !empty
                            && ((choiceMode && quizType === "typing")
                            || (!choiceMode
                            && plasmoid.configuration.revealMode === "typing"))
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
                        visible: answerChecked && !choiceMode
                        wrapMode: Text.Wrap
                        font.bold: choiceMode
                        font.pixelSize: choiceMode ? 13 : 12
                        color: suggestedRating.length === 0
                            ? Kirigami.Theme.textColor
                            : (suggestedRating === "again"
                                ? Kirigami.Theme.negativeTextColor
                                : Kirigami.Theme.positiveTextColor)
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
                            && primaryExampleText.length > 0
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
                                textFormat: Text.RichText
                                text: root.highlightTerm(
                                    root.primaryExampleText, root.primaryText)
                                wrapMode: Text.Wrap
                                font.italic: true
                                font.pixelSize: 12
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }

                            PlasmaComponents.Label {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                                text: secondaryExampleText
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
                visible: !choiceMode || quizUnavailable
                implicitHeight: 36
                text: i18n("Next") + "  →"
                icon.name: "go-next"
                enabled: loaded && !empty && !busy
                onClicked: loadNext()
            }

            PlasmaComponents.ProgressBar {
                id: countdownProgress
                Layout.fillWidth: true
                implicitHeight: 3
                from: 0
                to: Math.max(1, plasmoid.configuration.rotationSeconds)
                value: Math.max(0, secondsLeft)
                indeterminate: false
                PlasmaComponents.ToolTip.text: i18n(
                    "%1:%2 until the next card",
                    Math.floor(secondsLeft / 60),
                    String(secondsLeft % 60).padStart(2, "0"))
                PlasmaComponents.ToolTip.visible: hovered
            }
        }
    }
}
