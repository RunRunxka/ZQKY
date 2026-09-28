"""题库导入与校对：规则拆题、原文保留、乐观锁、拆分/合并。

全部用 ``TestClient`` + 注入替身（模型端口、临时目录），只写 pytest ``tmp_path``；
正式 ``.local-data`` / ``.env`` 与真实模型调用一律不参与。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.services.question_bank.organizer import DEFAULT_ORGANIZE_MODEL
from app.services.question_bank.service import QuestionBankService

ALLOWED_ORIGINS = frozenset({"http://127.0.0.1:5173"})
#: 替身声明的本机已安装模型；测试绝不访问真实 Ollama /api/tags
DEFAULT_LOCAL_MODELS = ("qwen2.5:7b",)
DISTRACTOR_TOP = "答题须知：本卷共四题，请在答题卡上作答，考试时间 90 分钟。"
DISTRACTOR_MID = "本卷所有选择题均为单项选择，请将所选字母填涂在答题卡相应位置。"
SAMPLE_NAME = "第三章练习.md"

SAMPLE_DOC = f"""# 第三章 练习

{DISTRACTOR_TOP}

1. 下列函数中，是一次函数的是（ ）
A. y = x^2
B. y = 2x + 1
C. y = 1/x
D. y = x^3
答案：B
解析：形如 y = kx + b（k≠0）的函数是一次函数。

2. 下列各数中，最小的数是（ ）
A. -3
B. 0
C. 1
D. 2
答案：A

{DISTRACTOR_MID}

3. 下列关于三角形的说法正确的是（ ）
A. 三条边都相等
B. 内角和为 180°
C. 有两个直角
D. 对边平行
答案：B
解析：三角形内角和定理。

4. 半径为 3 的圆的面积是 ______。
答案：9π
解析：S = πr²。
"""

#: 只有一道没有答案的选择题：用于缺答案确认路径
NO_ANSWER_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
"""


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=ALLOWED_ORIGINS,
        env="test",
        data_dir=tmp_path / "data",
        question_bank_dir=tmp_path / "question-bank",
    )


def block_ids_of(input_text: str) -> list[str]:
    return [
        line[len("[块 ") : -1]
        for line in input_text.split("\n")
        if line.startswith("[块 ") and line.endswith("]")
    ]


def organize_reply(
    block_ids: Sequence[str],
    *,
    stem: str = "整理后的题干（ ）",
    options: Sequence[dict[str, str]] | None = None,
    answer: dict[str, Any] | None = None,
    explanation: str | None = None,
    question_type: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": question_type or ("single_choice" if options else "short_answer"),
        "stem": stem,
        "options": list(options or []),
        "answer": answer,
        "explanation": explanation,
        "sourceBlockIds": list(block_ids),
    }
    return json.dumps(payload, ensure_ascii=False)


class FakeOrganizer:
    """模型端口替身：按批次返回预设回复（字符串）或抛出预设异常。"""

    def __init__(self, replies: Sequence[Any] | None = None, handler: Callable | None = None) -> None:
        self.replies = list(replies or [])
        self.handler = handler
        self.calls: list[Any] = []

    def organize(self, call):
        self.calls.append(call)
        if self.handler is not None:
            return self.handler(call)
        if self.replies:
            value = self.replies.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        blocks = block_ids_of(call.input_text)
        return organize_reply(blocks)


class FakeModelCatalog:
    """本机已安装模型清单替身：不触碰真实 Ollama /api/tags。"""

    def __init__(self, models: Sequence[str] = DEFAULT_LOCAL_MODELS, error: Exception | None = None) -> None:
        self.models = list(models)
        self.error = error
        self.calls = 0

    def installed_models(self) -> list[str]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.models)


class Harness:
    """一次测试用的完整应用：真实目录（临时文件）+ 注入替身的题库服务。"""

    def __init__(
        self,
        tmp_path: Path,
        *,
        organizer: Any | None = None,
        model_catalog: Any | None = None,
        default_model: str = DEFAULT_ORGANIZE_MODEL,
    ) -> None:
        self.settings = make_settings(tmp_path)
        self.app = create_app(self.settings)
        self.catalog: QuestionBankCatalog = self.app.state.question_bank
        assert self.catalog is not None, "题库目录未装配"
        self.organizer = organizer if organizer is not None else FakeOrganizer()
        self.model_catalog = (
            model_catalog if model_catalog is not None else FakeModelCatalog()
        )
        self.service = QuestionBankService(
            self.catalog,
            self.settings,
            organizer=self.organizer,
            model_catalog=self.model_catalog,
            default_model=default_model,
        )
        self.app.state.question_bank_service = self.service
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    # -------------------------------------------------------------- 便捷方法

    def upload(self, data: bytes | str, *, name: str = SAMPLE_NAME, **fields: str):
        payload = data.encode("utf-8") if isinstance(data, str) else data
        return self.client.post(
            "/api/v1/question-imports",
            files={"file": (name, payload, "text/markdown")},
            data=fields or None,
        )

    def import_detail(self, import_id: str) -> dict:
        response = self.client.get(f"/api/v1/question-imports/{import_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def sample_detail(self, **fields: str) -> dict:
        response = self.upload(SAMPLE_DOC, **fields)
        assert response.status_code == 201, response.text
        return response.json()

    def patch_draft(self, draft: dict, **overrides: Any):
        payload = review_payload(draft, **overrides)
        return self.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json=payload)

    def block_texts(self, import_id: str) -> list[str]:
        return [block.text for block in self.catalog.list_source_blocks(import_id)]


def review_payload(
    draft: dict,
    *,
    review_state: str = "reviewed",
    acknowledge: bool | None = None,
    content: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "expectedRevision": draft["revision"],
        "content": content if content is not None else draft["content"],
        "metadata": metadata if metadata is not None else draft["metadata"],
        "reviewState": review_state,
    }
    if acknowledge is not None:
        payload["missingAnswerAcknowledged"] = acknowledge
    return payload


def open_harness(tmp_path: Path, **kwargs: Any) -> Harness:
    return Harness(tmp_path, **kwargs)


@pytest.fixture()
def harness(tmp_path: Path):
    instance = Harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- 1/2


def test_import_splits_sample_document_and_keeps_unassigned(harness: Harness) -> None:
    detail = harness.sample_detail(subjectId="math", gradeId="senior-1")

    assert detail["state"] == "needs_review"
    assert detail["draftCount"] == 4
    assert [draft["content"]["type"] for draft in detail["drafts"]] == [
        "single_choice",
        "single_choice",
        "single_choice",
        "fill_blank",
    ]
    for draft in detail["drafts"]:
        assert draft["reviewState"] == "needs_review"
        assert draft["extractionMethod"] == "rule"
        assert draft["metadata"]["subjectId"] == "math"
        assert draft["metadata"]["gradeId"] == "senior-1"

    first = detail["drafts"][0]["content"]
    assert first["stemMarkdown"] == "下列函数中，是一次函数的是（ ）"
    assert [(item["key"], item["textMarkdown"]) for item in first["options"]] == [
        ("A", "y = x^2"),
        ("B", "y = 2x + 1"),
        ("C", "y = 1/x"),
        ("D", "y = x^3"),
    ]
    assert first["answer"]["choiceKeys"] == ["B"]
    assert first["answer"]["accepted"] is None
    assert first["answer"]["textMarkdown"] is None
    assert first["explanationMarkdown"] == "形如 y = kx + b（k≠0）的函数是一次函数。"

    second = detail["drafts"][1]["content"]
    assert second["stemMarkdown"] == "下列各数中，最小的数是（ ）"
    assert second["answer"]["choiceKeys"] == ["A"]
    assert second["explanationMarkdown"] is None

    third = detail["drafts"][2]["content"]
    assert third["stemMarkdown"] == "下列关于三角形的说法正确的是（ ）"
    assert third["answer"]["choiceKeys"] == ["B"]
    assert third["explanationMarkdown"] == "三角形内角和定理。"

    fourth = detail["drafts"][3]["content"]
    assert fourth["type"] == "fill_blank"
    assert fourth["stemMarkdown"] == "半径为 3 的圆的面积是 ______。"
    assert fourth["options"] == []
    assert fourth["answer"]["textMarkdown"] == "9π"
    assert fourth["explanationMarkdown"] == "S = πr²。"

    # 干扰段落必须出现在 unassignedBlocks，且原文可在 question_source_blocks 查到
    unassigned_texts = [block["text"] for block in detail["unassignedBlocks"]]
    assert DISTRACTOR_TOP in unassigned_texts
    assert DISTRACTOR_MID in unassigned_texts
    assert detail["unassignedCount"] == len(detail["unassignedBlocks"])
    stored_texts = harness.block_texts(detail["importId"])
    assert DISTRACTOR_TOP in stored_texts
    assert DISTRACTOR_MID in stored_texts

    # 未归属块没有任何草稿 span 指向它（不硬塞进题目）
    assigned_blocks = {
        span["blockId"] for draft in detail["drafts"] for span in draft["sourceSpans"]
    }
    unassigned_blocks = {block["blockId"] for block in detail["unassignedBlocks"]}
    assert assigned_blocks & unassigned_blocks == set()


def test_source_blocks_are_never_dropped(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    expected = len(SAMPLE_DOC.split("\n"))
    assert len(harness.catalog.list_source_blocks(import_id)) == expected

    # 编辑、拆分、合并之后行数只增不减，原文一条不丢
    before_ids = {item["draftId"] for item in detail["drafts"]}
    draft = detail["drafts"][0]
    assert harness.patch_draft(draft).status_code == 200
    current = harness.import_detail(import_id)["drafts"][0]
    spans = current["sourceSpans"]
    offset = (min(span["charStart"] for span in spans) + max(span["charEnd"] for span in spans)) // 2
    split = harness.client.post(
        f"/api/v1/question-imports/{import_id}/split",
        params={"draftId": current["draftId"]},
        json={"expectedRevision": current["revision"], "charOffset": offset},
    )
    assert split.status_code == 200, split.text
    after_split = split.json()
    new_ids = [
        item["draftId"]
        for item in after_split["drafts"]
        if item["draftId"] not in before_ids and item["reviewState"] != "excluded"
    ]
    assert len(new_ids) == 2
    revisions = {
        item["draftId"]: item["revision"] for item in after_split["drafts"] if item["draftId"] in new_ids
    }
    merge = harness.client.post(
        f"/api/v1/question-imports/{import_id}/merge", json={"expectedRevisions": revisions}
    )
    assert merge.status_code == 200, merge.text

    assert len(harness.catalog.list_source_blocks(import_id)) == expected
    assert len(merge.json()["unassignedBlocks"]) == len(detail["unassignedBlocks"])


# ------------------------------------------------------------------------------- 3


def test_editing_reviewed_draft_returns_to_needs_review(harness: Harness) -> None:
    detail = harness.sample_detail()
    draft = detail["drafts"][0]

    # 只改 reviewState：不触发回退
    reviewed = harness.patch_draft(draft)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewState"] == "reviewed"
    assert reviewed.json()["revision"] == 1

    # 编辑已校对草稿：强制回到 needs_review
    edited_content = copy.deepcopy(draft["content"])
    edited_content["stemMarkdown"] = "改写后的题干（ ）"
    edited = harness.patch_draft(reviewed.json(), content=edited_content)
    assert edited.status_code == 200, edited.text
    assert edited.json()["reviewState"] == "needs_review"
    assert edited.json()["revision"] == 2
    assert edited.json()["content"]["stemMarkdown"] == "改写后的题干（ ）"

    # 即使同一次请求显式传 reviewed，内容变化也不保留已校对状态
    further = copy.deepcopy(edited_content)
    further["explanationMarkdown"] = "再次改写的解析。"
    again = harness.patch_draft(
        edited.json(), content=further, review_state="reviewed"
    )
    assert again.status_code == 200
    assert again.json()["reviewState"] == "needs_review"

    # 过期 revision：409 且保留用户编辑
    stale = harness.patch_draft(draft)
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"


# ------------------------------------------------------------------------------- 4


def test_split_and_merge_spans(harness: Harness) -> None:
    detail = harness.sample_detail()
    import_id = detail["importId"]
    draft = detail["drafts"][0]
    spans = draft["sourceSpans"]
    start = min(span["charStart"] for span in spans)
    end = max(span["charEnd"] for span in spans)
    offset = (start + end) // 2

    before_ids = {item["draftId"] for item in detail["drafts"]}
    split = harness.client.post(
        f"/api/v1/question-imports/{import_id}/split",
        params={"draftId": draft["draftId"]},
        json={"expectedRevision": draft["revision"], "charOffset": offset},
    )
    assert split.status_code == 200, split.text
    after = split.json()
    new_drafts = [
        item
        for item in after["drafts"]
        if item["draftId"] not in before_ids and item["reviewState"] != "excluded"
    ]
    assert len(new_drafts) == 2
    left, right = sorted(
        new_drafts, key=lambda item: min(span["charStart"] for span in item["sourceSpans"])
    )
    left_end = max(span["charEnd"] for span in left["sourceSpans"])
    right_start = min(span["charStart"] for span in right["sourceSpans"])
    assert left_end <= right_start
    assert min(span["charStart"] for span in left["sourceSpans"]) == start
    assert max(span["charEnd"] for span in right["sourceSpans"]) == end
    # 原草稿保留但已排除，不再参与确认
    origin = [item for item in after["drafts"] if item["draftId"] == draft["draftId"]][0]
    assert origin["reviewState"] == "excluded"

    before_merge_ids = {item["draftId"] for item in after["drafts"]}
    merge = harness.client.post(
        f"/api/v1/question-imports/{import_id}/merge",
        json={
            "expectedRevisions": {
                left["draftId"]: left["revision"],
                right["draftId"]: right["revision"],
            }
        },
    )
    assert merge.status_code == 200, merge.text
    merged_detail = merge.json()
    created = [
        item
        for item in merged_detail["drafts"]
        if item["draftId"] not in before_merge_ids and item["reviewState"] != "excluded"
    ]
    assert len(created) == 1
    merged = created[0]
    assert min(span["charStart"] for span in merged["sourceSpans"]) == start
    assert max(span["charEnd"] for span in merged["sourceSpans"]) == end
    # 合并取并集：每个 blockId 的区间覆盖两侧
    left_ranges = {span["blockId"]: (span["charStart"], span["charEnd"]) for span in left["sourceSpans"]}
    for span in merged["sourceSpans"]:
        if span["blockId"] in left_ranges:
            left_start, left_end_span = left_ranges[span["blockId"]]
            assert span["charStart"] <= left_start
            assert span["charEnd"] >= left_end_span
    excluded_ids = {
        item["draftId"] for item in merged_detail["drafts"] if item["reviewState"] == "excluded"
    }
    assert {left["draftId"], right["draftId"]} <= excluded_ids

    # 冲突：用过期的 revision 再合并一次
    conflict = harness.client.post(
        f"/api/v1/question-imports/{import_id}/merge",
        json={
            "expectedRevisions": {
                left["draftId"]: left["revision"],
                right["draftId"]: right["revision"],
            }
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] in {"REVISION_CONFLICT", "DRAFT_EXCLUDED"}


# ------------------------------------------------------------------------------ 11


def test_unsupported_format_is_422(harness: Harness) -> None:
    response = harness.upload(b"whatever", name="notes.rtf")
    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_DOCUMENT_FORMAT"


def test_missing_file_part_is_422(harness: Harness) -> None:
    response = harness.client.post(
        "/api/v1/question-imports", files={"other": ("a.md", b"x", "text/markdown")}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_import_bad_metadata_json_is_422(harness: Harness) -> None:
    response = harness.client.post(
        "/api/v1/question-imports",
        files={"file": (SAMPLE_NAME, SAMPLE_DOC.encode("utf-8"), "text/markdown")},
        data={"metadataJson": "{not json"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize("limit", [0, 201])
def test_import_list_limit_bounds(harness: Harness, limit: int) -> None:
    response = harness.client.get("/api/v1/question-imports", params={"limit": limit})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_upload_above_limit_is_413(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import question_bank as route_module
    from app.services.question_bank import service as service_module

    monkeypatch.setattr(route_module, "MAX_UPLOAD_BYTES", 16)
    monkeypatch.setattr(service_module, "MAX_UPLOAD_BYTES", 16)
    response = harness.upload(b"0123456789abcdefghij", name="big.md")
    assert response.status_code == 413
    assert response.json()["code"] == "DOCUMENT_TOO_LARGE"


def test_large_declared_content_length_is_413(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1 import question_bank as route_module

    monkeypatch.setattr(route_module, "MAX_UPLOAD_BYTES", 8)
    # multipart 体积本身超过 上限 + 头部开销：解析前直接拒绝
    response = harness.upload(b"x" * 5000, name="big.md")
    assert response.status_code == 413
    assert response.json()["code"] == "DOCUMENT_TOO_LARGE"


def test_import_list_and_missing_import(harness: Harness) -> None:
    detail = harness.sample_detail()
    listing = harness.client.get("/api/v1/question-imports")
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["imports"]) == 1
    summary = body["imports"][0]
    assert summary["importId"] == detail["importId"]
    assert summary["draftCount"] == 4
    assert summary["uploadedFileName"] == SAMPLE_NAME
    assert summary["unassignedCount"] == len(detail["unassignedBlocks"])

    missing = harness.client.get("/api/v1/question-imports/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "IMPORT_NOT_FOUND"


def test_rule_splitter_supports_alternative_question_markers() -> None:
    """题号标记覆盖 第1题 / 一、 / （1）；无法归属的答案行不硬塞给上一题。"""
    from app.services.question_bank import rules

    text = """第1题 下列说法正确的是（ ）
A. 甲
B. 乙
答案：A

一、地球是圆的吗？

（1）水的化学式是 ______。
答案：H₂O
"""
    blocks: list[rules.RuleBlock] = []
    cursor = 0
    for index, line in enumerate(text.split("\n")):
        blocks.append(
            rules.RuleBlock(
                block_id=f"b{index}", text=line, char_start=cursor, char_end=cursor + len(line)
            )
        )
        cursor += len(line) + 1
    drafts = rules.split_questions(blocks)
    assert len(drafts) == 3
    assert drafts[0].content["type"] == "single_choice"
    assert drafts[0].content["stemMarkdown"] == "下列说法正确的是（ ）"
    assert drafts[0].content["answer"]["choiceKeys"] == ["A"]
    assert drafts[1].content["type"] == "other"
    assert drafts[1].content["stemMarkdown"] == "地球是圆的吗？"
    assert drafts[1].content["answer"] is None
    assert drafts[2].content["type"] == "fill_blank"
    assert drafts[2].content["answer"]["textMarkdown"] == "H₂O"
