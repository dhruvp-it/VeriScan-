import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  Linking, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const FALLBACK_PLANS = {
  launch_promo: true, country: "IN", currency: "INR", symbol: "₹", provider: "razorpay",
  scan_intro: { price: 5, label: "First 20 purchased scans" },
  scan_standard: { price: 15, label: "After introductory credits" },
  subscriptions: [
    { id: "monthly", price: 72, regular_price: 180, period: "month" },
    { id: "yearly", price: 450, regular_price: 1500, period: "year" },
  ],
};

export default function PlansRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [promo, setPromo] = useState("");
  const [promoValid, setPromoValid] = useState<{ discount: number; kind?: string | null; bonus?: number } | null>(null);
  const [promoError, setPromoError] = useState("");
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: () => api.plans(), initialData: FALLBACK_PLANS });

  const applyPromo = async () => {
    setPromoError(""); setPromoValid(null);
    if (!promo.trim()) return;
    try {
      // Preview against a nominal ₹100 base so user sees discount kind
      const preview = await api.promocodePreview(promo.trim(), 10000);
      setPromoValid({ discount: preview.discount, kind: preview.kind, bonus: preview.bonus_credits });
    } catch (e) {
      setPromoError((e as Error).message);
    }
  };

  const goBuy = (credits: number, tier: "intro" | "standard") => {
    router.push({
      pathname: "/checkout",
      params: { credits: String(credits), tier, promo: promoValid ? promo.trim() : "" },
    });
  };

  const goSubscribe = (plan: "monthly" | "yearly") => {
    router.push({
      pathname: "/checkout",
      params: { kind: "subscription", plan, promo: promoValid ? promo.trim() : "" },
    });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Pressable testID="plans-back" onPress={() => router.back()} style={styles.backRow}>
          <Ionicons name="arrow-back" size={21} color={colors.onSurface} />
          <Text style={styles.backText}>Back</Text>
        </Pressable>
        <Text style={styles.eyebrow}>SCAN MORE, WORRY LESS</Text>
        <Text style={styles.title}>Choose your clean scan plan.</Text>
        <Text style={styles.body}>
          New account? You&apos;re on 3 months of unlimited scans on the house. After that, subscribe or buy credits.
        </Text>

        <View style={styles.promoRow}>
          <TextInput
            testID="plans-promo-input"
            value={promo}
            onChangeText={(v) => { setPromo(v.toUpperCase()); setPromoValid(null); setPromoError(""); }}
            placeholder="Promo code"
            autoCapitalize="characters"
            placeholderTextColor={colors.muted}
            style={styles.promoInput}
          />
          <Pressable testID="plans-promo-apply" onPress={applyPromo} style={styles.promoButton}>
            <Text style={styles.promoButtonText}>Apply</Text>
          </Pressable>
        </View>
        {promoValid ? (
          <Text style={styles.promoSuccess} testID="plans-promo-success">
            Applied. {promoValid.kind === "free_scans"
              ? `+${promoValid.bonus} free scans on your next purchase`
              : `Discount will apply at checkout (${promoValid.kind ?? "code"})`}
          </Text>
        ) : promoError ? (
          <Text style={styles.promoError} testID="plans-promo-error">{promoError}</Text>
        ) : null}

        <View style={styles.card}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>LAUNCH PROMO · YEAR 1</Text>
          </View>
          <Text style={styles.cardTitle}>VeriScan Plus</Text>
          {plans.subscriptions.map((plan) => (
            <View key={plan.id} style={styles.planRow} testID={`plan-${plan.id}`}>
              <View>
                <Text style={styles.planName}>{plan.id === "yearly" ? "Annual" : "Monthly"}</Text>
                <Text style={styles.muted}>Unlimited scans</Text>
              </View>
              <View style={styles.planPriceBox}>
                <Text style={styles.planPrice}>{plans.symbol}{plan.price}</Text>
                <Text style={styles.strike}>{plans.symbol}{plan.regular_price}/{plan.period}</Text>
              </View>
              <Pressable
                testID={`plan-choose-${plan.id}`}
                onPress={() => goSubscribe(plan.id as "monthly" | "yearly")}
                style={styles.smallButton}
              >
                <Text style={styles.smallButtonText}>Choose</Text>
              </Pressable>
            </View>
          ))}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Pay per scan</Text>
          <View style={styles.tierRow}>
            <View style={styles.tierPill}>
              <Text style={styles.tierNumber}>{plans.symbol}{plans.scan_intro.price}</Text>
              <Text style={styles.muted}>{plans.scan_intro.label}</Text>
              <Pressable testID="buy-intro-credits" onPress={() => goBuy(10, "intro")} style={styles.buyButton}>
                <Text style={styles.buyButtonText}>Buy 10</Text>
              </Pressable>
            </View>
            <View style={styles.tierPill}>
              <Text style={styles.tierNumber}>{plans.symbol}{plans.scan_standard.price}</Text>
              <Text style={styles.muted}>{plans.scan_standard.label}</Text>
              <Pressable testID="buy-standard-credits" onPress={() => goBuy(10, "standard")} style={styles.buyButton}>
                <Text style={styles.buyButtonText}>Buy 10</Text>
              </Pressable>
            </View>
          </View>
          <Text style={styles.disclaimer}>
            {plans.provider === "razorpay"
              ? "India pricing paid via Razorpay · UPI, cards, netbanking & wallets."
              : "Non-India regions are free for now — admin will enable pricing later."}
          </Text>
        </View>

        <Pressable onPress={() => Linking.openURL("https://razorpay.com/")} testID="plans-secure-note" style={styles.secureRow}>
          <Ionicons name="shield-checkmark-outline" size={16} color={colors.muted} />
          <Text style={styles.muted}>Payments are secured by Razorpay</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 40 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, marginBottom: 12 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 28, fontWeight: "800", marginTop: 10 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 22, marginTop: 12, marginBottom: 20 },
  promoRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  promoInput: { flex: 1, minHeight: 44, borderRadius: 12, backgroundColor: colors.surfaceTertiary, paddingHorizontal: 12, color: colors.onSurface, fontSize: 14 },
  promoButton: { minWidth: 76, minHeight: 44, borderRadius: 12, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 14 },
  promoButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
  promoSuccess: { color: colors.brandPrimary, fontSize: 12, marginBottom: 12 },
  promoError: { color: colors.error, fontSize: 12, marginBottom: 12 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 22, padding: 20, marginBottom: 16 },
  badge: { alignSelf: "flex-start", backgroundColor: colors.brandSecondary, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6, marginBottom: 14 },
  badgeText: { color: colors.onBrandSecondary, fontSize: 10, fontWeight: "900", letterSpacing: 0.7 },
  cardTitle: { color: colors.onSurface, fontSize: 20, fontWeight: "800" },
  planRow: { minHeight: 72, borderTopWidth: 1, borderTopColor: colors.divider, marginTop: 12, paddingTop: 14, flexDirection: "row", alignItems: "center", gap: 12 },
  planName: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  muted: { color: colors.muted, fontSize: 13 },
  planPriceBox: { alignItems: "flex-end", marginLeft: "auto" },
  planPrice: { color: colors.brandPrimary, fontSize: 20, fontWeight: "900" },
  strike: { color: colors.muted, fontSize: 12, textDecorationLine: "line-through" },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 13 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
  tierRow: { flexDirection: "row", gap: 10, marginTop: 12 },
  tierPill: { flex: 1, backgroundColor: colors.surface, borderRadius: 16, padding: 14 },
  tierNumber: { color: colors.brandPrimary, fontSize: 22, fontWeight: "900" },
  buyButton: { minHeight: 40, borderRadius: 12, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 14, marginTop: 10 },
  buyButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 17, marginTop: 14, fontStyle: "italic" },
  secureRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 12 },
}));
