# update_events.py
# Run this script to update existing events with categories

from webapp import app, db
from webapp.models import Event
import re

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

# Subcategory mappings
SUBCATEGORY_MAPPINGS = {
    'Tech': {
        'ai': 'AI & Machine Learning',
        'machine learning': 'AI & Machine Learning',
        'artificial intelligence': 'AI & Machine Learning',
        'blockchain': 'Blockchain',
        'cryptocurrency': 'Blockchain',
        'code': 'Programming',
        'programming': 'Programming',
        'developer': 'Programming',
        'software': 'Programming',
        'web': 'Web Development',
        'frontend': 'Web Development',
        'backend': 'Web Development',
        'mobile': 'Mobile Development',
        'app': 'Mobile Development',
        'android': 'Mobile Development',
        'ios': 'Mobile Development',
        'startup': 'Startups',
        'cloud': 'Cloud Computing',
        'aws': 'Cloud Computing',
        'azure': 'Cloud Computing',
        'data': 'Data Science',
        'analytics': 'Data Science',
        'security': 'Cybersecurity',
        'cyber': 'Cybersecurity'
    },
    # Add more subcategory mappings for other categories as needed
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
    
    return best_category, subcategory

def update_events_with_categories():
    """Update events in the database with guessed categories"""
    with app.app_context():
        # Get all events without categories
        events = Event.query.filter(
            (Event.category.is_(None)) | 
            (Event.category == '') |
            (Event.subcategory.is_(None)) | 
            (Event.subcategory == '')
        ).all()
        
        print(f"Found {len(events)} events without complete category information")
        
        updated_count = 0
        for event in events:
            category, subcategory = guess_category(event)
            
            if category:
                print(f"Event '{event.title}': {category} - {subcategory or 'Unknown subcategory'}")
                event.category = category
                if subcategory:
                    event.subcategory = subcategory
                else:
                    # Set a default subcategory if none was found
                    event.subcategory = "General"
                updated_count += 1
            
        db.session.commit()
        print(f"Updated {updated_count} events with categories")

if __name__ == '__main__':
    update_events_with_categories()