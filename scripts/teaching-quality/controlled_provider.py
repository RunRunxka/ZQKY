"""Single-instance production Provider/HTTP boundary decoration.

The original adapter serializes and parses the request. No shared class/global
transport is patched. A transport permits exactly one possible upstream send.
"""
from __future__ import annotations

import json
import ipaddress
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import httpx2 as httpx

from common import CheckError, canonical, require, sha_bytes
from controlled_scope import BillingProof
from app.providers.llm.openai_chat import build_chat_body
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.services.lesson_generation.privacy import check_text, check_wire
from app.services.lesson_generation.service import SYSTEM_PROMPT
from app.services.model_runtime import fingerprint_of_handle


def wire_body(config, request):
    protocol = getattr(config.protocol, "value", config.protocol)
    if protocol == "openai-chat":
        return build_chat_body(config, request, stream=False)
    if protocol == "openai-responses":
        return OpenAIResponsesProvider()._body(config, request, stream=False)
    if protocol == "anthropic-messages":
        return AnthropicMessagesProvider()._body(config, request, stream=False)
    raise CheckError("protocol", "trial supports only the three production serializers", "UNSUPPORTED_PROTOCOL")


def config_identity(config):
    # Hash effective endpoint/config without persisting credentials, headers,
    # query tokens or full non-sensitive config copies.
    return sha_bytes(canonical({"protocol": str(config.protocol), "baseUrl": config.baseUrl,
        "modelId": config.modelId, "providerId": config.providerId, "apiFormat": config.apiFormat,
        "apiVersion": config.apiVersion, "connectionId": config.connectionId,
        "modelProfileId": config.modelProfileId, "reasoningEnabled": config.reasoningEnabled,
        "reasoningEffort": config.reasoningEffort, "timeoutSeconds": config.timeoutSeconds,
        "extraHeaders": config.extraHeaders}))


def safe_record_text(text, *, secrets, personal_tokens):
    require(type(text) is str, "response", "response is not text", "UNSAFE_RESPONSE")
    require(not any(secret and secret in text for secret in secrets), "response", "credential echo suppressed", "SECRET_ECHO")
    check_text(text, personal_tokens, field="responseEvidence")
    return text


def verify_live_transport(transport):
    require(type(transport) is httpx.AsyncHTTPTransport, "transport", "live requires the unmodified no-retry HTTP transport", "LIVE_TRANSPORT_UNSUPPORTED")
    require(getattr(transport._pool, "_retries", None) == 0, "transport", "hidden HTTP retries cannot be counted", "LIVE_TRANSPORT_UNSUPPORTED")


def verify_live_endpoint(config):
    parsed = urlsplit(config.baseUrl)
    host = parsed.hostname or ""
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() in {"localhost", "fixture.invalid"} or host.lower().endswith(".localhost")
    require(parsed.scheme == "https" and bool(host) and not loopback and parsed.port != 9, "endpoint", "local fixture endpoint cannot be live", "FIXTURE_NOT_LIVE")


def write_artifact(directory, name, value, *, raw=False):
    path = Path(directory) / name
    data = value.encode("utf-8") if raw else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")+b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    require(path.read_bytes() == data, "artifact", "artifact write readback differs", "JOURNAL_FAILED")
    return {"file": str(path.resolve()), "sha256": sha_bytes(data)}


def verified_usage(raw, protocol, bound, *, policy=None):
    require(type(raw) is dict, "usage", "missing usage object", "USAGE_UNCERTAIN")
    if protocol == "openai-chat":
        in_key, out_key = "prompt_tokens", "completion_tokens"
    else:
        in_key, out_key = "input_tokens", "output_tokens"
    if policy is None:
        require(set(raw) <= {in_key, out_key, "total_tokens"}, "usage", "unproven additional billing dimension", "USAGE_UNCERTAIN")
    else:
        # Live proof declares the official dimension set for the selected model.
        allowed = {in_key, out_key, "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "prompt_tokens_details", "completion_tokens_details"}
        require(set(raw) <= allowed, "usage", "dimension outside the proven usage policy", "USAGE_UNCERTAIN")
        for name in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
            if name in raw:
                require(type(raw[name]) is int and raw[name] >= 0, "usage", "cache token count must be a nonnegative integer", "USAGE_UNCERTAIN")
        if "prompt_cache_hit_tokens" in raw and "prompt_cache_miss_tokens" in raw:
            require(raw["prompt_cache_hit_tokens"] + raw["prompt_cache_miss_tokens"] == raw.get(in_key), "usage", "cache hit+miss must equal prompt tokens", "USAGE_UNCERTAIN")
        if "prompt_tokens_details" in raw:
            details = raw["prompt_tokens_details"]
            require(type(details) is dict and set(details) <= {"cached_tokens"} and all(type(v) is int and v >= 0 for v in details.values()), "usage", "prompt detail dimension outside the policy", "USAGE_UNCERTAIN")
        if "completion_tokens_details" in raw:
            details = raw["completion_tokens_details"]
            require(type(details) is dict and set(details) <= {"reasoning_tokens"} and all(type(v) is int and v >= 0 for v in details.values()), "usage", "completion detail dimension outside the policy", "USAGE_UNCERTAIN")
            if "reasoning_tokens" in details:
                require(type(raw.get(out_key)) is int and details["reasoning_tokens"] <= raw[out_key], "usage", "reasoning tokens exceed completion tokens; probe containment disproved", "USAGE_OUT_OF_BOUND")
    values = [raw.get(in_key), raw.get(out_key)]
    require(all(type(x) is int and x >= 0 for x in values), "usage", "missing/negative/bool/noninteger usage", "USAGE_UNCERTAIN")
    total = sum(values)
    if "total_tokens" in raw:
        require(type(raw["total_tokens"]) is int and raw["total_tokens"] == total, "usage", "inconsistent total usage", "USAGE_UNCERTAIN")
    require(values[0] <= bound.input_upper and values[1] <= bound.output_upper and total <= bound.total_upper, "usage", "usage disproves the reserved model bound", "USAGE_OUT_OF_BOUND")
    return dict(inputTokens=values[0], outputTokens=values[1], totalTokens=total)


class BoundaryTransport(httpx.AsyncBaseTransport):
    def __init__(self, owner, delegate):
        self.owner, self.delegate = owner, delegate
        self.sends = 0
        self.raw_usage = None
        self.raw_http_sha = None

    async def handle_async_request(self, request):
        owner = self.owner
        if self.sends:
            owner.ledger.unknown(owner.ticket, "MULTIPLE_SENDS_FORBIDDEN")
            raise CheckError("wire", "internal retries and redirects are forbidden", "MULTIPLE_SENDS_FORBIDDEN")
        require(request.method == "POST", "wire", "unexpected HTTP method", "WIRE_DRIFT")
        actual = json.loads(request.content)
        require(canonical(actual) == canonical(owner.expected_wire), "wire", "actual adapter body differs from frozen request", "WIRE_DRIFT")
        require(str(request.url) == owner.expected_url, "wire", "actual endpoint differs from frozen configuration", "MODEL_CONFIG_DRIFT")
        owner.ledger.dispatch(owner.ticket)
        # Conservatively marks a possible send BEFORE entering underlying
        # transport. No unknown delivery is ever decremented to zero.
        self.sends += 1
        owner.actual_wire_sends += 1
        response = await self.delegate.handle_async_request(request)
        await response.aread()
        self.raw_http_sha = sha_bytes(response.content)
        try:
            payload = response.json()
            self.raw_usage = payload.get("usage") if type(payload) is dict else None
        except (ValueError, TypeError):
            self.raw_usage = None
        # Capture upstream usage durably before adapter parsing, status errors,
        # output JSON/finish/length validation. Later normalized capture binds
        # the Provider text if it exists.
        safe_record_text(json.dumps(self.raw_usage, ensure_ascii=False), secrets=owner.secrets,
                         personal_tokens=owner.frozen["source"]["personalTokens"])
        owner.artifacts["upstreamUsage"] = write_artifact(owner.directory, "upstream-usage.json", {
            "rawUsage": self.raw_usage, "rawHttpSHA": self.raw_http_sha, "httpStatus": response.status_code,
            "wireSHA": owner.artifacts["wire"]["sha256"], "scopeSHA": owner.authorization.scope_sha})
        return response

    async def aclose(self):
        await self.delegate.aclose()


class GuardedProvider:
    def __init__(self, handle, *, authorization, ledger, proof: BillingProof, transport_factory,
                 case_id, job_id, job_attempt, input_hash, frozen, directory, run_label, production_wire_sha):
        self.handle, self.authorization, self.ledger, self.proof = handle, authorization, ledger, proof
        self.transport_factory = transport_factory
        self.case_id, self.job_id, self.job_attempt, self.input_hash = case_id, job_id, job_attempt, input_hash
        self.frozen, self.directory, self.run_label = frozen, Path(directory), run_label
        self.artifacts, self.ticket, self.actual_wire_sends = {}, None, 0
        self.expected_wire, self.expected_url = None, None
        self.frozen_config_sha = config_identity(handle.config)
        self.frozen_fingerprint = fingerprint_of_handle(handle)
        self.production_wire_sha = production_wire_sha
        self.secrets = [handle.config.apiKey, *handle.config.extraHeaders.values()]

    async def complete(self, config, request, **_):
        self.ledger.ensure_running()
        require(self.case_id in self.authorization.scope["caseIds"], "case", "case outside selected scope", "CASE_NOT_AUTHORIZED")
        require(self.handle.profile_id == self.authorization.scope["modelProfileId"] and self.handle.model_id == self.authorization.scope["modelId"], "model", "scope model differs", "MODEL_CONFIG_DRIFT")
        require(config_identity(config) == self.frozen_config_sha and fingerprint_of_handle(self.handle) == self.frozen_fingerprint, "config", "effective model parameters changed", "MODEL_CONFIG_DRIFT")
        if self.authorization.evidence_kind == "live":
            verify_live_endpoint(config)
        self.expected_wire = wire_body(config, request)
        require(sha_bytes(canonical(self.expected_wire)) == self.production_wire_sha, "wire", "request differs from original production build_request", "WIRE_DRIFT")
        protocol = getattr(config.protocol, "value", config.protocol)
        check_wire(self.expected_wire, self.frozen["source"]["personalTokens"], protocol=protocol,
                   model_payload=self.frozen["modelPayload"], system_prompt=SYSTEM_PROMPT)
        require(not any(secret and secret in canonical(self.expected_wire).decode("utf-8") for secret in self.secrets), "wire", "credential found in request body", "SECRET_ECHO")
        bound = self.proof.prove(self.authorization, self.handle, self.expected_wire)
        bound.verify(self.authorization, self.handle, self.expected_wire)
        if hasattr(self.proof, "proof_document"):
            self.artifacts["billingProof"] = write_artifact(self.directory, "billing-proof.json", self.proof.proof_document(bound))
        self.artifacts["wire"] = write_artifact(self.directory, "wire.json", self.expected_wire)
        suffix = {"openai-chat": "/chat/completions", "openai-responses": "/responses", "anthropic-messages": "/messages" if config.baseUrl.rstrip("/").endswith("/v1") else "/v1/messages"}[protocol]
        self.expected_url = config.baseUrl.rstrip("/") + suffix
        self.ticket = self.ledger.reserve(dict(caseId=self.case_id, jobId=self.job_id, jobAttempt=self.job_attempt,
            modelFingerprint=self.frozen_fingerprint, inputHash=self.input_hash, wireSHA=self.artifacts["wire"]["sha256"]), bound, self.run_label)
        try:
            transport = self.transport_factory()
            if self.authorization.evidence_kind == "live":
                verify_live_transport(transport)
            boundary = BoundaryTransport(self, transport)
            response = await self.handle.provider.complete(config, request, transport=boundary)
            raw_sha = sha_bytes(response.text.encode("utf-8"))
            self.ticket["rawSHA"] = raw_sha
            safe_record_text(response.text, secrets=self.secrets, personal_tokens=self.frozen["source"]["personalTokens"])
            self.artifacts["raw"] = write_artifact(self.directory, "raw.txt", response.text, raw=True)
            usage_doc = dict(schemaVersion=1, caseId=self.case_id, scopeSHA=self.authorization.scope_sha,
                jobId=self.job_id, jobAttempt=self.job_attempt, caseAttempt=self.ticket["caseAttempt"],
                protocol=protocol, evidenceKind=self.authorization.evidence_kind, rawUsage=boundary.raw_usage,
                normalizedUsage=None, validation={"status": "uncertain", "reason": None},
                rawSHA=raw_sha, wireSHA=self.artifacts["wire"]["sha256"])
            usage_error = None
            try:
                policy = self.proof.usage_policy() if hasattr(self.proof, "usage_policy") else None
                usage = verified_usage(boundary.raw_usage, protocol, bound, policy=policy)
                require(response.usage is not None and response.usage.inputTokens == usage["inputTokens"] and response.usage.outputTokens == usage["outputTokens"], "usage", "normalized Provider usage differs from upstream", "USAGE_UNCERTAIN")
                usage_doc.update(normalizedUsage=usage, validation={"status": "verified", "reason": None})
            except CheckError as exc:
                usage_error = exc
                usage_doc["validation"] = {"status": "out_of_bound" if exc.code == "USAGE_OUT_OF_BOUND" else "uncertain", "reason": exc.code}
            self.artifacts["usage"] = write_artifact(self.directory, "usage.json", usage_doc)
            self.ledger.response(self.ticket, raw_sha=raw_sha, usage_sha=self.artifacts["usage"]["sha256"])
            if usage_error:
                self.ledger.unknown(self.ticket, usage_error.code)
                raise usage_error
            intended = {**self.ticket, "state": "settled", "settledTokens": usage_doc["normalizedUsage"]["totalTokens"]}
            self.artifacts["attempt"] = write_artifact(self.directory, "attempt.json", intended)
            self.ledger.settle(self.ticket, usage_doc["normalizedUsage"]["totalTokens"])
            return response
        except BaseException as exc:
            reason = exc.code if isinstance(exc, CheckError) else "UNKNOWN_MODEL_RESULT"
            self.ledger.unknown(self.ticket, reason)
            if "attempt" not in self.artifacts and not (self.directory / "attempt.json").exists():
                try:
                    self.artifacts["attempt"] = write_artifact(self.directory, "attempt.json", self.ticket)
                except BaseException:
                    pass  # Existing durable reserved/dispatched state remains.
            raise

    def wrapped_handle(self):
        return replace(self.handle, provider=self)
