# Developer Tools

This directory contains scripts used for debugging, deep inspection, and verifying data fidelity during the development of the migration tool. These are not required for standard usage but are helpful for troubleshooting.

## Verification & Inspection
- **`check_aspect_rules.py`**: Queries eBay Taxonomy API to check rules (cardinality, mode) for specific categories (e.g., Books).
- **`check_locations.py`**: Lists configured inventory locations on the Target account.
- **`check_target_item.py`**: Fetches the raw JSON of a specific Inventory Item from the Target account.
- **`check_topics.py`**: Scans the local database for listings with multiple "Topic" values.
- **`inspect_data.py`**: General purpose script to dump raw data for a specific listing from the DB.
- **`inspect_eps_urls.py`**: Checks if images have valid new EPS URLs assigned.
- **`verify_db_state.py`**: Quick consistency check of the database tables.

## Debugging Specific Issues
- **`debug_condition.py`**: Inspects condition IDs and descriptions for a specific SKU.
- **`debug_identifiers.py`**: Checks for product identifiers (ISBN, UPC, EAN) in the source data.
- **`debug_item.py`**: Dumps general item details.
- **`debug_topic.py`**: Specifically debugs the "Topic" aspect structure.
- **`test_weight.py`**: Tests the logic for parsing shipping package weights and dimensions.
