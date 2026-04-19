from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, Message, Status, Call
from datetime import datetime
import bcrypt
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whatsapp-clone-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

online_users = {}
user_sessions = {}

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password):
            session['user_id'] = user.id
            session['username'] = user.username
            user.is_online = True
            user.last_seen = datetime.now()
            db.session.commit()
            flash('✅ Login successful!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('❌ Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form.get('full_name', '')
        phone = request.form.get('phone', '')
        
        if User.query.filter_by(username=username).first():
            flash('❌ Username exists!', 'error')
        else:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            new_user = User(username=username, password=hashed, full_name=full_name, phone=phone)
            db.session.add(new_user)
            db.session.commit()
            flash('✅ Account created! Login now.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/logout')
def logout():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.is_online = False
            user.last_seen = datetime.now()
            db.session.commit()
        if session['username'] in online_users:
            del online_users[session['username']]
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('login'))

# ========== API ROUTES ==========

@app.route('/api/search')
def search_users():
    if 'username' not in session:
        return jsonify([])
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    users = User.query.filter(
        User.username != session['username'],
        User.username.contains(query)
    ).limit(20).all()
    return jsonify([{
        'username': u.username,
        'full_name': u.full_name,
        'profile_pic': u.profile_pic,
        'is_online': u.is_online,
        'last_seen': u.last_seen.strftime('%H:%M') if u.last_seen else 'offline'
    } for u in users])

@app.route('/api/contacts')
def get_contacts():
    if 'username' not in session:
        return jsonify([])
    # Get users who have chatted with current user
    sent = Message.query.filter_by(sender=session['username']).all()
    received = Message.query.filter_by(receiver=session['username']).all()
    contact_usernames = set()
    for msg in sent:
        contact_usernames.add(msg.receiver)
    for msg in received:
        contact_usernames.add(msg.sender)
    
    # Also add users who are online
    for user in online_users.keys():
        if user != session['username']:
            contact_usernames.add(user)
    
    contacts = User.query.filter(User.username.in_(contact_usernames)).all() if contact_usernames else []
    return jsonify([{
        'username': c.username,
        'full_name': c.full_name,
        'profile_pic': c.profile_pic,
        'is_online': c.is_online,
        'last_seen': c.last_seen.strftime('%H:%M') if c.last_seen else 'offline'
    } for c in contacts])

@app.route('/api/statuses')
def get_statuses():
    if 'username' not in session:
        return jsonify([])
    from datetime import timedelta
    expiry = datetime.now() - timedelta(hours=24)
    statuses = Status.query.filter(
        Status.expires_at > datetime.now(),
        Status.created_at > expiry
    ).order_by(Status.created_at.desc()).all()
    
    result = []
    for s in statuses:
        views = json.loads(s.views) if s.views else []
        result.append({
            'id': s.id,
            'username': s.username,
            'content': s.content,
            'content_type': s.content_type,
            'image_url': s.image_url,
            'created_at': s.created_at.strftime('%H:%M'),
            'view_count': len(views),
            'has_viewed': session['username'] in views
        })
    return jsonify(result)

@app.route('/api/post_status', methods=['POST'])
def post_status():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'})
    data = request.json
    from datetime import timedelta
    status = Status(
        username=session['username'],
        content=data.get('content', ''),
        content_type=data.get('content_type', 'text'),
        image_url=data.get('image_url', ''),
        expires_at=datetime.now() + timedelta(hours=24)
    )
    db.session.add(status)
    db.session.commit()
    return jsonify({'success': True, 'id': status.id})

@app.route('/api/view_status/<int:status_id>', methods=['POST'])
def view_status(status_id):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'})
    status = Status.query.get(status_id)
    if status:
        views = json.loads(status.views) if status.views else []
        if session['username'] not in views:
            views.append(session['username'])
            status.views = json.dumps(views)
            db.session.commit()
    return jsonify({'success': True})

@app.route('/api/calls')
def get_calls():
    if 'username' not in session:
        return jsonify([])
    calls = Call.query.filter(
        (Call.caller == session['username']) | (Call.receiver == session['username'])
    ).order_by(Call.timestamp.desc()).limit(50).all()
    
    result = []
    for c in calls:
        other = c.caller if c.receiver == session['username'] else c.caller
        result.append({
            'id': c.id,
            'with': other,
            'call_type': c.call_type,
            'status': c.status,
            'duration': c.duration,
            'timestamp': c.timestamp.strftime('%H:%M'),
            'is_incoming': c.receiver == session['username']
        })
    return jsonify(result)

@app.route('/api/make_call', methods=['POST'])
def make_call():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'})
    data = request.json
    call = Call(
        caller=session['username'],
        receiver=data['to'],
        call_type=data.get('call_type', 'audio'),
        status='missed'
    )
    db.session.add(call)
    db.session.commit()
    
    if data['to'] in online_users:
        socketio.emit('incoming_call', {
            'from': session['username'],
            'call_type': data.get('call_type', 'audio'),
            'call_id': call.id
        }, room=online_users[data['to']])
    
    return jsonify({'success': True, 'call_id': call.id})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'})
    user = User.query.filter_by(username=session['username']).first()
    data = request.json
    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'bio' in data:
        user.bio = data['bio']
    if 'profile_pic' in data:
        user.profile_pic = data['profile_pic']
    if 'phone' in data:
        user.phone = data['phone']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/get_messages/<receiver>')
def get_messages(receiver):
    if 'username' not in session:
        return jsonify([])
    messages = Message.query.filter(
        ((Message.sender == session['username']) & (Message.receiver == receiver)) |
        ((Message.sender == receiver) & (Message.receiver == session['username']))
    ).order_by(Message.timestamp).all()
    
    return jsonify([{
        'id': m.id,
        'sender': m.sender,
        'receiver': m.receiver,
        'message': m.message,
        'timestamp': m.timestamp.strftime('%I:%M %p'),
        'read': m.read,
        'delivered': m.delivered
    } for m in messages])

# ========== SOCKET.IO EVENTS ==========

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        online_users[session['username']] = request.sid
        user_sessions[request.sid] = session['username']
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.is_online = True
            user.last_seen = datetime.now()
            db.session.commit()
        print(f'✅ {session["username"]} connected')
        emit('user_status', {'username': session['username'], 'is_online': True}, broadcast=True)
        # Send online users list to all
        emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in user_sessions:
        username = user_sessions[sid]
        if username in online_users:
            del online_users[username]
        user = User.query.filter_by(username=username).first()
        if user:
            user.is_online = False
            user.last_seen = datetime.now()
            db.session.commit()
        print(f'❌ {username} disconnected')
        emit('user_status', {'username': username, 'is_online': False}, broadcast=True)
        emit('online_users', list(online_users.keys()), broadcast=True)
        del user_sessions[sid]

@socketio.on('private_message')
def handle_private_message(data):
    if 'username' not in session:
        return
    
    print(f'📨 Message from {session["username"]} to {data["to"]}: {data["message"]}')
    
    # Save message to database
    msg = Message(
        sender=session['username'],
        receiver=data['to'],
        message=data['message'],
        timestamp=datetime.now()
    )
    db.session.add(msg)
    db.session.commit()
    
    # Mark as delivered
    msg.delivered = True
    db.session.commit()
    
    message_data = {
        'id': msg.id,
        'from': session['username'],
        'message': data['message'],
        'timestamp': datetime.now().strftime('%I:%M %p'),
        'message_id': msg.id,
        'delivered': True
    }
    
    # Send to receiver if online
    if data['to'] in online_users:
        emit('receive_message', message_data, room=online_users[data['to']])
        print(f'✅ Message delivered to {data["to"]}')
    else:
        print(f'⚠️ {data["to"]} is offline')
    
    # Send confirmation to sender
    emit('message_sent', {'to': data['to'], 'message_id': msg.id})

@socketio.on('mark_read')
def handle_mark_read(data):
    if 'username' not in session:
        return
    messages = Message.query.filter_by(sender=data['from'], receiver=session['username'], read=False).all()
    for msg in messages:
        msg.read = True
    db.session.commit()
    print(f'📖 {session["username"]} read messages from {data["from"]}')
    
    if data['from'] in online_users:
        emit('messages_read', {'from': session['username']}, room=online_users[data['from']])

@socketio.on('typing')
def handle_typing(data):
    if 'username' in session and data['to'] in online_users:
        emit('user_typing', {'from': session['username']}, room=online_users[data['to']])

@socketio.on('typing_stop')
def handle_typing_stop(data):
    if 'username' in session and data['to'] in online_users:
        emit('user_stop_typing', {'from': session['username']}, room=online_users[data['to']])

@socketio.on('get_history')
def handle_get_history(data):
    if 'username' not in session:
        return
    print(f'📜 Loading history between {session["username"]} and {data["with"]}')
    messages = Message.query.filter(
        ((Message.sender == session['username']) & (Message.receiver == data['with'])) |
        ((Message.sender == data['with']) & (Message.receiver == session['username']))
    ).order_by(Message.timestamp).all()
    
    history = []
    for msg in messages:
        history.append({
            'id': msg.id,
            'sender': msg.sender,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%I:%M %p'),
            'read': msg.read,
            'delivered': msg.delivered
        })
    emit('message_history', history)
    print(f'📜 Sent {len(history)} messages to {session["username"]}')

@socketio.on('call_answered')
def handle_call_answered(data):
    if data['to'] in online_users:
        emit('call_connected', {'from': session['username'], 'call_id': data['call_id']}, room=online_users[data['to']])

@socketio.on('call_rejected')
def handle_call_rejected(data):
    if data['to'] in online_users:
        emit('call_rejected', {'from': session['username']}, room=online_users[data['to']])

@socketio.on('call_end')
def handle_call_end(data):
    if data['to'] in online_users:
        emit('call_ended', {'from': session['username']}, room=online_users[data['to']])

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 WHATSAPP CLONE IS RUNNING!")
    print("📍 Open http://127.0.0.1:5000 in your browser")
    print("💡 Press CTRL+C to stop the server")
    print("=" * 50)
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
