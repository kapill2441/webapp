from serpapi import GoogleSearch
from datetime import datetime
import os

class EventService:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def search_events(self, query=None, location=None, date=None, page=1):
        """
        Search for events using SerpApi Google Events
        
        Parameters:
            query (str): Search term for events
            location (str): Location for events
            date (str): Date filter (today, tomorrow, week, month)
            page (int): Page number for pagination
        """
        params = {
            "engine": "google_events",
            "api_key": self.api_key,
            "q": query or "",
            "location": location or "worldwide",
            "htichips": f"date:{date}" if date else None,
            "start": (page - 1) * 10 if page > 1 else 0
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            
            if "events_results" not in results:
                return []
                
            return self._format_events(results["events_results"])
        except Exception as e:
            print(f"Error fetching events: {e}")
            return []
    
    def _format_events(self, events):
        """Format the SerpApi events into our application's format"""
        formatted_events = []
        
        for event in events:
            formatted_event = {
                "title": event.get("title", ""),
                "description": event.get("description", ""),
                "date": self._parse_date(event.get("date", {})),
                "address": event.get("address", []),
                "link": event.get("link", ""),
                "venue": event.get("venue", {}).get("name", ""),
                "thumbnail": event.get("thumbnail", ""),
                "tickets": self._get_ticket_info(event)
            }
            formatted_events.append(formatted_event)
            
        return formatted_events
    
    def _parse_date(self, date_info):
        """Parse the date information from SerpApi format"""
        if isinstance(date_info, dict):
            start_date = date_info.get("start_date", "")
            when = date_info.get("when", "")
            return {
                "start_date": start_date,
                "when": when
            }
        return {"start_date": "", "when": ""}
    
    def _get_ticket_info(self, event):
        """Extract ticket information if available"""
        if "ticket_info" in event:
            return {
                "price": event["ticket_info"].get("price", ""),
                "status": event["ticket_info"].get("status", ""),
                "link": event["ticket_info"].get("link", "")
            }
        return None
