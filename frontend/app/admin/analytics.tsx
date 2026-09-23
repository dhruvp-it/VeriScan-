import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function AdminAnalyticsRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data: entitlement } = useEntitlement();
  const isAdmin = entitlement?.role === "admin";
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-analytics", 30],
    queryFn: () => api.analyticsOverview(30),
    refetchOnWindowFocus: false,
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <View style={[styles.root, { paddingTop: insets.top, justifyContent: "center", alignItems: "center", padding: 24 }]}>
        <Ionicons name="shield-outline" size={40} color={colors.brandPrimary} />
        <Text style={styles.title}>Admin only</Text>
        <Text style={styles.body}>Sign in with an admin account to see analytics.</Text>
        <Pressable testID="analytics-back-unauth" onPress={() => router.back()} style={[styles.roundButton, { marginTop: 16 }]}>
          <Ionicons name="arrow-back" size={18} color={colors.onSurface} />
        </Pressable>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="analytics-back" onPress={() => router.back()} style={styles.backRow}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
          <Text style={styles.backText}>Back</Text>
        </Pressable>
        <Pressable testID="analytics-refresh" onPress={() => refetch()} style={styles.roundButton}>
          <Ionicons name="refresh" size={18} color={colors.onSurface} />
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.eyebrow}>ANONYMOUS INSIGHTS</Text>
        <Text style={styles.title}>Analytics · last 30 days</Text>
        <Text style={styles.body}>
          Aggregate scan and retailer-click counters. No user id, email or device id is stored.
        </Text>

        {isLoading || !data ? (
          <View style={styles.loading}><ActivityIndicator color={colors.brandPrimary} /></View>
        ) : (
          <>
            <View style={styles.statsRow}>
              <StatCard label="Product scans" value={data.totals.scan} color={colors.brandPrimary} icon="scan-outline" />
              <StatCard label="Retailer taps" value={data.totals.retailer_click} color={colors.brandSecondary} icon="cart-outline" />
              <StatCard label="Contributions" value={data.totals.contribute} color={colors.info ?? colors.brandPrimary} icon="create-outline" />
            </View>

            <Text style={styles.sectionTitle}>Retailer taps by store</Text>
            {data.retailers.length === 0 ? (
              <Text style={styles.muted}>No retailer taps yet — will appear as users tap Buying options.</Text>
            ) : (
              data.retailers.map((row) => (
                <View key={row.retailer_id} style={styles.retailerRow} testID={`analytics-retailer-${row.retailer_id}`}>
                  <View style={styles.retailerIcon}>
                    <Ionicons name="storefront-outline" size={16} color={colors.brandPrimary} />
                  </View>
                  <Text style={styles.retailerName}>{row.retailer_id}</Text>
                  <View style={styles.retailerBar}>
                    <View style={[styles.retailerBarFill, { width: `${Math.min(100, (row.count / (data.retailers[0]?.count || 1)) * 100)}%` }]} />
                  </View>
                  <Text style={styles.retailerCount}>{row.count}</Text>
                </View>
              ))
            )}

            <Text style={styles.sectionTitle}>By category</Text>
            {data.categories.length === 0 ? (
              <Text style={styles.muted}>No category data yet.</Text>
            ) : (
              data.categories.map((row) => {
                const max = data.categories[0]?.total || 1;
                return (
                  <View key={row.category} style={styles.retailerRow} testID={`analytics-category-${row.category}`}>
                    <View style={styles.retailerIcon}>
                      <Ionicons name={row.category === "food" ? "nutrition-outline" : row.category === "personal_care" ? "sparkles-outline" : "flask-outline"} size={16} color={colors.brandSecondary} />
                    </View>
                    <Text style={styles.retailerName}>{row.category.replace("_", " ")}</Text>
                    <View style={styles.retailerBar}>
                      <View style={[styles.retailerBarFill, { width: `${Math.min(100, (row.total / max) * 100)}%`, backgroundColor: colors.brandSecondary }]} />
                    </View>
                    <Text style={styles.retailerCount}>{row.total}</Text>
                  </View>
                );
              })
            )}

            <Text style={styles.sectionTitle}>By country</Text>
            {data.countries.length === 0 ? (
              <Text style={styles.muted}>No country data yet — set the user's country header in-app to see this.</Text>
            ) : (
              <View style={styles.countriesGrid}>
                {data.countries.map((row) => (
                  <View key={row.country} style={styles.countryChip} testID={`analytics-country-${row.country}`}>
                    <Text style={styles.countryCode}>{row.country}</Text>
                    <Text style={styles.countryCount}>{row.count}</Text>
                  </View>
                ))}
              </View>
            )}

            <Text style={styles.sectionTitle}>Top scanned products</Text>
            {data.top_products.length === 0 ? (
              <Text style={styles.muted}>No scans in the last 30 days.</Text>
            ) : (
              data.top_products.map((prod) => (
                <View key={prod.barcode} style={styles.productRow} testID={`analytics-product-${prod.barcode}`}>
                  <View style={styles.productCopy}>
                    <Text style={styles.productName} numberOfLines={1}>{prod.name}</Text>
                    <Text style={styles.muted} numberOfLines={1}>{prod.brand} · {prod.category.replace("_", " ")} · {prod.barcode}</Text>
                  </View>
                  <Text style={styles.count}>{prod.count}</Text>
                </View>
              ))
            )}

            <Text style={styles.sectionTitle}>Daily activity</Text>
            <View style={styles.chartRow}>
              {data.daily.slice(-14).map((day) => {
                const max = Math.max(...data.daily.map((d) => d.scan + d.retailer_click), 1);
                const h = ((day.scan + day.retailer_click) / max) * 80;
                return (
                  <View key={day.date} style={styles.chartCol}>
                    <View style={[styles.chartBar, { height: Math.max(4, h), backgroundColor: colors.brandPrimary }]} />
                    <Text style={styles.chartLabel}>{day.date.slice(5)}</Text>
                  </View>
                );
              })}
            </View>
            <Text style={styles.disclaimer}>
              Export the full CSV via the admin endpoint{" "}
              <Text style={styles.link}>/api/admin/analytics/export?days=90</Text>
              {" "}with an admin bearer token.
            </Text>
          </>
        )}
        {isFetching ? <Text style={styles.muted}>Refreshing…</Text> : null}
      </ScrollView>
    </View>
  );
}

function StatCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: string }) {
  const styles = useStyles();
  return (
    <View style={styles.statCard}>
      <View style={[styles.statIcon, { backgroundColor: `${color}1A` }]}>
        <Ionicons name={icon as never} size={16} color={color} />
      </View>
      <Text style={styles.statValue}>{value.toLocaleString()}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 20, paddingVertical: 10 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  roundButton: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  scroll: { paddingHorizontal: 20, paddingBottom: 40 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1, marginTop: 8 },
  title: { color: colors.onSurface, fontSize: 26, fontWeight: "800", marginTop: 6 },
  body: { color: colors.muted, fontSize: 14, lineHeight: 21, marginTop: 10, marginBottom: 22 },
  loading: { paddingVertical: 40, alignItems: "center" },
  statsRow: { flexDirection: "row", gap: 10, marginBottom: 20 },
  statCard: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: 18, padding: 14, gap: 8 },
  statIcon: { width: 32, height: 32, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  statValue: { color: colors.onSurface, fontSize: 22, fontWeight: "800" },
  statLabel: { color: colors.muted, fontSize: 11, fontWeight: "700", letterSpacing: 0.4 },
  sectionTitle: { color: colors.onSurface, fontSize: 16, fontWeight: "800", marginTop: 8, marginBottom: 8 },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  retailerRow: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44, paddingVertical: 6 },
  retailerIcon: { width: 30, height: 30, borderRadius: 10, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  retailerName: { color: colors.onSurface, fontSize: 13, fontWeight: "700", width: 90 },
  retailerBar: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.surfaceSecondary, overflow: "hidden" },
  retailerBarFill: { height: "100%", backgroundColor: colors.brandPrimary },
  retailerCount: { color: colors.onSurface, fontSize: 13, fontWeight: "800", width: 40, textAlign: "right" },
  productRow: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 56, borderBottomWidth: 1, borderBottomColor: colors.divider },
  productCopy: { flex: 1 },
  productName: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  count: { color: colors.brandPrimary, fontSize: 16, fontWeight: "800" },
  chartRow: { flexDirection: "row", gap: 4, alignItems: "flex-end", marginTop: 8, marginBottom: 8, height: 110 },
  chartCol: { flex: 1, alignItems: "center", gap: 4 },
  chartBar: { width: "80%", borderRadius: 3, minHeight: 4 },
  chartLabel: { color: colors.muted, fontSize: 9 },
  countriesGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  countryChip: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.surfaceSecondary, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 7 },
  countryCode: { color: colors.onSurface, fontSize: 13, fontWeight: "800", letterSpacing: 0.4 },
  countryCount: { color: colors.brandPrimary, fontSize: 13, fontWeight: "800" },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 17, marginTop: 20, fontStyle: "italic" },
  link: { color: colors.brandPrimary, fontWeight: "700", fontStyle: "normal" },
}));
