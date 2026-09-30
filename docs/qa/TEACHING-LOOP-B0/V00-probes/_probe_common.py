"""V00 独立验收探针公共工具（只读候选代码；所有数据落临时目录）。

用法：探针脚本首行 ``from _probe_common import ...``（脚本自身目录即 sys.path[0]）。
不读写正式 .local-data / apps/api/.env / F:\\人教版教材 / 真实 Qdrant。
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# 隔离默认数据根（与 apps/api/tests/conftest.py 同一手法）：`app.main` 在**导入时**执行
# 模块级 create_app()，会对默认数据根（仓库 .local-data）建库/迁移。探针在导入 app.* 之前
# 把 ZQKY_DATA_DIR 指向会话级临时目录，确保不读写正式 .local-data（显式设置优先）。
_PROBE_DATA_DIR = tempfile.mkdtemp(prefix="zqky-v00-probe-env-")
os.environ.setdefault("ZQKY_DATA_DIR", _PROBE_DATA_DIR)
atexit.register(shutil.rmtree, _PROBE_DATA_DIR, ignore_errors=True)

EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

_RESULTS: list[tuple[str, bool, str]] = []
_OBSERVATIONS: list[tuple[str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(ok), detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""), flush=True)


def observe(name: str, detail: str) -> None:
    """记录不参与 pass/fail 判定的口径观察项（报告 observation 列表的来源）。"""
    _OBSERVATIONS.append((name, detail))
    print(f"[OBS ] {name} :: {detail}", flush=True)


def check(name: str, condition: bool, detail: str = "") -> None:
    record(name, condition, detail)


def expect_error(name: str, exc: BaseException, code: str) -> None:
    actual = getattr(exc, "code", None)
    record(
        name,
        actual == code,
        f"expected code={code} got code={actual!r} type={type(exc).__name__} msg={exc}",
    )


def temp_root(prefix: str) -> Path:
    """新建本次探针独占的临时数据根（放在系统 temp，不进仓库）。"""
    return Path(tempfile.mkdtemp(prefix=f"zqky-v00-{prefix}-"))


def cleanup(path: Path | None) -> None:
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)


def finish(probe_name: str) -> int:
    failed = [name for name, ok, _ in _RESULTS if not ok]
    summary = {
        "probe": probe_name,
        "total": len(_RESULTS),
        "failed": failed,
        "results": [{"name": n, "ok": ok, "detail": d} for n, ok, d in _RESULTS],
        "observations": [{"name": n, "detail": d} for n, d in _OBSERVATIONS],
    }
    out = EVIDENCE_DIR / f"{probe_name}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\n== {probe_name}: {len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed; "
        f"failed={failed}; observations={[n for n, _ in _OBSERVATIONS]} ==\n证据：{out}",
        flush=True,
    )
    return 1 if failed else 0


def run_main(probe_name: str, fn) -> None:
    """执行探针主体；未捕获异常按 fail 记录并保留首败栈。"""
    try:
        fn()
    except BaseException:  # noqa: BLE001 - 探针必须留全栈
        record(f"{probe_name}.uncaught", False, traceback.format_exc().splitlines()[-1])
        traceback.print_exc()
    raise SystemExit(finish(probe_name))
