#!/usr/bin/env python3
"""
Dev helper: send form submissions sequentially for email stress testing.
All use the same email, but unique names for easy tracking.

Usage:
    python scripts/test_bulk.py contact              # 50 contacts, no delay
    python scripts/test_bulk.py contact 2            # 50 contacts, 2s delay
    python scripts/test_bulk.py contact 1 10         # 10 contacts, 1s delay
    python scripts/test_bulk.py register             # 50 registrations, no delay
    python scripts/test_bulk.py register 2           # 50 registrations, 2s delay
    python scripts/test_bulk.py register 0.5 20      # 20 registrations, 0.5s delay
"""

import os
import signal
import sys
import re
import time
import requests

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
EMAIL = "romano.udige@gmail.com"
EVENT_SLUG = "novy-testovaci-kurz"

# Graceful Ctrl+C
stopped = False

def handle_sigint(sig, frame):
    global stopped
    stopped = True
    print("\n\n  [!] Ctrl+C — stopping after current request...\n")

signal.signal(signal.SIGINT, handle_sigint)


def get_csrf(session, url):
    r = session.get(url)
    r.raise_for_status()
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
    if not match:
        match = re.search(r'id="csrf_token"[^>]*value="([^"]+)"', r.text)
    if not match:
        print(f"  [!] CSRF token not found on {url}")
        sys.exit(1)
    return match.group(1)


def bulk_contact(total, delay):
    print(f"=== Sending {total} contact forms (delay: {delay}s) ===\n")
    ok, fail = 0, 0
    t0 = time.time()

    for i in range(1, total + 1):
        if stopped:
            break

        s = requests.Session()
        url = f"{BASE}/kontakt"
        csrf = get_csrf(s, url)

        data = {
            "name": f"Test Kontakt {i:02d}",
            "email": EMAIL,
            "phone": f"+420 700 {i:03d} {i:03d}",
            "subject": "consultation",
            "message": f"Testovací zpráva č. {i:02d} z {total}. Bulk test odesílání kontaktního formuláře.",
            "gdpr": "y",
            "csrf_token": csrf,
        }

        r = s.post(url, data=data, headers={"Referer": url}, allow_redirects=True)
        if "odeslano" in r.url:
            ok += 1
            print(f"  [{i:02d}/{total}] OK - Test Kontakt {i:02d}")
        else:
            fail += 1
            errors = re.findall(r'class="form-error">([^<]+)<', r.text)
            print(f"  [{i:02d}/{total}] FAIL - Test Kontakt {i:02d} - {errors or r.status_code}")

        if delay and i < total:
            time.sleep(delay)

    elapsed = time.time() - t0
    print(f"\n=== Done in {elapsed:.1f}s: {ok} OK, {fail} FAIL ===")


def bulk_register(total, delay):
    print(f"=== Sending {total} registrations (delay: {delay}s) ===\n")
    ok, fail, skip = 0, 0, 0
    t0 = time.time()

    for i in range(1, total + 1):
        if stopped:
            break

        s = requests.Session()
        detail_url = f"{BASE}/skoleni/{EVENT_SLUG}"
        post_url = f"{BASE}/skoleni/{EVENT_SLUG}/registrace"
        csrf = get_csrf(s, detail_url)

        # Unique email per registration (event has unique constraint on event_id + email)
        unique_email = f"test.lekar{i:02d}.{int(time.time())}@example.com"

        data = {
            "first_name": f"Lekar",
            "last_name": f"Test {i:02d}",
            "email": unique_email,
            "phone": f"+420 600 {i:03d} {i:03d}",
            "organization": f"Klinika Test {i:02d}",
            "notes": f"Bulk test registrace č. {i:02d} z {total}.",
            "gdpr": "y",
            "event_slug": EVENT_SLUG,
            "csrf_token": csrf,
        }

        r = s.post(post_url, data=data, headers={"Referer": detail_url}, allow_redirects=True)
        if "uspesna" in r.url:
            ok += 1
            print(f"  [{i:02d}/{total}] OK - Lekar Test {i:02d} ({unique_email})")
        else:
            flashes = re.findall(r'class="flash[^"]*">([^<]+)<', r.text)
            errors = re.findall(r'class="form-error">([^<]+)<', r.text)
            msg = flashes or errors or [f"status {r.status_code}"]
            if "naplněna" in str(msg).lower() or "naplnila" in str(msg).lower():
                skip += 1
                print(f"  [{i:02d}/{total}] FULL - Lekar Test {i:02d} - capacity reached")
                break
            else:
                fail += 1
                print(f"  [{i:02d}/{total}] FAIL - Lekar Test {i:02d} - {msg}")

        if delay and i < total:
            time.sleep(delay)

    elapsed = time.time() - t0
    print(f"\n=== Done in {elapsed:.1f}s: {ok} OK, {fail} FAIL, {skip} FULL ===")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else None
    delay = float(args[1]) if len(args) > 1 else 0
    total = int(args[2]) if len(args) > 2 else 50

    if cmd == "contact":
        bulk_contact(total, delay)
    elif cmd == "register":
        bulk_register(total, delay)
    else:
        print(f"Usage: python {sys.argv[0]} <contact|register> [delay_seconds] [count]")
        print(f"\nExamples:")
        print(f"  python {sys.argv[0]} contact          # 50 contacts, no delay (stress test)")
        print(f"  python {sys.argv[0]} contact 2        # 50 contacts, 2s between each")
        print(f"  python {sys.argv[0]} contact 1 10     # 10 contacts, 1s between each")
        print(f"  python {sys.argv[0]} register 0.5 20  # 20 registrations, 0.5s between each")
