import { StyleSheet, Text, View } from "react-native";

import { Product } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const TIERS: { id: string; label: string }[] = [
  { id: "low", label: "Budget" },
  { id: "affordable", label: "Fair" },
  { id: "high", label: "Premium" },
  { id: "premium", label: "Premium" },
];

const CATEGORY_LABEL: Record<string, string> = {
  food: "Category",
  supplement: "Supplement category",
  personal_care: "Personal care",
  cosmetics: "Cosmetics",
};

export function PriceBenchmark({ product }: { product: Product }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const activeIndex = product.price_tier === "high" || product.price_tier === "premium" ? 2 : product.price_tier === "low" ? 0 : 1;
  return (
    <View style={styles.card} testID="price-benchmark">
      <View style={styles.headerRow}>
        <Text style={styles.title}>Category price benchmark</Text>
        <Text style={styles.caption}>{CATEGORY_LABEL[product.category] ?? "Category"}</Text>
      </View>
      <View style={styles.spectrum}>
        {TIERS.slice(0, 3).map((tier, index) => (
          <View
            key={tier.id + index}
            style={[
              styles.segment,
              index === activeIndex && { backgroundColor: colors.brandPrimary },
            ]}
          >
            <Text style={[styles.segmentText, index === activeIndex && { color: colors.onBrandPrimary }]}>
              {tier.label}
            </Text>
          </View>
        ))}
      </View>
      {product.price_inr ? (
        <Text style={styles.priceText}>
          ₹{product.price_inr}
          {product.serving_size ? ` · ${product.serving_size}` : ""}
        </Text>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  card: { borderRadius: 20, backgroundColor: colors.surfaceSecondary, padding: 18, marginBottom: 18 },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  title: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  caption: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  spectrum: { flexDirection: "row", gap: 6, marginBottom: 12 },
  segment: { flex: 1, minHeight: 46, borderRadius: 12, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  segmentText: { color: colors.onSurfaceSecondary, fontSize: 13, fontWeight: "700" },
  priceText: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
}));
