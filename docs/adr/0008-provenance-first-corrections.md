# ADR-0008: provenance-first local correction proposals

Status: accepted for Phase 6 implementation

## Decision

Golavo stores correction proposals locally, separated by license namespace. A
proposal is never an authoritative match fact. It may be shown only as a
clearly labelled annotation beside the unchanged source-backed value.

Every promotable proposal requires a registered HTTPS source URL and captured
evidence. Evidence pages are not fetched by Golavo. Pasted text is untrusted;
an exact excerpt found in a hash-verified local source generation may receive
the stronger `snapshot_verified` label.

External contribution is export-only. Golavo creates deterministic JSON and may
open a registry-controlled contribution page after a separate user action. It
never files an issue, opens a pull request, or transmits proposal contents.

## Trust ladder

1. `draft` and `evidence_attached` are untrusted local claims.
2. `validated_candidate` has passed schema, identity, license and conflict checks.
3. `accepted_local` is a user-visible local annotation, not an override.
4. `exported` and user-attested `submitted` do not change source authority.
5. Only a later source-pack refresh can update the canonical index.
6. Model eligibility remains governed by the independent cutoff and backtest gates.

## Isolation

Each license namespace uses its own SQLite database and evidence directory under
the writable application-support `corrections/` root. ODbL proposals remain
local and cannot be exported. Unknown sources remain quarantined and cannot be
validated, accepted, or exported.

Correction modules may read canonical match/context records for comparison but
core ingestion, sealing, settlement, calibration and artifact modules must not
import or read correction state.

## Explicit exclusions

No accounts, telemetry, central moderation, automatic evidence fetch, binary
attachments, correction import, fuzzy identity promotion, automatic submission,
background helper, or correction-derived model feature is part of this phase.
