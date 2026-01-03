import requests
from ebay_migration.auth import EbayAuth
from dotenv import load_dotenv
import os
import json

load_dotenv(override=True)

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")
RU_NAME = os.getenv("EBAY_RU_NAME")

INVENTORY_API_URL = "https://api.ebay.com/sell/inventory/v1"

def list_locations(token):
    """List all merchant locations on the eBay account."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"{INVENTORY_API_URL}/location"
    resp = requests.get(url, headers=headers)
    
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    print("=== Checking Merchant Locations on TARGET Account ===\n")
    
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
    
    list_locations(token)
