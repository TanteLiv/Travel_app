"""
Mock provider for testing flight search functionality.
MIT License
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from zoneinfo import ZoneInfo

from .base import FlightProvider, Flight, FlightSegment


class MockProvider(FlightProvider):
    """Mock flight provider that returns sample data for testing."""
    
    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        self.data_file = Path(__file__).parent.parent / "data" / "mock_osl_per.json"
        self._load_mock_data()
    
    def _load_mock_data(self):
        """Load mock flight data from JSON file."""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.mock_data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Mock data file not found at {self.data_file}")
            self.mock_data = {"flights": []}
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in mock data file: {e}")
            self.mock_data = {"flights": []}
    
    def search_flights(self, params: Dict[str, Any]) -> List[Flight]:
        """
        Return mock flight data.
        
        Args:
            params: Search parameters (ignored in mock mode)
        
        Returns:
            List of mock Flight objects
        """
        flights = []
        oslo_tz = ZoneInfo("Europe/Oslo")
        
        for flight_data in self.mock_data.get("flights", []):
            # Parse segments
            segments = []
            for seg_data in flight_data.get("itinerary", []):
                # Parse datetime strings and ensure timezone
                dep_time = datetime.fromisoformat(seg_data["dep_time_local"])
                arr_time = datetime.fromisoformat(seg_data["arr_time_local"])
                
                # Add timezone if not present
                if dep_time.tzinfo is None:
                    dep_time = dep_time.replace(tzinfo=oslo_tz)
                if arr_time.tzinfo is None:
                    # For simplicity, assume all times are in Oslo timezone in mock data
                    # In real implementation, this would be based on airport timezone
                    arr_time = arr_time.replace(tzinfo=oslo_tz)
                
                segment = FlightSegment(
                    from_airport=seg_data["from_airport"],
                    to_airport=seg_data["to_airport"],
                    dep_time_local=dep_time,
                    arr_time_local=arr_time,
                    duration_minutes=seg_data["duration_minutes"],
                    flight_number=seg_data["flight_number"],
                    airline_code=seg_data["airline_code"]
                )
                segments.append(segment)
            
            # Create flight object
            flight = Flight(
                price_total=flight_data["price_total"],
                currency=flight_data["currency"],
                airline_codes=flight_data["airline_codes"],
                itinerary=segments,
                booking_link=flight_data.get("booking_link")
            )
            flights.append(flight)
        
        return flights
    
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        return "MockProvider"