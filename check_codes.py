from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")  # load keys from .env

import os, json
from amadeus import Client, ResponseError

CID = os.getenv("AMADEUS_CLIENT_ID")
CSECRET = os.getenv("AMADEUS_CLIENT_SECRET")
if not CID or not CSECRET:
    raise SystemExit("Missing AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET in .env")

amadeus = Client(client_id=CID, client_secret=CSECRET)

def verify_airport(code: str) -> None:
    code = code.strip().upper()
    try:
        # Ask for both AIRPORT and CITY to be safe
        resp = amadeus.reference_data.locations.get(
            keyword=code,
            subType="AIRPORT,CITY"
        )
        data = resp.data or []
        exact = [d for d in data if d.get("iataCode") == code]

        if exact:
            d0 = exact[0]
            print(f"✔ {code} recognized as: {d0.get('name','Unknown')} — type: {d0.get('subType')}")
        else:
            print(f"✖ {code} not found as an exact code in this endpoint.")
            # Show what DID come back so we can diagnose
            if data:
                print("Top matches returned by Amadeus:")
                print(json.dumps(data[:3], indent=2))  # show first few
            else:
                print("(No results returned.)\n"
                      "If Flight Offers works but this returns empty, you likely need to add "
                      "'Airport & City Search' to your Self-Service app.")

    except ResponseError as e:
        print("Amadeus error:", getattr(e, "code", "unknown"))
        if getattr(e, "response", None) and getattr(e.response, "result", None):
            print(json.dumps(e.response.result, indent=2))

verify_airport("OSL")
verify_airport("PER")
