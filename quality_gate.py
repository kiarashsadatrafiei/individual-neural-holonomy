#!/usr/bin/env python3
"""Final multi-layer quality gate for code, artifacts, statistics, and figures."""
from __future__ import annotations

import compileall
import json
from pathlib import Path
import re
import sys

import numpy as np
from PIL import Image


ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"integrated"/"results"
FIGURES=ROOT/"integrated"/"figures"
QC=ROOT/"integrated"/"qc"


def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))


def record(checks,name,condition,detail=""):
    checks.append({"check":name,"pass":bool(condition),"detail":str(detail)})


def finite_json(value) -> bool:
    if isinstance(value,dict): return all(finite_json(v) for v in value.values())
    if isinstance(value,list): return all(finite_json(v) for v in value)
    if isinstance(value,float): return bool(np.isfinite(value))
    return True


def main():
    checks=[]
    compiled=compileall.compile_dir(ROOT/"stages",quiet=1) and compileall.compile_dir(ROOT/"scripts",quiet=1)
    record(checks,"recursive Python compilation",compiled)
    s1,s2,s3,s4,s5=[load(RESULTS/f"stage{i}_final"/"summary.json") for i in range(1,6)]
    for i,s in enumerate((s1,s2,s3,s4,s5),1): record(checks,f"Stage {i} JSON finite",finite_json(s))
    record(checks,"Stage 1 implementation QC passes",s1["implementation_validation_pass"])
    record(checks,"Stage 1 scientific interaction criterion correctly fails",not s1["scientific_criteria"]["passed"])
    record(checks,"Stage 2 split has no overlap",not s2["design"]["split_overlap"])
    record(checks,"Stage 2 independent-noise correction positive",s2["independent_noise_null_corrected"]["null_corrected_interaction"]["lower"]>0)
    record(checks,"Stage 2 fast RIC not overclaimed",not s2["specificity_and_RIC_controls"]["fast_RIC_modulation_supported"])
    record(checks,"Stage 3 pilot-only RIC calibration",s3["design"]["pilot_only_ric_calibration"])
    record(checks,"Stage 3 paired exogenous streams",s3["design"]["paired_exogenous_streams_for_ablations"])
    record(checks,"Stage 3 focal family passes",s3["criteria"]["overall_pass_for_stable_vs_nonstable_claim"])
    record(checks,"Stage 3 global taxonomy correctly fails",not s3["criteria"]["global_four_regime_taxonomy_supported"])
    record(checks,"Stage 3 fast RIC not overclaimed",not s3["criteria"]["fast_ric_causality_supported"])
    record(checks,"Stage 3 numerical QC",s3["criteria"]["numerical_pass"])
    record(checks,"Stage 4 split has no overlap",not s4["split"]["overlap"])
    record(checks,"Stage 4 controlled recovery passes",s4["criteria"]["overall_pass"])
    record(checks,"Stage 4 clone-clustered ICC criterion",s4["validation"]["repeat_icc_within_setup_absolute"]["lower"]>.70)
    record(checks,"Stage 4 independent-session estimate present","independent_session_generalization" in s4)
    record(checks,"Stage 5 cohort reuse disclosed","reused" in s5["design"]["cohort_status"].lower())
    record(checks,"Stage 5 selected repeat exactly reproduces frozen arrays",s5["criteria"]["baseline_exact_reproduction_pass"] and s5["design"]["baseline_exact_reproduction_max_delta"]<=1e-12)
    record(checks,"Stage 5 single-repeat scalar limitation retained",not s5["criteria"]["single_repeat_baseline_claim_pass"] and not s5["baseline"]["claims"]["scalar_value"])
    record(checks,"Stage 5 true information-loss families only",set(k for k,v in s5["information_loss_diagnostics"].items() if isinstance(v,dict))=={"channel_projection","temporal_coarse_graining","phase_scrambling"})
    record(checks,"Stage 5 strict 2-of-3 result retained",s5["information_loss_diagnostics"]["successful_families"]==2 and not s5["information_loss_diagnostics"]["channel_projection"]["family_success"] and s5["information_loss_diagnostics"]["temporal_coarse_graining"]["family_success"] and s5["information_loss_diagnostics"]["phase_scrambling"]["family_success"])
    record(checks,"Stage 5 overall scientific decision correctly limited",not s5["criteria"]["overall_pass"])
    record(checks,"Stage 5 circular shift not classified as information loss",any(item["transformation"]=="trial_timing_jitter" and item["family"]=="temporal_nuisance" for item in s5["scenarios"]))
    record(checks,"Stage 5 numerical QC",s5["criteria"]["numerical_pass"])

    stage3_source=(ROOT/"stages"/"stage3"/"src"/"inh_stage3"/"experiment.py").read_text(encoding="utf-8")
    record(checks,"Stage 3 seed excludes intervention flags","int(remodeling_enabled)" not in stage3_source and "int(constant_gate)" not in stage3_source)
    stage4_source=(ROOT/"stages"/"stage4"/"src"/"inh_stage4"/"experiment.py").read_text(encoding="utf-8")
    record(checks,"Stage 4 uses clustered ICC","bootstrap_icc_clustered" in stage4_source)
    stage5_source=(ROOT/"stages"/"stage5"/"src"/"inh_stage5"/"experiment.py").read_text(encoding="utf-8")
    record(checks,"Stage 5 requires all three loss families","len(names) == 3 and successful_families == len(names)" in stage5_source)

    for path in sorted(FIGURES.glob("Figure_*.png")):
        with Image.open(path) as image:
            width,height=image.size
        record(checks,f"Figure resolution {path.name}",width>=3000 and height>=1000,f"{width}x{height}")
        record(checks,f"Vector PDF exists {path.stem}",(path.with_suffix(".pdf")).exists())
        record(checks,f"Vector SVG exists {path.stem}",(path.with_suffix(".svg")).exists())
    record(checks,"All eight main figures present",len(list(FIGURES.glob("Figure_*.png")))==8)

    audit=load(QC/"independent_recomputation.json") if (QC/"independent_recomputation.json").exists() else {}
    record(checks,"Independent point-estimate recomputation",audit.get("all_checks_pass",False),f"{len(audit.get('checks',[]))} comparisons")
    seed_path=QC/"stage3_seed_robustness.csv"
    record(checks,"Stage 3 independent-root robustness artifact",seed_path.exists())

    output={"quality_gate":"INH integrated v1.0.0","checks":checks,"passed":all(item["pass"] for item in checks),"passed_count":sum(item["pass"] for item in checks),"total_count":len(checks)}
    QC.mkdir(parents=True,exist_ok=True); (QC/"quality_gate.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:output[k] for k in ("passed","passed_count","total_count")},indent=2))
    if not output["passed"]: raise SystemExit(2)


if __name__=="__main__": main()
