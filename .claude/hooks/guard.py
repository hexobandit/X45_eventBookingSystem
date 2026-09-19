#!/usr/bin/env python3
"""
Two guards for this repo, driven by Claude Code hooks.

PreToolUse   Refuse edits to paths that must never be written from here:
             the client repo next door, the read-only reference copy, the
             deploy key, the local database and the .env file.

PostToolUse  After an admin stylesheet partial is edited, check that its
             cache-busting query in admin.css was bumped today. nginx caches
             static files for 30 days, so a forgotten bump ships a change
             nobody can see.

Reads the hook payload on stdin, writes a JSON decision on stdout.
"""

import datetime
import json
import os
import re
import sys

PROTECTED = [
    ('X41_anterior', 'the client site repo is a separate business and is never edited from here'),
    ('00-reference-web-to-replicate', 'the reference copy is read-only'),
    ('/nono/', 'the deploy key must not be touched or committed'),
    ('/instance/', 'the local database and instance files stay out of edits'),
]

PROTECTED_EXACT = [
    ('.env', 'secrets file: edit it by hand, never from a tool call'),
]


def deny(reason):
    json.dump({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    }, sys.stdout)
    sys.exit(0)


def pre_tool_use(tool_input):
    path = tool_input.get('file_path') or tool_input.get('notebook_path') or ''
    if not path:
        return
    normalised = os.path.abspath(path)
    for needle, why in PROTECTED:
        if needle in normalised:
            deny(f'Refused: {why} ({needle}).')
    if os.path.basename(normalised) in [name for name, _ in PROTECTED_EXACT]:
        why = dict(PROTECTED_EXACT)[os.path.basename(normalised)]
        deny(f'Refused: {why}.')


def post_tool_use(tool_input, project_dir):
    """Remind about the cache-busting bump after an admin partial changes."""
    path = tool_input.get('file_path') or ''
    if not path.endswith('.css'):
        return
    if '/static/css/admin/' in path:
        index_name, prefix = 'admin.css', 'admin/'
    elif '/static/css/_' in path:
        index_name, prefix = 'style.css', ''
    else:
        return
    partial = os.path.basename(path)
    index = os.path.join(project_dir, 'app', 'static', 'css', index_name)
    try:
        with open(index, encoding='utf-8') as handle:
            imports = handle.read()
    except OSError:
        return

    match = re.search(rf"@import '{re.escape(prefix + partial)}\?v=(\d{{8}})", imports)
    today = datetime.date.today().strftime('%Y%m%d')
    if match and match.group(1) == today:
        return

    stamped = match.group(1) if match else 'none'
    message = (f'{partial} changed but its @import in app/static/css/{index_name} still says '
               f'v={stamped} (today is {today}). nginx caches /static/ for 30 days, so bump it '
               f'or the change will not reach anyone.')
    json.dump({
        'systemMessage': message,
        'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': message},
    }, sys.stdout)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    event = payload.get('hook_event_name')
    tool_input = payload.get('tool_input') or {}
    project_dir = payload.get('cwd') or os.getcwd()

    if event == 'PreToolUse':
        pre_tool_use(tool_input)
    elif event == 'PostToolUse':
        post_tool_use(tool_input, project_dir)


if __name__ == '__main__':
    main()
