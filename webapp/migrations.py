# webapp/migrations.py
from flask import Flask
from flask_migrate import Migrate
import os
from dotenv import load_dotenv

# Use relative imports with the webapp package name
from webapp.models import db, User, UserInterests, EventAttendee, Event

load_dotenv(".env.local")

def create_app():
    """Create Flask application for migrations."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/event_organizer")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database with the app
    db.init_app(app)
    
    # Setup Flask-Migrate
    migrate = Migrate(app, db)
    
    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # This is just a placeholder - actual migrations are run with Flask-Migrate commands
        print("Migration app created. Use Flask-Migrate commands to manage migrations.")