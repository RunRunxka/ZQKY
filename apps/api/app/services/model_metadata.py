"""模型元数据：从供应商 `/models` 与 models.dev 公开目录获取上下文/输出上限。

设计参考 ZCode 的「内置模型配置 + 远端同步」思路，但保持本项目的本地优先边界：

1. 供应商 `/models` 返回的字段最可信（OpenRouter 等）；
2. 缺失时查 models.dev 公开目录（24h 本地缓存；网络失败回退过期缓存）；
3. 仍缺失时用内置精确模型表（离线可用）；
4. 模型族粗估只用于展示，**不写回档案**。

本模块只读取公开元数据，不发送任何用户凭证或模型 ID；缓存不含密钥。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx2 as httpx

from app.providers.llm.base import ProviderError
from app.services.model_discovery import discover_connection_models

#: models.dev 公开目录；置空可禁用远端（只用内置表/供应商接口）。
MODELS_DEV_URL = os.environ.get("ZQKY_MODELS_DEV_URL", "https://models.dev/api.json").strip()
CACHE_FILENAME = "model-metadata-cache.json"
CACHE_SCHEMA_VERSION = 1
CACHE_TTL_SECONDS = 24 * 60 * 60

_MAX_CONTEXT_TOKENS = 100_000_000
_MAX_OUTPUT_TOKENS = 1_000_000
_KNOWN_PROFILE_PARAMS = frozenset({"temperature", "top_p"})

#: 离线兜底：已核对的精确模型 ID（来自 models.dev / 用户真机配置）。
BUNDLED_MODEL_METADATA: dict[str, dict[str, Any]] = {
    "deepseek-flash": {"contextTokens": 1_000_000, "maxOutputTokens": 384_000},
    "deepseek-v4-flash": {"contextTokens": 1_000_000, "maxOutputTokens": 384_000},
    "deepseek-v4.1-flash": {"contextTokens": 1_000_000, "maxOutputTokens": 128_000},
    "deepseek-v4-pro": {"contextTokens": 1_000_000, "maxOutputTokens": 384_000},
}

#: 本项目 providerId → models.dev provider key（找不到时再全目录搜模型 ID）。
PROVIDER_KEY_ALIASES: dict[str, str] = {
    "openai_codex": "openai",
    "azure_openai": "azure",
    "gemini": "google",
    "dashscope": "alibaba",
    "zhipu": "zhipuai",
    "moonshot": "moonshotai",
    "minimax_anthropic": "minimax",
    "volcengine_coding_plan": "volcengine",
    "byteplus_coding_plan": "byteplus",
}

#: 自定义连接按 baseUrl 主机推断 models.dev provider key。
BASE_URL_PROVIDER_HINTS: tuple[tuple[str, str], ...] = (
    ("api.deepseek.com", "deepseek"),
    ("api.openai.com", "openai"),
    ("api.anthropic.com", "anthropic"),
    ("openrouter.ai", "openrouter"),
    ("dashscope.aliyuncs.com", "alibaba"),
    ("open.bigmodel.cn", "zhipuai"),
    ("api.moonshot.cn", "moonshotai"),
    ("api.mistral.ai", "mistral"),
    ("generativelanguage.googleapis.com", "google"),
    ("api.groq.com", "groq"),
    ("api.x.ai", "xai"),
    ("api.minimax.io", "minimax"),
)

#: 已知别名：用户/网关常用短名 → models.dev 的规范模型 ID。
MODEL_ID_ALIASES: dict[str, str] = {
    "deepseek-flash": "deepseek-v4-flash",
}

#: 进程内 memo：路径 → (expires_at, fetched_at, catalog)
_MEMO: dict[str, tuple[float, float, dict]] = {}


@dataclass(frozen=True)
class CatalogState:
    catalog: dict
    source: str
    fetched_at: float | None
    notes: tuple[str, ...] = ()


@dataclass
class MetadataCandidate:
    context_tokens: int | None = None
    max_output_tokens: int | None = None
    supported_params: tuple[str, ...] = ()
    capabilities: dict[str, Any] = field(default_factory=dict)
    matched_provider: str | None = None
    matched_model_id: str | None = None
    notes: tuple[str, ...] = ()


def reset_catalog_memo() -> None:
    """测试用：清空进程内目录缓存。"""
    _MEMO.clear()


def _positive_int(value: Any, *, maximum: int) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value if 0 < value <= maximum else None


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _bare_id(value: Any) -> str:
    text = _normalize(value)
    if ":" in text:
        text = text.split(":", 1)[0]
    return text.rsplit("/", 1)[-1]


def infer_provider_key(connection: Any) -> str | None:
    """从连接推断 models.dev provider key；custom 连接按 baseUrl 主机推断。"""
    provider_id = _normalize(getattr(connection, "providerId", None))
    if provider_id and provider_id not in {"custom", "custom_anthropic"}:
        return PROVIDER_KEY_ALIASES.get(provider_id, provider_id)
    base_url = str(getattr(connection, "baseUrl", "") or "")
    host = (urlsplit(base_url).hostname or "").lower()
    for suffix, key in BASE_URL_PROVIDER_HINTS:
        if host == suffix or host.endswith(f".{suffix}"):
            return key
    return None


def _provider_models(provider: Any) -> dict[str, dict]:
    """兼容 models.dev 两种形状：`{models: {...}}` 或 provider 直接映射模型。"""
    if not isinstance(provider, dict):
        return {}
    models = provider.get("models")
    if isinstance(models, dict):
        return {str(k): v for k, v in models.items() if isinstance(v, dict)}
    return {
        str(k): v
        for k, v in provider.items()
        if isinstance(v, dict) and ("limit" in v or "id" in v)
    }


def _iter_catalog(catalog: dict):
    for provider_key, provider in catalog.items():
        for model_key, data in _provider_models(provider).items():
            yield str(provider_key), model_key, data


def _output_limit(data: dict) -> int | None:
    limit = data.get("limit")
    if not isinstance(limit, dict):
        return None
    return _positive_int(limit.get("output"), maximum=_MAX_OUTPUT_TOKENS)


def _context_limit(data: dict) -> int | None:
    limit = data.get("limit")
    if isinstance(limit, dict):
        value = _positive_int(limit.get("context"), maximum=_MAX_CONTEXT_TOKENS)
        if value is not None:
            return value
        # 少量条目只有 input 限制；不再臆造，留空
    return None


def _release_sort_key(data: dict) -> str:
    return str(data.get("release_date") or data.get("last_updated") or "")


def _candidate_from_models_dev(
    provider_key: str, model_key: str, data: dict
) -> MetadataCandidate:
    params: list[str] = []
    if data.get("temperature") is True:
        params.append("temperature")
    capabilities: dict[str, Any] = {}
    for source_key, target_key in (
        ("tool_call", "toolCall"),
        ("reasoning", "reasoning"),
        ("structured_output", "structuredOutput"),
        ("temperature", "temperature"),
    ):
        if isinstance(data.get(source_key), bool):
            capabilities[target_key] = data[source_key]
    modalities = data.get("modalities")
    if isinstance(modalities, dict):
        inputs = modalities.get("input")
        if isinstance(inputs, list):
            values = [str(item) for item in inputs if isinstance(item, str)][:8]
            if values:
                capabilities["inputModalities"] = values
    return MetadataCandidate(
        context_tokens=_context_limit(data),
        max_output_tokens=_output_limit(data),
        supported_params=tuple(params),
        capabilities=capabilities,
        matched_provider=provider_key,
        matched_model_id=model_key,
    )


def _find_exact(
    entries: list[tuple[str, str, dict]],
    target_full: str,
    target_bare: str,
    *,
    provider_keys: set[str] | None = None,
) -> tuple[str, str, dict] | None:
    for provider_key, model_key, data in entries:
        if provider_keys and _normalize(provider_key) not in provider_keys:
            continue
        canonical = data.get("canonical_model_id")
        keys = {
            _normalize(model_key),
            _bare_id(model_key),
            _normalize(canonical),
            _bare_id(canonical),
        }
        if target_full in keys or target_bare in keys:
            return provider_key, model_key, data
    return None


def lookup_model_metadata(
    catalog: dict,
    provider_hint: str | None,
    model_id: str,
    *,
    existing_output: int | None = None,
) -> MetadataCandidate | None:
    """在 models.dev 目录中匹配模型；返回带匹配来源的候选值。"""
    if not catalog:
        return None
    entries = list(_iter_catalog(catalog))
    target_full = _normalize(model_id)
    target_bare = _bare_id(model_id)
    provider_keys = {_normalize(provider_hint)} if provider_hint else set()

    found = _find_exact(entries, target_full, target_bare, provider_keys=provider_keys)
    if found is None:
        found = _find_exact(entries, target_full, target_bare)

    alias = MODEL_ID_ALIASES.get(target_bare)
    if found is None and alias:
        found = _find_exact(entries, _normalize(alias), _bare_id(alias))

    notes: list[str] = []
    if found is None:
        # 同族兜底：只按最后一段匹配（如 deepseek-flash → *-flash），并优先 provider。
        tail = target_bare.rsplit("-", 1)[-1] if "-" in target_bare else ""
        if tail and tail.isalpha() and len(tail) >= 3:
            candidates = [
                entry
                for entry in entries
                if _bare_id(entry[1]).rsplit("-", 1)[-1] == tail
                and (not provider_keys or _normalize(entry[0]) in provider_keys)
            ]
            if not candidates:
                candidates = [
                    entry
                    for entry in entries
                    if _bare_id(entry[1]).rsplit("-", 1)[-1] == tail
                ]
            if candidates:
                candidates.sort(
                    key=lambda entry: (
                        existing_output is not None
                        and _output_limit(entry[2]) == existing_output,
                        _release_sort_key(entry[2]),
                    ),
                    reverse=True,
                )
                found = candidates[0]
                if len(candidates) > 1:
                    notes.append(
                        f"同族存在 {len(candidates)} 个匹配，已选 {found[1]}；如有误请在档案手填覆盖。"
                    )

    if found is None:
        return None
    candidate = _candidate_from_models_dev(*found)
    if notes:
        candidate.notes = tuple(notes)
    return candidate


def _bundled_candidate(model_id: str) -> MetadataCandidate | None:
    target = _bare_id(model_id)
    data = BUNDLED_MODEL_METADATA.get(target)
    if data is None:
        alias = MODEL_ID_ALIASES.get(target)
        data = BUNDLED_MODEL_METADATA.get(alias) if alias else None
    if data is None:
        return None
    return MetadataCandidate(
        context_tokens=data.get("contextTokens"),
        max_output_tokens=data.get("maxOutputTokens"),
        matched_provider="bundled",
        matched_model_id=target,
    )


def _candidate_from_upstream(
    entry: dict, provider_hint: str | None
) -> MetadataCandidate:
    context = _positive_int(entry.get("contextLength"), maximum=_MAX_CONTEXT_TOKENS)
    output = _positive_int(entry.get("maxOutputTokens"), maximum=_MAX_OUTPUT_TOKENS)
    raw_params = entry.get("supportedParameters")
    params = (
        [str(item) for item in raw_params if str(item) in _KNOWN_PROFILE_PARAMS]
        if isinstance(raw_params, list)
        else []
    )
    capabilities = entry.get("capabilities")
    return MetadataCandidate(
        context_tokens=context,
        max_output_tokens=output,
        supported_params=tuple(dict.fromkeys(params)),
        capabilities=dict(capabilities) if isinstance(capabilities, dict) else {},
        matched_provider=provider_hint,
        matched_model_id=str(entry.get("id") or "") or None,
    )


def _find_upstream_entry(rows: list[dict], model_id: str) -> dict | None:
    target_full = _normalize(model_id)
    target_bare = _bare_id(model_id)
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = row.get("id")
        if _normalize(row_id) == target_full or _bare_id(row_id) == target_bare:
            return row
    return None


def merge_candidates(
    upstream: MetadataCandidate | None,
    catalog: MetadataCandidate | None,
    bundled: MetadataCandidate | None,
) -> dict:
    """按 provider > models.dev > bundled 合并；返回 API 友好的扁平结果。"""
    values: dict[str, int] = {}
    sources: dict[str, str] = {}
    for field_name, attr in (("contextTokens", "context_tokens"), ("maxOutputTokens", "max_output_tokens")):
        for label, candidate in (("provider", upstream), ("models.dev", catalog), ("bundled", bundled)):
            if candidate is None:
                continue
            value = getattr(candidate, attr)
            if value is not None and field_name not in values:
                values[field_name] = value
                sources[field_name] = label

    supported: list[str] = []
    for candidate in (upstream, catalog, bundled):
        if candidate and candidate.supported_params:
            supported = list(candidate.supported_params)
            break

    capabilities: dict[str, Any] = {}
    for candidate in (bundled, catalog, upstream):
        if candidate:
            capabilities.update(candidate.capabilities)

    notes: list[str] = []
    for candidate in (upstream, catalog, bundled):
        if candidate:
            notes.extend(candidate.notes)

    matched = catalog or bundled or upstream
    source = "unavailable"
    for label in ("provider", "models.dev", "bundled"):
        if label in sources.values():
            source = label
            break
    return {
        "contextTokens": values.get("contextTokens"),
        "maxOutputTokens": values.get("maxOutputTokens"),
        "supportedParams": supported,
        "capabilities": capabilities,
        "source": source,
        "sources": sources,
        "matchedProvider": matched.matched_provider if matched else None,
        "matchedModelId": matched.matched_model_id if matched else None,
        "notes": notes,
    }


def _cache_path(settings: Any) -> Path:
    return Path(settings.data_dir) / CACHE_FILENAME


def _read_cache(path: Path) -> tuple[float, dict] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get("schemaVersion") != CACHE_SCHEMA_VERSION:
        return None
    catalog = raw.get("catalog")
    fetched_at = raw.get("fetchedAt")
    if not isinstance(catalog, dict) or not isinstance(fetched_at, (int, float)):
        return None
    return float(fetched_at), catalog


def _write_cache(path: Path, fetched_at: float, catalog: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporaries = path.with_name(f"{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    payload = {
        "schemaVersion": CACHE_SCHEMA_VERSION,
        "fetchedAt": fetched_at,
        "sourceUrl": MODELS_DEV_URL,
        "catalog": catalog,
    }
    try:
        temporaries.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporaries, path)
    finally:
        try:
            if temporaries.exists():
                temporaries.unlink()
        except OSError:
            pass


def _valid_catalog(data: Any) -> dict | None:
    if not isinstance(data, dict):
        return None
    catalog: dict[str, dict] = {}
    for provider_key, provider in data.items():
        models = _provider_models(provider)
        if models:
            catalog[str(provider_key)] = {"models": models}
    return catalog or None


async def load_catalog(settings: Any, *, force: bool = False) -> CatalogState:
    """加载 models.dev 目录（memo → 磁盘缓存 → 网络），失败时回退缓存。"""
    if not MODELS_DEV_URL:
        return CatalogState({}, "disabled", None, ("未配置模型元数据目录 URL，已跳过远端获取。",))

    path = _cache_path(settings)
    now = time.time()
    memo = _MEMO.get(str(path))
    if memo and not force and memo[0] > now:
        return CatalogState(memo[2], "cache", memo[1])

    disk = _read_cache(path)
    if disk and not force and now - disk[0] < CACHE_TTL_SECONDS:
        _MEMO[str(path)] = (disk[0] + CACHE_TTL_SECONDS, disk[0], disk[1])
        return CatalogState(disk[1], "cache", disk[0])

    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"user-agent": "ZQKY-model-metadata/1"},
        ) as client:
            response = await client.get(MODELS_DEV_URL)
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}")
            catalog = _valid_catalog(response.json())
            if catalog is None:
                raise ValueError("目录结构不受支持")
    except Exception as exc:  # 网络/解析失败不阻断档案编辑
        if disk:
            _MEMO[str(path)] = (now + 60, disk[0], disk[1])
            return CatalogState(
                disk[1],
                "stale",
                disk[0],
                (f"模型元数据目录获取失败（{type(exc).__name__}），已使用本地缓存。",),
            )
        return CatalogState(
            {},
            "unavailable",
            None,
            (f"模型元数据目录获取失败（{type(exc).__name__}）；仅使用供应商接口与内置精确值。",),
        )

    try:
        _write_cache(path, now, catalog)
    except OSError as exc:
        _MEMO[str(path)] = (now + CACHE_TTL_SECONDS, now, catalog)
        return CatalogState(
            catalog,
            "network",
            now,
            (f"模型元数据缓存写入失败（{type(exc).__name__}），本次结果未落盘。",),
        )
    _MEMO[str(path)] = (now + CACHE_TTL_SECONDS, now, catalog)
    return CatalogState(catalog, "network", now)


async def resolve_metadata(
    settings: Any,
    connection: Any,
    model_id: str,
    *,
    key: str | None,
    existing_output: int | None = None,
    force_catalog: bool = False,
    upstream_rows: list[dict] | None = None,
) -> dict:
    """解析一个模型的元数据；供应商失败/无数据时继续用 models.dev 与内置表。"""
    notes: list[str] = []
    provider_hint = infer_provider_key(connection)
    if upstream_rows is None:
        try:
            result = await discover_connection_models(connection, key)
            upstream_rows = [
                entry for entry in (result.get("models") or []) if isinstance(entry, dict)
            ]
        except ProviderError as exc:
            notes.append(f"供应商模型列表读取失败：{exc}")
            upstream_rows = []
        except Exception as exc:  # pragma: no cover - 防御异常上游
            notes.append(f"供应商模型列表读取失败（{type(exc).__name__}）。")
            upstream_rows = []

    entry = _find_upstream_entry(upstream_rows, model_id)
    upstream = _candidate_from_upstream(entry, provider_hint) if entry else None

    catalog_state = await load_catalog(settings, force=force_catalog)
    notes.extend(catalog_state.notes)
    catalog = (
        lookup_model_metadata(
            catalog_state.catalog,
            provider_hint,
            model_id,
            existing_output=existing_output,
        )
        if catalog_state.catalog
        else None
    )
    bundled = _bundled_candidate(model_id)
    merged = merge_candidates(upstream, catalog, bundled)
    merged["notes"] = notes + list(merged.get("notes") or [])
    merged["catalogSource"] = catalog_state.source
    merged["catalogFetchedAt"] = catalog_state.fetched_at
    return merged


__all__ = [
    "BUNDLED_MODEL_METADATA",
    "CatalogState",
    "MODELS_DEV_URL",
    "infer_provider_key",
    "load_catalog",
    "lookup_model_metadata",
    "merge_candidates",
    "reset_catalog_memo",
    "resolve_metadata",
]
