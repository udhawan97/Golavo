#!/usr/bin/env python3
"""Assemble (or validate) the Tauri updater manifest — latest.json — for a release.

generate: scan a dist directory of release assets for updater artifacts and their
detached .sig files, then emit one manifest covering every shipped installer:

    darwin-aarch64       <- *.app.tar.gz   (Tauri emits it unversioned as
                            "Golavo.app.tar.gz"; we normalize the file name to
                            Golavo_<version>_aarch64.app.tar.gz so a second macOS
                            arch can never collide inside one release)
    windows-x86_64-nsis  <- *-setup.exe
    windows-x86_64-msi   <- *.msi

The installer-specific Windows keys matter: the updater plugin resolves
{os}-{arch}-{installer} first, so MSI installs update via MSI and NSIS via NSIS —
never NSIS-over-MSI (duplicate installs).

validate: re-parse a manifest and hard-fail on anything the updater plugin would
choke on at runtime: missing platform keys, empty signatures, a non-RFC3339
pub_date (which fails the WHOLE manifest deserialization), or URLs that do not
point at files present in dist.

Usage:
    make_update_manifest.py generate --dist dist --version 0.2.0 --tag v0.2.0 \
        --repo udhawan97/Golavo [--notes-file NOTES.md] [--out dist/latest.json]
    make_update_manifest.py validate --manifest dist/latest.json --dist dist --tag v0.2.0
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
from pathlib import Path

REQUIRED_PLATFORMS = ("darwin-aarch64", "windows-x86_64-nsis", "windows-x86_64-msi")
SEMVER = re.compile(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?$")


def _single(dist: Path, pattern: str, describe: str) -> Path:
    """Exactly one artifact may match; zero or several means a broken release."""
    matches = sorted(p for p in dist.glob(pattern) if not p.name.endswith(".sig"))
    if len(matches) != 1:
        names = ", ".join(p.name for p in matches) or "none"
        raise SystemExit(f"expected exactly one {describe} in {dist} ({pattern}): {names}")
    return matches[0]


def _signature(artifact: Path) -> str:
    sig = artifact.with_name(artifact.name + ".sig")
    if not sig.is_file():
        raise SystemExit(f"missing detached signature for {artifact.name}: {sig.name}")
    content = sig.read_text(encoding="utf-8").strip()
    if not content:
        raise SystemExit(f"empty signature file: {sig.name}")
    return content


def _normalize_macos_name(dist: Path, version: str) -> Path:
    """Rename the unversioned macOS updater tarball (and its .sig) in place."""
    tarball = _single(dist, "*.app.tar.gz", "macOS updater tarball")
    if f"_{version}_" in tarball.name:
        return tarball
    stem = tarball.name.removesuffix(".app.tar.gz")
    renamed = dist / f"{stem}_{version}_aarch64.app.tar.gz"
    tarball.rename(renamed)
    old_sig = tarball.with_name(tarball.name + ".sig")
    if old_sig.is_file():
        old_sig.rename(renamed.with_name(renamed.name + ".sig"))
    print(f"  normalized {tarball.name} -> {renamed.name}")
    return renamed


def generate(args: argparse.Namespace) -> None:
    dist: Path = args.dist
    version = args.version.lstrip("v")
    artifacts = {
        "darwin-aarch64": _normalize_macos_name(dist, version),
        "windows-x86_64-nsis": _single(dist, "*-setup.exe", "NSIS installer"),
        "windows-x86_64-msi": _single(dist, "*.msi", "MSI installer"),
    }
    base = f"https://github.com/{args.repo}/releases/download/{args.tag}"
    platforms = {
        key: {
            "signature": _signature(path),
            "url": f"{base}/{urllib.parse.quote(path.name)}",
        }
        for key, path in artifacts.items()
    }
    manifest = {
        "version": version,
        "notes": (
            args.notes_file.read_text(encoding="utf-8").strip()
            if args.notes_file
            else f"Golavo {version} — see the release page for details."
        ),
        "pub_date": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": platforms,
    }
    out: Path = args.out or dist / "latest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} covering: {', '.join(platforms)}")


def validate(args: argparse.Namespace) -> None:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    problems: list[str] = []

    version = manifest.get("version", "")
    if not SEMVER.match(version):
        problems.append(f"version is not semver: {version!r}")

    pub_date = manifest.get("pub_date")
    if pub_date is not None:
        # The plugin rejects the ENTIRE manifest on a bad pub_date — so do we.
        try:
            dt.datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        except ValueError:
            problems.append(f"pub_date is not RFC 3339: {pub_date!r}")

    platforms = manifest.get("platforms", {})
    for key in REQUIRED_PLATFORMS:
        entry = platforms.get(key)
        if entry is None:
            problems.append(f"missing platform key: {key}")
            continue
        if not entry.get("signature", "").strip():
            problems.append(f"{key}: empty signature")
        url = entry.get("url", "")
        if args.tag and f"/releases/download/{args.tag}/" not in url:
            problems.append(f"{key}: url does not point at tag {args.tag}: {url}")
        name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        if args.dist and not (args.dist / name).is_file():
            problems.append(f"{key}: url names {name}, which is not in {args.dist}")

    if problems:
        raise SystemExit("latest.json validation failed:\n" + "\n".join(f"  {p}" for p in problems))
    print(f"latest.json OK: v{version.lstrip('v')}, platforms {', '.join(sorted(platforms))}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="scan dist/ and emit latest.json")
    gen.add_argument("--dist", type=Path, required=True)
    gen.add_argument("--version", required=True)
    gen.add_argument("--tag", required=True)
    gen.add_argument("--repo", required=True, help="owner/name")
    gen.add_argument("--notes-file", type=Path, default=None)
    gen.add_argument("--out", type=Path, default=None)
    gen.set_defaults(func=generate)

    val = sub.add_parser("validate", help="hard-fail on a manifest the updater would reject")
    val.add_argument("--manifest", type=Path, required=True)
    val.add_argument("--dist", type=Path, default=None)
    val.add_argument("--tag", default=None)
    val.set_defaults(func=validate)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
