from sqlalchemy.orm import Session
from ebay_migration.db import init_db, Listing
import json
import os

def get_val(obj):
    if not obj: return 0
    if isinstance(obj, (int, float, str)): return obj
    for k in ['value', 'Value', '#text']:
        if k in obj: return obj[k]
    return 0

engine = init_db()
db = Session(engine)

item = db.query(Listing).filter_by(sku='YOUR_SKU_HERE').first()
raw = item.raw_listing_json
pkg = raw['ShippingPackageDetails']
if isinstance(pkg, list): pkg = pkg[0]

package_details = {}
w_major = pkg.get('WeightMajor') or pkg.get('weightMajor')
w_minor = pkg.get('WeightMinor') or pkg.get('weightMinor')

print(f"w_major: {w_major}")
print(f"w_minor: {w_minor}")

if w_major is not None:
    lbs = float(get_val(w_major))
    oz = float(get_val(w_minor)) if w_minor else 0
    total_lbs = lbs + (oz / 16.0)
    print(f"Calculated weight: {total_lbs} lbs")
    if total_lbs > 0:
        package_details["weight"] = {
            "value": round(total_lbs, 2),
            "unit": "POUND"
        }

print("Final package_details:")
print(json.dumps(package_details, indent=2))
