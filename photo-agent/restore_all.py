#!/usr/bin/env python3
"""Restore ALL files from quarantine back to original paths using scan logs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

LOG_DIR = Path("/Volumes/Cloud/_review/logs")
QUARANTINE = Path("/Volumes/Cloud/_review/quarantine")


def restore_from_logs() -> int:
    restored = 0
    seen_dest: set[str] = set()

    for log_file in sorted(LOG_DIR.glob("scan_*.jsonl")):
        with log_file.open() as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("dry_run") or entry.get("action") != "quarantine":
                    continue
                src = Path(entry["destination"])
                dest = Path(entry["source"])
                key = str(src)
                if key in seen_dest or not src.exists():
                    continue
                seen_dest.add(key)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                print(f"Restored: {dest.name}")
                restored += 1
    return restored


def restore_orphans() -> int:
    """Restore any files in quarantine not covered by logs (fallback)."""
    restored = 0
    for f in QUARANTINE.rglob("*"):
        if not f.is_file() or f.name.startswith("._"):
            continue
        # Cannot know original path — leave for manual review
        pass
    return restored


def main() -> None:
    print("Restoring all quarantined files from scan logs...")
    n = restore_from_logs()
    print(f"\n{n} file(s) restored to original locations.")

    remaining = [f for f in QUARANTINE.rglob("*") if f.is_file() and not f.name.startswith("._")]
    if remaining:
        print(f"\nWarning: {len(remaining)} file(s) still in quarantine (no log entry).")
        for f in remaining[:10]:
            print(f"  {f}")


if __name__ == "__main__":
    main()
