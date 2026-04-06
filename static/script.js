// Socket.IO connection
var socket = io();
var currentReceiver = null;
var typingTimeout = null;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadUsers();
    setupEventListeners();
});

// Socket events
socket.on('connect', function() {
    console.log('Connected to server');
});

socket.on('users_list', function(users) {
    updateUsersList(users);
});

socket.on('receive_message', function(data) {
    if (currentReceiver === data.from) {
        displayMessage(data.from, data.message, data.timestamp, false);
        playNotificationSound();
    } else {
        showNotificationBadge(data.from);
    }
    saveMessageToStorage(data.from, data.message, data.timestamp, false);
});

socket.on('user_joined', function(data) {
    addSystemMessage(data.username + ' joined the chat');
    loadUsers();
});

socket.on('user_left', function(username) {
    addSystemMessage(username + ' left the chat');
    loadUsers();
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
    messages.forEach(function(msg) {
        displayMessage(msg.sender, msg.message, msg.time, msg.sender === username);
    });
});

// Load users from server
function loadUsers() {
    socket.emit('get_users');
}

// Update users list in sidebar
function updateUsersList(users) {
    var usersList = document.getElementById('usersList');
    if (!usersList) return;
    
    usersList.innerHTML = '';
    
    if (users.length === 0) {
        usersList.innerHTML = '<div class="empty-state">No other users online</div>';
        return;
    }
    
    users.forEach(function(user) {
        var userDiv = document.createElement('div');
        userDiv.className = 'user-item';
        userDiv.setAttribute('data-user', user.id);
        userDiv.setAttribute('data-name', user.name || user.id);
        
        userDiv.innerHTML = `
            <div class="avatar small">${(user.name || user.id).charAt(0).toUpperCase()}</div>
            <div class="user-info">
                <div class="name">${escapeHtml(user.name || user.id)}</div>
                <div class="last-msg">Click to chat</div>
            </div>
            <div class="notification-badge" style="display:none;">●</div>
        `;
        
        userDiv.onclick = (function(u) {
            return function() { selectUser(u.id, u.name || u.id); };
        })(user);
        
        usersList.appendChild(userDiv);
    });
}

// Select user to chat with
function selectUser(userId, userName) {
    currentReceiver = userId;
    
    // Update header
    document.getElementById('selectedUserName').innerText = userName;
    document.getElementById('chatHeader').style.display = 'flex';
    
    // Highlight active user
    document.querySelectorAll('.user-item').forEach(function(item) {
        item.classList.remove('active');
        if (item.getAttribute('data-user') === userId) {
            item.classList.add('active');
            // Hide notification badge
            var badge = item.querySelector('.notification-badge');
            if (badge) badge.style.display = 'none';
        }
    });
    
    // Load chat history
    loadChatHistory(userId);
    
    // Clear messages container
    var messagesDiv = document.getElementById('messages');
    if (messagesDiv) {
        messagesDiv.innerHTML = '';
    }
    
    // Load stored messages
    loadStoredMessages(userId);
    
    // Focus on input
    document.getElementById('msg')?.focus();
}

// Load chat history from server
function loadChatHistory(userId) {
    socket.emit('get_history', { with: userId });
}

// Load stored messages from localStorage
function loadStoredMessages(userId) {
    var stored = localStorage.getItem('chat_' + username + '_' + userId);
    if (stored) {
        var messages = JSON.parse(stored);
        messages.forEach(function(msg) {
            displayMessage(msg.sender, msg.text, msg.time, msg.sender === username);
        });
    }
}

// Save message to localStorage
function saveMessageToStorage(receiver, text, time, isSent) {
    var key = 'chat_' + username + '_' + (isSent ? receiver : currentReceiver);
    var stored = localStorage.getItem(key);
    var messages = stored ? JSON.parse(stored) : [];
    
    messages.push({
        sender: isSent ? username : receiver,
        text: text,
        time: time,
        isSent: isSent
    });
    
    // Keep only last 100 messages
    if (messages.length > 100) messages.shift();
    localStorage.setItem(key, JSON.stringify(messages));
}

// Send message
function sendMessage() {
    var input = document.getElementById('msg');
    var message = input.value.trim();
    
    if (!message) return;
    if (!currentReceiver) {
        alert('Please select a user to chat with');
        return;
    }
    
    var time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Send via socket
    socket.emit('private_message', {
        to: currentReceiver,
        message: message,
        timestamp: time
    });
    
    // Display message locally
    displayMessage(username, message, time, true);
    saveMessageToStorage(currentReceiver, message, time, true);
    
    // Clear input
    input.value = '';
    input.focus();
    
    // Stop typing indicator
    if (typingTimeout) clearTimeout(typingTimeout);
    socket.emit('typing_stop', { to: currentReceiver });
}

// Display message in chat
function displayMessage(sender, text, time, isSent) {
    var messagesDiv = document.getElementById('messages');
    if (!messagesDiv) return;
    
    // Remove empty state if present
    var emptyState = messagesDiv.querySelector('.empty-chat');
    if (emptyState) emptyState.remove();
    
    var messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + (isSent ? 'sent' : 'received');
    
    messageDiv.innerHTML = `
        <div class="bubble">
            ${!isSent ? '<div class="message-name">' + escapeHtml(sender) + '</div>' : ''}
            <div class="msg-text">${escapeHtml(text)}</div>
            <div class="msg-time">${time} ${isSent ? '<i class="fas fa-check"></i>' : ''}</div>
        </div>
    `;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Show typing indicator
function showTypingIndicator(user) {
    var typingDiv = document.getElementById('typing');
    if (typingDiv) {
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <span class="typing-dots">
                    <span></span><span></span><span></span>
                </span>
                <span>${escapeHtml(user)} is typing...</span>
            </div>
        `;
    }
}

// Hide typing indicator
function hideTypingIndicator() {
    var typingDiv = document.getElementById('typing');
    if (typingDiv) {
        typingDiv.innerHTML = '';
    }
}

// Add system message
function addSystemMessage(message) {
    var messagesDiv = document.getElementById('messages');
    if (!messagesDiv) return;
    
    var systemDiv = document.createElement('div');
    systemDiv.className = 'system-message';
    systemDiv.innerHTML = `<span>${escapeHtml(message)}</span>`;
    messagesDiv.appendChild(systemDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Show notification badge on user item
function showNotificationBadge(userId) {
    var userItems = document.querySelectorAll('.user-item');
    userItems.forEach(function(item) {
        if (item.getAttribute('data-user') === userId && !item.classList.contains('active')) {
            var badge = item.querySelector('.notification-badge');
            if (badge) badge.style.display = 'inline-block';
        }
    });
}

// Play notification sound
function playNotificationSound() {
    // Simple beep using Web Audio (optional)
    try {
        var audio = new Audio('data:audio/wav;base64,U3RlYWx0aCBzb3VuZA==');
        audio.play().catch(function(e) {});
    } catch(e) {}
}

// Add emoji to input
function addEmoji() {
    var emojis = ['😀', '😂', '😍', '🔥', '👍', '🎉', '❤️', '😎', '✨', '💯', '🥰', '🤣', '😭', '🙌', '💪'];
    var emoji = emojis[Math.floor(Math.random() * emojis.length)];
    var input = document.getElementById('msg');
    input.value += emoji;
    input.focus();
}

// Setup event listeners
function setupEventListeners() {
    // Send on Enter key
    var msgInput = document.getElementById('msg');
    if (msgInput) {
        msgInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Typing indicator
        msgInput.addEventListener('input', function() {
            if (!currentReceiver) return;
            
            socket.emit('typing', { to: currentReceiver });
            
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(function() {
                socket.emit('typing_stop', { to: currentReceiver });
            }, 1000);
        });
    }
    
    // Search users
    var searchInput = document.getElementById('searchUsers');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            var searchTerm = e.target.value.toLowerCase();
            var users = document.querySelectorAll('.user-item');
            users.forEach(function(user) {
                var name = user.querySelector('.name')?.innerText.toLowerCase() || '';
                if (name.includes(searchTerm)) {
                    user.style.display = 'flex';
                } else {
                    user.style.display = 'none';
                }
            });
        });
    }
    
    // Logout button
    var logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            socket.emit('disconnect');
            window.location.href = '/logout';
        });
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Refresh users list periodically
setInterval(function() {
    if (socket.connected) {
        socket.emit('get_users');
    }
}, 10000);

// Handle page visibility (mark messages as read)
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && currentReceiver) {
        socket.emit('mark_read', { with: currentReceiver });
    }
});

// Export functions for global use
window.sendMessage = sendMessage;
window.addEmoji = addEmoji;
window.selectUser = selectUser;
