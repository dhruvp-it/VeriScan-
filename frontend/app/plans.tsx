import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const FALLBACK_PLANS = {
  launch_promo: true,
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
  const { data: plans } = useQuery({
    queryKey: ["plans"],
    queryFn: () => api.plans(),
    initialData: FALLBACK_PLANS,
  });

  const subscribe = async (plan: string) => {
    try {
      const result = await api.subscription(plan);
      const { Linking } = await import("react-native");
      await Linking.openURL(result.url);
    } catch {
      // Stripe not configured yet in preview — silently ignore.
    }
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
          Start with five complimentary scans every month. Upgrade any time for unlimited ingredient intelligence.
        </Text>

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
                onPress={() => subscribe(plan.id)}
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
              <Pressable
                testID="buy-intro-credits"
                onPress={() => router.push({ pathname: "/checkout", params: { credits: "10", tier: "intro" } })}
                style={styles.buyButton}
              >
                <Text style={styles.buyButtonText}>Buy 10</Text>
              </Pressable>
            </View>
            <View style={styles.tierPill}>
              <Text style={styles.tierNumber}>{plans.symbol}{plans.scan_standard.price}</Text>
              <Text style={styles.muted}>{plans.scan_standard.label}</Text>
              <Pressable
                testID="buy-standard-credits"
                onPress={() => router.push({ pathname: "/checkout", params: { credits: "10", tier: "standard" } })}
                style={styles.buyButton}
              >
                <Text style={styles.buyButtonText}>Buy 10</Text>
              </Pressable>
            </View>
          </View>
          <Text style={styles.disclaimer}>
            {plans.provider === "razorpay"
              ? "India pricing paid via Razorpay · UPI, cards, netbanking & wallets."
              : "Paid via Stripe · Apple Pay available on native iOS builds."}
          </Text>
        </View>
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
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 22, marginTop: 12, marginBottom: 22 },
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
}));
