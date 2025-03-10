/**
 * Google Calendar Service for EventFlowAI
 * Handles OAuth authentication and calendar operations
 */

class GoogleCalendarService {
    constructor() {
        // Google API client configuration
        this.apiKey = ''; // Set your API key if using restricted API key
        this.clientId = ''; // Your Google Client ID from Google Developer Console
        this.discoveryDocs = ['https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest'];
        this.scopes = 'https://www.googleapis.com/auth/calendar.events';
        
        // Authentication state
        this.isAuthenticated = false;
        this.isInitialized = false;
        this.tokenClient = null;
        this.accessToken = null;
    }

    /**
     * Initialize the Google API client
     * @returns {Promise} Promise that resolves when Google API client is loaded
     */
    async initialize() {
        if (this.isInitialized) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            // Load the Google API client library
            const script = document.createElement('script');
            script.src = 'https://apis.google.com/js/api.js';
            script.onload = () => {
                // Initialize the gapi client
                gapi.load('client', async () => {
                    try {
                        await gapi.client.init({
                            apiKey: this.apiKey,
                            discoveryDocs: this.discoveryDocs,
                        });
                        
                        // Load auth2 library
                        const authScript = document.createElement('script');
                        authScript.src = 'https://accounts.google.com/gsi/client';
                        authScript.onload = () => {
                            this.tokenClient = google.accounts.oauth2.initTokenClient({
                                client_id: this.clientId,
                                scope: this.scopes,
                                callback: (tokenResponse) => {
                                    if (tokenResponse && tokenResponse.access_token) {
                                        this.accessToken = tokenResponse.access_token;
                                        this.isAuthenticated = true;
                                        resolve();
                                    } else {
                                        reject(new Error('Failed to get access token'));
                                    }
                                },
                            });
                            
                            this.isInitialized = true;
                            resolve();
                        };
                        authScript.onerror = () => {
                            reject(new Error('Failed to load Google Identity Services'));
                        };
                        document.body.appendChild(authScript);
                    } catch (error) {
                        reject(error);
                    }
                });
            };
            script.onerror = () => {
                reject(new Error('Failed to load Google API client'));
            };
            document.body.appendChild(script);
        });
    }

    /**
     * Authenticate with Google
     * @param {boolean} immediate - Whether to use immediate mode (no popup)
     * @returns {Promise} Promise that resolves when authenticated
     */
    authenticate(immediate = false) {
        if (!this.isInitialized) {
            return this.initialize().then(() => this.authenticate(immediate));
        }

        if (this.isAuthenticated) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            try {
                if (immediate) {
                    // Try silent authentication
                    this.tokenClient.requestAccessToken({ prompt: 'none' });
                } else {
                    // Show authentication popup
                    this.tokenClient.requestAccessToken({ prompt: 'consent' });
                }
                
                // The callback in initTokenClient will handle resolving the promise
                // This is a bit of a hack, but it works because the callback is set in initialize()
                const originalCallback = this.tokenClient.callback;
                this.tokenClient.callback = (tokenResponse) => {
                    originalCallback(tokenResponse);
                    if (tokenResponse && tokenResponse.access_token) {
                        resolve();
                    } else {
                        reject(new Error('Authentication failed'));
                    }
                };
            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Sign out from Google
     */
    signOut() {
        if (gapi.client.getToken()) {
            google.accounts.oauth2.revoke(gapi.client.getToken().access_token, () => {
                gapi.client.setToken('');
                this.isAuthenticated = false;
                this.accessToken = null;
            });
        }
    }

    /**
     * Add an event to the user's Google Calendar
     * @param {Object} event - The event details
     * @returns {Promise} Promise that resolves with the created event
     */
    async addEventToCalendar(event) {
        if (!this.isAuthenticated) {
            await this.authenticate();
        }

        const calendarEvent = {
            'summary': event.title,
            'location': event.location,
            'description': event.description,
            'start': {
                'dateTime': event.startDateTime,
                'timeZone': Intl.DateTimeFormat().resolvedOptions().timeZone
            },
            'end': {
                'dateTime': event.endDateTime || this.addHoursToDate(new Date(event.startDateTime), 1).toISOString(),
                'timeZone': Intl.DateTimeFormat().resolvedOptions().timeZone
            },
            'reminders': {
                'useDefault': true
            }
        };

        try {
            const response = await gapi.client.calendar.events.insert({
                'calendarId': 'primary',
                'resource': calendarEvent
            });
            
            return response.result;
        } catch (error) {
            console.error('Error adding event to calendar:', error);
            throw error;
        }
    }

    /**
     * Get events from the user's Google Calendar
     * @param {Date} startDate - Start date for event range
     * @param {Date} endDate - End date for event range
     * @returns {Promise} Promise that resolves with the list of events
     */
    async getCalendarEvents(startDate = new Date(), endDate = new Date(new Date().setMonth(startDate.getMonth() + 1))) {
        if (!this.isAuthenticated) {
            await this.authenticate();
        }

        try {
            const response = await gapi.client.calendar.events.list({
                'calendarId': 'primary',
                'timeMin': startDate.toISOString(),
                'timeMax': endDate.toISOString(),
                'showDeleted': false,
                'singleEvents': true,
                'maxResults': 100,
                'orderBy': 'startTime'
            });
            
            return response.result.items;
        } catch (error) {
            console.error('Error getting calendar events:', error);
            throw error;
        }
    }

    /**
     * Utility function to add hours to a date
     * @param {Date} date - The base date
     * @param {number} hours - Number of hours to add
     * @returns {Date} New date with hours added
     */
    addHoursToDate(date, hours) {
        return new Date(date.getTime() + hours * 60 * 60 * 1000);
    }

    /**
     * Check if the user is authenticated
     * @returns {boolean} True if authenticated
     */
    isUserAuthenticated() {
        return this.isAuthenticated;
    }
}

// Create singleton instance
const googleCalendarService = new GoogleCalendarService();

// Export for use in other modules
export default googleCalendarService;