"""Validate a non-sensitive live scope offline. This CLI cannot execute it."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from common import CheckError, canonical, checked_json, create_output, exact_object, known_case_ids, live_scope, offline_status, require, sha_bytes, sha_file, strict_json, trimmed_string, write_json


def validate(args) -> dict:
    manifest = checked_json(args.case_manifest, args.case_manifest_sha)
    known = known_case_ids(manifest)
    scope = live_scope(strict_json(args.scope), known)
    description = None
    if args.model_description:
        description = exact_object(strict_json(args.model_description), "modelDescription", {"modelProfileId", "modelId", "description"}, {"modelProfileId", "modelId", "description"})
        for key, value in description.items():
            trimmed_string(value, "modelDescription." + key)
        for key in ("modelProfileId", "modelId"):
            require(description[key] == scope[key], "modelDescription." + key, "must match explicit scope identity")
    return {
        "status": "SCOPE_PREFLIGHT_PASSED_FOR_HUMAN_REVIEW_ONLY",
        "scopeSHA": sha_bytes(canonical(scope)),
        "scopeFileSHA": sha_file(args.scope),
        "caseManifestSHA": args.case_manifest_sha,
        "caseIds": scope["caseIds"],
        "sampleCount": scope["sampleCount"],
        "maxAttempts": scope["maxAttempts"],
        "maximumCalls": scope["sampleCount"] * scope["maxAttempts"],
        "extraAttemptsNeedExplicitAuthorization": scope["maxAttempts"] > 1,
        "modelDescriptionProvided": description is not None,
        "modelDescriptionSHA": sha_file(args.model_description) if description else None,
        "createsHumanAuthorization": False,
        "executorPresent": False,
        "budgetEnforced": False,
        "message": "Shape validation only. A future authorized executor must recheck scope/hash, resolver identity/fingerprint and executable total budget, counting failed attempts. No model has been verified or called.",
        **offline_status(),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-manifest", type=Path, required=True)
    parser.add_argument("--case-manifest-sha", required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--model-description", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        create_output(args.output_dir)
    except CheckError as error:
        print(json.dumps({"status": "FAIL", "error": error.as_dict(), **offline_status()}, ensure_ascii=False))
        return 2
    try:
        result = validate(args)
        exit_code = 0
    except (CheckError, OSError) as error:
        detail = error.as_dict() if isinstance(error, CheckError) else {"field": "filesystem", "reason": "required input could not be read", "code": "IO_ERROR"}
        result = {"status": "FAIL_SCOPE_PREFLIGHT", "error": detail, "createsHumanAuthorization": False, **offline_status()}
        exit_code = 2
    result.update({"pid": os.getpid(), "at": datetime.now().astimezone().isoformat(), "exitCode": exit_code})
    write_json(args.output_dir / "RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
