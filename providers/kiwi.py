"""
Kiwi (Tequila) API provider for flight search.
MIT License
"""

import requests
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from .base import FlightProvider, Flight, FlightSegment


class KiwiProvider(FlightProvider):
    """Kiwi (Tequila) API flight provider."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.tequila.kiwi.com"
        self.headers = {
            "apikey": api_key,
            "Content-Type": "application/json"
        }
    
    def search_flights(self, params: Dict[str, Any]) -> List[Flight]:
        """
        Search for flights using Kiwi API.
        
        Args:
            params: Dictionary containing search parameters
        
        Returns:
            List of Flight objects
        """
        # Prepare API parameters
        api_params = {
            "fly_from": params.get("from_airport", "OSL"),
            "fly_to": params.get("to_airport", "PER"),
            "date_from": params["departure_date"].strftime("%d/%m/%Y"),
            "date_to": params["departure_date"].strftime("%d/%m/%Y"),
            "adults": params.get("adults", 1),
            "selected_cabins": self._map_cabin_class(params.get("cabin", "economy")),
            "flight_type": "oneway",
            "one_for_city": 1,
            "one_per_date": 0,
            "max_stopovers": 3,
            "curr": "NOK",
            "limit": 50
        }
        
        # Add return date if provided
        if params.get("return_date"):
            api_params["return_from"] = params["return_date"].strftime("%d/%m/%Y")
            api_params["return_to"] = params["return_date"].strftime("%d/%m/%Y")
            api_params["flight_type"] = "round"
        
        try:
            response = requests.get(
                f"{self.base_url}/v2/search",
                headers=self.headers,
                params=api_params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_flights(data)
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Kiwi API request failed: {e}")
        except Exception as e:
            raise Exception(f"Error parsing Kiwi API response: {e}")
    
    def _map_cabin_class(self, cabin: str) -> str:
        """Map cabin class to Kiwi API format."""
        mapping = {
            "economy": "M",
            "premium_economy": "W", 
            "business": "C",
            "first": "F"
        }
        return mapping.get(cabin.lower(), "M")
    
    def _parse_flights(self, data: Dict[str, Any]) -> List[Flight]:
        """Parse Kiwi API response into Flight objects."""
        flights = []
        oslo_tz = ZoneInfo("Europe/Oslo")
        
        for flight_data in data.get("data", []):
            try:
                # Parse route segments
                segments = []
                for route in flight_data.get("route", []):
                    # Parse timestamps
                    dep_time = datetime.fromtimestamp(
                        route["dTimeUTC"], 
                        tz=ZoneInfo("UTC")
                    ).astimezone(oslo_tz)
                    
                    arr_time = datetime.fromtimestamp(
                        route["aTimeUTC"], 
                        tz=ZoneInfo("UTC")
                    ).astimezone(oslo_tz)
                    
                    # Calculate duration
                    duration_minutes = int((arr_time - dep_time).total_seconds() / 60)
                    
                    segment = FlightSegment(
                        from_airport=route["flyFrom"],
                        to_airport=route["flyTo"],
                        dep_time_local=dep_time,
                        arr_time_local=arr_time,
                        duration_minutes=duration_minutes,
                        flight_number=route.get("flight_no", ""),
                        airline_code=route.get("airline", "")
                    )
                    segments.append(segment)
                
                # Extract airline codes
                airline_codes = list(set(
                    route.get("airline", "") for route in flight_data.get("route", [])
                    if route.get("airline")
                ))
                
                # Create flight object
                flight = Flight(
                    price_total=float(flight_data.get("price", 0)),
                    currency=flight_data.get("currency", "EUR"),
                    airline_codes=airline_codes,
                    itinerary=segments,
                    booking_link=flight_data.get("deep_link")
                )
                flights.append(flight)
                
            except (KeyError, ValueError, TypeError) as e:
                # Skip malformed flight data
                print(f"Warning: Skipping malformed flight data: {e}")
                continue
        
        return flights
    
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        return "KiwiProvider"