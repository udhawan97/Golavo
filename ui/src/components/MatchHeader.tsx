/**
 * Shared match/forecast page header.
 *
 * One calm hierarchy: a chip row (status + optional right-aligned control), the
 * teams as the page hero, then a single aligned meta line (competition · date ·
 * venue). The raw match_id is deliberately NOT here — it lives in the provenance
 * drawer, where an auditor looks for it, instead of bleeding into the headline.
 */
import type { ReactNode } from "react";
import { kickoffRelative, utcDate } from "../lib/format";
import { CalendarIcon, PinIcon, TrophyIcon } from "./icons";
import { MetaItem, MetaLine } from "./primitives";

export function MatchHeader({
  home,
  away,
  competition,
  kickoffUtc,
  venue,
  chips,
  right,
}: {
  home: string;
  away: string;
  competition: string;
  kickoffUtc: string;
  venue: string;
  chips?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <header className="detail-hero stack" style={{ ["--gap" as string]: ".6rem" }}>
      <div className="badge-row">
        {chips}
        {right && <span style={{ marginLeft: "auto" }}>{right}</span>}
      </div>
      <h1>
        {home} <span className="dim" style={{ fontWeight: 400 }}>v</span> {away}
      </h1>
      <MetaLine>
        <MetaItem icon={<TrophyIcon />}>{competition}</MetaItem>
        <MetaItem icon={<CalendarIcon />}>
          <span className="num">{utcDate(kickoffUtc)}</span>
          {kickoffRelative(kickoffUtc) && (
            <> <span className="dim">· {kickoffRelative(kickoffUtc)}</span></>
          )}
        </MetaItem>
        <MetaItem icon={<PinIcon />}>{venue}</MetaItem>
      </MetaLine>
    </header>
  );
}
