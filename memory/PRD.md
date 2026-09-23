# VeriScan — PRD & State

## Vision
AI product-health & ingredient intelligence app for global users. Barcode scanner, ingredient-level toxicity (0–100), personalized match, watchlist, OCR fallback, admin backoffice.

## Stack
- **Frontend**: Expo Router (React Native), React Query, Expo Camera, Expo Image
- **Backend**: FastAPI + MongoDB (Motor)
- **LLM**: Claude Sonnet 4.6 via Emergent LLM Key (OCR extraction on contribution photos)
- **Email**: Emergent-managed Resend (password reset OTP, watchlist alerts, admin reset codes)
- **External data**: Open Food Facts + Open Beauty Facts
- **Payments** (planned Iter 3): Razorpay (IN) + Stripe with Apple Pay (US/CA/EU/GB/AE/AU/NZ) + PPP pricing table already wired

## Shipped (Iter 1 + 2)
### User-facing
- Onboarding preferences (dietary, health targets, ingredient sensitivities)
- Guest mode with 3 free scans (device fingerprint in secure storage)
- **T&C + Privacy Policy acceptance is mandatory on signup**; content served from `/api/legal/terms` and `/api/legal/privacy`, versioned
- Email+password auth (bcrypt); minimal PII (only email needed)
- **Password reset via 6-digit OTP** (10-min expiry, delivered by Resend)
- Real product lookup via Open Food Facts / Open Beauty Facts with ingredient scoring
- Nutrition per 100 g extracted and displayed
- 0–100 safety spectrum (Red / Orange / Yellow / Light Green / Emerald) with color-coded chips
- Personalized Match % — penalizes sensitivity violations
- Ingredient bottom sheet with function, bodily impact, regulatory context
- Nutrition per 100 g + Price benchmark card
- **Better-For-You** carousel — 3 cleaner alternatives in same category
- Product detail: watch-heart, report-flag, contribute-correction
- **Watchlist** — save any product; email alert when a cleaner alt lands
- **Notifications** (in-app inbox)
- Scan history (registered + guest, migrated on signup)
- **Support tickets** — user files ticket + sees status/response
- **Misinformation reports** on any product
- Contribution flow (5-step guided photo capture) — photos sent to Claude Sonnet 4.6 which returns structured ingredients + nutrition JSON
- Legal screens (T&C + Privacy Policy readable in-app)

### Admin (role-based, gated by `role === "admin"`)
- Admin dashboard with counts (users, suspended, open tickets, open reports, products, pending contributions)
- Users list with **masked emails**, suspend/reactivate with reason, send-reset-code
- Support tickets: filter by status, add internal note, transition to in_progress/resolved/closed
- Data reports: same filter + resolution workflow
- Country pricing editor (8 countries seeded: IN, US, CA, EU, GB, AE, AU, NZ)
- Promo codes: create (percent / flat / free_scans) with max redemptions, per-country whitelist; deactivate
- **Admin cannot**: see plaintext passwords, edit user preferences/history, hard-delete accounts (soft-suspend only), or unmask user emails

### Legal-safety features
- Terms of Service + Privacy Policy templates (v1.0.0) explicitly disclaim medical advice, cover IP, indemnity, UGC licensing, arbitration
- Ingredient/scoring outputs are labelled as informational, never medical
- All scan requests trust server-side entitlement counter (no client-side quota)
- Admin actions logged in DB (support_tickets, reports, entitlements records)
- Email guardrails enforced via `_assert_safe_email` — blocks credential harvesting, non-https links, form fields, homoglyph impersonation

## Pending (Iter 3)
- Razorpay checkout (India)
- Stripe with Apple Pay for US/CA/EU/GB/AE/AU/NZ
- Wire promo code redemption at checkout
- Product image caching via Emergent Object Storage

## API summary
- `POST /api/auth/{register,login,forgot-password,reset-password}`
- `GET/PUT /api/profile` · `GET /api/entitlements`
- `GET /api/legal/terms|privacy`
- `GET /api/products/lookup?barcode=` · `/api/products/alternatives?barcode=` · `/api/history`
- `POST /api/contributions` (calls Claude for OCR when images attached)
- `GET/POST/DELETE /api/watchlist[/{barcode}]` · `GET /api/notifications` · `POST /api/notifications/{id}/read`
- `POST /api/support` · `GET /api/support/mine` · `POST /api/reports`
- `GET /api/plans?country=` · `GET /api/promocodes/{code}`
- `GET /api/admin/{overview,users,pricing,promocodes,support,reports,contributions}`
- `POST /api/admin/users/{id}/{suspend,reactivate,send-reset}`
- `PUT /api/admin/{pricing,support,reports}/{id_or_country}`
- `POST /api/admin/promocodes` · `DELETE /api/admin/promocodes/{code}`

## Testing status
- Iter 2 backend regression: **22/22 pass** (JUnit at `/app/test_reports/pytest/iteration_4.xml`)
- Test credentials in `/app/memory/test_credentials.md`

## Notes for next iteration (payments)
- `country_pricing` collection is the single source of truth — the admin panel already edits it
- Each row includes `provider` field ('razorpay' or 'stripe') so the checkout screen can pick the right SDK
- Multi-currency amounts already in place; iter 3 just needs SDK wiring + Apple Pay merchant setup on native build
