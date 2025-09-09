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
from dotenv import load_dotenv
load_dotenv()
import os
try:
    from amadeus import Client, ResponseError  # installed? (sdk)
    HAS_AMADEUS_SDK = True
except Exception as e:
    HAS_AMADEUS_SDK = False
    AMADEUS_IMPORT_ERROR = e

CID = os.getenv("AMADEUS_CLIENT_ID")
CSECRET = os.getenv("AMADEUS_CLIENT_SECRET")
HAS_KEYS = bool(CID and CSECRET)
AMAD_READY = HAS_AMADEUS_SDK and HAS_KEYS
with st.sidebar:
    st.caption(f"Amadeus ready: {AMAD_READY}")

import re
from datetime import timedelta  # you already import date/time/datetime

def _amadeus_travel_class(cabin: str) -> str:
    """Map UI values to Amadeus enum."""
    mapping = {
        "economy": "ECONOMY",
        "premium_economy": "PREMIUM_ECONOMY",
        "business": "BUSINESS",
        "first": "FIRST",
    }
    return mapping.get(cabin.lower(), "ECONOMY")

def _iso8601_duration_to_minutes(d: str) -> int:
    """Amadeus duration like 'PT11H5M' -> minutes."""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", d)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return h * 60 + mins

def _parse_dt(s: str) -> datetime:
    """'2025-12-30T14:10:00' or '...Z' -> naive datetime (local-naive for UI)."""
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    # Drop tzinfo to keep your existing UI happy
    return dt.replace(tzinfo=None)

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
            background-color: #ffffff; /* lighter fallback behind any gaps */
            font-size: 2.1em; /* Increase font size */
            font-weight: 1000; /* Make text slightly bolder */
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
    children = st.number_input("Children (0-17)", min_value=0, max_value=9, value=0)
    infants = st.number_input("Infants (0-1)", min_value=0, max_value=9, value=0)
    if infants > adults:
        st.warning("Each infant must be accompanied by an adult.")
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
        st.write(f"**Price per Person:** {flight_obj.price_total / adults:.0f} {flight_obj.currency}")
        st.write(f"**Total Price for {adults} Adults:** {flight_obj.price_total:.0f} {flight_obj.currency}")
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
            "Airlines": ", ".join(AIRLINE_CODES.get(code, code) for code in fl.airline_codes),
            "Departure": first_segment.dep_time_local.strftime("%H:%M"),
            "Arrival": last_segment.arr_time_local.strftime("%H:%M"),
            "Duration": format_duration(total_duration),
            "Stops": format_stops(fl.itinerary),
        })

    if summary_data:
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True)

        st.subheader("Flight Details")
        st.markdown(
            """
            <style>
            .stExpander {
                background-color: #ffffff; /* Set background to white */
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        for i, fl in enumerate(flights_list):
            if not fl.itinerary:
                continue
            with st.expander(f"Flight {i + 1} — {fl.price_total:.0f} {fl.currency}"):
                display_flight_details(fl)
from datetime import timedelta

st.caption(f"Searching: {from_airport} → {to_airport} on {departure_date} "
           f"| adults={adults}, children={children}, infants={infants}, cabin={cabin}")

def fetch_live_offers_amadeus(origin, dest, dep_dt, adults, children, infants, cabin):
    """
    Fetch live flight offers from Amadeus and convert them into your Flight objects.
    """
    # Build parameters correctly (omit children/infants if zero; travelClass in Amadeus format)
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": dest,
        "departureDate": dep_dt.strftime("%Y-%m-%d"),
        "adults": int(adults),
        "currencyCode": "NOK",
        "max": 20,
        "travelClass": _amadeus_travel_class(cabin),
    }
    if int(children) > 0:
        params["children"] = int(children)
    if int(infants) > 0:
        params["infants"] = int(infants)

    # Optional: simple guard to avoid past dates
    if dep_dt < date.today():
        st.warning("Departure date is in the past; shifting to today.")
        params["departureDate"] = date.today().strftime("%Y-%m-%d")

    # Do the call
    try:
        amadeus = Client(
            client_id=os.getenv("AMADEUS_CLIENT_ID"),
            client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
        )
        resp = amadeus.shopping.flight_offers_search.get(**params)
        offers = resp.data or []

        # Convert Amadeus offers -> your Flight dataclass list
        flights: List[Flight] = []
        for offer in offers:
            price_total = float(offer["price"]["grandTotal"])
            currency = offer["price"]["currency"]

            segments_all: List[FlightSegment] = []
            airline_codes_set = set()

            for itin in offer.get("itineraries", []):
                for seg in itin.get("segments", []):
                    carrier = seg["carrierCode"]
                    number = seg["number"]
                    dep = seg["departure"]
                    arr = seg["arrival"]

                    dep_dt_local = _parse_dt(dep["at"])
                    arr_dt_local = _parse_dt(arr["at"])

                    # Prefer the given duration; if missing, compute diff
                    dur_minutes = _iso8601_duration_to_minutes(seg.get("duration", "PT0M"))
                    if dur_minutes == 0:
                        dur_minutes = int((arr_dt_local - dep_dt_local).total_seconds() // 60)

                    segments_all.append(
                        FlightSegment(
                            from_airport=dep["iataCode"],
                            to_airport=arr["iataCode"],
                            flight_number=f"{carrier} {number}",
                            airline_code=carrier,
                            dep_time_local=dep_dt_local,
                            arr_time_local=arr_dt_local,
                            duration_minutes=dur_minutes,
                        )
                    )
                    airline_codes_set.add(carrier)

            flights.append(
                Flight(
                    itinerary=segments_all,
                    price_total=price_total,
                    currency=currency,
                    airline_codes=sorted(airline_codes_set),
                    booking_link=None,  # you can add a deeplink later if you want
                )
            )

        return flights

    except ResponseError as e:
        # Show full error detail so we know *why* 400 happens
        st.error(f"Amadeus API error: [{getattr(e, 'code', 'unknown')}]")
        if getattr(e, "response", None) and getattr(e.response, "result", None):
            st.code(str(e.response.result), language="json")
        return []


# --------------------------
# Search action
# --------------------------
if search_clicked:
    if not PROVIDERS_OK:
        st.error(
            "Provider modules not loaded, so I can't run live searches yet.\n\n"
            f"Details: {PROVIDER_IMPORT_ERROR}"
        )

    else:
        with st.spinner("Searching for flights..."):
            try:
                if AMAD_READY:
                    # ✅ LIVE data via Amadeus
                    flights = fetch_live_offers_amadeus(
                        origin=from_airport,
                        dest=to_airport,
                        dep_dt=departure_date,
                        adults=adults,
                        children=children,
                        infants=infants,
                        cabin=cabin,
                    )
                else:
                    # 🧪 Fallback to mock (only if keys/SDK not ready)
                    st.info("Amadeus not configured/activated yet — showing mock results.")
                    flights = make_mock_flights(departure_date, from_airport, to_airport) # type: ignore

                # Apply your existing filters/sort + render
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
