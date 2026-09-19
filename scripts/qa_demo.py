#!/usr/bin/env python3
"""
Walk the whole site in-process and report anything a visitor or an admin
would hit: server errors, leaked client branding, and broken demo-mode rules.

Runs against the development database through Flask's test client, so it needs
no server and changes nothing. Exits non-zero when it finds a problem, which
makes it usable as a pre-deploy gate.

    python scripts/qa_demo.py                 # crawl + brand check
    python scripts/qa_demo.py --demo          # also assert the demo-mode rules
    python scripts/qa_demo.py --forbid Acme   # extra words that must not appear

The brand check is the important half: this repo is the product, so a client's
name, domain or accent colour appearing anywhere in a page means a de-branding
slip that would otherwise reach the public demo.
"""

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Words that must never appear in a rendered page of the product.
DEFAULT_FORBIDDEN = ['ANTERIOR', 'Anterior', 'anteriorcourses', 'Otrusin', 'McGregor', '29ABE2']

# Pages that are expected to answer 404 (removed client-specific sections).
EXPECT_404 = ['/books', '/nature-teaches-us']


def sample_ids(app):
    """Ids and a slug to fill into parameterised routes."""
    from app.models import Event, Registration
    with app.app_context():
        event = Event.query.filter_by(is_test=False).first() or Event.query.first()
        reg = Registration.query.first()
        return {
            'event_id': event.id if event else 0,
            'slug': event.slug if event else 'none',
            'reg_id': reg.id if reg else 0,
            'token': reg.confirmation_token if reg else 'none',
            'email': reg.email if reg else 'none@example.com',
        }


def public_paths(ids):
    return ['/', '/courses', f'/courses/{ids["slug"]}', '/about', '/contact',
            '/privacy', '/robots.txt', '/sitemap.xml', '/admin/login']


def admin_paths(app, ids):
    """Every admin GET route, with ?id= filled in where the view needs one."""
    paths = []
    for rule in app.url_map.iter_rules():
        path = str(rule)
        if not path.startswith('/admin') or 'GET' not in rule.methods or '<' in path:
            continue
        # Flask-Admin plumbing, not pages an admin visits
        if any(part in path for part in ('/logout', '/ajax/', '/export/', '/action/', '/new/')):
            continue
        needs_id = any(k in path for k in ('details', 'edit', 'manage', 'attendee-sheet',
                                           'visual-edit', 'email-preview', 'test-qr'))
        if 'email-preview' in path:
            paths.append(f'{path}?reg_id={ids["reg_id"]}&type=payment')
        elif needs_id:
            paths.append(f'{path}?id={ids["event_id"] if "registration" not in path else ids["reg_id"]}')
        else:
            paths.append(path)
    return sorted(set(paths))


def check(client, path, forbidden, problems, expect_404=False):
    response = client.get(path, follow_redirects=False)
    body = response.get_data(as_text=True) if response.content_type and 'text' in response.content_type else ''
    leaks = [word for word in forbidden if word in body]
    bad_status = response.status_code >= 500 or (expect_404 and response.status_code != 404)
    if bad_status:
        problems.append(f'{path}: HTTP {response.status_code}')
    if leaks:
        problems.append(f'{path}: brand leak {leaks}')
    flag = ''
    if bad_status:
        flag = 'ERROR'
    elif leaks:
        flag = f'LEAK {leaks}'
    print(f'  {response.status_code:>3} {path} {flag}')


def demo_rules(app, client, ids, problems):
    """DEMO_MODE promises: banner, in-browser email previews, guarded actions."""
    print('\nDemo mode rules')
    home = client.get('/').get_data(as_text=True)
    if 'demo-banner' not in home:
        problems.append('demo: banner missing on the public site')
    print(f'  banner on the public site: {"yes" if "demo-banner" in home else "NO"}')

    for kind in ('confirmation', 'payment', 'reminder'):
        code = client.get(f'/registration/{ids["token"]}/email/{kind}').status_code
        if code != 200:
            problems.append(f'demo: email preview {kind} returned {code}')
        print(f'  email preview {kind}: {code}')

    created = client.post('/admin/admin_users/new/', data={
        'email': 'qa-should-not-exist@example.com', 'first_name': 'Q', 'last_name': 'A',
        'is_admin': 'y', 'is_active': 'y', 'new_password': 'x' * 12})
    from app.models import User
    with app.app_context():
        leaked = User.query.filter_by(email='qa-should-not-exist@example.com').count()
    if leaked:
        problems.append('demo: guard let a user be created')
    print(f'  user creation refused: {"yes" if not leaked else "NO"} (HTTP {created.status_code})')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--demo', action='store_true', help='Also check the demo-mode rules')
    parser.add_argument('--forbid', nargs='*', default=[], help='Extra forbidden words')
    parser.add_argument('--email', default=os.environ.get('DEMO_ADMIN_EMAIL', 'admin@example.com'))
    parser.add_argument('--password', default=os.environ.get('DEMO_ADMIN_PASSWORD', 'local-dev-2026'))
    args = parser.parse_args()

    if args.demo:
        os.environ['DEMO_MODE'] = '1'
    os.environ.setdefault('FLASK_CONFIG', 'development')

    from app import create_app
    app = create_app(os.environ.get('FLASK_CONFIG', 'development'))
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    forbidden = DEFAULT_FORBIDDEN + args.forbid
    ids = sample_ids(app)
    problems = []

    print('Public pages')
    for path in public_paths(ids):
        check(client, path, forbidden, problems)
    for path in EXPECT_404:
        check(client, path, forbidden, problems, expect_404=True)

    print('\nAdmin pages')
    login = client.post('/admin/login', data={'email': args.email, 'password': args.password})
    if login.status_code != 302:
        sys.exit(f'Admin login failed for {args.email}. Pass --email / --password.')
    for path in admin_paths(app, ids):
        check(client, path, forbidden, problems)

    if args.demo:
        demo_rules(app, client, ids, problems)

    print()
    if problems:
        print(f'{len(problems)} problem(s):')
        for problem in problems:
            print(f'  - {problem}')
        sys.exit(1)
    print('No problems found.')


if __name__ == '__main__':
    main()
