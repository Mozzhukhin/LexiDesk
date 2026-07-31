from __future__ import annotations

from PySide6.QtWidgets import QApplication

from lexidesk.support import SUPPORT_ADDRESS, SUPPORT_NETWORK, SupportDialog


def test_support_dialog_copies_public_trc20_address() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SupportDialog()

    dialog.copy_address()

    assert SUPPORT_NETWORK == "TRON (TRC20)"
    assert app.clipboard().text() == SUPPORT_ADDRESS
    assert dialog.copy_button.text() == "Copied"
