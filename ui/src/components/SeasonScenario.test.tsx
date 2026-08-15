// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchSeasonScenario } from "../lib/api";
import type { SeasonOutlook, SeasonOutlookVoice } from "../lib/contract";
import { ScenarioBuilder, SeasonOutlookBody } from "./SeasonOutlook";

vi.mock("../lib/api", () => ({
  fetchSeasonOutlook: vi.fn(),
  fetchSeasonScenario: vi.fn(),
}));

const VOICE_IDS = ["elo_ordlogit", "dixon_coles", "equal-chance-baseline"] as const;

function voice(
  voiceId: SeasonOutlookVoice["voice_id"],
  firstTitle: number,
  reverse = false,
): SeasonOutlookVoice {
  const teams = [
    {
      team: "A",
      title: firstTitle / 100,
      top_four: 1,
      relegation: 0,
      display_percent: { title: firstTitle, top_four: 100, relegation: 0 },
    },
    {
      team: "B",
      title: (100 - firstTitle) / 100,
      top_four: 1,
      relegation: 0,
      display_percent: { title: 100 - firstTitle, top_four: 100, relegation: 0 },
    },
  ];
  return {
    voice_id: voiceId,
    label: voiceId,
    role: voiceId === "equal-chance-baseline" ? "baseline" : "voice",
    scoreline_method: "declared method",
    teams: reverse ? teams.reverse() : teams,
    totals: { title: 1, top_four: 2, relegation: 0 },
  };
}

function outlook(conditional = false): SeasonOutlook {
  const titles = conditional ? [11, 22, 33] : [10, 20, 30];
  return {
    schema_version: "0.2.0",
    status: "available",
    label: "Season outlook — not a seal.",
    competition_id: "test-league",
    competition_name: "Test League",
    season: "2026-27",
    as_of_utc: "2026-08-20T08:00:00Z",
    simulation_rule: "season-mc-2026.07.1",
    ledger_status: "never_persisted_or_scored_as_a_seal",
    reason_code: null,
    reason: null,
    standings_rule_id: "test-2026.1",
    fixture_certificate: {
      expected_teams: 2,
      observed_teams: 2,
      teams: ["A", "B"],
      expected_matches: 2,
      observed_matches: 2,
      unique_ordered_pairs: 2,
      duplicate_ordered_pairs: 0,
      self_fixtures: 0,
      incomplete_fixtures: 0,
      past_result_gaps: 0,
      future_completed_results: 0,
      complete_fixture_list: true,
    },
    current_table: [],
    remaining_fixtures: [
      { match_id: "m-1", kickoff_utc: "2027-02-01T15:00:00Z", home_team: "A", away_team: "B" },
      { match_id: "m-2", kickoff_utc: "2027-02-08T15:00:00Z", home_team: "B", away_team: "A" },
      { match_id: "m-3", kickoff_utc: "2027-02-15T15:00:00Z", home_team: "A", away_team: "B" },
    ],
    scenario: conditional ? {
      hypothetical_only: true,
      persisted: false,
      model_input: false,
      forced_results: [{
        match_id: "m-1",
        home_team: "A",
        away_team: "B",
        home_score: 2,
        away_score: 1,
      }],
    } : null,
    iterations: 10_000,
    seed: 42,
    voices: VOICE_IDS.map((voiceId, index) => voice(voiceId, titles[index], conditional)),
    provenance: { source_ids: ["test-source"], index_sha256: "0".repeat(64) },
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.resetAllMocks();
});

function button(name: string): HTMLButtonElement {
  const match = Array.from(container.querySelectorAll("button")).find(
    (item) => item.textContent === name || item.getAttribute("aria-label") === name,
  );
  if (!(match instanceof HTMLButtonElement)) throw new Error(`button not found: ${name}`);
  return match;
}

function setInput(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

async function clickAndSettle(control: HTMLButtonElement) {
  await act(async () => {
    control.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("Season scenario interactions", () => {
  it("preserves a multi-result draft through failure, retry, and reset", async () => {
    const canonical = outlook();
    const conditional = outlook(true);
    const onResult = vi.fn();
    const onReset = vi.fn();
    vi.mocked(fetchSeasonScenario)
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce(conditional);

    act(() => {
      root.render(
        <ScenarioBuilder
          outlook={canonical}
          activeScenario={null}
          onResult={onResult}
          onReset={onReset}
        />,
      );
    });
    await clickAndSettle(button("Add another result"));
    expect(container.querySelectorAll(".season-scenario__result")).toHaveLength(2);

    const scores = container.querySelectorAll<HTMLInputElement>('input[type="number"]');
    act(() => {
      setInput(scores[2], "3");
      setInput(scores[3], "2");
    });
    await clickAndSettle(button("Remove result 1"));
    await clickAndSettle(button("Add another result"));

    await clickAndSettle(button("Run 2-result scenario"));
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "could not run this conditional scenario",
    );
    expect(container.querySelectorAll(".season-scenario__result")).toHaveLength(2);
    expect(Array.from(container.querySelectorAll<HTMLInputElement>('input[type="number"]'))
      .map((input) => input.value)).toContain("3");

    await clickAndSettle(button("Run 2-result scenario"));
    expect(fetchSeasonScenario).toHaveBeenCalledTimes(2);
    const forced = vi.mocked(fetchSeasonScenario).mock.calls[1][1];
    expect(forced).toHaveLength(2);
    expect(new Set(forced.map((result) => result.match_id)).size).toBe(2);
    expect(onResult).toHaveBeenCalledWith(conditional);

    act(() => {
      root.render(
        <ScenarioBuilder
          outlook={canonical}
          activeScenario={conditional}
          onResult={onResult}
          onReset={onReset}
        />,
      );
    });
    await clickAndSettle(button("Reset to verified outlook"));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("uses one voice control for verified and conditional values", async () => {
    const canonical = outlook();
    const conditional = outlook(true);
    act(() => {
      root.render(<SeasonOutlookBody outlook={conditional} canonical={canonical} />);
    });
    expect(container.querySelector('[aria-label^="Ratings verified and conditional"]'))
      .not.toBeNull();

    await clickAndSettle(button("Goals"));
    const comparison = container.querySelector(
      '[aria-label^="Goals verified and conditional"]',
    );
    expect(comparison).not.toBeNull();
    expect(button("Goals").getAttribute("aria-pressed")).toBe("true");
    expect(comparison?.textContent).toContain("20.0%");
    expect(comparison?.textContent).toContain("22.0%");
  });

  it("freezes draft and reset mutations while a scenario request is in flight", async () => {
    let resolveRequest: ((value: SeasonOutlook) => void) | undefined;
    const pending = new Promise<SeasonOutlook>((resolve) => { resolveRequest = resolve; });
    vi.mocked(fetchSeasonScenario).mockReturnValueOnce(pending);
    const canonical = outlook();
    const conditional = outlook(true);
    const onResult = vi.fn();
    const onReset = vi.fn();

    act(() => {
      root.render(
        <ScenarioBuilder
          outlook={canonical}
          activeScenario={conditional}
          onResult={onResult}
          onReset={onReset}
        />,
      );
    });
    await act(async () => {
      button("Run 1-result scenario").click();
      await Promise.resolve();
    });

    const input = container.querySelector<HTMLInputElement>('input[type="number"]');
    const select = container.querySelector<HTMLSelectElement>("select");
    expect(input?.matches(":disabled")).toBe(true);
    expect(select?.matches(":disabled")).toBe(true);
    expect(button("Add another result").disabled).toBe(true);
    expect(button("Reset to verified outlook").disabled).toBe(true);
    act(() => {
      if (input) setInput(input, "9");
      button("Reset to verified outlook").click();
    });
    expect(input?.value).toBe("1");
    expect(onReset).not.toHaveBeenCalled();

    await act(async () => {
      resolveRequest?.(conditional);
      await pending;
    });
    expect(onResult).toHaveBeenCalledWith(conditional);
  });

  it.each([
    ["missing", (teams: SeasonOutlookVoice["teams"]) => teams.slice(0, 1)],
    ["duplicate", (teams: SeasonOutlookVoice["teams"]) => [teams[0], teams[0]]],
    ["extra", (teams: SeasonOutlookVoice["teams"]) => [
      ...teams,
      { ...teams[0], team: "C" },
    ]],
  ])("refuses a %s conditional team set", (_name, alterTeams) => {
    const canonical = outlook();
    const conditional = outlook(true);
    conditional.voices[0].teams = alterTeams(conditional.voices[0].teams);
    act(() => {
      root.render(<SeasonOutlookBody outlook={conditional} canonical={canonical} />);
    });
    expect(container.textContent).toContain("Conditional comparison unavailable");
    expect(container.querySelector(".season-comparison-table")).toBeNull();
  });

  it("refuses a comparison when the selected conditional voice is missing", () => {
    const canonical = outlook();
    const conditional = outlook(true);
    conditional.voices = conditional.voices.filter((voice) => voice.voice_id !== "elo_ordlogit");
    act(() => {
      root.render(<SeasonOutlookBody outlook={conditional} canonical={canonical} />);
    });
    expect(container.textContent).toContain("Conditional comparison unavailable");
    expect(container.querySelector(".season-comparison-table")).toBeNull();
  });
});
