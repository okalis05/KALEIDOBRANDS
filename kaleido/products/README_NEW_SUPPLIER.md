# KaleidoBrands — New Supplier Catalog Integration Guide

**Purpose:** Onboard a new promotional-products supplier into the existing KaleidoBrands Django marketplace without disrupting existing catalogs, pricing, orders, supplier synchronization, or production data.

**Repository:** `KALEIDOBRANDS`  
**Django project directory:** `kaleido/`  
**Known runtime:** Django 4.2.26, Python in the project's `dev` Conda environment  
**Deployment:** Render; scheduled supplier synchronization already exists.

> **Important:** This guide combines confirmed KaleidoBrands project conventions with implementation checklists. Exact model fields, management-command flags, and integration-module names **must be verified in the current repository** before using or extending them. Examples marked *illustrative* are not commands guaranteed to exist.

## 1. Non-negotiable safety rules

- **Extend, never replace** the existing supplier, catalog, product, variant, pricing, inventory, quote, purchase-order, or synchronization systems.
- **Never delete or truncate** existing catalog records to onboard a supplier.
- Use **additive, data-preserving migrations**; review generated migrations before applying them.
- Keep every new supplier's identifiers **namespaced by supplier**. Do not assume an SKU is globally unique.
- Use **idempotent upserts**, not blind inserts, so repeated imports do not duplicate records.
- Do not overwrite hand-curated product fields or prices unless the existing system explicitly owns those fields as supplier-managed.
- Treat a supplier's disappearance from a partial API response as **unknown**, not as proof that the product was discontinued.
- Never print, commit, or paste live API secrets into logs or source files.
- Work in small, testable packages; do not change unrelated applications or the live synchronization schedule during onboarding.

## 2. Establish a baseline and create a focused branch

From the local repository:

```bash
cd /Users/francoiseelismbazoaokala/Documents/KALEIDOBRANDS/kaleido
conda activate dev
python manage.py check
git status --short
git branch --show-current
python manage.py help
```

Review uncommitted work before switching branches. Do not use `git add .`, `git reset --hard`, or any cleanup that could remove ongoing changes. When safe, create a focused branch from the current intended base:

```bash
git switch -c supplier/<supplier-slug>-integration
```

Record a baseline of existing supplier counts, product counts, variant counts, and last-successful-sync times using the **actual model names and relations in the repository**. Capture a production database backup or confirm an available restore point before any production migration or large import.

## 3. Inspect the current integration architecture

Locate the canonical supplier, product, variant, image, pricing, inventory, and sync models and commands:

```bash
find . -path '*/migrations/*' -prune -o -type f \( -name 'models.py' -o -name 'services.py' -o -name '*supplier*.py' -o -name '*sync*.py' \) -print
find . -path '*/management/commands/*.py' -type f -print
rg -n 'class (Supplier|SupplierCatalog|Product|ProductImage)|sync_all_suppliers|weekly-batch|family-batch-size|generic-batch-size' . --glob '*.py'
python manage.py help sync_all_suppliers
```

If `rg` is not installed, use `grep -R` instead. Inspect existing adapters and shared services **before** creating new models or utilities. Reuse the established supplier catalog mapping, product family/variant relationships, image storage, import checkpoints, logging, and pricing policies.

### Architecture questions to answer

| Area | Confirm in the actual code |
|---|---|
| Supplier identity | Model, slug, active flag, external identifier, website, credentials reference |
| Catalog | SupplierCatalog linkage, catalog version, source URL, last import |
| Products | Parent/family model, supplier foreign key, unique source identifiers |
| Variants | SKU, color, size, imprint method, minimum quantity, packaging |
| Prices | Cost vs. selling price, quantity breaks, setup charges, currency |
| Inventory | Availability, stock status, backorder, update timestamps |
| Images | Image URL, local/media storage, primary image, duplicates |
| Sync state | Cursor/page, last success, failures, retry state, timestamps |
| Visibility | Publish flags, supplier enablement, product eligibility |
| Orders | Quote and purchase-order references that must remain stable |

**Decision gate:** If an existing model or service already supports a concept, use it. Add fields only if the new supplier requires genuinely new information.

## 4. Collect the supplier's technical requirements

Obtain the supplier's official integration documentation and confirm:

1. Supplier legal/display name, slug, primary website, support contact, and integration owner.
2. API base URL and version, authentication type, credential rotation procedure, and test/sandbox environment.
3. Product data source: REST/JSON, XML, CSV/SFTP, PromoStandards endpoints, or another documented interface.
4. Product and variant identifiers, parent-child relationships, and change timestamps.
5. Categories, attributes, descriptions, brand restrictions, product availability, and discontinued statuses.
6. Image endpoints and image-use permissions.
7. Cost/price files, quantity tiers, setup fees, decoration charges, and minimum order quantities.
8. Inventory endpoints, stock update frequency, rate limits, pagination, and expected catalog size.
9. Data refresh cadence, API quotas, timeout/retry rules, and incremental sync capabilities.
10. Terms governing storage, display, redistribution, and caching of supplier data.

Create an internal supplier configuration record; store credentials in environment variables or the existing secret-management system. Example variable names (illustrative only):

```text
SUPPLIER_<SLUG>_API_BASE_URL=
SUPPLIER_<SLUG>_API_KEY=
SUPPLIER_<SLUG>_API_USERNAME=
SUPPLIER_<SLUG>_API_PASSWORD=
```

Use only the variables required by the supplier's real authentication scheme. Add secret names to deployment configuration, **not** secret values to Git.

## 5. Register the supplier safely

- Reuse the existing Supplier model and supplier registration mechanism.
- Normalize the slug consistently (for example, `example-supplier`).
- Set new suppliers to **inactive or unpublished** until validation passes, if supported by the existing model.
- Link the appropriate SupplierCatalog record, using existing constraints and foreign keys.
- Do not change existing supplier records, IDs, or display order.
- Keep showcase logo onboarding separate from catalog ingestion; a missing logo must not block a catalog import.

**Uniqueness:** Verify how the database enforces supplier + external product ID and supplier + variant ID. A supplier-specific ID must not collide with another supplier's ID.

## 6. Implement or configure a supplier adapter

Follow the established supplier integration pattern. A new adapter should, as applicable:

- Authenticate securely and handle credential expiration.
- Fetch catalog pages or files with bounded request timeouts.
- Respect rate limits and `Retry-After` responses.
- Retry transient failures with exponential backoff and jitter; do not endlessly retry invalid credentials.
- Support pagination and **resume/checkpoint** behavior for large imports.
- Parse source data into the **existing normalized product schema**.
- Separate **fetch**, **normalize**, **validate**, and **persist** stages for testability.
- Record source identifiers, update timestamps, and provenance.
- Produce structured counters: fetched, created, updated, unchanged, skipped, failed.
- Fail safely on malformed payloads; never erase valid records because one page fails.

### Recommended normalized product contract (illustrative)

```python
{
    "supplier_slug": "example-supplier",
    "external_product_id": "EX-100",
    "parent_sku": "EX-100",
    "name": "Example Promotional Product",
    "description": "...",
    "category": "...",
    "variants": [
        {
            "external_variant_id": "EX-100-BLK",
            "sku": "EX-100-BLK",
            "color": "Black",
            "size": None,
        }
    ],
    "images": ["https://supplier.example/path/image.jpg"],
    "source_updated_at": None,
}
```

**Do not copy this structure directly into production code** until it is mapped to the actual existing KaleidoBrands models.

## 7. Map product families and variants

For each supplier product:

1. Identify the stable **parent product/family ID**.
2. Identify all purchasable variants (color, size, material, decoration option, etc.).
3. Preserve the supplier's original SKU and external ID.
4. Normalize strings, units, currency, dimensions, and category labels without discarding source values needed for audit.
5. Link variants to the correct parent and supplier.
6. Deduplicate **within the supplier namespace**.
7. Record missing required attributes as validation errors or quarantine rows rather than inventing values.
8. Preserve existing product references used by quotes, carts, and orders.

**Special cases:** Products with no variants, reused supplier SKUs, discontinued colorways, blank images, restricted brands, and products with multiple decoration methods must each have an explicit mapping rule.

## 8. Import pricing and quantity tiers

- Verify whether the supplier returns **net cost**, MSRP, list price, or decorated selling price.
- Apply the **existing KaleidoBrands markup/pricing engine**; do not introduce a second conflicting formula.
- Store quantity breaks and effective dates according to existing pricing models.
- Handle minimum quantities, setup fees, run charges, additional color/location charges, and currency precision.
- Use `Decimal` for monetary values; avoid binary floating-point arithmetic.
- Validate tier ordering and prohibit negative prices or nonsensical minimums.
- Do not publish products with unknown or unvalidated sell prices unless the existing site explicitly supports quote-only products.

**Pricing audit examples:** A single-SKU product, a multi-color family, a tiered-price product, and a product with setup/decoration charges.

## 9. Import images and categories

- Map supplier categories into the existing marketplace taxonomy; do not create near-duplicate categories for spelling differences.
- Respect the existing `ProductImage` model and primary-image rules.
- Validate URLs, content types, file sizes, and image dimensions.
- Avoid repeatedly downloading identical images; use existing caching/deduplication behavior.
- Keep image download failures non-destructive: a temporary HTTP 403 or 404 must not delete previously valid images.
- Check supplier rights and usage rules for catalog images and brand assets.

## 10. Build the sync in safe stages

**Stage A — Discovery:** Fetch a small sample, inspect source payloads, and record mapping gaps. **No database writes.**

**Stage B — Dry run:** Normalize and validate a small family batch; report what *would* be created/updated. Implement dry-run behavior if the current importer does not have it.

**Stage C — Controlled write:** Import one product family and its variants into the development database. Confirm relationships, prices, and images.

**Stage D — Bounded batch:** Import a few families/pages with throttling and checkpoints. Confirm rerunning the same batch creates **zero duplicate records**.

**Stage E — Full initial load:** Only after sample and bounded tests pass, import the catalog in batches with resumability and progress logging.

**Stage F — Incremental sync:** Update changed products, prices, inventory, and images without reprocessing the full catalog when the supplier supports incremental changes.

**Stage G — Reconciliation:** Compare source totals and database totals. Treat missing products cautiously until a **complete, successful** source snapshot has been processed.

Never infer a full-sync success from a partial page or a request that stopped at a rate limit.

## 11. Verification and acceptance tests

Run project checks:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

If the repository has additional test runners or targeted tests, use those too. The `makemigrations` command above is **read-only** and verifies that model changes have been accounted for; it does not replace migration review.

Required integration tests:

- Authentication succeeds and invalid credentials fail safely.
- Pagination fetches each page exactly once and handles empty pages.
- Rate limits, timeouts, malformed JSON/XML/CSV, and intermittent failures do not corrupt existing data.
- Parent products and variants have correct supplier ownership.
- Product IDs and SKUs do not collide across suppliers.
- Pricing tiers and decoration charges match representative source records.
- Image URLs and categories map correctly.
- Running the same import twice does not create duplicates.
- Failed or partial syncs do not mass-deactivate or delete products.
- Existing supplier catalog counts remain unchanged by onboarding.
- Product listing, detail, search, quote/cart, and checkout behavior remain valid.
- Sync logs and status clearly report errors and last successful completion.

### Before/after reconciliation sheet

| Metric | Before | After | Expected |
|---|---:|---:|---|
| Existing suppliers | Record | Record | Unchanged |
| Existing products | Record | Record | Unchanged except authorized sync updates |
| Existing variants | Record | Record | Unchanged except authorized sync updates |
| New supplier parents | 0 | Record | Matches accepted source families |
| New supplier variants | 0 | Record | Matches accepted source variants |
| Invalid/unpriced products | 0 | Record | Quarantined or unpublished |
| Duplicate external IDs | 0 | Record | 0 |
| Failed import rows | 0 | Record | Investigated |

## 12. Connect to the existing orchestration only after passing tests

The project has an existing `sync_all_suppliers` management command and a weekly Render supplier-sync job. **Do not change the production job or its schedule during initial onboarding.**

Known existing production invocation (for reference, **not** an instruction to run it locally):

```bash
PYTHONUNBUFFERED=1 python -u manage.py sync_all_suppliers --weekly-batch --since-days 8 --family-batch-size 1 --generic-batch-size 5 --pause 1
```

Before registering the new adapter in the aggregator:

1. Inspect the current `sync_all_suppliers` implementation and supplier selection logic.
2. Confirm whether it supports targeting **only the new supplier**; use that path for testing.
3. Verify the new adapter has independent failure handling and cannot stop unrelated supplier jobs.
4. Check that existing `--weekly-batch`, `--since-days`, batch-size, and pause semantics are preserved.
5. Test the full aggregator in a **development/staging** environment with mocked or sandbox APIs.
6. Obtain approval before changing the production supplier registry or enabling the new supplier in the weekly job.

## 13. Deployment checklist

1. Review `git diff` and commit **only** the new supplier's adapter, mapping, tests, configuration references, and any approved additive migrations.
2. Confirm no API keys, tokens, local DB files, media caches, or generated `staticfiles/` directories are staged.
3. Confirm a database backup/restore point and migration rollback plan.
4. Add the supplier's secrets to Render environment settings using the existing secret-management procedure.
5. Deploy code and apply **reviewed** migrations using the project's existing deployment process.
6. Run `python manage.py check` in the deployment environment.
7. Execute a small targeted import; inspect logs, DB counts, product pages, and pricing.
8. Execute a controlled full import, monitoring rate limits and database load.
9. Enable storefront visibility only after data-quality approval.
10. Register the supplier for recurring synchronization only after a successful independent production sync.
11. Monitor the next scheduled sync and compare counts before/after.

### Rollback principles

- Prefer disabling the **new supplier's visibility or sync** rather than deleting its data.
- Roll back application code through the existing deployment process if necessary.
- Do not automatically reverse data-bearing migrations or remove shared tables.
- Restore the database only with a verified recovery plan and awareness of orders/changes made since the backup.

## 14. Supplier-specific handoff record

Create a short onboarding record for each supplier:

```text
Supplier name:
Supplier slug:
Technical contact:
API/documentation URL:
Authentication method:
Credential variable names (never values):
Source format / endpoints:
Product identifier:
Variant identifier:
Pricing source and currency:
Inventory source:
Image source:
Rate limits / retry policy:
Initial sync method:
Incremental sync method:
Expected parent count:
Expected variant count:
Validated sample products:
Dry-run result:
Idempotency test result:
Regression test result:
Production backup/restore point:
Deployment commit:
First production sync timestamp:
Next scheduled sync verification:
Known limitations:
Approved by:
```

## 15. Definition of done

A supplier integration is **complete** only when:

- [ ] Official source documentation and credentials are verified.
- [ ] Supplier and catalog records are linked using existing models.
- [ ] Product families, variants, prices, categories, and images are correctly mapped.
- [ ] Initial import is resumable and idempotent.
- [ ] Incremental synchronization is implemented or its absence documented.
- [ ] Invalid records are safely quarantined/unpublished.
- [ ] Existing supplier catalogs and application workflows pass regression tests.
- [ ] Source and database counts are reconciled and sampled manually.
- [ ] Secrets are configured outside source control.
- [ ] Production deploy and targeted sync are successful.
- [ ] New supplier storefront visibility is approved.
- [ ] Recurring synchronization is enabled and observed successfully.
- [ ] Onboarding handoff record is complete.

---

## Existing supplier integrations — preservation notes

KaleidoBrands already has a multi-supplier integration system and a weekly sync process. Previously validated examples include Koozie Group, The Magnet Group, Vantage Apparel, and Jornik. Their product families, variants, and supplier sync behavior are **regression baselines**, not templates to overwrite. Always inspect current database totals and current code before relying on historical counts.

**Suggested file location in the repository:** `kaleido/README_NEW_SUPPLIER.md` (next to `manage.py`).
