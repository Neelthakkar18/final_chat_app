from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
from models import db, User, Message
from datetime import datetime
import bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_PERMANENT'] = False  # Session expires when browser closes

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

online_users = {}

# Create database tables
with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully!")

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any existing session
    if request.method == 'GET':
        session.clear()
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('✅ Login successful!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('❌ Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('❌ Username already exists!', 'error')
        else:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('✅ Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    users = User.query.filter(User.id != session['user_id']).all()
    return render_template('chat.html', username=session['username'], users=users)

@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    flash('✅ Logged out successfully', 'success')
    return redirect(url_for('login'))

# ========== SOCKET.IO EVENTS ==========

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        online_users[session['username']] = request.sid
        print(f"📡 {session['username']} connected")
        
        users_list = []
        all_users = User.query.all()
        for user in all_users:
            if user.username != session['username']:
                users_list.append({'id': user.username, 'name': user.username})
        
        emit('users_list', users_list)
        emit('user_joined', {'username': session['username']}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        if session['username'] in online_users:
            del online_users[session['username']]
        print(f"📡 {session['username']} disconnected")
        emit('user_left', session['username'], broadcast=True)

@socketio.on('get_users')
def handle_get_users():
    if 'username' in session:
        users_list = []
        all_users = User.query.all()
        for user in all_users:
            if user.username != session['username']:
                users_list.append({'id': user.username, 'name': user.username})
        emit('users_list', users_list)

@socketio.on('private_message')
def handle_private_message(data):
    if 'username' not in session:
        return
    
    new_message = Message(
        sender=session['username'],
        receiver=data['to'],
        message=data['message'],
        timestamp=datetime.now()
    )
    db.session.add(new_message)
    db.session.commit()
    
    print(f"💬 {session['username']} → {data['to']}: {data['message']}")
    
    if data['to'] in online_users:
        emit('receive_message', {
            'from': session['username'],
            'message': data['message'],
            'timestamp': datetime.now().strftime('%H:%M')
        }, room=online_users[data['to']])

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
    
    messages = Message.query.filter(
        ((Message.sender == session['username']) & (Message.receiver == data['with'])) |
        ((Message.sender == data['with']) & (Message.receiver == session['username']))
    ).order_by(Message.timestamp).all()
    
    history = []
    for msg in messages:
        history.append({
            'sender': msg.sender,
            'message': msg.message,
            'time': msg.timestamp.strftime('%H:%M')
        })
    
    emit('message_history', history)

if __name__ == '__main__':
    print("🚀 Starting Chat App Server...")
    print("📍 Open http://127.0.0.1:5000 in your browser")
    print("💡 Press CTRL+C to stop the server")
    socketio.run(app, host='0.0.0.0', port=10000)