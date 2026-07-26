from pathlib import Path
import re
import shutil

target = Path("build_integrated_outputs.py")
backup = Path("build_integrated_outputs.before_figure3_patch.py")

if not target.exists():
    raise FileNotFoundError(
        f"File not found: {target.resolve()}\n"
        "Run this script from the project's scripts folder."
    )

text = target.read_text(encoding="utf-8")

# Keep an untouched backup before editing.
if not backup.exists():
    shutil.copy2(target, backup)

# Locate only the Figure 3 function, so no other figure is modified.
start_match = re.search(
    r"(?m)^def\s+figure3[^\n]*\n",
    text,
)

if start_match is None:
    raise RuntimeError(
        "Could not find a function whose name begins with 'figure3'."
    )

start = start_match.start()

next_function = re.search(
    r"(?m)^def\s+\w+\s*\(",
    text[start_match.end():],
)

if next_function is None:
    end = len(text)
else:
    end = start_match.end() + next_function.start()

before = text[:start]
block = text[start:end]
after = text[end:]


def replace_once(pattern: str, replacement: str, label: str) -> None:
    global block

    updated, count = re.subn(
        pattern,
        lambda _: replacement,
        block,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Could not uniquely patch: {label}\n"
            f"Matches found: {count}"
        )

    block = updated


# Panel a title
replace_once(
    r'\.set_title\(\s*["\']Connection change["\']\s*\)',
    '.set_title("Remodeling-state change")',
    "Panel a title",
)

# Panel b title
replace_once(
    r'\.set_title\(\s*["\']Closure margin K["\']\s*\)',
    r'.set_title(r"Operational closure margin, $\kappa^{\mathrm{op}}$")',
    "Panel b title",
)

# Panel c title
replace_once(
    r'\.set_title\(\s*["\']Mismatch["\']\s*\)',
    r'.set_title(r"Mismatch magnitude, $m$")',
    "Panel c title",
)

# Panel d title
replace_once(
    r'\.set_title\(\s*["\']Directional coherence["\']\s*\)',
    r'.set_title(r"Directional coherence, $c^{\delta}$")',
    "Panel d title",
)

# Panel a x-axis: theta displacement includes the initial state plus
# successive post-episode remodeling states.
x_axis_pattern = (
    r'([A-Za-z_]\w*)\[\s*0\s*,\s*0\s*\]'
    r'\.set_xlabel\(\s*["\']Episode["\']\s*\)'
)

x_axis_match = re.search(x_axis_pattern, block)

if x_axis_match is None:
    raise RuntimeError(
        "Could not find the panel-a Episode x-axis label."
    )

axis_object = x_axis_match.group(1)

block = re.sub(
    x_axis_pattern,
    (
        f'{axis_object}[0,0]'
        '.set_xlabel("Post-episode index")'
    ),
    block,
    count=1,
)

# Correct regime terminology in the Figure 3 legend only.
diffuse_updated, diffuse_count = re.subn(
    r'(["\'])Diffuse\1',
    '"Dispersive"',
    block,
)

if diffuse_count < 1:
    raise RuntimeError(
        "Could not find the 'Diffuse' legend label in Figure 3."
    )

block = diffuse_updated

patched_text = before + block + after
target.write_text(patched_text, encoding="utf-8")

print("Figure 3 patch completed successfully.")
print(f"Updated file: {target.resolve()}")
print(f"Backup file:  {backup.resolve()}")
print("No data arrays, numerical values, curves, or intervals were modified.")