import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, WatchlistItem } from "@/src/lib/api";
import { scoreColor } from "@/src/lib/scoring";
import { makeStyles, useTheme } from "@/src/theme";

export default function WatchlistRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data, isLoading } = useQuery<WatchlistItem[]>({
    queryKey: ["watchlist"], queryFn: () => api.watchlist(), initialData: [],
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="watchlist-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Watchlist</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : !data || data.length === 0 ? (
          <View style={styles.empty} testID="watchlist-empty">
            <Ionicons name="heart-outline" size={40} color={colors.brandPrimary} />
            <Text style={styles.emptyTitle}>Save cleaner picks</Text>
            <Text style={styles.emptyBody}>
              Tap the heart on a product to save it. We&apos;ll email and notify you when a healthier version launches.
            </Text>
          </View>
        ) : (
          data.map((item) => (
            <Pressable
              key={item.barcode}
              testID={`watch-${item.barcode}`}
              onPress={() => router.push({ pathname: "/product/[barcode]", params: { barcode: item.barcode } })}
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
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  scroll: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 32 },
  empty: { alignItems: "center", justifyContent: "center", padding: 45, gap: 12 },
  emptyTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  emptyBody: { color: colors.muted, textAlign: "center", fontSize: 13, lineHeight: 20 },
  row: { minHeight: 72, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: 1, borderBottomColor: colors.divider },
  artwork: { width: 44, height: 44, borderRadius: 14, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowCopy: { flex: 1 },
  itemName: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  muted: { color: colors.muted, fontSize: 13 },
  score: { fontSize: 17, fontWeight: "800" },
}));
