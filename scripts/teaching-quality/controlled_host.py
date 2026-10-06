"""Trusted live host for the single-model controlled trial (DeepSeek v4 flash).

Trust model
-----------
The authorization anchor is the CURRENT human instruction. CTRL records it as a
receipt (``HumanAuthorizationReceipt``) outside the run's output directory; the host
refuses a receipt that lacks provenance fields, drifts from the run scope, carries
fixture-looking identities, or was not authored by CTRL. The host never treats an
arbitrary JSON, a boolean flag or a file hash as human authorization by itself.

Reads (before any run guard is installed, read-only, never logged):
- the selected profile's non-sensitive config via the production
  ``ModelConfigRepository`` (formal ``.local-data/model-config.json``);
- the selected connection's credential via the production ``SecretStore``
  (formal ``apps/api/.env``), used only inside the production resolver/Provider.

The run itself stays isolated: TEMP data root, TEMP-only SQL, no other network.
"""
from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import CheckError, canonical, live_scope, require, sha_bytes, strict_json, write_json

REPOSITORY = Path(__file__).resolve().parents[2]
FORMAL_CONFIG = REPOSITORY / ".local-data/model-config.json"
FORMAL_ENV = REPOSITORY / "apps" / "api" / ".env"
LIVE_CONTROL_NAMESPACE = REPOSITORY / "docs/qa/TEACHING-LOOP-G7-B7C-20261005/b7c/control-live"
ACCEPTED_OPTION = "B + 保留推理 + 探针"
RECEIPT_FIELDS = {"schemaVersion", "authorizationId", "at", "instruction", "acceptedOption", "probeAccepted", "scope", "provenance"}
# Trial wait policy: the production non-streaming path waits only DEFAULT_TIMEOUT_SECONDS=30
# (app/providers/llm/base.py), which a reasoning-effort=max completion exceeds. The trial
# waits longer; the waiting policy is NOT part of the wire body (unchanged), and the change
# shows up in config_identity which the run records.
TRIAL_CLIENT_WAIT_SECONDS = 300.0


@dataclass(frozen=True)
class HumanAuthorizationReceipt:
    path: Path
    authorization_id: str
    instruction: str
    accepted_option: str
    scope: dict
    scope_sha: str
    sha256: str

    @classmethod
    def load(cls, path: Path, known_cases: list[str]) -> "HumanAuthorizationReceipt":
        path = Path(path)
        require(path.is_file(), "authorization", "human authorization receipt is missing", "AUTHORIZATION_MISSING")
        document = strict_json(path)
        require(type(document) is dict, "authorization", "receipt must be a JSON object", "AUTHORIZATION_INVALID")
        require(set(document) == RECEIPT_FIELDS, "authorization", "receipt shape differs from the registered schema", "AUTHORIZATION_INVALID")
        require(document["schemaVersion"] == 1, "authorization", "unsupported receipt revision", "AUTHORIZATION_INVALID")
        require(type(document["instruction"]) is str and document["instruction"].strip(), "authorization", "verbatim instruction text required", "AUTHORIZATION_INVALID")
        require(document["acceptedOption"] == ACCEPTED_OPTION, "authorization", "accepted risk option differs from the recorded human choice", "AUTHORIZATION_INVALID")
        require(document["probeAccepted"] is True, "authorization", "probe basis acceptance missing", "AUTHORIZATION_INVALID")
        provenance = document["provenance"]
        require(type(provenance) is dict and provenance.get("recordedBy") == "CTRL" and type(provenance.get("source")) is str and provenance["source"].strip(), "authorization", "receipt provenance is missing or not authored by CTRL", "AUTHORIZATION_INVALID")
        live_scope(document["scope"], known_cases)
        require(not any(marker in document["scope"][key].lower() for key in ("modelProfileId", "modelId") for marker in ("fixture", "isolated", "mock")), "authorization", "fixture identity cannot be authorized as live", "FIXTURE_NOT_LIVE")
        scope_sha = sha_bytes(canonical(document["scope"]))
        require(document["authorizationId"] == sha_bytes(canonical({"scopeSHA": scope_sha, "acceptedOption": document["acceptedOption"], "instruction": document["instruction"]})), "authorization", "authorizationId does not bind this instruction and scope", "AUTHORIZATION_INVALID")
        return cls(path, document["authorizationId"], document["instruction"], document["acceptedOption"], json.loads(canonical(document["scope"])), scope_sha, sha_bytes(path.read_bytes()))


def record_human_authorization(path: Path, *, instruction: str, scope: dict, provenance: dict) -> HumanAuthorizationReceipt:
    """CTRL-only helper that writes the receipt from the current human instruction."""
    document = {
        "schemaVersion": 1,
        "authorizationId": sha_bytes(canonical({"scopeSHA": sha_bytes(canonical(scope)), "acceptedOption": ACCEPTED_OPTION, "instruction": instruction})),
        "at": datetime.now(timezone.utc).isoformat(),
        "instruction": instruction,
        "acceptedOption": ACCEPTED_OPTION,
        "probeAccepted": True,
        "scope": json.loads(canonical(scope)),
        "provenance": provenance,
    }
    write_json(path, document)
    return HumanAuthorizationReceipt.load(path, scope["caseIds"])


def resolve_endpoint_addresses(host: str) -> tuple[str, ...]:
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return tuple(sorted({info[4][0] for info in infos}))


@dataclass
class LiveHost:
    authorization: object
    proof: object
    handle: object
    transport_factory: object
    live_endpoint: tuple[str, tuple[str, ...]]
    receipt: HumanAuthorizationReceipt

    def verify_handle(self) -> None:
        from urllib.parse import urlsplit
        config = self.handle.config
        protocol = str(getattr(config.protocol, "value", config.protocol))
        host = (urlsplit(config.baseUrl).hostname or "").lower()
        require(protocol == "openai-chat" and host == "api.deepseek.com", "model", "resolved handle is not the registered endpoint/protocol", "MODEL_CONFIG_DRIFT")
        require(self.handle.model_id == "deepseek-flash", "model", "resolved handle is not the registered model", "MODEL_CONFIG_DRIFT")


def build_live_host(receipt_path: Path, scope: dict, known_cases: list[str], tokenizer_json: Path) -> LiveHost:
    """Read the receipt, then the selected profile/credential through production readers."""
    from controlled_scope import AuthorizedScope
    from controlled_proof import DeepseekFlashProbeProof

    receipt = HumanAuthorizationReceipt.load(receipt_path, known_cases)
    require(canonical(receipt.scope) == canonical(scope), "scope", "run scope differs from the recorded human authorization", "SCOPE_DRIFT")
    authorization = AuthorizedScope.validated(scope, known_cases, authorization_id=receipt.authorization_id,
                                              evidence_kind="live", human_verified=True)  # host verified the CTRL receipt above
    # Formal reads happen here, before any run guard, only for the selected profile.
    import sys
    sys.path.insert(0, str(REPOSITORY / "apps/api"))
    from app.core.secrets import SecretStore
    from app.repositories.model_config_repository import ModelConfigRepository
    from app.services.model_runtime import resolve_chat_model
    repository = ModelConfigRepository(FORMAL_CONFIG)
    secrets = SecretStore(FORMAL_ENV)
    handle = resolve_chat_model(repository, secrets, scope["modelProfileId"], purpose="chat")
    from dataclasses import replace as _replace
    handle = _replace(handle, config=_replace(handle.config, timeoutSeconds=TRIAL_CLIENT_WAIT_SECONDS))
    proof = DeepseekFlashProbeProof(tokenizer_json)
    import httpx2 as httpx
    host = LiveHost(authorization, proof, handle, lambda: httpx.AsyncHTTPTransport(retries=0),
                    ("api.deepseek.com", resolve_endpoint_addresses("api.deepseek.com")), receipt)
    host.verify_handle()
    return host
