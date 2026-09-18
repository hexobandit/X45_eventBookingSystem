"""
Payment QR code generation.

Two offline payment methods, each with its own open QR standard:
- "domestic": Czech bank transfer in CZK — SPAYD ("QR platba"), scanned by
  every Czech banking app.
- "sepa": SEPA credit transfer in EUR — EPC069-12 ("SEPA QR" / GiroCode),
  scanned by German/Austrian/Dutch/Slovak banking apps.

Both encode a plain string into a QR image; no third-party service involved.
"""

import io
import re

import qrcode

from app import branding


QR_KINDS = ('domestic', 'sepa')

CZ_ACCOUNT_RE = re.compile(r'^(?:(\d{1,6})-)?(\d{2,10})/(\d{4})$')
IBAN_RE = re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$')
BIC_RE = re.compile(r'^[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?$')


def normalize_iban(value):
    """Strip spaces/uppercase; return the IBAN or None if it does not validate."""
    if not value:
        return None
    cleaned = value.replace(' ', '').upper()
    if not IBAN_RE.match(cleaned):
        return None
    # ISO 7064 mod 97-10 check
    rearranged = cleaned[4:] + cleaned[:4]
    numeric = ''.join(str(int(ch, 36)) for ch in rearranged)
    if int(numeric) % 97 != 1:
        return None
    return cleaned


def normalize_bic(value):
    """Uppercase a BIC/SWIFT code, or None if empty/invalid."""
    if not value:
        return None
    cleaned = value.replace(' ', '').upper()
    return cleaned if BIC_RE.match(cleaned) else None


def czech_account_to_iban(account):
    """Convert a Czech domestic account number ("[prefix-]number/bank") to IBAN.

    Returns the IBAN string, or None if the input is not a valid Czech
    domestic account format. Passes through strings that already look
    like an IBAN (spaces ignored).
    """
    if not account:
        return None
    cleaned = account.replace(' ', '').upper()
    if IBAN_RE.match(cleaned):
        return cleaned

    m = CZ_ACCOUNT_RE.match(cleaned)
    if not m:
        return None
    prefix, number, bank = m.groups()
    bban = f"{bank}{(prefix or '').zfill(6)}{number.zfill(10)}"

    # ISO 13616 check digits: move country+00 to the end, letters -> numbers, mod 97
    rearranged = bban + 'CZ00'
    numeric = ''.join(str(int(ch, 36)) for ch in rearranged)
    check = 98 - int(numeric) % 97
    return f"CZ{check:02d}{bban}"


def _spayd_escape(value):
    """SPAYD requires * to be percent-encoded; keep values plain ASCII-ish."""
    return str(value).replace('*', '%2A')


def spayd_string(iban, amount, currency, variable_symbol=None, message=None):
    """Build a SPAYD 1.0 payment string (Czech "QR platba" standard)."""
    parts = [
        'SPD*1.0',
        f'ACC:{iban}',
        f'AM:{amount:.2f}',
        f'CC:{currency.upper()}',
    ]
    if variable_symbol:
        parts.append(f'X-VS:{_spayd_escape(variable_symbol)}')
    if message:
        parts.append(f'MSG:{_spayd_escape(message[:60])}')
    return '*'.join(parts)


def epc_string(beneficiary, iban, amount_eur, reference=None, bic=None):
    """Build an EPC069-12 QR string for a SEPA credit transfer (EUR only)."""
    return '\n'.join([
        'BCD',
        '002',
        '1',
        'SCT',
        bic or '',  # BIC optional since EPC v2
        beneficiary[:70],
        iban,
        f'EUR{amount_eur:.2f}',
        '',  # purpose code
        '',  # structured reference
        (reference or '')[:140],  # unstructured remittance info
        '',
    ])


def qr_png_bytes(data, box_size=8):
    """Render a payment string into PNG bytes."""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=3,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def domestic_qr_string(account, amount_czk, vs=None, message=None):
    """SPAYD string for a domestic CZK transfer, or None if inputs are unusable."""
    if amount_czk is None:
        return None
    iban = czech_account_to_iban(account)
    if not iban:
        return None
    return spayd_string(iban, float(amount_czk), 'CZK', variable_symbol=vs, message=message)


def sepa_qr_string(iban, amount_eur, beneficiary, vs=None, message=None, bic=None):
    """EPC string for a SEPA EUR transfer, or None if inputs are unusable."""
    if amount_eur is None:
        return None
    iban = normalize_iban(iban)
    if not iban:
        return None
    reference = f'VS {vs} {message or ""}'.strip() if vs else (message or '')
    return epc_string(beneficiary or branding.PAYMENT_BENEFICIARY, iban, float(amount_eur),
                      reference=reference, bic=normalize_bic(bic))


def payment_qr_string(kind, event, vs, message, overrides=None):
    """Payment string for one method of an event, with optional field overrides.

    `overrides` lets the admin "Generate QR" button preview unsaved form
    values: keys account, amount, iban, bic, beneficiary, vs.
    """
    o = overrides or {}
    if 'vs' in o:
        vs = o['vs'] or None
    if kind == 'domestic':
        return domestic_qr_string(
            o.get('account', event.payment_bank_account),
            o.get('amount', event.domestic_amount),
            vs=vs, message=message)
    if kind == 'sepa':
        return sepa_qr_string(
            o.get('iban', event.payment_sepa_iban),
            o.get('amount', event.sepa_amount),
            o.get('beneficiary', event.payment_beneficiary_name) or branding.PAYMENT_BENEFICIARY,
            vs=vs, message=message,
            bic=o.get('bic', event.payment_sepa_bic))
    return None


def event_test_qr_png(event, kind='domestic', overrides=None):
    """Sample payment QR for an event with placeholder client data.

    Same content a real registration QR gets, but with a dummy name and the
    event-level variable symbol — lets admins scan-test payment details
    before any registration exists. Returns None when details are missing.
    """
    message = f'{event.title[:40]} TEST Jan Novak'[:60]
    data = payment_qr_string(kind, event, event.payment_variable_symbol, message, overrides)
    return qr_png_bytes(data) if data else None


def registration_qr_png(registration, kind='domestic'):
    """Payment QR PNG for a registration and method, or None if not configured."""
    event = registration.event
    vs = registration.variable_symbol or event.payment_variable_symbol
    message = f'{event.title[:40]} {registration.full_name}'[:60]
    data = payment_qr_string(kind, event, vs, message)
    return qr_png_bytes(data) if data else None


def registration_qr_pngs(registration):
    """Dict of kind -> PNG bytes for every method the event offers."""
    event = registration.event
    out = {}
    if event.has_domestic_payment:
        png = registration_qr_png(registration, 'domestic')
        if png:
            out['domestic'] = png
    if event.has_sepa_payment:
        png = registration_qr_png(registration, 'sepa')
        if png:
            out['sepa'] = png
    return out
