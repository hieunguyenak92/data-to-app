# Synthetic datasets

The installable skill bundles its examples so the first run works after installation.

- [Inventory model](../skills/data-to-app/assets/examples/inventory/model.json)
- [Initial products](../skills/data-to-app/assets/examples/inventory/initial/products.csv)
- [Order lines](../skills/data-to-app/assets/examples/inventory/initial/orders.csv)
- [Next products snapshot](../skills/data-to-app/assets/examples/inventory/next/products.csv)

Every value is synthetic. The initial products file contains an identical duplicate and leading-zero identifiers. In the next snapshot, some unedited fields change, one record is missing and another is new. Set product `00128`'s local reorder level to `20` before importing the next snapshot to create a deliberate source/local conflict.

```sh
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 ./inventory-app/app.py --port 8765
```

Use the app's Import preview, or the CLI described in the README. This dataset illustrates behavior; it does not constitute a performance benchmark or customer adoption.
