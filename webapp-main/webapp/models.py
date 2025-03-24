# webapp/models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import JSONB

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
    interactions = db.relationship('UserEventInteraction', backref='user', lazy=True)
    
    # New: Google Calendar Integration
    google_calendar_token = db.Column(db.Text, nullable=True)
    google_calendar_refresh_token = db.Column(db.Text, nullable=True)
    google_calendar_token_expiry = db.Column(db.DateTime, nullable=True)
    calendar_sync_enabled = db.Column(db.Boolean, default=False)
    
    # New: Location preferences
    precise_location_enabled = db.Column(db.Boolean, default=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # New: User preferences
    preferences = db.Column(JSONB, nullable=True)

    def set_password(self, password):
        """Set the password hash for the user."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)
    
    def get_location_info(self):
        """Get formatted location information."""
        if self.latitude and self.longitude and self.precise_location_enabled:
            return {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'precise': True,
                'display': self.location
            }
        else:
            return {
                'latitude': None,
                'longitude': None,
                'precise': False,
                'display': self.location
            }
    
    def get_user_interests_by_category(self):
        """Get user interests grouped by category."""
        interests = {}
        for interest in self.interests:
            if interest.category not in interests:
                interests[interest.category] = []
            interests[interest.category].append(interest.subcategory)
        return interests
    
    def has_joined_event(self, event_id):
        """Check if user has joined an event."""
        return EventAttendee.query.filter_by(user_id=self.id, event_id=event_id).first() is not None
    
    def calculate_completion_score(self):
        """Calculate a profile completion score (0-100)."""
        score = 0
        # Basic profile - 50%
        if self.username: score += 10
        if self.email: score += 10
        if self.birthyear: score += 5
        if self.gender: score += 5
        if self.location: score += 10
        if self.locale: score += 5
        if self.timezone is not None: score += 5
        
        # Interests - 30%
        interest_count = len(self.interests)
        if interest_count > 0:
            score += min(30, interest_count * 3)
        
        # Event participation - 20%
        events_joined = len(self.joined_events)
        if events_joined > 0:
            score += min(20, events_joined * 2)
        
        return score

    def __repr__(self):
        """Return string representation of the user."""
        return f'<User {self.username}>'

class UserInterests(db.Model):
    __tablename__ = 'user_interests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50), nullable=False)
    # New: strength of interest (0-1)
    strength = db.Column(db.Float, default=1.0)
    # New: timestamp when this interest was added
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        """Return string representation of the user interest."""
        return f'<UserInterest {self.category}:{self.subcategory}>'

class EventAttendee(db.Model):
    __tablename__ = 'event_attendees'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    # New: RSVP status
    status = db.Column(db.String(20), default='attending')  # attending, maybe, declined
    # New: Sync to Google Calendar
    synced_to_calendar = db.Column(db.Boolean, default=False)
    calendar_event_id = db.Column(db.String(256), nullable=True)

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
    interactions = db.relationship('UserEventInteraction', backref='event', lazy=True)
    
    # New: Additional event information
    end_date = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    subcategory = db.Column(db.String(50), nullable=True)
    max_attendees = db.Column(db.Integer, nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # New: Location coordinates
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # New: Event metadata (e.g., for additional fields)
    event_metadata = db.Column(JSONB, nullable=True)
    
    def get_attendee_count(self):
        """Return the number of attendees for the event."""
        return EventAttendee.query.filter_by(event_id=self.id).count()
    
    def is_user_attending(self, user_id):
        """Check if a user is attending the event."""
        return EventAttendee.query.filter_by(event_id=self.id, user_id=user_id).first() is not None
    
    def get_location_info(self):
        """Get formatted location information."""
        if self.latitude and self.longitude:
            return {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'display': self.location
            }
        else:
            return {
                'latitude': None,
                'longitude': None,
                'display': self.location
            }
    
    def is_upcoming(self):
        """Check if the event is upcoming."""
        return self.date > datetime.utcnow()
    
    def get_day_difference(self):
        """Get the number of days until (or since) the event."""
        delta = self.date.date() - datetime.utcnow().date()
        return delta.days
    
    def calculate_trending_score(self):
        """Calculate a trending score for the event."""
        # Base is the event popularity
        score = self.event_popularity * 40
        
        # Recent interactions boost score
        recent_interactions = UserEventInteraction.query.filter(
            UserEventInteraction.event_id == self.id,
            UserEventInteraction.timestamp > datetime.utcnow() - timedelta(days=7)
        ).count()
        
        interaction_boost = min(30, recent_interactions)
        
        # Recent creation date
        days_since_creation = (datetime.utcnow() - self.created_at).days
        recency_score = max(0, 30 - min(days_since_creation, 30))
        
        return score + interaction_boost + recency_score

# New model: Track user interactions with events
class UserEventInteraction(db.Model):
    __tablename__ = 'user_event_interactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    interaction_type = db.Column(db.String(50), nullable=False)  # view, click, join, leave, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    interaction_metadata = db.Column(JSONB, nullable=True)  # Any additional data about the interaction
    
    def __repr__(self):
        """Return string representation of the interaction."""
        return f'<UserEventInteraction user_id={self.user_id}, event_id={self.event_id}, type={self.interaction_type}>'