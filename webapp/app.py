# webapp/app.py
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from webapp.serpAPIService import EventService
import logging
from flask import current_app
import random
from faker import Faker
from sqlalchemy import func, desc
import math
# Import models using relative imports
from webapp.models import db, User, Event, UserInterests, EventAttendee, UserEventInteraction

import os
from pathlib import Path
from dotenv import load_dotenv

# Get the project root directory
project_root = Path(__file__).parent.parent.absolute()

# Load environment variables from .env.local in the project root
env_path = project_root / '.env.local'
print(f"Looking for .env.local at: {env_path}")
load_dotenv(env_path)

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
# Update database URI for PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/event_organizer")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the app
db.init_app(app)

# Initialize the Flask-Login extension
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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
            location=request.form['location'],
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
        self.min_recommendations = 10
        print(f"Initializing RecommendationService with API URL: {api_url}")
        
        # Test API connectivity
        try:
            response = requests.get(f"{api_url}/health", timeout=2)
            if response.status_code == 200:
                print("API connection successful!")
            else:
                print(f"API connection test failed with status: {response.status_code}")
        except requests.RequestException as e:
            print(f"API connection test failed: {e}")

    def _safe_get_day_difference(self, event):
        """Safely calculate days until event, handling None dates"""
        if event.date is None:
            # Default to 30 days in the future if no date
            return 30
        
        try:
            return (event.date - datetime.utcnow()).days
        except Exception as e:
            print(f"Error calculating days difference: {e}")
            return 30  # Default fallback
    
    def get_user_interests(self, user_id):
        """Get user interests from database"""
        interests = []
        user_interests = UserInterests.query.filter_by(user_id=user_id).all()
        
        for interest in user_interests:
            interests.append({
                'category': interest.category,
                'subcategory': interest.subcategory,
                'strength': interest.strength
            })
            
        return interests

    def get_recommendations(self, user, events):
        """
        Get personalized event recommendations
        Uses AI model with better error handling
        """
        # Prepare user data with default values for missing fields
        user_data = {
            'birthyear': user.birthyear or 1990,
            'gender': user.gender or 'unknown',
            'locale': user.locale or 'unknown',
            'location': user.location or 'unknown',
            'timezone': user.timezone or 0,
            'joinedAt': user.joinedAt.isoformat() if user.joinedAt else datetime.utcnow().isoformat(),
            'latitude': user.latitude,
            'longitude': user.longitude,
            'precise_location_enabled': user.precise_location_enabled
        }

        # Get user interests
        user_interests = self.get_user_interests(user.id)

        # Get user interactions for learning
        user_interactions = self._get_user_interactions(user.id)

        # Prepare event data ensuring all required fields are present
        events_data = []
        for event in events:
            try:
                # Calculate distance from user if location data available
                distance = None
                if user.latitude and user.longitude and event.latitude and event.longitude:
                    distance = self._calculate_distance(
                        user.latitude, user.longitude,
                        event.latitude, event.longitude
                    )
                
                # Safely get day difference
                days_until_event = self._safe_get_day_difference(event)
                
                event_dict = {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description or '',
                    'location': event.location,
                    'latitude': event.latitude,
                    'longitude': event.longitude,
                    'date': event.date.isoformat() if event.date else (datetime.utcnow() + timedelta(days=30)).isoformat(),
                    'privacy': event.privacy or 'public',
                    'category': event.category or 'unknown',
                    'subcategory': event.subcategory or 'unknown',
                    'event_popularity': float(event.event_popularity if event.event_popularity is not None else 0.5),
                    'invited': 0,  # Adding default value for invited field
                    'attendee_count': event.get_attendee_count(),  # Add attendee count
                    'days_until_event': days_until_event,
                    'distance_km': distance,
                    'is_trending': getattr(event, 'calculate_trending_score', lambda: 50)() > 70,
                    'created_at': event.created_at.isoformat() if event.created_at else datetime.utcnow().isoformat()
                }
                events_data.append(event_dict)
            except Exception as e:
                print(f"Error preparing event data for event {event.id}: {e}")
                # Skip this event rather than failing the entire request
                continue

        # Prepare request data
        request_data = {
            'user': {'id': user.id},
            'events': events_data,
            'user_data': user_data,
            'user_interests': user_interests,
            'user_interactions': user_interactions
        }

        try:
            # Log the request for debugging
            print(f"Sending request to AI API: {self.api_url}")
            
            # Make API request with increased timeout
            response = requests.post(
                f"{self.api_url}/api/recommendations",
                json=request_data,
                headers={'Content-Type': 'application/json'},
                timeout=10  # Increased timeout
            )
            
            if response.status_code == 200:
                # Get the recommendations from the API response
                api_recommendations = response.json().get('recommendations', [])
                
                # Process the recommendations to match the expected format in the webapp
                processed_recommendations = []
                for rec in api_recommendations:
                    processed_recommendations.append({
                        'event_id': rec.get('event_id'),
                        'score': rec.get('score'),
                        'title': rec.get('title', '')
                    })
                    
                return processed_recommendations
            else:
                print(f"API Error Response ({response.status_code}): {response.text}")
                return []  # Return empty list on error
        except requests.RequestException as e:
            print(f"Request error getting recommendations: {e}")
            return []  # Return empty list on error
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return []  # Return empty list on error
    
    def _get_user_interactions(self, user_id):
        """Get recent user interactions for recommendation learning"""
        interactions = UserEventInteraction.query.filter_by(user_id=user_id).order_by(
            UserEventInteraction.timestamp.desc()
        ).limit(100).all()
        
        return [
            {
                'event_id': interaction.event_id,
                'interaction_type': interaction.interaction_type,
                'timestamp': interaction.timestamp.isoformat()
            }
            for interaction in interactions
        ]
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers using Haversine formula"""
        # Radius of earth in kilometers
        R = 6371.0
        
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Difference in coordinates
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        
        return distance
    
    def _generate_fallback_recommendations(self, user, events, user_interests, count=None):
        """
        Generate fallback recommendations based on user interests and event attributes
        This is used when the AI API is unavailable or returns insufficient recommendations
        """
        app.logger.info("Generating fallback recommendations")
        
        # Create a mapping of user interests for quick lookup
        user_interest_map = {}
        for interest in user_interests:
            category = interest['category'].lower()
            subcategory = interest['subcategory'].lower()
            
            if category not in user_interest_map:
                user_interest_map[category] = set()
            
            user_interest_map[category].add(subcategory)
        
        # Score each event
        scored_events = []
        for event in events:
            score = self._calculate_event_score(event, user, user_interest_map)
            scored_events.append({
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'location': event.location,
                    'date': event.date.isoformat() if event.date else None,
                    'privacy': event.privacy,
                    'category': event.category,
                    'subcategory': event.subcategory,
                    'event_popularity': event.event_popularity,
                    'attendee_count': event.get_attendee_count()
                },
                'score': score
            })
        
        # Sort by score (highest first)
        scored_events.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit results if count specified
        if count is not None:
            scored_events = scored_events[:count]
            
        return scored_events
    
    def _calculate_event_score(self, event, user, user_interest_map):
        """Calculate a recommendation score for an event based on user preferences"""
        score = 0.5  # Base score
        
        # Category and subcategory matching
        if event.category and event.subcategory:
            category_lower = event.category.lower()
            subcategory_lower = event.subcategory.lower()
            
            # Direct matches
            if category_lower in user_interest_map:
                score += 0.15  # Category match
                
                if subcategory_lower in user_interest_map[category_lower]:
                    score += 0.25  # Subcategory match (more specific)
        
        # Event popularity factor
        if event.event_popularity:
            score += event.event_popularity * 0.15
            
        # Recency factor - prefer newer events
        if event.created_at:
            days_old = (datetime.utcnow() - event.created_at).days
            recency_score = max(0, 0.1 - (days_old / 100) * 0.1)  # Up to 0.1 points for new events
            score += recency_score
            
        # Date proximity factor - prefer events coming soon (but not too soon)
        days_until = event.get_day_difference()
        if days_until > 0:  # Future event
            if days_until <= 7:  # Within a week
                score += 0.1
            elif days_until <= 30:  # Within a month
                score += 0.05
        
        # Location factor - prioritize events in the user's location
        if user.location and event.location and user.location.lower() in event.location.lower():
            score += 0.1
            
        # Distance factor - if we have precise coordinates
        if hasattr(event, 'distance_km') and event.distance_km is not None:
            if event.distance_km < 5:  # Very close
                score += 0.15
            elif event.distance_km < 20:  # Reasonably close
                score += 0.1
            elif event.distance_km < 50:  # Somewhat close
                score += 0.05
        
        # Cap the score at 1.0
        return min(1.0, score)
            
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

        # Process recommendations for template
        recommended_events = []
        for rec in recommendations:
            # Check the response structure - the API now returns event_id directly
            event_id = rec.get('event_id')
            if event_id is None:
                continue  # Skip this recommendation if event_id is missing
                
            event = db.session.get(Event, event_id)
            if event:
                recommended_events.append((event, rec['score']))

        return render_template(
            'recommendations.html',
            recommended_events=recommended_events
        )

    except Exception as e:
        app.logger.error(f"Error in recommendations: {str(e)}")
        flash('Error generating recommendations. Please try again later.', 'error')
        return redirect(url_for('index'))



@app.route('/api/track_interaction', methods=['POST'])
@login_required
def track_interaction():
    """
    Track user interactions with events for improving recommendations
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Validate required fields
        required_fields = ['event_id', 'interaction_type']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Validate event ID
        event_id = data['event_id']
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        # Validate interaction type
        valid_interaction_types = [
            'view',             # User viewed event details
            'click',            # User clicked on event
            'join',             # User joined event
            'leave',            # User left event
            'bookmark',         # User bookmarked event
            'share',            # User shared event
            'calendar_add',     # User added event to calendar
            'recommend_click',  # User clicked on a recommended event
            'impression'        # Event was shown to user
        ]
        
        interaction_type = data['interaction_type']
        if interaction_type not in valid_interaction_types:
            return jsonify({'error': 'Invalid interaction type'}), 400
            
        # Create new interaction record
        interaction = UserEventInteraction(
            user_id=current_user.id,
            event_id=event_id,
            interaction_type=interaction_type,
            timestamp=datetime.now(),
            interaction_metadata=data.get('metadata')
        )
        
        db.session.add(interaction)
        db.session.commit()
        
        # Update event popularity if it's a significant interaction
        significant_interactions = ['join', 'bookmark', 'share', 'calendar_add']
        if interaction_type in significant_interactions:
            # Adjust event popularity based on interaction
            if interaction_type == 'join':
                # Joining an event is a strong signal, boost popularity more
                event.event_popularity = min(1.0, event.event_popularity + 0.02)
            else:
                # Other interactions provide smaller boosts
                event.event_popularity = min(1.0, event.event_popularity + 0.01)
                
            db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Interaction tracked successfully',
            'interaction_id': interaction.id
        })
        
    except Exception as e:
        app.logger.error(f"Error tracking interaction: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/trending_events')
def trending_events():
    """
    Get trending events based on recent interactions and popularity
    """
    try:
        # Number of events to return
        limit = request.args.get('limit', default=10, type=int)
        
        # Time period for trending (default: last 7 days)
        days = request.args.get('days', default=7, type=int)
        period_start = datetime.utcnow() - timedelta(days=days)
        
        # Get events with interaction counts
        trending_events = db.session.query(
            Event,
            func.count(UserEventInteraction.id).label('interaction_count')
        ).join(
            UserEventInteraction,
            Event.id == UserEventInteraction.event_id
        ).filter(
            UserEventInteraction.timestamp >= period_start,
            Event.date >= datetime.utcnow()  # Only future events
        ).group_by(
            Event.id
        ).order_by(
            desc('interaction_count'),
            desc(Event.event_popularity)
        ).limit(limit).all()
        
        # Format results
        results = []
        for event, interaction_count in trending_events:
            results.append({
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'location': event.location,
                'date': event.date.isoformat(),
                'popularity': event.event_popularity,
                'interaction_count': interaction_count,
                'attendee_count': event.get_attendee_count(),
                'trending_score': event.calculate_trending_score()
            })
            
        return jsonify({'trending_events': results})
        
    except Exception as e:
        app.logger.error(f"Error getting trending events: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/calendar_events')
@login_required
def user_calendar_events():
    """
    Get events the user has added to their Google Calendar
    """
    try:
        synced_events = EventAttendee.query.filter_by(
            user_id=current_user.id,
            synced_to_calendar=True
        ).all()
        
        events = []
        for attendee in synced_events:
            event = Event.query.get(attendee.event_id)
            if event:
                events.append({
                    'id': event.id,
                    'title': event.title,
                    'date': event.date.isoformat(),
                    'location': event.location,
                    'calendar_event_id': attendee.calendar_event_id
                })
        
        return jsonify({'calendar_events': events})
        
    except Exception as e:
        app.logger.error(f"Error getting calendar events: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync_calendar', methods=['POST'])
@login_required
def sync_calendar():
    """
    Sync an event with Google Calendar
    """
    try:
        data = request.get_json()
        
        if not data or 'event_id' not in data:
            return jsonify({'error': 'Event ID required'}), 400
            
        event_id = data['event_id']
        
        # Check if user is attending the event
        attendee = EventAttendee.query.filter_by(
            user_id=current_user.id,
            event_id=event_id
        ).first()
        
        if not attendee:
            return jsonify({'error': 'You are not attending this event'}), 400
            
        # Update calendar sync status
        attendee.synced_to_calendar = True
        attendee.calendar_event_id = data.get('calendar_event_id')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Calendar synced successfully'})
        
    except Exception as e:
        app.logger.error(f"Error syncing calendar: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


from webapp.commands import seed_db_command
app.cli.add_command(seed_db_command)
if __name__ == '__main__':
    required_env_vars = ['SERPAPI_KEY', 'SECRET_KEY', 'DATABASE_URL', 'AI_API']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"WARNING: Missing environment variables: {', '.join(missing_vars)}")
        exit(1)
    app.run(host='0.0.0.0',port=8080,debug=True, use_reloader=False)