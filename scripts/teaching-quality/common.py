"""Strict, offline-only primitives for teaching quality evidence checks.

This package deliberately uses only the Python standard library. It does not
import application modules, resolve a model, read credentials, or make requests.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class CheckError(ValueError):
    def __init__(self, field: str, reason: str, code: str = "INVALID_INPUT"):
        super().__init__(f"{field}: {reason}")
        self.field, self.reason, self.code = field, reason, code

    def as_dict(self) -> dict:
        return {"field": self.field, "reason": self.reason, "code": self.code}


def require(condition: bool, field: str, reason: str, code: str = "INVALID_INPUT") -> None:
    if not condition:
        raise CheckError(field, reason, code)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    require(path.is_file(), str(path), "required file is missing", "MISSING_FILE")
    return sha_bytes(path.read_bytes())


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(path: Path):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "$.'" + key + "'", "duplicate JSON key", "DUPLICATE_KEY")
            out[key] = value
        return out

    def constant(_value):
        raise CheckError("$", "NaN and Infinity are not JSON numbers", "NONFINITE_NUMBER")

    def finite(value, field="$"):
        if type(value) is float:
            require(math.isfinite(value), field, "number must be finite", "NONFINITE_NUMBER")
        elif isinstance(value, dict):
            for key, item in value.items():
                finite(item, field + "." + key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                finite(item, field + f"[{i}]")

    require(path.is_file(), str(path), "required JSON is missing", "MISSING_FILE")
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=constant)
    except CheckError:
        raise
    except (ValueError, UnicodeError) as error:
        raise CheckError(str(path), "invalid JSON", "INVALID_JSON") from error
    finite(value)
    return value


def checked_json(path: Path, expected_sha: str):
    require(type(expected_sha) is str and len(expected_sha) == 64 and all(c in "0123456789abcdef" for c in expected_sha), "sha256", "expected lowercase SHA-256 is required")
    require(sha_file(path) == expected_sha, str(path), "SHA-256 differs from frozen input", "HASH_MISMATCH")
    return strict_json(path)


def exact_object(value, field: str, allowed: set[str], required: set[str]) -> dict:
    require(type(value) is dict, field, "must be a JSON object")
    extra = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    require(not extra, field, "unexpected fields: " + ", ".join(extra), "UNEXPECTED_FIELD")
    require(not missing, field, "missing fields: " + ", ".join(missing), "MISSING_FIELD")
    return value


def positive_int(value, field: str) -> int:
    require(type(value) is int and value > 0, field, "must be an exact positive integer; boolean is not an integer")
    return value


def trimmed_string(value, field: str) -> str:
    require(type(value) is str and bool(value) and value == value.strip(), field, "must be a trimmed nonempty string")
    return value


def known_case_ids(manifest: dict) -> list[str]:
    require(type(manifest) is dict and type(manifest.get("cases")) is list and bool(manifest["cases"]), "manifest.cases", "must be a nonempty frozen case list")
    ids = []
    for i, item in enumerate(manifest["cases"]):
        require(type(item) is dict, f"manifest.cases[{i}]", "must be an object")
        case_id = trimmed_string(item.get("caseId"), f"manifest.cases[{i}].caseId")
        require(case_id not in {".", ".."} and "/" not in case_id and "\\" not in case_id and ":" not in case_id, f"manifest.cases[{i}].caseId", "must be a single safe case directory name")
        ids.append(case_id)
    require(len(ids) == len(set(ids)), "manifest.cases", "duplicate expected case ID", "DUPLICATE_CASE")
    return ids


def selected_cases(scope: dict, known: list[str]) -> list[str]:
    ids = scope.get("caseIds")
    require(type(ids) is list and bool(ids), "scope.caseIds", "must be a nonempty JSON array")
    for i, case in enumerate(ids):
        trimmed_string(case, f"scope.caseIds[{i}]")
        require(case in known, f"scope.caseIds[{i}]", "unknown frozen case ID", "UNKNOWN_CASE")
    require(len(ids) == len(set(ids)), "scope.caseIds", "duplicate case ID", "DUPLICATE_CASE")
    positive_int(scope.get("sampleCount"), "scope.sampleCount")
    require(scope["sampleCount"] == len(ids), "scope.sampleCount", "must equal exact caseIds length")
    return ids


def selection_scope(scope: dict, known: list[str]) -> list[str]:
    exact_object(scope, "scope", {"caseIds", "sampleCount"}, {"caseIds", "sampleCount"})
    return selected_cases(scope, known)


def live_scope(scope: dict, known: list[str]) -> dict:
    required = {"modelProfileId", "modelId", "caseIds", "sampleCount", "maxAttempts"}
    exact_object(scope, "scope", required | {"maxTotalTokens", "maxCostCny"}, required)
    trimmed_string(scope["modelProfileId"], "scope.modelProfileId")
    trimmed_string(scope["modelId"], "scope.modelId")
    selected_cases(scope, known)
    positive_int(scope["maxAttempts"], "scope.maxAttempts")
    require("maxTotalTokens" in scope or "maxCostCny" in scope, "scope.budget", "at least one explicit valid total limit is required", "MISSING_BUDGET")
    if "maxTotalTokens" in scope:
        positive_int(scope["maxTotalTokens"], "scope.maxTotalTokens")
    if "maxCostCny" in scope:
        cost = scope["maxCostCny"]
        require((type(cost) is int or (type(cost) is float and math.isfinite(cost))) and cost > 0, "scope.maxCostCny", "must be a finite positive number; boolean is not a number")
    return scope


def create_output(path: Path) -> None:
    require(not path.exists(), str(path), "output directory exists; use a new label", "OUTPUT_EXISTS")
    path.mkdir(parents=True, exist_ok=False)


def write_json(path: Path, value) -> None:
    with path.open("xb") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n")


def offline_status() -> dict:
    return {"networkCalls": 0, "mainImported": False, "formalEnvRead": False, "modelVerified": False, "liveRun": "not_run_user_offline_only", "teacherReview": "teacher_review_pending", "nativeWordWps": "not_run", "RAG_REL": "OPEN"}
