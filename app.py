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

# ✅ FIX (ADDED ONLY THIS)
with app.app_context():
    db.create_all()

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_photo = db.Column(db.String(200), default='/static/default-avatar.png')
    bio = db.Column(db.String(160), default='Hey there! I am using WhatsApp Clone')
    online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

# Message Model
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

# Blocked Users Model
class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_blocked(user1_id, user2_id):
    block = BlockedUser.query.filter_by(blocker_id=user1_id, blocked_id=user2_id).first()
    return block is not None

def is_blocked_by_other(user1_id, user2_id):
    block = BlockedUser.query.filter_by(blocker_id=user2_id, blocked_id=user1_id).first()
    return block is not None

# Routes
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/chat")
    return redirect("/login")

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
        flash('Invalid credentials', 'error')
        return render_template("login.html", error="Invalid credentials")
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/chat")
    
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", error="Username already exists")
        
        hashed = generate_password_hash(password)
        user = User(username=username, password=hashed)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect("/chat")
    
    return render_template("register.html")

# (REST OF YOUR CODE SAME — NO CHANGE)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
