-- SQL Script to insert dummy events with locations in USA and Singapore
-- Run this with the sqlite3 CLI tool:
-- sqlite3 instance/smart_event_organizer.db < dummy_events.sql

-- USA Event Locations
INSERT INTO event (title, description, location, date, privacy, organizer_id, event_popularity)
VALUES 
-- Tech Events
('TechCon 2025', 'Annual technology conference featuring the latest innovations in AI and machine learning.', 'San Francisco, CA, USA', '2025-04-15 09:00:00', 'public', 1, 0.9),
('Startup Pitch Night', 'Emerging startups present their business ideas to potential investors.', 'New York, NY, USA', '2025-03-28 18:30:00', 'public', 1, 0.7),
('Developer Workshop: Modern Web Dev', 'Hands-on workshop covering the latest web development frameworks and tools.', 'Seattle, WA, USA', '2025-03-10 13:00:00', 'public', 2, 0.6),
('Cybersecurity Summit', 'Industry experts discuss the latest threats and security strategies.', 'Austin, TX, USA', '2025-05-05 10:00:00', 'public', 3, 0.8),

-- Music Events
('Jazz in the Park', 'Open-air jazz concert featuring local and national artists.', 'Chicago, IL, USA', '2025-06-12 19:00:00', 'public', 2, 0.8),
('Electronic Music Festival', 'Three-day festival with top electronic music artists and immersive experiences.', 'Miami, FL, USA', '2025-04-22 16:00:00', 'public', 3, 0.9),
('Symphony Orchestra: Classical Nights', 'Performance of Beethoven and Mozart classics by the city symphony.', 'Boston, MA, USA', '2025-03-18 19:30:00', 'public', 1, 0.7),
('Rock Concert: Legends Reunion', 'Legendary rock bands reunite for one night only.', 'Los Angeles, CA, USA', '2025-05-20 20:00:00', 'public', 2, 0.8),

-- Food Events
('Food Truck Festival', 'Celebration of street food with dozens of food trucks, live music, and activities.', 'Portland, OR, USA', '2025-04-11 11:00:00', 'public', 3, 0.7),
('Wine Tasting: California Vintages', 'Sample award-winning wines from California vineyards.', 'Napa Valley, CA, USA', '2025-04-05 15:00:00', 'public', 1, 0.6),
('Cooking Masterclass', 'Learn to cook gourmet meals with a renowned chef.', 'Denver, CO, USA', '2025-03-22 17:00:00', 'public', 2, 0.5),
('Farmers Market Anniversary', 'Special edition of the weekly farmers market with activities and demonstrations.', 'Atlanta, GA, USA', '2025-04-19 08:00:00', 'public', 3, 0.6),

-- Sports Events
('Marathon for Charity', 'Annual marathon supporting local charities and community programs.', 'Philadelphia, PA, USA', '2025-05-16 07:00:00', 'public', 1, 0.7),
('Basketball Tournament', 'Regional basketball championship with teams from across the state.', 'Houston, TX, USA', '2025-03-29 13:00:00', 'public', 2, 0.7),
('Yoga in the Park', 'Free community yoga sessions for all skill levels.', 'Washington, DC, USA', '2025-04-26 08:00:00', 'public', 3, 0.5),

-- Singapore Event Locations
('Singapore Tech Summit', 'Leading technology conference in Asia featuring keynotes, workshops, and networking.', 'Marina Bay Sands, Singapore', '2025-04-08 09:00:00', 'public', 1, 0.9),
('Cultural Food Festival', 'Celebration of Singapores diverse culinary traditions with food stalls and cooking demonstrations.', 'Gardens by the Bay, Singapore', '2025-05-01 11:00:00', 'public', 2, 0.8),
('Singapore Jazz Festival', 'Annual jazz festival featuring international and local artists.', 'Esplanade, Singapore', '2025-03-15 18:30:00', 'public', 3, 0.7),
('FinTech Conference', 'Exploring the future of financial technology and digital banking.', 'Suntec Convention Centre, Singapore', '2025-04-29 10:00:00', 'public', 1, 0.8),
('Singapore Night Race', 'Experience the thrill of night racing in the heart of the city.', 'Marina Bay Street Circuit, Singapore', '2025-06-18 19:00:00', 'public', 2, 0.9),
('Art Exhibition: Modern Asia', 'Contemporary art exhibition featuring artists from across Asia.', 'National Gallery, Singapore', '2025-04-12 10:00:00', 'public', 3, 0.6),
('Business Networking Mixer', 'Connect with professionals from various industries in a casual setting.', 'Raffles Hotel, Singapore', '2025-03-25 18:00:00', 'private', 1, 0.5),
('Singapore International Film Festival', 'Screening of award-winning films from around the world.', 'Shaw Theatres Lido, Singapore', '2025-05-10 14:00:00', 'public', 2, 0.7),
('Wellness Retreat Day', 'Day-long retreat focusing on mindfulness, yoga, and healthy living.', 'Sentosa Island, Singapore', '2025-04-06 09:00:00', 'public', 3, 0.6),
('Singapore Night Festival', 'Annual night festival with light installations, performances, and activities.', 'Bras Basah.Bugis, Singapore', '2025-05-24 19:00:00', 'public', 1, 0.8);