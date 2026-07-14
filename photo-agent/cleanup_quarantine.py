"""Delete quarantine folders older than retention_days."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path


def cleanup_old_quarantine(
    quarantine_root: Path,
    log_dir: Path,
    retention_days: int,
    dry_run: bool = False,
) -> int:
    if not quarantine_root.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0
    log_entries: list[dict] = []

    for date_dir in sorted(quarantine_root.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            folder_date = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if folder_date >= cutoff:
            continue

        file_count = sum(1 for _ in date_dir.rglob("*") if _.is_file())
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "action": "auto_delete",
            "folder": str(date_dir),
            "file_count": file_count,
            "age_days": (datetime.now(timezone.utc) - folder_date).days,
            "dry_run": dry_run,
        }
        log_entries.append(entry)

        if dry_run:
            print(f"  [dry-run] would delete {date_dir.name}/ ({file_count} files, {entry['age_days']} days old)")
        else:
            shutil.rmtree(date_dir)
            print(f"  [deleted] {date_dir.name}/ ({file_count} files, {entry['age_days']} days old)")

        deleted += file_count

    if log_entries:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"cleanup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
        with log_file.open("w") as f:
            for entry in log_entries:
                f.write(json.dumps(entry) + "\n")

    return deleted


if __name__ == "__main__":
    import argparse
    import yaml

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    root = Path(cfg["quarantine_root"])
    log_dir = Path(cfg["log_dir"])
    days = cfg.get("quarantine_retention_days", 30)

    print(f"Cleaning quarantine older than {days} days...")
    n = cleanup_old_quarantine(root, log_dir, days, dry_run=args.dry_run)
    print(f"Done. {n} file(s) {'would be' if args.dry_run else ''} removed.")
