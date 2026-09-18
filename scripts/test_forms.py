#!/usr/bin/env python3
"""
Dev helper: auto-populate and submit contact & registration forms.
Handles CSRF tokens automatically.

Usage:
    python scripts/test_forms.py contact
    python scripts/test_forms.py register
    python scripts/test_forms.py both
"""

import os
import sys
import re
import requests

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:5000")

CONTACT_DATA = {
    "name": "Jan Testovací",
    "email": "romano.udige@gmail.com",
    "phone": "+420 777 888 999",
    "subject": "consultation",
    "message": "Dobrý den, toto je testovací zpráva z automatického skriptu. Mám zájem o konzultaci ohledně estetické stomatologie. Děkuji za odpověď.",
    "gdpr": "y",
}

REGISTRATION_DATA = {
    "first_name": "Jana",
    "last_name": "Testová",
    "email": f"test.reg.{int(__import__('time').time())}@example.com",
    "phone": "+420 666 555 444",
    "organization": "Testovací Klinika s.r.o.",
    "notes": "Testovací registrace - prosím ignorujte.",
    "gdpr": "y",
}

EVENT_SLUG = "digitalni-stomatologie"


def get_csrf(session, url):
    """GET the page and extract the CSRF token."""
    r = session.get(url)
    r.raise_for_status()
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
    if not match:
        match = re.search(r'id="csrf_token"[^>]*value="([^"]+)"', r.text)
    if not match:
        print(f"  [!] CSRF token not found on {url}")
        sys.exit(1)
    return match.group(1)


def submit_contact():
    print("=== Submitting contact form ===")
    s = requests.Session()
    url = f"{BASE}/kontakt"

    csrf = get_csrf(s, url)
    data = {**CONTACT_DATA, "csrf_token": csrf}

    r = s.post(url, data=data, allow_redirects=True)
    if "odeslano" in r.url or "kontakt/odeslano" in r.url:
        print(f"  [OK] Contact form submitted -> {r.url}")
    elif r.status_code == 200:
        errors = re.findall(r'class="form-error">([^<]+)<', r.text)
        if errors:
            print(f"  [FAIL] Validation errors: {errors}")
        else:
            print(f"  [OK] Status {r.status_code}, URL: {r.url}")
    else:
        print(f"  [?] Status {r.status_code}, URL: {r.url}")


def submit_registration():
    print(f"=== Submitting registration for: {EVENT_SLUG} ===")
    s = requests.Session()
    detail_url = f"{BASE}/skoleni/{EVENT_SLUG}"
    post_url = f"{BASE}/skoleni/{EVENT_SLUG}/registrace"

    csrf = get_csrf(s, detail_url)
    data = {**REGISTRATION_DATA, "csrf_token": csrf, "event_slug": EVENT_SLUG}

    r = s.post(post_url, data=data, allow_redirects=True)
    if "uspesna" in r.url:
        print(f"  [OK] Registration submitted -> {r.url}")
    elif r.status_code == 200:
        errors = re.findall(r'class="form-error">([^<]+)<', r.text)
        flashes = re.findall(r'class="flash[^"]*">([^<]+)<', r.text)
        if errors:
            print(f"  [FAIL] Validation errors: {errors}")
        elif flashes:
            print(f"  [INFO] Flash messages: {flashes}")
        else:
            print(f"  [OK] Status {r.status_code}, URL: {r.url}")
    else:
        print(f"  [?] Status {r.status_code}, URL: {r.url}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "both"

    if cmd in ("contact", "both"):
        submit_contact()
    if cmd in ("register", "both"):
        submit_registration()
    if cmd not in ("contact", "register", "both"):
        print(f"Usage: python {sys.argv[0]} [contact|register|both]")
