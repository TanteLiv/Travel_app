#!/usr/bin/env python3
"""
Travel App - Flight Search Tool
MIT License - Search flights from OSL to PER with filtering capabilities
"""

import os
import sys
from datetime import datetime, date, time
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json

import typer
from tabulate import tabulate
from dotenv import load_dotenv
import requests
from zoneinfo import ZoneInfo

# Load environment variables
load_dotenv()

# Import providers
from providers.base import FlightProvider, Flight, FlightSegment
from providers.mock import MockProvider
from providers.kiwi import KiwiProvider
from providers.amadeus import AmadeusProvider
from providers.skyscanner import SkyscannerProvider

app = typer.Typer(help="Flight search tool for OSL to PER routes")

# Configuration
OSLO_TZ = ZoneInfo("Europe/Oslo")
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "NOK")
PROVIDER_NAME = os.getenv("PROVIDER", "MOCK").upper()

# Airline code mappings
AIRLINE_CODES = {
    "QR": "Qatar Airways",
    "QF": "Qantas", 
    "BA": "British Airways",
    "EK": "Emirates",
    "SK": "SAS",
    "SQ": "Singapore Airlines",
    "AY": "Finnair",
    "SAS": "SAS"  # Alternative code
}

AIRLINE_NAMES_TO_CODES = {v.lower(): k for k, v in AIRLINE_CODES.items()}


def get_provider() -> FlightProvider:
    """Get the configured flight provider."""
    if PROVIDER_NAME == "KIWI" and os.getenv("KIWI_API_KEY"):
        return KiwiProvider(os.getenv("KIWI_API_KEY"))
    elif PROVIDER_NAME == "AMADEUS" and os.getenv("AMADEUS_API_KEY"):
        return AmadeusProvider(os.getenv("AMADEUS_API_KEY"))
    elif PROVIDER_NAME == "SKYSCANNER" and os.getenv("SKYSCANNER_API_KEY"):
        return SkyscannerProvider(os.getenv("SKYSCANNER_API_KEY"))
    else:
        if PROVIDER_NAME != "MOCK":
            typer.echo(f"WARNING: No API key found for {PROVIDER_NAME}, falling back to MOCK provider", err=True)
        return MockProvider()


def normalize_airline_codes(airlines: Optional[str]) -> Optional[List[str]]:
    """Convert airline names/codes to standardized IATA codes."""
    if not airlines:
        return None
    
    codes = []
    for airline in airlines.split(","):
        airline = airline.strip().upper()
        if airline in AIRLINE_CODES:
            codes.append(airline)
        else:
            # Try to find by name
            for name, code in AIRLINE_NAMES_TO_CODES.items():
                if airline.lower() in name:
                    codes.append(code)
                    break
            else:
                codes.append(airline)  # Keep as-is if not found
    
    return codes


def parse_time_window(time_window: Optional[str]) -> Optional[Tuple[time, time]]:
    """Parse time window string like '06:00-12:00' into time objects."""
    if not time_window:
        return None
    
    try:
        start_str, end_str = time_window.split("-")
        start_hour, start_min = map(int, start_str.split(":"))
        end_hour, end_min = map(int, end_str.split(":"))
        return (time(start_hour, start_min), time(end_hour, end_min))
    except ValueError:
        typer.echo(f"ERROR: Invalid time window format: {time_window}. Use HH:MM-HH:MM", err=True)
        raise typer.Exit(1)


def parse_date_range(date_input: str) -> Tuple[date, Optional[date]]:
    """Parse date or date range string."""
    if ":" in date_input:
        start_str, end_str = date_input.split(":")
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        return start_date, end_date
    else:
        single_date = datetime.strptime(date_input, "%Y-%m-%d").date()
        return single_date, None


def filter_flights(
    flights: List[Flight],
    airlines: Optional[List[str]] = None,
    max_price: Optional[float] = None,
    dep_time_between: Optional[Tuple[time, time]] = None,
    dates: Optional[Tuple[date, Optional[date]]] = None
) -> List[Flight]:
    """Filter flights based on criteria."""
    filtered = flights
    
    # Filter by airlines
    if airlines:
        airline_set = set(code.upper() for code in airlines)
        filtered = [f for f in filtered if any(code in airline_set for code in f.airline_codes)]
    
    # Filter by max price
    if max_price is not None:
        filtered = [f for f in filtered if f.price_total <= max_price]
    
    # Filter by departure time window
    if dep_time_between:
        start_time, end_time = dep_time_between
        filtered = [
            f for f in filtered 
            if f.itinerary and start_time <= f.itinerary[0].dep_time_local.time() <= end_time
        ]
    
    # Filter by dates
    if dates:
        start_date, end_date = dates
        if end_date:
            # Date range
            filtered = [
                f for f in filtered 
                if f.itinerary and start_date <= f.itinerary[0].dep_time_local.date() <= end_date
            ]
        else:
            # Single date
            filtered = [
                f for f in filtered 
                if f.itinerary and f.itinerary[0].dep_time_local.date() == start_date
            ]
    
    return filtered


def format_duration(minutes: int) -> str:
    """Format duration in minutes to human readable format."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def format_stops(segments: List[FlightSegment]) -> str:
    """Format number of stops."""
    stops = len(segments) - 1
    if stops == 0:
        return "non-stop"
    elif stops == 1:
        return "1 stop"
    else:
        return f"{stops} stops"


def display_flights(flights: List[Flight], sort_by: str = "price"):
    """Display flights in a formatted table."""
    if not flights:
        typer.echo("No flights found matching your criteria.")
        return
    
    # Sort flights
    if sort_by == "price":
        flights.sort(key=lambda f: f.price_total)
    elif sort_by == "duration":
        flights.sort(key=lambda f: sum(s.duration_minutes for s in f.itinerary))
    elif sort_by == "departure":
        flights.sort(key=lambda f: f.itinerary[0].dep_time_local if f.itinerary else datetime.min)
    
    # Prepare table data
    headers = ["Price", "Airlines", "Departure -> Arrival", "Duration", "Stops", "Booking"]
    rows = []
    
    for flight in flights:
        if not flight.itinerary:
            continue
            
        first_segment = flight.itinerary[0]
        last_segment = flight.itinerary[-1]
        
        price = f"{flight.price_total:.0f} {flight.currency}"
        airlines = ", ".join(flight.airline_codes)
        
        dep_time = first_segment.dep_time_local.strftime("%H:%M")
        arr_time = last_segment.arr_time_local.strftime("%H:%M")
        route = f"{first_segment.from_airport} {dep_time} -> {last_segment.to_airport} {arr_time}"
        
        total_duration = sum(s.duration_minutes for s in flight.itinerary)
        duration = format_duration(total_duration)
        
        stops = format_stops(flight.itinerary)
        
        booking = flight.booking_link[:50] + "..." if flight.booking_link and len(flight.booking_link) > 50 else flight.booking_link or "N/A"
        
        rows.append([price, airlines, route, duration, stops, booking])
    
    typer.echo(tabulate(rows, headers=headers, tablefmt="grid"))


@app.command()
def search(
    from_airport: str = typer.Option("OSL", "--from", help="Origin airport code"),
    to_airport: str = typer.Option("PER", "--to", help="Destination airport code"),
    date: Optional[str] = typer.Option(None, "--date", help="Departure date (YYYY-MM-DD)"),
    date_range: Optional[str] = typer.Option(None, "--date-range", help="Date range (YYYY-MM-DD:YYYY-MM-DD)"),
    adults: int = typer.Option(1, "--adults", help="Number of adult passengers"),
    cabin: str = typer.Option("economy", "--cabin", help="Cabin class"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum price filter"),
    airlines: Optional[str] = typer.Option(None, "--airlines", help="Comma-separated airline codes (e.g., QR,QF,BA)"),
    dep_window: Optional[str] = typer.Option(None, "--dep-window", help="Departure time window (HH:MM-HH:MM)"),
    sort: str = typer.Option("price", "--sort", help="Sort by: price, duration, departure")
):
    """Search for flights between airports."""
    
    # Validate inputs
    if not date and not date_range:
        typer.echo("ERROR: Please specify either --date or --date-range", err=True)
        raise typer.Exit(1)
    
    if date and date_range:
        typer.echo("ERROR: Please specify either --date or --date-range, not both", err=True)
        raise typer.Exit(1)
    
    # Parse date(s)
    try:
        if date:
            dates = parse_date_range(date)
        else:
            dates = parse_date_range(date_range)
    except ValueError as e:
        typer.echo(f"ERROR: Invalid date format: {e}", err=True)
        raise typer.Exit(1)
    
    # Parse filters
    airline_codes = normalize_airline_codes(airlines)
    time_window = parse_time_window(dep_window)
    
    # Get provider and search
    provider = get_provider()
    typer.echo(f"Searching flights using {provider.__class__.__name__}...")
    
    try:
        search_params = {
            "from_airport": from_airport,
            "to_airport": to_airport,
            "departure_date": dates[0],
            "return_date": dates[1] if dates[1] else None,
            "adults": adults,
            "cabin": cabin
        }
        
        flights = provider.search_flights(search_params)
        
        # Apply filters
        filtered_flights = filter_flights(
            flights,
            airlines=airline_codes,
            max_price=max_price,
            dep_time_between=time_window,
            dates=dates
        )
        
        typer.echo(f"Found {len(filtered_flights)} flights (from {len(flights)} total)")
        display_flights(filtered_flights, sort_by=sort)
        
    except Exception as e:
        typer.echo(f"ERROR: Error searching flights: {e}", err=True)
        raise typer.Exit(1)


@app.callback()
def main():
    """
    Flight Search Tool - Find flights from OSL to PER with advanced filtering.
    
    Examples:
      python travel_app.py search --date 2025-12-10
      python travel_app.py search --date-range 2025-12-10:2025-12-20 --airlines QR,EK --max-price 1200
      python travel_app.py search --date 2025-12-10 --dep-window 06:00-12:00 --sort duration
    """
    pass


if __name__ == "__main__":
    app()