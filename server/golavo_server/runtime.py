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
