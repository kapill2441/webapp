# webapp/commands.py
import click
from flask.cli import with_appcontext
from webapp.models import db, User, UserInterests, Event, EventAttendee, UserEventInteraction
from faker import Faker
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import json

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
    
    seed_database(users, events)
    click.echo(f'Successfully created {users} users, {events} events, and related records.')

def reset_database():
    """Drop all tables and recreate them."""
    db.drop_all()
    db.create_all()

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
    click.echo("Creating users...")
    created_users = create_users(num_users)
    
    click.echo("Adding user interests...")
    add_user_interests(created_users)
    
    click.echo("Creating events...")
    created_events = create_events(num_events, created_users)
    
    click.echo("Creating event attendees and interactions...")
    create_attendees_and_interactions(created_users, created_events)

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
    return users

def add_user_interests(users):
    """Add interests to users."""
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
    
    db.session.commit()

def create_events(num_events, users):
    """Create random events."""
    events = []
    
    for i in range(num_events):
        # Select a random organizer
        organizer = random.choice(users)
        
        # Select a random category and subcategory
        category = random.choice(list(INTEREST_CATEGORIES.keys()))
        subcategory = random.choice(INTEREST_CATEGORIES[category])
        
        # Select a random location (use exact values, no modifications)
        location = random.choice(LOCATIONS)
        
        # Create future or past date for the event
        if random.random() < 0.7:  # 70% chance of a future event
            event_date = fake.date_time_between(start_date='now', end_date='+6m')
            # End date 1-5 hours after start date
            end_date = event_date + timedelta(hours=random.randint(1, 5))
        else:
            event_date = fake.date_time_between(start_date='-6m', end_date=datetime.utcnow())
            end_date = event_date + timedelta(hours=random.randint(1, 5))
        
        # Create event with exact location values
        event = Event(
            title=fake.sentence(nb_words=5)[:-1],  # Remove trailing period
            description=fake.paragraph(nb_sentences=3),
            location=location['name'],
            date=event_date,
            end_date=end_date,
            privacy=random.choice(['public', 'private']),  # Simplified privacy options
            organizer_id=organizer.id,
            event_popularity=random.uniform(0.2, 0.9),
            category=category,
            subcategory=subcategory,
            max_attendees=random.choice([None, 10, 20, 50, 100]),
            is_featured=random.random() < 0.1,  # 10% chance of being featured
            created_at=fake.date_time_between(start_date='-1y', end_date=datetime.utcnow()),
            latitude=location['lat'],  # Use exact latitude
            longitude=location['lng'],  # Use exact longitude
            event_metadata={
                'has_tickets': random.choice([True, False]),
                'price': random.choice([None, 'Free', '$5', '$10', '$25', '$50']),
                'dress_code': random.choice([None, 'Casual', 'Business Casual', 'Formal']),
                'age_restriction': random.choice([None, '18+', '21+'])
            }
        )
        
        db.session.add(event)
        events.append(event)
    
    db.session.commit()
    return events

def create_attendees_and_interactions(users, events):
    """Create event attendees and user-event interactions."""
    # Common interaction types that recommendation systems typically expect
    interaction_types = ['view', 'click', 'join', 'share', 'bookmark']
    
    for event in events:
        # Determine how many users will attend this event (between 0 and 50% of users)
        num_attendees = random.randint(0, len(users) // 2)
        attendee_users = random.sample(users, num_attendees)
        
        for user in attendee_users:
            # Skip if user is the organizer (they're automatically attending)
            if user.id == event.organizer_id:
                continue
                
            # Create attendee record
            joined_at = fake.date_time_between(
                start_date=event.created_at, 
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
            
            # Generate some interactions
            num_interactions = random.randint(1, 5)
            
            for _ in range(num_interactions):
                interaction_type = random.choice(interaction_types)
                timestamp = fake.date_time_between(
                    start_date=event.created_at,
                    end_date=datetime.utcnow()
                )
                
                interaction = UserEventInteraction(
                    user_id=user.id,
                    event_id=event.id,
                    interaction_type=interaction_type,
                    timestamp=timestamp,
                    interaction_metadata={
                        'duration': random.randint(10, 300) if interaction_type == 'view' else None,
                        'source': random.choice(['search', 'recommendation', 'feed'])
                    }
                )
                
                db.session.add(interaction)
    
    # Final commit
    db.session.commit()