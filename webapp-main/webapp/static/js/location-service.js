/**
 * Location Service for EventFlowAI
 * Handles location detection, permissions, and provides fallbacks
 */

class LocationService {
    constructor() {
        this.currentLocation = null;
        this.fallbackLocation = null;
        this.permissionDenied = false;
        this.isLoading = false;
    }

    /**
     * Initialize the location service
     * @returns {Promise} Promise that resolves when location is determined
     */
    async initialize() {
        // Try to get cached location from localStorage
        const cachedLocation = localStorage.getItem('userLocation');
        if (cachedLocation) {
            try {
                this.currentLocation = JSON.parse(cachedLocation);
                console.log('Using cached location:', this.currentLocation);
                return this.currentLocation;
            } catch (e) {
                console.error('Error parsing cached location:', e);
                localStorage.removeItem('userLocation');
            }
        }
        
        // Get IP-based location as fallback
        await this.getFallbackLocation();
        
        // Attempt to get precise location
        return this.getCurrentPosition();
    }

    /**
     * Get current position using Geolocation API
     * @returns {Promise} Promise that resolves with location data
     */
    getCurrentPosition() {
        this.isLoading = true;
        
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                console.log('Geolocation is not supported by this browser');
                this.permissionDenied = true;
                this.isLoading = false;
                resolve(this.fallbackLocation);
                return;
            }
            
            navigator.permissions.query({ name: 'geolocation' }).then(permissionStatus => {
                if (permissionStatus.state === 'denied') {
                    console.log('Location permission denied');
                    this.permissionDenied = true;
                    this.isLoading = false;
                    resolve(this.fallbackLocation);
                    return;
                }
                
                navigator.geolocation.getCurrentPosition(
                    // Success callback
                    position => {
                        this.currentLocation = {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy,
                            timestamp: new Date().toISOString(),
                            source: 'geolocation'
                        };
                        
                        // Cache the location
                        localStorage.setItem('userLocation', JSON.stringify(this.currentLocation));
                        
                        this.isLoading = false;
                        resolve(this.currentLocation);
                    },
                    // Error callback
                    error => {
                        console.error('Error getting location:', error.message);
                        
                        if (error.code === error.PERMISSION_DENIED) {
                            this.permissionDenied = true;
                        }
                        
                        this.isLoading = false;
                        resolve(this.fallbackLocation);
                    },
                    // Options
                    {
                        enableHighAccuracy: true,
                        timeout: 5000,
                        maximumAge: 600000 // 10 minutes
                    }
                );
            });
        });
    }

    /**
     * Get fallback location using IP geolocation
     * @returns {Promise} Promise that resolves with approximate location
     */
    async getFallbackLocation() {
        try {
            // Using ipinfo.io for IP-based geolocation
            const response = await fetch('https://ipinfo.io/json?token=YOUR_IPINFO_TOKEN');
            const data = await response.json();
            
            if (data && data.loc) {
                const [latitude, longitude] = data.loc.split(',').map(parseFloat);
                this.fallbackLocation = {
                    latitude,
                    longitude,
                    country: data.country,
                    region: data.region,
                    city: data.city,
                    source: 'ip-geolocation'
                };
                
                console.log('Fallback location obtained:', this.fallbackLocation);
                return this.fallbackLocation;
            }
        } catch (error) {
            console.error('Error getting fallback location:', error);
            // Default fallback - could be based on user's country selection or app's default region
            this.fallbackLocation = {
                country: 'US',
                source: 'default'
            };
        }
        
        return this.fallbackLocation;
    }

    /**
     * Get location data for events API
     * @returns {Object} Location data suitable for API request
     */
    getLocationForAPI() {
        if (this.permissionDenied || !this.currentLocation) {
            // If permission denied or no precise location, use fallback
            if (this.fallbackLocation) {
                if (this.fallbackLocation.city && this.fallbackLocation.region) {
                    return {
                        location: `${this.fallbackLocation.city}, ${this.fallbackLocation.region}`,
                        coordinates: this.fallbackLocation.latitude && this.fallbackLocation.longitude ? 
                            [this.fallbackLocation.latitude, this.fallbackLocation.longitude] : null
                    };
                } else if (this.fallbackLocation.country) {
                    return { 
                        location: this.fallbackLocation.country,
                        coordinates: null
                    };
                }
            }
            return { location: null, coordinates: null };
        }
        
        // Return precise coordinates
        return {
            coordinates: [this.currentLocation.latitude, this.currentLocation.longitude],
            location: null // Let the API handle reverse geocoding
        };
    }

    /**
     * Trigger location refresh
     * @returns {Promise} Promise that resolves with updated location
     */
    refreshLocation() {
        localStorage.removeItem('userLocation');
        return this.getCurrentPosition();
    }

    /**
     * Check if we have precise location permission
     * @returns {Boolean} True if we have precise location
     */
    hasPreciseLocation() {
        return !!this.currentLocation && !this.permissionDenied;
    }

    /**
     * Format location for display to user
     * @returns {String} Human-readable location
     */
    getDisplayLocation() {
        if (this.currentLocation && this.currentLocation.formattedAddress) {
            return this.currentLocation.formattedAddress;
        }
        
        if (this.fallbackLocation) {
            if (this.fallbackLocation.city && this.fallbackLocation.region) {
                return `${this.fallbackLocation.city}, ${this.fallbackLocation.region}`;
            } else if (this.fallbackLocation.country) {
                return this.fallbackLocation.country;
            }
        }
        
        return 'Location unknown';
    }
}

// Create singleton instance
const locationService = new LocationService();

// Export for use in other modules
export default locationService;