"""版本化索引规格：把「检索空间（chunks）」与「向量索引（index_dir）」的**成对身份**
写成可核对的契约（P10 修复批）。

缺陷背景（本模块要解决的问题）
------------------------------
两条入口各自带**隐式缺省**，成对关系没有任何地方声明：
  - `src/locate_cli.py` 的 `--chunks` 与 `--index-dir` 各自有缺省值，两边可以来自
    不同批次而"看起来都能跑"；
  - 批处理入口 `tools/p8h_gen88.py` 把 chunks 路径写死在代码里，另一半（索引目录）
    靠 `build_searcher_provider` 的缺省——改一侧就会静默错绑。
AGENTS 硬约束 2（检索空间只能是判定为正文的块）要求这种失配必须**硬失败**，
不能靠"默认值恰好配对"来保证。

契约（单一定义点）
------------------
1. 规格清单只有一份：`configs/index_specs.yaml`（name/version/chunks_path/index_dir/
   expected_chunks_sha256/expected_body_n/role）。**不得声明 default**——缺省就是缺陷来源。
2. `resolve_index_identity()` 只接受两种输入：
     - `index_spec="<name>"`（规格名），或
     - **同时**显式给 `chunks=` 与 `index_dir=`（临时/新建索引，无声明期望值）。
   其它组合（都不给、只给一侧、两者同时给）→ `IndexSpecError`（非零退出，不回落、不自动改选）。
3. `verify_index_identity()` 做四项核对：chunks 文件指纹 == 规格声明值、
   正文块数 == 规格声明值、索引 meta 的 `chunks_fingerprint` == chunks 实际指纹、
   向量行数 == 正文块数（且行序/维度/模型身份交给 `src/retrieval/session.py`
   的既有唯一实现点）。任一项不符 → `IndexSpecError`（不重建、不改选、不回落云端）。
4. 核对结果（规格名 + 版本 + chunks 指纹 + index_dir + 各项声明值/实测值）回传成
   `INDEX_PROVENANCE_KEYS` 描述的字典，由入口写进 `provenance` 与运行台账。

本模块只做"解析与核对"，不建索引、不改选、不写任何产物。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from app.services.rag_engine.retrieval.session import (IndexIdentityError, IndexSnapshot,
                                   get_snapshot, load_verified_snapshot)

ROOT = Path(__file__).resolve().parents[2]

#: 唯一规格清单（相对项目根）
DEFAULT_SPECS_PATH = ROOT / "configs" / "index_specs.yaml"

#: 显式成对（未由规格声明）时记录到 provenance 的标签
EXPLICIT_PAIR_LABEL = "（显式 --chunks + --index-dir，非规格声明）"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ROLES = ("active", "legacy", "shadow", "explicit-pair")

#: 索引身份进入 provenance / 运行台账的字段（生产者与消费者共用同一份清单）
INDEX_PROVENANCE_KEYS: tuple[str, ...] = (
    "index_spec", "index_spec_version", "index_spec_role", "index_spec_source",
    "index_spec_declared", "index_identity_verified",
    "chunks_path", "chunks_fingerprint",
    "index_dir", "index_chunks_fingerprint", "index_vector_rows",
    "index_dim", "index_model_id",
    "expected_chunks_sha256", "expected_body_n",
)


class IndexSpecError(IndexIdentityError):
    """规格缺失/非法，或 chunks 与索引身份失配。

    `IndexIdentityError` 的子类：与 `src/retrieval/session.py` 的四项核对同族，
    调用方一律**硬失败**（非零退出、不回落、不自动改选、不重建）。
    """


#: 索引身份/成对契约不满足时的进程退出码（`src/locate_cli.py` 与三个评测入口共用）
EXIT_INDEX_CONTRACT = 3


@dataclass(frozen=True)
class IndexSpec:
    """一次运行实际绑定的索引身份。

    `declared=True` 时来自 `configs/index_specs.yaml`（有独立声明的期望值）；
    `declared=False` 时是命令行显式成对（`expected_*` 为 None，只做四项目实录核对）。
    """

    name: str | None
    version: str | None
    chunks_path: Path
    index_dir: Path
    expected_chunks_sha256: str | None
    expected_body_n: int | None
    role: str
    declared: bool
    source: str | None
    note: str = ""

    @property
    def label(self) -> str:
        """人读标签（provenance/打印/错误信息共用）。"""
        if self.declared and self.name:
            return f"{self.name}@{self.version}"
        return EXPLICIT_PAIR_LABEL


def _abs(path: str | Path, base_dir: str | Path | None = None) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (Path(base_dir) if base_dir is not None else ROOT) / p


def _display(path: str | Path) -> str:
    """provenance 里记**项目根相对**路径（可迁移），根外路径记绝对路径。"""
    p = _abs(path)
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p)


def _require(entry: Mapping[str, Any], key: str, name: str) -> Any:
    if key not in entry or entry[key] in (None, ""):
        raise IndexSpecError(f"索引规格 {name!r} 缺字段 {key}（规格不完整即不可用）")
    return entry[key]


def _parse_spec(name: str, entry: Any, *, source: str,
                base_dir: str | Path | None = None) -> IndexSpec:
    if not isinstance(entry, Mapping):
        raise IndexSpecError(f"索引规格 {name!r} 不是字典（{source}）")
    declared_name = str(_require(entry, "name", name))
    if declared_name != name:
        raise IndexSpecError(f"索引规格键 {name!r} 与条目内 name={declared_name!r} 不一致")
    version = str(_require(entry, "version", name))
    chunks_path = str(_require(entry, "chunks_path", name))
    index_dir = str(_require(entry, "index_dir", name))
    fp = str(_require(entry, "expected_chunks_sha256", name)).strip().lower()
    if not _SHA256_RE.match(fp):
        raise IndexSpecError(
            f"索引规格 {name!r} 的 expected_chunks_sha256 不是 64 位十六进制：{fp!r}")
    body_n = _require(entry, "expected_body_n", name)
    if isinstance(body_n, bool) or not isinstance(body_n, int) or body_n <= 0:
        raise IndexSpecError(f"索引规格 {name!r} 的 expected_body_n 必须是正整数：{body_n!r}")
    role = str(entry.get("role") or "").strip() or "unspecified"
    if role not in _ROLES:
        raise IndexSpecError(f"索引规格 {name!r} 的 role={role!r} 非法（可选 {list(_ROLES)}）")
    return IndexSpec(name=name, version=version, chunks_path=_abs(chunks_path, base_dir),
                     index_dir=_abs(index_dir, base_dir), expected_chunks_sha256=fp,
                     expected_body_n=int(body_n), role=role, declared=True,
                     source=source, note=str(entry.get("note") or "").strip())


def load_index_specs(path: str | Path | None = None, *,
                     base_dir: str | Path | None = None) -> dict[str, IndexSpec]:
    """读唯一规格清单。文件缺失/非法即 `IndexSpecError`（不内置任何兜底规格）。"""
    p = _abs(path) if path else DEFAULT_SPECS_PATH
    if not p.is_file():
        raise IndexSpecError(
            f"索引规格清单不存在：{_display(p)}——入口必须能读到唯一清单；"
            f"没有内置兜底、也没有隐式缺省")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise IndexSpecError(f"索引规格清单不是字典：{_display(p)}")
    if "default" in raw or "default_spec" in raw:
        raise IndexSpecError(
            "索引规格清单不得声明 default/default_spec——缺省是缺陷来源，"
            "入口必须显式选择规格名或显式成对")
    specs_raw = raw.get("specs")
    if not isinstance(specs_raw, Mapping) or not specs_raw:
        raise IndexSpecError(f"索引规格清单缺 specs 段或为空：{_display(p)}")
    source = _display(p)
    out: dict[str, IndexSpec] = {}
    for name, entry in specs_raw.items():
        spec = _parse_spec(str(name), entry, source=source, base_dir=base_dir)
        out[str(name)] = spec
    return out


def get_index_spec(name: str, path: str | Path | None = None, *,
                   base_dir: str | Path | None = None) -> IndexSpec:
    """按名取规格。未知名字 → `IndexSpecError`（**不回落**到任何其它规格/路径）。"""
    specs = load_index_specs(path, base_dir=base_dir)
    if name not in specs:
        raise IndexSpecError(
            f"未知索引规格 {name!r}（可用：{sorted(specs)}）——不回落、不自动改选")
    return specs[name]


def resolve_index_identity(*, index_spec: str | None = None,
                           chunks: str | Path | None = None,
                           index_dir: str | Path | None = None,
                           specs_path: str | Path | None = None) -> IndexSpec:
    """把入口参数解析成**唯一**索引身份。

    只接受两种形态：规格名，或 chunks+index_dir **成对**显式给出。
    其余组合一律硬失败（缺一侧、只给一侧、两者同时给）。
    """
    if index_spec and (chunks is not None or index_dir is not None):
        raise IndexSpecError(
            "索引身份只能二选一：--index-spec <name> 或**同时**给 "
            "--chunks + --index-dir（两者同时给，实际生效的是哪一个就不可复核）")
    if index_spec:
        return get_index_spec(index_spec, specs_path)
    if chunks is None and index_dir is None:
        raise IndexSpecError(
            "未指定索引身份：必须给 --index-spec <name>，或同时给 --chunks + --index-dir"
            f"（可用规格：{sorted(load_index_specs(specs_path))}）——"
            "无隐式缺省、不回落、不自动改选")
    if chunks is None or index_dir is None:
        missing = "--index-dir" if index_dir is None else "--chunks"
        raise IndexSpecError(
            f"--chunks 与 --index-dir 必须**成对**显式给出（当前缺 {missing}）："
            "只给一侧等于另一半身份不明，拒绝按缺省补")
    cp, idr = _abs(chunks), _abs(index_dir)
    if not cp.is_file():
        raise IndexSpecError(f"chunks 文件不存在：{_display(cp)}")
    if not idr.is_dir():
        raise IndexSpecError(f"索引目录不存在：{_display(idr)}")
    return IndexSpec(name=None, version=None, chunks_path=cp, index_dir=idr,
                     expected_chunks_sha256=None, expected_body_n=None,
                     role="explicit-pair", declared=False,
                     source=None, note="命令行显式成对，未由 configs/index_specs.yaml 声明")


def index_dir_artifacts(index_dir: str | Path, model_ns: str, dim: int,
                        tag: str = "cch") -> dict:
    """索引目录内**实际文件**的指纹（评测报告 provenance 用，不编造）。

    键：`index_meta_path` / `index_meta_sha256` / `vectors_path` / `vectors_sha256`；
    文件不存在时对应值为 None（如实记 None，不写假值、不跳过报告）。
    """
    ns_dir = _abs(index_dir) / model_ns
    meta_p = ns_dir / f"index_meta_{int(dim)}_{tag}.json"
    vec_p = ns_dir / f"vectors_{int(dim)}_{tag}.npy"
    return {
        "index_meta_path": _display(meta_p),
        "index_meta_sha256": _sha256_file(meta_p),
        "vectors_path": _display(vec_p),
        "vectors_sha256": _sha256_file(vec_p),
    }


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_index_identity(identity: IndexSpec, *, dim: int, model_ns: str,
                          model_id: str, tag: str = "cch",
                          session_cache: bool = True) -> tuple[IndexSnapshot, dict]:
    """核对身份并返回 (快照, provenance 字段)。

    ① chunks 指纹 == 规格声明值（未声明则跳过，只做实测比对）；
    ② 正文块数 == 规格声明值；
    ③ 索引 meta 的 `chunks_fingerprint` == chunks 实际指纹 + 行序一致 + 形状
       + 模型身份（**复用** `src/retrieval/session.py` 的单一定义点）；
    ④ 向量行数 == 正文块数。
    任一不符 → `IndexSpecError`（不自动重建、不自动改选、不回落）。
    """
    kwargs = dict(chunks_path=identity.chunks_path, index_dir=identity.index_dir,
                  model_ns=model_ns, dim=dim, tag=tag, model_id=model_id)
    try:
        snap = get_snapshot(**kwargs) if session_cache else load_verified_snapshot(**kwargs)
    except IndexIdentityError as e:
        raise IndexSpecError(
            f"索引身份校验失败（规格 {identity.label}）：{e}"
            f"——不自动重建、不自动改选、不回落") from e

    actual_fp = str(snap.chunks_fingerprint)
    meta_fp = str(snap.meta.get("chunks_fingerprint") or "")
    actual_body_n = len(snap.body)
    rows = int(snap.vectors.shape[0])

    if not meta_fp:
        raise IndexSpecError(
            f"索引 meta 未登记 chunks_fingerprint（{_display(identity.index_dir)}）"
            f"——无法核对，拒绝使用（规格 {identity.label}）")
    if identity.expected_chunks_sha256 and actual_fp != identity.expected_chunks_sha256:
        raise IndexSpecError(
            f"规格 {identity.label} 声明的 chunks 指纹 "
            f"{identity.expected_chunks_sha256[:16]}… != 实际 {actual_fp[:16]}…"
            f"（{_display(identity.chunks_path)}）——切分产物与规格不符，"
            f"硬失败，不自动改选")
    if identity.expected_body_n is not None and actual_body_n != identity.expected_body_n:
        raise IndexSpecError(
            f"规格 {identity.label} 声明的正文块数 {identity.expected_body_n} != 实际 "
            f"{actual_body_n}（{_display(identity.chunks_path)}）——硬失败，不自动改选")
    if rows != actual_body_n:
        raise IndexSpecError(
            f"向量行数 {rows} != 正文块数 {actual_body_n}"
            f"（索引 {_display(identity.index_dir)}）——硬失败，不自动改选")

    provenance = {
        "index_spec": identity.name,
        "index_spec_version": identity.version,
        "index_spec_role": identity.role,
        "index_spec_source": identity.source,
        "index_spec_declared": bool(identity.declared),
        "index_identity_verified": True,
        "chunks_path": _display(identity.chunks_path),
        "chunks_fingerprint": actual_fp,
        "index_dir": _display(identity.index_dir),
        "index_chunks_fingerprint": meta_fp,
        "index_vector_rows": rows,
        "index_dim": int(dim),
        "index_model_id": snap.meta.get("model_id"),
        "expected_chunks_sha256": identity.expected_chunks_sha256,
        "expected_body_n": identity.expected_body_n,
    }
    return snap, provenance
