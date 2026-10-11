"""教材 Markdown 的有状态扫描：保护区、引用定义、图片节点。

本模块只做**定位**，不产生文本；删除与映射由 :mod:`app.services.text_projection.projection`
统一完成。扫描是单遍、左到右、无正则整篇替换的：

1. 先求**保护区**（代码围栏、行内代码、``$$…$$``、行内 ``$…$``）——保护区内的
   ``![…]``、``<img>`` 是字面示例，不得当成真实图片节点；
2. 再在保护区之外解析**引用定义**（``[label]: dest "title"``，整行生效）；
3. 最后扫描**图片节点**与**外层链接**，产出 :class:`RemovalPlan`。

坐标口径：全部是 Python ``str`` 下标（Unicode 码点），不是字节、也不是 UTF-16 码元。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.text_projection.alt_text import IMAGE_EXTENSIONS, meaningful_alt_text

# --------------------------------------------------------------------- 节点与区间

IMAGE_KIND_MARKDOWN = "markdown_image"
IMAGE_KIND_HTML_IMG = "html_img"
IMAGE_KIND_HTML_PICTURE = "html_picture"

PROTECTED_KIND_CODE_FENCE = "code_fence"
PROTECTED_KIND_CODE_SPAN = "code_span"
PROTECTED_KIND_MATH_DISPLAY = "math_display"
PROTECTED_KIND_MATH_INLINE = "math_inline"

#: 单行内联图片的整体长度上限（码点）；超过即认为不是真实图片节点
MAX_INLINE_NODE_CHARS = 4096
#: HTML 标签（含属性）的长度上限（码点）
MAX_HTML_TAG_CHARS = 4096
#: 引用标签长度上限（对齐 CommonMark 的 999）
MAX_LABEL_CHARS = 999
#: Markdown 图片节点允许出现的最少字符数 ``![x](y)``
MIN_INLINE_NODE_CHARS = 6

_TRIMS = " \t\n\r\f\v"


@dataclass(frozen=True)
class ProtectedRange:
    """代码或公式保护区；其中不解释 Markdown 语法。"""

    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class ReferenceDefinition:
    """引用式链接定义；``start``/``end`` 为整行区间（不含行尾换行）。"""

    label: str
    label_key: str
    start: int
    end: int
    line_end: int
    destination: str


@dataclass(frozen=True)
class RemovalPlan:
    """一段要清除的原文区间；``kept_spans`` 是需要逐字保留的说明文字子区间。

    ``image_count`` 是该区间内被清除的图片节点数（仅保留说明文字时同样计数）。
    """

    start: int
    end: int
    kept_spans: tuple[tuple[int, int], ...] = ()
    image_count: int = 0

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("RemovalPlan 区间必须非空。")


@dataclass(frozen=True)
class ScanResult:
    """一次扫描的全部发现，便于测试与诊断。"""

    protected: tuple[ProtectedRange, ...] = ()
    definitions: tuple[ReferenceDefinition, ...] = ()
    plans: tuple[RemovalPlan, ...] = ()
    #: 被普通文字链接使用到的引用标签（归一后），用于判定定义是否可删
    text_link_labels: frozenset[str] = frozenset()
    #: 被截断的标签残片（``rag-readable-v2`` 起；v1 为空）
    fragments: tuple[RemovalPlan, ...] = ()


__all__ = [
    "IMAGE_KIND_HTML_IMG",
    "IMAGE_KIND_HTML_PICTURE",
    "IMAGE_KIND_MARKDOWN",
    "PROTECTED_KIND_CODE_FENCE",
    "PROTECTED_KIND_CODE_SPAN",
    "PROTECTED_KIND_MATH_DISPLAY",
    "PROTECTED_KIND_MATH_INLINE",
    "ProtectedRange",
    "ReferenceDefinition",
    "RemovalPlan",
    "ScanResult",
    "ImageNode",
    "normalize_label_key",
    "scan_code_and_math_ranges",
    "scan_document",
    "scan_reference_definitions",
    "scan_tag_fragments",
]


# ------------------------------------------------------------------- 基础工具


def _is_escaped(raw: str, index: int) -> bool:
    """``index`` 处字符是否被奇数个反斜杠转义。"""
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and raw[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _iter_lines(raw: str) -> list[tuple[int, int, int]]:
    """返回 ``(行首, 行尾, 下一行行首)``；行尾不含换行符。"""
    lines: list[tuple[int, int, int]] = []
    cursor = 0
    total = len(raw)
    while cursor <= total:
        newline = raw.find("\n", cursor)
        if newline == -1:
            lines.append((cursor, total, total + 1))
            break
        lines.append((cursor, newline, newline + 1))
        cursor = newline + 1
        if cursor == total:
            lines.append((cursor, total, total + 1))
            break
    return lines


def _step_cursor(cursor: int, target: int) -> int:
    """保证扫描游标**严格前进**：未完成/异常构造只作为一个字面字符跳过。

    RAG-QUALITY v1.1 的死循环修复把「游标必须严格递增」变成结构性约束：
    任何分支把游标指向 ``target`` 时，若 ``target`` 不大于当前位置，就原地前进一个码点。
    """
    return target if target > cursor else cursor + 1


def _run_length(raw: str, index: int, char: str) -> int:
    cursor = index
    total = len(raw)
    while cursor < total and raw[cursor] == char:
        cursor += 1
    return cursor - index


def _range_index_at(ranges: tuple[ProtectedRange, ...], index: int, hint: int = 0) -> int:
    """保护区游标：返回第一个 ``end > index`` 的下标（递减 hint 前提是游标单调前进）。

    逐字符线性扫描保护区列表在长文档上会退化（v1.1 实测 32 万字慢 20 倍），
    因此所有保护区判断都走这个单调游标，复杂度保持 O(n + k)。
    """
    cursor = hint
    while cursor < len(ranges) and ranges[cursor].end <= index:
        cursor += 1
    return cursor


def _next_blank_line(raw: str, start: int) -> int | None:
    """``start`` 之后第一个空行（连续两个换行，中间仅空白）的位置。"""
    cursor = start
    total = len(raw)
    while cursor < total:
        newline = raw.find("\n", cursor)
        if newline == -1:
            return None
        probe = newline + 1
        while probe < total and raw[probe] in " \t\r":
            probe += 1
        if probe < total and raw[probe] == "\n":
            return newline
        cursor = newline + 1
    return None


# ------------------------------------------------------------------- 保护区


def _fence_marker(line: str) -> tuple[str, int] | None:
    """行首（最多 3 个空格缩进）的代码围栏开启标记。"""
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return None
    if not stripped:
        return None
    char = stripped[0]
    if char not in ("`", "~"):
        return None
    width = _run_length(stripped, 0, char)
    if width < 3:
        return None
    rest = stripped[width:]
    if char == "`" and "`" in rest:
        return None
    return char, width


def _closing_fence(line: str, char: str, width: int) -> bool:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    run = _run_length(stripped, 0, char)
    if run < width:
        return False
    return stripped[run:].strip() == ""


def _scan_fences(raw: str) -> list[ProtectedRange]:
    ranges: list[ProtectedRange] = []
    total = len(raw)
    cursor = 0
    while cursor < total:
        newline = raw.find("\n", cursor)
        line_end = total if newline == -1 else newline
        marker = _fence_marker(raw[cursor:line_end])
        if marker is None:
            if newline == -1:
                break
            cursor = newline + 1
            continue
        char, width = marker
        probe = line_end + 1 if newline != -1 else total
        close_end: int | None = None
        while probe < total:
            inner_newline = raw.find("\n", probe)
            inner_end = total if inner_newline == -1 else inner_newline
            if _closing_fence(raw[probe:inner_end], char, width):
                close_end = inner_end
                break
            if inner_newline == -1:
                break
            probe = inner_newline + 1
        if close_end is None:
            # 未闭合围栏按 CommonMark 处理到文末
            ranges.append(ProtectedRange(cursor, total, PROTECTED_KIND_CODE_FENCE))
            break
        ranges.append(ProtectedRange(cursor, close_end, PROTECTED_KIND_CODE_FENCE))
        next_newline = raw.find("\n", close_end)
        if next_newline == -1:
            break
        cursor = next_newline + 1
    return ranges


def _find_closing_run(
    raw: str,
    start: int,
    char: str,
    width: int,
    *,
    allow_newlines: bool,
    dollar_rules: bool,
    skip: tuple[ProtectedRange, ...] = (),
) -> int | None:
    """找与开始处等长的下一次 char 连续段；返回该段之后的位置。

    ``skip`` 里的区间（代码围栏）不可跨越：跨过围栏会造出重叠的保护区。
    """
    total = len(raw)
    blank_at = _next_blank_line(raw, start)
    skip_index = 0
    cursor = start
    while cursor < total:
        while skip_index < len(skip) and cursor >= skip[skip_index].end:
            skip_index += 1
        if skip_index < len(skip) and skip[skip_index].start <= cursor:
            cursor = _step_cursor(cursor, skip[skip_index].end)
            continue
        if blank_at is not None and cursor > blank_at:
            return None
        current = raw[cursor]
        if current == "\n" and not allow_newlines:
            return None
        if current == "\\" and cursor + 1 < total:
            cursor += 2
            continue
        if current != char:
            cursor += 1
            continue
        run = _run_length(raw, cursor, char)
        if run == width:
            if not dollar_rules or _dollar_can_close(raw, cursor, run):
                return cursor + run
        cursor += run
    return None


def _dollar_can_open(raw: str, index: int, run: int) -> bool:
    """``$$…$$`` 公式块允许换行；行内 ``$…$`` 采用 Pandoc 规则避免误判金额。"""
    if run >= 2:
        return True
    after = index + run
    if after >= len(raw):
        return False
    return not raw[after].isspace()


def _dollar_can_close(raw: str, index: int, run: int) -> bool:
    """``$$…$$`` 公式块允许换行；行内 ``$…$`` 前不能是空白、后不能紧跟数字。"""
    if run >= 2:
        return True
    if index == 0 or raw[index - 1].isspace():
        return False
    after = index + run
    if after < len(raw) and raw[after].isdigit():
        return False
    return True


def _scan_inline_protected(raw: str, fences: list[ProtectedRange]) -> list[ProtectedRange]:
    ranges: list[ProtectedRange] = []
    total = len(raw)
    fence_index = 0
    fence_tuple = tuple(fences)
    cursor = 0
    while cursor < total:
        while fence_index < len(fences) and cursor >= fences[fence_index].end:
            fence_index += 1
        if fence_index < len(fences) and fences[fence_index].start <= cursor:
            cursor = _step_cursor(cursor, fences[fence_index].end)
            continue
        char = raw[cursor]
        if char not in ("`", "$") or _is_escaped(raw, cursor):
            cursor += 1
            continue
        run = _run_length(raw, cursor, char)
        if char == "`":
            if run == 0:
                cursor += 1
                continue
            end = _find_closing_run(
                raw,
                cursor + run,
                "`",
                run,
                allow_newlines=True,
                dollar_rules=False,
                skip=fence_tuple,
            )
            if end is not None:
                ranges.append(ProtectedRange(cursor, end, PROTECTED_KIND_CODE_SPAN))
                cursor = end
                continue
            cursor += run
            continue
        if not _dollar_can_open(raw, cursor, run):
            cursor += run
            continue
        end = _find_closing_run(
            raw,
            cursor + run,
            "$",
            run,
            allow_newlines=run >= 2,
            dollar_rules=True,
            skip=fence_tuple,
        )
        if end is not None:
            kind = PROTECTED_KIND_MATH_DISPLAY if run >= 2 else PROTECTED_KIND_MATH_INLINE
            ranges.append(ProtectedRange(cursor, end, kind))
            cursor = end
            continue
        cursor += run
    return ranges


def scan_code_and_math_ranges(raw: str) -> tuple[ProtectedRange, ...]:
    """扫描代码与公式保护区，按起点排序、互不重叠。

    规则（写入本模块契约，不得在别处再实现一份）：

    - 代码围栏 `` ``` `` / ``~~~``：缩进 ≤3，闭合围栏字符相同且长度不小于开启围栏；
      未闭合则保护到文末；
    - 行内代码：反引号连续段等长配对；
    - 公式：``$`` 连续段等长配对，采用 Pandoc 风格 ``$`` 规则（开启 ``$`` 后必须紧跟
      非空白字符；闭合 ``$`` 前不能是空白、后不能紧跟数字），避免把 ``$5 … $10``
      之类的价格误判成公式；
    - 保护区一律不跨空行。
    """
    fences = _scan_fences(raw)
    inline = _scan_inline_protected(raw, fences)
    merged: list[ProtectedRange] = []
    for span in sorted([*fences, *inline], key=lambda item: (item.start, item.end)):
        # 行内保护区不得与代码围栏重叠；重叠时以围栏为准
        if any(other.start < span.end and span.start < other.end for other in fences):
            if span not in fences:
                continue
        if merged and span.start < merged[-1].end:
            continue
        merged.append(span)
    return tuple(merged)


# --------------------------------------------------------------- 引用定义


def normalize_label_key(label: str) -> str:
    """引用标签归一（大小写折叠 + 内部空白折叠），对齐 CommonMark 匹配规则。"""
    return " ".join(label.split()).casefold()


def _parse_definition_line(
    raw: str, line_start: int, line_end: int
) -> ReferenceDefinition | None:
    cursor = line_start
    indent = 0
    while cursor < line_end and raw[cursor] == " " and indent < 4:
        cursor += 1
        indent += 1
    if indent > 3 or cursor >= line_end or raw[cursor] != "[":
        return None
    label_start = cursor + 1
    probe = label_start
    while probe < line_end:
        if raw[probe] == "\\":
            probe += 2
            continue
        if raw[probe] == "[":
            return None
        if raw[probe] == "]":
            break
        probe += 1
    if probe >= line_end:
        return None
    label = raw[label_start:probe]
    if not label.strip() or len(label) > MAX_LABEL_CHARS:
        return None
    cursor = probe + 1
    if cursor >= line_end or raw[cursor] != ":":
        return None
    cursor += 1
    while cursor < line_end and raw[cursor] in " \t":
        cursor += 1
    destination, cursor = _parse_destination(raw, cursor, line_end)
    if not destination:
        return None
    while cursor < line_end and raw[cursor] in " \t":
        cursor += 1
    title_end = _parse_title(raw, cursor, line_end)
    if title_end is not None:
        cursor = title_end
    if raw[cursor:line_end].strip() != "":
        return None
    return ReferenceDefinition(
        label=label,
        label_key=normalize_label_key(label),
        start=line_start,
        end=line_end,
        line_end=line_end,
        destination=destination,
    )


def _parse_destination(raw: str, cursor: int, limit: int) -> tuple[str, int]:
    """解析链接目标；支持 ``<…>`` 与带嵌套括号的裸目标。"""
    if cursor >= limit:
        return "", cursor
    if raw[cursor] == "<":
        probe = cursor + 1
        while probe < limit:
            if raw[probe] == "\\":
                probe += 2
                continue
            if raw[probe] == ">":
                return raw[cursor + 1 : probe], probe + 1
            if raw[probe] == "<" or raw[probe] == "\n":
                return "", cursor
            probe += 1
        return "", cursor
    probe = cursor
    depth = 0
    while probe < limit:
        char = raw[probe]
        if char == "\\":
            probe += 2
            continue
        if char in " \t":
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        probe += 1
    text = raw[cursor:probe]
    return (text, probe) if text else ("", cursor)


def _parse_title(raw: str, cursor: int, limit: int) -> int | None:
    if cursor >= limit:
        return None
    opener = raw[cursor]
    if opener not in "\"'(":
        return None
    closer = ")" if opener == "(" else opener
    probe = cursor + 1
    while probe < limit:
        if raw[probe] == "\\":
            probe += 2
            continue
        if raw[probe] == closer:
            return probe + 1
        if opener == "(" and raw[probe] == "(":
            return None
        probe += 1
    return None


def scan_reference_definitions(
    raw: str, protected: tuple[ProtectedRange, ...] = ()
) -> tuple[ReferenceDefinition, ...]:
    """扫描引用式链接定义；整行生效，保护区内的行不算定义。"""
    found: list[ReferenceDefinition] = []
    range_index = 0
    for line_start, line_end, _ in _iter_lines(raw):
        range_index = _range_index_at(protected, line_start, range_index)
        if range_index < len(protected) and protected[range_index].start <= line_start:
            continue
        parsed = _parse_definition_line(raw, line_start, line_end)
        if parsed is not None:
            found.append(parsed)
    return tuple(found)


# ------------------------------------------------------------------- 图片节点


@dataclass(frozen=True)
class ImageNode:
    """扫描到的图片节点（Markdown 或 HTML），坐标为原文码点区间。"""

    kind: str
    start: int
    end: int
    alt_start: int
    alt_end: int
    alt_text: str
    reference_definition: ReferenceDefinition | None = None


@dataclass(frozen=True)
class _NodeScan:
    plans: tuple[RemovalPlan, ...]
    image_labels: frozenset[str]
    text_labels: frozenset[str]
    nodes: tuple[ImageNode, ...] = ()


def _trim_span(raw: str, start: int, end: int) -> tuple[int, int]:
    while start < end and raw[start].isspace():
        start += 1
    while end > start and raw[end - 1].isspace():
        end -= 1
    return start, end


def _line_limit(raw: str, index: int) -> int:
    newline = raw.find("\n", index)
    return len(raw) if newline == -1 else newline


def _find_matching_bracket(
    raw: str, open_index: int, protected: tuple[ProtectedRange, ...]
) -> int | None:
    """找与 ``[`` 配对的 ``]``；不跨行、不跨保护区、有长度上限。"""
    limit = min(len(raw), open_index + MAX_INLINE_NODE_CHARS)
    depth = 0
    cursor = open_index
    range_index = _range_index_at(protected, cursor)
    while cursor < limit:
        range_index = _range_index_at(protected, cursor, range_index)
        if range_index < len(protected) and protected[range_index].start <= cursor:
            return None
        char = raw[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "\n":
            return None
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return None


def _parse_inline_destination(raw: str, open_index: int, *, allow_empty: bool) -> int | None:
    """解析 ``(dest "title")``；返回右括号之后的位置。"""
    limit = _line_limit(raw, open_index)
    cursor = open_index + 1
    while cursor < limit and raw[cursor] in " \t":
        cursor += 1
    destination, cursor = _parse_destination(raw, cursor, limit)
    if not destination and not allow_empty:
        return None
    while cursor < limit and raw[cursor] in " \t":
        cursor += 1
    title_end = _parse_title(raw, cursor, limit)
    if title_end is not None:
        cursor = title_end
    while cursor < limit and raw[cursor] in " \t":
        cursor += 1
    if cursor >= limit or raw[cursor] != ")":
        return None
    return cursor + 1


def _parse_markdown_image(
    raw: str,
    start: int,
    definitions: dict[str, ReferenceDefinition],
    protected: tuple[ProtectedRange, ...],
) -> ImageNode | None:
    """解析以 ``![`` 开头的图片节点；无法解析或不构成节点时返回 None。"""
    bracket = start + 1
    close = _find_matching_bracket(raw, bracket, protected)
    if close is None:
        return None
    alt_start = bracket + 1
    alt_end = close
    alt_text = raw[alt_start:alt_end]
    cursor = close + 1
    if cursor < len(raw) and raw[cursor] == "(":
        end = _parse_inline_destination(raw, cursor, allow_empty=True)
        if end is None:
            return None
        return ImageNode(
            kind=IMAGE_KIND_MARKDOWN,
            start=start,
            end=end,
            alt_start=alt_start,
            alt_end=alt_end,
            alt_text=alt_text,
        )
    if cursor < len(raw) and raw[cursor] == "[":
        ref_close = _find_matching_bracket(raw, cursor, protected)
        if ref_close is None:
            return None
        label = raw[cursor + 1 : ref_close]
        key = normalize_label_key(label) if label.strip() else normalize_label_key(alt_text)
        definition = definitions.get(key)
        if definition is None:
            return None
        return ImageNode(
            kind=IMAGE_KIND_MARKDOWN,
            start=start,
            end=ref_close + 1,
            alt_start=alt_start,
            alt_end=alt_end,
            alt_text=alt_text,
            reference_definition=definition,
        )
    # 简写式 ``![说明]``：只有存在同名引用定义时才算图片节点
    definition = definitions.get(normalize_label_key(alt_text))
    if definition is None:
        return None
    return ImageNode(
        kind=IMAGE_KIND_MARKDOWN,
        start=start,
        end=close + 1,
        alt_start=alt_start,
        alt_end=alt_end,
        alt_text=alt_text,
        reference_definition=definition,
    )


def _parse_markdown_link(
    raw: str,
    start: int,
    definitions: dict[str, ReferenceDefinition],
    protected: tuple[ProtectedRange, ...],
) -> tuple[int, int, int, ReferenceDefinition | None] | None:
    """解析 ``[文字](目标)`` / ``[文字][标签]``；返回 (内容起, 内容止, 节点止, 引用定义)。"""
    close = _find_matching_bracket(raw, start, protected)
    if close is None:
        return None
    content_start = start + 1
    content_end = close
    cursor = close + 1
    if cursor < len(raw) and raw[cursor] == "(":
        end = _parse_inline_destination(raw, cursor, allow_empty=True)
        if end is None:
            return None
        return content_start, content_end, end, None
    if cursor < len(raw) and raw[cursor] == "[":
        ref_close = _find_matching_bracket(raw, cursor, protected)
        if ref_close is None:
            return None
        label = raw[cursor + 1 : ref_close]
        fallback = raw[content_start:content_end]
        key = normalize_label_key(label) if label.strip() else normalize_label_key(fallback)
        definition = definitions.get(key)
        if definition is None:
            return None
        return content_start, content_end, ref_close + 1, definition
    definition = definitions.get(normalize_label_key(raw[content_start:content_end]))
    if definition is None:
        return None
    return content_start, content_end, close + 1, definition


def _parse_html_tag(
    raw: str, start: int
) -> tuple[str, int, dict[str, tuple[str, int, int]]] | None:
    """解析 ``<name attr=…>``；返回 (小写标签名, 标签之后的位置, 属性表)。

    属性表的值是 ``(属性值, 原文起, 原文止)``——保留 alt 时要锚定原文区间。
    属性值不做 HTML 实体解码，逐字保留。
    """
    total = len(raw)
    if raw[start] != "<":
        return None
    cursor = start + 1
    if cursor < total and raw[cursor] in "/!?":
        return None
    # HTML 标签名必须字母开头：数学比较写法 ``4x-5<3``、``a<b`` 不得被当成未闭合标签
    if cursor >= total or not raw[cursor].isascii() or not raw[cursor].isalpha():
        return None
    name_start = cursor
    while cursor < total and (raw[cursor].isalnum() or raw[cursor] in "-_:"):
        cursor += 1
    name = raw[name_start:cursor].lower()
    if not name:
        return None
    if cursor < total and raw[cursor] not in " \t\n\r/>":
        return None
    limit = min(total, start + MAX_HTML_TAG_CHARS)
    blank_at = _next_blank_line(raw, start)
    attrs: dict[str, tuple[str, int, int]] = {}
    while cursor < limit:
        if blank_at is not None and cursor > blank_at:
            # 标签属性不可能跨空行；在此收口，避免长文里每个 "<" 都扫满 4096 字符
            return None
        char = raw[cursor]
        if char == ">":
            return name, cursor + 1, attrs
        if char == "/" and cursor + 1 < limit and raw[cursor + 1] == ">":
            return name, cursor + 2, attrs
        if char in " \t\n\r":
            cursor += 1
            continue
        attr_start = cursor
        while cursor < limit and raw[cursor] not in "= \t\n\r/>":
            cursor += 1
        attr_name = raw[attr_start:cursor].lower()
        if not attr_name:
            # 未识别字符（例如不成对的 "/"、孤立的 "="）：按字面跳过一个字符，
            # 保证标签扫描游标严格前进。RAG-QUALITY v1.1 死循环修复点：
            # 这里曾让 `4x-5<3 … images/abc` 这类「不等式 + 图片」文本永久卡住。
            cursor += 1
            continue
        while cursor < limit and raw[cursor] in " \t\n\r":
            cursor += 1
        value = ""
        value_start = cursor
        value_end = cursor
        if cursor < limit and raw[cursor] == "=":
            cursor += 1
            while cursor < limit and raw[cursor] in " \t\n\r":
                cursor += 1
            if cursor < limit and raw[cursor] in "\"'":
                quote = raw[cursor]
                cursor += 1
                value_start = cursor
                while cursor < limit and raw[cursor] != quote:
                    cursor += 1
                value = raw[value_start:cursor]
                value_end = cursor
                cursor += 1
            else:
                value_start = cursor
                while cursor < limit and raw[cursor] not in " \t\n\r>":
                    cursor += 1
                value = raw[value_start:cursor]
                value_end = cursor
        if attr_name:
            attrs.setdefault(attr_name, (value, value_start, value_end))
    return None


def _find_html_close(raw: str, name: str, start: int) -> tuple[int, int] | None:
    """找 ``</name>``；返回 (内容止, 元素止)。"""
    lowered = raw.lower()
    marker = f"</{name}"
    cursor = start
    while True:
        found = lowered.find(marker, cursor)
        if found == -1:
            return None
        after = found + len(marker)
        if after < len(raw) and raw[after] in " \t\n\r>":
            closing = raw.find(">", after)
            if closing != -1 and closing - found <= MAX_HTML_TAG_CHARS:
                return found, closing + 1
        cursor = found + 1


@dataclass(frozen=True)
class _HtmlHit:
    """HTML 里一处可清除的图片元素；``nodes`` 是其内被清除的图片节点。"""

    start: int
    end: int
    nodes: tuple[ImageNode, ...]


def _parse_html_media(raw: str, start: int) -> _HtmlHit | None:
    tag = _parse_html_tag(raw, start)
    if tag is None:
        return None
    name, tag_end, attrs = tag
    if name == "img":
        alt, alt_start, alt_end = attrs.get("alt", ("", tag_end, tag_end))
        node = ImageNode(
            kind=IMAGE_KIND_HTML_IMG,
            start=start,
            end=tag_end,
            alt_start=alt_start,
            alt_end=alt_end,
            alt_text=alt,
        )
        return _HtmlHit(start, tag_end, (node,))
    if name == "picture":
        closed = _find_html_close(raw, "picture", tag_end)
        if closed is None:
            return None
        content_end, element_end = closed
        inner = _scan_child_images(raw, tag_end, content_end, {}, ())
        img = inner[0] if inner else None
        node = ImageNode(
            kind=IMAGE_KIND_HTML_PICTURE,
            start=start,
            end=element_end,
            alt_start=img.alt_start if img is not None else element_end,
            alt_end=img.alt_end if img is not None else element_end,
            alt_text=img.alt_text if img is not None else "",
        )
        return _HtmlHit(start, element_end, (node,))
    if name == "source":
        if "srcset" not in attrs and "src" not in attrs:
            return None
        return _HtmlHit(start, tag_end, ())
    if name != "a":
        return None
    closed = _find_html_close(raw, "a", tag_end)
    if closed is None:
        return None
    content_end, element_end = closed
    children = _scan_child_images(raw, tag_end, content_end, {}, ())
    if not children or not _children_cover(raw, tag_end, content_end, children):
        return None
    return _HtmlHit(start, element_end, children)


def _children_cover(raw: str, start: int, end: int, nodes: tuple[ImageNode, ...]) -> bool:
    """区间内除这些图片节点与空白外是否别无内容。"""
    cursor = start
    for node in nodes:
        if raw[cursor:node.start].strip():
            return False
        cursor = node.end
    return raw[cursor:end].strip() == ""


def _kept_span_for(raw: str, node: ImageNode) -> tuple[int, int] | None:
    """节点里有说明价值的 alt 原文区间；没有则返回 None。"""
    core_start, core_end = _trim_span(raw, node.alt_start, node.alt_end)
    if core_start >= core_end:
        return None
    if not meaningful_alt_text(raw[core_start:core_end]):
        return None
    return core_start, core_end


def _plan_for(raw: str, nodes: tuple[ImageNode, ...], start: int, end: int) -> RemovalPlan:
    kept: list[tuple[int, int]] = []
    for node in nodes:
        span = _kept_span_for(raw, node)
        if span is not None:
            kept.append(span)
    return RemovalPlan(start, end, tuple(sorted(kept)), image_count=len(nodes))


def _scan_child_images(
    raw: str,
    start: int,
    end: int,
    definitions: dict[str, ReferenceDefinition],
    protected: tuple[ProtectedRange, ...],
) -> tuple[ImageNode, ...]:
    """在给定区间内扫描图片节点（Markdown 图片与 HTML ``<img>``/``<picture>``）。"""
    found: list[ImageNode] = []
    cursor = start
    protected_index = 0
    while cursor < end:
        while protected_index < len(protected) and cursor >= protected[protected_index].end:
            protected_index += 1
        if protected_index < len(protected) and protected[protected_index].start <= cursor:
            cursor = _step_cursor(cursor, protected[protected_index].end)
            continue
        char = raw[cursor]
        if char == "!" and not _is_escaped(raw, cursor) and raw[cursor + 1 : cursor + 2] == "[":
            node = _parse_markdown_image(raw, cursor, definitions, protected)
            if node is not None and node.end <= end:
                found.append(node)
                cursor = _step_cursor(cursor, node.end)
                continue
        elif char == "<":
            hit = _parse_html_media(raw, cursor)
            if hit is not None and hit.end <= end:
                found.extend(hit.nodes)
                cursor = _step_cursor(cursor, hit.end)
                continue
        cursor += 1
    return tuple(found)


# ------------------------------------------------- 被截断的标签残片（v2）

#: 会被分块边界截断的媒体标签：残片按图片处理
MEDIA_TAG_NAMES = frozenset({"img", "picture", "source"})
#: 图片外层链接标签：残片删除但不计入图片数
LINK_TAG_NAMES = frozenset({"a"})
#: 承载资源地址的属性名
IMAGE_ATTRIBUTE_NAMES = frozenset(
    {
        "src",
        "srcset",
        "data-src",
        "data-srcset",
        "data-original",
        "data-lazy-src",
        "data-image",
        "data-url",
        "poster",
        "longdesc",
        "usemap",
    }
)
#: 片段里可以按图片规则保留文字的属性名
KEPT_TEXT_ATTRIBUTE_NAMES = frozenset({"alt", "title"})


@dataclass(frozen=True)
class _Attribute:
    """残片里解析到的一个 ``name=value``。"""

    name: str
    value: str
    terminated: bool
    value_start: int
    value_end: int


def _value_looks_like_resource(value: str) -> bool:
    """属性值是否像资源地址：URL，或以图片扩展名结尾的路径/文件名。

    **不**使用宽松的「含 ``/`` 就算路径」判定——英文教材的音标行
    （``/ˌɔːɡənaɪz/``）会被误判成资源地址并被删除（v1.2 实测踩到过）。
    """
    if not value:
        return False
    if "://" in value:
        return True
    return _token_has_image_suffix(value)


def _token_has_image_suffix(token: str) -> bool:
    cleaned = token.split("?", 1)[0].split("#", 1)[0].rstrip("\"'").lower()
    if "." not in cleaned:
        return False
    return cleaned.rsplit(".", 1)[-1] in IMAGE_EXTENSIONS


def _parse_attribute_run(
    raw: str, cursor: int, limit: int
) -> tuple[list[_Attribute], int]:
    """尽量解析连续的 ``name="value"`` / ``name='value'`` / ``name=value``。

    返回 ``(属性表, 最后成功解析的属性之后的位置)``；遇到不成形状的内容立即停下。
    """
    attributes: list[_Attribute] = []
    end = cursor
    while cursor < limit:
        while cursor < limit and raw[cursor] in " \t":
            cursor += 1
        if cursor >= limit or not raw[cursor].isascii() or not raw[cursor].isalpha():
            break
        name_start = cursor
        while cursor < limit and (raw[cursor].isalnum() or raw[cursor] in "-_:"):
            cursor += 1
        name = raw[name_start:cursor].lower()
        while cursor < limit and raw[cursor] in " \t":
            cursor += 1
        if cursor >= limit or raw[cursor] != "=":
            break
        cursor += 1
        while cursor < limit and raw[cursor] in " \t":
            cursor += 1
        if cursor < limit and raw[cursor] in "\"'":
            quote = raw[cursor]
            value_start = cursor + 1
            cursor += 1
            while cursor < limit and raw[cursor] != quote:
                cursor += 1
            terminated = cursor < limit
            value = raw[value_start:cursor]
            value_end = cursor
            if terminated:
                cursor += 1
        else:
            value_start = cursor
            # 无引号值可以包含 "/"（``src=images/x.jpg``），只以空白或 ">" 结束；
            # 收口过早会把地址尾部漏在文本里（v1.2 实测发现）。
            while cursor < limit and raw[cursor] not in " \t\n\r>":
                cursor += 1
            value = raw[value_start:cursor]
            value_end = cursor
            terminated = True
        attributes.append(
            _Attribute(
                name=name,
                value=value,
                terminated=terminated,
                value_start=value_start,
                value_end=value_end,
            )
        )
        end = cursor
    return attributes, end


def _consume_tag_tail(raw: str, cursor: int, limit: int) -> int:
    """吃掉残片末尾孤立的 ``/``、``>``（如 ``…jpg"/>`` 的 ``/>``）。"""
    if cursor < limit and raw[cursor] == "/":
        cursor += 1
        if cursor < limit and raw[cursor] == ">":
            cursor += 1
        return cursor
    if cursor < limit and raw[cursor] == ">":
        return cursor + 1
    return cursor


def _fragment_has_address(attributes: list[_Attribute]) -> bool:
    return any(
        attribute.name in IMAGE_ATTRIBUTE_NAMES
        or _value_looks_like_resource(attribute.value)
        for attribute in attributes
    )


def _fragment_kept_spans(
    raw: str, attributes: list[_Attribute]
) -> tuple[tuple[int, int], ...]:
    """残片里可以保留的说明文字（已闭合且有说明价值的 ``alt``/``title``）。"""
    spans: list[tuple[int, int]] = []
    for attribute in attributes:
        if attribute.name not in KEPT_TEXT_ATTRIBUTE_NAMES or not attribute.terminated:
            continue
        core_start, core_end = _trim_span(raw, attribute.value_start, attribute.value_end)
        if core_start >= core_end:
            continue
        if meaningful_alt_text(raw[core_start:core_end]):
            spans.append((core_start, core_end))
    return tuple(sorted(spans))


def _bare_value_fragment(
    raw: str, index: int, limit: int
) -> RemovalPlan | None:
    """行首的**属性值残片**：切点落在 ``src="`` 与值之间（``images/x.jpg"/>…``）。"""
    cursor = index
    while cursor < limit and (raw[cursor].isalnum() or raw[cursor] in "_./\\:@%+=~-"):
        cursor += 1
    token = raw[index:cursor]
    if not token or cursor >= limit or raw[cursor] not in "\"'":
        return None
    if "://" not in token and not _token_has_image_suffix(token):
        return None
    end = _consume_tag_tail(raw, cursor + 1, limit)
    return RemovalPlan(start=index, end=end, kept_spans=(), image_count=1)


def _bare_attribute_fragment(
    raw: str, index: int, limit: int
) -> RemovalPlan | None:
    """行首/块首的裸属性残片：``src="images/….jpg"/>…``（没有开 ``<``）。

    只在行首（或文本开头）识别：分块边界只会切出「块首残片」，而正文里
    中段出现的 ``src="…"`` 更可能是说明文字，不予删除。
    """
    attributes, end = _parse_attribute_run(raw, index, limit)
    if not attributes:
        return None
    tail_end = _consume_tag_tail(raw, end, limit)
    has_address = _fragment_has_address(attributes)
    has_alt = any(attribute.name == "alt" for attribute in attributes)
    if not has_address and not (has_alt and tail_end > end):
        # 只有 alt/title 且没有标签终止符残留 → 不像残片，按普通文本保留
        return None
    return RemovalPlan(
        start=index,
        end=tail_end,
        kept_spans=_fragment_kept_spans(raw, attributes),
        image_count=1,
    )


def _incomplete_media_tag(
    raw: str, index: int, protected: tuple[ProtectedRange, ...]
) -> RemovalPlan | None:
    """被截断的媒体标签：``<img src="images/x.jpg"``（到行尾/文末都没有 ``>``）。

    同一行里出现 ``>`` 说明标签是完整的，交给图片节点路径处理。
    """
    total = len(raw)
    cursor = index + 1
    name_start = cursor
    while cursor < total and raw[cursor].isascii() and raw[cursor].isalpha():
        cursor += 1
    name = raw[name_start:cursor].lower()
    if name not in MEDIA_TAG_NAMES and name not in LINK_TAG_NAMES:
        return None
    if cursor < total and raw[cursor] not in " \t\n\r/>":
        return None
    limit = min(_line_limit(raw, index), index + MAX_HTML_TAG_CHARS)
    if raw.find(">", cursor, limit) != -1:
        return None
    attributes, end = _parse_attribute_run(raw, cursor, limit)
    tail_end = _consume_tag_tail(raw, end, limit)
    if not attributes and raw[tail_end:limit].strip():
        # 只有 ``<img`` 后面还跟着别的内容（例如正文里讲 ``<img 标签``）→ 不当残片
        return None
    return RemovalPlan(
        start=index,
        end=tail_end,
        kept_spans=_fragment_kept_spans(raw, attributes),
        image_count=1 if name in MEDIA_TAG_NAMES else 0,
    )


def scan_tag_fragments(
    raw: str, protected: tuple[ProtectedRange, ...] = ()
) -> tuple[RemovalPlan, ...]:
    """扫描被分块边界截断的标签残片，产出与图片节点同样的清除区间。

    两类残片：

    1. **块首/行首的裸属性片段**（``src="images/….jpg"/>…``）——块起点落在 ``<img``
       标签内部时出现；
    2. **未闭合的媒体标签**（``<img src="images/x.jpg"``、``<td><img ``）——块终点落在
       标签内部时出现。

    规则与图片节点一致：地址不进入清洗文本；已闭合且有说明价值的 ``alt``/``title`` 逐字保留；
    找不到地址的 ``<a href>`` 残片删除但**不计入** ``removedImageCount``。
    """
    plans: list[RemovalPlan] = []
    total = len(raw)
    cursor = 0
    protected_index = 0
    line_clean = True
    while cursor < total:
        while protected_index < len(protected) and cursor >= protected[protected_index].end:
            protected_index += 1
        if protected_index < len(protected) and protected[protected_index].start <= cursor:
            cursor = _step_cursor(cursor, protected[protected_index].end)
            continue
        char = raw[cursor]
        if char == "\n":
            line_clean = True
            cursor += 1
            continue
        if char in " \t":
            cursor += 1
            continue
        if char == "<":
            plan = _incomplete_media_tag(raw, cursor, protected)
            if plan is not None:
                plans.append(plan)
                cursor = _step_cursor(cursor, plan.end)
                line_clean = False
                continue
        elif line_clean:
            plan = _bare_attribute_fragment(raw, cursor, limit=_line_limit(raw, cursor))
            if plan is None:
                plan = _bare_value_fragment(raw, cursor, limit=_line_limit(raw, cursor))
            if plan is not None:
                plans.append(plan)
                cursor = _step_cursor(cursor, plan.end)
                line_clean = False
                continue
        line_clean = False
        cursor += 1
    return _finalize_plans(plans)


# --------------------------------------------------------------- 主扫描


def _scan_nodes(
    raw: str,
    definitions: dict[str, ReferenceDefinition],
    protected: tuple[ProtectedRange, ...],
) -> _NodeScan:
    plans: list[RemovalPlan] = []
    nodes: list[ImageNode] = []
    image_labels: set[str] = set()
    text_labels: set[str] = set()
    total = len(raw)
    definition_lines = {definition.start: definition for definition in definitions.values()}
    cursor = 0
    protected_index = 0
    while cursor < total:
        while protected_index < len(protected) and cursor >= protected[protected_index].end:
            protected_index += 1
        if protected_index < len(protected) and protected[protected_index].start <= cursor:
            cursor = _step_cursor(cursor, protected[protected_index].end)
            continue
        if cursor in definition_lines:
            definition = definition_lines[cursor]
            cursor = _step_cursor(
                cursor, definition.end + 1 if definition.end < total else total
            )
            continue
        char = raw[cursor]
        if char == "!" and not _is_escaped(raw, cursor) and raw[cursor + 1 : cursor + 2] == "[":
            node = _parse_markdown_image(raw, cursor, definitions, protected)
            if node is not None:
                nodes.append(node)
                plans.append(_plan_for(raw, (node,), node.start, node.end))
                if node.reference_definition is not None:
                    image_labels.add(node.reference_definition.label_key)
                cursor = _step_cursor(cursor, node.end)
                continue
        elif char == "[" and not _is_escaped(raw, cursor):
            parsed = _parse_markdown_link(raw, cursor, definitions, protected)
            if parsed is not None:
                content_start, content_end, link_end, definition = parsed
                children = _scan_child_images(raw, content_start, content_end, definitions, protected)
                if children and _children_cover(raw, content_start, content_end, children):
                    nodes.extend(children)
                    plans.append(_plan_for(raw, children, cursor, link_end))
                    if definition is not None:
                        image_labels.add(definition.label_key)
                    cursor = _step_cursor(cursor, link_end)
                    continue
                if definition is not None:
                    text_labels.add(definition.label_key)
        elif char == "<":
            hit = _parse_html_media(raw, cursor)
            if hit is not None:
                nodes.extend(hit.nodes)
                plans.append(_plan_for(raw, hit.nodes, hit.start, hit.end))
                cursor = _step_cursor(cursor, hit.end)
                continue
        cursor += 1
    return _NodeScan(
        plans=_finalize_plans(plans),
        image_labels=frozenset(image_labels),
        text_labels=frozenset(text_labels),
        nodes=tuple(nodes),
    )


def _finalize_plans(plans: list[RemovalPlan]) -> tuple[RemovalPlan, ...]:
    """按起点排序并丢弃重叠区间；重叠说明扫描异常，绝不静默扩大删除范围。"""
    ordered = sorted(plans, key=lambda plan: (plan.start, plan.end))
    result: list[RemovalPlan] = []
    previous_end = -1
    for plan in ordered:
        if plan.start < previous_end:
            continue
        result.append(plan)
        previous_end = plan.end
    return tuple(result)


def _definition_plan(raw: str, definition: ReferenceDefinition) -> RemovalPlan:
    """引用定义的删除区间：整行（含行尾换行），避免留下来源不明的空行。"""
    end = definition.end
    if end < len(raw) and raw[end] == "\n":
        end += 1
    return RemovalPlan(definition.start, end)


def scan_document(raw: str, *, include_image_fragments: bool = True) -> ScanResult:
    """完整扫描：保护区 → 引用定义 → 图片节点/外层链接 → 待删除区间。

    - 图片引用定义只在**仅被图片使用**时删除；同时被普通文字链接使用时保留；
    - 外层链接只在内容**全部是图片与空白**时整体删除（说明文字仍按图片规则保留）；
    - ``include_image_fragments`` 控制是否清洗被截断的标签残片
      （``rag-readable-v2`` 为 True，历史 ``rag-readable-v1`` 为 False）；
    - 返回的 ``plans`` 互不重叠、按起点有序。
    """
    protected = scan_code_and_math_ranges(raw)
    definitions = scan_reference_definitions(raw, protected)
    definition_map = {definition.label_key: definition for definition in definitions}
    scan = _scan_nodes(raw, definition_map, protected)
    fragments = (
        scan_tag_fragments(raw, protected) if include_image_fragments else ()
    )
    plans = [*scan.plans, *fragments]
    for definition in definitions:
        if definition.label_key in scan.text_labels:
            continue
        if definition.label_key in scan.image_labels:
            plans.append(_definition_plan(raw, definition))
    return ScanResult(
        protected=protected,
        definitions=definitions,
        plans=_finalize_plans(plans),
        text_link_labels=scan.text_labels,
        fragments=fragments,
    )



