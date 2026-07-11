"""Golavo Phase 0 command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from golavo_core.artifacts import score_forecast, seal_forecast
from golavo_core.evaluation import write_club_evaluation, write_evaluation
from golavo_core.ingest import write_parquet
from golavo_core.models import FAMILIES

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="golavo")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="materialize the typed Parquet match table")
    ingest.add_argument("--pack", type=Path, default=REPO_ROOT / "packs/martj42-internationals")
    ingest.add_argument("--output", type=Path, default=REPO_ROOT / "data/warehouse/matches.parquet")

    evaluate = commands.add_parser("evaluate", help="run frozen chronological folds")
    evaluate.add_argument("--pack", type=Path, default=REPO_ROOT / "packs/martj42-internationals")
    evaluate.add_argument(
        "--summary", type=Path, default=REPO_ROOT / "docs/handoff/eval_summary.json"
    )
    evaluate.add_argument("--report", type=Path, default=REPO_ROOT / "docs/handoff/eval_report.md")

    evaluate_club = commands.add_parser(
        "evaluate-club", help="run frozen chronological English Premier League season folds"
    )
    evaluate_club.add_argument(
        "--pack", type=Path, default=REPO_ROOT / "packs/openfootball-eng-pl"
    )
    evaluate_club.add_argument(
        "--summary", type=Path, default=REPO_ROOT / "docs/handoff/eval_summary_epl.json"
    )
    evaluate_club.add_argument(
        "--report", type=Path, default=REPO_ROOT / "docs/handoff/eval_report_epl.md"
    )

    seal = commands.add_parser("seal", help="write an immutable ForecastArtifact")
    seal.add_argument("--pack", type=Path, default=REPO_ROOT / "packs/martj42-internationals")
    seal.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data/artifacts")
    seal.add_argument("--date", required=True)
    seal.add_argument("--home-team", required=True)
    seal.add_argument("--away-team", required=True)
    seal.add_argument("--as-of", required=True, dest="as_of_utc")
    seal.add_argument("--horizon", choices=("T-72h", "T-24h", "T-60m"), default="T-24h")
    seal.add_argument("--family", choices=FAMILIES, default="elo_ordlogit")
    seal.add_argument("--seed", type=int, default=20260710)
    seal.add_argument("--match-id")

    score = commands.add_parser("score", help="score a seal from a newer snapshot")
    score.add_argument("--artifact", type=Path, required=True)
    score.add_argument("--newer-pack", type=Path, required=True)
    score.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data/artifacts")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "ingest":
        print(write_parquet(args.pack, args.output))
    elif args.command == "evaluate":
        write_evaluation(
            args.pack,
            args.summary,
            args.report,
            REPO_ROOT / "docs/contracts/forecast_artifact.schema.json",
        )
        print(args.summary)
    elif args.command == "evaluate-club":
        write_club_evaluation(
            args.pack,
            args.summary,
            args.report,
            REPO_ROOT / "docs/contracts/forecast_artifact.schema.json",
        )
        print(args.summary)
    elif args.command == "seal":
        print(
            seal_forecast(
                pack_dir=args.pack,
                output_dir=args.output_dir,
                date=args.date,
                home_team=args.home_team,
                away_team=args.away_team,
                as_of_utc=args.as_of_utc,
                horizon=args.horizon,
                family=args.family,
                seed=args.seed,
                match_id=args.match_id,
            )
        )
    elif args.command == "score":
        print(
            score_forecast(
                artifact_path=args.artifact,
                newer_pack_dir=args.newer_pack,
                output_dir=args.output_dir,
            )
        )


if __name__ == "__main__":
    main()
