"""
Configuration guards: production must refuse to start with insecure defaults.
"""

import pytest

from app import create_app


class TestProductionGuards:
    def test_production_requires_env(self, monkeypatch):
        monkeypatch.delenv('SECRET_KEY', raising=False)
        monkeypatch.delenv('DATABASE_URL', raising=False)
        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            create_app('production')

    def test_production_requires_database_url(self, monkeypatch):
        monkeypatch.setenv('SECRET_KEY', 'x' * 64)
        monkeypatch.delenv('DATABASE_URL', raising=False)
        with pytest.raises(RuntimeError, match='DATABASE_URL'):
            create_app('production')


class TestTestingConfig:
    def test_testing_uses_memory_db(self, app):
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
        assert app.config['EMAIL_ASYNC'] is False
        assert app.config['WTF_CSRF_ENABLED'] is False


class TestSecurityHeaders:
    def test_headers_present(self, client):
        r = client.get('/')
        assert r.headers['X-Content-Type-Options'] == 'nosniff'
        assert r.headers['X-Frame-Options'] == 'SAMEORIGIN'


class TestRobotsAndSitemap:
    def test_robots(self, client):
        body = client.get('/robots.txt').get_data(as_text=True)
        assert 'Disallow: /admin/' in body
        assert 'Disallow: /registration/' in body

    def test_sitemap_lists_courses(self, client, event):
        body = client.get('/sitemap.xml').get_data(as_text=True)
        assert f'/courses/{event.slug}' in body
        assert '/about' in body
        # test event must never leak into the sitemap
        assert 'test-event' not in body
