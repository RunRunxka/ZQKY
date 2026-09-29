"""RAG 首答与证据预算的单一事实来源（RAG-QUALITY v1.1 · C0 冻结）。

这些数字同时被后端（证据选择、摘要打包、presenter）与验收矩阵引用。**不得在各模块
散写数字**：改预算只改本文件，并同步更新 `docs/API.md` 与批次任务卡。

口径说明：
- 长度单位是 **Unicode 码点**（Python ``str`` 下标），不是 UTF-8 字节、也不是前端 UTF-16 码元。
- 预算按「清洗后文本」计算（见 B0-TEXT-PROJECTION 的 `project_readable`），
  但单条证据的**原文切片**另有上限，避免用清洗把超长原文"洗进"预算。
"""

from __future__ import annotations

# --------------------------------------------------------------------- 首答证据

#: 首答最多返回多少条证据（旧口径是 20 条；本批收紧为 6 条）
FIRST_ANSWER_EVIDENCE_MAX_ITEMS = 6
#: 邻块扩展：命中块左右各最多补几块（旧实现沿同章无上限扩张）
EVIDENCE_NEIGHBOURS_EACH_SIDE = 1
#: 单条证据**清洗后**长度上限（码点）
EVIDENCE_SINGLE_CLEANED_MAX_CHARS = 1600
#: 首答送入概括模型的证据总长上限（码点，且还要受模型预算二次约束）
EVIDENCE_PROMPT_MAX_CHARS = 6000
#: 单条证据的**原文切片**长度上限（码点）；超过则整条不采用，绝不截断受保护单元
EVIDENCE_SINGLE_RAW_MAX_CHARS = 6000
#: 首答返回的原文证据总量上限（码点）
EVIDENCE_TOTAL_RAW_MAX_CHARS = 16000

# --------------------------------------------------------------- 详解（历史兼容）

#: 详解请求仍接受最多 20 条引用，沿用既有硬限制；不改历史语义
EXPLAIN_MAX_EVIDENCE_REFS = 20
#: 详解上下文里的证据总量沿用既有 40,000 字符上限
EXPLAIN_EVIDENCE_MAX_CHARS = 40000

# ------------------------------------------------------------------------ 首答长度

#: 首答最多知识点数
SUMMARY_MAX_POINTS = 3
#: 单点「标题 + 说明」合计上限（码点）
SUMMARY_MAX_POINT_CHARS = 90
#: 全部知识点「标题 + 说明」合计上限（码点）
SUMMARY_MAX_TOTAL_CHARS = 250
#: 每个知识点最多引用几条证据
SUMMARY_MAX_REFS_PER_POINT = 2
#: 目标长度区间（码点），仅作提示与验收参考；**不设最低字数门槛**
SUMMARY_TARGET_MIN_CHARS = 150
SUMMARY_TARGET_MAX_CHARS = 250
#: 概括模型超长/重复/格式错误时最多修正几次（一次修正，不无限重试）
SUMMARY_MAX_CORRECTIONS = 1

# ------------------------------------------------------------------ 状态与原因码

#: `RagResultV2.reasonCode` 的固定取值（不新增未登记的原因码）
REASON_CODES = (
    "NO_MATCH",                 # 范围内没有任何文本命中
    "EVIDENCE_TEXT_EMPTY",      # 有命中，但清洗后没有可检索文本
    "EVIDENCE_UNIT_TOO_LARGE",  # 有命中，但受保护单元超预算，无法完整装入
    "SUMMARY_INVALID",          # 概括输出不合法且修正后仍不可用
    "SUMMARY_PARTIAL",          # 部分知识点合法可用，已按预算保留
)

#: 把状态映射为默认原因码（服务层可覆盖为更具体的原因）
DEFAULT_REASON_CODE_BY_STATUS = {
    "no_evidence": "NO_MATCH",
    "uncertain": "EVIDENCE_TEXT_EMPTY",
    "partial": "SUMMARY_INVALID",
    "ok": None,
}

__all__ = [
    "FIRST_ANSWER_EVIDENCE_MAX_ITEMS",
    "EVIDENCE_NEIGHBOURS_EACH_SIDE",
    "EVIDENCE_SINGLE_CLEANED_MAX_CHARS",
    "EVIDENCE_PROMPT_MAX_CHARS",
    "EVIDENCE_SINGLE_RAW_MAX_CHARS",
    "EVIDENCE_TOTAL_RAW_MAX_CHARS",
    "EXPLAIN_MAX_EVIDENCE_REFS",
    "EXPLAIN_EVIDENCE_MAX_CHARS",
    "SUMMARY_MAX_POINTS",
    "SUMMARY_MAX_POINT_CHARS",
    "SUMMARY_MAX_TOTAL_CHARS",
    "SUMMARY_MAX_REFS_PER_POINT",
    "SUMMARY_TARGET_MIN_CHARS",
    "SUMMARY_TARGET_MAX_CHARS",
    "SUMMARY_MAX_CORRECTIONS",
    "REASON_CODES",
    "DEFAULT_REASON_CODE_BY_STATUS",
]
