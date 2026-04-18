from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit
from models import db, User, Message, Status
from datetime import datetime
import bcrypt
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whatsapp-clone-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

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
        full_name = request.form.get('full_name', '')
        if User.query.filter_by(username=username).first():
            flash('❌ Username exists!', 'error')
        else:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            new_user = User(username=username, password=hashed, full_name=full_name)
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

@app.route('/api/search_users')
def search_users():
    if 'username' not in session:
        return jsonify([])
    query = request.args.get('q', '')
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

@app.route('/api/get_contacts')
def get_contacts():
    if 'username' not in session:
        return jsonify([])
    # Get users who have chatted with current user
    messages = Message.query.filter(
        (Message.sender == session['username']) | (Message.receiver == session['username'])
    ).all()
    contact_usernames = set()
    for msg in messages:
        if msg.sender != session['username']:
            contact_usernames.add(msg.sender)
        if msg.receiver != session['username']:
            contact_usernames.add(msg.receiver)
    
    contacts = User.query.filter(User.username.in_(contact_usernames)).all()
    return jsonify([{
        'username': u.username,
        'full_name': u.full_name,
        'profile_pic': u.profile_pic,
        'is_online': u.is_online,
        'last_seen': u.last_seen.strftime('%H:%M') if u.last_seen else 'offline'
    } for u in contacts])

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
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/post_status', methods=['POST'])
def post_status():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'})
    data = request.json
    status = Status(
        username=session['username'],
        content=data['content'],
        content_type=data.get('content_type', 'text')
    )
    db.session.add(status)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/get_statuses')
def get_statuses():
    if 'username' not in session:
        return jsonify([])
    statuses = Status.query.filter(
        Status.expires_at > datetime.now()
    ).order_by(Status.created_at.desc()).all()
    return jsonify([{
        'username': s.username,
        'content': s.content,
        'content_type': s.content_type,
        'time_ago': s.created_at.strftime('%H:%M')
    } for s in statuses])

@app.route('/api/view_status/<int:status_id>', methods=['POST'])
def view_status(status_id):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'})
    status = Status.query.get(status_id)
    if status:
        views = json.loads(status.views)
        if session['username'] not in views:
            views.append(session['username'])
            status.views = json.dumps(views)
            db.session.commit()
    return jsonify({'success': True})

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        online_users[session['username']] = request.sid
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.is_online = True
            user.last_seen = datetime.now()
            db.session.commit()
        emit('user_online', {'username': session['username']}, broadcast=True)

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
        emit('user_offline', {'username': session['username'], 'last_seen': datetime.now().strftime('%H:%M')}, broadcast=True)

@socketio.on('search_users')
def handle_search_users(data):
    if 'username' not in session:
        return
    query = data.get('query', '')
    users = User.query.filter(
        User.username != session['username'],
        User.username.contains(query)
    ).limit(20).all()
    emit('search_results', [{
        'username': u.username,
        'full_name': u.full_name,
        'profile_pic': u.profile_pic,
        'is_online': u.is_online
    } for u in users])

@socketio.on('private_message')
def handle_private_message(data):
    if 'username' not in session:
        return
    msg = Message(
        sender=session['username'],
        receiver=data['to'],
        message=data['message'],
        timestamp=datetime.now()
    )
    db.session.add(msg)
    db.session.commit()
    
    if data['to'] in online_users:
        emit('receive_message', {
            'from': session['username'],
            'message': data['message'],
            'timestamp': datetime.now().strftime('%I:%M %p'),
            'message_id': msg.id
        }, room=online_users[data['to']])
    
    emit('message_sent', {
        'to': data['to'],
        'message': data['message'],
        'timestamp': datetime.now().strftime('%I:%M %p'),
        'message_id': msg.id
    })

@socketio.on('typing')
def handle_typing(data):
    if 'username' in session and data['to'] in online_users:
        emit('user_typing', {'from': session['username']}, room=online_users[data['to']])

@socketio.on('typing_stop')
def handle_typing_stop(data):
    if 'username' in session and data['to'] in online_users:
        emit('user_stop_typing', {'from': session['username']}, room=online_users[data['to']])

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

@socketio.on('get_history')
def handle_get_history(data):
    if 'username' not in session:
        return
    messages = Message.query.filter(
        ((Message.sender == session['username']) & (Message.receiver == data['with'])) |
        ((Message.sender == data['with']) & (Message.receiver == session['username']))
    ).order_by(Message.timestamp).all()
    history = [{
        'sender': m.sender,
        'message': m.message,
        'timestamp': m.timestamp.strftime('%I:%M %p'),
        'read': m.read,
        'delivered': m.delivered
    } for m in messages]
    emit('message_history', history)

if __name__ == '__main__':
    print("🚀 WhatsApp Clone Server Running at http://127.0.0.1:5000")
    socketio.run(app, debug=True, port=5000)
