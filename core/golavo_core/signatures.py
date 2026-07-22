"""Small, dependency-light Minisign verifier for release and source-pack trust."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Golavo uses one public release identity for updater metadata, release checksums,
# and bundled source-pack manifests. The matching private key remains a GitHub
# Actions secret and is never present in the repository or application.
RELEASE_PUBLIC_KEY = (
    "untrusted comment: minisign public key\n"
    "RWSThEcV9IUiShiiuoXJLqLtPGcNWvMyHDbACD48bHGolaglLW5RdQxN"
)


def _unwrap_tauri(value: str, *, label: str) -> str:
    """Accept raw Minisign text or Tauri's Base64-wrapped text transport."""
    stripped = value.strip()
    if stripped.startswith("untrusted comment:"):
        return stripped
    if "\n" in stripped:
        raise ValueError(f"invalid minisign {label}")
    try:
        decoded = base64.b64decode(stripped, validate=True).decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid minisign {label}") from exc
    if not decoded.startswith("untrusted comment:"):
        raise ValueError(f"invalid minisign {label}")
    return decoded


def _packet(lines: list[str], index: int, *, label: str) -> bytes:
    try:
        return base64.b64decode(lines[index].strip(), validate=True)
    except (IndexError, ValueError) as exc:
        raise ValueError(f"invalid minisign {label}") from exc


def _public_packet(public_key_text: str) -> bytes:
    raw = _unwrap_tauri(public_key_text, label="public key")
    lines = [line for line in raw.splitlines() if line.strip()]
    index = 1 if lines and lines[0].startswith("untrusted comment:") else 0
    packet = _packet(lines, index, label="public key")
    if len(packet) != 42 or packet[:2] != b"Ed":
        raise ValueError("unsupported minisign public key")
    return packet


def verify_minisign(
    source_path: Path, signature_path: Path, public_key_text: str | None = None
) -> dict[str, str | bool]:
    """Verify a Minisign hashed Ed25519 signature and its trusted comment.

    Tauri's signer emits Minisign-compatible ``.sig`` files. Golavo verifies the
    primary Blake2b signature, key id, and global signature binding the trusted
    comment, so neither the payload nor signature metadata can be edited.
    """
    source_path = Path(source_path)
    signature_path = Path(signature_path)
    public_packet = _public_packet(
        public_key_text
        or os.environ.get("GOLAVO_PACK_SIGNATURE_PUBLIC_KEY", "").strip()
        or RELEASE_PUBLIC_KEY
    )
    raw_signature = _unwrap_tauri(
        signature_path.read_text(encoding="utf-8"), label="signature envelope"
    )
    lines = [line for line in raw_signature.splitlines() if line]
    if len(lines) < 4 or not lines[0].startswith("untrusted comment:"):
        raise ValueError("invalid minisign signature envelope")
    signature_packet = _packet(lines, 1, label="signature")
    if len(signature_packet) != 74 or signature_packet[:2] != b"ED":
        raise ValueError("unsupported minisign signature algorithm")
    if signature_packet[2:10] != public_packet[2:10]:
        raise ValueError("minisign signature key id does not match public key")
    if not lines[2].startswith("trusted comment: "):
        raise ValueError("missing minisign trusted comment")
    trusted_comment = lines[2].removeprefix("trusted comment: ")
    global_signature = _packet(lines, 3, label="global signature")
    if len(global_signature) != 64:
        raise ValueError("invalid minisign global signature")

    public_key = Ed25519PublicKey.from_public_bytes(public_packet[10:])
    try:
        public_key.verify(signature_packet[10:], hashlib.blake2b(source_path.read_bytes()).digest())
        public_key.verify(global_signature, signature_packet[10:] + trusted_comment.encode())
    except InvalidSignature as exc:
        raise ValueError(f"signature verification failed for {source_path}") from exc
    return {
        "verified": True,
        "algorithm": "minisign-ed25519-blake2b",
        "key_id": public_packet[2:10][::-1].hex(),
        "trusted_comment": trusted_comment,
    }
