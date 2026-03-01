(() => {
    const table = document.getElementById('leaderboardBody');
    if (!table) return;

    const sortSelect = document.getElementById('sortBy');

    function rowTemplate(team, index) {
        const total = Number(team.total_score || 0) + Number(team.bonus_points || 0);
        const health = Number(team.health_score || 0);
        const rankBadge = index === 0 ? '<span class="badge badge-rank-1">🥇 1</span>' :
            index === 1 ? '<span class="badge badge-rank-2">🥈 2</span>' :
            index === 2 ? '<span class="badge badge-rank-3">🥉 3</span>' : `<span>#${team.rank || index + 1}</span>`;
        return `
            <tr class="rank-animate" data-team="${team.team_code}">
                <td class="text-center">${rankBadge}</td>
                <td>
                    <span style="display:inline-block;width:10px;height:10px;border-radius:999px;background:${team.avatar_color};margin-right:8px;"></span>
                    <strong>${ArenaUI.escapeHtml(team.name)}</strong>
                    <span class="text-muted ms-1">${ArenaUI.escapeHtml(team.team_code)}</span>
                </td>
                <td><strong style="font-family:'JetBrains Mono',monospace;">${total.toFixed(1)}</strong></td>
                <td>${Number(team.total_score || 0).toFixed(1)}</td>
                <td class="text-success">+${Number(team.bonus_points || 0).toFixed(0)}</td>
                <td>${team.missions_completed || 0}</td>
                <td>${team.total_submissions || 0}</td>
                <td>${Number(team.validation_rate || 0).toFixed(1)}%</td>
                <td>
                    <div class="score-bar" style="width:70px;"><div class="score-bar-fill" style="width:${health}%;background:${health > 70 ? '#22c55e' : health > 40 ? '#f59e0b' : '#ef4444'};"></div></div>
                </td>
                <td><button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#breakdown-${team.team_code}">Breakdown</button></td>
            </tr>
            <tr class="collapse" id="breakdown-${team.team_code}">
                <td colspan="10">
                    <div class="py-2">
                        <div class="small mb-1">Mission progress</div>
                        <div class="progress progress-thin mb-2"><div class="progress-bar bg-info" style="width:${Math.min(100, (team.missions_completed || 0) * 20)}%"></div></div>
                        <div class="small text-muted">Validation ${Number(team.validation_rate || 0).toFixed(1)}% · Health ${health.toFixed(0)}%</div>
                    </div>
                </td>
            </tr>
        `;
    }

    function refreshLeaderboard() {
        const sortBy = sortSelect?.value || 'score';
        fetch(`/api/leaderboard?sort_by=${encodeURIComponent(sortBy)}&limit=100`)
            .then(r => r.json())
            .then(data => {
                const rows = (data.leaderboard || []).map((t, i) => rowTemplate(t, i)).join('');
                table.innerHTML = rows || '<tr><td colspan="10" class="text-center text-muted py-4">No ranked teams yet</td></tr>';
                ArenaUI.initTeamDots();
                ArenaUI.initBars();
            })
            .catch(() => null);
    }

    if (sortSelect) {
        sortSelect.addEventListener('change', refreshLeaderboard);
    }

    ArenaUI.startPolling(refreshLeaderboard, 8000);
})();
