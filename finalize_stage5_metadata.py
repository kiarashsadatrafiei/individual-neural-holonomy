#!/usr/bin/env python3
"""Finalize Stage 5 metadata after verifying the saved baseline arrays.

The expensive numerical run is not altered.  This deterministic step separates
exact implementation reproduction of the selected frozen Stage 4 repeat from
the scientific question of whether that one repeat satisfies every confidence-
bound cutoff used by the Stage 4 repeat-averaged primary analysis.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "integrated" / "results" / "stage5_final"
FROZEN = ROOT / "stages" / "stage5" / "data" / "stage4_frozen" / "stage4_recovery_arrays.npz"
STAGE5_SRC = ROOT / "stages" / "stage5" / "src"
sys.path.insert(0, str(STAGE5_SRC))
from inh_stage4.lineage import sha256_file, sha256_tree


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def report(summary: dict) -> str:
    criteria = summary["criteria"]
    metrics = summary["baseline"]["metrics"]
    lines = [
        "# Stage 5 validation report",
        "",
        "## Scope",
        "",
        summary["model_scope"]["primary_claim"],
        "",
        summary["model_scope"]["identifiability_distinction"],
        "",
        "Stage 5 reuses the Stage 4 validation cohort and is a sensitivity analysis, not an independent replication.",
        "",
        "## Frozen lineage and single-repeat baseline",
        "",
        f"- Stage 4 version: `{summary['lineage']['stage4_version']}`",
        f"- Adversarial clone count: `{len(summary['design']['clone_ids'])}`",
        f"- Prespecified observation repeat: `{summary['design']['observation_repeat']}`",
        f"- Exact equality with the corresponding frozen Stage 4 repeat: `{criteria['baseline_exact_reproduction_pass']}` (maximum absolute delta `{summary['design']['baseline_exact_reproduction_max_delta']:.3e}`).",
        f"- All single-repeat scientific claim cutoffs passed: `{criteria['single_repeat_baseline_claim_pass']}`.",
        "- This single-repeat decision is distinct from the Stage 4 primary result, which averages three repeats and passes its prespecified criteria.",
        "",
        f"- Scalar Spearman: {metrics['scalar_spearman']['value']:.4f} [{metrics['scalar_spearman']['lower']:.4f}, {metrics['scalar_spearman']['upper']:.4f}]",
        f"- Scalar MAE: {metrics['scalar_mae']['value']:.6f} [{metrics['scalar_mae']['lower']:.6f}, {metrics['scalar_mae']['upper']:.6f}]",
        f"- Ordinal accuracy: {metrics['ordinal_accuracy']['value']:.4f} [{metrics['ordinal_accuracy']['lower']:.4f}, {metrics['ordinal_accuracy']['upper']:.4f}]",
        f"- Pairwise Spearman: {metrics['pairwise_spearman']['value']:.4f} [{metrics['pairwise_spearman']['lower']:.4f}, {metrics['pairwise_spearman']['upper']:.4f}]",
        f"- Path AUC: {metrics['path_auc']['value']:.4f} [{metrics['path_auc']['lower']:.4f}, {metrics['path_auc']['upper']:.4f}]",
        "",
        "## Equivalence and known-invertible controls",
        "",
    ]
    for name, item in summary["equivalence"].items():
        lines.append(f"- {name}: pass={item['pass']}; scalar delta UCB={item['scalar_delta']['upper']:.3e}; pairwise delta UCB={item['pairwise_delta']['upper']:.3e}")
    for label, item in summary["known_invertible_controls"].items():
        lines.append(f"- {label}: information_preserved={item['information_preserved']}; raw inverse error={item['raw_reconstruction_error']:.3e}; corrected spot-check delta={item['corrected_recovery_spotcheck_delta']:.3e}")
    lines += ["", "## Strict information-loss diagnostics", ""]
    diagnostics = summary["information_loss_diagnostics"]
    for name in ("channel_projection", "temporal_coarse_graining", "phase_scrambling"):
        item = diagnostics[name]
        lines.append(
            f"- {name}: family_success={item['family_success']}; boundary={item['boundary_present']}; "
            f"ordering_drop={item['ordering_degraded']}; error_rise={item['error_increased']}."
        )
    lines += [
        f"- Strict families passing: {diagnostics['successful_families']}/{diagnostics['required_families']}.",
        "- Channel projection did not show a bootstrap-supported monotonic ordering decline from its weak to strong setting; it is therefore not counted as a strict information-loss boundary.",
        "",
        "## Decision",
        "",
        f"`overall_pass = {criteria['overall_pass']}`",
        "",
        "## Criteria",
        "",
    ]
    lines.extend(f"- `{name}`: {value}" for name, value in criteria.items())
    lines += ["", "## Interpretation limits", ""]
    lines.extend(f"- {value}" for value in summary["interpretation_limits"])
    return "\n".join(lines) + "\n"


def main() -> None:
    summary_path = RESULT / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    arrays = np.load(RESULT / "stage5_arrays.npz")
    frozen = np.load(FROZEN)
    repeat = int(summary["design"]["observation_repeat"])
    deltas = {
        "scalar": float(np.max(np.abs(arrays["baseline_scalar"][:, 0] - frozen["calibrated_angles"][:, repeat]))),
        "pairwise": float(np.max(np.abs(arrays["baseline_pairwise"][:, 0] - frozen["estimated_pairwise_calibrated"][:, repeat]))),
        "positive_angles": float(np.max(np.abs(arrays["scenario_positive_angles"][0, :, 0] - frozen["absolute_angles"][:, repeat]))),
        "null_angles": float(np.max(np.abs(arrays["scenario_null_angles"][0, :, 0] - frozen["dynamic_null_absolute_angles"][:, repeat]))),
    }
    maximum = max(deltas.values())
    if maximum > 1e-12:
        raise SystemExit(f"Frozen Stage 4 repeat mismatch: {maximum}")

    old_claim_pass = bool(summary["criteria"].pop("baseline_reproduction_pass"))
    summary["criteria"] = {
        "frozen_lineage_pass": summary["criteria"]["frozen_lineage_pass"],
        "baseline_exact_reproduction_pass": True,
        "single_repeat_baseline_claim_pass": old_claim_pass,
        "equivalence_pass": summary["criteria"]["equivalence_pass"],
        "known_invertible_information_preservation_pass": summary["criteria"]["known_invertible_information_preservation_pass"],
        "information_loss_boundary_pass": summary["criteria"]["information_loss_boundary_pass"],
        "claim_lattice_consistency_pass": summary["criteria"]["claim_lattice_consistency_pass"],
        "numerical_pass": summary["criteria"]["numerical_pass"],
    }
    summary["criteria"]["overall_pass"] = bool(all(summary["criteria"].values()))
    summary["design"]["baseline_estimand"] = "one prespecified Stage 4 observation repeat; distinct from the Stage 4 repeat-averaged primary estimand"
    summary["design"]["baseline_exact_reproduction_max_delta"] = maximum
    summary["design"]["baseline_exact_reproduction_component_deltas"] = deltas
    note = "The single-repeat baseline exactly reproduces the corresponding frozen Stage 4 arrays, but its scalar confidence-bound criterion fails; the repeat-averaged Stage 4 primary result remains the relevant confirmatory estimand."
    if note not in summary["interpretation_limits"]:
        summary["interpretation_limits"].append(note)
    write_json(summary_path, summary)
    (RESULT / "VALIDATION_REPORT.md").write_text(report(summary), encoding="utf-8")

    manifest_path = RESULT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["criteria"] = summary["criteria"]
    manifest["source_tree_sha256"] = sha256_tree(STAGE5_SRC / "inh_stage5")
    write_json(manifest_path, manifest)

    rows = []
    for path in sorted(RESULT.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            rows.append(f"{sha256_file(path)}  {path.name}")
    (RESULT / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"maximum_reproduction_delta": maximum, "criteria": summary["criteria"]}, indent=2))


if __name__ == "__main__":
    main()
