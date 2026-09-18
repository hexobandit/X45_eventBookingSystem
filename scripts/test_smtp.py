#!/usr/bin/env python3
"""
Standalone SMTP connection test.

Reads connection details from environment variables — never hardcode
credentials in this file.

Usage:
    SMTP_HOST=mail.example.com SMTP_USER=info@anteriorcourses.com \
    SMTP_PASS=... FROM_EMAIL=info@anteriorcourses.com TO_EMAIL=you@example.com \
    python scripts/test_smtp.py
"""

import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)
FROM_NAME = os.environ.get("FROM_NAME", "ANTERIOR")
TO_EMAIL = os.environ.get("TO_EMAIL", "")


def test_smtps_465():
    """Port 465: implicit SSL (SMTPS) — wraps entire connection in SSL."""
    print("=== Testing SMTPS (port 465) ===")
    print(f"Connecting to {SMTP_HOST}:465 with SSL ...\n")

    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=30)
        server.set_debuglevel(1)
        print("[OK] Connected with SSL\n")

        server.login(SMTP_USER, SMTP_PASS)
        print("[OK] Logged in\n")

        send_test(server)
        server.quit()
        print("[OK] Done - check your inbox!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {type(e).__name__}: {e}")
        return False


def test_starttls_587():
    """Port 587: STARTTLS — upgrades a plain connection to TLS."""
    print("=== Testing STARTTLS (port 587) ===")
    print(f"Connecting to {SMTP_HOST}:587 ...\n")

    try:
        server = smtplib.SMTP(SMTP_HOST, 587, timeout=30)
        server.set_debuglevel(1)
        server.starttls()
        print("[OK] STARTTLS established\n")

        server.login(SMTP_USER, SMTP_PASS)
        print("[OK] Logged in\n")

        send_test(server)
        server.quit()
        print("[OK] Done - check your inbox!")
        return True

    except Exception as e:
        print(f"\n[FAIL] {type(e).__name__}: {e}")
        return False


def send_test(server):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'SMTP Test - anteriorcourses.com'
    msg['From'] = f'{FROM_NAME} <{FROM_EMAIL}>'
    msg['To'] = TO_EMAIL
    msg.attach(MIMEText('SMTP test OK. If you can see this email, sending works.', 'plain', 'utf-8'))
    msg.attach(MIMEText('<h2>SMTP Test OK</h2><p>If you can see this email, sending works.</p>', 'html', 'utf-8'))

    refused = server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
    if refused:
        print(f"[WARN] Refused: {refused}")
    else:
        print(f"[OK] Email sent to {TO_EMAIL}\n")


if __name__ == "__main__":
    missing = [name for name, val in [("SMTP_HOST", SMTP_HOST), ("SMTP_USER", SMTP_USER),
                                      ("SMTP_PASS", SMTP_PASS), ("TO_EMAIL", TO_EMAIL)] if not val]
    if missing:
        print(f"[!] Missing environment variables: {', '.join(missing)}")
        sys.exit(1)
    # Try port 465 first, fall back to 587
    if not test_smtps_465():
        test_starttls_587()
