from pathlib import Path

target = Path("build_integrated_outputs(4).py")

text = target.read_text(encoding="utf-8")

replacements = {
    'axes[0,1].set_title("Stage 1 criterion is not met")':
    'axes[0,1].set_title("Stage 1 interaction criterion is not met")',

    '"Dashed margin applies to the interaction estimand"':
    '"Dashed margin applies only to the interaction estimand"',

    'axes[1,1].set_ylabel("Clone-mean interaction"); axes[1,1].set_title("Independent-noise robustness")':
    'axes[1,1].set_ylabel("Clone-mean interaction"); axes[1,1].set_title("Independent-noise null correction")',

    '''    axes[1,1].text(.03,.95,f"Observed = {independent['observed_clone_mean_interaction']:.4f}",transform=axes[1,1].transAxes,va="top",fontsize=7)
''':
    "",
}

for old, new in replacements.items():
    if old not in text:
        raise RuntimeError(
            "Expected text was not found. The file may already be edited or "
            f"the source differs:\n{old}"
        )
    text = text.replace(old, new, 1)

target.write_text(text, encoding="utf-8")

print(f"Patched successfully: {target.resolve()}")