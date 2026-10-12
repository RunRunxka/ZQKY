"""R6 冻结端点（knowledge-stats / student-knowledge / distribution / report）的回归测试。

用 ``AnalysisScene`` 真实夹具（4 人 × 3 题，max=[200,300,500]，含 recorded/missing/
absent/exempt；知识点 k1/k2 的 primary 链接：i000→k1，i001→{k1,k2}，i002→k2）：

- **knowledge-stats**：按小题得分率（item_stats 同口径）以满分加权聚合到 primary
  知识点，``scoreRate`` 降序；全部小题无有效作答的知识点不出现；
- **student-knowledge**：行 = 脱敏代称（学生A…，**不是**姓名），单元无 recorded 依据
  → ``scoreRate=null``（不补 0）；
- **distribution**：学生级（全部计分小题）得分率分档 低<60% / 中 60–85% / 高≥85%；
  全 absent/无依据学生不进档；
- **report**：docx 产物（zip 魔数 ``PK``、字节>0、文件名清洗、可经
  ``ExportArtifactsService`` 下载、重复导出新产物不覆盖）；
- 未就绪报告（report_ready=0）一律 409 ``REPORT_NOT_READY``。
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.services.export_artifacts import ExportArtifactsService
from tests.analysis_support import AnalysisScene


async def _ready_scene(tmp_path) -> AnalysisScene:
    scene = AnalysisScene(tmp_path)
    await scene.ready()
    return scene


# --------------------------------------------------------------------------- knowledge-stats


async def test_knowledge_stats_weighted_primary_and_sorted(tmp_path):
    scene = await _ready_scene(tmp_path)
    run_id = scene.service.list_runs().items[0].run_id
    response = scene.service.knowledge_stats(run_id)
    items = {item.knowledge_point_id: item for item in response.items}
    # 夹具：i000(200)→k1、i001(300)→{k1,k2}、i002(500)→k2；得分样本
    #   i000: 200+200+0/缺考 → 3 人有效，率 400/600=2/3
    #   i001: 200+300/missing+300 → 3 人有效，率 800/900=8/9
    #   i002: 500+500 → 2 人有效（missing/absent 不进分母），率 1.0
    # k1 = (2/3×200 + 8/9×300) / 500 = (400/3 + 800/3)/500 = 400/500 = 0.8
    # k2 = (8/9×300 + 1.0×500) / 800 = (800/3+500)/800 ≈ 0.9583
    assert set(items) == {"k1", "k2"}
    k1, k2 = items["k1"], items["k2"]
    assert k1.score_rate == pytest.approx(0.8)
    assert k2.score_rate == pytest.approx((800 / 3 + 500) / 800)
    # k2 > k1：scoreRate 降序
    rates = [item.score_rate for item in response.items]
    assert rates == sorted(rates, reverse=True)
    assert k1.question_count == 2 and k2.question_count == 2
    # 冻结形状：items 字段集合
    dumped = response.items[0].model_dump(by_alias=True)
    assert set(dumped) == {"knowledgePointId", "name", "path", "scoreRate", "questionCount"}
    # 知识点库未注入 → path 为 null（不伪造路径）
    assert dumped["path"] is None


async def test_knowledge_stats_requires_ready(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError) as excinfo:
        scene.service.knowledge_stats(receipt.run_id)
    assert excinfo.value.code == "REPORT_NOT_READY"


# --------------------------------------------------------------------------- student-knowledge


async def test_student_knowledge_matrix_labels_and_null_cells(tmp_path):
    scene = await _ready_scene(tmp_path)
    run_id = scene.service.list_runs().items[0].run_id
    response = scene.service.student_knowledge(run_id)
    # 列 = 有 primary 链接的知识点（k1、k2），行 = 全部参测人次
    assert [kp.knowledge_point_id for kp in response.knowledge_points] == ["k1", "k2"]
    assert [row.label for row in response.students] == ["学生A", "学生B", "学生C", "学生D"]
    # 姓名不进 label（红线）
    assert all("张" not in row.label and "A" != row.label[:1] or row.label.startswith("学生") for row in response.students)
    by_label = {row.label: {cell.knowledge_point_id: cell for cell in row.cells} for row in response.students}
    # 学生A（p000，全 recorded 200/200/500）：k1=(200+200)/(200+300)=0.8；k2=200/(300)+500/500 → (200+500)/(300+500)
    a = by_label["学生A"]
    assert a["k1"].score_rate == pytest.approx(400 / 500)
    assert a["k2"].score_rate == pytest.approx(700 / 800)
    # 学生C（p002，全 absent）：全部单元 null（不补 0）
    c = by_label["学生C"]
    assert all(cell.score_rate is None for cell in c.values())
    # questionCount = 该知识点的 primary 链接小题数（不随个人变化）
    assert a["k1"].question_count == 2 and a["k2"].question_count == 2
    # 冻结形状
    dumped = response.students[0].model_dump(by_alias=True)
    assert set(dumped) == {"label", "cells"}
    assert set(dumped["cells"][0]) == {"knowledgePointId", "scoreRate", "questionCount"}


async def test_student_knowledge_requires_ready(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError) as excinfo:
        scene.service.student_knowledge(receipt.run_id)
    assert excinfo.value.code == "REPORT_NOT_READY"


# --------------------------------------------------------------------------- distribution


async def test_distribution_buckets_by_student_rate(tmp_path):
    scene = await _ready_scene(tmp_path)
    run_id = scene.service.list_runs().items[0].run_id
    response = scene.service.distribution(run_id)
    labels = [bucket.label for bucket in response.buckets]
    assert labels == ["低 (<60%)", "中 (60–85%)", "高 (≥85%)"]
    # 学生A：900/1000=0.9 → 高；学生B：500/1000=0.5 → 低；学生C：全 absent → 不进档；
    # 学生D：0+300+500=800/1000=0.8 → 中
    counts = {bucket.label: bucket.count for bucket in response.buckets}
    assert counts["低 (<60%)"] == 1 and counts["中 (60–85%)"] == 1 and counts["高 (≥85%)"] == 1
    assert sum(counts.values()) == 3  # 4 人次中全缺考的 1 人不进任何分档


async def test_distribution_requires_ready(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError) as excinfo:
        scene.service.distribution(receipt.run_id)
    assert excinfo.value.code == "REPORT_NOT_READY"


# --------------------------------------------------------------------------- HTTP 形状


async def test_new_endpoints_http_shapes(tmp_path):
    scene = await _ready_scene(tmp_path)
    run_id = scene.service.list_runs().items[0].run_id
    with scene.http_client() as client:
        stats = client.get(f"/api/v1/analysis-runs/{run_id}/knowledge-stats")
        assert stats.status_code == 200, stats.text
        assert set(stats.json()) == {"items"}
        matrix = client.get(f"/api/v1/analysis-runs/{run_id}/student-knowledge")
        assert matrix.status_code == 200
        assert set(matrix.json()) == {"knowledgePoints", "students"}
        dist = client.get(f"/api/v1/analysis-runs/{run_id}/distribution")
        assert dist.status_code == 200
        assert set(dist.json()) == {"buckets"}
        # 未就绪报告 → 409（用未就绪场景自己的 http 装配）
        other = AnalysisScene(tmp_path / "unready")
        receipt = await other.accept()
        with other.http_client() as other_client:
            blocked = other_client.get(f"/api/v1/analysis-runs/{receipt.run_id}/distribution")
            assert blocked.status_code == 409 and blocked.json()["code"] == "REPORT_NOT_READY"


# --------------------------------------------------------------------------- 报告导出


async def test_report_export_produces_managed_docx(tmp_path):
    scene = await _ready_scene(tmp_path)
    run_id = scene.service.list_runs().items[0].run_id
    from app.services.assets.store import AssetStore

    file_assets = FileAssetsRepository(scene.catalog)
    receipt = scene.service.export_report(run_id, file_assets=file_assets)
    artifact = receipt.artifact
    assert artifact.byte_size > 2
    assert artifact.file_name.endswith(".docx")
    assert "学情分析报告" in artifact.file_name
    # 下载：zip 魔数 PK + 大小一致
    service = ExportArtifactsService(scene.catalog, assets=scene.assets, file_assets=file_assets)
    view, data = service.download(artifact.artifact_id)
    assert data[:2] == b"PK" and len(data) == artifact.byte_size
    assert view.media_type.endswith("wordprocessingml.document")
    # 重复导出 → 新产物（不覆盖旧产物）
    again = scene.service.export_report(run_id, file_assets=file_assets)
    assert again.artifact.artifact_id != artifact.artifact_id
    first_view, first_data = service.download(artifact.artifact_id)
    assert first_data == data  # 旧产物仍可下载（内容寻址 blob 不覆盖）


async def test_report_export_requires_ready(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    # 未就绪先于资产检查：不传 file_assets 也应先被 REPORT_NOT_READY 拦下
    with pytest.raises(AppError) as excinfo:
        scene.service.export_report(receipt.run_id, file_assets=FileAssetsRepository(scene.catalog))
    assert excinfo.value.code == "REPORT_NOT_READY"


def test_report_filename_sanitized() -> None:
    from app.services.analysis.service import _report_filename

    report = {
        "paperTitle": '期中/数学:卷*？',
        "participants": [{"className": "三年二班"}, {"className": "三年二班"}],
    }
    name = _report_filename(report)
    # 非法字符（\/:*?"<>|）一律替换为 "-"；全角"？"是合法字符保留
    assert name == "三年二班-期中-数学-卷-？-学情分析报告.docx"
    assert not any(char in name for char in '\\/:*?"<>|')
    missing = _report_filename({"paperTitle": None, "participants": []})
    assert missing == "未记录班级-未命名试卷-学情分析报告.docx"
