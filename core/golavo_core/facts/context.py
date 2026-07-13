"""Context templates — background the fixture sits in, never a prediction.

Every template is a pure function of a :class:`TemplateContext`. Text is
number-disciplined (every digit is a registered number) and names only the
fixture's own two teams and competition; opponent names, player names and exact
dates that carry digits live in ``values``/``date_range`` for the UI to render,
so a fact stays safe to fold verbatim into the AI numeric whitelist.
"""

from __future__ import annotations

import pandas as pd

from ._history import (
    Candidate,
    TemplateContext,
    as_date_iso,
    clamp_unit,
    head_to_head,
    team_perspective,
    trailing_run,
)
from .render import NumberBag


def _sides(ctx: TemplateContext) -> tuple[tuple[str, bool], tuple[str, bool]]:
    """The two teams paired with whether each is the home side in this fixture."""
    return (ctx.home_team, True), (ctx.away_team, False)


def _run_dates(persp: pd.DataFrame, run: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    tail = persp.iloc[len(persp) - run :]
    return tail["date"].iloc[0], tail["date"].iloc[-1]


def unbeaten_run(ctx: TemplateContext) -> list[Candidate]:
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        results = persp["result"].tolist()
        run = trailing_run([r in ("W", "D") for r in results])
        if run < 2:
            continue
        tail = persp.iloc[len(persp) - run :]
        wins = int((tail["result"] == "W").sum())
        draws = run - wins
        nb = NumberBag()
        n = nb.count("run", run)
        w = nb.count("wins", wins)
        d = nb.count("draws", draws)
        first, last = _run_dates(persp, run)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} are unbeaten in their last {n} matches ({w} won, {d} drawn).",
                values={"run": run, "wins": wins, "draws": draws},
                numbers=nb.items(),
                sample_n=run,
                denominator=run,
                first_date=first,
                last_date=last,
                specificity=clamp_unit(run / 15.0),
            )
        )
    return out


def winless_run(ctx: TemplateContext) -> list[Candidate]:
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        results = persp["result"].tolist()
        run = trailing_run([r in ("D", "L") for r in results])
        if run < 2:
            continue
        tail = persp.iloc[len(persp) - run :]
        losses = int((tail["result"] == "L").sum())
        draws = run - losses
        nb = NumberBag()
        n = nb.count("run", run)
        d = nb.count("draws", draws)
        lo = nb.count("losses", losses)
        first, last = _run_dates(persp, run)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} are winless in their last {n} matches ({d} drawn, {lo} lost).",
                values={"run": run, "draws": draws, "losses": losses},
                numbers=nb.items(),
                sample_n=run,
                denominator=run,
                first_date=first,
                last_date=last,
                specificity=clamp_unit(run / 15.0),
            )
        )
    return out


def win_streak(ctx: TemplateContext) -> list[Candidate]:
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        run = trailing_run([r == "W" for r in persp["result"].tolist()])
        if run < 2:
            continue
        nb = NumberBag()
        n = nb.count("run", run)
        first, last = _run_dates(persp, run)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} have won each of their last {n} matches in a row.",
                values={"run": run},
                numbers=nb.items(),
                sample_n=run,
                denominator=run,
                first_date=first,
                last_date=last,
                specificity=clamp_unit(run / 10.0),
            )
        )
    return out


def clean_sheet_run(ctx: TemplateContext) -> list[Candidate]:
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        run = trailing_run([int(ga) == 0 for ga in persp["ga"].tolist()])
        if run < 2:
            continue
        nb = NumberBag()
        n = nb.count("run", run)
        first, last = _run_dates(persp, run)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} have kept a clean sheet in each of their last {n} matches.",
                values={"run": run},
                numbers=nb.items(),
                sample_n=run,
                denominator=run,
                first_date=first,
                last_date=last,
                specificity=clamp_unit(run / 8.0),
            )
        )
    return out


def biggest_win(ctx: TemplateContext) -> list[Candidate]:
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        wins = persp.loc[persp["result"] == "W"].copy()
        if wins.empty:
            continue
        wins["margin"] = wins["gf"] - wins["ga"]
        best = wins.sort_values(
            ["margin", "date", "gf"], ascending=[False, False, False], kind="mergesort"
        ).iloc[0]
        gf, ga = int(best["gf"]), int(best["ga"])
        nb = NumberBag()
        gf_d = nb.count("goals_for", gf)
        ga_d = nb.count("goals_against", ga)
        out.append(
            Candidate(
                subject=team,
                # Opponent name is omitted from the whitelist-safe text (a club
                # opponent may carry digits, e.g. "Schalke 04"); the UI reads it
                # from ``values``.
                text=f"{team}'s biggest win in this data was by {gf_d}–{ga_d}.",
                values={
                    "goals_for": gf,
                    "goals_against": ga,
                    "margin": gf - ga,
                    "opponent": str(best["opponent"]),
                    "match_date": as_date_iso(best["date"]),
                },
                numbers=nb.items(),
                sample_n=int(len(persp)),
                denominator=int(len(persp)),
                first_date=persp["date"].iloc[0],
                last_date=persp["date"].iloc[-1],
                specificity=clamp_unit((gf - ga) / 10.0),
            )
        )
    return out


def head_to_head_record(ctx: TemplateContext) -> list[Candidate]:
    h2h = head_to_head(ctx.matches, ctx.home_team, ctx.away_team)
    if h2h.empty:
        return []
    home = ctx.home_team
    home_is_home = h2h["home_team"].eq(home)
    home_gf = h2h["home_score"].where(home_is_home, h2h["away_score"]).astype(int)
    home_ga = h2h["away_score"].where(home_is_home, h2h["home_score"]).astype(int)
    wins = int((home_gf > home_ga).sum())
    draws = int((home_gf == home_ga).sum())
    losses = int((home_gf < home_ga).sum())
    meetings = int(len(h2h))
    last = h2h.iloc[-1]
    last_home_gf = int(last["home_score"])
    last_away_gf = int(last["away_score"])
    nb = NumberBag()
    m = nb.count("meetings", meetings)
    w = nb.count("home_wins", wins)
    d = nb.count("draws", draws)
    lo = nb.count("home_losses", losses)
    lh = nb.count("last_home_goals", last_home_gf)
    la = nb.count("last_away_goals", last_away_gf)
    decisiveness = abs(wins - losses) / meetings if meetings else 0.0
    return [
        Candidate(
            subject=f"{home} v {ctx.away_team}",
            text=(
                f"In {m} previous meetings, {home} have {w} wins, {d} draws and {lo} "
                f"losses against {ctx.away_team}. Their most recent meeting finished "
                f"{lh}–{la}."
            ),
            values={
                "meetings": meetings,
                "home_wins": wins,
                "draws": draws,
                "home_losses": losses,
                "last_meeting_date": as_date_iso(last["date"]),
                "last_home_team": str(last["home_team"]),
                "last_away_team": str(last["away_team"]),
                "last_score": f"{last_home_gf}-{last_away_gf}",
            },
            numbers=nb.items(),
            sample_n=meetings,
            denominator=meetings,
            first_date=h2h["date"].iloc[0],
            last_date=h2h["date"].iloc[-1],
            specificity=clamp_unit(0.3 + 0.7 * decisiveness),
        )
    ]


def _side_form(persp: pd.DataFrame, home_leg: bool) -> pd.DataFrame:
    return persp.loc[persp["is_home"] == home_leg]


def home_away_form(ctx: TemplateContext) -> list[Candidate]:
    """Home team's recent home form, and away team's recent away form (last 10)."""
    window = 10
    out: list[Candidate] = []
    for team, is_home_side in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        legs = _side_form(persp, is_home_side).tail(window)
        if legs.empty:
            continue
        wins = int((legs["result"] == "W").sum())
        draws = int((legs["result"] == "D").sum())
        losses = int((legs["result"] == "L").sum())
        n = int(len(legs))
        where = "At home" if is_home_side else "Away from home"
        leg_word = "home" if is_home_side else "away"
        nb = NumberBag()
        n_d = nb.count("matches", n)
        w = nb.count("wins", wins)
        d = nb.count("draws", draws)
        lo = nb.count("losses", losses)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"{where}, {team} have a {w}–{d}–{lo} win–draw–loss record from their "
                    f"last {n_d} {leg_word} matches."
                ),
                values={"matches": n, "wins": wins, "draws": draws, "losses": losses,
                        "leg": leg_word},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=wins / n if n else None,
                first_date=legs["date"].iloc[0],
                last_date=legs["date"].iloc[-1],
                specificity=clamp_unit(abs(wins - losses) / max(n, 1)),
            )
        )
    return out


def neutral_venue_record(ctx: TemplateContext) -> list[Candidate]:
    """Only relevant when THIS fixture is at a neutral venue."""
    if not ctx.neutral:
        return []
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        neutral = persp.loc[persp["neutral"]]
        n = int(len(neutral))
        if n == 0:
            continue
        wins = int((neutral["result"] == "W").sum())
        draws = int((neutral["result"] == "D").sum())
        losses = int((neutral["result"] == "L").sum())
        nb = NumberBag()
        n_d = nb.count("matches", n)
        w = nb.count("wins", wins)
        d = nb.count("draws", draws)
        lo = nb.count("losses", losses)
        rate = nb.percent("win_rate", wins / n)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"At neutral venues, {team} have a {w}–{d}–{lo} record in {n_d} matches "
                    f"({rate} won)."
                ),
                values={"matches": n, "wins": wins, "draws": draws, "losses": losses},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=wins / n,
                first_date=neutral["date"].iloc[0],
                last_date=neutral["date"].iloc[-1],
                specificity=clamp_unit(abs(wins - losses) / max(n, 1)),
            )
        )
    return out


def top_scorer(ctx: TemplateContext) -> list[Candidate]:
    """Internationals only: the team's leading scorer in the vendored goalscorers."""
    scorers = ctx.goalscorers
    if scorers is None or scorers.empty:
        return []
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        team_goals = scorers.loc[
            scorers["team"].eq(team) & (~scorers["own_goal"].astype("boolean").fillna(False))
        ]
        if team_goals.empty:
            continue
        tally = team_goals.groupby("scorer").size().sort_values(
            ascending=False, kind="mergesort"
        )
        # Deterministic tie-break: most goals, then alphabetical scorer name.
        top = sorted(tally.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))[0]
        name, goals = str(top[0]), int(top[1])
        nb = NumberBag()
        g = nb.count("goals", goals)
        out.append(
            Candidate(
                subject=team,
                # Player name kept out of the whitelist-safe text; UI reads ``values``.
                text=f"{team}'s leading scorer in this data has {g} goals for them.",
                values={"scorer": name, "goals": goals},
                numbers=nb.items(),
                sample_n=goals,
                denominator=goals,
                first_date=pd.Timestamp(team_goals["date"].min()),
                last_date=pd.Timestamp(team_goals["date"].max()),
                specificity=clamp_unit(goals / 80.0),
            )
        )
    return out


def in_form_scorer(ctx: TemplateContext) -> list[Candidate]:
    """Internationals only: the team's most in-form scorer over its last N matches.

    Unlike ``top_scorer`` (all-time leading scorer), this scopes to the team's most
    recent completed matches before the cutoff — "who's hot right now". Emits only
    when the leader has a meaningful tally in the window, so a single goal never
    reads as "in form". The player NAME lives in ``values`` (never in the
    whitelist-safe text), exactly like ``top_scorer``.
    """
    scorers = ctx.goalscorers
    if scorers is None or scorers.empty:
        return []
    window = 10  # the "recent" horizon, in the team's own completed matches
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        if persp.empty:
            continue
        recent = persp.tail(window)
        m = int(len(recent))
        # Reconstruct the (date, home_team, away_team) keys of the recent matches so
        # the scorer join is exact (a shared date can't merge two fixtures).
        keys = set()
        for _, r in recent.iterrows():
            day = pd.Timestamp(r["date"]).normalize()
            if bool(r["is_home"]):
                keys.add((day, team, str(r["opponent"])))
            else:
                keys.add((day, str(r["opponent"]), team))
        team_goals = scorers.loc[
            scorers["team"].eq(team) & (~scorers["own_goal"].astype("boolean").fillna(False))
        ]
        if team_goals.empty:
            continue
        in_window = team_goals.loc[
            team_goals.apply(
                lambda row, _keys=keys: (
                    pd.Timestamp(row["date"]).normalize(),
                    str(row["home_team"]),
                    str(row["away_team"]),
                )
                in _keys,
                axis=1,
            )
        ]
        if in_window.empty:
            continue
        tally = in_window.groupby("scorer").size()
        # Deterministic tie-break: most goals, then alphabetical scorer name.
        name, goals = sorted(tally.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))[0]
        goals = int(goals)
        if goals < 3:  # below this it is noise, not "in form"
            continue
        penalties = int(
            in_window.loc[
                in_window["scorer"].eq(name)
                & in_window["penalty"].astype("boolean").fillna(False)
            ].shape[0]
        )
        nb = NumberBag()
        g = nb.count("goals", goals)
        m_d = nb.count("window_matches", m)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"{team}'s most in-form scorer has {g} goals across their "
                    f"last {m_d} internationals in this data."
                ),
                values={
                    "scorer": str(name),
                    "goals": goals,
                    "window_matches": m,
                    "penalties": penalties,
                },
                numbers=nb.items(),
                sample_n=m,
                denominator=m,
                first_date=pd.Timestamp(in_window["date"].min()),
                last_date=pd.Timestamp(in_window["date"].max()),
                specificity=clamp_unit(goals / 10.0),
            )
        )
    return out


def tournament_record(ctx: TemplateContext) -> list[Candidate]:
    """A team's all-time record IN THIS COMPETITION (e.g. World-Cup-only form).

    Only meaningful when the fixture's competition is a named tournament and the
    team actually plays across several competitions — so it never fires for a club
    side whose every match is the same league (the degenerate case).
    """
    comp = ctx.competition
    if not comp or comp == "Friendly":
        return []
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        if persp.empty or persp["tournament"].nunique() < 2:
            continue
        in_comp = persp.loc[persp["tournament"].eq(comp)]
        n = int(len(in_comp))
        if n == 0:
            continue
        wins = int((in_comp["result"] == "W").sum())
        draws = int((in_comp["result"] == "D").sum())
        losses = n - wins - draws
        nb = NumberBag()
        w = nb.count("wins", wins)
        n_d = nb.count("matches", n)
        rate = nb.percent("win_rate", wins / n)
        out.append(
            Candidate(
                subject=team,
                # Competition named in ``values``; the text stays generic so a
                # tournament name that carried a digit could never break discipline.
                text=(
                    f"{team} have won {w} of their {n_d} matches in this competition "
                    f"in this data ({rate})."
                ),
                values={"competition": comp, "matches": n, "wins": wins,
                        "draws": draws, "losses": losses},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=wins / n,
                first_date=pd.Timestamp(in_comp["date"].min()),
                last_date=pd.Timestamp(in_comp["date"].max()),
                specificity=clamp_unit(abs(wins - losses) / max(n, 1)),
            )
        )
    return out


def shootout_record(ctx: TemplateContext) -> list[Candidate]:
    """Internationals only: penalty-shootout win/loss record."""
    shootouts = ctx.shootouts
    if shootouts is None or shootouts.empty:
        return []
    out: list[Candidate] = []
    for team, _ in _sides(ctx):
        played = shootouts.loc[
            shootouts["home_team"].eq(team) | shootouts["away_team"].eq(team)
        ]
        n = int(len(played))
        if n == 0:
            continue
        wins = int(played["winner"].eq(team).sum())
        losses = n - wins
        nb = NumberBag()
        w = nb.count("wins", wins)
        n_d = nb.count("shootouts", n)
        rate = nb.percent("win_rate", wins / n)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} have won {w} of {n_d} penalty shootouts in this data ({rate}).",
                values={"shootouts": n, "wins": wins, "losses": losses},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=wins / n,
                first_date=pd.Timestamp(played["date"].min()),
                last_date=pd.Timestamp(played["date"].max()),
                specificity=clamp_unit(abs(wins - losses) / max(n, 1)),
            )
        )
    return out
