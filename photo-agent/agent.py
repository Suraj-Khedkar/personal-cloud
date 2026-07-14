#!/usr/bin/env python3
"""
Photo cleanup agent — conservative mode.
Only quarantines when confidence = 100%. When unsure, keeps the file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cleanup_quarantine import cleanup_old_quarantine
from rules import (
    file_sha256,
    has_camera_exif,
    is_blurry,
    is_greeting_illustration,
    is_screenshot,
    perceptual_hash,
    pick_best_to_keep,
)

try:
    from clip_detect import clip_available, is_screen_or_document
except ImportError:
    clip_available = lambda: False  # type: ignore
    is_screen_or_document = None  # type: ignore

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}


def load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def should_skip_dir(name: str, exclude_dirs: list[str]) -> bool:
    for ex in exclude_dirs:
        if name.startswith(ex) or name == ex:
            return True
    return False


def collect_images(scan_paths: list[str], exclude_dirs: list[str], min_bytes: int, extensions: list[str]) -> list[Path]:
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    images: list[Path] = []
    seen_paths: set[str] = set()
    seen_inodes: set[tuple[int, int]] = set()

    for scan_path in scan_paths:
        root = Path(scan_path)
        if not root.exists():
            print(f"  [skip] path not found: {root}")
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            if any(should_skip_dir(part, exclude_dirs) for part in path.parts):
                continue
            try:
                if path.stat().st_size < min_bytes:
                    continue
                resolved = str(path.resolve())
                if resolved in seen_paths:
                    continue
                st = path.stat()
                inode_key = (st.st_dev, st.st_ino)
                if inode_key in seen_inodes:
                    continue
                seen_paths.add(resolved)
                seen_inodes.add(inode_key)
            except OSError:
                continue
            images.append(path)
    return images


def load_state(state_file: Path) -> set[str]:
    if not state_file.exists():
        return set()
    with state_file.open() as f:
        return set(json.load(f).get("processed", []))


def save_state(state_file: Path, processed: set[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w") as f:
        json.dump({"processed": sorted(processed), "updated": datetime.now(timezone.utc).isoformat()}, f, indent=2)


def maybe_quarantine(
    src: Path,
    category: str,
    reason: str,
    confidence: float,
    min_confidence: float,
    quarantine_root: Path,
    dry_run: bool,
    log_entries: list[dict],
) -> bool:
    """Quarantine only if confidence meets threshold. Returns True if quarantined."""
    if confidence < min_confidence:
        print(f"  [kept] {src.name} — uncertain ({reason}, confidence {confidence:.0%})")
        return False

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dest_dir = quarantine_root / today / category
    dest = dest_dir / src.name
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
        counter += 1

    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "action": "quarantine",
        "category": category,
        "reason": reason,
        "confidence": confidence,
        "source": str(src),
        "destination": str(dest),
        "dry_run": dry_run,
    }
    log_entries.append(entry)

    if dry_run:
        print(f"  [dry-run] {category}: {src.name} — {reason}")
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        print(f"  [moved] {category}: {src.name} — {reason}")

    return True


def find_exact_duplicates(images: list[Path]) -> list[tuple[Path, Path, str]]:
    """Return (extra_copy, keeper, reason) — keeper stays in Nextcloud."""
    by_hash: dict[str, list[Path]] = defaultdict(list)
    results: list[tuple[Path, Path, str]] = []

    for img in images:
        try:
            digest = file_sha256(img)
            by_hash[digest].append(img)
        except OSError:
            continue

    for digest, group in by_hash.items():
        if len(group) < 2:
            continue
        keeper = pick_best_to_keep(group, blur_threshold=0)
        for extra in group:
            if extra.resolve() == keeper.resolve():
                continue
            results.append((
                extra,
                keeper,
                f"extra copy of {keeper.name} — keeping original in place",
            ))
    return results


def find_similar_duplicates(images: list[Path], threshold: int, blur_threshold: float) -> list[tuple[Path, list[Path], str]]:
    if threshold > 0:
        return []
    hashed: list[tuple[Path, object]] = []
    for img in images:
        h = perceptual_hash(img)
        if h is not None:
            hashed.append((img, h))
    used: set[Path] = set()
    results: list[tuple[Path, list[Path], str]] = []
    for i, (img_a, hash_a) in enumerate(hashed):
        if img_a in used:
            continue
        group = [img_a]
        for img_b, hash_b in hashed[i + 1 :]:
            if img_b in used:
                continue
            if hash_a - hash_b == 0:
                group.append(img_b)
        if len(group) < 2:
            continue
        keeper = pick_best_to_keep(group, blur_threshold)
        for dup in group:
            if dup != keeper:
                used.add(dup)
                results.append((dup, group, f"identical visual duplicate of {keeper.name}"))
    return results


def run_scan(config: dict, dry_run: bool, force: bool, use_clip: bool = True) -> None:
    scan_paths = config["scan_paths"]
    exclude_dirs = config.get("exclude_dirs", [])
    quarantine_root = Path(config["quarantine_root"])
    log_dir = Path(config["log_dir"])
    min_confidence = config.get("min_quarantine_confidence", 1.0)
    retention_days = config.get("quarantine_retention_days", 30)

    state_file = log_dir / "processed_files.json"
    processed = set() if force else load_state(state_file)

    print("=" * 60)
    print("Photo Cleanup Agent (conservative — when unsure, keep)")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Min confidence to quarantine: {min_confidence:.0%}")
    print("=" * 60)

    # Auto-delete old quarantine
    print(f"\n[0] Cleaning quarantine older than {retention_days} days...")
    deleted = cleanup_old_quarantine(quarantine_root, log_dir, retention_days, dry_run=dry_run)
    if deleted == 0:
        print("  Nothing to delete.")
    else:
        print(f"  {'Would remove' if dry_run else 'Removed'} {deleted} file(s).")

    print("\n[1] Collecting images...")
    images = collect_images(
        scan_paths, exclude_dirs, config.get("min_file_bytes", 20480), config.get("image_extensions", list(IMAGE_EXTS))
    )
    new_images = [img for img in images if str(img) not in processed]
    print(f"  Found {len(images)} total, {len(new_images)} new since last run")

    if not new_images:
        print("\nNothing new to scan. Use --scan-now to rescan everything.")
        return

    log_entries: list[dict] = []
    quarantined_paths: set[str] = set()

    def q(img: Path, cat: str, reason: str, conf: float = 1.0) -> None:
        if str(img) in quarantined_paths:
            return
        if maybe_quarantine(img, cat, reason, conf, min_confidence, quarantine_root, dry_run, log_entries):
            quarantined_paths.add(str(img))

    remaining = new_images

    if config.get("enable_exact_duplicates", True):
        print("\n[2] Exact duplicates (keep 1 in Nextcloud, quarantine extras)...")
        for extra, keeper, reason in find_exact_duplicates(remaining):
            q(extra, "duplicate-exact", f"{reason} (kept: {keeper})", 1.0)
        remaining = [i for i in remaining if str(i) not in quarantined_paths]
    else:
        print("\n[2] Exact duplicates: disabled")

    if config.get("enable_similar_duplicates", False):
        print("\n[3] Visual duplicates (identical hash only)...")
        for dup, _, reason in find_similar_duplicates(remaining, 0, config.get("blur_threshold", 15)):
            q(dup, "duplicate-similar", reason, 1.0)
        remaining = [i for i in remaining if str(i) not in quarantined_paths]
    else:
        print("\n[3] Similar duplicates: disabled (avoid false positives)")

    if config.get("enable_blur", False):
        print("\n[4] Blurry images (entire frame must be blurry)...")
        for img in remaining:
            matched, reason, conf = is_blurry(img, config.get("blur_threshold", 15))
            if matched:
                q(img, "blur", reason, conf)
        remaining = [i for i in remaining if str(i) not in quarantined_paths]
    else:
        print("\n[4] Blur detection: disabled (portraits were misclassified)")

    if config.get("enable_screenshots", True):
        print("\n[5] Screenshots (explicit filename only)...")
        for img in remaining:
            matched, reason, conf = is_screenshot(img, config.get("screenshot_patterns", []))
            if matched:
                q(img, "screenshot", reason, conf)
        remaining = [i for i in remaining if str(i) not in quarantined_paths]
    else:
        print("\n[5] Screenshots: disabled")

    if config.get("enable_greetings", True):
        print("\n[6] Greeting illustrations (explicit phrases only)...")
        for img in remaining:
            matched, reason, conf = is_greeting_illustration(
                img,
                config.get("greeting_filename_phrases", []),
                config.get("greeting_ocr_keywords", []),
            )
            if matched:
                q(img, "greeting", reason, conf)
        remaining = [i for i in remaining if str(i) not in quarantined_paths]
    else:
        print("\n[6] Greetings: disabled")

    if config.get("enable_clip", False) and use_clip and clip_available() and is_screen_or_document:
        print("\n[7] Screen/document photos (CLIP — high confidence only)...")
        for i, img in enumerate(remaining):
            if i % 25 == 0 and i > 0:
                print(f"  ... {i}/{len(remaining)}")
            matched, reason, conf = is_screen_or_document(
                img,
                config.get("clip_confidence_threshold", 0.55),
                config.get("clip_margin_threshold", 0.25),
                has_camera_exif_fn=has_camera_exif,
            )
            if matched and conf >= min_confidence:
                q(img, "screen-document", reason, conf)
    else:
        print("\n[7] CLIP AI: disabled (not 100% reliable)")

    print("\n" + "=" * 60)
    print(f"Done. {len(log_entries)} file(s) {'would be' if dry_run else ''} quarantined.")
    print(f"Quarantine: {quarantine_root}")
    print(f"Auto-deletes quarantine after {retention_days} days.")
    print("=" * 60)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"scan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
    with log_file.open("w") as f:
        for entry in log_entries:
            f.write(json.dumps(entry) + "\n")

    if not dry_run:
        processed.update(str(img) for img in new_images)
        save_state(state_file, processed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Photo cleanup agent (conservative)")
    parser.add_argument("--config", default="/app/config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scan-now", action="store_true")
    parser.add_argument("--no-clip", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        local = Path(__file__).parent / "config.yaml"
        config_path = local if local.exists() else config_path

    if not config_path.exists():
        print(f"Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    run_scan(load_config(config_path), dry_run=args.dry_run, force=args.scan_now, use_clip=not args.no_clip)


if __name__ == "__main__":
    main()
