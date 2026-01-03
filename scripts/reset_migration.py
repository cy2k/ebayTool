from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing

def reset_migration_flags():
    engine = init_db()
    db = Session(engine)
    
    print("--- RESET MIGRATION FLAGS ---")
    print("This allows you to RE-RUN the publish step for items that were already marked as 'Done'.")
    print("Options:")
    print("1. Reset a SINGLE SKU")
    print("2. Reset ALL items (Start fresh)")
    
    choice = input("Select option (1/2): ")
    
    if choice == '1':
        sku = input("Enter SKU to reset: ")
        item = db.query(Listing).filter_by(sku=sku).first()
        if item:
            item.migrated = False
            item.migration_error = None
            item.new_offer_id = None
            db.commit()
            print(f"Successfully reset SKU: {sku}")
        else:
            print("SKU not found.")
            
    elif choice == '2':
        confirm = input("Are you sure you want to reset ALL 2125 items? (y/n): ")
        if confirm.lower() == 'y':
            count = db.query(Listing).update({
                Listing.migrated: False, 
                Listing.migration_error: None,
                Listing.new_offer_id: None
            })
            db.commit()
            print(f"Reset {count} items. You can now run Step 5 again for everything.")
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    reset_migration_flags()
