/**
 * RentEase AI — Application Logic
 * Authentication, Form Validation, Chat Session Management, and Interactive Actions
 */

// ── DOM References ─────────────────────────────────────────────
const chatBox = document.getElementById('chat-box');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');

// Auth DOM
const authPortal = document.getElementById('auth-portal');
const chatApp = document.getElementById('chat-app');
const portalTitle = document.getElementById('portal-title');
const portalSubtitle = document.getElementById('portal-subtitle');
const tabLoginBtn = document.getElementById('tab-login-btn');
const tabSignupBtn = document.getElementById('tab-signup-btn');
const loginForm = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const authAlert = document.getElementById('auth-alert');

const loggedOutActions = document.getElementById('logged-out-actions');
const loggedInActions = document.getElementById('logged-in-actions');
const userDisplayName = document.getElementById('user-display-name');
const userAvatarInitials = document.getElementById('user-avatar-initials');
const toastBanner = document.getElementById('toast-banner');

const welcomeUserTitle = document.getElementById('welcome-user-title');
const welcomeUserDesc = document.getElementById('welcome-user-desc');

// ── App State ──────────────────────────────────────────────────
let currentSessionId = null;
let currentAuthUser = null;
let currentAuthToken = localStorage.getItem('rentease_auth_token') || null;

// ── App Initialization ─────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    updateTracesCount();
});

// ── Authentication Management ──────────────────────────────────

async function checkAuth() {
    if (!currentAuthToken) {
        setUnauthenticatedUI();
        return;
    }

    try {
        const res = await fetch('/api/auth/me', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${currentAuthToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (res.ok) {
            const data = await res.json();
            currentAuthUser = data.user;
            localStorage.setItem('rentease_auth_user', JSON.stringify(currentAuthUser));
            setAuthenticatedUI(currentAuthUser);
        } else {
            // Token expired or invalid
            handleLogout(false);
        }
    } catch (err) {
        console.warn('Auth verification error:', err);
        const cached = localStorage.getItem('rentease_auth_user');
        if (cached) {
            try {
                currentAuthUser = JSON.parse(cached);
                setAuthenticatedUI(currentAuthUser);
            } catch (e) {
                setUnauthenticatedUI();
            }
        } else {
            setUnauthenticatedUI();
        }
    }
}

function setAuthenticatedUI(user) {
    if (!user) return;

    // Show Chat, Hide Auth Gate
    if (authPortal) authPortal.classList.add('hidden');
    if (chatApp) chatApp.classList.remove('hidden');

    // Update Nav bar
    if (loggedOutActions) loggedOutActions.classList.add('hidden');
    if (loggedInActions) loggedInActions.classList.remove('hidden');

    const name = user.name || (user.email ? user.email.split('@')[0] : 'User');
    if (userDisplayName) userDisplayName.textContent = name;

    const initials = name
        .split(' ')
        .map(n => n.charAt(0))
        .join('')
        .toUpperCase()
        .slice(0, 2) || 'U';

    if (userAvatarInitials) userAvatarInitials.textContent = initials;

    // Admin-only Observability Link
    const adminBtn = document.getElementById('admin-traces-nav-btn');
    if (adminBtn) {
        if (user.is_admin || user.email === 'admin@gmail.com') {
            adminBtn.classList.remove('hidden');
        } else {
            adminBtn.classList.add('hidden');
        }
    }

    // Load this user's isolated chat history
    loadUserChatHistory(user);

    if (userInput) {
        userInput.focus();
    }
}

function setUnauthenticatedUI() {
    currentAuthUser = null;
    currentAuthToken = null;
    currentSessionId = null;
    localStorage.removeItem('rentease_auth_token');
    localStorage.removeItem('rentease_auth_user');

    // Hide admin observability button
    const adminBtn = document.getElementById('admin-traces-nav-btn');
    if (adminBtn) adminBtn.classList.add('hidden');

    // CLEAR CHAT BOX COMPLETELY to prevent cross-account chat leaks!
    if (chatBox) {
        chatBox.innerHTML = '';
    }

    // Hide Chat, Show Auth Gate
    if (chatApp) chatApp.classList.add('hidden');
    if (authPortal) authPortal.classList.remove('hidden');

    // Update Nav bar
    if (loggedOutActions) loggedOutActions.classList.remove('hidden');
    if (loggedInActions) loggedInActions.classList.add('hidden');

    switchAuthTab('login');
}

// ── Tab Controls ───────────────────────────────────────────────

window.switchAuthTab = function(tab) {
    clearAuthAlert();
    clearFormErrors();

    if (tab === 'login') {
        if (tabLoginBtn) tabLoginBtn.classList.add('active');
        if (tabSignupBtn) tabSignupBtn.classList.remove('active');
        if (loginForm) loginForm.classList.remove('hidden');
        if (signupForm) signupForm.classList.add('hidden');
        if (portalTitle) portalTitle.textContent = 'Sign In to Continue';
        if (portalSubtitle) portalSubtitle.textContent = 'Access verified properties and interact with the AI rental assistant';
        const emailInput = document.getElementById('login-email');
        if (emailInput) setTimeout(() => emailInput.focus(), 50);
    } else {
        if (tabSignupBtn) tabSignupBtn.classList.add('active');
        if (tabLoginBtn) tabLoginBtn.classList.remove('active');
        if (signupForm) signupForm.classList.remove('hidden');
        if (loginForm) loginForm.classList.add('hidden');
        if (portalTitle) portalTitle.textContent = 'Create an Account';
        if (portalSubtitle) portalSubtitle.textContent = 'Join RentEase to find your ideal PG or flat and book visits instantly';
        const nameInput = document.getElementById('signup-name');
        if (nameInput) setTimeout(() => nameInput.focus(), 50);
    }
};

window.togglePasswordVisibility = function(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
};

// ── Input Validation Helpers ───────────────────────────────────

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function setFieldError(fieldId, message) {
    const errorEl = document.getElementById(fieldId + '-error');
    const inputEl = document.getElementById(fieldId);
    if (errorEl) {
        errorEl.textContent = message || '';
    }
    if (inputEl) {
        if (message) {
            inputEl.classList.add('input-error');
        } else {
            inputEl.classList.remove('input-error');
        }
    }
}

function clearFormErrors() {
    const errors = document.querySelectorAll('.field-error');
    errors.forEach(e => e.textContent = '');
    const inputs = document.querySelectorAll('.input-error');
    inputs.forEach(i => i.classList.remove('input-error'));
}

function showAuthAlert(message, type = 'error') {
    if (!authAlert) return;
    authAlert.className = 'auth-alert ' + (type === 'error' ? 'auth-alert-error' : 'auth-alert-success');
    authAlert.innerHTML = `<span>${type === 'error' ? '⚠️' : '✅'}</span> <div>${message}</div>`;
    authAlert.classList.remove('hidden');
}

function clearAuthAlert() {
    if (!authAlert) return;
    authAlert.classList.add('hidden');
    authAlert.innerHTML = '';
}

// Password strength calculation
window.evaluatePasswordStrength = function(password) {
    const bar = document.getElementById('strength-bar');
    const text = document.getElementById('strength-text');
    if (!bar || !text) return;

    if (!password) {
        bar.className = 'strength-bar-fill';
        text.textContent = 'Password strength';
        return;
    }

    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[a-zA-Z]/.test(password) && /\d/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;

    bar.className = 'strength-bar-fill';
    if (score <= 1) {
        bar.classList.add('strength-weak');
        text.textContent = 'Weak — min 6 chars with letters & numbers';
    } else if (score === 2 || score === 3) {
        bar.classList.add('strength-medium');
        text.textContent = 'Good password';
    } else {
        bar.classList.add('strength-strong');
        text.textContent = 'Strong password! 🔒';
    }
};

// ── Auth Form Handlers ─────────────────────────────────────────

window.handleLoginSubmit = async function(e) {
    e.preventDefault();
    clearAuthAlert();
    clearFormErrors();

    const emailInput = document.getElementById('login-email');
    const passwordInput = document.getElementById('login-password');
    const submitBtn = document.getElementById('login-submit-btn');

    const email = emailInput ? emailInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value : '';

    let hasError = false;

    if (!email) {
        setFieldError('login-email', 'Please enter your email address.');
        hasError = true;
    } else if (!EMAIL_REGEX.test(email)) {
        setFieldError('login-email', 'Please enter a valid email address.');
        hasError = true;
    }

    if (!password) {
        setFieldError('login-password', 'Please enter your password.');
        hasError = true;
    }

    if (hasError) return;

    setButtonLoading(submitBtn, true);

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (!res.ok) {
            showAuthAlert(data.detail || 'Invalid email or password. Please try again.');
            setButtonLoading(submitBtn, false);
            return;
        }

        // Login success — clear existing chat first to prevent leaks
        if (chatBox) chatBox.innerHTML = '';
        currentSessionId = null;

        currentAuthToken = data.token;
        currentAuthUser = data.user;
        localStorage.setItem('rentease_auth_token', currentAuthToken);
        localStorage.setItem('rentease_auth_user', JSON.stringify(currentAuthUser));

        setAuthenticatedUI(currentAuthUser);
        showToast(`Welcome back, ${currentAuthUser.name || 'User'}! Chat is now unlocked. 👋`);

    } catch (err) {
        showAuthAlert('Network error occurred. Please check your connection.');
    } finally {
        setButtonLoading(submitBtn, false);
    }
};

window.handleSignupSubmit = async function(e) {
    e.preventDefault();
    clearAuthAlert();
    clearFormErrors();

    const nameInput = document.getElementById('signup-name');
    const emailInput = document.getElementById('signup-email');
    const phoneInput = document.getElementById('signup-phone');
    const passwordInput = document.getElementById('signup-password');
    const confirmInput = document.getElementById('signup-confirm-password');
    const submitBtn = document.getElementById('signup-submit-btn');

    const name = nameInput ? nameInput.value.trim() : '';
    const email = emailInput ? emailInput.value.trim() : '';
    const phone = phoneInput ? phoneInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value : '';
    const confirmPassword = confirmInput ? confirmInput.value : '';

    let hasError = false;

    if (!name || name.length < 2) {
        setFieldError('signup-name', 'Please enter your full name (at least 2 letters).');
        hasError = true;
    }

    if (!email) {
        setFieldError('signup-email', 'Please enter your email address.');
        hasError = true;
    } else if (!EMAIL_REGEX.test(email)) {
        setFieldError('signup-email', 'Please enter a valid email address (e.g., user@example.com).');
        hasError = true;
    }

    if (!password) {
        setFieldError('signup-password', 'Password is required.');
        hasError = true;
    } else if (password.length < 6) {
        setFieldError('signup-password', 'Password must be at least 6 characters.');
        hasError = true;
    } else if (!(/[a-zA-Z]/.test(password) && /\d/.test(password))) {
        setFieldError('signup-password', 'Password must include both letters and numbers.');
        hasError = true;
    }

    if (password !== confirmPassword) {
        setFieldError('signup-confirm-password', 'Passwords do not match.');
        hasError = true;
    }

    if (phone) {
        const cleanPhone = phone.replace(/[\s\-\(\)]/g, '');
        if (cleanPhone.length < 7 || cleanPhone.length > 15) {
            setFieldError('signup-phone', 'Please enter a valid phone number.');
            hasError = true;
        }
    }

    if (hasError) return;

    setButtonLoading(submitBtn, true);

    try {
        const res = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                email,
                phone: phone || null,
                password,
                confirm_password: confirmPassword
            })
        });

        const data = await res.json();

        if (!res.ok) {
            showAuthAlert(data.detail || 'Sign up failed. Please check your details.');
            setButtonLoading(submitBtn, false);
            return;
        }

        // Signup success — clear existing chat to start clean
        if (chatBox) chatBox.innerHTML = '';
        currentSessionId = null;

        currentAuthToken = data.token;
        currentAuthUser = data.user;
        localStorage.setItem('rentease_auth_token', currentAuthToken);
        localStorage.setItem('rentease_auth_user', JSON.stringify(currentAuthUser));

        setAuthenticatedUI(currentAuthUser);
        showToast(`Account created! Welcome to RentEase AI, ${currentAuthUser.name}! 🎉`);

    } catch (err) {
        showAuthAlert('Network error occurred. Please try again.');
    } finally {
        setButtonLoading(submitBtn, false);
    }
};

window.handleLogout = async function(showNotification = true) {
    if (window.isStreaming && typeof window.stopGeneration === 'function') {
        try {
            await window.stopGeneration();
        } catch (e) {}
    }
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {
        // Ignore network errors on logout
    }

    setUnauthenticatedUI();
    if (showNotification) {
        showToast('You have been signed out.');
    }
};

function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    const textEl = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.btn-spinner');

    btn.disabled = isLoading;
    if (isLoading) {
        if (textEl) textEl.style.opacity = '0';
        if (spinner) spinner.classList.remove('hidden');
    } else {
        if (textEl) textEl.style.opacity = '1';
        if (spinner) spinner.classList.add('hidden');
    }
}

// ── Toast Notifications ────────────────────────────────────────

function showToast(message, duration = 3500) {
    if (!toastBanner) return;
    toastBanner.textContent = message;
    toastBanner.classList.remove('hidden');
    setTimeout(() => {
        toastBanner.classList.add('hidden');
    }, duration);
}

// ── User-Isolated Chat History Loading ─────────────────────────

function renderWelcomeCard(userName) {
    if (!chatBox) return;
    const name = userName || (currentAuthUser ? currentAuthUser.name : 'there');
    chatBox.innerHTML = `
        <div class="message system-msg welcome-card" id="welcome-chat-card">
            <div class="welcome-header">
                <div class="welcome-icon">👋</div>
                <div>
                    <h3 id="welcome-user-title">Welcome to RentEase AI, ${name}!</h3>
                    <p id="welcome-user-desc">Your personal rental concierge. Search verified properties, inspect pricing & sharing, and book visits in seconds.</p>
                </div>
            </div>
            <div class="welcome-steps">
                <div class="welcome-step"><span>1</span> Search by city, area, & budget</div>
                <div class="welcome-step"><span>2</span> Pick your preferred room or flat</div>
                <div class="welcome-step"><span>3</span> Pick a 1-hour slot for a visit</div>
            </div>
        </div>
    `;
}

async function loadUserChatHistory(user) {
    if (!currentAuthToken || !user) {
        renderWelcomeCard('');
        return;
    }

    try {
        const res = await fetch('/api/chat/history', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${currentAuthToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (res.ok) {
            const data = await res.json();
            chatBox.innerHTML = '';
            renderWelcomeCard(user.name);

            if (data.session_id && Array.isArray(data.messages) && data.messages.length > 0) {
                currentSessionId = data.session_id;

                data.messages.forEach(m => {
                    if (m.sender === 'USER') {
                        appendMessage('You', m.content, 'user-msg');
                    } else {
                        appendSavedBotMessage(m.agent || 'general', m.content);
                    }
                });

                chatBox.scrollTop = chatBox.scrollHeight;
            } else {
                currentSessionId = null;
            }
        } else {
            renderWelcomeCard(user.name);
        }
    } catch (err) {
        console.warn('Could not load user chat history:', err);
        renderWelcomeCard(user.name);
    }
}

function appendSavedBotMessage(agent, content) {
    if (!chatBox) return;
    const botDiv = document.createElement('div');
    botDiv.className = 'message bot-msg';
    const badgeHtml = (window.getAgentBadgeHtml) ? window.getAgentBadgeHtml(agent) : `<div class="agent-badge-wrapper"><span class="agent-label-badge badge-general">${agent || 'Agent'}</span></div><div class="agent-content-body">`;
    botDiv.innerHTML = badgeHtml + content + '</div>';
    if (window.formatCompletedMessage) {
        window.formatCompletedMessage(botDiv);
    }
    chatBox.appendChild(botDiv);
}

// ── Chat Form & Messaging ──────────────────────────────────────

chatForm.addEventListener('submit', async function (e) {
    e.preventDefault();

    if (!currentAuthUser) {
        showToast('Please sign in to send messages.');
        setUnauthenticatedUI();
        return;
    }

    const msg = userInput.value.trim();
    if (!msg) return;

    appendMessage('You', msg, 'user-msg');

    userInput.value = '';
    sendBtn.disabled = true;

    try {
        const body = {
            message: msg,
            provider: modelSelect.value,
            user_id: currentAuthUser.id
        };

        if (currentSessionId) {
            body.session_id = currentSessionId;
        }

        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${currentAuthToken}`
        };

        const res = await fetch('/api/chat', {
            method: 'POST',
            headers,
            body: JSON.stringify(body)
        });

        if (res.status === 401) {
            showToast('Session expired. Please sign in again.');
            handleLogout(false);
            return;
        }

        if (!res.ok) {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        const data = await res.json();
        currentSessionId = data.session_id;

        connectStream(data.session_id);

    } catch (err) {
        appendMessage('Error', err.message, 'error-msg');
        if (window.resetStreamingUI) {
            window.resetStreamingUI();
        } else if (sendBtn) {
            sendBtn.disabled = false;
        }
    }
});

async function newConversation() {
    if (window.isStreaming && typeof window.stopGeneration === 'function') {
        try {
            await window.stopGeneration();
        } catch (e) {}
    }

    currentSessionId = null;

    if (currentAuthToken) {
        try {
            const res = await fetch('/api/chat/new', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${currentAuthToken}`,
                    'Content-Type': 'application/json'
                }
            });
            if (res.ok) {
                const data = await res.json();
                currentSessionId = data.session_id;
            }
        } catch (e) {
            console.warn('Could not reset session on backend:', e);
        }
    }

    const name = currentAuthUser ? (currentAuthUser.name || 'there') : 'there';
    chatBox.innerHTML = `
        <div class="message system-msg welcome-card">
            <div class="welcome-header">
                <div class="welcome-icon">👋</div>
                <div>
                    <h3>New Conversation Started</h3>
                    <p>Welcome, ${name}! Tell me what kind of PG or flat you're looking for, or pick a recommendation below.</p>
                </div>
            </div>
        </div>
    `;
    if (userInput) {
        userInput.value = '';
        userInput.focus();
    }
}

function appendMessage(sender, text, cls) {
    const div = document.createElement('div');
    div.className = 'message ' + cls;
    if (cls === 'user-msg') {
        div.textContent = text;
    } else {
        div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    }
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ── Interactive UI Action Helpers ──────────────────────────────

window.sendQuickPrompt = function(promptText) {
    if (!userInput) return;
    userInput.value = promptText;
    if (sendBtn && !sendBtn.disabled) {
        chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }
};

window.selectProperty = function(propertyIndex, propertyTitle) {
    if (!userInput) return;
    userInput.value = `select ${propertyIndex}`;
    if (sendBtn && !sendBtn.disabled) {
        chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }
};

window.selectSlot = function(dateStr, timeStr) {
    if (!userInput) return;
    userInput.value = `${dateStr} at ${timeStr} book`;
    if (sendBtn && !sendBtn.disabled) {
        chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }
};

window.confirmBooking = function() {
    if (!userInput) return;
    userInput.value = 'yes';
    if (sendBtn && !sendBtn.disabled) {
        chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }
};

window.proceedToCalendar = function() {
    if (!userInput) return;
    userInput.value = 'proceed';
    if (sendBtn && !sendBtn.disabled) {
        chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }
};

// ── Observability & Tracing Logic (LangSmith & Local Traces) ────
let currentTracesList = [];
let selectedTraceId = null;

async function updateTracesCount() {
    const badge = document.getElementById('trace-badge-count');
    if (!badge) return;
    try {
        const res = await fetch('/api/traces?limit=100');
        if (res.ok) {
            const data = await res.json();
            badge.textContent = data.total || '0';
        }
    } catch (e) {
        // quiet ignore
    }
}
window.updateTracesCount = updateTracesCount;

async function openTracesModal() {
    const modal = document.getElementById('traces-modal');
    if (!modal) return;
    modal.classList.remove('hidden');

    const myUserToggleEmail = document.getElementById('trace-current-user-email');
    if (myUserToggleEmail) {
        myUserToggleEmail.textContent = currentAuthUser ? currentAuthUser.email : 'not logged in';
    }

    await fetchLangSmithStatus();
    await fetchAndRenderTraces();
}
window.openTracesModal = openTracesModal;

function closeTracesModal() {
    const modal = document.getElementById('traces-modal');
    if (modal) modal.classList.add('hidden');
}
window.closeTracesModal = closeTracesModal;

function handleTracesBackdropClick(e) {
    if (e.target && e.target.id === 'traces-modal') {
        closeTracesModal();
    }
}
window.handleTracesBackdropClick = handleTracesBackdropClick;

async function fetchLangSmithStatus() {
    const badge = document.getElementById('langsmith-badge');
    const text = document.getElementById('langsmith-text');
    const link = document.getElementById('langsmith-link');
    if (!badge || !text) return;

    try {
        const res = await fetch('/api/traces/config/langsmith');
        if (res.ok) {
            const data = await res.json();
            if (data.langsmith_active) {
                badge.className = 'langsmith-pill active';
                badge.textContent = '☁️ LangSmith Cloud Active';
                text.textContent = `Streaming traces directly to project: "${data.project}"`;
                if (link) {
                    link.href = data.dashboard_url;
                    link.classList.remove('hidden');
                }
            } else {
                badge.className = 'langsmith-pill inactive';
                badge.textContent = '💻 Local Tracing Mode';
                text.textContent = data.instructions;
                if (link) {
                    link.classList.add('hidden');
                }
            }
        }
    } catch (e) {
        badge.className = 'langsmith-pill inactive';
        badge.textContent = 'Traces Ready';
        text.textContent = 'Local trace collector active.';
    }
}
window.fetchLangSmithStatus = fetchLangSmithStatus;

async function fetchAndRenderTraces() {
    const listPane = document.getElementById('traces-list-pane');
    if (!listPane) return;

    const statusFilter = document.getElementById('trace-status-filter')?.value || '';
    const agentFilter = document.getElementById('trace-agent-filter')?.value || '';
    const onlyMyUser = document.getElementById('trace-my-user-filter')?.checked || false;

    let url = '/api/traces?limit=100';
    if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
    if (agentFilter) url += `&agent=${encodeURIComponent(agentFilter)}`;
    if (onlyMyUser && currentAuthUser) {
        url += `&user_id=${encodeURIComponent(currentAuthUser.id)}`;
    }

    listPane.innerHTML = '<div class="traces-loading-state">Loading traces...</div>';

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        currentTracesList = data.traces || [];

        const countBadge = document.getElementById('trace-badge-count');
        if (countBadge) countBadge.textContent = data.total || '0';

        if (currentTracesList.length === 0) {
            listPane.innerHTML = `
                <div class="traces-loading-state" style="padding:40px 20px;">
                    <div style="font-size:28px; margin-bottom:8px;">🔍</div>
                    <strong>No traces found</strong>
                    <p style="margin-top:4px;">Send a message in the chat assistant to generate your first live multi-agent trace!</p>
                </div>
            `;
            const detailPane = document.getElementById('traces-detail-pane');
            if (detailPane) {
                detailPane.innerHTML = `
                    <div class="traces-empty-selection">
                        <span style="font-size:36px;">💬</span>
                        <h4>No trace selected</h4>
                        <p>Traces will appear here once you interact with the chat.</p>
                    </div>
                `;
            }
            return;
        }

        listPane.innerHTML = '';
        currentTracesList.forEach((t) => {
            const isSelected = t.trace_id === selectedTraceId;
            const card = document.createElement('div');
            card.className = `trace-card-item ${isSelected ? 'selected' : ''}`;
            card.id = `trace-item-${t.trace_id}`;
            card.onclick = () => selectTrace(t.trace_id);

            const durationSec = (t.duration_ms / 1000).toFixed(2);
            const agents = (t.agents_invoked || []).map(a => `<span class="flow-agent-chip">${a}</span>`).join('<span class="flow-arrow">➔</span>');
            const timeStr = t.start_time ? new Date(t.start_time).toLocaleTimeString() : 'Just now';

            card.innerHTML = `
                <div class="trace-card-top">
                    <span class="trace-status-tag ${t.status || 'SUCCESS'}">
                        ${t.status === 'SUCCESS' ? '✓' : '⚠'} ${t.status || 'SUCCESS'}
                    </span>
                    <span class="trace-duration-tag">⏱ ${t.duration_ms ? t.duration_ms + 'ms' : durationSec + 's'}</span>
                </div>
                <div class="trace-query-preview" title="${t.user_input || ''}">
                    💬 "${escapeHtml(t.user_input || 'No user input')}"
                </div>
                <div class="trace-flow-row">
                    ${agents || '<span class="flow-agent-chip">supervisor</span>'}
                </div>
                <div class="trace-user-pill">
                    <span>👤 ${t.user_email || 'anonymous'}</span> • <span>🕒 ${timeStr}</span>
                </div>
            `;
            listPane.appendChild(card);
        });

        // Auto-select first trace if none selected
        if (!selectedTraceId && currentTracesList.length > 0) {
            selectTrace(currentTracesList[0].trace_id);
        } else if (selectedTraceId) {
            selectTrace(selectedTraceId);
        }

    } catch (err) {
        listPane.innerHTML = `<div class="traces-loading-state" style="color:var(--danger)">Failed to load traces: ${err.message}</div>`;
    }
}
window.fetchAndRenderTraces = fetchAndRenderTraces;

async function selectTrace(traceId) {
    selectedTraceId = traceId;

    // Highlight selected card
    document.querySelectorAll('.trace-card-item').forEach(el => el.classList.remove('selected'));
    const targetCard = document.getElementById(`trace-item-${traceId}`);
    if (targetCard) targetCard.classList.add('selected');

    const detailPane = document.getElementById('traces-detail-pane');
    if (!detailPane) return;

    detailPane.innerHTML = '<div class="traces-loading-state">Loading trace details & spans...</div>';

    try {
        const res = await fetch(`/api/traces/${traceId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const trace = await res.json();
        renderTraceDetail(trace);
    } catch (err) {
        detailPane.innerHTML = `<div class="traces-loading-state" style="color:var(--danger)">Failed to load details: ${err.message}</div>`;
    }
}
window.selectTrace = selectTrace;

function renderTraceDetail(trace) {
    const detailPane = document.getElementById('traces-detail-pane');
    if (!detailPane) return;

    const spans = trace.spans || [];
    const formattedDate = trace.start_time ? new Date(trace.start_time).toLocaleString() : 'N/A';

    let spansHtml = '';
    if (spans.length === 0) {
        spansHtml = '<div style="color:var(--text-muted); font-size:0.85rem; padding:10px 0;">No granular spans recorded for this trace.</div>';
    } else {
        spansHtml = spans.map((s) => {
            let icon = '⚡';
            if (s.span_type === 'supervisor') icon = '🎯';
            else if (s.span_type === 'agent') icon = '🤖';
            else if (s.span_type === 'tool') icon = '🛠️';
            else if (s.span_type === 'llm') icon = '✨';

            const inputsJson = s.inputs ? JSON.stringify(s.inputs, null, 2) : null;
            const outputsJson = s.outputs ? JSON.stringify(s.outputs, null, 2) : null;

            return `
                <div class="span-card">
                    <div class="span-node-icon">${icon}</div>
                    <div class="span-header">
                        <div>
                            <span class="span-name">${escapeHtml(s.name)}</span>
                            <span class="span-type-badge span-type-${s.span_type}">${s.span_type}</span>
                        </div>
                        <div class="span-time-badge">
                            ⏱ ${s.duration_ms} ms ${s.status === 'ERROR' ? '<span style="color:var(--danger); font-weight:700;">(ERROR)</span>' : ''}
                        </div>
                    </div>
                    <div class="span-body">
                        ${inputsJson ? `
                            <div class="span-data-box">
                                <div class="span-data-label">Inputs & Parameters</div>
                                <div class="span-data-content">${escapeHtml(inputsJson)}</div>
                            </div>
                        ` : ''}
                        ${outputsJson ? `
                            <div class="span-data-box">
                                <div class="span-data-label">Outputs & Returned State</div>
                                <div class="span-data-content">${escapeHtml(outputsJson)}</div>
                            </div>
                        ` : ''}
                        ${s.error ? `
                            <div class="span-data-box" style="border-color:var(--danger-border); background:var(--danger-light);">
                                <div class="span-data-label" style="color:var(--danger)">Error</div>
                                <div class="span-data-content" style="color:var(--danger)">${escapeHtml(s.error)}</div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    const agentsPills = (trace.agents_invoked || []).map(a => `<span class="flow-agent-chip">${a}</span>`).join('<span class="flow-arrow">➔</span>');

    detailPane.innerHTML = `
        <!-- Top Metadata Grid -->
        <div class="trace-meta-grid">
            <div class="meta-field">
                <span class="meta-label">Trace ID</span>
                <span class="meta-value" style="font-family:monospace; font-size:0.75rem;">${trace.trace_id}</span>
            </div>
            <div class="meta-field">
                <span class="meta-label">User Email</span>
                <span class="meta-value">${trace.user_email || 'anonymous'}</span>
            </div>
            <div class="meta-field">
                <span class="meta-label">Endpoint</span>
                <span class="meta-value">${trace.endpoint}</span>
            </div>
            <div class="meta-field">
                <span class="meta-label">Total Latency</span>
                <span class="meta-value" style="color:var(--primary); font-weight:700;">${trace.duration_ms} ms</span>
            </div>
            <div class="meta-field">
                <span class="meta-label">Status</span>
                <span class="meta-value" style="color:${trace.status === 'SUCCESS' ? 'var(--success)' : 'var(--danger)'}">
                    ${trace.status === 'SUCCESS' ? '✓ SUCCESS' : '✕ ' + (trace.error_message || 'ERROR')}
                </span>
            </div>
            <div class="meta-field">
                <span class="meta-label">Started At</span>
                <span class="meta-value" style="font-size:0.75rem;">${formattedDate}</span>
            </div>
        </div>

        <!-- User Prompt Box -->
        <div class="span-data-box" style="background:#f1f5f9; border-color:#cbd5e1;">
            <div class="span-data-label">💬 User Input Query</div>
            <div style="font-weight:600; color:#0f172a; font-size:0.9rem;">
                ${escapeHtml(trace.user_input || '')}
            </div>
        </div>

        <!-- Agent Flow -->
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:0.8rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Agent Invocation Chain:</span>
            <div class="trace-flow-row">${agentsPills || '<span class="flow-agent-chip">supervisor</span>'}</div>
        </div>

        <!-- Spans Section -->
        <div>
            <div class="spans-section-title">
                <span>Execution Timeline &amp; Sub-Agent Spans</span>
                <span style="font-size:0.75rem; font-weight:500; color:var(--text-muted);">(${spans.length} spans recorded)</span>
            </div>
            <div class="spans-timeline">
                ${spansHtml}
            </div>
        </div>

        <!-- Final Agent Output -->
        ${trace.agent_response ? `
            <div class="trace-response-box">
                <div class="trace-response-header">🤖 Final Agent Output</div>
                <div class="trace-response-text">${trace.agent_response}</div>
            </div>
        ` : ''}
    `;
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
