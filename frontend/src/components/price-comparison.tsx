import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { api, CompareResponse } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export function PriceComparison({ barcode }: { barcode: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { data, isLoading } = useQuery<CompareResponse>({
    queryKey: ["compare", barcode],
    queryFn: () => api.compare(barcode),
    enabled: !!barcode,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <View style={styles.loadingBox} testID="compare-loading">
        <ActivityIndicator color={colors.brandPrimary} size="small" />
        <Text style={styles.muted}>Checking buying options…</Text>
      </View>
    );
  }
  if (!data) return null;

  const liveProducts = data.products ?? [];
  const links = data.deep_links ?? [];
  const liveSet = new Set(liveProducts.map((p) => p.retailer));
  const linkOnly = links.filter((l) => !liveSet.has(l.name));

  return (
    <View testID="price-comparison">
      <View style={styles.rowBetween}>
        <Text style={styles.sectionTitle}>Buying options</Text>
        <View style={[styles.liveChip, !data.live_enabled && styles.searchChip]}>
          <View style={[styles.liveDot, { backgroundColor: data.live_enabled ? colors.success : colors.muted }]} />
          <Text style={styles.liveChipText}>{data.live_enabled ? "Live prices" : "Search links"}</Text>
        </View>
      </View>

      {liveProducts.map((item, index) => (
        <Pressable
          key={`${item.retailer}-${index}`}
          testID={`live-price-${item.retailer.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
          onPress={() => Linking.openURL(item.url)}
          style={styles.row}
        >
          <View style={styles.rowIcon}>
            <Ionicons name="pricetag-outline" size={17} color={colors.brandPrimary} />
          </View>
          <View style={styles.rowCopy}>
            <Text style={styles.rowTitle} numberOfLines={1}>{item.retailer}</Text>
            <Text style={styles.muted} numberOfLines={1}>{item.title}</Text>
          </View>
          <View style={styles.priceCol}>
            {item.price_inr != null ? (
              <Text style={styles.price}>₹{Math.round(item.price_inr).toLocaleString("en-IN")}</Text>
            ) : (
              <Text style={styles.muted}>See price</Text>
            )}
            {item.mrp_inr != null && item.price_inr != null && item.mrp_inr > item.price_inr ? (
              <Text style={styles.mrp}>₹{Math.round(item.mrp_inr).toLocaleString("en-IN")}</Text>
            ) : null}
          </View>
          <Ionicons name="open-outline" size={17} color={colors.muted} />
        </Pressable>
      ))}

      {linkOnly.length > 0 ? (
        <>
          {liveProducts.length > 0 ? (
            <Text style={[styles.muted, styles.compareLabel]}>Compare on</Text>
          ) : null}
          {linkOnly.map((link) => (
            <Pressable
              key={link.id}
              testID={`retailer-link-${link.id}`}
              onPress={() => Linking.openURL(link.url)}
              style={styles.row}
            >
              <View style={[styles.rowIcon, { backgroundColor: `${link.color}1A` }]}>
                <Ionicons name={link.icon as never} size={17} color={link.color} />
              </View>
              <View style={styles.rowCopy}>
                <Text style={styles.rowTitle}>{link.name}</Text>
                <Text style={styles.muted}>Opens search results</Text>
              </View>
              <Ionicons name="open-outline" size={17} color={colors.muted} />
            </Pressable>
          ))}
        </>
      ) : null}

      <Text style={styles.disclaimer}>
        Prices and availability are set by the retailer and may vary by city. Verify on the store before buying.
      </Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  loadingBox: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 18 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 4 },
  sectionTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  liveChip: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.surfaceSecondary, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 5 },
  searchChip: { backgroundColor: colors.surfaceSecondary },
  liveDot: { width: 7, height: 7, borderRadius: 4 },
  liveChipText: { color: colors.onSurfaceSecondary, fontSize: 11, fontWeight: "700" },
  row: { minHeight: 64, flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: colors.divider, gap: 11 },
  rowIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowCopy: { flex: 1 },
  rowTitle: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  priceCol: { alignItems: "flex-end" },
  price: { color: colors.onSurface, fontSize: 15, fontWeight: "800" },
  mrp: { color: colors.muted, fontSize: 12, textDecorationLine: "line-through" },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  compareLabel: { marginTop: 14, marginBottom: 2, fontWeight: "700", textTransform: "uppercase", fontSize: 11, letterSpacing: 0.6 },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 17, marginTop: 12, fontStyle: "italic" },
}));
