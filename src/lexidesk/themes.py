from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "Breeze Dark": {
        "window": "#20242b",
        "surface": "#2a3038",
        "text": "#f1f3f5",
        "muted": "#aeb6c1",
        "accent": "#3daee9",
        "danger": "#e06c75",
        "success": "#78c091",
        "border": "#3b4450",
    },
    "Breeze Light": {
        "window": "#eff0f1",
        "surface": "#ffffff",
        "text": "#232629",
        "muted": "#6c737a",
        "accent": "#1d99f3",
        "danger": "#c0394a",
        "success": "#2d8a57",
        "border": "#c9cdd1",
    },
    "OLED": {
        "window": "#050505",
        "surface": "#111111",
        "text": "#ffffff",
        "muted": "#a0a0a0",
        "accent": "#00b7ff",
        "danger": "#ff5570",
        "success": "#50e38a",
        "border": "#2a2a2a",
    },
    "Forest": {
        "window": "#17251d",
        "surface": "#223329",
        "text": "#eef7f0",
        "muted": "#a9bcae",
        "accent": "#8bc34a",
        "danger": "#ef7a76",
        "success": "#82d49d",
        "border": "#3a5142",
    },
    "Purple": {
        "window": "#221b2e",
        "surface": "#302642",
        "text": "#f7f2ff",
        "muted": "#bdb0cf",
        "accent": "#b388ff",
        "danger": "#ff7597",
        "success": "#7ee0b8",
        "border": "#493b60",
    },
}


def stylesheet(name: str, scale: int = 100) -> str:
    colors = THEMES.get(name, THEMES["Breeze Dark"])
    factor = max(80, min(scale, 150)) / 100
    body = round(13 * factor)
    word = round(28 * factor)
    translation = round(20 * factor)
    return f"""
        QWidget {{
            color: {colors["text"]};
            font-family: "Noto Sans", sans-serif;
            font-size: {body}px;
        }}
        QWidget#root {{
            background: {colors["window"]};
            border: 1px solid {colors["border"]};
            border-radius: 18px;
        }}
        QFrame#card {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 14px;
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
        QPushButton {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 9px;
            padding: 8px 12px;
        }}
        QPushButton:hover {{
            border-color: {colors["accent"]};
        }}
        QPushButton#know {{
            color: {colors["success"]};
            font-weight: 700;
        }}
        QPushButton#unknown {{
            color: {colors["danger"]};
            font-weight: 700;
        }}
        QPushButton#icon {{
            border: none;
            background: transparent;
            padding: 5px;
            min-width: 25px;
        }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 7px;
            padding: 7px;
            selection-background-color: {colors["accent"]};
        }}
        QTableWidget {{
            background: {colors["surface"]};
            alternate-background-color: {colors["window"]};
            border: 1px solid {colors["border"]};
            gridline-color: {colors["border"]};
            selection-background-color: {colors["accent"]};
            selection-color: #ffffff;
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
            border: 1px solid {colors["border"]};
            padding: 5px;
        }}
        QMenu::item:selected {{
            background: {colors["accent"]};
        }}
        QDialog {{
            background: {colors["window"]};
        }}
        QToolTip {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
        }}
    """
