from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app import _configure_proxy_headers


def _make_probe_app():
    app = Flask(__name__)

    @app.get('/proxy-probe')
    def proxy_probe():
        return jsonify(
            host=request.host,
            scheme=request.scheme,
            secure=request.is_secure,
        )

    return app


def test_production_proxy_headers_restore_https_scheme(monkeypatch):
    monkeypatch.setenv('TRUST_PROXY_HEADERS', 'true')
    monkeypatch.setenv('PROXY_FIX_HOPS', '1')
    app = _make_probe_app()

    _configure_proxy_headers(app, 'production')

    response = app.test_client().get(
        '/proxy-probe',
        base_url='http://gunicorn.internal:8000',
        headers={
            'X-Forwarded-Proto': 'https',
            'X-Forwarded-Host': 'codesense.example',
            'X-Forwarded-Port': '443',
        },
    )

    assert isinstance(app.wsgi_app, ProxyFix)
    assert response.get_json() == {
        'host': 'codesense.example',
        'scheme': 'https',
        'secure': True,
    }


def test_development_does_not_trust_forwarded_headers_by_default(monkeypatch):
    monkeypatch.delenv('TRUST_PROXY_HEADERS', raising=False)
    monkeypatch.delenv('PROXY_FIX_HOPS', raising=False)
    app = _make_probe_app()

    _configure_proxy_headers(app, 'development')

    response = app.test_client().get(
        '/proxy-probe',
        base_url='http://gunicorn.internal:8000',
        headers={'X-Forwarded-Proto': 'https'},
    )

    assert not isinstance(app.wsgi_app, ProxyFix)
    assert response.get_json()['scheme'] == 'http'
    assert response.get_json()['secure'] is False
