import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { TournamentRetrospective, TrustFold } from "../lib/contract";
import { WorldCupRetrospectiveBody, trustVoices } from "./WorldCupRetrospective";

/** The bivariate row carries values that appear nowhere else, so a filter
 *  regression is caught by the number itself surfacing — not by a label that a
 *  disclosure sentence also legitimately contains. */
const BIVARIATE_ONLY_LOG_LOSS = 9.876;
const BIVARIATE_ONLY_BRIER = 8.765;

const TRUST: TrustFold = {
  status: "available",
  fold_id: "WC2026",
  competition: "FIFA World Cup",
  n_matches: 102,
  training_cutoff_utc: "2026-06-10T00:00:00Z",
  window_start: "2026-06-11",
  window_end: "2026-07-19",
  models: [
    { family: "climatological", log_loss: 1.05, brier: 0.66 },
    { family: "elo_ordlogit", log_loss: 0.98, brier: 0.61 },
    { family: "poisson_independent", log_loss: 1.01, brier: 0.63 },
    { family: "dixon_coles", log_loss: 0.99, brier: 0.62 },
    {
      family: "bivariate_poisson",
      log_loss: BIVARIATE_ONLY_LOG_LOSS,
      brier: BIVARIATE_ONLY_BRIER,
    },
  ],
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
  matches: [],
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

  it("never offers bivariate Poisson as a voice in the trust table", () => {
    const html = render(DATA);
    // If the filter regresses, this family's own metrics render as a row.
    expect(html).not.toContain(String(BIVARIATE_ONLY_LOG_LOSS));
    expect(html).not.toContain(String(BIVARIATE_ONLY_BRIER));
    // …and the reader is told where it went rather than left to notice a gap.
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
      coverage: { status: "partial", scored: 102, pending: 2, note: "2 not yet played." },
    });
    expect(html).toContain("2 not yet played.");
  });

  it("renders typed unavailable copy without fabricated numbers", () => {
    const html = render({
      ...DATA,
      status: "unavailable",
      reason: "No completed matches",
      biggest_surprises: [],
      matches: [],
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
      matches: [],
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

describe("trustVoices", () => {
  it("drops bivariate Poisson and reports it as omitted", () => {
    const { shown, omitted } = trustVoices(TRUST);
    expect(shown.map((m) => m.family)).toEqual([
      "climatological",
      "elo_ordlogit",
      "poisson_independent",
      "dixon_coles",
    ]);
    expect(omitted).toEqual(["bivariate_poisson"]);
  });

  it("reports nothing omitted when the fold never carried the duplicate", () => {
    const { shown, omitted } = trustVoices({
      ...TRUST,
      models: TRUST.models.filter((m) => m.family !== "bivariate_poisson"),
    });
    expect(shown).toHaveLength(4);
    expect(omitted).toEqual([]);
  });
});
