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

## Iteration 8 (2026-09-23) — Legal hardening, Analytics, Stripe, Fuzzy dedup
**Legal v2.0.0 (T&C + Privacy)** — jurisdiction-aware, strict no-refund + no-cancellation, AS-IS warranty disclaimer, liability capped at INR 500 / USD 6 or 3-month fees (lower), force-majeure + delayed-ticket disclaimer, arbitration seated in Mumbai under Arbitration Act 1996, class-action waiver, explicit consent to waive EU/UK/India digital-service withdrawal rights per EU Consumer Rights Directive Art. 16(m), UK CCR 2013 reg. 36(2), and IN Consumer Protection Act 2019. Mandatory re-acceptance enforced at (a) login (via TermsGate modal in _layout.tsx) and (b) every Razorpay + Stripe checkout call (returns 428 TERMS_ACCEPTANCE_REQUIRED).

**Anonymous analytics** — `analytics_daily` MongoDB collection stores counters keyed by (date, event, key). NO user id / email / IP / device id ever stored. Events: `scan` (auto-fired inside /api/products/lookup), `retailer_click` (fired from PriceComparison component), `contribute`, `share`. Admin endpoints: GET /api/admin/analytics/overview (totals, top products, retailer breakdown, daily buckets) and GET /api/admin/analytics/export (CSV download). Admin screen at /admin/analytics with stat cards + retailer bar chart + top products + 14-day activity chart.

**Stripe checkout (non-IN)** — POST /api/payments/stripe/checkout creates a Checkout Session in subscription mode with `automatic_payment_methods={enabled: true}` so Card + Apple Pay + Google Pay all show up on eligible clients. Gated: /api/payments/stripe/status returns enabled=false unless admin has toggled a positive price via POST /api/admin/pricing/stripe/toggle. Requires up-to-date T&C. STRIPE_API_KEY is expected from env; a real Stripe test/live key must be provided (placeholder in preview env fails Stripe's validation with a friendly error).

**Smart fuzzy dedup** — /api/admin/duplicates now returns both exact clusters (`kind='exact'`, confidence=100) AND fuzzy clusters via RapidFuzz `token_set_ratio ≥ 82` on `brand+name` (`kind='fuzzy'`, confidence=avg%). Same-category constraint enforced. Frontend shows "AI · 87%" chip for fuzzy suggestions.

**Enforcement + regression** — /api/payments/razorpay/order and /api/payments/razorpay/subscription now return 428 unless user is current-version-accepted. New endpoints /api/profile/terms-status and POST /api/profile/accept-terms. Testing agent verified 96/96 functional pass (77 regression + 19 new). Stripe integration path verified end-to-end; only real Stripe key missing.

### Where analytics data is saved (user question)
Anonymous counters live in MongoDB collection `analytics_daily` inside the `test_database` DB. To access:
- **Admin dashboard**: /admin/analytics screen (auto-refresh)
- **CSV download**: `GET {backend}/api/admin/analytics/export?days=90` with admin bearer token → downloads `veriscan-analytics-<date>.csv` with columns date,event,key,count,category,retailer_id,barcode.
- **Direct Mongo**: `db.analytics_daily.find({date: {$gte: "2026-09-01"}})` on MongoDB Atlas.

Data is retained indefinitely (no PII → no retention duty). If the user later wants a hosted BI dashboard we can point Metabase or Retool at the same collection.

## Iteration 9 (2026-09-23) — Launch prep: trial email, analytics insights, admin self-service
**Trial reminder emails** — new `/app/backend/scheduler.py` runs an asyncio task on backend startup that wakes every hour and sends a friendly email to any user whose trial_expires_at is within 7 days and hasn't been reminded yet. Idempotent via `trial_reminder_sent_at` field.
**Monthly analytics report** — same scheduler fires on day 1 of each month, emails every admin the previous month's totals + top 10 products + top 10 retailers. Idempotent via `monthly_report_log` collection. Manual force-send endpoint `POST /api/admin/analytics/report/send-now` for on-demand triggering.
**Category + country breakdowns** — `analytics_daily` now stores extra `category:{cat}` and `country:{CC}` counters per event. `/api/admin/analytics/overview` returns `categories[]` and `countries[]`. Frontend request() sends `x-country` header from `veriscan_country` storage; /products/lookup passes it into scan analytics.
**Admin profile with OTP self-service** — new `/api/admin/profile` (GET), `/change-email/start`+`/confirm` (two OTPs — one to current email, one to new), `/change-phone/start`+`/confirm` (single OTP to admin email — no SMS gateway integrated). Frontend screen `/admin/profile` with 3 sections.
**Admin covers all critical ops** (verified): users list/suspend/reactivate/reset, country pricing, promocodes (create/deactivate), support tickets, data reports, payments+refund, duplicates (exact+fuzzy), contributions queue, anonymous analytics with CSV export, admin profile & security. Seeded admin email: `dhruvpateld230@gmail.com`.
**Test results**: 20/20 new + 44/44 regression = 116/116 functional pass (77+19+20). SMS OTP for phone change is future work — requires Twilio/MSG91 integration.

### Version 1.0 — Launch checklist
- ✅ 3-month free trial with 7-day reminder email
- ✅ Legal v2.0.0 (no-refund, no-cancellation, AS-IS, arbitration in Mumbai, jurisdiction carve-outs)
- ✅ Razorpay for India (order + subscription + promo + refund + webhook)
- ✅ Stripe for non-India (built + gated; requires real STRIPE_API_KEY to fire)
- ✅ Anonymous analytics with category/country/product/retailer breakdown + monthly email + CSV export
- ✅ Admin dashboard: users, pricing, promocodes, support, refunds, duplicates (fuzzy), analytics, admin profile
- ✅ Live e-commerce comparison (7 retailers, hybrid deep-links + optional QuickCommerce/Apify)
- ✅ OCR contribution flow (Claude Sonnet 4.6 via Emergent)
- ✅ Regulatory badges (FSSAI/FDA/PETA/Vegan Society etc.)
- ⏭ Stripe live key → drop into backend/.env
- ⏭ SMS OTP for admin phone verification → add Twilio or MSG91 keys

## Launch offer (2026-09-30)
**Goal:** celebrate launch — every new download gets **1 year free, unlimited scans, no payment method required**; eligibility window open **3 months** from launch, admin-extendable.
- `core/settings.py` — `app_settings.launch_offer` doc `{active, launched_at, eligibility_ends_at, free_days:365}`; seeded on startup (window = launch + 90 days). `trial_days_for_signup()` returns 365 while offer live, else 90.
- `routes/launch.py` — `GET /api/launch-offer` (public), `GET/PUT /api/admin/launch-offer` (admin: toggle active, extend eligibility_ends_at, set free_days 1–3650).
- Registration (`routes/auth.py`) sets `trial_expires_at = now + trial_days_for_signup()`.
- Frontend: `src/components/launch-welcome.tsx` first-launch celebratory modal (flag `veriscan_launch_welcome_seen`); Home banner while live; admin screen `/admin/launch-offer` (toggle, +1/+3/+6mo extend, end-now, free-duration stepper + presets).
- Verified: new signup → 365-day trial; admin GET/PUT ok; non-admin 401; welcome screen renders.

## Security audit remediation (2026-09-30) — 20/20 verified
- **SEC-001 CRITICAL (fixed)**: `JWT_SECRET` now loaded strictly from env with fail-fast on weak/missing/default (`core/config.py`); strong secret added to `backend/.env`. Old sessions invalidated (users re-login once).
- **SEC-002 MEDIUM (fixed)**: CSV formula-injection neutralized in `/admin/analytics/export` via `_csv_safe()` (`routes/analytics.py`).
- **Hardening**: login brute-force account lockout (5 fails → 15-min lock) + constant-time bcrypt dummy hash (`routes/auth.py`, `auth_throttle` collection); password-reset OTP now bcrypt-hashed at rest, single-use, max-5-attempts, 10-min expiry (`core/otp.py`, auth + admin send-reset); CORS `allow_credentials=False` (`server.py`); admin user-search regex `re.escape`d; guest-id upgraded to high-entropy token (`_layout.tsx`); removed unused `/payments/subscription-session` shadow endpoint. Testing agent: 20/20 pass, no regressions (`test_reports/iteration_10.json`).
