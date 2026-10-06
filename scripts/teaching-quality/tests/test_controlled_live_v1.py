"""Live-path oracles for the selected-model proof, trusted host and live guard.

No network is used anywhere: transports are never opened, the official tokenizer
artifact is the only external file, and every refusal path is exercised directly.
"""
from __future__ import annotations

import os
import socket
import sys
from dataclasses import replace
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "apps/api"))
from controlled_guard import AuditGuard, establish_isolation  # noqa: E402

ISOLATION = establish_isolation("zqky-live-tests-")

from common import CheckError, canonical, live_scope, sha_bytes  # noqa: E402
from controlled_scope import AuthorizedScope, BillingBound, FixtureBillingProof  # noqa: E402
from controlled_proof import DeepseekFlashProbeProof, PINNED_MODEL_ID, PINNED_PROFILE_ID, PRODUCTION_OUTPUT_CAP, usage_dimension_policy  # noqa: E402
from controlled_host import ACCEPTED_OPTION, HumanAuthorizationReceipt, build_live_host, record_human_authorization, resolve_endpoint_addresses  # noqa: E402
from controlled_provider import verified_usage, verify_live_transport  # noqa: E402
from controlled_ledger import TrialLedger  # noqa: E402

TOKENIZER = ROOT / "docs/qa/TEACHING-LOOP-G7-B7C-20261005/b7c/tokenizer/extracted/deepseek_v4_tokenizer/tokenizer.json"
KNOWN = [f"C{i:02d}" for i in range(1, 16)]
SCOPE = {"modelProfileId": PINNED_PROFILE_ID, "modelId": PINNED_MODEL_ID, "caseIds": ["C01"], "sampleCount": 1,
         "maxAttempts": 1, "maxTotalTokens": 20000}


def wire(model= PINNED_MODEL_ID, cap=PRODUCTION_OUTPUT_CAP, reasoning=True):
    body = {"model": model, "messages": [{"role": "system", "content": "系统提示"}, {"role": "user", "content": "教师要求"}],
            "max_tokens": cap}
    if reasoning:
        body["reasoning_effort"] = "max"
    return body


class FakeHandle:
    def __init__(self, model_id=PINNED_MODEL_ID, profile_id=PINNED_PROFILE_ID, protocol="openai-chat", host="api.deepseek.com"):
        self.model_id, self.profile_id = model_id, profile_id
        class _Config:
            pass
        self.config = _Config()
        self.config.protocol = protocol
        self.config.baseUrl = f"https://{host}/v1"
        self.config.apiKey = "secret-key"


def authorized(scope=None):
    return AuthorizedScope.validated(scope or SCOPE, KNOWN, authorization_id="live-test", evidence_kind="live", human_verified=True)


def proof():
    return DeepseekFlashProbeProof(TOKENIZER)


def test_receipt_requires_provenance_and_scope_binding(tmp_path):
    path = tmp_path / "receipt.json"
    record_human_authorization(path, instruction="user said run it", scope=SCOPE,
                               provenance={"recordedBy": "CTRL", "source": "direct human instruction", "receivedAt": "2026-10-05T00:00:00+08:00"})
    receipt = HumanAuthorizationReceipt.load(path, KNOWN)
    assert receipt.scope == SCOPE and receipt.scope_sha == sha_bytes(canonical(SCOPE))
    # forged authorizationId
    document = path.read_text(encoding="utf-8").replace(receipt.authorization_id, "f" * 64)
    path.write_text(document, encoding="utf-8")
    with pytest.raises(CheckError) as exc:
        HumanAuthorizationReceipt.load(path, KNOWN)
    assert exc.value.code == "AUTHORIZATION_INVALID"
    # scope drift at run time
    drift_path = tmp_path / "receipt-drift.json"
    record_human_authorization(drift_path, instruction="user said run it", scope=SCOPE,
                               provenance={"recordedBy": "CTRL", "source": "direct human instruction", "receivedAt": "2026-10-05T00:00:00+08:00"})
    with pytest.raises(CheckError) as exc:
        build_live_host(drift_path, {**SCOPE, "maxTotalTokens": 99999}, KNOWN, TOKENIZER)
    assert exc.value.code == "SCOPE_DRIFT"
    # fixture identities cannot be authorized as live
    fixture_scope = {**SCOPE, "modelId": "mock-deepseek"}
    with pytest.raises(CheckError) as exc:
        AuthorizedScope.validated(fixture_scope, KNOWN, authorization_id="x", evidence_kind="live", human_verified=True)
    assert exc.value.code == "FIXTURE_NOT_LIVE"


def test_proof_binds_model_endpoint_wire_and_cap():
    authorization, handle = authorized(), FakeHandle()
    bound = proof().prove(authorization, handle, wire())
    assert bound.input_upper > 0 and bound.output_upper == PRODUCTION_OUTPUT_CAP and bound.reasoning_upper == 0 and bound.other_upper == 0
    # margin policy: upper = count + max(16, ceil(10%)); reconciliation evidence recorded
    from controlled_proof import COUNT_MARGIN_ABS, COUNT_MARGIN_RATIO, RECONCILIATION_EVIDENCE, input_upper_for
    assert bound.input_upper == input_upper_for(bound.proof_facts["frozenInputCount"])
    assert bound.input_upper >= bound.proof_facts["frozenInputCount"] + COUNT_MARGIN_ABS
    assert bound.proof_facts["marginPolicy"]["ratio"] == COUNT_MARGIN_RATIO
    assert bound.proof_facts["reconciliationEvidence"] == RECONCILIATION_EVIDENCE
    assert RECONCILIATION_EVIDENCE["apiPromptTokens"] > RECONCILIATION_EVIDENCE["tokenizerCount"]
    counter = proof()
    first, second = counter.prove(authorization, handle, wire()), counter.prove(authorization, handle, wire())
    assert first.input_upper == second.input_upper  # deterministic count
    for bad_handle, code in ((FakeHandle(model_id="other-model"), "MODEL_CONFIG_DRIFT"),
                             (FakeHandle(host="evil.example.com"), "PROOF_UNSUPPORTED"),
                             (FakeHandle(protocol="openai-responses"), "PROOF_UNSUPPORTED")):
        with pytest.raises(CheckError) as exc:
            proof().prove(authorization, bad_handle, wire())
        assert exc.value.code == code
    with pytest.raises(CheckError) as exc:
        proof().prove(authorization, handle, wire(cap=4096))
    assert exc.value.code == "WIRE_CAP_DRIFT"
    with pytest.raises(CheckError) as exc:
        proof().prove(authorization, handle, wire(reasoning=False))
    assert exc.value.code == "PROOF_UNSUPPORTED"
    with pytest.raises(CheckError) as exc:
        proof().prove(AuthorizedScope.validated(SCOPE, KNOWN, authorization_id="f", evidence_kind="fixture"), handle, wire())
    assert exc.value.code == "FIXTURE_NOT_LIVE"


def test_live_usage_policy_official_dimensions_and_containment():
    authorization, handle = authorized(), FakeHandle()
    bound = proof().prove(authorization, handle, wire())
    policy = usage_dimension_policy()
    inp = bound.input_upper
    hit, miss, out = max(0, inp - 10), min(10, inp), min(50, bound.output_upper)
    good = {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": inp + out,
            "prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": miss,
            "prompt_tokens_details": {"cached_tokens": hit},
            "completion_tokens_details": {"reasoning_tokens": out}}
    usage = verified_usage(good, "openai-chat", bound, policy=policy)
    assert usage == {"inputTokens": inp, "outputTokens": out, "totalTokens": inp + out}
    for bad, code in (({**good, "unknown_tokens": 1}, "USAGE_UNCERTAIN"),
                      ({**good, "prompt_cache_hit_tokens": hit + 1}, "USAGE_UNCERTAIN"),
                      ({**good, "completion_tokens_details": {"reasoning_tokens": out + 1}}, "USAGE_OUT_OF_BOUND"),
                      ({**good, "completion_tokens_details": {"other": 1}}, "USAGE_UNCERTAIN"),
                      ({**good, "prompt_tokens": inp + 1, "prompt_cache_hit_tokens": hit + 1, "total_tokens": inp + out + 1}, "USAGE_OUT_OF_BOUND")):
        with pytest.raises(CheckError) as exc:
            verified_usage(bad, "openai-chat", bound, policy=policy)
        assert exc.value.code == code
    # fixture proof keeps the strict three-key rule
    fixture_bound = FixtureBillingProof().prove(AuthorizedScope.validated(SCOPE, KNOWN, authorization_id="f", evidence_kind="fixture"), handle, wire())
    with pytest.raises(CheckError) as exc:
        verified_usage(good, "openai-chat", fixture_bound)
    assert exc.value.code == "USAGE_UNCERTAIN"


def test_live_guard_allows_only_selected_endpoint():
    guard = AuditGuard(ISOLATION, ROOT, live_endpoint=("api.deepseek.com", ("203.0.113.10",))).install()
    try:
        for host_arg in ("api.deepseek.com", b"api.deepseek.com"):
            try:
                socket.getaddrinfo(host_arg, 443)  # DNS may be unavailable; the guard decision is what we assert
            except OSError:
                pass
        with pytest.raises(PermissionError):
            socket.getaddrinfo("example.com", 443)
        with pytest.raises(PermissionError):
            socket.getaddrinfo(b"example.com", 443)
        with pytest.raises(PermissionError):
            socket.getaddrinfo("api.deepseek.com", 80)
        with pytest.raises(PermissionError):
            socket.getaddrinfo(b"api.deepseek.com", b"80")
        assert guard.counts["allowedLiveDnsLookups"] >= 2
        assert guard.counts["forbiddenNetworkAttempts"] >= 4
    finally:
        guard.active = False


def test_live_transport_requires_no_retry_http_transport():
    import httpx2 as httpx
    verify_live_transport(httpx.AsyncHTTPTransport(retries=0))
    with pytest.raises(CheckError) as exc:
        verify_live_transport(httpx.AsyncHTTPTransport(retries=1))
    assert exc.value.code == "LIVE_TRANSPORT_UNSUPPORTED"


def test_live_budget_and_attempt_ledger_bounds(tmp_path):
    authorization, handle = authorized(), FakeHandle()
    with TrialLedger(tmp_path / "control", authorization) as ledger:
        bound = proof().prove(authorization, handle, wire())
        ticket = ledger.reserve(dict(caseId="C01", jobId="j1", jobAttempt=1, modelFingerprint="sha256:" + "5" * 64,
                                     inputHash="1" * 64, wireSHA="2" * 64), bound, "live-label")
        assert ticket["reservedTokens"] == bound.total_upper
        with pytest.raises(CheckError) as exc:
            ledger.reserve(dict(caseId="C01", jobId="j2", jobAttempt=1, modelFingerprint="sha256:" + "5" * 64,
                                inputHash="1" * 64, wireSHA="2" * 64), bound, "live-label")
        assert exc.value.code == "ATTEMPTS_EXHAUSTED"
    # budget smaller than the proven upper bound is refused
    tight = {**SCOPE, "maxTotalTokens": 100}
    with TrialLedger(tmp_path / "control2", AuthorizedScope.validated(tight, KNOWN, authorization_id="tight", evidence_kind="live", human_verified=True)) as ledger:
        with pytest.raises(CheckError) as exc:
            ledger.reserve(dict(caseId="C01", jobId="j", jobAttempt=1, modelFingerprint="sha256:" + "5" * 64,
                                inputHash="1" * 64, wireSHA="2" * 64), proof().prove(authorized(tight), handle, wire()), "label")
        assert exc.value.code == "BUDGET_INSUFFICIENT"


def test_accepted_option_is_the_recorded_human_choice():
    assert ACCEPTED_OPTION == "B + 保留推理 + 探针"
