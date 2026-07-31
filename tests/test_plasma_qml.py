from pathlib import Path

QML_PATH = (
    Path(__file__).parents[1]
    / "plasma"
    / "io.github.lexidesk"
    / "contents"
    / "ui"
    / "main.qml"
)


def test_widget_keeps_typing_state_in_root_scope() -> None:
    """Root functions must not reach into fullRepresentation component IDs."""
    qml = QML_PATH.read_text(encoding="utf-8")

    assert "property string typedAnswer" in qml
    assert "answerField" not in qml
    assert "shellQuote(answer)" in qml


def test_widget_distinguishes_json_and_display_failures() -> None:
    qml = QML_PATH.read_text(encoding="utf-8")

    assert "Could not parse LexiDesk response:" in qml
    assert "Could not apply LexiDesk response:" in qml
    assert "could not display the local response" in qml


def test_widget_uses_simple_reviews_and_four_choice_quizzes() -> None:
    qml = QML_PATH.read_text(encoding="utf-8")

    assert 'text: i18n("Don’t know")' not in qml
    assert 'text: i18n("Know")' not in qml
    assert 'text: i18n("Next") + "  →"' in qml
    assert 'quizRating = "dont-know"' in qml
    assert 'quizRating = "know"' in qml
    assert "choiceOptions = quiz.choices || []" in qml
    assert "choiceMode = false" in qml
    assert "id: appMenu" in qml
    assert 'root.selectQuizMode("typing")' in qml
    assert 'text: i18n("Mixed — adaptive + regular checks")' in qml
    assert "property bool adaptiveQuiz" in qml
    assert "property bool quizEligible" in qml
    assert "property int mixedDryStreak" in qml
    assert "mixedDryStreak++" in qml
    assert "quizEligible && mixedDryStreak >= 5" in qml
    assert 'quizMode === "mixed" ? " --adaptive"' in qml
    assert 'var mixedKinds = ["translation", "reverse", "cloze", "context"]' in qml
    assert 'checked: root.quizMode === "mixed"' in qml
    assert "enabled: Boolean(root.quizVariants" not in qml
    assert "Math.random() < quizProbability" not in qml
    assert 'quizType === "typing"' in qml
    assert 'quizType === "context"' in qml
    assert "parent.correctOption" in qml
    assert "parent.selectedOption" in qml
    assert "Kirigami.Theme.positiveTextColor" in qml
    assert "Kirigami.Theme.negativeTextColor" in qml
    assert "id: choiceAdvanceTimer" in qml
    assert "interval: 1000" in qml
    assert "Incorrect — correct answer" in qml
    assert "exampleColumn.implicitHeight" in qml
    assert "id: examplePanel" in qml
    assert "&& primaryExampleText.length > 0" in qml
    assert "id: cardEnterAnimation" in qml
    assert "Easing.OutCubic" in qml
    assert 'text: i18n("Hard")' not in qml
    assert 'text: i18n("Easy")' not in qml
    assert "Undo last review" not in qml
    assert "undoReview" not in qml


def test_widget_has_compact_navigation_and_hover_actions() -> None:
    qml = QML_PATH.read_text(encoding="utf-8")

    assert "id: appMenu" in qml
    assert 'text: i18n("Vocabulary library")' in qml
    assert 'text: i18n("Settings")' in qml
    assert "id: countdownProgress" in qml
    assert "until the next card" in qml
    assert "id: contentHover" in qml
    assert 'text: i18n("Edit card")' in qml
    assert 'text: i18n("Hide for now")' in qml
    assert 'text: i18n("Delete card…")' in qml
    assert "maximumLineCount: 2" in qml
    assert "% recall" not in qml
    assert 'internalAction("configure").trigger()' in qml
    assert "Layout.minimumHeight: 270" in qml


def test_widget_settings_write_string_values() -> None:
    config = (QML_PATH.parent / "configGeneral.qml").read_text(encoding="utf-8")

    assert "property alias cfg_colorTheme" not in config
    assert "property string cfg_colorTheme" in config
    assert "onActivated: form.cfg_colorTheme = currentValue" in config
    assert "onActivated: form.cfg_revealMode = currentValue" in config
    assert "onActivated: form.cfg_quizMode = currentValue" in config


def test_widget_keeps_english_above_russian_on_regular_cards() -> None:
    qml = QML_PATH.read_text(encoding="utf-8")

    assert 'sourceLanguage === "ru"' in qml
    assert "? translationText : sourceText" in qml
    assert "? sourceText : translationText" in qml
    assert "(choiceMode ? quizPrompt : primaryText)" in qml
    assert "(choiceMode ? quizAnswer : secondaryText)" in qml
    assert "root.primaryExampleText, root.primaryText" in qml


def test_widget_rotation_skips_an_unanswered_quiz() -> None:
    qml = QML_PATH.read_text(encoding="utf-8")

    assert "if (choiceMode && !choiceAnswered)" not in qml
    assert "LexiDesk backend is unavailable" in qml
