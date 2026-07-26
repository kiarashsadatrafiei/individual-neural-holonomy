#!/usr/bin/env python3
"""Independent point-estimate and artifact-integrity audit.

This script intentionally recomputes reported point estimates from saved arrays
without calling the Stage 2–5 experiment summary functions.
"""
from __future__ import annotations

import hashlib
import json
from itertools import combinations
from pathlib import Path
import sys

import numpy as np
from scipy.stats import rankdata, spearmanr


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "integrated" / "results"
QC = ROOT / "integrated" / "qc"
TOL = 5e-10


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compare(checks: list[dict], label: str, calculated: float, reported: float, tol: float = TOL):
    delta = abs(float(calculated) - float(reported))
    checks.append({
        "label": label,
        "calculated": float(calculated),
        "reported": float(reported),
        "absolute_delta": delta,
        "tolerance": tol,
        "pass": bool(delta <= tol),
    })


def group_distance(left: np.ndarray, right: np.ndarray) -> float:
    relative = left.conj().T @ right
    scalar = float(np.clip(np.real(np.trace(relative)) / 2.0, -1.0, 1.0))
    return float(np.arccos(scalar))


def su2_angle(matrix: np.ndarray) -> float:
    scalar = float(np.clip(np.real(np.trace(matrix)) / 2.0, -1.0, 1.0))
    return float(np.arccos(scalar))


def conjugacy_distance(left: np.ndarray, right: np.ndarray) -> float:
    return abs(su2_angle(left) - su2_angle(right))


def safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float).ravel()
    right = np.asarray(right, dtype=float).ravel()
    if left.size < 3 or np.std(left) <= 1e-14 or np.std(right) <= 1e-14:
        return 0.0
    return float(spearmanr(left, right).statistic)


def relative_distortion(truth: np.ndarray, estimate: np.ndarray) -> float:
    return float(np.linalg.norm(estimate - truth) / max(np.linalg.norm(truth), 1e-15))


def icc_absolute(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    n, k = values.shape
    grand = float(np.mean(values))
    rows = np.mean(values, axis=1)
    cols = np.mean(values, axis=0)
    ms_row = k * np.sum((rows - grand) ** 2) / (n - 1)
    ms_col = n * np.sum((cols - grand) ** 2) / (k - 1)
    residual = values - rows[:, None] - cols[None, :] + grand
    ms_error = np.sum(residual**2) / ((n - 1) * (k - 1))
    denominator = ms_row + (k - 1) * ms_error + k * (ms_col - ms_error) / n
    return float((ms_row - ms_error) / denominator)


def roc_auc(positive: np.ndarray, negative: np.ndarray) -> float:
    positive = np.asarray(positive).ravel()
    negative = np.asarray(negative).ravel()
    ranks = rankdata(np.concatenate([positive, negative]))
    n_pos, n_neg = positive.size, negative.size
    return float((np.sum(ranks[:n_pos]) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def audit_stage1(checks: list[dict]):
    sys.path.insert(0, str(ROOT / "stages" / "stage1" / "src"))
    from inh_stage1.config import Stage1Config
    from inh_stage1.experiment import run_stage1

    rerun = run_stage1(Stage1Config()).summary
    saved = read_json(RESULTS / "stage1_final" / "summary.json")
    for key in ("R", "P", "RP"):
        compare(checks, f"stage1.common_frame.{key}", rerun["estimands"]["common_frame_transport_effects"][key], saved["estimands"]["common_frame_transport_effects"][key])
        compare(checks, f"stage1.conjugacy.{key}", rerun["estimands"]["gauge_invariant_conjugacy_effects"][key], saved["estimands"]["gauge_invariant_conjugacy_effects"][key])
    compare(checks, "stage1.interaction_R_then_P", rerun["estimands"]["interaction_R_then_P"], saved["estimands"]["interaction_R_then_P"])
    compare(checks, "stage1.interaction_P_then_R", rerun["estimands"]["interaction_P_then_R"], saved["estimands"]["interaction_P_then_R"])


def audit_stage2(checks: list[dict]):
    summary = read_json(RESULTS / "stage2_final" / "summary.json")
    data = np.load(RESULTS / "stage2_final" / "held_out_population.npz")
    mapping = {
        "common_R": "common_R", "common_P": "common_P", "common_RP": "common_RP",
        "conjugacy_R": "conjugacy_R", "conjugacy_P": "conjugacy_P", "conjugacy_RP": "conjugacy_RP",
    }
    for summary_key, array_key in mapping.items():
        compare(checks, f"stage2.{summary_key}", np.mean(data[array_key]), summary["held_out_validation"]["estimates"][summary_key]["mean"])
    interaction = 0.5 * (data["interaction_R_then_P"] + data["interaction_P_then_R"])
    compare(checks, "stage2.interaction", np.mean(interaction), summary["held_out_validation"]["estimates"]["interaction"]["mean"])


def audit_stage3(checks: list[dict]):
    summary = read_json(RESULTS / "stage3_final" / "summary.json")
    data = np.load(RESULTS / "stage3_final" / "episode_trajectories.npz")
    hol = data["holonomies"]
    validation = data["validation_indices"]
    regimes = ["adaptive_consolidation", "corrective_reopening", "rigid_closure", "dispersive_instability"]
    for left, right in combinations(range(4), 2):
        common, conj = [], []
        for clone in validation:
            cd, jd = [], []
            for a in range(hol.shape[2]):
                for b in range(hol.shape[2]):
                    cd.append(group_distance(hol[clone, left, a, -1], hol[clone, right, b, -1]))
                    jd.append(conjugacy_distance(hol[clone, left, a, -1], hol[clone, right, b, -1]))
            common.append(np.mean(cd)); conj.append(np.mean(jd))
        key = f"{regimes[left]}__{regimes[right]}"
        compare(checks, f"stage3.{key}.common", np.mean(common), summary["pairwise_validation"][key]["common_frame"]["mean"])
        compare(checks, f"stage3.{key}.conjugacy", np.mean(conj), summary["pairwise_validation"][key]["conjugacy"]["mean"])


def audit_stage4(checks: list[dict]):
    summary = read_json(RESULTS / "stage4_final" / "summary.json")
    data = np.load(RESULTS / "stage4_final" / "recovery_arrays.npz")
    truth = data["truth_angles"]
    estimate = data["calibrated_angle_mean"]
    pair_truth = data["truth_pairwise"]
    pair_estimate = data["estimated_pairwise_mean_calibrated"]
    compare(checks, "stage4.scalar_spearman", safe_spearman(truth, estimate), summary["validation"]["angles"]["spearman"]["value"])
    compare(checks, "stage4.scalar_mae", np.mean(np.abs(truth-estimate)), summary["validation"]["angles"]["mae"]["value"])
    compare(checks, "stage4.pair_spearman", safe_spearman(pair_truth, pair_estimate), summary["validation"]["pairwise_distance_ordering"]["spearman"]["value"])
    compare(checks, "stage4.pair_distortion", relative_distortion(pair_truth, pair_estimate), summary["validation"]["pairwise_distance_ordering"]["relative_distortion"]["value"])
    icc_input = data["calibrated_angles"].transpose(0,2,1).reshape(-1, data["calibrated_angles"].shape[1])
    compare(checks, "stage4.within_setup_icc", icc_absolute(icc_input), summary["validation"]["repeat_icc_within_setup_absolute"]["value"])
    compare(checks, "stage4.dynamic_null_auc", roc_auc(data["absolute_angles"], data["dynamic_null_absolute_angles"]), summary["validation"]["dynamic_zero_holonomy_auc"]["value"])


def audit_stage5(checks: list[dict]):
    summary = read_json(RESULTS / "stage5_final" / "summary.json")
    data = np.load(RESULTS / "stage5_final" / "stage5_arrays.npz")
    truth = data["truth_scalar"]
    pair_truth = data["truth_pairwise"]
    for index, item in enumerate(summary["scenarios"]):
        count = int(data["scenario_draw_counts"][index])
        scalar = np.nanmean(data["scenario_scalar"][index, :, :count], axis=1)
        pair = np.nanmean(data["scenario_pairwise"][index, :, :count], axis=1)
        label = item["label"]
        compare(checks, f"stage5.{label}.scalar_spearman", safe_spearman(truth, scalar), item["metrics"]["scalar_spearman"]["value"])
        compare(checks, f"stage5.{label}.scalar_mae", np.mean(np.abs(truth-scalar)), item["metrics"]["scalar_mae"]["value"])
        compare(checks, f"stage5.{label}.pair_spearman", safe_spearman(pair_truth, pair), item["metrics"]["pairwise_spearman"]["value"])
        compare(checks, f"stage5.{label}.pair_distortion", relative_distortion(pair_truth, pair), item["metrics"]["pairwise_relative_distortion"]["value"])


def checksum_inventory() -> list[dict]:
    inventory = []
    for stage in sorted(RESULTS.glob("stage*_final")):
        for path in sorted(stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS.txt":
                inventory.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size})
    return inventory


def main() -> None:
    checks: list[dict] = []
    audit_stage1(checks)
    audit_stage2(checks)
    audit_stage3(checks)
    audit_stage4(checks)
    audit_stage5(checks)
    output = {
        "audit_type": "independent point-estimate recomputation from saved arrays",
        "tolerance": TOL,
        "checks": checks,
        "all_checks_pass": bool(checks and all(item["pass"] for item in checks)),
        "artifact_inventory": checksum_inventory(),
    }
    QC.mkdir(parents=True, exist_ok=True)
    destination = QC / "independent_recomputation.json"
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": len(checks), "all_checks_pass": output["all_checks_pass"], "output": str(destination)}, indent=2))
    if not output["all_checks_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

