---
name: port-from-client
description: Bring a feature that was built on a client site (X41_anterior) into this product repo, de-branded. Use when asked to port, copy, or merge admin or site work from the client project, or when handed a handoff document describing changes made there.
---

# Port a feature from the client site

This repo was moved out of the client repo, so the two have diverged in both
directions. A plain file copy silently reverts product work. The last port
brought back an obsolete payment model and broke saving payment details, which
only a failing test caught.

## 1. Find the point where they diverged

```bash
cd ../X41_anterior && git log --oneline -10 && git diff --stat <base>..<head>
```

The useful base is the commit before the feature work, not the newest commit.
Compare a file that neither side touched to sanity-check the base.

## 2. Merge each file, never copy it

For every file the feature touched, three-way merge rather than overwrite:

```bash
git -C ../X41_anterior show <base>:<path> > /tmp/base
git merge-file -p ours /tmp/base theirs > merged
```

Where `ours` is this repo's file and `theirs` is the client's. Conflicts are
information: they mark where the product has moved on. Resolve them in favour
of the product unless the feature genuinely needs the client's version.

Files that exist only in the feature can be copied outright.

## 3. Look for divergent subsystems

A merge can be clean per hunk and still wrong as a whole. Before running
anything, grep the merged files for identifiers the product no longer has:

```bash
.venv/bin/python -c "import app.admin" && .venv/bin/python -m pytest -q
```

Known divergence to watch: payments. The client site had one transfer method
per course. This product has two independent methods,
`has_domestic_payment` and `has_sepa_payment`, with no `transfer_kind`.

## 4. De-brand what you brought in

Client names, domains, emails and the client accent colour must not survive.
Brand strings come from `app/branding.py` through the template context. Then:

```bash
.venv/bin/python scripts/qa_demo.py --demo
```

## 5. Finish

Run the full suite, screenshot the pages you touched with the `screenshot`
skill, and record anything a future reader would need in `CLAUDE.md`. Leave the
client repo untouched: it is a separate business and is never edited from here.
