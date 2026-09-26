"""语料读取：书册发现、学科归属、文本与清单。语料全程只读（PROJECT_GUIDE D1）。"""
from __future__ import annotations

import glob
import hashlib
import os
from dataclasses import dataclass


@dataclass
class BookInfo:
    book: str          # 书名 = 文件名去掉 .md（chunk_id 前缀，与原型一致）
    path: str          # 绝对路径
    rel_path: str      # 相对语料根的路径
    subject: str       # 学科（按顶层目录名前缀映射）
    chars: int
    lines: int
    md5: str


def discover_books(corpus_root: str) -> list[str]:
    """与原型一致的发现顺序：sorted(glob("**/*.md"))。"""
    return sorted(glob.glob(os.path.join(corpus_root, "**", "*.md"), recursive=True))


def subject_of(rel_path: str, subject_table: list[dict]) -> str:
    """按语料根下第一级目录名前缀判定学科；未匹配返回 "未知"。"""
    top = rel_path.replace("\\", "/").split("/")[0]
    for row in subject_table:
        if top.startswith(row["match"]):
            return row["subject"]
    return "未知"


def read_book(path: str) -> str:
    # 与原型一致：encoding="utf-8" 直读（不剥 BOM），保证字节级等价
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_manifest(corpus_root: str, subject_table: list[dict],
                  filter_sub: str | None = None) -> list[BookInfo]:
    books = []
    for path in discover_books(corpus_root):
        if filter_sub and filter_sub not in path:
            continue
        rel = os.path.relpath(path, corpus_root)
        text = read_book(path)
        with open(path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        books.append(BookInfo(
            book=os.path.basename(path)[:-3],
            path=path,
            rel_path=rel,
            subject=subject_of(rel, subject_table),
            chars=len(text),
            lines=len(text.splitlines()),
            md5=md5,
        ))
    return books
