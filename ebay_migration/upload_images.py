from ebaysdk.trading import Connection as Trading
from sqlalchemy.orm import Session, sessionmaker
from db import ListingImage, init_db
import os
import concurrent.futures
from functools import partial

# Create a scoped session factory for thread safety
SessionLocal = sessionmaker(bind=init_db())

def upload_single_image(img_id, oauth_token):
    """
    Worker function to upload a single image.
    Uses its own DB session to be thread-safe.
    """
    db = SessionLocal()
    try:
        img = db.query(ListingImage).get(img_id)
        if not img or not img.local_path or not os.path.exists(img.local_path):
            return f"Skipped (Missing): {img.local_path if img else 'Unknown'}"

        api = Trading(
            appid=os.getenv("EBAY_APP_ID"), 
            certid=os.getenv("EBAY_CERT_ID"),
            devid=os.getenv("EBAY_DEV_ID"),
            iaf_token=oauth_token,
            siteid='0',
            timeout=60,
            config_file=None
        )
        
        files = {'file': (img.local_path, open(img.local_path, 'rb'))}
        
        # API Call: UploadSiteHostedPictures
        response = api.execute('UploadSiteHostedPictures', { 
            'ExtensionInDays': 30,
        }, files=files)
        
        resp_dict = response.dict()
        full_url = resp_dict.get('SiteHostedPictureDetails', {}).get('FullURL')
        
        if full_url:
            img.new_eps_url = full_url
            db.commit()
            return f"Success: {img.local_path} -> {full_url}"
        else:
            return f"Failed (No URL): {img.local_path}"

    except Exception as e:
        return f"Error {img_id}: {str(e)}"
    finally:
        db.close()

def upload_to_eps(db: Session, oauth_token):
    """
    Uploads images in parallel using ThreadPoolExecutor.
    """
    # 1. Gather all IDs to process
    images_to_upload = db.query(ListingImage).filter(
        ListingImage.local_path != None,
        ListingImage.new_eps_url == None
    ).all()
    
    img_ids = [img.id for img in images_to_upload]
    total = len(img_ids)
    
    if total == 0:
        print("No images to upload.")
        return

    print(f"Found {total} images. Starting upload with 4 threads...")
    
    # 2. Parallel Execution
    # We pass IDs instead of objects to avoid DB session threading issues
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Create a partial function with the token fixed
        worker = partial(upload_single_image, oauth_token=oauth_token)
        
        # Submit all tasks
        futures = {executor.submit(worker, iid): iid for iid in img_ids}
        
        # Process results as they complete
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            result = future.result()
            print(f"[{completed}/{total}] {result}")


