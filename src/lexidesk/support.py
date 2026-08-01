from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

SUPPORT_ASSET = "USDT"
SUPPORT_NETWORK = "TRON (TRC20)"
SUPPORT_ADDRESS = "TCJxcsKVhm2Mjs7q5XkVvLK492XLpnY8um"


class SupportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Support the developer")
        self.setMinimumWidth(430)

        title = QLabel("Support LexiDesk development")
        title.setObjectName("dialogTitle")

        description = QLabel(
            "If LexiDesk is useful to you, you can support its continued "
            "development. This is completely optional."
        )
        description.setWordWrap(True)

        network = QLabel(f"{SUPPORT_ASSET} · {SUPPORT_NETWORK}")
        network.setObjectName("metadata")

        self.address_label = QLineEdit(SUPPORT_ADDRESS)
        self.address_label.setReadOnly(True)
        self.address_label.setCursorPosition(0)
        self.address_label.setToolTip("USDT TRC20 wallet address")

        self.copy_button = QPushButton("Copy address")
        self.copy_button.clicked.connect(self.copy_address)

        address_row = QHBoxLayout()
        address_row.addWidget(self.address_label, 1)
        address_row.addWidget(self.copy_button)

        warning = QLabel("Send only USDT using the TRON (TRC20) network.")
        warning.setObjectName("muted")
        warning.setWordWrap(True)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(4)
        layout.addWidget(network)
        layout.addLayout(address_row)
        layout.addWidget(warning)
        layout.addSpacing(6)
        layout.addLayout(actions)

    def copy_address(self) -> None:
        QApplication.clipboard().setText(SUPPORT_ADDRESS)
        self.copy_button.setText("Copied")
