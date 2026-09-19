---
name: demo-qa
description: Check the whole site before a deploy or after a redesign - crawls every public and admin page for server errors, hunts leaked client branding, verifies the demo-mode rules, and runs the test suite. Use when asked to verify, smoke-test, or QA the app, and always before deploying the demo.
---

# Check the app end to end

Three commands, in this order. Stop and report at the first one that fails.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/qa_demo.py --demo
git status --short
```

`qa_demo.py` walks every public page and every admin GET route in-process,
logging in as the demo admin. It reports HTTP 500s, pages that should be gone
but answer 200, and any leaked client branding. With `--demo` it also asserts
the demo promises: the banner renders, the three in-browser email previews
work, and the guard refuses to create a user.

Add `--forbid <word>` for extra strings that must not appear, for instance the
name of a client whose site you just ported something from.

## What a leak means

This repo is the product, not a client site. A client's name, domain, or accent
colour appearing in a rendered page is a de-branding slip that would otherwise
reach the public demo. Fix it at the source: brand strings come from
`app/branding.py` through the template context, never hardcoded in a template,
email, or admin label.

## Finish the check by looking

Numbers do not catch layout damage. After the crawl passes, screenshot whatever
you changed, using the `screenshot` skill, and actually look at it.

## When the database is empty

The crawl needs a course and a registration to fill in `?id=` parameters. If
the dev database is fresh, seed it first:

```bash
FLASK_APP=wsgi .venv/bin/flask seed-events --reset
```
