/*
 * Touch helpers for the kiosk display, included on every page.
 * - Immediate visual feedback on pointerdown (the click may arrive much later)
 * - Loading bar while the next page is being fetched
 * - No long-press context menu
 */
(function () {
    const TAPPABLE = 'button, a, .tappable, [onclick]';

    document.addEventListener('pointerdown', (e) => {
        const el = e.target.closest(TAPPABLE);
        if (!el || el.disabled || el.closest('.leaflet-container')) return;
        el.classList.add('pressed');
        const release = () => setTimeout(() => el.classList.remove('pressed'), 120);
        el.addEventListener('pointerup', release, { once: true });
        el.addEventListener('pointercancel', release, { once: true });
        el.addEventListener('pointerleave', release, { once: true });
    }, { passive: true });

    document.addEventListener('contextmenu', (e) => {
        if (!e.target.closest('input, textarea')) e.preventDefault();
    });

    const bar = document.createElement('div');
    bar.id = 'nav-loading';

    function attach() { document.body.appendChild(bar); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach);
    else attach();

    // Navigation started (button → location.href, reload, link)
    window.addEventListener('beforeunload', () => bar.classList.add('active'));
    // Back from the page cache: reset
    window.addEventListener('pageshow', () => bar.classList.remove('active'));
})();
