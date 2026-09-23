import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Product } from "@/src/lib/api";
import { scoreColor } from "@/src/lib/scoring";
import { makeStyles, useTheme } from "@/src/theme";

export default function HistoryTab() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<{ product: Product; scanned_at: string }[]>({
    queryKey: ["history"],
    queryFn: () => api.history(),
    initialData: [],
  });

  const open = (item: { product: Product }) => {
    queryClient.setQueryData(["product", item.product.barcode], item.product);
    router.push({ pathname: "/product/[barcode]", params: { barcode: item.product.barcode } });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.eyebrow}>YOUR LIBRARY</Text>
            <Text style={styles.title}>Scan history</Text>
          </View>
          <Ionicons name="bookmark-outline" size={23} color={colors.brandPrimary} />
        </View>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : !data || data.length === 0 ? (
          <View style={styles.empty} testID="history-empty">
            <Ionicons name="scan-outline" size={40} color={colors.brandPrimary} />
            <Text style={styles.cardTitle}>No scans yet</Text>
            <Text style={styles.muted}>Your product story will appear here after your first scan.</Text>
            <Pressable onPress={() => router.push("/(tabs)/scan")} style={styles.cta}>
              <Text style={styles.ctaText}>Scan first product</Text>
            </Pressable>
          </View>
        ) : (
          data.map((item, index) => (
            <Pressable
              key={`${item.product.id}-${index}`}
              testID={`history-row-${item.product.barcode}`}
              onPress={() => open(item)}
              style={styles.row}
            >
              <View style={styles.artwork}>
                <Ionicons
                  name={item.product.category === "food" ? "nutrition-outline" : "flask-outline"}
                  size={22}
                  color={colors.brandPrimary}
                />
              </View>
              <View style={styles.rowCopy}>
                <Text style={styles.itemName}>{item.product.name}</Text>
                <Text style={styles.muted}>{item.product.brand}</Text>
              </View>
              <Text style={[styles.score, { color: scoreColor(item.product.overall_health_score, colors) }]}>
                {Math.round(item.product.overall_health_score)}
              </Text>
              <Ionicons name="chevron-forward" size={17} color={colors.muted} />
            </Pressable>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 32 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 22 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 27, fontWeight: "800", marginTop: 8 },
  empty: { alignItems: "center", justifyContent: "center", padding: 45, gap: 12 },
  cardTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19, textAlign: "center" },
  cta: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 18, marginTop: 8 },
  ctaText: { color: colors.onBrandPrimary, fontWeight: "800", fontSize: 14 },
  row: { minHeight: 76, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: 1, borderBottomColor: colors.divider },
  artwork: { width: 44, height: 44, borderRadius: 14, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowCopy: { flex: 1 },
  itemName: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  score: { fontSize: 18, fontWeight: "800" },
}));
