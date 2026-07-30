#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import argostranslate.package
import argostranslate.translate

PAIRS = (("en", "ru"), ("ru", "en"))


def installed_pairs() -> set[tuple[str, str]]:
    languages = argostranslate.translate.get_installed_languages()
    result: set[tuple[str, str]] = set()
    for source in languages:
        for target in languages:
            if source.code == target.code:
                continue
            try:
                source.get_translation(target)
            except Exception:
                continue
            result.add((source.code, target.code))
    return result


def main() -> int:
    current = installed_pairs()
    if all(pair in current for pair in PAIRS):
        for source, target in PAIRS:
            print(f"{source.upper()} → {target.upper()} is already installed.")
        print("Offline EN ↔ RU translation is ready.")
        return 0

    print("Updating the Argos package index…")
    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()

    for source, target in PAIRS:
        if (source, target) in current:
            print(f"{source.upper()} → {target.upper()} is already installed.")
            continue
        package = next(
            (
                item
                for item in available
                if item.from_code == source and item.to_code == target
            ),
            None,
        )
        if package is None:
            print(f"No Argos package found for {source} → {target}.", file=sys.stderr)
            return 1
        print(f"Downloading {source.upper()} → {target.upper()}…")
        model_path = package.download()
        print(f"Installing {Path(model_path).name}…")
        argostranslate.package.install_from_path(model_path)
        Path(model_path).unlink(missing_ok=True)

    print("Offline EN ↔ RU translation is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
