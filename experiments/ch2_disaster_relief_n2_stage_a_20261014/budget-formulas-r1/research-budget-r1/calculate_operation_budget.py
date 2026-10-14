#!/usr/bin/env python3
"""Calculate deterministic operation counts without filling unknown measurements."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def calculate(usable_training_windows: int | None = None,
              training_candidate_counts: list[int] | None = None,
              development_candidate_counts: list[int] | None = None,
              branch_windows_by_split: dict[str, list[dict]] | None = None,
              horizon_minutes: int | None = None) -> dict:
    parents = {"train": 56, "development": 14, "confirmation": 24}
    window_minutes = [8, 16, 24, 32]
    split_names = tuple(parents)
    methods = 2
    seeds = 3
    smoke_rounds = 8
    total_rounds = 32
    episodes_per_round = 4
    ppo_updates_per_round = 16
    confirmation_parents = 24
    reference_horizon = 60

    result = {
        "status": "UNFROZEN",
        "authorization_created": False,
        "stage_b": {
            "nominal_window_slots_by_split": {name: count * len(window_minutes) for name, count in parents.items()},
            "context_scan_count_if_one_per_parent": sum(parents.values()),
            "context_scan_steps_if_one_per_parent": None if horizon_minutes is None else sum(parents.values()) * horizon_minutes,
            "branch_count_by_split": None,
            "candidate_continuation_step_upper_bound_by_split": None,
            "actual_candidate_continuation_steps": None,
            "complete_b_ledger_environment_steps": None,
            "noop_reference_and_restore_prefix_steps": None,
            "actual_context_scan_steps": None,
            "formal_horizon_minutes": horizon_minutes,
            "candidate_continuation_step_formula": "sum(candidate_count * min(30, max(0, H - window_minute))) over executed opportunity windows; excludes NOOP-reference and restore/prefix work",
        },
        "world_model": {
            "usable_training_windows": usable_training_windows,
            "batch_size_window_rows": 8,
            "epochs": 40,
            "updates_per_seed": None,
            "updates_all_three_seeds": None,
            "candidate_sample_visits_all_three_seeds": None,
            "target_forwards_all_three_seeds_reference": None,
            "update_evidence_rows_reference": None,
            "development_candidate_prediction_rows": None,
            "formal_candidate_model_evaluations": None,
            "formal_forward_call_count": None,
            "final_checkpoint_writes_if_reference_trainer_adopted": 3,
            "final_checkpoint_readbacks_if_reference_trainer_adopted": 3,
        },
        "combination": {
            "smoke_updates": methods * seeds * smoke_rounds * ppo_updates_per_round,
            "total_updates_including_smoke": methods * seeds * total_rounds * ppo_updates_per_round,
            "post_smoke_updates": methods * seeds * (total_rounds - smoke_rounds) * ppo_updates_per_round,
            "smoke_episodes": methods * seeds * smoke_rounds * episodes_per_round,
            "total_episodes": methods * seeds * total_rounds * episodes_per_round,
            "formal_smoke_environment_steps": None,
            "formal_total_environment_steps": None,
            "environment_step_formula": "episode_count * H_run; formal H_run is unresolved",
            "formal_horizon_minutes": horizon_minutes,
            "smoke_environment_steps_at_60_minute_reference": methods * seeds * smoke_rounds * episodes_per_round * reference_horizon,
            "total_environment_steps_at_60_minute_reference": methods * seeds * total_rounds * episodes_per_round * reference_horizon,
        },
        "confirmation": {
            "parents": confirmation_parents,
            "trajectories": confirmation_parents * (seeds + seeds + 1),
            "formal_minute_step_upper_bound": None,
            "minute_step_upper_bound_formula": "trajectory_count * H_confirmation; formal horizon is unresolved",
            "minute_step_upper_bound_at_60_minute_reference": confirmation_parents * (seeds + seeds + 1) * reference_horizon,
            "bootstrap_replicates": 10000,
            "bootstrap_seed": 20261014,
            "logical_parent_draws": 10000 * confirmation_parents,
            "trajectory_slots_across_resamples": 10000 * confirmation_parents * (seeds + seeds + 1),
        },
        "empirical_costs": {
            "linux_cpu_seconds": None,
            "linux_wall_seconds": None,
            "peak_rss_bytes": None,
            "checkpoint_bytes": None,
            "export_bytes": None,
        },
        "unresolved_counts": [
            "usable windows after termination/no-opportunity/admission",
            "candidate catalogs per window",
            "branch environment steps",
            "prediction forwards and candidate evaluations",
            "checkpoint and export operations/bytes",
            "target-runtime empirical resource costs",
        ],
    }

    if usable_training_windows is not None:
        if type(usable_training_windows) is not int or usable_training_windows < 0:
            raise ValueError("usable_training_windows must be a nonnegative integer")
        updates_per_seed = 40 * math.ceil(usable_training_windows / 8)
        result["world_model"]["updates_per_seed"] = updates_per_seed
        result["world_model"]["updates_all_three_seeds"] = 3 * updates_per_seed
        result["world_model"]["target_forwards_all_three_seeds_reference"] = 3 * 40 * usable_training_windows
        result["world_model"]["update_evidence_rows_reference"] = 3 * updates_per_seed
    if horizon_minutes is not None:
        if type(horizon_minutes) is not int or horizon_minutes <= 0:
            raise ValueError("horizon_minutes must be a positive integer")
        result["combination"]["formal_smoke_environment_steps"] = (
            result["combination"]["smoke_episodes"] * horizon_minutes
        )
        result["combination"]["formal_total_environment_steps"] = (
            result["combination"]["total_episodes"] * horizon_minutes
        )
        result["confirmation"]["formal_minute_step_upper_bound"] = (
            result["confirmation"]["trajectories"] * horizon_minutes
        )

    if training_candidate_counts is not None:
        if any(type(n) is not int or n < 1 for n in training_candidate_counts):
            raise ValueError("candidate counts must be positive integers including any legal NOOP")
        if usable_training_windows is None or len(training_candidate_counts) != usable_training_windows:
            raise ValueError("provide one candidate count per usable training window")
        result["world_model"]["candidate_sample_visits_all_three_seeds"] = (
            3 * 40 * sum(training_candidate_counts)
        )
    if development_candidate_counts is not None:
        if any(type(n) is not int or n < 1 for n in development_candidate_counts):
            raise ValueError("development candidate counts must be positive integers including any legal NOOP")
        result["world_model"]["development_candidate_prediction_rows"] = (
            3 * sum(development_candidate_counts)
        )
    if branch_windows_by_split is not None:
        if set(branch_windows_by_split) != set(split_names):
            raise ValueError("branch windows must provide train, development, and confirmation arrays")
        branch_counts: dict[str, int] = {}
        branch_step_caps: dict[str, int] | None = {} if horizon_minutes is not None else None
        allowed_minutes = set(window_minutes)
        for split, rows in branch_windows_by_split.items():
            if not isinstance(rows, list):
                raise ValueError(f"{split} branch windows must be an array")
            branch_counts[split] = 0
            for row in rows:
                minute = row.get("minute")
                count = row.get("candidate_count")
                if type(minute) is not int or minute not in allowed_minutes:
                    raise ValueError(f"{split} branch window minute must be one of {window_minutes}")
                if type(count) is not int or count < 1:
                    raise ValueError("candidate_count must be a positive integer including any legal NOOP")
                branch_counts[split] += count
                if branch_step_caps is not None:
                    if horizon_minutes <= minute:
                        raise ValueError("branch window minute must precede the supplied horizon")
                    branch_step_caps[split] = branch_step_caps.get(split, 0) + count * min(30, horizon_minutes - minute)
        result["stage_b"]["branch_count_by_split"] = branch_counts
        result["stage_b"]["candidate_continuation_step_upper_bound_by_split"] = branch_step_caps
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usable-training-windows", type=int)
    parser.add_argument("--candidate-counts-json", type=Path,
                        help="JSON file containing one integer legal-candidate count per usable window")
    parser.add_argument("--development-candidate-counts-json", type=Path,
                        help="JSON array containing one legal-candidate count per development window")
    parser.add_argument("--branch-windows-json", type=Path,
                        help="JSON object of split arrays; each executed opportunity window has minute and candidate_count")
    parser.add_argument("--horizon-minutes", type=int,
                        help="Measured/frozen horizon for branch and context step bounds; omitted means unresolved")
    args = parser.parse_args()
    counts = None
    if args.candidate_counts_json is not None:
        counts = json.loads(args.candidate_counts_json.read_text(encoding="utf-8"))
        if not isinstance(counts, list):
            parser.error("candidate-counts-json must contain a JSON array")
        if args.usable_training_windows is None:
            args.usable_training_windows = len(counts)
    development_counts = None
    if args.development_candidate_counts_json is not None:
        development_counts = json.loads(args.development_candidate_counts_json.read_text(encoding="utf-8"))
        if not isinstance(development_counts, list):
            parser.error("development-candidate-counts-json must contain a JSON array")
    branch_windows = None
    if args.branch_windows_json is not None:
        branch_windows = json.loads(args.branch_windows_json.read_text(encoding="utf-8"))
        if not isinstance(branch_windows, dict):
            parser.error("branch-windows-json must contain a JSON object")
    print(json.dumps(calculate(args.usable_training_windows, counts, development_counts,
                               branch_windows, args.horizon_minutes), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
