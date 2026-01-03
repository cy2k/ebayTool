from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class SourcePolicy(Base):
    __tablename__ = 'source_policies'
    
    id = Column(Integer, primary_key=True)
    policy_type = Column(String(50))  # PAYMENT, FULFILLMENT, RETURN
    policy_id = Column(String(100), unique=True)
    name = Column(String(255))
    description = Column(Text, nullable=True)
    payload_json = Column(JSON)  # Full raw data to send to target
    target_policy_id = Column(String(100), nullable=True) # Mapped ID on target account

class Listing(Base):
    __tablename__ = 'listings'
    
    id = Column(Integer, primary_key=True)
    item_id = Column(String(50), unique=True) # Source Item ID
    sku = Column(String(100), nullable=True)
    title = Column(String(255))
    subtitle = Column(String(255), nullable=True) # Added
    description = Column(Text)
    quantity = Column(Integer)
    price = Column(String(20))
    currency = Column(String(10))
    category_id = Column(String(50))
    
    # Store policy IDs used by this listing (Source IDs)
    payment_policy_id = Column(String(100))
    return_policy_id = Column(String(100))
    shipping_policy_id = Column(String(100))
    
    item_specifics_json = Column(JSON) # Brand, MPN, Size, etc.
    product_identifiers_json = Column(JSON) # UPC, EAN, ISBN
    variations_json = Column(JSON) # For multi-variation listings
    best_offer_json = Column(JSON) # Best Offer settings
    
    # Condition
    condition_id = Column(String(10))
    condition_description = Column(Text, nullable=True)
    
    # Safety Net
    raw_listing_json = Column(JSON) # Full API response dump

    # Validation flags
    migrated = Column(Boolean, default=False)
    migration_error = Column(Text, nullable=True)
    new_offer_id = Column(String(100), nullable=True)

class ListingImage(Base):
    __tablename__ = 'listing_images'
    
    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id'))
    original_url = Column(Text)
    local_path = Column(Text) # Path to downloaded file
    new_eps_url = Column(Text, nullable=True) # URL on Target Account (eBay Picture Services)
    rank = Column(Integer) # Display order

    listing = relationship("Listing", backref="images")

def init_db(db_path='sqlite:///ebay_migration.db'):
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
