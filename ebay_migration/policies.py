import requests
import json
from sqlalchemy.orm import Session
from db import init_db, SourcePolicy
from auth import EbayAuth
import os

ACCOUNT_API_URL = "https://api.ebay.com/sell/account/v1"

def fetch_policies(access_token, policy_type):
    """
    Fetch all policies of a given type (fulfillment, payment, return).
    """
    url = f"{ACCOUNT_API_URL}/{policy_type}_policy"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    policies = []
    # Simplified pagination (assuming < 181 items means not too many policies, but good measure)
    # The Account API usually returns all in one go or standard pagination.
    # Default limit is typically 20 or 50. Let's ask for 100.
    # Note: real implementation needs robust loop.
    resp = requests.get(url, headers=headers, params={"limit": 100, "marketplace_id": "EBAY_US"})
    
    if resp.status_code == 200:
        data = resp.json()
        # Key naming differs: fulfillmentPolicies, paymentPolicies, returnPolicies
        key = f"{policy_type}Policies" 
        return data.get(key, [])
    else:
        print(f"Error fetching {policy_type}: {resp.text}")
        return []

def save_source_policies(db: Session, policies, policy_type):
    for p in policies:
        # ID fields differ: fulfillmentPolicyId, paymentPolicyId, etc.
        p_id = p.get(f"{policy_type}PolicyId")
        
        # Check existence
        exists = db.query(SourcePolicy).filter_by(policy_id=p_id).first()
        if not exists:
            new_policy = SourcePolicy(
                policy_type=policy_type,
                policy_id=p_id,
                name=p.get('name'),
                description=p.get('description'),
                payload_json=p
            )
            db.add(new_policy)
    db.commit()

def sanitize_payload(policy_data, policy_type):
    """Remove Read-Only fields before sending to create/update."""
    payload = policy_data.copy()
    
    # Remove System IDs & Read-Only Metadata
    keys_to_remove = [
        f"{policy_type}PolicyId", 
        # "marketplaceId", # KEEP THIS for Create
        # "categoryTypes", # KEEP THIS for Create
        "creationDate",
        "lastModifiedDate",
        "version"
    ]
    
    for k in keys_to_remove:
        payload.pop(k, None)
    
    # FIX: shipToLocations can sometimes extract as {} from source.
    # eBay rejects {} (Error 2003) and [] (Error 2004). Must remove field if empty.
    if 'shipToLocations' in payload:
        val = payload['shipToLocations']
        if isinstance(val, (dict, list)) and not val:
            payload.pop('shipToLocations')

    # FIX: Sanitize Shipping Options
    if 'shippingOptions' in payload:
        for opt in payload['shippingOptions']:
            # Remove Discount Profiles (Target likely doesn't have them, causing crash)
            opt.pop('shippingDiscountProfileId', None)
            
            # Fix Logic: If Calculated and FreeShipping=False, Buyer MUST be responsible
            if opt.get('costType') == 'CALCULATED':
                for svc in opt.get('shippingServices', []):
                    if svc.get('freeShipping') is False:
                        svc['buyerResponsibleForShipping'] = True
            
    return payload

def sync_to_target(db: Session, source_token, target_token):
    """
    Read SourcePolicies from DB.
    Check Target for name match.
    Create or Update.
    """
    policy_types = ['fulfillment', 'payment', 'return']
    
    for p_type in policy_types:
        # 1. Get existing policies on Target
        target_policies = fetch_policies(target_token, p_type)
        target_map = {tp['name']: tp for tp in target_policies} # Map Name -> Full Policy Data
        
        # 2. Iterate Source Policies in DB
        source_policies_db = db.query(SourcePolicy).filter_by(policy_type=p_type).all()
        
        batch_remaining = 0
        process_all = False

        for idx, src_pol in enumerate(source_policies_db):
            # BATCH CONTROL LOGIC
            if not process_all and batch_remaining <= 0:
                print(f"\n--- PAUSED at Policy {idx+1}/{len(source_policies_db)}: '{src_pol.name}' ---")
                while True:
                    choice = input("Enter number to process (e.g. 1, 5), 'all' for rest, or 'q' to quit: ").strip().lower()
                    if choice == 'q':
                        print("Stopping policy sync.")
                        return # Break out of function/loop
                    elif choice == 'all':
                        process_all = True
                        break
                    elif choice.isdigit() and int(choice) > 0:
                        batch_remaining = int(choice)
                        break
                    else:
                        print("Invalid input. Please enter a number, 'all', or 'q'.")
            
            # Decrement if not in 'all' mode
            if not process_all:
                batch_remaining -= 1

            # Name Collision Strategy: Append suffix to ensure we create fresh policies
            # This avoids "Internal Error" when updating legacy policies
            original_name = src_pol.name
            policy_name = f"{original_name} (Migrated)"
            
            src_pol.target_policy_name = policy_name # Store intended name if needed later
            
            src_data = src_pol.payload_json
            payload = sanitize_payload(src_data, p_type)
            payload['name'] = policy_name # Override name with (Migrated) suffix
            
            # 3. Reconciliation
            if policy_name in target_map:
                # UPDATE
                target_existing = target_map[policy_name]
                target_id = target_existing.get(f"{p_type}PolicyId")
                
                print(f"Updating {p_type} policy: {policy_name} (ID: {target_id})")
                
                # DEBUG: Print payload (remove in prod)
                print(json.dumps(payload, indent=2))
                
                url = f"{ACCOUNT_API_URL}/{p_type}_policy/{target_id}"
                resp = requests.put(url, headers={
                    "Authorization": f"Bearer {target_token}",
                    "Content-Type": "application/json"
                }, json=payload)
                
                if resp.status_code in [200, 204]:
                    src_pol.target_policy_id = target_id
                    print("Success.")
                else:
                    print(f"Failed to update {policy_name}: {resp.text}")

            else:
                # CREATE
                print(f"Creating {p_type} policy: {policy_name}")
                url = f"{ACCOUNT_API_URL}/{p_type}_policy"
                resp = requests.post(url, headers={
                    "Authorization": f"Bearer {target_token}",
                    "Content-Type": "application/json"
                }, json=payload)
                
                if resp.status_code == 201:
                    # Location header contains ID usually, or body
                    new_id = None
                    if 'location' in resp.headers:
                        new_id = resp.headers['location'].split('/')[-1]
                    elif resp.json():
                        new_id = resp.json().get(f"{p_type}PolicyId")
                        
                    src_pol.target_policy_id = new_id
                    print("Success.")
                elif resp.status_code == 409 or (resp.status_code == 400 and 'Duplicate Policy' in resp.text):
                     # Handle Duplicate Policy (Error 20400)
                     # If settings match exactly, eBay returns the existing ID.
                     try:
                         # Attempt to extract duplicatePolicyId
                         # JSON: {"errors":[{"parameters":[{"name":"duplicatePolicyId","value":"..."}]}]}
                         err_data = resp.json()
                         dup_id = None
                         for err in err_data.get('errors', []):
                             for param in err.get('parameters', []):
                                 if param.get('name') == 'duplicatePolicyId':
                                     dup_id = param.get('value')
                                     break
                         
                         if dup_id:
                             src_pol.target_policy_id = dup_id
                             print(f"Policy already exists (ID: {dup_id}). Mapped successfully.")
                         else:
                             print(f"Failed to create (Duplicate detected but no ID found): {resp.text}")
                     except Exception as e:
                         print(f"Failed to create (Error parsing duplicate response): {resp.text}")

                else:
                    print(f"Failed to create {policy_name}: {resp.text}")
                    
        db.commit()

# Main Entry (for testing)
if __name__ == "__main__":
    # This block allows standalone running if tokens are present
    pass
