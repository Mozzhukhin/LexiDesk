import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents

Kirigami.FormLayout {
    property alias cfg_rotationSeconds: rotation.value
    property alias cfg_revealMode: reveal.currentValue
    property alias cfg_colorTheme: colors.currentValue
    property alias cfg_dailyGoal: dailyGoal.value
    property alias cfg_quizMode: quizMode.currentValue

    PlasmaComponents.SpinBox {
        id: rotation
        Kirigami.FormData.label: i18n("Change card every:")
        from: 30
        to: 3600
        stepSize: 10
        textFromValue: function(value) {
            return i18np("%1 second", "%1 seconds", value)
        }
    }

    PlasmaComponents.ComboBox {
        id: quizMode
        Kirigami.FormData.label: i18n("Practice mode:")
        textRole: "text"
        valueRole: "value"
        model: [
            { text: i18n("Off"), value: "off" },
            { text: i18n("Mixed — every fifth card"), value: "mixed" },
            { text: i18n("Choose translation"), value: "translation" },
            { text: i18n("Reverse translation"), value: "reverse" },
            { text: i18n("Complete the sentence"), value: "cloze" },
            { text: i18n("Choose the context"), value: "context" },
            { text: i18n("Type the translation"), value: "typing" }
        ]
    }

    PlasmaComponents.ComboBox {
        id: reveal
        Kirigami.FormData.label: i18n("Card mode:")
        textRole: "text"
        valueRole: "value"
        model: [
            { text: i18n("Show both"), value: "both" },
            { text: i18n("Click to reveal"), value: "quiz" },
            { text: i18n("Type the translation"), value: "typing" }
        ]
    }

    PlasmaComponents.SpinBox {
        id: dailyGoal
        Kirigami.FormData.label: i18n("Daily goal:")
        from: 1
        to: 500
        textFromValue: function(value) {
            return i18np("%1 review", "%1 reviews", value)
        }
    }

    PlasmaComponents.ComboBox {
        id: colors
        Kirigami.FormData.label: i18n("Color theme:")
        textRole: "text"
        valueRole: "value"
        model: [
            { text: i18n("Follow Plasma"), value: "system" },
            { text: i18n("OLED"), value: "oled" },
            { text: i18n("Forest"), value: "forest" },
            { text: i18n("Purple"), value: "purple" }
        ]
    }
}
