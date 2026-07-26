#!/usr/bin/env python3
"""Reproduce the corrected Stage 1–5 analysis and integrated artifacts."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "integrated" / "results"
QC = ROOT / "integrated" / "qc"


def environment(src: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYTHONHASHSEED": "0",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(ROOT / ".mplconfig"),
        "PYTHONPATH": str(src),
    })
    return env


def run(stage: Path, command: list[str], log_name: str) -> None:
    QC.mkdir(parents=True, exist_ok=True)
    with (QC / log_name).open("w", encoding="utf-8") as log:
        subprocess.run(
            command, cwd=stage, env=environment(stage / "src"),
            stdout=log, stderr=subprocess.STDOUT, check=True,
        )


def regenerate_stage4_export(stage4: Path) -> None:
    code = """
from pathlib import Path
from inh_stage4.config import Stage4Config
from inh_stage4.lineage import generate_export, save_export
root=Path('.').resolve(); config=Stage4Config()
save_export(generate_export(config,root),root/'data'/'stage3_v0.4.0_stage4_cohort_export.npz')
"""
    run(stage4, [sys.executable, "-c", code], "stage4_export.log")


def freeze_stage4_for_stage5(stage4: Path, stage5: Path) -> None:
    source_result = RESULTS / "stage4_final"
    frozen = stage5 / "data" / "stage4_frozen"
    frozen.mkdir(parents=True, exist_ok=True)
    mapping = {
        source_result / "summary.json": frozen / "stage4_summary.json",
        source_result / "manifest.json": frozen / "stage4_manifest.json",
        source_result / "recovery_arrays.npz": frozen / "stage4_recovery_arrays.npz",
        stage4 / "data" / "stage3_v0.4.0_stage4_cohort_export.npz": stage5 / "data" / "stage3_v0.4.0_stage4_cohort_export.npz",
        stage4 / "data" / "stage3_v0.4.0_stage4_cohort_export.json": stage5 / "data" / "stage3_v0.4.0_stage4_cohort_export.json",
    }
    for source, destination in mapping.items():
        shutil.copy2(source, destination)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    stages = ROOT / "stages"
    run(stages / "stage1", [sys.executable, "scripts/run_stage1.py", "--output", str(RESULTS / "stage1_final")], "stage1.log")
    run(stages / "stage2", [sys.executable, "scripts/run_stage2.py", "--output", str(RESULTS / "stage2_final")], "stage2.log")
    run(stages / "stage3", [sys.executable, "scripts/run_stage3.py", "--output", str(RESULTS / "stage3_final")], "stage3.log")
    regenerate_stage4_export(stages / "stage4")
    run(stages / "stage4", [sys.executable, "scripts/run_stage4.py", "--output", str(RESULTS / "stage4_final")], "stage4.log")
    freeze_stage4_for_stage5(stages / "stage4", stages / "stage5")
    run(stages / "stage5", [sys.executable, "scripts/run_stage5.py", "--output", str(RESULTS / "stage5_final")], "stage5.log")
    run(ROOT, [sys.executable, "scripts/finalize_stage5_metadata.py"], "stage5_metadata.log")
    run(ROOT, [sys.executable, "scripts/stage3_seed_robustness.py"], "stage3_seed_robustness.log")
    run(ROOT, [sys.executable, "scripts/build_integrated_outputs.py"], "integrated_outputs.log")
    run(ROOT, [sys.executable, "scripts/run_embedded_tests.py"], "embedded_tests.log")
    run(ROOT, [sys.executable, "scripts/independent_audit.py"], "independent_audit.log")
    run(ROOT, [sys.executable, "scripts/quality_gate.py"], "quality_gate.log")
    run(ROOT, [sys.executable, "scripts/build_report_docx.py"], "report_docx.log")
    run(ROOT, [sys.executable, "scripts/build_revised_article_docx.py"], "revised_article_docx.log")
    print("All corrected stages and editable integrated artifacts completed. Rebuild PDFs/workbook, then run release_audit.py and build_release.py.")


if __name__ == "__main__":
    main()
