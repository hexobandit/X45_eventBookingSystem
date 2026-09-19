/**
 * Main JavaScript
 * Course booking engine — public site scripts
 */

/* ==========================================================================
   Mobile Menu
   ========================================================================== */

function toggleMenu() {
    const overlay = document.getElementById('menuOverlay');
    const bg = document.getElementById('overlayBg');
    const trigger = document.querySelector('.menu-toggle');

    if (overlay && bg) {
        const open = overlay.classList.toggle('is-open');
        bg.classList.toggle('is-open', open);
        if (trigger) {
            trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
        // Prevent body scroll when menu is open
        document.body.style.overflow = open ? 'hidden' : '';
    }
}

// Close menu on escape key
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        const overlay = document.getElementById('menuOverlay');
        if (overlay && overlay.classList.contains('is-open')) {
            toggleMenu();
        }
    }
});

/* ==========================================================================
   Smooth Scroll
   ========================================================================== */

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

/* ==========================================================================
   Header hairline on scroll
   ========================================================================== */

const header = document.getElementById('siteHeader');

window.addEventListener('scroll', () => {
    if (header) {
        header.classList.toggle('is-scrolled', window.pageYOffset > 50);
    }
}, { passive: true });

/* ==========================================================================
   Scroll reveal
   ========================================================================== */

(function () {
    const targets = document.querySelectorAll('.reveal');
    if (!targets.length) return;

    if (!('IntersectionObserver' in window) ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        targets.forEach(el => el.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    targets.forEach(el => observer.observe(el));
})();

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

/* ==========================================================================
   Hero: the cursor is the key light
   Writes --lx / --ly (0..1) on the hero as the pointer moves; the CSS does
   the lighting. Modifier chips set data-mod. Touch devices get the CSS
   orbit animation instead; reduced motion keeps the default lamp.
   ========================================================================== */

(function () {
    const hero = document.getElementById('hero');
    if (!hero) return;

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const canHover = window.matchMedia('(hover: hover)').matches;

    const clamp = (v) => Math.min(1, Math.max(0, v));
    const setLamp = (x, y) => {
        hero.style.setProperty('--lx', clamp(x).toFixed(3));
        hero.style.setProperty('--ly', clamp(y).toFixed(3));
    };

    if (reduce) {
        // static lamp, nothing moves
    } else if (canHover) {
        let x = 0, y = 0, raf = null;
        hero.addEventListener('pointermove', (e) => {
            const r = hero.getBoundingClientRect();
            x = (e.clientX - r.left) / r.width;
            y = (e.clientY - r.top) / r.height;
            if (raf) return;
            raf = requestAnimationFrame(() => { setLamp(x, y); raf = null; });
        });
    } else {
        // Touch: scrolling moves the lamp down and across the stage, a slow
        // drift keeps it alive while the page is still. A finger on the hero
        // overrides both for a moment.
        let touchUntil = 0;
        hero.addEventListener('pointermove', (e) => {
            if (e.pointerType !== 'touch') return;
            const r = hero.getBoundingClientRect();
            setLamp((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
            touchUntil = performance.now() + 1500;
        }, { passive: true });

        const tick = (now) => {
            if (now > touchUntil) {
                const h = hero.offsetHeight || 1;
                const progress = clamp(window.scrollY / h);            // 0 at top, 1 when hero scrolled away
                const drift = Math.sin(now / 2600) * 0.12;
                setLamp(0.25 + progress * 0.55 + drift, 0.18 + progress * 0.6);
            }
            if (window.scrollY < hero.offsetHeight * 1.2) requestAnimationFrame(tick);
            else setTimeout(() => requestAnimationFrame(tick), 400);   // idle cheaply once out of view
        };
        requestAnimationFrame(tick);
    }

    hero.querySelectorAll('.mod').forEach((btn) => {
        btn.addEventListener('click', () => {
            hero.dataset.mod = btn.dataset.mod;
            hero.querySelectorAll('.mod').forEach((b) => b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'));
        });
    });
})();
