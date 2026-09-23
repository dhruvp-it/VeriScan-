import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { IngredientSheet } from "@/src/components/ingredient-sheet";
import { NutritionCard } from "@/src/components/nutrition-card";
import { PriceBenchmark } from "@/src/components/price-benchmark";
import { api, Ingredient, Product } from "@/src/lib/api";
import { scoreColor, scoreLabel } from "@/src/lib/scoring";
import { makeStyles, useTheme } from "@/src/theme";

export default function ProductRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { barcode } = useLocalSearchParams<{ barcode: string }>();
  const [selected, setSelected] = useState<Ingredient | null>(null);
  const { data: product, isLoading, error } = useQuery<Product>({
    queryKey: ["product", barcode],
    queryFn: () => api.lookup(barcode as string),
    enabled: !!barcode,
    staleTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  });

  if (isLoading || !product) {
    return (
      <View style={[styles.center, { paddingTop: insets.top }]} testID="product-loading">
        {error ? (
          <>
            <Text style={styles.errorText}>{(error as Error).message}</Text>
            <Pressable onPress={() => router.back()} style={styles.smallButton}>
              <Text style={styles.smallButtonText}>Back</Text>
            </Pressable>
          </>
        ) : (
          <>
            <ActivityIndicator color={colors.brandPrimary} size="large" />
            <Text style={styles.muted}>Analyzing ingredients…</Text>
          </>
        )}
      </View>
    );
  }

  const tone = scoreColor(product.overall_health_score, colors);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Pressable testID="product-back" onPress={() => router.back()} style={styles.backRow}>
          <Ionicons name="arrow-back" size={21} color={colors.onSurface} />
          <Text style={styles.backText}>Back</Text>
        </Pressable>

        <View style={styles.hero}>
          <View style={styles.artwork}>
            {product.image_url ? (
              <Image source={{ uri: product.image_url }} style={styles.artworkImage} contentFit="cover" />
            ) : (
              <Ionicons
                name={product.category === "food" ? "nutrition" : "flask"}
                size={46}
                color={colors.brandPrimary}
              />
            )}
          </View>
          <Text style={styles.brand} testID="product-brand">{product.brand}</Text>
          <Text style={styles.name} testID="product-name">{product.name}</Text>
          <Text style={styles.muted}>{product.serving_size} · {product.category.replace("_", " ")}</Text>
          <View style={styles.badgeRow}>
            <View style={styles.badge}>
              <Ionicons name="leaf" size={13} color={colors.success} />
              <Text style={styles.badgeText}>
                {product.dietary_type === "not_applicable" ? "Personal care" : product.dietary_type}
              </Text>
            </View>
            <View style={styles.badge}>
              <Ionicons name="location-outline" size={13} color={colors.info} />
              <Text style={styles.badgeText}>{product.origin_country}</Text>
            </View>
            <View style={styles.badge}>
              <Ionicons name="calendar-outline" size={13} color={colors.muted} />
              <Text style={styles.badgeText}>Since {product.first_detected_year}</Text>
            </View>
          </View>
        </View>

        <View style={styles.scoreCard} testID="score-card">
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>HOLISTIC HEALTH SCORE</Text>
            <Text style={[styles.scoreNumber, { color: tone }]} testID="score-value">
              {Math.round(product.overall_health_score)}
            </Text>
            <Text style={styles.muted}>{scoreLabel(product.overall_health_score)} · out of 100</Text>
          </View>
          <View style={[styles.ring, { borderColor: tone }]}>
            <Text style={[styles.ringNumber, { color: tone }]} testID="match-value">
              {product.personal_match}%
            </Text>
            <Text style={styles.ringLabel}>match</Text>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Why this score?</Text>
          <Text style={styles.body}>
            {product.description} Our index weighs every listed ingredient and lower-scoring items are penalized more strongly.
          </Text>
          <Text style={styles.disclaimer}>
            Date of first appearance is estimated based on global web registry logs and retail listings. Analysis is informational, not medical advice.
          </Text>
        </View>

        {product.nutrition_per_100g ? (
          <NutritionCard nutrition={product.nutrition_per_100g} servingSize={product.serving_size} />
        ) : null}

        <PriceBenchmark product={product} />

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Ingredient breakdown</Text>
          <Text style={styles.muted}>{product.ingredients.length} listed</Text>
        </View>
        {product.ingredients.map((ingredient) => (
          <Pressable
            key={ingredient.name}
            testID={`ingredient-row-${ingredient.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            onPress={() => setSelected(ingredient)}
            style={styles.ingredientRow}
          >
            <View style={[styles.scoreDot, { backgroundColor: scoreColor(ingredient.score, colors) }]} />
            <View style={styles.ingredientCopy}>
              <Text style={styles.ingredientName}>{ingredient.name}</Text>
              <Text style={styles.muted}>{ingredient.function}</Text>
            </View>
            <Text style={[styles.ingredientScore, { color: scoreColor(ingredient.score, colors) }]}>
              {ingredient.score}
            </Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        ))}

        {product.retailers.length > 0 ? (
          <>
            <View style={styles.rowBetween}>
              <Text style={styles.sectionTitle}>Buying options</Text>
              <Text style={styles.muted}>INR</Text>
            </View>
            {product.retailers.map((retailer) => (
              <Pressable
                key={retailer.name}
                testID={`retailer-${retailer.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                onPress={() => Linking.openURL(retailer.url)}
                style={styles.retailerRow}
              >
                <View style={styles.retailerIcon}>
                  <Ionicons name="bag-outline" size={18} color={colors.brandPrimary} />
                </View>
                <View style={styles.retailerCopy}>
                  <Text style={styles.ingredientName}>{retailer.name}</Text>
                  <Text style={styles.muted}>Live price</Text>
                </View>
                <Text style={styles.price}>₹{retailer.price}</Text>
                <Ionicons name="open-outline" size={17} color={colors.muted} />
              </Pressable>
            ))}
          </>
        ) : null}

        <Pressable
          testID="product-contribute"
          onPress={() => router.push({ pathname: "/contribute/[barcode]", params: { barcode: product.barcode } })}
          style={styles.outlineButton}
        >
          <Ionicons name="add-circle-outline" size={19} color={colors.brandPrimary} />
          <Text style={styles.outlineText}>Contribute a correction</Text>
        </Pressable>
      </ScrollView>
      <IngredientSheet ingredient={selected} onClose={() => setSelected(null)} />
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 14, backgroundColor: colors.surface },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, marginBottom: 12 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  hero: { alignItems: "center", paddingBottom: 22 },
  artwork: { width: 112, height: 112, borderRadius: 32, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: 16, overflow: "hidden" },
  artworkImage: { width: "100%", height: "100%" },
  brand: { color: colors.brandPrimary, fontSize: 13, fontWeight: "800", letterSpacing: 0.6 },
  name: { color: colors.onSurface, fontSize: 26, fontWeight: "800", textAlign: "center", marginTop: 5 },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8, marginTop: 14 },
  badge: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, paddingHorizontal: 11, paddingVertical: 8, flexDirection: "row", gap: 5, alignItems: "center" },
  badgeText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: "700" },
  scoreCard: { borderRadius: 22, backgroundColor: colors.surfaceSecondary, padding: 20, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 14 },
  label: { color: colors.muted, fontSize: 11, fontWeight: "800", letterSpacing: 0.8 },
  scoreNumber: { fontSize: 45, fontWeight: "800", marginTop: 3 },
  ring: { width: 82, height: 82, borderRadius: 41, borderWidth: 5, alignItems: "center", justifyContent: "center", marginLeft: 16 },
  ringNumber: { fontSize: 20, fontWeight: "800" },
  ringLabel: { color: colors.muted, fontSize: 11 },
  card: { borderRadius: 20, backgroundColor: colors.surfaceSecondary, padding: 18, marginBottom: 18 },
  cardTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800", marginBottom: 7 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21 },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 17, marginTop: 12, fontStyle: "italic" },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 4 },
  sectionTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  ingredientRow: { minHeight: 68, flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: colors.divider, gap: 11 },
  scoreDot: { width: 10, height: 10, borderRadius: 5 },
  ingredientCopy: { flex: 1 },
  ingredientName: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  ingredientScore: { fontWeight: "800", fontSize: 17 },
  retailerRow: { minHeight: 68, flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: colors.divider, gap: 11 },
  retailerIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  retailerCopy: { flex: 1 },
  price: { color: colors.onSurface, fontSize: 15, fontWeight: "800" },
  outlineButton: { minHeight: 48, borderRadius: 16, borderWidth: 1, borderColor: colors.brandPrimary, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginTop: 22 },
  outlineText: { color: colors.brandPrimary, fontSize: 14, fontWeight: "800" },
  errorText: { color: colors.error, fontSize: 14, textAlign: "center", paddingHorizontal: 24 },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 16, marginTop: 10 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
}));
