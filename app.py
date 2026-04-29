from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Create upload folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/profile_photos', exist_ok=True)
os.makedirs('static', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= MODELS ================= #

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_photo = db.Column(db.String(200), default='/static/default-avatar.png')
    bio = db.Column(db.String(160), default='Hey there! I am using WhatsApp Clone')
    online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.Text, nullable=True)
    message_type = db.Column(db.String(20), default='text')
    media_url = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    is_delivered = db.Column(db.Boolean, default=False)

class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ================= LOGIN ================= #

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_blocked(user1_id, user2_id):
    return BlockedUser.query.filter_by(blocker_id=user1_id, blocked_id=user2_id).first() is not None

def is_blocked_by_other(user1_id, user2_id):
    return BlockedUser.query.filter_by(blocker_id=user2_id, blocked_id=user1_id).first() is not None

# ================= ROUTES ================= #

@app.route("/")
def index():
    return redirect("/chat") if current_user.is_authenticated else redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/chat")

    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            user.online = True
            db.session.commit()
            return redirect("/chat")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/chat")

    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already exists")

        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect("/chat")

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    current_user.online = False
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    logout_user()
    return redirect("/login")

@app.route("/chat")
@login_required
def chat():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template("chat.html", users=users)

# ================= SOCKET ================= #

@socketio.on('connect')
def connect():
    if current_user.is_authenticated:
        join_room(str(current_user.id))
        current_user.online = True
        db.session.commit()

@socketio.on('send_message')
def send_message(data):
    msg = Message(
        sender_id=current_user.id,
        receiver_id=data['receiver_id'],
        text=data['text']
    )
    db.session.add(msg)
    db.session.commit()

    emit('new_message', {
        'text': msg.text,
        'sender_id': msg.sender_id
    }, room=str(data['receiver_id']))

# ================= ✅ FIX HERE ================= #

with app.app_context():
    db.create_all()

# ================= RUN ================= #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    socketio.run(app, host='0.0.0.0', port=port)
