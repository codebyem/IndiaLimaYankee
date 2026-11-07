/*
 * Night mode + screen-off overlay, included on every page.
 * The server decides the state (/api/display); this script only renders it.
 * With backlight control the panel itself dims; otherwise a black overlay does.
 */
(function () {
    const POLL_MS = 30000;
    let dim, offScreen, lastState = null;

    const css = `
        #night-dim {
            position: fixed; inset: 0; background: #000; opacity: 0;
            pointer-events: none; z-index: 10000; transition: opacity 2s ease;
        }
        #screen-off {
            position: fixed; inset: 0; background: #000; z-index: 10001;
            display: none; align-items: center; justify-content: center;
        }
        #screen-off.active { display: flex; }
        #wake-btn {
            width: 140px; height: 140px; border-radius: 50%;
            background: #000; border: 2px solid rgba(0, 255, 255, 0.35);
            color: rgba(0, 255, 255, 0.6);
            box-shadow: 0 0 18px rgba(0, 255, 255, 0.15);
            font-family: 'Orbitron', monospace; font-size: 0.7rem; font-weight: 700;
            letter-spacing: 1px; cursor: pointer;
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
            touch-action: manipulation; -webkit-tap-highlight-color: transparent;
            animation: wakePulse 4s ease-in-out infinite;
        }
        #wake-btn:active { transform: scale(0.95); }
        @keyframes wakePulse {
            0%, 100% { box-shadow: 0 0 10px rgba(0, 255, 255, 0.1); }
            50%      { box-shadow: 0 0 24px rgba(0, 255, 255, 0.3); }
        }
    `;

    function build() {
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);

        dim = document.createElement('div');
        dim.id = 'night-dim';

        offScreen = document.createElement('div');
        offScreen.id = 'screen-off';
        offScreen.innerHTML = `
            <button id="wake-btn" type="button" aria-label="Bildschirm einschalten">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" aria-hidden="true">
                    <path d="M18.4 6.6a9 9 0 1 1-12.8 0"/><path d="M12 2v10"/>
                </svg>
                EINSCHALTEN
            </button>`;

        document.body.append(dim, offScreen);
        document.getElementById('wake-btn').addEventListener('click', () => post('/api/display/on'));
    }

    function render(s) {
        lastState = s;
        const night = s.night && !s.screen_off;

        // Night forces the dark theme (without touching the saved preference)
        document.body.classList.toggle('night-mode', night);
        if (night) {
            document.body.classList.remove('light-mode');
        } else {
            let light = false;
            try { light = localStorage.getItem('theme') === 'light'; } catch (e) {}
            document.body.classList.toggle('light-mode', light);
        }

        // Backlight dims the panel itself — only a soft overlay to calm the neon glow.
        // Without it, the overlay does all the dimming (max. 85 % black).
        const brightness = s.settings.night_brightness / 100;
        dim.style.opacity = night ? (s.backlight ? 0.15 : (1 - brightness) * 0.85) : 0;

        offScreen.classList.toggle('active', s.screen_off);
        document.dispatchEvent(new CustomEvent('displaystate', { detail: s }));
    }

    async function post(url, body) {
        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body ? JSON.stringify(body) : undefined,
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || resp.status);
            render(data);
            return data;
        } catch (e) {
            console.error('[display]', e);
            throw e;
        }
    }

    async function refresh() {
        try {
            const resp = await fetch('/api/display');
            if (resp.ok) render(await resp.json());
        } catch (e) {
            console.warn('[display] refresh failed', e);
        }
    }

    window.DisplayCtl = {
        refresh,
        off: () => post('/api/display/off'),
        on: () => post('/api/display/on'),
        save: (settings) => post('/api/display', settings),
        get state() { return lastState; },
    };

    function init() {
        build();
        refresh();
        setInterval(refresh, POLL_MS);
        // Coming back from the screen-off page after a while: update immediately
        document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
