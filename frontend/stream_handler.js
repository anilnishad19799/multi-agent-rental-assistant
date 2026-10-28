/**
 * SSE stream handler — connects to /api/stream/{sessionId}
 * Streams tokens in real time with stylized multi-agent badges and markdown rendering.
 * Supports on-demand response cancellation via Stop button and Esc key.
 */

const AGENT_META = {
    supervisor: { name: 'Supervisor Agent', icon: '🎯', badgeClass: 'badge-supervisor' },
    rent: { name: 'Rent Specialist', icon: '🏠', badgeClass: 'badge-rent' },
    calendar: { name: 'Calendar & Visits', icon: '📅', badgeClass: 'badge-calendar' },
    user_info: { name: 'Profile Assistant', icon: '👤', badgeClass: 'badge-user_info' },
    general: { name: 'Rental Concierge', icon: '💬', badgeClass: 'badge-general' }
};

// Global streaming session state
let streamCounter = 0;
window.activeStreamId = null;
window.activeEventSource = null;
window.activeBotDiv = null;
window.activeSessionId = null;
window.isStreaming = false;

function getAgentBadgeHtml(agentKey) {
    const key = (agentKey || 'general').toLowerCase();
    const meta = AGENT_META[key] || { name: key.charAt(0).toUpperCase() + key.slice(1) + ' Agent', icon: '🤖', badgeClass: 'badge-general' };
    return `<div class="agent-badge-wrapper"><span class="agent-label-badge ${meta.badgeClass}">${meta.icon} ${meta.name}</span></div><div class="agent-content-body">`;
}

function appendStoppedNotice(container) {
    if (!container) return;
    if (container.querySelector('.stopped-notice')) return;

    const body = container.querySelector('.agent-content-body') || container;
    const notice = document.createElement('div');
    notice.className = 'stopped-notice';
    notice.innerHTML = '<span class="stop-icon">⏹</span> <span>Response generation stopped</span>';
    body.appendChild(notice);
    if (typeof chatBox !== 'undefined' && chatBox) {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

function resetStreamingUI() {
    window.isStreaming = false;
    window.activeEventSource = null;
    window.activeBotDiv = null;

    const stopBtn = document.getElementById('stop-btn');
    const sendBtn = document.getElementById('send-btn');
    if (stopBtn) stopBtn.classList.add('hidden');
    if (sendBtn) {
        sendBtn.classList.remove('hidden');
        sendBtn.disabled = false;
    }
    const inputEl = document.getElementById('user-input');
    if (inputEl) {
        inputEl.disabled = false;
        inputEl.focus();
    }
}

function connectStream(sessionId) {
    // Increment unique stream identifier for this query turn
    const thisStreamId = ++streamCounter;
    window.activeStreamId = thisStreamId;

    // If a previous stream is still open, close it cleanly
    if (window.activeEventSource) {
        try {
            window.activeEventSource.close();
        } catch (e) {}
    }

    const source = new EventSource('/api/stream/' + sessionId);

    // Create bot message container for this turn
    const botDiv = document.createElement('div');
    botDiv.className = 'message bot-msg streaming-cursor';
    botDiv.dataset.streamId = thisStreamId;
    botDiv.innerHTML = getAgentBadgeHtml('supervisor');
    chatBox.appendChild(botDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    // Track active stream globals
    window.activeEventSource = source;
    window.activeBotDiv = botDiv;
    window.activeSessionId = sessionId;
    window.isStreaming = true;

    // Toggle button UI to show Stop button
    const stopBtn = document.getElementById('stop-btn');
    const sendBtn = document.getElementById('send-btn');
    if (stopBtn) stopBtn.classList.remove('hidden');
    if (sendBtn) sendBtn.classList.add('hidden');

    let currentAgent = 'supervisor';
    let rawContent = '';

    source.onmessage = function (event) {
        // Discard any events if this stream is no longer the active one
        if (window.activeStreamId !== thisStreamId) {
            try { source.close(); } catch (e) {}
            return;
        }

        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error('Error parsing SSE event:', e);
            return;
        }

        if (data.type === 'AGENT_START') {
            const agent = data.data.agent || 'supervisor';
            if (agent && agent !== currentAgent) {
                currentAgent = agent;
                updateAgentHeader(botDiv, currentAgent);
            }
        }

        if (data.type === 'AGENT_SWITCH') {
            const toAgent = data.data.to_agent || '';
            if (toAgent && toAgent !== currentAgent) {
                currentAgent = toAgent;
                updateAgentHeader(botDiv, currentAgent);
            }
        }

        if (data.type === 'LLM_TOKEN') {
            const token = data.data.token || '';
            rawContent += token;
            appendToken(botDiv, token);
        }

        if (data.type === 'DATA_EXTRACTED') {
            // Data captured event
        }

        if (data.type === 'ERROR') {
            const errBody = botDiv.querySelector('.agent-content-body') || botDiv;
            errBody.innerHTML += '<div class="error-msg" style="margin-top:8px;">⚠️ ' + (data.data.error || 'Something went wrong') + '</div>';
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        if (data.type === 'DONE') {
            source.close();
            botDiv.classList.remove('streaming-cursor');
            if (data.data && data.data.stopped) {
                appendStoppedNotice(botDiv);
            }
            formatCompletedMessage(botDiv);
            resetStreamingUI();
            if (typeof window.updateTracesCount === 'function') {
                setTimeout(window.updateTracesCount, 500);
            }
        }
    };

    source.onerror = function () {
        if (window.activeStreamId === thisStreamId) {
            source.close();
            botDiv.classList.remove('streaming-cursor');
            formatCompletedMessage(botDiv);
            resetStreamingUI();
        }
    };
}

/**
 * Stop active generation on user request.
 * Closes the browser SSE stream, marks ONLY the active bot message container with stopped notice,
 * and calls the backend POST /api/chat/stop endpoint to terminate background LLM execution.
 */
window.stopGeneration = async function () {
    if (!window.isStreaming && !window.activeEventSource) {
        return;
    }

    const targetDiv = window.activeBotDiv;
    const sessId = window.activeSessionId || (typeof currentSessionId !== 'undefined' ? currentSessionId : null);

    // 1. Invalidate active stream ID so no further SSE callbacks process on this container
    window.activeStreamId = null;

    // 2. Immediately close client SSE connection
    if (window.activeEventSource) {
        try {
            window.activeEventSource.close();
        } catch (e) {
            console.warn('Error closing SSE source:', e);
        }
    }

    // 3. Mark ONLY this specific message container with stopped notice
    if (targetDiv) {
        targetDiv.classList.remove('streaming-cursor');
        appendStoppedNotice(targetDiv);
        formatCompletedMessage(targetDiv);
    }

    // 4. Reset input bar buttons immediately so user can type the next message
    resetStreamingUI();

    // 5. Notify user via brief toast
    if (typeof showToast === 'function') {
        showToast('⏹️ Generation stopped. You can enter a new question.');
    }

    // 6. Notify backend to cancel the active orchestrator task & clear pubsub queue
    if (sessId) {
        try {
            const token = localStorage.getItem('rentease_auth_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            await fetch('/api/chat/stop', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ session_id: sessId })
            });
        } catch (err) {
            console.warn('Error calling /api/chat/stop:', err);
        }
    }

    // 7. Refresh admin traces count
    if (typeof window.updateTracesCount === 'function') {
        setTimeout(window.updateTracesCount, 500);
    }
};

// Global Esc key listener to stop response generation
window.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        if (window.isStreaming) {
            e.preventDefault();
            window.stopGeneration();
        }
    }
});

function updateAgentHeader(container, agentName) {
    const badgeWrapper = container.querySelector('.agent-badge-wrapper');
    const meta = AGENT_META[agentName.toLowerCase()] || {
        name: agentName.charAt(0).toUpperCase() + agentName.slice(1) + ' Agent',
        icon: '🤖',
        badgeClass: 'badge-general'
    };
    if (badgeWrapper) {
        badgeWrapper.innerHTML = `<span class="agent-label-badge ${meta.badgeClass}">${meta.icon} ${meta.name}</span>`;
    }
}

function appendToken(container, token) {
    let body = container.querySelector('.agent-content-body');
    if (!body) {
        body = container;
    }
    // If token contains HTML tags, append directly; otherwise convert newlines to <br>
    if (token.includes('<') && token.includes('>')) {
        body.innerHTML += token;
    } else {
        body.innerHTML += token.replace(/\n/g, '<br>');
    }
    chatBox.scrollTop = chatBox.scrollHeight;
}

function formatCompletedMessage(container) {
    if (!container) return;
    const body = container.querySelector('.agent-content-body');
    if (!body) return;

    let html = body.innerHTML;
    // Format bold **text**
    html = html.replace(/\*\*([^*\n<]+)\*\*/g, '<strong>$1</strong>');
    body.innerHTML = html;
    chatBox.scrollTop = chatBox.scrollHeight;
}

window.getAgentBadgeHtml = getAgentBadgeHtml;
window.formatCompletedMessage = formatCompletedMessage;
window.resetStreamingUI = resetStreamingUI;
