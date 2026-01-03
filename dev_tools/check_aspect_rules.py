import os
import requests
from dotenv import load_dotenv
from ebay_migration.auth import EbayAuth

load_dotenv()

def check_aspect_rules():
    print("Fetching Aspect Rules for Category 261186 (Books)...")
    
    auth = EbayAuth(
        os.getenv("EBAY_APP_ID"),
        os.getenv("EBAY_CERT_ID"),
        os.getenv("EBAY_RU_NAME")
    )
    token = auth.get_access_token('target')
    
    if not token:
        print("Failed to get access token. Please run main.py to auth first.")
        return
    
    # Taxonomy API: getItemAspectsForCategory
    # Using the correct endpoint and parameters
    url = "https://api.ebay.com/commerce/taxonomy/v1/category_tree/0/get_item_aspects_for_category?category_id=261186"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    }
    
    print(f"Calling URL: {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch rules: {resp.status_code} {resp.text}")
        return

    data = resp.json()
    aspects = data.get('aspects', [])
    
    target_aspects = ['Topic', 'Language', 'Country of Origin']
    
    # Also look for any aspect that allows MULTI
    multi_count = 0
    
    print("\n--- ASPECT RULES FOR 'BOOKS' (261186) ---")
    found_targets = []
    
    for aspect in aspects:
        name = aspect.get('localizedAspectName')
        constraint = aspect.get('aspectConstraint', {})
        cardinality = constraint.get('itemToAspectCardinality')
        mode = constraint.get('aspectMode')
        
        if name in target_aspects:
            found_targets.append(name)
            print(f"Aspect: {name}")
            print(f"  Cardinality: {cardinality}") # SINGLE or MULTI
            print(f"  Mode: {mode}") # FREE_TEXT or SELECTION_ONLY
            print("-" * 20)
            
        if cardinality == 'MULTI':
            multi_count += 1
            
    print(f"\nTotal aspects allowing MULTI values: {multi_count}")
    print(f"Found target aspects: {found_targets}")

if __name__ == "__main__":
    check_aspect_rules()
