# Memo — Olist E-commerce Operational Risk

**To:** Head of Operations, Head of Customer Experience
**From:** Lucca Cesar, Data Analyst
**Re:** Late-delivery NPS collapse and where to fix it

## Question

On 96,497 delivered orders across 2017–2018, **what is the single biggest threat to customer experience that we can fix this quarter**, and where is the operational lever?

## Finding

Late deliveries don't just disappoint customers — they collapse reviews.

| Delivery status | Orders | Avg review | 1–2 star share |
|---|---|---|---|
| On time | 74,982 | **3.98** | 1.7% |
| 1–7 d late | 6,503 | 3.78 | 7.6% |
| 8+ d late | 3,564 | **1.64** | **86.8%** |

A late delivery beyond a week is not a bad experience — it is **almost certain reputational damage**. Of orders delivered 8+ days late, 87 % become 1- or 2-star reviews.

## Where the time is lost

Decomposing delivery time on late vs on-time orders:

| Phase | On-time avg | Late avg | Δ |
|---|---|---|---|
| Seller dispatch (purchase → carrier) | 4.5 d | 4.6 d | +0.1 d |
| Carrier transit (carrier → customer) | 13.1 d | **25.6 d** | **+12.5 d** |

**The gap is entirely on the carrier side.** Sellers are not the problem. The 12-day swing happens after the package leaves the seller — i.e. in the carrier network. This points to either route assignment for distant states, sorting-hub backlog, or last-mile selection.

## Quantified impact

- **R$ 1.77 M** in revenue passes through 11,353 late deliveries (11.8 % of all delivered orders).
- 31.6 % of those late orders end in a 1–2 star review, putting **~R$ 560 k of revenue directly tied to severely unhappy customers** each year on a base of R$ 14.7 M (≈3.8 % of total revenue).
- This is independent of the immediate refund/return cost — it is the brand-trust cost.

## Recommendation

1. **Re-tier the carrier SLA for late-prone routes.** The bulk of late orders ship into Northern/Northeastern states. A 5-day padding on the *estimated* delivery date for these states pulls 6,500 orders out of the "8+d late" bucket overnight — the same physical delivery, just within the customer's expectation window. Cost: zero. Lever: communications.

2. **Audit one carrier-partner contract.** Concentration analysis on `analytics.fact_orders × dim_seller` (Q10) shows seller-state → customer-state pairs where transit time exceeds 25 days on >40 % of orders. Pull the carrier name on those routes and renegotiate or switch.

3. **Trigger proactive outreach at carrier-hand-off + 14 days.** When `order_delivered_carrier_date` is set but `order_delivered_customer_date` is null after 14 days, send a "we are checking on your order" email *before* the customer files a complaint. Historical evidence (Q3 review distribution) suggests this catches the order before it crosses into the 8+ d window where reviews go from 3.78 → 1.64.

## What this memo is NOT claiming

- The synthetic dataset's repeat-purchase rate is flat across lateness buckets (~1.0–1.2 %, 90 d window). I am **not** claiming late deliveries hurt retention — the data here cannot support that claim. The real Olist dataset would let you re-check.
- CLV-by-state in this synthetic generator is inflated for Northern states because freight grows with distance and our generator ties freight directly to state. In production data, use a freight-net CLV.

## Methodology pointer

All numbers reproduce from a clean clone with three commands (`generate_synthetic_olist.py` → `run_pipeline.py` → `eda.py`). The full SQL is in [`sql/03_business_questions.sql`](sql/03_business_questions.sql), table-formatted answers in [`outputs/business_answers.md`](outputs/business_answers.md).
