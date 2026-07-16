from __future__ import annotations

import subprocess

from golavo_core import artifacts


def test_injected_release_sha_is_authoritative(monkeypatch) -> None:
    sha = "a" * 40
    monkeypatch.setenv("GOLAVO_SOURCE_SHA", sha.upper())
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("git must not run")),
    )
    assert artifacts._code_sha() == sha


def test_invalid_injected_sha_fails_closed_when_git_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_SOURCE_SHA", "0000000")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    assert artifacts._code_sha() == "0000000"
