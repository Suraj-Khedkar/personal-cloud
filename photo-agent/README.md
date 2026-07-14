# Photo Cleanup Agent — Conservative Mode

**When unsure, the file is kept.** Only 100% certain matches are quarantined.

## What gets quarantined (enabled)

| Category | Certainty | How |
|----------|-----------|-----|
| Exact duplicates | 100% | Identical file hash (byte-for-byte) |
| Screenshots | 100% | Filename contains `Screenshot`, `screencapture`, etc. |
| Greeting wishes | 100% | Filename or OCR contains explicit phrase (`happy birthday`, `good morning`, etc.) |

## Disabled (too many false positives)

| Category | Why disabled |
|----------|--------------|
| Similar duplicates | Burst shots flagged as dupes |
| Blur | Portraits with soft backgrounds misclassified |
| CLIP AI | Never 100% certain |
| PNG aspect-ratio guessing | Salary slips, etc. misclassified |

## Auto-delete quarantine

Folders in `_review/quarantine/YYYY-MM-DD/` are **permanently deleted after 30 days**.

You have 30 days to review and restore anything before it's gone.

## Commands

```bash
# Preview (safe)
~/personal-cloud/photo-agent/run-local.sh --dry-run

# Run on new photos only
~/personal-cloud/photo-agent/run-local.sh

# Preview quarantine cleanup only
~/personal-cloud/photo-agent/run-local.sh --dry-run  # step [0] shows old deletions
```

## Tune in config.yaml

```yaml
min_quarantine_confidence: 1.0   # only 100% matches
quarantine_retention_days: 30    # auto-delete after N days
enable_blur: false               # keep false unless you want blur back
enable_clip: false               # keep false for zero AI false positives
```

## Restore a file

Drag from `/Volumes/Cloud/_review/quarantine/` back into your Nextcloud folder, then:

```bash
docker exec -u www-data personal-cloud-nextcloud-1 php occ files:scan suraj
```
