from sqlalchemy.orm import Session
from ebay_migration.db import init_db, ListingImage

def verify_state():
    engine = init_db()
    db = Session(engine)
    
    total = db.query(ListingImage).count()
    uploaded = db.query(ListingImage).filter(ListingImage.new_eps_url != None).count()
    to_upload = db.query(ListingImage).filter(ListingImage.new_eps_url == None).count()
    
    print(f"Total Images: {total}")
    print(f"Already Uploaded (Target URL set): {uploaded}")
    print(f"Ready to Upload (Target URL is None): {to_upload}")
    
    if uploaded == 0 and to_upload == total:
        print("\nSUCCESS: Database is clean. All images are ready for upload.")
    else:
        print("\nWARNING: Some images are already marked as uploaded!")

if __name__ == "__main__":
    verify_state()
