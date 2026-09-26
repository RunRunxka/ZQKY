"""离线精确 token 计数（P8C-0.3）——Qwen2/Qwen2.5 字节级 BPE，纯标准库实现。

**为什么需要**：输入完整性不能靠"字符数估算 + 事后 `prompt_eval_count`"证明。服务端若
先截断再返回，`prompt_eval_count + num_predict <= num_ctx` 仍可能成立（返回的是**已处理**
的 token 数）；估算系数（chars/token）只由少量样本标定，不是通用上界。因此本模块从
**本地已安装权重**（Ollama GGUF）中取词表 / merges / 特殊 token / chat template，在进程内
做与权重一致的 token 计数：准入判断用**真实 token 数**，而不是估算。

实现口径（与 HF `Qwen2TokenizerFast` / llama.cpp `qwen2` pre-tokenizer 一致）：
  1. 预切分正则（按顺序取第一个匹配的候选，量词贪婪）：
     ``(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\\r\\n\\p{L}\\p{N}]?\\p{L}+|\\p{N}``
     ``| ?[^\\s\\p{L}\\p{N}]+[\\r\\n]*|\\s*[\\r\\n]+|\\s+(?!\\S)|\\s+``
  2. 每段用 `bytes_to_unicode()` 映射到 GPT-2 字节空间；
  3. 按 merges 排名做 BPE 合并；
  4. 特殊 token（`token_type==3`，如 `<|im_start|>`）在文本中**原子匹配**（优先于普通编码）；
  5. chat template 用权重的 Jinja 模板原样渲染（jinja2，缺失即明确失败，不退化为估算）。

**验证**（不得只靠自述）：`tools/tokenizer_reference.py` 在 `.venv-local-rerank`（含 Rust
`tokenizers`）里用同一份词表构造参考实现，对大批字符串逐 id 比对；另有小样本真实
`/api/chat` 调用核对整条 prompt 的 token 数。详见 `docs/EVAL.md` 的登记条目。
"""
from __future__ import annotations

import heapq
import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

#: 与 HF/llama.cpp 一致的 Qwen2 预切分正则（此处按语义手工实现，避免引入 regex 依赖）
QWEN2_PRETOKENIZER_PATTERN = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}"
    r"| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
)
_CONTRACTIONS = ("'s", "'t", "'re", "'ve", "'m", "'ll", "'d")
#: Unicode White_Space（Rust `\s` 语义；Python 的 str.isspace() 多算 \x1c-\x1f）
_WHITE_SPACE = frozenset(
    "\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000")
_CRLF = frozenset("\r\n")


def _is_space(ch: str) -> bool:
    return ch in _WHITE_SPACE


def _is_letter(ch: str) -> bool:
    return unicodedata.category(ch).startswith("L")


def _is_number(ch: str) -> bool:
    return unicodedata.category(ch).startswith("N")


def _is_other(ch: str) -> bool:
    """`[^\\s\\p{L}\\p{N}]`：非空白、非字母、非数字。"""
    return ch not in _WHITE_SPACE and not _is_letter(ch) and not _is_number(ch)


@lru_cache(maxsize=1)
def bytes_to_unicode() -> dict[int, str]:
    """GPT-2 字节 → unicode 映射（可逆；保证词表里没有控制字符）。"""
    bs = (list(range(ord("!"), ord("~") + 1))
          + list(range(ord("\xa1"), ord("\xac") + 1))
          + list(range(ord("\xae"), ord("\xff") + 1)))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, (chr(c) for c in cs)))


class TokenizerUnavailable(RuntimeError):
    """词表产物缺失/损坏——调用方必须明确失败，不得退化成估算。"""


@dataclass
class TokenCount:
    """一次计数的完整证据（进 provenance，便于事后核对）。"""

    n_tokens: int
    method: str                    # "gguf_bpe"
    source_manifest_sha256: str | None
    source_blob_digest: str | None
    n_special_tokens: int = 0
    n_text_segments: int = 0

    def to_dict(self) -> dict:
        return {"n_tokens": self.n_tokens, "method": self.method,
                "source_manifest_sha256": self.source_manifest_sha256,
                "source_blob_digest": self.source_blob_digest,
                "n_special_tokens": self.n_special_tokens,
                "n_text_segments": self.n_text_segments}


DEFAULT_VOCAB = (Path(__file__).resolve().parents[2]
                 / "data/derived/tokenizer/qwen2_5_7b_gguf_vocab.json")

_ENV = None
_TEMPLATES: dict[str, object] = {}


def _jinja_env():
    """与 transformers chat template 环境一致（trim_blocks/lstrip_blocks=True）。

    不一致会让块标签后的换行残留，渲染串与模型实际看到的提示不同（P8C 实测发现）。
    """
    global _ENV
    if _ENV is None:
        from jinja2 import Environment
        env = Environment(trim_blocks=True, lstrip_blocks=True,
                          autoescape=False, keep_trailing_newline=True)
        env.filters["tojson"] = lambda v, **kw: json.dumps(v, ensure_ascii=False)

        def _raise(msg: str):
            raise TokenizerUnavailable(f"chat template 渲染失败：{msg}")

        env.globals["raise_exception"] = _raise
        _ENV = env
    return _ENV


def _compiled_template(tpl: str):
    """编译缓存：模板 2.5k 字符，每次重新解析约 8 ms（P8C 实测），必须缓存。"""
    t = _TEMPLATES.get(tpl)
    if t is None:
        t = _jinja_env().from_string(tpl)
        _TEMPLATES[tpl] = t
    return t


class Qwen2OfflineTokenizer:
    """从 GGUF 抽取的词表构造的 Qwen2 BPE（进程内、零网络）。"""

    def __init__(self, payload: Mapping[str, Any]):
        tok = payload.get("tokenizer") or {}
        for key in ("tokens", "merges", "token_types", "chat_template"):
            if key not in tok:
                raise TokenizerUnavailable(f"词表产物缺少 tokenizer.{key}")
        self.tokens: list[str] = list(tok["tokens"])
        self.token_types: list[int] = list(tok["token_types"])
        self.merges: list[str] = list(tok["merges"])
        self.chat_template: str = tok["chat_template"]
        self.add_bos_token: bool = bool(tok.get("add_bos_token", False))
        self.bos_token_id = tok.get("bos_token_id")
        self.eos_token_id = tok.get("eos_token_id")
        self.pre: str = str(tok.get("pre") or "")
        if self.pre != "qwen2":
            raise TokenizerUnavailable(
                f"预切分器 {self.pre!r} 不是 qwen2：本实现只覆盖 qwen2 口径")
        src = payload.get("source") or {}
        self.source_manifest_sha256 = src.get("manifest_sha256")
        self.source_blob_digest = src.get("blob_digest")
        self.source_blob_bytes = src.get("blob_bytes")

        self._b2u = bytes_to_unicode()
        self._token_to_id: dict[str, int] = {}
        for i, t in enumerate(self.tokens):
            self._token_to_id.setdefault(t, i)
        # merges: "a b" → rank（按行序）
        self._ranks: dict[tuple[str, str], int] = {}
        for rank, m in enumerate(self.merges):
            parts = m.split(" ")
            if len(parts) == 2:
                self._ranks[(parts[0], parts[1])] = rank
        # 特殊 token（token_type == 3 CONTROL）：原子匹配
        self._special_ids = {self.tokens[i] for i, tt in enumerate(self.token_types)
                             if tt == 3 and self.tokens[i]}
        self._special_first_chars = {t[0] for t in self._special_ids if t}
        self._max_special_len = max((len(t) for t in self._special_ids), default=0)

    # ---- 构造 ----

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_VOCAB) -> "Qwen2OfflineTokenizer":
        p = Path(path)
        if not p.exists():
            raise TokenizerUnavailable(
                f"未找到离线词表产物：{p}。先运行 "
                f"`python tools/extract_gguf_tokenizer.py`（从本地 GGUF 抽取，不联网）")
        return cls(json.loads(p.read_text(encoding="utf-8")))

    # ---- 预切分 ----

    def pre_tokenize(self, text: str) -> list[str]:
        """按 Qwen2 正则的语义切分（替代方案：手工实现，避免引入 `regex` 依赖）。"""
        out: list[str] = []
        i, n = 0, len(text)
        while i < n:
            end = (self._m_contraction(text, i) or self._m_optional_letter(text, i)
                   or self._m_number(text, i) or self._m_space_symbols(text, i)
                   or self._m_ws_newline(text, i) or self._m_ws_not_followed(text, i)
                   or self._m_ws(text, i))
            if end is None:                     # 理论不可达（最后一个候选必匹配）
                end = i + 1
            out.append(text[i:end])
            i = end
        return out

    @staticmethod
    def _m_contraction(text: str, i: int) -> int | None:
        low = text[i:i + 4].lower()
        for c in _CONTRACTIONS:
            if low.startswith(c):
                return i + len(c)
        return None

    @staticmethod
    def _m_optional_letter(text: str, i: int) -> int | None:
        n = len(text)
        if i < n and text[i] not in _CRLF and not _is_letter(text[i]) \
                and not _is_number(text[i]):
            j = i + 1
            if j < n and _is_letter(text[j]):
                k = j
                while k < n and _is_letter(text[k]):
                    k += 1
                return k
        if i < n and _is_letter(text[i]):
            k = i
            while k < n and _is_letter(text[k]):
                k += 1
            return k
        return None

    @staticmethod
    def _m_number(text: str, i: int) -> int | None:
        return i + 1 if i < len(text) and _is_number(text[i]) else None

    @staticmethod
    def _m_space_symbols(text: str, i: int) -> int | None:
        n = len(text)
        start = None
        if i < n and text[i] == " " and i + 1 < n and _is_other(text[i + 1]):
            start = i + 1
        elif i < n and _is_other(text[i]):
            start = i
        if start is None:
            return None
        k = start
        while k < n and _is_other(text[k]):
            k += 1
        while k < n and text[k] in _CRLF:
            k += 1
        return k

    @staticmethod
    def _m_ws_newline(text: str, i: int) -> int | None:
        n = len(text)
        e = i
        while e < n and _is_space(text[e]):
            e += 1
        if e == i:
            return None
        p = e
        while p > i and text[p - 1] in _CRLF:
            p -= 1
        if p < e:                      # 空白 run 以换行结尾 → 整段匹配
            return e
        q = e                          # run 末尾不是换行：找最后一个换行
        while q > i and text[q - 1] not in _CRLF:
            q -= 1
        if q == i:
            return None
        r = q
        while r < n and text[r] in _CRLF:
            r += 1
        return r

    @staticmethod
    def _m_ws_not_followed(text: str, i: int) -> int | None:
        """`\\s+(?!\\S)`：贪心后回退一位即可满足"后面不是非空白"。"""
        n = len(text)
        e = i
        while e < n and _is_space(text[e]):
            e += 1
        if e == i:
            return None
        if e == n:
            return n
        return e - 1 if e - 1 > i else None

    @staticmethod
    def _m_ws(text: str, i: int) -> int | None:
        n = len(text)
        e = i
        while e < n and _is_space(text[e]):
            e += 1
        return e if e > i else None

    # ---- BPE ----

    def _bpe(self, piece: str) -> list[str]:
        """对单段（已映射到字节空间）做 BPE 合并，返回 token 字符串序列。

        实现 = 双向链表 + 最小堆（懒失效校验）：每轮合并**当前序列中排名最小**的相邻对，
        与朴素实现语义等价，但对长串（整段无空白的正文/代码）是 O(n log n)。
        P8C 实测：朴素实现在 15000 字符单段上耗时 > 300 s——会拖垮准入判断本身；
        正确性由 `tools/tokenizer_parity.py` 对 Rust 参考实现逐 id 比对锁定。
        """
        if not piece:
            return []
        n = len(piece)
        if n == 1:
            return [piece]
        text = list(piece)
        nxt = [i + 1 for i in range(n)]
        nxt[n - 1] = -1
        prev = [i - 1 for i in range(n)]
        alive = [True] * n
        ranks = self._ranks
        heap: list[tuple[int, int, int]] = []

        def push(left: int) -> None:
            if left < 0 or not alive[left]:
                return
            right = nxt[left]
            if right < 0 or not alive[right]:
                return
            r = ranks.get((text[left], text[right]))
            if r is not None:
                heapq.heappush(heap, (r, left, right))

        for i in range(n - 1):
            push(i)
        while heap:
            r, left, right = heapq.heappop(heap)
            if not alive[left] or nxt[left] != right or not alive[right]:
                continue                      # 已被更早的合并失效
            if ranks.get((text[left], text[right])) != r:
                continue                      # 内容已变，条目过期
            text[left] = text[left] + text[right]
            alive[right] = False
            nxt[left] = nxt[right]
            if nxt[left] >= 0:
                prev[nxt[left]] = left
            push(prev[left])
            push(left)
        out: list[str] = []
        i = 0
        while i >= 0:
            out.append(text[i])
            i = nxt[i]
        return out

    def _encode_plain(self, text: str) -> list[int]:
        ids: list[int] = []
        for piece in self.pre_tokenize(text):
            mapped = "".join(self._b2u[b] for b in piece.encode("utf-8"))
            for tok in self._bpe(mapped):
                tid = self._token_to_id.get(tok)
                if tid is None:
                    raise TokenizerUnavailable(
                        f"BPE 结果不在词表中：{tok!r}（pre-token={piece!r}）——"
                        "实现与权重不一致，拒绝给出计数")
                ids.append(tid)
        return ids

    def encode(self, text: str, *, allow_special: bool = True) -> list[int]:
        """编码文本；`allow_special` 时特殊 token 原子匹配（与 HF 默认一致）。"""
        if not allow_special or not self._special_ids:
            return self._encode_plain(text)
        ids: list[int] = []
        buf: list[str] = []
        i, n = 0, len(text)
        while i < n:
            if text[i] in self._special_first_chars:
                hit = None
                for length in range(min(self._max_special_len, n - i), 2, -1):
                    cand = text[i:i + length]
                    if cand in self._special_ids:
                        hit = cand
                        break
                if hit is not None:
                    if buf:
                        ids.extend(self._encode_plain("".join(buf)))
                        buf = []
                    ids.append(self._token_to_id[hit])
                    i += len(hit)
                    continue
            buf.append(text[i])
            i += 1
        if buf:
            ids.extend(self._encode_plain("".join(buf)))
        return ids

    # ---- chat template ----

    def render_chat(self, messages: Sequence[Mapping[str, Any]], *,
                    add_generation_prompt: bool = True,
                    template: str | None = None) -> str:
        """用权重自带的 Jinja 模板渲染 chat（默认 add_generation_prompt=True）。

        Ollama `/api/chat` 的等价渲染；模板缺失/渲染失败 → 明确失败（不退化为近似拼接）。
        """
        try:
            _jinja_env()
        except Exception as e:      # noqa: BLE001
            raise TokenizerUnavailable(
                f"缺少 jinja2，无法离线渲染 chat template：{e}") from e
        tpl = template if template is not None else self.chat_template
        if not tpl:
            raise TokenizerUnavailable("权重未携带 chat_template，无法做模板级计数")
        compiled = _compiled_template(tpl)

        def _raise(msg: str):
            raise TokenizerUnavailable(f"chat template 渲染失败：{msg}")

        # 与 transformers 的 chat template 环境一致（trim_blocks/lstrip_blocks=True）：
        # 否则块标签后的换行会残留，渲染串与模型实际看到的提示不同（P8C 实测发现）。
        env = _jinja_env()
        try:
            return compiled.render(
                messages=list(messages), add_generation_prompt=add_generation_prompt,
                tools=None, bos_token="", eos_token="")
        except TokenizerUnavailable:
            raise
        except Exception as e:      # noqa: BLE001
            raise TokenizerUnavailable(f"chat template 渲染异常：{e}") from e

    def count_chat(self, messages: Sequence[Mapping[str, Any]], *,
                   add_generation_prompt: bool = True) -> TokenCount:
        """整条 chat 提示的**精确 token 数**（模板 + 特殊 token 全部计入）。"""
        rendered = self.render_chat(messages, add_generation_prompt=add_generation_prompt)
        ids = self.encode(rendered)
        n_special = sum(1 for i in ids if self.tokens[i] in self._special_ids)
        return TokenCount(n_tokens=len(ids), method="gguf_bpe",
                          source_manifest_sha256=self.source_manifest_sha256,
                          source_blob_digest=self.source_blob_digest,
                          n_special_tokens=n_special,
                          n_text_segments=len(self.pre_tokenize(rendered)))

    def count_text(self, text: str, *, allow_special: bool = True) -> TokenCount:
        ids = self.encode(text, allow_special=allow_special)
        return TokenCount(n_tokens=len(ids), method="gguf_bpe",
                          source_manifest_sha256=self.source_manifest_sha256,
                          source_blob_digest=self.source_blob_digest)

    def to_dict(self) -> dict:
        """计数后端的身份摘要（进 provenance：词表来源与规模，便于独立复算）。"""
        return {
            "impl": "src/llm/offline_tokenizer.py（纯标准库 Qwen2 BPE）",
            "n_vocab": len(self.tokens),
            "n_merges": len(self.merges),
            "n_special_tokens": len(self._special_ids),
            "pre_tokenizer": self.pre,
            "add_bos_token": self.add_bos_token,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_blob_digest": self.source_blob_digest,
            "source_blob_bytes": self.source_blob_bytes,
        }


_TOKENIZERS: dict[str, Qwen2OfflineTokenizer] = {}


def get_tokenizer(path: str | Path | None = None) -> Qwen2OfflineTokenizer:
    """按**路径**缓存的单例（加载约 0.15 s；只读、构建后不可变，可并发读）。

    按路径缓存而不是全局单例：调用方若显式给出别的词表路径，绝不能静默拿到旧的词表
    （那会让"精确计数"用到与权重不符的词表）。
    """
    key = str(Path(path) if path is not None else DEFAULT_VOCAB)
    tok = _TOKENIZERS.get(key)
    if tok is None:
        tok = Qwen2OfflineTokenizer.from_file(key)
        _TOKENIZERS[key] = tok
    return tok


def count_tokens(text: str, *, path: str | Path | None = None) -> int:
    return get_tokenizer(path).count_text(text).n_tokens


def decode(ids: Iterable[int], *, path: str | Path | None = None) -> str:
    """token id → 文本（调试/校验用；反向映射字节空间）。"""
    tok = get_tokenizer(path)
    rev = {v: k for k, v in bytes_to_unicode().items()}
    out = bytearray()
    for i in ids:
        s = tok.tokens[i]
        if s in tok._special_ids:
            out.extend(s.encode("utf-8"))
            continue
        out.extend(bytes(rev[ch] for ch in s))
    return out.decode("utf-8", errors="replace")
