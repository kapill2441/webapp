# webapp/commands.py
import click
from flask.cli import with_appcontext
from webapp.models import db, User, UserInterests, Event, EventAttendee, UserEventInteraction
from faker import Faker
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import json
import math

# Initialize Faker
fake = Faker()

# Interest categories for generating user interests
INTEREST_CATEGORIES = {
    'Music': ['Rock', 'Pop', 'Jazz', 'Classical', 'Hip Hop', 'Electronic', 'Country', 'R&B'],
    'Sports': ['Football', 'Basketball', 'Tennis', 'Swimming', 'Cycling', 'Running', 'Golf', 'Yoga'],
    'Technology': ['AI', 'Web Development', 'Data Science', 'Blockchain', 'Mobile Apps', 'Cybersecurity'],
    'Arts': ['Painting', 'Photography', 'Sculpture', 'Theater', 'Cinema', 'Literature', 'Dance'],
    'Food': ['Fine Dining', 'Cooking', 'Baking', 'Wine Tasting', 'Craft Beer', 'Vegetarian', 'Food Trucks'],
    'Outdoors': ['Hiking', 'Camping', 'Fishing', 'Gardening', 'Climbing', 'Birdwatching', 'Kayaking'],
    'Business': ['Entrepreneurship', 'Marketing', 'Finance', 'Networking', 'Startups', 'Real Estate'],
    'Education': ['Languages', 'Science', 'History', 'Mathematics', 'Psychology', 'Philosophy'],
    'Health': ['Fitness', 'Meditation', 'Nutrition', 'Mental Health', 'Alternative Medicine']
}

# Sample locations with coordinates (precise names to match your expectation)
LOCATIONS = [
    {'name': 'New York, NY', 'lat': 40.7128, 'lng': -74.0060},
    {'name': 'Los Angeles, CA', 'lat': 34.0522, 'lng': -118.2437},
    {'name': 'Chicago, IL', 'lat': 41.8781, 'lng': -87.6298},
    {'name': 'Houston, TX', 'lat': 29.7604, 'lng': -95.3698},
    {'name': 'Phoenix, AZ', 'lat': 33.4484, 'lng': -112.0740},
    {'name': 'Philadelphia, PA', 'lat': 39.9526, 'lng': -75.1652},
    {'name': 'San Francisco, CA', 'lat': 37.7749, 'lng': -122.4194},
    {'name': 'Seattle, WA', 'lat': 47.6062, 'lng': -122.3321},
    {'name': 'Boston, MA', 'lat': 42.3601, 'lng': -71.0589},
    {'name': 'Austin, TX', 'lat': 30.2672, 'lng': -97.7431}
]

# Common gender values that recommendation systems typically expect
GENDER_VALUES = ['male', 'female', 'unknown']

# Common locale values (simpler than Faker's wide range)
LOCALE_VALUES = ['en_US', 'en_GB', 'es_ES', 'fr_FR', 'de_DE', 'it_IT', 'ja_JP', 'zh_CN']

# Common timezone values
TIMEZONE_VALUES = [-8, -7, -6, -5, -4, 0, 1, 2]


import click
from flask.cli import with_appcontext
from webapp.models import db, Event, User, UserInterests, EventAttendee
import re
from datetime import datetime, timedelta
import random

# Add this to your existing commands.py file

@click.command('update-event-categories')
@with_appcontext
def update_event_categories_command():
    """Update existing events with categories based on their title and description."""
    # Common keywords that might indicate categories
    CATEGORY_KEYWORDS = {
        'Tech': ['technology', 'tech', 'coding', 'programming', 'developers', 'software', 'hardware', 'ai', 'machine learning', 'data', 'computer', 'digital', 'cyber', 'cloud', 'blockchain', 'hackathon'],
        'Business': ['business', 'entrepreneur', 'startup', 'finance', 'marketing', 'leadership', 'management', 'networking', 'career', 'investment', 'funding', 'venture', 'corporate'],
        'Arts': ['art', 'museum', 'gallery', 'exhibition', 'creative', 'design', 'photography', 'film', 'movie', 'theater', 'theatre', 'dance', 'painting', 'sculpture', 'drawing', 'literature', 'poetry', 'writing'],
        'Community': ['community', 'volunteer', 'charity', 'nonprofit', 'social', 'activism', 'environment', 'sustainability', 'local', 'neighborhood'],
        'Health': ['health', 'wellness', 'fitness', 'yoga', 'meditation', 'mindfulness', 'nutrition', 'diet', 'mental health', 'healthcare', 'medical'],
        'Sports': ['sport', 'athletic', 'running', 'marathon', 'cycling', 'swimming', 'hiking', 'climbing', 'football', 'soccer', 'basketball', 'baseball', 'tennis', 'golf'],
        'Food': ['food', 'cooking', 'cuisine', 'culinary', 'chef', 'restaurant', 'dining', 'baking', 'wine', 'beer', 'cocktail', 'tasting', 'gastronomy'],
        'Education': ['education', 'learning', 'school', 'academic', 'university', 'college', 'lecture', 'workshop', 'seminar', 'conference', 'training', 'course', 'class'],
        'Music': ['music', 'concert', 'festival', 'band', 'musician', 'singer', 'performer', 'dj', 'jazz', 'rock', 'classical', 'hip hop', 'rap', 'electronic']
    }

    # Subcategory mappings (short version)
    SUBCATEGORY_MAPPINGS = {
        'Tech': {
            'ai': 'AI & Machine Learning',
            'machine learning': 'AI & Machine Learning',
            'blockchain': 'Blockchain',
            'programming': 'Programming',
            'web': 'Web Development',
            'mobile': 'Mobile Development',
            'startup': 'Startups',
            'cloud': 'Cloud Computing',
            'data': 'Data Science',
            'security': 'Cybersecurity'
        },
        'Business': {
            'network': 'Networking',
            'market': 'Marketing',
            'finance': 'Finance',
            'lead': 'Leadership',
            'startup': 'Entrepreneurship'
        },
        'Arts': {
            'visual': 'Visual Arts',
            'paint': 'Visual Arts',
            'theater': 'Theater',
            'film': 'Film',
            'movie': 'Film', 
            'literature': 'Literature',
            'book': 'Literature'
        }
    }

    # Default subcategories for each category
    DEFAULT_SUBCATEGORIES = {
        'Tech': 'Programming',
        'Business': 'Networking',
        'Arts': 'Visual Arts',
        'Community': 'Volunteering',
        'Health': 'Fitness',
        'Sports': 'Team Sports',
        'Food': 'Dining',
        'Education': 'Workshops',
        'Music': 'Live Music'
    }

    def guess_category(event):
        """Guess the category of an event based on its title and description"""
        if not event.title and not event.description:
            return None, None
        
        text = (event.title + ' ' + (event.description or '')).lower()
        
        # Check for category matches
        category_scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = re.findall(pattern, text)
                score += len(matches)
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            return None, None
        
        # Get category with highest score
        best_category = max(category_scores.items(), key=lambda x: x[1])[0]
        
        # Try to find a subcategory
        subcategory = None
        if best_category in SUBCATEGORY_MAPPINGS:
            for key, value in SUBCATEGORY_MAPPINGS[best_category].items():
                if key in text:
                    subcategory = value
                    break
        
        # Use default subcategory if none found
        if not subcategory and best_category in DEFAULT_SUBCATEGORIES:
            subcategory = DEFAULT_SUBCATEGORIES[best_category]
        
        return best_category, subcategory

    # Get all events without categories
    events = Event.query.filter(
        (Event.category.is_(None)) | 
        (Event.category == '') |
        (Event.subcategory.is_(None)) | 
        (Event.subcategory == '')
    ).all()
    
    click.echo(f"Found {len(events)} events without complete category information")
    
    updated_count = 0
    for event in events:
        category, subcategory = guess_category(event)
        
        if category:
            click.echo(f"Event '{event.title}': {category} - {subcategory or 'Unknown subcategory'}")
            event.category = category
            if subcategory:
                event.subcategory = subcategory
            else:
                # Set a default subcategory if none was found
                event.subcategory = "General"
            
            # Update timestamps if missing
            if not event.created_at:
                event.created_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))
            if not event.updated_at:
                event.updated_at = datetime.utcnow()
                
            updated_count += 1
    
    db.session.commit()
    click.echo(f"Updated {updated_count} events with categories")
    
    
@click.command('seed-db')
@click.option('--users', default=50, help='Number of users to create')
@click.option('--events', default=20, help='Number of events to create')
@click.option('--reset', is_flag=True, help='Reset database before seeding')
@with_appcontext
def seed_db_command(users, events, reset):
    """Seed the database with sample data for testing."""
    if reset:
        click.echo('Resetting database...')
        reset_database()
    
    click.echo(f'Starting database seeding: {users} users, {events} events')
    seed_database(users, events)
    click.echo(f'Successfully created {users} users, {events} events, and related records.')
    
    # Verify data after seeding
    verify_database()

def verify_database():
    """Verify the database has valid data after seeding."""
    click.echo("\nVerifying database:")
    
    user_count = User.query.count()
    click.echo(f"- Users: {user_count}")
    
    interest_count = UserInterests.query.count()
    click.echo(f"- User Interests: {interest_count}")
    
    event_count = Event.query.count()
    click.echo(f"- Events: {event_count}")
    
    attendee_count = EventAttendee.query.count()
    click.echo(f"- Event Attendees: {attendee_count}")
    
    interaction_count = UserEventInteraction.query.count()
    click.echo(f"- User-Event Interactions: {interaction_count}")
    
    # Check for events with null dates (should be none)
    null_date_count = Event.query.filter(Event.date == None).count()
    if null_date_count > 0:
        click.echo(f"WARNING: Found {null_date_count} events with NULL dates!")
    else:
        click.echo("- All events have valid dates")
    
    # Test day difference calculation on a sample event
    sample_event = Event.query.first()
    if sample_event:
        try:
            days_diff = sample_event.get_day_difference()
            click.echo(f"- Sample event day difference calculation: {days_diff} days")
        except Exception as e:
            click.echo(f"ERROR: Day difference calculation failed: {e}")

def reset_database():
    """Drop all tables and recreate them."""
    db.drop_all()
    db.create_all()
    click.echo("Database reset complete - all tables dropped and recreated.")

def seed_database(num_users=50, num_events=20):
    """
    Seed the database with fake users, events, and interactions.
    
    Parameters:
    -----------
    num_users : int
        Number of users to create
    num_events : int
        Number of events to create
    """
    with click.progressbar(length=4, label='Seeding database') as bar:
        click.echo("Creating users...")
        created_users = create_users(num_users)
        bar.update(1)
        
        click.echo("Adding user interests...")
        add_user_interests(created_users)
        bar.update(1)
        
        click.echo("Creating events...")
        created_events = create_events(num_events, created_users)
        bar.update(1)
        
        click.echo("Creating event attendees and interactions...")
        create_attendees_and_interactions(created_users, created_events)
        bar.update(1)

def create_users(num_users):
    """Create fake users with consistent password."""
    # Common password for all users (make testing easier)
    common_password = "password123"
    common_password_hash = generate_password_hash(common_password)
    
    users = []
    
    for i in range(num_users):
        # Select a random location without modification
        location = random.choice(LOCATIONS)
        
        # Generate user data with simplified attribute values
        user = User(
            username=fake.user_name() + str(random.randint(1, 999)),  # Ensure uniqueness
            email=fake.email(),
            password_hash=common_password_hash,
            birthyear=random.randint(1970, 2000),
            gender=random.choice(GENDER_VALUES),  # Use consistent gender values
            locale=random.choice(LOCALE_VALUES),  # Use consistent locale values 
            location=location['name'],  # Use exact location name
            timezone=random.choice(TIMEZONE_VALUES),  # Use consistent timezone values
            joinedAt=fake.date_time_between(start_date='-2y', end_date='now'),
            precise_location_enabled=random.choice([True, False]),
            preferences=json.dumps({
                'email_notifications': random.choice([True, False]),
                'theme': random.choice(['light', 'dark', 'system']),
                'distance_unit': random.choice(['km', 'miles']),
                'privacy': random.choice(['public', 'private', 'friends']),
            })
        )
        
        # Add exact coordinates for users with precise location
        if user.precise_location_enabled:
            user.latitude = location['lat']
            user.longitude = location['lng']
        
        db.session.add(user)
        users.append(user)
    
    db.session.commit()
    click.echo(f"Created {len(users)} users with username:password {users[0].username}:password123")
    return users

def add_user_interests(users):
    """Add interests to users."""
    total_interests = 0
    
    for user in users:
        # Select 1-5 random categories
        selected_categories = random.sample(
            list(INTEREST_CATEGORIES.keys()),
            random.randint(1, min(5, len(INTEREST_CATEGORIES)))
        )
        
        for category in selected_categories:
            # Select 1-3 subcategories from each selected category
            subcategories = random.sample(
                INTEREST_CATEGORIES[category],
                random.randint(1, min(3, len(INTEREST_CATEGORIES[category])))
            )
            
            for subcategory in subcategories:
                interest = UserInterests(
                    user_id=user.id,
                    category=category,
                    subcategory=subcategory,
                    strength=random.uniform(0.4, 1.0),
                    created_at=fake.date_time_between(
                        start_date=user.joinedAt,
                        end_date=datetime.utcnow()
                    )
                )
                db.session.add(interest)
                total_interests += 1
    
    db.session.commit()
    click.echo(f"Added {total_interests} interests to users")

def create_events(num_events, users):
    """Create random events with guaranteed valid dates."""
    events = []
    
    # Get current time for date calculations
    now = datetime.utcnow()
    
    # Create a mix of past and future events
    for i in range(num_events):
        # Select a random organizer
        organizer = random.choice(users)
        
        # Select a random category and subcategory
        category = random.choice(list(INTEREST_CATEGORIES.keys()))
        subcategory = random.choice(INTEREST_CATEGORIES[category])
        
        # Select a random location (use exact values, no modifications)
        location = random.choice(LOCATIONS)
        
        # Create future or past date for the event - ENSURING NO NULL DATES
        is_future = random.random() < 0.7  # 70% chance of a future event
        
        if is_future:
            # Future event: between tomorrow and 6 months ahead
            days_ahead = random.randint(1, 180)
            event_date = now + timedelta(days=days_ahead)
            # End date 1-5 hours after start date
            end_date = event_date + timedelta(hours=random.randint(1, 5))
        else:
            # Past event: between yesterday and 6 months ago
            days_ago = random.randint(1, 180)
            event_date = now - timedelta(days=days_ago)
            end_date = event_date + timedelta(hours=random.randint(1, 5))
        
        # Double-check that dates are not None
        assert event_date is not None, "Event date cannot be None"
        assert end_date is not None, "End date cannot be None"
        
        # Create event with exact location values
        event = Event(
            title=fake.sentence(nb_words=5)[:-1],  # Remove trailing period
            description=fake.paragraph(nb_sentences=3),
            location=location['name'],
            date=event_date,  # Guaranteed to be non-null
            end_date=end_date,  # Guaranteed to be non-null
            privacy=random.choice(['public', 'private']),  # Simplified privacy options
            organizer_id=organizer.id,
            event_popularity=random.uniform(0.2, 0.9),
            category=category,
            subcategory=subcategory,
            max_attendees=random.choice([None, 10, 20, 50, 100]),
            is_featured=random.random() < 0.1,  # 10% chance of being featured
            created_at=fake.date_time_between(
                start_date=event_date - timedelta(days=30),  # Created between 30 days before event
                end_date=min(event_date, now)  # And either the event date or now, whichever is earlier
            ),
            latitude=location['lat'],  # Use exact latitude
            longitude=location['lng'],  # Use exact longitude
            event_metadata=json.dumps({
                'has_tickets': random.choice([True, False]),
                'price': random.choice([None, 'Free', '$5', '$10', '$25', '$50']),
                'dress_code': random.choice([None, 'Casual', 'Business Casual', 'Formal']),
                'age_restriction': random.choice([None, '18+', '21+'])
            })
        )
        
        # Verify that the day difference calculation works for this event
        try:
            # Make a dummy day difference calculation to catch any errors
            current_time = datetime.utcnow()
            delta = event_date - current_time
            days_diff = delta.days
        except Exception as e:
            click.echo(f"WARNING: Day difference calculation failed for new event: {e}")
            click.echo(f"Event date: {event_date}, Current time: {current_time}")
            # Attempt to fix the date
            event.date = now + timedelta(days=random.randint(1, 180))
        
        db.session.add(event)
        events.append(event)
    
    db.session.commit()
    
    # Verify no events have NULL dates
    null_date_events = Event.query.filter(Event.date == None).count()
    if null_date_events > 0:
        click.echo(f"WARNING: {null_date_events} events still have NULL dates after creation!")
    else:
        click.echo(f"Created {len(events)} events with valid dates")
    
    return events

def create_attendees_and_interactions(users, events):
    """Create event attendees and user-event interactions."""
    # Common interaction types that recommendation systems typically expect
    interaction_types = ['view', 'click', 'join', 'share', 'bookmark']
    
    total_attendees = 0
    total_interactions = 0
    
    for event in events:
        # Ensure event.created_at is not None
        if event.created_at is None:
            event.created_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))
            db.session.add(event)
        
        # Determine how many users will attend this event (between 0 and 50% of users)
        num_attendees = random.randint(0, len(users) // 2)
        attendee_users = random.sample(users, num_attendees)
        
        for user in attendee_users:
            # Skip if user is the organizer (they're automatically attending)
            if user.id == event.organizer_id:
                continue
            
            # Create attendee record with safe date handling
            try:
                # Ensure event.created_at is not None for comparison
                event_created = event.created_at or datetime.utcnow() - timedelta(days=random.randint(1, 30))
                
                # Calculate a safe joined_at time (between event creation and either now or event date)
                if event.date > datetime.utcnow():
                    # Future event
                    joined_at = fake.date_time_between(
                        start_date=event_created,
                        end_date=datetime.utcnow()
                    )
                else:
                    # Past event
                    joined_at = fake.date_time_between(
                        start_date=event_created,
                        end_date=min(event.date, datetime.utcnow())
                    )
                
                attendee = EventAttendee(
                    user_id=user.id,
                    event_id=event.id,
                    joined_at=joined_at,
                    status=random.choice(['attending', 'maybe', 'declined']),
                    synced_to_calendar=random.choice([True, False])
                )
                
                if attendee.synced_to_calendar:
                    attendee.calendar_event_id = fake.uuid4()
                    
                db.session.add(attendee)
                total_attendees += 1
                
                # Generate some interactions
                num_interactions = random.randint(1, 5)
                
                for _ in range(num_interactions):
                    interaction_type = random.choice(interaction_types)
                    
                    # Ensure timestamp is not before event creation
                    timestamp = fake.date_time_between(
                        start_date=event_created,
                        end_date=datetime.utcnow()
                    )
                    
                    interaction = UserEventInteraction(
                        user_id=user.id,
                        event_id=event.id,
                        interaction_type=interaction_type,
                        timestamp=timestamp,
                        interaction_metadata=json.dumps({
                            'duration': random.randint(10, 300) if interaction_type == 'view' else None,
                            'source': random.choice(['search', 'recommendation', 'feed'])
                        })
                    )
                    
                    db.session.add(interaction)
                    total_interactions += 1
            
            except Exception as e:
                click.echo(f"Error creating attendee/interaction: {e}")
                continue
    
    # Final commit
    db.session.commit()
    click.echo(f"Created {total_attendees} event attendees and {total_interactions} user-event interactions")

# Add these methods to the Event model
def add_event_model_methods():
    """Add safer versions of methods to the Event model"""
    
    # Add get_day_difference method with better null handling
    if not hasattr(Event, '_original_get_day_difference'):
        Event._original_get_day_difference = Event.get_day_difference
        
        def safe_get_day_difference(self):
            """Calculate days until event, handling None dates safely"""
            if self.date is None:
                return 30  # Default to 30 days in the future
                
            current_time = datetime.utcnow()
            
            # Convert datetime.date to datetime.datetime if needed
            event_date = self.date
            if isinstance(self.date, datetime.date) and not isinstance(self.date, datetime.datetime):
                # Convert date to datetime at midnight
                event_date = datetime.datetime.combine(self.date, datetime.time.min)
            
            try:
                # Calculate difference in days
                delta = event_date - current_time
                return delta.days
            except Exception as e:
                print(f"Error calculating day difference for event {self.id}: {e}")
                return 30  # Default fallback
        
        Event.get_day_difference = safe_get_day_difference
    
    # Add calculate_trending_score with better null handling
    if not hasattr(Event, '_original_calculate_trending_score'):
        Event._original_calculate_trending_score = Event.calculate_trending_score
        
        def safe_calculate_trending_score(self):
            """Calculate a trending score for the event, safely handling None dates"""
            score = 50  # Base score
            
            try:
                # Factor 1: Event popularity (0-100 points)
                if self.event_popularity is not None:
                    popularity_score = float(self.event_popularity) * 100
                    score += popularity_score * 0.3  # 30% weight for popularity
                
                # Factor 2: Recent creation (0-100 points)
                if self.created_at is not None:
                    days_since_created = (datetime.utcnow() - self.created_at).days
                    recency_score = max(0, 100 - days_since_created * 5)  # 5 points per day
                    score += recency_score * 0.2  # 20% weight for recency
                
                # Factor 3: Upcoming event (0-100 points)
                if self.date is not None:
                    days_until = self.get_day_difference()
                    if days_until >= 0:  # Future event
                        if days_until <= 7:  # Very soon (within a week)
                            proximity_score = 100 - (days_until * 10)  # Closer is better
                        elif days_until <= 30:  # Soon (within a month)
                            proximity_score = 40 - ((days_until - 7) * 1)  # Gradual decrease
                        else:  # Further away
                            proximity_score = max(0, 40 - ((days_until - 30) * 0.5))  # Slow decline
                        score += proximity_score * 0.2  # 20% weight for date proximity
                
                # Factor 4: Attendee count (0-100 points)
                attendee_count = self.get_attendee_count()
                if attendee_count > 0:
                    # Logarithmic scale to favor events with more attendees
                    attendee_score = min(100, 20 * math.log2(attendee_count + 1))
                    score += attendee_score * 0.3  # 30% weight for attendees
                
                return min(100, max(0, score))  # Ensure score is between 0-100
            except Exception as e:
                print(f"Error calculating trending score for event {self.id}: {e}")
                return 50  # Default score on error
        
        Event.calculate_trending_score = safe_calculate_trending_score

    click.echo("Updated Event model methods for safer date handling")