"""Correct-behavior trial oracles, with actual production chain/HTTP adapters."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
import sys
import uuid
import atexit
from dataclasses import replace
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0,str(TOOLS))
from controlled_guard import establish_isolation, AuditGuard
ISOLATION = establish_isolation("zqky-controlled-tests-")
AUDIT = AuditGuard(ISOLATION,ROOT).install()
def final_guard():
    output = os.environ.get("CONTROLLED_GUARD_OUTPUT")
    if output:
        Path(output).write_text(json.dumps(AUDIT.report(),ensure_ascii=False,indent=2),encoding="utf-8")
atexit.register(final_guard)
sys.path.insert(0,str(ROOT/"apps/api"))
from common import CheckError, canonical, sha_bytes
from controlled_scope import AuthorizedScope, BillingBound, FixtureBillingProof, UnsupportedLiveProof
from controlled_ledger import TrialLedger, ExclusiveLock
from controlled_provider import GuardedProvider, BoundaryTransport, verified_usage, wire_body, verify_live_transport, verify_live_endpoint
from controlled_fixtures import SourceScene
from controlled_trial import execute_case, fixed_case_pack, fixed_case_spec, DEFAULT_CASE_SPECS
import httpx2 as httpx

PACK = json.loads((ROOT/"docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json").read_bytes())
SPEC = PACK["cases"][0]


def authorization(*, tokens=100000, attempts=2, cases=None, identity=None):
    return AuthorizedScope.validated(dict(modelProfileId="controlled-fixture-profile",modelId="controlled-fixture-model",
        caseIds=cases or ["C01"],sampleCount=len(cases or ["C01"]),maxAttempts=attempts,maxTotalTokens=tokens),[x["caseId"] for x in PACK["cases"]],
        authorization_id=identity or "fixture:"+uuid.uuid4().hex,evidence_kind="fixture")


def identity(case="C01"):
    return dict(caseId=case,jobId="owned-job",jobAttempt=1,modelFingerprint="sha256:"+"f"*64,inputHash="a"*64,wireSHA="b"*64)


def bound(tokens=10):
    return BillingBound("controlled-fixture-model","controlled-fixture-profile","c"*64,"fixture",tokens,0,0,0,{"fixture":True})


def test_scope_source_lists_are_deep_copied_and_mutation_is_refused(tmp_path):
    original = authorization()
    source = copy.deepcopy(original.scope)
    auth = AuthorizedScope.validated(source,["C01","C02"],authorization_id="fixture:immutable",evidence_kind="fixture")
    source["caseIds"].append("C02")
    assert auth.scope["caseIds"] == ["C01"]
    with TrialLedger(tmp_path,auth) as ledger:
        auth.scope["maxTotalTokens"] = 999999
        with pytest.raises(CheckError,match="mutated"):
            ledger.reserve(identity(),bound(),"later-label")
        assert ledger.state["tickets"] == []


def test_opened_scope_mutation_cannot_move_ledger_authorization(tmp_path):
    auth = authorization()
    with TrialLedger(tmp_path,auth) as ledger:
        ledger.state["scope"]["maxAttempts"] = 99
        with pytest.raises(CheckError) as error:
            ledger.reserve(identity(),bound(),"label")
        assert error.value.code == "SCOPE_DRIFT"


def test_same_authorization_scope_drift_preserves_original_ledger(tmp_path):
    auth = authorization(identity="fixture:same")
    with TrialLedger(tmp_path,auth) as ledger:
        ticket = ledger.reserve(identity(),bound(),"first")
        ledger.dispatch(ticket)
        ledger.response(ticket,raw_sha="e"*64,usage_sha="d"*64)
        ledger.settle(ticket,5)
        path = ledger.path
    old = path.read_bytes()
    drift = authorization(identity="fixture:same",tokens=200000)
    with pytest.raises(CheckError) as error:
        with TrialLedger(tmp_path,drift): pass
    assert error.value.code == "SCOPE_DRIFT" and path.read_bytes() == old


@pytest.mark.parametrize("mutation",[
    lambda t:t.update(reservedTokens=-1),lambda t:t.update(reservedTokens=True),
    lambda t:t.pop("jobId"),lambda t:t.update(settledTokens=-3),lambda t:t.update(settledTokens=True),
    lambda t:t.update(settledTokens=999),lambda t:t.update(caseAttempt=2),lambda t:t.update(providerSendCount=True),
    lambda t:t.update(state="unknown",settledTokens=5),lambda t:t.update(scopeSHA="0"*64)])
def test_corrupt_ledger_never_credits_budget_or_recreates_empty(tmp_path,mutation):
    auth = authorization()
    with TrialLedger(tmp_path,auth) as ledger:
        ticket = ledger.reserve(identity(),bound(),"first")
        ledger.dispatch(ticket)
        ledger.response(ticket,raw_sha="e"*64,usage_sha="d"*64)
        ledger.settle(ticket,5)
        path = ledger.path
        state = ledger.snapshot()
    mutation(state["tickets"][0])
    path.write_bytes(canonical(state))
    corrupt = path.read_bytes()
    with pytest.raises(CheckError) as error:
        with TrialLedger(tmp_path,auth): pass
    assert error.value.code == "LEDGER_CORRUPT" and path.read_bytes() == corrupt


@pytest.mark.parametrize("state",["reserved","dispatched","responded"])
def test_restart_unsettled_keeps_reservation_and_stops(tmp_path,state):
    auth = authorization()
    with TrialLedger(tmp_path,auth) as ledger:
        ticket = ledger.reserve(identity(),bound(),"first")
        if state != "reserved": ledger.dispatch(ticket)
        if state == "responded": ledger.response(ticket,raw_sha="e"*64,usage_sha="d"*64)
    with TrialLedger(tmp_path,auth) as restarted:
        assert restarted.state["tickets"][0]["state"] == "unknown" and restarted.committed() == 10
        with pytest.raises(CheckError) as error: restarted.reserve(identity(),bound(),"restart")
        assert error.value.code == "TRIAL_STOPPED"


def test_changed_label_carries_attempt_limit_and_settled_budget(tmp_path):
    auth = authorization(tokens=15,attempts=1)
    with TrialLedger(tmp_path,auth) as ledger:
        ticket = ledger.reserve(identity(),bound(),"first")
        ledger.dispatch(ticket)
        ledger.response(ticket,raw_sha="e"*64,usage_sha="d"*64)
        ledger.settle(ticket,7)
    with TrialLedger(tmp_path,auth) as ledger:
        assert ledger.committed() == 7
        with pytest.raises(CheckError) as error: ledger.reserve(identity(),bound(),"completely-new-label")
        assert error.value.code == "ATTEMPTS_EXHAUSTED" and len(ledger.state["tickets"]) == 1


def test_last_case_insufficient_upper_refuses_before_dispatch(tmp_path):
    auth = authorization(tokens=15,cases=["C01","C02"])
    with TrialLedger(tmp_path,auth) as ledger:
        ticket = ledger.reserve(identity(),bound(),"first")
        ledger.dispatch(ticket)
        ledger.response(ticket,raw_sha="e"*64,usage_sha="d"*64)
        ledger.settle(ticket,7)
        with pytest.raises(CheckError) as error: ledger.reserve(identity("C02"),bound(),"last")
        assert error.value.code == "BUDGET_INSUFFICIENT" and ledger.state["attempts"] == {"C01":1}


def test_real_os_lock_same_process_and_separate_process(tmp_path):
    lock = tmp_path/"owner.lock"
    with ExclusiveLock(lock):
        with pytest.raises(CheckError) as error:
            with ExclusiveLock(lock): pass
        assert error.value.code == "LEDGER_BUSY"
        code = "import sys;sys.path.insert(0,"+repr(str(TOOLS))+");from controlled_ledger import ExclusiveLock;from common import CheckError\ntry:\n with ExclusiveLock("+repr(str(lock))+"):sys.exit(9)\nexcept CheckError as e:sys.exit(0 if e.code=='LEDGER_BUSY' else 8)"
        process = subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
        assert process.returncode == 0,process.stderr
    with ExclusiveLock(lock): pass


@pytest.mark.parametrize("raw",[None,{}, {"prompt_tokens":1}, {"prompt_tokens":-1,"completion_tokens":1},
    {"prompt_tokens":True,"completion_tokens":1},{"prompt_tokens":1,"completion_tokens":False},
    {"prompt_tokens":1.0,"completion_tokens":1},{"prompt_tokens":1,"completion_tokens":1,"total_tokens":3},
    {"prompt_tokens":1,"completion_tokens":1,"total_tokens":True},
    {"prompt_tokens":1,"completion_tokens":1,"reasoning_tokens":1}])
def test_usage_invalid_never_settles(raw):
    with pytest.raises(CheckError) as error: verified_usage(raw,"openai-chat",bound(10))
    assert error.value.code in {"USAGE_UNCERTAIN","USAGE_OUT_OF_BOUND"}


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol",["openai-chat","openai-responses","anthropic-messages"])
async def test_actual_production_chain_adapter_wire_prompt_and_receipt_replay(tmp_path,protocol):
    scene = SourceScene(tmp_path/"scene",protocol)
    auth = authorization(attempts=1)
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            result = await execute_case(scene,SPEC,auth,ledger,tmp_path/"result","production")
            assert result["technicalStatus"] == "technical_pass" and scene.actual_wire_sends == result["providerSendCount"] == 1
            assert ledger.committed() == 200 and result["caseAttempt"] == 1
            wire = json.loads(Path(result["artifacts"]["wire"]["file"]).read_bytes())
            assert [wire[k] for k in ("max_tokens","max_output_tokens","max_completion_tokens") if k in wire] == [4096]
            candidate = json.loads(Path(result["artifacts"]["candidate"]["file"]).read_bytes())
            assert [x["minutes"] for x in candidate["budget"]["stages"]] != SPEC["stageMinutes"]
            applied = json.loads(Path(result["artifacts"]["applied"]["file"]).read_bytes())
            for field in ("title","totalLessons","currentLessonNo","lessonTypes","otherTypeText","reflection"):
                assert applied["beforeData"][field] == applied["afterData"][field]
            assert applied["selectionActor"] == "qa"
            frozen = json.loads(Path(result["artifacts"]["frozenInput"]["file"]).read_bytes())
            assert frozen["source"]["questions"] and all(x not in canonical(wire).decode("utf-8") for x in frozen["source"]["personalTokens"])
    finally: await scene.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure",["bad_json","invalid_structure","length","missing_usage","negative_usage","bool_usage","inconsistent_usage","over_upper","secret_echo","timeout"])
async def test_real_response_failures_retain_send_usage_or_reservation_and_stop(tmp_path,failure):
    scene = SourceScene(tmp_path/"scene")
    auth = authorization(cases=["C01","C02"])
    original_case = scene.case
    async def prepare(spec):
        result = await original_case(spec)
        if failure == "bad_json": scene.response_text = "{"
        if failure == "invalid_structure": scene.response_text = '{"patch":{},"budget":{}}'
        if failure == "length": scene.finish = "length"
        if failure == "missing_usage": scene.usage = {}
        if failure == "negative_usage": scene.usage = {"prompt_tokens":-1,"completion_tokens":10}
        if failure == "bool_usage": scene.usage = {"prompt_tokens":True,"completion_tokens":10}
        if failure == "inconsistent_usage": scene.usage = {"prompt_tokens":5,"completion_tokens":10,"total_tokens":99}
        if failure == "over_upper": scene.usage = {"prompt_tokens":1001,"completion_tokens":10}
        if failure == "secret_echo": scene.response_text = scene.handle.config.apiKey
        if failure == "timeout":
            scene.delay = .1
            scene.handle = replace(scene.handle,config=replace(scene.handle.config,timeoutSeconds=.02))
        return result
    scene.case = prepare
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            result = await execute_case(scene,SPEC,auth,ledger,tmp_path/"result",failure,apply=False)
            assert result["technicalStatus"] == "technical_fail" and scene.actual_wire_sends == result["providerSendCount"] == 1
            ticket = ledger.state["tickets"][0]
            if failure in {"bad_json","invalid_structure","length"}:
                assert ticket["state"] == "settled" and ticket["settledTokens"] == 200 and result["artifacts"]["usage"]
                assert result["artifacts"]["raw"] and not result["artifacts"]["candidate"]
            else:
                assert ticket["state"] == "unknown" and ledger.committed() == 5096 and ledger.state["stopReason"]
                with pytest.raises(CheckError): ledger.reserve(identity("C02"),bound(),"next")
            if failure == "secret_echo":
                assert result["artifacts"]["raw"] is None
                assert all(scene.handle.config.apiKey not in p.read_text(encoding="utf-8") for p in (tmp_path/"result").glob("*.json"))
    finally: await scene.close()


@pytest.mark.asyncio
async def test_cancellation_keeps_unknown_reservation(tmp_path):
    scene = SourceScene(tmp_path/"scene")
    auth = authorization()
    original_case = scene.case
    async def prepare(spec):
        result = await original_case(spec)
        scene.delay = 1
        return result
    scene.case = prepare
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            task = asyncio.create_task(execute_case(scene,SPEC,auth,ledger,tmp_path/"result","cancel",apply=False))
            await asyncio.wait_for(scene.started.wait(),5)
            await scene.engine.shutdown()
            with pytest.raises(asyncio.CancelledError): await task
            assert scene.actual_wire_sends == 1 and ledger.committed() == 5096 and ledger.state["stopReason"]
            assert ledger.state["tickets"][0]["state"] == "unknown"
    finally: await scene.close()


@pytest.mark.parametrize("field,value",[("modelId","other"),("modelProfileId","other"),("caseIds",["C02"]),("maxCostCny",1)])
@pytest.mark.asyncio
async def test_scope_model_case_cost_mismatch_never_reaches_wire(tmp_path,field,value):
    scene = SourceScene(tmp_path/"scene")
    changed = authorization().scope
    changed[field] = value
    auth = AuthorizedScope.validated(changed,["C01","C02"],authorization_id="fixture:"+uuid.uuid4().hex,evidence_kind="fixture")
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            if field == "caseIds":
                with pytest.raises(CheckError): await execute_case(scene,SPEC,auth,ledger,tmp_path/"result","drift")
            else:
                result = await execute_case(scene,SPEC,auth,ledger,tmp_path/"result","drift")
                assert result["technicalStatus"] == "technical_fail"
            assert scene.actual_wire_sends == 0 and not ledger.state["tickets"]
    finally: await scene.close()


def test_live_missing_authorization_and_fixture_identity_hard_refuse():
    auth = authorization()
    with pytest.raises(CheckError) as error:
        AuthorizedScope.validated(auth.scope,["C01"],authorization_id="live",evidence_kind="live")
    assert error.value.code == "AUTHORIZATION_MISSING"
    with pytest.raises(CheckError) as error:
        AuthorizedScope.validated(auth.scope,["C01"],authorization_id="live",evidence_kind="live",human_verified=True)
    assert error.value.code == "FIXTURE_NOT_LIVE"
    with pytest.raises(CheckError) as error: UnsupportedLiveProof().prove(None,None,{})
    assert error.value.code == "BILLING_BOUND_UNSUPPORTED"


@pytest.mark.asyncio
async def test_internal_second_actual_http_send_is_blocked(tmp_path):
    auth = authorization()
    calls = []
    class Owner:
        pass
    with TrialLedger(tmp_path/"state",auth) as ledger:
        owner = Owner()
        owner.ledger,owner.authorization,owner.expected_wire,owner.expected_url = ledger,auth,{"model":"x"},"https://fixture.invalid/one"
        owner.directory = tmp_path
        owner.secrets,owner.frozen = [],{"source":{"personalTokens":[]}}
        owner.artifacts = {"wire":{"sha256":"d"*64}}
        owner.actual_wire_sends = 0
        owner.ticket = ledger.reserve(identity(),bound(),"wire")
        transport = BoundaryTransport(owner,httpx.MockTransport(lambda request:(calls.append(request) or httpx.Response(307,json={"usage":{}}))))
        request = httpx.Request("POST",owner.expected_url,json=owner.expected_wire)
        await transport.handle_async_request(request)
        with pytest.raises(CheckError) as error: await transport.handle_async_request(request)
        assert error.value.code == "MULTIPLE_SENDS_FORBIDDEN" and len(calls) == owner.actual_wire_sends == 1


@pytest.mark.asyncio
async def test_response_evidence_write_failure_keeps_full_reservation(tmp_path,monkeypatch):
    import controlled_provider
    scene = SourceScene(tmp_path/"scene")
    auth = authorization()
    original = controlled_provider.write_artifact
    def fail(directory,name,value,**kwargs):
        if name == "usage.json": raise OSError("fixture journal failure contains no raw upstream")
        return original(directory,name,value,**kwargs)
    monkeypatch.setattr(controlled_provider,"write_artifact",fail)
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            result = await execute_case(scene,SPEC,auth,ledger,tmp_path/"result","journal",apply=False)
            assert result["technicalStatus"] == "technical_fail" and scene.actual_wire_sends == 1
            assert ledger.committed() == 5096 and ledger.state["stopReason"] and ledger.state["tickets"][0]["state"] == "unknown"
    finally: await scene.close()


@pytest.mark.parametrize("mutation",[
    lambda t:t.update(state="reserved",settledTokens=None),
    lambda t:t.update(state="unknown",settledTokens=None),
    lambda t:t.update(rawSHA=None),lambda t:t.update(usageSHA=None),
    lambda t:t.update(inputHash="wrong"),lambda t:t.update(schemaVersion=True),
    lambda t:t.update(state="dispatched",settledTokens=None,providerSendCount=0)])
def test_corrupt_state_send_or_evidence_identity_refuses(tmp_path,mutation):
    auth = authorization()
    with TrialLedger(tmp_path,auth) as ledger:
        ticket = ledger.reserve(identity(),bound(),"first")
        ledger.dispatch(ticket)
        ledger.response(ticket,raw_sha="e"*64,usage_sha="d"*64)
        ledger.settle(ticket,5)
        path,state = ledger.path,ledger.snapshot()
    mutation(state["tickets"][0])
    path.write_bytes(canonical(state))
    with pytest.raises(CheckError) as error:
        with TrialLedger(tmp_path,auth): pass
    assert error.value.code == "LEDGER_CORRUPT"


@pytest.mark.asyncio
@pytest.mark.parametrize("change",["cap","message","config","model"])
async def test_final_request_and_handle_drift_sends_zero(tmp_path,monkeypatch,change):
    from app.providers.llm.base import LLMMessage
    scene = SourceScene(tmp_path/"scene")
    auth = authorization()
    original = GuardedProvider.complete
    async def altered(owner,config,request,**kwargs):
        if change == "cap": request = replace(request,maxOutputTokens=1)
        if change == "message": request = replace(request,messages=[*request.messages,LLMMessage("user","学生实名张三 电话13812345678")])
        if change == "config": config = replace(config,baseUrl="https://another.invalid/v1")
        if change == "model": owner.handle = replace(owner.handle,model_id="different-model")
        return await original(owner,config,request,**kwargs)
    monkeypatch.setattr(GuardedProvider,"complete",altered)
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            result = await execute_case(scene,SPEC,auth,ledger,tmp_path/"result",change,apply=False)
            assert result["technicalStatus"] == "technical_fail" and scene.actual_wire_sends == 0 and not ledger.state["tickets"]
    finally: await scene.close()


@pytest.mark.asyncio
async def test_known_json_failure_explicit_next_run_carries_attempts_then_exhausts(tmp_path):
    auth = authorization(attempts=2)
    with TrialLedger(tmp_path/"state",auth) as ledger:
        for attempt in (1,2,3):
            scene = SourceScene(tmp_path/("scene"+str(attempt)))
            original = scene.case
            async def broken(spec):
                result = await original(spec)
                scene.response_text = "{broken"
                return result
            scene.case = broken
            try:
                result = await execute_case(scene,SPEC,auth,ledger,tmp_path/("result"+str(attempt)),"label"+str(attempt),apply=False)
                assert result["technicalStatus"] == "technical_fail"
                assert scene.actual_wire_sends == (1 if attempt <= 2 else 0)
                assert len(ledger.state["tickets"]) == min(attempt,2)
                assert ledger.committed() == 200*min(attempt,2) and ledger.state["stopReason"] is None
            finally: await scene.close()


@pytest.mark.asyncio
async def test_production_last_case_insufficient_upper_preserves_first(tmp_path):
    auth = authorization(tokens=5295,cases=["C01","C02"])
    scene = SourceScene(tmp_path/"scene")
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            first = await execute_case(scene,PACK["cases"][0],auth,ledger,tmp_path/"first","first")
            last = await execute_case(scene,PACK["cases"][1],auth,ledger,tmp_path/"last","last")
            assert first["technicalStatus"] == "technical_pass" and last["technicalStatus"] == "technical_fail"
            assert scene.actual_wire_sends == 1 and last["providerSendCount"] == 0 and ledger.committed() == 200
            assert ledger.state["attempts"] == {"C01":1}
    finally: await scene.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage",["reservation","attempt-evidence"])
async def test_reservation_and_postsend_log_failures_stop_conservatively(tmp_path,monkeypatch,stage):
    import controlled_provider
    scene = SourceScene(tmp_path/"scene")
    auth = authorization()
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            if stage == "reservation":
                def fail():
                    ledger.poisoned = True
                    raise CheckError("ledger","controlled reservation write failure","JOURNAL_FAILED")
                monkeypatch.setattr(ledger,"_write",fail)
            else:
                original = controlled_provider.write_artifact
                def fail(directory,name,value,**kwargs):
                    if name == "attempt.json": raise OSError("controlled attempt evidence write failure")
                    return original(directory,name,value,**kwargs)
                monkeypatch.setattr(controlled_provider,"write_artifact",fail)
            result = await execute_case(scene,SPEC,auth,ledger,tmp_path/"result",stage,apply=False)
            assert result["technicalStatus"] == "technical_fail"
            assert scene.actual_wire_sends == (0 if stage == "reservation" else 1)
            assert ledger.committed() == 5096
            assert ledger.poisoned if stage == "reservation" else bool(ledger.state["stopReason"])
    finally: await scene.close()


@pytest.mark.asyncio
async def test_source_gap_fixture_production_chain_and_teacher_pending(tmp_path):
    spec = next(x for x in PACK["cases"] if x["caseId"] == "C09")
    scene = SourceScene(tmp_path/"scene")
    auth = authorization(cases=["C09"])
    try:
        with TrialLedger(tmp_path/"state",auth) as ledger:
            result = await execute_case(scene,spec,auth,ledger,tmp_path/"result","gap")
            assert result["technicalStatus"] == "technical_pass" and scene.actual_wire_sends == 1
            frozen = json.loads(Path(result["artifacts"]["frozenInput"]["file"]).read_bytes())
            assert frozen["source"]["questions"] == []
            assert result["teacherStatus"] == "teacher_pending" and result["nativeStatus"] == "native_pending"
    finally: await scene.close()


@pytest.mark.asyncio
async def test_live_transport_proof_interface_rejects_fixture_and_hidden_retries():
    mock = httpx.MockTransport(lambda _:httpx.Response(200))
    retry = httpx.AsyncHTTPTransport(retries=1,trust_env=False)
    plain = httpx.AsyncHTTPTransport(retries=0,trust_env=False)
    class Custom(httpx.AsyncHTTPTransport): pass
    custom = Custom(retries=0,trust_env=False)
    try:
        for bad in (mock,retry,custom):
            with pytest.raises(CheckError): verify_live_transport(bad)
        verify_live_transport(plain)
        from types import SimpleNamespace
        for url in ("http://127.0.0.1:9/v1","https://127.0.0.1/v1","https://localhost/v1","https://server.invalid:9/v1"):
            with pytest.raises(CheckError): verify_live_endpoint(SimpleNamespace(baseUrl=url))
        verify_live_endpoint(SimpleNamespace(baseUrl="https://model.invalid/v1"))
    finally:
        for transport in (mock,retry,plain,custom): await transport.aclose()


@pytest.mark.parametrize("field,value",[("caseId","unknown"),("requirements","changed"),("selectedFields",["keyPoints"]),("expectedTargetCounts",[])])
def test_fixed_case_facts_cannot_be_substituted(field,value):
    spec = copy.deepcopy(SPEC)
    spec[field] = value
    with pytest.raises(CheckError) as error: fixed_case_spec(spec)
    assert error.value.code == "CASE_SPEC_DRIFT"


def test_fixed_case_file_accepts_exact_copy_and_rejects_reformat_or_mutation(tmp_path):
    path = tmp_path/"cases.json"
    path.write_bytes(DEFAULT_CASE_SPECS.read_bytes())
    assert fixed_case_pack(path) == PACK
    path.write_bytes(canonical(PACK))
    with pytest.raises(CheckError) as error: fixed_case_pack(path)
    assert error.value.code == "CASE_SPEC_DRIFT"


def test_cost_only_budget_without_pricing_proof_is_explicitly_unsupported(tmp_path):
    scope = authorization().scope
    scope.pop("maxTotalTokens")
    scope["maxCostCny"] = 10
    auth = AuthorizedScope.validated(scope,["C01"],authorization_id="fixture:cost-only",evidence_kind="fixture")
    with pytest.raises(CheckError) as error:
        with TrialLedger(tmp_path,auth): pass
    assert error.value.code == "COST_BOUND_UNSUPPORTED"
