#!/usr/bin/env python3
"""Build checksums and a clean, versioned submission archive."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "INH_Integrated_Submission_Package_v1.0.0.zip"
OUT_HASH = OUT.with_suffix(OUT.suffix + ".sha256")
CHECKSUMS = ROOT / "SHA256SUMS.txt"
INVENTORY = ROOT / "integrated" / "qc" / "release_inventory.json"


def excluded(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    name = path.name
    if name in {"SHA256SUMS.txt"}:
        return True
    if "__pycache__" in parts or name.endswith((".pyc", ".pyo")):
        return True
    if ".mplconfig" in parts or name.startswith("."):
        return True
    if len(parts) >= 3 and parts[0] == "stages" and parts[2] == "results":
        return True
    if len(parts) >= 3 and parts[:2] == ("integrated", "qc"):
        if parts[2] in {"article_render", "article_render_final", "report_render", "report_render_final"}:
            return True
        if "pages_" in name or "contact" in name:
            return True
        if name.endswith("_a11y.json") and not name.endswith("_a11y_final.json"):
            return True
    return False


def files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and not excluded(path))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    inventory = {
        "release": "INH integrated v1.0.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "archive_policy": "excludes caches, temporary renders/contact sheets, and stale stage-local result directories",
    }
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    release_files = files()
    lines = [f"{digest(path)}  {path.relative_to(ROOT).as_posix()}" for path in release_files]
    CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    release_files = files() + [CHECKSUMS]

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(release_files):
            arcname = Path(ROOT.name) / path.relative_to(ROOT)
            archive.write(path, arcname.as_posix())

    with zipfile.ZipFile(OUT) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"corrupt archive member: {bad}")
    OUT_HASH.write_text(f"{digest(OUT)}  {OUT.name}\n", encoding="utf-8")
    print(json.dumps({
        "archive": str(OUT),
        "archive_sha256": digest(OUT),
        "files": len(release_files),
        "bytes": OUT.stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()

