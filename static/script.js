/* ============================================
   WHATSAPP CLONE - COMPLETE JAVASCRIPT
   ============================================ */

// ============================================
// GLOBAL VARIABLES
// ============================================

var username = "";
var currentReceiver = null;
var socket = null;
var typingTimeout = null;
var currentTab = "chats";

// ============================================
// SOCKET.IO CONNECTION
// ============================================

function initSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('✅ Connected to server');
        loadContacts();
        loadStatuses();
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
    
    socket.on('user_online', function(data) {
        updateUserStatus(data.username, true);
        addSystemMessage('✨ ' + data.username + ' is online');
    });
    
    socket.on('user_offline', function(data) {
        updateUserStatus(data.username, false);
        addSystemMessage('👋 ' + data.username + ' went offline');
    });
    
    socket.on('message_history', function(messages) {
        var container = document.getElementById('messages');
        container.innerHTML = '';
        if (messages.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-comment-dots"></i><p>No messages yet. Say hello!</p></div>';
        } else {
            messages.forEach(function(msg) {
                displayMessage(msg.sender, msg.message, msg.timestamp, msg.sender === username);
            });
            scrollToBottom();
        }
    });
    
    socket.on('messages_read', function(data) {
        updateReadReceipts(data.from);
    });
}

// ============================================
// CONTACT MANAGEMENT
// ============================================

function loadContacts() {
    fetch('/api/get_contacts')
        .then(response => response.json())
        .then(contacts => {
            var container = document.getElementById('contactsList');
            if (currentTab === 'chats') {
                if (contacts.length === 0) {
                    container.innerHTML = '<div class="empty-state"><i class="fas fa-users"></i><p>No chats yet.<br>Search for users to start chatting!</p></div>';
                } else {
                    var html = '';
                    contacts.forEach(contact => {
                        var statusText = contact.is_online ? 'Online' : ('Last seen ' + contact.last_seen);
                        var onlineDot = contact.is_online ? '<div class="online-dot"></div>' : '';
                        html += `
                            <div class="contact-item" data-user="${contact.username}" onclick="selectUser('${contact.username}')">
                                <div class="contact-avatar">
                                    ${contact.profile_pic || contact.username.charAt(0).toUpperCase()}
                                    ${onlineDot}
                                </div>
                                <div class="contact-info">
                                    <div class="contact-name">${escapeHtml(contact.full_name || contact.username)}</div>
                                    <div class="contact-last-msg">${escapeHtml(statusText)}</div>
                                </div>
                            </div>
                        `;
                    });
                    container.innerHTML = html;
                }
            }
        })
        .catch(error => console.error('Error loading contacts:', error));
}

function searchUsers() {
    var query = document.getElementById('searchInput').value;
    if (query.length < 1) {
        loadContacts();
        return;
    }
    
    fetch('/api/search_users?q=' + encodeURIComponent(query))
        .then(response => response.json())
        .then(users => {
            var container = document.getElementById('contactsList');
            if (users.length === 0) {
                container.innerHTML = '<div class="empty-state"><i class="fas fa-user-slash"></i><p>No users found</p></div>';
            } else {
                var html = '';
                users.forEach(user => {
                    var onlineDot = user.is_online ? '<div class="online-dot"></div>' : '';
                    html += `
                        <div class="contact-item" onclick="selectUser('${user.username}')">
                            <div class="contact-avatar">
                                ${user.profile_pic || user.username.charAt(0).toUpperCase()}
                                ${onlineDot}
                            </div>
                            <div class="contact-info">
                                <div class="contact-name">${escapeHtml(user.full_name || user.username)}</div>
                                <div class="contact-last-msg">@${escapeHtml(user.username)}</div>
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
        });
}

function globalSearch() {
    var query = document.getElementById('globalSearch').value;
    if (query.length < 1) {
        document.getElementById('searchResults').innerHTML = '';
        return;
    }
    
    fetch('/api/search_users?q=' + encodeURIComponent(query))
        .then(response => response.json())
        .then(users => {
            var container = document.getElementById('searchResults');
            if (users.length === 0) {
                container.innerHTML = '<p style="text-align:center;padding:20px;color:#999;">No users found</p>';
            } else {
                var html = '';
                users.forEach(user => {
                    html += `
                        <div class="contact-item" onclick="selectUser('${user.username}'); closeSearchModal();">
                            <div class="contact-avatar">${user.profile_pic || user.username.charAt(0).toUpperCase()}</div>
                            <div class="contact-info">
                                <div class="contact-name">${escapeHtml(user.full_name || user.username)}</div>
                                <div class="contact-last-msg">@${escapeHtml(user.username)}</div>
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
    
    // Update UI
    document.getElementById('chatContactName').innerText = user;
    document.getElementById('chatContactStatus').innerText = 'Online';
    document.getElementById('chatArea').style.display = 'flex';
    
    // Highlight selected contact
    document.querySelectorAll('.contact-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-user') === user) {
            item.classList.add('active');
        }
    });
    
    // Load chat history
    socket.emit('get_history', { with: user });
    
    // Mark messages as read
    markMessagesAsRead(user);
    
    // Focus input
    document.getElementById('messageInput').focus();
}

function sendMessage() {
    var input = document.getElementById('messageInput');
    var message = input.value.trim();
    
    if (!message) return;
    if (!currentReceiver) {
        alert('Please select a user to chat with');
        return;
    }
    
    var time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    socket.emit('private_message', {
        to: currentReceiver,
        message: message
    });
    
    displayMessage(username, message, time, true);
    input.value = '';
    scrollToBottom();
    
    // Stop typing indicator
    clearTimeout(typingTimeout);
    socket.emit('typing_stop', { to: currentReceiver });
}

function displayMessage(sender, text, time, isSent) {
    var container = document.getElementById('messages');
    
    // Remove empty state if present
    var emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    var messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + (isSent ? 'sent' : 'received');
    
    messageDiv.innerHTML = `
        <div class="bubble">
            ${!isSent ? '<div class="message-name">' + escapeHtml(sender) + '</div>' : ''}
            <div class="msg-text">${escapeHtml(text)}</div>
            <div class="msg-time">
                ${time}
                ${isSent ? '<i class="fas fa-check-double"></i>' : ''}
            </div>
        </div>
    `;
    
    container.appendChild(messageDiv);
}

function markMessagesAsRead(user) {
    socket.emit('mark_read', { from: user });
}

function updateReadReceipts(user) {
    // Update read receipts for messages from user
    var messages = document.querySelectorAll('.message.received');
    messages.forEach(msg => {
        var nameElement = msg.querySelector('.message-name');
        if (nameElement && nameElement.innerText === user) {
            var timeElement = msg.querySelector('.msg-time');
            if (timeElement) {
                var checkIcon = timeElement.querySelector('.fa-check-double');
                if (checkIcon) checkIcon.style.color = '#34b7f1';
            }
        }
    });
}

// ============================================
// TYPING INDICATOR
// ============================================

function showTypingIndicator(user) {
    var typingDiv = document.getElementById('typingIndicator');
    typingDiv.innerHTML = `
        <div class="typing-dots">
            <span></span><span></span><span></span>
        </div>
        <span>${escapeHtml(user)} is typing...</span>
    `;
}

function hideTypingIndicator() {
    document.getElementById('typingIndicator').innerHTML = '';
}

// ============================================
// STATUS MANAGEMENT
// ============================================

function loadStatuses() {
    fetch('/api/get_statuses')
        .then(response => response.json())
        .then(statuses => {
            var container = document.getElementById('contactsList');
            if (currentTab === 'status') {
                var html = `
                    <div class="status-item" onclick="openStatusModal()">
                        <div class="contact-avatar status-ring">📷</div>
                        <div class="contact-info">
                            <div class="contact-name">My Status</div>
                            <div class="contact-last-msg">Tap to add status update</div>
                        </div>
                    </div>
                `;
                
                if (statuses.length === 0) {
                    html += '<div class="empty-state"><i class="fas fa-camera"></i><p>No status updates<br>Tap above to add your status</p></div>';
                } else {
                    statuses.forEach(status => {
                        html += `
                            <div class="status-item" onclick="viewStatus(${status.id})">
                                <div class="contact-avatar status-ring">${status.content_type === 'text' ? '📝' : '📷'}</div>
                                <div class="contact-info">
                                    <div class="contact-name">${escapeHtml(status.username)}</div>
                                    <div class="contact-last-msg">${escapeHtml(status.content.substring(0, 40))}</div>
                                </div>
                                <div class="contact-time">${status.time_ago}</div>
                            </div>
                        `;
                    });
                }
                container.innerHTML = html;
            }
        });
}

function postStatus() {
    var content = document.getElementById('statusContent').value;
    if (!content) {
        alert('Please enter a status');
        return;
    }
    
    fetch('/api/post_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content, content_type: 'text' })
    })
    .then(response => response.json())
    .then(() => {
        closeStatusModal();
        loadStatuses();
        document.getElementById('statusContent').value = '';
    });
}

function viewStatus(statusId) {
    fetch('/api/view_status/' + statusId, { method: 'POST' })
        .then(() => {
            // Show status in modal
            alert('Status viewed!');
        });
}

// ============================================
// PROFILE MANAGEMENT
// ============================================

function updateProfile() {
    var data = {
        full_name: document.getElementById('editFullName').value,
        bio: document.getElementById('editBio').value,
        profile_pic: document.getElementById('editProfilePic').value
    };
    
    fetch('/api/update_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(() => {
        closeProfileModal();
        location.reload();
    });
}

// ============================================
// UI HELPER FUNCTIONS
// ============================================

function switchTab(tab) {
    currentTab = tab;
    
    // Update tab UI
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    if (tab === 'chats') {
        document.querySelector('.tab:first-child').classList.add('active');
        loadContacts();
    } else if (tab === 'status') {
        document.querySelector('.tab:nth-child(2)').classList.add('active');
        loadStatuses();
    } else if (tab === 'calls') {
        document.querySelector('.tab:nth-child(3)').classList.add('active');
        document.getElementById('contactsList').innerHTML = '<div class="empty-state"><i class="fas fa-phone-slash"></i><p>No call history</p></div>';
    }
}

function addEmoji() {
    var emojis = ['😀','😂','😍','🔥','👍','🎉','❤️','😎','✨','💯','🥰','🤣','😭','🙌','💪','👋','🙏','💀','🤡','👻','🐱','🐶','🦊','🐼','🐨'];
    var emoji = emojis[Math.floor(Math.random() * emojis.length)];
    var input = document.getElementById('messageInput');
    input.value += emoji;
    input.focus();
}

function scrollToBottom() {
    var container = document.getElementById('messages');
    container.scrollTop = container.scrollHeight;
}

function addSystemMessage(message) {
    var container = document.getElementById('messages');
    var emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    var systemDiv = document.createElement('div');
    systemDiv.className = 'system-message';
    systemDiv.innerHTML = `<span>${escapeHtml(message)}</span>`;
    container.appendChild(systemDiv);
    scrollToBottom();
    
    setTimeout(() => {
        if (systemDiv) systemDiv.remove();
    }, 3000);
}

function showNotificationBadge(user) {
    var contact = document.querySelector(`.contact-item[data-user="${user}"]`);
    if (contact && !contact.classList.contains('active')) {
        var badge = document.createElement('div');
        badge.className = 'notification-badge';
        badge.innerHTML = '●';
        badge.style.cssText = 'color:#25D366;font-size:12px;margin-left:auto;';
        if (!contact.querySelector('.notification-badge')) {
            contact.appendChild(badge);
        }
    }
}

function updateUserStatus(username, isOnline) {
    var contact = document.querySelector(`.contact-item[data-user="${username}"]`);
    if (contact) {
        var avatar = contact.querySelector('.contact-avatar');
        if (isOnline) {
            if (!avatar.querySelector('.online-dot')) {
                var dot = document.createElement('div');
                dot.className = 'online-dot';
                avatar.appendChild(dot);
            }
            var statusText = contact.querySelector('.contact-last-msg');
            if (statusText) statusText.innerText = 'Online';
        } else {
            var dot = avatar.querySelector('.online-dot');
            if (dot) dot.remove();
        }
    }
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// MODAL FUNCTIONS
// ============================================

function openProfileModal() { document.getElementById('profileModal').style.display = 'flex'; }
function closeProfileModal() { document.getElementById('profileModal').style.display = 'none'; }
function openSearchModal() { document.getElementById('searchModal').style.display = 'flex'; }
function closeSearchModal() { document.getElementById('searchModal').style.display = 'none'; }
function openStatusModal() { document.getElementById('statusModal').style.display = 'flex'; }
function closeStatusModal() { document.getElementById('statusModal').style.display = 'none'; }

function logout() {
    window.location.href = '/logout';
}

// ============================================
// EVENT LISTENERS
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    initSocket();
    
    // Message input events
    var messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });
        
        messageInput.addEventListener('input', function() {
            if (!currentReceiver) return;
            socket.emit('typing', { to: currentReceiver });
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(function() {
                socket.emit('typing_stop', { to: currentReceiver });
            }, 1000);
        });
    }
    
    // Search input events
    var searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', searchUsers);
    }
    
    var globalSearchInput = document.getElementById('globalSearch');
    if (globalSearchInput) {
        globalSearchInput.addEventListener('input', globalSearch);
    }
    
    // Click outside modal to close
    window.onclick = function(event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    };
});

// Auto-refresh contacts every 10 seconds
setInterval(function() {
    if (currentTab === 'chats') loadContacts();
    else if (currentTab === 'status') loadStatuses();
}, 10000);
