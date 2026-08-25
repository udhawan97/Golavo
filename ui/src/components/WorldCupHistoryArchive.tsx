import { useEffect, useState } from "react";
import { fetchWorldCupHistory } from "../lib/api";
import type { WorldCupHistoryResponse } from "../lib/contract";
import { handleExternalLinkClick } from "../lib/external-links";
import { ErrorState } from "./states";

export function WorldCupHistoryArchiveBody({
  data,
  initialCategory = "women",
}: {
  data: WorldCupHistoryResponse;
  initialCategory?: "women" | "men";
}) {
  const [categoryId, setCategoryId] = useState(initialCategory);
  const category = data.categories.find((item) => item.id === categoryId) ?? data.categories[0];
  const [year, setYear] = useState(category.tournaments[0]?.year ?? category.last_year);

  const tournament = category.tournaments.find((item) => item.year === year) ?? category.tournaments[0];
  return (
    <section className="wc-archive stack" aria-labelledby="wc-archive-title" style={{ ["--gap" as string]: ".9rem" }}>
      <div>
        <span className="eyebrow">Pinned tournament archive</span>
        <h2 id="wc-archive-title">Women’s history, beside the men’s record</h2>
        <p className="measure dim" style={{ margin: ".25rem 0 0" }}>
          Titles, finals, appearances and player awards from one hash-verified history pack. This is
          reference history only: it never trains a model, changes a probability or becomes a seal.
        </p>
      </div>

      <div className="mv-filter-chips" role="group" aria-label="World Cup category">
        {data.categories.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`btn btn--chip${item.id === category.id ? " is-active" : ""}`}
            aria-pressed={item.id === category.id}
            onClick={() => {
              setCategoryId(item.id);
              setYear(item.tournaments[0]?.year ?? item.last_year);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="wc-archive__summary" aria-label={`${category.label} archive coverage`}>
        <div><strong>{category.tournament_count}</strong><span>tournaments</span></div>
        <div><strong>{category.first_year}–{category.last_year}</strong><span>pinned era</span></div>
        <div><strong>{category.pedigree.length}</strong><span>teams represented</span></div>
      </div>

      <p className="small dim" style={{ margin: 0 }}>Leading 12 teams by titles, finals, then appearances. The coverage total above includes every represented team.</p>
      <div className="table-wrap" role="region" aria-label={`${category.label} pedigree table`} tabIndex={0}>
        <table className="grid">
          <thead><tr><th scope="col">Team</th><th scope="col">Titles</th><th scope="col">Finals</th><th scope="col">Appearances</th></tr></thead>
          <tbody>
            {category.pedigree.slice(0, 12).map((team) => (
              <tr key={team.team_id}>
                <th scope="row">{team.team_name} <span className="small dim">{team.team_code}</span></th>
                <td className="num" data-label="Titles">{team.titles}{team.title_years.length > 0 ? <span className="small dim" style={{ display: "block" }}>{team.title_years.join(", ")}</span> : null}</td>
                <td className="num" data-label="Finals">{team.finals}</td>
                <td className="num" data-label="Appearances">{team.appearances}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="wc-archive__edition stack" style={{ ["--gap" as string]: ".6rem" }}>
        <div className="settings__row">
          <div>
            <h3 style={{ margin: 0 }}>Edition record</h3>
            <p className="small dim" style={{ margin: ".15rem 0 0" }}>Final four and individual awards as recorded in the pinned source.</p>
          </div>
          <label className="small">
            <span className="sr-only">Tournament year</span>
            <select className="select" value={tournament?.year} onChange={(event) => setYear(Number(event.target.value))}>
              {category.tournaments.map((item) => <option key={item.tournament_id} value={item.year}>{item.year}</option>)}
            </select>
          </label>
        </div>
        {tournament && (
          <div className="wc-archive__edition-grid">
            <ol aria-label={`${tournament.year} final standings`}>
              {tournament.standings.map((standing) => <li key={standing.team_id}><span>{standing.position}</span><strong>{standing.team_name}</strong><small>{standing.team_code}</small></li>)}
            </ol>
            <div>
              <h4>Player awards</h4>
              {tournament.awards.length > 0 ? (
                <ul>{tournament.awards.map((award, index) => <li key={`${award.award}-${award.player}-${index}`}><strong>{award.award}</strong><span>{award.player} · {award.team_name}</span></li>)}</ul>
              ) : <p className="small dim">No individual awards are present for this edition in the pinned pack.</p>}
            </div>
          </div>
        )}
      </div>

      <p className="small dim measure" style={{ margin: 0 }}>
        {data.source.name} · {data.source.copyright_notice} · {data.source.license} · pinned at {data.source.upstream_ref}. {data.source.modification_note}{" "}
        <a href={data.source.url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Source</a>{" · "}
        <a href={data.source.license_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>License</a>
      </p>
    </section>
  );
}

export function WorldCupHistoryArchive() {
  const [data, setData] = useState<WorldCupHistoryResponse | null | undefined>(undefined);
  const [error, setError] = useState<Error | null>(null);
  const load = () => {
    setError(null);
    void fetchWorldCupHistory().then(setData).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason : new Error("The World Cup archive could not be read."));
    });
  };
  useEffect(load, []);
  if (error) return <ErrorState error={error} onRetry={load} />;
  if (data === undefined) return <p className="small dim" role="status">Reading the pinned World Cup archive…</p>;
  if (data === null) {
    return (
      <div className="callout callout--info" role="status"><div><div className="callout__title">Archive needs the local Golavo engine</div><p>The web preview does not invent historical rows. Run the source app or installed desktop build to read the bundled, hash-verified pack.</p></div></div>
    );
  }
  return <WorldCupHistoryArchiveBody data={data} />;
}
