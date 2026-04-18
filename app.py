from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit
from models import db, User, Message
from datetime import datetime
import bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whatsapp-clone-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

online_users = {}
typing_users = {}

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
        if User.query.filter_by(username=username).first():
            flash('❌ Username exists!', 'error')
        else:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            new_user = User(username=username, password=hashed)
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
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('login'))

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
    
    contacts = User.query.filter(User.username.in_(contact_usernames)).all()
    # Add users who are online but no chat yet
    for user in User.query.filter(User.username != session['username']).all():
        if user.username not in contact_usernames and user.is_online:
            contacts.append(user)
    
    return jsonify([{
        'username': c.username,
        'is_online': c.is_online,
        'last_seen': c.last_seen.strftime('%H:%M') if c.last_seen else 'offline'
    } for c in contacts])

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        online_users[session['username']] = request.sid
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.is_online = True
            user.last_seen = datetime.now()
            db.session.commit()
        emit('user_status', {'username': session['username'], 'is_online': True, 'last_seen': 'Online'}, broadcast=True)
        print(f'✅ {session["username"]} connected')

@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        if session['username'] in online_users:
            del online_users[session['username']]
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.is_online = False
            user.last_seen = datetime.now()
            db.session.commit()
        emit('user_status', {'username': session['username'], 'is_online': False, 'last_seen': user.last_seen.strftime('%H:%M') if user else 'offline'}, broadcast=True)
        print(f'❌ {session["username"]} disconnected')

@socketio.on('get_online_users')
def handle_get_online_users():
    if 'username' in session:
        users = User.query.filter(User.username != session['username']).all()
        emit('users_list', [{
            'username': u.username,
            'is_online': u.is_online,
            'last_seen': u.last_seen.strftime('%H:%M') if u.last_seen else 'offline'
        } for u in users])

@socketio.on('private_message')
def handle_private_message(data):
    if 'username' not in session:
        return
    
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
    
    # Send to receiver if online
    if data['to'] in online_users:
        emit('receive_message', {
            'from': session['username'],
            'message': data['message'],
            'timestamp': datetime.now().strftime('%I:%M %p'),
            'message_id': msg.id,
            'delivered': True
        }, room=online_users[data['to']])
        
        # Send delivery confirmation to sender
        emit('message_delivered', {
            'to': data['to'],
            'message_id': msg.id
        })
    else:
        # Send delivery failed (user offline)
        emit('message_delivered', {
            'to': data['to'],
            'message_id': msg.id,
            'delivered': False
        })

@socketio.on('mark_read')
def handle_mark_read(data):
    if 'username' not in session:
        return
    messages = Message.query.filter_by(sender=data['from'], receiver=session['username'], read=False).all()
    for msg in messages:
        msg.read = True
    db.session.commit()
    
    if data['from'] in online_users:
        emit('messages_read', {'from': session['username']}, room=online_users[data['from']])

@socketio.on('typing_start')
def handle_typing_start(data):
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
    messages = Message.query.filter(
        ((Message.sender == session['username']) & (Message.receiver == data['with'])) |
        ((Message.sender == data['with']) & (Message.receiver == session['username']))
    ).order_by(Message.timestamp).all()
    
    history = []
    for msg in messages:
        history.append({
            'sender': msg.sender,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%I:%M %p'),
            'read': msg.read if msg.receiver == session['username'] else True,
            'delivered': msg.delivered
        })
    emit('message_history', history)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
