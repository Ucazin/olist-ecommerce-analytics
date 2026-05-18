# Dataset Download

This project uses the **Brazilian E-Commerce Public Dataset by Olist**.

## Option A — Kaggle CLI (recommended)

```bash
pip install kaggle
# Configure your kaggle.json token: https://www.kaggle.com/docs/api
kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
```

## Option B — Manual

1. Visit https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
2. Click **Download** (requires a free Kaggle account).
3. Unzip the archive into `data/raw/`.

## Expected files in `data/raw/`

```
olist_orders_dataset.csv                    # 99,441 orders
olist_order_items_dataset.csv               # 112,650 line items
olist_order_payments_dataset.csv            # 103,886 payment records
olist_order_reviews_dataset.csv             #  99,224 reviews
olist_products_dataset.csv                  #  32,951 products
olist_customers_dataset.csv                 #  99,441 customers
olist_sellers_dataset.csv                   #   3,095 sellers
olist_geolocation_dataset.csv               # 1,000,163 zip-code → lat/lon
product_category_name_translation.csv       #      71 PT-EN translations
```

## Size

Total: ~140 MB unzipped. The largest file is `geolocation` (~60 MB).

## License

The dataset is released under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — non-commercial use, attribution required, share-alike.
