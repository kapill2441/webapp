import os
from flask import redirect, request, url_for, session, current_app, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json

class GoogleCalendarService:
    """Service for integrating with Google Calendar API"""
    
    # Scopes required for Google Calendar
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    
    def __init__(self, app=None):
        self.app = app
        self.client_config = {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")]
            }
        }
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        
    def get_authorization_url(self, user_id):
        """Generate authorization URL for Google OAuth"""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            redirect_uri=self.client_config["web"]["redirect_uris"][0]
        )
        
        # Generate authorization URL and state
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force to show consent screen to get refresh token
        )
        
        # Store state and user_id in session
        session['google_auth_state'] = state
        session['google_auth_user_id'] = user_id
        
        return auth_url
        
    def handle_auth_callback(self):
        """Handle OAuth callback from Google"""
        from webapp.models import db, User
        
        # Get state and code from callback
        state = request.args.get('state')
        code = request.args.get('code')
        
        # Verify state matches
        if state != session.get('google_auth_state'):
            flash('Authentication failed: State mismatch.', 'error')
            return False
            
        # Get user_id from session
        user_id = session.get('google_auth_user_id')
        if not user_id:
            flash('Authentication failed: User ID not found.', 'error')
            return False
            
        # Create flow object
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            redirect_uri=self.client_config["web"]["redirect_uris"][0],
            state=state
        )
        
        # Exchange code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Update user with token information
        user = User.query.get(user_id)
        if user:
            user.google_calendar_token = credentials.token
            user.google_calendar_refresh_token = credentials.refresh_token
            user.google_calendar_token_expiry = datetime.fromtimestamp(credentials.expiry.timestamp())
            user.calendar_sync_enabled = True
            db.session.commit()
            return True
        
        return False
        
    def get_credentials(self, user):
        """Get valid credentials for a user"""
        if not user.google_calendar_token:
            return None
            
        # Create credentials object
        creds = Credentials(
            token=user.google_calendar_token,
            refresh_token=user.google_calendar_refresh_token,
            token_uri=self.client_config["web"]["token_uri"],
            client_id=self.client_config["web"]["client_id"],
            client_secret=self.client_config["web"]["client_secret"],
            scopes=self.SCOPES
        )
        
        # Check if credentials are expired and refresh if needed
        if user.google_calendar_token_expiry and user.google_calendar_token_expiry < datetime.utcnow():
            from webapp.models import db
            
            # Request does not exist in this context, so create a new refresh request
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            
            creds.refresh(request)
            
            # Update tokens in database
            user.google_calendar_token = creds.token
            if creds.refresh_token:  # Only update if a new refresh token was provided
                user.google_calendar_refresh_token = creds.refresh_token
            user.google_calendar_token_expiry = datetime.fromtimestamp(creds.expiry.timestamp())
            db.session.commit()
            
        return creds
        
    def add_event_to_calendar(self, user, event, notify=False):
        """Add an event to user's Google Calendar"""
        from webapp.models import db, EventAttendee
        
        # Get credentials
        credentials = self.get_credentials(user)
        if not credentials:
            return False, "Google Calendar not connected"
            
        # Build the Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Validate event date
        start_datetime = event.date
        if not start_datetime:
            return False, "Event has no start date"
        
        # Make sure start_datetime has time component
        if isinstance(start_datetime, datetime) and start_datetime.hour == 0 and start_datetime.minute == 0 and start_datetime.second == 0:
            # If it's midnight exactly, it might be just a date without time
            # Set a default time like 9:00 AM
            start_datetime = datetime.combine(start_datetime.date(), datetime.min.time()) + timedelta(hours=9)
        
        # Calculate end_datetime - ensure it's at least 30 minutes after start
        if event.end_date and event.end_date > start_datetime:
            end_datetime = event.end_date
        else:
            # Default to 2 hours after start
            end_datetime = start_datetime + timedelta(hours=2)
        
        # Ensure times are different by at least some amount
        if end_datetime <= start_datetime:
            end_datetime = start_datetime + timedelta(minutes=30)
        
        # Log the date values for debugging
        current_app.logger.debug(f"Event dates: start={start_datetime}, end={end_datetime}")
        
        # Create calendar event
        calendar_event = {
            'summary': event.title,
            'location': event.location,
            'description': event.description,
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'UTC',  # Ideally use the user's timezone
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'UTC',  # Ideally use the user's timezone
            },
            'reminders': {
                'useDefault': True
            }
        }
        
        try:
            # Insert event to calendar
            created_event = service.events().insert(
                calendarId='primary',
                body=calendar_event,
                sendNotifications=notify
            ).execute()
            
            # Update event_attendee record
            attendee = EventAttendee.query.filter_by(
                user_id=user.id,
                event_id=event.id
            ).first()
            
            if attendee:
                attendee.synced_to_calendar = True
                attendee.calendar_event_id = created_event['id']
                db.session.commit()
            
            return True, created_event['id']
            
        except Exception as e:
            current_app.logger.error(f"Error adding event to calendar: {str(e)}")
            return False, str(e)
            
    def remove_event_from_calendar(self, user, calendar_event_id):
        """Remove an event from user's Google Calendar"""
        # Get credentials
        credentials = self.get_credentials(user)
        if not credentials:
            return False, "Google Calendar not connected"
            
        # Build the Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        try:
            # Delete event from calendar
            service.events().delete(
                calendarId='primary',
                eventId=calendar_event_id
            ).execute()
            
            return True, "Event removed from calendar"
            
        except Exception as e:
            current_app.logger.error(f"Error removing event from calendar: {str(e)}")
            return False, str(e)