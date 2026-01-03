from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing
import json

def debug_item():
    engine = init_db()
    session = Session(engine)
    
    # The user said the item failed is YOUR_SKU_HERE
    sku = "YOUR_SKU_HERE"
    
    item = session.query(Listing).filter_by(sku=sku).first()
    
    if not item:
        print(f"Item {sku} not found in DB!")
        return

    print(f"--- Debugging {sku} ---")
    raw = item.raw_listing_json or {}
    
    pkg = raw.get('ShippingPackageDetails')
    print(f"ShippingPackageDetails: {json.dumps(pkg, indent=2)}")
    
    shipping = raw.get('ShippingDetails', {})
    print(f"ShippingDetails: {json.dumps(shipping, indent=2)}")

if __name__ == "__main__":
    debug_item()
