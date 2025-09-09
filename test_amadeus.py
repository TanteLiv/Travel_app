from dotenv import load_dotenv
load_dotenv()

import os
from amadeus import Client, ResponseError

print("CID present:", bool(os.getenv("AMADEUS_CLIENT_ID")))
print("CSECRET present:", bool(os.getenv("AMADEUS_CLIENT_SECRET")))

amadeus = Client(  # uses the test (sandbox) API by default
    client_id=os.getenv("AMADEUS_CLIENT_ID"),
    client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
)

try:
    resp = amadeus.shopping.flight_offers_search.get(
        originLocationCode="OSL",
        destinationLocationCode="PER",
        departureDate="2025-12-01",
        adults=1,
        currencyCode="NOK",
        max=5
    )
    print("OK, got", len(resp.data), "offers")
except ResponseError as e:
    print("Amadeus error:", e)
    if getattr(e, "response", None):
        print(e.response.body)