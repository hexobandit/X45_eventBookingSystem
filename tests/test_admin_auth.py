"""
Admin authentication and access control.
"""

from app.extensions import db


def login(client, email, password):
    return client.post('/admin/login', data={'email': email, 'password': password},
                       follow_redirects=False)


class TestAccessControl:
    def test_admin_requires_login(self, client):
        r = client.get('/admin/', follow_redirects=False)
        assert r.status_code == 302
        assert '/admin/login' in r.headers['Location']

    def test_login_page_renders(self, client):
        assert client.get('/admin/login').status_code == 200


class TestLogin:
    def test_valid_login(self, client, admin_user):
        r = login(client, 'admin@example.com', 'test-password-123')
        assert r.status_code == 302
        # now the dashboard is reachable
        assert client.get('/admin/').status_code == 200

    def test_wrong_password(self, client, admin_user):
        r = login(client, 'admin@example.com', 'wrong')
        assert r.status_code == 200  # re-rendered login page
        assert client.get('/admin/', follow_redirects=False).status_code == 302

    def test_inactive_user_rejected(self, client, admin_user):
        admin_user.is_active = False
        db.session.commit()
        login(client, 'admin@example.com', 'test-password-123')
        assert client.get('/admin/', follow_redirects=False).status_code == 302

    def test_non_admin_rejected(self, client, admin_user):
        admin_user.is_admin = False
        db.session.commit()
        login(client, 'admin@example.com', 'test-password-123')
        assert client.get('/admin/', follow_redirects=False).status_code == 302

    def test_logout(self, client, admin_user):
        login(client, 'admin@example.com', 'test-password-123')
        client.get('/admin/logout')
        assert client.get('/admin/', follow_redirects=False).status_code == 302


class TestChangePassword:
    def test_change_password_flow(self, client, admin_user):
        login(client, 'admin@example.com', 'test-password-123')
        r = client.post('/admin/change-password/', data={
            'current_password': 'test-password-123',
            'new_password': 'new-password-456',
            'confirm_password': 'new-password-456',
        })
        assert r.status_code == 302
        assert admin_user.check_password('new-password-456')

    def test_wrong_current_password(self, client, admin_user):
        login(client, 'admin@example.com', 'test-password-123')
        client.post('/admin/change-password/', data={
            'current_password': 'nope',
            'new_password': 'new-password-456',
            'confirm_password': 'new-password-456',
        })
        assert admin_user.check_password('test-password-123')
