"""multipart/form-data 的有界解析（不引入新依赖）。

后端固定依赖里没有 ``python-multipart``，而 FastAPI 的 ``File``/``Form`` 声明会在
路由定义阶段就要求该包；为了继续支持前端 ``FormData`` 上传，这里在路由层自己解析
``multipart/form-data``，只接受 ``file`` 与 ``metadataJson`` 两个部件。

已知边界：整段请求体在内存中解析（上传上限 100 MiB，见 ``MAX_UPLOAD_BYTES``）；
超出上限在读取前后各拦一次，不落盘、不进入解析。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppError

CRLF = b"\r\n"
_HEADER_SEPARATOR = b"\r\n\r\n"


@dataclass(frozen=True)
class MultipartPart:
    name: str
    filename: str | None
    content_type: str | None
    data: bytes

    def text(self) -> str:
        try:
            return self.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _invalid_multipart("表单字段不是合法 UTF-8 文本。") from exc


def _invalid_multipart(detail: str) -> AppError:
    return AppError(
        f"multipart 请求体不合法：{detail}",
        code="INVALID_REQUEST",
        status_code=422,
    )


def extract_boundary(content_type: str) -> str:
    if not content_type:
        raise _invalid_multipart("缺少 Content-Type。")
    if "multipart/form-data" not in content_type.lower():
        raise AppError(
            "上传接口要求 multipart/form-data。",
            code="UNSUPPORTED_CONTENT_TYPE",
            status_code=415,
        )
    for segment in content_type.split(";"):
        segment = segment.strip()
        if segment.lower().startswith("boundary="):
            boundary = segment[len("boundary="):].strip().strip('"')
            if boundary:
                return boundary
    raise _invalid_multipart("缺少 boundary。")


def _parse_headers(raw: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw.split(CRLF):
        if not line.strip():
            continue
        try:
            decoded = line.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if ":" not in decoded:
            continue
        key, _, value = decoded.partition(":")
        headers[key.strip().lower()] = value.strip()
    return headers


def _parse_disposition(value: str) -> tuple[str | None, str | None]:
    name: str | None = None
    filename: str | None = None
    extended: str | None = None
    for segment in value.split(";"):
        segment = segment.strip()
        lowered = segment.lower()
        if lowered.startswith("name="):
            name = segment[len("name="):].strip().strip('"')
        elif lowered.startswith("filename*="):
            extended = segment[len("filename*="):].strip()
        elif lowered.startswith("filename="):
            filename = segment[len("filename="):].strip().strip('"')
    if extended:
        # RFC 5987：filename*=utf-8''%E7%AC%AC...；优先于普通 filename
        encoded = extended.split("''", 1)[-1]
        try:
            from urllib.parse import unquote

            filename = unquote(encoded, encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 解码失败保留普通 filename
            pass
    return name, filename


def parse_multipart_form(raw: bytes, content_type: str) -> dict[str, MultipartPart]:
    """解析为 ``{字段名: MultipartPart}``；结构不符抛 422。"""
    boundary = extract_boundary(content_type)
    delimiter = b"--" + boundary.encode("utf-8")
    if not raw.startswith(delimiter):
        raise _invalid_multipart("起始边界缺失。")
    parts: dict[str, MultipartPart] = {}
    position = raw.find(delimiter)
    while position != -1:
        cursor = position + len(delimiter)
        if raw[cursor:cursor + 2] == b"--":
            break
        if raw[cursor:cursor + 2] == CRLF:
            cursor += 2
        next_position = raw.find(CRLF + delimiter, cursor)
        if next_position == -1:
            section = raw[cursor:]
        else:
            section = raw[cursor:next_position]
        position = next_position + len(CRLF) if next_position != -1 else -1
        separator = section.find(_HEADER_SEPARATOR)
        if separator == -1:
            raise _invalid_multipart("部件缺少头部/正文分隔。")
        headers = _parse_headers(section[:separator])
        body = section[separator + len(_HEADER_SEPARATOR):]
        disposition = headers.get("content-disposition", "")
        name, filename = _parse_disposition(disposition)
        if not name:
            raise _invalid_multipart("部件缺少 name。")
        if name not in parts:
            parts[name] = MultipartPart(
                name=name,
                filename=filename,
                content_type=headers.get("content-type"),
                data=body,
            )
    if not parts:
        raise _invalid_multipart("没有任何表单部件。")
    return parts
