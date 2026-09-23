# VeriScan — PRD & State

## Vision
AI product-health & ingredient intelligence app for global users. Barcode scanner, ingredient-level toxicity (0–100), personalized match, watchlist, OCR fallback, admin backoffice, secure payments.

## Stack
- Frontend: Expo Router (React Native), React Query, Expo Camera, react-native-webview
- Backend: FastAPI + MongoDB (Motor)
- LLM: Claude Sonnet 4.6 via Emergent LLM Key (multimodal OCR)
- Email: Emergent-managed Resend (OTP, watchlist alerts, refund tickets)
- Payments: Razorpay (India, INR); other countries FREE for now (admin can enable pricing per country)
- External data: Open Food Facts + Open Beauty Facts

## Shipped through Iter 4
### User experience
- 3-scan guest mode (device fingerprint)
- Email-only signup (T&C + Privacy accepted, no DOB or extra PII)
- **3-month free trial** for every new user — unlimited scans, no card
- Post-trial: pay-per-scan (₹5 intro / ₹15 standard) or monthly (₹72) / yearly (₹450) subscription
- Password reset via 6-digit OTP (Resend) — admin can send a reset code but cannot see or change passwords
- Real product lookup via Open Food Facts + Open Beauty Facts; unknown barcode → guided OCR contribution flow (Claude Sonnet 4.6) → immediate scored report (**always free**)
- Regulatory badges chip row: FSSAI, FDA, USDA Organic, EU Bio, PETA, Leaping Bunny, Vegan Society, Trustified, Informed Sport, Kosher, Halal, Gluten-Free, Non-GMO, Green Dot (IN veg), Brown Triangle (IN non-veg); auto-detected from labels, plus admin override per product
- Watchlist + email alerts, in-app inbox
- Support tickets + misinformation reports
- Better-For-You carousel of cleaner alternatives
- Country-aware pricing: `x-country` header determines whether a scan consumes credits; non-IN countries free until admin enables pricing

### Payments (Razorpay, INR)
- `POST /api/payments/razorpay/order` — pay-per-scan credits, accepts `promo_code`, applies discount/bonus
- `POST /api/payments/razorpay/subscription` — one-time payment that activates a 30/365-day subscription
- `POST /api/promocodes/preview` — public preview endpoint that returns the discount without creating an order
- Hosted checkout page with signature-verified callback and idempotent crediting
- Webhook handler (HMAC-SHA256, dedup by event id)

### Admin
- Users (masked emails), suspend/reactivate/send-reset
- Support tickets and misinformation reports workflows
- Country pricing editor (all 8 countries)
- Promo codes: create, list, deactivate (percent, flat, free_scans)
- **Payments & refunds** — list credited payments; refund any payment (calls Razorpay refunds API, reverses credits, auto-opens a resolved support ticket)
- **Merge duplicates** — mongo aggregation groups by lower(name, brand); admin picks the canonical barcode, others soft-marked `merged` with `merged_into` pointer; watchlist/reports/history/contributions repointed

### Legal
- T&C + Privacy templates (versioned) served from `/api/legal/*`; users can only register after accepting both
- Admin actions logged; passwords bcrypt-hashed; email sending guarded against phishing patterns

## API summary (additions this iteration)
- `POST /api/promocodes/preview`
- `POST /api/payments/razorpay/subscription`
- `POST /api/admin/refund`
- `GET /api/admin/payments`
- `GET /api/admin/duplicates`
- `POST /api/admin/products/merge`
- `PUT /api/admin/products/{barcode}/badges`
- `x-country` header on lookup — governs whether a scan consumes credits

## Testing
- **Iter 6 backend regression: 44/44 pass** — trial, badges, promo discount, subscription order, admin refund path, merge duplicates, region_free lookup

## Deployment notes
- After **Publish** → Deploy, register Razorpay webhook at `https://<app>.emergent.host/api/payments/razorpay/webhook` with `RAZORPAY_WEBHOOK_SECRET`
- Payments only need live-mode Razorpay keys before public release
- Apple Pay / Stripe for non-IN countries is deferred; countries are currently FREE and admin can enable pricing later from the Admin → Country pricing screen

## Update — Price comparison + Router refactor + Preferences v2 (2026-09-23)
- `server.py` (1653 lines) split into modular routers: `routes/{auth,profile,products,payments,admin,misc}.py` + `core/{config,models,deps,product_logic,pricing_logic}.py`. `server.py` is now a slim app factory; API surface unchanged.
- Hybrid e-commerce price comparison: `GET /api/products/compare?barcode=X` returns category-routed retailer deep-links (Amazon IN, Flipkart, Blinkit, Zepto, Nykaa, Tata 1mg, HealthKart) always, plus live prices via QuickCommerce API + Apify when `QUICKCOMMERCE_API_KEY`/`APIFY_TOKEN` are set in backend/.env (currently placeholders). 15-min MongoDB cache (`price_cache`).
- Frontend: `src/components/price-comparison.tsx` renders live prices (with MRP strikethrough) or deep-link buttons with "Search links"/"Live prices" chip; replaces the old static `product.retailers` block on the product page.
- Preferences expanded (frontend options + backend scoring): dietary +Keto/High protein/Halal/Jain, targets +Low sodium/Weight management/Energy & focus, sensitivities +Sulfate-free/Dairy-free/Soy-free/Palm oil free.
- Test suite: 49 passed / 10 failed — all 10 failures are stale iteration 1-3 tests (register without T&C versions, barcode 9999999999999 polluted into DB by old contribution tests). Same failures exist on pre-refactor code (18 failed there).
