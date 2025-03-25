# webapp/recommendation_service.py
"""
Enhanced recommendation service implementing collaborative filtering and personalized recommendations
based on user preferences and interactions.
"""
import os
import math
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask import current_app
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

from webapp.models import db, User, Event, UserInterests, EventAttendee, UserEventInteraction

class EnhancedRecommendationService:
    """
    Service for generating event recommendations using collaborative filtering and personalized preferences.
    User profiles are dynamically updated based on interactions, and collaborative filtering
    is used to find patterns in user behavior.
    """
    
    def __init__(self, api_url):
        """Initialize the recommendation service with API URL"""
        self.api_url = api_url
        self.min_recommendations = 10
        print(f"Initializing EnhancedRecommendationService with API URL: {api_url}")
        
        # Test API connectivity
        try:
            response = requests.get(f"{api_url}/health", timeout=2)
            if response.status_code == 200:
                print("AI API connection successful!")
            else:
                print(f"AI API connection test failed with status: {response.status_code}")
        except requests.RequestException as e:
            print(f"AI API connection test failed: {e}")
            
    def get_recommendations(self, user, events):
        """
        Get personalized event recommendations using AI and collaborative filtering.
        
        User profiles are dynamically updated based on interactions, and collaborative filtering
        is used to find patterns in user behavior. The recommendation engine learns from past
        interactions and adapts over time to provide more relevant suggestions.
        """
        try:
            # Get AI API recommendations first
            api_recommendations = self._get_api_recommendations(user, events)
            
            # If we don't have enough recommendations or API failed, use collaborative filtering
            if len(api_recommendations) < self.min_recommendations:
                print(f"Insufficient API recommendations ({len(api_recommendations)}), using collaborative filtering")
                
                # Get collaborative filtering recommendations
                cf_recommendations = self._get_collaborative_filtering_recommendations(user, events)
                
                # Merge recommendations, prioritizing API recommendations
                combined_recommendations = self._merge_recommendations(api_recommendations, cf_recommendations)
                
                # Ensure minimum number of recommendations
                if len(combined_recommendations) < self.min_recommendations:
                    print(f"Still insufficient recommendations ({len(combined_recommendations)}), adding fallback recommendations")
                    
                    # Add fallback recommendations based on popularity and recency
                    fallback_recommendations = self._get_fallback_recommendations(
                        user, 
                        events, 
                        existing_recommendations=combined_recommendations,
                        count=self.min_recommendations - len(combined_recommendations)
                    )
                    
                    # Add fallback recommendations
                    combined_recommendations.extend(fallback_recommendations)
                
                return combined_recommendations
            
            return api_recommendations
            
        except Exception as e:
            current_app.logger.error(f"Error getting recommendations: {e}")
            # Fallback to simpler recommendation method
            return self._get_fallback_recommendations(user, events, count=self.min_recommendations)
            
    def _get_api_recommendations(self, user, events):
        """
        Get recommendations from the AI API.
        The API uses a neural network model trained to identify personalized event matches.
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
        user_interests = self._get_user_interests(user.id)

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
                    'is_trending': event.calculate_trending_score() > 70,
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
                timeout=60  # Increased timeout
            )
            
            if response.status_code == 200:
                # Get the recommendations from the API response
                api_recommendations = response.json().get('recommendations', [])
                
                # Process the recommendations
                processed_recommendations = []
                for rec in api_recommendations:
                    event_id = rec.get('event_id')
                    if event_id is None:
                        continue
                        
                    event = next((e for e in events if e.id == event_id), None)
                    if event:
                        processed_recommendations.append({
                            'event': event,
                            'score': rec.get('score', 0.5)
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
            
    def _get_collaborative_filtering_recommendations(self, user, events):
        """
        Generate recommendations using collaborative filtering based on user interactions.
        This employs similarity metrics like cosine similarity to find patterns in user behavior.
        """
        try:
            # Get all user interactions
            interactions = UserEventInteraction.query.all()
            
            if not interactions:
                return []
                
            # Create user-event interaction matrix
            user_event_data = []
            
            for interaction in interactions:
                # Weight interaction based on type
                weight = 1.0
                if interaction.interaction_type == 'view':
                    weight = 0.5
                elif interaction.interaction_type == 'click':
                    weight = 0.7
                elif interaction.interaction_type in ['join', 'bookmark']:
                    weight = 1.0
                
                user_event_data.append({
                    'user_id': interaction.user_id,
                    'event_id': interaction.event_id,
                    'weight': weight
                })
                
            # Create DataFrame
            if not user_event_data:
                return []
                
            df = pd.DataFrame(user_event_data)
            
            # Create user-event matrix (pivot table)
            user_event_matrix = df.pivot_table(
                index='user_id',
                columns='event_id',
                values='weight',
                aggfunc='mean',
                fill_value=0
            )
            
            # Get the current user's vector
            if user.id not in user_event_matrix.index:
                return []  # User has no interactions
                
            user_vector = user_event_matrix.loc[user.id]
            
            # Calculate similarity with other users
            similarities = []
            for other_user_id in user_event_matrix.index:
                if other_user_id == user.id:
                    continue
                    
                other_vector = user_event_matrix.loc[other_user_id]
                
                # Calculate cosine similarity
                similarity = self._calculate_cosine_similarity(user_vector, other_vector)
                
                if similarity > 0:
                    similarities.append((other_user_id, similarity))
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Get top similar users
            top_similar_users = [user_id for user_id, _ in similarities[:10]]
            
            if not top_similar_users:
                return []
                
            # Find events that similar users interacted with that the current user hasn't
            user_events = set(UserEventInteraction.query.filter_by(user_id=user.id).with_entities(UserEventInteraction.event_id).all())
            user_events = {event_id for (event_id,) in user_events}
            
            similar_user_interactions = UserEventInteraction.query.filter(
                UserEventInteraction.user_id.in_(top_similar_users),
                ~UserEventInteraction.event_id.in_(user_events) if user_events else True
            ).all()
            
            # Count interactions by event
            event_scores = defaultdict(float)
            event_counts = defaultdict(int)
            
            for interaction in similar_user_interactions:
                # Get similarity of the user who interacted
                similarity = next((sim for uid, sim in similarities if uid == interaction.user_id), 0)
                
                # Weight by similarity and interaction type
                weight = 0.5  # Default
                if interaction.interaction_type == 'view':
                    weight = 0.3
                elif interaction.interaction_type == 'click':
                    weight = 0.5
                elif interaction.interaction_type == 'join':
                    weight = 1.0
                elif interaction.interaction_type == 'bookmark':
                    weight = 0.8
                    
                # Add weighted score
                event_scores[interaction.event_id] += weight * similarity
                event_counts[interaction.event_id] += 1
            
            # Calculate average scores
            cf_recommendations = []
            
            for event_id, score in event_scores.items():
                count = event_counts[event_id]
                if count > 0:
                    avg_score = score / count
                    
                    # Find event object
                    event = next((e for e in events if e.id == event_id), None)
                    if event:
                        cf_recommendations.append({
                            'event': event,
                            'score': min(avg_score, 1.0)  # Cap at 1.0
                        })
            
            # Sort by score
            cf_recommendations.sort(key=lambda x: x['score'], reverse=True)
            
            return cf_recommendations
            
        except Exception as e:
            print(f"Error in collaborative filtering: {e}")
            return []
    
    def _calculate_cosine_similarity(self, vector1, vector2):
        """Calculate cosine similarity between two vectors"""
        # Handle empty vectors
        if vector1.sum() == 0 or vector2.sum() == 0:
            return 0
            
        # Calculate dot product
        dot_product = np.dot(vector1, vector2)
        
        # Calculate magnitudes
        magnitude1 = np.sqrt(np.sum(vector1**2))
        magnitude2 = np.sqrt(np.sum(vector2**2))
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
            
        # Calculate cosine similarity
        return dot_product / (magnitude1 * magnitude2)
    
    def _merge_recommendations(self, api_recs, cf_recs):
        """Merge recommendations from different sources, avoiding duplicates"""
        # Create a set of event IDs from API recommendations
        api_event_ids = {rec['event'].id for rec in api_recs}
        
        # Add API recommendations to final list
        merged_recs = list(api_recs)
        
        # Add collaborative filtering recommendations not already in API results
        for rec in cf_recs:
            if rec['event'].id not in api_event_ids:
                merged_recs.append(rec)
                api_event_ids.add(rec['event'].id)
        
        # Sort by score
        merged_recs.sort(key=lambda x: x['score'], reverse=True)
        
        return merged_recs
    
    def _get_fallback_recommendations(self, user, events, existing_recommendations=None, count=10):
        """
        Generate fallback recommendations based on event popularity, recency, and user interests.
        This ensures new events automatically appear in recommendations.
        """
        # Create a set of already recommended event IDs
        recommended_event_ids = set()
        if existing_recommendations:
            recommended_event_ids = {rec['event'].id for rec in existing_recommendations}
        
        # Get user interests
        user_interests = self._get_user_interests(user.id)
        user_interest_map = self._create_interest_map(user_interests)
        
        # Score events based on factors including recency
        scored_events = []
        
        for event in events:
            # Skip already recommended events
            if event.id in recommended_event_ids:
                continue
                
            # Score this event
            interest_match_score = self._calculate_interest_match_score(event, user_interest_map)
            
            # Calculate days since creation (for recency)
            days_since_creation = 365  # Default to a year if no creation date
            if event.created_at:
                delta = datetime.utcnow() - event.created_at
                days_since_creation = delta.days
            
            # Recency boost (exponential decay)
            recency_boost = math.exp(-0.05 * days_since_creation)  # Higher for newer events
            
            # Calculate final score with recency as a significant factor
            final_score = (
                0.4 * interest_match_score +  # 40% interest match
                0.3 * float(event.event_popularity or 0.5) +  # 30% popularity
                0.3 * recency_boost  # 30% recency
            )
            
            scored_events.append({
                'event': event,
                'score': final_score
            })
        
        # Sort by score
        scored_events.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top events up to count
        return scored_events[:count]
    
    def _get_user_interests(self, user_id):
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
    
    def _create_interest_map(self, user_interests):
        """Create a mapping of user interests for quick lookup"""
        interest_map = {
            'categories': set(),
            'subcategories': set()
        }
        
        for interest in user_interests:
            if 'category' in interest and interest['category']:
                interest_map['categories'].add(interest['category'].lower())
            if 'subcategory' in interest and interest['subcategory']:
                interest_map['subcategories'].add(interest['subcategory'].lower())
        
        return interest_map
    
    def _calculate_interest_match_score(self, event, interest_map):
        """Calculate how well an event matches user interests"""
        if not interest_map['categories'] and not interest_map['subcategories']:
            return 0.5  # Neutral score if no interests
        
        # Check for category match
        category_match = False
        subcategory_match = False
        
        if event.category:
            category_match = event.category.lower() in interest_map['categories']
            
        if event.subcategory:
            subcategory_match = event.subcategory.lower() in interest_map['subcategories']
        
        # Calculate score
        if subcategory_match:
            return 1.0  # Perfect match
        elif category_match:
            return 0.8  # Good match
        else:
            # Check for partial matches in description
            if event.description:
                desc_lower = event.description.lower()
                for subcategory in interest_map['subcategories']:
                    if subcategory in desc_lower:
                        return 0.6  # Partial match
                        
                for category in interest_map['categories']:
                    if category in desc_lower:
                        return 0.5  # Weak match
            
            return 0.3  # No match
    
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