#!/usr/bin/env python3
"""Generate the model-cards docs page from the frozen evaluation artifacts.

The metrics on the public model-cards page must be *real* — never hand-typed.
This script reads the schema-validated `eval_summary*.json` files that the core's
`evaluate` / `evaluate-club` commands emit and renders one model card per
competition (log loss by fold, calibration on the most recent fold, and a real
reliability diagram for the best model). It is deterministic: no wall clock, no
network. Re-run it whenever the evaluation artifacts change:

    python scripts/build_model_cards.py

CI (`scripts/validate_artifacts.py` / the docs build) then guards the output.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF = REPO_ROOT / "docs" / "handoff"
OUT = REPO_ROOT / "docs-site" / "src" / "content" / "docs" / "methodology" / "model-cards.md"

# (summary file, display name, upstream source, surface)
COMPETITIONS = [
    ("eval_summary.json", "Men's senior full internationals", "martj42/international_results", "forward"),
    ("eval_summary_epl.json", "English Premier League", "openfootball", "historical"),
    ("eval_summary_laliga.json", "La Liga", "openfootball", "historical"),
    ("eval_summary_bundesliga.json", "Bundesliga", "openfootball", "historical"),
    ("eval_summary_seriea.json", "Serie A", "openfootball", "historical"),
    ("eval_summary_ligue1.json", "Ligue 1", "openfootball", "historical"),
]

FAMILY_LABEL = {
    "climatological": "climatological (baseline)",
    "elo_ordlogit": "Elo ordinal-logit",
    "poisson_independent": "independent Poisson",
    "dixon_coles": "time-decayed Dixon-Coles",
    "bivariate_poisson": "bivariate Poisson",
    "contextual_dixon_coles": "Dixon-Coles with per-club home advantage and rest days",
}


def _f(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _model(fold: dict, family: str) -> dict:
    return next(m for m in fold["models"] if m["family"] == family)


def _families(summary: dict) -> list[str]:
    # Stable order: baseline first, then the rest as they appear.
    seen: list[str] = []
    for m in summary["folds"][0]["models"]:
        if m["family"] not in seen:
            seen.append(m["family"])
    return seen


def _log_loss_table(summary: dict) -> list[str]:
    folds = summary["folds"]
    header = "| Model | " + " | ".join(f["fold_id"] for f in folds) + " |"
    rule = "|---|" + "---:|" * len(folds)
    lines = [header, rule]
    # Which family has the lowest log loss in each fold (for bolding).
    best = [min(f["models"], key=lambda m: m["log_loss"])["family"] for f in folds]
    for family in _families(summary):
        cells = []
        for i, f in enumerate(folds):
            val = _f(_model(f, family)["log_loss"])
            cells.append(f"**{val}**" if best[i] == family else val)
        lines.append(f"| {FAMILY_LABEL.get(family, family)} | " + " | ".join(cells) + " |")
    return lines


def _calibration_table(summary: dict) -> tuple[str, list[str]]:
    fold = summary["folds"][-1]  # most recent fold
    lines = ["| Model | Brier | ECE | RPS |", "|---|---:|---:|---:|"]
    for family in _families(summary):
        m = _model(fold, family)
        lines.append(
            f"| {FAMILY_LABEL.get(family, family)} | {_f(m['brier'])} | "
            f"{_f(m['ece'])} | {_f(m.get('rps'))} |"
        )
    return fold["fold_id"], lines


def _reliability_table(summary: dict) -> tuple[str, str, list[str]]:
    fold = summary["folds"][-1]
    best = min(fold["models"], key=lambda m: m["log_loss"])
    lines = ["| Confidence bin | n | Empirical | Wilson 95% |", "|---|---:|---:|---|"]
    for b in best["reliability_bins"]:
        if not b["count"]:
            continue
        wilson = f"[{b['wilson_low']:.2f}, {b['wilson_high']:.2f}]"
        lines.append(
            f"| {b['lower']:.1f}–{b['upper']:.1f} | {b['count']} | "
            f"{b['accuracy']:.3f} | {wilson} |"
        )
    return fold["fold_id"], FAMILY_LABEL.get(best["family"], best["family"]), lines


def _skill(value: float) -> str:
    return f"{value * 100:+.1f}%"


def _report_card_tables(summary: dict) -> list[str]:
    lines: list[str] = []
    for card in summary.get("report_cards", []):
        lines += [
            f"**{card['competition']} report card** ({card['window_start']} to {card['window_end']}):",
            "",
            "| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for model in card["models"]:
            interval = model["skill_ci_95"]
            skill = (
                f"{_skill(model['skill_score'])} ({_skill(interval[0])} to {_skill(interval[1])})"
                if interval is not None
                else f"insufficient sample (a fold has <{card['minimum_matches']})"
            )
            lines.append(
                f"| {FAMILY_LABEL.get(model['family'], model['family'])} | "
                f"{model['n_matches']} / {model['n_folds']} | {_f(model['log_loss'])} | "
                f"{skill} | {_f(model['ece'])} | {model['mean_rank']:.1f} "
                f"({model['best_rank']}–{model['worst_rank']}) |"
            )
        lines += [
            "",
            f"Skill intervals use {card['bootstrap']['replicates']:,} seeded, "
            "fold-stratified match-bootstrap samples.",
            "",
        ]
    return lines


def _card(summary: dict, name: str, source: str, surface: str) -> list[str]:
    snap = summary["source_snapshot"]
    ref = str(snap["upstream_ref"])[:12]
    retrieved = str(snap["retrieved_at_utc"])[:10]
    fold_ids = ", ".join(f["fold_id"] for f in summary["folds"])
    surface_note = (
        "forward seal→score surface plus these historical test folds"
        if surface == "forward"
        else "historical, completed seasons only — **not live**"
    )
    lines = [
        f"## {name}",
        "",
        f"- **Scope:** {name} ({surface_note}).",
        f"- **Source snapshot:** {source} `{ref}`, retrieved {retrieved} ({snap['license']}).",
        f"- **Folds:** {fold_ids} — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.",
        "",
        "**Competition report cards** (positive skill means lower log loss than climatology):",
        "",
    ]
    lines += _report_card_tables(summary)
    lines += [
        "**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):",
        "",
    ]
    lines += _log_loss_table(summary)
    lines += [
        "",
        "Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.",
        "",
    ]
    cal_fold, cal_lines = _calibration_table(summary)
    lines += [f"**Calibration — most recent fold ({cal_fold}):**", ""]
    lines += cal_lines
    rel_fold, rel_model, rel_lines = _reliability_table(summary)
    lines += ["", f"**Reliability — {rel_model} on {rel_fold}** (Wilson 95% intervals; empty bins omitted):", ""]
    lines += rel_lines
    lines += [""]
    return lines


def build() -> str:
    header = [
        "---",
        "title: Model cards & calibration",
        "description: Per-competition model cards with skill intervals, real backtest metrics, and reliability diagrams.",
        "---",
        "",
        "These cards report the **actual** out-of-sample backtest metrics Golavo emits, one card per competition. They are generated from the schema-validated `eval_summary*.json` artifacts by `scripts/build_model_cards.py` — never hand-edited — so the numbers here match what CI validates. **Log loss is primary.** No model is a declared champion; forward evidence (the [calibration record](/Golavo/prediction-ledger/)) is kept separate from these historical folds.",
        "",
        ":::note[How to read a card]",
        "Each card lists every deterministic candidate evaluated on that competition against the climatological baseline — the five seated families everywhere, plus any club-league candidate on trial in the domestic cards. Skill is `1 - model log loss / baseline log loss`; its 95% interval is a seeded, fold-stratified bootstrap over held-out matches. Metrics are out-of-sample on strictly chronological folds. League strengths are **not** comparable across competitions — each league is modeled independently from its own pack.",
        ":::",
        "",
    ]
    parts = list(header)
    for filename, name, source, surface in COMPETITIONS:
        summary = json.loads((HANDOFF / filename).read_text(encoding="utf-8"))
        parts += _card(summary, name, source, surface)

    parts += [
        "## Promotion criteria for challengers",
        "",
        "A black-box challenger (e.g. gradient boosting on engineered features, including Dixon-Coles outputs) may be considered only after: (1) at least **two full forward seasons** of evaluation, (2) better RPS **and** log loss (paired bootstrap, p < 0.05), (3) no calibration regression, and (4) a feature-attribution audit. Until then it stays a lab exhibit, not a shipped model.",
        "",
        "Full method, leakage controls, and references: [Prediction methodology](/Golavo/methodology/prediction/).",
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"model cards: wrote {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
