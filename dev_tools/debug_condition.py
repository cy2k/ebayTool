from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing

def debug_condition():
    engine = init_db()
    session = Session(engine)
    
    sku = "YOUR_SKU_HERE"
    item = session.query(Listing).filter_by(sku=sku).first()
    
    if not item:
        print(f"Item {sku} not found!")
        return

    print(f"--- Debugging {sku} ---")
    print(f"Condition ID: {item.condition_id} (Type: {type(item.condition_id)})")
    print(f"Condition Description: {item.condition_description}")

if __name__ == "__main__":
    debug_condition()
