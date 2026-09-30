"""V00 probe: recompute sha256 of every file in FROZEN-CANDIDATE.json (read-only).

Usage:  python docs/qa/TEACHING-LOOP-B1/V00-probes/v00_fingerprint.py
Exit 0 = 100% match, exit 1 = mismatch/missing, exit 2 = extra-file warning only.
Does not write anything except stdout.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FROZEN = os.path.join(ROOT, "docs", "qa", "TEACHING-LOOP-B1", "FROZEN-CANDIDATE.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    with open(FROZEN, encoding="utf-8") as fh:
        frozen = json.load(fh)
    files = frozen["files"]
    mismatched, missing, matched = [], [], []
    for rel, want in sorted(files.items()):
        abs_path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(abs_path):
            missing.append(rel)
            continue
        got = sha256_file(abs_path)
        if got == want:
            matched.append(rel)
        else:
            mismatched.append((rel, want, got))

    print(f"frozen revision={frozen.get('revision')} declared fileCount={frozen.get('fileCount')} "
          f"entries={len(files)}")
    print(f"matched={len(matched)} mismatched={len(mismatched)} missing={len(missing)}")
    for rel, want, got in mismatched:
        print(f"MISMATCH {rel}\n  want {want}\n  got  {got}")
    for rel in missing:
        print(f"MISSING  {rel}")
    if mismatched or missing:
        return 1
    print("FINGERPRINT_OK 95/95")
    return 0


if __name__ == "__main__":
    sys.exit(main())
