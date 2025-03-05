# webapp/models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Initialize SQLAlchemy with no app yet
db = SQLAlchemy()

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    events = db.relationship('Event', backref='organizer', lazy=True)
    birthyear = db.Column(db.Integer)
    gender = db.Column(db.String(256))
    locale = db.Column(db.String(256))
    location = db.Column(db.String(256))
    timezone = db.Column(db.Integer)
    joinedAt = db.Column(db.DateTime, default=datetime.utcnow)
    interests = db.relationship('UserInterests', backref='user', lazy=True)
    joined_events = db.relationship('EventAttendee', backref='user', lazy=True)

    def set_password(self, password):
        """Set the password hash for the user."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        """Return string representation of the user."""
        return f'<User {self.username}>'

class UserInterests(db.Model):
    __tablename__ = 'user_interests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        """Return string representation of the user interest."""
        return f'<UserInterest {self.category}:{self.subcategory}>'

class EventAttendee(db.Model):
    __tablename__ = 'event_attendees'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        """Return string representation of the event attendee."""
        return f'<EventAttendee user_id={self.user_id}, event_id={self.event_id}>'

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    privacy = db.Column(db.String(20), nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_popularity = db.Column(db.Float, default=0.5)
    attendees = db.relationship('EventAttendee', backref='event', lazy=True)
    
    def get_attendee_count(self):
        """Return the number of attendees for the event."""
        return EventAttendee.query.filter_by(event_id=self.id).count()