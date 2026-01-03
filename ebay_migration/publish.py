import requests
import json
from sqlalchemy.orm import Session
from db import Listing, SourcePolicy
import uuid

INVENTORY_API_URL = "https://api.ebay.com/sell/inventory/v1"

def get_target_policy_id(db: Session, source_id):
    """Resolve Source Policy ID -> Target Policy ID"""
    if not source_id: return None
    mapping = db.query(SourcePolicy).filter_by(policy_id=source_id).first()
    if mapping and mapping.target_policy_id:
        return mapping.target_policy_id
    print(f"Warning: No mapping found for source policy {source_id}")
    return None

# Map Numeric IDs (Trading API) to Enum (Inventory API)
# Ref: https://developer.ebay.com/api-docs/sell/inventory/types/slr:ConditionEnum
CONDITION_MAP = {
    '1000': 'NEW',
    '1500': 'NEW_OTHER',
    '1750': 'NEW_WITH_DEFECTS',
    '2000': 'CERTIFIED_REFURBISHED', 
    '2010': 'EXCELLENT_REFURBISHED',
    '2020': 'VERY_GOOD_REFURBISHED',
    '2030': 'GOOD_REFURBISHED',
    '2500': 'SELLER_REFURBISHED',
    '2750': 'LIKE_NEW',
    '2990': 'PRE_OWNED_EXCELLENT',
    '3000': 'USED_EXCELLENT',
    '3010': 'PRE_OWNED_FAIR',
    '4000': 'USED_VERY_GOOD',
    '5000': 'USED_GOOD',
    '6000': 'USED_ACCEPTABLE',
    '7000': 'FOR_PARTS_OR_NOT_WORKING'
}

def publish_listings(db: Session, target_token):
    """
    1. Create/Update Inventory Item.
    2. Create Offer.
    3. Publish Offer.
    """
    headers = {
        "Authorization": f"Bearer {target_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    }
    
    listings = db.query(Listing).filter(Listing.migrated == False).all()
    
    if not listings:
        print("No pending listings found.")
        return

    print(f"Found {len(listings)} pending items.")
    limit_input = input("How many to publish? (enter number or 'all'): ").strip().lower()
    
    limit = len(listings)
    if limit_input != 'all':
        try:
            limit = int(limit_input)
        except ValueError:
            print("Invalid input. Exiting.")
            return

    print(f"Starting migration for {limit} listings...")
    
    for idx, item in enumerate(listings):
        if idx >= limit:
            print(f"Reached batch limit of {limit}.")
            break
                
        try:
            # --- PREPARE DATA ---
            # 1. Images (Must be new EPS URLs)
            img_urls = []
            for img in item.images:
                if img.new_eps_url:
                    # FORCE HIGH RES: eBay API often returns $_1 (thumbnail) even for high-res uploads.
                    # We simply rewrite it to $_57 (1600px) which is valid for the same asset.
                    final_url = img.new_eps_url
                    if "$_1" in final_url:
                        final_url = final_url.replace("$_1", "$_57")
                    img_urls.append(final_url)
                
            if not img_urls:
                print(f"Stopping: {item.sku} has no images uploaded to Target yet.")
                print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
                return
                
            # 2. Policies
            pay_id = get_target_policy_id(db, item.payment_policy_id)
            ship_id = get_target_policy_id(db, item.shipping_policy_id)
            ret_id = get_target_policy_id(db, item.return_policy_id)
            
            if not (pay_id and ship_id and ret_id):
                print(f"Stopping: {item.sku} has missing mapped policies.")
                print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
                return

            # --- STEP 1: CREATE INVENTORY ITEM ---
            
            target_condition = CONDITION_MAP.get(str(item.condition_id), 'USED_GOOD') # Default fallback
            
            # Prepare aspects - ensure required fields are present
            aspects = item.item_specifics_json or {}
            
            # --- FIX FOR "TOPIC SHOULD CONTAIN ONLY ONE VALUE" ERROR ---
            # Aspect Rule says MULTI + FREE_TEXT, but API rejects Array.
            # Workaround: Send as single string with comma separation.
            # We apply this to Topic and Language. Country is typically strictly SINGLE SELECTION.
            
            # 1. Comma-Join Candidates (with Length Limit of 65 chars)
            # "Topic's value... is too long. Enter a value of no more than 65 characters."
            JOIN_KEYS = ['Topic', 'Language']
            for key in JOIN_KEYS:
                if key in aspects and isinstance(aspects[key], list) and len(aspects[key]) > 1:
                     parts = aspects[key]
                     final_val = parts[0]
                     for p in parts[1:]:
                         if len(final_val) + len(p) + 2 <= 65: # +2 for ", "
                             final_val += ", " + p
                         else:
                             break
                     
                     print(f"  Merging aspect '{key}': Joined to '{final_val}' (Limit 65)")
                     aspects[key] = [final_val]
            
            # 2. Strict Single Candidates (Truncate)
            TRUNCATE_KEYS = ['Country of Origin', 'Country/Region of Manufacture']
            for key in TRUNCATE_KEYS:
                if key in aspects and isinstance(aspects[key], list) and len(aspects[key]) > 1:
                    print(f"  Fixing strict aspect '{key}': Truncating to single value.")
                    aspects[key] = [aspects[key][0]]
            
            # For Books category (261186), "Book Title" is required
            # Auto-fill from listing title if missing
            if not aspects.get('Book Title') and item.category_id == '261186':
                aspects['Book Title'] = [item.title]  # Aspects values must be arrays
            
            # Prepare package weight and dimensions
            package_details = None
            raw = item.raw_listing_json or {}
            if 'ShippingPackageDetails' in raw:
                pkg = raw['ShippingPackageDetails']
                if isinstance(pkg, list): pkg = pkg[0]
                
                package_details = {}
                
                # Helper to get nested value (handles 'Value', 'value', '#text', etc.)
                def get_val(obj):
                    if not obj: return 0
                    if isinstance(obj, (int, float, str)): return obj
                    for k in ['value', 'Value', '#text']:
                        if k in obj: return obj[k]
                    return 0

                # Weight - Try multiple common keys
                w_major = pkg.get('WeightMajor') or pkg.get('weightMajor')
                w_minor = pkg.get('WeightMinor') or pkg.get('weightMinor')
                
                if w_major is not None:
                    lbs = float(get_val(w_major))
                    oz = float(get_val(w_minor)) if w_minor else 0
                    total_lbs = lbs + (oz / 16.0)
                    if total_lbs > 0:
                        package_details["weight"] = {
                            "value": round(total_lbs, 2),
                            "unit": "POUND"
                        }
                
                # Package Type mapping (Trading API -> Inventory API Enum)
                # Ref: https://developer.ebay.com/api-docs/sell/inventory/types/slr:PackageTypeEnum
                pkg_type_map = {
                    'PackageThickEnvelope': 'PACKAGE_THICK_ENVELOPE',
                    'Letter': 'LETTER',
                    'MailingBox': 'MAILING_BOX',
                    'LargePackage': 'VERY_LARGE_PACK',
                    'ExtraLargePackage': 'VERY_LARGE_PACK',
                    'SmallCanadaPostBox': 'MAILING_BOX',
                    'SmallCanadaPostBubbleMailer': 'PARCEL_OR_PADDED_ENVELOPE'
                }
                src_pkg_type = pkg.get('ShippingPackage') or pkg.get('shippingPackage')
                package_details["packageType"] = pkg_type_map.get(src_pkg_type, 'MAILING_BOX')

                # Dimensions - Try multiple common keys
                d_h = pkg.get('PackageDepth') or pkg.get('packageDepth')
                d_l = pkg.get('PackageLength') or pkg.get('packageLength')
                d_w = pkg.get('PackageWidth') or pkg.get('packageWidth')
                
                if all(v is not None for v in [d_h, d_l, d_w]):
                    try:
                        package_details["dimensions"] = {
                            "height": float(get_val(d_h)),
                            "length": float(get_val(d_l)),
                            "width": float(get_val(d_w)),
                            "unit": "INCH"
                        }
                    except:
                        pass
                
                # Final check - provide default dimensions if missing but weight exists
                # Calculated shipping often REQUIRES dimensions.
                if package_details and "weight" in package_details and "dimensions" not in package_details:
                    # Logic for Media Mail: 11x7x1
                    # Logic for Others: 6x4x1
                    is_media = False
                    ship_ops = raw.get('ShippingDetails', {}).get('ShippingServiceOptions', [])
                    if isinstance(ship_ops, dict): ship_ops = [ship_ops]
                    for opt in ship_ops:
                        service = opt.get('ShippingService', '')
                        if 'Media' in service or 'MediaMail' in service:
                            is_media = True
                            break
                    
                    if is_media:
                        if idx == 0: print("  DEBUG: Detected USPS Media Mail, using 11x7x1 fallback")
                        package_details["dimensions"] = {
                            "height": 1,
                            "length": 11,
                            "width": 7,
                            "unit": "INCH"
                        }
                    else:
                        if idx == 0: print("  DEBUG: Non-Media Mail, using 6x4x1 fallback")
                        package_details["dimensions"] = {
                            "height": 1,
                            "length": 6,
                            "width": 4,
                            "unit": "INCH"
                        }
                
                if not package_details:
                    package_details = None
                else:
                    if idx == 0: print(f"  DEBUG: Final package details: {package_details}")

            item_payload = {
                "product": {
                    "title": item.title,
                    "description": item.description,
                    "aspects": aspects,
                    "imageUrls": img_urls
                },
                "condition": target_condition,
                "conditionDescription": item.condition_description,
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": item.quantity
                    }
                }
            }
            
            # --- ADD PRODUCT IDENTIFIERS (ISBN, UPC, EAN) ---
            if item.product_identifiers_json:
                p_ids = item.product_identifiers_json
                if 'ISBN' in p_ids:
                    item_payload["product"]["isbn"] = [p_ids['ISBN']]
                if 'UPC' in p_ids:
                    item_payload["product"]["upc"] = [p_ids['UPC']]
                if 'EAN' in p_ids:
                    item_payload["product"]["ean"] = [p_ids['EAN']]
                if 'Brand' in p_ids:
                    item_payload["product"]["brand"] = p_ids['Brand']
                if 'MPN' in p_ids:
                    item_payload["product"]["mpn"] = p_ids['MPN']
            
            if package_details:
                item_payload["packageWeightAndSize"] = package_details
                 
            # SKU usually needs to be URL encoded in path, but usually safe if simple
            sku = item.sku
            url = f"{INVENTORY_API_URL}/inventory_item/{sku}"
            
            # DEBUG: Print the payload for first item
            if idx == 0:
                import json
                print("\n=== DEBUG: Inventory Item Payload ===")
                print(json.dumps(item_payload, indent=2, default=str))
                print("=== END DEBUG ===\n")
            
            resp = requests.put(url, headers=headers, json=item_payload)
            if resp.status_code not in [200, 204]:
                print(f"Failed to create/update inventory item {sku}: {resp.text}")
                item.migration_error = f"Item Create: {resp.status_code} {resp.text}"
                db.commit()
                print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
                return
            elif idx == 0:
                print(f"  Inventory item {sku} updated successfully (Status: {resp.status_code})")

                
            # --- STEP 2: CREATE OFFER ---
            
            # Prepare Policy Block
            listing_policies = {
                "fulfillmentPolicyId": ship_id,
                "paymentPolicyId": pay_id,
                "returnPolicyId": ret_id
            }
            
            # Add Best Offer if enabled in source
            if item.best_offer_json:
                bo_data = item.best_offer_json
                # Check if explicitly enabled (string 'true' or boolean True)
                is_enabled = str(bo_data.get('BestOfferEnabled', '')).lower() == 'true'
                
                if is_enabled:
                    listing_policies["bestOfferTerms"] = {
                        "bestOfferEnabled": True
                    }
                    # We could map AutoAccept/AutoDecline here if needed, 
                    # but simple enablement is the most critical part.

            offer_payload = {
                "sku": sku,
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "availableQuantity": item.quantity, 
                "categoryId": item.category_id,
                "listingPolicies": listing_policies,
                "pricingSummary": {
                    "price": {
                        "value": item.price,
                        "currency": item.currency or "USD"
                    }
                },
                "merchantLocationKey": "default", # Created via setup_location.py
                "countryCode": "US"  # Required for publishing
            }
            
            offer_id = None
            
            # Check if we already have an offer_id from a previous run
            if item.new_offer_id:
                offer_id = item.new_offer_id
                print(f"Using existing offerId from DB: {offer_id}")
            else:
                # Try to create NEW offer
                url = f"{INVENTORY_API_URL}/offer"
                resp = requests.post(url, headers=headers, json=offer_payload)
                
                if resp.status_code in [200, 201]:
                    offer_id = resp.json().get('offerId')
                elif resp.status_code == 409 or "already exists" in resp.text.lower():
                    # Offer already exists - extract the existing offerId from error response
                    try:
                        error_data = resp.json()
                        for error in error_data.get('errors', []):
                            for param in error.get('parameters', []):
                                if param.get('name') == 'offerId':
                                    offer_id = param.get('value')
                                    print(f"Offer already exists for {sku}, using existing offerId: {offer_id}")
                                    break
                    except:
                        pass

            if not offer_id:
                print(f"Failed to create/resolve offer for {sku}: {resp.text}")
                item.migration_error = f"Offer Create: {resp.status_code} {resp.text}"
                db.commit()
                print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
                return

            # --- ALWAYS UPDATE OFFER ---
            # This ensures that even if an offer existed, we send the LATEST data (fixed aspects, etc.)
            print(f"Updating offer {offer_id} with latest data...")
            update_url = f"{INVENTORY_API_URL}/offer/{offer_id}"
            resp = requests.put(update_url, headers=headers, json=offer_payload)
            if resp.status_code not in [200, 204]:
                print(f"Failed to update offer {offer_id}: {resp.text}")
                item.migration_error = f"Offer Update: {resp.status_code} {resp.text}"
                db.commit()
                print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
                return
                 
            item.new_offer_id = offer_id
            
            # --- STEP 3: PUBLISH OFFER ---
            if offer_id:
                url = f"{INVENTORY_API_URL}/offer/{offer_id}/publish"
                resp = requests.post(url, headers=headers)
                
                if resp.status_code == 200:
                    print(f"SUCCESS: Published {sku} (Offer: {offer_id})")
                    item.migrated = True
                    item.migration_error = None
                else:
                    print(f"Failed to publish {sku}: {resp.text}")
                    item.migration_error = f"Publish: {resp.status_code} {resp.text}"
                    db.commit()
                    print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
                    return

            
            db.commit()
            
            print(f"✓ Published {item.sku}. ({idx+1}/{limit})")

        except Exception as e:
            print(f"Exception processing {item.sku}: {e}")
            item.migration_error = str(e)
            db.commit()
            print("⚠️ Stopping batch due to error. Fix the issue and re-run.")
            return


