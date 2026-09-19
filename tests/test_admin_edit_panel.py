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


class TestFormRoundTrip:
    """The page renders every form field (the rarely used ones inside the
    "All fields" fold), so saving from the browser cannot silently wipe a
    value the layout does not show."""

    def _fields(self, html):
        """Field names the browser would submit: inputs, selects, textareas."""
        import re
        names = set()
        for tag in re.findall(r'<(?:input|select|textarea)\b[^>]*>', html):
            if 'disabled' in tag:
                continue
            m = re.search(r'name="([^"]+)"', tag)
            if m:
                names.add(m.group(1))
        return names

    def test_every_editable_column_is_rendered(self, client, admin_user, event, make_registration):
        reg = make_registration(event)
        login(client, 'admin@example.com', 'test-password-123')
        names = self._fields(client.get(f'{EDIT}?id={reg.id}').get_data(as_text=True))
        for expected in ('status', 'payment_status', 'admin_note', 'payment_note',
                         'billing_name', 'billing_ico', 'paid_at', 'confirmed_at',
                         'cancellation_reason', 'payment_method'):
            assert expected in names, f'{expected} is missing from the edit page'

    def test_saving_unchanged_keeps_the_hidden_values(self, app, client, admin_user, event, make_registration):
        from datetime import datetime
        from app.extensions import db
        from app.models import Registration
        from app.models.registration import PaymentStatus

        reg = make_registration(event)
        reg.billing_name = 'Studio Lumen s.r.o.'
        reg.billing_ico = '12345678'
        reg.payment_note = 'paid at the door'
        reg.payment_status = PaymentStatus.PAID
        reg.paid_at = datetime(2026, 9, 1, 10, 30)
        db.session.commit()
        reg_id = reg.id

        login(client, 'admin@example.com', 'test-password-123')
        html = client.get(f'{EDIT}?id={reg_id}').get_data(as_text=True)
        assert 'Studio Lumen s.r.o.' in html          # rendered, so it round-trips

        r = client.post(f'{EDIT}?id={reg_id}', data={
            'email': reg.email, 'phone': '', 'status': 'PENDING',
            'payment_status': 'PAID', 'paid_at': '2026-09-01 10:30:00',
            'admin_note': 'note from the new page', 'payment_note': 'paid at the door',
            'billing_name': 'Studio Lumen s.r.o.', 'billing_ico': '12345678',
        })
        assert r.status_code == 302

        saved = db.session.get(Registration, reg_id)
        assert saved.admin_note == 'note from the new page'
        assert saved.billing_name == 'Studio Lumen s.r.o.'
        assert saved.billing_ico == '12345678'
        assert saved.payment_note == 'paid at the door'
        assert saved.payment_status == PaymentStatus.PAID
