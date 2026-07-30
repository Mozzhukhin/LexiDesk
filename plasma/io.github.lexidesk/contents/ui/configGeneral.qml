import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents

Kirigami.FormLayout {
    property alias cfg_rotationSeconds: rotation.value
    property alias cfg_revealMode: reveal.currentValue
    property alias cfg_colorTheme: colors.currentValue
    property alias cfg_dailyGoal: dailyGoal.value

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
