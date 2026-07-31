from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "Breeze Dark": {
        "window": "#20242b",
        "surface": "#2a3038",
        "text": "#f1f3f5",
        "muted": "#aeb6c1",
        "accent": "#3daee9",
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
        "danger": "#ff7597",
        "warning": "#e4b76f",
        "success": "#7ee0b8",
        "border": "#493b60",
    },
}


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
        QLabel#badge {{
            color: {colors["muted"]};
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: 2px 7px;
            font-size: {round(10 * factor)}px;
            font-weight: 600;
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
            border-color: transparent;
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
