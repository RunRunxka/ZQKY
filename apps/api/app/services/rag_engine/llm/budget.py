"""完整上下文预算（P8A / R5）——首轮与修复轮都在**发送前**验证。

审查结论（2026-09-21 R5）：服务只限制"证据包"，没有完整准入检查。以 15,000 中文字符
题面调用时，按程序自身估算已是 10,624 prompt tokens > `num_ctx` 8192，程序仍照常调用
生成器并返回 `ok`。证据包预算 `evidence_pack_max_tokens` 只是**输入的一部分**，
题面、系统提示、约束行、chat 模板开销、输出预留与修复轮追加消息都不在其中。

本模块的口径（配套 docs/SCHEMA.md §十一）：

- **输入上限** `input_limit = num_ctx − num_predict − safety_margin_tokens`：
  `num_ctx` 覆盖"输入 + 输出"，因此输出必须预留；安全余量吸收估算误差。
- **估算** `est(text) = ceil(len(text) / chars_per_token_lower)`，默认
  `chars_per_token_lower = 1.0`——即**每字符至少 1 token**，在中文为主的输入上偏向
  高估（真实中文约 0.7–1.2 token/字符）。`estimate_tokens()`（chars/1.5）**不是**
  上界，只作历史口径保留，不得用于准入判断。
- **保守性必须由实测支撑**：每次真实调用记录 `prompt_eval_count` 与提示字符数，
  偏差写进 provenance / 台账（`observed_tokens_per_char`），由
  `budget.chars_per_token_lower` 与 `budget.calibration` 登记。**未测量的范围不得
  声明为"不会截断"**。
- **超限行为**：先按相关度从低到高减少证据（整条丢弃并记录排名，不截断文本；
  拆分则重算坐标——由证据层负责），题面与引用**不静默截断**；连题面都放不下时
  **明确拒绝**并返回结构化状态，不调用生成器。
- 生成返回后核对 `prompt_eval_count + num_predict <= num_ctx`，不满足即记
  `suspect_input_truncation=true` 并在 provenance 里留下实测值——不允许把
  "输出 JSON 合规"当作"输入完整"。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

#: 历史估算口径（chars/token）。**不用于准入**，仅保留给旧报告与对照。
LEGACY_CHARS_PER_TOKEN = 1.5


class ContextBudgetExceeded(RuntimeError):
    """发送前即可判定必然超限（不可通过减证据解决，例如题面本身过长）。"""


def estimate_tokens(text: str, chars_per_token_lower: float) -> int:
    """保守 token 估算：ceil(字符数 / chars_per_token_lower)。

    `chars_per_token_lower=1.0` ⇒ 每字符至少 1 token（高估方向，保守）。
    空串为 0。**这是准入判断唯一允许使用的估算**。
    """
    if not text:
        return 0
    if chars_per_token_lower <= 0:
        raise ValueError(f"chars_per_token_lower 必须为正，得到 {chars_per_token_lower}")
    return int(math.ceil(len(text) / float(chars_per_token_lower)))


def measure_messages(messages: Sequence[Mapping[str, Any]], *,
                     chars_per_token_lower: float,
                     template_overhead_tokens: float) -> int:
    """消息列表的**估算**输入 token 数（含 chat 模板固定开销）。

    模板开销单列而不是摊进内容：它与消息条数/角色标记有关，与文本长度无关。

    **口径限制（P8C-0.3 起明确）**：本函数是估算，不是上界证明；准入判断应优先使用
    离线精确计数（`src.llm.offline_tokenizer`，与已安装权重同词表+同模板）。只有在
    词表产物不可用或模型身份不符时才退回本估算，并在 provenance 标注为
    `estimation_only`（不得据此声称输入完整）。
    """
    total = float(template_overhead_tokens)
    for m in messages:
        total += estimate_tokens(str(m.get("content", "")), chars_per_token_lower)
    return int(total)


# ---------------------------------------------------------------------------
# 计数后端：优先"离线精确"，退回"保守估算"（P8C-0.3）
# ---------------------------------------------------------------------------


class CountingResult:
    """一次计数的结果与**证据来源**（进 provenance，便于事后核对）。"""

    __slots__ = ("n_tokens", "method", "exact", "source", "reason")

    def __init__(self, n_tokens: int, method: str, exact: bool,
                 source: dict | None, reason: str | None = None):
        self.n_tokens = int(n_tokens)
        self.method = method            # "gguf_bpe" | "estimate"
        self.exact = bool(exact)
        self.source = source or {}
        self.reason = reason            # 退回估算的原因（精确不可用时必填）

    def to_dict(self) -> dict:
        return {"n_tokens": self.n_tokens, "method": self.method,
                "exact": self.exact, "source": self.source, "reason": self.reason}


def resolve_counter(*, model_manifest_digest: str | None = None,
                    vocab_path: str | Path | None = None):
    """返回离线精确计数器；不可用/身份不符时返回 (None, 原因)。

    身份守卫：抽取词表的权重 manifest digest 必须与配置的
    `expected_manifest_digest` 一致，否则**拒绝**用作精确计数（不同权重的词表可能不同，
    静默使用等于给出错误的"完整性"证据）。
    """
    try:
        from app.services.rag_engine.llm.offline_tokenizer import (TokenizerUnavailable,
                                               get_tokenizer)
    except Exception as e:      # noqa: BLE001
        return None, f"offline tokenizer 模块不可用：{type(e).__name__}: {e}"
    try:
        tok = get_tokenizer(vocab_path)
    except TokenizerUnavailable as e:
        return None, str(e)
    except Exception as e:      # noqa: BLE001
        return None, f"加载词表失败：{type(e).__name__}: {e}"
    # 摘要比较必须**归一化**：配置里通常带 `sha256:` 前缀，而词表产物记录的是裸 hex。
    # 不归一化会让守卫误判为"权重不符"，从而静默退回估算（P8C-GEN-1 实测踩到：
    # 整轮 78 行都被标成 estimate，尽管权重其实是同一个）。
    def _norm_digest(d: str) -> str:
        # 先小写再去前缀：`SHA256:AB…` 与 `sha256:ab…` 必须等价
        return str(d).strip().lower().removeprefix("sha256:")

    if model_manifest_digest and tok.source_manifest_sha256 \
            and _norm_digest(tok.source_manifest_sha256) != _norm_digest(model_manifest_digest):
        return None, (f"词表来源权重与当前模型不符：vocab={tok.source_manifest_sha256[:16]}… "
                      f"config={str(model_manifest_digest)[:16]}… —— 拒绝用作精确计数")
    return tok, None


def measure_messages_auto(messages: Sequence[Mapping[str, Any]], *,
                          chars_per_token_lower: float,
                          template_overhead_tokens: float,
                          counter=None, counter_reason: str | None = None,
                          add_generation_prompt: bool = True) -> CountingResult:
    """优先精确计数；不可用时退回估算并**如实标注**（不声称输入完整）。"""
    if counter is not None:
        try:
            tc = counter.count_chat(list(messages),
                                    add_generation_prompt=add_generation_prompt)
            return CountingResult(tc.n_tokens, "gguf_bpe", True, tc.to_dict())
        except Exception as e:      # noqa: BLE001 —— 精确路径异常也退回估算并记录
            counter_reason = f"精确计数失败：{type(e).__name__}: {e}"
    est = measure_messages(messages, chars_per_token_lower=chars_per_token_lower,
                           template_overhead_tokens=template_overhead_tokens)
    return CountingResult(est, "estimate", False, {}, counter_reason or "未提供精确计数器")


def input_token_limit(*, num_ctx: int, num_predict: int,
                      safety_margin_tokens: float) -> int:
    """可用输入 token 上限。非正 ⇒ 配置自相矛盾（由 config 校验拦下）。"""
    return int(num_ctx) - int(num_predict) - int(math.ceil(safety_margin_tokens))


@dataclass
class BudgetPlan:
    """一次发送前预算核算的完整记录（进 provenance，供审计与再校准）。"""

    num_ctx: int
    num_predict: int
    safety_margin_tokens: int
    template_overhead_tokens: int
    chars_per_token_lower: float
    input_limit: int
    est_input_tokens: int
    n_messages: int
    prompt_chars: int
    evidence_span_ids: list[str] = field(default_factory=list)
    evidence_chars: int = 0
    dropped_span_ids: list[str] = field(default_factory=list)
    drops_by_budget: list[dict] = field(default_factory=list)
    fits: bool = True
    refusal_reason: str | None = None
    #: 计数口径（P8C-0.3）：exact=True 表示用与已安装权重同词表+同模板的离线精确计数
    counting_method: str = "estimate"        # "gguf_bpe" | "estimate"
    counting_exact: bool = False
    counting_source: dict = field(default_factory=dict)
    counting_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "num_ctx": self.num_ctx, "num_predict": self.num_predict,
            "safety_margin_tokens": self.safety_margin_tokens,
            "template_overhead_tokens": self.template_overhead_tokens,
            "chars_per_token_lower": self.chars_per_token_lower,
            "input_limit": self.input_limit,
            "est_input_tokens": self.est_input_tokens,
            "n_messages": self.n_messages, "prompt_chars": self.prompt_chars,
            "evidence_span_ids": list(self.evidence_span_ids),
            "evidence_chars": self.evidence_chars,
            "dropped_span_ids": list(self.dropped_span_ids),
            "budget_drops": list(self.drops_by_budget),
            "fits": self.fits, "refusal_reason": self.refusal_reason,
            "counting": {"method": self.counting_method, "exact": self.counting_exact,
                         "source": self.counting_source,
                         "reason": self.counting_reason},
        }


def check_usage(*, usage: Mapping[str, Any], num_ctx: int, num_predict: int,
                est_input_tokens: int, prompt_chars: int,
                input_limit: int | None = None) -> dict:
    """生成返回后的实测核对（截断疑似、估算偏差、准入是否被证伪）。

    不修改任何结果，只产出审计字段：
      - `observed_tokens_per_char`：实测 chars/token（估算口径的校准依据）；
      - `estimation_error_ratio`：估算 / 实测（>1 = 我们的估算偏保守）；
      - `admission_violated`：`prompt_eval_count > input_limit` —— 事后**异常探测**。
        **注意口径（P8C-0.3）**：本字段与 `suspect_input_truncation` 都**不能**证明输入
        未被截断——若服务端先丢弃输入再返回，已处理 token 数仍可能满足这两个条件。
        它们只用于发现"实际比预算更大"这类异常；输入完整性以**发送前的精确计数**为准
        （`counting.method == "gguf_bpe"`），否则该次调用标 `input_integrity: not_verified`。
      - `suspect_input_truncation`：`prompt_eval_count + num_predict > num_ctx`
        （输入被服务端截断的直接迹象）；`done_reason == "length"` 亦记为疑似输出截断。
    """
    pe = usage.get("prompt_eval_count")
    ec = usage.get("eval_count")
    done = usage.get("done_reason")
    out: dict[str, Any] = {
        "prompt_eval_count": pe if isinstance(pe, int) else None,
        "eval_count": ec if isinstance(ec, int) else None,
        "done_reason": done,
        "prompt_chars": int(prompt_chars),
    }
    if isinstance(pe, int) and pe > 0 and prompt_chars > 0:
        out["observed_tokens_per_char"] = round(prompt_chars / pe, 4)
        if est_input_tokens > 0:
            out["estimation_error_ratio"] = round(est_input_tokens / pe, 4)
    if isinstance(pe, int) and input_limit is not None:
        out["admission_violated"] = bool(pe > int(input_limit))
    else:
        out["admission_violated"] = None
    out["suspect_input_truncation"] = bool(
        isinstance(pe, int) and pe + int(num_predict) > int(num_ctx))
    out["suspect_output_truncation"] = bool(
        isinstance(ec, int) and done == "length")
    return out
