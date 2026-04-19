from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), default='')
    bio = db.Column(db.String(200), default='Available')
    profile_pic = db.Column(db.String(10), default='😀')
    phone = db.Column(db.String(20), default='')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    receiver = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    delivered = db.Column(db.Boolean, default=False)

class Status(db.Model):
    __tablename__ = 'status'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.String(20), default='text')
    image_url = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    views = db.Column(db.Text, default='[]')

class Call(db.Model):
    __tablename__ = 'call'
    id = db.Column(db.Integer, primary_key=True)
    caller = db.Column(db.String(80), nullable=False)
    receiver = db.Column(db.String(80), nullable=False)
    call_type = db.Column(db.String(20), default='audio')  # audio, video
    duration = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='missed')  # missed, answered, rejected
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
