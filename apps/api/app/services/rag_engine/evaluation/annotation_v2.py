"""P8B 人工标注契约 **v2**（单一定义点）——落实
[`docs/qa/P8B-ROUND12-RULES-v2.md`](../../docs/qa/P8B-ROUND12-RULES-v2.md) 的十项裁定。

## 与 v1 的关系（不得混用）

- v1 契约（`segment_annotation.ANNOTATION_STATUSES` / 平铺 `gold_spans` /
  `review_material.py` 的 v1 模板）**原样保留**，历史产物与既有测试不受影响；
- v2 是**新版本**：新状态字段、新 gold 表达（知识点↔证据方案）、新校验器、新指标版本。
  **v1 校验通过不代表满足 v2**；
- 同一个报表里**不得**把 v1 平铺金标与 v2 方案金标放在同一个分母下（见
  `quality_report_v2` 的 `legacy_flat_not_v2` 桶：平铺行一律不进 v2 指标）。

## v2 相比 v1 新增的语义（逐条对应裁定）

| 裁定 | v2 落地方式 |
|---|---|
| 1 习题区 | `RegionIndex.verify_body_only()`：每个 gold 区间机械复核**正文归属**；与习题区相交即拒收。候选侧打 `exercise_intersecting` / `region_unassigned` 标记，评审者可见 |
| 2 重复候选 | `candidate_key()` = `(归一化 file, start, end, text_sha256)`；`fold_duplicate_candidates()` 折并同键候选并**保留全部原始选项 ID**；指标按区间并集计字符 |
| 3 论断归属 | `explanation_link ∈ {matched, unmapped}` + `link_reason`：由**真人**判定；序号字段降级为 `*_hint`；`unmapped` 不进知识点覆盖/解释条目归属统计 |
| 5 知识点↔证据 | `knowledge_points[]` + `evidence_schemes[]`（方案内 AND、方案间 OR）+ `supports` 多对多 + `schemes_frozen_at` 冻结时间 |
| 7 空证据/图片 | `no_evidence` 需 `no_evidence_reason`（可机械区分"仅习题区有文字"）；`image_dependent` 独立字段；两者都要签名+时间+notes |
| 8 区间长度 | **不设长度上限**（≤1000 只约束索引 chunk）；`line_span` 可选但给了就要复核一致 |
| 9 教材外标注 | `external_label` / `visible_marking` / `external_basis` 三个**独立人工字段**（见 `claim_review_v2`） |
| 10 身份可推断 | `identity_guess` / `identity_confidence` 可空字段 + 显示顺序登记（见 `claim_review_v2`） |

## 纪律（写在代码里，不靠自觉）

- 本模块**不产生**任何语义判定：不填 `reviewer` / `reviewed_at` / `verdict` / gold；
  只做结构校验、机械坐标/哈希换算与区间归属复核；
- 主控与子智能体**不得**替代真人填写；`reviewer` 只接受人来签名；
- 全部函数纯读盘、零模型调用、零网络。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.services.rag_engine.contracts import (REGION_BODY, REGION_EXERCISE, normalize_file,
                           read_jsonl)

#: v2 契约版本号（进每条 v2 记录与每份 v2 报表；与 v1 明确区分）
CONTRACT_VERSION = "p8b-annotation-v2"
#: v2 指标版本号（多方案段级评分；**不得**与 `p6-segment-v1` 混用或互相换算）
SEGMENT_METRIC_VERSION_V2 = "p8b-scheme-segment-v2"
#: v2 claim 层口径版本号
CLAIM_PROTOCOL_VERSION_V2 = "p8b-claim-v2"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = PROJECT_ROOT / "data" / "derived" / "chunks.jsonl"

# ---------------------------------------------------------------------------
# 状态词表与枚举
# ---------------------------------------------------------------------------

#: 段级标注状态。v1 五态保留，语义不变（`unreviewed` 与 `pending` 同义的历史取值）。
ANNOTATION_STATUSES_V2 = ("pending", "unreviewed", "reviewed",
                          "reviewed_incomplete", "no_evidence", "image_dependent")
NOT_REVIEWED_STATUSES = ("pending", "unreviewed")

#: `no_evidence` 的**结构化原因**（裁定 1：把"仅习题区有文字"从散文里提到字段上）。
#:   `body_has_no_support`      已核查适用正文，正文无支撑且不依赖图片；
#:   `only_exercise_region_text` 仅习题区有相关文字（正文已核查）→ 可签名 no_evidence；
#:   `other`                    其它原因（`notes` 必须写清）。
NO_EVIDENCE_REASONS = ("body_has_no_support", "only_exercise_region_text", "other")

#: 多段证据关系（**信息性字段，不参与任何评分**：AND/OR 由 `evidence_schemes` 结构表达）
ANNOTATION_RELATIONS = ("single", "parallel", "hierarchical", "complementary",
                        "unclear")

#: 区间归属复核结论。`practice_conflict` = chunk 标签说 body、但标题命中练习类栏目
#: （内容层冲突）——**同样拒收**，见下方说明。
REGION_VERDICTS = ("body", "exercise_intersecting", "unassigned", "practice_conflict")

# --- 内容层冲突检测：练习类栏目 -------------------------------------------
# 为什么需要它：`region` 来自切分时的标题规则表（`configs/heading_rules.yaml` 的
# `practice:` 列表）。该列表**不完整**——独立验收实测有 **188 个 `region=body` 的 chunk**
# 其标题是 `A组/B组/C组/复习题` 这类章末复习题（120,140 个非空白字符），
# 其中 **32 条 12 题候选**就落在这些 chunk 里。也就是说：只看 `region` 标签，
# 习题区原文会被当成正文通过闸门（与裁定 1 正好相反）。
#
# 处置（**不擅自改配置**）：本模块按"标题/内容层"**再判一次**，命中就把区间**拒收**
# （保守方向），并如实报告冲突。把 `A组/B组/C组` 补进 `heading_rules.yaml` 会改变切分、
# 索引与全部历史指标，属数据负责人决策，不在本批内擅自执行。
#: 补充冲突模式（配置里没有、但实测确属练习类栏目的标题形态）
PRACTICE_SUPPLEMENT_PATTERNS = (
    r"^(a|b|c)\s*组$",
    r"^[ab]\s*[、,]\s*[ab]?\s*组$",              # A、B组
    r"^\d{0,2}\s*复习题[\s\-_a-z0-9]*$",          # 复习题 5-1 / 复习题A / 03 复习题
    r"^总复习题$",
    r"^\d{0,2}\s*练习[a-z]?$",
    r"^\d{0,2}\s*(选择|填空|解答|计算|证明|简答|应用|作图)题$",
    r"^\d{0,2}\s*(章末|期末|期中|单元|模块)(检测|测试|复习|小结)$",
    r"^课后练习$",
    r"^.{0,8}练习$",          # 计算机上的练习 / 课堂练习
    r"^.{0,8}作业$",          # 课题作业 / 分层作业
    r"^习题\s*\d",
)
_NUM_PREFIX = re.compile(r"^(?:[（(]?\d{1,2}\s*[)）.、]?|[①②③④⑤⑥⑦⑧⑨⑩])\s*")
_HEAD_PREFIX = re.compile(r"^#{1,6}\s*")
_practice_cache: tuple[tuple[str, ...], tuple[re.Pattern[str], ...]] | None = None


def practice_markers() -> tuple[tuple[str, ...], tuple[re.Pattern[str], ...]]:
    """(配置里的 practice 栏目名, 补充冲突模式)。配置只读一次并缓存。

    配置读不到时**不静默降级**：返回空 markers 并只保留补充模式，由调用方在报告里
    标 `practice_markers_source` —— 本函数不隐藏"配置缺失"这件事。
    """
    global _practice_cache
    if _practice_cache is None:
        names: tuple[str, ...] = ()
        try:
            from app.services.rag_engine.parsing.heading_rules import load_rules
            rules = load_rules(None)
            names = tuple(str(x) for x in (getattr(rules, "practice", None)
                                          or getattr(rules, "practice_markers", None)
                                          or ()))
        except Exception:                     # noqa: BLE001 —— 配置缺失见 docstring
            names = ()
        _practice_cache = (names, tuple(re.compile(p, re.IGNORECASE)
                                       for p in PRACTICE_SUPPLEMENT_PATTERNS))
    return _practice_cache


def line_is_practice_heading(line: str) -> bool:
    """一行是否是练习类栏目标题（去掉 `#` 与编号前缀后判定）。"""
    names, pats = practice_markers()
    raw = str(line or "").strip()
    if not raw:
        return False
    bare = _HEAD_PREFIX.sub("", raw).strip()
    bare = _NUM_PREFIX.sub("", bare).strip()
    if not bare:
        return False
    for name in names:
        if bare == name or bare.startswith(name):
            return True
    for pat in pats:
        if pat.match(bare.replace(" ", "")):
            return True
    return False


#: 题目式提示语（内容形态判据之一）
EXERCISE_PROMPT_TOKENS = (
    "回答下列问题", "下列说法正确的是", "下列说法中正确", "请据此回答", "根据以上信息",
    "填在横线上", "填空", "画出", "作出", "求下列", "计算下列", "说明理由",
    "判断下列", "写出下列", "解释下列", "该反应的化学方程式", "为检验",
)
_ITEM_START = re.compile(r"^\s*(?:[（(]?\d{1,2}\s*[)）.．、]|[①②③④⑤⑥⑦⑧⑨⑩])\s*\S")
_BLANKS = re.compile(r"_{4,}|＿{3,}|\\_\\_")
_OPTION_MARK = re.compile(r"[（(]\s*[A-DＡ-Ｄ]\s*[)）]")
#: 紧邻 `(` 且**不能**算作选项标记的标识符尾巴：`P (A)`（概率）、`\text{card} (A)`、
#: `f(A)` 都是函数调用/函数记号，不是选项。用 ASCII 白名单而**不是** `\w`——
#: Python 的 `\w` 默认含 CJK，`正确的是（A）` 会被整条误杀（实测踩过）。
_IDENT_BEFORE = re.compile(r"[A-Za-z0-9_}\\$]\s*$")
#: 行首选项形态 `A.` / `B．` / `C、`（独立验收 R4-N4 实测：只认 `（A）` 会漏这类选择题）
_OPTION_LINE = re.compile(r"^\s*[A-DＡ-Ｄ]\s*[.．、)）]\s*\S")


def option_marker_letters(text: str) -> set[str]:
    """文本里的**选项字母**集合（`（A）`/`(B)`），剔除函数记号的括号。

    剔除规则：括号前（允许空白）紧邻 ASCII 标识符字符的，是 `P (A)` / `\\text{card} (A)`
    / `f(A)` 这类函数调用，不算选项。实测这条误判会把数学「集合中元素的个数」
    「探究」栏目整段判成选择题（P8D-2c 三轮误杀审计的根因）。
    """
    body = str(text or "")
    letters: set[str] = set()
    for i, ch in enumerate(body):
        if ch in "（(":
            tail = body[:i]
            if _IDENT_BEFORE.search(tail):
                continue
            m = _OPTION_MARK.match(body, i)
            if m:
                letters |= {c for c in m.group(0) if c.isalpha()}
    return letters


def exercise_item_marks(text: str, strong_only: bool = False) -> tuple[int, list[str]]:
    """内容形态判据：区间是否像**题目条目**（做题痕迹）。

    **强信号**（`strong_only=True`）：行首选项行（`A.` / `B．` / `C、`）或**≥2 个不同**
    字母的选项标记（`（A）`/`(B)`，函数记号的括号不算，见 `option_marker_letters`）。

    三轮收紧都有实测依据，也**三次都仍以误杀为主**（417 → 189 → 89 块，逐轮抽样都发现
    正文被排除：`例2 求下列…`、`尝试与发现`/`探究` 栏目、`集合中元素的个数` 整节、
    数学建模报告参考形式模板）。因此本判据的**最终定位是"咨询信号"**：
      - **不作索引排除依据**（索引 = 全部 `region == body` 的块，见 tools/p8d_rebuild.py）；
      - 只在**预测闸门**（P-SCORE-1 逐证据复核）里作为拒收理由之一，并逐条登记理由与样例，
        影响面可测（第一轮 964 条候选里 12 条，1.2%）。

    弱信号（编号条目 + 题目式提示语）与填空横线在 `strong_only=False` 时一并计入。
    返回 (命中行数, 前几行样例)。
    """
    body = str(text or "")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    hits: list[str] = []
    multi_letters = len(option_marker_letters(body)) >= 2
    for ln in lines:
        if ln.lstrip().startswith("#"):
            continue
        if (_OPTION_LINE.match(ln) or (multi_letters and _OPTION_MARK.search(ln))
                or (not strong_only and _BLANKS.search(ln))):
            hits.append(ln.strip()[:60])
    if not hits and not strong_only:
        if any(tok in body for tok in EXERCISE_PROMPT_TOKENS):
            for ln in lines:
                if ln.lstrip().startswith("#"):
                    continue
                if _ITEM_START.match(ln):
                    hits.append(ln.strip()[:60])
                    break
    return len(hits), hits[:3]


#: 内容层判据的版本号（随判据语义变化而升；写进重建报告与 manifest 便于溯源）
CONTENT_DETECTOR_ID = "content-layer-2"


def weak_item_marks(text: str) -> tuple[int, list[str]]:
    """**弱信号**命中数——仅供**咨询清单**（`advisory_weak_body.jsonl`），不作排除依据。

    三类：填空横线、编号条目 + 题目式提示语、编号条目本身（当文本含提示语时）。
    单条弱信号不构成"这是习题"的证据：实测 `例2 求下列各式中 x 的值`、
    `尝试与发现`/`探究` 栏目、数学建模报告参考形式（`____年____班`）都命中而它们是正文。
    """
    text = str(text or "")
    hits: list[str] = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        if _BLANKS.search(ln):
            hits.append(ln.strip()[:60])
    if any(tok in text for tok in EXERCISE_PROMPT_TOKENS):
        for ln in text.splitlines():
            if ln.lstrip().startswith("#"):
                continue
            if _ITEM_START.match(ln):
                hits.append(ln.strip()[:60])
                break
    return len(hits), hits[:3]


def chunk_looks_like_practice(row: Mapping[str, Any]) -> bool:
    """一个 chunk 的**标题层**是否命中练习类栏目（看 `subhead` 与首行标题）。"""
    if line_is_practice_heading(row.get("subhead")):
        return True
    text = str(row.get("text") or "")
    first = text.split(chr(10), 1)[0] if text else ""
    return line_is_practice_heading(first)


def practice_conflict_chars(text: str) -> tuple[int, list[str]]:
    """区间文本里命中练习类栏目标题的行 → (涉及字符数, 前几行样例)。"""
    chars = 0
    samples: list[str] = []
    for line in str(text or "").splitlines():
        if line_is_practice_heading(line):
            chars += sum(1 for ch in line if not ch.isspace())
            if len(samples) < 3:
                samples.append(line.strip()[:60])
    return chars, samples

_HEX64 = set("0123456789abcdef")
_OPTION_RE = re.compile(r"^O\d{2,}$")


def is_hex64(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and set(value.lower()) <= _HEX64)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _meaningful_text(value: object, min_len: int = 2) -> bool:
    """"有意义"的非空文本：去空白后长度 ≥ `min_len` 且至少含一个字母/数字/汉字。

    防止 `notes="_"`、`notes="。"` 这类占位符被当成"写明了依据"（独立验收实测可达标）。
    """
    if not isinstance(value, str):
        return False
    t = value.strip()
    if len(t) < min_len:
        return False
    return any(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in t)


# --- 非人工签名者筛查（**只是筛查，不是身份证明**）---------------------------
# 纪律：签名字符串本身**无法**证明真人身份（裁定原文）。本筛查只能拦住"明显是
# AI/模型/占位"的名字，且必须先做 Unicode 归一化，否则零宽字符/全角/同形字一绕就过
# （独立验收实测：初版黑名单被 14/22 个名字绕过）。真正的控制是
# `data/derived/qa/P8B-HUMAN-V2-20260923/registry/personnel_registry.json` 的
# 人员指派与交接记录，本函数不是替代品。
_ZERO_WIDTH = dict.fromkeys(
    [0x200b, 0x200c, 0x200d, 0x200e, 0x200f, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064,
     0xfeff, 0x00ad] + list(range(0x202a, 0x202f)))
#: 常见同形字折叠（希腊/西里尔 → 拉丁）；大小写由 casefold 处理
_CONFUSABLES = str.maketrans({
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
    "с": "c", "т": "t", "у": "y", "х": "x", "і": "i", "ѕ": "s", "ԁ": "d", "ј": "j",
    "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p",
    "τ": "t", "υ": "u", "χ": "x", "ɡ": "g", "ı": "i",
    "г": "g", "и": "u", "п": "n", "л": "n", "б": "b", "з": "3", "м": "m",
    # 拉丁小型大写/音标同形字（ɢPT 这类绕过）
    "ɢ": "g", "ʀ": "r", "ʟ": "l", "ɴ": "n", "ʏ": "y", "ʜ": "h", "ɪ": "i",
    "ᴍ": "m", "ᴄ": "c", "ᴘ": "p", "ᴛ": "t", "ᴋ": "k", "ᴅ": "d", "ʙ": "b",
    "ᴠ": "v", "ᴢ": "z", "ᴊ": "j", "ᴡ": "w", "ꜱ": "s",
})
NON_HUMAN_TOKENS = (
    # 通用
    "agent", "assistant", "chatbot", "bot", "llm", "model", "openai", "anthropic",
    "placeholder", "synthetic", "dryrun", "automation", "script",
    "tbd", "todo", "test", "unknown", "none", "null", "nobody",
    # 国产/外部模型与助手名（独立验收实测曾漏网）
    "wenxin", "xunfei", "zhipu", "xinghuo", "hunyuan", "yuanbao", "sonnet",
    "opus", "haiku", "o3", "r1", "小助手", "助手",
    # 已知模型/厂商（含本项目与常见外部 agent，避免"用别的名字就过"）
    "gpt", "claude", "gemini", "copilot", "kimi", "deepseek", "zcode", "glm",
    "llama", "mistral", "qwen", "ollama", "bge", "moonshot", "doubao", "ernie",
    "tongyi", "spark", "grok", "phi", "yi34b", "yilarge", "minimax",
    "sora",
    # 中文
    "子智能体", "智能体", "模型", "机器人", "人工智能", "自动", "脚本", "占位",
    "测试", "待定", "未知", "豆包", "通义", "文心", "星火", "讯飞", "智谱",
)
#: **短但高信号**的 token：仍按子串匹配（会被嵌进 `ChatGPT` 这类拼接名）。
#: 其余短 token 一律按词元边界匹配，避免 `phi` 误伤 `Philip`、`yi` 误伤 `Yi Zhao`。
SUBSTRING_TOKENS = frozenset({"gpt", "llm", "glm", "qwen", "bge", "ai", "zcode"})

#: **短但明确**的模型/厂商名：即使 ≤4 字符也算"硬命中"，不接受 override
#: （`phi` 这类歧义短词不在此列——真人姓名可能真叫 Phi）。
HARD_TOKENS = frozenset({"kimi", "opus", "qwen", "glm", "gpt", "llm", "bge",
                         "sora"})

#: 视为"管道自检/合成"的签名（这类**允许**签名，但由报表层的合成闸门拒跑）
SYNTHETIC_SIGNER_TOKENS = ("合成", "synthetic", "管道自检", "占位", "do_not_use",
                           "do_not_use", "non-human", "nonhuman", "dryrun", "dry_run")


def fold_tokens(text: object) -> list[str]:
    """把签名切成**词元**并逐个折叠（短词按词元边界匹配，避免 phi 误伤 Philip）。"""
    import unicodedata
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = t.translate(_ZERO_WIDTH)
    t = t.casefold()          # **先** casefold：否则大写同形字（Аgent）会漏
    t = t.translate(_CONFUSABLES)
    t = unicodedata.normalize("NFKD", t)      # 拆开组合记号…
    t = "".join(ch for ch in t if not unicodedata.combining(ch))  # …再去掉，不丢字母
    return [tok for tok in re.split(r"[^0-9a-z\u4e00-\u9fff]+", t) if tok]


def fold_signer_name(text: object) -> str:
    """把签名折叠成单一比较串（去零宽 / 同形字 / 组合记号 / 大小写 / 分隔符）。"""
    return "".join(fold_tokens(text))


def is_synthetic_signer(text: object) -> bool:
    """签名是否自称"合成/自检"（这类允许签名，由报表层默认拒跑）。"""
    folded = fold_signer_name(text)
    raw = str(text or "")
    return any(tok in raw or fold_signer_name(tok) in folded
               for tok in SYNTHETIC_SIGNER_TOKENS)


def screen_hit_token(text: object) -> str | None:
    """返回命中的非人特征 token（折叠后）；未命中返回 None。供调用方分级处置。"""
    if not _nonempty_str(text) or is_synthetic_signer(text):
        return None
    folded = fold_signer_name(text)
    toks = fold_tokens(text)
    for tok in NON_HUMAN_TOKENS:
        ft = fold_signer_name(tok)
        if not ft:
            continue
        cjk = any("一" <= ch <= "鿿" for ch in ft)
        if len(ft) >= 5 or cjk or ft in SUBSTRING_TOKENS:
            hit = ft in folded
        elif len(ft) >= 4:
            hit = any(x == ft or x.startswith(ft) for x in toks)
        else:
            hit = ft in toks or any(
                x.startswith(ft) and x[len(ft):len(ft) + 1].isdigit() for x in toks)
        if hit:
            return ft
    return None


def screen_kind(text: object) -> str:
    """把筛查结论分成 `ok` / `soft` / `hard`。

    `soft` = 命中**歧义短词**（≤4 个 ASCII 字符的 token，或 `ai` 前缀/独立词规则）——
    真人姓名可能真的撞上它们（`Phi Tran`、`Yi Zhao`），因此允许总控用
    `--override-nonhuman-screen --override-reason` 显式放行并留痕。
    `hard` = 命中模型/厂商/agent/CJK 占位词——那不是"可能撞名"，不接受 override。
    """
    if not _nonempty_str(text):
        return "hard"
    if is_synthetic_signer(text):
        return "ok"
    if not screen_human_name(text):
        return "ok"
    folded = fold_signer_name(text)
    toks = fold_tokens(text)
    for tok in NON_HUMAN_TOKENS:
        ft = fold_signer_name(tok)
        if not ft:
            continue
        cjk = any("\u4e00" <= ch <= "\u9fff" for ch in ft)
        prefix_only = False
        if len(ft) >= 5 or cjk or ft in SUBSTRING_TOKENS:
            hit = ft in folded
        elif len(ft) >= 4:
            # ≥4 字符：词元**相等** → 硬命中（`Kimi`）；仅是**前缀** → 软命中
            # （`kimiX` 要拦住，但 `Kimiya Tanaka` 是真名，须仍可 override）。
            if ft in toks:
                hit = True
            else:
                hit = any(tok.startswith(ft) for tok in toks)
                prefix_only = True
        else:
            hit = ft in toks      # ≤3 字符只认词元相等（phi 不得误伤 Philip）
        if hit:
            # 模型/厂商/agent/CJK 占位名 → 硬命中（不接受 override）；
            # 其余短词 / 前缀命中属"可能撞名"→ 软命中（可 override 并留痕）
            if not prefix_only and (cjk or ft in HARD_TOKENS
                                    or ft in SUBSTRING_TOKENS or len(ft) >= 5):
                return "hard"
            return "soft"
    return "soft"      # 只剩 `ai` 前缀/独立词规则 → 歧义类


def screen_human_name(text: object) -> list[str]:
    """筛查"这不像是人"的签名；返回问题列表（空 = 未命中筛查）。

    **不是身份证明**：命中只说明名字像 AI/占位。自称合成/自检的签名不在此拦（另由
    报表层的 `SYNTHETIC_NOT_HUMAN` 闸门处理），否则管道自检无法跑通。
    """
    if not _nonempty_str(text):
        return ["签名不能为空"]
    if is_synthetic_signer(text):
        return []
    folded = fold_signer_name(text)
    toks = fold_tokens(text)
    problems: list[str] = []
    for tok in NON_HUMAN_TOKENS:
        ft = fold_signer_name(tok)
        if not ft:
            continue
        # 长 token（≥5 字符）用子串匹配；**短 token 只在词元边界匹配**——否则 `phi`
        # 会误伤 `Philip`、`yi` 会误伤 `Wang Yiming`（独立验收实测的过拦方向）。
        # 含汉字的 token 一律子串匹配（`子智能体A` 这类拼接名会连成一个词元，词元边界
        # 匹配会漏）；纯 ASCII 的短 token 才按词元边界匹配。
        cjk = any("一" <= ch <= "鿿" for ch in ft)
        if len(ft) >= 5 or cjk or ft in SUBSTRING_TOKENS:
            hit = ft in folded
        elif len(ft) >= 4:
            # ≥4 字符：词元相等**或**是某词元的前缀（`kimiX`/`opusX` 这类拼接要拦住）；
            # ≤3 字符只认词元相等或"前缀+数字"（`bot01`），避免 `phi` 误伤 `Philip`。
            hit = any(tok == ft or tok.startswith(ft) for tok in toks)
        else:
            hit = ft in toks or any(
                tok.startswith(ft) and tok[len(ft):len(ft) + 1].isdigit()
                for tok in toks)
        if hit:
            problems.append(f"签名命中非人特征 {tok!r}（归一化后 {folded!r}）："
                            "AI/模型/占位名不得作为人工审核签名")
            break
    if re.search(r"(?<![a-z])ai(?![a-z])", folded) or (
            folded.startswith("ai") and len(folded) <= 4):
        # 独立词 'ai'，或很短的 'ai' 前缀名（aiX / ai2 …）——都是常见的 placeholder 命名
        problems.append(f"签名归一化后疑似 AI 命名（{folded!r}）："
                        "请用真人姓名或评审编号；如是真人姓名被误伤，"
                        "由总控在 `tools/p8b_v2_personnel.py register --override-nonhuman-screen` "
                        "记录理由后放行")
    if folded and folded.isdigit():
        problems.append("签名归一化后全是数字：无法作为人工签名的身份线索")
    return problems


# ---------------------------------------------------------------------------
# 稳定 ID（裁定 2 / 5：记录采用稳定 ID）
# ---------------------------------------------------------------------------

def span_id_of(file_rel: str, start: int, end: int, text_sha256: str) -> str:
    """证据区间的**稳定 ID**：由 `(归一化 file, start, end, text_sha256)` 派生。

    确定性、与产生方法/编号无关；同区间必同 ID，因此可作去重键与跨记录引用键。
    """
    raw = f"{normalize_file(file_rel)}|{int(start)}|{int(end)}|{str(text_sha256).lower()}"
    return "span-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def kp_id_of(text: str) -> str:
    """知识点稳定 ID：由知识点**原文**派生（同文同 ID）。"""
    return "kp-" + hashlib.sha256(str(text).strip().encode("utf-8")).hexdigest()[:12]


def segment_id_of(segment: Mapping[str, Any]) -> str:
    """一段证据的稳定 ID（缺 `text_sha256` 时退化为坐标派生，标注为不可核验）。"""
    cs = segment.get("char_span") or [0, 0]
    return span_id_of(str(segment.get("file", "")), int(cs[0]), int(cs[1]),
                      str(segment.get("text_sha256", "")))


def knowledge_point_id(kp: Mapping[str, Any]) -> str:
    """知识点有效 ID：显式 `kp_id` 优先，否则由 `text` 派生（缺两者返回空串）。"""
    explicit = kp.get("kp_id")
    if _nonempty_str(explicit):
        return str(explicit).strip()
    text = kp.get("text")
    return kp_id_of(str(text)) if _nonempty_str(text) else ""


# ---------------------------------------------------------------------------
# 坐标 → 区域归属（裁定 1）
# ---------------------------------------------------------------------------

_column_cache: tuple[str, ...] | None = None


def column_markers() -> tuple[str, ...]:
    """`configs/heading_rules.yaml` 的 `columns:` 列表（教材**栏目**，配置明确"不标 exercise"）。"""
    global _column_cache
    if _column_cache is None:
        try:
            from app.services.rag_engine.parsing.heading_rules import load_rules
            rules = load_rules(None)
            _column_cache = tuple(str(x) for x in (getattr(rules, "columns", None) or ()))
        except Exception:                     # noqa: BLE001
            _column_cache = ()
    return _column_cache


def line_is_column_heading(line: object) -> bool:
    """一行是否是教材**栏目**标题（如 `## 思考与讨论`、`## 探究`）。"""
    raw = str(line or "").strip()
    if not raw:
        return False
    bare = _HEAD_PREFIX.sub("", raw).strip()
    bare = _NUM_PREFIX.sub("", bare).strip()
    return any(bare == m or bare.startswith(m) for m in column_markers())


def _default_corpus_root() -> str | None:
    """配置里的语料根；读不到就返回 None（文本层关闭，由调用方如实登记）。"""
    try:
        from app.services.rag_engine.parsing.heading_rules import load_rules
        return str(load_rules(None).corpus_root)
    except Exception:                     # noqa: BLE001 —— 缺配置不该让整个复核崩掉
        return None


class _FileRegions:
    """一个文件的**区域分区**：把字符轴划成互不重叠、连续覆盖的 `(start, end, region, in_chunk)`。

    归属规则（确定性、可单测，实现即定义）：

      1. 落在某个 chunk 内 `[start, end)` 的字符 → 该 chunk 的 `region`（**唯一可核验**的部分）；
      2. 落在两个 chunk 之间的空隙 → **仅当两侧 chunk 的 region 相同**时才归该 region；
         两侧不同（例如 `exercise → body`）→ **`unassigned`**（无法证明，该 gold 区间拒收）。
         首版曾把空隙一律归"其后那个 chunk"，于是 `exercise → body` 的空隙被算成 `body`
         —— 亦即**习题区原文能通过正文归属闸门**（P8B v2 独立验收实测：18 个空隙 /
         236 个非空白字符，含 `（3）当 $MN$ 的长最小时…` 这类习题子项与 `## 学习拓展`
         提示语）。那与"body-only"这条防线正好相反，故改为两侧一致才归属。
      3. 文件首个 chunk **之前**与最后一个 chunk **之后**的字符 → `unassigned`
         （封面/版权页/目录同样无法证明是正文）。

    取向说明（**不要写成"保守"就完事**）：规则 2/3 让边界处的少量正文也可能被判成
    `unassigned`（拒收，取"拿不准就待审"），代价是过严；但它消除了"习题区原文当正文"
    这个方向的漏放。两个方向的实测规模见 `docs/EVAL.md` 的 v2 登记节。

    实测前提（2026-09-23 全量核对 54 个文件的 13,787 个 chunk）：同文件内 chunk **互不重叠**
    （部分重叠 0 处、包含 0 处），因此分区构造无歧义。
    """

    __slots__ = ("pieces", "first_start", "last_end", "chunk_heads")

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        # (start, end, region, 标题是否命中练习类栏目)
        items = sorted(((int(r["start"]), int(r["end"]), str(r["region"]),
                         chunk_looks_like_practice(r))
                        for r in rows if int(r["end"]) > int(r["start"])),
                       key=lambda t: (t[0], t[1]))
        self.pieces: list[tuple[int, int, str | None, bool, bool]] = []
        self.chunk_heads: list[tuple[int, int, str]] = [
            (int(r["start"]), int(r["end"]), str(r.get("subhead") or "")) for r in rows]
        if not items:
            self.first_start = self.last_end = 0
            return
        self.first_start = items[0][0]
        pos = items[0][0]
        prev = items[0]
        for cur in items:
            if cur[0] > pos:
                # 空隙：两侧 region 相同才归属，不同则无法证明（unassigned）
                self.pieces.append((pos, cur[0],
                                    prev[2] if prev[2] == cur[2] else None, False, False))
            cs = max(pos, cur[0])
            if cur[1] > cs:
                self.pieces.append((cs, cur[1], cur[2], True, cur[3]))
                pos = cur[1]
            prev = cur
        self.last_end = pos

    def classify(self, start: int, end: int) -> dict[str, Any]:
        """复核 `[start, end)` 的正文归属；返回逐区域字符数、结论与可读问题列表。"""
        if end <= start:
            return {"ok": False, "verdict": "unassigned", "regions": {},
                    "exercise_chars": 0, "unassigned_chars": 0,
                    "unchunked_chars": 0, "boundary_ambiguous_chars": 0,
                    "practice_conflict_chars": 0,
                    "problems": [f"区间非法（start={start} end={end}）"]}
        counts: dict[str, int] = {}
        gap_chars = ambiguous = practice = 0
        pos = start
        while pos < end:
            region, in_chunk, nxt, suspect = self._region_at(pos)
            step = min(end, nxt) if nxt > pos else end
            counts[region] = counts.get(region, 0) + (step - pos)
            if suspect:
                practice += step - pos
            if not in_chunk:
                if region == "unassigned":
                    ambiguous += step - pos
                else:
                    gap_chars += step - pos
            pos = step
        problems: list[str] = []
        if counts.get(REGION_EXERCISE):
            problems.append(
                f"区间与习题区（region=exercise）相交 {counts[REGION_EXERCISE]} 字符——"
                "裁定 1：段级 gold 只取正文区原文，习题区不得作为可命中的证据")
        if counts.get("unassigned"):
            problems.append(
                f"区间有 {counts['unassigned']} 字符无法机械证明正文归属"
                "（不在任何 chunk 内且两侧区域不一致，或落在全部 chunk 之外）——"
                "裁定 1 要求逐区间复核；拿不准应保持待审")
        if practice:
            problems.append(
                f"区间有 {practice} 字符落在**标题命中练习类栏目**的 chunk 内"
                "（内容层与 chunk 标签冲突）——正文归属无法确认，须数据负责人确认标签"
                "后由总控登记例外；在此之前不得写入 gold")
        verdict = ("exercise_intersecting" if counts.get(REGION_EXERCISE)
                   else "unassigned" if counts.get("unassigned")
                   else "practice_conflict" if practice else "body")
        return {"ok": not problems, "verdict": verdict,
                "regions": {k: v for k, v in counts.items()},
                "exercise_chars": counts.get(REGION_EXERCISE, 0),
                "unassigned_chars": counts.get("unassigned", 0),
                "practice_conflict_chars": practice,
                # 可归属且两侧一致的空隙字符（标题行等）：**如实披露但不拒收**
                "unchunked_chars": gap_chars,
                # 两侧区域不一致、因此判 unassigned 的空隙字符（与"在全部 chunk 之外"分开）
                "boundary_ambiguous_chars": ambiguous,
                "text_layer_checked": False,     # 由 RegionIndex.classify 按语料可达性覆写
                "problems": problems}

    def _region_at(self, pos: int) -> tuple[str, bool, int, bool]:
        """`pos` 的 (region, 是否落在 chunk 内, 该归属段的右边界, 标题是否练习类)。"""
        if not self.pieces:
            return "unassigned", False, pos + 1, False
        if pos < self.first_start or pos >= self.last_end:
            edge = self.first_start if pos < self.first_start else self.last_end + 1
            return "unassigned", False, max(edge, pos + 1), False
        lo, hi = 0, len(self.pieces)
        while lo < hi:                        # 最后一个 start <= pos 的段
            mid = (lo + hi) // 2
            if self.pieces[mid][0] <= pos:
                lo = mid + 1
            else:
                hi = mid
        s, e, region, in_chunk, suspect = self.pieces[max(0, lo - 1)]
        return (region or "unassigned"), in_chunk, e, suspect


class RegionIndex:
    """按文件缓存的分区序列（惰性读 `data/derived/chunks.jsonl`）。

    `chunks.jsonl` 的 `file` 含反斜杠、证据层的 `file` 用正斜杠 → 一律先
    `normalize_file()`（SCHEMA §9.1 的同源要求）。
    """

    def __init__(self, chunks_path: str | os.PathLike | None = None,
                 corpus_root: str | None | bool = None) -> None:
        self.chunks_path = Path(chunks_path or CHUNKS_PATH)
        self._by_file: dict[str, _FileRegions] | None = None
        self.source_sha256: str | None = None
        # 文本层（标题命中练习类栏目 / 题目条目形态 / 就近上溯标题）**默认开启**：
        # corpus_root 缺省自动取配置里的语料根；显式传 `False` 才关闭。
        # 为什么默认开启——独立验收 R3-N1 实测：裸 `RegionIndex()` 会静默丢掉这三道检查，
        # 于是 README 里那条 `annotation_v2 check` 比报表路径宽松，同一份数据两种结论。
        if corpus_root is False:
            self.corpus_root: str | None = None
        elif corpus_root:
            self.corpus_root = str(corpus_root)
        else:
            self.corpus_root = _default_corpus_root()
        self._text_cache: dict[str, str | None] = {}

    @property
    def text_layer_enabled(self) -> bool:
        return bool(self.corpus_root)

    def _in_column_context(self, file_rel: str, start: int) -> bool:
        """该位置是否处在教材**栏目**（`columns:`，配置明确"不标 exercise"）之内。

        为什么需要：栏目里的"（1）写出…""结论："这类文字会被"题目条目形态"判据误伤
        （独立验收 R4-N3 实测 18/150 是 `思考与讨论`/`探究` 栏目）。配置已经把 columns
        与 practice 分开，本闸门必须尊重这一区分：**栏目语境下不用条目形态判据**，
        标题层与就近上溯判据仍然生效。
        """
        regs = self._load().get(normalize_file(file_rel))
        if regs is not None:
            for cs, ce, sub in regs.chunk_heads:
                if cs <= start < ce and line_is_column_heading(sub):
                    return True
        text = self._text(file_rel)
        if text is None:
            return False
        head = None
        for line in text[max(0, start - 20000):start].splitlines():
            if line.lstrip().startswith("#") and line.strip("#").strip():
                head = line
        return head is not None and line_is_column_heading(head)

    def _text(self, file_rel: str) -> str | None:
        if not self.corpus_root:
            return None
        f = normalize_file(file_rel)
        if f not in self._text_cache:
            try:
                from app.services.rag_engine.retrieval.evidence import load_source
                self._text_cache[f] = load_source(f, self.corpus_root).text
            except Exception:                 # noqa: BLE001 —— 读不到就不做文本层检查
                self._text_cache[f] = None
        return self._text_cache[f]

    def _load(self) -> dict[str, _FileRegions]:
        if self._by_file is not None:
            return self._by_file
        if not self.chunks_path.exists():
            raise FileNotFoundError(
                f"chunks 产物不存在，无法复核正文归属：{self.chunks_path}")
        rows = read_jsonl(self.chunks_path)
        by_file: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_file.setdefault(normalize_file(str(r["file"])), []).append(r)
        self._by_file = {f: _FileRegions(v) for f, v in by_file.items()}
        self.source_sha256 = hashlib.sha256(
            self.chunks_path.read_bytes()).hexdigest()
        return self._by_file

    @property
    def files(self) -> set[str]:
        return set(self._load())

    def classify(self, file_rel: str, start: int, end: int) -> dict[str, Any]:
        f = normalize_file(file_rel)
        regs = self._load().get(f)
        if regs is None:
            return {"ok": False, "verdict": "unassigned", "regions": {},
                    "exercise_chars": 0, "unassigned_chars": int(end - start),
                    "unchunked_chars": 0, "boundary_ambiguous_chars": 0,
                    "practice_conflict_chars": 0,
                    "problems": [f"文件不在 chunks 产物中，无法复核正文归属：{file_rel}"]}
        out = regs.classify(int(start), int(end))
        text = self._text(file_rel)
        out["text_layer_checked"] = text is not None
        piece = (text[int(start):int(end)]
                 if text is not None and 0 <= int(start) < int(end) <= len(text)
                 else "")
        if text is not None and 0 <= int(start) < int(end) <= len(text):
            # **就近上溯**：只有题目条目、练习类标题落在区间之外（"续块"）时，
            # 上面的行扫描抓不到。规则很直白：区间起点之前最近的标题行若是练习类
            # 标题，则这个区间就在练习区里 → 拒收。窗口设 20,000 字符（覆盖很长的
            # 章末复习题），且只看标题行，不猜正文。
            head = None
            win = text[max(0, int(start) - 20000):int(start)]
            for line in win.splitlines():
                if line.lstrip().startswith("#") and line.strip("#").strip():
                    head = line
            # 区间**自己以标题开头**时不做上溯：那个标题就是它所在小节的起点，
            # 拿更早的标题去判会误伤（实测：以 `## 5.7 三角函数的应用` 开头的区间
            # 被前面的 `## 1. 选择题` 误判为练习区）。
            starts_with_heading = bool(
                next((ln for ln in piece.splitlines() if ln.strip()), ""
                     ).lstrip().startswith("#"))
            if head is not None and not starts_with_heading                     and line_is_practice_heading(head):
                out["practice_backref_heading"] = head.strip()[:80]
                out["verdict"] = ("exercise_intersecting"
                                  if out["verdict"] == "exercise_intersecting"
                                  else "practice_conflict")
                if not any("练习类栏目" in p for p in out["problems"]):
                    out["problems"] = list(out["problems"]) + [
                        f"区间之前的最近标题是练习类栏目（{head.strip()[:40]!r}）："
                        "本区间在练习区内，不得写入 gold"]
                out["ok"] = False
            pch, samples = practice_conflict_chars(piece)
            # 栏目语境（`columns:`，配置明确"不标 exercise"）下**不用**条目形态判据：
            # 否则"思考与讨论/探究"这类教材栏目会被误判成习题（独立验收 R4-N3 实测 18 例）。
            if not pch:
                # 栏目语境只用**强信号**（填空横线/选项标记），不用弱信号
                # （编号条目+提示语）——栏目里的讨论题常像编号条目，但在栏目里出现
                # 填空横线或 ABCD 选项时那就是题目形态（实测：思考与讨论 下的选择题）。
                # P8D 修正：**一律只用强信号**。弱信号（编号条目+提示语）单条即可命中，
                # 实测把 417 块正文（例2 求下列…、尝试与发现/探究 栏目）判成题目条目，
                # 并让 964 条候选里 12 条合法正文被误判 `practice_conflict`。
                # 弱信号改为**咨询清单**（tools/p8d_rebuild.py 的 advisory_weak_body.jsonl），
                # 不作拒收依据。
                nhit, nsamples = exercise_item_marks(piece, strong_only=True)
                if nhit:
                    out["exercise_item_marks"] = nhit
                    out["exercise_item_samples"] = nsamples
                    if out["verdict"] == "body":
                        out["verdict"] = "practice_conflict"
                    if not any("练习类栏目" in p or "题目条目" in p for p in out["problems"]):
                        out["problems"] = list(out["problems"]) + [
                            f"区间文本有 {nhit} 行呈**题目条目**形态"
                            f"（行首选项行 / ≥2 个不同字母的选项标记；填空横线与"
                            f"「编号条目+提示语」属弱信号、不触发本拒收，样例：{nsamples[:2]}）"
                            "——按裁定 1 不得写入 gold"]
                    out["ok"] = False
                    raise_if = None
            if pch:
                out["practice_conflict_chars"] = max(
                    int(out.get("practice_conflict_chars") or 0), pch)
                out["practice_conflict_samples"] = samples
                if out["verdict"] == "body":
                    out["verdict"] = "practice_conflict"
                if not any("练习类栏目" in p for p in out["problems"]):
                    out["problems"] = list(out["problems"]) + [
                        f"区间文本里有 {pch} 字符的标题命中练习类栏目"
                        f"（样例：{samples[:2]}）——正文归属无法确认，不得写入 gold"]
                out["ok"] = False
        return out


# ---------------------------------------------------------------------------
# 重复候选归一（裁定 2）
# ---------------------------------------------------------------------------

def candidate_key(row: Mapping[str, Any]) -> tuple[str, int, int, str]:
    """候选/证据区间的归一化键：`(归一化 file, start, end, text_sha256)`。

    同键 = 同一区间（裁定 2）。`text_sha256` 缺失时用空串占位并在折并时不视为同一区间
    （保守：宁可不去重也不误并）。
    """
    cs = row.get("char_span") or [0, 0]
    return (normalize_file(str(row.get("file", ""))), int(cs[0]), int(cs[1]),
            str(row.get("text_sha256") or "").lower())


def fold_duplicate_candidates(rows: Sequence[Mapping[str, Any]],
                              option_field: str = "option"
                              ) -> dict[str, Any]:
    """按 `candidate_key` 折并同题重复候选，**保留全部原始选项 ID**（裁定 2）。

    返回：
      `spans`    每个区间一条：`{span_id, file, char_span, text_sha256, option_ids,
                 n_options, candidates}`（`candidates` 为原始记录，溯源用）；
      `groups`   只有重复（`n_options > 1`）的键与折并结果；
      `stats`    `n_rows` / `n_spans` / `n_duplicate_groups` / `n_rows_folded`。

    `selected_options` 不因折并而变成金标——折并只影响"候选怎么呈现与记账"，
    gold 仍由真人写出 `evidence_schemes`。
    """
    by_key: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    order: list[tuple[str, int, int, str]] = []
    for row in rows:
        key = candidate_key(row)
        if key not in by_key:
            by_key[key] = {"key": key, "rows": []}
            order.append(key)
        by_key[key]["rows"].append(dict(row))
    spans: list[dict[str, Any]] = []
    for key in order:
        entry = by_key[key]
        f, s, e, h = key
        opts = [str(r.get(option_field)) for r in entry["rows"]
                if _nonempty_str(r.get(option_field))]
        spans.append({
            "span_id": span_id_of(f, s, e, h),
            "file": f, "char_span": [s, e], "text_sha256": h or None,
            "option_ids": sorted(opts),
            "n_options": len(entry["rows"]),
            "candidates": entry["rows"],
        })
    dup = [sp for sp in spans if sp["n_options"] > 1]
    return {
        "spans": spans,
        "groups": dup,
        "stats": {
            "key": "(归一化 file, start, end, text_sha256)  —— 裁定 2",
            "n_rows": len(rows),
            "n_spans": len(spans),
            "n_duplicate_groups": len(dup),
            "n_rows_folded": sum(sp["n_options"] for sp in dup) - len(dup),
        },
    }


# ---------------------------------------------------------------------------
# v2 记录校验（结构 + 归属；不做语义判定）
# ---------------------------------------------------------------------------

def _segment_problems(seg: object, where: str, region_index: RegionIndex | None,
                      ) -> tuple[list[str], dict[str, Any] | None]:
    problems: list[str] = []
    if not isinstance(seg, Mapping):
        return [f"{where} 必须是对象"], None
    file = seg.get("file")
    if not _nonempty_str(file):
        problems.append(f"{where}.file 必须是非空字符串")
    cs = seg.get("char_span")
    if (not isinstance(cs, (list, tuple)) or len(cs) != 2
            or not all(_is_int(x) for x in cs) or cs[0] < 0 or cs[1] <= cs[0]):
        problems.append(f"{where}.char_span 必须是 [start, end) 且 start < end（两个整数）")
        cs = None
    if not is_hex64(seg.get("text_sha256")):
        problems.append(f"{where}.text_sha256 必须是 64 位十六进制")
    ls = seg.get("line_span")
    if ls is not None and (not isinstance(ls, (list, tuple)) or len(ls) != 2
                           or not all(_is_int(x) for x in ls) or ls[0] < 1
                           or ls[1] < ls[0]):
        problems.append(f"{where}.line_span 若给出必须是 1-based 闭区间 [a, b] 且 a ≤ b")
    oids = seg.get("source_option_ids")
    if oids is not None and not isinstance(oids, list):
        problems.append(f"{where}.source_option_ids 若给出必须是列表")
    if region_index is None or problems or cs is None or not _nonempty_str(file):
        return problems, None
    verdict = region_index.classify(str(file), int(cs[0]), int(cs[1]))
    problems += [f"{where}.{p}" for p in verdict["problems"]]
    return problems, verdict


def validate_v2_record(row: Mapping[str, Any],
                       region_index: RegionIndex | None = None,
                       known_options: Sequence[str] | None = None) -> list[str]:
    """校验一条 v2 段级标注记录；返回问题列表（空 = 可用于 v2 口径统计）。

    `region_index` 给出时**机械复核**每个区间的正文归属（裁定 1）；为 None 时跳过
    归属复核（调用方必须在报告里标 `region_checked=false`，不得声称已复核）。
    `known_options` 给出时校验 `source_option_ids` 是否真的是该题模板里的编号（溯源）。
    """
    problems: list[str] = []
    status = row.get("status")
    if status not in ANNOTATION_STATUSES_V2:
        return [f"status 非法或缺失：{status!r}（允许 {ANNOTATION_STATUSES_V2}）"]
    if status in NOT_REVIEWED_STATUSES:
        # 待审：不是金标。允许带 humans 的痕迹（reviewer/notes/human_checked=true）——
        # 裁定 7 的"核查过但拿不准仍为待审"，痕迹由报告单列为 pending_with_human_trace。
        return problems
    if not _nonempty_str(row.get("reviewer")):
        problems.append("reviewer 必须是非空字符串（谁审的；不得由 agent 代签）")
    else:
        problems += [f"reviewer: {p}" for p in screen_human_name(row.get("reviewer"))]
    if not _nonempty_str(row.get("reviewed_at")):
        problems.append("reviewed_at 必须是非空字符串（何时审的）")
    notes = row.get("notes")
    schemes = row.get("evidence_schemes")
    flat = row.get("gold_spans")

    if status in ("no_evidence", "image_dependent"):
        if not _meaningful_text(notes):
            problems.append(f"{status} 必须写明 notes（检查范围/依据/为何依赖图片；"
                            "不能只写一个占位符号）")
        if schemes:
            problems.append(f"{status} 不得给出 evidence_schemes（另列统计，不进正例金标）")
        if flat:
            problems.append(f"{status} 不得给出正文 gold_spans（v2 起亦不得给平铺区间）")
        if status == "no_evidence":
            reason = row.get("no_evidence_reason")
            if reason not in NO_EVIDENCE_REASONS:
                problems.append(
                    f"no_evidence 必须给出 no_evidence_reason ∈ {NO_EVIDENCE_REASONS}"
                    "（裁定 1：'仅习题区有文字'要为机械可辨）")
            elif reason == "only_exercise_region_text" and not _meaningful_text(notes):
                problems.append("only_exercise_region_text 必须在 notes 写清检查范围")
        return problems

    # status == "reviewed"
    if flat and not schemes:
        # v2 起 reviewed 的 gold 只用方案集表达；平铺区间只允许由仲裁者记为
        # `primary_scheme_id` 指向的那一个方案（此处不自动折算——避免"OR 拼成 AND"）。
        problems.append(
            "reviewed 行给出平铺 gold_spans 但缺 evidence_schemes：v2 的 gold 必须用"
            "知识点↔证据方案表达（裁定 5）；平铺区间不得自动折算为方案")
    if not schemes:
        if not problems:
            problems.append("reviewed 必须有非空 evidence_schemes（无依据请用 no_evidence）")
        return problems
    if not isinstance(schemes, list):
        problems.append("evidence_schemes 必须是列表")
        return problems
    if not _nonempty_str(row.get("schemes_frozen_at")):
        problems.append(
            "reviewed 必须给出 schemes_frozen_at（方案在看系统结果前冻结的时间；"
            "裁定 5 要求所有可接受方案先冻结后看结果）")
    if row.get("schemes_frozen_before_system_results") is not True:
        problems.append(
            "reviewed 必须显式声明 schemes_frozen_before_system_results=true"
            "（方案在看系统结果前冻结；由真人确认）")
    if row.get("relation") not in ANNOTATION_RELATIONS:
        problems.append(f"reviewed 必须给出 relation ∈ {ANNOTATION_RELATIONS}"
                        "（信息性字段，不参与评分：AND/OR 由方案结构表达）")
    kps = row.get("knowledge_points")
    kp_ids: list[str] = []
    if not (isinstance(kps, list) and kps):
        problems.append("reviewed 必须给出 knowledge_points（非空列表）")
    else:
        for i, kp in enumerate(kps):
            if not isinstance(kp, Mapping):
                problems.append(f"knowledge_points[{i}] 必须是对象（{{kp_id?, text}}）")
                continue
            if not _nonempty_str(kp.get("text")):
                problems.append(f"knowledge_points[{i}].text 必须是非空字符串")
                continue
            kid = knowledge_point_id(kp)
            if not kid:
                problems.append(f"knowledge_points[{i}] 无法得到稳定 ID")
            elif kid in kp_ids:
                problems.append(f"knowledge_points[{i}] 的 ID 重复：{kid}")
            else:
                kp_ids.append(kid)

    scheme_ids: list[str] = []
    for j, sch in enumerate(schemes):
        where = f"evidence_schemes[{j}]"
        if not isinstance(sch, Mapping):
            problems.append(f"{where} 必须是对象")
            continue
        sid = sch.get("scheme_id")
        if not _nonempty_str(sid):
            problems.append(f"{where}.scheme_id 必须是非空字符串（稳定方案 ID）")
        elif str(sid) in scheme_ids:
            problems.append(f"{where}.scheme_id 与前面的方案重复：{sid}")
        else:
            scheme_ids.append(str(sid))
        segs = sch.get("segments")
        if not (isinstance(segs, list) and segs):
            problems.append(f"{where}.segments 必须是非空列表"
                            "（方案内多段为 AND：共同必需）")
            segs = []
        for k, seg in enumerate(segs):
            sp, _v = _segment_problems(seg, f"{where}.segments[{k}]",
                                       region_index)
            problems += sp
            if (known_options is not None and isinstance(seg, Mapping)
                    and not sp):
                for oid in (seg.get("source_option_ids") or []):
                    if str(oid) not in known_options:
                        problems.append(
                            f"{where}.segments[{k}].source_option_ids 含未知编号"
                            f" {oid!r}（不在该题盲化编号表内，无法溯源）")
        supports = sch.get("supports")
        if not isinstance(supports, list):
            problems.append(f"{where}.supports 必须是列表（可空：方案也可不对应已列知识点）")
        else:
            for kid in supports:
                if kp_ids and str(kid) not in kp_ids:
                    problems.append(
                        f"{where}.supports 引用了未在 knowledge_points 中定义的 ID：{kid}")
    primary = row.get("primary_scheme_id")
    if _nonempty_str(primary) and scheme_ids and str(primary) not in scheme_ids:
        problems.append(f"primary_scheme_id 未指向任何已定义方案：{primary}")
    dis = row.get("disagreement")
    if _nonempty_str(dis) and not (isinstance(row.get("arbitration"), (str, Mapping))
                                   and str(row["arbitration"]).strip()):
        problems.append("有 disagreement 必须有 arbitration（分歧与仲裁都要留痕）")
    return problems


# ---------------------------------------------------------------------------
# 分桶（不丢行、不改行）
# ---------------------------------------------------------------------------

def partition_v2_rows(rows: Sequence[Mapping[str, Any]],
                      region_index: RegionIndex | None = None,
                      options_by_qid: Mapping[str, Sequence[str]] | None = None,
                      corpus_root: str | None = None,
                      ) -> dict[str, Any]:
    """把 v2 标注行分进**互斥**的桶，并附逐行问题台账。

    桶：
      `reviewed`             结构齐备 + 归属复核通过（v2 正例金标）
      `reviewed_region_fail` 结构齐备但**正文归属复核失败**（裁定 1 拒收）
      `reviewed_hash_fail`   结构齐备、归属通过，但区间 `text_sha256`（或 `line_span`）
                             与当前语料不符——**陈旧/错位区间，不得当金标**
      `reviewed_incomplete`  有审核痕迹但必填/结构不齐
      `no_evidence`          已签名且字段齐备的空金标（含 `no_evidence_reason`）
      `image_dependent`      已签名、正文无法判定
      `pending`              未审核（另分 `pending_with_human_trace` / `pending_untouched`）
      `legacy_flat_not_v2`   只给平铺 `gold_spans`、无 `evidence_schemes` 的已审核行——
                              v1 金标**不得**混进 v2 指标
      `duplicate_qid`        **同一 qid 出现多行**——分母是"题数"，重复行会让同一题
                             被计两次（独立验收实测：88 题全集 + 1 重复行 → 89 条正例而
                             门禁照样放行）。故整组移出，单列
      `status_invalid`       状态词不在词表内
      `rows_missing_qid`     缺 qid 的行（单列，不进任何分母）
      `rows_not_object`      不是 JSON 对象的行（如 `[1,2,3]`；单列，不应崩栈）

    归属复核由 `region_index` 负责；`corpus_root` 给出时**另**复核每个区间的
    `text_sha256` / `line_span` 是否仍是当前语料原文（v1 的取数入口一直做这一步，
    v2 若不补就会放行"坐标对但哈希陈旧"的金标）。两者都不给时报告层必须标
    `verified=false`，不得声称已复核。
    """
    buckets: dict[str, list[dict[str, Any]]] = {
        "reviewed": [], "reviewed_incomplete": [], "reviewed_region_fail": [],
        "reviewed_hash_fail": [], "no_evidence": [], "image_dependent": [],
        "pending": [], "legacy_flat_not_v2": [], "duplicate_qid": [],
        "status_invalid": [],
    }
    problems_by_qid: dict[str, list[str]] = {}
    hash_problems_by_qid: dict[str, list[str]] = {}
    rows_missing_qid: list[dict[str, Any]] = []
    rows_not_object: list[dict[str, Any]] = []
    # 重复 qid 预扫描：先按 qid 计数，再把**整组**重复行移出（不做"保留第一条"的静默挑选）
    qid_counts: dict[str, int] = {}
    for row in rows:
        if isinstance(row, Mapping):
            q = str(row.get("qid") or "").strip()
            if q:
                qid_counts[q] = qid_counts.get(q, 0) + 1
    dup_qids = {q for q, n in qid_counts.items() if n > 1}
    for line_no, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            rows_not_object.append({"line": line_no, "type": type(row).__name__})
            continue
        qid = str(row.get("qid") or "").strip()
        status = str(row.get("status"))
        if not qid:
            rows_missing_qid.append({"line": line_no, "status": status})
            continue
        if qid in dup_qids:
            buckets["duplicate_qid"].append(row)
            # 仍然把**结构问题**一并记下：重复 qid 不该把"字段也不合法"这类信息吃掉
            # （独立验收 R3-4：只报"同一 qid 多行"会让评审者改完还错）。
            dup_msg = (f"同一 qid 在标注文件里出现 {qid_counts[qid]} 行：分母是题数，"
                       "重复行会让同一题被计两次（门禁 2：逐题完整性）")
            probs = [] if dup_msg in problems_by_qid.get(qid, []) else [dup_msg]
            probs += [p for p in validate_v2_record(row, region_index,
                                                    (options_by_qid or {}).get(qid))
                      if "正文区" not in p and "正文归属" not in p]
            problems_by_qid.setdefault(qid, []).extend(probs)
            continue
        opts = (options_by_qid or {}).get(qid)
        problems = validate_v2_record(row, region_index, opts)
        if status == "reviewed":
            if row.get("gold_spans") and not row.get("evidence_schemes"):
                buckets["legacy_flat_not_v2"].append(row)
            elif problems:
                region_fail = any("正文区" in p or "正文归属" in p for p in problems)
                buckets["reviewed_region_fail" if region_fail
                        else "reviewed_incomplete"].append(row)
                problems_by_qid[qid] = problems
            else:
                bad = _hash_problems(row, corpus_root) if corpus_root is not None else []
                if bad:
                    buckets["reviewed_hash_fail"].append(row)
                    hash_problems_by_qid[qid] = bad
                else:
                    buckets["reviewed"].append(row)
        elif status in ("no_evidence", "image_dependent"):
            if problems:
                buckets["reviewed_incomplete"].append(row)
                problems_by_qid[qid] = problems
            else:
                buckets[status].append(row)
        elif status == "reviewed_incomplete":
            # 词表内的合法取值（人工自报"填不齐"）：必须显式落进 `reviewed_incomplete`，
            # 不得当成"状态词非法"（否则题号进不了任何台账）
            buckets["reviewed_incomplete"].append(row)
            problems_by_qid[qid] = (problems or ["status=reviewed_incomplete（人工自报未填齐）"])
        elif status in NOT_REVIEWED_STATUSES:
            buckets["pending"].append(row)
        else:
            buckets["status_invalid"].append(row)
    pend = buckets["pending"]
    pending_traced = [r for r in pend if _nonempty_str(r.get("reviewer"))
                      or _nonempty_str(r.get("notes")) or r.get("human_checked") is True]
    pending_untouched = [r for r in pend if r not in pending_traced]
    return {
        "buckets": buckets,
        "problems_by_qid": problems_by_qid,
        "hash_problems_by_qid": hash_problems_by_qid,
        "rows_missing_qid": rows_missing_qid,
        "rows_not_object": rows_not_object,
        "duplicate_qids": sorted(dup_qids),
        "pending_with_human_trace": pending_traced,
        "pending_untouched": pending_untouched,
    }


# ---------------------------------------------------------------------------
# 方案 → 计分用区间集合
# ---------------------------------------------------------------------------

def scheme_spans_by_file(scheme: Mapping[str, Any]) -> dict[str, list[list[int]]]:
    """一个方案 → `{归一化 file: [[start, end), ...]}`（未合并；由指标层合并）。"""
    out: dict[str, list[list[int]]] = {}
    for seg in scheme.get("segments") or []:
        if not isinstance(seg, Mapping):
            continue
        cs = seg.get("char_span")
        if not (isinstance(cs, (list, tuple)) and len(cs) == 2):
            continue
        f = normalize_file(str(seg.get("file", "")))
        out.setdefault(f, []).append([int(cs[0]), int(cs[1])])
    return out


def record_schemes(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """取一条 v2 金标行的方案列表（附带有效 `scheme_id`；不排序、不改写）。"""
    out: list[dict[str, Any]] = []
    for i, sch in enumerate(row.get("evidence_schemes") or [], 1):
        if not isinstance(sch, Mapping):
            continue
        out.append({"scheme_id": str(sch.get("scheme_id") or f"S{i}"),
                    "supported_kp_ids": [str(x) for x in (sch.get("supports") or [])],
                    "spans_by_file": scheme_spans_by_file(sch)})
    return out


def effective_knowledge_points(row: Mapping[str, Any]) -> list[dict[str, str]]:
    """有效知识点列表（`kp_id` 已补全为稳定 ID）。"""
    out: list[dict[str, str]] = []
    for kp in row.get("knowledge_points") or []:
        if not isinstance(kp, Mapping):
            continue
        kid = knowledge_point_id(kp)
        if kid:
            out.append({"kp_id": kid, "text": str(kp.get("text", "")).strip()})
    return out


# ---------------------------------------------------------------------------
# 空模板 / 记录骨架（供工具与测试复用；不填任何判定）
# ---------------------------------------------------------------------------

def empty_record_template(qid: str, subject: str | None, question: str | None,
                          blinded_options: Sequence[str] | None = None,
                          option_key: Mapping[str, Any] | None = None,
                          in_calibration_set: bool = False) -> dict[str, Any]:
    """一条 v2 空白标注记录。所有判定字段留空/None——**生成器不预填任何结论**。"""
    return {
        "contract_version": CONTRACT_VERSION,
        "qid": qid,
        "subject": subject,
        "question": question,
        "blinded_options": list(blinded_options or []),
        "option_key": dict(option_key or {}),   # 编号 → {file, char_span, text_sha256, flags}
        "selected_options": [],
        "status": "pending",
        "reviewer": None,
        "reviewed_at": None,
        "human_checked": False,
        "knowledge_points": [],
        "evidence_schemes": [],
        "primary_scheme_id": None,
        "schemes_frozen_at": None,
        "schemes_frozen_before_system_results": False,
        "relation": None,
        "no_evidence_reason": None,
        "notes": None,
        "disagreement": None,
        "arbitration": None,
        "in_calibration_set": in_calibration_set,
    }


__all__ = [
    "CONTRACT_VERSION", "SEGMENT_METRIC_VERSION_V2", "CLAIM_PROTOCOL_VERSION_V2",
    "ANNOTATION_STATUSES_V2", "NOT_REVIEWED_STATUSES", "NO_EVIDENCE_REASONS",
    "ANNOTATION_RELATIONS", "REGION_VERDICTS",
    "span_id_of", "kp_id_of", "segment_id_of", "knowledge_point_id",
    "RegionIndex", "candidate_key", "fold_duplicate_candidates",
    "validate_v2_record", "partition_v2_rows", "scheme_spans_by_file",
    "record_schemes", "effective_knowledge_points", "empty_record_template",
    "fold_tokens", "practice_markers", "line_is_practice_heading",
    "chunk_looks_like_practice", "practice_conflict_chars",
    "PRACTICE_SUPPLEMENT_PATTERNS", "SUBSTRING_TOKENS",
    "is_hex64", "stamp_schemes_frozen", "check_file", "main",
    "screen_kind", "screen_hit_token", "HARD_TOKENS", "EXERCISE_PROMPT_TOKENS",
    "exercise_item_marks", "fold_tokens", "practice_markers",
    "line_is_practice_heading", "chunk_looks_like_practice",
    "practice_conflict_chars", "PRACTICE_SUPPLEMENT_PATTERNS",
    "SUBSTRING_TOKENS",
    "screen_human_name", "fold_signer_name", "is_synthetic_signer",
    "NON_HUMAN_TOKENS", "SYNTHETIC_SIGNER_TOKENS",
]


# ---------------------------------------------------------------------------
# CLI：给评审者用的"机械换算 + 自检"两个命令（不产生任何判定）
# ---------------------------------------------------------------------------

def stamp_schemes_frozen(path: str | os.PathLike, timestamp: str,
                         confirm: bool) -> dict[str, Any]:
    """给已填好的 v2 标注文件盖"方案冻结时间"戳（**只写时间与确认位**）。

    裁定 5 要求所有可接受方案在看系统结果前冻结。本命令是这一步的**机械**部分：
    时间戳由程序填，是否冻结由人用 `confirm` 声明。除 `schemes_frozen_at` /
    `schemes_frozen_before_system_results` 外，**不改任何字段**。
    """
    rows = read_jsonl(Path(path))
    n = 0
    for row in rows:
        if str(row.get("status")) == "reviewed":
            row["schemes_frozen_at"] = timestamp
            row["schemes_frozen_before_system_results"] = bool(confirm)
            n += 1
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"file": str(path), "n_stamped": n, "timestamp": timestamp,
            "confirmed": bool(confirm)}


def check_file(path: str | os.PathLike,
               region_index: RegionIndex | None = None,
               corpus_root: str | None = None) -> dict[str, Any]:
    """自检一份 v2 标注文件：结构 + **正文归属** + 区间哈希 + 方案结构。"""
    rows = read_jsonl(Path(path))
    if corpus_root is None:
        from app.services.rag_engine.parsing.heading_rules import load_rules
        corpus_root = load_rules().corpus_root
    # **先解析 corpus_root 再建索引**：否则默认调用会静默丢掉"文本层 / 就近上溯"
    # 那两道检查（独立验收 R3-N1：README 里那条命令因此比报表路径宽松）。
    ri = region_index if region_index is not None else RegionIndex(corpus_root=corpus_root)
    options_by_qid = {str(r.get("qid")): [str(o) for o in (r.get("blinded_options") or [])]
                      for r in rows if r.get("qid")}
    part = partition_v2_rows(rows, ri, options_by_qid, corpus_root=corpus_root)
    b = part["buckets"]
    hash_notes = [f"{qid}: {p}" for qid, ps in part["hash_problems_by_qid"].items()
                  for p in ps]
    counts = {s: len([r for r in rows if str(r.get("status")) == s])
              for s in ANNOTATION_STATUSES_V2}
    return {
        "file": str(path),
        "contract_version": CONTRACT_VERSION,
        "n_rows": len(rows),
        "status_counts": counts,
        "n_usable_positive_gold": len(b["reviewed"]),
        "n_no_evidence": len(b["no_evidence"]),
        "n_image_dependent": len(b["image_dependent"]),
        "n_reviewed_incomplete": len(b["reviewed_incomplete"]),
        "n_reviewed_region_fail": len(b["reviewed_region_fail"]),
        "n_reviewed_hash_fail": len(b["reviewed_hash_fail"]),
        "n_legacy_flat_not_v2": len(b["legacy_flat_not_v2"]),
        "n_pending_with_human_trace": len(part["pending_with_human_trace"]),
        "n_pending_untouched": len(part["pending_untouched"]),
        "n_duplicate_qid": len(part["buckets"]["duplicate_qid"]),
        "duplicate_qids": part["duplicate_qids"],
        "rows_missing_qid": part["rows_missing_qid"],
        "rows_not_object": part["rows_not_object"],
        "problems_by_qid": part["problems_by_qid"],
        "hash_problems": hash_notes,
        "conclusion": ("not_run：没有任何可用的已审核 v2 金标"
                       if not b["reviewed"] else "存在可用 v2 金标（数量见上）"),
    }


def _hash_problems(row: Mapping[str, Any],
                   corpus_root: str | None = None) -> list[str]:
    """复核 v2 方案里每个区间的 `text_sha256` / `line_span` 与当前语料是否一致（独立读盘）。"""
    out: list[str] = []
    for j, sch in enumerate(row.get("evidence_schemes") or []):
        for k, seg in enumerate((sch or {}).get("segments") or []):
            if not isinstance(seg, Mapping):
                continue
            cs = seg.get("char_span") or []
            if len(cs) != 2:
                continue
            try:
                from app.services.rag_engine.retrieval.evidence import load_source
                src = load_source(normalize_file(str(seg.get("file", ""))), corpus_root)
            except Exception as e:      # noqa: BLE001 —— 读不到也算复核不通过
                out.append(f"evidence_schemes[{j}].segments[{k}] 源文件不可读"
                           f"（{type(e).__name__}）")
                continue
            s, e = int(cs[0]), int(cs[1])
            if not (0 <= s < e <= len(src.text)):
                out.append(f"evidence_schemes[{j}].segments[{k}] 区间 [{s},{e}) 越界")
                continue
            want = hashlib.sha256(src.text[s:e].encode("utf-8")).hexdigest()
            if want != str(seg.get("text_sha256", "")).lower():
                out.append(f"evidence_schemes[{j}].segments[{k}] text_sha256 与当前语料不符"
                           f"（实算 {want[:12]}…）")
            ls = seg.get("line_span")
            if ls is not None:
                want_ls = [src.line_of(s), src.line_of(e)]
                if [int(x) for x in ls] != want_ls:
                    out.append(f"evidence_schemes[{j}].segments[{k}] line_span {ls} "
                               f"与重算 {want_ls} 不一致")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="v2 人工标注的机械换算与自检（不产生判定）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stamp", help="给已填好的标注盖方案冻结时间戳（只写时间与确认位）")
    st.add_argument("--file", required=True)
    st.add_argument("--timestamp", default=None, help="缺省用当前 UTC 时间")
    st.add_argument("--confirm-frozen", action="store_true",
                    help="由**真人**声明：方案是在看系统结果之前冻结的")

    ck = sub.add_parser("check", help="自检：字段 + 哈希 + 正文归属 + 方案结构")
    ck.add_argument("--file", required=True)
    ck.add_argument("--report", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "stamp":
        ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        out = stamp_schemes_frozen(args.file, ts, args.confirm_frozen)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    report = check_file(args.file)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
        print(f"[annotation_v2] 写出 {args.report}")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("problems_by_qid",)}, ensure_ascii=False, indent=2))
    for qid, probs in report["problems_by_qid"].items():
        print(f"  [问题] {qid}: {probs[:3]}")
    return 0 if report["n_usable_positive_gold"] or report["n_no_evidence"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
