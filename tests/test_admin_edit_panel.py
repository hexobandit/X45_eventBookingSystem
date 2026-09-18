"""
Slide-in edit panel: panel-mode rendering of the registration edit view.
"""

from tests.test_admin_auth import login

EDIT = '/admin/admin_registrations/edit/'


class TestPanelMode:
    def test_panel_mode_renders_chromeless(self, client, admin_user, event, make_registration):
        reg = make_registration(event)
        login(client, 'admin@example.com', 'test-password-123')
        html = client.get(f'{EDIT}?id={reg.id}&panel=1').get_data(as_text=True)

        assert 'panel-mode' in html                      # chrome-less base
        assert 'Website Administration' not in html      # no sidebar
        assert 'Delete registration' not in html         # no delete zone
        assert 'Full edit page' in html or 'full edit page' in html
        assert 'Back to list' not in html

    def test_regular_edit_view_unchanged(self, client, admin_user, event, make_registration):
        reg = make_registration(event)
        login(client, 'admin@example.com', 'test-password-123')
        html = client.get(f'{EDIT}?id={reg.id}').get_data(as_text=True)

        assert 'panel-mode' not in html
        assert 'Website Administration' in html          # sidebar present
        assert 'Delete registration' in html             # delete zone present

    def test_save_in_panel_mode_redirects_back_into_panel(self, client, admin_user, event, make_registration):
        reg = make_registration(event)
        login(client, 'admin@example.com', 'test-password-123')
        r = client.post(f'{EDIT}?id={reg.id}&panel=1', data={
            'email': reg.email,
            'phone': '',
            'status': 'PENDING',
            'payment_status': 'UNPAID',
            'admin_note': 'edited from panel',
            'payment_note': '',
            'variable_symbol': reg.variable_symbol or '',
        })
        assert r.status_code == 302
        assert 'panel=1' in r.headers['Location']
        assert 'saved=1' in r.headers['Location']
