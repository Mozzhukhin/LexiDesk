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
    assert 'text: i18n("Next")' in qml
    assert 'quizRating = "dont-know"' in qml
    assert 'quizRating = "know"' in qml
    assert "choiceOptions.length === 4" in qml
    assert "cardsSinceQuiz >= 4" in qml
    assert "Math.random() < quizProbability" in qml
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
    assert "&& exampleText.length > 0" in qml
    assert "id: cardEnterAnimation" in qml
    assert "Easing.OutCubic" in qml
    assert 'text: i18n("Hard")' not in qml
    assert 'text: i18n("Easy")' not in qml
