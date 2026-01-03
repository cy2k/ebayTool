from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing
import json

def debug_identifiers():
    engine = init_db()
    session = Session(engine)
    
    sku = "YOUR_SKU_HERE"
    item = session.query(Listing).filter_by(sku=sku).first()
    
    if not item:
        print(f"Item {sku} not found!")
        return

    print(f"--- Debugging Identifiers for {sku} ---")
    print(f"Product Identifiers JSON: {item.product_identifiers_json}")
    
    # Also check aspects as sometimes they hide there
    aspects = item.item_specifics_json or {}
    print(f"ISBN in aspects? {aspects.get('ISBN')}")
    print(f"UPC in aspects? {aspects.get('UPC')}")
    print(f"EAN in aspects? {aspects.get('EAN')}")

if __name__ == "__main__":
    debug_identifiers()
