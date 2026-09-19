#!/usr/bin/env python3
"""
Screenshot a page of this app, including admin pages that need a login.

Two modes:

  rendered (default)  The page is rendered through Flask's test client, so no
                      server has to run and admin pages work without a real
                      login round-trip. The HTML is written to a temp file with
                      /static/ rewritten to file:// paths, then Chrome shoots
                      it. JavaScript still runs; anything that needs a live
                      server (fetch calls, form posts) will not.

  --live              Chrome opens the URL on a running server instead. Use it
                      for public pages whose behaviour depends on real requests.

Examples:
    python scripts/shoot.py /admin/admin_events/
    python scripts/shoot.py /admin/admin_registrations/edit/ --id 3 --height 2000
    python scripts/shoot.py / --live --width 390 --height 844 --name phone
    python scripts/shoot.py /admin/admin_events/attendee-sheet/ --id 2 --open

Why this exists: Chrome sometimes never exits in headless mode and macOS has no
`timeout`, so every call needs its own watchdog. Getting that wrong wastes
minutes per screenshot.
"""

import argparse
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHROME_CANDIDATES = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'google-chrome',
    'chromium',
]


def find_chrome():
    for candidate in CHROME_CANDIDATES:
        if os.path.sep in candidate:
            if os.path.exists(candidate):
                return candidate
        else:
            from shutil import which
            found = which(candidate)
            if found:
                return found
    sys.exit('No Chrome or Chromium found. Set CHROME_PATH.')


def default_out_dir():
    """Scratchpad when Claude Code set one, else a temp dir."""
    for var in ('CLAUDE_SCRATCHPAD', 'TMPDIR'):
        value = os.environ.get(var)
        if value:
            return pathlib.Path(value) / 'shots'
    return pathlib.Path('/tmp/shots')


def render_to_file(path, out_file, email, password, login=True):
    """Render `path` through the test client and save it as a standalone file."""
    os.environ.setdefault('FLASK_CONFIG', 'development')
    from app import create_app

    app = create_app(os.environ.get('FLASK_CONFIG', 'development'))
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    if login:
        client.post('/admin/login', data={'email': email, 'password': password})

    response = client.get(path, follow_redirects=True)
    html = response.get_data(as_text=True)

    static = (ROOT / 'app' / 'static').as_uri()
    html = html.replace('"/static/', f'"{static}/').replace("'/static/", f"'{static}/")
    out_file.write_text(html)
    return response.status_code


def run_chrome(chrome, url, png, width, height, profile, wait):
    """Shoot one page, killing Chrome if it hangs (it sometimes does)."""
    cmd = [
        chrome, '--headless=new', '--disable-gpu', '--no-first-run',
        '--no-default-browser-check', '--hide-scrollbars',
        '--allow-file-access-from-files',
        f'--user-data-dir={profile}',
        f'--window-size={width},{height}',
        '--virtual-time-budget=5000',
        f'--screenshot={png}',
        url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + wait
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    else:
        proc.kill()
        proc.wait()
    return png.exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', help='Path on the site, e.g. /admin/admin_events/')
    parser.add_argument('--id', help='Value for an ?id= query parameter')
    parser.add_argument('--query', default='', help='Extra query string, e.g. "panel=1"')
    parser.add_argument('--live', action='store_true',
                        help='Shoot a running server instead of rendering in-process')
    parser.add_argument('--base', default='http://127.0.0.1:5000', help='Server for --live')
    parser.add_argument('--width', type=int, default=1440)
    parser.add_argument('--height', type=int, default=900,
                        help='Use a tall value for a whole-page shot')
    parser.add_argument('--name', help='Output file stem (default: derived from the path)')
    parser.add_argument('--out', help='Output directory')
    parser.add_argument('--wait', type=int, default=40, help='Seconds before Chrome is killed')
    parser.add_argument('--no-login', action='store_true', help='Render without logging in')
    parser.add_argument('--email', default=os.environ.get('DEMO_ADMIN_EMAIL', 'admin@example.com'))
    parser.add_argument('--password', default=os.environ.get('DEMO_ADMIN_PASSWORD', 'local-dev-2026'))
    parser.add_argument('--open', action='store_true', help='Open the PNG when done (macOS)')
    args = parser.parse_args()

    path = args.path
    query = args.query
    if args.id:
        query = f'id={args.id}' + (f'&{query}' if query else '')
    if query:
        path = f'{path}{"&" if "?" in path else "?"}{query}'

    out_dir = pathlib.Path(args.out) if args.out else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or (path.strip('/').replace('/', '-').split('?')[0] or 'home')
    png = out_dir / f'{stem}.png'
    chrome = os.environ.get('CHROME_PATH') or find_chrome()

    if args.live:
        url = args.base.rstrip('/') + path
        status = 'live'
    else:
        html_file = out_dir / f'{stem}.html'
        code = render_to_file(path, html_file, args.email, args.password,
                              login=not args.no_login)
        if code >= 400:
            print(f'warning: {path} returned {code}', file=sys.stderr)
        url = html_file.as_uri()
        status = code

    ok = run_chrome(chrome, url, png, args.width, args.height,
                    out_dir / f'profile-{stem}', args.wait)
    if not ok:
        sys.exit(f'Chrome produced no file for {path}')

    print(f'{png}  ({status}, {args.width}x{args.height})')
    if args.open:
        subprocess.run(['open', str(png)], check=False)


if __name__ == '__main__':
    main()
