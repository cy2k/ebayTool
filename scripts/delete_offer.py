import requests
from ebay_migration.auth import EbayAuth
from dotenv import load_dotenv
import os

load_dotenv(override=True)

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")
RU_NAME = os.getenv("EBAY_RU_NAME")

INVENTORY_API_URL = "https://api.ebay.com/sell/inventory/v1"

def delete_offer(token, offer_id):
    """Delete an offer by ID."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"{INVENTORY_API_URL}/offer/{offer_id}"
    resp = requests.delete(url, headers=headers)
    
    if resp.status_code in [200, 204]:
        print(f"✓ Deleted offer {offer_id}")
        return True
    else:
        print(f"Failed to delete offer: {resp.status_code} {resp.text}")
        return False

if __name__ == "__main__":
    print("=== Delete Corrupt Offer ===\n")
    
    offer_id = input("Enter offer ID to delete (e.g., YOUR_OFFER_ID): ").strip()
    
    if not offer_id:
        print("No offer ID provided.")
        exit()
    
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
    
    confirm = input(f"Delete offer {offer_id}? (y/n): ")
    if confirm.lower() == 'y':
        delete_offer(token, offer_id)
    else:
        print("Cancelled.")
