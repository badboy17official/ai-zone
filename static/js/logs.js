(() => {
    const tableBody = document.getElementById('logsTableBody');
    if (!tableBody) return;

    const detailModalEl = document.getElementById('logDetailModal');
    const detailModal = detailModalEl ? new bootstrap.Modal(detailModalEl) : null;

    function jsonHighlight(raw) {
        let text = raw || '';
        try {
            text = JSON.stringify(JSON.parse(raw), null, 2);
        } catch (_) {}
        const safe = ArenaUI.escapeHtml(ArenaUI.truncate(text, 18000));
        return safe
            .replace(/(".*?")(?=\s*:)/g, '<span class="json-k">$1</span>')
            .replace(/:\s(".*?")/g, ': <span class="json-s">$1</span>')
            .replace(/:\s(-?\d+(\.\d+)?)/g, ': <span class="json-n">$1</span>');
    }

    function setContent(id, html) {
        const el = document.getElementById(id);
        if (el) el.innerHTML = html;
    }

    function loadLogDetail(logId) {
        fetch(`/admin/api/logs/${logId}`)
            .then(r => r.json())
            .then(log => {
                setContent('logModalTitle', `Log Detail · ${ArenaUI.escapeHtml(log.team_code)}${log.mission_title ? ' · ' + ArenaUI.escapeHtml(log.mission_title) : ''}`);
                setContent('logPrompt', ArenaUI.escapeHtml(ArenaUI.truncate(log.prompt_text, 10000)));
                setContent('logRawOutput', jsonHighlight(log.ai_raw_output));
                setContent('logParsedOutput', jsonHighlight(log.ai_parsed_output || '{}'));
                setContent('logValidationMeta', `Parse: ${ArenaUI.escapeHtml(log.parse_result || 'N/A')} · Validation: ${ArenaUI.escapeHtml(log.validation_result || 'N/A')} · Confidence: ${Number(log.confidence_score || 0).toFixed(3)}`);
                setContent('logSecurityMeta', `Injection: ${Number(log.injection_score || 0).toFixed(3)} · Hallucination: ${(Number(log.hallucination_probability || 0) * 100).toFixed(1)}% · Retry: ${log.retry_attempt || 0}`);
                setContent('logErrors', ArenaUI.escapeHtml(ArenaUI.truncate(log.error_details || 'None', 6000)));

                const copyPromptBtn = document.getElementById('copyPromptBtn');
                const copyOutputBtn = document.getElementById('copyOutputBtn');
                copyPromptBtn.onclick = () => ArenaUI.copyText(log.prompt_text || '', copyPromptBtn);
                copyOutputBtn.onclick = () => ArenaUI.copyText(log.ai_raw_output || '', copyOutputBtn);

                detailModal?.show();
            })
            .catch(() => null);
    }

    tableBody.addEventListener('click', event => {
        const btn = event.target.closest('[data-log-id]');
        if (!btn) return;
        loadLogDetail(btn.dataset.logId);
    });

    const searchInput = document.getElementById('logSearchInput');
    if (searchInput) {
        const doFilter = ArenaUI.debounce(() => {
            const q = searchInput.value.toLowerCase().trim();
            document.querySelectorAll('#logsTableBody tr[data-filter-text]').forEach(row => {
                row.classList.toggle('d-none', !row.dataset.filterText.includes(q));
            });
        }, 200);
        searchInput.addEventListener('input', doFilter);
    }
})();
