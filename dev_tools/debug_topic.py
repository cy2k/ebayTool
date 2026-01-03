from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing
import json

def debug_topic():
    engine = init_db()
    session = Session(engine)
    
    sku = "YOUR_SKU_HERE"
    item = session.query(Listing).filter_by(sku=sku).first()
    
    if not item:
        print(f"Item {sku} not found!")
        return

    print(f"--- Debugging {sku} ---")
    print(f"Source Item ID: {item.item_id}")
    if item.item_id:
        print(f"Source URL: https://www.ebay.com/itm/{item.item_id}")
    
    print(f"Title: {item.title}")

if __name__ == "__main__":
    debug_topic()
