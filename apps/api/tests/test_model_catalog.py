import json
import pytest
import httpx2 as httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.services import model_metadata
from tests.conftest import make_settings
from tests.test_model_settings_api import create_connection, create_profile


@pytest.fixture(autouse=True)
def _disable_models_dev(monkeypatch):
    """端点测试不触网：models.dev 远端关闭，只用供应商 mock + 内置精确值。"""
    monkeypatch.setattr(model_metadata, "MODELS_DEV_URL", "")
    model_metadata.reset_catalog_memo()


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(make_settings(tmp_path)), base_url='http://127.0.0.1:8001') as c:
        yield c

def test_catalog_default_params_and_conflict(client):
    c = create_connection(client)
    p = create_profile(client,c['id'],params={'temperature':0.3})
    catalog = client.get('/api/v1/model-catalog').json()
    assert catalog['profiles'][0]['params'] == {'temperature':0.3}
    assert 'sk-secret' not in json.dumps(catalog)
    selected = client.put('/api/v1/model-defaults',json={'modelProfileId':p['id'],'expectedRevision':catalog['revision']})
    assert selected.status_code == 200
    assert selected.json()['defaultChatProfileId'] == p['id']
    assert client.put('/api/v1/model-defaults',json={'modelProfileId':None,'expectedRevision':catalog['revision']}).status_code == 409
    assert client.post('/api/v1/model-profiles',json={'connectionId':c['id'],'modelId':'test-model','displayName':'duplicate'}).status_code == 409
    client.delete('/api/v1/model-profiles/'+p['id'])
    assert client.get('/api/v1/model-catalog').json()['defaultChatProfileId'] is None

def test_catalog_marks_local_connections_and_default_profile(client):
    """教案生成/RAG 概括按 isLocal 排除本机连接；未显式选择时用 isDefault 档案。"""
    cloud = create_connection(client, displayName="云端连接", providerId="deepseek")
    local = create_connection(client, displayName="本机连接", providerId="ollama", baseUrl="http://127.0.0.1:11434/v1")
    cloud_profile = create_profile(client, cloud["id"], displayName="云端档案")
    local_profile = create_profile(client, local["id"], displayName="本机档案")
    revision = client.get("/api/v1/model-catalog").json()["revision"]
    assert client.put("/api/v1/model-defaults", json={"modelProfileId": cloud_profile["id"], "expectedRevision": revision}).status_code == 200

    connection_by_id = {item["id"]: item for item in client.get("/api/v1/model-connections").json()}
    assert connection_by_id[cloud["id"]]["isLocal"] is False
    assert connection_by_id[local["id"]]["isLocal"] is True

    profiles = {item["id"]: item for item in client.get("/api/v1/model-profiles").json()}
    assert profiles[cloud_profile["id"]]["connection"]["isLocal"] is False
    assert profiles[local_profile["id"]]["connection"]["isLocal"] is True
    assert profiles[cloud_profile["id"]]["isDefault"] is True
    assert profiles[local_profile["id"]]["isDefault"] is False

    catalog = client.get("/api/v1/model-catalog").json()
    catalog_profiles = {item["id"]: item for item in catalog["profiles"]}
    assert catalog["defaultChatProfileId"] == cloud_profile["id"]
    assert catalog_profiles[local_profile["id"]]["connection"]["isLocal"] is True
    assert catalog_profiles[cloud_profile["id"]]["isDefault"] is True


def test_parameter_validation_and_nullable_updates(client):
    c = create_connection(client)
    p = create_profile(client,c['id'],maxOutputTokens=1024)
    url = '/api/v1/model-profiles/'+p['id']
    assert client.put(url,json={'params':{'temperature':3}}).status_code == 422
    assert client.put(url,json={'params':{'top_p':0.3}}).status_code == 422
    assert client.put(url,json={'maxOutputTokens':None}).json()['maxOutputTokens'] is None
    assert client.put(url,json={'capabilities':{'chat':'verified'}}).json()['capabilities']['chat'] == 'claimed'

@pytest.mark.parametrize('status,code', [(401,'UPSTREAM_AUTH_FAILED'),(429,'RATE_LIMITED'),(404,'MODEL_DISCOVERY_UNSUPPORTED')])
def test_discovery_errors_are_safe(client,monkeypatch,status,code):
    c = create_connection(client)
    original = httpx.AsyncClient
    monkeypatch.setattr('app.services.model_discovery.httpx.AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':{'message':'sk-secret-123'}}))))
    response = client.get(f"/api/v1/model-connections/{c['id']}/models")
    assert response.json()['code'] == code
    assert 'sk-secret-123' not in response.text

def test_discovery_does_not_mutate_and_deduplicates(client,monkeypatch):
    c = create_connection(client)
    original = httpx.AsyncClient
    def handler(request):
        assert request.headers['authorization'] == 'Bearer sk-secret-123'
        return httpx.Response(200,json={'data':[{'id':'b'},{'id':'a'},{'id':'a'}]})
    monkeypatch.setattr('app.services.model_discovery.httpx.AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(handler)))
    before = client.get('/api/v1/model-catalog').json()
    assert client.get(f"/api/v1/model-connections/{c['id']}/models").json()['models'] == [{'id':'a'},{'id':'b'}]
    assert client.get('/api/v1/model-catalog').json() == before

def test_stream_test_separate_from_connection_test(client,monkeypatch):
    from app.providers.llm.base import LLMStreamEvent
    c = create_connection(client)
    p = create_profile(client,c['id'])
    async def stream(self,config,request,transport=None):
        yield LLMStreamEvent(type='start')
        yield LLMStreamEvent(type='text',text='中文')
        yield LLMStreamEvent(type='text',text='测试')
        yield LLMStreamEvent(type='end',finishReason='stop')
    monkeypatch.setattr('app.providers.llm.openai_chat.OpenAIChatProvider._stream',stream)
    r = client.post('/api/v1/model-profiles/'+p['id']+'/test',json={'stream':True}).json()
    assert r['ok'] and r['stream']['chunks'] == 2
    evidence = client.get('/api/v1/model-catalog').json()['profiles'][0]['capabilities']
    assert evidence['stream'] == 'verified' and evidence['chat'] == 'unknown'


def _stub_models(monkeypatch, rows):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        'app.services.model_discovery.httpx.AsyncClient',
        lambda **kw: original(**kw, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'data': rows}))),
    )


def test_catalog_uses_exact_model_context_override(client):
    """档案未填时，deepseek-flash/v4-pro 按模型 ID 已知值给 1M，不再落到 deepseek 族 128k。"""
    c = create_connection(client)
    flash = create_profile(client, c["id"], modelId="deepseek-flash")
    pro = create_profile(client, c["id"], modelId="deepseek-v4-pro")
    profiles = {item["id"]: item for item in client.get("/api/v1/model-catalog").json()["profiles"]}
    assert profiles[flash["id"]]["contextTokens"] is None
    assert profiles[flash["id"]]["contextWindow"]["tokens"] == 1_000_000
    assert profiles[flash["id"]]["contextWindow"]["source"] == "model"
    assert profiles[pro["id"]]["contextWindow"]["tokens"] == 1_000_000
    assert profiles[pro["id"]]["contextWindow"]["source"] == "model"


def test_preview_metadata_reads_without_writing_profile(client, monkeypatch):
    c = create_connection(client)
    p = create_profile(client, c["id"], modelId="deepseek-flash")
    _stub_models(
        monkeypatch,
        [{"id": "deepseek-flash", "context_length": 1_000_000, "max_output_tokens": 384_000}],
    )
    before = client.get("/api/v1/model-catalog").json()

    body = client.post(
        "/api/v1/model-metadata/preview",
        json={"connectionId": c["id"], "modelId": "deepseek-flash"},
    ).json()
    metadata = body["metadata"]
    assert metadata["contextTokens"] == 1_000_000
    assert metadata["maxOutputTokens"] == 384_000
    assert metadata["source"] == "provider"

    after = client.get("/api/v1/model-catalog").json()
    assert after == before
    profile = next(item for item in after["profiles"] if item["id"] == p["id"])
    assert profile["contextTokens"] is None


def test_refresh_metadata_writes_both_limits(client, monkeypatch):
    c = create_connection(client)
    p = create_profile(client, c["id"], modelId="deepseek-flash")
    _stub_models(
        monkeypatch,
        [{"id": "deepseek-flash", "context_length": 1_000_000, "max_output_tokens": 384_000}],
    )

    body = client.post(f"/api/v1/model-profiles/{p['id']}/refresh-metadata").json()
    assert body["updated"] is True
    changes = {change["field"]: change for change in body["changes"]}
    assert changes["contextTokens"]["oldValue"] is None
    assert changes["contextTokens"]["newValue"] == 1_000_000
    assert changes["maxOutputTokens"]["newValue"] == 384_000
    assert body["metadata"]["source"] == "provider"

    catalog_profile = next(
        item for item in client.get("/api/v1/model-catalog").json()["profiles"] if item["id"] == p["id"]
    )
    assert catalog_profile["contextTokens"] == 1_000_000
    assert catalog_profile["maxOutputTokens"] == 384_000


def test_refresh_metadata_overwrites_existing_values_and_reports_old_new(client, monkeypatch):
    c = create_connection(client)
    p = create_profile(
        client, c["id"], modelId="deepseek-flash", contextTokens=64000, maxOutputTokens=2048
    )
    _stub_models(
        monkeypatch,
        [{"id": "deepseek-flash", "context_length": 1_000_000, "max_output_tokens": 384_000}],
    )

    body = client.post(f"/api/v1/model-profiles/{p['id']}/refresh-metadata").json()
    assert body["updated"] is True
    changes = {change["field"]: change for change in body["changes"]}
    assert changes["contextTokens"]["oldValue"] == 64000
    assert changes["contextTokens"]["newValue"] == 1_000_000
    assert changes["maxOutputTokens"]["oldValue"] == 2048
    assert changes["maxOutputTokens"]["newValue"] == 384_000
    assert "64,000 → 1,000,000" in body["message"]
    assert "2,048 → 384,000" in body["message"]


def test_refresh_context_alias_returns_context_part(client, monkeypatch):
    c = create_connection(client)
    p = create_profile(client, c["id"], modelId="deepseek-flash")
    _stub_models(
        monkeypatch,
        [{"id": "deepseek/deepseek-flash", "context_length": 1_000_000}],
    )

    body = client.post(f"/api/v1/model-profiles/{p['id']}/refresh-context").json()
    assert body["updated"] is True
    assert body["contextTokens"] == 1_000_000
    assert body["source"] == "provider"


def test_refresh_context_does_not_guess_when_no_source(client, monkeypatch):
    c = create_connection(client)
    p = create_profile(client, c["id"], modelId="test-model")
    _stub_models(monkeypatch, [{"id": "test-model"}])

    body = client.post(f"/api/v1/model-profiles/{p['id']}/refresh-context").json()
    assert body["updated"] is False
    assert body["contextTokens"] is None
    assert body["source"] == "unavailable"
    assert "未获取到" in body["message"]


def test_batch_refresh_updates_multiple_profiles(client, monkeypatch):
    c = create_connection(client)
    flash = create_profile(client, c["id"], modelId="deepseek-flash")
    pro = create_profile(client, c["id"], modelId="deepseek-v4-pro")
    _stub_models(
        monkeypatch,
        [
            {"id": "deepseek-flash", "context_length": 1_000_000, "max_output_tokens": 384_000},
            {"id": "deepseek-v4-pro", "context_length": 1_000_000, "max_output_tokens": 384_000},
        ],
    )

    body = client.post(
        "/api/v1/model-metadata/refresh", json={"connectionId": c["id"]}
    ).json()
    assert body["updatedCount"] == 2
    profiles = {item["id"]: item for item in client.get("/api/v1/model-catalog").json()["profiles"]}
    for profile_id in (flash["id"], pro["id"]):
        assert profiles[profile_id]["contextTokens"] == 1_000_000
        assert profiles[profile_id]["maxOutputTokens"] == 384_000
