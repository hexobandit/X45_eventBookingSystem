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
