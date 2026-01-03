# eBay Listing Migration Tool
## Background
I had to create a new eBay account for a new organization, and I had a LOT of listings in the old account that I wanted to transfer to the new account. No way was I going to do that manually, and the handful of 3rd party tools I found were either expensive or janky... so with the help of Google's new Antigravity AI coding app, I built this migration tool. I got it working over the course of a couple days, and used it to successfuly migrate almost 200 listings. I want to share the code since there really wasn't anything else like it that I could find. I hope someone else finds it useful! Feel free to reach out to me if you have any questions or need help.

## Functionality Summary
A Python-based tool for migrating eBay listings from a source account to a target account, featuring:
- **Inventory API Integration**: Uses the modern Inventory API for listings.
- **Smart Policy Mapping**: Syncs and maps Business Policies (Payment, Shipping, Return).
- **Image Migration**: Downloads images locally and re-uploads them to eBay Picture Services (EPS).
- **Batch Processing**: Supports batched publishing with stop-on-error logic.
- **Verification**: Comprehensive post-migration verification against the local database.

## Prerequisites

- Python 3.9+
- Two eBay Accounts (Source and Target)
- eBay Developer Account (App ID, Cert ID, RU Name)

## Setup

1. **Clone the repository**
2. **Create a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables**:
   Create a `.env` file in the root directory (do NOT commit this file):
   ```env
   EBAY_APP_ID=your_app_id
   EBAY_CERT_ID=your_cert_id
   EBAY_RU_NAME=your_ru_name
   ```

## Usage

Run the main dashboard:
```bash
./venv/bin/python ebay_migration/main.py
```

### Workflow Steps
1. **Extract from SOURCE**: Pulls active listings and policies into the local database.
2. **Download Images**: Saves listing images to `data/images`.
3. **Sync Policies**: Checks for matching policies on the Target account or creates placeholders.
4. **Upload Images to TARGET**: Uploads local images to the Target account's EPS hosting.
5. **Publish Listings**: Creates Inventory Items and Offers on the Target account.
6. **Verify Listings**: Compares the live listing data against the local database to ensure fidelity.

## Project Structure

- **`ebay_migration/`**: Core application code.
- **`scripts/`**: Utility scripts for maintenance (resetting data, setting up locations).
- **`dev_tools/`**: detailed inspection and debugging scripts.

## Important Notes on API Limits
- **Aspects**: The tool handles multi-value aspects (e.g., "Topic", "Language") by joining them with commas if the Inventory API rejects array values for specific categories.
- **Rate Limits**: The tool processes items sequentially to be respectful of API limits.

## License
GNU GPLv3 License
