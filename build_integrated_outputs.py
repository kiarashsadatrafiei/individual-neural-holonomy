#!/usr/bin/env python3
"""Build manuscript-ready tables, figures, and paste-ready text."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import re
import tempfile
from typing import Any, Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "integrated" / "results"
FIGURES = ROOT / "integrated" / "figures"
TABLES = ROOT / "integrated" / "tables"
MANUSCRIPT = ROOT / "integrated" / "manuscript"
QC = ROOT / "integrated" / "qc"

COLORS = {
    "blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
    "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9",
    "yellow": "#F0E442", "black": "#222222", "gray": "#7A7A7A",
    "light": "#E9EEF3", "stable": "#0072B2", "corrective": "#E69F00",
    "rigid": "#7A7A7A", "diffuse": "#CC79A7",
}
REGIME_COLORS = [COLORS["stable"], COLORS["corrective"], COLORS["rigid"], COLORS["diffuse"]]
REGIME_NAMES = ["Stable", "Corrective", "Rigid", "Diffuse"]
PAIR_SHORT = ["S–C", "S–R", "S–D", "C–R", "C–D", "R–D"]


mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.0,
    "axes.titlesize": 9.0,
    "axes.labelsize": 8.0,
    "xtick.labelsize": 7.0,
    "ytick.labelsize": 7.0,
    "legend.fontsize": 7.0,
    "axes.linewidth": 0.7,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.facecolor": "white",
})


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dirs() -> None:
    for path in (FIGURES, TABLES, MANUSCRIPT, QC):
        path.mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, stem: str) -> None:
    # Save through hidden temporary files and atomically publish completed
    # images. This prevents the shared-workspace synchronizer from observing a
    # partially written PNG during long high-resolution encodes.
    for suffix, options in (
        (".pdf", {}),
        (".svg", {}),
        (".png", {"dpi": 600}),
    ):
        handle = tempfile.NamedTemporaryFile(
            prefix=f".{stem}.", suffix=f".tmp{suffix}", dir=FIGURES, delete=False
        )
        temporary = Path(handle.name)
        handle.close()
        try:
            fig.savefig(temporary, format=suffix[1:], bbox_inches="tight", **options)
            os.replace(temporary, FIGURES / f"{stem}{suffix}")
        finally:
            temporary.unlink(missing_ok=True)
    plt.close(fig)


def panel(axis: plt.Axes, label: str) -> None:
    axis.text(-0.12, 1.06, label, transform=axis.transAxes, fontsize=10, fontweight="bold", va="top")


def clean_axis(axis: plt.Axes) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(axis="y", color="#D8DDE3", linewidth=.5, alpha=.75)
    axis.set_axisbelow(True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def latex_escape(value: Any) -> str:
    text = str(value)
    for old, new in (("\\", "\\textbackslash{}"), ("_", "\\_"), ("%", "\\%"), ("&", "\\&"), ("#", "\\#")):
        text = text.replace(old, new)
    return text


def write_latex(path: Path, rows: list[dict[str, Any]], caption: str, label: str) -> None:
    if not rows:
        return
    columns = list(rows[0])
    spec = "l" + "r" * (len(columns) - 1)
    lines = ["\\begin{table}[t]", "\\centering", "\\small", f"\\caption{{{latex_escape(caption)}}}", f"\\label{{{label}}}", f"\\begin{{tabular}}{{{spec}}}", "\\toprule", " & ".join(latex_escape(c) for c in columns) + " \\\\", "\\midrule"]
    for row in rows:
        lines.append(" & ".join(latex_escape(row[c]) for c in columns) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def err(est: dict[str, float], key: str = "mean") -> tuple[float, float, float]:
    center = float(est[key])
    return center, center - float(est["lower"]), float(est["upper"]) - center


def cluster_time_ci(values: np.ndarray, seed: int = 1, samples: int = 2000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Clone-clustered time-course mean and percentile interval."""
    clone_means = np.mean(np.asarray(values, dtype=float), axis=1)
    observed = np.mean(clone_means, axis=0)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, clone_means.shape[0], size=(samples, clone_means.shape[0]))
    boot = np.mean(clone_means[indices], axis=1)
    lower, upper = np.quantile(boot, [0.025, 0.975], axis=0)
    return observed, lower, upper


def figure1_design() -> None:
    fig, axis = plt.subplots(figsize=(7.2, 2.9))
    axis.set_xlim(0, 1); axis.set_ylim(0, 1); axis.axis("off")
    boxes = [
        ("Stage 1", "Constructive\nshared-frame example", "criterion fails"),
        ("Stage 2", "Pilot + held-out\nlatent validation", "CRN + noise null"),
        ("Stage 3", "Pilot-calibrated\nremodeling", "stable vs non-stable"),
        ("Stage 4", "Cross-fitted\nsynthetic recovery", "dev / cal / val"),
        ("Stage 5", "Transformation\nboundaries", "sensitivity cohort"),
    ]
    xs = np.linspace(.11, .89, 5)
    for index, (title, body, foot) in enumerate(boxes):
        x = xs[index]
        color = [COLORS["gray"], COLORS["orange"], COLORS["blue"], COLORS["green"], COLORS["purple"]][index]
        box = FancyBboxPatch((x-.085, .40), .17, .38, boxstyle="round,pad=0.012,rounding_size=.018", facecolor="white", edgecolor=color, linewidth=1.4)
        axis.add_patch(box)
        axis.text(x, .71, title, ha="center", va="center", fontweight="bold", color=color, fontsize=9)
        axis.text(x, .58, body, ha="center", va="center", fontsize=7.2, linespacing=1.25)
        axis.text(x, .44, foot, ha="center", va="center", fontsize=6.5, color="#555555")
        if index < 4:
            axis.add_patch(FancyArrowPatch((x+.087, .59), (xs[index+1]-.087, .59), arrowstyle="-|>", mutation_scale=9, linewidth=1.0, color="#89929C"))
    axis.text(.5, .91, "Integrated evidence chain and strict claim boundary", ha="center", fontsize=11, fontweight="bold", color=COLORS["black"])
    axis.add_patch(FancyBboxPatch((.06, .12), .88, .15, boxstyle="round,pad=.012", facecolor="#F4F6F8", edgecolor="#C8D0D8", linewidth=.8))
    axis.text(.5, .215, "Supported scope", ha="center", fontweight="bold", fontsize=8, color=COLORS["green"])
    axis.text(.5, .16, "Controlled rank-2 SU(2) simulation; matched-probe stable-vs-nonstable separation; claim-matched descriptor recovery", ha="center", fontsize=7.1)
    axis.text(.5, .055, "Not established: complete four-regime taxonomy • fast-RIC causality • full connection • real ECoG • phenomenology", ha="center", fontsize=7.1, color=COLORS["red"])
    save_figure(fig, "Figure_1_Integrated_Study_Design")


def figure2_stage1_stage2(s1: dict, s2: dict) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.0))
    x = np.arange(3); width=.36
    common = [s1["estimands"]["common_frame_transport_effects"][k] for k in ("R","P","RP")]
    conj = [s1["estimands"]["gauge_invariant_conjugacy_effects"][k] for k in ("R","P","RP")]
    axes[0,0].bar(x-width/2, common, width, color=COLORS["blue"], label="Common frame")
    axes[0,0].bar(x+width/2, conj, width, color=COLORS["orange"], label="Conjugacy")
    axes[0,0].set_xticks(x, ["R","P","RP"]); axes[0,0].set_ylabel("Holonomy distance")
    axes[0,0].set_title("Stage 1 constructive effects"); axes[0,0].legend(frameon=False); clean_axis(axes[0,0]); panel(axes[0,0], "a")

    interactions=[s1["estimands"]["interaction_R_then_P"],s1["estimands"]["interaction_P_then_R"]]
    axes[0,1].bar([0,1],interactions,color=[COLORS["sky"],COLORS["purple"]])
    threshold=s1["scientific_criteria"]["epsilon_H"]
    axes[0,1].axhline(threshold,color=COLORS["red"],linestyle="--",label=f"criterion = {threshold:.3f}")
    axes[0,1].set_xticks([0,1],["R→P","P→R"]); axes[0,1].set_ylabel("Interaction residual"); axes[0,1].set_title("Stage 1 criterion is not met")
    axes[0,1].legend(frameon=False); clean_axis(axes[0,1]); panel(axes[0,1], "b")

    order=["common_R","common_P","common_RP","conjugacy_R","conjugacy_P","conjugacy_RP","interaction"]
    labels=["R","P","RP","R conj.","P conj.","RP conj.","Interaction"]
    estimates=s2["held_out_validation"]["estimates"]
    centers=[]; low=[]; high=[]
    for key in order:
        c,l,u=err(estimates[key]); centers.append(c); low.append(l); high.append(u)
    axes[1,0].errorbar(np.arange(len(order)),centers,yerr=np.asarray([low,high]),fmt="o",color=COLORS["blue"],ecolor=COLORS["blue"],capsize=2.5)
    axes[1,0].axhline(s2["held_out_validation"]["thresholds_frozen_from_pilot_null"]["interaction"],color=COLORS["red"],linestyle="--",linewidth=1)
    axes[1,0].set_xticks(np.arange(len(order)),labels,rotation=35,ha="right"); axes[1,0].set_ylabel("Mean effect (95% clone CI)"); axes[1,0].set_title("Stage 2 held-out effects")
    axes[1,0].text(.98,.05,"Dashed margin applies to the interaction estimand",transform=axes[1,0].transAxes,ha="right",va="bottom",fontsize=6.2,color=COLORS["red"])
    clean_axis(axes[1,0]); panel(axes[1,0], "c")

    independent=s2["independent_noise_null_corrected"]
    null=independent["paired_null_bias"]; corrected=independent["null_corrected_interaction"]
    values=[null["mean"],corrected["mean"]]
    yerr=np.asarray([[values[0]-null["lower"],values[1]-corrected["lower"]],[null["upper"]-values[0],corrected["upper"]-values[1]]])
    axes[1,1].errorbar([0,1],values,yerr=yerr,fmt="o",capsize=3,color=COLORS["green"])
    axes[1,1].axhline(0,color="#333333",linewidth=.8)
    axes[1,1].set_xticks([0,1],["Noise-null bias","Null-corrected\ninteraction"])
    axes[1,1].set_ylabel("Clone-mean interaction"); axes[1,1].set_title("Independent-noise robustness")
    axes[1,1].text(.03,.95,f"Observed = {independent['observed_clone_mean_interaction']:.4f}",transform=axes[1,1].transAxes,va="top",fontsize=7)
    clean_axis(axes[1,1]); panel(axes[1,1], "d")
    fig.tight_layout(w_pad=2.2,h_pad=2.0); save_figure(fig,"Figure_2_Constructive_and_Heldout_Latent_Evidence")


def figure3_stage3_dynamics(data: np.lib.npyio.NpzFile) -> None:
    main={key:data[key] for key in data.files}
    validation=main["validation_indices"]
    theta=main["theta"][validation]
    baseline=theta[:,:,:,0][:,:,:,None,:,:]
    theta_change=np.linalg.norm(theta-baseline,axis=(-2,-1))
    series=[(theta_change,"Connection change",np.arange(theta_change.shape[-1])),(main["kappa"][validation],"Closure margin κ",np.arange(main["kappa"].shape[-1])),(main["mismatch"][validation],"Mismatch",np.arange(main["mismatch"].shape[-1])),(main["coherence"][validation],"Directional coherence",np.arange(main["coherence"].shape[-1]))]
    fig,axes=plt.subplots(2,2,figsize=(7.2,5.8))
    for p,(values,title,times) in enumerate(series):
        axis=axes.ravel()[p]
        for regime in range(4):
            observed,lower,upper=cluster_time_ci(values[:,regime],seed=510+p*10+regime)
            axis.plot(times,observed,color=REGIME_COLORS[regime],label=REGIME_NAMES[regime])
            axis.fill_between(times,lower,upper,color=REGIME_COLORS[regime],alpha=.15,linewidth=0)
        axis.set_title(title); axis.set_xlabel("Episode"); clean_axis(axis); panel(axis,chr(ord('a')+p))
    axes[0,0].set_ylabel(r"$||\theta_n-\theta_0||_F$")
    axes[0,1].legend(frameon=False,ncol=2)
    fig.tight_layout(w_pad=2,h_pad=2); save_figure(fig,"Figure_3_Endogenous_Remodeling_Dynamics")


def figure4_stage3_inference(s3: dict) -> None:
    pairs=list(s3["pairwise_validation"])
    fig,axes=plt.subplots(2,2,figsize=(7.2,6.2))
    for column,(metric,threshold_key,title) in enumerate((("common_frame","common_frame","Common-frame distances"),("conjugacy","conjugacy","Conjugacy distances"))):
        axis=axes[0,column]; centers=[]; lower=[]; upper=[]; simultaneous=[]
        for key in pairs:
            estimate=s3["pairwise_validation"][key][metric]
            centers.append(estimate["mean"]); lower.append(estimate["mean"]-estimate["lower"]); upper.append(estimate["upper"]-estimate["mean"]); simultaneous.append(estimate["simultaneous_lower"])
        colors=[COLORS["green"]]*3+[COLORS["gray"]]*3
        for i in range(6):
            axis.errorbar(i,centers[i],yerr=np.asarray([[lower[i]],[upper[i]]]),fmt="o",color=colors[i],ecolor=colors[i],capsize=2.5)
            axis.plot(i,simultaneous[i],marker="v",markersize=4,color=colors[i])
        axis.axhline(s3["null_thresholds"][threshold_key],color=COLORS["red"],linestyle="--",label="stochastic-null threshold")
        axis.set_xticks(range(6),PAIR_SHORT); axis.set_ylabel("Distance"); axis.set_title(title)
        clean_axis(axis); panel(axis,chr(ord('a')+column))
        if column==1: axis.legend(frameon=False)
    ablations=list(s3["ablations"])
    display=["No remodeling","No retention","No protention","Constant fast gate","No slow κ"]
    for column,(metric,title) in enumerate((("paired_reduction_common","Paired reduction in common-frame separation"),("paired_reduction_conjugacy","Paired reduction in conjugacy separation"))):
        axis=axes[1,column]; centers=[]; lo=[]; hi=[]
        for name in ablations:
            c,l,u=err(s3["ablations"][name][metric]); centers.append(c); lo.append(l); hi.append(u)
        colors=[COLORS["green"] if l>0 else COLORS["red"] if u<0 else COLORS["gray"] for l,u in zip(np.asarray(centers)-np.asarray(lo),np.asarray(centers)+np.asarray(hi))]
        axis.bar(np.arange(5),centers,color=colors,alpha=.85)
        axis.errorbar(np.arange(5),centers,yerr=np.asarray([lo,hi]),fmt="none",ecolor="#222222",capsize=2.5,linewidth=.8)
        axis.axhline(0,color="#333333",linewidth=.8); axis.set_xticks(range(5),display,rotation=32,ha="right")
        axis.set_ylabel("Main − ablation"); axis.set_title(title); clean_axis(axis); panel(axis,chr(ord('c')+column))
    fig.tight_layout(w_pad=2,h_pad=2.2); save_figure(fig,"Figure_4_Stage3_Familywise_Inference_and_Ablations")


def figure5_stage4_recovery(s4: dict, data: np.lib.npyio.NpzFile) -> None:
    fig,axes=plt.subplots(2,2,figsize=(7.2,6.1))
    truth=data["truth_angles"].ravel(); estimate=data["calibrated_angle_mean"].ravel()
    axes[0,0].scatter(truth,estimate,s=18,color=COLORS["blue"],alpha=.75,edgecolors="none")
    low=min(truth.min(),estimate.min()); high=max(truth.max(),estimate.max()); axes[0,0].plot([low,high],[low,high],"--",color="#555555",linewidth=.8)
    m=s4["validation"]["angles"]; axes[0,0].text(.03,.97,f"ρ={m['spearman']['value']:.3f}\nMAE={m['mae']['value']:.4f}",transform=axes[0,0].transAxes,va="top")
    axes[0,0].set_xlabel("True reference-anchored change"); axes[0,0].set_ylabel("Recovered change"); axes[0,0].set_title("Scalar recovery"); clean_axis(axes[0,0]); panel(axes[0,0],"a")
    truthp=data["truth_pairwise"].ravel(); estimatep=data["estimated_pairwise_mean_calibrated"].ravel()
    axes[0,1].scatter(truthp,estimatep,s=18,color=COLORS["orange"],alpha=.75,edgecolors="none")
    low=min(truthp.min(),estimatep.min()); high=max(truthp.max(),estimatep.max()); axes[0,1].plot([low,high],[low,high],"--",color="#555555",linewidth=.8)
    m=s4["validation"]["pairwise_distance_ordering"]; axes[0,1].text(.03,.97,f"ρ={m['spearman']['value']:.3f}\nDistortion={m['relative_distortion']['value']:.3f}",transform=axes[0,1].transAxes,va="top")
    axes[0,1].set_xlabel("True pairwise distance"); axes[0,1].set_ylabel("Recovered distance"); axes[0,1].set_title("Within-clone metric recovery"); clean_axis(axes[0,1]); panel(axes[0,1],"b")
    axes[1,0].hist(data["absolute_angles"].ravel(),bins=22,density=True,alpha=.65,color=COLORS["blue"],label="Nontrivial paths")
    axes[1,0].hist(data["dynamic_null_absolute_angles"].ravel(),bins=22,density=True,alpha=.65,color=COLORS["gray"],label="Dynamic zero-holonomy")
    axes[1,0].set_xlabel("Recovered absolute angle"); axes[1,0].set_ylabel("Density"); axes[1,0].set_title("Path discrimination (AUC = 1.00)"); axes[1,0].legend(frameon=False); clean_axis(axes[1,0]); panel(axes[1,0],"c")
    metrics=[s4["validation"]["repeat_icc_within_setup_absolute"],s4["independent_session_generalization"]["icc_absolute_across_independent_setups"],s4["independent_session_generalization"]["scalar_spearman"],s4["independent_session_generalization"]["pairwise_spearman"]]
    labels=["Within setup\nICC","Across setups\nICC","Across setups\nscalar ρ","Across setups\npairwise ρ"]
    centers=[x["value"] for x in metrics]; lo=[x["value"]-x["lower"] for x in metrics]; hi=[x["upper"]-x["value"] for x in metrics]
    axes[1,1].errorbar(range(4),centers,yerr=np.asarray([lo,hi]),fmt="o",capsize=3,color=COLORS["green"])
    axes[1,1].axhline(.70,color=COLORS["red"],linestyle="--",linewidth=.8,label="primary ICC LCB criterion")
    axes[1,1].set_xticks(range(4),labels,fontsize=6.5); axes[1,1].set_ylim(.55,1.02); axes[1,1].set_ylabel("Estimate (95% clone CI)"); axes[1,1].set_title("Repeatability and session generalization"); axes[1,1].legend(frameon=False); clean_axis(axes[1,1]); panel(axes[1,1],"d")
    fig.tight_layout(w_pad=2,h_pad=2); save_figure(fig,"Figure_5_CrossFitted_Observation_Model_Recovery")


def figure6_stage4_stress(s4: dict) -> None:
    families=[("noise","Noise ratio"),("channels","Retained channel fraction"),("carrier_misspecification","Carrier offset (Hz)"),("mixing_drift","Mixing drift amplitude")]
    fig,axes=plt.subplots(2,2,figsize=(7.2,5.8))
    for index,(family,xlabel) in enumerate(families):
        axis=axes.ravel()[index]
        items=sorted((float(k),v) for k,v in s4["stress_tests"][family].items())
        x=np.asarray([v[0] for v in items])
        for metric,color,marker,label in (("angle_spearman",COLORS["blue"],"o","Scalar ρ"),("pairwise_spearman",COLORS["orange"],"s","Pairwise ρ")):
            center=np.asarray([v[1][metric]["value"] for v in items]); lower=np.asarray([v[1][metric]["lower"] for v in items]); upper=np.asarray([v[1][metric]["upper"] for v in items])
            axis.plot(x,center,marker=marker,color=color,label=label); axis.fill_between(x,lower,upper,color=color,alpha=.15)
        axis.set_xlabel(xlabel); axis.set_ylabel("Spearman correlation"); axis.set_ylim(-.45,1.05); clean_axis(axis); panel(axis,chr(ord('a')+index))
        if index==0: axis.legend(frameon=False)
    fig.tight_layout(w_pad=2,h_pad=2); save_figure(fig,"Figure_6_Observation_Model_Stress_Tests")


def figure7_stage5_boundaries(s5: dict) -> None:
    families=[("channel_projection","Channel projection (loss)"),("temporal_coarse_graining","Temporal coarse-graining (loss)"),("phase_scrambling","Phase scrambling (loss)"),("trial_timing_jitter","Circular timing shift (nuisance)")]
    fig,axes=plt.subplots(2,2,figsize=(7.2,5.9))
    for index,(family,title) in enumerate(families):
        axis=axes.ravel()[index]
        items=sorted((item for item in s5["scenarios"] if item["transformation"]==family),key=lambda x:x["degradation_index"])
        x=np.asarray([item["degradation_index"] for item in items]); labels=[f"{item['value']:g}" for item in items]
        for metric,color,marker,label in (("scalar_spearman",COLORS["blue"],"o","Scalar ρ"),("pairwise_spearman",COLORS["orange"],"s","Pairwise ρ"),("path_auc",COLORS["green"],"^","Path AUC")):
            center=np.asarray([item["metrics"][metric]["value"] for item in items]); lower=np.asarray([item["metrics"][metric]["lower"] for item in items]); upper=np.asarray([item["metrics"][metric]["upper"] for item in items])
            axis.plot(x,center,marker=marker,color=color,label=label); axis.fill_between(x,lower,upper,color=color,alpha=.12)
        axis.axhline(.72,color="#7A7A7A",linestyle="--",linewidth=.7,label="ρ cutoff" if index==0 else None)
        axis.axhline(.85,color="#7A7A7A",linestyle=":",linewidth=.7,label="AUC cutoff" if index==0 else None)
        axis.set_xticks(x,labels); axis.set_xlabel("Transformation value"); axis.set_ylabel("Performance"); axis.set_ylim(-.2,1.05); axis.set_title(title); clean_axis(axis); panel(axis,chr(ord('a')+index))
        if index==0: axis.legend(frameon=False,ncol=2)
    fig.tight_layout(w_pad=2,h_pad=2); save_figure(fig,"Figure_7_Transformation_Specific_Claim_Boundaries")


def figure8_claim_matrix(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict) -> None:
    claims=["Constructive shared-frame effect","Noise-robust shared-frame interaction","Stable vs non-stable remodeling separation","Controlled scalar/metric recovery","Transformation-specific loss boundaries","Complete four-regime taxonomy","Fast-RIC causality","Real-ECoG validity","Phenomenology / unique experience"]
    # 1 supported, .5 limited, 0 not supported, nan outside stage scope.
    values=np.asarray([
        [1,np.nan,np.nan,np.nan,np.nan],
        [np.nan,1,np.nan,np.nan,np.nan],
        [np.nan,np.nan,1,np.nan,np.nan],
        [np.nan,np.nan,np.nan,1,np.nan],
        [np.nan,np.nan,np.nan,np.nan,1 if s5["criteria"]["information_loss_boundary_pass"] else .5 if s5["information_loss_diagnostics"]["successful_families"]>0 else 0],
        [np.nan,np.nan,0,np.nan,np.nan],
        [np.nan,0,0,np.nan,np.nan],
        [0,0,0,0,0],
        [0,0,0,0,0],
    ],dtype=float)
    cmap=ListedColormap(["#D73027","#FEE08B","#1A9850"]); cmap.set_bad("#ECEFF1")
    fig,axis=plt.subplots(figsize=(7.2,4.5)); image=axis.imshow(values,aspect="auto",vmin=0,vmax=1,cmap=cmap)
    axis.set_xticks(range(5),["Stage 1","Stage 2","Stage 3","Stage 4","Stage 5"]); axis.set_yticks(range(len(claims)),claims)
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value=values[row,col]; label="—" if np.isnan(value) else "SUPPORTED" if value==1 else "LIMITED" if value==.5 else "NO"
            axis.text(col,row,label,ha="center",va="center",fontsize=6.3,color="white" if value in (0,1) else "#333333",fontweight="bold" if not np.isnan(value) else "normal")
    axis.set_title("Evidence and claim boundary across the integrated analysis",pad=10)
    axis.tick_params(length=0); fig.tight_layout(); save_figure(fig,"Figure_8_Integrated_Claim_Matrix")


def supplementary_figures(s1: dict, s3: dict, s4: dict, s5: dict) -> None:
    # Candidate selection.
    rows=load_json(RESULTS/"stage4_final"/"summary.json")
    candidate_csv=RESULTS/"stage4_final"/"development_candidate_table.csv"
    if candidate_csv.exists():
        with candidate_csv.open(encoding="utf-8") as handle: candidates=list(csv.DictReader(handle))
        fig,axis=plt.subplots(figsize=(7.2,3.7)); x=np.arange(len(candidates)); angle=np.asarray([float(r["angle_spearman"]) for r in candidates]); pair=np.asarray([float(r["pairwise_spearman"]) for r in candidates]); selected=[f"bins{r['n_bins']}_ridge{float(r['ridge']):g}_{r['projection']}"==f"bins{s4['selected_candidate']['n_bins']}_ridge{s4['selected_candidate']['ridge']:g}_{s4['selected_candidate']['projection']}" for r in candidates]
        axis.scatter(x,angle,color=COLORS["blue"],label="Scalar ρ"); axis.scatter(x,pair,color=COLORS["orange"],marker="s",label="Pairwise ρ")
        for i,flag in enumerate(selected):
            if flag: axis.axvspan(i-.4,i+.4,color=COLORS["green"],alpha=.15,label="Selected" if i==0 or not any(selected[:i]) else None)
        axis.set_xticks(x,[r["label"].replace("_","\n") for r in candidates],rotation=55,ha="right",fontsize=5.8); axis.set_ylabel("Development performance"); axis.set_ylim(0,1.03); axis.legend(frameon=False,ncol=3); clean_axis(axis); fig.tight_layout(); save_figure(fig,"Supplementary_Figure_1_Stage4_Candidate_Selection")

    # Numerical QC across stages.
    qcs=[
        ("Stage 1 transport unitarity",s1["numerical_qc"]["max_transport_unitarity_error"]),
        ("Stage 1 gauge covariance",s1["numerical_qc"]["max_gauge_covariance_error"]),
        ("Stage 3 transport unitarity",s3["numerical_qc"]["max_unitarity_error"]),
        ("Stage 3 gauge covariance",s3["numerical_qc"]["gauge_covariance_error"]),
        ("Stage 4 recovery unitarity",s4["numerical_and_lineage_qc"]["max_recovery_unitarity_error"]),
        ("Stage 4 gauge signal",s4["numerical_and_lineage_qc"]["gauge_equivalent_signal_error"]),
        ("Stage 5 recovery unitarity",s5["numerical_qc"]["max_unitarity_error"]),
    ]
    fig,axis=plt.subplots(figsize=(7.2,3.8)); axis.barh(np.arange(len(qcs)),[max(v,1e-18) for _,v in qcs],color=COLORS["blue"]); axis.set_yticks(np.arange(len(qcs)),[k for k,_ in qcs]); axis.set_xscale("log"); axis.set_xlabel("Maximum absolute/Frobenius error (log scale)"); axis.invert_yaxis(); clean_axis(axis); fig.tight_layout(); save_figure(fig,"Supplementary_Figure_2_Numerical_QC")

    # Invertibility versus frozen-estimator dependence.
    items=[item for item in s5["scenarios"] if item["family"] in {"equivalence","known_invertible"}]
    fig,axis=plt.subplots(figsize=(7.2,3.8)); x=np.arange(len(items)); fixed=[item["metrics"]["scalar_spearman"]["value"] for item in items]; baseline=s5["baseline"]["metrics"]["scalar_spearman"]["value"]
    axis.bar(x,fixed,color=COLORS["orange"],label="Frozen estimator"); axis.scatter(x,[baseline]*len(x),marker="D",color=COLORS["green"],label="After exact inverse (spot-check baseline)")
    axis.set_xticks(x,[item["label"] for item in items],rotation=35,ha="right"); axis.set_ylim(-.1,1.05); axis.set_ylabel("Scalar Spearman"); axis.set_title("Invertibility is distinct from frozen-estimator robustness"); axis.legend(frameon=False); clean_axis(axis); fig.tight_layout(); save_figure(fig,"Supplementary_Figure_3_Invertible_Transform_Controls")

    seed_path=QC/"stage3_seed_robustness.csv"
    if seed_path.exists():
        with seed_path.open(encoding="utf-8") as handle: rows=list(csv.DictReader(handle))
        fig,axis=plt.subplots(figsize=(7.2,3.5)); x=np.arange(len(rows)); lcb=np.asarray([float(r["minimum_stable_common_simultaneous_lcb"]) for r in rows]); threshold=np.asarray([float(r["common_threshold"]) for r in rows]); axis.plot(x,lcb,"o-",color=COLORS["blue"],label="Minimum stable-vs-nonstable LCB"); axis.plot(x,threshold,"s--",color=COLORS["red"],label="Stochastic-null threshold"); axis.set_xticks(x,[r["root_seed"] for r in rows],rotation=30); axis.set_xlabel("Independent root seed"); axis.set_ylabel("Common-frame distance"); axis.legend(frameon=False); clean_axis(axis); fig.tight_layout(); save_figure(fig,"Supplementary_Figure_4_Stage3_Seed_Robustness")


def build_tables(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str,list[dict[str,Any]]]={}
    tables["Study_Design"]=[
        {"Stage":"1","Role":"Constructive example","Independent unit":"Deterministic","Split / repeats":"None","Primary status":"Criterion failed; constructive only"},
        {"Stage":"2","Role":"Held-out latent validation","Independent unit":"Clone","Split / repeats":"8 pilot; 20 validation; 4 repeats","Primary status":"Shared-frame interaction robust to independent noise"},
        {"Stage":"3","Role":"Endogenous remodeling","Independent unit":"Clone","Split / repeats":"8 pilot; 32 validation; 4 repeats","Primary status":"Stable vs non-stable supported; global taxonomy failed"},
        {"Stage":"4","Role":"Observation-model recovery","Independent unit":"Clone","Split / repeats":"6 dev; 6 cal; 16 val; 3 repeats","Primary status":"All claim-matched criteria passed"},
        {"Stage":"5","Role":"Sensitivity / boundaries","Independent unit":"Clone","Split / repeats":"Stage 4 val reused; repeat 0; 10/20 transform draws","Primary status":"Limited: exact repeat reproduction; single-repeat scalar LCB and 1/3 strict loss families fail"},
    ]
    tables["Stage2_Effects"]=[]
    for name,estimate in s2["held_out_validation"]["estimates"].items():
        tables["Stage2_Effects"].append({"Estimand":name,"Mean":estimate["mean"],"CI lower":estimate["lower"],"CI upper":estimate["upper"],"Unit":"clone-clustered"})
    tables["Stage3_Pairwise"]=[]
    for index,(key,item) in enumerate(s3["pairwise_validation"].items()):
        tables["Stage3_Pairwise"].append({"Pair":PAIR_SHORT[index],"Full label":key,"Common mean":item["common_frame"]["mean"],"Common CI lower":item["common_frame"]["lower"],"Common CI upper":item["common_frame"]["upper"],"Common simultaneous LCB":item["common_frame"]["simultaneous_lower"],"Conjugacy mean":item["conjugacy"]["mean"],"Conjugacy CI lower":item["conjugacy"]["lower"],"Conjugacy CI upper":item["conjugacy"]["upper"],"Conjugacy simultaneous LCB":item["conjugacy"]["simultaneous_lower"],"Claim family":"Primary" if index<3 else "Global-taxonomy secondary"})
    tables["Stage3_Ablations"]=[]
    for name,item in s3["ablations"].items():
        tables["Stage3_Ablations"].append({"Ablation":name,"Ablation common mean":item["ablation_common_mean"],"Paired common reduction":item["paired_reduction_common"]["mean"],"Common CI lower":item["paired_reduction_common"]["lower"],"Common CI upper":item["paired_reduction_common"]["upper"],"Paired conjugacy reduction":item["paired_reduction_conjugacy"]["mean"],"Conjugacy CI lower":item["paired_reduction_conjugacy"]["lower"],"Conjugacy CI upper":item["paired_reduction_conjugacy"]["upper"]})
    v=s4["validation"]
    tables["Stage4_Validation"]=[
        {"Estimand":"Scalar Spearman","Estimate":v["angles"]["spearman"]["value"],"CI lower":v["angles"]["spearman"]["lower"],"CI upper":v["angles"]["spearman"]["upper"],"Criterion":"LCB > 0.72","Pass":s4["criteria"]["angle_claim_pass"]},
        {"Estimand":"Scalar MAE","Estimate":v["angles"]["mae"]["value"],"CI lower":v["angles"]["mae"]["lower"],"CI upper":v["angles"]["mae"]["upper"],"Criterion":"UCB < 0.045","Pass":s4["criteria"]["angle_claim_pass"]},
        {"Estimand":"Pairwise Spearman","Estimate":v["pairwise_distance_ordering"]["spearman"]["value"],"CI lower":v["pairwise_distance_ordering"]["spearman"]["lower"],"CI upper":v["pairwise_distance_ordering"]["spearman"]["upper"],"Criterion":"LCB > 0.72","Pass":s4["criteria"]["pairwise_ordering_claim_pass"]},
        {"Estimand":"Pairwise distortion","Estimate":v["pairwise_distance_ordering"]["relative_distortion"]["value"],"CI lower":v["pairwise_distance_ordering"]["relative_distortion"]["lower"],"CI upper":v["pairwise_distance_ordering"]["relative_distortion"]["upper"],"Criterion":"UCB < 0.65","Pass":s4["criteria"]["pairwise_ordering_claim_pass"]},
        {"Estimand":"Within-setup ICC","Estimate":v["repeat_icc_within_setup_absolute"]["value"],"CI lower":v["repeat_icc_within_setup_absolute"]["lower"],"CI upper":v["repeat_icc_within_setup_absolute"]["upper"],"Criterion":"LCB > 0.70","Pass":s4["criteria"]["repeat_reliability_pass"]},
        {"Estimand":"Dynamic-null AUC","Estimate":v["dynamic_zero_holonomy_auc"]["value"],"CI lower":v["dynamic_zero_holonomy_auc"]["lower"],"CI upper":v["dynamic_zero_holonomy_auc"]["upper"],"Criterion":"LCB > 0.85","Pass":s4["criteria"]["dynamic_null_discrimination_pass"]},
    ]
    tables["Stage4_Stress"]=[]
    for family,items in s4["stress_tests"].items():
        for value,metrics in items.items():
            tables["Stage4_Stress"].append({"Family":family,"Value":float(value),"Scalar Spearman":metrics["angle_spearman"]["value"],"Scalar lower":metrics["angle_spearman"]["lower"],"Scalar upper":metrics["angle_spearman"]["upper"],"Pairwise Spearman":metrics["pairwise_spearman"]["value"],"Pairwise lower":metrics["pairwise_spearman"]["lower"],"Pairwise upper":metrics["pairwise_spearman"]["upper"],"Scalar MAE":metrics["angle_mae"]["value"],"Pairwise distortion":metrics["pairwise_relative_distortion"]["value"]})
    tables["Stage5_Scenarios"]=[]
    for item in s5["scenarios"]:
        tables["Stage5_Scenarios"].append({"Family":item["family"],"Transformation":item["transformation"],"Label":item["label"],"Degradation index":item["degradation_index"],"Value":item["value"],"Scalar Spearman":item["metrics"]["scalar_spearman"]["value"],"Scalar lower":item["metrics"]["scalar_spearman"]["lower"],"Scalar upper":item["metrics"]["scalar_spearman"]["upper"],"Scalar MAE":item["metrics"]["scalar_mae"]["value"],"Ordinal accuracy":item["metrics"]["ordinal_accuracy"]["value"],"Pairwise Spearman":item["metrics"]["pairwise_spearman"]["value"],"Pairwise distortion":item["metrics"]["pairwise_relative_distortion"]["value"],"Path AUC":item["metrics"]["path_auc"]["value"],"Scalar pass":item["claims"]["scalar_value"],"Ordinal pass":item["claims"]["ordinal_structure"],"Metric pass":item["claims"]["metric_geometry"],"Path pass":item["claims"]["nontrivial_path_dependence"]})
    tables["Stage5_Boundaries"]=s5["failure_boundaries"]
    for name,rows in tables.items():
        write_csv(TABLES/f"{name}.csv",rows)
        write_latex(TABLES/f"{name}.tex",rows,name.replace("_"," "),f"tab:{name.lower()}")
    return tables


def manuscript_text(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict) -> None:
    s2v=s2["held_out_validation"]["estimates"]; independent=s2["independent_noise_null_corrected"]
    s4v=s4["validation"]; sess=s4["independent_session_generalization"]
    stable_keys=list(s3["pairwise_validation"])[:3]
    stable_common=[s3["pairwise_validation"][k]["common_frame"]["mean"] for k in stable_keys]
    stable_conj=[s3["pairwise_validation"][k]["conjugacy"]["mean"] for k in stable_keys]
    methods=f"""# Manuscript-ready Methods and Results

## Methods

### Integrated analysis design

We evaluated the Individual Neural Holonomy (INH) construction in five linked computational stages. Stage 1 was a deterministic constructive example. Stage 2 used non-overlapping pilot and held-out clone cohorts to evaluate shared-frame retention/protention transport effects. Stage 3 introduced endogenous history-dependent remodeling and treated stable-versus-non-stable contrasts as the claim-aligned primary family; complete separation of all four modeled regimes was evaluated as a stricter secondary taxonomy criterion. Stage 4 tested whether claim-matched holonomy descriptors could be recovered from controlled synthetic multichannel observations using disjoint development, calibration, and validation clones. Stage 5 mapped transformation-specific equivalences, estimator dependence, temporal nuisance, and information-loss boundaries on the Stage 4 validation cohort; it was therefore treated as a sensitivity analysis rather than an independent replication.

### Statistical units, splits, and uncertainty

The clone was the independent unit of inference. Branches, regimes, repeated traversals, observation repeats, and transformation draws were nested within clone. Stage 2 used 8 pilot clones and 20 held-out validation clones with four validation repeats. Stage 3 used 8 pilot clones only for calibration of the neutral RIC reference and 32 held-out validation clones with four repeats. Stage 4 used 6 development, 6 calibration, and 16 validation clones, with three observation repeats and disjoint frame-estimation and holonomy-estimation trial subsets. Confidence intervals were obtained by resampling whole clones. Stage 3 used one-sided familywise simultaneous lower bounds across the reported pair families. Stage 4 nested calibration- and validation-clone resampling. Stage 5 resampled clones and transformation draws hierarchically. Unless explicitly identified as a simultaneous lower bound, intervals are two-sided 95% bootstrap intervals.

### Randomization and null models

All stochastic streams were derived from fixed SeedSequence keys. Intervention labels were excluded from Stage 3 seeds, ensuring that the main model and each ablation reused identical clone, regime, repeat, episode, and exogenous-noise streams. Stage 2 primary comparisons used common random numbers (CRN); an additional independent-noise analysis subtracted a paired histories-disabled null within clone. Stage 3 thresholds were the larger of the pilot no-remodeling numerical-floor 95th percentile and the held-out same-history independent-repeat 95th percentile, plus a fixed practical margin of {s3['null_thresholds']['practical_margin']:.3f}. Stage 4 used a dynamic zero-holonomy path that preserved nontrivial local dynamics while returning to the identity. All numerical integration, SU(2), gauge-covariance, determinant, and unitarity checks were evaluated against prespecified tolerances.

### Controlled observation model and recovery

Stage 4 generated rank-two complex-fiber signals mixed into 24 real-valued channels across 20 trials and 161 samples. Eight trials were used only to estimate the shared complex frame and the remaining 12 only for holonomy estimation. Candidate recovery pipelines varied temporal binning, ridge regularization, and SU(2) projection and were selected using development clones only. Positive-slope affine calibrations for scalar angle changes and within-clone pairwise distances were fit on calibration clones only and frozen for validation. Primary repeatability held the clone-specific mixing/fiber setup fixed while varying measurement noise; a secondary independent-session analysis varied mixing, initial fibers, nuisance frequencies, and nuisance phases across repeats.

### Transformation taxonomy

Stage 5 separated exact equivalences (channel permutation and orthogonal mixing), known-invertible transforms, information-destroying transforms (channel projection, temporal coarse-graining, and phase scrambling), circular trial shifts as temporal-alignment nuisance, time-model misspecification, and estimator-only perturbations. It used one prespecified observation repeat from the reused Stage 4 validation cohort and verified exact equality with the corresponding frozen Stage 4 arrays; this single-repeat sensitivity estimand was kept distinct from the Stage 4 primary estimator, which averages three repeats. Exact equivalences used {s5['design']['equivalence_draws']} draws and random transformations used {s5['design']['random_transformation_draws']} draws per clone and severity. An information-loss family passed only when it exhibited a claim boundary together with a bootstrap-supported ordering decline and error increase from weak to strong degradation. All three genuine information-loss families were required.

## Results

### Stage 1 establishes only a constructive shared-frame example

Stage 1 produced common-frame distances of {s1['estimands']['common_frame_transport_effects']['R']:.4f}, {s1['estimands']['common_frame_transport_effects']['P']:.4f}, and {s1['estimands']['common_frame_transport_effects']['RP']:.4f} for R, P, and RP, respectively. The corresponding conjugacy distances were {s1['estimands']['gauge_invariant_conjugacy_effects']['R']:.4f}, {s1['estimands']['gauge_invariant_conjugacy_effects']['P']:.4f}, and {s1['estimands']['gauge_invariant_conjugacy_effects']['RP']:.4f}. Both interaction residuals ({s1['estimands']['interaction_R_then_P']:.4f} and {s1['estimands']['interaction_P_then_R']:.4f}) were below the prespecified {s1['scientific_criteria']['epsilon_H']:.3f} threshold. Stage 1 therefore supports a constructive shared-frame proof of principle but not suprathreshold retention-by-protention interaction or emergent individuation.

### Stage 2 validates a shared-frame interaction and independent-noise robustness

On 20 held-out clones, common-frame R, P, and RP effects were {s2v['common_R']['mean']:.4f} (95% CI {s2v['common_R']['lower']:.4f}–{s2v['common_R']['upper']:.4f}), {s2v['common_P']['mean']:.4f} ({s2v['common_P']['lower']:.4f}–{s2v['common_P']['upper']:.4f}), and {s2v['common_RP']['mean']:.4f} ({s2v['common_RP']['lower']:.4f}–{s2v['common_RP']['upper']:.4f}). The interaction residual was {s2v['interaction']['mean']:.4f} ({s2v['interaction']['lower']:.4f}–{s2v['interaction']['upper']:.4f}). Under independent noise, the paired null bias was {independent['paired_null_bias']['mean']:.4f} ({independent['paired_null_bias']['lower']:.4f}–{independent['paired_null_bias']['upper']:.4f}); after subtraction, the interaction remained positive at {independent['null_corrected_interaction']['mean']:.4f} ({independent['null_corrected_interaction']['lower']:.4f}–{independent['null_corrected_interaction']['upper']:.4f}). Fast-RIC modulation was not supported because its paired interval included zero.

### Stage 3 supports stable-versus-non-stable separation, not a complete taxonomy

The three stable-versus-non-stable common-frame distances ranged from {min(stable_common):.4f} to {max(stable_common):.4f}; their familywise simultaneous lower bounds all exceeded the stochastic-null threshold of {s3['null_thresholds']['common_frame']:.4f}. Conjugacy distances ranged from {min(stable_conj):.4f} to {max(stable_conj):.4f}, and the three primary simultaneous lower bounds exceeded the conjugacy threshold of {s3['null_thresholds']['conjugacy']:.4f}. In contrast, the all-pairs common-frame and all-pairs conjugacy criteria failed, showing that the three non-stable regimes were not all separable beyond repeat variability. The global four-regime taxonomy claim was therefore rejected.

Paired ablations showed robust contributions of retention (common-frame reduction {s3['ablations']['no_retention']['paired_reduction_common']['mean']:.4f}, 95% CI {s3['ablations']['no_retention']['paired_reduction_common']['lower']:.4f}–{s3['ablations']['no_retention']['paired_reduction_common']['upper']:.4f}), protentional relevance ({s3['ablations']['no_protention']['paired_reduction_common']['mean']:.4f}, {s3['ablations']['no_protention']['paired_reduction_common']['lower']:.4f}–{s3['ablations']['no_protention']['paired_reduction_common']['upper']:.4f}), and slow κ-dependent remodeling ({s3['ablations']['no_slow_kappa']['paired_reduction_common']['mean']:.4f}, {s3['ablations']['no_slow_kappa']['paired_reduction_common']['lower']:.4f}–{s3['ablations']['no_slow_kappa']['paired_reduction_common']['upper']:.4f}). Replacing the fast gate by a constant increased rather than reduced common-frame separation, so fast-RIC causality was not supported.

### Stage 4 recovers claim-matched descriptors in the controlled inverse problem

The development-only procedure selected `{s4['selected_candidate']['n_bins']}` temporal bins, ridge {s4['selected_candidate']['ridge']:g}, and `{s4['selected_candidate']['projection']}` projection. On validation clones, scalar recovery achieved Spearman ρ={s4v['angles']['spearman']['value']:.3f} (95% CI {s4v['angles']['spearman']['lower']:.3f}–{s4v['angles']['spearman']['upper']:.3f}) and MAE={s4v['angles']['mae']['value']:.4f} ({s4v['angles']['mae']['lower']:.4f}–{s4v['angles']['mae']['upper']:.4f}). Pairwise-distance recovery achieved ρ={s4v['pairwise_distance_ordering']['spearman']['value']:.3f} ({s4v['pairwise_distance_ordering']['spearman']['lower']:.3f}–{s4v['pairwise_distance_ordering']['spearman']['upper']:.3f}) and relative distortion={s4v['pairwise_distance_ordering']['relative_distortion']['value']:.3f} ({s4v['pairwise_distance_ordering']['relative_distortion']['lower']:.3f}–{s4v['pairwise_distance_ordering']['relative_distortion']['upper']:.3f}). Clone-clustered within-setup ICC was {s4v['repeat_icc_within_setup_absolute']['value']:.3f} ({s4v['repeat_icc_within_setup_absolute']['lower']:.3f}–{s4v['repeat_icc_within_setup_absolute']['upper']:.3f}), and dynamic zero-holonomy discrimination was AUC={s4v['dynamic_zero_holonomy_auc']['value']:.3f}. Independent-session recovery remained strong (scalar ρ={sess['scalar_spearman']['value']:.3f}, pairwise ρ={sess['pairwise_spearman']['value']:.3f}, ICC={sess['icc_absolute_across_independent_setups']['value']:.3f}). Stress tests identified pronounced failure under 4-Hz carrier misspecification, demonstrating estimator/model dependence rather than unrestricted identifiability.

### Stage 5 maps claim-specific robustness and failure boundaries

The selected single-repeat baseline exactly reproduced the corresponding frozen Stage 4 arrays (maximum absolute delta {s5['design']['baseline_exact_reproduction_max_delta']:.1e}), but its scalar Spearman confidence bound did not satisfy the Stage 4 cutoff: ρ={s5['baseline']['metrics']['scalar_spearman']['value']:.3f} (95% CI {s5['baseline']['metrics']['scalar_spearman']['lower']:.3f}–{s5['baseline']['metrics']['scalar_spearman']['upper']:.3f}). Scalar MAE was {s5['baseline']['metrics']['scalar_mae']['value']:.4f}, pairwise Spearman was {s5['baseline']['metrics']['pairwise_spearman']['value']:.3f}, and path AUC was {s5['baseline']['metrics']['path_auc']['value']:.3f}. Exact equivalence transforms preserved recovery within the prespecified delta bounds, while known-invertible transforms were distinguished from frozen-estimator robustness by exact inverse controls. {s5['information_loss_diagnostics']['successful_families']} of {s5['information_loss_diagnostics']['required_families']} genuine information-loss families met the strict ordering-drop, error-rise, and boundary criteria: temporal coarse-graining and phase scrambling passed, whereas channel projection did not show a bootstrap-supported ordering decline from weak to strong projection. Stage 5 therefore remained a limited sensitivity analysis rather than a positive confirmatory stage. Circular timing shifts were reported separately as temporal-alignment nuisance and were not counted as information destruction.

## Integrated conclusion and limitations

Together, the results support a controlled-model statement: pilot-calibrated history-dependent remodeling separates the modeled stable regime from non-stable alternatives under matched probes, and selected conjugacy-invariant scalar and within-clone metric descriptors are recoverable under a declared synthetic observation model. They do not support a complete four-regime taxonomy, fast-RIC causality, recovery of the full connection, unrestricted cross-subject gauge identification, real-ECoG validity, or any claim about phenomenology or unique experience.
"""
    (MANUSCRIPT/"Manuscript_Ready_Methods_and_Results.md").write_text(methods,encoding="utf-8")
    abstract=f"""# Proposed structured abstract

**Background.** Individual Neural Holonomy (INH) proposes that retention- and protention-dependent neural histories alter representational transport even when present-state trajectories are matched. The computational status and identifiable claim boundary of this proposal were evaluated.

**Methods.** Five linked stages tested a deterministic construction, pilot/held-out latent effects, endogenous slow remodeling, cross-fitted descriptor recovery from controlled synthetic multichannel observations, and transformation-specific failure boundaries. The clone was the independent unit. Calibration and selection were confined to pilot, development, or calibration cohorts; confidence intervals resampled whole clones. Ablations shared identical exogenous streams. Stage 5 used hierarchical clone-and-transformation bootstrap inference.

**Results.** Stage 1 produced a constructive shared-frame effect but failed its suprathreshold interaction criterion. In Stage 2, the held-out interaction was {s2v['interaction']['mean']:.4f} (95% CI {s2v['interaction']['lower']:.4f}–{s2v['interaction']['upper']:.4f}) and remained positive after paired independent-noise null subtraction ({independent['null_corrected_interaction']['mean']:.4f}, {independent['null_corrected_interaction']['lower']:.4f}–{independent['null_corrected_interaction']['upper']:.4f}). Stage 3 supported familywise stable-versus-non-stable separation in common-frame and conjugacy distance across 32 validation clones, but complete four-regime separation failed. Retention, protentional relevance, and slow κ-dependent remodeling had positive paired contributions; fast-RIC causality was unsupported. Stage 4 recovered reference-anchored scalar change (Spearman ρ={s4v['angles']['spearman']['value']:.3f}, {s4v['angles']['spearman']['lower']:.3f}–{s4v['angles']['spearman']['upper']:.3f}) and within-clone pairwise geometry (ρ={s4v['pairwise_distance_ordering']['spearman']['value']:.3f}, {s4v['pairwise_distance_ordering']['spearman']['lower']:.3f}–{s4v['pairwise_distance_ordering']['spearman']['upper']:.3f}) under the declared synthetic observation model. Stage 5 exactly reproduced the selected frozen Stage 4 repeat but its single-repeat scalar lower bound failed the Stage 4 cutoff; {s5['information_loss_diagnostics']['successful_families']}/{s5['information_loss_diagnostics']['required_families']} strict information-loss families passed, so Stage 5 was interpreted as limited sensitivity evidence.

**Conclusions.** The analysis supports stable-versus-non-stable matched-probe differentiation and claim-matched descriptor recovery in a controlled rank-two SU(2) simulation. It does not establish a complete regime taxonomy, fast-RIC causality, full-connection recovery, real-ECoG validity, or phenomenological individuation.
"""
    (MANUSCRIPT/"Proposed_Abstract.md").write_text(abstract,encoding="utf-8")
    captions="""# Figure captions

**Figure 1 | Integrated study design and claim boundary.** Five linked computational stages move from a deterministic constructive example to held-out latent validation, endogenous remodeling, controlled observation-model recovery, and transformation-specific sensitivity analysis. The green scope box states the strongest supported claim; the red line lists claims not established by the analysis.

**Figure 2 | Constructive and held-out latent evidence.** (a) Stage 1 common-frame and conjugacy distances. (b) Both Stage 1 interaction residuals remain below the prespecified criterion. (c) Stage 2 held-out clone-clustered estimates and 95% CIs; dashed line marks the practical double-null threshold. (d) Independent-noise paired-null bias and null-corrected interaction.

**Figure 3 | Endogenous Stage 3 remodeling dynamics.** Clone-clustered means and 95% bootstrap bands for connection change, standardized closure margin, mismatch, and directional coherence across episodes and regimes.

**Figure 4 | Stage 3 familywise inference and paired ablations.** (a,b) Held-out pairwise common-frame and conjugacy distances with pointwise 95% CIs; triangles denote simultaneous lower bounds and dashed lines the matched stochastic-null thresholds. Green points are stable-versus-non-stable claim-aligned contrasts; gray points are global-taxonomy secondary contrasts. (c,d) Paired clone-bootstrap reductions from the main model after each intervention. Positive intervals support a contribution; the constant fast gate does not support fast-RIC causality in common-frame separation.

**Figure 5 | Cross-fitted recovery from controlled synthetic multichannel observations.** (a) Reference-anchored scalar change. (b) Within-clone pairwise geometry. (c) Nontrivial paths versus dynamic zero-holonomy null. (d) Within-setup repeatability and independent-session generalization. Intervals resample whole clones.

**Figure 6 | Observation-model stress tests.** Scalar and pairwise ordering across noise, retained channels, carrier misspecification, and mixing drift, using all validation clones and all observation repeats. Bands are 95% clone-bootstrap intervals.

**Figure 7 | Transformation-specific claim boundaries.** Scalar ordering, pairwise ordering, and path AUC under three genuine information-loss families and circular timing shift. Circular shifts are temporal-alignment nuisance, not information loss.

**Figure 8 | Integrated evidence and claim matrix.** Green cells indicate supported scope, red cells indicate explicitly unsupported claims, and gray cells are outside a stage's inferential scope.
"""
    (MANUSCRIPT/"Figure_Captions.md").write_text(captions,encoding="utf-8")
    # Simple LaTeX-ready prose (Markdown headings removed; emphasis normalized).
    latex=methods.replace("# Manuscript-ready Methods and Results\n\n","").replace("## Methods","\\section{Methods}").replace("## Results","\\section{Results}").replace("## Integrated conclusion and limitations","\\section{Integrated conclusion and limitations}")
    for heading in ("Integrated analysis design","Statistical units, splits, and uncertainty","Randomization and null models","Controlled observation model and recovery","Transformation taxonomy","Stage 1 establishes only a constructive shared-frame example","Stage 2 validates a shared-frame interaction and independent-noise robustness","Stage 3 supports stable-versus-non-stable separation, not a complete taxonomy","Stage 4 recovers claim-matched descriptors in the controlled inverse problem","Stage 5 maps claim-specific robustness and failure boundaries"):
        latex=latex.replace(f"### {heading}",f"\\subsection{{{heading}}}")
    latex=re.sub(r"`([^`]*)`",lambda match:"\\texttt{"+match.group(1)+"}",latex)
    (MANUSCRIPT/"Manuscript_Ready_Methods_and_Results.tex").write_text(latex,encoding="utf-8")


def workbook_payload(tables: dict[str,list[dict[str,Any]]]) -> None:
    payload={"title":"Individual Neural Holonomy — integrated source data","version":"1.0.0","sheets":[]}
    for name,rows in tables.items():
        payload["sheets"].append({"name":name[:31],"columns":list(rows[0]) if rows else [],"rows":[[row[column] for column in rows[0]] for row in rows] if rows else []})
    (TABLES/"workbook_payload.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")


def main() -> None:
    ensure_dirs()
    required=[RESULTS/f"stage{i}_final"/"summary.json" for i in range(1,6)]
    missing=[str(path) for path in required if not path.exists()]
    if missing: raise FileNotFoundError(f"Missing full-run results: {missing}")
    s1,s2,s3,s4,s5=[load_json(path) for path in required]
    stage3_data=np.load(RESULTS/"stage3_final"/"episode_trajectories.npz")
    stage4_data=np.load(RESULTS/"stage4_final"/"recovery_arrays.npz")
    tables=build_tables(s1,s2,s3,s4,s5); workbook_payload(tables)
    figure1_design(); figure2_stage1_stage2(s1,s2); figure3_stage3_dynamics(stage3_data); figure4_stage3_inference(s3); figure5_stage4_recovery(s4,stage4_data); figure6_stage4_stress(s4); figure7_stage5_boundaries(s5); figure8_claim_matrix(s1,s2,s3,s4,s5); supplementary_figures(s1,s3,s4,s5)
    manuscript_text(s1,s2,s3,s4,s5)
    summary={"version":"1.0.0","stage_passes":{"stage1_constructive_criterion":s1["scientific_criteria"]["passed"],"stage2_limited_shared_frame_claim":s2["overall_pass"],"stage3_stable_vs_nonstable_claim":s3["criteria"]["overall_pass"],"stage3_global_taxonomy":s3["criteria"]["global_four_regime_taxonomy_supported"],"stage4_controlled_recovery":s4["criteria"]["overall_pass"],"stage5_strict_boundaries":s5["criteria"]["overall_pass"]},"strongest_supported_claim":"In a controlled rank-two SU(2) simulation, pilot-calibrated history-dependent remodeling separates the modeled stable regime from non-stable alternatives under matched probes, and selected conjugacy-invariant scalar and within-clone metric descriptors are recoverable under the declared synthetic observation model.","unsupported_claims":["complete four-regime taxonomy","fast-RIC causality","full-connection recovery","unrestricted cross-subject gauge identification","real-ECoG validity","phenomenology or unique experience"]}
    (RESULTS/"integrated_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(f"Built {len(list(FIGURES.glob('*.pdf')))} PDF figures and {len(tables)} source-data tables")


if __name__=="__main__": main()
