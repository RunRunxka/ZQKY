"""规则拆题：按题号起始行切分题干/选项/答案/解析，并保留无法归属的原文。

判定顺序（固定、可测试）：
1. 段落 = 空行分隔的连续非空行（markdown 每行一个原文块；pdf 每页、docx 每段再按行拆）；
2. 行内先按"答案 / 解析"标记切成「未标注文本 + 标注段」；标注段一律归入当前草稿；
3. 未标注文本按题号 / 选项正则判定：命中题号开始新草稿，命中选项归入当前题；
4. 无任何标记的独立段落：紧跟当前草稿且不以句末标点收尾时视为续行，否则整段保留为未归属原文；
5. 未归属行不进入任何草稿的 ``source_spans``，因此不会被打包进 AI 整理或确认入库，
   但原文块本身始终保存在 ``question_source_blocks``，可由导入详情读回。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

SENTENCE_ENDS = ("。", "！", "？", "；", "!", "?", ";", "…")

_QUESTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[（(]\s*\d{1,3}\s*[)）]\s*"),
    re.compile(r"^第\s*\d{1,3}\s*题\s*[.、．:：]?\s*"),
    re.compile(r"^\d{1,3}\s*[.、．)）]\s*(?!\d)"),
    re.compile(r"^[（(]\s*[一二三四五六七八九十]{1,3}\s*[)）]\s*"),
    re.compile(r"^[一二三四五六七八九十]{1,3}\s*[、.．]\s*"),
)

_OPTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?P<key>[A-Ha-h])\s*[.、．)）]\s*(?P<text>\S.*)$"),
    re.compile(r"^[（(]\s*(?P<key>[A-Ha-h])\s*[)）]\s*(?P<text>\S.*)$"),
)

_ANSWER_LABELS = ("参考答案", "答案")
_EXPLANATION_LABELS = ("解析", "详解")
_MARKER_BOUNDARY = " \t\u3000。；;，,、：:（(【《\"'"

_BLANK_MARKER = re.compile(r"_{2,}|＿{2,}|（\s{0,4}）|\(\s{0,4}\)")
_CHOICE_KEYS_ONLY = re.compile(r"^[A-Ha-h](?:\s*[、,，/．.]?\s*[A-Ha-h])*$")
_TRUE_WORDS = frozenset({"正确", "对", "是", "√", "t", "true", "yes"})
_FALSE_WORDS = frozenset({"错误", "错", "否", "×", "x", "f", "false", "no"})


@dataclass(frozen=True)
class RuleBlock:
    block_id: str
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class RuleLine:
    block_id: str
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class SplitDraft:
    content: dict[str, Any]
    source_spans: list[dict[str, Any]]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Segment:
    label: str | None
    text: str


def blocks_from_records(records: Iterable[Any]) -> list[RuleBlock]:
    """把仓储原文块记录映射为规则输入；locator 缺 charStart/charEnd 时按文本长度兜底。"""
    blocks: list[RuleBlock] = []
    for record in records:
        locator = getattr(record, "locator", None) or {}
        text = getattr(record, "text", "") or ""
        start = locator.get("charStart")
        end = locator.get("charEnd")
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            start = 0
        if not isinstance(end, int) or isinstance(end, bool) or end < start:
            end = start + len(text)
        blocks.append(
            RuleBlock(
                block_id=str(getattr(record, "block_id", "")),
                text=text,
                char_start=start,
                char_end=end,
            )
        )
    return blocks


def lines_from_blocks(blocks: Sequence[RuleBlock]) -> list[RuleLine]:
    lines: list[RuleLine] = []
    for block in blocks:
        cursor = block.char_start
        for raw_line in block.text.split("\n"):
            lines.append(
                RuleLine(
                    block_id=block.block_id,
                    text=raw_line,
                    char_start=cursor,
                    char_end=cursor + len(raw_line),
                )
            )
            cursor += len(raw_line) + 1
    return lines


def split_segments(text: str) -> list[Segment]:
    """把一行切成「未标注文本 + 答案/解析标注段」；标注段按出现顺序排列。"""
    hits: list[tuple[int, int, str]] = []
    for label, tokens in (("answer", _ANSWER_LABELS), ("explanation", _EXPLANATION_LABELS)):
        for token in tokens:
            start = 0
            while True:
                index = text.find(token, start)
                if index < 0:
                    break
                if _is_marker_position(text, index, len(token)):
                    hits.append((index, len(token), label))
                    break
                start = index + 1
    if not hits:
        return [Segment(label=None, text=text)]
    hits.sort(key=lambda item: (item[0], -item[1]))
    ordered: list[tuple[int, int, str]] = []
    for index, length, label in hits:
        if ordered and index < ordered[-1][0] + ordered[-1][1]:
            continue
        ordered.append((index, length, label))
    segments: list[Segment] = [Segment(label=None, text=text[: ordered[0][0]])]
    for position, (index, length, label) in enumerate(ordered):
        end = ordered[position + 1][0] if position + 1 < len(ordered) else len(text)
        body = text[index + length : end]
        body = body.lstrip("】]")
        stripped = body.lstrip()
        if stripped[:1] in (":", "："):
            body = stripped[1:]
        segments.append(Segment(label=label, text=body))
    return segments


def _is_marker_position(text: str, index: int, length: int) -> bool:
    if index > 0 and text[index - 1] not in _MARKER_BOUNDARY:
        return False
    tail = text[index + length :].lstrip("】]").lstrip()
    if not tail:
        return True
    return tail[0] in ":："


def match_question(text: str) -> re.Match[str] | None:
    for pattern in _QUESTION_PATTERNS:
        match = pattern.match(text)
        if match is not None:
            return match
    return None


def match_option(text: str) -> re.Match[str] | None:
    for pattern in _OPTION_PATTERNS:
        match = pattern.match(text)
        if match is not None:
            return match
    return None


def parse_answer_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {"choiceKeys": [], "accepted": None, "textMarkdown": None}
    if _CHOICE_KEYS_ONLY.match(stripped):
        keys = [character.upper() for character in stripped if character.isalpha()]
        if 0 < len(keys) <= 26:
            return {"choiceKeys": keys, "accepted": None, "textMarkdown": None}
    lowered = stripped.casefold()
    if lowered in _TRUE_WORDS:
        return {"choiceKeys": [], "accepted": True, "textMarkdown": None}
    if lowered in _FALSE_WORDS:
        return {"choiceKeys": [], "accepted": False, "textMarkdown": None}
    return {"choiceKeys": [], "accepted": None, "textMarkdown": stripped}


def infer_type(stem: str, options: Sequence[dict[str, str]], answer: dict[str, Any] | None) -> str:
    if options:
        if answer and len(answer.get("choiceKeys") or []) > 1:
            return "multiple_choice"
        return "single_choice"
    has_blank = bool(_BLANK_MARKER.search(stem))
    if answer and answer.get("accepted") is not None:
        return "true_false"
    if answer and answer.get("textMarkdown"):
        return "fill_blank" if has_blank else "short_answer"
    return "fill_blank" if has_blank else "other"


def split_questions(blocks: Sequence[RuleBlock]) -> list[SplitDraft]:
    """按规则拆题；无法归属的行不进任何草稿（由调用方按 spans 判定未归属块）。"""
    paragraphs = _group_paragraphs(lines_from_blocks(blocks))
    drafts: list[SplitDraft] = []
    builder: _Builder | None = None
    for paragraph in paragraphs:
        skip_paragraph = (
            builder is not None
            and not _paragraph_has_marker(paragraph)
            and not _looks_continuation(paragraph)
        )
        if skip_paragraph:
            continue
        for line in paragraph:
            segments = split_segments(line.text)
            head = segments[0].text.strip()
            labeled = [segment for segment in segments if segment.label is not None]
            if head:
                question = match_question(head)
                if question is not None:
                    if builder is not None:
                        drafts.append(builder.build())
                    builder = _Builder()
                    builder.consume(line)
                    rest = head[question.end() :].strip()
                    if rest:
                        builder.stem_lines.append(rest)
                else:
                    option = match_option(head)
                    if builder is not None:
                        builder.consume(line)
                        if option is not None:
                            builder.add_option(option.group("key"), option.group("text"))
                        else:
                            builder.append_text(head)
            for segment in labeled:
                if builder is None:
                    continue
                builder.consume(line)
                if segment.label == "answer":
                    builder.add_answer(segment.text)
                else:
                    builder.add_explanation(segment.text)
    if builder is not None:
        drafts.append(builder.build())
    return [draft for draft in drafts if draft is not None]


def drafts_from_lines(lines: Sequence[RuleLine]) -> list[SplitDraft]:
    blocks = [
        RuleBlock(
            block_id=line.block_id,
            text=line.text,
            char_start=line.char_start,
            char_end=line.char_end,
        )
        for line in lines
        if line.text.strip()
    ]
    if not blocks:
        return []
    return split_questions(blocks)


def fallback_draft(lines: Sequence[RuleLine]) -> SplitDraft:
    """拆分后某一半没有题号时的兜底草稿：保留原文文本，类型待人工确认。"""
    text = "\n".join(line.text for line in lines).strip()
    if not text:
        text = "（原文未识别题干）"
    return SplitDraft(
        content={
            "type": "other",
            "stemMarkdown": text,
            "options": [],
            "answer": None,
            "explanationMarkdown": None,
            "assetIds": [],
        },
        source_spans=spans_from_lines(lines),
        warnings=("未能按题号识别为独立题目，已按原文保留，需人工整理。",),
    )


def cut_lines(
    lines: Sequence[RuleLine], offset: int
) -> tuple[list[RuleLine], list[RuleLine]]:
    """按 charOffset 切断行序列；跨切点的行按字符切开，两侧区间精确相接。"""
    left: list[RuleLine] = []
    right: list[RuleLine] = []
    for line in lines:
        if line.char_end <= offset:
            left.append(line)
            continue
        if line.char_start >= offset:
            right.append(line)
            continue
        split_at = offset - line.char_start
        head_text = line.text[:split_at]
        tail_text = line.text[split_at:]
        if head_text:
            left.append(
                RuleLine(
                    block_id=line.block_id,
                    text=head_text,
                    char_start=line.char_start,
                    char_end=offset,
                )
            )
        if tail_text:
            right.append(
                RuleLine(
                    block_id=line.block_id,
                    text=tail_text,
                    char_start=offset,
                    char_end=line.char_end,
                )
            )
    return left, right


def spans_from_lines(lines: Sequence[RuleLine]) -> list[dict[str, Any]]:
    spans: list[tuple[str, int, int]] = []
    for line in lines:
        if line.char_end <= line.char_start:
            continue
        span = (line.block_id, line.char_start, line.char_end)
        if spans and spans[-1] == span:
            continue
        if spans and spans[-1][0] == span[0] and spans[-1][2] == span[1]:
            spans[-1] = (span[0], spans[-1][1], span[2])
            continue
        spans.append(span)
    return [
        {"blockId": block_id, "charStart": start, "charEnd": end}
        for block_id, start, end in spans
    ]


def line_touches_spans(line: RuleLine, spans: Sequence[dict[str, Any]]) -> bool:
    for span in spans:
        if span.get("blockId") != line.block_id:
            continue
        start = span.get("charStart")
        end = span.get("charEnd")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < line.char_end and end > line.char_start:
            return True
    return False


# ------------------------------------------------------------------ 内部实现


class _Builder:
    def __init__(self) -> None:
        self.spans: list[tuple[str, int, int]] = []
        self.raw_lines: list[str] = []
        self.stem_lines: list[str] = []
        self.options: list[dict[str, str]] = []
        self.answer_lines: list[str] = []
        self.explanation_lines: list[str] = []
        self.section = "stem"

    def consume(self, line: RuleLine) -> None:
        self.raw_lines.append(line.text)
        if line.char_end <= line.char_start:
            return
        span = (line.block_id, line.char_start, line.char_end)
        if self.spans and self.spans[-1] == span:
            return
        if self.spans and self.spans[-1][0] == span[0] and self.spans[-1][2] == span[1]:
            self.spans[-1] = (span[0], self.spans[-1][1], span[2])
            return
        self.spans.append(span)

    def append_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.section == "answer":
            self.answer_lines.append(text)
        elif self.section == "explanation":
            self.explanation_lines.append(text)
        elif self.section == "option":
            if self.options:
                self.options[-1]["textMarkdown"] = (
                    f"{self.options[-1]['textMarkdown']} {text}".strip()
                )
            else:
                self.stem_lines.append(text)
        else:
            self.stem_lines.append(text)

    def add_option(self, key: str, text: str) -> None:
        self.options.append({"key": key.upper(), "textMarkdown": text.strip()})
        self.section = "option"

    def add_answer(self, text: str) -> None:
        stripped = text.strip()
        if stripped:
            self.answer_lines.append(stripped)
        self.section = "answer"

    def add_explanation(self, text: str) -> None:
        stripped = text.strip()
        if stripped:
            self.explanation_lines.append(stripped)
        self.section = "explanation"

    def build(self) -> SplitDraft:
        stem = "\n".join(self.stem_lines).strip()
        warnings: list[str] = []
        if not stem:
            stem = "\n".join(self.raw_lines).strip() or "（原文未识别题干）"
            warnings.append("未识别到题干文本，已按原文保留，需人工整理。")
        options = self._unique_options()
        answer_text = "\n".join(self.answer_lines).strip()
        parsed_answer = parse_answer_text(answer_text) if answer_text else None
        explanation = "\n".join(self.explanation_lines).strip() or None
        question_type = infer_type(stem, options, parsed_answer)
        if parsed_answer is None:
            warnings.append("原文未提供答案，需要人工补全或标记“原文未提供答案”。")
        return SplitDraft(
            content={
                "type": question_type,
                "stemMarkdown": stem,
                "options": options,
                "answer": parsed_answer,
                "explanationMarkdown": explanation,
                "assetIds": [],
            },
            source_spans=[
                {"blockId": block_id, "charStart": start, "charEnd": end}
                for block_id, start, end in self.spans
            ],
            warnings=tuple(warnings),
        )

    def _unique_options(self) -> list[dict[str, str]]:
        seen: dict[str, int] = {}
        unique: list[dict[str, str]] = []
        for option in self.options:
            key = option["key"]
            text = option["textMarkdown"].strip()
            if not text:
                continue
            if key in seen:
                # 选项 key 重复：按出现顺序重新编号，不丢内容
                key = self._next_key(seen, unique)
            seen[key] = len(unique)
            unique.append({"key": key, "textMarkdown": text})
        return unique

    @staticmethod
    def _next_key(seen: dict[str, int], unique: Sequence[dict[str, str]]) -> str:
        used = {option["key"] for option in unique} | set(seen)
        for code in range(ord("A"), ord("Z") + 1):
            candidate = chr(code)
            if candidate not in used:
                return candidate
        return f"X{len(unique) + 1}"


def _group_paragraphs(lines: Sequence[RuleLine]) -> list[list[RuleLine]]:
    paragraphs: list[list[RuleLine]] = []
    current: list[RuleLine] = []
    for line in lines:
        if line.text.strip():
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def _paragraph_has_marker(paragraph: Sequence[RuleLine]) -> bool:
    for line in paragraph:
        segments = split_segments(line.text)
        if any(segment.label is not None for segment in segments):
            return True
        head = segments[0].text.strip()
        if head and (match_question(head) is not None or match_option(head) is not None):
            return True
    return False


def _looks_continuation(paragraph: Sequence[RuleLine]) -> bool:
    text = "\n".join(line.text for line in paragraph).rstrip()
    return not text.endswith(SENTENCE_ENDS)
