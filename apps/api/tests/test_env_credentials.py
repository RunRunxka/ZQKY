from pathlib import Path

import pytest

from app.core.secrets import SecretStore
from app.core.exceptions import AppError
from app.api.v1.model_views import connection_view
from app.schemas.model_config import ModelConnection, now_utc
from app.core.config import Settings
from app.main import create_app
from starlette.testclient import TestClient


def test_save_restart_delete_and_no_plaintext_view(tmp_path: Path):
    path = tmp_path / '.env'
    path.write_text('# retained\nZQKY_API_PORT=8000\n', encoding='utf-8')
    store = SecretStore(path)
    value = 'test-only-$#"\\credential'
    store.put('connection123', value)
    restarted = SecretStore(path)
    assert restarted.resolve('connection123') == value
    assert 'ZQKY_API_PORT=8000' in path.read_text()
    connection = ModelConnection(id='connection123', displayName='test', protocol='openai-chat',
        baseUrl='https://example.com', createdAt=now_utc(), updatedAt=now_utc())
    view = connection_view(connection, restarted)
    assert view['hasCredential'] is True
    assert view['credentialScope'] == 'env-file'
    assert view['credentialEnvName'] == 'ZQKY_API_KEY_connection123'
    assert value not in str(view)
    restarted.put('connection123', 'rotated-test-key')
    assert path.read_text().count('ZQKY_API_KEY_connection123=') == 1
    restarted.delete('connection123')
    assert not SecretStore(path).has('connection123')
    assert '# retained' in path.read_text()


def test_manual_values_and_environment_precedence(tmp_path: Path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text("export ZQKY_API_KEY_a='manual-test-value'\nZQKY_API_KEY_b=plain-test-value\n", encoding='utf-8')
    monkeypatch.setenv('ZQKY_API_KEY_a', 'environment-test-value')
    store = SecretStore(path)
    assert store.resolve('a') == 'environment-test-value'
    assert store.resolve('b') == 'plain-test-value'


def test_failed_write_keeps_memory_and_original_file(tmp_path: Path, monkeypatch):
    path = tmp_path / '.env'
    store = SecretStore(path)
    store.put('a', 'old-test-key')
    def fail(*args):
        raise OSError('private filesystem detail')
    monkeypatch.setattr('app.core.secrets.os.replace', fail)
    with pytest.raises(AppError, match='后端凭证保存失败') as error:
        store.put('a', 'new-test-key')
    assert 'private filesystem detail' not in str(error.value)
    assert store.resolve('a') == 'old-test-key'
    assert SecretStore(path).resolve('a') == 'old-test-key'
    assert not list(tmp_path.glob('*.tmp'))


def test_http_save_then_restart_recovers_without_exposing_key(tmp_path: Path):
    settings = Settings(host='127.0.0.1', port=8001, allowed_origins=frozenset(), env='test',
        data_dir=tmp_path, credentials_file=tmp_path / '.env')
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        response = client.post('/api/v1/model-connections', json={
            'displayName': '环境凭证验收', 'protocol': 'openai-chat',
            'baseUrl': 'https://example.com/v1', 'apiKey': 'http-fixture-key',
        })
        assert response.status_code == 201
        connection_id = response.json()['id']
        assert 'http-fixture-key' not in response.text
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        response = client.get('/api/v1/model-connections')
        assert response.json()[0]['hasCredential'] is True
        assert response.json()[0]['credentialScope'] == 'env-file'
        assert 'http-fixture-key' not in response.text
        assert client.delete(f'/api/v1/model-connections/{connection_id}').status_code == 204
    assert not SecretStore(settings.credentials_file).has(connection_id)
