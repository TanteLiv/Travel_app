"""
Streamlit Web UI for Travel App
MIT License
"""

# --------------------------
# Imports
# --------------------------
from __future__ import annotations
import base64
import mimetypes
from pathlib import Path
from datetime import datetime, date, time
from typing import List, Optional

import pandas as pd
import streamlit as st

# OPTIONAL: if you use env vars
# from dotenv import load_dotenv
# load_dotenv()

# --------------------------
# Try provider imports (don't crash UI if missing)
# --------------------------
PROVIDERS_OK = True
PROVIDER_IMPORT_ERROR = None
try:
    from providers.base import Flight, FlightSegment  # type: ignore
    from travel_app import (  # type: ignore
        get_provider,
        filter_flights,
        format_duration,
        format_stops,
        AIRLINE_CODES,
    )
except Exception as e:
    PROVIDERS_OK = False
    PROVIDER_IMPORT_ERROR = e
    # Minimal fallbacks so the UI still renders
    AIRLINE_CODES = {
        "QR": "Qatar Airways",
        "QF": "Qantas",
        "BA": "British Airways",
        "EK": "Emirates",
        "SK": "SAS",
        "SQ": "Singapore Airlines",
        "AY": "Finnair",
    }

# --------------------------
# Page configuration (must be before any other st.*)
# --------------------------
st.set_page_config(page_title="Flight Search - OSL to PER", page_icon="✈️", layout="wide")

# --------------------------
# Background helper
# --------------------------
def set_background(
    image_path: str,
    fit_mode: str = "cover",   # "cover" | "contain" | "percent"
    pos_x: int = 50,           # 0 = left, 100 = right
    pos_y: int = 85,           # 0 = top, 100 = bottom
    zoom: int = 100,           # used when fit_mode == "percent"
    fixed: bool = True,
) -> None:
    """
    Apply a full-page background image from local file.
    """
    try:
        mime, _ = mimetypes.guess_type(image_path)
        if mime is None:
            mime = "image/png"
        data = Path(image_path).read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
    except FileNotFoundError:
        st.warning(
            f"Background image not found at '{image_path}'. "
            "Put your file in the assets/ folder and update the path if needed."
        )
        return

    if fit_mode == "contain":
        size_css = "contain"
    elif fit_mode == "percent":
        size_css = f"{zoom}%"
    else:
        size_css = "cover"

    attach_css = "fixed" if fixed else "scroll"

    st.markdown(
        f"""
        <style>
          .stApp {{
            background-image: url("data:{mime};base64,{b64}");
            background-repeat: no-repeat;
            background-attachment: {attach_css};
            background-position: {pos_x}% {pos_y}%;
            background-size: {size_css};
            background-color: #f7f3ea; /* warm fallback behind any gaps */
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# --------------------------
# Sidebar – Parameters
# --------------------------
with st.sidebar:
    st.header("✈️ Flight Search Parameters")
    st.markdown("**Oslo (OSL) → Perth (PER)**")

    # Origin & destination (locked to your example)
    col_from, col_to = st.columns(2)
    with col_from:
        from_airport = st.text_input("From", value="OSL", disabled=True)
    with col_to:
        to_airport = st.text_input("To", value="PER", disabled=True)

    # Dates
    st.subheader("Travel Dates")
    date_type = st.radio("Date Type", ["Single Date", "Date Range"], index=0)

    if date_type == "Single Date":
        departure_date = st.date_input("Departure Date", value=date.today(), min_value=date.today())
        date_range_end: Optional[date] = None
    else:
        # two-date default to avoid tuple issues
        date_range_val = st.date_input(
            "Date Range",
            value=[date.today(), date.today()],
            min_value=date.today()
        )
        if isinstance(date_range_val, list) and len(date_range_val) == 2:
            departure_date, date_range_end = date_range_val
        else:
            departure_date = date.today()
            date_range_end = None

    # Passenger & cabin
    adults = st.number_input("Adults", min_value=1, max_value=9, value=1)
    cabin = st.selectbox("Cabin Class", ["economy", "premium_economy", "business", "first"], index=0)

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
    max_price = st.number_input("Maximum Price (NOK)", min_value=0, max_value=50000, value=15000, step=500)

    # Departure time window
    use_time_filter = st.checkbox("Filter By Departure Time")
    if use_time_filter:
        c1, c2 = st.columns(2)
        with c1:
            dep_start = st.time_input("Earliest Departure", value=time(6, 0))
        with c2:
            dep_end = st.time_input("Latest Departure", value=time(23, 59))
        time_window: Optional[tuple[time, time]] = (dep_start, dep_end)
    else:
        time_window = None

    # Sort options
    sort_by = st.selectbox("Sort By", ["price", "duration", "departure"], index=0)

    # Background controls (easy sliders)
    st.subheader("🎨 Background (optional)")
    bg_fit = st.radio("Fit mode", ["cover", "contain", "percent"], index=0, horizontal=True)
    bg_pos_x = st.slider("Horizontal position (%)", 0, 100, 50)
    bg_pos_y = st.slider("Vertical position (%)", 0, 100, 90)    # 90 = show more of the bottom
    bg_zoom  = st.slider("Zoom (%) (when 'percent')", 30, 200, 90)
    bg_fixed = st.checkbox("Lock background while scrolling", value=True)

    # Search button
    search_clicked = st.button("🔍 Search Flights", type="primary", use_container_width=True)

# --------------------------
# Apply background
# --------------------------
# Change filename if your image differs, e.g. "assets/plane_sky.webp"
set_background(
    image_path="assets/plane_sky.png",
    fit_mode=bg_fit,
    pos_x=bg_pos_x,
    pos_y=bg_pos_y,
    zoom=bg_zoom,
    fixed=bg_fixed,
)

# --------------------------
# Main content
# --------------------------
st.title("✈️ Flight Search: Oslo to Perth")
st.markdown("### Search and filter flights from Oslo Airport Gardermoen (OSL) to Perth, Australia (PER)")

def display_flight_details(flight_obj) -> None:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**Itinerary:**")
        for j, segment in enumerate(flight_obj.itinerary):
            st.markdown(f"**Segment {j + 1}:** {segment.from_airport} → {segment.to_airport}")
            c_a, c_b, c_c = st.columns(3)
            with c_a:
                st.write(f"**Flight:** {segment.flight_number}")
                st.write(f"**Airline:** {segment.airline_code}")
            with c_b:
                st.write(f"**Departure:** {segment.dep_time_local.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Arrival:** {segment.arr_time_local.strftime('%Y-%m-%d %H:%M')}")
            with c_c:
                st.write(f"**Duration:** {format_duration(segment.duration_minutes)}")

            if j < len(flight_obj.itinerary) - 1:
                st.markdown("---")

    with col2:
        st.markdown("**Summary:**")
        st.write(f"**Total Price:** {flight_obj.price_total:.0f} {flight_obj.currency}")
        st.write(f"**Airlines:** {', '.join(flight_obj.airline_codes)}")
        total_duration = sum(s.duration_minutes for s in flight_obj.itinerary)
        st.write(f"**Total Duration:** {format_duration(total_duration)}")
        st.write(f"**Stops:** {format_stops(flight_obj.itinerary)}")
        if getattr(flight_obj, 'booking_link', None):
            st.markdown(f"[🔗 Book this flight]({flight_obj.booking_link})")

def display_results(flights_list, sort_key: str) -> None:
    if not flights_list:
        st.warning("No flights found matching your criteria. Try adjusting your filters.")
        return

    # Sort flights
    if sort_key == "price":
        flights_list.sort(key=lambda f: f.price_total)
    elif sort_key == "duration":
        flights_list.sort(key=lambda f: sum(s.duration_minutes for s in f.itinerary))
    elif sort_key == "departure":
        flights_list.sort(key=lambda f: f.itinerary[0].dep_time_local if f.itinerary else datetime.min)

    st.success(f"Found {len(flights_list)} flights matching your criteria")

    # Summary table
    summary_data = []
    for i, fl in enumerate(flights_list):
        if not fl.itinerary:
            continue

        first_segment = fl.itinerary[0]
        last_segment = fl.itinerary[-1]
        total_duration = sum(s.duration_minutes for s in fl.itinerary)

        summary_data.append({
            "Flight": i + 1,
            "Price": f"{fl.price_total:.0f} {fl.currency}",
            "Airlines": ", ".join(fl.airline_codes),
            "Departure": first_segment.dep_time_local.strftime("%H:%M"),
            "Arrival": last_segment.arr_time_local.strftime("%H:%M"),
            "Duration": format_duration(total_duration),
            "Stops": format_stops(fl.itinerary),
        })

    if summary_data:
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True)

        st.subheader("Flight Details")
        for i, fl in enumerate(flights_list):
            if not fl.itinerary:
                continue
            with st.expander(f"Flight {i + 1} — {fl.price_total:.0f} {fl.currency}"):
                display_flight_details(fl)

# --------------------------
# Search action
# --------------------------
if search_clicked:
    if not PROVIDERS_OK:
        st.error(
            "Provider modules not found yet, so I can't search real flights.\n\n"
            f"Details: {PROVIDER_IMPORT_ERROR}"
        )
    else:
        with st.spinner("Searching for flights..."):
            try:
                provider = get_provider()
                st.info(f"Using {provider.get_provider_name()} for flight search")

                search_params = {
                    "from_airport": from_airport,
                    "to_airport": to_airport,
                    "departure_date": departure_date,
                    "return_date": date_range_end,
                    "adults": adults,
                    "cabin": cabin,
                }

                flights = provider.search_flights(search_params)

                dates_tuple = (departure_date, date_range_end) if date_range_end else (departure_date, None)

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

                display_results(filtered_flights, sort_by)

            except Exception as e:
                st.error(f"Error searching flights: {e}")
else:
    st.markdown(
        """
        ### Welcome to the Flight Search Tool

        Use the sidebar to configure your search parameters:

        1. **Select your travel dates** – single date or date range  
        2. **Set passenger details** – number of adults and cabin class  
        3. **Apply filters** – airlines, price, departure time  
        4. **Choose sorting** – price, duration, or departure time  
        5. **Click Search** – find flights matching your criteria  

        If providers aren’t configured yet, the UI still loads so you can design it.
        """
    )
