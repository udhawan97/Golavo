"""The client's retrospective types must not drift from the frozen contract.

``ui/src/lib/contract.ts`` hand-mirrors ``docs/contracts/*.schema.json``: two
sources of truth for one schema, kept in agreement by whoever remembers. The
schema is the owner; this fails when the mirror stops matching it, so a field
added on one side cannot ship without the other.

Deliberately structural, not a parser: it checks that every field the contract
REQUIRES appears in the mirrored interface, which is the drift that actually
breaks a reader (a required field the client never reads). Optional and
permissive fields stay the client's business — the contract itself declares
``additionalProperties: true`` for the fold precisely so evaluation.py can add a
metric without a client release.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT = _ROOT / "docs" / "contracts" / "tournament_retrospective.schema.json"
_MIRROR = _ROOT / "ui" / "src" / "lib" / "contract.ts"

# schema $def -> the interface mirroring it in contract.ts. SnapshotAgreement is
# deliberately absent: the client models it as a discriminated UNION of its three
# states rather than one interface, which is a sharper reading of the contract than
# this structural check could express.
_MIRRORED = {
    "TrustFold": "TrustFold",
    "TrustFoldModel": "TrustFoldModel",
    "TrustUnavailable": "TrustUnavailable",
    "Row": "RetrospectiveRow",
}


def _schema() -> dict:
    return json.loads(_CONTRACT.read_text(encoding="utf-8"))


def _interface_body(name: str) -> str:
    source = _MIRROR.read_text(encoding="utf-8")
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.DOTALL)
    assert match is not None, f"contract.ts no longer declares interface {name}"
    return match.group(1)


@pytest.mark.parametrize(("def_name", "interface"), sorted(_MIRRORED.items()))
def test_every_required_contract_field_is_mirrored(def_name: str, interface: str) -> None:
    definition = _schema()["$defs"][def_name]
    body = _interface_body(interface)

    missing = [
        field
        for field in definition.get("required", [])
        if not re.search(rf"^\s+{re.escape(field)}\??:", body, re.MULTILINE)
    ]

    assert not missing, (
        f"{interface} in ui/src/lib/contract.ts is missing required field(s) "
        f"{missing} from {def_name} in {_CONTRACT.name}"
    )


@pytest.mark.parametrize(("def_name", "interface"), sorted(_MIRRORED.items()))
def test_no_required_contract_field_is_mirrored_as_optional(
    def_name: str, interface: str
) -> None:
    """A required field typed ``field?:`` invites a client to handle an absence the
    contract promises can never happen — the drift that reads as defensive code."""
    definition = _schema()["$defs"][def_name]
    body = _interface_body(interface)

    optional = [
        field
        for field in definition.get("required", [])
        if re.search(rf"^\s+{re.escape(field)}\?:", body, re.MULTILINE)
    ]

    assert not optional, (
        f"{interface} types {optional} as optional, but {def_name} requires them"
    )
