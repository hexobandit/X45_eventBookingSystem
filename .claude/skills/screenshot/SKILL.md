---
name: screenshot
description: Take a screenshot of any page of this app, including admin pages that need a login. Use whenever you change a template or stylesheet and want to see the result, or when the user asks how a page looks. Handles the login, the static asset paths and the headless Chrome watchdog.
---

# Screenshot a page

Use `scripts/shoot.py`. Do not hand-roll Chrome commands: it hangs often, macOS
has no `timeout`, and admin pages need a session.

```bash
.venv/bin/python scripts/shoot.py <path> [--id N] [--width W] [--height H] [--name STEM] [--out DIR]
```

Always pass `--out` with this session's scratchpad directory so you can read the
PNG back afterwards. Then view it with the Read tool.

## Typical calls

```bash
# admin list, desktop
.venv/bin/python scripts/shoot.py /admin/admin_events/ --out "$SCRATCH" --name courses

# one record, tall enough for the whole page
.venv/bin/python scripts/shoot.py /admin/admin_registrations/edit/ --id 3 --height 2000 --out "$SCRATCH"

# the slide-in panel variant
.venv/bin/python scripts/shoot.py /admin/admin_registrations/edit/ --id 3 --query panel=1 --width 760 --out "$SCRATCH"

# public page at phone width, against the running server
.venv/bin/python scripts/shoot.py / --live --width 390 --height 844 --name phone --out "$SCRATCH"
```

## How it works, and what that costs you

By default the page is rendered through Flask's test client and written to a
temporary HTML file with `/static/` rewritten to `file://`, then Chrome shoots
that file. No server needed and the admin login is automatic. CSS and page
JavaScript run normally.

What does not work in that mode: anything needing a live request, so fetch
calls, form posts, and Bootstrap assets that load from a CDN. A Flask-Admin
filter dropdown looking unstyled in a shot is that, not a real bug. When the
behaviour matters, start the server and add `--live`.

## Notes

- Chrome refuses windows narrower than 500 px. A 390 px shot comes back cropped
  at 500 px, so do not read a "phone overflow" from it. Measure real overflow by
  comparing `document.documentElement.scrollWidth` to `clientWidth` instead.
- The dev server cannot bind a port inside the sandbox. Start it outside the
  sandbox before using `--live`.
- Credentials default to the demo admin. Override with `--email` / `--password`
  or the `DEMO_ADMIN_EMAIL` / `DEMO_ADMIN_PASSWORD` environment variables.
