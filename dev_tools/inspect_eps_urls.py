from sqlalchemy.orm import Session
from ebay_migration.db import init_db, ListingImage

def inspect_urls():
    engine = init_db()
    db = Session(engine)
    
    # Get 10 samples that have been uploaded
    images = db.query(ListingImage).filter(ListingImage.new_eps_url != None).limit(10).all()
    
    print(f"Inspecting {len(images)} uploaded images:")
    for img in images:
        print(f"Ref: {img.new_eps_url}")

if __name__ == "__main__":
    inspect_urls()
