/**
 * LangSmith Observability Dashboard — Logic
 * Dedicated Admin Tracing, User-Wise Drill-Down, and Span Inspector
 */

let currentAuthToken = localStorage.getItem('rentease_auth_token') || null;
let currentAdminUser = null;
let allRunsList = [];
let allUsersList = [];
let selectedRunId = null;
let activeSelectedNode = null;
let selectedUserFilter = '';

// ── Initialization ─────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
    await verifyAdminAccess();
});

// ── Authentication & Access Control ────────────────────────────
async function verifyAdminAccess() {
    if (!currentAuthToken) {
        showAccessDenied("You must be logged in as an administrator to access observability traces.");
        return;
    }

    try {
        const res = await fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${currentAuthToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (res.ok) {
            const data = await res.json();
            const user = data.user;
            const isAdmin = Boolean(user.is_admin || user.email === 'admin@gmail.com');

            if (!isAdmin) {
                showAccessDenied(`Current user (${user.email}) does not have administrative privileges.`);
                return;
            }

            currentAdminUser = user;
            hideAccessDenied();
            document.getElementById('admin-user-email').textContent = user.email;

            // Load all dashboard components
            await Promise.all([
                loadCloudStatus(),
                loadSummaryStats(),
                loadUserList(),
                loadRunsTable(),
            ]);

        } else {
            showAccessDenied("Your session has expired. Please sign in as an administrator.");
        }
    } catch (err) {
        console.error('Auth verification error:', err);
        showAccessDenied("Could not verify administrator credentials.");
    }
}

function showAccessDenied(message) {
    const gate = document.getElementById('access-denied-gate');
    const msgEl = document.getElementById('denied-message');
    if (msgEl && message) msgEl.textContent = message;
    if (gate) gate.classList.remove('hidden');
}

function hideAccessDenied() {
    const gate = document.getElementById('access-denied-gate');
    if (gate) gate.classList.add('hidden');
}

function promptAdminLogin() {
    const modal = document.getElementById('admin-login-modal');
    if (modal) modal.classList.remove('hidden');
}

function closeAdminLoginModal() {
    const modal = document.getElementById('admin-login-modal');
    if (modal) modal.classList.add('hidden');
}

async function handleAdminLogin(event) {
    event.preventDefault();
    const email = document.getElementById('admin-email').value.trim();
    const password = document.getElementById('admin-password').value;
    const errBox = document.getElementById('admin-login-error');
    const submitBtn = document.getElementById('admin-login-submit-btn');

    if (errBox) errBox.classList.add('hidden');
    if (submitBtn) submitBtn.disabled = true;

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Login failed. Please check your credentials.');
        }

        const user = data.user;
        const isAdmin = Boolean(user.is_admin || user.email === 'admin@gmail.com');
        if (!isAdmin) {
            throw new Error("This account does not have administrator privileges.");
        }

        currentAuthToken = data.token;
        currentAdminUser = user;
        localStorage.setItem('rentease_auth_token', currentAuthToken);
        localStorage.setItem('rentease_auth_user', JSON.stringify(user));

        closeAdminLoginModal();
        hideAccessDenied();
        document.getElementById('admin-user-email').textContent = user.email;

        await Promise.all([
            loadCloudStatus(),
            loadSummaryStats(),
            loadUserList(),
            loadRunsTable(),
        ]);

        showToast("Authenticated as System Administrator.");

    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove('hidden');
        }
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

function handleAdminLogout() {
    localStorage.removeItem('rentease_auth_token');
    localStorage.removeItem('rentease_auth_user');
    window.location.href = '/';
}

// ── LangSmith Cloud Status ─────────────────────────────────────
async function loadCloudStatus() {
    const badge = document.getElementById('cloud-status-badge');
    const statusText = document.getElementById('cloud-status-text');
    const directBtn = document.getElementById('cloud-direct-btn');

    try {
        const res = await fetch('/api/traces/config/langsmith', {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.langsmith_active) {
                badge.classList.add('active');
                statusText.textContent = `Cloud Sync: Active (${data.project})`;
                if (directBtn) {
                    directBtn.href = data.dashboard_url;
                    directBtn.classList.remove('hidden');
                }
            } else {
                badge.classList.remove('active');
                statusText.textContent = 'Local Mode (Cloud Ready)';
            }
        }
    } catch (e) {
        statusText.textContent = 'Local High-Fidelity Tracing';
    }
}

function openCloudSetupModal() {
    const modal = document.getElementById('cloud-setup-modal');
    if (modal) modal.classList.remove('hidden');
}

function closeCloudSetupModal() {
    const modal = document.getElementById('cloud-setup-modal');
    if (modal) modal.classList.add('hidden');
}

// ── Metrics Bar ────────────────────────────────────────────────
async function loadSummaryStats() {
    try {
        const res = await fetch('/api/traces/stats', {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });
        if (res.ok) {
            const stats = await res.json();
            document.getElementById('metric-total-runs').textContent = stats.total_runs;
            document.getElementById('metric-users-count').textContent = stats.users_count;
            document.getElementById('metric-avg-latency').textContent = `${stats.avg_latency_ms} ms`;
            document.getElementById('metric-success-rate').textContent = `${stats.success_rate}%`;
            document.getElementById('metric-error-sub').textContent = `${stats.error_count} errors, ${stats.success_count} successful`;
        }
    } catch (e) {
        console.error('Error loading stats:', e);
    }
}

// ── User-Wise Filter & Quick Tabs ──────────────────────────────
async function loadUserList() {
    try {
        const res = await fetch('/api/traces/users', {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });
        if (res.ok) {
            const data = await res.json();
            allUsersList = data.users || [];

            // Populate Dropdown
            const select = document.getElementById('filter-user');
            select.innerHTML = '<option value="">All Users (Global)</option>';

            allUsersList.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.user_email || u.user_id;
                opt.textContent = `${u.user_email} (${u.trace_count} runs)`;
                select.appendChild(opt);
            });

            // Populate Quick Tabs Bar
            const tabsBar = document.getElementById('user-tabs-bar');
            tabsBar.innerHTML = '<span class="user-tab-label">User Traces:</span>';

            const allBtn = document.createElement('button');
            allBtn.type = 'button';
            allBtn.className = `user-tab-btn ${selectedUserFilter === '' ? 'active' : ''}`;
            allBtn.textContent = 'All Users';
            allBtn.onclick = () => selectUserTab('');
            tabsBar.appendChild(allBtn);

            allUsersList.forEach(u => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = `user-tab-btn ${selectedUserFilter === u.user_email ? 'active' : ''}`;
                btn.innerHTML = `👤 ${escapeHtml(u.user_email)} <span class="user-pill-badge">${u.trace_count}</span>`;
                btn.onclick = () => selectUserTab(u.user_email);
                tabsBar.appendChild(btn);
            });
        }
    } catch (e) {
        console.error('Error loading users:', e);
    }
}

function selectUserTab(userEmail) {
    selectedUserFilter = userEmail;
    const select = document.getElementById('filter-user');
    if (select) select.value = userEmail;

    document.querySelectorAll('.user-tab-btn').forEach(btn => {
        if (btn.dataset.email === userEmail || (userEmail === '' && btn.textContent === 'All Users') || btn.innerHTML.includes(userEmail)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    loadRunsTable();
}

function handleFilterChange() {
    const userSelect = document.getElementById('filter-user');
    selectedUserFilter = userSelect ? userSelect.value : '';
    selectUserTab(selectedUserFilter);
}

function handleSearchInput() {
    renderFilteredRuns();
}

// ── Runs Table ─────────────────────────────────────────────────
async function loadRunsTable() {
    const tbody = document.getElementById('runs-tbody');
    const countLabel = document.getElementById('results-count-label');
    tbody.innerHTML = '<tr><td colspan="8" class="table-loading-row">Fetching LangSmith runs...</td></tr>';

    const agentFilter = document.getElementById('filter-agent')?.value || '';
    const statusFilter = document.getElementById('filter-status')?.value || '';

    let url = '/api/traces?limit=150';
    if (selectedUserFilter) {
        if (selectedUserFilter.includes('@')) {
            url += `&user_email=${encodeURIComponent(selectedUserFilter)}`;
        } else {
            url += `&user_id=${encodeURIComponent(selectedUserFilter)}`;
        }
    }
    if (agentFilter) url += `&agent=${encodeURIComponent(agentFilter)}`;
    if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;

    try {
        const res = await fetch(url, {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        allRunsList = data.traces || [];

        if (countLabel) countLabel.textContent = `Showing ${allRunsList.length} runs`;
        renderFilteredRuns();

        // Auto-select first run if none selected
        if (allRunsList.length > 0 && !selectedRunId) {
            selectRun(allRunsList[0].trace_id);
        }

    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="table-loading-row" style="color:var(--ls-error)">Failed to load runs: ${err.message}</td></tr>`;
    }
}

function renderFilteredRuns() {
    const tbody = document.getElementById('runs-tbody');
    const searchVal = (document.getElementById('filter-search-input')?.value || '').toLowerCase().trim();

    let filtered = allRunsList;
    if (searchVal) {
        filtered = filtered.filter(r =>
            (r.user_input && r.user_input.toLowerCase().includes(searchVal)) ||
            (r.user_email && r.user_email.toLowerCase().includes(searchVal)) ||
            (r.trace_id && r.trace_id.toLowerCase().includes(searchVal)) ||
            (r.agents_invoked && r.agents_invoked.some(a => a.toLowerCase().includes(searchVal)))
        );
    }

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="table-loading-row">No runs match your current filter criteria.</td></tr>';
        return;
    }

    tbody.innerHTML = '';
    filtered.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = `ls-run-row ${r.trace_id === selectedRunId ? 'selected' : ''}`;
        tr.id = `row-${r.trace_id}`;
        tr.onclick = () => selectRun(r.trace_id);

        const flowPills = (r.agents_invoked || []).map(a => `<span class="flow-pill">${a}</span>`).join('<span class="flow-sep">➔</span>');
        const timeFormatted = r.start_time ? formatRelativeTime(r.start_time) : 'Just now';
        const status = r.status || 'SUCCESS';

        tr.innerHTML = `
            <td>
                <div class="run-name-cell">
                    <span class="run-type-icon">⚡</span>
                    <span>multi_agent_orchestrator</span>
                </div>
            </td>
            <td>
                <div class="run-user-cell">
                    <span>👤</span>
                    <span>${escapeHtml(r.user_email || 'anonymous')}</span>
                </div>
            </td>
            <td>
                <div class="run-flow-cell">
                    ${flowPills || '<span class="flow-pill">supervisor</span>'}
                </div>
            </td>
            <td>
                <div class="run-query-cell" title="${escapeHtml(r.user_input || '')}">
                    "${escapeHtml(r.user_input || 'No user input')}"
                </div>
            </td>
            <td>
                <span class="latency-badge">${r.duration_ms} ms</span>
            </td>
            <td>
                <span class="spans-badge">${r.span_count || (r.spans ? r.spans.length : 0)} spans</span>
            </td>
            <td>
                <span class="status-pill ${status}">
                    ${status === 'SUCCESS' ? '✓ COMPLETED' : '✕ ERROR'}
                </span>
            </td>
            <td>
                <span style="color:var(--ls-text-muted); font-size:0.75rem;">${timeFormatted}</span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function refreshTraces() {
    const btn = document.getElementById('refresh-btn');
    if (btn) btn.textContent = '🔄 Loading...';
    await Promise.all([
        loadSummaryStats(),
        loadUserList(),
        loadRunsTable(),
    ]);
    if (btn) btn.textContent = '🔄 Refresh Runs';
    showToast("LangSmith runs refreshed.");
}

// ── Inspector Drawer & Execution Tree ──────────────────────────
async function selectRun(traceId) {
    selectedRunId = traceId;

    // Highlight row
    document.querySelectorAll('.ls-run-row').forEach(row => row.classList.remove('selected'));
    const targetRow = document.getElementById(`row-${traceId}`);
    if (targetRow) targetRow.classList.add('selected');

    const emptyState = document.getElementById('drawer-empty-state');
    const drawerContent = document.getElementById('drawer-content');
    if (emptyState) emptyState.classList.add('hidden');
    if (drawerContent) drawerContent.classList.remove('hidden');

    try {
        const res = await fetch(`/api/traces/${traceId}`, {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const trace = await res.json();
        renderDrawer(trace);
    } catch (e) {
        console.error('Error reading trace details:', e);
    }
}

function renderDrawer(trace) {
    document.getElementById('drawer-run-id').textContent = trace.trace_id;
    document.getElementById('drawer-run-latency').textContent = `${trace.duration_ms} ms`;
    document.getElementById('drawer-meta-user').textContent = trace.user_email || 'anonymous';
    document.getElementById('drawer-meta-session').textContent = trace.session_id ? trace.session_id.slice(0, 12) + '...' : 'N/A';
    document.getElementById('drawer-meta-endpoint').textContent = trace.endpoint || '/api/chat';
    document.getElementById('drawer-meta-time').textContent = trace.start_time ? new Date(trace.start_time).toLocaleTimeString() : 'N/A';

    const statusPill = document.getElementById('drawer-run-status');
    statusPill.className = `status-pill ${trace.status || 'SUCCESS'}`;
    statusPill.textContent = trace.status === 'SUCCESS' ? '✓ COMPLETED' : '✕ ERROR';

    const spans = trace.spans || [];
    document.getElementById('drawer-spans-count').textContent = `${spans.length} spans`;

    // Render Execution Tree
    const treeContainer = document.getElementById('run-tree-container');
    treeContainer.innerHTML = '';

    // Root Node (multi_agent_orchestrator)
    const rootItem = document.createElement('div');
    rootItem.className = 'tree-node-item selected';
    rootItem.id = 'node-root';
    rootItem.onclick = () => selectNode('root', {
        name: 'multi_agent_orchestrator',
        span_type: 'chain',
        inputs: { user_input: trace.user_input, session_id: trace.session_id, user_email: trace.user_email },
        outputs: { agent_response: trace.agent_response, status: trace.status },
        metadata: { ...trace.metadata, agents_invoked: trace.agents_invoked },
        raw: trace,
    });
    rootItem.innerHTML = `
        <div class="node-left">
            <span class="node-icon-pill" style="background:#3b82f6; color:white;">CHAIN</span>
            <span class="node-name">multi_agent_orchestrator</span>
        </div>
        <div class="node-right">${trace.duration_ms} ms</div>
    `;
    treeContainer.appendChild(rootItem);

    // Spans Children
    spans.forEach((s, idx) => {
        const item = document.createElement('div');
        item.className = 'tree-node-item';
        item.id = `node-span-${idx}`;
        item.style.paddingLeft = '22px';
        item.onclick = (e) => {
            e.stopPropagation();
            selectNode(`span-${idx}`, {
                name: s.name,
                span_type: s.span_type,
                inputs: s.inputs,
                outputs: s.outputs,
                metadata: s.metadata,
                error: s.error,
                raw: s,
            });
        };

        let typeClass = 'node-icon-agent';
        if (s.span_type === 'supervisor') typeClass = 'node-icon-supervisor';
        else if (s.span_type === 'tool') typeClass = 'node-icon-tool';
        else if (s.span_type === 'llm') typeClass = 'node-icon-llm';

        item.innerHTML = `
            <div class="node-left">
                <span class="node-icon-pill ${typeClass}">${s.span_type}</span>
                <span class="node-name">${escapeHtml(s.name)}</span>
            </div>
            <div class="node-right">${s.duration_ms} ms</div>
        `;
        treeContainer.appendChild(item);
    });

    // Default select root node
    selectNode('root', {
        name: 'multi_agent_orchestrator',
        span_type: 'chain',
        inputs: { user_input: trace.user_input, session_id: trace.session_id, user_email: trace.user_email },
        outputs: { agent_response: trace.agent_response, status: trace.status },
        metadata: { ...trace.metadata, agents_invoked: trace.agents_invoked },
        raw: trace,
    });
}

function selectNode(nodeId, nodeData) {
    activeSelectedNode = nodeData;

    // Highlight tree item
    document.querySelectorAll('.tree-node-item').forEach(el => el.classList.remove('selected'));
    const target = document.getElementById(`node-${nodeId}`);
    if (target) target.classList.add('selected');

    document.getElementById('selected-node-title').textContent = nodeData.name;
    document.getElementById('selected-node-type').textContent = (nodeData.span_type || 'span').toUpperCase();

    // Populate Tab Contents
    document.getElementById('node-inputs-content').textContent = nodeData.inputs ? JSON.stringify(nodeData.inputs, null, 2) : 'No inputs recorded.';
    document.getElementById('node-outputs-content').textContent = nodeData.outputs ? JSON.stringify(nodeData.outputs, null, 2) : (nodeData.error ? `ERROR:\n${nodeData.error}` : 'No outputs recorded.');
    document.getElementById('node-metadata-content').textContent = nodeData.metadata ? JSON.stringify(nodeData.metadata, null, 2) : '{}';
    document.getElementById('node-raw-content').textContent = nodeData.raw ? JSON.stringify(nodeData.raw, null, 2) : '{}';
}

function switchNodeTab(tabId) {
    document.querySelectorAll('.node-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.node-tab-content').forEach(content => {
        content.classList.toggle('hidden', content.id !== tabId);
    });
}

function copyTraceId() {
    const text = document.getElementById('drawer-run-id').textContent;
    if (text) {
        navigator.clipboard.writeText(text);
        showToast("Trace ID copied to clipboard.");
    }
}

// ── Helpers ────────────────────────────────────────────────────
function formatRelativeTime(isoString) {
    try {
        const date = new Date(isoString);
        const diffMs = Date.now() - date.getTime();
        const diffSec = Math.floor(diffMs / 1000);
        if (diffSec < 60) return `${diffSec}s ago`;
        const diffMin = Math.floor(diffSec / 60);
        if (diffMin < 60) return `${diffMin}m ago`;
        const diffHr = Math.floor(diffMin / 60);
        if (diffHr < 24) return `${diffHr}h ago`;
        return date.toLocaleDateString();
    } catch (e) {
        return 'N/A';
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function showToast(msg) {
    const toast = document.getElementById('ls-toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}
