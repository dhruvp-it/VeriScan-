import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const CARDS: { id: string; label: string; icon: keyof typeof Ionicons.glyphMap; path: string }[] = [
  { id: "users", label: "Users", icon: "people-outline", path: "/admin/users" },
  { id: "support", label: "Support tickets", icon: "chatbubble-ellipses-outline", path: "/admin/support" },
  { id: "reports", label: "Data reports", icon: "flag-outline", path: "/admin/reports" },
  { id: "payments", label: "Payments & refunds", icon: "card-outline", path: "/admin/payments" },
  { id: "duplicates", label: "Merge duplicates", icon: "git-merge-outline", path: "/admin/duplicates" },
  { id: "analytics", label: "Anonymous analytics", icon: "stats-chart-outline", path: "/admin/analytics" },
  { id: "pricing", label: "Country pricing", icon: "cash-outline", path: "/admin/pricing" },
  { id: "promos", label: "Promo codes", icon: "pricetag-outline", path: "/admin/promocodes" },
  { id: "admin-profile", label: "Admin profile & security", icon: "person-circle-outline", path: "/admin/profile" },
  { id: "launch-offer", label: "Launch offer", icon: "rocket-outline", path: "/admin/launch-offer" },
];

export default function AdminHome() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data: entitlement } = useEntitlement();
  const isAdmin = entitlement?.role === "admin";

  const { data: overview, isLoading } = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () => api.adminOverview(),
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <View style={[styles.root, { paddingTop: insets.top, justifyContent: "center", alignItems: "center", padding: 24 }]}>
        <Ionicons name="shield-outline" size={40} color={colors.brandPrimary} />
        <Text style={styles.title}>Admin only</Text>
        <Text style={styles.body}>Sign in with an admin account to continue.</Text>
        <Pressable onPress={() => router.back()} style={styles.smallButton}>
          <Text style={styles.smallButtonText}>Back</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Admin</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading || !overview ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (
          <View style={styles.statsRow}>
            <Stat label="Users" value={overview.users} />
            <Stat label="Suspended" value={overview.suspended} tone={colors.warning} />
            <Stat label="Open tickets" value={overview.open_tickets} />
            <Stat label="Open reports" value={overview.open_reports} tone={colors.error} />
            <Stat label="Products" value={overview.products} />
            <Stat label="Pending" value={overview.contributions_pending} />
          </View>
        )}
        {CARDS.map((card) => (
          <Pressable
            key={card.id} testID={`admin-nav-${card.id}`}
            onPress={() => router.push(card.path as never)} style={styles.card}
          >
            <View style={styles.cardIcon}>
              <Ionicons name={card.icon} size={20} color={colors.brandPrimary} />
            </View>
            <Text style={styles.cardLabel}>{card.label}</Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  const styles = useStyles();
  return (
    <View style={styles.stat}>
      <Text style={[styles.statValue, tone ? { color: tone } : null]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 20, fontWeight: "800" },
  body: { color: colors.onSurfaceSecondary, textAlign: "center", fontSize: 14, marginTop: 6 },
  scroll: { padding: 20, gap: 10 },
  statsRow: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 8 },
  stat: { flexBasis: "48%", flexGrow: 1, backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14 },
  statValue: { color: colors.onSurface, fontSize: 24, fontWeight: "800" },
  statLabel: { color: colors.muted, fontSize: 12, fontWeight: "700", marginTop: 4 },
  card: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, minHeight: 60 },
  cardIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  cardLabel: { flex: 1, color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, paddingHorizontal: 18, alignItems: "center", justifyContent: "center", marginTop: 14 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: "800" },
}));
