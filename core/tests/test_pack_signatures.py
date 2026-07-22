from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from golavo_core.ingest.snapshot import validate_pack
from golavo_core.signatures import RELEASE_PUBLIC_KEY, verify_minisign


def _minisign_fixture(
    payload: bytes, *, trusted_comment: str = "timestamp:1784678400"
) -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    key_id = bytes.fromhex("4b844715f485224a")
    public_packet = b"Ed" + key_id + public
    signature_packet = b"ED" + key_id + private.sign(hashlib.blake2b(payload).digest())
    global_signature = private.sign(signature_packet[10:] + trusted_comment.encode())
    public_text = (
        "untrusted comment: minisign public key\n" + base64.b64encode(public_packet).decode()
    )
    signature_text = "\n".join(
        (
            "untrusted comment: signature from minisign secret key",
            base64.b64encode(signature_packet).decode(),
            f"trusted comment: {trusted_comment}",
            base64.b64encode(global_signature).decode(),
            "",
        )
    )
    return public_text, signature_text


def _pack(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "data.txt").write_text("verified bytes\n", encoding="utf-8")
    manifest = {
        "source_id": "test-source",
        "upstream_ref": "a" * 40,
        "url": "https://example.test/source",
        "retrieved_at_utc": "2026-07-21T00:00:00Z",
        "license": "CC0-1.0",
        "files": [
            {
                "name": "data.txt",
                "sha256": hashlib.sha256((pack / "data.txt").read_bytes()).hexdigest(),
            }
        ],
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    return pack


def test_pack_verifier_release_identity_matches_tauri_updater() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads(
        (root / "desktop/src-tauri/tauri.updater.conf.json").read_text(encoding="utf-8")
    )
    updater_key = base64.b64decode(config["plugins"]["updater"]["pubkey"]).decode()

    assert RELEASE_PUBLIC_KEY.strip().splitlines()[1] == updater_key.strip().splitlines()[1]


def test_minisign_verifier_accepts_hashed_signature_and_global_comment(tmp_path: Path) -> None:
    payload = b"Golavo signed pack\n"
    public_key, signature = _minisign_fixture(payload)
    source = tmp_path / "manifest.json"
    source.write_bytes(payload)
    sig = tmp_path / "manifest.json.sig"
    sig.write_text(signature)

    result = verify_minisign(source, sig, public_key)

    assert result["verified"] is True
    assert result["algorithm"] == "minisign-ed25519-blake2b"
    assert result["key_id"] == "4a2285f41547844b"


def test_minisign_verifier_accepts_tauri_base64_transport(tmp_path: Path) -> None:
    payload = b"tauri transport"
    public_key, signature = _minisign_fixture(payload)
    source = tmp_path / "manifest.json"
    source.write_bytes(payload)
    sig = tmp_path / "manifest.json.sig"
    sig.write_text(base64.b64encode(signature.encode()).decode())

    wrapped_public_key = base64.b64encode(public_key.encode()).decode()
    assert verify_minisign(source, sig, wrapped_public_key)["verified"] is True


def test_minisign_verifier_rejects_tampered_bytes(tmp_path: Path) -> None:
    public_key, signature = _minisign_fixture(b"original")
    source = tmp_path / "manifest.json"
    source.write_bytes(b"tampered")
    sig = tmp_path / "manifest.json.sig"
    sig.write_text(signature)

    with pytest.raises(ValueError, match="signature verification failed"):
        verify_minisign(source, sig, public_key)


def test_pack_accepts_a_verified_manifest_signature(monkeypatch, tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    public_key, signature = _minisign_fixture((pack / "manifest.json").read_bytes())
    (pack / "manifest.json.sig").write_text(signature)
    monkeypatch.setenv("GOLAVO_PACK_SIGNATURE_PUBLIC_KEY", public_key)

    manifest = validate_pack(pack)

    assert manifest["source_id"] == "test-source"


def test_pack_rejects_a_bad_manifest_signature_even_in_source_mode(
    monkeypatch, tmp_path: Path
) -> None:
    pack = _pack(tmp_path)
    public_key, signature = _minisign_fixture(b"different manifest")
    (pack / "manifest.json.sig").write_text(signature)
    monkeypatch.setenv("GOLAVO_PACK_SIGNATURE_PUBLIC_KEY", public_key)

    with pytest.raises(ValueError, match="signature verification failed"):
        validate_pack(pack)


def test_packaged_mode_requires_a_manifest_signature(monkeypatch, tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    monkeypatch.setenv("GOLAVO_REQUIRE_SIGNED_PACKS", "1")

    with pytest.raises(ValueError, match="missing manifest signature"):
        validate_pack(pack)


def test_unsigned_local_frozen_build_does_not_claim_official_pack_signatures(
    monkeypatch, tmp_path: Path
) -> None:
    pack = _pack(tmp_path)
    monkeypatch.setattr("golavo_core.resources.is_frozen", lambda: True)
    monkeypatch.setattr("golavo_core.resources.resource_root", lambda: tmp_path)

    assert validate_pack(pack)["source_id"] == "test-source"


def test_official_frozen_marker_requires_every_pack_signature(monkeypatch, tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    marker = tmp_path / "packs" / ".signatures-required"
    marker.parent.mkdir()
    marker.touch()
    monkeypatch.setattr("golavo_core.resources.is_frozen", lambda: True)
    monkeypatch.setattr("golavo_core.resources.resource_root", lambda: tmp_path)

    with pytest.raises(ValueError, match="missing manifest signature"):
        validate_pack(pack)
