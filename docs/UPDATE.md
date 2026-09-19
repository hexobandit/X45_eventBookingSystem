# Admin UX changes — handoff (2026-09-19)

Scope: Flask-Admin based admin of the ANTERIOR site (X41_anterior). Four changes,
all uncommitted on branch `1st` at the time of writing. Test suite: 131 passing
(`.venv/bin/python -m pytest -q`).

Goal of the session: one consistent vocabulary for "what can I do with a course",
own icon graphics instead of Font Awesome glyphs, a printable welcome-desk sheet,
and visible loading states while the server works.

---

## 1. Course action vocabulary (icons + labels)

Used identically everywhere a course is shown. Names are the object, not the verb.

| Icon (class)  | Label              | Goes to                                   | Endpoint                          |
|---------------|--------------------|-------------------------------------------|-----------------------------------|
| `ra-people`   | Registrations      | course detail page (who signed up)        | `admin_events.details_view?id=`   |
| `ra-pencil`   | Edit page          | visual editor (what the website shows)    | `admin_events.visual_edit_view?id=` |
| `ra-money`    | Payments & emails  | former "Manage" page (bank/QR, emails, waitlist, add participant) | `admin_events.manage_view?id=` |
| `ra-trash`    | Delete             | Flask-Admin delete (row form)             | `.delete_view`                    |
| `ra-external` | View on website    | public course page, new tab               | `main.course_detail`              |

Removed: the "Manage" column and button in the Courses list, the "Manage" button on
the dashboard course minis, the "Manage course / Edit / Edit course" text buttons on
the course pages. The `manage_view` route and page still exist, only the naming
changed ("Payments & emails: <title>", back link "Back to registrations").

### Shared macro

`app/templates/admin/_course_actions.html`

```jinja
{% from 'admin/_course_actions.html' import course_actions %}
{{ course_actions(event) }}                                   {# icon-only, tooltips #}
{{ course_actions(event, current='registrations', labels=True, website=True) }}
```

- `current` = which page we are on; rendered as a dark pill (`.ra-current`,
  `aria-current="page"`, pointer-events none).
- `labels=True` = icon + text (`.ra-btn-label`), used in page headers.
- Icon-only buttons carry `data-tip="<label>"` and `aria-label`.

Where it is used: `admin/index.html` (dashboard minis, icon-only),
`admin/event_detail.html` (header, current=registrations),
`admin/event_manage.html` (header, current=payments),
`admin/visual_edit.html` (header, current=edit; for a new course a hidden
placeholder group `#courseActions` with `__ID__` in `data-url-*` attributes is
filled and shown by `visual-edit.js` `updateFullPreview()` after the first save).

### Flask-Admin list rows

`app/templates/admin/model/row_actions.html` overrides Flask-Admin's
`bootstrap4/admin/model/row_actions.html` (same macro names and signatures, so any
`ModelView` picks it up). Markup per action:

```html
<a class="icon ra-btn" href="..." data-tip="Registrations" aria-label="Registrations">
  <span class="ra-icon ra-people"></span>
</a>
```

Delete stays a `<form class="icon">` with a `<button class="ra-btn ra-danger">` and
the original `onclick="return faHelpers.safeConfirm(...)"` fallback, because
`master.html` intercepts clicks on `form.icon button` to show the site confirm modal.

Extra macros for courses only: `registrations_row` (people icon to details) and
`payments_row` (money icon to manage). `EventModelView.get_list_row_actions()`
(`app/admin/__init__.py`) returns, in order: registrations, edit, payments, delete
(+ `column_extra_row_actions`). Other views (Registrations list etc.) keep the
default view / edit / delete order and now render eye / pencil / trash in the same
button style.

### CSS (all in `app/static/css/admin/_components.css`)

- `.ra-group` inline-flex container, `gap: 6px`. `.ra-group[hidden]{display:none}`.
- `.ra-btn` 34px tall pill, `border-radius: 17px`, 1px border
  `--admin-border-medium`, white bg, `--admin-text-secondary`. Hover/focus-visible:
  `--accent-blue-bg` background, `--admin-accent` border + color, `translateY(-1px)`.
  `.ra-danger` hover = red (`--status-cancelled-bg` / `--accent-red`).
  `.ra-btn-label` adds `padding: 0 14px 0 10px`, `white-space: nowrap`.
- `.ra-icon` 18×18 block, `background-color: currentColor`, and
  `-webkit-mask / mask: var(--ra-svg) center / contain no-repeat`. Each icon class
  only sets `--ra-svg` to a `url("data:image/svg+xml,...")` stroke SVG
  (24×24 viewBox, `stroke-width 1.8`, round caps/joins, `stroke='%23000'` — the
  stroke colour is irrelevant since it is a mask). Icons available: `ra-eye`,
  `ra-people`, `ra-pencil`, `ra-money`, `ra-trash`, `ra-external`, `ra-print`,
  `ra-check`, `ra-minus`. No icon font involved; Font Awesome is still loaded by
  Flask-Admin but unused for these.
- Tooltip: `.ra-tip` fixed-position bubble (dark `--admin-primary`, white text,
  small caret), appended once to `<body>` by a script in `master.html`. Shown on
  `mouseover` / `focusin` of any `[data-tip]`, hidden on `mouseout` / `focusout` /
  scroll. Fixed positioning was chosen because the list table card has
  `overflow: hidden`, which would clip an in-flow tooltip.
- Cache busting: the `@import` lines in `app/static/css/admin.css` carry
  `?v=20260919a` for every partial touched (nginx caches `/static/` for 30 days).

### Active / Featured toggle in the Courses list

`EventModelView._flag_toggle()` now renders
`<button class="ra-btn flag-toggle is-on" data-field="is_active" data-value="1"
data-tip="Visible on website — click to hide"><span class="ra-icon ra-check"></span></button>`
(off state: no `is-on`, `ra-minus`, tip "Hidden — click to publish"; `is_featured`
has its own tip texts). Styling lives in the `<style>` block of
`admin/list_with_heading.html`: on = green (`--accent-green`, `--accent-green-bg`),
off = muted; hover previews the opposite state (red to hide, green to publish).
The click handler in the same template still confirms via `showConfirm`, POSTs JSON
to `admin_events.toggle_flag`, and on success swaps icon class, `is-on`, `data-tip`
and `aria-label`.

---

## 2. Attendee list (printable welcome-desk sheet)

Purpose: the person at the door knows who to expect, whether they paid, from which
organisation, and has phone numbers to call late arrivals.

- Entry point: button "Attendee list" (`ra-print` icon) in the header of the
  "Registrations" card on `admin/event_detail.html`.
- Route: `EventModelView.attendee_sheet()` at
  `/admin/admin_events/attendee-sheet/?id=<event_id>` (login required through
  `SecureAdminMixin` like every other event view).
- Data: registrations of the event ordered by `last_name, first_name`.
  `expected` = status CONFIRMED or PENDING, `waitlist` = WAITLIST, cancelled are
  excluded entirely. `paid_count` = expected rows with `payment_status == PAID`.
- Template: `app/templates/admin/event_attendee_sheet.html`, standalone HTML (does
  not extend `master.html`, no sidebar). Loads `css/_fonts.css` (Inter) and
  `css/admin.css` (for `.ra-btn` / `.ra-icon`), everything else is inline CSS.
  Layout is a 210 mm "paper" sheet:
  - Hero block, 62 mm high: `event.image_url` as cover image with
    `object-position: center <image_position_y>%`, dark gradient overlay,
    "ANTERIOR" wordmark (brand blue `#29ABE2`, letter-spaced), "Attendee list"
    label, eyebrow "<type> · <formatted_date> – <end_date>", `<h1>` title,
    location · venue. Solid `#14181C` block when there is no image.
  - Meta strip (4 cells): date & time (time shown only if not 00:00), Expected
    N of capacity, Paid N of expected, Waiting list N.
  - "Expected attendees" table: `#`, tick box (`.as-box`, empty square for a pen),
    Name (surname first, plus "Not confirmed" pill for PENDING, participant `notes`
    and `admin_note` as small sub-lines), Organization (+ `billing_name` if it
    differs), Phone (nowrap), Email (10.5 px, break-all), Paid (Paid / Unpaid /
    Refunded pill + "Card" / "Bank" from `payment_method`).
  - "Waiting list" table (`#`, name, organization, phone, email) if any.
  - Footer: "Printed <dd.mm.yyyy HH:MM> · cancelled registrations not listed" and
    a personal-data disposal reminder.
- Print: `@page { size: A4 portrait; margin: 0 }`, `print-color-adjust: exact`,
  toolbar hidden, `thead` repeats (`display: table-header-group`), rows
  `break-inside: avoid`. Verified with headless Chrome `--print-to-pdf`.
- Toolbar (screen only, sticky): Back to registrations, Download PNG, Save as PDF,
  Print.
  - Print → `window.print()`.
  - Save as PDF → also `window.print()`, with a hint "In the print dialog choose
    'Save as PDF'". No server-side PDF; the browser's print-to-PDF keeps the hero
    image and layout 1:1 (fpdf2 exists in the project but would need a second,
    text-only layout).
  - Download PNG → `html2canvas(#sheet, {scale: 2, useCORS: true})`, then an
    `<a download>` with the data URL, filename `<slug>-attendees.png`.
    html2canvas 1.4.1 is vendored at `app/static/js/vendor/html2canvas.min.js`
    (no CDN dependency).
- Tests: `tests/test_admin_attendee_sheet.py` (login required; expected + waitlist
  listed, cancelled not; surname ordering; counts in the meta strip; detail page
  links to the sheet).

---

## 3. Busy / loading state for buttons

Purpose: after confirming a delete or sending an email the user sees the button
spinning until the server responds, and cannot double-submit.

- Helper: `app/templates/admin/_busy_buttons.html`, included by both
  `admin/master.html` and `admin/panel_base.html` (the chrome-less base used
  inside the slide-in iframe panel). Exposes `window.setLoading(btn, on)`.
  - `setLoading(btn)` adds `.is-loading` + `aria-busy="true"` and disables the
    button on the next tick (`setTimeout 0`) so the button's `name`/`value` still
    end up in the form data of an in-flight submit.
  - `setLoading(btn, false)` reverts (remembers whether it was disabled before).
  - A document-level `submit` listener (bubbling phase) marks `e.submitter` (or the
    first submit button) of every POST form unless the event was
    `preventDefault`ed. Note: `form.submit()` called from JS fires no submit
    event, so modals mark their own buttons (below).
  - `pageshow` listener clears all `.is-loading` / `.is-busy` (back button,
    bfcache).
- Confirm modal (`admin/_confirm_modal.html`, `window.showConfirm(msg, cb)`):
  on OK the dialog now stays open, the OK button spins, Cancel and × are greyed
  (`.manage-modal.is-busy`). If `cb()` returns a promise the modal closes when it
  settles (used by the Active/Featured toggle, which now `return`s its `fetch`
  chain); if it returns nothing the callback is assumed to navigate (form submit),
  and the spinner stays until the new page loads.
  Covers: row delete, bulk "With selected" actions, every
  `confirmAction(this, msg)` button (send confirmation / payment / reminder emails
  on the manage page and in the registration edit panel).
- Delete-registration modal (`admin/_delete_registration_modal.html`): same
  pattern, its own OK button spins and the modal stays open while the form
  submits.
- CSS (`_components.css`): `.is-loading` = `pointer-events: none`,
  `cursor: progress`, `opacity: .85`, and a `::before` 12 px ring spinner drawn
  with `border: 2px solid currentColor; border-right-color: transparent` and
  `@keyframes ra-spin`. On `.ra-btn` the icon is hidden while spinning.
- Not covered on purpose: the visual editor "Save" (has its own status text via
  fetch) and the QR "Generate" buttons.

---

## 4. Smaller things

- Course list row actions render inside `.list-buttons-column`; only layout rules
  remain in `_flask-admin.css` (`a.icon` / `form.icon` inline-flex, 4 px gap).
- `_dashboard.css`: `.event-detail-title` now wraps (`flex-wrap`) and the action
  group inside it can wrap; `.event-mini > .ra-group` replaces the old
  `.event-mini-manage` button. `_responsive.css` updated accordingly.
- `_visual-edit.css`: `.ve-view-btn` removed; `.ve-header-right .ra-group` gets a
  left border separator; hidden under 768 px.
- Visual editor note about payment details now says they live on the
  "Payments & emails" page (the money icon next to the course).

## Files touched

Modified: `app/admin/__init__.py`, `app/static/css/admin.css`,
`app/static/css/admin/_components.css`, `_dashboard.css`, `_flask-admin.css`,
`_responsive.css`, `_visual-edit.css`, `app/static/js/visual-edit.js`,
`app/templates/admin/_confirm_modal.html`, `_delete_registration_modal.html`,
`event_detail.html`, `event_manage.html`, `index.html`, `list_with_heading.html`,
`master.html`, `panel_base.html`, `visual_edit.html`.

New: `app/templates/admin/_busy_buttons.html`, `_course_actions.html`,
`event_attendee_sheet.html`, `model/row_actions.html`,
`app/static/js/vendor/html2canvas.min.js`, `tests/test_admin_attendee_sheet.py`.

## How to port to the demo project

1. Copy `_components.css` blocks: "Course action icons", "Busy state", tooltip.
2. Copy the four new templates (`_course_actions.html`, `model/row_actions.html`,
   `_busy_buttons.html`, `event_attendee_sheet.html`) and the vendored html2canvas.
3. In the events `ModelView`: drop the manage column, add `get_list_row_actions()`,
   update `_flag_toggle()`, add the `attendee_sheet` route (needs
   `RegistrationStatus`, `PaymentStatus`, `datetime`).
4. Include `_busy_buttons.html` and the tooltip script in the base template; apply
   the confirm-modal changes (keep open + spinner, promise-aware close).
5. Replace old "Manage" / "Edit" links in dashboard, detail, manage and editor
   headers with `course_actions(...)` calls; bump the CSS cache query strings.
