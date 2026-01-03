from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from sqlalchemy.orm import Session
from db import init_db, Listing, ListingImage
import datetime
import os

def create_trading_api(oauth_token):
    """Create a Trading API connection."""
    return Trading(
        appid=os.getenv("EBAY_APP_ID"), 
        certid=os.getenv("EBAY_CERT_ID"),
        devid=os.getenv("EBAY_DEV_ID"),
        config_file=None,
        iaf_token=oauth_token,
        siteid='0' # US
    )

def fetch_item_details(api, item_id):
    """
    Fetch full item details including ItemSpecifics using GetItem API.
    GetSellerList doesn't return ItemSpecifics reliably, so we need this.
    """
    try:
        response = api.execute('GetItem', {
            'ItemID': item_id,
            'DetailLevel': 'ReturnAll',
            'IncludeItemSpecifics': 'true'
        })
        return response.dict().get('Item', {})
    except ConnectionError as e:
        print(f"  Error fetching item {item_id}: {e}")
        return None

def fetch_active_listings(ioauth_token):
    """
    Fetch all active listings using Trading API GetSellerList.
    Using OAuth token (iaf_token).
    """
    api = create_trading_api(ioauth_token)

    # Time window for GetSellerList: Active items.
    # Standard trick: EndTimeFrom = Now, EndTimeTo = Now + 120 days
    now = datetime.datetime.utcnow()
    end_time_from = now
    end_time_to = now + datetime.timedelta(days=120)

    try:
        # Page 1 (assuming < 200 items as user said 181)
        # GranularityLevel=Coarse or DetailLevel=ReturnAll? 
        # ReturnAll is needed for Description and Specifics.
        response = api.execute('GetSellerList', {
            'DetailLevel': 'ReturnAll',
            'IncludeItemSpecifics': 'true',  # CRITICAL: Include Book Title, Author, etc.
            'EndTimeFrom': end_time_from.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'EndTimeTo': end_time_to.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'Pagination': {
                'EntriesPerPage': 200,
                'PageNumber': 1
            }
        })
        
        # Return both the response and the API object for individual item fetches
        return response.dict(), api

    except ConnectionError as e:
        print(f"Trading API Error: {e}")
        print(f"Response: {e.response.dict() if e.response else 'None'}")
        return None, None

def parse_and_save_listings(db: Session, api_response, api=None):
    """
    Parse listings and save to DB.
    If api is provided, fetches full item details via GetItem for each listing
    to get complete ItemSpecifics (GetSellerList doesn't return them reliably).
    """
    if not api_response or 'ItemArray' not in api_response or 'Item' not in api_response['ItemArray']:
        print("No items found in response.")
        return

    items = api_response['ItemArray']['Item']
    if not isinstance(items, list):
        items = [items] # Handle single item case

    print(f"Processing {len(items)} items...")
    
    # If we have API access, fetch full details for each item
    use_getitem = api is not None
    if use_getitem:
        print(f"(Fetching full item details for {len(items)} items including ItemSpecifics...)")

    for idx, item in enumerate(items):
        item_id = item.get('ItemID')
        
        # If API available, get FULL item details via GetItem
        if use_getitem:
            if (idx + 1) % 10 == 0 or idx == 0:
                print(f"  Fetching full details: {idx+1}/{len(items)}...")
            full_item = fetch_item_details(api, item_id)
            if full_item:
                item = full_item  # Replace with full data
                
        # Extract basic fields
        item_id = item.get('ItemID')
        sku = item.get('SKU', f"NOSKU_{item_id}") # Fallback if no SKU
        title = item.get('Title')
        subtitle = item.get('SubTitle')
        description = item.get('Description')
        price = item.get('SellingStatus', {}).get('CurrentPrice', {}).get('value')
        qty = int(item.get('Quantity', 0)) - int(item.get('SellingStatus', {}).get('QuantitySold', 0))
        cat_id = item.get('PrimaryCategory', {}).get('CategoryID')
        
        # Policy IDs
        seller_profiles = item.get('SellerProfiles', {})
        pay_id = seller_profiles.get('SellerPaymentProfile', {}).get('PaymentProfileID')
        ship_id = seller_profiles.get('SellerShippingProfile', {}).get('ShippingProfileID')
        ret_id = seller_profiles.get('SellerReturnProfile', {}).get('ReturnProfileID')

        # Condition
        cond_id = item.get('ConditionID', '1000') 
        cond_desc = item.get('ConditionDescription')

        # Item Specifics - SAVE AS LISTS (Inventory API REST format)
        specifics = {}
        if 'ItemSpecifics' in item and 'NameValueList' in item['ItemSpecifics']:
             nv_list = item['ItemSpecifics']['NameValueList']
             if not isinstance(nv_list, list): nv_list = [nv_list]
             for nv in nv_list:
                 name = nv.get('Name')
                 val = nv.get('Value')
                 if not isinstance(val, list): val = [val]
                 specifics[name] = val
                 
        # Deep Dive: Product Identifiers (UPC, EAN, ISBN)
        product_ids = {}
        prod_listing_details = item.get('ProductListingDetails', {})
        for key in ['UPC', 'EAN', 'ISBN', 'BrandMPN']:
            if prod_listing_details.get(key):
                product_ids[key] = prod_listing_details.get(key)
                
        # Deep Dive: Variations
        variations_data = None
        if 'Variations' in item:
            variations_data = item.get('Variations')
            
        # Deep Dive: Best Offer
        best_offer_data = item.get('BestOfferDetails')

        # Check existence - UPDATE if exists, INSERT if new
        existing = db.query(Listing).filter_by(item_id=item_id).first()
        if existing:
            # UPDATE existing record with new data (especially item_specifics_json)
            existing.item_specifics_json = specifics
            existing.product_identifiers_json = product_ids
            existing.variations_json = variations_data
            existing.best_offer_json = best_offer_data
            existing.raw_listing_json = item
            # Update other fields that might have changed
            existing.title = title
            existing.description = description
            existing.quantity = qty
            existing.price = price
            existing.condition_id = cond_id
            existing.condition_description = cond_desc
            listing = existing
            print(f"  Updated: {sku}")
        else:
            listing = Listing(
                item_id=item_id,
                sku=sku,
                title=title,
                subtitle=subtitle,
                description=description,
                quantity=qty,
                price=price,
                category_id=cat_id,
                payment_policy_id=pay_id,
                shipping_policy_id=ship_id,
                return_policy_id=ret_id,
                condition_id=cond_id,
                condition_description=cond_desc,
                item_specifics_json=specifics,
                product_identifiers_json=product_ids,
                variations_json=variations_data,
                best_offer_json=best_offer_data,
                raw_listing_json=item # Full safety net
            )
            db.add(listing)
            db.flush() # Get ID
            print(f"  New: {sku}")
            
            # Images
            pic_details = item.get('PictureDetails', {})
            urls = pic_details.get('PictureURL', [])
            if isinstance(urls, str): urls = [urls]
            
            for idx, url in enumerate(urls):
                img = ListingImage(
                    listing_id=listing.id,
                    original_url=url,
                    rank=idx
                )
                db.add(img)

    db.commit()
    print("Listings saved to DB.")
