import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { WorldCupHistoryResponse } from "../lib/contract";
import { WorldCupHistoryArchiveBody } from "./WorldCupHistoryArchive";

const DATA: WorldCupHistoryResponse = {
  schema_version: "0.1.0",
  source: {
    source_id: "fjelstul-worldcup",
    name: "The Fjelstul World Cup Database",
    creator: "Joshua C. Fjelstul, Ph.D.",
    copyright_notice: "© 2022 Joshua C. Fjelstul, Ph.D.",
    license: "CC-BY-SA-4.0",
    license_url: "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
    url: "https://github.com/jfjelstul/worldcup",
    upstream_ref: "f942c6b",
    retrieved_at_utc: "2026-07-14T04:03:17Z",
    modification_note: "Golavo selects pinned rows.",
  },
  categories: [
    {
      id: "women", label: "Women's World Cup", tournament_count: 1, first_year: 2019, last_year: 2019,
      pedigree: [{ team_id: "T-USA", team_name: "United States", team_code: "USA", appearances: 8, titles: 4, title_years: [1991, 1999, 2015, 2019], finals: 5, best_finish: 1 }],
      tournaments: [{ tournament_id: "WC-2019", tournament_name: "2019 FIFA Women's World Cup", year: 2019, ended_on: "2019-07-07", standings: [
        { position: 1, team_id: "T-USA", team_name: "United States", team_code: "USA" },
        { position: 2, team_id: "T-NED", team_name: "Netherlands", team_code: "NED" },
        { position: 3, team_id: "T-SWE", team_name: "Sweden", team_code: "SWE" },
        { position: 4, team_id: "T-ENG", team_name: "England", team_code: "ENG" },
      ], awards: [{ award: "Golden Ball", player: "Megan Rapinoe", team_name: "United States", team_code: "USA" }] }],
    },
    {
      id: "men", label: "Men's World Cup", tournament_count: 1, first_year: 2022, last_year: 2022,
      pedigree: [], tournaments: [{ tournament_id: "WC-2022", tournament_name: "2022 FIFA Men's World Cup", year: 2022, ended_on: "2022-12-18", standings: [
        { position: 1, team_id: "T-ARG", team_name: "Argentina", team_code: "ARG" },
        { position: 2, team_id: "T-FRA", team_name: "France", team_code: "FRA" },
        { position: 3, team_id: "T-CRO", team_name: "Croatia", team_code: "CRO" },
        { position: 4, team_id: "T-MAR", team_name: "Morocco", team_code: "MAR" },
      ], awards: [] }],
    },
  ],
};

describe("WorldCupHistoryArchiveBody", () => {
  it("defaults to the women's archive and states the forecast boundary", () => {
    const html = renderToStaticMarkup(createElement(WorldCupHistoryArchiveBody, { data: DATA }));
    expect(html).toContain("Women’s history");
    expect(html).toContain("United States");
    expect(html).toContain("Megan Rapinoe");
    expect(html).toContain("never trains a model");
    expect(html).toContain("CC-BY-SA-4.0");
    expect(html).toContain("© 2022 Joshua C. Fjelstul, Ph.D.");
    expect(html).not.toContain("Argentina");
  });
});
