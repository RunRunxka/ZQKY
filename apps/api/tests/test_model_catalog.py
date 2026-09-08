import json
import pytest
import httpx2 as httpx
from fastapi.testclient import TestClient
from app.main import create_app
from tests.conftest import make_settings
from tests.test_model_settings_api import create_connection, create_profile

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
    monkeypatch.setattr('app.api.v1.model_catalog.httpx.AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':{'message':'sk-secret-123'}}))))
    response = client.get(f"/api/v1/model-connections/{c['id']}/models")
    assert response.json()['code'] == code
    assert 'sk-secret-123' not in response.text

def test_discovery_does_not_mutate_and_deduplicates(client,monkeypatch):
    c = create_connection(client)
    original = httpx.AsyncClient
    def handler(request):
        assert request.headers['authorization'] == 'Bearer sk-secret-123'
        return httpx.Response(200,json={'data':[{'id':'b'},{'id':'a'},{'id':'a'}]})
    monkeypatch.setattr('app.api.v1.model_catalog.httpx.AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(handler)))
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
