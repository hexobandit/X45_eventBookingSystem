/* romansolutions.cz — the only script on the page.
   1. Play the hero ledger animation once, after the font has loaded.
   2. Point demo links at the local engine when the page itself runs locally. */
(function () {
    var ledger = document.querySelector('.ledger');
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function play() {
        if (!ledger) return;
        if (reduce) { ledger.classList.add('is-paid'); return; }
        ledger.classList.add('play');
        // Flip the pill to the stamp at the moment the statement line lands.
        setTimeout(function () { ledger.classList.add('is-paid'); }, 2350);
    }
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(function () { setTimeout(play, 400); });
    } else {
        setTimeout(play, 600);
    }

    var host = location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
        document.querySelectorAll('[data-demo]').forEach(function (a) {
            a.href = 'http://127.0.0.1:5000/';
        });
    }
})();
