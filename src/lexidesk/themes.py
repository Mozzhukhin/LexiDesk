from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

THEMES: dict[str, dict[str, str]] = {
    "Breeze Dark": {
        "window": "#20242b",
        "surface": "#2a3038",
        "text": "#f1f3f5",
        "muted": "#aeb6c1",
        "accent": "#3daee9",
        "accent_text": "#07131a",
        "danger": "#e06c75",
        "warning": "#d6a85f",
        "success": "#78c091",
        "border": "#3b4450",
    },
    "Breeze Light": {
        "window": "#eff0f1",
        "surface": "#ffffff",
        "text": "#232629",
        "muted": "#6c737a",
        "accent": "#1d99f3",
        "accent_text": "#07131a",
        "danger": "#c0394a",
        "warning": "#a66b16",
        "success": "#2d8a57",
        "border": "#c9cdd1",
    },
    "OLED": {
        "window": "#050505",
        "surface": "#111111",
        "text": "#ffffff",
        "muted": "#a0a0a0",
        "accent": "#00b7ff",
        "accent_text": "#001018",
        "danger": "#ff5570",
        "warning": "#ffc266",
        "success": "#50e38a",
        "border": "#2a2a2a",
    },
    "Forest": {
        "window": "#17251d",
        "surface": "#223329",
        "text": "#eef7f0",
        "muted": "#a9bcae",
        "accent": "#8bc34a",
        "accent_text": "#10200d",
        "danger": "#ef7a76",
        "warning": "#d6b15f",
        "success": "#82d49d",
        "border": "#3a5142",
    },
    "Purple": {
        "window": "#221b2e",
        "surface": "#302642",
        "text": "#f7f2ff",
        "muted": "#bdb0cf",
        "accent": "#b388ff",
        "accent_text": "#170d24",
        "danger": "#ff7597",
        "warning": "#e4b76f",
        "success": "#7ee0b8",
        "border": "#493b60",
    },
}


def apply_application_theme(
    app: QApplication,
    name: str,
    scale: int = 100,
) -> None:
    """Apply one consistent palette to native controls and popup windows."""
    colors = THEMES.get(name, THEMES["Breeze Dark"])
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)

    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors["window"],
        QPalette.ColorRole.WindowText: colors["text"],
        QPalette.ColorRole.Base: colors["surface"],
        QPalette.ColorRole.AlternateBase: colors["window"],
        QPalette.ColorRole.ToolTipBase: colors["surface"],
        QPalette.ColorRole.ToolTipText: colors["text"],
        QPalette.ColorRole.Text: colors["text"],
        QPalette.ColorRole.Button: colors["surface"],
        QPalette.ColorRole.ButtonText: colors["text"],
        QPalette.ColorRole.BrightText: colors["danger"],
        QPalette.ColorRole.Highlight: colors["accent"],
        QPalette.ColorRole.HighlightedText: colors["accent_text"],
        QPalette.ColorRole.Link: colors["accent"],
        QPalette.ColorRole.PlaceholderText: colors["muted"],
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.PlaceholderText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            role,
            QColor(colors["muted"]),
        )
    app.setPalette(palette)
    # Combo-box views and menus are separate top-level popup windows on
    # Windows, so an application stylesheet is required in addition to the
    # stylesheet inherited by each dialog.
    app.setStyleSheet(stylesheet(name, scale))


def stylesheet(name: str, scale: int = 100) -> str:
    colors = THEMES.get(name, THEMES["Breeze Dark"])
    factor = max(80, min(scale, 150)) / 100
    body = round(13 * factor)
    word = round(26 * factor)
    translation = round(19 * factor)
    return f"""
        QWidget {{
            color: {colors["text"]};
            font-family: "Noto Sans", sans-serif;
            font-size: {body}px;
        }}
        QMainWindow, QDialog {{
            background-color: {colors["window"]};
        }}
        QLabel {{
            background: transparent;
        }}
        QWidget#root {{
            background: {colors["window"]};
            border: 1px solid {colors["border"]};
            border-radius: 16px;
        }}
        QFrame#card {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 13px;
        }}
        QLabel#word {{
            font-size: {word}px;
            font-weight: 700;
        }}
        QLabel#translation {{
            color: {colors["accent"]};
            font-size: {translation}px;
            font-weight: 600;
        }}
        QLabel#muted, QLabel#metadata, QLabel#countdown {{
            color: {colors["muted"]};
        }}
        QLabel#example {{
            color: {colors["muted"]};
            background: {colors["window"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: 6px;
        }}
        QLabel#brand {{
            font-size: {round(11 * factor)}px;
            font-weight: 800;
            letter-spacing: 1px;
        }}
        QLabel#badge, QPushButton#badge {{
            color: {colors["muted"]};
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: 2px 7px;
            font-size: {round(10 * factor)}px;
            font-weight: 600;
        }}
        QLabel#modeBadge {{
            color: {colors["accent"]};
            font-size: {round(10 * factor)}px;
            font-weight: 700;
        }}
        QPushButton {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: 6px 10px;
        }}
        QPushButton:hover {{
            border-color: {colors["accent"]};
            background: {colors["window"]};
        }}
        QPushButton:pressed {{
            background: {colors["border"]};
        }}
        QPushButton[active="true"] {{
            color: {colors["accent"]};
            border-color: {colors["accent"]};
        }}
        QPushButton:disabled {{
            color: {colors["muted"]};
            background: {colors["window"]};
            border-color: {colors["border"]};
        }}
        QPushButton[role="rating"] {{
            min-height: 24px;
        }}
        QPushButton#know {{
            color: {colors["success"]};
            font-weight: 700;
        }}
        QPushButton#primary {{
            color: {colors["accent"]};
            font-weight: 700;
        }}
        QPushButton#unknown {{
            color: {colors["danger"]};
            font-weight: 700;
        }}
        QLabel#know {{
            color: {colors["success"]};
            font-weight: 700;
        }}
        QLabel#unknown {{
            color: {colors["danger"]};
            font-weight: 700;
        }}
        QLabel#hard {{
            color: {colors["warning"]};
            font-weight: 700;
        }}
        QPushButton#correctChoice {{
            color: {colors["success"]};
            border-color: {colors["success"]};
            font-weight: 700;
        }}
        QPushButton#wrongChoice {{
            color: {colors["danger"]};
            border-color: {colors["danger"]};
            font-weight: 700;
        }}
        QPushButton#hard {{
            color: {colors["warning"]};
            font-weight: 600;
        }}
        QPushButton#easy {{
            color: {colors["accent"]};
            font-weight: 600;
        }}
        QPushButton#secondary {{
            color: {colors["muted"]};
            background: transparent;
            border-color: transparent;
            padding: 4px 7px;
        }}
        QPushButton#secondary:hover {{
            color: {colors["text"]};
            background: {colors["surface"]};
            border-color: {colors["border"]};
        }}
        QPushButton#icon {{
            border: none;
            background: transparent;
            padding: 3px;
            min-width: 23px;
            min-height: 23px;
        }}
        QPushButton#icon:hover {{
            background: {colors["surface"]};
            border-radius: 7px;
        }}
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            border-radius: 7px;
            padding: 7px;
            selection-background-color: {colors["accent"]};
            selection-color: {colors["accent_text"]};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {colors["accent"]};
        }}
        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
            color: {colors["muted"]};
            background: {colors["window"]};
        }}
        QComboBox QAbstractItemView, QAbstractItemView {{
            background-color: {colors["surface"]};
            color: {colors["text"]};
            alternate-background-color: {colors["window"]};
            border: 1px solid {colors["border"]};
            outline: 0;
            selection-background-color: {colors["accent"]};
            selection-color: {colors["accent_text"]};
        }}
        QAbstractItemView::item {{
            min-height: 26px;
            padding: 3px 7px;
        }}
        QAbstractItemView::item:hover {{
            background: {colors["window"]};
            color: {colors["text"]};
        }}
        QAbstractItemView::item:selected {{
            background: {colors["accent"]};
            color: {colors["accent_text"]};
        }}
        QTableWidget {{
            background: {colors["surface"]};
            alternate-background-color: {colors["window"]};
            border: 1px solid {colors["border"]};
            gridline-color: {colors["border"]};
            selection-background-color: {colors["accent"]};
            selection-color: {colors["accent_text"]};
        }}
        QTableWidget::item {{
            padding: 5px;
        }}
        QHeaderView::section {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: none;
            border-right: 1px solid {colors["border"]};
            border-bottom: 1px solid {colors["border"]};
            padding: 7px;
        }}
        QMenu {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            padding: 5px;
        }}
        QMenu::item {{
            background: transparent;
            color: {colors["text"]};
            border-radius: 5px;
            padding: 6px 24px 6px 9px;
        }}
        QMenu::item:selected {{
            background: {colors["accent"]};
            color: {colors["accent_text"]};
        }}
        QMenu::item:disabled {{
            color: {colors["muted"]};
        }}
        QMenu::separator {{
            height: 1px;
            background: {colors["border"]};
            margin: 4px 7px;
        }}
        QTabWidget::pane {{
            background: {colors["window"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: {colors["surface"]};
            color: {colors["muted"]};
            border: 1px solid {colors["border"]};
            padding: 7px 13px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            color: {colors["accent"]};
            background: {colors["window"]};
            border-bottom-color: {colors["window"]};
            font-weight: 700;
        }}
        QTabBar::tab:hover:!selected {{
            color: {colors["text"]};
            border-color: {colors["accent"]};
        }}
        QScrollArea, QAbstractScrollArea::viewport {{
            background: {colors["window"]};
        }}
        QScrollBar:vertical {{
            background: {colors["window"]};
            width: 11px;
            margin: 0;
        }}
        QScrollBar:horizontal {{
            background: {colors["window"]};
            height: 11px;
            margin: 0;
        }}
        QScrollBar::handle {{
            background: {colors["border"]};
            border-radius: 5px;
            min-height: 24px;
            min-width: 24px;
        }}
        QScrollBar::handle:hover {{
            background: {colors["muted"]};
        }}
        QScrollBar::add-line, QScrollBar::sub-line,
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: transparent;
            border: none;
            width: 0;
            height: 0;
        }}
        QCheckBox {{
            spacing: 7px;
            color: {colors["text"]};
        }}
        QCheckBox:disabled {{
            color: {colors["muted"]};
        }}
        QGroupBox {{
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            margin-top: 9px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            color: {colors["muted"]};
            subcontrol-origin: margin;
            left: 9px;
            padding: 0 4px;
        }}
        QToolTip {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
        }}
        QProgressBar#countdown {{
            background: {colors["border"]};
            border: none;
            border-radius: 2px;
        }}
        QProgressBar#countdown::chunk {{
            background: {colors["accent"]};
            border-radius: 2px;
        }}
    """
