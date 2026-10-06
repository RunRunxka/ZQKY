"""Selected-model live billing proof: DeepSeek v4 flash, openai-chat, reasoning kept.

Accepted basis (user instruction 2026-10-05, option "B + 保留推理 + 探针"):

- input upper bound: deterministic count of the FROZEN final wire, rendered with the
  OFFICIAL chat template and encoded with the OFFICIAL tokenizer.json (pinned SHA-256,
  source https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip). This is a
  reproducible count, not a character/ratio estimate; the API-returned usage remains
  the source of truth at settle time.
- output upper bound: the wire's single generation cap (`max_tokens` = production
  cap 16384). Official docs define it as the maximum tokens generated in the chat
  completion.
- reasoning upper: 0 under the explicit PROBE assumption that the generation cap
  bounds all generated tokens including reasoning. The official material does not
  state the containment relation; the first calls are probes whose returned usage is
  reconciled at settle time. Usage that disproves the reserved bound stops the
  authorization (cost already incurred is reported as-is, never hidden).
- other upper: 0. Official usage has no other billed dimension; cache-hit/miss tokens
  are additive parts of prompt_tokens and therefore already inside the input bound.

Only this exact profile/model/protocol may use this proof; any parameter change
produces a different final wire and is re-proven on that wire (never reused).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template
from tokenizers import Tokenizer

from common import CheckError, canonical, require, sha_bytes
from controlled_scope import BillingBound

PROOF_KIND = "deepseek-v4-flash-openai-chat-reasoning-probe-v1"
PINNED_PROFILE_ID = "63b3ffdc87fb4c8f8b278c3b58923296"
PINNED_MODEL_ID = "deepseek-flash"
PINNED_HOST = "api.deepseek.com"
PINNED_PROTOCOL = "openai-chat"
PRODUCTION_OUTPUT_CAP = 16384
PINNED_TOKENIZER_SHA256 = "89085f12ef79460ac5f66d1119325ddfc694b4ab209d80bbd81d35f081dc9614"
PINNED_CONFIG_SHA256 = "841f8cf146e3f0ad1082594a31f68ecf7608c20467ef355081333d85bbaeb1cb"
TOKENIZER_SOURCE_URL = "https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip"
OFFICIAL_FACTS = {
    "maxTokensDefinition": "The maximum number of tokens that can be generated in the chat completion.",
    "usageFields": ["prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "prompt_tokens_details.cached_tokens", "completion_tokens_details.reasoning_tokens"],
    "promptEqualsCacheParts": "prompt_tokens equals prompt_cache_hit_tokens + prompt_cache_miss_tokens",
    "reasoningEffortValues": ["none", "low", "high", "max"],
    "thinkingFields": ["type", "reasoning_effort"],
    "reasoningCapFieldExists": False,
    "maxTokensContainmentDocumented": False,
    "docsURLs": ["https://api-docs.deepseek.com/api/create-chat-completion", "https://api-docs.deepseek.com/quick_start/token_usage", "https://api-docs.deepseek.com/quick_start/pricing"],
}
PROBE_FACTS = {
    "userOption": "B + 保留推理 + 探针",
    "acceptedByHumanBecause": "user explicitly chose to accept the probe input basis with reasoning kept",
    "outputCapBoundsAllGeneratedTokens": "assumed by the accepted probe; not stated by official docs; reconciled against returned usage at settle time",
    "overBoundPolicy": "usage disproving the reserved bound stops the authorization; incurred cost is reported, never hidden",
}
# Bound policy on top of the official count. The official tokenizer/chat-template count is a
# deterministic measurement of the frozen wire, but the provider's own prompt_tokens can be
# slightly higher; the reservation therefore adds a recorded margin and the settle-time
# reconciliation remains the backstop (usage beyond the reservation stops the run).
COUNT_MARGIN_RATIO = 0.10
COUNT_MARGIN_ABS = 16
RECONCILIATION_EVIDENCE = {
    "at": "2026-10-06",
    "caseId": "C01",
    "wireFileSHA256": "fb9e8442da4692b85599d7512cc6ded58ac6e789a84d26d795f26916b510c1aa",
    "tokenizerCount": 698,
    "apiPromptTokens": 726,
    "delta": 28,
    "ratio": 1.0401146131805158,
    "evidenceKind": "first real provider call on this wire (HTTP 200, usage captured before adapter parsing)",
    "reasoningContainmentConfirmed": "completion_tokens 9664 >= completion_tokens_details.reasoning_tokens 8176 on the same call",
    "candidateStructuralValidation": "parse_output/normalize_model_output/validate_for_apply all passed offline on the same raw candidate",
}


def input_upper_for(count: int) -> int:
    import math
    return int(count) + max(COUNT_MARGIN_ABS, math.ceil(int(count) * COUNT_MARGIN_RATIO))


def official_token_counter(tokenizer_json: Path):
    """Return a counter for the frozen wire using the official pinned artifacts."""
    tokenizer_json = Path(tokenizer_json)
    config_path = tokenizer_json.with_name("tokenizer_config.json")
    require(tokenizer_json.is_file() and config_path.is_file(), "tokenizer", "official tokenizer artifacts missing", "PROOF_UNSUPPORTED")
    require(sha_bytes(tokenizer_json.read_bytes()) == PINNED_TOKENIZER_SHA256, "tokenizer", "official tokenizer.json hash differs from the pinned revision", "PROOF_UNSUPPORTED")
    require(sha_bytes(config_path.read_bytes()) == PINNED_CONFIG_SHA256, "tokenizer", "official tokenizer_config.json hash differs from the pinned revision", "PROOF_UNSUPPORTED")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    template = Template(config["chat_template"])
    tokenizer = Tokenizer.from_file(str(tokenizer_json))
    bos = config["bos_token"]["content"]

    def count(wire: dict) -> int:
        messages = [{"role": item["role"], "content": item["content"]} for item in wire["messages"]]
        rendered = template.render(messages=messages, bos_token=bos, add_generation_prompt=False)
        return len(tokenizer.encode(rendered).ids)

    return count


@dataclass(frozen=True)
class DeepseekFlashProbeProof:
    """BillingProof implementation bound to one accepted probe revision."""

    tokenizer_json: Path

    def prove(self, authorization, handle, wire: dict) -> BillingBound:
        require(authorization.evidence_kind == "live", "proof", "this proof serves live trials only", "FIXTURE_NOT_LIVE")
        scope = authorization.scope
        require(scope.get("modelProfileId") == PINNED_PROFILE_ID and scope.get("modelId") == PINNED_MODEL_ID, "proof", "proof serves only the registered profile/model", "PROOF_UNSUPPORTED")
        require(handle is not None, "proof", "resolved production handle required", "PROOF_UNSUPPORTED")
        from urllib.parse import urlsplit
        config = handle.config
        protocol = str(getattr(config.protocol, "value", config.protocol))
        host = (urlsplit(config.baseUrl).hostname or "").lower()
        require(protocol == PINNED_PROTOCOL and host == PINNED_HOST, "proof", "proof serves only the registered endpoint/protocol", "PROOF_UNSUPPORTED")
        require(handle.model_id == PINNED_MODEL_ID and handle.profile_id == PINNED_PROFILE_ID, "proof", "resolved handle drift", "MODEL_CONFIG_DRIFT")
        require(wire.get("model") == PINNED_MODEL_ID, "model", "wire model differs from the selected model", "MODEL_CONFIG_DRIFT")
        require("reasoning_effort" in wire or "thinking" in wire, "proof", "accepted basis requires the profile's reasoning parameters on the wire", "PROOF_UNSUPPORTED")
        caps = [wire[key] for key in ("max_tokens", "max_completion_tokens", "max_output_tokens") if key in wire]
        require(len(caps) == 1 and type(caps[0]) is int and caps[0] == PRODUCTION_OUTPUT_CAP, "wire.cap", "final wire must carry exactly the production generation cap", "WIRE_CAP_DRIFT")
        raw_count = official_token_counter(self.tokenizer_json)(wire)
        input_upper = input_upper_for(raw_count)
        require(input_upper >= 1, "proof", "frozen wire token count must be positive", "PROOF_UNSUPPORTED")
        facts = dict(OFFICIAL_FACTS, probe=PROBE_FACTS, method="official chat_template render + official tokenizer.json encode",
                     tokenizerSHA256=PINNED_TOKENIZER_SHA256, tokenizerSourceURL=TOKENIZER_SOURCE_URL,
                     frozenInputCount=raw_count, frozenInputUpper=input_upper, productionOutputCap=PRODUCTION_OUTPUT_CAP, proofKind=PROOF_KIND,
                     marginPolicy={"ratio": COUNT_MARGIN_RATIO, "absoluteAdd": COUNT_MARGIN_ABS,
                                   "rationale": "bound policy on top of the official deterministic count; first real call reconciliation evidence below"},
                     reconciliationEvidence=RECONCILIATION_EVIDENCE)
        return BillingBound(PINNED_MODEL_ID, PINNED_PROFILE_ID, sha_bytes(canonical(wire)), "live",
                            input_upper, caps[0], 0, 0, facts)

    def proof_document(self, bound: BillingBound) -> dict:
        return {
            "schemaVersion": 1, "proofKind": PROOF_KIND, "evidenceKind": "live",
            "modelProfileId": bound.profile_id, "modelId": bound.model_id, "wireSHA": bound.wire_sha,
            "inputUpper": bound.input_upper, "outputUpper": bound.output_upper,
            "reasoningUpper": bound.reasoning_upper, "otherUpper": bound.other_upper,
            "tokenizerSHA256": PINNED_TOKENIZER_SHA256, "tokenizerSourceURL": TOKENIZER_SOURCE_URL,
            "officialFacts": OFFICIAL_FACTS, "probeFacts": PROBE_FACTS, "proofSHA": bound.proof_sha,
        }

    def usage_policy(self) -> dict:
        return usage_dimension_policy()

    def preflight(self) -> None:
        """Validate the pinned official artifacts before any host/credential work.

        Called by the live CLI before reading the selected config/credential so a
        missing or drifted tokenizer refuses with PROOF_UNSUPPORTED and zero side
        effects (no credential read, no handle resolution, no ledger reservation).
        """
        official_token_counter(self.tokenizer_json)


def usage_dimension_policy() -> dict:
    """Official usage dimensions this proof normalizes, with strict containment rules."""
    return {
        "required": ["prompt_tokens", "completion_tokens"],
        "optional": ["total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "prompt_tokens_details", "completion_tokens_details"],
        "detailKeys": {"prompt_tokens_details": ["cached_tokens"], "completion_tokens_details": ["reasoning_tokens"]},
        "normalized": {"input": "prompt_tokens", "output": "completion_tokens", "total": "prompt_tokens+completion_tokens"},
        "cacheRule": "prompt_cache_hit_tokens + prompt_cache_miss_tokens == prompt_tokens when present",
        "reasoningRule": "completion_tokens_details.reasoning_tokens must not exceed completion_tokens (probe containment)",
    }


def proof_sha256(document: dict) -> str:
    return hashlib.sha256(canonical(document)).hexdigest()
