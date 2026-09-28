"""生成 RAG-REBUILD v1.0 的冻结候选记录（文件清单 + 指纹 + 前端 BUILD_ID）。"""

import hashlib
import json
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main() -> int:
    raw = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    ).stdout
    manifest_path = ROOT / "docs/qa/RAG-REBUILD-v1/FROZEN-CANDIDATE.json"
    entries = []
    for line in raw.splitlines():
        status, path = line[:2].strip(), line[3:].strip().strip('"')
        target = ROOT / path
        if not target.is_file():
            continue
        if target == manifest_path:
            # 清单自身不参与哈希：否则每次重算都会改变自己，永远无法自洽
            continue
        entries.append(
            {
                "path": path.replace("\\", "/"),
                "status": status,
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    build_id = (ROOT / "apps/web/.next/BUILD_ID").read_text(encoding="utf-8").strip()
    record = {
        "taskId": "RAG-REBUILD-v1",
        "version": "v1",
        "frozenAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "baseCommit": "c2f31ec0a70fc9b9e9d38479b6c193416c19befb",
        "hashSource": "sha256(file bytes)",
        "frontendBuildId": build_id,
        "changedFileCount": len(entries),
        "files": entries,
        "note": (
            "候选为工作树（未提交）。验收期间不得再改产品代码；需要修复时升级版本并重新冻结。"
            "本清单不包含自身（排除自引用），也不包含 Next 自动生成的 next-env.d.ts 之外的构建产物。"
        ),
    }
    out = manifest_path
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"files={len(entries)} BUILD_ID={build_id}")
    print(f"written={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
