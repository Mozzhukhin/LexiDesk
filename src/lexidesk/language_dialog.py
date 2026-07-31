from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .language_packages import (
    LanguagePackage,
    cached_catalog,
    install_package,
    package_for_pair,
    refresh_catalog,
)
from .languages import language_label
from .model_translation import OfflineModelRegistry

logger = logging.getLogger(__name__)


class PackageWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progressed = Signal(int)

    def __init__(self, packages: tuple[LanguagePackage, ...] | None = None) -> None:
        super().__init__()
        self.packages = packages

    def run(self) -> None:
        try:
            if self.packages is None:
                self.completed.emit(refresh_catalog())
                return
            for index, package in enumerate(self.packages):
                offset = round(index * 100 / len(self.packages))
                span = 100 / len(self.packages)

                def report(
                    value: int, offset: int = offset, span: float = span
                ) -> None:
                    self.progressed.emit(min(100, round(offset + value * span / 100)))

                install_package(
                    package,
                    report,
                )
            self.completed.emit(self.packages)
        except Exception as error:
            logger.exception("Language package operation failed")
            self.failed.emit(str(error))


class LanguagePackagesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Offline language packages")
        self.setMinimumWidth(520)
        self._worker: PackageWorker | None = None
        self._packages = cached_catalog()

        self.installed_label = QLabel()
        self.installed_label.setWordWrap(True)
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(self._update_targets)
        self.both_directions = QCheckBox("Install both directions")
        self.both_directions.setChecked(True)
        self.progress = QProgressBar()
        self.progress.hide()
        self.status = QLabel(
            "Models are downloaded only on request. Translation is offline afterwards."
        )
        self.status.setWordWrap(True)

        self.refresh_button = QPushButton("Refresh online catalog")
        self.refresh_button.clicked.connect(self.refresh)
        self.install_button = QPushButton("Download and install")
        self.install_button.clicked.connect(self.install_selected)

        pair_row = QHBoxLayout()
        pair_row.addWidget(self.source_combo, 1)
        pair_row.addWidget(QLabel("→"))
        pair_row.addWidget(self.target_combo, 1)
        form = QFormLayout()
        form.addRow("Installed", self.installed_label)
        form.addRow("Language pair", pair_row)
        form.addRow("", self.both_directions)
        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.refresh_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.install_button)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addLayout(buttons_row)
        layout.addWidget(close_buttons)
        self._populate()
        self._update_installed()

    def refresh(self) -> None:
        self._start(PackageWorker(), "Downloading the official package catalog…")

    def install_selected(self) -> None:
        source = str(self.source_combo.currentData() or "")
        target = str(self.target_combo.currentData() or "")
        forward = package_for_pair(self._packages, source, target)
        if forward is None:
            QMessageBox.warning(
                self, "Package unavailable", "This pair is unavailable."
            )
            return
        selected = [forward]
        if self.both_directions.isChecked():
            reverse = package_for_pair(self._packages, target, source)
            if reverse is None:
                QMessageBox.warning(
                    self,
                    "Reverse package unavailable",
                    "Only the selected direction is available in the catalog.",
                )
            else:
                selected.append(reverse)
        self._start(
            PackageWorker(tuple(selected)),
            "Downloading and verifying the offline model…",
        )

    def _start(self, worker: PackageWorker, message: str) -> None:
        if self._worker is not None:
            return
        self._worker = worker
        self.status.setText(message)
        self.progress.setValue(0)
        self.progress.show()
        self.refresh_button.setEnabled(False)
        self.install_button.setEnabled(False)
        worker.progressed.connect(self.progress.setValue)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def _completed(self, result: object) -> None:
        if isinstance(result, tuple) and (
            not result or isinstance(result[0], LanguagePackage)
        ):
            if self._worker is not None and self._worker.packages is None:
                self._packages = result
                self._populate()
                self.status.setText(
                    f"Catalog updated: {len(result)} directions available."
                )
            else:
                self.status.setText(
                    "Language package installed. Restart LexiDesk to use it."
                )
                self.progress.setValue(100)
                self._update_installed()

    def _failed(self, message: str) -> None:
        self.status.setText(f"Could not complete the operation: {message}")

    def _finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.refresh_button.setEnabled(True)
        self.install_button.setEnabled(bool(self._packages))

    def _populate(self) -> None:
        current = self.source_combo.currentData()
        sources = sorted({package.source for package in self._packages})
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for code in sources:
            self.source_combo.addItem(language_label(code), code)
        index = self.source_combo.findData(current)
        self.source_combo.setCurrentIndex(max(0, index))
        self.source_combo.blockSignals(False)
        self._update_targets()
        self.install_button.setEnabled(bool(self._packages))

    def _update_targets(self) -> None:
        source = str(self.source_combo.currentData() or "")
        current = self.target_combo.currentData()
        targets = sorted(
            {package.target for package in self._packages if package.source == source}
        )
        self.target_combo.clear()
        for code in targets:
            self.target_combo.addItem(language_label(code), code)
        index = self.target_combo.findData(current)
        self.target_combo.setCurrentIndex(max(0, index))

    def _update_installed(self) -> None:
        pairs = OfflineModelRegistry().installed_pairs()
        self.installed_label.setText(
            ", ".join(f"{source.upper()}→{target.upper()}" for source, target in pairs)
            or "No translation models found"
        )

    def reject(self) -> None:
        if self._worker is not None:
            QMessageBox.information(
                self,
                "Download in progress",
                "Wait for the current package operation to finish.",
            )
            return
        super().reject()
