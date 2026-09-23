# VeriScan — Product Requirements & State

## Vision
AI product-health & ingredient intelligence app. Real-time barcode scanning, ingredient-level toxicity analysis (0–100), personalized health matching, price benchmark, and cleaner-alternative discovery.

## Target platform
Expo React Native mobile app (iOS 17+, Android). Preview served via Expo web + QR code.

## Tech stack
- Frontend: Expo Router (file-based routing) + React Query + Expo Camera
- Backend: FastAPI (Python)
- DB: MongoDB (Motor async driver) — problem statement mentioned Supabase/Postgres, but pod environment mandates MongoDB
- Ingredient safety: keyword knowledge base of ~90 entries mapped to 0–100 scores + hazard tiers
- External data: Open Food Facts + Open Beauty Facts public APIs
- Payments (planned): Razorpay for India, Stripe for USA/CAD/EU/UAE/AU/NZ with Apple Pay, PPP-based currency conversion

## App structure (Expo Router)
```
app/
  _layout.tsx            Stack + providers (QueryClient, KeyboardProvider, SafeAreaProvider)
  index.tsx              Splash — redirect to onboarding or (tabs)
  onboarding.tsx         Preference collection (dietary, targets, sensitivities)
  preferences.tsx        Editable clean profile (modal)
  plans.tsx              Subscription / pay-per-scan plans (modal)
  (tabs)/
    _layout.tsx          Bottom tabs (Home, Scan, History, Profile)
    index.tsx            Home dashboard
    scan.tsx             Camera + manual barcode lookup
    history.tsx          Scan history
    profile.tsx          Account + wallet + sign in
  product/[barcode].tsx  Product detail (hero, score, nutrition, ingredients, retailers)
  contribute/[barcode].tsx  5-step community capture (stub)
```

## Shipped features
- ✅ Onboarding preference collection (dietary, health targets, ingredient sensitivities)
- ✅ Guest mode with 3 free scans tracked via secure `x-guest-id` header
- ✅ Compulsory registration gate after quota
- ✅ Email/password auth (JWT, bcrypt)
- ✅ 5 free monthly scans for registered users (reset monthly)
- ✅ Live camera barcode scanning (EAN-13, EAN-8, UPC-A/E) + torch + manual entry
- ✅ Real product lookup via Open Food Facts / Open Beauty Facts
- ✅ Ingredient-level safety scoring (0–100) with 5 hazard tiers and color spectrum
- ✅ Nutrition per 100g extracted and displayed
- ✅ Personalized Match % — penalizes when sensitivities are violated, boosts when preferences aligned
- ✅ Product detail view with hero header, score ring, nutrition card, price benchmark, ingredient breakdown (sorted by risk), retailer list
- ✅ Ingredient bottom sheet with function, bodily impact, regulatory context
- ✅ Scan history with quick reopen
- ✅ Guest → registered history migration on signup
- ✅ Editable clean profile (Preferences modal)
- ✅ Contribution flow (5-step guided capture, submits to community verification queue)
- ✅ Plans / subscription screen with launch-promo pricing (₹72/mo, ₹450/yr, ₹5 intro + ₹15 standard per scan)

## Pending / Iteration 2 & 3
- 🔨 OCR fallback: extract nutrition + ingredients + certification badges from photos via Claude Sonnet 4.6
- 🔨 Stripe/Razorpay checkout UI with Apple Pay (native build only)
- 🔨 Multi-currency PPP pricing (USA, CAD, EU, UAE, AU, NZ, IN)
- 🔨 Better For You alternatives carousel on product detail
- 🔨 Product image caching via Emergent Object Storage

## Key API endpoints
- `POST /api/auth/register` – Body `{email,password}`; header `x-guest-id` migrates guest data
- `POST /api/auth/login`
- `GET /api/entitlements` – Returns `{registered, free_remaining, wallet, subscribed, email}`
- `GET /api/profile` / `PUT /api/profile` – Preferences
- `GET /api/products/lookup?barcode=…` – Consumes 1 scan on success (404 does NOT consume)
- `GET /api/history` – Sorted desc by scanned_at
- `POST /api/contributions` – Enqueues a `pending_verification` record
- `GET /api/plans`
- `POST /api/payments/scan-intent` / `subscription-session` (503 until payment key configured)

## Database collections (MongoDB)
- `users` – `{id, email, password_hash, preferences, created_at}`
- `entitlements` – `{user_id, free_month, free_used, purchased_balance, intro_used, subscribed}`
- `guests` – `{guest_id, used, preferences}`
- `products` – `{barcode, name, brand, category, ingredients_text, ingredients[], nutrition_per_100g, image_url, ...}`
- `history` – `{id, user_id, product, scanned_at}`
- `contributions` – `{id, barcode, product_name, notes, images[], status, submitted_by, created_at}`
- `payments` – `{stripe_payment_intent_id, user_id, quantity, status, created_at}`

## Testing status
Iteration 3 backend regression: 13/13 pass after fix. Personalized match now correctly PENALIZES sensitivity violations (fragrance in a fragrance-free profile drops match from 66 → 37). 404 lookups no longer consume a scan.
