# webapp/app.py
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from webapp.recommendation_service import EnhancedRecommendationService
from webapp.google_calendar import GoogleCalendarService
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


# Add custom Jinja filters
@app.template_filter('attr_list')
def get_attr_list(obj):
    """
    Returns a list of available attributes/methods on an object.
    Usage in template: {% if 'method_name' in object|attr_list %}
    """
    return dir(obj)


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
    # Get user interests to pass to template
    user_interests = UserInterests.query.filter_by(user_id=current_user.id).all()
    return render_template('home.html', current_user=current_user,user_interests=user_interests)    

@app.route('/api/events')
def api_events():
    app.logger.debug("Received request for events API")
    event_service = EventService(os.getenv('SERPAPI_KEY'))
    
    # Get location parameters
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    location = request.args.get('location')  # Direct location string (city, address, etc.)
    
    # Debug log the coordinates
    app.logger.debug(f"Received coordinates: lat={lat}, lng={lng}")
    app.logger.debug(f"Received location: {location}")
    
    # Get other filter parameters
    query = request.args.get('q')
    date = request.args.get('date')
    page = int(request.args.get('page', 1))
    
    # If we have coordinates, convert to location string (if no direct location was provided)
    resolved_location = None
    if lat and lng and not location:
        try:
            app.logger.debug(f"Attempting reverse geocoding for coordinates: {lat}, {lng}")
            response = requests.get(
                f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json",
                headers={'User-Agent': 'EventFlowAI/1.0'}
            )
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})
                
                # Try to get location at different levels - from most specific to least
                # Prefer city, state/province, or country to avoid too-specific locations
                resolved_location = (
                    address.get('city') or 
                    address.get('county') or 
                    address.get('state') or 
                    address.get('country')
                )
                
                # If all we got was a specific location (ward, neighborhood), use country instead
                if not resolved_location and ('ward' in address or 'suburb' in address or 'neighbourhood' in address):
                    resolved_location = address.get('country')
                
                app.logger.debug(f"Reverse geocoded location: {resolved_location}")
        except Exception as e:
            app.logger.error(f"Error in reverse geocoding: {e}")
    
    # If reverse geocoding failed or returned something too specific, try coordinates
    if not resolved_location and lat and lng:
        # For SerpAPI, the format is typically "latitude,longitude"
        resolved_location = f"{lat},{lng}"
        app.logger.debug(f"Using coordinate-based location: {resolved_location}")
    
    # Use provided location if no coordinates or geocoding failed
    final_location = location or resolved_location
    
    # If user is logged in and we still don't have location, use their profile location
    if not final_location and current_user.is_authenticated and current_user.location:
        final_location = current_user.location
        app.logger.debug(f"Using user profile location: {final_location}")
    
    # Final fallback to a nearby major city if we still couldn't resolve location
    if not final_location:
        # Default to a major city that SerpAPI definitely supports
        final_location = "Nairobi"  # Assuming this is in Kenya based on the coordinates
        app.logger.debug(f"Using fallback location: {final_location}")

    # Try to search for events
    events = []
    try:
        # Search for events using the EventService
        events = event_service.search_events(
            query=query,
            location=final_location,
            date=date,
            page=page
        )
        
        # If no events found and we have a specific location, try with a broader location
        if not events and final_location and "," not in final_location and final_location != "Nairobi":
            app.logger.debug(f"No events found with location '{final_location}', trying with broader location")
            # Try with a broader location (country or major city)
            if current_user.is_authenticated and current_user.location:
                broader_location = current_user.location.split(',')[0]  # Take the first part of location
                app.logger.debug(f"Trying with user's broader location: {broader_location}")
                events = event_service.search_events(query=query, location=broader_location, date=date, page=page)
            
            # Final fallback to "Nairobi" if still no events
            if not events:
                app.logger.debug("Still no events, trying with Nairobi")
                events = event_service.search_events(query=query, location="Nairobi", date=date, page=page)
    except Exception as e:
        app.logger.error(f"Error searching events: {e}")
        # Return empty list in case of errors
    
    # Return JSON response
    return jsonify({
        'events': events,
        'meta': {
            'location': final_location,
            'query': query,
            'date': date,
            'page': page
        }
    })
    
# Initialize Google Calendar service
google_calendar_service = GoogleCalendarService()
google_calendar_service.init_app(app)

@app.route('/connect_google_calendar')
@login_required
def connect_google_calendar():
    """Start the Google Calendar OAuth flow"""
    auth_url = google_calendar_service.get_authorization_url(current_user.id)
    return redirect(auth_url)

@app.context_processor
def utility_processor():
    def get_attendee(user_id, event_id):
        """Get an attendee record for a specific user and event"""
        from webapp.models import EventAttendee
        return EventAttendee.query.filter_by(
            user_id=user_id, 
            event_id=event_id
        ).first()
    
    return {'get_attendee': get_attendee}


@app.route('/browse_local_events')
@login_required
def browse_local_events():
    # Get all events from the database (not from SerpAPI)
    all_events = Event.query.filter_by(privacy='public').all()
    return render_template('browse_local_events.html', events=all_events)

# Update your Google Calendar callback route to match your REDIRECT_URI
@app.route('/auth/google/callback')
def google_auth_callback():
    """Handle Google OAuth callback"""
    success = google_calendar_service.handle_auth_callback()
    
    if success:
        flash('Successfully connected to Google Calendar!', 'success')
    else:
        flash('Failed to connect to Google Calendar.', 'error')
        
    return redirect(url_for('joined_events'))

@app.route('/api/add_to_calendar/<int:event_id>', methods=['POST'])
@login_required
def add_to_calendar(event_id):
    """Add an event to the user's Google Calendar"""
    event = Event.query.get_or_404(event_id)
    
    # Check if user is attending the event
    is_attending = EventAttendee.query.filter_by(user_id=current_user.id, event_id=event_id).first()
    if not is_attending:
        return jsonify({'error': 'You must join this event before adding it to your calendar'}), 400
    
    # Check if user has connected Google Calendar
    if not current_user.calendar_sync_enabled or not current_user.google_calendar_token:
        return jsonify({'error': 'Please connect your Google Calendar first'}), 400
    
    # Add event to calendar
    success, result = google_calendar_service.add_event_to_calendar(current_user, event)
    
    if success:
        return jsonify({'success': True, 'message': 'Event added to your Google Calendar', 'calendar_event_id': result})
    else:
        return jsonify({'error': f'Failed to add event to calendar: {result}'}), 500

@app.route('/api/remove_from_calendar/<int:event_id>', methods=['POST'])
@login_required
def remove_from_calendar(event_id):
    """Remove an event from the user's Google Calendar"""
    attendee = EventAttendee.query.filter_by(user_id=current_user.id, event_id=event_id).first()
    
    if not attendee or not attendee.synced_to_calendar or not attendee.calendar_event_id:
        return jsonify({'error': 'Event not found in your calendar'}), 400
    
    # Remove from calendar
    success, result = google_calendar_service.remove_event_from_calendar(
        current_user, 
        attendee.calendar_event_id
    )
    
    if success:
        # Update the attendee record
        attendee.synced_to_calendar = False
        attendee.calendar_event_id = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Event removed from your Google Calendar'})
    else:
        return jsonify({'error': f'Failed to remove event from calendar: {result}'}), 500


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
        # Create a new event with category and subcategory
        event = Event(
            title=request.form['title'],
            description=request.form['description'],
            location=request.form['location'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
            privacy=request.form['privacy'],
            organizer_id=current_user.id,
            event_popularity=float(request.form['event_popularity']),
            # Add category and subcategory
            category=request.form['category'],
            subcategory=request.form['subcategory'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(event)
        db.session.commit()
        
        # Track this as an interaction
        interaction = UserEventInteraction(
            user_id=current_user.id,
            event_id=event.id,
            interaction_type='create',
            timestamp=datetime.utcnow()
        )
        db.session.add(interaction)
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
        # Update category and subcategory
        event.category = request.form['category']
        event.subcategory = request.form['subcategory']
        event.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Track this as an interaction
        interaction = UserEventInteraction(
            user_id=current_user.id,
            event_id=event.id,
            interaction_type='edit',
            timestamp=datetime.utcnow()
        )
        db.session.add(interaction)
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

          
# Initialize recommendation service
ai_api = os.getenv("AI_API")
recommendation_service = EnhancedRecommendationService(ai_api)

# Update the recommendations route
@app.route('/recommendations')
@login_required
def recommendations():
    try:
        # Get all public events
        public_events = Event.query.filter_by(privacy='public').all()
        
        if not public_events:
            flash('No public events available for recommendations.')
            return redirect(url_for('home'))

        # Get recommendations from enhanced service
        recommendations = recommendation_service.get_recommendations(
            current_user,
            public_events
        )

        # Process recommendations for template
        recommended_events = []
        for rec in recommendations:
            event = rec['event']
            score = rec['score']
            recommended_events.append((event, score))

        return render_template(
            'recommendations.html',
            recommended_events=recommended_events
        )

    except Exception as e:
        app.logger.error(f"Error in recommendations: {str(e)}")
        flash('Error generating recommendations. Please try again later.', 'error')
        return redirect(url_for('index'))

@app.route('/update_preferences', methods=['GET', 'POST'])
@login_required
def update_preferences():
    """Update user preferences/interests after registration"""
    if request.method == 'POST':
        # Clear existing interests
        UserInterests.query.filter_by(user_id=current_user.id).delete()
        
        # Get selected interests from form
        interests = request.form.getlist('interests[]')
        
        # Save new interests
        for interest in interests:
            try:
                category, subcategory = interest.split(':', 1)
                new_interest = UserInterests(
                    user_id=current_user.id,
                    category=category,
                    subcategory=subcategory,
                    strength=1.0,  # Default strength
                    created_at=datetime.now()
                )
                db.session.add(new_interest)
            except ValueError:
                # Skip interests that don't have the correct format
                app.logger.warning(f"Skipping invalid interest format: {interest}")
                continue
        
        db.session.commit()
        flash('Your preferences have been updated successfully!', 'success')
        return redirect(url_for('recommendations'))
    
    # GET request - show the form
    # Get current user interests for pre-filling the form
    user_interests = []
    interests = UserInterests.query.filter_by(user_id=current_user.id).all()
    
    for interest in interests:
        user_interests.append(f"{interest.category}:{interest.subcategory}")
    
    return render_template('update_preferences.html', user_interests=user_interests)


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


from webapp.commands import seed_db_command,update_event_categories_command
app.cli.add_command(seed_db_command)
app.cli.add_command(update_event_categories_command)
if __name__ == '__main__':
    required_env_vars = ['SERPAPI_KEY', 'SECRET_KEY', 'DATABASE_URL', 'AI_API']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"WARNING: Missing environment variables: {', '.join(missing_vars)}")
        exit(1)
    app.run(host='0.0.0.0',port=8080,debug=True, use_reloader=False)