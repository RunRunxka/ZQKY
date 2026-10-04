import json
import os
import platform
import time
from pathlib import Path
from app.services.analysis.aggregate import aggregate
from app.services.analysis.snapshot import read_facts
from tests.analysis_support import AnalysisScene


async def test_200_students_100_leaves_complete_evidence_and_real_http_pages(tmp_path):
    seed_started = time.perf_counter()
    scene = AnalysisScene(tmp_path, participant_count=200, leaf_count=100)
    seed_ms = (time.perf_counter() - seed_started) * 1000
    read_started = time.perf_counter()
    facts = read_facts(scene.catalog, "assessment", scene.request(), "local")
    read_ms = (time.perf_counter() - read_started) * 1000
    calculation_ms = []
    for _ in range(2):
        started = time.perf_counter()
        result = aggregate(facts)
        calculation_ms.append((time.perf_counter() - started) * 1000)
    assert len(result["students"]) == 1000 and len(result["classes"]) == 5
    assert len(facts["cells"]) == 20000 and max(calculation_ms) < 3000
    accept_started = time.perf_counter()
    receipt = await scene.accept()
    accept_ms = (time.perf_counter() - accept_started) * 1000
    job_started = time.perf_counter()
    job = await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    job_ms = (time.perf_counter() - job_started) * 1000
    assert job.state == "succeeded" and scene.count("analysis_evidence") == 20000
    assert scene.count("analysis_item_snapshots") == 100 and scene.count("analysis_participants") == 200
    pages_started = time.perf_counter()
    seen, cells = set(), set()
    with scene.http_client() as client:
        url = f"/api/v1/analysis-runs/{receipt.run_id}/evidence"
        for offset in range(0, 20000, 200):
            response = client.get(url, params={"offset": offset, "limit": 200})
            assert response.status_code == 200, response.text
            page = response.json()
            assert page["total"] == 20000 and page["offset"] == offset and page["limit"] == 200
            assert len(page["items"]) == 200
            for row in page["items"]:
                assert row["evidenceId"] not in seen
                seen.add(row["evidenceId"])
                cells.add((row["participant"]["participantId"], row["itemId"]))
                assert row["content"]["stemBlocks"] == scene.rich["stemBlocks"] and row["sharedMaterials"] == scene.rich["sharedMaterials"]
                assert row["assets"] == scene.rich["assets"] and row["participant"]["className"] is None
        assert len(seen) == len(cells) == 20000
        assert cells == {(pid, iid) for pid in scene.participant_ids for iid in scene.item_ids}
        assert client.get(url, params={"knowledgePointId": "k0", "limit": 200}).json()["total"] == 4000
        assert client.get(url, params={"participantId": "p000", "limit": 200}).json()["total"] == 100
        assert client.get(url, params={"classId": "class", "offset": 20000}).json()["items"] == []
    metrics = {"sample": {"selectedStudents": 200, "leaves": 100, "cells": 20000, "allHttpEvidenceRows": len(seen),
                          "pages": 100, "normalizedRichItems": 100},
               "hardware": {"platform": platform.platform(), "processor": platform.processor(), "logicalCpuCount": os.cpu_count(), "python": platform.python_version()},
               "timingsMs": {"seed": seed_ms, "fixedRead": read_ms, "pureAggregateCold": calculation_ms[0],
                             "pureAggregateWarm": calculation_ms[1], "acceptReadHashAssetAndTxn": accept_ms,
                             "jobAggregateAndSameTxnPublication": job_ms, "allHttpPagesAndFilters": (time.perf_counter() - pages_started) * 1000},
               "target": {"pureAggregateLimitMs": 3000, "passed": max(calculation_ms) < 3000}, "fixtureRoot": str(tmp_path),
               "reportJobAtomicResult": job.result, "reportReady": True, "completeCartesianMatrix": True}
    print("ANALYSIS_PERFORMANCE=" + json.dumps(metrics, ensure_ascii=False))
    evidence_dir = os.environ.get("ZQKY_ANALYSIS_EVIDENCE_DIR")
    if evidence_dir:
        Path(evidence_dir, os.environ["ZQKY_ANALYSIS_RUN_LABEL"] + "-performance.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
