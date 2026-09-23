import Constants from "expo-constants";

import { storage } from "@/src/utils/storage";

const configuredUrl = Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL;
const API_ROOT = `${String(configuredUrl ?? "").replace(/\/$/, "")}/api`;
export const BACKEND_URL = String(configuredUrl ?? "").replace(/\/$/, "");
export const TOKEN_KEY = "veriscan_auth_token";
export const GUEST_KEY = "veriscan_guest_id";

export type Preferences = { dietary: string[]; targets: string[]; sensitivities: string[] };
export type Ingredient = { name: string; score: number; hazard: string; function: string; effect: string };
export type Nutrition = {
  energy_kcal: number | null; protein_g: number | null; carbohydrates_g: number | null;
  sugars_g: number | null; fat_g: number | null; saturated_fat_g: number | null;
  fiber_g: number | null; salt_g: number | null;
};
export type Retailer = { name: string; price: number; url: string };
export type Badge = { id: string; label: string; region: string };
export type CompareProduct = {
  retailer: string; title: string; url: string;
  price_inr: number | null; mrp_inr: number | null;
  image: string | null; rating: number | null; available: boolean | null;
};
export type DeepLink = { id: string; name: string; icon: string; color: string; url: string };
export type CompareResponse = {
  query: string; live_enabled: boolean; fetched_at: number;
  products: CompareProduct[]; deep_links: DeepLink[];
};

export type Product = {
  id: string; barcode: string; name: string; brand: string; category: string; description: string;
  dietary_type: string; origin_country: string; manufactured_in: string; first_detected_year: number;
  price_tier: string; target_age_group: string; primary_region: string; serving_size: string; price_inr: number;
  image_url: string | null; labels: string[];
  ingredients: Ingredient[]; retailers: Retailer[];
  overall_health_score: number; personal_match: number;
  nutrition_per_100g: Nutrition | null;
  badges?: Badge[];
  scan?: { remaining: number | null; source: string };
};
export type Entitlement = {
  registered: boolean; free_remaining: number; wallet: number; subscribed: boolean;
  email: string | null; role: string;
  trial_active: boolean; trial_days_remaining: number;
};
export type Profile = { email: string | null; preferences: Preferences; registered: boolean; role: string };
export type Legal = { version: string; effective: string; content: string };
export type PlansResponse = {
  launch_promo: boolean; country: string; currency: string; symbol: string; provider: string;
  scan_intro: { price: number; label: string };
  scan_standard: { price: number; label: string };
  subscriptions: { id: string; price: number; regular_price: number; period: string }[];
};
export type WatchlistItem = { barcode: string; added_at: string; product: Product };
export type NotificationItem = {
  id: string; kind: string; title: string; body: string;
  product_barcode?: string; read: boolean; created_at: string;
};
export type SupportTicket = {
  id: string; subject: string; message: string; category: string;
  status: string; admin_note: string | null; created_at: string; updated_at: string;
  user_email?: string; user_id?: string; guest_id?: string;
};
export type Report = {
  id: string; barcode: string; reason: string; status: string;
  admin_note: string | null; created_at: string; updated_at: string;
};
export type AdminUser = { id: string; email_masked: string; suspended: boolean; created_at: string; terms_version: string };
export type CountryPricing = {
  country: string; currency: string; symbol: string;
  scan_intro: number; scan_standard: number;
  monthly: number; yearly: number; monthly_regular: number; yearly_regular: number; provider: string;
};
export type Promocode = {
  code: string; kind: string; value: number; max_redemptions: number;
  countries: string[]; expires_at: string | null; active: boolean; redemptions: number;
};

type RequestOptions = RequestInit & { guestId?: string };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = await storage.secureGet(TOKEN_KEY, "");
  const guestId = options.guestId ?? await storage.secureGet(GUEST_KEY, "");
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (guestId) headers.set("x-guest-id", guestId);
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : body.detail?.message ?? message;
    } catch { /* keep friendly fallback */ }
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

export const api = {
  // Auth
  register: (email: string, password: string, terms: string, privacy: string) =>
    request<{ token: string; user: { id: string; email: string; preferences: Preferences; role: string } }>(
      "/auth/register",
      { method: "POST", body: JSON.stringify({ email, password, accepted_terms_version: terms, accepted_privacy_version: privacy }) },
    ),
  login: (email: string, password: string) =>
    request<{ token: string; user: { id: string; email: string; preferences: Preferences; role: string } }>(
      "/auth/login", { method: "POST", body: JSON.stringify({ email, password }) },
    ),
  forgotPassword: (email: string) => request<{ status: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (email: string, otp: string, newPassword: string) =>
    request<{ status: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ email, otp, new_password: newPassword }) }),

  // Profile
  profile: () => request<Profile>("/profile"),
  saveProfile: (preferences: Preferences) => request<Preferences>("/profile", { method: "PUT", body: JSON.stringify(preferences) }),
  entitlements: () => request<Entitlement>("/entitlements"),

  // Legal
  terms: () => request<Legal>("/legal/terms"),
  privacy: () => request<Legal>("/legal/privacy"),

  // Products
  lookup: (barcode: string) => request<Product>(`/products/lookup?barcode=${encodeURIComponent(barcode)}`),
  compare: (barcode: string) => request<CompareResponse>(`/products/compare?barcode=${encodeURIComponent(barcode)}`),
  alternatives: (barcode: string) => request<Product[]>(`/products/alternatives?barcode=${encodeURIComponent(barcode)}`),
  history: () => request<{ product: Product; scanned_at: string }[]>("/history"),
  contribute: (payload: { barcode: string; product_name?: string; brand?: string; notes?: string; images: string[] }) =>
    request<{ status: string; contribution_id: string; product?: Product; ocr_error?: string }>("/contributions", { method: "POST", body: JSON.stringify(payload) }),

  // Watchlist & notifications
  watchlist: () => request<WatchlistItem[]>("/watchlist"),
  watchlistAdd: (barcode: string) => request<{ status: string }>(`/watchlist/${encodeURIComponent(barcode)}`, { method: "POST" }),
  watchlistRemove: (barcode: string) => request<{ status: string }>(`/watchlist/${encodeURIComponent(barcode)}`, { method: "DELETE" }),
  notifications: () => request<NotificationItem[]>("/notifications"),
  markRead: (id: string) => request<{ status: string }>(`/notifications/${id}/read`, { method: "POST" }),

  // Support / reports
  submitSupport: (subject: string, message: string, category: string = "general") =>
    request<{ id: string; status: string; created_at: string }>("/support", { method: "POST", body: JSON.stringify({ subject, message, category }) }),
  mySupport: () => request<SupportTicket[]>("/support/mine"),
  submitReport: (barcode: string, reason: string) => request<{ id: string; status: string }>("/reports", { method: "POST", body: JSON.stringify({ barcode, reason }) }),

  // Plans & payments
  plans: (country?: string) => request<PlansResponse>(`/plans${country ? `?country=${country}` : ""}`),
  promocode: (code: string, country?: string) => request<Promocode>(`/promocodes/${encodeURIComponent(code)}${country ? `?country=${country}` : ""}`),
  subscription: (plan: string, country?: string) => request<{ url: string }>("/payments/subscription-session", { method: "POST", body: JSON.stringify({ plan, country }) }),
  razorpayOrder: (credits: number, tier: "intro" | "standard", promoCode?: string) =>
    request<{ key_id: string; order_id: string; amount: number; base_amount: number; discount: number; bonus_credits: number; currency: string; description: string }>(
      "/payments/razorpay/order", { method: "POST", body: JSON.stringify({ credits, tier, promo_code: promoCode }) },
    ),
  razorpaySubscription: (plan: "monthly" | "yearly", promoCode?: string) =>
    request<{ key_id: string; order_id: string; amount: number; base_amount: number; discount: number; currency: string; description: string }>(
      "/payments/razorpay/subscription", { method: "POST", body: JSON.stringify({ plan, promo_code: promoCode }) },
    ),
  promocodePreview: (code: string, basePaise: number, country: string = "IN") =>
    request<{ amount: number; discount: number; bonus_credits: number; kind: string | null }>(
      "/promocodes/preview", { method: "POST", body: JSON.stringify({ code, base_paise: basePaise, country }) },
    ),

  // Admin
  adminOverview: () => request<{ users: number; suspended: number; open_tickets: number; open_reports: number; products: number; contributions_pending: number }>("/admin/overview"),
  adminUsers: (q?: string) => request<AdminUser[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  adminSuspend: (id: string, reason: string) => request<{ status: string }>(`/admin/users/${id}/suspend`, { method: "POST", body: JSON.stringify({ reason }) }),
  adminReactivate: (id: string) => request<{ status: string }>(`/admin/users/${id}/reactivate`, { method: "POST" }),
  adminSendReset: (id: string) => request<{ status: string }>(`/admin/users/${id}/send-reset`, { method: "POST" }),
  adminPricing: () => request<CountryPricing[]>("/admin/pricing"),
  adminPricingUpdate: (country: string, payload: CountryPricing) =>
    request<{ status: string }>(`/admin/pricing/${country}`, { method: "PUT", body: JSON.stringify(payload) }),
  adminPromos: () => request<Promocode[]>("/admin/promocodes"),
  adminPromoCreate: (payload: Omit<Promocode, "redemptions">) =>
    request<{ status: string }>("/admin/promocodes", { method: "POST", body: JSON.stringify(payload) }),
  adminPromoDeactivate: (code: string) => request<{ status: string }>(`/admin/promocodes/${encodeURIComponent(code)}`, { method: "DELETE" }),
  adminSupport: (status?: string) => request<SupportTicket[]>(`/admin/support${status ? `?status=${status}` : ""}`),
  adminSupportUpdate: (id: string, status: string, adminNote?: string) =>
    request<{ status: string }>(`/admin/support/${id}`, { method: "PUT", body: JSON.stringify({ status, admin_note: adminNote }) }),
  adminReports: (status?: string) => request<Report[]>(`/admin/reports${status ? `?status=${status}` : ""}`),
  adminReportUpdate: (id: string, status: string, adminNote?: string) =>
    request<{ status: string }>(`/admin/reports/${id}`, { method: "PUT", body: JSON.stringify({ status, admin_note: adminNote }) }),
  adminPayments: () => request<{ razorpay_order_id: string; razorpay_payment_id?: string; user_id: string; kind: string; credits: number; bonus_credits?: number; amount_paise: number; created_at: number; refunded?: boolean; refund_id?: string; plan?: string; promo_code?: string | null }[]>("/admin/payments"),
  adminRefund: (paymentId: string, reason: string) =>
    request<{ refund_id: string; status: string; ticket_id: string }>("/admin/refund", { method: "POST", body: JSON.stringify({ payment_id: paymentId, reason }) }),
  adminDuplicates: () => request<{ _id: { name: string; brand: string }; products: { barcode: string; name: string; brand: string; category: string }[]; count: number }[]>("/admin/duplicates"),
  adminMerge: (primary: string, dupes: string[]) =>
    request<{ merged: number; primary_barcode: string }>("/admin/products/merge", { method: "POST", body: JSON.stringify({ primary_barcode: primary, duplicate_barcodes: dupes }) }),
  adminProductBadges: (barcode: string, badges: { id: string; label: string; region: string }[]) =>
    request<{ status: string }>(`/admin/products/${barcode}/badges`, { method: "PUT", body: JSON.stringify({ badges_extra: badges, badges_override: null }) }),
};
