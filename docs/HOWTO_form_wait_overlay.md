# How-to: Form wait overlay (prevent double email submissions)

Purpose: when a contact/order form POST is slow (server blocks while handing mail to SMTP), users click Submit again and the server sends duplicate emails. This fix shows a full-screen "Sending…" overlay on submit and blocks any repeat submission until the server responds with a redirect.

Origin: X41_anterior, commit `46c5003`. This document is self-contained — everything needed to port the fix to another site is below.

## How it works

1. Any `<form>` you tag with a `data-wait="Your message"` attribute opts into the behavior.
2. On first submit, JavaScript marks the form as pending (`form.dataset.waitPending`), shows a fixed full-screen overlay (spinner ring + paper-plane icon + animated "Sending…" text), and disables the submit buttons.
3. Any further submit events while pending are cancelled with `e.preventDefault()` — this is the actual duplicate-email guard.
4. The POST is a normal (non-AJAX) form submission, so the overlay stays up exactly as long as the server takes and disappears naturally when the redirect/response loads the next page. No timers, no polling.
5. A `pageshow` handler resets everything if the browser restores the page from the back/forward cache (otherwise the form would come back frozen with the overlay stuck on).

Details that matter:

- Submit buttons are disabled inside `setTimeout(..., 0)`, not synchronously. Disabling a submit button before the browser serializes the form would drop that button's name/value from the POST body.
- The overlay has `role="status"` and `aria-live="polite"` for screen readers.
- `prefers-reduced-motion` disables all animations.
- This is a client-side guard only. Keep (or add) a server-side one-time form token as a second layer for users without JavaScript or double-POST edge cases.

## Step 1 — JavaScript

Append to the site's main JS file (loaded on pages that have forms):

```js
/* ==========================================================================
   Form wait overlay
   Forms marked data-wait show a full-screen "sending" overlay on submit.
   The POST blocks until the server is done (emails handed to SMTP), so the
   overlay lives exactly as long as the send and vanishes with the redirect.
   ========================================================================== */

(function () {
    const forms = document.querySelectorAll('form[data-wait]');
    if (!forms.length) return;

    let overlay = null;

    function buildOverlay() {
        overlay = document.createElement('div');
        overlay.className = 'wait-overlay';
        overlay.setAttribute('role', 'status');
        overlay.setAttribute('aria-live', 'polite');
        overlay.innerHTML =
            '<div class="wait-spinner">' +
                '<svg viewBox="0 0 108 108" aria-hidden="true">' +
                    '<circle class="wait-ring-track" cx="54" cy="54" r="51"/>' +
                    '<circle class="wait-ring-arc" cx="54" cy="54" r="51"/>' +
                '</svg>' +
                '<div class="wait-glyph">' +
                    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                        '<path d="M22 2 11 13"/>' +
                        '<path d="M22 2 15 22l-4-9-9-4z"/>' +
                    '</svg>' +
                '</div>' +
            '</div>' +
            '<div class="wait-text">' +
                '<span class="wait-msg"></span>' +
                '<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>' +
            '</div>';
        document.body.appendChild(overlay);
    }

    forms.forEach((form) => {
        form.addEventListener('submit', (e) => {
            if (form.dataset.waitPending) {
                e.preventDefault();
                return;
            }
            form.dataset.waitPending = '1';

            if (!overlay) buildOverlay();
            overlay.querySelector('.wait-msg').textContent = form.dataset.wait || 'Sending';
            requestAnimationFrame(() => overlay.classList.add('is-active'));

            // Disable after submission data is captured, not before
            setTimeout(() => {
                form.querySelectorAll('button[type="submit"]').forEach(b => { b.disabled = true; });
            }, 0);
        });
    });

    // Back/forward cache restores the page mid-overlay — reset so the form works again
    window.addEventListener('pageshow', (e) => {
        if (!e.persisted) return;
        if (overlay) overlay.classList.remove('is-active');
        forms.forEach((form) => {
            delete form.dataset.waitPending;
            form.querySelectorAll('button[type="submit"]').forEach(b => { b.disabled = false; });
        });
    });
})();
```

## Step 2 — CSS

Append to the site's component/global stylesheet. The original uses these design tokens — replace each with the target site's equivalent (or hard-code values):

| Token | Meaning in the original (dark B&W + blue theme) |
|---|---|
| `--accent` | brand accent color (`#29ABE2`) — spinner arc |
| `--border-color` | subtle border gray — spinner track ring |
| `--text-primary` / `--text-secondary` | main / muted text colors |
| `--sp-8` | spacing unit (~2rem gap between spinner and text) |
| `--fs-small` | small font size |
| `--tracking-eyebrow` | wide letter-spacing for uppercase labels |
| `--transition-base` | standard transition (~0.3s ease) |

Also note the overlay background `rgba(7, 8, 9, 0.88)` assumes a dark theme — for a light site use a light or dark scrim as fits, and the arc's `drop-shadow` color `rgba(41, 171, 226, 0.55)` is the accent color at 55% alpha — match it to the target accent.

```css
/* --- Wait overlay (form submit) --------------------------------------------- */

.wait-overlay {
    position: fixed;
    inset: 0;
    z-index: 2000;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--sp-8);
    background: rgba(7, 8, 9, 0.88);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--transition-base);
}

.wait-overlay.is-active {
    opacity: 1;
    pointer-events: auto;
}

.wait-spinner {
    position: relative;
    width: 108px;
    height: 108px;
}

.wait-spinner > svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
}

.wait-ring-track {
    fill: none;
    stroke: var(--border-color);
    stroke-width: 1.5;
}

.wait-ring-arc {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-dasharray: 90 231;   /* r=51 → circumference ≈ 321 */
    filter: drop-shadow(0 0 6px rgba(41, 171, 226, 0.55));
    transform-origin: 50% 50%;
    animation: wait-spin 1.4s linear infinite;
}

.wait-glyph {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: wait-bob 2.6s ease-in-out infinite;
}

.wait-glyph svg {
    width: 38px;
    height: 38px;
    fill: none;
    stroke: var(--text-primary);
    stroke-width: 1.2;
    stroke-linecap: round;
    stroke-linejoin: round;
}

.wait-text {
    display: flex;
    align-items: baseline;
    font-size: var(--fs-small);
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
    color: var(--text-secondary);
    padding-left: var(--tracking-eyebrow);
}

.wait-text .dot {
    animation: wait-dot 1.2s infinite;
}

.wait-text .dot:nth-child(3) { animation-delay: 0.2s; }
.wait-text .dot:nth-child(4) { animation-delay: 0.4s; }

@keyframes wait-spin {
    to { transform: rotate(360deg); }
}

@keyframes wait-bob {
    0%, 100% { transform: translate(0, 2px); }
    50%      { transform: translate(3px, -3px); }
}

@keyframes wait-dot {
    0%, 60%, 100% { opacity: 0.25; }
    30%           { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
    .wait-ring-arc,
    .wait-glyph,
    .wait-text .dot {
        animation: none;
    }
}
```

## Step 3 — Tag the forms

Add `data-wait` to every form that sends email (or is otherwise slow). The attribute value is the overlay message:

```html
<form class="contact-form" action="..." method="post" novalidate data-wait="Sending your message">
```

In the original site this was applied to the contact form, the book order form, and the course signup form. Forms without the attribute are untouched.

## Step 4 — Verify

1. Open a tagged form, submit it: overlay must appear instantly, buttons disable, page redirects normally when the server finishes.
2. While the overlay is up, hammer Enter / click Submit repeatedly: exactly one email must arrive.
3. After the redirect, press the browser Back button: the form page must come back usable (no stuck overlay, buttons enabled).
4. Check the POST body still contains the submit button's name/value if the server relies on it.
5. Toggle "reduce motion" in OS settings: overlay still shows, animations off.
