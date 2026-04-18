/* ============================================
   WHATSAPP CLONE - COMPLETE JAVASCRIPT
   ============================================ */

// ============================================
// GLOBAL VARIABLES
// ============================================

let username = "";
let currentReceiver = null;
let socket = null;
let typingTimeout = null;
let messageElements = {};

// ============================================
// SOCKET.IO CONNECTION
// ============================================

function initSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('✅ Connected to server as:', username);
        loadContacts();
        loadOnlineUsers();
    });
    
    socket.on('users_list', function(users) {
        updateContactsList(users);
    });
    
    socket.on('user_status', function(data) {
        updateUserStatus(data.username, data.is_online, data.last_seen);
        if (currentReceiver === data.username) {
            updateChatStatus(data.is_online ? 'Online' : 'Last seen ' + data.last_seen);
        }
    });
    
    socket.on('receive_message', function(data) {
        if (currentReceiver === data.from) {
            displayMessage(data.from, data.message, data.timestamp, false);
            scrollToBottom();
            markMessagesAsRead(data.from);
        } else {
            showNotificationBadge(data.from);
        }
        loadContacts();
        playNotificationSound();
    });
    
    socket.on('message_delivered', function(data) {
        updateMessageStatus(data.message_id, 'delivered');
    });
    
    socket.on('messages_read', function(data) {
        updateAllMessagesRead(data.from);
    });
    
    socket.on('user_typing', function(data) {
        if (currentReceiver === data.from) {
            showTypingIndicator(data.from);
        }
    });
    
    socket.on('user_stop_typing', function(data) {
        if (currentReceiver === data.from) {
            hideTypingIndicator();
        }
    });
    
    socket.on('message_history', function(messages) {
        const container = document.getElementById('messages');
        container.innerHTML = '';
        if (messages.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-comment-dots"></i><p>No messages yet. Say hello!</p></div>';
        } else {
            messages.forEach(function(msg) {
                displayMessage(msg.sender, msg.message, msg.timestamp, msg.sender === username, msg.read, msg.delivered);
            });
            scrollToBottom();
        }
    });
}

// ============================================
// CONTACT & SEARCH FUNCTIONS
// ============================================

function loadContacts() {
    fetch('/api/contacts')
        .then(response => response.json())
        .then(contacts => {
            const container = document.getElementById('contactsList');
            if (contacts.length === 0) {
                container.innerHTML = '<div class="empty-state"><i class="fas fa-users"></i><p>No contacts yet.<br>Search for users to start chatting!</p></div>';
            } else {
                let html = '';
                contacts.forEach(contact => {
                    const statusText = contact.is_online ? 'Online' : ('Last seen ' + contact.last_seen);
                    html += `
                        <div class="contact" data-user="${contact.username}" onclick="selectUser('${contact.username}')">
                            <div class="avatar">${contact.username.charAt(0).toUpperCase()}${contact.is_online ? '<div class="online-dot"></div>' : ''}</div>
                            <div class="contact-info">
                                <div class="contact-name">${escapeHtml(contact.username)}</div>
                                <div class="contact-status">${escapeHtml(statusText)}</div>
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
        })
        .catch(error => console.error('Error loading contacts:', error));
}

function loadOnlineUsers() {
    if (socket) {
        socket.emit('get_online_users');
    }
}

function updateContactsList(users) {
    const container = document.getElementById('contactsList');
    if (users.length === 0) return;
    
    let html = '';
    users.forEach(user => {
        const statusText = user.is_online ? 'Online' : ('Last seen ' + user.last_seen);
        html += `
            <div class="contact" data-user="${user.username}" onclick="selectUser('${user.username}')">
                <div class="avatar">${user.username.charAt(0).toUpperCase()}${user.is_online ? '<div class="online-dot"></div>' : ''}</div>
                <div class="contact-info">
                    <div class="contact-name">${escapeHtml(user.username)}</div>
                    <div class="contact-status">${escapeHtml(statusText)}</div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function searchUsers() {
    const query = document.getElementById('searchInput').value.trim();
    const resultsDiv = document.getElementById('searchResults');
    
    if (query.length < 1) {
        resultsDiv.style.display = 'none';
        return;
    }
    
    fetch('/api/search?q=' + encodeURIComponent(query))
        .then(response => response.json())
        .then(users => {
            if (users.length === 0) {
                resultsDiv.innerHTML = '<div style="padding:12px;text-align:center;color:#999;">No users found</div>';
                resultsDiv.style.display = 'block';
            } else {
                let html = '';
                users.forEach(user => {
                    html += `
                        <div class="search-result-item" onclick="selectUser('${user.username}'); document.getElementById('searchResults').style.display='none'; document.getElementById('searchInput').value='';">
                            <div class="avatar" style="width:40px;height:40px;font-size:16px;">${user.username.charAt(0).toUpperCase()}</div>
                            <div>
                                <div style="font-weight:600;">${escapeHtml(user.username)}</div>
                                <div style="font-size:12px;color:#6c757d;">${user.is_online ? 'Online' : 'Last seen ' + user.last_seen}</div>
                            </div>
                        </div>
                    `;
                });
                resultsDiv.innerHTML = html;
                resultsDiv.style.display = 'block';
            }
        });
}

function globalSearch() {
    const query = document.getElementById('globalSearch').value.trim();
    const container = document.getElementById('globalSearchResults');
    
    if (query.length < 1) {
        container.innerHTML = '';
        return;
    }
    
    fetch('/api/search?q=' + encodeURIComponent(query))
        .then(response => response.json())
        .then(users => {
            if (users.length === 0) {
                container.innerHTML = '<p style="text-align:center;padding:20px;color:#999;">No users found</p>';
            } else {
                let html = '';
                users.forEach(user => {
                    html += `
                        <div style="padding:12px;border-bottom:1px solid #eee;display:flex;align-items:center;gap:12px;cursor:pointer;" onclick="selectUser('${user.username}'); closeSearchModal();">
                            <div style="width:40px;height:40px;background:linear-gradient(135deg,#075E54,#128C7E);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:600;">${user.username.charAt(0).toUpperCase()}</div>
                            <div>
                                <div style="font-weight:600;">${escapeHtml(user.username)}</div>
                                <div style="font-size:12px;color:#6c757d;">${user.is_online ? 'Online' : 'Last seen ' + user.last_seen}</div>
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
        });
}

// ============================================
// CHAT FUNCTIONS
// ============================================

function selectUser(user) {
    currentReceiver = user;
    
    document.getElementById('chatArea').style.display = 'flex';
    document.getElementById('chatContactName').innerText = user;
    document.getElementById('chatContactStatus').innerText = 'Online';
    
    document.querySelectorAll('.contact').forEach(c => c.classList.remove('active'));
    const activeContact = document.querySelector(`.contact[data-user="${user}"]`);
    if (activeContact) activeContact.classList.add('active');
    
    if (socket) {
        socket.emit('get_history', { with: user });
        markMessagesAsRead(user);
    }
    
    document.getElementById('messageInput').focus();
    
    // Clear search results
    document.getElementById('searchResults').style.display = 'none';
    document.getElementById('searchInput').value = '';
}

function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !currentReceiver) return;
    
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const messageId = Date.now();
    
    displayMessage(username, message, time, true, false, true);
    
    if (socket) {
        socket.emit('private_message', { to: currentReceiver, message: message });
    }
    
    input.value = '';
    scrollToBottom();
    
    clearTimeout(typingTimeout);
    if (socket) {
        socket.emit('typing_stop', { to: currentReceiver });
    }
}

function displayMessage(sender, text, time, isSent, isRead, isDelivered) {
    const container = document.getElementById('messages');
    const empty = container.querySelector('.empty-state');
    if (empty) empty.remove();
    
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ' + (isSent ? 'sent' : 'received');
    msgDiv.setAttribute('data-sender', sender);
    
    let tickHtml = '';
    if (isSent) {
        if (isRead) {
            tickHtml = '<i class="fas fa-check-double blue-tick"></i>';
        } else if (isDelivered) {
            tickHtml = '<i class="fas fa-check-double"></i>';
        } else {
            tickHtml = '<i class="fas fa-check"></i>';
        }
    }
    
    msgDiv.innerHTML = `
        <div class="bubble">
            ${!isSent ? '<div class="message-name">' + escapeHtml(sender) + '</div>' : ''}
            <div class="msg-text">${escapeHtml(text)}</div>
            <div class="msg-time">${time} ${tickHtml}</div>
        </div>
    `;
    
    container.appendChild(msgDiv);
}

function markMessagesAsRead(user) {
    if (socket) {
        socket.emit('mark_read', { from: user });
    }
}

function updateMessageStatus(messageId, status) {
    const messages = document.querySelectorAll('.message.sent');
    const lastMsg = messages[messages.length - 1];
    if (lastMsg) {
        const timeDiv = lastMsg.querySelector('.msg-time');
        if (timeDiv && status === 'delivered') {
            const checkIcon = timeDiv.querySelector('.fa-check');
            if (checkIcon) {
                checkIcon.className = 'fas fa-check-double';
            }
        }
    }
}

function updateAllMessagesRead(fromUser) {
    const messages = document.querySelectorAll('.message.sent');
    messages.forEach(msg => {
        const timeDiv = msg.querySelector('.msg-time');
        if (timeDiv) {
            const icon = timeDiv.querySelector('.fa-check-double');
            if (icon) icon.classList.add('blue-tick');
        }
    });
}

// ============================================
// UI HELPER FUNCTIONS
// ============================================

function updateUserStatus(user, isOnline, lastSeen) {
    const contact = document.querySelector(`.contact[data-user="${user}"]`);
    if (contact) {
        const statusDiv = contact.querySelector('.contact-status');
        if (statusDiv) {
            statusDiv.innerText = isOnline ? 'Online' : ('Last seen ' + lastSeen);
        }
        
        const avatar = contact.querySelector('.avatar');
        if (avatar) {
            if (isOnline && !avatar.querySelector('.online-dot')) {
                const dot = document.createElement('div');
                dot.className = 'online-dot';
                avatar.appendChild(dot);
            } else if (!isOnline) {
                const dot = avatar.querySelector('.online-dot');
                if (dot) dot.remove();
            }
        }
    }
}

function updateChatStatus(status) {
    const statusElement = document.getElementById('chatContactStatus');
    if (statusElement) {
        statusElement.innerText = status;
    }
}

function showTypingIndicator(user) {
    const typingDiv = document.getElementById('typingIndicator');
    if (typingDiv) {
        typingDiv.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div> ${escapeHtml(user)} is typing...`;
    }
}

function hideTypingIndicator() {
    const typingDiv = document.getElementById('typingIndicator');
    if (typingDiv) {
        typingDiv.innerHTML = '';
    }
}

function showNotificationBadge(user) {
    const contact = document.querySelector(`.contact[data-user="${user}"]`);
    if (contact && !contact.classList.contains('active')) {
        const statusDiv = contact.querySelector('.contact-status');
        if (statusDiv && !statusDiv.innerText.includes('●')) {
            statusDiv.innerText = '● New message ●';
            statusDiv.style.color = '#25D366';
        }
    }
}

function addEmoji() {
    const emojis = ['😀','😂','😍','🔥','👍','🎉','❤️','😎','✨','💯','🥰','🤣','😭','🙌','💪','👋','🙏','💀','🤡','👻','🐱','🐶','🦊','🐼','🐨'];
    const emoji = emojis[Math.floor(Math.random() * emojis.length)];
    const input = document.getElementById('messageInput');
    input.value += emoji;
    input.focus();
}

function scrollToBottom() {
    const container = document.getElementById('messages');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function playNotificationSound() {
    try {
        const audio = new Audio('data:audio/wav;base64,U3RlYWx0aCBzb3VuZA==');
        audio.play().catch(e => {});
    } catch(e) {}
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// MODAL FUNCTIONS
// ============================================

function openSearchModal() {
    const modal = document.getElementById('searchModal');
    if (modal) modal.style.display = 'flex';
}

function closeSearchModal() {
    const modal = document.getElementById('searchModal');
    if (modal) modal.style.display = 'none';
}

function openProfileModal() {
    const modal = document.getElementById('profileModal');
    if (modal) modal.style.display = 'flex';
}

function closeProfileModal() {
    const modal = document.getElementById('profileModal');
    if (modal) modal.style.display = 'none';
}

function logout() {
    window.location.href = '/logout';
}

// ============================================
// REGISTER PAGE VALIDATION
// ============================================

function validateUsername() {
    const username = document.getElementById('username');
    if (!username) return;
    
    const value = username.value.trim();
    const validationDiv = document.getElementById('usernameValidation');
    
    if (value.length === 0) {
        validationDiv.innerHTML = '';
        return false;
    }
    
    if (value.length < 3) {
        validationDiv.innerHTML = '<i class="fas fa-times-circle"></i> Username must be at least 3 characters';
        validationDiv.className = 'validation-message invalid';
        username.classList.add('invalid');
        username.classList.remove('valid');
        return false;
    }
    
    if (!/^[a-zA-Z0-9_]+$/.test(value)) {
        validationDiv.innerHTML = '<i class="fas fa-times-circle"></i> Only letters, numbers, and underscore';
        validationDiv.className = 'validation-message invalid';
        username.classList.add('invalid');
        username.classList.remove('valid');
        return false;
    }
    
    validationDiv.innerHTML = '<i class="fas fa-check-circle"></i> Username available';
    validationDiv.className = 'validation-message valid';
    username.classList.add('valid');
    username.classList.remove('invalid');
    return true;
}

function validatePassword() {
    const password = document.getElementById('password');
    if (!password) return;
    
    const value = password.value;
    const validationDiv = document.getElementById('passwordValidation');
    const strengthDiv = document.getElementById('passwordStrength');
    
    if (value.length === 0) {
        validationDiv.innerHTML = '';
        strengthDiv.innerHTML = '';
        return false;
    }
    
    let strength = 0;
    if (value.length >= 8) strength++;
    if (/[A-Z]/.test(value)) strength++;
    if (/[a-z]/.test(value)) strength++;
    if (/[0-9]/.test(value)) strength++;
    if (/[^A-Za-z0-9]/.test(value)) strength++;
    
    const strengthPercent = (strength / 5) * 100;
    let strengthText = '', strengthColor = '';
    
    if (strength <= 2) { strengthText = 'Weak'; strengthColor = '#dc3545'; }
    else if (strength <= 3) { strengthText = 'Medium'; strengthColor = '#ffc107'; }
    else if (strength <= 4) { strengthText = 'Strong'; strengthColor = '#28a745'; }
    else { strengthText = 'Very Strong'; strengthColor = '#20c997'; }
    
    strengthDiv.innerHTML = `
        <div class="strength-bar" style="width: ${strengthPercent}%; background: ${strengthColor};"></div>
        <div class="strength-text" style="color: ${strengthColor};">${strengthText} password</div>
    `;
    
    if (strength >= 4) {
        validationDiv.innerHTML = '<i class="fas fa-check-circle"></i> Strong password';
        validationDiv.className = 'validation-message valid';
        password.classList.add('valid');
        password.classList.remove('invalid');
        return true;
    } else {
        validationDiv.innerHTML = '<i class="fas fa-times-circle"></i> Use 8+ chars, uppercase, number, special';
        validationDiv.className = 'validation-message invalid';
        password.classList.add('invalid');
        password.classList.remove('valid');
        return false;
    }
}

function validateConfirmPassword() {
    const password = document.getElementById('password');
    const confirm = document.getElementById('confirmPassword');
    if (!password || !confirm) return;
    
    const validationDiv = document.getElementById('confirmValidation');
    
    if (confirm.value.length === 0) {
        validationDiv.innerHTML = '';
        return false;
    }
    
    if (password.value === confirm.value) {
        validationDiv.innerHTML = '<i class="fas fa-check-circle"></i> Passwords match';
        validationDiv.className = 'validation-message valid';
        confirm.classList.add('valid');
        confirm.classList.remove('invalid');
        return true;
    } else {
        validationDiv.innerHTML = '<i class="fas fa-times-circle"></i> Passwords do not match';
        validationDiv.className = 'validation-message invalid';
        confirm.classList.add('invalid');
        confirm.classList.remove('valid');
        return false;
    }
}

// ============================================
// EVENT LISTENERS
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // Chat page elements
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', searchUsers);
    }
    
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });
        
        messageInput.addEventListener('input', function() {
            if (!currentReceiver || !socket) return;
            socket.emit('typing_start', { to: currentReceiver });
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(function() {
                socket.emit('typing_stop', { to: currentReceiver });
            }, 1000);
        });
    }
    
    // Register page elements
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.addEventListener('input', validateUsername);
    }
    
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.addEventListener('input', validatePassword);
    }
    
    const confirmInput = document.getElementById('confirmPassword');
    if (confirmInput) {
        confirmInput.addEventListener('input', validateConfirmPassword);
    }
    
    const termsCheckbox = document.getElementById('termsCheckbox');
    const submitBtn = document.getElementById('submitBtn');
    
    if (termsCheckbox && submitBtn) {
        function updateSubmitButton() {
            const isUsernameValid = document.getElementById('username')?.classList.contains('valid') || false;
            const isPasswordValid = document.getElementById('password')?.classList.contains('valid') || false;
            const isConfirmValid = document.getElementById('confirmPassword')?.classList.contains('valid') || false;
            const isTermsAccepted = termsCheckbox.checked;
            
            submitBtn.disabled = !(isUsernameValid && isPasswordValid && isConfirmValid && isTermsAccepted);
        }
        
        termsCheckbox.addEventListener('change', updateSubmitButton);
        usernameInput?.addEventListener('input', updateSubmitButton);
        passwordInput?.addEventListener('input', updateSubmitButton);
        confirmInput?.addEventListener('input', updateSubmitButton);
    }
    
    // Click outside search results
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.search-bar')) {
            const results = document.getElementById('searchResults');
            if (results) results.style.display = 'none';
        }
    });
    
    // Initialize socket for chat page
    if (document.getElementById('chatArea')) {
        username = document.body.getAttribute('data-username') || '{{ username }}';
        initSocket();
        setInterval(loadContacts, 10000);
    }
});

// Password visibility toggle
function togglePasswordVisibility(inputId, iconElement) {
    const input = document.getElementById(inputId);
    if (input) {
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        iconElement.classList.toggle('fa-eye');
        iconElement.classList.toggle('fa-eye-slash');
    }
}
