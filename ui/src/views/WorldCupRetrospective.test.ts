import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { FAMILY_LABELS } from "../lib/contract";
import type { TournamentRetrospective, TrustFold } from "../lib/contract";
import { WorldCupRetrospectiveBody } from "./WorldCupRetrospective";

const TRUST: TrustFold = {
  status: "available",
  fold_id: "WC2026",
  competition: "FIFA World Cup",
  // Reconciles with DATA.coverage.scored. A fixture whose layers disagree fires
  // the cross-layer warning on every unrelated test, which is how that warning
  // went 16 tests without a single assertion in either direction.
  n_matches: 2,
  training_cutoff_utc: "2026-06-10T00:00:00Z",
  window_start: "2026-06-11",
  window_end: "2026-07-19",
  // Exactly what the sidecar sends: it projects evaluation.py's five-family fold
  // onto the story's four voices and names what it dropped. This view renders that
  // decision; it no longer re-derives it (server/golavo_server/retrospective.py).
  models: [
    { family: "climatological", log_loss: 1.05, brier: 0.66 },
    { family: "elo_ordlogit", log_loss: 0.98, brier: 0.61 },
    { family: "poisson_independent", log_loss: 1.01, brier: 0.63 },
    { family: "dixon_coles", log_loss: 0.99, brier: 0.62 },
  ],
  omitted_families: ["bivariate_poisson"],
};

const DATA: TournamentRetrospective = {
  schema_version: "0.1.0",
  status: "available",
  label:
    "Tournament retrospective — every match backtested at its own pre-kickoff cutoff. A backtest, not a sealed record.",
  tournament_id: "worldcup-2026",
  tournament_name: "2026 FIFA World Cup",
  ledger_status: "never_persisted_or_scored_as_a_seal",
  ranking_family: "dixon_coles",
  ranking_metric: "log_loss",
  families: ["climatological", "elo_ordlogit", "poisson_independent", "dixon_coles"],
  window_start: "2026-06-11",
  window_end: "2026-07-19",
  coverage: {
    status: "complete",
    scored: 2,
    pending: 0,
    note: "Every 2026 World Cup match in this snapshot has been played and backtested.",
  },
  exposure: {
    rows_with_same_day_proxies: 1,
    note: "A day-precision kickoff is a 00:00 UTC calendar-day stand-in, not a verified kickoff time.",
  },
  biggest_surprises: [
    {
      match_id: "m_1",
      kickoff_utc: "2026-06-20T12:00:00Z",
      kickoff_precision: "exact",
      information_cutoff_utc: "2026-06-20T11:59:59Z",
      home_team: "France",
      away_team: "Spain",
      home_score: 1,
      away_score: 0,
      outcome: "home",
      log_loss: 2.1,
      // The disclosure case that `kickoff_precision: "exact"` cannot express.
      training_same_day_proxy_rows: 3,
      families: {
        dixon_coles: { probs: { home: 0.1, draw: 0.3, away: 0.6 }, log_loss: 2.1 },
      },
    },
    {
      match_id: "m_2",
      kickoff_utc: "2026-06-21T00:00:00Z",
      kickoff_precision: "day",
      information_cutoff_utc: "2026-06-20T23:59:59Z",
      home_team: "England",
      away_team: "Argentina",
      home_score: 2,
      away_score: 1,
      outcome: "home",
      log_loss: 0.4,
      training_same_day_proxy_rows: 0,
      families: {
        dixon_coles: { probs: { home: 0.7, draw: 0.2, away: 0.1 }, log_loss: 0.4 },
      },
    },
  ],
  trust: TRUST,
};

const render = (data: TournamentRetrospective) =>
  renderToStaticMarkup(createElement(WorldCupRetrospectiveBody, { data }));

describe("WorldCupRetrospectiveBody", () => {
  it("says plainly that every number is a backtest, never a record", () => {
    const html = render(DATA);
    expect(html).toContain("backtest");
    expect(html).toContain(DATA.label);
    // v1 has no sealed-pick layer beside these numbers, so the page must say
    // outright that nothing here was called in advance.
    expect(html).toContain("Nothing on this page was called in advance");
    expect(html).toContain("never as a track record");
    expect(html).not.toContain("sealed forecast");
  });

  it("keeps the story and trust layers labelled as different cutoffs", () => {
    const html = render(DATA);
    expect(html).toContain("its own kickoff");
    expect(html).toContain("never sees a match inside it");
    // The two layers must never be presentable as one blended number.
    expect(html).toContain("not an average of the matches above");
  });

  it("lists exactly the voices the sidecar sent, and no others", () => {
    // Which families are voices is one rule with one home — the story layer's
    // RETROSPECTIVE_FAMILIES, projected onto the fold by the sidecar and pinned in
    // server/tests/test_retrospective_api.py. This view must render that decision
    // rather than re-deriving it, so the two tables cannot disagree.
    const html = render(DATA);
    const rows = html.match(/<th scope="row"[^>]*>([^<]+)<\/th>/g) ?? [];
    expect(rows.join(" ")).toContain(FAMILY_LABELS.dixon_coles);
    expect(rows.join(" ")).not.toContain(FAMILY_LABELS.bivariate_poisson);
    // …and the reader is told where the dropped family went, not left with a gap.
    expect(html).toContain("Bivariate Poisson is not listed");
    expect(html).toContain("Poisson (independent)");
  });

  it("marks a date-proxy kickoff so same-day ordering is not implied", () => {
    const html = render(DATA);
    expect(html).toContain("date proxy");
  });

  it("flags proxy-trained rows that kickoff_precision alone calls exact", () => {
    const html = render(DATA);
    // m_1 is kickoff_precision "exact" but trained on 3 same-day proxy rows.
    // Its own precision label would tell a reader nothing leaked in.
    expect(html).toContain("Trained on 3 same-day date-proxy results");
  });

  it("renders the server's exposure note verbatim", () => {
    const html = render(DATA);
    expect(html).toContain(DATA.exposure!.note);
  });

  it("shows the partial-coverage note from the server verbatim", () => {
    const html = render({
      ...DATA,
      coverage: { status: "partial", scored: 2, pending: 2, note: "2 not yet played." },
    });
    expect(html).toContain("2 not yet played.");
  });

  // --- the cross-layer safety net -------------------------------------------
  // This warning is the only thing on the page telling a reader that the two
  // layers may describe different data. Asserted in BOTH directions: a
  // regression that deletes it, and one that inverts the comparison so it fires
  // forever, must each turn a test red.

  const DISAGREE_TITLE = "The two layers’ match counts disagree";

  it("warns when the story's count and the trust fold's count disagree", () => {
    const html = render({ ...DATA, trust: { ...TRUST, n_matches: 103 } });
    expect(html).toContain(DISAGREE_TITLE);
    expect(html).toContain("2 matches were backtested below");
    expect(html).toContain("103");
    // Raised at the same prominence as the page's other broken guarantees, not
    // trailed in small print under the fold's metadata.
    expect(html).toContain('class="callout callout--warning" role="status"');
  });

  it("states the disagreement's possible causes without asserting one", () => {
    const html = render({ ...DATA, trust: { ...TRUST, n_matches: 103 } });
    // The two layers use different window predicates (kickoff vs date), so a
    // disagreement does NOT prove two snapshots — the old copy asserted exactly
    // that, and could not have known it.
    expect(html).toContain("the counts alone cannot tell them apart");
    expect(html).toContain("may have read different snapshots");
    expect(html).toContain("select the tournament window’s edges");
    expect(html).not.toContain("which means the two layers read different snapshots");
  });

  it("says nothing about a disagreement when the two counts reconcile", () => {
    // DATA reconciles (coverage.scored 2 === trust.n_matches 2). If the
    // comparison is ever inverted, this is the test that catches it.
    expect(DATA.coverage!.scored).toBe(TRUST.n_matches);
    const html = render(DATA);
    expect(html).not.toContain(DISAGREE_TITLE);
    expect(html).not.toContain("cannot tell them apart");
  });

  it("does not reconcile against an unavailable fold's absent count", () => {
    // An unavailable fold has no n_matches. Reading a missing count as 0 would
    // fire the warning on top of a state that already says why it has no number.
    const html = render({
      ...DATA,
      trust: { status: "unavailable", cause: "no_pack", reason: "no sourcepack resolved" },
    });
    expect(html).not.toContain(DISAGREE_TITLE);
  });

  // --- the one-snapshot claim, checked not asserted --------------------------

  it("warns when the server proves the two layers ran on different packs", () => {
    const html = render({
      ...DATA,
      provenance: {
        index_sha256: "f".repeat(64),
        pack: "sp_bbbbbbbbbbbb@" + "b".repeat(64),
        snapshot_agreement: {
          status: "mismatched",
          cause: "pack_index_mismatch",
          reason: "the backtested matches were read from an index built on pack aaa…, but the skill fold was computed on pack bbb…: the two layers describe different datasets.",
          index_pack_sha256: "a".repeat(64),
          pack_sha256: "b".repeat(64),
        },
      },
    });
    expect(html).toContain("The two layers read different snapshots");
    expect(html).toContain("the two layers describe different datasets");
    expect(html).toContain("neither is a check on the other");
  });

  it("claims a verified one-snapshot check only when the server ran one", () => {
    const verified = render({
      ...DATA,
      provenance: {
        snapshot_agreement: {
          status: "verified",
          index_pack_sha256: "a".repeat(64),
          pack_sha256: "a".repeat(64),
        },
      },
    });
    expect(verified).toContain("both layers verified on pack");
    expect(verified).not.toContain("The two layers read different snapshots");

    // A check that could not run must never read as agreement.
    const unverified = render({
      ...DATA,
      provenance: {
        snapshot_agreement: {
          status: "unverified",
          cause: "index_provenance_unreadable",
          reason: "the match index does not record which pack it was built from",
        },
      },
    });
    expect(unverified).toContain("could not run (index_provenance_unreadable)");
    expect(unverified).not.toContain("verified on pack");
  });

  it("never asserts one snapshot as a bare fact in the method note", () => {
    const html = render(DATA);
    // The old copy stated "Two layers, one snapshot" flatly — a guarantee the
    // page cannot make on its own, since the two layers read different files.
    expect(html).not.toContain("Two layers, one snapshot,");
    expect(html).toContain("checked rather than assumed");
  });

  it("renders typed unavailable copy without fabricated numbers", () => {
    const html = render({
      ...DATA,
      status: "unavailable",
      reason: "No completed matches",
      biggest_surprises: [],
    });
    expect(html).toContain("No completed matches");
    expect(html).not.toContain("0.0%");
    expect(html).not.toContain("0.000");
  });

  it("renders a paused envelope with the server's own reason", () => {
    // The server returns the mid-compute index change as an unavailable
    // envelope whose reason carries the pause — never a fabricated result.
    const reason = "retrospective paused because the verified match index changed; retry";
    const html = render({
      ...DATA,
      status: "unavailable",
      reason,
      biggest_surprises: [],
    });
    expect(html).toContain(reason);
  });

  it.each([
    ["no_pack", "no sourcepack resolved for this index"],
    ["evaluation_failed", "the WC2026 fold could not be recomputed: no completed rows"],
    ["fold_absent", "this snapshot evaluation carries no WC2026 fold"],
  ] as const)("renders the typed trust cause %s without inventing skill", (cause, reason) => {
    const html = render({
      ...DATA,
      trust: { status: "unavailable", cause, reason },
    });
    expect(html).toContain("Model skill could not be measured");
    expect(html).toContain(reason);
    // A missing guarantee must never read as a measured-and-poor one: no skill
    // table at all, rather than one full of zeros.
    expect(html).not.toContain("0.000");
    expect(html).not.toContain("Brier");
  });

  it("does not fake a skill interval a single fold cannot support", () => {
    const html = render(DATA);
    expect(html).toContain("No skill interval is shown");
    expect(html).not.toContain("95% CI");
    // Guards the "Brier" absence check above from passing for the wrong reason.
    expect(html).toContain("Brier");
  });

  it("omits the trust section entirely when core is called directly", () => {
    // trust is absent (not null-shaped) when core emits the envelope itself.
    const { trust: _trust, ...withoutTrust } = DATA;
    const html = render(withoutTrust as TournamentRetrospective);
    expect(html).not.toContain("Model skill could not be measured");
    expect(html).not.toContain("Did these models have skill?");
    // The story layer still stands on its own.
    expect(html).toContain("France");
  });
});

describe("trust voices", () => {
  it("names the family the sidecar dropped, instead of leaving a silent gap", () => {
    const html = render(DATA);
    expect(html).toContain("not listed");
    expect(html).toContain("Bivariate Poisson");
  });

  it("says nothing about omissions when the sidecar dropped nothing", () => {
    const html = render({ ...DATA, trust: { ...TRUST, omitted_families: [] } });
    expect(html).not.toContain("not listed");
  });
});
