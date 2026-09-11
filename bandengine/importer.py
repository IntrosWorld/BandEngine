"""Guitar Pro import bridge backed by alphaTab's score engine."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
NODE_PROJECT = HERE / "importer"
SUPPORTED = {".gp", ".gp3", ".gp4", ".gp5", ".gpx"}


class ImportFailure(RuntimeError):
    """Raised when the Guitar Pro score cannot be imported."""


def _program(name: str) -> str:
    found = shutil.which(name) or shutil.which(f"{name}.cmd")
    if not found:
        raise ImportFailure(f"{name} is required but was not found on PATH")
    return found


def ensure_importer() -> None:
    """Install the pinned alphaTab dependency on first use."""
    if (NODE_PROJECT / "node_modules" / "@coderline" / "alphatab").is_dir():
        return
    npm = _program("npm")
    print("Installing the Guitar Pro importer (first run only)...", flush=True)
    result = subprocess.run(
        [npm, "ci", "--omit=dev", "--no-audit", "--no-fund"],
        cwd=NODE_PROJECT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=300,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ImportFailure(f"npm could not install the importer: {detail}")


def _run(script: str, source: Path, *arguments: object) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ImportFailure(f"score not found: {source}")
    if source.suffix.lower() not in SUPPORTED:
        kinds = ", ".join(sorted(SUPPORTED))
        raise ImportFailure(f"unsupported score type; expected one of: {kinds}")
    ensure_importer()
    result = subprocess.run(
        [_program("node"), str(NODE_PROJECT / script), str(source), *map(str, arguments)],
        cwd=NODE_PROJECT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=180,
    )
    if result.returncode:
        detail = result.stderr.strip().splitlines()
        raise ImportFailure(detail[0] if detail else "Guitar Pro import failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ImportFailure("the importer returned invalid data") from error


def list_tracks(source: Path) -> dict:
    return _run("list_tracks.cjs", source)


def load_track(source: Path, track: int) -> dict:
    return _run("export_score.cjs", source, track)

