# Scheduled Supplier Sync

This command is used to refresh supplier product data from a CSV file.

## Dry Run

```bash
python manage.py sync_suppliers --dry-run

then:

## Real Sync.
`python manage.py sync_suppliers --file data/my_supplier_products.csv`

Or:
## Render Cron Example
`python manage.py sync_suppliers --file data/my_supplier_products.csv`