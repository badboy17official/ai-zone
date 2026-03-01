(() => {
    const statTeams = document.getElementById('stat-total-teams');
    if (!statTeams) return;

    const feedContainer = document.getElementById('live-feed');
    const activeTeamsEl = document.getElementById('activeTeamsCounter');
    const hallucRateEl = document.getElementById('hallucinationRate');
    const queueEl = document.getElementById('serverQueueDepth');

    let submissionTrendChart;
    let validationPieChart;

    function statusBadge(status) {
        if (status === 'valid') return '<span class="badge badge-valid">VALID</span>';
        if (status === 'invalid') return '<span class="badge badge-invalid">INVALID</span>';
        return '<span class="badge badge-error">ERROR</span>';
    }

    function renderFeed(items = []) {
        if (!feedContainer) return;
        if (!items.length) {
            feedContainer.innerHTML = '<div class="text-muted small">No recent activity.</div>';
            return;
        }

        feedContainer.innerHTML = items.map(item => {
            const cls = item.suspicious ? 'suspicious' : item.status;
            const t = new Date(item.created_at).toLocaleTimeString('en-GB');
            return `
                <article class="feed-item ${cls}">
                    <div>
                        <div class="feed-title">${ArenaUI.escapeHtml(item.team_code)} · ${ArenaUI.escapeHtml(item.mission)}</div>
                        <div class="feed-meta">${t} · Prompt ${item.prompt_length} chars · Attempt #${item.attempt}</div>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        ${statusBadge(item.status)}
                        ${item.suspicious ? '<span class="badge badge-flagged">Suspicious</span>' : ''}
                    </div>
                </article>
            `;
        }).join('');
    }

    function upsertCharts(data) {
        const trendCtx = document.getElementById('submissionTrendChart');
        const pieCtx = document.getElementById('validationStatusChart');
        if (!trendCtx || !pieCtx || !window.Chart) return;

        const labels = data.hourly.map(h => h.hour);
        const totals = data.hourly.map(h => h.total);
        const invalid = data.hourly.map(h => h.invalid);

        if (!submissionTrendChart) {
            submissionTrendChart = new Chart(trendCtx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        { label: 'Total', data: totals, borderColor: '#6d7dff', backgroundColor: 'rgba(109,125,255,.2)', tension: 0.32, fill: true },
                        { label: 'Failures', data: invalid, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,.15)', tension: 0.32, fill: true }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#cbd5e1' } } }, scales: { x: { ticks: { color: '#94a3b8' } }, y: { ticks: { color: '#94a3b8' }, beginAtZero: true } } }
            });
        } else {
            submissionTrendChart.data.labels = labels;
            submissionTrendChart.data.datasets[0].data = totals;
            submissionTrendChart.data.datasets[1].data = invalid;
            submissionTrendChart.update('none');
        }

        const pieData = [data.status_counts.valid, data.status_counts.invalid, data.status_counts.error];
        if (!validationPieChart) {
            validationPieChart = new Chart(pieCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Valid', 'Invalid', 'Error'],
                    datasets: [{ data: pieData, backgroundColor: ['#22c55e', '#ef4444', '#f59e0b'], borderColor: '#0f172a' }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#cbd5e1' } } } }
            });
        } else {
            validationPieChart.data.datasets[0].data = pieData;
            validationPieChart.update('none');
        }

        if (activeTeamsEl) activeTeamsEl.textContent = data.active_teams_15m;
        if (hallucRateEl) hallucRateEl.textContent = `${data.hallucination_rate}%`;
        if (queueEl) queueEl.textContent = data.server_load.queue_depth;
    }

    function refreshStats() {
        fetch('/admin/api/stats').then(r => r.json()).then(data => {
            document.getElementById('stat-total-teams').textContent = data.teams.total;
            document.getElementById('stat-total-subs').textContent = data.submissions.total;
            document.getElementById('stat-recent').textContent = data.submissions.recent_hour;
            document.getElementById('stat-security').textContent = data.security.open_events;
            const rate = data.submissions.total > 0 ? ((data.submissions.valid / data.submissions.total) * 100).toFixed(1) : '0.0';
            document.getElementById('stat-validation-rate').textContent = `${rate}%`;
        }).catch(() => null);
    }

    function refreshFeed() {
        fetch('/admin/api/activity_feed?limit=15').then(r => r.json()).then(data => renderFeed(data.feed || [])).catch(() => null);
    }

    function refreshAnalytics() {
        fetch('/admin/api/analytics').then(r => r.json()).then(upsertCharts).catch(() => null);
    }

    window.refreshStats = refreshStats;
    ArenaUI.startPolling(refreshStats, 9000);
    ArenaUI.startPolling(refreshFeed, 5000);
    ArenaUI.startPolling(refreshAnalytics, 10000);
})();
