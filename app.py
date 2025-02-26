# main webapp
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from serpAPIService import EventService
import logging
from flask import current_app
from dotenv import load_dotenv
import random
import faker
from faker import Faker

load_dotenv(".env.local")

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_event_organizer.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    events = db.relationship('Event', backref='organizer', lazy=True)
    birthyear = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    locale = db.Column(db.String(10))
    location = db.Column(db.String(100))
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
    location = db.Column(db.String(100), nullable=False)  # Added location field
    date = db.Column(db.DateTime, nullable=False)
    privacy = db.Column(db.String(20), nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_popularity = db.Column(db.Float, default=0.5)
    attendees = db.relationship('EventAttendee', backref='event', lazy=True)
    
    def get_attendee_count(self):
        """Return the number of attendees for the event."""
        return EventAttendee.query.filter_by(event_id=self.id).count()

from sqlalchemy import inspect

def init_db():
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        print("Current tables:", inspector.get_table_names())


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Routes
@app.route('/')
def index():
    # Initialize the event service with your API key
    event_service = EventService(os.getenv('SERPAPI_KEY'))
    
    # Get query parameters
    query = request.args.get('q')
    location = request.args.get('location')
    date = request.args.get('date')
    page = int(request.args.get('page', 1))
    
    # Get events based on user interests if logged in
    if current_user.is_authenticated and not query:
        user_interests = UserInterests.query.filter_by(user_id=current_user.id).all()
        if user_interests:
            # Use the first interest as a search term
            query = user_interests[0].subcategory
    
    events = event_service.search_events(
        query=query,
        location=location,
        date=date,
        page=page
    )
    
    return render_template('lander.html', events=events)

@app.route('/home')
@login_required
def home():
    # Initialize the event service with your API key
    event_service = EventService(os.getenv('SERPAPI_KEY'))
    
    # Get events based on user interests if available
    user_interests = UserInterests.query.filter_by(user_id=current_user.id).all()
    query = user_interests[0].subcategory if user_interests else None
    
    # Get initial events for the page
    events = event_service.search_events(
        query=query,
        location=current_user.location,
        page=1
    )
    
    return render_template('home.html', events=events)


@app.route('/browse_local_events')
@login_required
def browse_local_events():
    # Get all events from the database (not from SerpAPI)
    all_events = Event.query.filter_by(privacy='public').all()
    return render_template('browse_local_events.html', events=all_events)


@app.route('/api/events')
def api_events():
    app.logger.debug("Received request for events API")
    event_service = EventService(os.getenv('SERPAPI_KEY'))
    
    # Get location parameters
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    
    # Debug log the coordinates
    app.logger.debug(f"Received coordinates: lat={lat}, lng={lng}")
    
    # Get other filter parameters
    query = request.args.get('q')
    date = request.args.get('date')
    page = int(request.args.get('page', 1))
    
    # If we have coordinates, convert to location string
    location = None
    if lat and lng:
        try:
            app.logger.debug(f"Attempting reverse geocoding for coordinates: {lat}, {lng}")
            response = requests.get(
                f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json",
                headers={'User-Agent': 'EventFlowAI/1.0'}
            )
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})
                # Try to get city, state, or country
                location = address.get('city') or address.get('state') or address.get('country')
                app.logger.debug(f"Reverse geocoded location: {location}")
        except Exception as e:
            app.logger.error(f"Error in reverse geocoding: {e}")
    
    # If location lookup failed, use a default radius around coordinates
    if not location and lat and lng:
        location = f"{lat},{lng}"
        app.logger.debug(f"Using coordinate-based location: {location}")

    # Search for events using the EventService
    events = event_service.search_events(
        query=query,
        location=location,
        date=date,
        page=page
    )
    
    # Return JSON response
    return jsonify({
        'events': events,
        'meta': {
            'location': location,
            'query': query,
            'date': date,
            'page': page
        }
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/check_exists')
def check_exists():
    check_type = request.args.get('type')
    value = request.args.get('value')
    
    if check_type == 'username':
        exists = User.query.filter_by(username=value).first() is not None
    elif check_type == 'email':
        exists = User.query.filter_by(email=value).first() is not None
    else:
        return jsonify({'error': 'Invalid check type'}), 400
    
    return jsonify({'exists': exists})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            birthyear=int(request.form['birthyear']),
            gender=request.form['gender'],
            locale=request.form['locale'],
            location=request.form['location'],
            timezone=int(request.form['timezone']),
            joinedAt=datetime.now()
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        login_user(user)  # Log the user in
        return redirect(url_for('select_interests'))  # Redirect to interests
    return render_template('register.html')


@app.route('/select-interests', methods=['GET', 'POST'])
@login_required
def select_interests():
    if request.method == 'POST':
        # Clear existing interests
        UserInterests.query.filter_by(user_id=current_user.id).delete()
        
        # Get selected interests from form
        interests = request.form.getlist('interests[]')
        
        # Save new interests
        for interest in interests:
            category, subcategory = interest.split(':', 1)
            new_interest = UserInterests(
                user_id=current_user.id,
                category=category,
                subcategory=subcategory
            )
            db.session.add(new_interest)
        
        db.session.commit()
        flash('Interests updated successfully!')
        return redirect(url_for('recommendations'))
        
    return render_template('select_interests.html')


@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        event = Event(
            title=request.form['title'],
            description=request.form['description'],
            location=request.form['location'],  # Added location field
            date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
            privacy=request.form['privacy'],
            organizer_id=current_user.id,
            event_popularity=float(request.form['event_popularity'])
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created successfully')
        return redirect(url_for('my_events'))
    return render_template('create_event.html')

@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    
    # Ensure only the organizer can edit the event
    if event.organizer_id != current_user.id:
        flash('You do not have permission to edit this event.')
        return redirect(url_for('my_events'))
    
    if request.method == 'POST':
        event.title = request.form['title']
        event.description = request.form['description']
        event.location = request.form['location']
        event.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        event.privacy = request.form['privacy']
        event.event_popularity = float(request.form['event_popularity'])
        
        db.session.commit()
        flash('Event updated successfully')
        return redirect(url_for('my_events'))
    
    return render_template('edit_event.html', event=event)

@app.route('/my_events')
@login_required
def my_events():
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    return render_template('my_events.html', events=events)

@app.route('/join_event/<int:event_id>', methods=['POST'])
@login_required
def join_event(event_id):
    event = Event.query.get_or_404(event_id)
    
    # Check if user is already attending
    existing_attendee = EventAttendee.query.filter_by(
        user_id=current_user.id, 
        event_id=event_id
    ).first()
    
    if existing_attendee:
        flash('You are already attending this event.')
        return redirect(url_for('event_details', event_id=event_id))
    
    # Create new attendee record
    attendee = EventAttendee(
        user_id=current_user.id,
        event_id=event_id,
        joined_at=datetime.utcnow()
    )
    
    db.session.add(attendee)
    db.session.commit()
    
    flash('You have successfully joined the event!')
    return redirect(url_for('event_details', event_id=event_id))

@app.route('/leave_event/<int:event_id>', methods=['POST'])
@login_required
def leave_event(event_id):
    # Find and delete the attendee record
    attendee = EventAttendee.query.filter_by(
        user_id=current_user.id, 
        event_id=event_id
    ).first()
    
    if attendee:
        db.session.delete(attendee)
        db.session.commit()
        flash('You have left the event.')
    else:
        flash('You are not attending this event.')
    
    return redirect(url_for('event_details', event_id=event_id))

@app.route('/event/<int:event_id>')
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    
    # Check if current user is attending
    is_attending = False
    if current_user.is_authenticated:
        is_attending = EventAttendee.query.filter_by(
            user_id=current_user.id, 
            event_id=event_id
        ).first() is not None
    
    # Get all attendees
    attendees = User.query.join(EventAttendee).filter(
        EventAttendee.event_id == event_id
    ).all()
    
    return render_template(
        'event_details.html', 
        event=event, 
        is_attending=is_attending,
        attendees=attendees
    )

@app.route('/joined_events')
@login_required
def joined_events():
    # Get all events the user has joined
    joined_events = Event.query.join(EventAttendee).filter(
        EventAttendee.user_id == current_user.id
    ).all()
    
    return render_template('joined_events.html', events=joined_events)


class RecommendationService:
    def __init__(self, api_url):
        self.api_url = api_url

    def get_recommendations(self, user, events):
        try:
            # Prepare user data with default values for missing fields
            user_data = {
                'birthyear': user.birthyear or 1990,
                'gender': user.gender or 'unknown',
                'locale': user.locale or 'unknown',
                'location': user.location or 'unknown',
                'timezone': user.timezone or 0,
                'joinedAt': user.joinedAt.isoformat() if user.joinedAt else datetime.utcnow().isoformat()
            }

            # Prepare event data ensuring all required fields are present
            events_data = []
            for event in events:
                event_dict = {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description or '',
                    'location': event.location,  # Added location field
                    'date': event.date.isoformat() if event.date else datetime.utcnow().isoformat(),
                    'privacy': event.privacy or 'public',
                    'event_popularity': float(event.event_popularity if event.event_popularity is not None else 0.5),
                    'invited': 0,  # Adding default value for invited field
                    'attendee_count': event.get_attendee_count()  # Add attendee count
                }
                events_data.append(event_dict)

            # Prepare request data
            request_data = {
                'user': {'id': user.id},
                'events': events_data,
                'user_data': user_data
            }

            # Make API request
            response = requests.post(
                f"{self.api_url}/api/recommendations",
                json=request_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                return response.json()['recommendations']
            else:
                print(f"API Response: {response.text}")  # Debug print
                raise Exception(f"API request failed: {response.text}")

        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return []
            
# Initialize recommendation service
ai_api = os.getenv("AI_API")
recommendation_service = RecommendationService(ai_api)

@app.route('/recommendations')
@login_required
def recommendations():
    try:
        # Get all public events
        public_events = Event.query.filter_by(privacy='public').all()
        
        if not public_events:
            flash('No public events available for recommendations.')
            return redirect(url_for('home'))

        # Get recommendations from API
        recommendations = recommendation_service.get_recommendations(
            current_user,
            public_events
        )

        # Process recommendations for template using session.get()
        recommended_events = [
            (
                db.session.get(Event, rec['event']['id']),
                rec['score']
            )
            for rec in recommendations
        ]

        return render_template(
            'recommendations.html',
            recommended_events=recommended_events
        )

    except Exception as e:
        app.logger.error(f"Error in recommendations: {str(e)}")
        flash('Error generating recommendations. Please try again later.', 'error')
        return redirect(url_for('index'))

def generate_dummy_events(count=20):
    """Generate dummy events using Faker library."""
    fake = Faker()
    
    # Get all users for random assignment
    users = User.query.all()
    if not users:
        app.logger.warning("No users found to assign dummy events to.")
        return
    
    # Event categories for more realistic data
    categories = [
        "Music Concert", "Tech Conference", "Food Festival", 
        "Art Exhibition", "Sports Game", "Charity Run",
        "Workshop", "Networking", "Movie Screening", "Book Club"
    ]
    
    # Locations - mix of real cities
    locations = [
        "New York, NY", "San Francisco, CA", "Chicago, IL", 
        "Austin, TX", "Seattle, WA", "Boston, MA",
        "Los Angeles, CA", "Miami, FL", "Denver, CO", "Atlanta, GA"
    ]
    
    # Privacy options
    privacy_options = ["public", "private", "invitation"]
    
    # Generate events
    events_created = 0
    for _ in range(count):
        # Create event with random data
        event = Event(
            title=fake.sentence(nb_words=4).rstrip('.'),
            description=fake.paragraph(nb_sentences=3),
            location=random.choice(locations),
            date=fake.date_time_between(start_date='now', end_date='+90d'),
            privacy=random.choice(privacy_options),
            organizer_id=random.choice(users).id,
            event_popularity=round(random.uniform(0.1, 1.0), 2)
        )
        
        db.session.add(event)
        events_created += 1
    
    try:
        db.session.commit()
        app.logger.info(f"Successfully created {events_created} dummy events.")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating dummy events: {e}")

@app.route('/generate_dummy_events', methods=['GET', 'POST'])
@login_required
def generate_dummy_events_route():
    if request.method == 'POST':
        count = int(request.form.get('count', 20))
        generate_dummy_events(count)
        flash(f'Successfully generated {count} dummy events!')
        return redirect(url_for('my_events'))
    
    return render_template('generate_dummy_events.html')

if __name__ == '__main__':
    if not os.getenv('SERPAPI_KEY'):
        print("WARNING: SERPAPI_KEY environment variable not set!")
    init_db()
    app.run(host='0.0.0.0', debug=True, use_reloader=False)