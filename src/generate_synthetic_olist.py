"""
generate_synthetic_olist.py — Generate a synthetic Olist-shaped dataset.

Produces the 9 CSVs in data/raw/ with the exact column names and types that
sql/01_load_raw.sql expects. Inspired by the real Brazilian E-Commerce
Public Dataset by Olist (Kaggle), but every row is procedurally generated
with a fixed seed for reproducibility.

Why synthetic instead of the real Kaggle dump:
  - zero external credentials / downloads
  - deterministic outputs that hiring managers can reproduce locally
  - same star-schema shape so all SQL in sql/*.sql runs unchanged

Volume targets (close to the real Olist scale):
  ~99k orders, ~95k unique customers, ~32k products in ~73 categories,
  ~3k sellers, time range 2016-09 → 2018-09 with a Black Friday peak.

Usage:
    py -3.12 src/generate_synthetic_olist.py
"""

from __future__ import annotations

import csv
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

SEED = 42
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

N_ORDERS = 99_441
N_UNIQUE_CUSTOMERS = 95_000
N_PRODUCTS = 32_000
N_SELLERS = 3_095

START_DATE = datetime(2016, 9, 4)
END_DATE = datetime(2018, 9, 3)

rng = np.random.default_rng(SEED)


# ---------------------------------------------------------------------------
# Reference data — Brazilian states, categories, payment types
# ---------------------------------------------------------------------------

# 27 BR states with population-weighted distribution. SP dominant, as in real Olist.
BR_STATES = {
    "SP": 0.420, "RJ": 0.128, "MG": 0.117, "RS": 0.055, "PR": 0.051,
    "SC": 0.041, "BA": 0.034, "DF": 0.021, "GO": 0.021, "ES": 0.020,
    "PE": 0.018, "CE": 0.013, "PA": 0.010, "MT": 0.009, "MA": 0.008,
    "MS": 0.008, "PB": 0.006, "PI": 0.005, "RN": 0.005, "AL": 0.004,
    "SE": 0.003, "TO": 0.003, "RO": 0.003, "AM": 0.003, "AC": 0.001,
    "AP": 0.001, "RR": 0.001,
}
STATE_NAMES = list(BR_STATES.keys())
STATE_WEIGHTS = np.array(list(BR_STATES.values()))
STATE_WEIGHTS = STATE_WEIGHTS / STATE_WEIGHTS.sum()

# Northern / Northeastern states get late deliveries more often.
LATE_PRONE_STATES = {"AM", "PA", "AC", "AP", "RR", "RO", "TO", "MA", "PI", "CE", "RN", "PB", "AL", "SE"}

# Major cities per state — just one each, keeps dataset light. Real Olist has thousands.
STATE_CITY = {
    "SP": "sao paulo", "RJ": "rio de janeiro", "MG": "belo horizonte",
    "RS": "porto alegre", "PR": "curitiba", "SC": "florianopolis",
    "BA": "salvador", "DF": "brasilia", "GO": "goiania", "ES": "vitoria",
    "PE": "recife", "CE": "fortaleza", "PA": "belem", "MT": "cuiaba",
    "MA": "sao luis", "MS": "campo grande", "PB": "joao pessoa",
    "PI": "teresina", "RN": "natal", "AL": "maceio", "SE": "aracaju",
    "TO": "palmas", "RO": "porto velho", "AM": "manaus", "AC": "rio branco",
    "AP": "macapa", "RR": "boa vista",
}

# 73 product categories (Portuguese → English). Subset of real Olist, ordered by frequency.
CATEGORIES_PT_EN = [
    ("cama_mesa_banho",                "bed_bath_table"),
    ("beleza_saude",                   "health_beauty"),
    ("esporte_lazer",                  "sports_leisure"),
    ("moveis_decoracao",               "furniture_decor"),
    ("informatica_acessorios",         "computers_accessories"),
    ("utilidades_domesticas",          "housewares"),
    ("relogios_presentes",             "watches_gifts"),
    ("telefonia",                      "telephony"),
    ("ferramentas_jardim",             "garden_tools"),
    ("automotivo",                     "auto"),
    ("brinquedos",                     "toys"),
    ("cool_stuff",                     "cool_stuff"),
    ("perfumaria",                     "perfumery"),
    ("bebes",                          "baby"),
    ("eletronicos",                    "electronics"),
    ("papelaria",                      "stationery"),
    ("fashion_bolsas_e_acessorios",    "fashion_bags_accessories"),
    ("fashion_calcados",               "fashion_shoes"),
    ("pet_shop",                       "pet_shop"),
    ("agro_industria_e_comercio",      "agro_industry_and_commerce"),
    ("alimentos_bebidas",              "food_drink"),
    ("construcao_ferramentas_construcao", "construction_tools_construction"),
    ("consoles_games",                 "consoles_games"),
    ("audio",                          "audio"),
    ("livros_interesse_geral",         "books_general_interest"),
    ("market_place",                   "market_place"),
    ("eletrodomesticos",               "home_appliances"),
    ("moveis_escritorio",              "office_furniture"),
    ("eletroportateis",                "small_appliances"),
    ("musica",                         "music"),
    ("malas_acessorios",               "luggage_accessories"),
    ("instrumentos_musicais",          "musical_instruments"),
    ("construcao_ferramentas_seguranca", "construction_tools_safety"),
    ("industria_comercio_e_negocios",  "industry_commerce_and_business"),
    ("fashion_underwear_e_moda_praia", "fashion_underwear_beach"),
    ("fashion_masculina",              "fashion_male_clothing"),
    ("artigos_de_festas",              "party_supplies"),
    ("livros_tecnicos",                "books_technical"),
    ("alimentos",                      "food"),
    ("dvds_blu_ray",                   "dvds_blu_ray"),
    ("la_cuisine",                     "la_cuisine"),
    ("artigos_de_natal",               "christmas_supplies"),
    ("agro_industria",                 "agro_industry"),
    ("construcao_ferramentas_jardim",  "construction_tools_garden"),
    ("cine_foto",                      "cine_photo"),
    ("artes_e_artesanato",             "arts_and_craftmanship"),
    ("portateis_casa_forno_e_cafe",    "small_appliances_home_oven_and_coffee"),
    ("seguros_e_servicos",             "security_and_services"),
    ("flores",                         "flowers"),
    ("casa_conforto",                  "home_comfort"),
    ("casa_construcao",                "home_construction"),
    ("pcs",                            "computers"),
    ("tablets_impressao_imagem",       "tablets_printing_image"),
    ("eletrodomesticos_2",             "home_appliances_2"),
    ("portateis_cozinha_e_preparadores_de_alimentos", "small_appliances_kitchen_and_preparers"),
    ("livros_importados",              "books_imported"),
    ("sinalizacao_e_seguranca",        "signaling_and_security"),
    ("cds_dvds_musicais",              "cds_dvds_musicals"),
    ("artes",                          "arts"),
    ("fashion_esporte",                "fashion_sport"),
    ("fashion_roupa_masculina",        "fashion_male_clothing_2"),
    ("fashion_roupa_feminina",         "fashion_female_clothing"),
    ("fashion_roupa_infanto_juvenil",  "fashion_kids_clothing"),
    ("fraldas_higiene",                "diapers_and_hygiene"),
    ("artigos_militares",              "military_supplies"),
    ("musica_e_filmes",                "music_and_movies"),
    ("artigos_de_papelaria",           "stationery_supplies"),
    ("equipamentos_de_seguranca",      "safety_equipment"),
    ("portateis_casa",                 "small_appliances_home"),
    ("musical",                        "musical"),
    ("brinquedos_educativos",          "educational_toys"),
    ("seguranca_e_servicos",           "security_services"),
    ("artigos_industriais",            "industrial_supplies"),
    ("artigos_pet",                    "pet_supplies"),
]

PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
PAYMENT_WEIGHTS = np.array([0.74, 0.19, 0.05, 0.02])

ORDER_STATUSES = [
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "approved", "created",
]
# Mostly 'delivered' (~97%), small fractions for the rest.
STATUS_WEIGHTS = np.array([0.970, 0.011, 0.006, 0.006, 0.003, 0.003, 0.0005, 0.0005])

REVIEW_TITLES = [
    "Recomendo", "Otimo produto", "Nao gostei", "Excelente",
    "Veio com defeito", "Entrega rapida", "Conforme o anunciado",
    "Pessimo atendimento", "Bom custo beneficio", "Atrasou demais", "",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def short_hash() -> str:
    """32-char hex id like real Olist uses for order_id / customer_id."""
    return uuid.UUID(int=rng.integers(0, 2**128, dtype=np.uint64).item() << 0).hex


def hashes(n: int) -> np.ndarray:
    """Vectorized 32-char hex generation, much faster than uuid in a loop."""
    raw = rng.integers(0, 16, size=(n, 32), dtype=np.int8)
    return np.array(["".join("0123456789abcdef"[c] for c in row) for row in raw])


def random_dates_in_2016_2018(n: int, peak_dates: bool = True) -> np.ndarray:
    """Sample purchase timestamps with a Black-Friday-2017 bump."""
    days_total = (END_DATE - START_DATE).days
    if peak_dates:
        # Build a daily weight curve: baseline 1, BF-2017 multiplier 2.8, ramp Dec→Mar
        weights = np.ones(days_total + 1)
        for i in range(days_total + 1):
            d = START_DATE + timedelta(days=i)
            if d.year == 2017 and d.month == 11 and 18 <= d.day <= 27:
                weights[i] = 2.8                           # Black Friday week
            elif d.year == 2017 and d.month == 12:
                weights[i] = 1.4                           # December holiday lift
            elif d.year == 2016 and d.month <= 11:
                weights[i] = 0.15                          # early Olist (very sparse)
            elif d.year == 2018 and d.month >= 9:
                weights[i] = 0.4                           # tail-off in 2018
        weights = weights / weights.sum()
        day_offsets = rng.choice(days_total + 1, size=n, p=weights)
    else:
        day_offsets = rng.integers(0, days_total + 1, size=n)

    second_offsets = rng.integers(0, 86_400, size=n)
    timestamps = []
    for d, s in zip(day_offsets, second_offsets):
        timestamps.append(START_DATE + timedelta(days=int(d), seconds=int(s)))
    return np.array(timestamps)


def fmt_ts(ts: datetime | None) -> str:
    if ts is None or (isinstance(ts, float) and np.isnan(ts)):
        return ""
    return ts.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_customers() -> tuple[list[dict], dict[str, str]]:
    """Returns customers (one row per customer_id) and a lookup customer_id → unique."""
    print(f"  customers: {N_ORDERS} rows ({N_UNIQUE_CUSTOMERS} unique)")
    unique_ids = hashes(N_UNIQUE_CUSTOMERS)
    states = rng.choice(STATE_NAMES, size=N_UNIQUE_CUSTOMERS, p=STATE_WEIGHTS)

    # Map each unique customer to a state + zip + city
    unique_zip = rng.integers(1000, 99999, size=N_UNIQUE_CUSTOMERS)

    unique_records = {}
    for i, uid in enumerate(unique_ids):
        unique_records[uid] = {
            "state": states[i],
            "city": STATE_CITY[states[i]],
            "zip": str(unique_zip[i]).zfill(5),
        }

    # 95k unique customers stretched across 99k customer_id (Olist quirk: same physical
    # person gets a new customer_id per order, customer_unique_id is the stable key).
    customers = []
    customer_id_to_unique = {}

    # First: assign one customer_id per unique customer (95k)
    customer_ids_first = hashes(N_UNIQUE_CUSTOMERS)
    for cid, uid in zip(customer_ids_first, unique_ids):
        rec = unique_records[uid]
        customers.append({
            "customer_id": cid, "customer_unique_id": uid,
            "customer_zip_code_prefix": rec["zip"],
            "customer_city": rec["city"], "customer_state": rec["state"],
        })
        customer_id_to_unique[cid] = uid

    # Then: add extra customer_ids for repeat buyers (orders - unique = 4.4k repeats)
    extra = N_ORDERS - N_UNIQUE_CUSTOMERS
    extra_ids = hashes(extra)
    # Repeats pick from existing unique customers — weighted slightly toward SP/RJ
    repeat_unique = rng.choice(unique_ids, size=extra, replace=True)
    for cid, uid in zip(extra_ids, repeat_unique):
        rec = unique_records[uid]
        customers.append({
            "customer_id": cid, "customer_unique_id": uid,
            "customer_zip_code_prefix": rec["zip"],
            "customer_city": rec["city"], "customer_state": rec["state"],
        })
        customer_id_to_unique[cid] = uid

    return customers, customer_id_to_unique


def generate_sellers() -> list[dict]:
    print(f"  sellers: {N_SELLERS} rows")
    sellers = []
    seller_ids = hashes(N_SELLERS)
    seller_states = rng.choice(STATE_NAMES, size=N_SELLERS, p=STATE_WEIGHTS)
    seller_zips = rng.integers(1000, 99999, size=N_SELLERS)
    for sid, st, zp in zip(seller_ids, seller_states, seller_zips):
        sellers.append({
            "seller_id": sid,
            "seller_zip_code_prefix": str(zp).zfill(5),
            "seller_city": STATE_CITY[st],
            "seller_state": st,
        })
    return sellers


def generate_products() -> list[dict]:
    print(f"  products: {N_PRODUCTS} rows in {len(CATEGORIES_PT_EN)} categories")
    products = []
    product_ids = hashes(N_PRODUCTS)
    # Category distribution: top 5 cover ~50% of products, long tail
    cat_weights = np.array([1 / (i + 1) ** 1.1 for i in range(len(CATEGORIES_PT_EN))])
    cat_weights /= cat_weights.sum()
    cat_indices = rng.choice(len(CATEGORIES_PT_EN), size=N_PRODUCTS, p=cat_weights)

    # Dimensions (g, cm) — log-normal makes a few heavy outliers
    weights_g = np.clip(rng.lognormal(mean=6.5, sigma=1.0, size=N_PRODUCTS), 50, 30_000).astype(int)
    lens = np.clip(rng.normal(30, 12, size=N_PRODUCTS), 5, 105).astype(int)
    hgts = np.clip(rng.normal(18, 8, size=N_PRODUCTS), 2, 60).astype(int)
    wdts = np.clip(rng.normal(22, 9, size=N_PRODUCTS), 5, 80).astype(int)
    photos = rng.integers(1, 6, size=N_PRODUCTS)
    name_lens = rng.integers(15, 80, size=N_PRODUCTS)
    desc_lens = rng.integers(80, 1000, size=N_PRODUCTS)

    for pid, ci, w, ln, ht, wd, ph, nl, dl in zip(
        product_ids, cat_indices, weights_g, lens, hgts, wdts, photos, name_lens, desc_lens
    ):
        products.append({
            "product_id": pid,
            "product_category_name": CATEGORIES_PT_EN[ci][0],
            "product_name_lenght": nl,
            "product_description_lenght": dl,
            "product_photos_qty": ph,
            "product_weight_g": w,
            "product_length_cm": ln,
            "product_height_cm": ht,
            "product_width_cm": wd,
        })
    return products


def generate_geolocation() -> list[dict]:
    """One geolocation row per state (light — real Olist has 1M+ rows)."""
    print(f"  geolocation: {len(STATE_NAMES)} rows (one per state)")
    coords = {
        "SP": (-23.55, -46.63), "RJ": (-22.91, -43.20), "MG": (-19.92, -43.94),
        "RS": (-30.03, -51.23), "PR": (-25.43, -49.27), "SC": (-27.59, -48.55),
        "BA": (-12.97, -38.51), "DF": (-15.78, -47.93), "GO": (-16.69, -49.26),
        "ES": (-20.32, -40.34), "PE": (-8.05,  -34.88), "CE": (-3.73,  -38.52),
        "PA": (-1.46,  -48.50), "MT": (-15.60, -56.10), "MA": (-2.53,  -44.30),
        "MS": (-20.45, -54.65), "PB": (-7.11,  -34.86), "PI": (-5.09,  -42.81),
        "RN": (-5.79,  -35.21), "AL": (-9.66,  -35.74), "SE": (-10.91, -37.07),
        "TO": (-10.18, -48.33), "RO": (-8.76,  -63.90), "AM": (-3.10,  -60.02),
        "AC": (-9.97,  -67.81), "AP": (0.04,   -51.07), "RR": (2.82,   -60.67),
    }
    rows = []
    for st, (lat, lng) in coords.items():
        rows.append({
            "geolocation_zip_code_prefix": str(rng.integers(1000, 99999)).zfill(5),
            "geolocation_lat": lat, "geolocation_lng": lng,
            "geolocation_city": STATE_CITY[st], "geolocation_state": st,
        })
    return rows


def generate_orders_and_items(
    customers: list[dict], products: list[dict], sellers: list[dict]
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """The heavy generator — produces orders + items + payments + reviews together,
    so that delivery lateness, review score and payment value stay consistent."""
    print(f"  orders + items + payments + reviews: {N_ORDERS} orders...")

    order_ids = hashes(N_ORDERS)
    purchase_ts = random_dates_in_2016_2018(N_ORDERS, peak_dates=True)

    # Assign each order a customer (the first 95k get unique customers, the rest are
    # repeat customers — same customer_unique_id, different customer_id)
    customer_pick = rng.permutation(len(customers))[:N_ORDERS]

    # Status — 97% delivered
    statuses = rng.choice(ORDER_STATUSES, size=N_ORDERS, p=STATUS_WEIGHTS)

    orders, items, payments, reviews = [], [], [], []
    product_ids_arr = np.array([p["product_id"] for p in products])
    product_weights = np.array([p["product_weight_g"] for p in products])
    seller_ids_arr = np.array([s["seller_id"] for s in sellers])
    seller_states_arr = np.array([s["seller_state"] for s in sellers])

    # Pre-sample items per order: 1 (most), 2 (some), 3+ (few)
    items_per_order = rng.choice([1, 2, 3, 4, 5], size=N_ORDERS,
                                  p=[0.86, 0.11, 0.025, 0.004, 0.001])

    customer_state_arr = np.array([c["customer_state"] for c in customers])

    for i in range(N_ORDERS):
        oid = order_ids[i]
        cust = customers[customer_pick[i]]
        purch = purchase_ts[i]
        status = statuses[i]

        # ---- Delivery timing -----------------------------------------------
        # Approval: 0–48h after purchase
        approved = purch + timedelta(hours=int(rng.integers(1, 48))) if status != "canceled" else None

        # Estimated delivery: 7–35 days from purchase (avg ~24d in BR)
        estimated_lag = max(5, int(rng.normal(24, 6)))
        estimated_delivery = purch + timedelta(days=estimated_lag)

        is_late = False
        carrier_dt = None
        delivered_dt = None
        if status == "delivered":
            cust_state = cust["customer_state"]
            # Base late probability 5%, double for late-prone states
            p_late = 0.12 if cust_state in LATE_PRONE_STATES else 0.05
            is_late = rng.random() < p_late

            # Carrier handoff: 2-12 days after purchase
            seller_lag = int(rng.normal(5, 2))
            seller_lag = max(1, min(seller_lag, 18))
            carrier_dt = purch + timedelta(days=seller_lag)

            # Customer delivery: depends on lateness
            if is_late:
                lag_days = int(rng.normal(estimated_lag + 12, 6))
            else:
                lag_days = int(rng.normal(estimated_lag - 5, 4))
            lag_days = max(seller_lag + 1, lag_days)
            delivered_dt = purch + timedelta(days=lag_days)

        orders.append({
            "order_id": oid, "customer_id": cust["customer_id"], "order_status": status,
            "order_purchase_timestamp": fmt_ts(purch),
            "order_approved_at": fmt_ts(approved),
            "order_delivered_carrier_date": fmt_ts(carrier_dt),
            "order_delivered_customer_date": fmt_ts(delivered_dt),
            "order_estimated_delivery_date": fmt_ts(estimated_delivery),
        })

        # ---- Items -------------------------------------------------------------
        n_items = int(items_per_order[i])
        product_picks = rng.integers(0, N_PRODUCTS, size=n_items)
        seller_pick = int(rng.integers(0, N_SELLERS))
        total_item_value = 0.0
        for j, pidx in enumerate(product_picks, start=1):
            # Price: lognormal, mean R$ 120
            price = float(round(rng.lognormal(4.5, 0.85), 2))
            price = max(5.0, min(price, 6500.0))
            # Freight: log-correlated with weight + cross-state distance
            base_freight = 8.0 + (product_weights[pidx] / 1000.0) * 4.5
            if cust["customer_state"] in LATE_PRONE_STATES:
                base_freight *= 1.4
            freight = round(base_freight * float(rng.normal(1.0, 0.15)), 2)
            freight = max(3.0, min(freight, 350.0))
            total_item_value += price + freight

            items.append({
                "order_id": oid, "order_item_id": j,
                "product_id": product_ids_arr[pidx],
                "seller_id": seller_ids_arr[seller_pick],
                "shipping_limit_date": fmt_ts(purch + timedelta(days=int(rng.integers(2, 9)))),
                "price": f"{price:.2f}", "freight_value": f"{freight:.2f}",
            })

        # ---- Payments ----------------------------------------------------------
        n_payments = 1 if rng.random() > 0.05 else int(rng.integers(2, 4))
        remaining = total_item_value
        for k in range(1, n_payments + 1):
            ptype = rng.choice(PAYMENT_TYPES, p=PAYMENT_WEIGHTS) if k == 1 else "voucher"
            if k < n_payments:
                share = float(rng.uniform(0.2, 0.6))
                pval = round(remaining * share, 2)
                remaining -= pval
            else:
                pval = round(remaining, 2)
            installments = 1
            if ptype == "credit_card":
                installments = int(rng.choice([1, 2, 3, 4, 5, 6, 8, 10, 12],
                                              p=[0.45, 0.13, 0.11, 0.08, 0.07, 0.05, 0.04, 0.03, 0.04]))
            payments.append({
                "order_id": oid, "payment_sequential": k, "payment_type": ptype,
                "payment_installments": installments, "payment_value": f"{pval:.2f}",
            })

        # ---- Reviews -----------------------------------------------------------
        # Only delivered orders get reviews ~88% of the time
        if status == "delivered" and rng.random() < 0.88:
            if delivered_dt is not None:
                # Late deliveries pull review score down strongly
                if is_late:
                    lag_days = (delivered_dt - estimated_delivery).days
                    if lag_days >= 8:
                        score = int(np.clip(rng.normal(1.9, 0.9), 1, 5))
                    else:
                        score = int(np.clip(rng.normal(3.2, 1.1), 1, 5))
                else:
                    score = int(np.clip(rng.normal(4.5, 0.7), 1, 5))
                review_creation = delivered_dt + timedelta(days=int(rng.integers(1, 12)))
                review_answer = review_creation + timedelta(hours=int(rng.integers(2, 96)))

                reviews.append({
                    "review_id": hashes(1)[0], "order_id": oid,
                    "review_score": score,
                    "review_comment_title": rng.choice(REVIEW_TITLES) if rng.random() < 0.18 else "",
                    "review_comment_message": "" if rng.random() < 0.55 else rng.choice(REVIEW_TITLES),
                    "review_creation_date": fmt_ts(review_creation),
                    "review_answer_timestamp": fmt_ts(review_answer),
                })

        if (i + 1) % 20_000 == 0:
            print(f"    {i+1:>6,} / {N_ORDERS:,} orders generated")

    return orders, items, payments, reviews


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"    wrote {path.name}  ({len(rows):,} rows, {path.stat().st_size/1024/1024:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    t0 = datetime.now()
    print(f"Generating synthetic Olist dataset in {RAW_DIR.resolve()}")
    print(f"Seed: {SEED}\n")

    print("[1/4] Reference tables")
    customers, _ = generate_customers()
    sellers = generate_sellers()
    products = generate_products()
    geo = generate_geolocation()

    cat_translation = [
        {"product_category_name": pt, "product_category_name_english": en}
        for pt, en in CATEGORIES_PT_EN
    ]

    print("\n[2/4] Fact tables (orders + items + payments + reviews)")
    orders, items, payments, reviews = generate_orders_and_items(customers, products, sellers)

    print("\n[3/4] Writing CSVs")
    write_csv(orders,           RAW_DIR / "olist_orders_dataset.csv")
    write_csv(items,            RAW_DIR / "olist_order_items_dataset.csv")
    write_csv(payments,         RAW_DIR / "olist_order_payments_dataset.csv")
    write_csv(reviews,          RAW_DIR / "olist_order_reviews_dataset.csv")
    write_csv(products,         RAW_DIR / "olist_products_dataset.csv")
    write_csv(customers,        RAW_DIR / "olist_customers_dataset.csv")
    write_csv(sellers,          RAW_DIR / "olist_sellers_dataset.csv")
    write_csv(geo,              RAW_DIR / "olist_geolocation_dataset.csv")
    write_csv(cat_translation,  RAW_DIR / "product_category_name_translation.csv")

    elapsed = (datetime.now() - t0).total_seconds()
    print(f"\n[4/4] Done in {elapsed:.1f}s. Total CSV size: "
          f"{sum(p.stat().st_size for p in RAW_DIR.glob('*.csv'))/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
