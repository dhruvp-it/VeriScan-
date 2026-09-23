import Constants from "expo-constants";

import { storage } from "@/src/utils/storage";

const configuredUrl = Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL;
const API_ROOT = `${String(configuredUrl ?? "").replace(/\/$/, "")}/api`;
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
export type Product = {
  id: string; barcode: string; name: string; brand: string; category: string; description: string;
  dietary_type: string; origin_country: string; manufactured_in: string; first_detected_year: number;
  price_tier: string; target_age_group: string; primary_region: string; serving_size: string; price_inr: number;
  image_url: string | null; labels: string[];
  ingredients: Ingredient[]; retailers: Retailer[];
  overall_health_score: number; personal_match: number;
  nutrition_per_100g: Nutrition | null;
  scan?: { remaining: number | null; source: string };
};
export type Entitlement = { registered: boolean; free_remaining: number; wallet: number; subscribed: boolean; email: string | null };
export type Profile = { email: string | null; preferences: Preferences; registered: boolean };

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
  register: (email: string, password: string) =>
    request<{ token: string; user: { id: string; email: string; preferences: Preferences } }>(
      "/auth/register", { method: "POST", body: JSON.stringify({ email, password }) },
    ),
  login: (email: string, password: string) =>
    request<{ token: string; user: { id: string; email: string; preferences: Preferences } }>(
      "/auth/login", { method: "POST", body: JSON.stringify({ email, password }) },
    ),
  profile: () => request<Profile>("/profile"),
  saveProfile: (preferences: Preferences) => request<Preferences>("/profile", { method: "PUT", body: JSON.stringify(preferences) }),
  entitlements: () => request<Entitlement>("/entitlements"),
  lookup: (barcode: string) => request<Product>(`/products/lookup?barcode=${encodeURIComponent(barcode)}`),
  history: () => request<{ product: Product; scanned_at: string }[]>("/history"),
  plans: () => request<{
    launch_promo: boolean;
    scan_intro: { price: number; label: string };
    scan_standard: { price: number; label: string };
    subscriptions: { id: string; price: number; regular_price: number; period: string }[];
  }>("/plans"),
  subscription: (plan: string) => request<{ url: string }>("/payments/subscription-session", { method: "POST", body: JSON.stringify({ plan }) }),
  contribute: (payload: { barcode: string; product_name?: string; notes?: string; images: string[] }) =>
    request<{ status: string }>("/contributions", { method: "POST", body: JSON.stringify(payload) }),
};
