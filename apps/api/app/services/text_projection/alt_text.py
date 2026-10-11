"""图片 alt 文字的「是否有说明价值」判定。

规则来自 RAG-QUALITY v1.1 PLAN §3.1：**空 alt、文件名、路径、长哈希、泛化占位词**
不作为说明文字保留。判定必须是纯函数、无 I/O、可跨语言复刻。

判定顺序（命中任意一条即不保留）：

1. 裁剪首尾空白后为空；
2. 形如路径/URL/文件名（含 ``/``、``\\``、``://``，或以图片扩展名结尾）；
3. 形如哈希（纯十六进制 ≥16 位、UUID、或无分隔的 ≥32 位字母数字串）；
4. 形如泛化占位词（``image`` / ``img`` / ``pic`` / ``图`` / ``图片`` … 可带编号）。
"""

from __future__ import annotations

import re

#: 图片扩展名（判定「alt 其实是文件名」时使用）
IMAGE_EXTENSIONS = frozenset(
    {
        "avif",
        "bmp",
        "gif",
        "heic",
        "heif",
        "ico",
        "jpeg",
        "jpg",
        "png",
        "svg",
        "tif",
        "tiff",
        "webp",
    }
)

#: 泛化占位词（可带编号、分隔符）；大小写不敏感，中文按原样匹配
_GENERIC_ALT_PATTERN = re.compile(
    r"^(?:"
    r"image|images|img|imgs|pic|pics|photo|photos|picture|pictures"
    r"|figure|figures|fig|figs|illustration|diagram|chart|graph|screenshot"
    r"|图片|图像|图|插图|附图|示意图|图表|照片|配图"
    r")[\s\-_.:：#]*\d*$",
    re.IGNORECASE,
)

#: 无分隔的字母数字长串（≥32 位）视为哈希/对象 ID
_LONG_OPAQUE_PATTERN = re.compile(r"^[0-9A-Za-z]{32,}$")

#: 纯十六进制（含常见分隔符）且去分隔后 ≥16 位视为哈希
_HEX_PATTERN = re.compile(r"^(?=[0-9A-Fa-f])[0-9A-Fa-f\s\-_.]+$")
_UUID_PATTERN = re.compile(
    r"^\{?[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}?$"
)
#: 文件名形态（形如 ``fig-3.png`` / ``a.b.c.jpeg``）
_FILENAME_PATTERN = re.compile(r"^[\w\-.()（）\[\] ]+\.[A-Za-z0-9]{2,5}$")
_HEX_MIN_DIGITS = 16


def normalize_alt_core(text: str) -> str:
    """裁剪 alt 首尾空白，返回用于判定与保留的文本（其余内容逐字保留）。"""
    return text.strip()


def looks_like_path(text: str) -> bool:
    """是否形如路径、URL 或带图片扩展名的文件名。"""
    if any(marker in text for marker in ("/", "\\", "://")):
        return True
    return _has_image_extension(text)


def looks_like_hash(text: str) -> bool:
    """是否形如长哈希、UUID 或不可读的长 ID。"""
    if _UUID_PATTERN.match(text):
        return True
    if _LONG_OPAQUE_PATTERN.match(text):
        return True
    if _HEX_PATTERN.match(text):
        return len(re.sub(r"[\s\-_.]", "", text)) >= _HEX_MIN_DIGITS
    return False


def looks_like_generic_placeholder(text: str) -> bool:
    """是否只是泛化占位词（如 ``图``、``image``、``图片 1``）。"""
    return bool(_GENERIC_ALT_PATTERN.match(text))


def meaningful_alt_text(text: str) -> str:
    """返回可作为说明文字保留的 alt；不具说明价值时返回空串。

    返回值要么是空串，要么是 ``normalize_alt_core(text)`` 的逐字结果——调用方据此把
    保留文字锚定到原文码点区间上。
    """
    core = normalize_alt_core(text)
    if not core:
        return ""
    if looks_like_path(core) or looks_like_hash(core) or looks_like_generic_placeholder(core):
        return ""
    return core


def _has_image_extension(text: str) -> bool:
    if not _FILENAME_PATTERN.match(text):
        return False
    suffix = text.rsplit(".", 1)[-1].lower()
    return suffix in IMAGE_EXTENSIONS


__all__ = [
    "IMAGE_EXTENSIONS",
    "looks_like_generic_placeholder",
    "looks_like_hash",
    "looks_like_path",
    "meaningful_alt_text",
    "normalize_alt_core",
]
