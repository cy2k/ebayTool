from sqlalchemy.orm import Session
from ebay_migration.db import init_db, ListingImage
import os
import shutil

def reset_image_state():
    print("--- RESETTING IMAGE STATE ---")
    
    confirm = input("This will DELETE all local images and clear upload records from the DB.\nAre you sure? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return

    engine = init_db()
    db = Session(engine)
    
    # 1. Reset Database Records
    print("Resetting DB records...")
    images = db.query(ListingImage).all()
    count = 0
    for img in images:
        img.local_path = None
        img.new_eps_url = None # This forces re-upload!
        count += 1
    
    db.commit()
    print(f"Reset {count} records in database.")
    
    # 2. Delete Local Files
    print("Deleting local files...")
    if os.path.exists("data/images"):
        shutil.rmtree("data/images")
        print("Deleted data/images directory.")
    
    # Re-create empty dir
    os.makedirs("data/images", exist_ok=True)
    
    print("\nDONE. You can now run:")
    print("1. Step 2 (Download Images) -> Will get High Res now.")
    print("2. Step 4 (Upload Images) -> Will upload the new High Res files.")

if __name__ == "__main__":
    reset_image_state()
