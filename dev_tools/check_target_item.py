import requests
import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)

# Helper to get target token (simulated for this quick check)
from ebay_migration.main import get_validated_token
from sqlalchemy.orm import Session
from ebay_migration.db import init_db

engine = init_db()
db = Session(engine)
token = get_validated_token('target')

sku = 'YOUR_SKU_HERE'
url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

resp = requests.get(url, headers=headers)
if resp.status_code == 200:
    print(f"Target Item Data for {sku}:")
    print(json.dumps(resp.json(), indent=2))
else:
    print(f"Error fetching item: {resp.status_code} - {resp.text}")
