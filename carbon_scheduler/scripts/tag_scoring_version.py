"""
Retroactively TAGS (annotation only, never rescoring) every pilot record
collected before the threshold-latency-scoring fix as scoring_method =
"linear_v1", so past and future decisions are never silently merged in
analysis. This does not change any decision, score, or measurement in the
existing records - it only adds a version label documenting what scoring
logic actually produced them, per the council's explicit rejection of
retroactive rescoring as data tampering.

Run from carbon_scheduler/: python scripts/tag_scoring_version.py
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

FILES_TO_TAG = [
    os.path.join(config.DATA_DIR, "pilot_log.jsonl"),
    os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl"),
    os.path.join(config.DATA_DIR, "pilot_log_cloud_vantage.jsonl"),
]

LEGACY_TAG = "linear_v1"


def tag_file(path):
    if not os.path.exists(path):
        print(f"  {path}: not found, skipping")
        return

    with open(path) as f:
        lines = [l for l in f if l.strip()]

    updated = []
    already_tagged = 0
    newly_tagged = 0
    for line in lines:
        record = json.loads(line)
        if "scoring_method" not in record:
            record["scoring_method"] = LEGACY_TAG
            newly_tagged += 1
        else:
            already_tagged += 1
        updated.append(record)

    with open(path, "w") as f:
        for record in updated:
            f.write(json.dumps(record) + "\n")

    print(f"  {os.path.basename(path)}: {newly_tagged} tagged '{LEGACY_TAG}', {already_tagged} already tagged (untouched)")


def main():
    print(f"Tagging pre-fix records as scoring_method='{LEGACY_TAG}' (annotation only, no scores/decisions altered):\n")
    for path in FILES_TO_TAG:
        tag_file(path)
    print(f"\nDone. New cycles going forward will be tagged '{config.SCORING_METHOD_VERSION}' automatically.")


if __name__ == "__main__":
    main()
