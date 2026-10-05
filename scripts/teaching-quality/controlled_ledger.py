"""Durable conservative reservations and one OS owner per authorization.

CLI namespace is fixed in controlled_trial; output labels never select state.
An authorization, not a scope hash, selects the ledger. Scope drift is refused.
"""
from __future__ import annotations

import copy
import json
import os
import uuid
from contextlib import AbstractContextManager
from pathlib import Path

from common import CheckError, canonical, require, sha_bytes, strict_json


class ExclusiveLock(AbstractContextManager):
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            self.stream = None
            raise CheckError("ledger.lock", "another executor owns this authorization", "LEDGER_BUSY") from exc
        return self

    def __exit__(self, *_):
        if self.stream is not None:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
            self.stream = None


class TrialLedger(AbstractContextManager):
    def __init__(self, namespace, authorization):
        self.authorization = authorization
        self.directory = Path(namespace) / sha_bytes(authorization.authorization_id.encode("utf-8"))
        self.path = self.directory / "ledger.json"
        self.lock = ExclusiveLock(self.directory / "owner.lock")
        self.state = None
        self.poisoned = False

    def __enter__(self):
        self.lock.__enter__()
        try:
            require("maxTotalTokens" in self.authorization.scope,"budget","cost-only accounting has no verified price proof","COST_BOUND_UNSUPPORTED")
            if self.path.exists():
                self.state = strict_json(self.path)
                require(self.state.get("schemaVersion") == 1 and self.state.get("authorizationId") == self.authorization.authorization_id, "ledger", "ledger identity corrupt", "LEDGER_CORRUPT")
                require(self.state.get("scopeSHA") == self.authorization.scope_sha and self.state.get("scope") == self.authorization.scope, "scope", "same authorization has a different immutable scope", "SCOPE_DRIFT")
                require(self.state.get("evidenceKind") == self.authorization.evidence_kind, "ledger", "evidence kind drift", "SCOPE_DRIFT")
                self._validate_state()
                for ticket in self.state["tickets"]:
                    require(ticket.get("state") in {"reserved", "dispatched", "responded", "unknown", "settled"}, "ledger", "unknown ticket state", "LEDGER_CORRUPT")
                    if ticket["state"] in {"reserved", "dispatched", "responded"}:
                        ticket["state"] = "unknown"
                        self.state["stopReason"] = "RESTART_UNSETTLED_RESERVATION"
                self._write()
            else:
                self.state = {"schemaVersion": 1, "authorizationId": self.authorization.authorization_id,
                    "scopeSHA": self.authorization.scope_sha, "scope": copy.deepcopy(self.authorization.scope),
                    "evidenceKind": self.authorization.evidence_kind, "stopReason": None, "attempts": {}, "tickets": []}
                self._write()
            return self
        except BaseException:
            self.lock.__exit__()
            raise

    def __exit__(self, *_):
        self.lock.__exit__()

    def _write(self):
        if self.poisoned:
            raise CheckError("ledger", "prior journal write failed; executor stopped", "JOURNAL_FAILED")
        payload = canonical(self.state) + b"\n"
        temporary = self.directory / ("ledger-"+uuid.uuid4().hex+".pending")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            require(self.path.read_bytes() == payload, "ledger", "durable write readback differs", "JOURNAL_FAILED")
        except BaseException as exc:
            self.poisoned = True
            raise CheckError("ledger", "reservation/response journal failed; no further sending", "JOURNAL_FAILED") from exc

    def _validate_state(self):
        state = self.state
        require(set(state) == {"schemaVersion", "authorizationId", "scopeSHA", "scope", "evidenceKind", "stopReason", "attempts", "tickets"} and type(state["schemaVersion"]) is int and state["schemaVersion"] == 1, "ledger", "ledger fields corrupt", "LEDGER_CORRUPT")
        require(type(state.get("tickets")) is list and type(state.get("attempts")) is dict and (state.get("stopReason") is None or type(state.get("stopReason")) is str), "ledger", "ledger shape corrupt", "LEDGER_CORRUPT")
        counts, ids = {}, set()
        fields = {"schemaVersion", "ticketId", "caseId", "jobId", "jobAttempt", "modelFingerprint", "inputHash", "wireSHA", "scopeSHA", "caseAttempt", "reservedTokens", "settledTokens", "providerSendCount", "state", "boundProofSHA", "runLabel", "rawSHA", "usageSHA"}
        for ticket in state["tickets"]:
            require(type(ticket) is dict and set(ticket) == fields and type(ticket["schemaVersion"]) is int and ticket["schemaVersion"] == 1, "ledger.ticket", "ticket fields corrupt", "LEDGER_CORRUPT")
            require(ticket["ticketId"] not in ids and ticket["caseId"] in self.authorization.scope["caseIds"] and ticket["scopeSHA"] == self.authorization.scope_sha, "ledger.ticket", "ticket identity corrupt", "LEDGER_CORRUPT")
            ids.add(ticket["ticketId"])
            for key in ("ticketId", "jobId", "modelFingerprint", "inputHash", "wireSHA", "boundProofSHA", "runLabel"):
                require(type(ticket[key]) is str and bool(ticket[key]), "ledger.ticket."+key, "ticket identity corrupt", "LEDGER_CORRUPT")
            for key in ("jobAttempt", "caseAttempt", "reservedTokens"):
                require(type(ticket[key]) is int and ticket[key] > 0, "ledger.ticket."+key, "invalid integer", "LEDGER_CORRUPT")
            require(type(ticket["providerSendCount"]) is int and ticket["providerSendCount"] in {0, 1}, "ledger.ticket", "send count corrupt", "LEDGER_CORRUPT")
            expected = counts.get(ticket["caseId"], 0) + 1
            require(ticket["caseAttempt"] == expected and expected <= self.authorization.scope["maxAttempts"], "ledger.ticket", "attempt sequence corrupt", "LEDGER_CORRUPT")
            counts[ticket["caseId"]] = expected
            require(ticket["state"] in {"reserved", "dispatched", "responded", "unknown", "settled"}, "ledger.ticket", "state corrupt", "LEDGER_CORRUPT")
            require((ticket["state"] != "reserved" or ticket["providerSendCount"] == 0) and (ticket["state"] not in {"dispatched", "responded", "settled"} or ticket["providerSendCount"] == 1), "ledger.ticket", "state/send count inconsistent", "LEDGER_CORRUPT")
            require(ticket["state"] != "unknown" or bool(state["stopReason"]), "ledger.ticket", "unknown ticket must stop authorization", "LEDGER_CORRUPT")
            settled = ticket["settledTokens"]
            require((ticket["state"] == "settled" and type(settled) is int and 0 <= settled <= ticket["reservedTokens"] and ticket["providerSendCount"] == 1) or (ticket["state"] != "settled" and settled is None), "ledger.ticket", "invalid settlement", "LEDGER_CORRUPT")
            for key in ("inputHash", "wireSHA", "boundProofSHA", "scopeSHA", "rawSHA", "usageSHA"):
                require(ticket[key] is None or (type(ticket[key]) is str and len(ticket[key]) == 64 and all(c in "0123456789abcdef" for c in ticket[key])), "ledger.ticket", "artifact SHA corrupt", "LEDGER_CORRUPT")
            require(ticket["state"] not in {"responded", "settled"} or (ticket["rawSHA"] is not None and ticket["usageSHA"] is not None), "ledger.ticket", "response evidence identity missing", "LEDGER_CORRUPT")
        require(counts == state["attempts"] and all(type(x) is int and x > 0 for x in state["attempts"].values()), "ledger.attempts", "attempts do not match persisted tickets", "LEDGER_CORRUPT")
        require(self.committed() <= self.authorization.scope["maxTotalTokens"], "ledger.budget", "ledger exceeds immutable cap", "LEDGER_CORRUPT")

    def ensure_running(self):
        self.authorization.assert_frozen()
        require(not self.poisoned and self.state is not None, "ledger", "ledger not writable", "JOURNAL_FAILED")
        require(self.state["scope"] == self.authorization.scope and self.state["scopeSHA"] == self.authorization.scope_sha, "scope", "opened ledger scope drift", "SCOPE_DRIFT")
        self._validate_state()
        require(not self.state["stopReason"], "ledger", "uncertain previous attempt stops this authorization", "TRIAL_STOPPED")

    def committed(self):
        return sum(t["settledTokens"] if t["state"] == "settled" else t["reservedTokens"] for t in self.state["tickets"])

    def reserve(self, identity, bound, run_label):
        self.ensure_running()
        require(type(bound.total_upper) is int and bound.total_upper > 0, "proof", "reservation upper must be a positive integer", "BILLING_BOUND_UNSUPPORTED")
        case_id = identity["caseId"]
        require(case_id in self.authorization.scope["caseIds"], "case", "case outside selected authorization", "CASE_NOT_AUTHORIZED")
        count = self.state["attempts"].get(case_id, 0)
        require(type(count) is int and count >= 0, "ledger.attempts", "invalid attempts", "LEDGER_CORRUPT")
        require(count < self.authorization.scope["maxAttempts"], "attempt", "case attempt limit exhausted", "ATTEMPTS_EXHAUSTED")
        require(self.committed() + bound.total_upper <= self.authorization.scope["maxTotalTokens"], "budget", "remaining total budget cannot reserve this proven upper bound", "BUDGET_INSUFFICIENT")
        ticket = {"schemaVersion": 1, "ticketId": uuid.uuid4().hex, **identity,
            "scopeSHA": self.authorization.scope_sha, "caseAttempt": count+1,
            "reservedTokens": bound.total_upper, "settledTokens": None, "providerSendCount": 0,
            "state": "reserved", "boundProofSHA": bound.proof_sha, "runLabel": run_label,
            "rawSHA": None, "usageSHA": None}
        self.state["attempts"][case_id] = count+1
        self.state["tickets"].append(ticket)
        self._write()
        return ticket

    def dispatch(self, ticket):
        self.ensure_running()
        require(ticket["state"] == "reserved" and ticket["providerSendCount"] == 0, "wire", "internal retry/redirect/additional send forbidden", "MULTIPLE_SENDS_FORBIDDEN")
        ticket["state"] = "dispatched"
        ticket["providerSendCount"] = 1
        self._write()

    def response(self, ticket, *, raw_sha, usage_sha):
        ticket.update(state="responded", rawSHA=raw_sha, usageSHA=usage_sha)
        self._write()

    def settle(self, ticket, usage):
        require(ticket["state"] == "responded" and ticket["rawSHA"] is not None and ticket["usageSHA"] is not None, "usage", "cannot settle without durable response evidence", "USAGE_UNCERTAIN")
        require(type(usage) is int and 0 <= usage <= ticket["reservedTokens"], "usage", "verified usage exceeds reservation", "USAGE_OUT_OF_BOUND")
        ticket.update(state="settled", settledTokens=usage)
        self._write()

    def unknown(self, ticket, reason):
        if ticket is not None and ticket["state"] != "settled":
            ticket["state"] = "unknown"
        self.state["stopReason"] = reason
        if not self.poisoned:
            self._write()

    def snapshot(self):
        return copy.deepcopy(self.state)
