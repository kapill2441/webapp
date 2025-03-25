# webapp/serpAPIService.py
from serpapi import GoogleSearch
from datetime import datetime, date, timedelta
import os

class EventService:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def search_events(self, query=None, location=None, date=None, page=1):
        """
        Search for events using SerpApi Google Events with improved search parameters
        """
        print(f"EventService.search_events called with: query={query}, location={location}, date={date}, page={page}")
        
        # Ensure we have a meaningful search query
        search_query = []
        if query:
            search_query.append(query)
        
        # Handle location in query differently depending on format
        if location:
            # Check if location is coordinates (contains a comma)
            if ',' in location and not any(c.isalpha() for c in location):
                # For coordinate-based locations, don't add "events in" to the query
                search_query.append("events")
            else:
                # For named locations, add "events in" to improve results
                search_query.append(f"events in {location}")
        elif not query:
            # Default to "upcoming events" if no query or location
            search_query.append("upcoming events")
            
        # Join search terms
        final_query = " ".join(search_query)
        
        # Prepare date parameter
        date_param = self._prepare_date_param(date)
        
        params = {
            "engine": "google_events",
            "api_key": self.api_key,
            "q": final_query,
            "start": (page - 1) * 10 if page > 1 else 0
        }
        
        # Add location if specified (separate from query)
        # For coordinate-based locations, we always want to include in both q and location
        if location:
            # For coordinate locations, strip any spaces
            if ',' in location and not any(c.isalpha() for c in location):
                params["location"] = location.replace(" ", "")
            else:
                params["location"] = location
            
        # Add date parameter if specified
        if date_param:
            params["htichips"] = date_param
            
        print(f"Final SerpAPI parameters: {params}")
        
        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            print(f"SerpAPI response received: {'events_results' in results}")
            
            if "error" in results:
                print(f"SerpAPI error: {results['error']}")
                
                # If location error, try again without the location parameter
                if "location parameter" in results["error"] and location:
                    print("Location error detected, trying without location parameter")
                    
                    # Remove location parameter but keep it in the query
                    params.pop("location", None)
                    
                    # Try search again
                    search = GoogleSearch(params)
                    results = search.get_dict()
                    
                    if "error" in results:
                        print(f"Still got error: {results['error']}")
                        return []
                    
                    if "events_results" not in results:
                        print("No events_results in second attempt response")
                        return []
                        
                    formatted_events = self._format_events(results["events_results"])
                    print(f"Formatted {len(formatted_events)} events from second attempt")
                    return formatted_events
                else:
                    return []
            
            if "events_results" not in results:
                print("No events_results in response")
                return []
            
            formatted_events = self._format_events(results["events_results"])
            print(f"Formatted {len(formatted_events)} events")
            return formatted_events
            
        except Exception as e:
            print(f"Error fetching events: {str(e)}")
            return []
    
    def _prepare_date_param(self, date_str):
        """
        Prepare the date parameter for SerpAPI
        """
        if not date_str:
            return "date:upcoming"  # Default to upcoming events
            
        try:
            # Parse the input date
            if isinstance(date_str, str):
                event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            elif isinstance(date_str, (datetime, date)):
                event_date = date_str.date() if isinstance(date_str, datetime) else date_str
            else:
                return "date:upcoming"
                
            today = date.today()
            
            # Determine appropriate date filter
            if event_date == today:
                return "date:today"
            elif event_date == today + timedelta(days=1):
                return "date:tomorrow"
            elif event_date < today + timedelta(days=7):
                return "date:week"
            elif event_date < today + timedelta(days=30):
                return "date:month"
            else:
                return "date:upcoming"
                
        except ValueError:
            return "date:upcoming"
    
    def _format_events(self, events):
        """Format the SerpApi events into our application's format"""
        formatted_events = []
        
        for event in events:
            try:
                formatted_event = {
                    "title": event.get("title", ""),
                    "description": event.get("description", ""),
                    "date": self._parse_date(event),
                    "address": event.get("address", []),
                    "link": event.get("link", ""),
                    "venue": event.get("venue", {}).get("name", "") if isinstance(event.get("venue"), dict) else "",
                    "thumbnail": event.get("thumbnail", ""),
                    "tickets": self._get_ticket_info(event)
                }
                formatted_events.append(formatted_event)
            except Exception as e:
                print(f"Error formatting event: {str(e)}")
                continue
            
        return formatted_events
    
    def _parse_date(self, event):
        """Parse the date information from SerpApi format"""
        try:
            # Handle both direct date field and nested date object
            date_info = event.get("date", {})
            if isinstance(date_info, str):
                return {
                    "start_date": date_info,
                    "when": date_info
                }
            elif isinstance(date_info, dict):
                return {
                    "start_date": date_info.get("start_date", ""),
                    "when": date_info.get("when", "")
                }
            else:
                return {
                    "start_date": "",
                    "when": event.get("when", "")  # Fallback to top-level "when" field
                }
        except Exception as e:
            print(f"Error parsing date: {str(e)}")
            return {"start_date": "", "when": ""}
    
    def _get_ticket_info(self, event):
        """Extract ticket information if available"""
        try:
            ticket_info = event.get("ticket_info", {})
            if isinstance(ticket_info, dict):
                return {
                    "price": ticket_info.get("price", ""),
                    "status": ticket_info.get("status", ""),
                    "link": ticket_info.get("link", "")
                }
            return None
        except Exception as e:
            print(f"Error getting ticket info: {str(e)}")
            return None