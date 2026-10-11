"""本地 Ollama 原生 Embedding 适配器：/api/tags、/api/show、/api/embed。

约束（RAG-REBUILD v1.0 §4.2）：
- 只允许本机回环地址；构造阶段即拒绝其他地址，不把公网/容器地址当作本地服务。
- 不读取环境代理（``trust_env=False``），不跟随重定向。
- 嵌入一律显式 ``truncate=False``，避免上游默认截断造成"看似成功"的截断向量。
- 调用前后核对模型清单 digest；同名 tag 的 digest 变化一律视为换模型（``EMBEDDING_MODEL_CHANGED``）。
- 输出校验：条数、维度一致、全部有限、每条非零；任一不满足抛 ``EMBEDDING_INVALID_OUTPUT``。
- 聊天模型不得被识别为 Embedding 模型；云端/远程模型直接拒绝。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.exceptions import AppError
from app.schemas.textbook import EmbeddingModelCandidate

ADAPTER = "ollama"
DEFAULT_TIMEOUT_SECONDS = 120.0
#: 只允许本机回环主机；与核心配置的 LOCAL_HOSTNAMES 语义一致（此处按 URL host 判定）。
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
#: 检测流程固定样例：与计划 §4.2 一致，两类学科文本各一条。
EMBEDDING_PROBE_TEXTS: tuple[str, ...] = ("集合与函数", "物质的结构与性质")
_DIGEST_PREFIX = "sha256:"
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_OOM_MARKERS = ("out of memory", "oom", "cuda", "memory")


@dataclass(frozen=True)
class EmbeddingProbeResult:
    """一次真实嵌入能力检测的结果；不含地址与凭证。"""

    model_name: str
    model_manifest_digest: str
    dimensions: int
    sample_count: int
    non_zero: bool
    finite: bool
    stable_digest: bool
    family: str
    parameter_size: str


def normalize_loopback_base_url(base_url: str) -> str:
    """校验并规范化本机回环地址；非回环、带凭证或带查询串的地址一律拒绝。"""
    raw = (base_url or "").strip()
    if not raw:
        raise AppError(
            "Embedding 服务地址不能为空。",
            code="EMBEDDING_BASE_URL_INVALID",
            status_code=422,
        )
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise AppError(
            "Embedding 服务地址必须是 http 或 https。",
            code="EMBEDDING_BASE_URL_INVALID",
            status_code=422,
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AppError(
            "Embedding 服务地址不允许携带凭证、查询串或片段。",
            code="EMBEDDING_BASE_URL_INVALID",
            status_code=422,
        )
    host = parsed.hostname
    if host is None or host not in LOOPBACK_HOSTS:
        raise AppError(
            "Embedding 服务只允许本机回环地址（127.0.0.1 / localhost / ::1），"
            f"收到：{host or raw}。",
            code="EMBEDDING_BASE_URL_NOT_LOCAL",
            status_code=422,
        )
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def is_embedding_capable(details: dict) -> bool:
    """判断模型是否具备嵌入能力；聊天模型返回 False，不靠名字猜测。"""
    if not isinstance(details, dict):
        return False
    capabilities = details.get("capabilities")
    if isinstance(capabilities, list):
        return any(
            isinstance(item, str) and item.strip().lower() == "embedding"
            for item in capabilities
        )
    family = details.get("family")
    if isinstance(family, str):
        return "bert" in family.lower()
    return False


def is_remote_or_cloud_model(name: str, details: dict) -> bool:
    """识别 Ollama 云端/远程模型：不得当作本地 Embedding 使用。"""
    if isinstance(name, str) and name.strip().lower().endswith("-cloud"):
        return True
    if not isinstance(details, dict):
        return False
    for key in ("remote_host", "remote_model", "remoteHost", "remoteModel"):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _strip_digest(value: object) -> str:
    if not isinstance(value, str):
        return ""
    digest = value.strip()
    if digest.startswith(_DIGEST_PREFIX):
        digest = digest[len(_DIGEST_PREFIX):]
    return digest


def normalize_model_tag(name: str) -> str:
    """按 Ollama tag 语义归一模型名：省略 tag 视为 ``:latest``。

    ``bge-m3`` 与 ``bge-m3:latest`` 是同一模型；``bge-m3:latest`` 与 ``bge-m3:v2`` 不是。
    带 registry/namespace 前缀时只检查最后一段是否含 tag（如 ``registry:5000/bge-m3``）。
    """
    model = (name or "").strip()
    if not model:
        return ""
    prefix, _, tail = model.rpartition("/")
    if not tail:
        prefix, tail = "", prefix
    if ":" in tail:
        tagged = tail
    else:
        tagged = f"{tail}:latest"
    return f"{prefix}/{tagged}" if prefix else tagged


def model_names_match(left: str, right: str) -> bool:
    """模型名等价比较（仅 tag 归一 + 全等），绝不做"包含即命中"。

    ``bge-m3`` == ``bge-m3:latest``；``bge-m3`` != ``bge-m3-large``、``bge-m3:v2``。
    """
    normalized_left = normalize_model_tag(left)
    normalized_right = normalize_model_tag(right)
    return bool(normalized_left) and normalized_left == normalized_right


def _invalid_output(message: str) -> AppError:
    return AppError(
        f"Embedding 输出不合法：{message}",
        code="EMBEDDING_INVALID_OUTPUT",
        status_code=502,
    )


class OllamaEmbeddingProvider:
    """同步 HTTP 客户端；每次调用独立连接，可被 FastAPI 线程池跨线程使用。"""

    adapter = ADAPTER

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_loopback_base_url(base_url)
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport

    # ------------------------------------------------------------- HTTP 底座

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        )

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> dict:
        try:
            with self._client() as client:
                response = client.request(method, path, json=json_body)
        except httpx.HTTPError as exc:
            raise AppError(
                f"本地 Embedding 服务不可达（{self.base_url}）：{exc.__class__.__name__}。",
                code="EMBEDDING_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        if response.status_code >= 300:
            raise _upstream_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(
                "本地 Embedding 服务返回了非 JSON 响应。",
                code="EMBEDDING_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        if not isinstance(payload, dict):
            raise _invalid_output("响应顶层不是 JSON 对象。")
        return payload

    # --------------------------------------------------------------- 模型清单

    def list_models(self) -> list[EmbeddingModelCandidate]:
        """GET /api/tags；family/parameterSize 取 /api/show，失败留空但不整体失败。"""
        payload = self._request("GET", "/api/tags")
        entries = payload.get("models")
        if not isinstance(entries, list):
            raise _invalid_output("/api/tags 响应缺少 models 数组。")
        candidates: list[EmbeddingModelCandidate] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("model")
            if not isinstance(name, str) or not name.strip():
                continue
            family = ""
            parameter_size = ""
            capabilities: object = None
            try:
                details_payload = self.show_model(name)
            except AppError:
                # 单个模型的详情失败不影响候选列表；能力字段留空并在前端显示未知
                details_payload = {}
            details = details_payload.get("details")
            if isinstance(details, dict):
                raw_family = details.get("family")
                if isinstance(raw_family, str):
                    family = raw_family
                raw_parameter = details.get("parameter_size")
                if isinstance(raw_parameter, str):
                    parameter_size = raw_parameter
            capabilities = details_payload.get("capabilities")
            candidate_details: dict = {"family": family}
            if capabilities is not None:
                candidate_details["capabilities"] = capabilities
            size = entry.get("size")
            candidates.append(
                EmbeddingModelCandidate(
                    name=name,
                    digest=_strip_digest(entry.get("digest")),
                    sizeBytes=size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else 0,
                    family=family,
                    parameterSize=parameter_size,
                    isEmbeddingCapable=is_embedding_capable(candidate_details),
                )
            )
        candidates.sort(key=lambda candidate: candidate.name)
        return candidates

    def show_model(self, name: str) -> dict:
        """GET /api/show（body ``{"model": name}``）；返回原始对象。

        个别 Ollama 版本只用 POST 读取 body：GET 被拒（400/405/415 映射为
        ``EMBEDDING_REQUEST_REJECTED``）时原样再发一次 POST，不改变参数语义。
        """
        model = (name or "").strip()
        if not model:
            raise AppError("模型名称不能为空。", code="INVALID_REQUEST", status_code=422)
        try:
            return self._request("GET", "/api/show", json_body={"model": model})
        except AppError as exc:
            if exc.code != "EMBEDDING_REQUEST_REJECTED":
                raise
            return self._request("POST", "/api/show", json_body={"model": model})

    def manifest_digest(self, model: str) -> str:
        """从 /api/tags 读取该模型的 digest（去掉 sha256: 前缀）。

        模型名比较按 Ollama tag 语义归一：``bge-m3`` 与 ``bge-m3:latest`` 视为同一模型
        （两个方向都命中），但绝不做包含匹配（``bge-m3`` 不命中 ``bge-m3-large``）。
        """
        name = (model or "").strip()
        if not name:
            raise AppError("模型名称不能为空。", code="INVALID_REQUEST", status_code=422)
        payload = self._request("GET", "/api/tags")
        entries = payload.get("models")
        if not isinstance(entries, list):
            raise _invalid_output("/api/tags 响应缺少 models 数组。")
        # 优先原始名全等，其次 tag 归一后全等；两者都不做包含匹配
        candidates: list[tuple[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_name = entry.get("name") or entry.get("model")
            if not isinstance(entry_name, str):
                continue
            candidates.append((entry_name, _strip_digest(entry.get("digest"))))
        for exact in (True, False):
            for entry_name, digest in candidates:
                matched = (
                    entry_name == name
                    if exact
                    else model_names_match(entry_name, name)
                )
                if not matched:
                    continue
                if not digest:
                    raise _invalid_output(f"模型 {name} 的清单缺少 digest。")
                return digest
        raise AppError(
            f"本地未安装模型 {name}，请先在 Ollama 中拉取。",
            code="EMBEDDING_MODEL_MISSING",
            status_code=404,
        )

    # ----------------------------------------------------------------- 嵌入

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        """POST /api/embed（truncate=False）并校验输出形状与数值。"""
        name = (model or "").strip()
        if not name:
            raise AppError("模型名称不能为空。", code="INVALID_REQUEST", status_code=422)
        if isinstance(texts, (str, bytes)) or not isinstance(texts, list) or not texts:
            raise AppError(
                "嵌入输入必须是非空文本列表。",
                code="INVALID_REQUEST",
                status_code=422,
            )
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise AppError(
                    "嵌入输入包含空文本；请先按完整边界分块。",
                    code="INVALID_REQUEST",
                    status_code=422,
                )
        payload = self._request(
            "POST",
            "/api/embed",
            json_body={"model": name, "input": list(texts), "truncate": False},
        )
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise _invalid_output("响应缺少 embeddings 数组。")
        if len(embeddings) != len(texts):
            raise _invalid_output(
                f"返回 {len(embeddings)} 条，与输入 {len(texts)} 条不一致。"
            )
        vectors: list[list[float]] = []
        dimension: int | None = None
        for index, vector in enumerate(embeddings):
            if not isinstance(vector, list) or not vector:
                raise _invalid_output(f"第 {index} 条向量为空或不是数组。")
            values: list[float] = []
            for value in vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise _invalid_output(f"第 {index} 条向量包含非数值元素。")
                values.append(float(value))
            if dimension is None:
                dimension = len(values)
            elif len(values) != dimension:
                raise _invalid_output(
                    f"第 {index} 条向量维度 {len(values)} 与首条 {dimension} 不一致。"
                )
            if not all(math.isfinite(value) for value in values):
                raise _invalid_output(f"第 {index} 条向量包含非有限值。")
            if not any(value != 0.0 for value in values):
                raise _invalid_output(f"第 {index} 条向量全为零向量。")
            vectors.append(values)
        return vectors

    # ----------------------------------------------------------------- 检测

    def verify_embedding_candidate(
        self,
        *,
        model_name: str,
        sample_texts: tuple[str, ...] | list[str] | None = None,
    ) -> EmbeddingProbeResult:
        """按计划 §4.2 的检测流程：清单 → 详情 → 能力 → 嵌入 → 前后 digest 一致。"""
        name = (model_name or "").strip()
        if not name:
            raise AppError("模型名称不能为空。", code="INVALID_REQUEST", status_code=422)
        samples = tuple(sample_texts) if sample_texts else EMBEDDING_PROBE_TEXTS
        if not samples:
            raise AppError("检测样例不能为空。", code="INVALID_REQUEST", status_code=422)

        digest_before = self.manifest_digest(name)
        details_payload = self.show_model(name)
        details = details_payload.get("details")
        details_dict = details if isinstance(details, dict) else {}
        if is_remote_or_cloud_model(name, details_dict):
            raise AppError(
                f"模型 {name} 是云端/远程模型；Embedding 检测只允许本机模型。",
                code="EMBEDDING_MODEL_NOT_LOCAL",
                status_code=422,
            )
        capability_details: dict = {"family": details_dict.get("family", "")}
        if "capabilities" in details_payload:
            capability_details["capabilities"] = details_payload["capabilities"]
        if not is_embedding_capable(capability_details):
            raise AppError(
                f"模型 {name} 未声明 embedding 能力，不能作为教材嵌入模型。",
                code="EMBEDDING_MODEL_NOT_EMBEDDING",
                status_code=422,
            )

        vectors = self.embed(model=name, texts=list(samples))
        digest_after = self.manifest_digest(name)
        if digest_after != digest_before:
            raise AppError(
                "检测期间模型清单 digest 发生变化，拒绝使用该模型空间；请重新检测。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        family = details_dict.get("family")
        parameter_size = details_dict.get("parameter_size")
        return EmbeddingProbeResult(
            model_name=name,
            model_manifest_digest=digest_after,
            dimensions=len(vectors[0]),
            sample_count=len(vectors),
            non_zero=True,
            finite=True,
            stable_digest=True,
            family=family if isinstance(family, str) else "",
            parameter_size=parameter_size if isinstance(parameter_size, str) else "",
        )


def _upstream_error(response: httpx.Response) -> AppError:
    """把上游状态映射为明确错误；不把"不可用"变成"没有结果"。"""
    status = response.status_code
    if status in _REDIRECT_STATUSES:
        return AppError(
            "Embedding 服务返回重定向；本机适配器不跟随重定向，已拒绝。",
            code="EMBEDDING_REDIRECT_REJECTED",
            status_code=502,
        )
    body = response.text[:400] if isinstance(response.text, str) else ""
    lowered = body.lower()
    if status == 404 or (status == 400 and ("not found" in lowered or "no such model" in lowered)):
        return AppError(
            "模型在本地 Ollama 中不存在。",
            code="EMBEDDING_MODEL_MISSING",
            status_code=404,
        )
    if status >= 500 and any(marker in lowered for marker in _OOM_MARKERS):
        return AppError(
            "本地 Embedding 服务内存不足；可缩小批次后重试，不更换模型。",
            code="EMBEDDING_OUT_OF_MEMORY",
            status_code=503,
            retryable=True,
        )
    if status >= 500:
        return AppError(
            "本地 Embedding 服务返回错误，服务可能暂不可用。",
            code="EMBEDDING_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    if status >= 300:
        # 3xx 已在上面处理；其余为 4xx：请求被上游拒绝，不自动重试
        return AppError(
            f"Embedding 请求被本地服务拒绝（HTTP {status}）。",
            code="EMBEDDING_REQUEST_REJECTED",
            status_code=422,
        )
    return AppError(
        "Embedding 调用失败。",
        code="EMBEDDING_UNAVAILABLE",
        status_code=503,
        retryable=True,
    )
