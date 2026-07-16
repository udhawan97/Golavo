"""Runtime configuration for the local sidecar.

The desktop shell launches the FastAPI server on an ephemeral loopback port with
a per-launch bearer token and (optionally) a writable ledger directory. All of
that is passed through the environment so this read-only server never has to
hardcode a port, and so ``pytest`` (which sets none of it) keeps running with an
open, source-mode configuration.

Environment:
  GOLAVO_TOKEN      required launch token; when unset the API is unauthenticated
                    (source-mode dev + CI). The shell always sets it.
  GOLAVO_DATA_DIR   override for the ledger directory; defaults to the bundled
                    (read-only) ``data/artifacts`` resource.
"""

from __future__ import annotations

import os
from pathlib import Path

from golavo_core.resources import resource

# Internationals first, then the big-five club leagues in customary order. Each
# file is one league's frozen chronological evaluation. Resolved through the
# bundle-aware resolver so the frozen sidecar finds them under sys._MEIPASS.
_EVAL_SUMMARY_NAMES = (
    "eval_summary.json",
    "eval_summary_epl.json",
    "eval_summary_laliga.json",
    "eval_summary_bundesliga.json",
    "eval_summary_seriea.json",
    "eval_summary_ligue1.json",
)

# Header the desktop shell attaches to every request; compared against GOLAVO_TOKEN.
TOKEN_HEADER = "x-golavo-token"


def data_dir() -> Path:
    """Ledger directory the read-only API serves forecasts/calibration from.

    Prefers an explicit ``GOLAVO_DATA_DIR`` (the shell points this at a writable
    per-user location so future sealing can persist); otherwise the bundled
    ``data/artifacts`` resource, which ships empty — an honest empty ledger.
    """
    override = os.environ.get("GOLAVO_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return resource("data", "artifacts")


def refresh_dir() -> Path | None:
    """Writable root for immutable refresh generations, or None.

    An opt-in refresh pulls a fresh internationals snapshot into a per-user
    location so a newly published fixture becomes searchable and sealable without
    a reinstall. It sits beside the writable ledger (``GOLAVO_DATA_DIR``). In
    source/CI mode, where the ledger is the read-only bundled resource, there is
    no writable refresh root, so this returns None — source mode refreshes via the
    ``watch_and_seal`` script and a committed index instead.
    """
    override = os.environ.get("GOLAVO_DATA_DIR")
    if not override:
        return None
    return Path(override).expanduser().parent / "refresh"


def openligadb_dir() -> Path | None:
    """Writable root for the optional ODbL overlay, or ``None``.

    OpenLigaDB is deliberately outside both the CC0 refresh generations and the
    forecast ledger.  The desktop shell points ``GOLAVO_DATA_DIR`` at
    ``.../ledger``; the overlay therefore lives at the sibling path
    ``.../overlays/openligadb`` in Application Support.  Source/CI mode has no
    writable application root unless a test explicitly supplies one.
    """
    override = os.environ.get("GOLAVO_DATA_DIR")
    if not override:
        return None
    return Path(override).expanduser().parent / "overlays" / "openligadb"


def follows_dir() -> Path:
    """Local followed-match state under the mutable forecast ledger.

    The desktop updater already backs up the ledger recursively. Keeping this
    CC0-only user state beneath it makes follow history survive app updates while
    remaining physically separate from the sibling ODbL overlay.
    """
    return data_dir() / "follows"


def corrections_dir() -> Path | None:
    """Writable, license-separated correction root, or ``None`` in source mode.

    Corrections sit beside the ledger and refresh/overlay roots so no proposal
    bytes can be mistaken for an authoritative artifact or source pack. The
    desktop shell always supplies ``GOLAVO_DATA_DIR``; source mode is deliberately
    read-only unless a developer explicitly configures a writable data root.
    """
    override = os.environ.get("GOLAVO_DATA_DIR")
    if not override:
        return None
    return Path(override).expanduser().parent / "corrections"


def refreshed_pack_dir() -> Path | None:
    """The active generation's pinned international pack, or a legacy fallback.

    Generation resolution validates every declared artifact before returning a
    path. The legacy ``refresh/pack`` check keeps older test/runtime state safe
    during the one-version migration and can be removed after v0.14.
    """
    root = refresh_dir()
    if root is None:
        return None
    try:
        from golavo_server import refresh_state

        active = refresh_state.active_pack_dir()
    except (OSError, RuntimeError, ValueError):
        active = None
    if active is not None:
        return active
    legacy = root / "pack"
    return legacy if (legacy / "manifest.json").is_file() else legacy


def analysis_cache_dir() -> Path | None:
    """Writable directory for the on-demand council disk cache, or None.

    A content-addressed L2 cache so re-opening a match (or the same match after a
    restart) doesn't refit five models. It sits beside the writable ledger; in
    source/CI mode there is no writable root, so this returns None and the analysis
    memo stays in-process only.
    """
    override = os.environ.get("GOLAVO_DATA_DIR")
    if not override:
        return None
    return Path(override).expanduser().parent / "analysis-cache"


def sample_artifacts_dir() -> Path:
    """Bundled synthetic sample forecasts.

    A fresh desktop install has an empty writable ledger, so the API serves
    these read-only samples until the user has real sealed forecasts — otherwise
    the app opens to an empty shell. Each sample carries its own 'synthetic
    fixture' provenance, and calibration always reads the real ledger, so samples
    never skew the forward record.
    """
    return resource("data", "fixtures", "sample_artifacts")


def eval_summary_paths() -> tuple[Path, ...]:
    """The committed per-league evaluation summaries, in declared order."""
    return tuple(resource("docs", "handoff", name) for name in _EVAL_SUMMARY_NAMES)


def launch_token() -> str | None:
    """The required launch token, or None when the API should stay open."""
    token = os.environ.get("GOLAVO_TOKEN")
    return token or None
