"""教材证据读取（TEACHING-LOOP B1 / T20 冻结签名）。

用途：知识点教材依据（``textbook_knowledge_links``）与 AI 候选的 ``textbookEvidence``
输入都在**写事务之外**经这里读取：核验教材修订存在、区间合法、并冻结当时的标题与文本
（``sha256`` 随文本一起冻结）。读取失败一律 503 ``TEXTBOOK_EVIDENCE_UNAVAILABLE``，
**绝不**当成"该知识点没有依据"或空成功（B1 任务卡 §2.5）。

- 标题：``catalog.current_metadata_revision(revision.document_id).title``；
- 文本：``source.read_normalized_text(revision)``（``rag_v2.source_text.ImmutableSource``，
  已校验字符数与 sha256 与修订登记一致）；
- 区间：``char_end <= char_start`` 或 ``char_end > revision.char_count`` → 422
  ``TEXTBOOK_EVIDENCE_INVALID``；
- 定位：``source.locate(...)`` 的可见字段（best-effort：来源映射不可用时降级为区间本身，
  文本与标题的证据性不受影响；区间才是权威）。

本模块只读，不写任何库。
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from app.contracts.knowledge import (
    TEXTBOOK_EVIDENCE_INVALID,
    TEXTBOOK_EVIDENCE_UNAVAILABLE,
)
from app.core.exceptions import AppError

logger = logging.getLogger("zhiqikeyuan.knowledge.evidence")


@dataclass(frozen=True)
class EvidenceText:
    """一次教材证据读取的冻结结果（文本 + 标题 + 可见定位）。"""

    document_revision_id: str
    char_start: int
    char_end: int
    title: str
    text: str
    sha256: str
    locator: dict[str, Any]


def evidence_unavailable(message: str) -> AppError:
    return AppError(message, code=TEXTBOOK_EVIDENCE_UNAVAILABLE, status_code=503, retryable=True)


def evidence_invalid(message: str) -> AppError:
    return AppError(message, code=TEXTBOOK_EVIDENCE_INVALID, status_code=422)


class TextbookEvidenceReader:
    """教材依据读取器：``catalog`` 是教材目录（``TextbookCatalog``），``source`` 是
    不可变文本来源（``rag_v2.source_text.ImmutableSource``）；两者都按构造注入，
    测试可整体替换为替身。"""

    def __init__(self, catalog: Any, *, source: Any) -> None:
        self._catalog = catalog
        self._source = source

    # ------------------------------------------------------------------ 读取

    def read(
        self, *, document_revision_id: str, char_start: int, char_end: int
    ) -> EvidenceText:
        revision_id = _text(document_revision_id, field="documentRevisionId")
        start = _count(char_start, field="charStart")
        end = _count(char_end, field="charEnd", minimum=1)
        if end <= start:
            raise evidence_invalid("教材证据区间必须满足 charEnd > charStart。")

        try:
            revision = self._catalog.get_revision(revision_id)
        except AppError as exc:
            raise evidence_unavailable(
                f"教材目录当前不可用，无法核验教材依据：{exc}"
            ) from exc
        if revision is None:
            raise evidence_unavailable(
                "教材修订不存在或已被删除，无法核验教材依据；"
                "请刷新教材资料库后重试，不要当作“没有依据”。"
            )
        char_count = getattr(revision, "char_count", None)
        if not isinstance(char_count, int) or isinstance(char_count, bool) or char_count < 0:
            raise evidence_unavailable("教材修订登记结构异常，无法核验教材依据。")
        if end > char_count:
            raise evidence_invalid(
                f"教材证据区间越界：该修订共 {char_count} 个字符，收到 {start}..{end}。"
            )

        try:
            normalized = self._source.read_normalized_text(revision)
        except AppError as exc:
            raise evidence_unavailable(
                f"教材规范化原文不可用，已停止使用该教材原句：{exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - 读取实现未知异常一律按不可用处理
            logger.warning("教材证据文本读取失败：%s", exc.__class__.__name__)
            raise evidence_unavailable("教材规范化原文不可用，已停止使用该教材原句。") from exc
        if not isinstance(normalized, str):
            raise evidence_unavailable("教材规范化原文读取结果非法，已停止使用该教材原句。")
        if len(normalized) < end:
            raise evidence_invalid(
                f"教材证据区间越界：该修订实际文本仅 {len(normalized)} 个字符。"
            )

        try:
            metadata = self._catalog.current_metadata_revision(revision.document_id)
        except AppError as exc:
            raise evidence_unavailable(f"教材标题当前不可读，无法冻结依据标题：{exc}") from exc
        title = getattr(metadata, "title", None)
        if not isinstance(title, str) or not title.strip():
            raise evidence_unavailable("教材标题为空，无法冻结依据标题。")

        text = normalized[start:end]
        return EvidenceText(
            document_revision_id=revision_id,
            char_start=start,
            char_end=end,
            title=title.strip(),
            text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            locator=self._locate(revision, start, end),
        )

    # ------------------------------------------------------------------ 内部

    def _locate(self, revision: Any, char_start: int, char_end: int) -> dict[str, Any]:
        """可定位信息：``charStart``/``charEnd`` 恒有；行号/页码等 best-effort。"""
        base: dict[str, Any] = {"charStart": char_start, "charEnd": char_end}
        locate = getattr(self._source, "locate", None)
        if not callable(locate):
            return base
        try:
            view = locate(revision, char_start, char_end)
        except Exception as exc:  # noqa: BLE001 - 定位失败不改变文本/标题的证据性
            logger.warning("教材证据定位失败（降级为字符区间）：%s", exc.__class__.__name__)
            return base
        if view is None:
            return base
        data: dict[str, Any] = {}
        dump = getattr(view, "model_dump", None)
        if callable(dump):
            try:
                data = dump(by_alias=True, exclude_none=True)
            except Exception:  # noqa: BLE001 - 视图形状未知时只保留区间
                data = {}
        elif isinstance(view, dict):
            data = dict(view)
        for key, value in data.items():
            if value is None or key in base:
                continue
            if isinstance(value, (str, int, float, bool)):
                base[key] = value
        return base


# --------------------------------------------------------------------------- 校验


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise evidence_invalid(f"{field} 必须是非空字符串。")
    return value.strip()


def _count(value: object, *, field: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise evidence_invalid(f"{field} 必须是不小于 {minimum} 的整数。")
    return value


__all__ = ["EvidenceText", "TextbookEvidenceReader", "evidence_invalid", "evidence_unavailable"]
