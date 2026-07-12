#!/usr/bin/env python3
"""Bump (or verify) the single project version across every file that hardcodes it.

Golavo's version lives in several files that must always agree — the desktop
updater compares the version compiled into tauri.conf.json against release tags,
so a stale spot silently breaks in-app updates forever.

Usage:
    python scripts/bump_version.py 0.2.0           # rewrite every spot
    python scripts/bump_version.py --check         # verify all spots agree
    python scripts/bump_version.py --check v0.2.0  # ...and match this tag (CI guard)
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SEMVER = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?"

# (relative path, template containing {v}, expected occurrence count).
# Templates are anchored enough to never touch dependency pins.
SPOTS: list[tuple[str, str, int]] = [
    ("desktop/src-tauri/tauri.conf.json", '"version": "{v}"', 1),
    ("desktop/src-tauri/Cargo.toml", 'version = "{v}"', 1),
    ("desktop/src-tauri/Cargo.lock", 'name = "golavo-desktop"\nversion = "{v}"', 1),
    ("desktop/package.json", '"version": "{v}"', 1),
    ("ui/package.json", '"version": "{v}"', 1),
    ("docs-site/package.json", '"version": "{v}"', 1),
    ("core/pyproject.toml", 'version = "{v}"', 1),
    ("server/pyproject.toml", 'version = "{v}"', 1),
    ("core/golavo_core/__init__.py", '__version__ = "{v}"', 1),
    ("server/golavo_server/__init__.py", '__version__ = "{v}"', 1),
    # Leading newline anchors past the "cff-version:" header line.
    ("CITATION.cff", "\nversion: {v}", 1),
    # Docs-site hardcoded "current version" mentions — these drift silently
    # because docs-site's build succeeds either way; only this check catches it.
    ("docs-site/src/components/Hero.astro", ">v{v} · unsigned pre-alpha · local-first", 1),
    ("docs-site/src/content/docs/index.mdx", "unsigned v{v} pre-alpha", 1),
    ("docs-site/src/content/docs/index.mdx", "Golavo is at **v{v}**", 1),
]


def _template_regex(template: str) -> re.Pattern[str]:
    """Turn a {v} template into a regex capturing the version it holds."""
    return re.compile(re.escape(template).replace(re.escape("{v}"), f"({SEMVER})"))


def read_versions(root: Path) -> list[str]:
    """The version found at each SPOTS entry, in order.

    Indexed by position, NOT by file path: several files (index.mdx) carry more
    than one independent spot, and keying by path would let a later spot's
    reading silently overwrite an earlier one for the same file — masking a real
    mismatch between two hardcoded mentions in one document.
    """
    found: list[str] = []
    for rel, template, count in SPOTS:
        text = (root / rel).read_text(encoding="utf-8")
        matches = _template_regex(template).findall(text)
        if len(matches) != count:
            raise SystemExit(
                f"{rel}: expected exactly {count} version spot(s) matching "
                f"{template!r}, found {len(matches)}"
            )
        found.append(matches[0])
    return found


def check(root: Path, expected: str | None) -> None:
    versions = read_versions(root)
    unique = sorted(set(versions))
    if len(unique) != 1:
        detail = "\n".join(
            f"  {rel} ({template!r}): {v}"
            for (rel, template, _count), v in zip(SPOTS, versions, strict=True)
        )
        raise SystemExit(f"version spots disagree:\n{detail}")
    current = unique[0]
    if expected is not None and current != expected:
        raise SystemExit(f"version is {current}, expected {expected} (from the tag)")
    print(f"all {len(versions)} version spots agree: {current}")


def bump(root: Path, new: str) -> None:
    if not re.fullmatch(SEMVER, new):
        raise SystemExit(f"not a semver version: {new!r}")
    versions = read_versions(root)
    current = versions[0]
    if new == current:
        raise SystemExit(f"already at {new}")
    for (rel, template, count), old_version in zip(SPOTS, versions, strict=True):
        path = root / rel
        text = path.read_text(encoding="utf-8")
        old = template.format(v=old_version)
        replaced = text.replace(old, template.format(v=new))
        if replaced == text:
            raise SystemExit(f"{rel}: could not rewrite {old!r}")
        path.write_text(replaced, encoding="utf-8")
        print(f"  {rel}: {old_version} -> {new} ({count} spot)")
    # A release bump is a release event: refresh the citation date alongside.
    citation = root / "CITATION.cff"
    text = citation.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()
    text = re.sub(r'date-released: "\d{4}-\d{2}-\d{2}"', f'date-released: "{today}"', text)
    citation.write_text(text, encoding="utf-8")
    check(root, new)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="new version, e.g. 0.2.0")
    parser.add_argument(
        "--check",
        nargs="?",
        const="",
        default=None,
        metavar="TAG",
        help="verify all spots agree; with a value (tag or version), also match it",
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.check is not None:
        expected = args.check.lstrip("v") or None
        check(args.root, expected)
        return 0
    if not args.version:
        parser.error("give a new version to bump to, or --check to verify")
    bump(args.root, args.version.lstrip("v"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
