#!/usr/bin/env python3
"""List active pack manifests in a shell-portable release-build format."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from golavo_core.packstore import active_packs


def active_manifest_paths(root: Path) -> tuple[str, ...]:
    """Return repository-relative POSIX paths for every active manifest."""
    root = root.resolve()
    registry = root / "packs/snapshots.json"
    resolve = lambda declared: (root / declared).resolve()  # noqa: E731
    paths = []
    for pack in active_packs(registry, resolve=resolve):
        manifest = (pack.directory / "manifest.json").resolve()
        paths.append(manifest.relative_to(root).as_posix())
    return tuple(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--null",
        action="store_true",
        help="separate paths with NUL bytes instead of platform text newlines",
    )
    args = parser.parse_args(argv)

    delimiter = b"\0" if args.null else b"\n"
    paths = active_manifest_paths(args.root)
    if paths:
        sys.stdout.buffer.write(delimiter.join(path.encode("utf-8") for path in paths))
        sys.stdout.buffer.write(delimiter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
