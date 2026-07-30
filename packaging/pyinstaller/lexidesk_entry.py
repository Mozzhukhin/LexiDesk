"""Entry point used by PyInstaller bundles."""

from lexidesk.main import main  # noqa: I001


if __name__ == "__main__":
    raise SystemExit(main())
