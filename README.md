# Travel App - Flight Search Tool

A comprehensive Python application for searching flights from Oslo Airport Gardermoen (OSL) to Perth, Australia (PER) with advanced filtering capabilities.

## Features

- **Multiple Provider Support**: Kiwi (Tequila), Amadeus, Skyscanner APIs with mock mode for testing
- **Advanced Filtering**: Filter by airline, price, departure time window, and dates
- **Dual Interface**: Command-line interface (CLI) and web UI
- **Timezone Aware**: All times displayed in Europe/Oslo timezone
- **Comprehensive Testing**: Unit tests for all filtering logic

## Quick Start

### Installation

1. Clone or download the project files
2. Install dependencies:
```bash
pip install typer[all] python-dotenv requests tabulate pydantic streamlit pytest
```

3. Copy environment configuration:
```bash
cp .env.example .env
```

4. Run in mock mode (no API keys required):
```bash
python travel_app.py search --date 2025-12-10
```

### Web UI

Launch the Streamlit web interface:
```bash
streamlit run app_streamlit.py
```

## Usage Examples

### Command Line Interface

#### Basic Search
```bash
# Search for flights on a specific date
python travel_app.py search --date 2025-12-10

# Search with date range
python travel_app.py search --date-range 2025-12-10:2025-12-20
```

#### Advanced Filtering
```bash
# Filter by airlines and price
python travel_app.py search --date 2025-12-10 --airlines QR,EK --max-price 1200

# Filter by departure time window
python travel_app.py search --date 2025-12-10 --dep-window 06:00-12:00

# Combine all filters
python travel_app.py search --date 2025-12-10 --airlines QR,QF,BA --max-price 1200 --dep-window 06:00-12:00 --sort duration
```

#### Sorting Options
```bash
# Sort by price (default)
python travel_app.py search --date 2025-12-10 --sort price

# Sort by duration
python travel_app.py search --date 2025-12-10 --sort duration

# Sort by departure time
python travel_app.py search --date 2025-12-10 --sort departure
```

### Supported Airlines

The app supports filtering by these airlines:
- **QR** - Qatar Airways
- **QF** - Qantas
- **BA** - British Airways
- **EK** - Emirates
- **SK/SAS** - SAS
- **SQ** - Singapore Airlines
- **AY** - Finnair

## Configuration

### Environment Variables

Edit `.env` file to configure the application:

```env
# Provider Selection
PROVIDER=MOCK  # Options: MOCK, KIWI, AMADEUS, SKYSCANNER

# Default Currency
DEFAULT_CURRENCY=NOK

# API Keys (uncomment and add your keys)
# KIWI_API_KEY=your_kiwi_api_key_here
# AMADEUS_API_KEY=your_amadeus_api_key_here
# SKYSCANNER_API_KEY=your_rapidapi_key_here
```

### Provider Setup

#### Mock Provider (Default)
No setup required. Uses sample data from `data/mock_osl_per.json`.

#### Kiwi (Tequila) Provider
1. Sign up at [Tequila Kiwi](https://tequila.kiwi.com/portal/login)
2. Get your API key
3. Set in `.env`:
```env
PROVIDER=KIWI
KIWI_API_KEY=your_api_key_here
```

#### Amadeus Provider
1. Sign up at [Amadeus for Developers](https://developers.amadeus.com/)
2. Get your API key and secret
3. Set in `.env`:
```env
PROVIDER=AMADEUS
AMADEUS_API_KEY=your_api_key_here
AMADEUS_API_SECRET=your_api_secret_here
```

#### Skyscanner Provider
1. Sign up at [RapidAPI](https://rapidapi.com/skyscanner/api/skyscanner-flight-search/)
2. Subscribe to Skyscanner API
3. Set in `.env`:
```env
PROVIDER=SKYSCANNER
SKYSCANNER_API_KEY=your_rapidapi_key_here
```

## Project Structure

```
travel_app/
├── travel_app.py           # Main CLI application
├── app_streamlit.py        # Streamlit web UI
├── providers/              # Flight search providers
│   ├── __init__.py
│   ├── base.py            # Base provider interface
│   ├── mock.py            # Mock provider for testing
│   ├── kiwi.py            # Kiwi (Tequila) API provider
│   ├── amadeus.py         # Amadeus API provider (stub)
│   └── skyscanner.py      # Skyscanner API provider (stub)
├── data/
│   └── mock_osl_per.json  # Sample flight data
├── tests/
│   ├── __init__.py
│   └── test_filters.py    # Unit tests for filtering
├── .env.example           # Environment configuration template
└── README.md              # This file
```

## API Reference

### Flight Data Model

```python
@dataclass
class FlightSegment:
    from_airport: str
    to_airport: str
    dep_time_local: datetime
    arr_time_local: datetime
    duration_minutes: int
    flight_number: str
    airline_code: str

@dataclass
class Flight:
    price_total: float
    currency: str
    airline_codes: List[str]
    itinerary: List[FlightSegment]
    booking_link: Optional[str] = None
```

### Provider Interface

```python
class FlightProvider(ABC):
    @abstractmethod
    def search_flights(self, params: Dict[str, Any]) -> List[Flight]:
        """Search for flights based on parameters."""
        pass
```

### Filtering Functions

```python
def filter_flights(
    flights: List[Flight],
    airlines: Optional[List[str]] = None,
    max_price: Optional[float] = None,
    dep_time_between: Optional[Tuple[time, time]] = None,
    dates: Optional[Tuple[date, Optional[date]]] = None
) -> List[Flight]:
    """Filter flights based on criteria."""
```

## Testing

Run the unit tests:
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_filters.py

# Run with coverage
pytest --cov=travel_app
```

### Test Coverage

The test suite covers:
- Airline filtering (single and multiple airlines)
- Price filtering (various price ranges)
- Time window filtering (morning, afternoon, narrow windows)
- Date filtering (single date and date ranges)
- Combined filtering scenarios
- Utility function validation

## Development

### Adding New Providers

1. Create a new provider class inheriting from `FlightProvider`
2. Implement the `search_flights` method
3. Add provider selection logic in `travel_app.py`
4. Update environment configuration

Example:
```python
class NewProvider(FlightProvider):
    def search_flights(self, params: Dict[str, Any]) -> List[Flight]:
        # Implement API integration
        # Parse response into Flight objects
        # Return list of flights
        pass
```

### Mock Data Format

The mock data in `data/mock_osl_per.json` follows this structure:
```json
{
  "flights": [
    {
      "price_total": 8950.0,
      "currency": "NOK",
      "airline_codes": ["QR"],
      "booking_link": "https://booking.example.com/qr123",
      "itinerary": [
        {
          "from_airport": "OSL",
          "to_airport": "DOH",
          "dep_time_local": "2025-12-10T07:30:00",
          "arr_time_local": "2025-12-10T15:45:00",
          "duration_minutes": 375,
          "flight_number": "QR183",
          "airline_code": "QR"
        }
      ]
    }
  ]
}
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **API Key Issues**: Check `.env` file configuration and API key validity
3. **No Results**: Try adjusting filters or using mock mode
4. **Timezone Issues**: All times are displayed in Europe/Oslo timezone

### Debug Mode

Enable debug output by setting environment variable:
```bash
export DEBUG=1
python travel_app.py search --date 2025-12-10
```

## License

MIT License - see individual files for license headers.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues and questions:
1. Check this README for configuration help
2. Run tests to verify functionality
3. Use mock mode to test without API keys
4. Check provider documentation for API-specific issues