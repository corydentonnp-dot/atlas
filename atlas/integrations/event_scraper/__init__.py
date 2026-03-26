"""Event/listings scraper interface.

TODO: Implement after scaffolding is approved.
Generic interface for scraping event listings, local activities, restaurants.

Capabilities:
- search_events(location, date_range, categories) -> list[Event]
- search_restaurants(location, cuisine, price_range) -> list[Restaurant]
- search_activities(location, type) -> list[Activity]
- get_details(listing_url) -> ListingDetails
"""
