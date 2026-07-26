#!/usr/bin/env python3
"""Independent-root robustness for the Stage 3 primary effect family."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from itertools import combinations
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stages" / "stage3" / "src"))

from inh_stage3.algebra import conjugacy_distance, group_distance
from inh_stage3.config import REGIME_ORDER, Stage3Config
from inh_stage3.experiment import (
    _pair_metrics,
    _pretrain_state,
    _run_condition,
    _simultaneous_lower_bounds,
    make_clones,
)
from inh_stage3.ric import calibrate_reference


def evaluate_seed(seed: int, bootstrap_samples: int) -> dict[str, float | int | bool]:
    config = replace(
        Stage3Config(),
        root_seed=seed,
        n_pilot_clones=6,
        n_validation_clones=16,
        n_repeats=2,
        bootstrap_samples=bootstrap_samples,
    )
    config.validate()
    clones = make_clones(config, np.random.default_rng(seed))
    pretrain, raw = [], []
    for clone in clones:
        rng = np.random.default_rng(np.random.SeedSequence([seed, 302, clone.clone_id]))
        state, values = _pretrain_state(config, clone, rng)
        pretrain.append(state)
        if clone.clone_id < config.n_pilot_clones:
            raw.extend(values)
    reference = calibrate_reference(np.asarray(raw, dtype=float), config)
    main = _run_condition(clones, pretrain, reference, config)
    no_remodel = _run_condition(
        clones, pretrain, reference, config, remodeling_enabled=False
    )
    validation = slice(config.n_pilot_clones, None)
    pairs = _pair_metrics(main["holonomies"])
    null_pairs = _pair_metrics(no_remodel["holonomies"])
    null_common = np.concatenate([value[:config.n_pilot_clones, 0] for value in null_pairs.values()])
    null_conj = np.concatenate([value[:config.n_pilot_clones, 1] for value in null_pairs.values()])

    h = main["holonomies"][validation]
    within_common, within_conj = [], []
    for clone in range(h.shape[0]):
        for regime in range(len(REGIME_ORDER)):
            for left, right in combinations(range(config.n_repeats), 2):
                within_common.append(group_distance(h[clone, regime, left, -1], h[clone, regime, right, -1]))
                within_conj.append(conjugacy_distance(h[clone, regime, left, -1], h[clone, regime, right, -1]))
    common_threshold = max(np.quantile(null_common, config.null_quantile), np.quantile(within_common, config.null_quantile)) + config.practical_margin
    conjugacy_threshold = max(np.quantile(null_conj, config.null_quantile), np.quantile(within_conj, config.null_quantile)) + config.practical_margin

    keys = list(pairs)
    common = np.column_stack([pairs[key][validation, 0] for key in keys])
    conjugacy = np.column_stack([pairs[key][validation, 1] for key in keys])
    rng = np.random.default_rng(seed + 992)
    common_lcb = _simultaneous_lower_bounds(common, rng, bootstrap_samples, config.ci_level)
    primary_conj_lcb = _simultaneous_lower_bounds(conjugacy[:, :3], rng, bootstrap_samples, config.ci_level)
    return {
        "root_seed": seed,
        "pilot_clones": config.n_pilot_clones,
        "validation_clones": config.n_validation_clones,
        "repeats": config.n_repeats,
        "common_threshold": float(common_threshold),
        "conjugacy_threshold": float(conjugacy_threshold),
        "minimum_common_mean": float(np.min(np.mean(common, axis=0))),
        "minimum_common_simultaneous_lcb": float(np.min(common_lcb)),
        "minimum_stable_common_mean": float(np.min(np.mean(common[:, :3], axis=0))),
        "minimum_stable_common_simultaneous_lcb": float(np.min(common_lcb[:3])),
        "minimum_primary_conjugacy_mean": float(np.min(np.mean(conjugacy[:, :3], axis=0))),
        "minimum_primary_conjugacy_simultaneous_lcb": float(np.min(primary_conj_lcb)),
        "stable_vs_nonstable_common_family_pass": bool(np.all(common_lcb[:3] > common_threshold)),
        "all_pairs_common_family_pass": bool(np.all(common_lcb > common_threshold)),
        "primary_conjugacy_family_pass": bool(np.all(primary_conj_lcb > conjugacy_threshold)),
        "global_taxonomy_pass": bool(np.all(common_lcb > common_threshold)),
        "overall_primary_pass": bool(np.all(common_lcb[:3] > common_threshold) and np.all(primary_conj_lcb > conjugacy_threshold)),
        "max_unitarity_error": float(main["max_u"]),
        "max_special_unitary_error": float(main["max_su"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="*", default=list(range(20260801, 20260807)))
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--output", type=Path, default=ROOT / "integrated" / "qc" / "stage3_seed_robustness.csv")
    args = parser.parse_args()
    rows = [evaluate_seed(seed, args.bootstrap_samples) for seed in args.seeds]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    passes = sum(bool(row["overall_primary_pass"]) for row in rows)
    print(f"Stage 3 primary pass in {passes}/{len(rows)} independent roots")
    print(args.output)


if __name__ == "__main__":
    main()
