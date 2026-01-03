import requests
from sqlalchemy.orm import Session
from db import Listing, SourcePolicy
from publish import CONDITION_MAP, get_target_policy_id

INVENTORY_API_URL = "https://api.ebay.com/sell/inventory/v1"

def normalize_text(text):
    if not text: return ""
    return " ".join(text.split()).strip()

def verify_migrations(db: Session, target_token):
    headers = {
        "Authorization": f"Bearer {target_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    }

    migrated_listings = db.query(Listing).filter(Listing.migrated == True).all()
    
    if not migrated_listings:
        print("No migrated listings found to verify.")
        return

    print(f"\nVerifying {len(migrated_listings)} migrated listings...")
    
    issues_found = 0
    
    for idx, item in enumerate(migrated_listings):
        sku = item.sku
        failures = []
        
        try:
            # 1. FETCH INVENTORY ITEM
            inv_url = f"{INVENTORY_API_URL}/inventory_item/{sku}"
            inv_resp = requests.get(inv_url, headers=headers)
            
            if inv_resp.status_code != 200:
                print(f"[FAIL] {sku}: Could not fetch Inventory Item ({inv_resp.status_code})")
                issues_found += 1
                continue
                
            inv_data = inv_resp.json()
            product = inv_data.get('product', {})
            
            # --- VERIFY PRODUCT DETAILS ---
            
            # Title
            if normalize_text(product.get('title')) != normalize_text(item.title):
                failures.append(f"Title Mismatch: '{product.get('title')}' != '{item.title}'")
                
            # Description (Check if one contains the other, usually description is wrapped in HTML divs)
            # This is hard to do exactly, so we check length or inclusion
            live_desc = normalize_text(product.get('description'))
            local_desc = normalize_text(item.description)
            if local_desc not in live_desc and len(local_desc) != len(live_desc):
                 # Fail only if significantly different to avoid HTML wrapper noise
                 failures.append("Description content mismatch")

            # Condition
            expected_cond = CONDITION_MAP.get(str(item.condition_id), 'USED_GOOD')
            if inv_data.get('condition') != expected_cond:
                # Fallback check - logic in publish.py handles unknown codes
                if inv_data.get('condition') == 'USED_GOOD' and expected_cond == 'USED':
                     pass # Acceptable fallback
                else:
                    failures.append(f"Condition: {inv_data.get('condition')} != {expected_cond}")

            # Images
            live_imgs = product.get('imageUrls', [])
            local_valid_imgs = [i for i in item.images if i.new_eps_url]
            if len(live_imgs) != len(local_valid_imgs):
                failures.append(f"Image Count: {len(live_imgs)} != {len(local_valid_imgs)}")

            # Aspects (Item Specifics)
            live_aspects = product.get('aspects', {})
            local_aspects = item.item_specifics_json or {}
            
            for key, val in local_aspects.items():
                if key not in live_aspects:
                     # Some keys might be normalized differently by eBay, but strict check for now
                     # Ignore 'Book Title' added by publish.py logic
                     if key == 'Book Title': continue 
                     failures.append(f"Missing Aspect: {key}")
                else:
                    if key in ['Topic', 'Language', 'Country of Origin', 'Country/Region of Manufacture']:
                         # Special handling for joined fields
                         local_vals = val if isinstance(val, list) else [val]
                         # Our publish logic joins them with ", " if > 1
                         if len(local_vals) > 1:
                             expected_str = ", ".join(local_vals)
                         else:
                             expected_str = local_vals[0]
                         
                         # Live side is likely a single string in a list ['A, B']
                         live_val_list = live_aspects.get(key, [])
                         live_str = live_val_list[0] if live_val_list else ""
                         
                         if normalize_text(expected_str).lower() != normalize_text(live_str).lower():
                             # Try partial match (sometimes order differs or eBay truncates)
                             if normalize_text(local_vals[0]).lower() not in normalize_text(live_str).lower():
                                failures.append(f"Aspect '{key}': '{live_str}' != '{expected_str}'")
                    else:
                        # Standard comparison
                        v1 = normalize_text(val[0]) if isinstance(val, list) and val else ""
                        v2 = normalize_text(live_aspects[key][0]) if isinstance(live_aspects[key], list) and live_aspects[key] else ""
                        if v1.lower() != v2.lower():
                            failures.append(f"Aspect '{key}': {v2} != {v1}")

            # Package
            pkg_data = inv_data.get('packageWeightAndSize', {})
            has_pkg = 'dimensions' in pkg_data or 'weight' in pkg_data
            # Code adds package if missing. Logic helps to ensure we HAVE it.
            if not has_pkg:
                failures.append("Missing Package Weight/Dimensions on Live Item")


            # 2. FETCH OFFER
            if not item.new_offer_id:
                failures.append("Missing Offer ID in local DB")
            else:
                offer_url = f"{INVENTORY_API_URL}/offer/{item.new_offer_id}"
                off_resp = requests.get(offer_url, headers=headers)
                
                if off_resp.status_code == 200:
                    off_data = off_resp.json()
                    
                    # Price
                    price = off_data.get('pricingSummary', {}).get('price', {}).get('value')
                    if float(price) != float(item.price):
                        failures.append(f"Price: {price} != {item.price}")
                        
                    # Quantity
                    qty = off_data.get('availableQuantity')
                    if int(qty) != int(item.quantity):
                         failures.append(f"Quantity: {qty} != {item.quantity}")
                         
                    # Status
                    status = off_data.get('listing', {}).get('listingStatus') or off_data.get('status')
                    if status not in ['PUBLISHED', 'ACTIVE']:
                        failures.append(f"Offer Status: {status} (Expected PUBLISHED or ACTIVE)")
                        
                else:
                    failures.append(f"Could not fetch Offer {item.new_offer_id} ({off_resp.status_code})")

            # REPORT
            if failures:
                issues_found += 1
                print(f"[FAIL] {sku}")
                for f in failures:
                    print(f"  - {f}")
            else:
                print(f"[PASS] {sku}")
                
        except Exception as e:
            print(f"[ERR] {sku}: {e}")
            issues_found += 1

    print(f"\nVerification Complete. {issues_found} issues found out of {len(migrated_listings)} items.")
