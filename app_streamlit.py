"""
Streamlit Web UI for Travel App
MIT License
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from typing import List, Optional, Tuple
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our travel app components
from providers.base import Flight, FlightSegment
from providers.mock import MockProvider
from providers.kiwi import KiwiProvider
from providers.amadeus import AmadeusProvider
from providers.skyscanner import SkyscannerProvider
from travel_app import (
    get_provider, normalize_airline_codes, parse_time_window, 
    filter_flights, format_duration, format_stops, AIRLINE_CODES
)

# Page configuration
st.set_page_config(
    page_title="Flight Search - OSL to PER",
    page_icon="✈️",
    layout="wide"
)

# --- Background & UI styling (replaces the old CSS block) ---
from airplane_background_base64 import get_airplane_background

# Build a robust CSS background-image value from whatever the helper returns
bg_src = get_airplane_background() or ""
if bg_src.startswith("url("):
    bg_url = bg_src                                   # already like url('data:image/png;base64,...')
elif bg_src.startswith("data:image"):
    bg_url = f"url('{bg_src}')"                       # full data URI but missing url(...)
else:
    bg_url = f"url('data:image/png;base64,{bg_src}')" # raw base64 -> full data URI

st.markdown(f"""
<style>
/* 1) Set the airplane image as the app-wide background */
html, body, [data-testid="stAppViewContainer"] {{
  background-image: {bg_url};
  background-size: cover;
  background-position: center center;
  background-attachment: fixed;
  min-height: 100%;
}}

/* 2) Make main content and sidebar glassy so the plane shows through */
[data-testid="stAppViewContainer"] > .main .block-container {{
  background: rgba(255, 255, 255, 0.35);
  backdrop-filter: blur(6px);
  border-radius: 16px;
  padding: 24px 24px 40px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}}

[data-testid="stSidebar"] {{
  background: rgba(255, 255, 255, 0.92) !important;
  backdrop-filter: blur(8px);
  box-shadow: 2px 0 15px rgba(0,0,0,0.2);
}}

/* 3) Nice touches for widgets and headers */
h1, h2, h3 {{
  color: #2F4F4F !important;
  text-shadow: 0 1px 2px rgba(255,255,255,0.7);
  font-weight: 700;
}}

.stButton > button {{
  background: linear-gradient(135deg, #ff9a56 0%, #ff6b35 100%);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-weight: 700;
  box-shadow: 0 6px 18px rgba(255,107,53,0.35);
  transition: transform .2s ease, box-shadow .2s ease;
}}
.stButton > button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 10px 22px rgba(255,107,53,0.45);
}}

.stTextInput input, .stNumberInput input, .stSelectbox > div {{
  background: rgba(255,255,255,0.95);
  border: 1px solid rgba(255,154,86,0.35);
  border-radius: 8px;
}}
</style>
""", unsafe_allow_html=True)

def main():
    """Main Streamlit application."""
    
    # Left column for parameters (using sidebar)
    with st.sidebar:
        st.header("✈️ Flight Search Parameters")
        st.markdown("**Oslo (OSL) → Perth (PER)**")
        
        # Origin and destination
        col1, col2 = st.columns(2)
        with col1:
            from_airport = st.text_input("From", value="OSL", disabled=True)
        with col2:
            to_airport = st.text_input("To", value="PER", disabled=True)
        
        # Date selection
        st.subheader("Travel Dates")
        date_type = st.radio("Date Type", ["Single Date", "Date Range"])
        
        if date_type == "Single Date":
            departure_date = st.date_input(
                "Departure Date",
                value=date.today(),
                min_value=date.today()
            )
            date_range_end = None
        else:
            date_range = st.date_input(
                "Date Range",
                value=[date.today()],
                min_value=date.today()
            )
            if len(date_range) == 2:
                departure_date, date_range_end = date_range
            else:
                departure_date = date_range[0] if date_range else date.today()
                date_range_end = None
        
        # Passenger and cabin
        adults = st.number_input("Adults", min_value=1, max_value=9, value=1)
        cabin = st.selectbox("Cabin Class", ["economy", "premium_economy", "business", "first"])
        
        # Filters
        st.subheader("Filters")
        
        # Airline filter
        airline_options = ["ALL"] + list(AIRLINE_CODES.keys())
        selected_airlines = st.multiselect(
            "Airlines",
            options=airline_options,
            default=["ALL"],
            format_func=lambda x: "All Airlines" if x == "ALL" else f"{x} - {AIRLINE_CODES[x]}"
        )
        
        # Price filter
        max_price = st.number_input(
            "Maximum Price (NOK)",
            min_value=0,
            max_value=50000,
            value=15000,
            step=500
        )
        
        # Departure time window
        use_time_filter = st.checkbox("Filter By Departure Time")
        if use_time_filter:
            col1, col2 = st.columns(2)
            with col1:
                dep_start = st.time_input("Earliest Departure", value=time(6, 0))
            with col2:
                dep_end = st.time_input("Latest Departure", value=time(23, 59))
            time_window = (dep_start, dep_end)
        else:
            time_window = None
        
        # Sort options
        sort_by = st.selectbox("Sort By", ["price", "duration", "departure"])
        
        # Search button
        search_clicked = st.button("🔍 Search Flights", type="primary", use_container_width=True)
    
    # Title and header
    st.title("✈️ Flight Search: Oslo to Perth")
    st.markdown("### Search and filter flights from Oslo Airport Gardermoen (OSL) to Perth, Australia (PER)")
    
    # Main content area
    if search_clicked:
        with st.spinner("Searching for flights..."):
            try:
                # Get provider
                provider = get_provider()
                
                # Show provider info
                st.info(f"Using {provider.get_provider_name()} for flight search")
                
                # Prepare search parameters
                search_params = {
                    "from_airport": from_airport,
                    "to_airport": to_airport,
                    "departure_date": departure_date,
                    "return_date": date_range_end,
                    "adults": adults,
                    "cabin": cabin
                }
                
                # Search flights
                flights = provider.search_flights(search_params)
                
                # Apply filters
                dates_tuple = (departure_date, date_range_end) if date_range_end else (departure_date, None)
                
                # Handle "ALL" airlines selection
                airlines_filter = None
                if selected_airlines and "ALL" not in selected_airlines:
                    airlines_filter = selected_airlines
                
                filtered_flights = filter_flights(
                    flights,
                    airlines=airlines_filter,
                    max_price=max_price,
                    dep_time_between=time_window,
                    dates=dates_tuple
                )
                
                # Display results
                display_results(filtered_flights, sort_by)
                
            except Exception as e:
                st.error(f"Error searching flights: {e}")
    else:
        # Show welcome message and instructions
        st.markdown("""
        ### Welcome to the Flight Search Tool
        
        Use the sidebar to configure your search parameters:
        
        1. **Select your travel dates** - Choose a single date or date range
        2. **Set passenger details** - Number of adults and cabin class
        3. **Apply filters** - Filter by airlines, price, and departure time
        4. **Choose sorting** - Sort results by price, duration, or departure time
        5. **Click Search** - Find flights matching your criteria
        
        The app will automatically use mock data if no API keys are configured,
        allowing you to test all features without external API access.
        """)
        
        # Show sample data info
        with st.expander("ℹ️ About the Data"):
            st.markdown("""
            **Mock Mode**: When no API keys are configured, the app uses sample flight data
            that includes realistic itineraries from various airlines:
            
            - Qatar Airways (QR) - via Doha
            - Emirates (EK) - via Dubai
            - Singapore Airlines (SQ) - via Copenhagen and Singapore
            - Qantas (QF) - via London or Sydney
            - Finnair (AY) - via Helsinki and Tokyo
            - British Airways (BA) - via London and Singapore
            - SAS (SK) - via Stockholm and Bangkok
            
            **Real API Mode**: Configure API keys in `.env` file to use live flight data
            from Kiwi, Amadeus, or Skyscanner APIs.
            """)
    

def display_results(flights: List[Flight], sort_by: str):
    """Display flight search results."""
    if not flights:
        st.warning("No flights found matching your criteria. Try adjusting your filters.")
        return
    
    # Sort flights
    if sort_by == "price":
        flights.sort(key=lambda f: f.price_total)
    elif sort_by == "duration":
        flights.sort(key=lambda f: sum(s.duration_minutes for s in f.itinerary))
    elif sort_by == "departure":
        flights.sort(key=lambda f: f.itinerary[0].dep_time_local if f.itinerary else datetime.min)
    
    st.success(f"Found {len(flights)} flights matching your criteria")
    
    # Create summary table
    summary_data = []
    for i, flight in enumerate(flights):
        if not flight.itinerary:
            continue
            
        first_segment = flight.itinerary[0]
        last_segment = flight.itinerary[-1]
        
        total_duration = sum(s.duration_minutes for s in flight.itinerary)
        
        summary_data.append({
            "Flight": i + 1,
            "Price": f"{flight.price_total:.0f} {flight.currency}",
            "Airlines": ", ".join(flight.airline_codes),
            "Departure": first_segment.dep_time_local.strftime("%H:%M"),
            "Arrival": last_segment.arr_time_local.strftime("%H:%M"),
            "Duration": format_duration(total_duration),
            "Stops": format_stops(flight.itinerary)
        })
    
    # Display summary table
    if summary_data:
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True)
        
        # Detailed flight information
        st.subheader("Flight Details")
        
        for i, flight in enumerate(flights):
            if not flight.itinerary:
                continue
                
            with st.expander(f"Flight {i + 1} - {flight.price_total:.0f} {flight.currency}"):
                display_flight_details(flight)


def display_flight_details(flight: Flight):
    """Display detailed information for a single flight."""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Itinerary:**")
        
        for j, segment in enumerate(flight.itinerary):
            # Segment header
            st.markdown(f"**Segment {j + 1}:** {segment.from_airport} → {segment.to_airport}")
            
            # Flight details
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write(f"**Flight:** {segment.flight_number}")
                st.write(f"**Airline:** {segment.airline_code}")
            with col_b:
                st.write(f"**Departure:** {segment.dep_time_local.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Arrival:** {segment.arr_time_local.strftime('%Y-%m-%d %H:%M')}")
            with col_c:
                st.write(f"**Duration:** {format_duration(segment.duration_minutes)}")
            
            if j < len(flight.itinerary) - 1:
                st.markdown("---")
    
    with col2:
        st.markdown("**Summary:**")
        st.write(f"**Total Price:** {flight.price_total:.0f} {flight.currency}")
        st.write(f"**Airlines:** {', '.join(flight.airline_codes)}")
        
        total_duration = sum(s.duration_minutes for s in flight.itinerary)
        st.write(f"**Total Duration:** {format_duration(total_duration)}")
        st.write(f"**Stops:** {format_stops(flight.itinerary)}")
        
        if flight.booking_link:
            st.markdown(f"[🔗 Book this flight]({flight.booking_link})")


if __name__ == "__main__":
    main()
