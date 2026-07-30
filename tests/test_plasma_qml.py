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
