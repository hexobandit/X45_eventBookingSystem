"""Deployed application version.

Production deploys via rsync (no git checkout on the server), so deploy.sh
writes app/deploy_info.json from the local git state before pushing. This
module reads that file; in development (no deploy_info.json) it falls back
to asking git directly. The file is read fresh on each call (it is tiny and
only admin pages ask); only the git fallback is cached per process.
"""

import json
import os
import subprocess

_git_cached = None

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_INFO_PATH = os.path.join(_APP_DIR, 'deploy_info.json')


def get_app_version():
    """Return {'rev', 'subject', 'date', 'changes': [...]} or None if unknown."""
    global _git_cached
    info = _read_deploy_info()
    if info:
        return info
    if _git_cached is None:
        _git_cached = _read_git() or {}
    return _git_cached or None


def _read_deploy_info():
    try:
        with open(DEPLOY_INFO_PATH, encoding='utf-8') as f:
            info = json.load(f)
        if info.get('rev'):
            return info
    except Exception:
        pass
    return None


def _read_git():
    root = os.path.dirname(_APP_DIR)
    try:
        out = subprocess.run(
            ['git', 'log', '-1', '--format=%h|%s|%cd', '--date=format:%d.%m.%Y %H:%M'],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and '|' in out.stdout:
            rev, subject, date = out.stdout.strip().split('|', 2)
            return {'rev': rev, 'subject': subject, 'date': date, 'changes': []}
    except Exception:
        pass
    return None
