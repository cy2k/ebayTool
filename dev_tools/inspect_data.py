from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing, SourcePolicy
import json

# Initialize DB
from sqlalchemy.orm import sessionmaker
engine = init_db()
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

def print_separator(title):
    print(f"\n{'='*20} {title} {'='*20}")

# 1. Inspect Listings
print_separator("DEEP DIVE: 1899 Ovid's Metamorphoses")
# The SKU was YOUR_SKU_HERE in previous output
listing = session.query(Listing).filter(Listing.sku == "YOUR_SKU_HERE").first()

if listing:
    print(f"Title:       {listing.title}")
    print(f"SKU:         {listing.sku}")
    print(f"Price:       {listing.price} {listing.currency}")
    print(f"Quantity:    {listing.quantity}")
    print(f"Condition:   {listing.condition_id} {listing.condition_description}")
    
    print("\n--- ITEM SPECIFICS ---")
    if listing.item_specifics_json:
        specs = json.loads(listing.item_specifics_json)
        for k, v in specs.items():
            print(f"  {k}: {v}")
    else:
        print("  None.")

    print("\n--- PRODUCT ID ---")
    if listing.product_identifiers_json:
        print(f"  {listing.product_identifiers_json}")
    else:
        print("  None.")

    print(f"\n--- IMAGES ({len(listing.images)}) ---")
    for img in listing.images:
        print(f"  - {img.url[:60]}...")

    print("\n--- DESCRIPTION (First 500 chars) ---")
    desc = listing.description or ""
    print(f"{desc[:500]}...")
else:
    print("Listing YOUR_SKU_HERE not found!")

# 2. Inspect Policies
print_separator("ALL SOURCE POLICIES")
types = ['fulfillment', 'payment', 'return']
for t in types:
    print(f"\n--- {t.upper()} POLICIES ---")
    policies = session.query(SourcePolicy).filter_by(policy_type=t).all()
    if policies:
        for p in policies:
            print(f"- {p.name} (ID: {p.policy_id})")
            # print(f"  Desc: {p.description}") 
    else:
        print("  None found.")
