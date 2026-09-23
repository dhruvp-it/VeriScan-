import Constants from "expo-constants";

import { storage } from "@/src/utils/storage";

const configuredUrl = Constants.expoConfig?.extra?.backendUrl ?? process.env.EXPO_PUBLIC_BACKEND_URL;
const API_ROOT = `${String(configuredUrl ?? "").replace(/\/$/, "")}/api`;
export const TOKEN_KEY = "veriscan_auth_token";

export type Preferences = { dietary: string[]; targets: string[]; sensitivities: string[] };
export type Ingredient = { name: string; score: number; hazard: string; function: string; effect: string };
export type Product = {
  id: string; barcode: string; name: string; brand: string; category: string; description: string;
  dietary_type: string; origin_country: string; manufactured_in: string; first_detected_year: number;
  price_tier: string; target_age_group: string; primary_region: string; serving_size: string; price_inr: number;
  ingredients: Ingredient[]; retailers: { name: string; price: number; url: string }[];
  overall_health_score: number; personal_match: number; scan?: { remaining: number | null; source: string };
};

type RequestOptions = RequestInit & { guestId?: string };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = await storage.secureGet(TOKEN_KEY, "");
  const guestId = options.guestId ?? await storage.secureGet("veriscan_guest_id", "");
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
  register: (email: string, password: string) => request<{ token: string; user: { id: string; email: string; preferences: Preferences } }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) => request<{ token: string; user: { id: string; email: string; preferences: Preferences } }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  saveProfile: (preferences: Preferences) => request<Preferences>("/profile", { method: "PUT", body: JSON.stringify(preferences) }),
  entitlements: () => request<{ registered: boolean; free_remaining: number; wallet: number; subscribed: boolean }>("/entitlements"),
  lookup: (barcode: string) => request<Product>(`/products/lookup?barcode=${encodeURIComponent(barcode)}`),
  history: () => request<{ product: Product; scanned_at: string }[]>("/history"),
  plans: () => request<{ launch_promo: boolean; scan_intro: { price: number; label: string }; scan_standard: { price: number; label: string }; subscriptions: { id: string; price: number; regular_price: number; period: string }[] }>("/plans"),
  subscription: (plan: string) => request<{ url: string }>("/payments/subscription-session", { method: "POST", body: JSON.stringify({ plan }) }),
  contribute: (payload: { barcode: string; product_name?: string; notes?: string; images: string[] }) => request<{ status: string }>("/contributions", { method: "POST", body: JSON.stringify(payload) }),
};
