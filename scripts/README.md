# Utility Scripts

This directory contains helpful scripts for managing your migration data and environment.

- **`reset_migration_flags.py`**: Resets the 'migrated' status of all listings in your local database to 'False'. Useful if you need to re-run the "Publish" step for all items (e.g., after a code update).
- **`setup_location.py`**: Helps configure the default inventory location for your eBay account. Run this once during setup.
- **`reset_images.py`**: Clears download flags for images, forcing a re-download/re-process on the next run.
- **`delete_offer.py`**: A utility to delete a specific offer from eBay by SKU or Offer ID. 
- **`reset_migration.py`**: A more aggressive reset script (check source before using).
