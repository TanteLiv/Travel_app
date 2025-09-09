"""
Unit tests for flight filtering functionality.
MIT License
"""

import pytest
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from providers.base import Flight, FlightSegment
from travel_app import filter_flights, normalize_airline_codes, parse_time_window


# Test data setup
OSLO_TZ = ZoneInfo("Europe/Oslo")

def create_test_flight(
    price: float,
    currency: str,
    airline_codes: list,
    dep_time: datetime,
    arr_time: datetime,
    from_airport: str = "OSL",
    to_airport: str = "PER"
) -> Flight:
    """Helper function to create test flights."""
    segment = FlightSegment(
        from_airport=from_airport,
        to_airport=to_airport,
        dep_time_local=dep_time.replace(tzinfo=OSLO_TZ),
        arr_time_local=arr_time.replace(tzinfo=OSLO_TZ),
        duration_minutes=int((arr_time - dep_time).total_seconds() / 60),
        flight_number="TEST123",
        airline_code=airline_codes[0] if airline_codes else "XX"
    )
    
    return Flight(
        price_total=price,
        currency=currency,
        airline_codes=airline_codes,
        itinerary=[segment]
    )


@pytest.fixture
def sample_flights():
    """Create sample flights for testing."""
    flights = [
        # Qatar Airways - early morning, cheap
        create_test_flight(
            price=8950.0,
            currency="NOK",
            airline_codes=["QR"],
            dep_time=datetime(2025, 12, 10, 7, 30),
            arr_time=datetime(2025, 12, 11, 17, 30)
        ),
        # Emirates - morning, expensive
        create_test_flight(
            price=11200.0,
            currency="NOK",
            airline_codes=["EK"],
            dep_time=datetime(2025, 12, 10, 9, 15),
            arr_time=datetime(2025, 12, 11, 17, 15)
        ),
        # Singapore Airlines - very early, medium price
        create_test_flight(
            price=9750.0,
            currency="NOK",
            airline_codes=["SQ"],
            dep_time=datetime(2025, 12, 10, 6, 45),
            arr_time=datetime(2025, 12, 11, 13, 30)
        ),
        # British Airways - afternoon, expensive
        create_test_flight(
            price=10800.0,
            currency="NOK",
            airline_codes=["BA"],
            dep_time=datetime(2025, 12, 10, 14, 20),
            arr_time=datetime(2025, 12, 12, 3, 15)
        ),
        # SAS - evening, medium price
        create_test_flight(
            price=9100.0,
            currency="NOK",
            airline_codes=["SK"],
            dep_time=datetime(2025, 12, 10, 15, 45),
            arr_time=datetime(2025, 12, 11, 22, 45)
        ),
        # Different date flight
        create_test_flight(
            price=8500.0,
            currency="NOK",
            airline_codes=["QR"],
            dep_time=datetime(2025, 12, 11, 8, 0),
            arr_time=datetime(2025, 12, 12, 18, 0)
        )
    ]
    return flights


class TestAirlineFiltering:
    """Test airline filtering functionality."""
    
    def test_filter_by_single_airline(self, sample_flights):
        """Test filtering by a single airline."""
        filtered = filter_flights(sample_flights, airlines=["QR"])
        assert len(filtered) == 2
        assert all("QR" in flight.airline_codes for flight in filtered)
    
    def test_filter_by_multiple_airlines(self, sample_flights):
        """Test filtering by multiple airlines."""
        filtered = filter_flights(sample_flights, airlines=["QR", "EK"])
        assert len(filtered) == 3
        assert all(
            any(code in flight.airline_codes for code in ["QR", "EK"]) 
            for flight in filtered
        )
    
    def test_filter_by_nonexistent_airline(self, sample_flights):
        """Test filtering by airline that doesn't exist."""
        filtered = filter_flights(sample_flights, airlines=["XX"])
        assert len(filtered) == 0
    
    def test_no_airline_filter(self, sample_flights):
        """Test that no airline filter returns all flights."""
        filtered = filter_flights(sample_flights, airlines=None)
        assert len(filtered) == len(sample_flights)


class TestPriceFiltering:
    """Test price filtering functionality."""
    
    def test_filter_by_max_price(self, sample_flights):
        """Test filtering by maximum price."""
        filtered = filter_flights(sample_flights, max_price=9000.0)
        assert len(filtered) == 2  # QR flights at 8950 and 8500
        assert all(flight.price_total <= 9000.0 for flight in filtered)
    
    def test_filter_by_high_max_price(self, sample_flights):
        """Test filtering with high max price includes all flights."""
        filtered = filter_flights(sample_flights, max_price=15000.0)
        assert len(filtered) == len(sample_flights)
    
    def test_filter_by_low_max_price(self, sample_flights):
        """Test filtering with very low max price."""
        filtered = filter_flights(sample_flights, max_price=8000.0)
        assert len(filtered) == 0
    
    def test_no_price_filter(self, sample_flights):
        """Test that no price filter returns all flights."""
        filtered = filter_flights(sample_flights, max_price=None)
        assert len(filtered) == len(sample_flights)


class TestTimeWindowFiltering:
    """Test departure time window filtering."""
    
    def test_filter_by_morning_window(self, sample_flights):
        """Test filtering by morning departure window."""
        time_window = (time(6, 0), time(10, 0))
        filtered = filter_flights(sample_flights, dep_time_between=time_window)
        assert len(filtered) == 4  # QR 7:30, EK 9:15, SQ 6:45, QR 8:00 (Dec 11)
        
        for flight in filtered:
            dep_time = flight.itinerary[0].dep_time_local.time()
            assert time(6, 0) <= dep_time <= time(10, 0)
    
    def test_filter_by_afternoon_window(self, sample_flights):
        """Test filtering by afternoon departure window."""
        time_window = (time(14, 0), time(16, 0))
        filtered = filter_flights(sample_flights, dep_time_between=time_window)
        assert len(filtered) == 2  # BA 14:20, SK 15:45
    
    def test_filter_by_narrow_window(self, sample_flights):
        """Test filtering by very narrow time window."""
        time_window = (time(7, 0), time(8, 0))
        filtered = filter_flights(sample_flights, dep_time_between=time_window)
        assert len(filtered) == 2  # QR 7:30 (Dec 10) and QR 8:00 (Dec 11)
    
    def test_no_time_filter(self, sample_flights):
        """Test that no time filter returns all flights."""
        filtered = filter_flights(sample_flights, dep_time_between=None)
        assert len(filtered) == len(sample_flights)


class TestDateFiltering:
    """Test date filtering functionality."""
    
    def test_filter_by_single_date(self, sample_flights):
        """Test filtering by single departure date."""
        target_date = date(2025, 12, 10)
        dates = (target_date, None)
        filtered = filter_flights(sample_flights, dates=dates)
        assert len(filtered) == 5  # All flights except the Dec 11 one
        
        for flight in filtered:
            assert flight.itinerary[0].dep_time_local.date() == target_date
    
    def test_filter_by_date_range(self, sample_flights):
        """Test filtering by date range."""
        start_date = date(2025, 12, 10)
        end_date = date(2025, 12, 11)
        dates = (start_date, end_date)
        filtered = filter_flights(sample_flights, dates=dates)
        assert len(filtered) == len(sample_flights)  # All flights in range
    
    def test_filter_by_narrow_date_range(self, sample_flights):
        """Test filtering by narrow date range."""
        start_date = date(2025, 12, 11)
        end_date = date(2025, 12, 11)
        dates = (start_date, end_date)
        filtered = filter_flights(sample_flights, dates=dates)
        assert len(filtered) == 1  # Only the Dec 11 flight
    
    def test_no_date_filter(self, sample_flights):
        """Test that no date filter returns all flights."""
        filtered = filter_flights(sample_flights, dates=None)
        assert len(filtered) == len(sample_flights)


class TestCombinedFiltering:
    """Test combined filtering scenarios."""
    
    def test_combined_airline_and_price(self, sample_flights):
        """Test filtering by both airline and price."""
        filtered = filter_flights(
            sample_flights, 
            airlines=["QR", "SQ"], 
            max_price=9000.0
        )
        assert len(filtered) == 2  # Both QR flights under 9000
        assert filtered[0].airline_codes == ["QR"]
        assert filtered[0].price_total <= 9000.0
    
    def test_combined_time_and_airline(self, sample_flights):
        """Test filtering by time window and airline."""
        time_window = (time(6, 0), time(10, 0))
        filtered = filter_flights(
            sample_flights,
            airlines=["QR", "EK"],
            dep_time_between=time_window
        )
        assert len(filtered) == 3  # QR 7:30, EK 9:15, and QR 8:00 (Dec 11)
    
    def test_all_filters_combined(self, sample_flights):
        """Test all filters combined."""
        time_window = (time(6, 0), time(10, 0))
        dates = (date(2025, 12, 10), None)
        filtered = filter_flights(
            sample_flights,
            airlines=["QR"],
            max_price=9000.0,
            dep_time_between=time_window,
            dates=dates
        )
        assert len(filtered) == 1  # Only QR 7:30 on Dec 10
    
    def test_restrictive_filters_no_results(self, sample_flights):
        """Test that overly restrictive filters return no results."""
        time_window = (time(23, 0), time(23, 59))
        filtered = filter_flights(
            sample_flights,
            airlines=["QR"],
            max_price=5000.0,
            dep_time_between=time_window
        )
        assert len(filtered) == 0


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_normalize_airline_codes_single(self):
        """Test normalizing single airline code."""
        result = normalize_airline_codes("QR")
        assert result == ["QR"]
    
    def test_normalize_airline_codes_multiple(self):
        """Test normalizing multiple airline codes."""
        result = normalize_airline_codes("QR,EK,BA")
        assert result == ["QR", "EK", "BA"]
    
    def test_normalize_airline_codes_with_spaces(self):
        """Test normalizing airline codes with spaces."""
        result = normalize_airline_codes("QR, EK , BA")
        assert result == ["QR", "EK", "BA"]
    
    def test_normalize_airline_codes_none(self):
        """Test normalizing None input."""
        result = normalize_airline_codes(None)
        assert result is None
    
    def test_parse_time_window_valid(self):
        """Test parsing valid time window."""
        result = parse_time_window("06:00-12:00")
        assert result == (time(6, 0), time(12, 0))
    
    def test_parse_time_window_none(self):
        """Test parsing None time window."""
        result = parse_time_window(None)
        assert result is None
    
    def test_parse_time_window_invalid_format(self):
        """Test parsing invalid time window format."""
        with pytest.raises(Exception):  # typer.Exit or click.Exit
            parse_time_window("invalid")


if __name__ == "__main__":
    pytest.main([__file__])