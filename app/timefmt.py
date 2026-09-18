"""Compact relative-time formatting shared by templates and admin views."""

from datetime import datetime


def time_ago(dt):
    """Compact relative time: 'just now', '5 min ago', '3 h ago', '2 d ago'."""
    if dt is None:
        return ''
    delta = datetime.utcnow() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return 'just now'
    if seconds < 3600:
        return f'{seconds // 60} min ago'
    if seconds < 86400:
        return f'{seconds // 3600} h ago'
    days = seconds // 86400
    if days < 30:
        return f'{days} d ago'
    return dt.strftime('%d.%m.%Y')
