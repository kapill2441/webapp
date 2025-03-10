/**
 * Main JavaScript file for EventFlowAI
 * Handles initialization and connects UI components with services
 */

// Import services
import locationService from './location-service.js';
import googleCalendarService from './google-calendar-service.js';

// App initialization
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize services
    try {
        await initializeApp();
    } catch (error) {
        console.error('Error initializing application:', error);
    }
    
    // Setup page-specific functionality
    setupPageHandlers();
});

/**
 * Initialize app services
 */
async function initializeApp() {
    // Initialize location service
    try {
        const location = await locationService.initialize();
        console.log('Location initialized:', location);
        
        // Update location display if element exists
        const locationDisplayElement = document.getElementById('currentLocationDisplay');
        if (locationDisplayElement) {
            locationDisplayElement.textContent = locationService.getDisplayLocation();
        }
        
        // Update location permission UI
        updateLocationPermissionUI();
    } catch (error) {
        console.error('Location service initialization failed:', error);
    }
    
    // Initialize Google Calendar service (lazy - will initialize when needed)
    const calendarButtons = document.querySelectorAll('.google-calendar-btn, #addToCalendarBtn');
    if (calendarButtons.length > 0) {
        try {
            await googleCalendarService.initialize();
            console.log('Google Calendar service initialized');
        } catch (error) {
            console.error('Google Calendar service initialization failed:', error);
            
            // Update UI to show error
            calendarButtons.forEach(button => {
                button.classList.add('bg-gray-300');
                button.classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
                button.disabled = true;
                button.title = 'Calendar integration unavailable';
            });
        }
    }
}

/**
 * Update UI elements related to location permissions
 */
function updateLocationPermissionUI() {
    const locationPermissionElements = document.querySelectorAll('.location-permission-status');
    
    locationPermissionElements.forEach(element => {
        if (locationService.permissionDenied) {
            element.innerHTML = `
                <div class="rounded-md bg-yellow-50 p-4 mb-4">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <h3 class="text-sm font-medium text-yellow-800">Location access denied</h3>
                            <div class="mt-2 text-sm text-yellow-700">
                                <p>You've denied location access. We're showing events based on your country/region instead. <button id="requestLocationPermission" class="text-indigo-600 hover:text-indigo-500 font-medium">Enable precise location</button></p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else if (locationService.hasPreciseLocation()) {
            element.innerHTML = `
                <div class="rounded-md bg-green-50 p-4 mb-4">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <h3 class="text-sm font-medium text-green-800">Using your location</h3>
                            <div class="mt-2 text-sm text-green-700">
                                <p>Showing events near ${locationService.getDisplayLocation()}</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            element.innerHTML = `
                <div class="rounded-md bg-blue-50 p-4 mb-4">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <h3 class="text-sm font-medium text-blue-800">Approximate location</h3>
                            <div class="mt-2 text-sm text-blue-700">
                                <p>We're showing events based on your general region. <button id="requestLocationPermission" class="text-indigo-600 hover:text-indigo-500 font-medium">Enable precise location</button></p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    });
    
    // Add event listener to location permission request buttons
    document.querySelectorAll('#requestLocationPermission').forEach(button => {
        button.addEventListener('click', async () => {
            try {
                await locationService.refreshLocation();
                updateLocationPermissionUI();
                
                // Refresh the page to apply new location
                window.location.reload();
            } catch (error) {
                console.error('Error refreshing location:', error);
            }
        });
    });
}

/**
 * Setup page-specific handlers based on current URL
 */
function setupPageHandlers() {
    const currentPath = window.location.pathname;
    
    // Event details page
    if (currentPath.includes('/event/')) {
        setupEventDetailsPage();
    }
    
    // Recommendations page
    if (currentPath.includes('/recommendations')) {
        setupRecommendationsPage();
    }
    
    // Browse events page
    if (currentPath.includes('/browse_local_events')) {
        setupBrowseEventsPage();
    }
    
    // Common elements on all pages
    setupCommonElements();
}

/**
 * Setup common UI elements present on all pages
 */
function setupCommonElements() {
    // Setup location display in navbar if exists
    const locationDisplay = document.getElementById('navbarLocationDisplay');
    if (locationDisplay) {
        if (locationService.hasPreciseLocation()) {
            locationDisplay.textContent = locationService.getDisplayLocation();
            locationDisplay.classList.remove('text-gray-400');
            locationDisplay.classList.add('text-gray-700');
        } else {
            locationDisplay.textContent = `${locationService.getDisplayLocation()} (approximate)`;
        }
    }
}

/**
 * Setup functionality specific to the event details page
 */
function setupEventDetailsPage() {
    // Initialize Google Calendar integration on event details page
    const addToCalendarBtn = document.getElementById('addToCalendarBtn');
    
    if (addToCalendarBtn) {
        addToCalendarBtn.addEventListener('click', async () => {
            // Get event details
            const eventTitle = document.querySelector('h1').textContent;
            const eventLocation = document.querySelector('.event-location')?.textContent || '';
            const eventDescription = document.querySelector('.event-description')?.textContent || '';
            const eventDateStr = document.querySelector('.event-date')?.getAttribute('data-datetime') || '';
            
            // Convert dates (handle case when only date is available)
            let startDateTime = new Date(eventDateStr);
            if (isNaN(startDateTime.getTime())) {
                // Try to parse from display format
                const dateDisplay = document.querySelector('.event-date')?.textContent;
                if (dateDisplay) {
                    // Attempt to parse from displayed format (might need adjustment based on your date format)
                    startDateTime = new Date(dateDisplay);
                } else {
                    // Default to now + 1 day if parsing fails
                    startDateTime = new Date();
                    startDateTime.setDate(startDateTime.getDate() + 1);
                }
            }
            
            // Add 1 hour for end time if not specified
            const endDateTime = new Date(startDateTime.getTime() + 60 * 60 * 1000);
            
            try {
                // Authenticate with Google
                if (!googleCalendarService.isUserAuthenticated()) {
                    await googleCalendarService.authenticate();
                }
                
                // Add event to calendar
                await googleCalendarService.addEventToCalendar({
                    title: eventTitle,
                    location: eventLocation,
                    description: eventDescription,
                    startDateTime: startDateTime.toISOString(),
                    endDateTime: endDateTime.toISOString()
                });
                
                // Show success message
                showNotification('Event added to your Google Calendar!', 'success');
            } catch (error) {
                console.error('Error adding event to calendar:', error);
                showNotification('Failed to add event to calendar. Please try again.', 'error');
            }
        });
    }
}

/**
 * Setup functionality specific to the recommendations page
 */
function setupRecommendationsPage() {
    // Track event interactions for learning
    document.querySelectorAll('.event-card').forEach(card => {
        // Track when users view event details (click on details button)
        const detailsButton = card.querySelector('.details-btn');
        if (detailsButton) {
            detailsButton.addEventListener('click', () => {
                trackEventInteraction('view_details', card.dataset.eventId);
            });
        }
        
        // Track when users join events
        const joinButton = card.querySelector('.join-btn');
        if (joinButton) {
            joinButton.addEventListener('click', () => {
                trackEventInteraction('join', card.dataset.eventId);
            });
        }
    });
}

/**
 * Setup functionality specific to the browse events page
 */
function setupBrowseEventsPage() {
    // Add location filter if available
    const filterContainer = document.querySelector('.filter-container');
    if (filterContainer && locationService.hasPreciseLocation()) {
        const locationFilter = document.createElement('div');
        locationFilter.innerHTML = `
            <label class="block text-sm font-medium text-gray-700 mb-1">Distance</label>
            <select id="distanceFilter" class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md">
                <option value="">Any distance</option>
                <option value="5">Within 5 miles</option>
                <option value="10">Within 10 miles</option>
                <option value="25">Within 25 miles</option>
                <option value="50">Within 50 miles</option>
            </select>
        `;
        filterContainer.appendChild(locationFilter);
    }
}

/**
 * Track event interactions for improving recommendations
 * @param {string} interactionType - Type of interaction (view, join, etc.)
 * @param {string} eventId - ID of the event
 */
function trackEventInteraction(interactionType, eventId) {
    try {
        // Send interaction data to backend
        fetch('/api/track_interaction', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_id: eventId,
                interaction_type: interactionType,
                timestamp: new Date().toISOString()
            })
        });
    } catch (error) {
        console.error('Error tracking interaction:', error);
    }
}

/**
 * Show notification to user
 * @param {string} message - Notification message
 * @param {string} type - Notification type (success, error, info)
 */
function showNotification(message, type = 'info') {
    // Check if notification container exists, create if not
    let notificationContainer = document.getElementById('notification-container');
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notification-container';
        notificationContainer.className = 'fixed bottom-4 right-4 z-50';
        document.body.appendChild(notificationContainer);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'notification mb-2 p-4 rounded-md shadow-md transform transition-all duration-300 translate-x-full';
    
    // Add type-specific classes and icon
    let icon = '';
    switch (type) {
        case 'success':
            notification.classList.add('bg-green-50', 'border-l-4', 'border-green-400', 'text-green-700');
            icon = '<svg class="h-5 w-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>';
            break;
        case 'error':
            notification.classList.add('bg-red-50', 'border-l-4', 'border-red-400', 'text-red-700');
            icon = '<svg class="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>';
            break;
        default:
            notification.classList.add('bg-blue-50', 'border-l-4', 'border-blue-400', 'text-blue-700');
            icon = '<svg class="h-5 w-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>';
    }
    
    // Set notification content
    notification.innerHTML = `
        <div class="flex">
            <div class="flex-shrink-0">
                ${icon}
            </div>
            <div class="ml-3">
                <p class="text-sm font-medium">${message}</p>
            </div>
            <div class="ml-auto pl-3">
                <div class="-mx-1.5 -my-1.5">
                    <button type="button" class="notification-close inline-flex rounded-md p-1.5 text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-50 focus:ring-gray-600">
                        <span class="sr-only">Dismiss</span>
                        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Add notification to container
    notificationContainer.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 10);
    
    // Add close button event listener
    notification.querySelector('.notification-close').addEventListener('click', () => {
        removeNotification(notification);
    });
    
    // Auto remove after delay
    setTimeout(() => {
        removeNotification(notification);
    }, 5000);
}

/**
 * Remove notification with animation
 * @param {HTMLElement} notification - Notification element to remove
 */
function removeNotification(notification) {
    notification.classList.add('translate-x-full');
    setTimeout(() => {
        notification.remove();
    }, 300);
}

// Export functions for use in inline scripts
window.appFunctions = {
    trackEventInteraction,
    showNotification,
    getLocationPermissionStatus: () => !locationService.permissionDenied
};