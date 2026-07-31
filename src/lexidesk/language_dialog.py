from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .language_packages import (
    LanguagePackage,
    cached_catalog,
    install_package,
    package_for_pair,
    refresh_catalog,
)
from .languages import LANGUAGES, language_name
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

                install_package(package, report)
            self.completed.emit(self.packages)
        except Exception as error:
            logger.exception("Language package operation failed")
            self.failed.emit(str(error))


class LanguagePackagesPage(QWidget):
    languages_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: PackageWorker | None = None
        self._packages = cached_catalog()
        self._installed: set[str] = set()

        intro = QLabel(
            "Download a language once, then translate offline. LexiDesk installs "
            "both directions through English so the language can also be used "
            "with every other installed language."
        )
        intro.setWordWrap(True)

        self.languages = QTreeWidget()
        self.languages.setColumnCount(2)
        self.languages.setHeaderLabels(["Language", "Status"])
        self.languages.setRootIsDecorated(False)
        self.languages.setAlternatingRowColors(True)
        self.languages.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.languages.header().setStretchLastSection(False)
        self.languages.header().setSectionResizeMode(
            0, self.languages.header().ResizeMode.Stretch
        )
        self.languages.header().setSectionResizeMode(
            1, self.languages.header().ResizeMode.ResizeToContents
        )
        self.languages.currentItemChanged.connect(self._selection_changed)

        self.progress = QProgressBar()
        self.progress.hide()
        self.status = QLabel(
            "Installed languages are shown first; each group is alphabetical."
        )
        self.status.setWordWrap(True)
        self.refresh_button = QPushButton("Refresh language list")
        self.refresh_button.clicked.connect(self.refresh)
        self.install_button = QPushButton("Download selected language")
        self.install_button.clicked.connect(self.install_selected)

        actions = QHBoxLayout()
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        actions.addWidget(self.install_button)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.languages, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addLayout(actions)
        self._populate()

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def refresh(self) -> None:
        self._start(PackageWorker(), "Downloading the official language list…")

    def install_selected(self) -> None:
        item = self.languages.currentItem()
        code = str(item.data(0, Qt.ItemDataRole.UserRole) if item else "")
        if not code or code in self._installed:
            return
        selected = tuple(
            package
            for package in (
                package_for_pair(self._packages, code, "en"),
                package_for_pair(self._packages, "en", code),
            )
            if package is not None
        )
        if len(selected) != 2:
            QMessageBox.warning(
                self,
                "Language unavailable",
                "The official catalog does not provide both directions "
                "for this language.",
            )
            return
        self._start(
            PackageWorker(selected),
            f"Downloading {language_name(code)} for offline use…",
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
        if not isinstance(result, tuple):
            return
        if self._worker is not None and self._worker.packages is None:
            self._packages = result
            self.status.setText(
                f"Language list updated: {len(self._language_codes())} languages."
            )
        else:
            self.status.setText("Language installed and ready to use offline.")
            self.progress.setValue(100)
            self.languages_changed.emit()
        self._populate()

    def _failed(self, message: str) -> None:
        self.status.setText(f"Could not complete the operation: {message}")

    def _finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.refresh_button.setEnabled(True)
        self._selection_changed(self.languages.currentItem())

    def _language_codes(self) -> set[str]:
        catalog_codes = {
            code
            for package in self._packages
            for code in (package.source, package.target)
        }
        return catalog_codes or set(LANGUAGES)

    def _populate(self) -> None:
        current = self.languages.currentItem()
        current_code = str(current.data(0, Qt.ItemDataRole.UserRole) if current else "")
        registry = OfflineModelRegistry()
        pairs = registry.installed_pairs()
        codes = self._language_codes()
        has_english = any("en" in pair for pair in pairs)
        self._installed = {
            code
            for code in codes
            if (code == "en" and has_english)
            or (
                code != "en"
                and registry.route(code, "en") is not None
                and registry.route("en", code) is not None
            )
        }
        catalog_names = {
            package.source: package.source_name for package in self._packages
        } | {package.target: package.target_name for package in self._packages}
        ordered = sorted(
            codes,
            key=lambda code: (
                code not in self._installed,
                (
                    LANGUAGES[code].name
                    if code in LANGUAGES
                    else catalog_names.get(code, code.upper())
                ).casefold(),
            ),
        )
        self.languages.clear()
        selected_item: QTreeWidgetItem | None = None
        for code in ordered:
            name = (
                LANGUAGES[code].name
                if code in LANGUAGES
                else catalog_names.get(code, code.upper())
            )
            installed = code in self._installed
            status = "✓ Installed" if installed else "Not installed"
            if code == "en" and installed:
                status = "✓ Installed · core"
            item = QTreeWidgetItem([f"{name}  ·  {code.upper()}", status])
            item.setData(0, Qt.ItemDataRole.UserRole, code)
            if installed:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            self.languages.addTopLevelItem(item)
            if code == current_code:
                selected_item = item
        item_to_select = selected_item or self.languages.topLevelItem(0)
        if item_to_select is not None:
            self.languages.setCurrentItem(item_to_select)
        self._selection_changed(self.languages.currentItem())

    def _selection_changed(self, item: QTreeWidgetItem | None, *_args) -> None:
        code = str(item.data(0, Qt.ItemDataRole.UserRole) if item else "")
        installed = code in self._installed
        available = (
            bool(
                package_for_pair(self._packages, code, "en")
                and package_for_pair(self._packages, "en", code)
            )
            if code and code != "en"
            else False
        )
        self.install_button.setText(
            "Installed" if installed else "Download selected language"
        )
        self.install_button.setEnabled(not self.busy and not installed and available)


class LanguagePackagesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Offline languages")
        self.resize(600, 620)
        self.page = LanguagePackagesPage(self)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.page)
        layout.addWidget(buttons)

    def reject(self) -> None:
        if self.page.busy:
            QMessageBox.information(
                self,
                "Download in progress",
                "Wait for the current language download to finish.",
            )
            return
        super().reject()
