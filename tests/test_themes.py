from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QVBoxLayout

from lexidesk.themes import THEMES, apply_application_theme, stylesheet


def test_every_theme_styles_popup_and_container_controls() -> None:
    required_selectors = (
        "QComboBox QAbstractItemView",
        "QAbstractItemView::item:selected",
        "QMenu::item:selected",
        "QTabWidget::pane",
        "QTabBar::tab:selected",
        "QScrollBar::handle",
        "QLineEdit:disabled",
    )

    for name, colors in THEMES.items():
        style = stylesheet(name)
        assert all(selector in style for selector in required_selectors)
        assert colors["surface"] in style
        assert colors["text"] in style
        assert colors["accent_text"] in style
        # Fusion must draw these native arrows; styling their subcontrols makes
        # the arrows black or invisible on Windows dark themes.
        assert "QComboBox::drop-down" not in style
        assert "QSpinBox::up-button" not in style


def test_application_palette_reaches_combo_popup(qapp: QApplication) -> None:
    apply_application_theme(qapp, "OLED")
    dialog = QDialog()
    combo = QComboBox(dialog)
    combo.addItems(["English", "Russian", "Ukrainian"])
    layout = QVBoxLayout(dialog)
    layout.addWidget(combo)
    dialog.show()
    combo.showPopup()
    qapp.processEvents()

    palette = combo.view().palette()
    colors = THEMES["OLED"]
    assert palette.color(QPalette.ColorRole.Base).name() == colors["surface"]
    assert palette.color(QPalette.ColorRole.Text).name() == colors["text"]
    assert palette.color(QPalette.ColorRole.Highlight).name() == colors["accent"]
    assert (
        palette.color(QPalette.ColorRole.HighlightedText).name()
        == (colors["accent_text"])
    )
    assert qapp.styleSheet() == stylesheet("OLED")

    combo.hidePopup()
    dialog.close()
    apply_application_theme(qapp, "Breeze Dark")
