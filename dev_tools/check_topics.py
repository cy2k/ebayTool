from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing
import json

def check_remaining_topics():
    engine = init_db()
    session = Session(engine)
    
    # Get all unmigrated listings
    pending_listings = session.query(Listing).filter(Listing.migrated == False).all()
    
    print(f"Scanning {len(pending_listings)} pending listings for multiple 'Topic' values...")
    
    count = 0
    examples = []
    
    for item in pending_listings:
        aspects = item.item_specifics_json or {}
        
        # Check Topic
        if 'Topic' in aspects and isinstance(aspects['Topic'], list):
            if len(aspects['Topic']) > 1:
                count += 1
                if len(examples) < 5:
                    examples.append(f"{item.sku}: {aspects['Topic']}")

    print(f"\nFound {count} pending listings with multiple Topics.")
    if count > 0:
        print("First 5 examples:")
        for ex in examples:
            print(f" - {ex}")

if __name__ == "__main__":
    check_remaining_topics()
