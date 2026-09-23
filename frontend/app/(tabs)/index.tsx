import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useEntitlement } from "@/src/hooks/use-entitlement";
import { makeStyles, useTheme } from "@/src/theme";

export default function HomeTab() {
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { data: entitlement } = useEntitlement();

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.eyebrow}>YOUR PRODUCT COMPANION</Text>
            <Text style={styles.title}>Scan with clarity.</Text>
          </View>
          <Pressable
            testID="home-history-shortcut"
            onPress={() => router.push("/(tabs)/history")}
            style={styles.iconButton}
          >
            <Ionicons name="time-outline" size={22} color={colors.onSurface} />
          </Pressable>
        </View>

        <View style={styles.hero}>
          <View style={styles.heroIcon}>
            <Ionicons name="shield-checkmark" size={30} color={colors.onBrandPrimary} />
          </View>
          <Text style={styles.heroTitle}>A calmer way to choose</Text>
          <Text style={styles.heroBody}>
            Get an ingredient-level health score, dietary match, and better options in seconds.
          </Text>
          <Pressable
            testID="home-scan-cta"
            onPress={() => router.push("/(tabs)/scan")}
            style={styles.heroButton}
          >
            <Text style={styles.heroButtonText}>Scan a product</Text>
            <Ionicons name="scan-outline" size={18} color={colors.brandPrimary} />
          </Pressable>
        </View>

        <View style={styles.quotaCard} testID="quota-card">
          <View>
            <Text style={styles.label}>
              {entitlement?.subscribed ? "VERISCAN PLUS"
                : entitlement?.trial_active ? "FREE TRIAL"
                : entitlement?.registered ? "SCAN WALLET" : "GUEST SCANS"}
            </Text>
            <Text style={styles.quotaNumber} testID="quota-remaining">
              {entitlement?.subscribed ? "∞"
                : entitlement?.trial_active ? "∞"
                : entitlement?.registered ? (entitlement?.wallet ?? 0)
                : (entitlement?.free_remaining ?? 0)}
            </Text>
            <Text style={styles.muted}>
              {entitlement?.subscribed ? "Unlimited active"
                : entitlement?.trial_active ? `${entitlement.trial_days_remaining} days of unlimited scans`
                : entitlement?.registered ? "credits in your wallet"
                : "free scans remaining"}
            </Text>
          </View>
          <View style={styles.quotaCircle}>
            <Ionicons name="sparkles-outline" size={25} color={colors.brandPrimary} />
          </View>
        </View>

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Explore your profile</Text>
          <Pressable onPress={() => router.push("/plans")} testID="home-plans-link">
            <Text style={styles.link}>See plans</Text>
          </Pressable>
        </View>
        <View style={styles.insightRow}>
          <View style={styles.insight}>
            <Ionicons name="nutrition-outline" size={21} color={colors.brandPrimary} />
            <Text style={styles.insightTitle}>Ingredient lens</Text>
            <Text style={styles.muted}>Personalized</Text>
          </View>
          <View style={styles.insight}>
            <Ionicons name="trending-up-outline" size={21} color={colors.brandPrimary} />
            <Text style={styles.insightTitle}>Clean index</Text>
            <Text style={styles.muted}>Build over time</Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 32 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 31, fontWeight: "800", marginTop: 8 },
  iconButton: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  hero: { borderRadius: 24, backgroundColor: colors.brandPrimary, padding: 22, marginBottom: 16 },
  heroIcon: { width: 54, height: 54, borderRadius: 18, backgroundColor: colors.brandSecondary, alignItems: "center", justifyContent: "center", marginBottom: 26 },
  heroTitle: { color: colors.onBrandPrimary, fontSize: 23, fontWeight: "800" },
  heroBody: { color: colors.onBrandPrimary, opacity: 0.85, fontSize: 15, lineHeight: 22, marginTop: 8 },
  heroButton: { alignSelf: "flex-start", minHeight: 44, marginTop: 22, paddingHorizontal: 16, borderRadius: 15, backgroundColor: colors.surface, flexDirection: "row", alignItems: "center", gap: 9 },
  heroButtonText: { color: colors.brandPrimary, fontWeight: "800", fontSize: 14 },
  quotaCard: { borderRadius: 20, backgroundColor: colors.surfaceSecondary, padding: 20, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 26 },
  label: { color: colors.muted, fontSize: 11, fontWeight: "800", letterSpacing: 0.8 },
  quotaNumber: { color: colors.onSurface, fontSize: 42, fontWeight: "800", marginTop: 4 },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  quotaCircle: { width: 54, height: 54, borderRadius: 27, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionTitle: { color: colors.onSurface, fontSize: 18, fontWeight: "700" },
  link: { color: colors.brandPrimary, fontWeight: "800", fontSize: 14, paddingVertical: 10 },
  insightRow: { flexDirection: "row", gap: 12, marginTop: 14 },
  insight: { flex: 1, borderRadius: 18, backgroundColor: colors.surfaceSecondary, padding: 16, minHeight: 120 },
  insightTitle: { color: colors.onSurface, fontWeight: "700", fontSize: 15, marginTop: 18, marginBottom: 2 },
}));
