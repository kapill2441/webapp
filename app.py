from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from serpAPIService import EventService

app = Flask(__name__)

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


if __name__ == '__main__':
    init_db()
    app.run(port="0.0.0.0",debug=True, use_reloader=False)