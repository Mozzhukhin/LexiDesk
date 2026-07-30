# Flatpak packaging

The manifest packages the standalone application. Plasma widgets cannot run
inside a Flatpak sandbox, so the native plasmoid is distributed by the Arch
package and the release archive instead.

The pinned dependency manifest is committed, so a release build does not need
network access to PyPI during the build phase:

```bash
flatpak-builder --force-clean --user --install-deps-from=flathub \
  --install build-flatpak packaging/flatpak/io.github.lexidesk.yml
```

The CPU-only PyTorch wheels are pinned separately in the main manifest because
they are published in PyTorch's wheel index rather than PyPI. PySide6 is
provided by Flathub's `io.qt.PySide.BaseApp` 6.9 base application.

Offline language packages must be imported into the sandbox data directory.
The application itself does not request network access.
