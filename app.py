import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session, jsonify
from flask_socketio import SocketIO, emit
from models import db, User, Message
from datetime import datetime
import bcrypt
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

online_users = {}

with app.app_context():
    db.create_all()

# ================= ROUTES =================

@app.route('/')
def home():
    return redirect('/chat') if 'username' in session else redirect('/login')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        user = User.query.filter_by(username=u).first()
        if user and bcrypt.checkpw(p.encode(), user.password):
            session['username'] = u
            return redirect('/chat')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        hashed = bcrypt.hashpw(p.encode(), bcrypt.gensalt())
        db.session.add(User(username=u, password=hashed))
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect('/login')
    return render_template('chat.html', username=session['username'])

@app.route('/api/users')
def users():
    return jsonify([u.username for u in User.query.all() if u.username != session['username']])

# ================= SOCKET =================

@socketio.on('connect')
def connect():
    if 'username' in session:
        online_users[session['username']] = request.sid

@socketio.on('disconnect')
def disconnect():
    user = session.get('username')
    if user in online_users:
        del online_users[user]

@socketio.on('send_message')
def handle_msg(data):
    sender = session['username']
    receiver = data['to']
    msg = data['msg']

    m = Message(sender=sender, receiver=receiver, message=msg)
    db.session.add(m)
    db.session.commit()

    payload = {
        'id': m.id,
        'from': sender,
        'msg': msg,
        'time': datetime.now().strftime('%H:%M')
    }

    if receiver in online_users:
        emit('receive_message', payload, room=online_users[receiver])

    emit('receive_message', payload)

@socketio.on('typing')
def typing(data):
    if data['to'] in online_users:
        emit('typing', {'from': session['username']}, room=online_users[data['to']])

# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
