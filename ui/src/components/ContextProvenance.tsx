import type {
  ConditionsSnapshot,
  ContextClaim,
  ContextDerivation,
} from "../lib/contract";

const SOURCE_LABELS: Record<string, string> = {
  geonames: "GeoNames",
  "natural-earth": "Natural Earth",
  "openfootball-worldcup-json": "openfootball/worldcup.json",
  wikidata: "Wikidata",
  "martj42-international-results": "international_results",
};

const SOURCE_TAG_LABELS: Record<string, string> = {
  "openfootball-worldcup-json": "OpenFootball",
  "martj42-international-results": "international_results",
};

export function contextSourceLabel(sourceId: string | null | undefined): string {
  if (!sourceId) return "No source available";
  return SOURCE_LABELS[sourceId] ?? sourceId;
}

export function claimSourceId(claim: ContextClaim | undefined): string | null {
  return claim?.source_refs[0]?.source_id ?? null;
}

export function FactSource({
  sourceId,
  derived = false,
}: {
  sourceId: string | null | undefined;
  derived?: boolean;
}) {
  const label = contextSourceLabel(sourceId);
  const tagLabel = sourceId ? (SOURCE_TAG_LABELS[sourceId] ?? label) : label;
  return (
    <span className="context-source-tag" title={sourceId ? `Source ID: ${sourceId}` : undefined}>
      {derived ? "Derived · " : "Source · "}{tagLabel}
    </span>
  );
}

function Method({ derivation }: { derivation: ContextDerivation }) {
  return (
    <li>
      <b>{derivation.algorithm_id}</b> <span className="muted">v{derivation.algorithm_version}</span>
      <span>{derivation.formula}</span>
    </li>
  );
}

export function ContextProvenance({ snapshot }: { snapshot: ConditionsSnapshot }) {
  const methods = new Map<string, ContextDerivation>();
  for (const team of snapshot.teams) {
    for (const derivation of [team.kickoff_gap.derivation, team.travel.derivation]) {
      if (derivation) methods.set(`${derivation.algorithm_id}:${derivation.algorithm_version}`, derivation);
    }
  }
  if (snapshot.match.local_kickoff.derivation) {
    const derivation = snapshot.match.local_kickoff.derivation;
    methods.set(`${derivation.algorithm_id}:${derivation.algorithm_version}`, derivation);
  }

  return (
    <details className="context-provenance">
      <summary>
        Sources, coverage and calculations
        <span>{snapshot.sources.length} pinned sources · pack {snapshot.capability.context_pack_version ?? "unavailable"}</span>
      </summary>
      <div className="context-provenance__body">
        <section aria-labelledby="context-coverage-title">
          <h3 id="context-coverage-title">Coverage</h3>
          <p>
            Coverage is <b>{snapshot.capability.status}</b>. Venue coverage is currently a reviewed
            subset, and schedule gaps only describe matches present in Golavo’s local index.
          </p>
          <ul className="context-provenance__limits">
            {snapshot.capability.reason_codes.map((reason) => (
              <li key={reason}>{reason.replaceAll("-", " ")}</li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="context-sources-title">
          <h3 id="context-sources-title">Pinned sources</h3>
          <ul className="context-provenance__sources">
            {snapshot.sources.map((source) => (
              <li key={source.source_id}>
                <b>{contextSourceLabel(source.source_id)}</b>
                <span>{source.attribution}</span>
                <span className="muted">{source.license} · revision {source.upstream_ref}</span>
              </li>
            ))}
          </ul>
        </section>

        {methods.size > 0 && (
          <section aria-labelledby="context-methods-title">
            <h3 id="context-methods-title">Deterministic calculations</h3>
            <ul className="context-provenance__methods">
              {[...methods.values()].map((derivation) => (
                <Method key={`${derivation.algorithm_id}:${derivation.algorithm_version}`} derivation={derivation} />
              ))}
            </ul>
          </section>
        )}

        <p className="context-provenance__boundary">
          Display only. These facts and calculations are not model inputs and do not alter sealed forecasts.
        </p>
      </div>
    </details>
  );
}
