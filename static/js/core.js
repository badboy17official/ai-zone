window.ArenaUI = (() => {
    const clockEl = () => document.getElementById('clock');

    function updateClock() {
        const el = clockEl();
        if (!el) return;
        const now = new Date();
        el.textContent = now.toLocaleTimeString('en-GB', { hour12: false }) + ' UTC';
    }

    function debounce(fn, delay = 280) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), delay);
        };
    }

    function escapeHtml(text = '') {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function truncate(text = '', max = 1200) {
        return text.length > max ? text.slice(0, max) + '\n…[truncated]' : text;
    }

    function copyText(text, triggerEl) {
        return navigator.clipboard.writeText(text || '').then(() => {
            if (!triggerEl) return;
            const original = triggerEl.innerHTML;
            triggerEl.innerHTML = '<i class="bi bi-clipboard-check"></i> Copied';
            setTimeout(() => { triggerEl.innerHTML = original; }, 1500);
        });
    }

    function dismissFlashes(ms = 4500) {
        setTimeout(() => {
            document.querySelectorAll('.flash-container .alert').forEach(el => {
                const inst = bootstrap.Alert.getOrCreateInstance(el);
                inst.close();
            });
        }, ms);
    }

    function initSidebarToggle() {
        const btn = document.getElementById('sidebarToggle');
        if (!btn) return;
        btn.addEventListener('click', () => {
            document.body.classList.toggle('sidebar-open');
        });
    }

    function initTeamDots() {
        document.querySelectorAll('.team-dot[data-color]').forEach(dot => {
            const color = (dot.dataset.color || '').trim();
            if (/^#[0-9a-fA-F]{6}$/.test(color)) {
                dot.style.background = color;
            }
        });
    }

    function initBars() {
        document.querySelectorAll('.score-bar-fill[data-width]').forEach(bar => {
            const width = Math.max(0, Math.min(100, Number(bar.dataset.width || 0)));
            bar.style.width = `${width}%`;

            if (bar.dataset.health === '1') {
                bar.style.background = width > 70 ? '#22c55e' : width > 40 ? '#f59e0b' : '#ef4444';
            }
        });

        document.querySelectorAll('.progress-bar[data-width]').forEach(bar => {
            const width = Math.max(0, Math.min(100, Number(bar.dataset.width || 0)));
            bar.style.width = `${width}%`;
        });
    }

    function startPolling(fn, ms = 8000) {
        fn();
        return setInterval(fn, ms);
    }

    return {
        updateClock,
        debounce,
        escapeHtml,
        truncate,
        copyText,
        dismissFlashes,
        initSidebarToggle,
        initTeamDots,
        initBars,
        startPolling,
    };
})();

ArenaUI.updateClock();
setInterval(ArenaUI.updateClock, 1000);
ArenaUI.dismissFlashes();
ArenaUI.initSidebarToggle();
    ArenaUI.initTeamDots();
    ArenaUI.initBars();
