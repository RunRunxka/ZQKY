"""阿里云百炼（DashScope）OpenAI 兼容 Embedding 适配器。

设计要点（与 ``ollama_embedding`` 同一质量边界）：

- 走 LangChain 官方 ``OpenAIEmbeddings``，**显式**传模型、Base URL、附加请求头与
  API Key；Key 只来自后端 ``SecretStore``，不回退进程环境变量。
- ``check_embedding_ctx_length=False``：不把文本交给 tiktoken 预切分，也不在客户端
  静默截断；超长文本由上游明确报错。
- ``encoding_format="float"``：百炼部分网关对 base64 支持不一致，统一按 float 读取。
- ``chunk_size`` 默认 10（百炼 ``text-embedding-v4`` 单批上限）；上游层再分批。
- 输出校验复用共享口径：条数、批内维度、有限值、非零向量。
- 云端没有权重 manifest digest：``manifest_digest`` 返回**声明式身份**（供应商 +
  连接 + 模型 ID + 维度）的派生值，``supports_digest_verification`` 为 False，
  调用方据此把它记成"非权重哈希"，不冒充可核验的清单。
- 错误映射：401/403 认证失败不重试；429/5xx/超时按可重试上报；请求体或密钥
  不进入错误消息。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.providers.embeddings.output_validation import normalize_vectors
from app.providers.embeddings.probe import EMBEDDING_PROBE_TEXTS, EmbeddingProbeResult

ADAPTER = "dashscope"
PROVIDER_ID = "dashscope"
DEFAULT_MODEL = "text-embedding-v4"
DEFAULT_DIMENSIONS = 1024
#: 百炼 text-embedding-v4 / v3 的单批文本条数上限。
MAX_BATCH_SIZE = 10
DEFAULT_TIMEOUT_SECONDS = 120.0
#: 受控模型清单：只列官方文档明确支持 ``dimensions`` 的文本 Embedding 模型。
#: 不拉通用 ``/models`` 清单冒充 Embedding 能力证明。
SUPPORTED_MODELS: tuple[str, ...] = ("text-embedding-v4", "text-embedding-v3")
DIMENSION_CHOICES: dict[str, tuple[int, ...]] = {
    "text-embedding-v4": (2048, 1536, 1024, 768, 512, 256, 128, 64),
    "text-embedding-v3": (1024, 768, 512, 256, 128, 64),
}
_DEFAULT_DIMENSION_BY_MODEL: dict[str, int] = {
    "text-embedding-v4": 1024,
    "text-embedding-v3": 1024,
}
#: 声明式身份前缀：明确区分"云端声明"与"本机权重哈希"。
DECLARED_DIGEST_PREFIX = "dashscope-declared:"


@dataclass(frozen=True)
class DashScopeTarget:
    """一次云端调用的非敏感配置快照（不含 Key）。"""

    connection_id: str
    base_url: str
    model: str
    dimensions: int
    headers: tuple[tuple[str, str], ...] = ()

    @property
    def header_map(self) -> dict[str, str]:
        return dict(self.headers)


def dimension_choices(model: str) -> tuple[int, ...]:
    return DIMENSION_CHOICES.get((model or "").strip(), ())


def default_dimensions(model: str) -> int:
    return _DEFAULT_DIMENSION_BY_MODEL.get((model or "").strip(), DEFAULT_DIMENSIONS)


def validate_target(
    *, connection_id: str, base_url: str, model: str, dimensions: int | None
) -> DashScopeTarget:
    """校验云端嵌入目标；模型、维度与地址不合法即拒绝（不猜测）。"""
    connection = (connection_id or "").strip()
    if not connection:
        raise AppError(
            "云端 Embedding 需要选择一个已保存凭证的百炼连接。",
            code="EMBEDDING_CONNECTION_REQUIRED",
            status_code=422,
        )
    base = (base_url or "").strip().rstrip("/")
    if not base.startswith(("https://", "http://")):
        raise AppError(
            "百炼连接缺少可用的 Base URL，请在设置 → 模型与连接中补全。",
            code="EMBEDDING_BASE_URL_INVALID",
            status_code=422,
        )
    name = (model or "").strip()
    if not name:
        raise AppError("模型名称不能为空。", code="INVALID_REQUEST", status_code=422)
    if name not in SUPPORTED_MODELS:
        raise AppError(
            f"暂不支持云端 Embedding 模型 {name}；可选：{', '.join(SUPPORTED_MODELS)}。",
            code="EMBEDDING_MODEL_UNSUPPORTED",
            status_code=422,
        )
    choices = dimension_choices(name)
    resolved = default_dimensions(name) if dimensions is None else int(dimensions)
    if resolved not in choices:
        raise AppError(
            f"模型 {name} 不支持 {resolved} 维；可选：{', '.join(str(item) for item in choices)}。",
            code="EMBEDDING_DIMENSIONS_UNSUPPORTED",
            status_code=422,
        )
    return DashScopeTarget(
        connection_id=connection,
        base_url=base,
        model=name,
        dimensions=resolved,
    )


def declared_identity_digest(
    *, connection_id: str, base_url: str, model: str, dimensions: int
) -> str:
    """云端向量空间的声明式身份：供应商 + 连接 + 模型 + 维度 的 sha256。

    这不是模型权重哈希，只用于让不同云端配置产生不同指纹；因此调用方必须把
    ``stable_digest`` 记为 False，界面上也不得描述成"可核验的权重摘要"。
    """
    payload = "|".join(
        [ADAPTER, (connection_id or "").strip(), (base_url or "").strip().rstrip("/"), (model or "").strip(), str(int(dimensions))]
    )
    return DECLARED_DIGEST_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _map_upstream_error(exc: Exception) -> AppError:
    """把上游异常映射为稳定错误码；消息不含请求体、响应体或凭证。"""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status in (401, 403):
            return AppError(
                "百炼 Embedding 认证失败；请检查「设置 → 模型与连接」中该连接是否已保存有效 API Key。",
                code="EMBEDDING_AUTH_FAILED",
                status_code=400,
            )
        if status == 404:
            return AppError(
                "百炼 Embedding 模型或地址不存在。",
                code="EMBEDDING_MODEL_MISSING",
                status_code=404,
            )
        if status == 429:
            return AppError(
                "百炼 Embedding 触发限流；稍后重试或降低并发。",
                code="EMBEDDING_RATE_LIMITED",
                status_code=503,
                retryable=True,
            )
        if status >= 500:
            return AppError(
                "百炼 Embedding 服务暂时不可用。",
                code="EMBEDDING_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        return AppError(
            f"百炼 Embedding 请求被拒绝（HTTP {status}）。",
            code="EMBEDDING_REQUEST_REJECTED",
            status_code=422,
        )
    name = exc.__class__.__name__.lower()
    if "timeout" in name:
        return AppError(
            "百炼 Embedding 请求超时。",
            code="EMBEDDING_TIMEOUT",
            status_code=503,
            retryable=True,
        )
    if "connect" in name or "network" in name:
        return AppError(
            "无法连接百炼 Embedding 服务。",
            code="EMBEDDING_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return AppError(
        "百炼 Embedding 调用失败。",
        code="EMBEDDING_UNAVAILABLE",
        status_code=503,
        retryable=True,
    )


class DashScopeEmbeddingProvider:
    """按连接绑定的云端 Embedding 客户端；同步调用，供线程池使用。

    ``client_factory`` 可注入（测试用），签名 ``(target, api_key) -> 有
    embed_documents(texts) 方法的对象``；缺省使用 LangChain ``OpenAIEmbeddings``。
    """

    adapter = ADAPTER
    supports_digest_verification = False
    declared_digest = True

    def __init__(
        self,
        target: DashScopeTarget,
        *,
        api_key: str,
        client_factory=None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not (api_key or "").strip():
            raise AppError(
                "该百炼连接未保存 API Key；请先在设置 → 模型与连接中填写。",
                code="EMBEDDING_AUTH_MISSING",
                status_code=400,
            )
        self.target = target
        self.base_url = target.base_url
        self.model = target.model
        self.dimensions = target.dimensions
        self._api_key = api_key
        self._timeout = float(timeout_seconds)
        self._client_factory = client_factory
        self._client = None

    # -------------------------------------------------------------- 身份

    @property
    def declared_identity(self) -> str:
        return declared_identity_digest(
            connection_id=self.target.connection_id,
            base_url=self.target.base_url,
            model=self.target.model,
            dimensions=self.target.dimensions,
        )

    def manifest_digest(self, model: str) -> str:
        """返回声明式身份；调用方必须结合 ``supports_digest_verification=False`` 解读。"""
        name = (model or "").strip()
        if name != self.model:
            raise AppError(
                f"本配置绑定模型 {self.model}，收到 {name}；云端不支持按名字探测其他模型。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        return self.declared_identity

    # -------------------------------------------------------------- 调用

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory(self.target, self._api_key)
        # 延迟导入：只有真正使用云端路径时才加载官方包。
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=self.model,
            api_key=self._api_key,
            base_url=self.target.base_url,
            default_headers=self.target.header_map,
            dimensions=self.target.dimensions,
            chunk_size=MAX_BATCH_SIZE,
            check_embedding_ctx_length=False,
            timeout=self._timeout,
            max_retries=0,
            model_kwargs={"encoding_format": "float"},
        )

    def _get_client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
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
        if name != self.model:
            raise AppError(
                f"本配置绑定模型 {self.model}，收到 {name}；拒绝跨模型调用。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        try:
            raw = self._get_client().embed_documents(list(texts))
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - 上游异常统一映射为稳定错误码
            raise _map_upstream_error(exc) from None
        return normalize_vectors(raw, expected=len(texts))

    # -------------------------------------------------------------- 探测

    def verify_embedding_candidate(
        self,
        *,
        model_name: str,
        sample_texts: tuple[str, ...] | list[str] | None = None,
    ) -> EmbeddingProbeResult:
        name = (model_name or "").strip()
        if not name:
            raise AppError("模型名称不能为空。", code="INVALID_REQUEST", status_code=422)
        if name != self.model:
            raise AppError(
                f"本配置绑定模型 {self.model}，收到 {name}；拒绝跨模型探测。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        samples = tuple(sample_texts) if sample_texts else EMBEDDING_PROBE_TEXTS
        if not samples:
            raise AppError("检测样例不能为空。", code="INVALID_REQUEST", status_code=422)
        vectors = self.embed(model=name, texts=list(samples))
        return EmbeddingProbeResult(
            model_name=name,
            model_manifest_digest=self.declared_identity,
            dimensions=len(vectors[0]),
            sample_count=len(vectors),
            non_zero=True,
            finite=True,
            stable_digest=False,
            family="dashscope",
            parameter_size="",
        )


__all__ = [
    "ADAPTER",
    "DECLARED_DIGEST_PREFIX",
    "DEFAULT_DIMENSIONS",
    "DEFAULT_MODEL",
    "DIMENSION_CHOICES",
    "DashScopeEmbeddingProvider",
    "DashScopeTarget",
    "MAX_BATCH_SIZE",
    "PROVIDER_ID",
    "SUPPORTED_MODELS",
    "declared_identity_digest",
    "default_dimensions",
    "dimension_choices",
    "validate_target",
]
