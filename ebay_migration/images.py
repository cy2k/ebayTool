import os
import requests
from sqlalchemy.orm import Session, sessionmaker
from db import init_db, Listing, ListingImage
import concurrent.futures
import re

IMAGE_DIR = "data/images"

# Create a scoped session factory for thread safety
SessionLocal = sessionmaker(bind=init_db())

def download_single_image(img_id):
    """
    Worker function to download a single image.
    Uses its own DB session to be thread-safe.
    """
    db = SessionLocal()
    try:
        img = db.query(ListingImage).get(img_id)
        if not img:
            return f"Skipped (Img ID {img_id} not found)"
            
        listing = db.query(Listing).get(img.listing_id)
        if not listing:
            return f"Skipped (Listing ID {img.listing_id} not found)"
            
        sku_safe = "".join([c for c in listing.sku if c.isalnum() or c in ('-','_')])
        
        # Create folder for this listing
        save_dir = os.path.join(IMAGE_DIR, sku_safe)
        os.makedirs(save_dir, exist_ok=True)
        
        # Filename: rank.jpg (or original extension)
        ext = 'jpg'
        if '.' in img.original_url:
            ext = img.original_url.split('.')[-1].split('?')[0]
            
        filename = f"{img.rank}.{ext}"
        local_path = os.path.join(save_dir, filename)
        
        # HACK: Force High Resolution (s-l1600 or $_57)
        download_url = img.original_url
        if "i.ebayimg.com" in download_url:
            # Modern format: s-l300 -> s-l1600
            if re.search(r's-l\d+', download_url):
                download_url = re.sub(r's-l\d+', 's-l1600', download_url)
            # Legacy format: $_1.JPG -> $_57.JPG (Standard High Res)
            elif re.search(r'\$_\d+\.(JPG|jpg|PNG|png)', download_url):
                 download_url = re.sub(r'\$_\d+', '$_57', download_url)
                
        r = requests.get(download_url, stream=True)
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            
            # Update DB
            img.local_path = local_path
            db.commit()
            return f"Success: {local_path}"
        else:
            return f"Failed {r.status_code}: {download_url}"

    except Exception as e:
        return f"Error {img_id}: {str(e)}"
    finally:
        db.close()

def download_images(db: Session):
    # Get all images that haven't been downloaded yet
    # We just need IDs here to pass to workers
    images = db.query(ListingImage).filter(ListingImage.local_path == None).all()
    img_ids = [img.id for img in images]
    
    total = len(img_ids)
    if total == 0:
        print("No images to download.")
        return
        
    print(f"Found {total} images. Starting download with 8 threads...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_single_image, iid): iid for iid in img_ids}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            result = future.result()
            print(f"[{completed}/{total}] {result}")
