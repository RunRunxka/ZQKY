"""把归档里的 markdown 恢复到 F:\\人教版教材\\markdown（只补 .md，不覆盖既有文件）。

背景：迁移脚本早期把**源文件**直接传给上传暂存接口（该接口是移动语义），
把这批 .md 从源目录搬走了。文件内容并未丢失（在归档 zip 与受管 blobs 里），
本脚本负责把源目录恢复到原状。

安全约束：
- 只写 `.md`，只写 `F:\\人教版教材\\markdown` 下；
- **已存在的文件一律跳过**（不覆盖用户任何现有内容）；
- 先解到临时目录校验，再落盘；
- 默认 `--dry-run`，要真正写入必须显式 `--apply`。
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

MARKER = "/markdown/"


def collect(zip_path: Path) -> list[tuple[str, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".md") and MARKER in name.replace("\\", "/")
        ]
    pairs = []
    for name in members:
        relative = name.replace("\\", "/").split(MARKER, 1)[1]
        pairs.append((name, relative))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="从归档恢复源目录的 markdown")
    parser.add_argument("--zip", default="F:/人教版教材.zip")
    parser.add_argument("--target", default="F:/人教版教材/markdown")
    parser.add_argument("--apply", action="store_true", help="真正写入（默认只报告）")
    args = parser.parse_args()

    zip_path = Path(args.zip)
    target_root = Path(args.target)
    if not zip_path.is_file():
        print(f"归档不存在：{zip_path}", file=sys.stderr)
        return 2
    if not target_root.is_dir():
        print(f"目标目录不存在（拒绝创建）：{target_root}", file=sys.stderr)
        return 2

    pairs = collect(zip_path)
    existing = [rel for _, rel in pairs if (target_root / rel).is_file()]
    missing = [(name, rel) for name, rel in pairs if not (target_root / rel).is_file()]
    print(f"归档内 markdown：{len(pairs)} 个")
    print(f"目标已存在（跳过）：{len(existing)} 个")
    print(f"需要恢复：{len(missing)} 个")
    if not args.apply:
        for _, rel in missing[:10]:
            print(f"  [dry-run] 将写入 {rel}")
        print("（未写入任何文件；加 --apply 才真正恢复）")
        return 0

    restored = 0
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        with zipfile.ZipFile(zip_path) as archive:
            for name, relative in missing:
                staged = staging / relative
                staged.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, staged.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                if staged.stat().st_size == 0:
                    print(f"  跳过（解出为空）：{relative}", file=sys.stderr)
                    continue
                destination = target_root / relative
                if destination.exists():
                    print(f"  跳过（已存在，可能被并发创建）：{relative}")
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged, destination)
                restored += 1
    print(f"已恢复 {restored} 个 markdown 到 {target_root}（未覆盖任何既有文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
