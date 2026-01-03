from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing

def reset_flags():
    print("Resetting 'migrated' flag for ALL listings...")
    engine = init_db()
    session = Session(engine)
    
    # Update all to False
    count = session.query(Listing).update({Listing.migrated: False})
    session.commit()
    
    print(f"Successfully reset {count} listings to pending state.")
    print("You can now run Step 5 again to re-publish and update them with the latest logic (Product Identifiers, Topic fixes, etc).")

if __name__ == "__main__":
    reset_flags()
