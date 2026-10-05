"""One-batch controlled teaching trial CLI: explicit dry-run/live modes.

Live has no registered model proof in this revision and refuses before imports,
credential resolution or sending. Trusted hosts may use execute_case via DI
after establishing human authorization and a real model-specific billing proof.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from common import CheckError, canonical, create_output, require, sha_bytes, strict_json
from controlled_guard import AuditGuard, establish_isolation
from controlled_ledger import TrialLedger
from controlled_scope import AuthorizedScope, FixtureBillingProof

REPOSITORY = Path(__file__).resolve().parents[2]
CONTROL_NAMESPACE = REPOSITORY / "docs/qa/TEACHING-LOOP-G6-B7B-20261005/executor/control-state"
DEFAULT_CASE_SPECS = REPOSITORY / "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json"
CASE_SPEC_FILE_SHA = "353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55"


def fixed_case_pack(path):
    require(sha_bytes(Path(path).read_bytes()) == CASE_SPEC_FILE_SHA,"caseSpecs","input differs from the frozen original 15-case facts","CASE_SPEC_DRIFT")
    return strict_json(Path(path))


def fixed_case_spec(spec):
    pack = fixed_case_pack(DEFAULT_CASE_SPECS)
    original = next((x for x in pack["cases"] if x["caseId"] == spec.get("caseId")),None)
    require(original is not None and canonical(spec) == canonical(original),"caseSpec","case differs from its original frozen facts/selection","CASE_SPEC_DRIFT")


def source_shas():
    production = ["apps/api/app/services/lesson_generation/service.py", "apps/api/app/services/lesson_generation/preparation.py", "apps/api/app/services/lesson_generation/common.py",
        "apps/api/app/services/lesson_generation/validation.py", "apps/api/app/services/lesson_generation/privacy.py",
        "apps/api/app/services/jobs/engine.py", "apps/api/app/services/model_runtime.py", "apps/api/app/contracts/lesson_plans.py",
        "apps/api/app/providers/llm/base.py", "apps/api/app/providers/llm/openai_chat.py",
        "apps/api/app/providers/llm/openai_responses.py", "apps/api/app/providers/llm/anthropic_messages.py"]
    executor_paths = [*Path(__file__).parent.glob("controlled_*.py"), Path(__file__).parent/"common.py"]
    return {name:sha_bytes((REPOSITORY/name).read_bytes()) for name in production}, {
        str(path.relative_to(REPOSITORY)).replace("\\","/"):sha_bytes(path.read_bytes()) for path in executor_paths}


async def execute_case(scene, spec, authorization, ledger, directory, label, *, proof=None, apply=True):
    """Host DI seam: scene services/readers/handle are independent dependencies.

    A trusted live host must supply a live authorization, a real resolver handle,
    an externally verified BillingProof and a no-retry network transport factory.
    This CLI only supplies the explicit SourceScene/MockTransport fixture host.
    """
    fixed_case_spec(spec)
    from controlled_provider import GuardedProvider, write_artifact, wire_body
    from app.contracts.lesson_plans import LessonApplyRequest
    from app.contracts.teaching_loop import canonical_hash
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    result = dict(caseId=spec["caseId"],caseSpecSHA=sha_bytes(canonical(spec)),inputHash=None,modelFingerprint=None,jobId=None,
        jobAttempt=0,caseAttempt=0,providerSendCount=0,status="unrun",technicalStatus="unrun",teacherStatus="teacher_pending",nativeStatus="native_pending",
        artifacts={key:None for key in ("frozenInput","raw","wire","usage","attempt","job","candidate","selectedFields","applied","docx")})
    ledger.ensure_running()
    require(spec["caseId"] in authorization.scope["caseIds"],"case","case is outside selected authorization","CASE_NOT_AUTHORIZED")
    lesson_id, body = await scene.case(spec)
    before = scene.lessons.get_lesson(lesson_id)
    guard_holder = {}
    original_factory = scene.generation.executor_for
    original_resolver = scene.generation.frozen_model_resolver

    def executor_for(record):
        async def execute(job,context):
            original_request = scene.generation.build_request(job.input,scene.handle)
            guard = GuardedProvider(scene.handle,authorization=authorization,ledger=ledger,proof=proof or FixtureBillingProof(),transport_factory=scene.transport,
                case_id=spec["caseId"],job_id=job.job_id,job_attempt=job.attempt,input_hash=job.input_hash,frozen=job.input,directory=directory,run_label=label,
                production_wire_sha=sha_bytes(canonical(wire_body(scene.handle.config,original_request))))
            guard_holder["provider"] = guard
            result["artifacts"]["frozenInput"] = write_artifact(directory,"frozen-input.json",job.input)
            scene.generation.frozen_model_resolver = lambda _snapshot: guard.wrapped_handle()
            return await scene.generation.execute(job,context)
        return execute

    scene.generation.executor_for = executor_for
    try:
        receipt = await scene.lessons.generate_proposal(lesson_id,body)
        record = scene.store.get(receipt["job"]["jobId"])
        done = await scene.engine.schedule("teaching",record.job_id,executor_for(record),uses_model=True)
        result.update(inputHash=done.input_hash,modelFingerprint=done.model_snapshot["fingerprint"],jobId=done.job_id,jobAttempt=done.attempt,
                      status=done.state,technicalStatus="technical_pass" if done.state == "succeeded" else "technical_fail")
        result["artifacts"]["job"] = write_artifact(directory,"job.json",done.view().model_dump(by_alias=True,mode="json"))
        guard = guard_holder.get("provider")
        if guard:
            for key in result["artifacts"]:
                if key in guard.artifacts:
                    result["artifacts"][key] = guard.artifacts[key]
            result["providerSendCount"] = guard.actual_wire_sends
            result["caseAttempt"] = guard.ticket["caseAttempt"] if guard.ticket else 0
        if done.state == "succeeded":
            with scene.catalog.read_connection() as conn:
                candidate = json.loads(conn.execute("SELECT payload_json FROM lesson_ai_proposals WHERE id=?",(done.result["proposalId"],)).fetchone()[0])
                frozen = json.loads(conn.execute("SELECT frozen_json FROM lesson_generation_inputs WHERE job_id=?",(done.job_id,)).fetchone()[0])
            scene.generation.validate_for_apply(candidate,frozen)
            result["artifacts"]["candidate"] = write_artifact(directory,"candidate.json",candidate)
            result["artifacts"]["selectedFields"] = write_artifact(directory,"selected-fields.json",spec["selectedFields"])
            calls_before = scene.actual_wire_sends
            replay = await scene.lessons.generate_proposal(lesson_id,body)
            require(replay["replayed"] and replay["job"]["jobId"] == done.job_id and scene.actual_wire_sends == calls_before,"replay","original production receipt replay must add zero calls")
            write_artifact(directory,"replay.json",dict(replayed=True,jobId=done.job_id,providerSendDelta=0))
            if apply:
                applied = await scene.lessons.apply_proposal(lesson_id,done.result["proposalId"],LessonApplyRequest(submissionId=spec["caseId"]+"-apply",expectedRevision=before["revision"],baseRevisionId=before["currentRevisionId"],selectedFields=spec["selectedFields"]))
                after = applied["currentRevision"]["data"]
                for field,value in before["currentRevision"]["data"].items():
                    require(after[field] == (candidate["patch"][field] if field in spec["selectedFields"] else value),"applied."+field,"whole-field selection/teacher preservation failed")
                result["artifacts"]["applied"] = write_artifact(directory,"applied.json",dict(beforeData=before["currentRevision"]["data"],afterData=after,selectionActor="qa",revisionId=applied["currentRevisionId"]))
        return result
    finally:
        scene.generation.executor_for = original_factory
        scene.generation.frozen_model_resolver = original_resolver


def empty_result(mode, label, scope, known):
    production,executor = source_shas()
    selected = scope.get("caseIds",[]) if type(scope) is dict else []
    return dict(schemaVersion=1,mode=mode,evidenceKind="fixture" if mode == "dry-run" else "live",reviewLabel=label,
        scopeSHA=sha_bytes(canonical(scope)),authorizationSHA=None,selectedCaseIds=selected,unrunCaseIds=[x for x in known if x not in selected],
        productionSourceSHA=production,executorSourceSHA=executor,cases=[],stopReason=None,realModelCalls=0,fixtureWireSends=0,ledgerRef=None,technicalGate="not_run")


async def dry_run(args, pack, scope, output):
    isolated = establish_isolation()
    audit = AuditGuard(isolated,REPOSITORY).install()
    sys.path.insert(0,str(REPOSITORY/"apps/api"))
    from controlled_fixtures import SourceScene
    from controlled_provider import write_artifact
    known = [x["caseId"] for x in pack["cases"]]
    authorization = AuthorizedScope.validated(scope,known,authorization_id="fixture:"+args.fixture_authorization,evidence_kind="fixture")
    manifest = empty_result("dry-run",args.label,scope,known)
    scene = None
    try:
        with TrialLedger(CONTROL_NAMESPACE,authorization) as ledger:
            scene = SourceScene(isolated/"source",protocol=args.protocol)
            for case_id in scope["caseIds"]:
                spec = next(x for x in pack["cases"] if x["caseId"] == case_id)
                if ledger.state["stopReason"]:
                    manifest["cases"].append(dict(caseId=case_id,caseSpecSHA=sha_bytes(canonical(spec)),inputHash=None,modelFingerprint=None,jobId=None,jobAttempt=0,caseAttempt=0,providerSendCount=0,status="unrun",technicalStatus="unrun",teacherStatus="teacher_pending",nativeStatus="native_pending",artifacts={key:None for key in ("frozenInput","raw","wire","usage","attempt","job","candidate","selectedFields","applied","docx")}))
                    continue
                case_result = await execute_case(scene,spec,authorization,ledger,output/case_id,args.label)
                manifest["cases"].append(case_result)
            manifest["stopReason"] = ledger.state["stopReason"]
            manifest["fixtureWireSends"] = scene.actual_wire_sends
            manifest["ledgerRef"] = write_artifact(output,"ledger-snapshot.json",ledger.snapshot())
            for case in manifest["cases"]:
                for ref in case["artifacts"].values():
                    if ref is not None:
                        ref["file"] = Path(ref["file"]).relative_to(output.resolve()).as_posix()
            manifest["ledgerRef"]["file"] = "ledger-snapshot.json"
            manifest["technicalGate"] = "fixture_technical_pass" if all(x["technicalStatus"] == "technical_pass" for x in manifest["cases"]) else "fixture_technical_fail"
            write_artifact(output,"trial-result.json",manifest)
    finally:
        if scene is not None:
            await scene.close()
            if not (output/"trial-result.json").exists():
                write_artifact(output,"execution-failure.json",dict(schemaVersion=1,fixtureWireSends=scene.actual_wire_sends,realModelCalls=0,status="stopped",reason="EXECUTION_OR_EVIDENCE_FAILURE"))
        write_artifact(output,"guard.json",audit.report())
        audit.active = False
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",required=True,choices=("dry-run","live"))
    parser.add_argument("--scope",type=Path,required=True)
    parser.add_argument("--case-specs",type=Path,default=DEFAULT_CASE_SPECS)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--label",required=True)
    parser.add_argument("--fixture-authorization",default="offline-self-check-v1")
    parser.add_argument("--protocol",choices=("openai-chat","openai-responses","anthropic-messages"),default="openai-chat")
    parser.add_argument("--authorization",type=Path)
    args = parser.parse_args(argv)
    create_output(args.output)
    try:
        pack,scope = fixed_case_pack(args.case_specs),strict_json(args.scope)
        known = [x["caseId"] for x in pack["cases"]]
        from common import live_scope
        live_scope(scope,known)
        if args.mode == "live":
            # Do not read credentials/config/data, or treat an arbitrary supplied
            # file as human authorization. This batch has no trusted live receipt
            # or registered model-specific billing proof.
            raise CheckError("authorization" if args.authorization is None else "billingProof",
                "No verified human authorization receipt" if args.authorization is None else "No supported live model billing proof is registered", "AUTHORIZATION_MISSING" if args.authorization is None else "BILLING_BOUND_UNSUPPORTED")
        manifest = asyncio.run(dry_run(args,pack,scope,args.output))
        print(json.dumps(dict(status=manifest["technicalGate"],realModelCalls=0,fixtureWireSends=manifest["fixtureWireSends"]),ensure_ascii=False))
        return 0 if manifest["technicalGate"] == "fixture_technical_pass" else 2
    except CheckError as exc:
        failure = strict_json(args.output/"execution-failure.json") if (args.output/"execution-failure.json").exists() else {}
        payload = dict(schemaVersion=1,mode=args.mode,evidenceKind="fixture" if args.mode == "dry-run" else "live",status="refused",error=exc.as_dict(),realModelCalls=0,fixtureWireSends=failure.get("fixtureWireSends",0))
        from common import write_json
        write_json(args.output/"REFUSAL.json",payload)
        print(json.dumps(payload,ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
