# Sales and order operations

## Public offer

- Preview: one free run per account.
- Standard: 5 credits; a new account receives 5 credits once.
- Professional: 20 credits; Starter package is ฿7,900.
- Growth: 110 credits for ฿34,900.
- Scale: 360 credits for ฿89,000.

Deep and Enterprise are not in the current public catalog. Customer-data
calibration, historical backtesting and custom regional work require a signed
project scope and must not be described as self-service platform features.

## Payment flow

1. Customer creates an order in the billing page.
2. The order page opens the official Lazzor WhatsApp contact
   (`+66 62 345 8238`) with the order ID, package and amount prefilled.
3. Sales verifies funds outside the application.
4. An authorized operator records the bank/payment reference with:

```bash
MARKET_TWIN_API_URL=https://YOUR_CLOUD_RUN_URL \
MARKET_TWIN_ADMIN_API_KEY=YOUR_ADMIN_KEY \
python3 scripts/complete_order.py \
  --order-id ord_xxxxxxxxxx \
  --payment-reference BANK-2026-000123 \
  --confirm
```

The API locks the order and user, changes the order to `PAID`, and creates one
ledger entry. Running the same command again does not grant credits twice.

Never accept a screenshot alone as proof of payment. Verify the bank or payment
provider record and ensure the payment reference is unique.

## Customer-facing claims

Say:

- “decision-support simulation”
- “official Thailand macro-demographic calibration”
- “prior-predictive P10–P90 interval”
- “public offer-price evidence”
- “compares scenarios and helps prioritize validation”

Do not say:

- “guaranteed purchase rate, revenue or market share”
- “real Shopee/Lazada sales” when only public page evidence exists
- “real consumer interviews” for LLM output
- “validated WTP” without observed choice data and holdout backtesting
- “300,000 live agents” or “Cloud Batch delivery” in the current offer

## Refund handling

Failed simulations automatically create `FAILED_RUN_REFUND` ledger entries.
For commercial refunds outside the platform, follow the signed order/contract
and record the external refund reference in the finance system. Do not grant or
remove credits by editing the database manually.
