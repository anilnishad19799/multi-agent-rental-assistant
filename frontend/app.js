const chatBox = document.getElementById('chat-box');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');

// Track session for multi-turn conversations
let currentSessionId = null;

chatForm.addEventListener('submit', async function (e) {
    e.preventDefault();

    const msg = userInput.value.trim();
    if (!msg) return;

    appendMessage('You', msg, 'user-msg');

    userInput.value = '';
    sendBtn.disabled = true;

    try {
        const body = {
            message: msg,
            provider: modelSelect.value
        };

        // Send session_id for follow-up messages
        if (currentSessionId) {
            body.session_id = currentSessionId;
        }

        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await res.json();

        // Update or set session_id
        currentSessionId = data.session_id;

        connectStream(data.session_id);

    } catch (err) {
        appendMessage('Error', err.message, 'error-msg');
        sendBtn.disabled = false;
    }
});

// New conversation button
function newConversation() {
    currentSessionId = null;
    chatBox.innerHTML = '';
    appendMessage('System', 'New conversation started. Ask me anything!', 'system-msg');
}

function appendMessage(sender, text, cls) {
    const div = document.createElement('div');
    div.className = 'message ' + cls;
    div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ── Interactive UI Helpers ─────────────────────────────────────
window.selectSlot = function(dateStr, timeStr) {
    if (!userInput) return;
    userInput.value = `${dateStr} at ${timeStr} book`;
    userInput.focus();
};

window.confirmBooking = function() {
    if (!userInput) return;
    userInput.value = 'yes';
    if (sendBtn && !sendBtn.disabled) {
        sendBtn.click();
    }
};

window.proceedToCalendar = function() {
    if (!userInput) return;
    userInput.value = 'proceed';
    if (sendBtn && !sendBtn.disabled) {
        sendBtn.click();
    }
};