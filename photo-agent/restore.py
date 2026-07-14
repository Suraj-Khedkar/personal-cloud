#!/usr/bin/env python3
"""Restore files from quarantine back to their original paths using scan logs."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

LOG_DIR = Path("/Volumes/Cloud/_review/logs")
CATEGORIES = sys.argv[1:] if len(sys.argv) > 1 else ["blur"]


def main() -> None:
    restored = 0
    for log_file in sorted(LOG_DIR.glob("scan_*.jsonl"), reverse=True):
        with log_file.open() as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("dry_run"):
                    continue
                if entry.get("category") not in CATEGORIES:
                    continue
                src = Path(entry["destination"])
                dest = Path(entry["source"])
                if not src.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                print(f"Restored: {dest.name} → {dest.parent.name}/")
                restored += 1

    print(f"\n{restored} file(s) restored.")


if __name__ == "__main__":
    main()
