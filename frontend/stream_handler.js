/**
 * SSE stream handler — connects to /api/stream/{sessionId}
 * and appends LLM tokens to the chat in real time.
 * Supports multi-agent events: AGENT_START, AGENT_SWITCH, DATA_EXTRACTED.
 */
function connectStream(sessionId) {
    const source = new EventSource('/api/stream/' + sessionId);

    // Create bot message container
    const botDiv = document.createElement('div');
    botDiv.className = 'message bot-msg streaming-cursor';
    botDiv.innerHTML = '<strong>Agent:</strong> ';
    chatBox.appendChild(botDiv);

    let currentAgent = '';

    source.onmessage = function (event) {
        const data = JSON.parse(event.data);

        if (data.type === 'AGENT_START') {
            currentAgent = data.data.agent || '';
            if (currentAgent && currentAgent !== 'supervisor') {
                botDiv.innerHTML = '<strong>' + currentAgent.charAt(0).toUpperCase() + currentAgent.slice(1) + ' Agent:</strong> ';
            }
        }

        if (data.type === 'AGENT_SWITCH') {
            const toAgent = data.data.to_agent || '';
            if (toAgent) {
                currentAgent = toAgent;
                // Update the label
                botDiv.innerHTML = '<strong>' + toAgent.charAt(0).toUpperCase() + toAgent.slice(1) + ' Agent:</strong> ';
            }
        }

        if (data.type === 'LLM_TOKEN') {
            appendToken(botDiv, data.data.token);
        }

        if (data.type === 'DATA_EXTRACTED') {
            // Optionally show extracted data indicator
            const badge = document.createElement('span');
            badge.className = 'data-badge';
            badge.textContent = ' 📋 Data captured';
            // botDiv.appendChild(badge);  // uncomment to show
        }

        if (data.type === 'ERROR') {
            botDiv.innerHTML += '<br><em style="color:#d93025;">[Error: ' + (data.data.error || 'unknown') + ']</em>';
        }

        if (data.type === 'DONE') {
            source.close();
            botDiv.classList.remove('streaming-cursor');
            formatCompletedMessage(botDiv);
            sendBtn.disabled = false;
        }
    };

    source.onerror = function () {
        source.close();
        botDiv.classList.remove('streaming-cursor');
        formatCompletedMessage(botDiv);
        sendBtn.disabled = false;
    };
}

function appendToken(container, token) {
    // Convert plain newlines to <br> so line breaks render in HTML
    container.innerHTML += token.replace(/\n/g, '<br>');
    chatBox.scrollTop = chatBox.scrollHeight;
}

function formatCompletedMessage(container) {
    if (!container) return;
    let html = container.innerHTML;
    // Convert markdown bold **text** to <strong>text</strong>
    html = html.replace(/\*\*([^*\n<]+)\*\*/g, '<strong>$1</strong>');
    container.innerHTML = html;
}