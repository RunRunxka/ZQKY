"""V00 独立验收探针公共设施（TEACHING-LOOP B1）。

纪律（B0 教训）：
- **任何**导入 ``app.*`` 之前先设 ``ZQKY_DATA_DIR`` 指向临时目录；绝不读写正式
  ``.local-data``、``.env``。
- 探针不修改候选：只读产品代码，写只发生在 ``V00-probes/evidence`` 与临时目录。
- 不联网、不启动 Qdrant；模型一律受控替身。

用法：
    from _probe_common import Probe, temp_data_root
    p = Probe("v1")
    p.check("...", ok, detail)
    p.finish()          # 写 evidence/<name>.json，返回退出码
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROBE_DIR.parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
FORMAL_DATA_DIR = REPO_ROOT / ".local-data"

#: 变异实验（V10）用：把被测 app 包指向一份**副本**（候选工作区永不被改）
APP_ROOT = Path(os.environ.get("ZQKY_PROBE_APP_ROOT") or API_ROOT).resolve()
#: 变异实验用：证据写到别处，避免覆盖基线证据
EVIDENCE_DIR = Path(
    os.environ.get("ZQKY_PROBE_EVIDENCE_DIR") or (PROBE_DIR / "evidence")
).resolve()

_EVIDENCE_TMP: list[str] = []


def guard_no_formal_data() -> None:
    """确认 ZQKY_DATA_DIR 已设且不指向正式数据根（防呆）。"""
    raw = os.environ.get("ZQKY_DATA_DIR")
    assert raw, "必须先设 ZQKY_DATA_DIR 再导入 app.*"
    resolved = Path(raw).resolve()
    formal = FORMAL_DATA_DIR.resolve()
    if resolved == formal or formal in resolved.parents:
        raise SystemExit(f"拒绝在正式数据根上运行探针：{resolved}")


def temp_data_root(tag: str) -> Path:
    """建一个临时数据根并把 ZQKY_DATA_DIR 指过去（导入 app.* 之前调用）。"""
    root = Path(tempfile.mkdtemp(prefix=f"zqky-v00-{tag}-")).resolve()
    _EVIDENCE_TMP.append(str(root))
    os.environ["ZQKY_DATA_DIR"] = str(root)
    return root


def cleanup_temp_roots() -> None:
    for raw in _EVIDENCE_TMP:
        shutil.rmtree(raw, ignore_errors=True)
    _EVIDENCE_TMP.clear()


class Probe:
    def __init__(self, name: str) -> None:
        self.name = name
        self.results: list[dict] = []
        self.crashed: str | None = None

    def check(self, name: str, ok: bool, detail: object = "") -> bool:
        self.results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:2000]})
        print(f"[{'OK ' if ok else 'FAIL'}] {name} :: {str(detail)[:300]}")
        return bool(ok)

    def expect_error(self, name: str, exc: BaseException, code: str | None = None, status: int | None = None) -> bool:
        got_code = getattr(exc, "code", None)
        got_status = getattr(exc, "status_code", None)
        ok = True
        detail = f"{type(exc).__name__}(code={got_code}, status={got_status}) {exc}"
        if code is not None and got_code != code:
            ok = False
        if status is not None and got_status != status:
            ok = False
        return self.check(name, ok, detail)

    def run(self, name: str, fn, *args, **kwargs):
        """执行一个子步骤；异常记录为 FAIL 并继续（不整探针崩）。"""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self.check(name, False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}")
            return None

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item["ok"])

    @property
    def failed(self) -> list[dict]:
        return [item for item in self.results if not item["ok"]]

    def finish(self) -> int:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "probe": self.name,
            "passed": self.passed,
            "failed": len(self.failed),
            "total": len(self.results),
            "results": self.results,
            "crashed": self.crashed,
        }
        out = EVIDENCE_DIR / f"{self.name}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n== {self.name}: {self.passed}/{len(self.results)} pass, {len(self.failed)} fail ==")
        print(f"evidence: {out}")
        for item in self.failed:
            print(f"  FAIL: {item['name']} :: {item['detail'][:300]}")
        return 1 if self.failed or self.crashed else 0


def ensure_api_on_path() -> None:
    raw = str(APP_ROOT)
    if raw not in sys.path:
        sys.path.insert(0, raw)
