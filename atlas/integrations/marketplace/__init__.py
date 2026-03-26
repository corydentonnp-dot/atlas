"""Marketplace/deal source adapter interface.

TODO: Implement after scaffolding is approved.
Generic interface for marketplace listings (FB Marketplace, Craigslist, etc.)

Capabilities:
- search_listings(query, location, radius, price_range) -> list[Listing]
- get_listing_details(url) -> ListingDetails
- watch_query(query, callback) -> WatchID
- stop_watch(watch_id) -> None
- estimate_resale_value(item) -> ResaleEstimate
"""
