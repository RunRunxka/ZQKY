"""生成 RAG-REBUILD v1.0 的冻结候选记录（文件清单 + 指纹 + 前端 BUILD_ID）。"""

import hashlib
import json
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="生成批次冻结候选记录（默认输出到批次目录）")
    parser.add_argument("--batch", required=True, help="批次目录名，例如 RAG-QUALITY-v1")
    parser.add_argument("--base-commit", default="", help="验收基线提交（默认取 HEAD）")
    args = parser.parse_args(argv)
    raw = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    ).stdout
    batch_dir = ROOT / "docs/qa" / args.batch
    if not batch_dir.is_dir():
        raise SystemExit(f"批次目录不存在（先建目录，避免把清单写到别处）：{batch_dir}")
    manifest_path = batch_dir / "FROZEN-CANDIDATE.json"
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
        "baseCommit": args.base_commit or subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
        ).stdout.strip(),
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
