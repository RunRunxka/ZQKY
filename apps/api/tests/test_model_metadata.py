"""模型元数据服务测试：models.dev 匹配/合并、缓存与内置兜底（不触网）。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import httpx2 as httpx
import pytest

from app.services import model_metadata
from app.services.model_discovery import _passthrough_metadata


@pytest.fixture(autouse=True)
def _reset_metadata(monkeypatch):
    model_metadata.reset_catalog_memo()
    monkeypatch.setattr(model_metadata, "MODELS_DEV_URL", "")
    yield
    model_metadata.reset_catalog_memo()


def _catalog() -> dict:
    return {
        "deepseek": {
            "models": {
                "deepseek-v4-pro": {
                    "id": "deepseek-v4-pro",
                    "limit": {"context": 1_000_000, "output": 384_000},
                    "tool_call": False,
                    "reasoning": True,
                    "structured_output": True,
                    "temperature": True,
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "release_date": "2026-08-13",
                },
                "deepseek-v4-flash": {
                    "id": "deepseek-v4-flash",
                    "limit": {"context": 1_000_000, "output": 384_000},
                    "temperature": True,
                    "release_date": "2026-07-31",
                },
                "deepseek-v4.1-flash": {
                    "id": "deepseek-v4.1-flash",
                    "limit": {"context": 1_000_000, "output": 128_000},
                    "temperature": True,
                    "release_date": "2026-09-01",
                },
            }
        },
        "openrouter": {
            "models": {
                "deepseek/deepseek-v4-pro": {
                    "id": "deepseek/deepseek-v4-pro",
                    "canonical_model_id": "deepseek/deepseek-v4-pro",
                    "limit": {"context": 1_000_000, "output": 384_000},
                }
            }
        },
    }


def test_upstream_metadata_parsing_openrouter_style():
    meta = _passthrough_metadata(
        {
            "id": "openai/gpt-5",
            "name": "GPT-5",
            "context_length": 400_000,
            "top_provider": {"max_completion_tokens": 128_000},
            "supported_parameters": ["tools", "temperature", "top_p"],
            "architecture": {"input_modalities": ["text", "image"]},
            "tool_call": True,
        }
    )
    assert meta["contextLength"] == 400_000
    assert meta["maxOutputTokens"] == 128_000
    assert meta["displayName"] == "GPT-5"
    assert meta["supportedParameters"] == ["tools", "temperature", "top_p"]
    assert meta["capabilities"]["toolCall"] is True
    assert meta["capabilities"]["inputModalities"] == ["text", "image"]


def test_upstream_metadata_parsing_plain_id_list():
    assert _passthrough_metadata({"id": "gpt-4o"}) == {}


def test_provider_key_inferred_from_custom_base_url():
    connection = SimpleNamespace(providerId="custom", baseUrl="https://api.deepseek.com")
    assert model_metadata.infer_provider_key(connection) == "deepseek"
    connection = SimpleNamespace(providerId="custom", baseUrl="https://openrouter.ai/api/v1")
    assert model_metadata.infer_provider_key(connection) == "openrouter"
    connection = SimpleNamespace(providerId="gemini", baseUrl="")
    assert model_metadata.infer_provider_key(connection) == "google"


def test_lookup_exact_canonical_and_gateway_prefix():
    catalog = _catalog()
    match = model_metadata.lookup_model_metadata(catalog, "deepseek", "deepseek-v4-pro")
    assert match is not None
    assert match.context_tokens == 1_000_000
    assert match.max_output_tokens == 384_000
    assert match.matched_model_id == "deepseek-v4-pro"

    match = model_metadata.lookup_model_metadata(catalog, None, "deepseek/deepseek-v4-pro")
    assert match is not None
    assert match.context_tokens == 1_000_000


def test_lookup_alias_deepseek_flash_prefers_existing_output():
    catalog = _catalog()
    match = model_metadata.lookup_model_metadata(
        catalog, "deepseek", "deepseek-flash", existing_output=384_000
    )
    assert match is not None
    # 别名命中的 v4-flash 输出 384k，与档案现有值一致
    assert match.matched_model_id == "deepseek-v4-flash"
    assert match.max_output_tokens == 384_000


def test_lookup_fuzzy_flash_ambiguity_selects_newest_without_existing_output():
    catalog = _catalog()
    # 去掉别名，强制走同族匹配；无 existing_output 时选发布日期最新的 v4.1-flash
    original = model_metadata.MODEL_ID_ALIASES.pop("deepseek-flash", None)
    try:
        match = model_metadata.lookup_model_metadata(catalog, "deepseek", "deepseek-flash")
    finally:
        if original:
            model_metadata.MODEL_ID_ALIASES["deepseek-flash"] = original
    assert match is not None
    assert match.matched_model_id == "deepseek-v4.1-flash"
    assert match.max_output_tokens == 128_000
    assert match.notes and "同族" in match.notes[0]


def test_merge_priority_provider_over_catalog_over_bundled():
    upstream = model_metadata.MetadataCandidate(
        context_tokens=500_000,
        max_output_tokens=64_000,
        supported_params=("temperature",),
        matched_provider="deepseek",
        matched_model_id="deepseek-flash",
    )
    catalog = model_metadata.MetadataCandidate(
        context_tokens=1_000_000,
        max_output_tokens=384_000,
        capabilities={"reasoning": True},
        matched_provider="deepseek",
        matched_model_id="deepseek-v4-flash",
    )
    bundled = model_metadata._bundled_candidate("deepseek-flash")
    merged = model_metadata.merge_candidates(upstream, catalog, bundled)
    assert merged["contextTokens"] == 500_000
    assert merged["maxOutputTokens"] == 64_000
    assert merged["source"] == "provider"
    assert merged["sources"] == {"contextTokens": "provider", "maxOutputTokens": "provider"}
    assert merged["capabilities"]["reasoning"] is True


def test_merge_fills_missing_fields_from_lower_priority():
    upstream = model_metadata.MetadataCandidate(context_tokens=500_000)
    catalog = model_metadata.MetadataCandidate(max_output_tokens=128_000)
    merged = model_metadata.merge_candidates(upstream, catalog, None)
    assert merged["contextTokens"] == 500_000
    assert merged["maxOutputTokens"] == 128_000
    assert merged["sources"] == {"contextTokens": "provider", "maxOutputTokens": "models.dev"}


def test_bundled_deepseek_values_are_available_offline():
    flash = model_metadata._bundled_candidate("deepseek-flash")
    pro = model_metadata._bundled_candidate("deepseek-v4-pro")
    assert flash is not None and flash.context_tokens == 1_000_000
    assert flash.max_output_tokens == 384_000
    assert pro is not None and pro.context_tokens == 1_000_000
    assert pro.max_output_tokens == 384_000


def _fake_client(handler):
    original = httpx.AsyncClient
    return lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_catalog_cache_avoids_second_network_call(tmp_path: Path, monkeypatch):
    settings = SimpleNamespace(data_dir=tmp_path)
    monkeypatch.setattr(model_metadata, "MODELS_DEV_URL", "https://models.example/api.json")
    calls = 0

    def handler(request):  # noqa: ANN001, ARG001
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_catalog())

    monkeypatch.setattr(model_metadata.httpx, "AsyncClient", _fake_client(handler))
    first = await model_metadata.load_catalog(settings)
    assert first.source == "network"
    assert first.catalog
    second = await model_metadata.load_catalog(settings)
    assert second.source == "cache"
    assert calls == 1

    # 清掉进程内 memo 后仍应读磁盘缓存，不触网
    model_metadata.reset_catalog_memo()
    third = await model_metadata.load_catalog(settings)
    assert third.source == "cache"
    assert calls == 1


@pytest.mark.asyncio
async def test_catalog_stale_fallback_on_network_failure(tmp_path: Path, monkeypatch):
    settings = SimpleNamespace(data_dir=tmp_path)
    monkeypatch.setattr(model_metadata, "MODELS_DEV_URL", "https://models.example/api.json")
    model_metadata._write_cache(tmp_path / model_metadata.CACHE_FILENAME, time.time() - 999_999, _catalog())

    def handler(request):  # noqa: ANN001, ARG001
        raise RuntimeError("offline")

    monkeypatch.setattr(model_metadata.httpx, "AsyncClient", _fake_client(handler))
    state = await model_metadata.load_catalog(settings)
    assert state.source == "stale"
    assert state.catalog
    assert any("缓存" in note for note in state.notes)


@pytest.mark.asyncio
async def test_catalog_cache_write_failure_does_not_break_loading(tmp_path: Path, monkeypatch):
    settings = SimpleNamespace(data_dir=tmp_path)
    monkeypatch.setattr(model_metadata, "MODELS_DEV_URL", "https://models.example/api.json")
    monkeypatch.setattr(
        model_metadata.httpx,
        "AsyncClient",
        _fake_client(lambda request: httpx.Response(200, json=_catalog())),
    )

    def fail_write(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        raise OSError("disk full")

    monkeypatch.setattr(model_metadata, "_write_cache", fail_write)
    state = await model_metadata.load_catalog(settings)
    assert state.source == "network"
    assert state.catalog
    assert any("缓存写入失败" in note for note in state.notes)


@pytest.mark.asyncio
async def test_catalog_disabled_uses_bundled_only(tmp_path: Path):
    settings = SimpleNamespace(data_dir=tmp_path)
    state = await model_metadata.load_catalog(settings)
    assert state.source == "disabled"
    assert state.catalog == {}


def test_cache_file_validation_rejects_bad_schema(tmp_path: Path):
    path = tmp_path / model_metadata.CACHE_FILENAME
    path.write_text(json.dumps({"schemaVersion": 999, "catalog": {}}), encoding="utf-8")
    assert model_metadata._read_cache(path) is None
