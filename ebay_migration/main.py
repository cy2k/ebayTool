import sys
import os
from sqlalchemy.orm import Session
from db import init_db
from auth import EbayAuth
from listings import fetch_active_listings, parse_and_save_listings
from images import download_images
from policies import fetch_policies, save_source_policies, sync_to_target
from upload_images import upload_to_eps
from publish import publish_listings
from verify import verify_migrations
from dotenv import load_dotenv

# Load env if exists
load_dotenv(override=True)

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")
DEV_ID = os.getenv("EBAY_DEV_ID")
RU_NAME = os.getenv("EBAY_RU_NAME")

import requests

def get_token(account_type):
    """Get or request token (basic, no validation)."""
    auth = EbayAuth(APP_ID, CERT_ID, RU_NAME)
    token = auth.get_access_token(account_type)
    if not token:
        print(f"\n--- {account_type.upper()} AUTHORIZATION REQUIRED ---")
        url = auth.get_authorization_url(account_type)
        print(f"Please open this URL in your browser:\n{url}")
        
        user_input = input("Enter the code (or paste the full redirect URL): ").strip()
        
        # Check if full URL
        if "http" in user_input and "code=" in user_input:
            import urllib.parse
            parsed = urllib.parse.urlparse(user_input)
            query = urllib.parse.parse_qs(parsed.query)
            code = query.get('code', [''])[0]
        else:
            code = user_input

        # Safety: Decode just in case
        import urllib.parse
        code = urllib.parse.unquote(code)
        
        token_data = auth.fetch_token(code, account_type)
        return token_data['access_token']
    return token

def get_validated_token(account_type):
    """
    Get token with live API validation.
    If token is expired/invalid, forces re-authentication.
    Works for both 'source' and 'target' accounts.
    """
    print(f"Validating {account_type.upper()} account token...")
    token = get_token(account_type)
    
    # Test the token with a simple API call
    test_url = "https://api.ebay.com/sell/account/v1/fulfillment_policy"
    test_headers = {"Authorization": f"Bearer {token}"}
    test_resp = requests.get(test_url, headers=test_headers)
    
    if test_resp.status_code == 401:
        print(f"\n⚠️  {account_type.upper()} token is invalid or expired. Forcing re-authentication...")
        # Delete the saved token
        try:
            os.remove(f"data/tokens/{account_type}_token.json")
        except:
            pass
        # Get fresh token
        token = get_token(account_type)
    
    print(f"✓ {account_type.upper()} token validated.")
    return token

def main():
    if not all([APP_ID, CERT_ID, RU_NAME]):
        print("Error: Please set EBAY_APP_ID, EBAY_CERT_ID, and EBAY_RU_NAME in .env file or environment.")
        return

    engine = init_db()
    db = Session(engine)

    while True:
        print("\n=== eBay Listing Migrator ===")
        print("1. Extract from SOURCE (Listings & Policies)")
        print("2. Download Images (Local)")
        print("3. Sync Policies to TARGET")
        print("4. Upload Images to TARGET (EPS)")
        print("5. Publish Listings to TARGET")
        print("6. Verify Migrated Listings")
        print("q. Quit")
        
        choice = input("Select step: ")
        
        if choice == '1':
            token = get_validated_token('source')
            
            print("Fetching Policies...")
            for p_type in ['fulfillment', 'payment', 'return']:
                pols = fetch_policies(token, p_type)
                save_source_policies(db, pols, p_type)
            
            print("Fetching Listings...")
            resp, api = fetch_active_listings(token)
            parse_and_save_listings(db, resp, api)
            
        elif choice == '2':
            download_images(db)
            
        elif choice == '3':
            # Ask if we need source data
            print("Do you want to re-pull Source policies from eBay? (y/n)")
            print("('n' uses local DB - recommended if you already ran Step 1)")
            repull = input("Selection: ").strip().lower()
            
            source_token = None
            if repull == 'y':
                source_token = get_validated_token('source')
            
            target_token = get_validated_token('target')
            sync_to_target(db, source_token, target_token)
            
        elif choice == '4':
            tgt_token = get_validated_token('target')
            upload_to_eps(db, tgt_token)
            
        elif choice == '5':
            tgt_token = get_validated_token('target')
            print("Starting publish process...")
            publish_listings(db, tgt_token)
            
        elif choice == '6':
            tgt_token = get_validated_token('target')
            verify_migrations(db, tgt_token)
            
        elif choice == 'q':
            break

if __name__ == "__main__":
    main()
