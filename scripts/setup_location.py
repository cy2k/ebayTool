import requests
from ebay_migration.auth import EbayAuth
from dotenv import load_dotenv
import os

load_dotenv(override=True)

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")
RU_NAME = os.getenv("EBAY_RU_NAME")

INVENTORY_API_URL = "https://api.ebay.com/sell/inventory/v1"

def setup_location(token):
    """
    Create a default merchant location on the eBay account.
    This is required before you can create offers via the Inventory API.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    }
    
    location_key = "default"
    
    # Check if location already exists
    url = f"{INVENTORY_API_URL}/location/{location_key}"
    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 200:
        print(f"✓ Merchant location '{location_key}' already exists.")
        return True
    
    # Create the location
    print(f"Creating merchant location '{location_key}'...")
    
    location_payload = {
        "location": {
            "address": {
                "addressLine1": "5 Jeffrey Ln",
                "city": "Albany",
                "stateOrProvince": "NY",
                "postalCode": "12211",
                "country": "US"
            }
        },
        "merchantLocationStatus": "ENABLED",
        "name": "Default Shipping Location",
        "locationTypes": ["WAREHOUSE"]
    }
    
    resp = requests.post(url, headers=headers, json=location_payload)
    
    if resp.status_code in [200, 201, 204]:
        print(f"✓ Merchant location '{location_key}' created successfully!")
        return True
    else:
        print(f"Failed to create location: {resp.status_code} {resp.text}")
        return False

if __name__ == "__main__":
    print("=== Setup Merchant Location ===")
    print("\nThis will create a default shipping location on your TARGET eBay account.")
    print("You can change the address later in eBay Seller Hub if needed.\n")
    
    auth = EbayAuth(APP_ID, CERT_ID, RU_NAME)
    token = auth.get_access_token('target')
    
    if not token:
        print("Need to authenticate first.")
        url = auth.get_authorization_url('target')
        print(f"Please open: {url}")
        code = input("Enter code: ").strip()
        if "http" in code and "code=" in code:
            import urllib.parse
            parsed = urllib.parse.urlparse(code)
            query = urllib.parse.parse_qs(parsed.query)
            code = query.get('code', [''])[0]
        code = urllib.parse.unquote(code)
        token_data = auth.fetch_token(code, 'target')
        token = token_data['access_token']
    
    setup_location(token)
