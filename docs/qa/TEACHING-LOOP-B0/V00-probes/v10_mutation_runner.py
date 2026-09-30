"""V10 变异实验运行器（V00 / TEACHING-LOOP B0）。

在不改动候选文件的前提下做"有牙齿"验证：把候选模块的源码读入内存 → 写入系统临时区的
**自己副本** → 以真实模块名注入 sys.modules 覆盖 → 再跑实现方测试 / 自己的探针，
观察关键断言是否失败。候选仓库文件全程只读；结束后由 `v10_hash_reconcile.py` 复算 55 个
sha256 对账 FROZEN-CANDIDATE.json。

用法：
  uv run python v10_mutation_runner.py --file <相对路径> --old <原文> --new <变异> \
      [--pytest <测试文件…>] [--probe <探针脚本…>] [--label M1]
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import re
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from _probe_common import API_ROOT, EVIDENCE_DIR, REPO_ROOT

INJECTED: list[str] = []


def _load_mutated(relative: str, old: str, new: str) -> str:
    source_path = REPO_ROOT / relative
    original = source_path.read_text(encoding="utf-8")
    if original.count(old) != 1:
        raise SystemExit(f"变异锚点必须唯一：{relative} 命中 {original.count(old)} 次：{old!r}")
    mutated = original.replace(old, new)
    module_name = ".".join(Path(relative).relative_to("apps/api").with_suffix("").parts)

    temporary_dir = Path(tempfile.mkdtemp(prefix="zqky-v00-mutation-"))
    target = temporary_dir / Path(relative).name
    target.write_text(mutated, encoding="utf-8")

    # 先正常导入一次，建立父包链（避免 __init__ 的再导出触发循环导入）
    import importlib

    importlib.import_module(module_name)

    spec = importlib.util.spec_from_file_location(module_name, target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    # 让父包的同名属性与再导出名都指向变异模块（覆盖 `from <pkg> import X` 的路径）
    parent_name, _, leaf = module_name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, leaf, module)
        for name in getattr(module, "__all__", ()):  # 重绑定 __init__ 的再导出名
            if hasattr(module, name):
                setattr(parent, name, getattr(module, name))
    INJECTED.append(module_name)
    # 若变异模块是被"注册表在导入期已构建"的包引用（例如 app.core.migrations 的
    # REGISTERED_MIGRATIONS），仅替换 sys.modules 不够——需要把注册表项重指到变异模块，
    # 否则测试实际执行的是真模块（这是探针基建问题，不是候选问题）。
    if getattr(module, "MIGRATIONS", None) is not None:
        registry_package = sys.modules.get("app.core.migrations")
        registry = getattr(registry_package, "REGISTERED_MIGRATIONS", None)
        target_name = Path(relative).stem
        if isinstance(registry, dict) and target_name in registry:
            registry[target_name] = module.MIGRATIONS
            print(f"[MUT] REGISTERED_MIGRATIONS[{target_name!r}] 已重指到变异模块", flush=True)
    print(f"[MUT] {module_name} 变异生效（临时副本 {target}；候选文件未改）", flush=True)
    print(f"[MUT] {old.strip()[:70]!r} -> {new.strip()[:70]!r}", flush=True)
    return module_name


def _run_pytest(targets: list[str]) -> dict:
    import pytest

    arguments = ["-q", "--no-header", "-p", "no:cacheprovider", *targets]
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        try:
            code = pytest.main(arguments)
        except SystemExit as exc:  # pragma: no cover
            code = exc.code
    output = buffer.getvalue()
    failed = sorted(set(re.findall(r"FAILED ([^\s]+)", output)))
    tail = "\n".join(line for line in output.splitlines() if line.strip())[-1500:]
    print(f"[MUT] pytest 退出码={code}；失败用例={len(failed)}", flush=True)
    for item in failed[:10]:
        print(f"[MUT]   FAILED {item}", flush=True)
    return {"kind": "pytest", "exit_code": int(code or 0), "failed": failed, "tail": tail, "targets": targets}


def _run_probe(path: str) -> dict:
    import runpy

    buffer = io.StringIO()
    code = 0
    with redirect_stdout(buffer), redirect_stderr(buffer):
        try:
            runpy.run_path(path, run_name="__main__")
        except SystemExit as exc:
            code = int(exc.code or 0)
        except BaseException:
            code = 70
            traceback.print_exc()
    output = buffer.getvalue()
    failures = [line.strip() for line in output.splitlines() if line.strip().startswith("[FAIL]")]
    print(f"[MUT] 探针退出码={code}；失败断言={len(failures)}", flush=True)
    for line in failures[:10]:
        print(f"[MUT]   {line}", flush=True)
    return {"kind": "probe", "exit_code": code, "failed": failures, "tail": output[-1500:], "targets": [path]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="候选文件（相对仓库根）")
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--label", default="mutation")
    parser.add_argument("--pytest", nargs="*", default=[])
    parser.add_argument("--probe", nargs="*", default=[])
    args = parser.parse_args()

    print(f"== V10 变异实验 {args.label} ==", flush=True)
    _load_mutated(args.file, args.old, args.new)
    results = {"label": args.label, "file": args.file, "old": args.old, "new": args.new, "runs": []}
    for target in args.pytest:
        results["runs"].append(_run_pytest([target]))
    for target in args.probe:
        results["runs"].append(_run_probe(target))

    import json

    out = EVIDENCE_DIR / f"v10_{args.label}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    total_failed = sum(len(run["failed"]) for run in results["runs"])
    print(f"== {args.label}：共观察 {total_failed} 个失败断言；证据 {out} ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
