from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import keras
import os
from dotenv import load_dotenv
load_dotenv(".env.local")
from serpAPIService import EventService

# Suppress TensorFlow INFO and WARNING messages (only show errors)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from sklearn.preprocessing import StandardScaler, LabelEncoder

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_event_organizer.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load the trained model
model = keras.models.load_model('event_recommendation_model.keras')

# Initialize StandardScaler and LabelEncoder
scaler = StandardScaler()
le = LabelEncoder()

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

from sqlalchemy import inspect

def init_db():
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        print("Current tables:", inspector.get_table_names())

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    privacy = db.Column(db.String(20), nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_popularity = db.Column(db.Float, default=0.5)



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Preprocessing function
def preprocess_test_data(df):
    # Create a copy to avoid modifying the original
    df = df.copy()
    
    # Ensure all required columns exist
    required_columns = ['timestamp', 'birthyear', 'joinedAt', 'gender', 'locale', 'location']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Convert timestamp to datetime if it isn't already
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Feature engineering
    df['user_age'] = datetime.now().year - df['birthyear']
    df['days_since_joined'] = (datetime.now() - pd.to_datetime(df['joinedAt'])).dt.total_seconds() / (24 * 3600)
    df['hour_of_day'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    
    # Encode categorical variables
    categorical_cols = ['gender', 'locale', 'location']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = le.fit_transform(df[col].astype(str))
    
    # Normalize numerical features
    numerical_cols = ['birthyear', 'timezone', 'user_age', 'days_since_joined']
    present_numerical_cols = [col for col in numerical_cols if col in df.columns]
    if present_numerical_cols:
        df[present_numerical_cols] = scaler.fit_transform(df[present_numerical_cols])
    
    return df

# Feature selection function
def select_features(df):
    features = ['user', 'event', 'invited', 'user_age', 'days_since_joined', 'hour_of_day', 'day_of_week',
                'gender', 'locale', 'location', 'timezone', 'event_popularity']
    return df[features]

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
    
    return render_template('index.html', events=events)

@app.route('/api/events')
def api_events():
    event_service = EventService(os.getenv('SERPAPI_KEY'))
    
    # Get location parameters
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    
    # Get other filter parameters
    query = request.args.get('q')
    date = request.args.get('date')
    page = int(request.args.get('page', 1))
    
    # If we have coordinates, convert to location string
    location = None
    if lat and lng:
        try:
            import requests
            response = requests.get(
                f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json",
                headers={'User-Agent': 'EventFlowAI/1.0'}
            )
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})
                # Try to get city, state, or country
                location = address.get('city') or address.get('state') or address.get('country')
        except Exception as e:
            app.logger.error(f"Error in reverse geocoding: {e}")
    
    # If location lookup failed, use a default radius around coordinates
    if not location and lat and lng:
        location = f"{lat},{lng}"
    
    try:
        events = event_service.search_events(
            query=query,
            location=location,
            date=date,
            page=page
        )
        return jsonify(events)
    except Exception as e:
        app.logger.error(f"Error fetching events: {e}")
        return jsonify([])



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
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
            date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
            privacy=request.form['privacy'],
            organizer_id=current_user.id,
            event_popularity=float(request.form['event_popularity'])
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created successfully')
        return redirect(url_for('index'))
    return render_template('create_event.html')

@app.route('/my_events')
@login_required
def my_events():
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    return render_template('my_events.html', events=events)

@app.route('/recommendations')
@login_required
def recommendations():
    # Get all public events
    public_events = Event.query.filter_by(privacy='public').all()
    
    if not public_events:
        flash('No public events available for recommendations.')
        return redirect(url_for('index'))

    # Prepare data for prediction
    current_time = datetime.now()
    test_data = []
    
    for event in public_events:
        test_data.append({
            'user': current_user.id,
            'event': event.id,
            'invited': 0,  # Assume not invited for simplicity
            'timestamp': current_time,
            'birthyear': current_user.birthyear,
            'gender': current_user.gender,
            'locale': current_user.locale,
            'location': current_user.location,
            'timezone': current_user.timezone,
            'joinedAt': current_user.joinedAt,
            'event_popularity': event.event_popularity
        })

    # Convert to DataFrame
    test_data = pd.DataFrame(test_data)

    try:
        # Validate required columns exist
        required_columns = ['timestamp', 'birthyear', 'joinedAt', 'gender', 'locale', 'location']
        missing_columns = [col for col in required_columns if col not in test_data.columns]
        
        if missing_columns:
            app.logger.error(f"Missing columns in test_data: {missing_columns}")
            # Check if any user data is missing
            if not current_user.birthyear or not current_user.gender or \
               not current_user.locale or not current_user.location:
                flash('Please complete your profile to get personalized recommendations.', 'warning')
                return redirect(url_for('index'))
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Handle null values before preprocessing
        test_data['birthyear'] = test_data['birthyear'].fillna(1990)  # Use a reasonable default
        test_data['gender'] = test_data['gender'].fillna('unknown')
        test_data['locale'] = test_data['locale'].fillna('unknown')
        test_data['location'] = test_data['location'].fillna('unknown')
        test_data['timezone'] = test_data['timezone'].fillna(0)
        
        # Preprocess the test data
        test_data_processed = preprocess_test_data(test_data)

        # Select features
        X_test = select_features(test_data_processed)

        # Make predictions
        predictions = model.predict([
            X_test['user'], 
            X_test['event'], 
            X_test.drop(['user', 'event'], axis=1)
        ])
        
        # Add predictions to the results
        event_predictions = list(zip(public_events, predictions.flatten()))
        
        # Sort events by predicted interest and get top 10
        recommended_events = sorted(
            event_predictions, 
            key=lambda x: x[1], 
            reverse=True
        )[:10]

        return render_template(
            'recommendations.html', 
            recommended_events=recommended_events
        )
        
    except Exception as e:
        app.logger.error(f"Error in recommendations: {str(e)}")
        flash('Error generating recommendations. Please try again later.', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, use_reloader=False)