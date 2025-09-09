"""
Base provider interface and data models for flight search.
MIT License
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo


@dataclass
class FlightSegment:
    """Represents a single flight segment."""
    from_airport: str
    to_airport: str
    dep_time_local: datetime
    arr_time_local: datetime
    duration_minutes: int
    flight_number: str
    airline_code: str
    
    def __post_init__(self):
        """Ensure datetime objects have timezone info."""
        if self.dep_time_local.tzinfo is None:
            # Assume local time if no timezone provided
            self.dep_time_local = self.dep_time_local.replace(tzinfo=ZoneInfo("Europe/Oslo"))
        if self.arr_time_local.tzinfo is None:
            # For arrival, we might need to guess based on destination
            # For now, assume same timezone as departure
            self.arr_time_local = self.arr_time_local.replace(tzinfo=ZoneInfo("Europe/Oslo"))


@dataclass
class Flight:
    """Represents a complete flight itinerary."""
    price_total: float
    currency: str
    airline_codes: List[str]
    itinerary: List[FlightSegment]
    booking_link: Optional[str] = None
    
    def __post_init__(self):
        """Extract airline codes from segments if not provided."""
        if not self.airline_codes and self.itinerary:
            self.airline_codes = list(set(segment.airline_code for segment in self.itinerary))


class FlightProvider(ABC):
    """Abstract base class for flight search providers."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    @abstractmethod
    def search_flights(self, params: Dict[str, Any]) -> List[Flight]:
        """
        Search for flights based on parameters.
        
        Args:
            params: Dictionary containing search parameters:
                - from_airport: Origin airport code (e.g., "OSL")
                - to_airport: Destination airport code (e.g., "PER")
                - departure_date: Departure date
                - return_date: Return date (optional, for round-trip)
                - adults: Number of adult passengers
                - cabin: Cabin class ("economy", "business", "first")
        
        Returns:
            List of Flight objects matching the search criteria
        """
        pass
    
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        return self.__class__.__name__