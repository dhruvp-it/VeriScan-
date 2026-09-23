import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api, Product } from "@/src/lib/api";
import { scoreColor } from "@/src/lib/scoring";
import { makeStyles, useTheme } from "@/src/theme";

export function BetterForYou({ barcode }: { barcode: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { data, isLoading } = useQuery<Product[]>({
    queryKey: ["alternatives", barcode],
    queryFn: () => api.alternatives(barcode),
    initialData: [],
  });

  if (isLoading || !data || data.length === 0) return null;

  return (
    <View style={styles.wrap} testID="better-for-you">
      <View style={styles.header}>
        <Text style={styles.title}>Better for you</Text>
        <Text style={styles.caption}>Cleaner in the same category</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {data.map((alt) => (
          <Pressable
            key={alt.barcode}
            testID={`alt-${alt.barcode}`}
            onPress={() => router.push({ pathname: "/product/[barcode]", params: { barcode: alt.barcode } })}
            style={styles.card}
          >
            <View style={styles.image}>
              {alt.image_url
                ? <Image source={{ uri: alt.image_url }} style={StyleSheet.absoluteFill} contentFit="cover" />
                : <Ionicons name={alt.category === "food" ? "nutrition" : "flask"} size={32} color={colors.brandPrimary} />}
            </View>
            <View style={styles.body}>
              <Text style={styles.brand}>{alt.brand}</Text>
              <Text style={styles.name} numberOfLines={2}>{alt.name}</Text>
              <View style={styles.scoreRow}>
                <View style={[styles.scoreDot, { backgroundColor: scoreColor(alt.overall_health_score, colors) }]} />
                <Text style={[styles.score, { color: scoreColor(alt.overall_health_score, colors) }]}>
                  {Math.round(alt.overall_health_score)}/100
                </Text>
                <Text style={styles.match}>· {alt.personal_match}% match</Text>
              </View>
            </View>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  wrap: { marginTop: 4, marginBottom: 18 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  title: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  caption: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  scroll: { gap: 12, paddingRight: 4 },
  card: { width: 200, borderRadius: 20, backgroundColor: colors.surfaceSecondary, overflow: "hidden", flexShrink: 0 },
  image: { height: 110, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  body: { padding: 12 },
  brand: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 0.5 },
  name: { color: colors.onSurface, fontSize: 14, fontWeight: "700", marginTop: 4, minHeight: 38 },
  scoreRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 8 },
  scoreDot: { width: 10, height: 10, borderRadius: 5 },
  score: { fontSize: 13, fontWeight: "800" },
  match: { color: colors.muted, fontSize: 12 },
}));
