"""Closed trial scope and explicit, model-specific billing proof interface.

No model billing facts are shipped. A fixture proof can only run a fixture.
The host supplying a live proof/authorization must independently establish its
human provenance; a JSON file or CLI switch is never that provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Protocol

from common import CheckError, canonical, live_scope, require, sha_bytes


@dataclass(frozen=True)
class AuthorizedScope:
    scope: dict
    authorization_id: str
    evidence_kind: str
    human_verified: bool = False
    frozen_scope_bytes: bytes = field(init=False, repr=False)

    def __post_init__(self):
        payload = canonical(self.scope)
        object.__setattr__(self, "scope", json.loads(payload))
        object.__setattr__(self, "frozen_scope_bytes", payload)

    def assert_frozen(self):
        require(canonical(self.scope) == self.frozen_scope_bytes, "scope", "authorized scope was mutated", "SCOPE_DRIFT")

    @property
    def scope_sha(self):
        self.assert_frozen()
        return sha_bytes(self.frozen_scope_bytes)

    @classmethod
    def validated(cls, scope, known, *, authorization_id, evidence_kind, human_verified=False):
        live_scope(scope, known)
        require(type(authorization_id) is str and bool(authorization_id), "authorization", "stable authorization identity required", "AUTHORIZATION_MISSING")
        require(evidence_kind in {"fixture", "live"}, "evidenceKind", "unsupported evidence kind")
        if evidence_kind == "live":
            require(human_verified is True, "authorization", "explicit human authorization has not been verified", "AUTHORIZATION_MISSING")
            require(not any(x in scope["modelProfileId"].lower() or x in scope["modelId"].lower() for x in ("fixture", "isolated", "mock")), "model", "fixture identity cannot be live", "FIXTURE_NOT_LIVE")
        return cls(dict(scope), authorization_id, evidence_kind, human_verified)


@dataclass(frozen=True)
class BillingBound:
    model_id: str
    profile_id: str
    wire_sha: str
    evidence_kind: str
    input_upper: int
    output_upper: int
    reasoning_upper: int
    other_upper: int
    proof_facts: dict
    # A cost-only scope requires an independently verified complete pricing
    # proof. This revision deliberately ships none, rather than invent rates.
    cost_upper_cny: str | None = None

    @property
    def total_upper(self):
        return self.input_upper + self.output_upper + self.reasoning_upper + self.other_upper

    @property
    def proof_sha(self):
        return sha_bytes(canonical(self.__dict__))

    def verify(self, authorization, handle, wire):
        require(self.evidence_kind == authorization.evidence_kind, "proof", "fixture proof is not a live model proof", "FIXTURE_NOT_LIVE")
        require(self.model_id == handle.model_id == authorization.scope["modelId"] and self.profile_id == handle.profile_id == authorization.scope["modelProfileId"], "model", "selected model/profile drift", "MODEL_CONFIG_DRIFT")
        require(self.wire_sha == sha_bytes(canonical(wire)), "wire", "billing proof is for a different final wire", "WIRE_DRIFT")
        for name in ("input_upper", "output_upper", "reasoning_upper", "other_upper"):
            require(type(getattr(self, name)) is int and getattr(self, name) >= 0, "proof."+name, "exact nonnegative upper bound required", "BILLING_BOUND_UNSUPPORTED")
        require(self.total_upper > 0 and bool(self.proof_facts), "proof", "model-specific verifiable billing facts missing", "BILLING_BOUND_UNSUPPORTED")
        caps = [wire[key] for key in ("max_tokens", "max_completion_tokens", "max_output_tokens") if key in wire]
        require(len(caps) == 1 and type(caps[0]) is int and caps[0] == self.output_upper, "wire.cap", "final protocol output cap differs from proof", "WIRE_CAP_DRIFT")
        require("maxTotalTokens" in authorization.scope, "budget", "cost accounting proof is not implemented in this revision", "COST_BOUND_UNSUPPORTED")
        require("maxCostCny" not in authorization.scope, "budget", "complete frozen pricing/currency/exchange evidence missing", "COST_BOUND_UNSUPPORTED")


class BillingProof(Protocol):
    """Trusted host DI interface, not user-controlled JSON billing claims."""
    def prove(self, authorization: AuthorizedScope, handle, wire: dict) -> BillingBound: ...


class UnsupportedLiveProof:
    def prove(self, authorization, handle, wire):
        raise CheckError("billingProof", "No verified input/output/reasoning/other billing bound is registered for this live model", "BILLING_BOUND_UNSUPPORTED")


class FixtureBillingProof:
    """Only a controlled MockTransport with finite fixture usage can use this."""
    def prove(self, authorization, handle, wire):
        require(authorization.evidence_kind == "fixture", "proof", "fixture proof cannot support live", "FIXTURE_NOT_LIVE")
        caps = [wire[key] for key in ("max_tokens", "max_completion_tokens", "max_output_tokens") if key in wire]
        require(len(caps) == 1, "wire", "one output cap required")
        return BillingBound(handle.model_id, handle.profile_id, sha_bytes(canonical(wire)), "fixture", 1000, caps[0], 0, 0,
            {"source": "controlled finite HTTP fixture", "usageIncludesReasoningAndOther": True, "inputUpperIsNotATokenizerClaim": True, "noRealModelSupport": True})
